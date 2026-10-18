# -*- coding: utf-8 -*-
"""
Orquestador: scrapea precios de los supermercados de Corrientes con API publica
(VTEX o WooCommerce) y consolida en un Excel.
Salida: precios_supermercados.xlsx (hoja 'Precios' con todo + 'Resumen' por tienda)
        y un CSV por tienda.
"""
import datetime
import pandas as pd

from scraper_vtex import scrape_vtex
from scraper_woo import scrape_woo

# (nombre, base_url, plataforma)
TIENDAS = [
    ("Depot Express", "https://depotexpress.com.ar", "woo"),
    ("Dia", "https://diaonline.supermercadosdia.com.ar", "vtex"),
    ("Carrefour", "https://www.carrefour.com.ar", "vtex"),
    ("ChangoMas", "https://www.masonline.com.ar", "vtex"),
    ("Makro", "https://makro.com.ar", "vtex"),
]

COLS = ["SKU", "EAN", "Nombre", "Marca", "Precio", "PrecioLista", "Fecha",
        "Categoria", "Tienda", "URL"]


def main():
    todo = []
    resumen = []
    for nombre, base, plat in TIENDAS:
        print(f"\n===== {nombre} ({plat}) =====", flush=True)
        try:
            filas = scrape_vtex(base, nombre) if plat == "vtex" else scrape_woo(base, nombre)
        except Exception as e:
            print(f"  FALLO {nombre}: {type(e).__name__}: {e}", flush=True)
            filas = []
        if filas:
            df = pd.DataFrame(filas)
            slug = nombre.lower().replace(" ", "_")
            df.to_csv(f"precios_{slug}.csv", index=False, encoding="utf-8-sig")
            con_precio = int((df.get("Precio").notna() & (df.get("Precio") > 0)).sum())
            resumen.append({"Tienda": nombre, "Plataforma": plat,
                            "SKUs": len(df), "Con precio": con_precio,
                            "Categorias": df["Categoria"].nunique()})
            todo.extend(filas)
            print(f"  -> {len(df)} SKUs ({con_precio} con precio)", flush=True)

    if not todo:
        print("Sin datos.")
        return
    full = pd.DataFrame(todo).reindex(columns=COLS)
    res = pd.DataFrame(resumen)
    with pd.ExcelWriter("precios_supermercados.xlsx", engine="openpyxl") as xl:
        full.to_excel(xl, sheet_name="Precios", index=False)
        res.to_excel(xl, sheet_name="Resumen", index=False)
        xl.sheets["Precios"].freeze_panes = "A2"
    full.to_csv("precios_supermercados.csv", index=False, encoding="utf-8-sig")
    print("\n===== RESUMEN =====")
    print(res.to_string(index=False))
    print(f"\nTOTAL SKUs: {len(full)}")
    print(f"Fecha: {datetime.date.today().isoformat()}")
    print("Guardado: precios_supermercados.xlsx")


if __name__ == "__main__":
    main()
