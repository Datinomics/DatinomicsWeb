# -*- coding: utf-8 -*-
"""Scraper Tiendanube via HTML de /productos (regex sobre data-product-id)."""
import datetime
import re
import time

import requests

HOY = datetime.date.today().isoformat()
H = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
     "(KHTML, like Gecko) Chrome/124.0 Safari/537.36", "Accept": "*/*"}
_S = requests.Session()
_S.mount("https://", requests.adapters.HTTPAdapter(pool_connections=20, pool_maxsize=20, max_retries=2))


def precio_ar(s):
    s = re.sub(r"[^\d,]", "", str(s))
    if not s:
        return None
    s = s.replace(".", "").replace(",", ".")
    try:
        return round(float(s), 2)
    except ValueError:
        return None


def scrape(base, tienda, max_pages=40, **_):
    rows, seen = [], set()
    for page in range(1, max_pages + 1):
        try:
            r = _S.get(f"{base}/productos", params={"page": page}, headers=H, timeout=25)
        except Exception:
            break
        if r.status_code != 200 or "js-item-product" not in r.text:
            break
        h = r.text
        ids = [(m.start(), m.group(1)) for m in re.finditer(r'data-product-id="(\d+)"', h)]
        if not ids:
            break
        nuevos = 0
        for i, (pos, pid) in enumerate(ids):
            if pid in seen:
                continue
            chunk = h[pos: ids[i + 1][0] if i + 1 < len(ids) else pos + 4000]
            nm = re.search(r'js-item-name[^>]*>\s*([^<]+?)\s*<', chunk)
            pr = re.search(r'js-price-display[^>]*>\s*([^<]+?)\s*<', chunk)
            if not nm:
                continue
            seen.add(pid)
            nuevos += 1
            rows.append({"SKU": pid, "Nombre": nm.group(1).strip(),
                         "Precio": precio_ar(pr.group(1)) if pr else None,
                         "Fecha": HOY, "Categoria": "", "Tienda": tienda})
        if nuevos == 0:
            break
        time.sleep(0.3)
    return rows
