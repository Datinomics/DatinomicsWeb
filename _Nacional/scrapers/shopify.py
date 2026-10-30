# -*- coding: utf-8 -*-
"""Scraper Shopify via /products.json (paginado)."""
import datetime
import random
import re
import threading
import time

import requests
from urllib3.util.retry import Retry
from . import diag

HOY = datetime.date.today().isoformat()
H = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
     "(KHTML, like Gecko) Chrome/124.0 Safari/537.36", "Accept": "*/*"}
_S = requests.Session()
# Sin reintentos por status: urllib3 por defecto reintenta los 429 durmiendo el Retry-After
# en cada hilo (2 x 60s); las esperas las maneja _get con un turno compartido.
_S.mount("https://", requests.adapters.HTTPAdapter(
    pool_connections=20, pool_maxsize=20,
    max_retries=Retry(total=2, connect=2, read=2, status=0, respect_retry_after_header=False)))


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


# Shopify limita el catalogo publico por tienda ("local_rate_limited" + Retry-After).
# Todos los hilos comparten un turno (un pedido cada 3-5 s en total) y un 429 pausa
# solo a esa tienda el tiempo que pide Shopify; las demas siguen.
INTERVALO = (3.0, 5.0)  # segundos entre pedidos (al azar en el rango), compartido por todos los hilos
_turno = threading.Lock()
_proximo = [0.0]
_pausa_hasta = {}  # host -> time.time() hasta el que no se le pide nada


def _get(url, params, alternativas=()):
    """GET con turno compartido. Ante un 429 prueba las URLs alternativas (mismo
    contenido por otra ruta) y si todas lo dan pausa solo a esa tienda."""
    host = url.split("/")[2]
    for _ in range(4):
        for u in (url, *alternativas):
            espera = _pausa_hasta.get(host, 0) - time.time()
            if espera > 0:
                time.sleep(espera)
            with _turno:
                espera = _proximo[0] - time.time()
                if espera > 0:
                    time.sleep(espera)
                _proximo[0] = time.time() + random.uniform(*INTERVALO)
            r = _S.get(u, params=params, headers=H, timeout=25)
            if r.status_code != 429:
                return r
        try:
            pausa = float(r.headers.get("Retry-After", 0)) or 30
        except ValueError:
            pausa = 30
        _pausa_hasta[host] = time.time() + min(pausa, 120)
    return r


# Las dos rutas devuelven el mismo JSON (todo el catalogo) y Shopify les aplica el
# limite por separado: la pagina 1 sale de la primera que responda y el resto de las
# paginas de esa MISMA ruta (ordenan distinto: mezclarlas saltea productos).
RUTAS = ("/collections/all/products.json", "/products.json")


def scrape(base, tienda, max_pages=100, **_):
    rows, vistos = [], set()
    urls = [f"{base}{ruta}" for ruta in RUTAS]
    for page in range(1, max_pages + 1):
        r, err = None, None
        try:
            r = _get(urls[0], {"limit": 250, "page": page}, urls[1:] if page == 1 else ())
            if page == 1 and r.status_code == 200:
                urls = [u for u in urls if r.url.split("?")[0].endswith(u.split(base, 1)[1])][:1] or urls
        except Exception as e:
            err = e
        if r is None:
            diag.fallo(type(err).__name__)
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
                vid = v.get("id") or (p.get("id"), v.get("sku"))
                if vid in vistos:
                    continue
                vistos.add(vid)
                rows.append({"SKU": v.get("sku") or v.get("id"),
                             "Nombre": p.get("title", ""),
                             "Precio": precio_ar(v.get("price")),
                             "Fecha": HOY, "Categoria": cat, "Tienda": tienda})
        if len(prods) < 250:  # ultima pagina: no gastar un pedido mas
            break
    return rows
