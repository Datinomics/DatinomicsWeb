# -*- coding: utf-8 -*-
"""Scraper Shopify via /products.json (paginado)."""
import datetime
import re
import time

import requests
from . import diag

HOY = datetime.date.today().isoformat()
H = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
     "(KHTML, like Gecko) Chrome/124.0 Safari/537.36", "Accept": "*/*"}
_S = requests.Session()
_S.mount("https://", requests.adapters.HTTPAdapter(pool_connections=20, pool_maxsize=20, max_retries=2))


def precio_ar(s):
    s = re.sub(r"[^\d,.]", "", str(s))
    if not s:
        return None
    # shopify suele venir en formato 1234.56 (no AR)
    if "." in s and "," not in s:
        try:
            return round(float(s), 2)
        except ValueError:
            return None
    s = s.replace(".", "").replace(",", ".")
    try:
        return round(float(s), 2)
    except ValueError:
        return None


def scrape(base, tienda, max_pages=10, **_):
    rows = []
    for page in range(1, max_pages + 1):
        try:
            r = _S.get(f"{base}/products.json", params={"limit": 250, "page": page},
                       headers=H, timeout=25)
        except Exception as e:
            diag.fallo(type(e).__name__)
            break
        if r.status_code != 200:
            diag.fallo(f"HTTP {r.status_code}")
            break
        try:
            prods = r.json().get("products", [])
        except Exception:
            diag.fallo("JSON invalido")
            break
        if not prods:
            if page == 1:
                diag.fallo("catalogo vacio")
            break
        for p in prods:
            cat = p.get("product_type", "") or ""
            for v in (p.get("variants") or [{}]):
                rows.append({"SKU": v.get("sku") or v.get("id"),
                             "Nombre": p.get("title", ""),
                             "Precio": precio_ar(v.get("price")),
                             "Fecha": HOY, "Categoria": cat, "Tienda": tienda})
        time.sleep(0.2)
    return rows
