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
  py etl.py <provincia> --workers 16 --tope-seg 900   # 16 locales a la vez, max 15 min c/u
"""
import argparse
import concurrent.futures as cf
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
from ubicaciones import FOLDER_A_LETRA

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
    # Excel no distingue mayusculas en nombres de hoja ("Pinturerias" == "PINTURERIAS")
    while n.lower() in {u.lower() for u in usados}:
        n = f"{base[:26]}_{k}"; k += 1
    usados.add(n)
    return n


def limpiar_nombre(s):
    """Nombre de hoja base (sin el sufijo _2, _3 que agrega sheet_name)."""
    return re.sub(r"[\[\]:\*\?/\\]", "", str(s))[:28].strip() or "Local"


def cargar_hojas_previas(out_path):
    """Devuelve (hojas, dominios_por_hoja) de un precios_*.xlsx ya existente.
    Si el archivo existe pero no se puede leer, lanza la excepcion: mejor no
    tocarlo que pisarlo con un Excel vacio."""
    if not os.path.exists(out_path):
        return {}, {}
    doms = {}
    # "with" cierra el archivo: en Windows, si queda abierto, despues no se puede reemplazar
    with pd.ExcelFile(out_path) as xl:
        hojas = {s: xl.parse(s) for s in xl.sheet_names if s != "Resumen"}
        if "Resumen" in xl.sheet_names:
            res = xl.parse("Resumen").fillna("")
            if "Dominio" in res.columns:
                doms = {str(r["Local"]): str(r["Dominio"]) for _, r in res.iterrows() if r["Dominio"]}
    # Excels viejos: openpyxl renombro hojas que chocaban sin distinguir mayusculas
    # ("...PINTURERIAS" -> "...PINTURERIAS1"); reasignar el dominio a la hoja real
    for local in [l for l in doms if l not in hojas]:
        real = next((h for h in hojas if h not in doms and h.lower().startswith(local.lower())), None)
        dom = doms.pop(local)
        if real:
            doms[real] = dom
    return hojas, doms


def guardar_rubro(out_path, hojas, doms):
    """Escribe el Excel del rubro de forma atomica (tmp + replace), asi un corte
    a mitad de la escritura no deja el archivo corrupto."""
    tmp = out_path + ".tmp.xlsx"
    with pd.ExcelWriter(tmp, engine="openpyxl") as xl:
        resumen = pd.DataFrame(
            [(n, doms.get(n, ""), len(d), _con_precio(d))
             for n, d in hojas.items()],
            columns=["Local", "Dominio", "Productos", "Con precio"])
        resumen.to_excel(xl, sheet_name="Resumen", index=False)
        for nombre, d in hojas.items():
            d.to_excel(xl, sheet_name=nombre[:31], index=False)
    os.replace(tmp, out_path)


GUARDAR_CADA_SEG = 60  # checkpoint: reescribir el Excel como mucho una vez por minuto


def master_de(dom, nacionales):
    """Provincia master de una cadena nacional, o None si no es cadena."""
    for nd, (_, master) in nacionales.items():
        if dom == nd or dom.endswith("." + nd):
            return str(master or "").strip()
    return None


def quitar_dominios(out_dir, folder, doms):
    """Saca de los precios_<Rubro>_<Folder>.xlsx scrapeados las hojas de esos dominios
    (ej. cadenas que pasan a tomar precios de SEPA)."""
    import glob
    for f in glob.glob(os.path.join(out_dir, f"precios_*_{folder}.xlsx")):
        if os.path.basename(f).startswith("precios_SEPA_"):
            continue
        hojas, ds = cargar_hojas_previas(f)
        sacar = [h for h, d in ds.items() if d in doms]
        if sacar:
            for h in sacar:
                hojas.pop(h, None)
                ds.pop(h, None)
            guardar_rubro(f, hojas, ds)
            print(f"  {os.path.basename(f)}: quitadas {sacar} (pasan a SEPA)", flush=True)


def productos_por_dominio(incluir_sepa=False):
    """dominio -> (productos, con precio, provincia) segun el Resumen de todos los
    precios_*.xlsx que existen en disco (los de SEPA solo si incluir_sepa)."""
    import glob
    out = {}
    for f in glob.glob(os.path.join(RAIZ, "*", "*", "excels", "precios_*.xlsx")):
        if not incluir_sepa and os.path.basename(f).startswith("precios_SEPA_"):
            continue
        prov = os.path.basename(os.path.dirname(os.path.dirname(f)))
        try:
            res = pd.read_excel(f, sheet_name="Resumen")
        except Exception:
            continue
        if "Dominio" not in res.columns:
            continue
        for _, r in res.iterrows():
            d = str(r["Dominio"])
            if d and (d not in out or r["Productos"] > out[d][0]):
                out[d] = (int(r["Productos"]), int(r.get("Con precio", 0) or 0), prov)
    return out


def _scrapear_local(r, tope_seg):
    """Corre en un hilo del pool. Devuelve (resultado, filas)."""
    nombre = str(r["Empresa"])[:40]
    plat_excel = str(r.get("Plataforma", "")).strip()
    diag.reset()
    diag.tope(tope_seg)
    t0 = time.time()
    try:
        filas, plat = dispatch(plat_excel, r["URL"], nombre)
    except Exception as e:
        filas, plat = [], f"error:{type(e).__name__}"
        diag.fallo(f"{type(e).__name__}: {str(e)[:80]}")
    for f in filas:  # "consultar precio" llega como 0: no es un precio
        if not _precio_valido(f.get("Precio")):
            f["Precio"] = None
    if filas and not any(f["Precio"] for f in filas):
        diag.fallo(f"sin precios publicados ({len(filas)} productos)")
        filas = []
    res = {"Dominio": r["dom"], "Empresa": nombre, "Rubro": r["rubro"],
           "Plataforma Excel": plat_excel, "Plataforma usada": plat,
           "Productos": len(filas), "Con precio": sum(1 for f in filas if f.get("Precio")),
           "Segundos": round(time.time() - t0, 1),
           "Estado scrape": ("parcial (tope)" if diag.corto_por_tope() and filas else
                             "ok" if filas else "sin datos"),
           "Motivo": "" if filas else (diag.ultimo() or "")}
    diag.tope(0)
    return res, filas


def _precio_valido(p):
    try:
        return float(p) > 0
    except (TypeError, ValueError):
        return False


def _con_precio(d):
    return int((pd.to_numeric(d["Precio"], errors="coerce") > 0).sum()) if "Precio" in d.columns else 0


def _resultado_sin_scrape(r, estado, productos="", con_precio=""):
    return {"Dominio": r["dom"], "Empresa": str(r["Empresa"])[:40], "Rubro": r["rubro"],
            "Plataforma Excel": r["Plataforma"], "Plataforma usada": "",
            "Productos": productos, "Con precio": con_precio, "Segundos": 0,
            "Estado scrape": estado, "Motivo": ""}


def correr_provincia(folder, rubro_filtro="", limite=0, skip_nacional=True, excel=None,
                     workers=1, df=None, filtrar_tienda=True, tope_seg=0):
    """Scrapea los locales de una provincia (workers = locales a la vez).
    Devuelve una lista de dicts, uno por local: productos, segundos, plataforma, estado."""
    provs = cargar_provincias()
    if folder not in provs:
        print(f"ERROR: {folder} no esta en PROVINCIAS", flush=True)
        return []
    display, region = provs[folder]
    out_dir = os.path.join(RAIZ, region, folder, "excels")
    if df is None:
        full_xlsx = excel or os.path.join(out_dir, f"{folder}_full.xlsx")
        if not os.path.exists(full_xlsx):
            print(f"ERROR: no encontre {full_xlsx}", flush=True)
            return []
        hojas_in = pd.ExcelFile(full_xlsx).sheet_names
        hoja = "Tiendas con web" if "Tiendas con web" in hojas_in else hojas_in[0]
        df = pd.read_excel(full_xlsx, sheet_name=hoja)
        print(f"\n#### {display} ({region}) - {full_xlsx}", flush=True)
    else:
        print(f"\n#### {display} ({region}) - {len(df)} locales recibidos", flush=True)
    df = df.fillna("").copy()
    if filtrar_tienda and "Tienda online" in df.columns:
        df = df[df["Tienda online"].astype(str).str.contains("Si|Probable", case=False, na=False)]
    df["rubro"] = df["Sector"].map(rubro_de)
    df["dom"] = df["URL"].map(dominio)
    if "Plataforma" not in df.columns:
        df["Plataforma"] = ""

    resultados = []
    # Regla: lo que informa a SEPA con sucursales en esta provincia usa los precios de
    # SEPA (precios_SEPA_<Folder>.xlsx, ver sepa.py). Todo lo demas se scrapea.
    import sepa
    cob = sepa.cobertura()
    letra = FOLDER_A_LETRA.get(folder)
    en_sepa = df["dom"].map(lambda d: (cob.get(sepa.clave_cobertura(d, cob)) or {}).get(letra, 0))
    if (en_sepa > 0).any():
        for i, r in df[en_sepa > 0].iterrows():
            resultados.append({**_resultado_sin_scrape(r, f"SEPA ({en_sepa[i]} sucursales)"),
                               "Plataforma usada": "SEPA"})
        quitar_dominios(out_dir, folder, set(df.loc[en_sepa > 0, "dom"]))
        print(f"  {int((en_sepa > 0).sum())} locales con precios de SEPA (no se scrapean)", flush=True)
        df = df[en_sepa == 0]

    if skip_nacional:
        # solo se saltean las cadenas cuyo catalogo YA esta en el precios_*.xlsx de otra
        # provincia (el MasterScrape del csv solo no alcanza: ese Excel puede no existir)
        nacionales = cargar_nacionales()
        hechos = productos_por_dominio()
        masters = df["dom"].map(lambda d: master_de(d, nacionales))
        en_otra = df["dom"].map(lambda d: d in hechos and hechos[d][2] != folder)
        ya = masters.notna() & en_otra
        for i, r in df[ya].iterrows():
            resultados.append(_resultado_sin_scrape(r, f"cadena nacional (master {masters[i]})"))
        print(f"  Total: {len(df)} | cadenas ya scrapeadas en otra provincia: {int(ya.sum())} | "
              f"a scrapear: {int((~ya).sum())}", flush=True)
        df = df[~ya]

    if rubro_filtro:
        df = df[df["rubro"].str.contains(rubro_filtro, case=False)]
        print(f"  Filtro rubro '{rubro_filtro}': {len(df)}", flush=True)

    # un Excel de precios por rubro, cada uno con su estado de guardado
    estado = {}
    tareas = []
    for rubro, grupo in df.groupby("rubro"):
        locales = grupo.drop_duplicates("dom")
        if limite:
            locales = locales.head(limite)
        out_path = os.path.join(out_dir, f"precios_{rubro}_{folder}.xlsx")
        try:
            hojas, doms = cargar_hojas_previas(out_path)
        except Exception as e:
            print(f"  {rubro}: ERROR leyendo {out_path} ({e}); lo salteo para no pisarlo", flush=True)
            continue
        estado[rubro] = {"out": out_path, "hojas": hojas, "doms": doms, "usados": set(hojas),
                         "pendiente": False, "ultimo": time.time(), "nuevos": 0}
        # Reanudacion: por dominio (Resumen nuevo) o por nombre de hoja (Excels viejos sin Dominio)
        hoja_de_dom = {d: h for h, d in doms.items()}
        hoja_de_nombre = {re.sub(r"_\d+$", "", h): h for h in hojas if h not in doms}
        for _, r in locales.iterrows():
            previa = hoja_de_dom.get(r["dom"]) or hoja_de_nombre.get(limpiar_nombre(str(r["Empresa"])[:40]))
            if previa:
                d = hojas[previa]
                con = _con_precio(d)
                if con:
                    resultados.append(_resultado_sin_scrape(r, "ya scrapeada", len(d), con))
                else:  # relevo previo sin ningun precio: se vuelve a intentar
                    tareas.append(r)
            else:
                tareas.append(r)
    tope_txt = f", tope {tope_seg}s por local" if tope_seg else ""
    print(f"  {len(tareas)} locales a scrapear con {workers} hilo(s){tope_txt}", flush=True)

    def checkpoint(st, forzar=False):
        if not st["pendiente"] or (not forzar and time.time() - st["ultimo"] < GUARDAR_CADA_SEG):
            return
        try:
            guardar_rubro(st["out"], st["hojas"], st["doms"])
            st["pendiente"] = False
            st["ultimo"] = time.time()
            print(f"  -> guardado {os.path.basename(st['out'])} ({len(st['hojas'])} locales, +{st['nuevos']} nuevos)", flush=True)
        except Exception as e:
            print(f"  ERROR guardando {st['out']}: {e} (reintento en el proximo local)", flush=True)

    t0 = time.time()
    ex = cf.ThreadPoolExecutor(max_workers=max(1, workers))
    try:
        futs = {ex.submit(_scrapear_local, r, tope_seg): r for r in tareas}
        for k, fut in enumerate(cf.as_completed(futs), 1):
            r = futs[fut]
            res, filas = fut.result()
            resultados.append(res)
            plat = res["Plataforma usada"]
            origen = f"({res['Plataforma Excel']}->{plat})" if res["Plataforma Excel"] else f"({plat})"
            motivo = f" [{res['Motivo']}]" if res["Motivo"] else ""
            print(f"  [{k}/{len(tareas)} {time.time() - t0:5.0f}s] {res['Empresa'][:34]:34s} {origen[:30]:30s} "
                  f"{res['Productos']:5d} prod ({res['Con precio']} c/precio) {res['Segundos']:6.1f}s{motivo}", flush=True)
            if filas:
                st = estado[r["rubro"]]
                d = pd.DataFrame(filas).reindex(columns=["SKU", "Nombre", "Precio", "Fecha", "Categoria"])
                sh = sheet_name(res["Empresa"], st["usados"])
                st["hojas"][sh] = d
                st["doms"][sh] = r["dom"]
                st["nuevos"] += 1
                st["pendiente"] = True
                checkpoint(st)
    finally:
        # tambien corre con Ctrl+C o error: guarda lo que haya quedado sin guardar
        ex.shutdown(wait=False, cancel_futures=True)
        for st in estado.values():
            checkpoint(st, forzar=True)
    return resultados


def correr_todas(paralelo=1, skip_nacional=True):
    provs = list(cargar_provincias().keys())
    if paralelo <= 1:
        for p in provs:
            correr_provincia(p, skip_nacional=skip_nacional)
        return
    # paralelo: spawnear N subprocesos
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
    ap.add_argument("--workers", type=int, default=1, help="locales scrapeados a la vez dentro de la provincia")
    ap.add_argument("--tope-seg", type=int, default=0, help="tope de segundos por local (0 = sin tope)")
    args = ap.parse_args()
    if args.provincia.lower() == "todas":
        correr_todas(paralelo=args.paralelo, skip_nacional=bool(args.skip_nacional))
    else:
        correr_provincia(args.provincia, rubro_filtro=args.rubro, limite=args.limite,
                         skip_nacional=bool(args.skip_nacional),
                         excel=args.excel or None, workers=args.workers, tope_seg=args.tope_seg)


if __name__ == "__main__":
    main()
