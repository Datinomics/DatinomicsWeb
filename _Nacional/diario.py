# -*- coding: utf-8 -*-
"""
Corrida diaria de extraccion. Corre igual en la PC y en GitHub Actions
(.github/workflows/extraccion_diaria.yml). Pasos:

  fuentes   fuentes externas: granos, hacienda, frutas y hortalizas, combustibles, BCRA,
            medicamentos (los lunes ademas inmuebles)
  sepa      baja el paquete SEPA del dia e ingesta (supermercados que informan precios)
  scrape    vuelve a scrapear los comercios curados ('Tiendas con web') que no estan en SEPA
  calidad   control de calidad del dia + comparacion con la corrida anterior
  db        carga lo del dia en PostgreSQL (db/cargar_db.py; necesita DATABASE_URL)

Lo de cada dia queda en datos/diario/<fecha>/:
  precios_<Folder>[_<shard>].parquet   una fila por producto: Provincia, Rubro, Comercio,
                                       Dominio, Localidad, Departamento, SKU, Nombre, Precio...
  corrida_<Folder>[_<shard>].json      estado y segundos por comercio
  calidad.json / calidad.xlsx          resultado del control

Las cadenas nacionales (Origen 'Cadena nacional') se scrapean una sola vez, en la
pseudo-provincia _cadenas, y no en cada provincia.

Uso:
  py diario.py fuentes sepa
  py diario.py scrape --provincias CABA Mendoza --workers 12 --tope-seg 600
  py diario.py scrape --provincias _cadenas
  py diario.py scrape --provincias CABA --shard 2/7      # un septimo de los comercios
  py diario.py calidad
"""
import argparse
import concurrent.futures as cf
import datetime
import glob
import json
import os
import time
import zlib

import pandas as pd

import etl
import sepa
from ubicaciones import FOLDER_A_LETRA
from verificar_ubicacion import dominio

HOY = datetime.date.today().isoformat()
DIR_DIA = os.path.join(etl.RAIZ, "datos", "diario", HOY)
CADENAS = "_cadenas"
FUENTES_DIARIAS = ["granos", "hacienda", "frutas_hortalizas", "combustibles", "bcra", "medicamentos",
                   "mercadolibre"]
FUENTES_SEMANALES = ["zonaprop"]  # lunes: listados grandes y sitios que limitan el ritmo
COLS = ["Provincia", "Rubro", "Comercio", "Dominio", "Localidad", "Departamento", "Plataforma",
        "SKU", "Nombre", "Precio", "Categoria", "Fecha"]


def paso_fuentes():
    import fuentes_externas
    nombres = FUENTES_DIARIAS + (FUENTES_SEMANALES if datetime.date.today().weekday() == 0 else [])
    with cf.ThreadPoolExecutor(len(nombres)) as ex:
        res = list(ex.map(lambda f: fuentes_externas.correr(f, {}), nombres))
    return {"fuentes": res}


def paso_sepa():
    t = time.time()
    path = sepa.descargar()
    sepa.ingestar(path)
    return {"sepa": os.path.basename(path), "segundos": round(time.time() - t, 1)}


def comercios(folder):
    """Comercios curados a scrapear de una provincia (o todas las cadenas nacionales)."""
    provs = etl.cargar_provincias()
    folders = list(provs) if folder == CADENAS else [folder]
    partes = []
    for f in folders:
        display, region = provs[f]
        full = os.path.join(etl.RAIZ, region, f, "excels", f"{f}_full.xlsx")
        if not os.path.exists(full):
            continue
        with pd.ExcelFile(full) as xl:
            if "Tiendas con web" not in xl.sheet_names:
                continue
            d = xl.parse("Tiendas con web").fillna("")
        if "Verificacion" not in d.columns:
            print(f"  {f}: sin curar (curar_provincia.py), no se scrapea", flush=True)
            continue
        d["Provincia"] = f
        partes.append(d)
    if not partes:
        return pd.DataFrame()
    df = pd.concat(partes, ignore_index=True)
    df["dom"] = df["URL"].map(dominio)
    df["rubro"] = df["Sector"].map(etl.rubro_de)
    for c in ("Plataforma", "Localidad", "Departamento", "Origen"):
        if c not in df.columns:
            df[c] = ""
    es_cadena = df["Origen"].astype(str) == "Cadena nacional"
    df = df[es_cadena] if folder == CADENAS else df[~es_cadena]
    df = df.drop_duplicates("dom")
    # lo que informa a SEPA en esa provincia toma los precios de SEPA
    cob = sepa.cobertura()
    en_sepa = [(cob.get(sepa.clave_cobertura(d, cob)) or {}).get(FOLDER_A_LETRA.get(p, ""), 0) > 0
               for d, p in zip(df["dom"], df["Provincia"])]
    if folder == CADENAS:  # una cadena que informa a SEPA en cualquier provincia sale de SEPA
        en_sepa = [bool(cob.get(sepa.clave_cobertura(d, cob))) for d in df["dom"]]
    return df[[not x for x in en_sepa]]


def paso_scrape(provincias, workers, tope_seg, shard=None):
    os.makedirs(DIR_DIA, exist_ok=True)
    resumen = {}
    for folder in provincias:
        df = comercios(folder)
        sufijo = ""
        if shard and len(df):
            k, n = shard
            df = df[[zlib.crc32(d.encode()) % n == k for d in df["dom"]]]
            sufijo = f"_{k}de{n}"
        print(f"\n#### {folder}{sufijo}: {len(df)} comercios a scrapear ({workers} hilos)", flush=True)
        t0, filas, estados = time.time(), [], []
        with cf.ThreadPoolExecutor(max(1, workers)) as ex:
            futs = {ex.submit(etl._scrapear_local, r, tope_seg): r for _, r in df.iterrows()}
            for i, fut in enumerate(cf.as_completed(futs), 1):
                r = futs[fut]
                res, prods = fut.result()
                estados.append({**res, "Provincia": r["Provincia"]})
                for p in prods:
                    filas.append({"Provincia": r["Provincia"], "Rubro": r["rubro"], "Comercio": res["Empresa"],
                                  "Dominio": r["dom"], "Localidad": r["Localidad"],
                                  "Departamento": r["Departamento"], "Plataforma": res["Plataforma usada"], **p})
                if i % 25 == 0 or i == len(futs):
                    print(f"  [{i}/{len(futs)} {time.time() - t0:5.0f}s] {len(filas):,} productos", flush=True)
        out = pd.DataFrame(filas).reindex(columns=COLS)
        out["Precio"] = pd.to_numeric(out["Precio"], errors="coerce")
        for c in ("SKU", "Nombre", "Categoria", "Fecha", "Localidad", "Departamento", "Comercio"):
            out[c] = out[c].astype("string")
        out.to_parquet(os.path.join(DIR_DIA, f"precios_{folder}{sufijo}.parquet"), index=False, compression="zstd")
        est = pd.DataFrame(estados)
        rep = {"provincia": folder, "shard": sufijo, "fecha": HOY, "segundos": round(time.time() - t0, 1),
               "comercios": len(df), "con_datos": int((est.get("Productos", pd.Series(dtype=int)) > 0).sum()),
               "productos": len(out), "estados": est.to_dict("records") if len(est) else []}
        with open(os.path.join(DIR_DIA, f"corrida_{folder}{sufijo}.json"), "w", encoding="utf-8") as f:
            json.dump(rep, f, ensure_ascii=False, indent=1, default=str)
        print(f"  {folder}{sufijo}: {rep['con_datos']}/{rep['comercios']} comercios con datos, "
              f"{rep['productos']:,} productos en {rep['segundos']}s", flush=True)
        resumen[folder + sufijo] = {k: v for k, v in rep.items() if k != "estados"}
    return resumen


def paso_calidad():
    """Control por comercio (control_calidad.revisar_comercio) y comparacion con la ultima
    corrida anterior: comercios que dejaron de traer datos y saltos de precio > 50%."""
    import control_calidad as cc
    archivos = sorted(glob.glob(os.path.join(DIR_DIA, "precios_*.parquet")))
    if not archivos:
        return {"calidad": "sin datos del dia"}
    hoy = pd.concat([pd.read_parquet(p) for p in archivos], ignore_index=True)
    filas = []
    for (prov, rubro, dom), d in hoy.groupby(["Provincia", "Rubro", "Dominio"]):
        filas.append({"Provincia": prov, "Rubro": rubro, "Dominio": dom, "Comercio": d["Comercio"].iloc[0],
                      **cc.revisar_comercio(d, rubro)})
    com = pd.DataFrame(filas)
    rep = {"fecha": HOY, "productos": len(hoy), "comercios": len(com),
           "estados": com["Estado"].value_counts().to_dict() if len(com) else {}}
    anteriores = sorted(d for d in glob.glob(os.path.join(etl.RAIZ, "datos", "diario", "*"))
                        if os.path.basename(d) < HOY and glob.glob(os.path.join(d, "precios_*.parquet")))
    if anteriores:
        ayer = pd.concat([pd.read_parquet(p) for p in glob.glob(os.path.join(anteriores[-1], "precios_*.parquet"))],
                         ignore_index=True)
        perdidos = sorted(set(ayer["Dominio"]) - set(hoy["Dominio"]))
        m = hoy.merge(ayer[["Dominio", "SKU", "Precio"]], on=["Dominio", "SKU"], suffixes=("", "_ant"))
        var = (m["Precio"] / m["Precio_ant"] - 1).dropna()
        rep["comparacion"] = {"contra": os.path.basename(anteriores[-1]), "productos_en_comun": len(m),
                              "con_cambio": int((var.abs() > 0.001).sum()),
                              "variacion_mediana_%": round(100 * float(var.median()), 2) if len(var) else 0,
                              "saltos_mayores_50%": int((var.abs() > 0.5).sum()),
                              "comercios_que_dejaron_de_traer_datos": perdidos[:200]}
    with pd.ExcelWriter(os.path.join(DIR_DIA, "calidad.xlsx"), engine="openpyxl") as xl:
        com.sort_values("Estado").to_excel(xl, "Comercios", index=False)
    with open(os.path.join(DIR_DIA, "calidad.json"), "w", encoding="utf-8") as f:
        json.dump(rep, f, ensure_ascii=False, indent=2, default=str)
    print(f"  calidad {HOY}: {rep['productos']:,} productos, {rep['comercios']} comercios -> {rep['estados']}",
          flush=True)
    return rep


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("pasos", nargs="+", choices=["fuentes", "sepa", "scrape", "calidad", "db"])
    ap.add_argument("--provincias", nargs="*", default=None, help="folders (o _cadenas); sin nada = todas + _cadenas")
    ap.add_argument("--workers", type=int, default=12)
    ap.add_argument("--tope-seg", type=int, default=600, help="tope por comercio")
    ap.add_argument("--shard", default=None, help="k/n: solo los comercios con crc32(dominio) %% n == k")
    a = ap.parse_args()
    shard = tuple(int(x) for x in a.shard.split("/")) if a.shard else None
    provincias = a.provincias or (list(etl.cargar_provincias()) + [CADENAS])
    t0, rep = time.time(), {"fecha": HOY, "pasos": a.pasos}
    for paso in a.pasos:
        if paso == "fuentes":
            rep.update(paso_fuentes())
        elif paso == "sepa":
            rep.update(paso_sepa())
        elif paso == "scrape":
            rep["scrape"] = paso_scrape(provincias, a.workers, a.tope_seg, shard)
        elif paso == "calidad":
            rep["calidad"] = paso_calidad()
        elif paso == "db":
            import subprocess
            import sys
            cmd = [sys.executable, "-X", "utf8", os.path.join(os.path.dirname(os.path.abspath(__file__)), "db",
                                                             "cargar_db.py"), "--solo", "precios", "sepa", "fuentes"]
            if a.provincias:
                cmd += ["--provincias", *[p for p in a.provincias if p != CADENAS]]
            rep["db"] = subprocess.run(cmd).returncode
    rep["segundos"] = round(time.time() - t0, 1)
    os.makedirs(DIR_DIA, exist_ok=True)
    nombre = "_".join(a.pasos) + (f"_{'-'.join(a.provincias)}" if a.provincias else "") + \
        (f"_{shard[0]}de{shard[1]}" if shard else "")
    with open(os.path.join(DIR_DIA, f"reporte_{nombre[:80]}.json"), "w", encoding="utf-8") as f:
        json.dump(rep, f, ensure_ascii=False, indent=2, default=str)


if __name__ == "__main__":
    main()
