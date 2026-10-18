# -*- coding: utf-8 -*-
"""
Scraper de Coto via API de Constructor.io (motor de busqueda/catalogo de coto).
Navega las categorias (browse/group_id) y pagina. Precio: por sucursal -> usa
el precio de lista mas frecuente. Genera Excel: SKU, Nombre, Precio, Fecha, Categoria.

Uso: py scraper_coto.py [--max-cats N]
"""
import argparse
import collections
import datetime
import socket
import time

import pandas as pd
import requests

socket.setdefaulttimeout(30)
KEY = "key_r6xzz4IAoTWcipni"
BASE = "https://ac.cnstrc.com"
H = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
     "(KHTML, like Gecko) Chrome/124.0 Safari/537.36",
     "Accept": "application/json", "Referer": "https://www.cotodigital.com.ar/"}
COMMON = {"key": KEY, "c": "ciojs-2", "i": "crawler", "s": "1"}


def get(url, params):
    return requests.get(url, params=params, headers=H, timeout=30)


def categorias_top():
    r = get(f"{BASE}/search/a", {**COMMON, "num_results_per_page": 1})
    grupos = r.json().get("response", {}).get("groups", [])
    out = []
    for root in grupos:
        for hijo in root.get("children", []):
            gid = hijo.get("group_id")
            if gid and gid != "categoria":
                out.append((gid, hijo.get("display_name", gid)))
    return out


def precio_repr(price_array):
    """Precio de lista mas frecuente entre sucursales (evita outliers/errores)."""
    vals = [p.get("listPrice") for p in price_array if isinstance(p.get("listPrice"), (int, float))]
    if not vals:
        return None
    return collections.Counter(vals).most_common(1)[0][0]


def scrape_coto(max_cats=0, delay=0.3):
    hoy = datetime.date.today().isoformat()
    cats = categorias_top()
    print(f"  {len(cats)} categorias top", flush=True)
    if max_cats:
        cats = cats[:max_cats]
    by_sku = {}
    for gid, cname in cats:
        page = 1
        total = None
        while True:
            try:
                r = get(f"{BASE}/browse/group_id/{gid}",
                        {**COMMON, "num_results_per_page": 200, "page": page})
            except Exception as e:
                print(f"    err {cname} p{page}: {e}", flush=True)
                break
            if r.status_code != 200:
                break
            resp = r.json().get("response", {})
            results = resp.get("results", [])
            if total is None:
                total = resp.get("total_num_results", 0)
            if not results:
                break
            for it in results:
                data = it.get("data", {})
                sku = data.get("sku_plu") or data.get("sku_id") or data.get("id")
                if not sku or sku in by_sku:
                    continue
                by_sku[sku] = {
                    "SKU": sku,
                    "Nombre": it.get("value", ""),
                    "Precio": precio_repr(data.get("price", []) or []),
                    "Fecha": hoy,
                    "Categoria": cname,
                    "Tienda": "Coto",
                    "URL": ("https://www.cotodigital.com.ar" + data.get("url", "")) if data.get("url") else "",
                }
            if page * 200 >= (total or 0):
                break
            page += 1
            time.sleep(delay)
        print(f"    {cname:16s} (total {total}) -> acum {len(by_sku)}", flush=True)
    return list(by_sku.values())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-cats", type=int, default=0)
    args = ap.parse_args()
    print("Scrapeando Coto (Constructor.io) ...", flush=True)
    filas = scrape_coto(args.max_cats)
    if not filas:
        print("Sin productos."); return
    df = pd.DataFrame(filas)
    con = df[df["Precio"].notna() & (df["Precio"] > 0)]
    df.to_excel("precios_coto.xlsx", index=False, engine="openpyxl")
    df.to_csv("precios_coto.csv", index=False, encoding="utf-8-sig")
    print(f"\nTotal SKUs: {len(df)} | con precio: {len(con)} | categorias: {df['Categoria'].nunique()}")
    print(con[["SKU", "Nombre", "Precio", "Categoria"]].head(8).to_string(index=False))
    print("Guardado: precios_coto.xlsx")


if __name__ == "__main__":
    main()
