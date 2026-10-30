# -*- coding: utf-8 -*-
"""
Fuentes de precios que no son comercios con tienda online: agro (granos, hacienda,
frutas y hortalizas), combustibles, medicamentos, inmuebles y variables del BCRA.

Cada modulo expone descargar(**opciones) -> DataFrame (una fila por precio).
fuentes_externas.py los corre y guarda con guardar():
  datos/fuentes/<fuente>/<fuente>_<fecha>.parquet   (historico, uno por corrida)
  reportes/fuentes/<fuente>.xlsx                    (ultima corrida)
"""
import datetime
import os
import re
import threading
import time

import pandas as pd
import requests

RAIZ = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
HOY = datetime.date.today().isoformat()
H = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
     "(KHTML, like Gecko) Chrome/124.0 Safari/537.36",
     "Accept-Language": "es-AR,es;q=0.9"}
FILAS_EXCEL = 1_000_000  # Excel admite 1.048.576 filas por hoja


def sesion(conexiones=8):
    s = requests.Session()
    s.headers.update(H)
    s.mount("https://", requests.adapters.HTTPAdapter(pool_connections=conexiones, pool_maxsize=conexiones,
                                                      max_retries=2))
    s.mount("http://", requests.adapters.HTTPAdapter(max_retries=2))
    return s


class Ritmo:
    """Espaciado minimo entre pedidos a un mismo sitio, compartido por todos los hilos."""

    def __init__(self, segundos):
        self.segundos, self._lock, self._proximo = segundos, threading.Lock(), 0.0

    def esperar(self):
        with self._lock:
            espera = self._proximo - time.time()
            if espera > 0:
                time.sleep(espera)
            self._proximo = time.time() + self.segundos


def num_ar(s):
    """'$1.234,56' / '1.234' / '3600,000' -> float (formato argentino)."""
    s = re.sub(r"[^\d,.-]", "", str(s))
    if not s or s in "-.,":
        return None
    s = s.replace(".", "").replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return None


def guardar(fuente, df):
    """Parquet historico + Excel de la ultima corrida. Devuelve la ruta del Excel."""
    dir_datos = os.path.join(RAIZ, "datos", "fuentes", fuente)
    dir_rep = os.path.join(RAIZ, "reportes", "fuentes")
    os.makedirs(dir_datos, exist_ok=True)
    os.makedirs(dir_rep, exist_ok=True)
    df.to_parquet(os.path.join(dir_datos, f"{fuente}_{HOY}.parquet"), index=False, compression="zstd")
    xlsx = os.path.join(dir_rep, f"{fuente}.xlsx")
    tmp = xlsx + ".tmp.xlsx"
    with pd.ExcelWriter(tmp, engine="openpyxl") as xl:
        for i in range(0, max(len(df), 1), FILAS_EXCEL):
            hoja = fuente[:28] if i == 0 else f"{fuente[:24]}_{i // FILAS_EXCEL + 1}"
            df.iloc[i:i + FILAS_EXCEL].to_excel(xl, sheet_name=hoja, index=False)
        for sh in xl.sheets.values():
            sh.freeze_panes = "A2"
            sh.auto_filter.ref = sh.dimensions
    os.replace(tmp, xlsx)
    return xlsx
