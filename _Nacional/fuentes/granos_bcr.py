# -*- coding: utf-8 -*-
"""Precios pizarra de granos de la Camara Arbitral de Cereales de la Bolsa de Comercio
de Rosario ($/tn, entrega inmediata, pago contado, sobre camion en zona Rosario).
S/C = sin cotizacion: la Camara publica igual un precio estimado (columna Estimado)."""
import re
from html import unescape

import pandas as pd

from . import num_ar, sesion

URL = "https://www.cac.bcr.com.ar/es/precios-de-pizarra"


def descargar(**_):
    h = sesion().get(URL, timeout=40).text
    fecha = re.search(r"Precios Pizarra del d[ií]a (\d{2}/\d{2}/\d{4})", h)
    fecha = pd.to_datetime(fecha.group(1), dayfirst=True).date().isoformat() if fecha else None
    filas = []
    for bloque in re.split(r'<div class="board board-', h)[1:]:
        grano = unescape(re.sub(r"<[^>]+>", " ", re.search(r"(?s)<h3>(.*?)</h3>", bloque).group(1))).strip()
        precio = re.search(r'(?s)<div class="price">(.*?)</div>', bloque).group(1)
        estimado = "S/C" in precio
        pesos = re.search(r"\$\s*([\d.,]+)", precio)
        usd = re.search(r"(?s)US\$</strong>\s*(?:\(E\))?\s*([\d.,]+)", bloque)
        filas.append({"Fecha": fecha, "Grano": grano, "Plaza": "Rosario",
                      "Precio_ARS_tn": num_ar(pesos.group(1)) if pesos else None,
                      "Precio_USD_tn": num_ar(usd.group(1)) if usd else None,
                      "Estimado": estimado, "Fuente": "BCR - Camara Arbitral de Cereales"})
    return pd.DataFrame(filas)
