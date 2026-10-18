# -*- coding: utf-8 -*-
"""
Scraper dedicado de FARMAR (farmacia/perfumeria, Next.js a medida con API gateada).
Navega sus 7 categorias en el navegador (Playwright) con scroll infinito y extrae
nombre+precio del DOM. Guarda precios_farmar.csv y agrega la hoja 'Farmar' al
precios_Farmacias.xlsx existente.
"""
import datetime
import os
import re

import pandas as pd
from playwright.sync_api import sync_playwright

from scraper_playwright import JS_EXTRACT, _precio

HOY = datetime.date.today().isoformat()
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")
CATS = [
    ("Belleza", "https://www.farmar.com.ar/categorias/belleza"),
    ("Cuidado Oral", "https://www.farmar.com.ar/categorias/cuidado-oral"),
    ("Cuidado Personal", "https://www.farmar.com.ar/categorias/cuidado-personal"),
    ("Dermocosmetica", "https://www.farmar.com.ar/categorias/dermocosmetica"),
    ("Fragancias", "https://www.farmar.com.ar/categorias/fragancias"),
    ("Limpieza", "https://www.farmar.com.ar/categorias/limpieza"),
    ("Universo Bebe", "https://www.farmar.com.ar/categorias/universo-bebe"),
]


def scrape_categoria(pg, url, max_scroll=120):
    pg.goto(url, wait_until="domcontentloaded", timeout=60000)
    pg.wait_for_timeout(4000)
    prev, estable = -1, 0
    for _ in range(max_scroll):
        pg.mouse.wheel(0, 9000)
        pg.wait_for_timeout(800)
        n = len(pg.evaluate(JS_EXTRACT))
        if n == prev:
            estable += 1
            if estable >= 6:
                break
        else:
            estable = 0
        prev = n
    return pg.evaluate(JS_EXTRACT)


def main():
    import sys
    solo = set(sys.argv[1:])  # opcional: limitar a ciertas categorias
    by_name = {}
    # acumular sobre lo ya scrapeado (re-runs)
    if os.path.exists("../excels/precios_farmar.csv"):
        prev = pd.read_csv("../excels/precios_farmar.csv").fillna("")
        for _, r in prev.iterrows():
            by_name[str(r["Nombre"]).strip()] = r.to_dict()
        print(f"acumulando sobre {len(by_name)} ya scrapeados", flush=True)
    cats = [(c, u) for c, u in CATS if not solo or c in solo]
    with sync_playwright() as p:
        b = p.chromium.launch(headless=True)
        pg = b.new_page(user_agent=UA, viewport={"width": 1366, "height": 1000})
        for cat, url in cats:
            try:
                prods = scrape_categoria(pg, url)
            except Exception as e:
                print(f"  {cat}: error {type(e).__name__}", flush=True)
                prods = []
            nuevos = 0
            for x in prods:
                nm = x["nombre"].strip()
                if nm in by_name:
                    continue
                by_name[nm] = {"SKU": "", "Nombre": nm, "Precio": _precio(x["precio"]),
                               "Fecha": HOY, "Categoria": cat, "Tienda": "Farmar"}
                nuevos += 1
            print(f"  {cat:18s} -> {len(prods)} en pagina, {nuevos} nuevos (total {len(by_name)})", flush=True)
        b.close()

    df = pd.DataFrame(by_name.values())
    print(f"\nFARMAR total: {len(df)} productos con precio: {int(df['Precio'].notna().sum())}")
    df.to_csv("../excels/precios_farmar.csv", index=False, encoding="utf-8-sig")

    # agregar hoja Farmar al precios_Farmacias.xlsx
    fx = "../excels/precios_Farmacias.xlsx"
    hojas = {}
    if os.path.exists(fx):
        xl = pd.ExcelFile(fx)
        for sh in xl.sheet_names:
            if sh not in ("Resumen", "Farmar"):
                hojas[sh] = xl.parse(sh)
    hojas["Farmar"] = df[["SKU", "Nombre", "Precio", "Fecha", "Categoria"]]
    with pd.ExcelWriter(fx, engine="openpyxl") as w:
        resumen = pd.DataFrame(
            [(n, len(d), int(pd.to_numeric(d.get("Precio"), errors="coerce").gt(0).sum())) for n, d in hojas.items()],
            columns=["Local", "Productos", "Con precio"])
        resumen.to_excel(w, sheet_name="Resumen", index=False)
        for n, d in hojas.items():
            d.to_excel(w, sheet_name=n[:31], index=False)
    print(f"Agregado a {fx} (hojas: {list(hojas.keys())})")


if __name__ == "__main__":
    main()
