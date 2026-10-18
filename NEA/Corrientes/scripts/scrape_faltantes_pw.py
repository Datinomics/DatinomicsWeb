# -*- coding: utf-8 -*-
"""
Segundo pase: para las tiendas que el scrape por API no pudo (Magento, Prestashop,
Next.js a medida), usa Playwright (scraper_playwright) y AGREGA su hoja al
precios_<rubro>.xlsx existente. No re-scrapea las que ya estan.

Uso: py scrape_faltantes_pw.py [--rubro X] [--limite N]
"""
import argparse
import os
import re

import pandas as pd

from scrape_categorias import rubro_de, sheet_name
from scraper_playwright import scrape_playwright

FULL = "../excels/Corrientes_full.xlsx"
OUTDIR = "../excels"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rubro", default="")
    ap.add_argument("--limite", type=int, default=0)
    args = ap.parse_args()

    df = pd.read_excel(FULL, sheet_name=0).fillna("")
    df = df[df["Tienda online"].astype(str).str.contains("Si|Probable", case=False, na=False)]
    df = df[~df["Sector"].astype(str).str.contains("Supermercado|Mayorista", case=False, na=False)]
    df["rubro"] = df["Sector"].map(rubro_de)
    if args.rubro:
        df = df[df["rubro"].str.contains(args.rubro, case=False)]

    for rubro, grupo in df.groupby("rubro"):
        xlsx = os.path.join(OUTDIR, f"precios_{rubro}.xlsx")
        # hojas existentes (las ya scrapeadas por API)
        hojas_exist = {}
        if os.path.exists(xlsx):
            xl = pd.ExcelFile(xlsx)
            for sh in xl.sheet_names:
                hojas_exist[sh] = xl.parse(sh)
        ya = set(hojas_exist.keys())
        locales = grupo.drop_duplicates("URL")
        if args.limite:
            locales = locales.head(args.limite)
        # faltantes = cuyo sheet_name no esta todavia
        faltantes = []
        usados = set(ya)
        for _, r in locales.iterrows():
            nm = str(r["Empresa"])[:40]
            base_sheet = re.sub(r"[\[\]:\*\?/\\]", "", nm)[:28].strip()
            if any(s.startswith(base_sheet[:20]) for s in ya):
                continue
            faltantes.append((nm, r["URL"]))
        if not faltantes:
            print(f"[{rubro}] sin faltantes", flush=True)
            continue
        print(f"\n[{rubro}] {len(faltantes)} faltantes -> Playwright", flush=True)
        nuevas = []
        for nm, url in faltantes:
            try:
                rows = scrape_playwright(url, nm)
            except Exception as e:
                rows = []
                print(f"    {nm[:30]:30s} PW error {type(e).__name__}", flush=True)
            con = sum(1 for x in rows if x.get("Precio"))
            print(f"    {nm[:30]:30s} {len(rows):5d} prod ({con} c/precio)", flush=True)
            if rows:
                d = pd.DataFrame(rows).reindex(columns=["SKU", "Nombre", "Precio", "Fecha", "Categoria"])
                nuevas.append((sheet_name(nm, usados), d))
        if not nuevas:
            print(f"  [{rubro}] Playwright no recupero nada", flush=True)
            continue
        # reescribir el Excel: hojas existentes (menos Resumen) + nuevas + Resumen recalculado
        datos = [(n, d) for n, d in hojas_exist.items() if n != "Resumen"] + nuevas
        with pd.ExcelWriter(xlsx, engine="openpyxl") as w:
            resumen = pd.DataFrame(
                [(n, len(d), int(pd.to_numeric(d.get("Precio"), errors="coerce").gt(0).sum())) for n, d in datos],
                columns=["Local", "Productos", "Con precio"])
            resumen.to_excel(w, sheet_name="Resumen", index=False)
            for n, d in datos:
                d.to_excel(w, sheet_name=n[:31], index=False)
        print(f"  -> Actualizado {xlsx} (+{len(nuevas)} locales por Playwright, total {len(datos)})", flush=True)


if __name__ == "__main__":
    main()
