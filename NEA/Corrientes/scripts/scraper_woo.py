# -*- coding: utf-8 -*-
"""
Scraper de precios para tiendas WooCommerce (Store API publica).
Genera Excel con: SKU, Nombre, Precio, Fecha, Categoria (+ Tienda, URL, Stock).

Uso: py scraper_woo.py <base_url> <nombre_tienda> [--max-pages N]
"""
import argparse
import datetime
import socket
import time

import pandas as pd
import requests

socket.setdefaulttimeout(30)
H = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
     "(KHTML, like Gecko) Chrome/124.0 Safari/537.36",
     "Accept": "application/json"}
_S = requests.Session()
_S.mount("https://", requests.adapters.HTTPAdapter(pool_connections=20, pool_maxsize=20, max_retries=2))


def get_categorias(base):
    cats, page = [], 1
    while True:
        try:
            r = _S.get(f"{base}/wp-json/wc/store/products/categories",
                             params={"per_page": 100, "page": page}, headers=H, timeout=25)
        except Exception:
            break
        if r.status_code != 200 or not r.json():
            break
        for c in r.json():
            if c.get("count", 0) > 0:
                cats.append((c["id"], c["name"]))
        if page >= int(r.headers.get("X-WP-TotalPages", 1) or 1):
            break
        page += 1
    return cats


def _fila(p, hoy, tienda, cat_fallback=""):
    pr = p.get("prices", {}) or {}
    minor = pr.get("currency_minor_unit", 2)
    raw = pr.get("price")
    try:
        precio = round(int(raw) / (10 ** minor), 2) if raw not in (None, "") else None
    except (ValueError, TypeError):
        precio = None
    cats = " > ".join(c.get("name", "") for c in (p.get("categories") or []))
    return {
        "SKU": p.get("sku") or p.get("id"),
        "Nombre": p.get("name", ""),
        "Precio": precio,
        "Fecha": hoy,
        "Categoria": cats or cat_fallback,
        "Tienda": tienda,
        "Stock": "Si" if p.get("is_in_stock") else "No",
        "URL": p.get("permalink", ""),
    }


def scrape_woo(base, tienda, max_pages=0, delay=0.35):
    """Scrapea por categoria (asi cada producto trae su rubro) y deduplica por SKU."""
    base = base.rstrip("/")
    hoy = datetime.date.today().isoformat()
    cats = get_categorias(base)
    print(f"  {len(cats)} categorias", flush=True)
    by_sku = {}
    for cid, cname in cats:
        page = 1
        while True:
            try:
                r = _S.get(f"{base}/wp-json/wc/store/products",
                                 params={"per_page": 100, "page": page, "category": cid},
                                 headers=H, timeout=30)
            except Exception as e:
                print(f"    error {cname} p{page}: {e}", flush=True)
                break
            if r.status_code != 200 or not r.json():
                break
            data = r.json()
            for p in data:
                key = str(p.get("sku") or p.get("id"))
                if key in by_sku:
                    # producto en varias categorias: sumar el rubro
                    prev = by_sku[key]["Categoria"]
                    if cname not in prev:
                        by_sku[key]["Categoria"] = f"{prev}, {cname}" if prev else cname
                    continue
                by_sku[key] = _fila(p, hoy, tienda, cname)
            tp = int(r.headers.get("X-WP-TotalPages", 1) or 1)
            if (max_pages and page >= max_pages) or page >= tp:
                break
            page += 1
            time.sleep(delay)
        print(f"    {cname:28s} -> acum {len(by_sku)}", flush=True)
    return list(by_sku.values())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("base")
    ap.add_argument("tienda")
    ap.add_argument("--max-pages", type=int, default=0)
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    print(f"Scrapeando {args.tienda} ({args.base}) ...", flush=True)
    filas = scrape_woo(args.base, args.tienda, args.max_pages)
    if not filas:
        print("Sin productos.")
        return
    df = pd.DataFrame(filas)
    con_precio = df[df["Precio"].notna() & (df["Precio"] > 0)]
    base = args.out or f"precios_{args.tienda.lower().replace(' ', '_')}"
    xlsx = f"{base}.xlsx"
    df.to_excel(xlsx, index=False, engine="openpyxl")
    df.to_csv(f"{base}.csv", index=False, encoding="utf-8-sig")
    print(f"\nTotal productos: {len(df)} | con precio: {len(con_precio)}")
    print(f"Categorias distintas: {df['Categoria'].nunique()}")
    print("Muestra:")
    print(con_precio[["SKU", "Nombre", "Precio", "Categoria"]].head(8).to_string(index=False))
    print(f"Guardado: {xlsx}")


if __name__ == "__main__":
    main()
