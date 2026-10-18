# -*- coding: utf-8 -*-
"""Sondea los supermercados de Corrientes: detecta plataforma y prueba API de catalogo."""
import socket
import requests

socket.setdefaulttimeout(25)
H = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
     "(KHTML, like Gecko) Chrome/124.0 Safari/537.36",
     "Accept": "application/json,text/html,*/*"}

SUPERS = {
    "La Reina": "https://www.lareinaonline.com.ar",
    "Depot Express": "https://depotexpress.com.ar",
    "Cuchermercados": "https://www.cuchermercados.com.ar",
    "Cluster": "https://www.clustersupermercados.com.ar",
    "Carrefour": "https://www.carrefour.com.ar",
    "ChangoMas": "https://www.masonline.com.ar",
    "Coto": "https://www.cotodigital.com.ar",
    "Dia": "https://diaonline.supermercadosdia.com.ar",
    "Diarco": "https://www.diarco.com.ar",
    "Makro": "https://makro.com.ar",
    "DISANCO": "https://www.disanco.com.ar",
}


def get(url, **kw):
    try:
        return requests.get(url, headers=H, timeout=20, **kw)
    except Exception as e:
        return e


def detect_platform(base):
    r = get(base)
    if isinstance(r, Exception):
        return f"(home error: {type(r).__name__})", ""
    h = r.text.lower()
    for p in ("vtex", "tiendanube", "woocommerce", "magento", "shopify", "prestashop", "mercadoshops"):
        if p in h:
            return p, r.url
    return "??", r.url


def try_vtex(base):
    r = get(f"{base}/api/catalog_system/pub/products/search/?_from=0&_to=2")
    if isinstance(r, Exception) or r.status_code != 200:
        return None
    try:
        data = r.json()
    except Exception:
        return None
    if not isinstance(data, list) or not data:
        return None
    p = data[0]
    it = (p.get("items") or [{}])[0]
    sku = it.get("itemId")
    price = None
    try:
        price = it["sellers"][0]["commertialOffer"]["Price"]
    except Exception:
        pass
    cat = (p.get("categories") or [""])[0]
    return {"api": "VTEX", "sample": f"{p.get('productName')} | SKU {sku} | ${price} | {cat}"}


def try_woo(base):
    for path in ("/wp-json/wc/store/products?per_page=2",
                 "/wp-json/wc/store/v1/products?per_page=2"):
        r = get(base + path)
        if isinstance(r, Exception) or r.status_code != 200:
            continue
        try:
            data = r.json()
        except Exception:
            continue
        if isinstance(data, list) and data:
            p = data[0]
            price = p.get("prices", {}).get("price")
            return {"api": "WooCommerce", "sample": f"{p.get('name')} | SKU {p.get('sku')} | {price} | {[c.get('name') for c in p.get('categories',[])][:1]}"}
    return None


for nombre, base in SUPERS.items():
    plat, final = detect_platform(base)
    api = try_vtex(base) or try_woo(base)
    estado = api["api"] if api else "sin API publica (?)"
    print(f"{nombre:16s} | plataforma: {plat:12s} | API: {estado}")
    if api:
        print(f"                   ejemplo: {api['sample']}")
