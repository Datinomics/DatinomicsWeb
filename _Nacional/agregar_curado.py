# -*- coding: utf-8 -*-
"""
Toma el CURADO_NACIONAL de relevar_provincia.py, verifica cada dominio una
sola vez (rapido, threaded) y mergea los activos a los <provincia>_full.xlsx
de las provincias indicadas (Buenos-Aires, CABA por default). Suma sin pisar:
si el dominio ya esta -> no duplica. Sirve para garantizar que marcas de
shoppings como Le Utthe queden listadas sin esperar a ddgs.

Uso: py agregar_curado.py [Folder1 Folder2 ...]   (default = Buenos-Aires CABA)
"""
import concurrent.futures as cf
import os
import sys
import shutil
import tempfile

import pandas as pd

from relevar_provincia import (
    CURADO_NACIONAL, PROVINCIAS, hacer_verificar, dominio,
)

COLS = ["Empresa", "Sector", "URL", "Tienda online", "Plataforma",
        "Menciona", "Estado", "Origen"]


def verificar_curado():
    """Verifica CURADO_NACIONAL una sola vez. terminos vacios -> Menciona=''. """
    verificar = hacer_verificar([])
    tareas = [(n, s, u, "Cadena nacional") for n, s, u in CURADO_NACIONAL]
    out = []
    with cf.ThreadPoolExecutor(max_workers=16) as ex:
        for r in ex.map(verificar, tareas):
            out.append(r)
    return pd.DataFrame(out)


def safe_read(salida):
    """Lee el xlsx aunque el original este lockeado por Excel."""
    try:
        return pd.ExcelFile(salida)
    except PermissionError:
        tmp = os.path.join(tempfile.gettempdir(), os.path.basename(salida))
        shutil.copy(salida, tmp)
        return pd.ExcelFile(tmp)


def safe_write(salida, principal, revisar):
    try:
        target = salida
        with pd.ExcelWriter(target, engine="openpyxl") as xl:
            principal.to_excel(xl, sheet_name="Tiendas con web", index=False)
            revisar.to_excel(xl, sheet_name="Candidatos (revisar)", index=False)
            for sh in xl.sheets.values():
                for c, w in zip("ABCDEFGH", (32, 24, 44, 16, 16, 12, 16, 18)):
                    sh.column_dimensions[c].width = w
                sh.freeze_panes = "A2"
        return target
    except PermissionError:
        base, ext = os.path.splitext(salida)
        target = base + "_NEW" + ext
        with pd.ExcelWriter(target, engine="openpyxl") as xl:
            principal.to_excel(xl, sheet_name="Tiendas con web", index=False)
            revisar.to_excel(xl, sheet_name="Candidatos (revisar)", index=False)
            for sh in xl.sheets.values():
                for c, w in zip("ABCDEFGH", (32, 24, 44, 16, 16, 12, 16, 18)):
                    sh.column_dimensions[c].width = w
                sh.freeze_panes = "A2"
        return target


def main():
    sel = sys.argv[1:] or ["Buenos-Aires", "CABA"]
    print(f"Verificando {len(CURADO_NACIONAL)} cadenas/marcas del CURADO_NACIONAL...", flush=True)
    df_cur = verificar_curado()
    activos = df_cur[df_cur["Estado"].str.startswith(("OK", "Activo"))]
    print(f"  {len(activos)} activos / {len(df_cur)} totales\n", flush=True)
    print(activos[["Empresa", "Estado", "Plataforma"]].to_string(index=False), flush=True)
    print()

    for folder in sel:
        if folder not in PROVINCIAS:
            print(f"  ?? {folder} no esta en PROVINCIAS, salteo", flush=True)
            continue
        display, region, _ = PROVINCIAS[folder]
        salida = os.path.join("..", region, folder, "excels", f"{folder}_full.xlsx")
        if not os.path.exists(salida):
            print(f"  ?? {salida} no existe, salteo", flush=True)
            continue

        xlp = safe_read(salida)
        prev_main = xlp.parse("Tiendas con web") if "Tiendas con web" in xlp.sheet_names else xlp.parse(xlp.sheet_names[0])
        prev_rev = xlp.parse("Candidatos (revisar)") if "Candidatos (revisar)" in xlp.sheet_names else pd.DataFrame(columns=COLS)
        prev_main = prev_main.reindex(columns=COLS).fillna("")
        prev_rev = prev_rev.reindex(columns=COLS).fillna("")

        # mergear: priorizar activos curados; lo que ya esta -> no duplicar
        nuevo = activos.reindex(columns=COLS).fillna("")
        merged = pd.concat([prev_main, nuevo], ignore_index=True)
        merged["_d"] = merged["URL"].map(dominio)
        merged = merged.drop_duplicates("_d").drop(columns="_d").sort_values(["Sector", "Empresa"])

        # los curados que se sumaron netos
        prev_doms = set(prev_main["URL"].map(dominio))
        nuevos_curados = nuevo[~nuevo["URL"].map(dominio).isin(prev_doms)]
        agregados = len(nuevos_curados)

        target = safe_write(salida, merged, prev_rev)
        nota = "" if target == salida else f" (lockeado -> {os.path.basename(target)})"
        print(f"  {display}: {len(prev_main)} -> {len(merged)} (+{agregados} curados){nota}", flush=True)
        if agregados:
            print("    nuevos:", ", ".join(nuevos_curados["Empresa"].tolist()), flush=True)


if __name__ == "__main__":
    main()
