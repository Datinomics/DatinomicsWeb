# -*- coding: utf-8 -*-
"""
Corre las fuentes de precios externas (agro, combustibles, medicamentos, inmuebles,
BCRA) y guarda cada una con fuentes.guardar(). Las fuentes son independientes:
con --paralelo corren a la vez (cada una respeta su propio ritmo de pedidos).

Uso:
  py fuentes_externas.py                         # todas
  py fuentes_externas.py granos hacienda         # algunas
  py fuentes_externas.py zonaprop --max-paginas 3 --prueba
Reporte de la corrida: reportes/fuentes/reporte_fuentes.json
"""
import argparse
import concurrent.futures as cf
import importlib
import json
import os
import time
import traceback

from fuentes import RAIZ, guardar

FUENTES = {
    "granos": "granos_bcr",
    "hacienda": "hacienda_mag",
    "frutas_hortalizas": "mercado_central",
    "combustibles": "combustibles",
    "bcra": "bcra",
    "medicamentos": "medicamentos_alfabeta",
    "zonaprop": "inmuebles_zonaprop",
    "argenprop": "inmuebles_argenprop",
    "mercadolibre": "mercadolibre",
}


def correr(nombre, opciones):
    t0 = time.time()
    try:
        mod = importlib.import_module(f"fuentes.{FUENTES[nombre]}")
        df = mod.descargar(**opciones)
        xlsx = guardar(nombre, df) if len(df) else None
        res = {"Fuente": nombre, "Filas": len(df), "Segundos": round(time.time() - t0, 1), "Excel": xlsx,
               "Estado": "ok" if len(df) else "sin datos"}
    except Exception as e:
        traceback.print_exc()
        res = {"Fuente": nombre, "Filas": 0, "Segundos": round(time.time() - t0, 1), "Excel": None,
               "Estado": f"error: {type(e).__name__}: {e}"[:300]}
    print(f"{res['Fuente']:18s} {res['Filas']:9d} filas {res['Segundos']:8.1f}s  {res['Estado']}", flush=True)
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("fuentes", nargs="*", default=list(FUENTES))
    ap.add_argument("--paralelo", action="store_true", help="correr las fuentes a la vez")
    ap.add_argument("--max-paginas", type=int, default=0, help="tope de paginas por busqueda (inmuebles)")
    ap.add_argument("--prueba", action="store_true", help="corrida corta: pocas paginas / productos")
    a = ap.parse_args()
    opciones = {"max_paginas": a.max_paginas or (2 if a.prueba else 0)}
    if a.prueba:
        opciones.update(limite=300, dias=3)
    t0 = time.time()
    if a.paralelo:
        with cf.ThreadPoolExecutor(len(a.fuentes)) as ex:
            resultados = list(ex.map(lambda f: correr(f, opciones), a.fuentes))
    else:
        resultados = [correr(f, opciones) for f in a.fuentes]
    rep = {"segundos_total": round(time.time() - t0, 1), "paralelo": a.paralelo, "prueba": a.prueba,
           "fuentes": resultados}
    out = os.path.join(RAIZ, "reportes", "fuentes", "reporte_fuentes.json")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(rep, f, ensure_ascii=False, indent=2)
    print(f"total {rep['segundos_total']}s -> {out}")


if __name__ == "__main__":
    main()
