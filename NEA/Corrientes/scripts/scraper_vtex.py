# -*- coding: utf-8 -*-
"""
Scraper de precios para tiendas VTEX (API publica de catalogo).
Itera el arbol de categorias y pagina productos. Acepta HTTP 200 y 206.
Genera Excel con: SKU, Nombre, Precio, Fecha, Categoria (+ marca, tienda, stock, URL).

Uso: py scraper_vtex.py <base_url> <nombre_tienda> [--max-cats N]
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


def get(url, **kw):
    return _S.get(url, headers=H, timeout=30, **kw)


def hojas_categorias(nodos, prefijo="", idpath=""):
    """Devuelve categorias hoja como (id_path, nombre_path).
    VTEX requiere el path completo de IDs: fq=C:/1/2/15/."""
    out = []
    for n in nodos:
        nombre = f"{prefijo}{n['name']}"
        ruta = f"{idpath}{n['id']}/"
        hijos = n.get("children") or []
        if hijos:
            out += hojas_categorias(hijos, nombre + " > ", ruta)
        else:
            out.append((ruta, nombre))
    return out


def precio_item(it):
    try:
        offer = it["sellers"][0]["commertialOffer"]
        return offer.get("Price"), offer.get("ListPrice")
    except Exception:
        return None, None


def scrape_vtex(base, tienda, max_cats=0, delay=0.25):
    base = base.rstrip("/")
    hoy = datetime.date.today().isoformat()
    r = get(f"{base}/api/catalog_system/pub/category/tree/5")
    if r.status_code not in (200, 206):
        print(f"  no se pudo leer arbol de categorias (HTTP {r.status_code})")
        return []
    cats = hojas_categorias(r.json())
    print(f"  {len(cats)} categorias hoja", flush=True)
    if max_cats:
        cats = cats[:max_cats]
    by_sku = {}
    for i, (cidpath, cname) in enumerate(cats, 1):
        frm = 0
        while frm < 2500:
            url = (f"{base}/api/catalog_system/pub/products/search/"
                   f"?fq=C:/{cidpath}&_from={frm}&_to={frm + 49}")
            try:
                r = get(url)
            except Exception as e:
                print(f"    err {cname} from {frm}: {e}", flush=True)
                break
            if r.status_code not in (200, 206):
                break
            try:
                data = r.json()
            except Exception:
                break
            if not data:
                break
            for p in data:
                marca = p.get("brand", "")
                for it in (p.get("items") or []):
                    sku = it.get("itemId")
                    if not sku or sku in by_sku:
                        continue
                    precio, lista = precio_item(it)
                    ean = it.get("ean", "")
                    by_sku[sku] = {
                        "SKU": sku,
                        "EAN": ean,
                        "Nombre": p.get("productName", ""),
                        "Precio": precio,
                        "PrecioLista": lista,
                        "Fecha": hoy,
                        "Categoria": cname,
                        "Marca": marca,
                        "Tienda": tienda,
                        "URL": (base + "/" + p.get("linkText", "") + "/p") if p.get("linkText") else "",
                    }
            if len(data) < 50:
                break
            frm += 50
            time.sleep(delay)
        if i % 10 == 0 or i == len(cats):
            print(f"    [{i}/{len(cats)}] {cname[:40]:40s} -> acum {len(by_sku)}", flush=True)
    return list(by_sku.values())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("base")
    ap.add_argument("tienda")
    ap.add_argument("--max-cats", type=int, default=0)
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    print(f"Scrapeando {args.tienda} (VTEX) ...", flush=True)
    filas = scrape_vtex(args.base, args.tienda, args.max_cats)
    if not filas:
        print("Sin productos.")
        return
    df = pd.DataFrame(filas)
    con_precio = df[df["Precio"].notna() & (df["Precio"] > 0)]
    base = args.out or f"precios_{args.tienda.lower().replace(' ', '_')}"
    df.to_excel(f"{base}.xlsx", index=False, engine="openpyxl")
    df.to_csv(f"{base}.csv", index=False, encoding="utf-8-sig")
    print(f"\nTotal SKUs: {len(df)} | con precio: {len(con_precio)} | categorias: {df['Categoria'].nunique()}")
    print(con_precio[["SKU", "Nombre", "Precio", "Categoria"]].head(8).to_string(index=False))
    print(f"Guardado: {base}.xlsx")


if __name__ == "__main__":
    main()
