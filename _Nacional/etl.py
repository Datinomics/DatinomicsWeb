# -*- coding: utf-8 -*-
"""
ETL parametrizado de precios. Lee un <provincia>_full.xlsx (relevamiento) y
para cada tienda usa la columna 'Plataforma' para decidir que scraper correr.
Si esta vacia, hace auto-detect. Respeta cadenas_nacionales.csv (no re-scrapea
masters). Salida: un xlsx por rubro, una hoja por local, columnas SKU/Nombre/
Precio/Fecha/Categoria. Resumable.

Uso:
  py etl.py <provincia>                 # ej: CABA, Buenos-Aires
  py etl.py <provincia> --rubro Farmacias
  py etl.py <provincia> --excel ruta.xlsx     # override del input
  py etl.py todas                       # cola secuencial por todas las del registro
  py etl.py todas --paralelo 3          # 3 provincias a la vez
"""
import argparse
import datetime
import os
import re
import socket
import subprocess
import sys
import time

import pandas as pd

# scrapers como paquete
from scrapers import dispatch, diag

socket.setdefaulttimeout(30)
HOY = datetime.date.today().isoformat()
RAIZ = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
NACIONALES_CSV = os.path.join(os.path.dirname(__file__), "cadenas_nacionales.csv")


def cargar_provincias():
    from relevar_provincia import PROVINCIAS
    provs = {k: (v[0], v[1]) for k, v in PROVINCIAS.items()}
    # Corrientes se relevó con scripts propios y no está en PROVINCIAS
    provs.setdefault("Corrientes", ("Corrientes", "NEA"))
    return provs


def cargar_nacionales():
    if not os.path.exists(NACIONALES_CSV):
        return {}
    df = pd.read_csv(NACIONALES_CSV)
    return {str(r["Dominio"]).lower().strip(): (r["Empresa"], r.get("MasterScrape", ""))
            for _, r in df.iterrows()}


def dominio(u):
    try:
        return u.split("//")[-1].split("/")[0].lower().replace("www.", "")
    except Exception:
        return str(u).lower()


def rubro_de(sector):
    s = str(sector).lower()
    tabla = [
        (("supermercado",), "Supermercados"),
        (("mayorista", "distribuidora"), "Mayoristas"),
        (("farmacia",), "Farmacias"),
        (("ferreteria", "construccion", "pintureria", "corralon", "sanitario", "griferia", "pintura"), "Ferreteria-Construccion"),
        (("electro", "tecnolog", "computacion", "celular", "telefonia"), "Electro-Tecnologia"),
        (("indumentaria", "calzado", "deporte", "ropa", "lenceria"), "Indumentaria-Calzado-Deportes"),
        (("perfumeria", "cosmetica", "belleza", "maquillaje"), "Perfumeria-Cosmetica"),
        (("muebles", "hogar", "bazar", "colchon", "deco", "blanqueria", "iluminacion"), "Muebles-Hogar-Bazar"),
        (("libreria", "jugueteria", "papeleria", "articulos escolares", "cotillon"), "Libreria-Jugueteria"),
        (("carniceria", "polleria", "pescaderia"), "Carnicerias-Pollerias"),
        (("panaderia", "confiteria", "pasteleria"), "Panaderias-Confiterias"),
        (("verduleria", "fruteria"), "Verdulerias"),
        (("dietetica",), "Dieteticas"),
        (("cerveza",), "Cervezas-Cervecerias"),
        (("bebida", "vinoteca"), "Bebidas-Vinotecas"),
        (("mascota", "veterinaria", "petshop"), "Mascotas-Veterinarias"),
        (("optica", "salud"), "Opticas-Salud"),
        (("joyeria", "relojeria", "regalo"), "Joyerias-Regalos"),
        (("auto", "moto", "repuesto", "neumatico", "bicicleta", "herramientas"), "Autos-Motos-Repuestos"),
        (("floreria", "vivero"), "Florerias-Viveros"),
        (("instrumento", "musica"), "Instrumentos-Musica"),
    ]
    for claves, nombre in tabla:
        if any(k in s for k in claves):
            return nombre
    return "Otros"


def sheet_name(s, usados):
    s = re.sub(r"[\[\]:\*\?/\\]", "", str(s))[:28].strip() or "Local"
    n, base = s, s
    k = 2
    while n in usados:
        n = f"{base[:26]}_{k}"; k += 1
    usados.add(n)
    return n


def cargar_hojas_previas(out_path):
    if not os.path.exists(out_path):
        return {}
    try:
        xl = pd.ExcelFile(out_path)
        return {s: xl.parse(s) for s in xl.sheet_names if s != "Resumen"}
    except Exception:
        return {}


def correr_provincia(folder, rubro_filtro="", limite=0, skip_nacional=True, excel=None):
    provs = cargar_provincias()
    if folder not in provs:
        print(f"ERROR: {folder} no esta en PROVINCIAS", flush=True)
        return
    display, region = provs[folder]
    full_xlsx = excel or os.path.join(RAIZ, region, folder, "excels", f"{folder}_full.xlsx")
    out_dir = os.path.join(RAIZ, region, folder, "excels")
    if not os.path.exists(full_xlsx):
        print(f"ERROR: no encontre {full_xlsx}", flush=True)
        return

    nacionales = cargar_nacionales() if skip_nacional else {}
    print(f"\n#### {display} ({region}) - {full_xlsx}", flush=True)

    hojas = pd.ExcelFile(full_xlsx).sheet_names
    hoja = "Tiendas con web" if "Tiendas con web" in hojas else hojas[0]
    df = pd.read_excel(full_xlsx, sheet_name=hoja).fillna("")
    df = df[df["Tienda online"].astype(str).str.contains("Si|Probable", case=False, na=False)]
    df["rubro"] = df["Sector"].map(rubro_de)
    df["dom"] = df["URL"].map(dominio)
    if "Plataforma" not in df.columns:
        df["Plataforma"] = ""

    total = len(df)
    if skip_nacional:
        es_nac = df["dom"].apply(lambda d: any(d == nd or d.endswith("." + nd) for nd in nacionales))
        skips = int(es_nac.sum())
        df = df[~es_nac]
        print(f"  Total: {total} | salteadas cadenas nacionales: {skips} | a scrapear: {len(df)}", flush=True)
    else:
        print(f"  Total: {total} (sin skip)", flush=True)

    if rubro_filtro:
        df = df[df["rubro"].str.contains(rubro_filtro, case=False)]
        print(f"  Filtro rubro '{rubro_filtro}': {len(df)}", flush=True)

    for rubro, grupo in df.groupby("rubro"):
        locales = grupo.drop_duplicates("dom")
        if limite:
            locales = locales.head(limite)
        out_path = os.path.join(out_dir, f"precios_{rubro}_{folder}.xlsx")
        previas = cargar_hojas_previas(out_path)
        usados = set(previas.keys())
        nuevos = []
        print(f"\n===== {rubro} ({len(locales)} locales, {len(previas)} ya hechos) =====", flush=True)
        for _, r in locales.iterrows():
            nombre = str(r["Empresa"])[:40]
            plat_excel = str(r.get("Plataforma", "")).strip()
            if sheet_name(nombre, set(usados)) in usados:
                continue
            diag.reset()
            try:
                filas, plat = dispatch(plat_excel, r["URL"], nombre)
            except Exception as e:
                filas, plat = [], f"error:{type(e).__name__}"
            con = sum(1 for f in filas if f.get("Precio"))
            origen = f"({plat_excel}->{plat})" if plat_excel else f"({plat})"
            motivo = f" [{diag.ultimo()}]" if not filas and diag.ultimo() else ""
            print(f"  {nombre[:34]:34s} {origen:30s} {len(filas):5d} prod ({con} c/precio){motivo}", flush=True)
            time.sleep(0.4)
            if filas:
                d = pd.DataFrame(filas).reindex(columns=["SKU", "Nombre", "Precio", "Fecha", "Categoria"])
                sh = sheet_name(nombre, usados)
                nuevos.append((sh, d))
        if not nuevos and not previas:
            print("  (sin datos)", flush=True)
            continue
        todas = list(previas.items()) + nuevos
        try:
            with pd.ExcelWriter(out_path, engine="openpyxl") as xl:
                resumen = pd.DataFrame([(n, len(d), int(d["Precio"].notna().sum()) if "Precio" in d.columns else 0)
                                        for n, d in todas], columns=["Local", "Productos", "Con precio"])
                resumen.to_excel(xl, sheet_name="Resumen", index=False)
                for nombre, d in todas:
                    d.to_excel(xl, sheet_name=nombre[:31], index=False)
            print(f"  -> {out_path} ({len(todas)} locales, +{len(nuevos)} nuevos)", flush=True)
        except Exception as e:
            print(f"  ERROR guardando {out_path}: {e}", flush=True)


def correr_todas(paralelo=1, skip_nacional=True):
    provs = list(cargar_provincias().keys())
    if paralelo <= 1:
        for p in provs:
            correr_provincia(p, skip_nacional=skip_nacional)
        return
    # paralelo: spawnear N subprocesos
    import concurrent.futures as cf
    def runner(p):
        return subprocess.run([sys.executable, "-X", "utf8", __file__, p,
                               "--skip-nacional", "1" if skip_nacional else "0"], check=False)
    with cf.ThreadPoolExecutor(max_workers=paralelo) as ex:
        list(ex.map(runner, provs))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("provincia", help="Folder (CABA, Buenos-Aires, ...) o 'todas'")
    ap.add_argument("--rubro", default="", help="substring de rubro a filtrar")
    ap.add_argument("--limite", type=int, default=0, help="max locales por rubro")
    ap.add_argument("--skip-nacional", type=int, default=1, help="1=saltea masters")
    ap.add_argument("--excel", default="", help="ruta a un xlsx custom")
    ap.add_argument("--paralelo", type=int, default=1, help="para 'todas': cuantas a la vez")
    args = ap.parse_args()
    if args.provincia.lower() == "todas":
        correr_todas(paralelo=args.paralelo, skip_nacional=bool(args.skip_nacional))
    else:
        correr_provincia(args.provincia, rubro_filtro=args.rubro, limite=args.limite,
                         skip_nacional=bool(args.skip_nacional),
                         excel=args.excel or None)


if __name__ == "__main__":
    main()
