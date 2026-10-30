# -*- coding: utf-8 -*-
"""
Control de calidad de los precios relevados. No modifica nada: informa.

Por provincia (precios_<Rubro>_<Folder>.xlsx + <Folder>_full.xlsx):
  - por comercio: productos, % sin precio, precios <= 0, duplicados, precios extremos
    respecto de la mediana del propio comercio, fecha del ultimo relevamiento
  - coherencia con el curado: datos de comercios que ya no estan verificados
  - rubro: que proporcion de los productos tiene palabras tipicas del rubro asignado
    (ej. una "farmacia" que vende gorras y banderines) y que rubro le cuadra mejor
  - SEPA: precios <= 0, minimo > maximo, dispersion entre sucursales
Fuentes externas (datos/fuentes/*): filas, nulos, rangos esperables, frescura.

Cada comercio queda OK / REVISAR / ERROR con la lista de alertas.

Salida: reportes/calidad/calidad_<Folder>.xlsx, reportes/calidad/fuentes.xlsx y
        reportes/calidad/resumen.json

Uso:
  py control_calidad.py CABA Mendoza Corrientes
  py control_calidad.py --todas --fuentes
  py control_calidad.py CABA --depurar      # ademas saca comercios sin precios / huerfanos
"""
import argparse
import datetime
import glob
import json
import os
import re

import pandas as pd

import etl
from ubicaciones import norm
from verificar_ubicacion import dominio

SALIDA = os.path.join(etl.RAIZ, "reportes", "calidad")
HOY = datetime.date.today()
DIAS_VIEJO = 7          # un precio relevado hace mas de esto ya no es "de hoy"
MIN_PRODUCTOS = 5       # menos que esto suele ser una pagina mal leida, no un catalogo
FACTOR_EXTREMO = 200    # precio > mediana*200 o < mediana/200 dentro del mismo comercio
PRECIO_MIN = 10         # $ por debajo de esto es casi siempre un error de lectura
PRECIO_MAX = 200_000_000

# palabras tipicas por rubro (se buscan como inicio de palabra en el nombre del producto)
PALABRAS = {
    "Supermercados": "leche arroz aceite fideo yerba azucar harina galletit gaseosa detergente jabon lavandina "
                     "cafe queso yogur manteca mermelada pure atun arveja papel higienico shampoo cerveza vino",
    "Mayoristas": "leche arroz aceite fideo yerba azucar harina galletit gaseosa detergente jabon lavandina "
                  "bulto pack caja display x12 x6 x24",
    "Farmacias": "comprimido capsula jarabe gotas crema ibuprofeno paracetamol protector solar panal shampoo "
                 "dermo suplemento vitamina gel desodorante toallita algodon preservativo tintura",
    "Verdulerias": "tomate papa cebolla lechuga manzana banana naranja zanahoria zapallo palta limon mandarina "
                   "frutilla acelga espinaca batata pera uva kiwi morron",
    "Carnicerias-Pollerias": "asado vacio pollo carne bife nalga cerdo milanesa chorizo matambre pechuga picada "
                             "costilla entrana lomo bondiola hamburguesa pescado merluza salmon suprema",
    "Panaderias-Confiterias": "pan factura torta medialuna alfajor budin galleta masa tarta pastafrola "
                              "bizcocho prepizza sandwich croissant brownie cookie",
    "Bebidas-Vinotecas": "vino cerveza malbec whisky gin vodka fernet espumante champagne aperitivo gaseosa "
                         "agua cabernet blend licor ron tequila sidra",
    "Cervezas-Cervecerias": "cerveza ipa apa stout lager growler pinta lata birra",
    "Dieteticas": "granola almendra nuez semilla avena harina integral tacc proteina chia mix keto stevia "
                  "mani pasas castana quinoa coco miel",
    "Mascotas-Veterinarias": "perro gato alimento balanceado correa collar piedra sanitaria arena cachorro "
                             "pipeta comedero cucha rascador snack royal pedigree",
    "Ferreteria-Construccion": "tornillo taladro pintura latex llave cano cable cemento griferia sierra martillo "
                               "mecha bulon codo canilla esmalte rodillo pincel cinta adhesivo inodoro ceramica",
    "Electro-Tecnologia": "celular notebook auricular smart tv led heladera lavarropas cargador usb parlante "
                          "mouse teclado monitor tablet aire microondas freezer cafetera licuadora joystick",
    "Indumentaria-Calzado-Deportes": "remera pantalon zapatilla buzo campera jean vestido camisa short media "
                                     "bota calza top musculosa pollera chomba sandalia ojota bermuda",
    "Perfumeria-Cosmetica": "perfume eau crema labial mascara shampoo acondicionador esmalte maquillaje serum "
                            "base corrector rubor delineador tintura fragancia colonia",
    "Muebles-Hogar-Bazar": "mesa silla sillon vaso plato taza olla sarten almohada sabana toalla lampara colchon "
                           "mueble cortina rack placard cubiertos jarra acolchado",
    "Libreria-Jugueteria": "cuaderno lapiz birome boligrafo marcador carpeta juguete muneca lego puzzle juego "
                           "libro resma papel goma regla tijera mochila cartuchera",
    "Opticas-Salud": "anteojo lente armazon receta ortoped contacto tensiometro faja nebulizador termometro",
    "Joyerias-Regalos": "anillo aro collar pulsera cadena dije reloj plata oro acero bijou",
    "Autos-Motos-Repuestos": "filtro aceite bateria neumatico cubierta casco freno pastilla amortiguador bujia "
                             "moto bicicleta rodado llanta embrague correa optica paragolpe",
    "Florerias-Viveros": "planta maceta semilla flor ramo rosa sustrato tierra cactus suculenta fertilizante",
}
RE_PALABRAS = {r: re.compile(r"\b(?:" + "|".join(p.split()) + r")") for r, p in PALABRAS.items()}


def proporcion_rubro(nombres):
    """{rubro: proporcion de productos con alguna palabra tipica del rubro}."""
    ns = [norm(n) for n in nombres if isinstance(n, str)]
    if not ns:
        return {}
    return {r: sum(bool(rx.search(n)) for n in ns) / len(ns) for r, rx in RE_PALABRAS.items()}


def revisar_comercio(d, rubro):
    """Metricas y alertas de la hoja de un comercio."""
    precio = pd.to_numeric(d.get("Precio"), errors="coerce") if "Precio" in d else pd.Series(dtype=float)
    n = len(d)
    con = precio.notna() & (precio > 0)
    med = float(precio[con].median()) if con.any() else None
    m = {"Productos": n, "Con precio": int(con.sum()),
         "% sin precio": round(100 * (1 - con.mean()), 1) if n else 100.0,
         "Precios <= 0": int((precio <= 0).sum()),
         # mismo SKU repetido (los talles/colores con igual nombre y precio son variantes, no duplicados)
         "Duplicados": int(d["SKU"].dropna().astype(str).duplicated().sum()) if "SKU" in d else 0,
         "Precio min": float(precio[con].min()) if con.any() else None,
         "Precio mediana": med,
         "Precio max": float(precio[con].max()) if con.any() else None}
    m["Extremos"] = int(((precio > med * FACTOR_EXTREMO) | (precio < med / FACTOR_EXTREMO)).sum()) if med else 0
    m["Fuera de rango"] = int(((precio > 0) & (precio < PRECIO_MIN)).sum() + (precio > PRECIO_MAX).sum())
    fechas = pd.to_datetime(d.get("Fecha"), errors="coerce") if "Fecha" in d else pd.Series(dtype="datetime64[ns]")
    ultima = fechas.max() if fechas.notna().any() else None
    m["Ultima fecha"] = ultima.date().isoformat() if ultima is not None else ""
    m["Dias desde relevo"] = (HOY - ultima.date()).days if ultima is not None else None

    alertas, error = [], False
    if n == 0 or not con.any():
        alertas.append("sin precios"); error = True
    elif n < MIN_PRODUCTOS:
        alertas.append(f"solo {n} productos")
    if n and m["% sin precio"] > 30:
        alertas.append(f"{m['% sin precio']}% sin precio")
    if m["Precios <= 0"]:
        alertas.append(f"{m['Precios <= 0']} precios en 0 o negativos")
    if n and m["Duplicados"] / n > 0.1:
        alertas.append(f"{m['Duplicados']} duplicados")
    if m["Extremos"]:
        alertas.append(f"{m['Extremos']} precios extremos")
    if m["Fuera de rango"]:
        alertas.append(f"{m['Fuera de rango']} precios fuera de rango")
    if m["Dias desde relevo"] is not None and m["Dias desde relevo"] > DIAS_VIEJO:
        alertas.append(f"relevado hace {m['Dias desde relevo']} dias")

    prop = proporcion_rubro(d["Nombre"]) if "Nombre" in d and n >= MIN_PRODUCTOS else {}
    propio = prop.get(rubro)
    if prop:
        mejor = max(prop, key=prop.get)
        m["% rubro asignado"] = round(100 * propio, 1) if propio is not None else None
        m["Rubro sugerido"] = mejor if prop[mejor] >= 0.2 else ""
        m["% rubro sugerido"] = round(100 * prop[mejor], 1)
        if propio is not None and propio < 0.1 and prop[mejor] >= 0.25 and mejor != rubro:
            alertas.append(f"rubro dudoso: parece {mejor}")
    m["Alertas"] = "; ".join(alertas)
    m["Estado"] = "ERROR" if error else ("REVISAR" if alertas else "OK")
    return m


def revisar_sepa(path):
    filas = []
    with pd.ExcelFile(path) as xl:
        for s in xl.sheet_names:
            if s == "Resumen":
                continue
            d = xl.parse(s)
            pmin, pmax = (pd.to_numeric(d.get(c), errors="coerce") for c in ("Precio_min", "Precio_max"))
            disp = (pmax / pmin).replace([float("inf")], None)
            alertas = []
            if (pmin <= 0).sum():
                alertas.append(f"{int((pmin <= 0).sum())} precios en 0")
            if (pmin > pmax).sum():
                alertas.append(f"{int((pmin > pmax).sum())} con minimo > maximo")
            if (disp > 5).sum():
                alertas.append(f"{int((disp > 5).sum())} productos con max/min > 5 entre sucursales")
            filas.append({"Bandera": s, "Productos": len(d), "Con EAN": int(d.get("EAN").notna().sum()) if "EAN" in d else 0,
                          "Precio mediana": float(pd.to_numeric(d.get("Precio_mediana"), errors="coerce").median()),
                          "Fecha": str(d["Fecha"].max()) if "Fecha" in d else "", "Alertas": "; ".join(alertas),
                          "Estado": "REVISAR" if alertas else "OK"})
    return pd.DataFrame(filas)


def depurar_provincia(folder):
    """Saca de los precios_*.xlsx los comercios sin ningun precio > 0 y los que ya no estan
    verificados (huerfanos), y pasa los primeros a 'Descartados (sin datos)' del _full."""
    from curar_provincia import HOJA_OK, HOJA_SIN, escribir_excel
    display, region = etl.cargar_provincias()[folder]
    d_exc = os.path.join(etl.RAIZ, region, folder, "excels")
    full = os.path.join(d_exc, f"{folder}_full.xlsx")
    with pd.ExcelFile(full) as xl:
        hojas_full = {s: xl.parse(s) for s in xl.sheet_names}
    ok = hojas_full.get(HOJA_OK, pd.DataFrame(columns=["URL"]))
    verificados = set(ok["URL"].map(dominio))
    curada = "Verificacion" in ok.columns
    sin_precio = set()
    for path in sorted(glob.glob(os.path.join(d_exc, f"precios_*_{folder}.xlsx"))):
        if path.endswith(f"precios_SEPA_{folder}.xlsx"):
            continue
        hojas, doms = etl.cargar_hojas_previas(path)
        fuera = [h for h, d in hojas.items()
                 if etl._con_precio(d) == 0 or (curada and doms.get(h) and doms[h] not in verificados)]
        for h in fuera:
            if etl._con_precio(hojas[h]) == 0 and doms.get(h):
                sin_precio.add(doms[h])
            hojas.pop(h)
            doms.pop(h, None)
        if fuera:
            etl.guardar_rubro(path, hojas, doms)
            print(f"  {os.path.basename(path)}: -{len(fuera)} comercios", flush=True)
    if curada and sin_precio:
        mover = ok["URL"].map(dominio).isin(sin_precio)
        sin = hojas_full.get(HOJA_SIN, pd.DataFrame())
        hojas_full[HOJA_SIN] = pd.concat([sin, ok[mover].assign(**{"Motivo descarte": "sin precios publicados"})],
                                         ignore_index=True)
        hojas_full[HOJA_OK] = ok[~mover]
        escribir_excel(full, hojas_full)
        print(f"  {folder}: {int(mover.sum())} comercios pasan a '{HOJA_SIN}'", flush=True)


def controlar_provincia(folder):
    display, region = etl.cargar_provincias()[folder]
    d_exc = os.path.join(etl.RAIZ, region, folder, "excels")
    full = os.path.join(d_exc, f"{folder}_full.xlsx")
    curados = pd.DataFrame()
    if os.path.exists(full):
        with pd.ExcelFile(full) as xl:
            if "Tiendas con web" in xl.sheet_names:
                curados = xl.parse("Tiendas con web")
    es_curada = "Verificacion" in curados.columns
    verificados = set(curados["URL"].map(dominio)) if "URL" in curados else set()
    filas = []
    for path in sorted(glob.glob(os.path.join(d_exc, f"precios_*_{folder}.xlsx"))):
        rubro = os.path.basename(path)[len("precios_"):-len(f"_{folder}.xlsx")]
        if rubro == "SEPA":
            continue
        hojas, doms = etl.cargar_hojas_previas(path)
        for hoja, d in hojas.items():
            m = revisar_comercio(d, rubro)
            dom = doms.get(hoja, "")
            if es_curada and dom and dom not in verificados:
                m["Alertas"] = "; ".join(x for x in ("no esta entre los verificados (dato huerfano)", m["Alertas"]) if x)
                m["Estado"] = "ERROR"
            filas.append({"Rubro": rubro, "Comercio": hoja, "Dominio": dom, **m})
    com = pd.DataFrame(filas)
    sepa_path = os.path.join(d_exc, f"precios_SEPA_{folder}.xlsx")
    sepa = revisar_sepa(sepa_path) if os.path.exists(sepa_path) else pd.DataFrame()

    res = {"provincia": folder, "curada": es_curada, "comercios_con_datos": len(com),
           "productos": int(com["Productos"].sum()) if len(com) else 0,
           "estados": com["Estado"].value_counts().to_dict() if len(com) else {},
           "alertas_frecuentes": (com["Alertas"].str.split("; ").explode().str.replace(r"^\d+ ", "", regex=True)
                                  .str.replace(r"\d+", "N", regex=True).value_counts().drop("", errors="ignore")
                                  .head(10).to_dict()) if len(com) else {},
           "rubro_dudoso": int(com["Alertas"].str.contains("rubro dudoso").sum()) if len(com) else 0,
           "huerfanos": int(com["Alertas"].str.contains("huerfano").sum()) if len(com) else 0,
           "sepa_banderas": len(sepa), "sepa_revisar": int((sepa["Estado"] != "OK").sum()) if len(sepa) else 0}
    if len(com):
        por_rubro = com.groupby("Rubro").agg(Comercios=("Comercio", "size"), Productos=("Productos", "sum"),
                                              OK=("Estado", lambda s: (s == "OK").sum()),
                                              Revisar=("Estado", lambda s: (s == "REVISAR").sum()),
                                              Error=("Estado", lambda s: (s == "ERROR").sum())).reset_index()
    else:
        por_rubro = pd.DataFrame()
    os.makedirs(SALIDA, exist_ok=True)
    out = os.path.join(SALIDA, f"calidad_{folder}.xlsx")
    orden = {"ERROR": 0, "REVISAR": 1, "OK": 2}
    with pd.ExcelWriter(out + ".tmp.xlsx", engine="openpyxl") as xl:
        pd.DataFrame([{k: (json.dumps(v, ensure_ascii=False) if isinstance(v, dict) else v) for k, v in res.items()}]) \
            .T.reset_index().rename(columns={"index": "Indicador", 0: "Valor"}).to_excel(xl, "Resumen", index=False)
        por_rubro.to_excel(xl, "Por rubro", index=False)
        if len(com):
            com.sort_values("Estado", key=lambda s: s.map(orden)).to_excel(xl, "Comercios", index=False)
        sepa.to_excel(xl, "SEPA", index=False)
        for sh in xl.sheets.values():
            sh.freeze_panes = "A2"
            for col in sh.columns:
                sh.column_dimensions[col[0].column_letter].width = min(60, max(10, max(len(str(c.value or "")) for c in col[:200]) + 2))
    os.replace(out + ".tmp.xlsx", out)
    print(f"  {folder}: {res['comercios_con_datos']} comercios, {res['productos']:,} productos -> {res['estados']} "
          f"| rubro dudoso {res['rubro_dudoso']} | huerfanos {res['huerfanos']} | SEPA {res['sepa_banderas']} banderas",
          flush=True)
    return res


# ---------------------------------------------------------------------------
# Fuentes externas: (columna de precio, rango esperable, columna de fecha)
# ---------------------------------------------------------------------------
REGLAS_FUENTES = {
    "combustibles": ("precio", (100, 10_000), "fecha_vigencia"),
    "granos": ("Precio_ARS_tn", (50_000, 3_000_000), "Fecha"),
    "hacienda": ("Promedio", (100, 50_000), "Fecha"),
    "frutas_hortalizas": ("Frecuente_kg", (10, 100_000), "Fecha"),
    "zonaprop": ("Precio", (1, 100_000_000_000), None),
    "argenprop": ("Precio", (1, 100_000_000_000), None),
    "bcra": ("Valor", (None, None), "Fecha"),
    "medicamentos": ("Precio", (10, 50_000_000), "Vigencia"),
}


def controlar_fuentes():
    filas = []
    for fuente, (col, (lo, hi), col_fecha) in REGLAS_FUENTES.items():
        archivos = sorted(glob.glob(os.path.join(etl.RAIZ, "datos", "fuentes", fuente, f"{fuente}_*.parquet")))
        if not archivos:
            filas.append({"Fuente": fuente, "Estado": "ERROR", "Alertas": "sin archivo"})
            continue
        d = pd.read_parquet(archivos[-1])
        v = pd.to_numeric(d.get(col), errors="coerce")
        fuera = int(((v < lo) | (v > hi)).sum()) if lo is not None else 0
        fecha = pd.to_datetime(d[col_fecha], errors="coerce", dayfirst=False).max() if col_fecha in d else None
        alertas = []
        if d.empty:
            alertas.append("vacia")
        if len(d) and v.isna().mean() > 0.05:
            alertas.append(f"{100 * v.isna().mean():.0f}% sin {col}")
        if fuera:
            alertas.append(f"{fuera} fuera de rango {lo}-{hi}")
        if fuente in ("zonaprop", "argenprop") and "Moneda" in d:
            alertas += [f"{int(d['Moneda'].isna().sum())} sin moneda"] if d["Moneda"].isna().sum() else []
        dups = int(d.duplicated().sum())
        if dups:
            alertas.append(f"{dups} filas duplicadas")
        filas.append({"Fuente": fuente, "Archivo": os.path.basename(archivos[-1]), "Filas": len(d),
                      f"Nulos": int(v.isna().sum()), "Fuera de rango": fuera,
                      "Mediana": float(v.median()) if v.notna().any() else None,
                      "Dato mas reciente": fecha.date().isoformat() if fecha is not None and pd.notna(fecha) else "",
                      "Alertas": "; ".join(alertas), "Estado": "REVISAR" if alertas else "OK"})
    df = pd.DataFrame(filas)
    os.makedirs(SALIDA, exist_ok=True)
    df.to_excel(os.path.join(SALIDA, "fuentes.xlsx"), index=False)
    for f in filas:
        print(f"  {f['Fuente']}: {f.get('Filas', 0):,} filas -> {f['Estado']} {f.get('Alertas', '')}", flush=True)
    return df.to_dict("records")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("provincias", nargs="*")
    ap.add_argument("--todas", action="store_true")
    ap.add_argument("--fuentes", action="store_true")
    ap.add_argument("--depurar", action="store_true",
                    help="quita comercios sin precios y huerfanos de los Excel (antes de controlar)")
    a = ap.parse_args()
    provs = list(etl.cargar_provincias()) if a.todas else a.provincias
    p_res = os.path.join(SALIDA, "resumen.json")
    resumen = json.load(open(p_res, encoding="utf-8")) if os.path.exists(p_res) else {}
    resumen["fecha"] = datetime.datetime.now().isoformat(timespec="seconds")
    resumen.setdefault("provincias", {})
    for p in provs:
        if a.depurar:
            depurar_provincia(p)
        resumen["provincias"][p] = controlar_provincia(p)
    if a.fuentes:
        resumen["fuentes"] = controlar_fuentes()
    os.makedirs(SALIDA, exist_ok=True)
    json.dump(resumen, open(p_res, "w", encoding="utf-8"), ensure_ascii=False, indent=2, default=str)


if __name__ == "__main__":
    main()
