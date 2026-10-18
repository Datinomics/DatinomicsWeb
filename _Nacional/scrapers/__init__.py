# -*- coding: utf-8 -*-
"""
Paquete de scrapers de plataforma + dispatcher.

dispatch(plataforma, base, tienda) -> (filas, plataforma_usada)

- "shopify"        -> scrapers.shopify.scrape
- "vtex"           -> scrapers.vtex.scrape_vtex
- "tiendanube"     -> scrapers.tiendanube.scrape
- "woocommerce"    -> scrapers.woo.scrape_woo
- "magento"        -> scrapers.playwright_fb.scrape  (fallback DOM)
- "prestashop"     -> woo (intenta primero) -> playwright
- ""/"auto"/None   -> auto-detect probando en orden

Si el scraper devuelve [] (sin productos), igual se reporta la plataforma probada.
"""
import re

import requests

from . import shopify as _shopify
from . import tiendanube as _tiendanube

# scraper_vtex/woo/playwright_fb son los modulos originales con scrape_vtex(), scrape_woo()
try:
    from . import vtex as _vtex_mod
    from . import woo as _woo_mod
except Exception:
    _vtex_mod = _woo_mod = None
try:
    from . import playwright_fb as _pw_mod
except Exception:
    _pw_mod = None

H = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
     "(KHTML, like Gecko) Chrome/124.0 Safari/537.36", "Accept": "*/*"}
_S = requests.Session()
_S.mount("https://", requests.adapters.HTTPAdapter(pool_connections=20, pool_maxsize=20, max_retries=2))


def base_url(u):
    u = str(u).strip()
    if not u.startswith("http"):
        u = "https://" + u
    m = re.match(r"(https?://[^/]+)", u)
    return m.group(1) if m else u


def _try_shopify(base):
    try:
        r = _S.get(f"{base}/products.json", params={"limit": 1}, headers=H, timeout=15)
        return r.status_code == 200 and isinstance(r.json().get("products"), list) and bool(r.json()["products"])
    except Exception:
        return False


def _try_vtex(base):
    try:
        r = _S.get(f"{base}/api/catalog_system/pub/category/tree/1",
                   headers={**H, "Accept": "application/json"}, timeout=15)
        return r.status_code in (200, 206) and isinstance(r.json(), list)
    except Exception:
        return False


def _try_tiendanube(base):
    try:
        r = _S.get(f"{base}/productos", headers=H, timeout=15)
        return r.status_code == 200 and "js-item-product" in r.text
    except Exception:
        return False


def _try_woo(base):
    try:
        r = _S.get(f"{base}/wp-json/wc/store/products", params={"per_page": 1},
                   headers={**H, "Accept": "application/json"}, timeout=15)
        return r.status_code == 200 and isinstance(r.json(), list)
    except Exception:
        return False


def _run_shopify(base, tienda):
    return _shopify.scrape(base, tienda)


def _run_vtex(base, tienda):
    if _vtex_mod is None:
        return []
    return _vtex_mod.scrape_vtex(base, tienda, max_cats=40)


def _run_tiendanube(base, tienda):
    return _tiendanube.scrape(base, tienda)


def _run_woo(base, tienda):
    if _woo_mod is None:
        return []
    return _woo_mod.scrape_woo(base, tienda, max_pages=25)


def _run_playwright(base, tienda):
    if _pw_mod is None:
        return []
    try:
        return _pw_mod.scrape_playwright(base, tienda)
    except Exception:
        return []


def dispatch(plataforma, url, tienda):
    """plataforma: string de la columna Plataforma del relevamiento, o None/'' para auto.
    Devuelve (filas, plataforma_usada)."""
    base = base_url(url)
    plat = (plataforma or "").strip().lower()
    # normalizar valores compuestos (ej "vtex, magento" -> "vtex")
    if "," in plat:
        plat = plat.split(",")[0].strip()

    if plat == "shopify":
        return _run_shopify(base, tienda), "shopify"
    if plat == "vtex":
        return _run_vtex(base, tienda), "vtex"
    if plat == "tiendanube":
        return _run_tiendanube(base, tienda), "tiendanube"
    if plat in ("woocommerce", "woo", "wp"):
        return _run_woo(base, tienda), "woocommerce"
    if plat == "magento":
        return _run_playwright(base, tienda), "magento(playwright)"
    if plat == "prestashop":
        # Prestashop a veces expone Woo-like; sino playwright
        if _try_woo(base):
            return _run_woo(base, tienda), "woocommerce"
        return _run_playwright(base, tienda), "prestashop(playwright)"

    # Auto-detect
    if _try_shopify(base):
        return _run_shopify(base, tienda), "shopify"
    if _try_vtex(base):
        return _run_vtex(base, tienda), "vtex"
    if _try_tiendanube(base):
        return _run_tiendanube(base, tienda), "tiendanube"
    if _try_woo(base):
        return _run_woo(base, tienda), "woocommerce"
    return [], "no-soportada"
