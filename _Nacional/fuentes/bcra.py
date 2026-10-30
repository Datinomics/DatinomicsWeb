# -*- coding: utf-8 -*-
"""Variables del BCRA (API publica): ultimo valor de cada variable monetaria (tasas,
tipos de cambio, reservas, CER, UVA...) y la cotizacion del dia de cada moneda."""
import pandas as pd

from . import sesion

API = "https://api.bcra.gob.ar"


def descargar(**_):
    s = sesion()
    variables, offset = [], 0
    while True:
        r = s.get(f"{API}/estadisticas/v4.0/monetarias", params={"limit": 1000, "offset": offset}, timeout=60).json()
        variables += r["results"]
        offset += len(r["results"])
        if not r["results"] or offset >= r["metadata"]["resultset"]["count"]:
            break
    v = pd.DataFrame(variables).rename(columns={"descripcion": "Descripcion", "ultFechaInformada": "Fecha",
                                                "ultValorInformado": "Valor", "unidadExpresion": "Unidad"})
    v["Tipo"] = "Variable monetaria"
    c = s.get(f"{API}/estadisticascambiarias/v1.0/Cotizaciones", timeout=60).json()["results"]
    m = pd.DataFrame(c["detalle"]).rename(columns={"descripcion": "Descripcion", "tipoCotizacion": "Valor"})
    m["Fecha"], m["Unidad"], m["Tipo"] = c["fecha"], "ARS por unidad", "Cotizacion"
    cols = ["Tipo", "Descripcion", "Fecha", "Valor", "Unidad", "idVariable", "categoria", "periodicidad",
            "codigoMoneda", "tipoPase"]
    df = pd.concat([v, m], ignore_index=True).reindex(columns=cols)
    df["Fuente"] = "BCRA"
    return df
