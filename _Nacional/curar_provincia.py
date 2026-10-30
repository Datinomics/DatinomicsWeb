# -*- coding: utf-8 -*-
"""
Curado de calidad de una provincia, de punta a punta:

  1) Relevo: junta todos los comercios de <Folder>_full.xlsx (todas las hojas
     menos las de descartados) y deduplica por dominio.
  2) Ubicacion: verificar_ubicacion.py confirma que cada comercio este en ESA
     provincia (OSM + direccion/CPA/coordenadas/telefono del propio sitio).
  3) Scrapeo: corre el ETL de precios sobre los verificados, en paralelo.
  4) Poda: reescribe <Folder>_full.xlsx dejando en 'Tiendas con web' solo los
     comercios verificados Y con datos scrapeados. El resto va a
     'Descartados (ubicacion)' / 'Descartados (sin datos)' con el motivo.
  5) Reporte: excels/reporte_curado_<Folder>.json + verificacion_<Folder>.xlsx.

Uso:
  py curar_provincia.py Corrientes
  py curar_provincia.py Corrientes Mendoza CABA --paralelo 3 --workers 16 --tope-seg 900
  py curar_provincia.py CABA --solo-verificar          # no scrapea ni toca el Excel
"""
import argparse
import datetime
import json
import os
import subprocess
import sys
import time

import pandas as pd

import etl
import geografia
import sepa
from ubicaciones import FOLDER_A_LETRA
from verificar_ubicacion import dominio, etiqueta_dominio, verificar_df

AQUI = os.path.dirname(os.path.abspath(__file__))
HOJA_OK = "Tiendas con web"
HOJA_UBIC = "Descartados (ubicacion)"
HOJA_SIN = "Descartados (sin datos)"


def rutas(folder):
    display, region = etl.cargar_provincias()[folder]
    d = os.path.join(etl.RAIZ, region, folder, "excels")
    return {"dir": d, "full": os.path.join(d, f"{folder}_full.xlsx"),
            "verif": os.path.join(d, f"verificacion_{folder}.xlsx"),
            "reporte": os.path.join(d, f"reporte_curado_{folder}.json")}


# columnas que agrega el curado: se descartan al releer para re-evaluar desde cero
COLS_CURADO = ["Verificacion", "Evidencia", "Plataforma usada", "Productos", "Estado scrape",
               "Motivo descarte", "Localidad", "Departamento", "Metodo zona"]
COLS_ZONA = ["Localidad", "Departamento", "Metodo zona"]


def relevar(full):
    """Todas las hojas del relevamiento, deduplicado por dominio (gana la primera:
    'Tiendas con web' antes que 'Candidatos'). Incluye las de descartados de una
    corrida anterior, asi una mejora del verificador puede rescatarlos."""
    with pd.ExcelFile(full) as xl:
        hojas = xl.sheet_names
        partes = []
        for s in hojas:
            d = xl.parse(s).drop(columns=COLS_CURADO, errors="ignore")
            if "Hoja origen" not in d.columns:
                d["Hoja origen"] = s
            partes.append(d)
    df = pd.concat(partes, ignore_index=True)
    df = df[df["URL"].notna() & (df["URL"].astype(str).str.strip() != "")]
    df["_dom"] = df["URL"].map(dominio)
    antes = len(df)
    df = df.drop_duplicates("_dom").drop(columns="_dom").reset_index(drop=True)
    return df, hojas, antes - len(df)


def escribir_excel(path, hojas):
    """Escritura atomica (tmp + replace)."""
    tmp = path + ".tmp.xlsx"
    with pd.ExcelWriter(tmp, engine="openpyxl") as xl:
        for nombre, d in hojas.items():
            d.to_excel(xl, sheet_name=nombre[:31], index=False)
            sh = xl.sheets[nombre[:31]]
            for i, col in enumerate(d.columns):
                ancho = 60 if col in ("Evidencia", "Motivo descarte") else 34 if col in ("Empresa", "URL") else 16
                sh.column_dimensions[sh.cell(1, i + 1).column_letter].width = ancho
            sh.freeze_panes = "A2"
    os.replace(tmp, path)


def agregar_zona(df, folder):
    """Ciudad / partido / barrio de cada comercio verificado (ver geografia.zona_de_evidencia)."""
    origen = df["Origen"].astype(str) if "Origen" in df.columns else pd.Series("", index=df.index)
    zonas = [geografia.zona_de_evidencia(e, folder, o in ("Cadena nacional", "SEPA")) if v == "VERIFICADA" else {}
             for e, v, o in zip(df["Evidencia"], df["Verificacion"], origen)]
    z = pd.DataFrame(zonas, index=df.index).reindex(columns=COLS_ZONA).fillna("")
    return pd.concat([df.drop(columns=COLS_ZONA, errors="ignore"), z], axis=1)


def curar(folder, workers=16, workers_verif=32, tope_seg=900, solo_verificar=False):
    r = rutas(folder)
    t_total = time.time()
    rep = {"provincia": folder, "fecha": datetime.datetime.now().isoformat(timespec="seconds"),
           "workers_scrape": workers, "workers_verificacion": workers_verif, "tope_seg_por_local": tope_seg}
    print(f"\n==================== {folder} ====================", flush=True)

    # 1) relevo
    df, hojas_leidas, dups = relevar(r["full"])
    # banderas que informan a SEPA en la provincia y no teniamos relevadas (ej. Vea)
    nuevas = [b for b in sepa.banderas_en(FOLDER_A_LETRA[folder])
              if not any(sepa.clave_cobertura(d, {etiqueta_dominio(dominio(b["URL"])): 1})
                         for d in df["URL"].map(dominio))]
    if nuevas:
        df = pd.concat([df, pd.DataFrame([{"Empresa": b["Empresa"], "Sector": "Supermercado", "URL": b["URL"],
                                           "Tienda online": "Si", "Origen": "SEPA", "Hoja origen": "SEPA"}
                                          for b in nuevas])], ignore_index=True)
        print(f"  + {len(nuevas)} banderas de SEPA que no estaban: {[b['Empresa'] for b in nuevas]}", flush=True)
    rep["agregadas_desde_sepa"] = [b["Empresa"] for b in nuevas]
    columnas_originales = [c for c in df.columns if c != "Hoja origen"]
    rep["relevados"] = len(df)
    rep["duplicados_quitados"] = dups
    rep["hojas_leidas"] = hojas_leidas
    print(f"  relevados: {len(df)} comercios unicos (de {hojas_leidas}; {dups} duplicados)", flush=True)

    # 2) ubicacion
    t = time.time()
    df = verificar_df(df, folder, workers=workers_verif)
    rep["seg_verificacion"] = round(time.time() - t, 1)
    rep["verificacion"] = df["Verificacion"].str.replace(r" \(.*", "", regex=True).value_counts().to_dict()
    rep["otra_ubicacion_detalle"] = df.loc[df["Verificacion"].str.startswith("OTRA"), "Verificacion"] \
        .value_counts().head(15).to_dict()
    df = agregar_zona(df, folder)
    rep["con_zona"] = int((df.loc[df["Verificacion"] == "VERIFICADA", "Localidad"] != "").sum())
    escribir_excel(r["verif"], {"Verificacion": df})
    verificados = df[df["Verificacion"] == "VERIFICADA"].copy()
    print(f"  verificacion: {rep['seg_verificacion']}s -> {rep['verificacion']}", flush=True)
    if solo_verificar:
        rep["seg_total"] = round(time.time() - t_total, 1)
        json.dump(rep, open(r["reporte"], "w", encoding="utf-8"), ensure_ascii=False, indent=2)
        return rep

    # 3) scrapeo de los verificados
    t = time.time()
    res = etl.correr_provincia(folder, df=verificados, filtrar_tienda=False, workers=workers, tope_seg=tope_seg)
    rep["seg_scrape"] = round(time.time() - t, 1)
    res = pd.DataFrame(res)
    if res.empty:
        res = pd.DataFrame(columns=["Dominio", "Plataforma usada", "Productos", "Con precio", "Segundos",
                                    "Estado scrape", "Motivo"])
    res = res.drop_duplicates("Dominio").set_index("Dominio")

    # 4) poda
    df["_dom"] = df["URL"].map(dominio)
    for col in ("Plataforma usada", "Productos", "Con precio", "Segundos", "Estado scrape", "Motivo"):
        df[col] = df["_dom"].map(res[col]) if col in res.columns else ""
    scrapeable = df["Estado scrape"].astype(str).str.startswith(("ok", "parcial", "cadena nacional", "ya scrapeada", "SEPA"))
    es_verif = df["Verificacion"] == "VERIFICADA"
    keep = es_verif & scrapeable
    cols_ok = columnas_originales + COLS_ZONA + ["Verificacion", "Evidencia", "Plataforma usada", "Productos",
                                                 "Estado scrape"]
    ok = df[keep][cols_ok].sort_values(["Sector", "Empresa"])
    desc_ubic = df[~es_verif].assign(**{"Motivo descarte": df.loc[~es_verif, "Verificacion"]})
    desc_sin = df[es_verif & ~scrapeable].assign(**{"Motivo descarte": df.loc[es_verif & ~scrapeable, "Motivo"]
                                                   .fillna("").replace("", "sin productos")})
    cols_desc = columnas_originales + ["Hoja origen", "Motivo descarte", "Evidencia"]
    escribir_excel(r["full"], {HOJA_OK: ok, HOJA_UBIC: desc_ubic[cols_desc], HOJA_SIN: desc_sin[cols_desc + ["Plataforma usada"]]})

    # 5) reporte
    scr = res[res["Estado scrape"].isin(["ok", "parcial (tope)", "sin datos"])]
    rep.update({
        "verificados": int(es_verif.sum()),
        "finales_en_excel": len(ok),
        "descartados_ubicacion": len(desc_ubic),
        "descartados_sin_datos": len(desc_sin),
        "scrapeados": int(len(scr)),
        "scrape_estados": res["Estado scrape"].astype(str).str.replace(r" \(master.*", "", regex=True).value_counts().to_dict(),
        "productos_totales": int(pd.to_numeric(scr["Productos"], errors="coerce").fillna(0).sum()),
        "seg_por_local_mediana": float(scr["Segundos"].median()) if len(scr) else 0,
        "seg_por_local_p90": float(scr["Segundos"].quantile(0.9)) if len(scr) else 0,
        "seg_suma_locales": float(scr["Segundos"].sum()) if len(scr) else 0,
        "por_plataforma": (scr.assign(ok=scr["Estado scrape"] != "sin datos")
                           .groupby("Plataforma usada")
                           .agg(locales=("ok", "size"), con_datos=("ok", "sum"), seg_mediana=("Segundos", "median"),
                                seg_total=("Segundos", "sum"))
                           .round(1).reset_index().to_dict("records")) if len(scr) else [],
        "mas_lentos": scr.sort_values("Segundos", ascending=False).head(10)
                        .reset_index()[["Dominio", "Plataforma usada", "Productos", "Segundos", "Estado scrape"]]
                        .to_dict("records") if len(scr) else [],
        "motivos_sin_datos": desc_sin["Motivo descarte"].astype(str).str[:40].value_counts().head(10).to_dict(),
    })
    rep["seg_total"] = round(time.time() - t_total, 1)
    json.dump(rep, open(r["reporte"], "w", encoding="utf-8"), ensure_ascii=False, indent=2, default=str)
    print(f"\n  {folder}: {rep['relevados']} relevados -> {rep['verificados']} verificados -> "
          f"{rep['finales_en_excel']} finales | verif {rep['seg_verificacion']}s, scrape {rep['seg_scrape']}s, "
          f"total {rep['seg_total']}s", flush=True)
    return rep


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("provincias", nargs="+", help="Folders (Corrientes, Mendoza, CABA, ...)")
    ap.add_argument("--workers", type=int, default=16, help="locales scrapeados a la vez")
    ap.add_argument("--workers-verif", type=int, default=32, help="sitios verificados a la vez")
    ap.add_argument("--tope-seg", type=int, default=900, help="tope de segundos por local (0 = sin tope)")
    ap.add_argument("--paralelo", type=int, default=1, help="provincias a la vez (subprocesos)")
    ap.add_argument("--solo-verificar", action="store_true")
    a = ap.parse_args()
    if a.paralelo > 1 and len(a.provincias) > 1:
        import concurrent.futures as cf

        def sub(p):
            log = open(os.path.join(rutas(p)["dir"], f"curado_{p}.log"), "w", encoding="utf-8")
            cmd = [sys.executable, "-X", "utf8", __file__, p, "--workers", str(a.workers),
                   "--workers-verif", str(a.workers_verif), "--tope-seg", str(a.tope_seg)]
            if a.solo_verificar:
                cmd.append("--solo-verificar")
            return p, subprocess.run(cmd, stdout=log, stderr=subprocess.STDOUT, cwd=AQUI).returncode

        with cf.ThreadPoolExecutor(max_workers=a.paralelo) as ex:
            for p, rc in ex.map(sub, a.provincias):
                print(f"{p}: terminado (rc={rc}) -> ver {rutas(p)['reporte']}", flush=True)
        return
    for p in a.provincias:
        curar(p, workers=a.workers, workers_verif=a.workers_verif, tope_seg=a.tope_seg,
              solo_verificar=a.solo_verificar)


if __name__ == "__main__":
    main()
