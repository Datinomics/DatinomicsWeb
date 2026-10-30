# -*- coding: utf-8 -*-
"""Precios de hacienda del Mercado Agroganadero de Canuelas ($/kg vivo) por categoria:
minimo, maximo, promedio, mediana, cabezas, importe y kilos. Se consulta dia por dia
para tener la fecha de cada precio (los dias sin remate vuelven vacios)."""
import datetime
import re
from html import unescape

import pandas as pd

from . import Ritmo, num_ar, sesion

URL = "https://www.mercadoagroganadero.com.ar/dll/hacienda1.dll/haciinfo000002"
COLS = ["Minimo", "Maximo", "Promedio", "Mediana", "Cabezas", "Importe", "Kgs", "Kgs_prom"]


def _dia(s, fecha):
    f = fecha.strftime("%d/%m/%Y")
    datos = {"ID": "", "CP": "", "FLASH": "", "USUARIO": "SIN IDENTIFICAR", "OPCIONMENU": "",
             "OPCIONSUBMENU": "", "txtFechaIni": f, "txtFechaFin": f}
    h = s.post(URL, data=datos, timeout=40).text
    filas = []
    for tr in re.findall(r"(?is)<tr[^>]*>(.*?)</tr>", h):
        celdas = [unescape(re.sub(r"<[^>]+>", "", c)).strip() for c in re.findall(r"(?is)<td[^>]*>(.*?)</td>", tr)]
        celdas = [c for c in celdas if c]
        # fila de categoria: nombre + 8 numeros (las de subtotal empiezan con un numero)
        if len(celdas) == 9 and not re.match(r"[\d.,$-]", celdas[0]):
            fila = {"Fecha": fecha.isoformat(), "Categoria": celdas[0]}
            fila.update({c: num_ar(v) for c, v in zip(COLS, celdas[1:])})
            filas.append(fila)
    return filas


def descargar(dias=7, **_):
    s, ritmo, filas = sesion(), Ritmo(1.0), []
    hoy = datetime.date.today()
    for i in range(dias, -1, -1):
        ritmo.esperar()
        filas += _dia(s, hoy - datetime.timedelta(days=i))
    df = pd.DataFrame(filas)
    if not df.empty:
        df["Grupo"] = df["Categoria"].str.split().str[0]
        df["Plaza"], df["Unidad"] = "Canuelas", "$/kg vivo"
        df["Fuente"] = "Mercado Agroganadero de Canuelas"
    return df
