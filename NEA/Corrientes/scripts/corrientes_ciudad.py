# -*- coding: utf-8 -*-
"""
Estrategia mejorada para la CIUDAD DE CORRIENTES.
Ancla en comercios que REALMENTE operan en Corrientes (fuentes locales/oficiales),
busca el sitio de cada uno y verifica si tiene tienda online con precios (scrapeable).

SEED: nombres reales de retailers de Corrientes capital por rubro.
Para cada uno: usa la URL conocida o la descubre, verifica live + plataforma e-commerce.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "_Nacional"))

import concurrent.futures as cf
import re
import socket
import time

import pandas as pd
from ddgs import DDGS

from verificar_cadenas import _try_get, _candidatos, clasificar_tienda, ANTIBOT

socket.setdefaulttimeout(20)

EXCLUIR = ("facebook", "instagram", "linkedin", "tiktok", "youtube", "twitter",
           "mercadolibre", "tiendeo", "rappi", "pedidosya", "paginasamarillas",
           "guiaclarin", "cuitonline", "licuo", "infoisinfo", "kompass",
           "argentino.com", "promosdelbanco", "wikipedia", "aloo.com",
           "catalogosofertas", "ilacad", "dgrcorrientes", "gov.ar", "gob.ar",
           "google.", "wa.me", "ar.kompass", "mapcarta")

# (nombre, sector, url_conocida_o_None, origen)
SEED = [
    # ---- SUPERMERCADOS de Corrientes capital ----
    ("La Reina", "Supermercado", "https://www.lareinaonline.com.ar", "Local Corrientes"),
    ("Impulso", "Supermercado", "https://www.supermercadoimpulso.com.ar", "Local Corrientes"),
    ("Supermax", "Supermercado", "https://www.supermaxsa.com.ar", "Local Corrientes"),
    ("Tatu Supermercados", "Supermercado", None, "Local Corrientes"),
    ("Supermercado Norte Corrientes", "Supermercado", None, "Local Corrientes"),
    ("Supermercado del Sol Corrientes", "Supermercado", None, "Local Corrientes"),
    ("Parada Canga", "Supermercado", None, "Local Corrientes"),
    ("Supermercados Big Corrientes", "Supermercado", None, "Local Corrientes"),
    ("Carrefour", "Supermercado", "https://www.carrefour.com.ar", "Cadena (opera en Ctes)"),
    ("ChangoMas", "Supermercado", "https://www.masonline.com.ar", "Cadena (opera en Ctes)"),
    ("Coto", "Supermercado", "https://www.cotodigital3.com.ar", "Cadena (opera en Ctes)"),
    # ---- FARMACIAS de Corrientes capital ----
    ("Central Oeste", "Farmacia", "https://www.centraloeste.com.ar", "Local Corrientes/NEA"),
    ("Farmalife Corrientes", "Farmacia", None, "Local/regional"),
    ("Farmar Corrientes", "Farmacia", None, "Local Corrientes"),
    ("Farmacia del Mercosur Corrientes", "Farmacia", None, "Local Corrientes"),
    ("Punto Farma Corrientes", "Farmacia", None, "Local/regional NEA"),
    ("Farmacias Pasteur Corrientes", "Farmacia", None, "Local Corrientes"),
]


def dominio(u):
    try:
        return u.split("//")[-1].split("/")[0].lower().replace("www.", "")
    except Exception:
        return u


_d = None
def buscar_url(nombre):
    """Busca el sitio oficial de un comercio (primer resultado no-directorio)."""
    global _d
    for intento in range(3):
        try:
            if _d is None:
                _d = DDGS(timeout=20)
            res = list(_d.text(f"{nombre} tienda online sitio oficial", region="ar-es", max_results=8))
            for r in res:
                u = r.get("href") or ""
                dom = dominio(u)
                if u and not any(x in dom for x in EXCLUIR):
                    return u
            return ""
        except Exception:
            _d = None
            time.sleep(8)
    return ""


def procesar(item):
    nombre, sector, url, origen = item
    if not url:
        url = buscar_url(nombre)
    res = {"Empresa": nombre, "Sector": sector, "URL": url or "(no encontrada)",
           "Origen": origen, "Estado": "", "Tienda online": "", "Plataforma": "",
           "Menciona Corrientes": ""}
    if not url:
        res["Estado"] = "sin web"
        res["Tienda online"] = "No"
        return res
    status = None
    for cand in _candidatos(url):
        status, final, html = _try_get(cand)
        if status is not None:
            break
    if status is None:
        res["Estado"] = "No responde"
        res["Tienda online"] = "No"
        return res
    res["Estado"] = "OK 200" if status == 200 else (
        f"Activo (anti-bot {status})" if status in ANTIBOT else f"HTTP {status}")
    res["URL"] = final or url
    res["Tienda online"], res["Plataforma"] = clasificar_tienda(status, html)
    res["Menciona Corrientes"] = "Si" if "corrientes" in (html or "").lower() else ""
    return res


def main():
    print(f"Procesando {len(SEED)} retailers reales de Corrientes...", flush=True)
    out = []
    # discovery secuencial (ddgs), verificacion puede ser concurrente luego
    for item in SEED:
        r = procesar(item)
        out.append(r)
        print(f"  {r['Empresa'][:34]:34s} {r['Estado']:18s} tienda={r['Tienda online']:20s} {r['URL'][:40]}", flush=True)
        time.sleep(2)

    df = pd.DataFrame(out, columns=["Empresa", "Sector", "URL", "Tienda online",
                                    "Plataforma", "Estado", "Menciona Corrientes", "Origen"])
    df = df.sort_values(["Sector", "Empresa"], kind="stable")
    with pd.ExcelWriter("corrientes_ciudad.xlsx", engine="openpyxl") as xl:
        df.to_excel(xl, sheet_name="Corrientes ciudad", index=False)
        sh = xl.sheets["Corrientes ciudad"]
        for col, w in zip("ABCDEFGH", (32, 18, 46, 20, 16, 18, 18, 22)):
            sh.column_dimensions[col].width = w
        sh.freeze_panes = "A2"
    scrap = df[df["Tienda online"].isin(["Si", "Probable (anti-bot)"])]
    print(f"\nTotal: {len(df)} | con tienda online (scrapeable): {len(scrap)}")
    print("Guardado: corrientes_ciudad.xlsx")


if __name__ == "__main__":
    main()
