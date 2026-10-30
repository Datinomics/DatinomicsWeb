# -*- coding: utf-8 -*-
"""Precios mayoristas de frutas y hortalizas del Mercado Central de Buenos Aires.
La pagina publica un zip por mes y rubro con un XLS por dia (RHddmmaa = hortalizas,
RFddmmaa = frutas). Por bulto y por kilo: maximo (MA), mas frecuente (MO), minimo (MI).
Solo se leen los XLS: algunos zips traen ademas archivos ajenos que se ignoran."""
import io
import os
import re
import zipfile

import pandas as pd
import xlrd

from . import sesion

PAGINA = "https://mercadocentral.gob.ar/informaci%C3%B3n/precios-mayoristas"
RE_XLS = re.compile(r"^R([HF])(\d{2})(\d{2})(\d{2})\.XLS$", re.I)
MESES = {m: i for i, m in enumerate(["ENERO", "FEBRERO", "MARZO", "ABRIL", "MAYO", "JUNIO", "JULIO", "AGOSTO",
                                     "SEPTIEMBRE", "OCTUBRE", "NOVIEMBRE", "DICIEMBRE"], 1)}


def _mes_de(url):
    n = re.sub(r"[^A-Z]", " ", url.rsplit("/", 1)[1].upper().replace("SEPTIENBRE", "SEPTIEMBRE"))
    return next((i for m, i in MESES.items() if m in n), 0)


def _leer_xls(nombre, contenido):
    m = RE_XLS.match(nombre.rsplit("/", 1)[-1])
    with open(os.devnull, "w") as nulo:  # xlrd avisa por cada XLS que no trae pagina de codigos
        libro = xlrd.open_workbook(file_contents=contenido, logfile=nulo)
    d = pd.read_excel(libro, header=0, engine="xlrd")
    d.columns = [re.sub(r"\d{6}$", "", str(c)).strip() for c in d.columns]
    d = d[d["VAR"].astype(str) != "Prom.Esp."]  # filas de promedio por especie
    d = d.rename(columns={"ESP": "Especie", "VAR": "Variedad", "PROC": "Procedencia", "ENV": "Envase",
                          "KG": "Kg_bulto", "CAL": "Calidad", "TAM": "Tamano", "GRADO": "Grado",
                          "MA": "Max_bulto", "MO": "Frecuente_bulto", "MI": "Min_bulto",
                          "MAPK": "Max_kg", "MOPK": "Frecuente_kg", "MIPK": "Min_kg"})
    d.insert(0, "Fecha", f"20{m.group(4)}-{m.group(3)}-{m.group(2)}")
    d.insert(1, "Rubro", "Hortalizas" if m.group(1).upper() == "H" else "Frutas")
    return d


def descargar(meses=1, **_):
    """meses: cuantos meses hacia atras (1 = solo el ultimo publicado)."""
    s = sesion()
    h = s.get(PAGINA, timeout=40).text
    zips = sorted(set(re.findall(r'href="([^"]+precios_mayoristas/[^"]+\.zip)"', h, re.I)), key=_mes_de)
    elegidos = {m for m in sorted({_mes_de(u) for u in zips})[-meses:]}
    partes = []
    for url in zips:
        if _mes_de(url) not in elegidos:
            continue
        zf = zipfile.ZipFile(io.BytesIO(s.get(url, timeout=120).content))
        for nombre in zf.namelist():
            if RE_XLS.match(nombre.rsplit("/", 1)[-1]):
                partes.append(_leer_xls(nombre, zf.read(nombre)))
    df = pd.concat(partes, ignore_index=True) if partes else pd.DataFrame()
    if not df.empty:
        df["Fuente"] = "Mercado Central de Buenos Aires"
    return df
