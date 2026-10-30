# -*- coding: utf-8 -*-
"""Avisos de inmuebles de ZonaProp: precio, moneda, expensas, superficies, ambientes,
dormitorios, banos, barrio/localidad, coordenadas e inmobiliaria.
Los avisos vienen en el JSON window.__PRELOADED_STATE__ de cada pagina del listado
(30 por pagina). Cada busqueda es '<tipo>-<operacion>-<zona>' (ej. departamentos-venta-capital-federal)."""
import json
import re
import time

import pandas as pd

from . import Ritmo, sesion

BASE = "https://www.zonaprop.com.ar"
TIPOS = ("departamentos", "casas", "ph", "terrenos", "locales-comerciales", "oficinas-comerciales")
OPERACIONES = ("venta", "alquiler")
ZONAS = ("capital-federal", "mendoza", "corrientes")


def _estado(html):
    i = html.find("window.__PRELOADED_STATE__")
    if i < 0:
        return None
    return json.JSONDecoder().raw_decode(html[html.index("{", i):])[0]


def _feat(p, clave):
    v = (p.get("mainFeatures") or {}).get(clave) or {}
    try:
        return float(v.get("value"))
    except (TypeError, ValueError):
        return None


def _fila(p, busqueda):
    precio = next(iter((p.get("priceOperationTypes") or [{}])), {})
    monto = next(iter(precio.get("prices") or [{}]), {})
    loc = (p.get("postingLocation") or {})
    l1 = loc.get("location") or {}
    l2 = l1.get("parent") or {}
    geo = ((loc.get("postingGeolocation") or {}).get("geolocation")) or {}
    return {"Busqueda": busqueda, "Id": p.get("postingId"), "Titulo": p.get("title"),
            "Tipo": (p.get("realEstateType") or {}).get("name"),
            "Operacion": (precio.get("operationType") or {}).get("name"),
            "Precio": monto.get("amount") or None,  # 0 = "consultar precio" "Moneda": monto.get("currency"),
            "Expensas": (p.get("expenses") or {}).get("amount"),
            "Sup_total_m2": _feat(p, "CFT100"), "Sup_cubierta_m2": _feat(p, "CFT101"),
            "Ambientes": _feat(p, "CFT1"), "Dormitorios": _feat(p, "CFT2"), "Banos": _feat(p, "CFT3"),
            "Direccion": (loc.get("address") or {}).get("name"),
            "Barrio": l1.get("name"), "Ciudad": l2.get("name"),
            "Lat": geo.get("latitude"), "Lon": geo.get("longitude"),
            "Inmobiliaria": (p.get("publisher") or {}).get("name"),
            "URL": BASE + (p.get("url") or "")}


def descargar(tipos=TIPOS, operaciones=OPERACIONES, zonas=ZONAS, max_paginas=0, segundos=2.0, **_):
    """max_paginas: tope por busqueda (0 = todas). segundos: pausa entre pedidos."""
    s, ritmo, filas = sesion(), Ritmo(segundos), []
    for zona in zonas:
        for tipo in tipos:
            for op in operaciones:
                busqueda = f"{tipo}-{op}-{zona}"
                pagina, total = 1, None
                while True:
                    url = f"{BASE}/{busqueda}.html" if pagina == 1 else f"{BASE}/{busqueda}-pagina-{pagina}.html"
                    ritmo.esperar()
                    try:
                        r = s.get(url, timeout=40)
                    except Exception as e:
                        print(f"  zonaprop {busqueda} p{pagina}: {type(e).__name__}", flush=True)
                        break
                    if r.status_code in (403, 429):
                        print(f"  zonaprop {busqueda} p{pagina}: HTTP {r.status_code}, se corta la busqueda", flush=True)
                        time.sleep(30)
                        break
                    st = _estado(r.text) if r.status_code == 200 else None
                    if not st:
                        break
                    ls = st["listStore"]
                    total = ls["paging"]["totalPages"]
                    filas += [_fila(p, busqueda) for p in ls.get("listPostings") or []]
                    if pagina >= total or (max_paginas and pagina >= max_paginas):
                        break
                    pagina += 1
                print(f"  zonaprop {busqueda}: {pagina}/{total} paginas, {len(filas)} avisos acumulados", flush=True)
    df = pd.DataFrame(filas).drop_duplicates("Id")
    df["Fuente"] = "ZonaProp"
    return df
