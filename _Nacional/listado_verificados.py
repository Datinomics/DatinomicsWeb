# -*- coding: utf-8 -*-
"""
Listado en Excel de los comercios verificados por curar_provincia.py, con su rubro
y la cantidad de productos scrapeados. Una hoja por provincia + 'Resumen por rubro'.

Las cadenas nacionales que no se re-scrapean (master en otra provincia) toman la
cantidad de productos del precios_<Rubro>_<Master>.xlsx de esa provincia.

Uso: py listado_verificados.py Corrientes Mendoza CABA [--out ruta.xlsx]
"""
import argparse
import os

import pandas as pd

import etl
import sepa
from verificar_ubicacion import dominio, etiqueta_dominio


def listado(folder, prods):
    display, region = etl.cargar_provincias()[folder]
    full = os.path.join(etl.RAIZ, region, folder, "excels", f"{folder}_full.xlsx")
    with pd.ExcelFile(full) as xl:
        if "Descartados (sin datos)" not in xl.sheet_names:
            raise SystemExit(f"{folder}: el Excel todavia no paso por curar_provincia.py")
        ok = xl.parse("Tiendas con web")
        sin = xl.parse("Descartados (sin datos)")
    ok["Queda en Excel"] = "Si"
    sin["Queda en Excel"] = "No (sin datos scrapeables)"
    sin["Productos"] = 0
    df = pd.concat([ok, sin], ignore_index=True)
    df["Rubro"] = df["Sector"].map(etl.rubro_de)
    df["Dominio"] = df["URL"].map(dominio)
    df["Con precio"] = ""
    df["Scrapeada en"] = folder
    df["Fuente precios"] = "Scraping"
    # comercios que informan a SEPA: productos del precios_SEPA_<Folder>.xlsx de ESTA provincia
    sepa_xlsx = os.path.join(etl.RAIZ, region, folder, "excels", f"precios_SEPA_{folder}.xlsx")
    sepa_res = pd.read_excel(sepa_xlsx, sheet_name="Resumen") if os.path.exists(sepa_xlsx) else pd.DataFrame()
    # varias banderas con la misma web (Carrefour Hiper/Market/Express/Maxi): productos = la
    # bandera de catalogo mas grande; sucursales = la suma
    sepa_cob = {}
    for d, p, s in zip(sepa_res.get("Dominio", []), sepa_res.get("Productos", []), sepa_res.get("Sucursales", [])):
        if str(d) in ("", "nan"):
            continue
        prev = sepa_cob.get(etiqueta_dominio(str(d)), (0, 0))
        sepa_cob[etiqueta_dominio(str(d))] = (max(prev[0], int(p)), prev[1] + int(s))
    for i, r in df.iterrows():
        clave = sepa.clave_cobertura(r["Dominio"], sepa_cob)
        if str(r.get("Plataforma usada", "")) == "SEPA" and clave:
            prod, suc = sepa_cob[clave]
            df.at[i, "Productos"], df.at[i, "Con precio"] = prod, prod
            df.at[i, "Scrapeada en"], df.at[i, "Fuente precios"] = "-", f"SEPA ({suc} suc.)"
            continue
        p = prods.get(r["Dominio"])
        if p:
            df.at[i, "Productos"], df.at[i, "Con precio"], df.at[i, "Scrapeada en"] = p
    df["Productos"] = pd.to_numeric(df["Productos"], errors="coerce").fillna(0).astype(int)
    cols = ["Empresa", "Rubro", "Sector", "URL", "Fuente precios", "Plataforma usada", "Productos",
            "Con precio", "Scrapeada en", "Queda en Excel", "Evidencia"]
    df = df.reindex(columns=cols)
    df["Provincia"] = display
    return df.sort_values(["Queda en Excel", "Rubro", "Productos"], ascending=[False, True, False])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("provincias", nargs="+")
    ap.add_argument("--out", default=os.path.join(etl.RAIZ, "reportes", "verificados.xlsx"))
    a = ap.parse_args()
    prods = etl.productos_por_dominio()
    hojas = {p: listado(p, prods) for p in a.provincias}
    todo = pd.concat(hojas.values(), ignore_index=True)
    todo = todo[todo["Queda en Excel"] == "Si"]
    resumen = (todo.groupby(["Provincia", "Rubro"])
               .agg(Comercios=("Empresa", "size"), Productos=("Productos", "sum"))
               .reset_index().sort_values(["Provincia", "Productos"], ascending=[True, False]))
    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    with pd.ExcelWriter(a.out, engine="openpyxl") as xl:
        resumen.to_excel(xl, sheet_name="Resumen por rubro", index=False)
        for p, d in hojas.items():
            d.drop(columns="Provincia").to_excel(xl, sheet_name=p[:31], index=False)
        for sh in xl.sheets.values():
            for col, w in zip("ABCDEFGHIJK", (40, 26, 24, 42, 18, 16, 11, 11, 13, 24, 70)):
                sh.column_dimensions[col].width = w
            sh.freeze_panes = "A2"
            sh.auto_filter.ref = sh.dimensions
    print(f"Guardado: {a.out}")
    print(resumen.groupby("Provincia")[["Comercios", "Productos"]].sum().to_string())


if __name__ == "__main__":
    main()
