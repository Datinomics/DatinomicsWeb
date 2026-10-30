# -*- coding: utf-8 -*-
"""Precios vigentes en surtidor por estacion de servicio (Secretaria de Energia,
Resolucion 314/2016): empresa, bandera, direccion, localidad, provincia, producto,
horario (diurno/nocturno), precio, fecha de vigencia y coordenadas."""
import io

import pandas as pd

from . import sesion

DIAS_VIGENTE = 60
URL = ("http://datos.energia.gob.ar/dataset/1c181390-5045-475e-94dc-410429be4b17/resource/"
       "80ac25de-a44a-4445-9215-090cf55cfda5/download/precios-en-surtidor-resolucin-3142016.csv")


def descargar(**_):
    r = sesion().get(URL, timeout=180)
    r.raise_for_status()
    df = pd.read_csv(io.BytesIO(r.content), low_memory=False)
    df = df.drop(columns=["geojson"], errors="ignore")
    # el dataset guarda el ultimo precio informado por cada estacion, aunque sea de 2017:
    # solo sirven los que la estacion actualizo hace poco
    vig = pd.to_datetime(df["fecha_vigencia"], errors="coerce")
    df = df[vig >= vig.max() - pd.Timedelta(days=DIAS_VIGENTE)]
    df["Fuente"] = "Secretaria de Energia - Res. 314/2016"
    return df
