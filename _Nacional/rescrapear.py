# -*- coding: utf-8 -*-
"""
Re-scrapea locales puntuales de una provincia ya curada y reemplaza su hoja en
precios_<Rubro>_<Folder>.xlsx (y la columna Productos de <Folder>_full.xlsx).

Uso:
  py rescrapear.py Mendoza --productos 440          # los que quedaron con exactamente 440
  py rescrapear.py CABA --dominios a.com.ar b.com   # dominios puntuales

Los dominios que estaban en 'Descartados (sin datos)' y ahora traen productos pasan
a 'Tiendas con web'.
"""
import argparse
import concurrent.futures as cf
import os

import pandas as pd

import etl
from curar_provincia import HOJA_OK, HOJA_SIN, escribir_excel, rutas
from verificar_ubicacion import dominio


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("provincia")
    ap.add_argument("--dominios", nargs="*", default=[])
    ap.add_argument("--productos", type=int, default=None, help="re-scrapear los que tienen exactamente N productos")
    ap.add_argument("--workers", type=int, default=16)
    ap.add_argument("--tope-seg", type=int, default=900)
    a = ap.parse_args()
    r = rutas(a.provincia)
    with pd.ExcelFile(r["full"]) as xl:
        hojas_full = {s: xl.parse(s) for s in xl.sheet_names}
    ok = hojas_full[HOJA_OK]
    ok["dom"] = ok["URL"].map(dominio)
    sin = hojas_full.get(HOJA_SIN, pd.DataFrame(columns=ok.columns))
    sin["dom"] = sin["URL"].map(dominio)
    rescatar = sin[sin["dom"].isin(a.dominios)]
    ok = pd.concat([ok, rescatar], ignore_index=True)
    sin = sin.drop(rescatar.index)
    sel = ok["dom"].isin(a.dominios)
    if a.productos is not None:
        sel |= pd.to_numeric(ok["Productos"], errors="coerce") == a.productos
    tareas = ok[sel].fillna("").copy()
    tareas["rubro"] = tareas["Sector"].map(etl.rubro_de)
    print(f"{a.provincia}: re-scrapeando {len(tareas)} locales", flush=True)

    with cf.ThreadPoolExecutor(max_workers=a.workers) as ex:
        resultados = list(ex.map(lambda t: etl._scrapear_local(t[1], a.tope_seg), tareas.iterrows()))

    por_rubro = {}
    for (_, t), (res, filas) in zip(tareas.iterrows(), resultados):
        print(f"  {res['Empresa'][:34]:34s} {res['Productos']:6d} prod {res['Segundos']:6.1f}s {res['Estado scrape']}", flush=True)
        if not filas:
            if t["dom"] in set(rescatar["dom"]):  # sigue sin datos: vuelve a descartados
                sin = pd.concat([sin, ok[ok["dom"] == t["dom"]]], ignore_index=True)
                ok = ok[ok["dom"] != t["dom"]]
            continue  # se queda con lo que tenia
        por_rubro.setdefault(t["rubro"], []).append((t["dom"], res, filas))
        ok.loc[ok["dom"] == t["dom"], ["Productos", "Estado scrape"]] = [res["Productos"], res["Estado scrape"]]

    for rubro, items in por_rubro.items():
        out = os.path.join(r["dir"], f"precios_{rubro}_{a.provincia}.xlsx")
        hojas, doms = etl.cargar_hojas_previas(out)
        hoja_de = {d: h for h, d in doms.items()}
        usados = set(hojas)
        for dom, res, filas in items:
            d = pd.DataFrame(filas).reindex(columns=["SKU", "Nombre", "Precio", "Fecha", "Categoria"])
            sh = hoja_de.get(dom) or etl.sheet_name(res["Empresa"], usados)
            hojas[sh] = d
            doms[sh] = dom
        etl.guardar_rubro(out, hojas, doms)
    hojas_full[HOJA_OK] = ok.drop(columns="dom")
    if HOJA_SIN in hojas_full:
        hojas_full[HOJA_SIN] = sin.drop(columns="dom")
    escribir_excel(r["full"], hojas_full)
    print("listo", flush=True)


if __name__ == "__main__":
    main()
