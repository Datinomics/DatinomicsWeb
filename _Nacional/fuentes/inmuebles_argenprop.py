# -*- coding: utf-8 -*-
"""Avisos de inmuebles de Argenprop: precio, moneda, direccion/barrio, superficie,
ambientes, dormitorios, banos, antiguedad e inmobiliaria (tarjetas del listado HTML,
20 por pagina). Cada busqueda es '<tipo>/<operacion>/<zona>'."""
import re
import time
from html import unescape

import pandas as pd

from . import Ritmo, num_ar, sesion

BASE = "https://www.argenprop.com"
TIPOS = ("departamentos", "casas", "ph", "terrenos", "locales", "oficinas")
OPERACIONES = ("venta", "alquiler")
ZONAS = ("capital-federal", "mendoza", "corrientes")
RASGOS = {"superficie_cubierta": "Sup_cubierta_m2", "superficie_total": "Sup_total_m2",
          "cantidad_ambientes": "Ambientes", "cantidad_dormitorios": "Dormitorios",
          "cantidad_banos": "Banos", "antiguedad": "Antiguedad"}


def _texto(s):
    return re.sub(r"\s+", " ", unescape(re.sub(r"<[^>]+>", " ", s or ""))).strip()


def _campo(card, clase):
    m = re.search(rf'(?s)class="{clase}"[^>]*>(.*?)</(?:p|h2|div)>', card)
    return _texto(m.group(1)) if m else None


def _fila(card, busqueda):
    attr = dict(re.findall(r'\s(id|idtipooperacion|idmoneda|montooperacion)="([^"]*)"', card[:2500]))
    precio = _campo(card, "card__price") or ""
    fila = {"Busqueda": busqueda, "Id": attr.get("id"),
            "Titulo": _campo(card, "card__title"), "Direccion": _campo(card, "card__address"),
            "Moneda": "USD" if "USD" in precio else ("ARS" if "$" in precio else None),
            "Precio": num_ar(re.sub(r"(?s).*?(USD|\$)", "", precio, count=1)) if re.search(r"\d", precio) else None,
            "Expensas": num_ar(m.group(1)) if (m := re.search(r"\+\s*\$\s*([\d.]+)\s*expensas", precio)) else None,
            "Inmobiliaria": _campo(card, "card__agent-name"),
            "URL": BASE + m.group(1) if (m := re.search(r'href="(/[^"]+)"', card)) else None}
    for icono, valor in re.findall(r'(?s)basico1-icon-(\w+)"></i>\s*<span>(.*?)</span>', card):
        if icono in RASGOS:
            fila[RASGOS[icono]] = num_ar(re.match(r"\s*([\d.,]+)", _texto(valor)).group(1)) \
                if re.match(r"\s*[\d.,]+", _texto(valor)) else None
    return fila


def descargar(tipos=TIPOS, operaciones=OPERACIONES, zonas=ZONAS, max_paginas=0, segundos=2.0, **_):
    """max_paginas: tope por busqueda (0 = todas). segundos: pausa entre pedidos."""
    s, ritmo, filas, bloqueado = sesion(), Ritmo(segundos), [], False
    for zona in zonas:
        for tipo in tipos:
            for op in operaciones:
                if bloqueado:
                    break
                busqueda = f"{tipo}/{op}/{zona}"
                pagina = 1
                while True:
                    url = f"{BASE}/{busqueda}" + (f"?pagina-{pagina}" if pagina > 1 else "")
                    ritmo.esperar()
                    try:
                        r = s.get(url, timeout=40)
                    except Exception as e:
                        print(f"  argenprop {busqueda} p{pagina}: {type(e).__name__}", flush=True)
                        break
                    if r.status_code == 202 and not r.text:
                        # desafio anti-bots (WAF) que exige un navegador: no se esquiva, se corta la fuente
                        print(f"  argenprop {busqueda} p{pagina}: desafio anti-bots (HTTP 202), se corta", flush=True)
                        bloqueado = True
                        break
                    if r.status_code in (403, 429):
                        print(f"  argenprop {busqueda} p{pagina}: HTTP {r.status_code}, se corta la busqueda", flush=True)
                        time.sleep(30)
                        break
                    cards = re.split(r'<div class="listing__item ', r.text)[1:] if r.status_code == 200 else []
                    nuevas = [_fila(c, busqueda) for c in cards]
                    nuevas = [f for f in nuevas if f["Id"] and f["Id"] not in {x["Id"] for x in filas[-200:]}]
                    if not nuevas:
                        break
                    filas += nuevas
                    if max_paginas and pagina >= max_paginas:
                        break
                    pagina += 1
                print(f"  argenprop {busqueda}: {pagina} paginas, {len(filas)} avisos acumulados", flush=True)
    df = pd.DataFrame(filas, columns=["Busqueda", "Id"] if not filas else None).drop_duplicates("Id")
    df["Operacion"] = df["Busqueda"].str.split("/").str[1].str.capitalize()
    df["Tipo"] = df["Busqueda"].str.split("/").str[0].str.capitalize()
    df["Fuente"] = "Argenprop"
    return df
