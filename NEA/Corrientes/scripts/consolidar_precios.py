# -*- coding: utf-8 -*-
"""
Consolida los CSV de precios por tienda (precios_<tienda>.csv) en UN solo Excel
con una HOJA POR SUPERMERCADO + una hoja 'Resumen'.
Salida: precios_supermercados_corrientes.xlsx
"""
import glob
import os
import re

import pandas as pd

COLS = ["SKU", "EAN", "Nombre", "Marca", "Precio", "PrecioLista", "Fecha",
        "Categoria", "Tienda", "Stock", "URL"]
EXCLUIR = {"precios_supermercados.csv", "precios_supermercados_corrientes.csv"}


def sheet_name(s):
    s = re.sub(r"[\[\]:\*\?/\\]", "", str(s))[:31]
    return s or "Tienda"


def main():
    files = [f for f in sorted(glob.glob("precios_*.csv")) if os.path.basename(f) not in EXCLUIR]
    if not files:
        print("No hay CSV de precios."); return
    resumen = []
    hojas = []
    for f in files:
        try:
            df = pd.read_csv(f)
        except Exception as e:
            print(f"  no pude leer {f}: {e}"); continue
        if df.empty:
            continue
        tienda = str(df["Tienda"].iloc[0]) if "Tienda" in df.columns else os.path.basename(f)
        df = df.reindex(columns=[c for c in COLS if c in df.columns])
        precio = pd.to_numeric(df.get("Precio"), errors="coerce")
        resumen.append({
            "Tienda": tienda,
            "Productos": len(df),
            "Con precio": int((precio > 0).sum()),
            "Categorias": df["Categoria"].nunique() if "Categoria" in df.columns else 0,
            "Fecha": df["Fecha"].iloc[0] if "Fecha" in df.columns else "",
        })
        hojas.append((sheet_name(tienda), df))

    res = pd.DataFrame(resumen).sort_values("Productos", ascending=False)
    out = "precios_supermercados_corrientes.xlsx"
    try:
        open(out, "ab").close()
    except PermissionError:
        out = "precios_supermercados_corrientes_NEW.xlsx"
        print(f"  (archivo abierto en Excel; guardo en {out})")
    with pd.ExcelWriter(out, engine="openpyxl") as xl:
        res.to_excel(xl, sheet_name="Resumen", index=False)
        for nombre, df in hojas:
            df.to_excel(xl, sheet_name=nombre, index=False)
            xl.sheets[nombre].freeze_panes = "A2"
    print("== CONSOLIDADO ==")
    print(res.to_string(index=False))
    print(f"\nTotal productos: {res['Productos'].sum()}")
    print(f"Hojas: Resumen + {len(hojas)} supermercados")
    print(f"Guardado: {out}")
    if out.endswith("_NEW.xlsx"):
        print("  -> CERRA el Excel viejo y renombro este como el definitivo.")


if __name__ == "__main__":
    main()
