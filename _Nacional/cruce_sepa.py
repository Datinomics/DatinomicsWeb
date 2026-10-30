# -*- coding: utf-8 -*-
"""
Cruza un paquete SEPA (Sistema Electronico de Publicidad de Precios) contra
nuestros relevamientos <Folder>_full.xlsx de las 24 jurisdicciones.

Para cada bandera SEPA (ej. La Anonima, Topsy, Carrefour Express):
  - sucursales oficiales por provincia (sucursales.csv)
  - si esta en nuestra base (match por dominio web o por nombre), en que
    provincias y en que hoja (Tiendas con web / Descartados ...)
  - contraste: provincias donde SEPA tiene sucursales y nosotros no la tenemos,
    y provincias donde la tenemos pero SEPA no informa sucursales.

Uso: py cruce_sepa.py ruta/sepa_viernes.zip [--out reportes/sepa_vs_bases.xlsx]
"""
import argparse
import glob
import io
import os
import re
import zipfile
from collections import defaultdict

import pandas as pd

import etl
from ubicaciones import FOLDER_A_LETRA, LETRA_A_NOMBRE, norm
from verificar_ubicacion import compacto, dominio, etiqueta_dominio

LETRA_A_FOLDER = {v: k for k, v in FOLDER_A_LETRA.items()}
# dominios genericos que no identifican a una bandera
DOM_IGNORAR = {"", "nan", "facebook.com", "instagram.com", "google.com", "linktr.ee"}


def _csv(z, nombre):
    """Lee un csv de SEPA (separador |, utf-8 con BOM, con una linea final de 'Ultima actualizacion')."""
    crudo = z.read(nombre).decode("utf-8-sig", errors="replace")
    lineas = [l for l in crudo.splitlines() if l.count("|") >= 3]
    return pd.read_csv(io.StringIO("\n".join(lineas)), sep="|", dtype=str)


def leer_sepa(path):
    comercios, sucursales = [], []
    with zipfile.ZipFile(path) as z:
        for n in z.namelist():
            if not n.endswith(".zip"):
                continue
            try:
                with zipfile.ZipFile(io.BytesIO(z.read(n))) as iz:
                    nombres = iz.namelist()
                    if "comercio.csv" in nombres:
                        comercios.append(_csv(iz, "comercio.csv"))
                    if "sucursales.csv" in nombres:
                        sucursales.append(_csv(iz, "sucursales.csv"))
            except (zipfile.BadZipFile, KeyError, pd.errors.ParserError) as e:
                # SEPA publica tal cual lo que sube cada comercio: hay archivos rotos
                print(f"  AVISO: {os.path.basename(n)} ilegible ({type(e).__name__}), se saltea", flush=True)
    com = pd.concat(comercios, ignore_index=True).drop_duplicates(["id_comercio", "id_bandera"])
    suc = pd.concat(sucursales, ignore_index=True)
    # viene como "AR-B", pero algunos comercios cargan el nombre ("Buenos Aires")
    por_nombre = {norm(v): k for k, v in LETRA_A_NOMBRE.items()}
    por_nombre.update({"capital federal": "C", "ciudad autonoma de buenos aires": "C"})
    suc["letra"] = [str(v).replace("AR-", "").strip() if str(v).startswith("AR-")
                    else por_nombre.get(norm(v).strip(), "?") for v in suc["sucursales_provincia"]]
    return com, suc


def leer_bases():
    """Todas las filas de todos los <Folder>_full.xlsx, con provincia y hoja."""
    filas = []
    for f in glob.glob(os.path.join(etl.RAIZ, "*", "*", "excels", "*_full.xlsx")):
        folder = os.path.basename(f).replace("_full.xlsx", "")
        with pd.ExcelFile(f) as xl:
            for s in xl.sheet_names:
                d = xl.parse(s)
                if "URL" not in d.columns:
                    continue
                for emp, url in zip(d.get("Empresa", [""] * len(d)), d["URL"]):
                    filas.append({"Provincia": folder, "Hoja": s, "Empresa": str(emp), "URL": str(url),
                                  "dom": dominio(url), "nombre": compacto(emp)})
    return pd.DataFrame(filas)


def estado_hoja(hojas):
    """La 'mejor' hoja donde aparece: primero la principal."""
    for h in ("Tiendas con web", "Comercios Corrientes", "Candidatos (revisar)"):
        if h in hojas:
            return h
    return sorted(hojas)[0]


def cruzar(com, suc, base):
    por_dom = defaultdict(list)
    por_etq = defaultdict(list)
    for i, r in base.iterrows():
        if r["dom"] not in DOM_IGNORAR:
            por_dom[r["dom"]].append(i)
            por_etq[etiqueta_dominio(r["dom"])].append(i)
    nombres = base["nombre"].tolist()

    salida = []
    for _, c in com.iterrows():
        bandera = str(c["comercio_bandera_nombre"]).strip()
        url = str(c.get("comercio_bandera_url", "") or "")
        dom = dominio(url) if url and url != "nan" else ""
        s = suc[(suc["id_comercio"] == c["id_comercio"]) & (suc["id_bandera"] == c["id_bandera"])]
        prov_sepa = s["letra"].value_counts().to_dict()

        idx, via = [], ""
        if dom and dom not in DOM_IGNORAR:
            idx = por_dom.get(dom) or por_etq.get(etiqueta_dominio(dom), [])
            via = "dominio" if idx else ""
        nb = compacto(bandera)
        if not idx and len(nb) >= 4:
            # nombre exacto, o la bandera como palabra al inicio del nombre ("Carrefour Express" ~ "carrefour...")
            idx = [i for i, n in enumerate(nombres) if n == nb or (len(nb) >= 6 and n.startswith(nb))]
            via = "nombre" if idx else ""
        hits = base.loc[idx] if idx else base.iloc[0:0]
        en_base = defaultdict(set)
        for _, h in hits.iterrows():
            en_base[h["Provincia"]].add(h["Hoja"])
        prov_nuestras = {FOLDER_A_LETRA.get(p) for p in en_base}
        en_principal = {FOLDER_A_LETRA.get(p) for p, hs in en_base.items()
                        if estado_hoja(hs) in ("Tiendas con web", "Comercios Corrientes")}

        faltan = [LETRA_A_NOMBRE.get(l, l) for l in prov_sepa if l not in en_principal]
        sobran = [LETRA_A_NOMBRE.get(l, l) for l in en_principal if l and l not in prov_sepa]
        salida.append({
            "Bandera": bandera,
            "Razon social": c["comercio_razon_social"],
            "CUIT": c["comercio_cuit"],
            "URL SEPA": url,
            "Sucursales SEPA": len(s),
            "Provincias SEPA": ", ".join(f"{LETRA_A_NOMBRE.get(k, k)} ({v})" for k, v in
                                         sorted(prov_sepa.items(), key=lambda x: -x[1])),
            "En nuestra base": "Si" if en_base else "No",
            "Match por": via,
            "Donde la tenemos": "; ".join(f"{p}: {estado_hoja(hs)}" for p, hs in sorted(en_base.items())),
            "Provincias SEPA sin la bandera en hoja principal": ", ".join(faltan),
            "En hoja principal pero SEPA sin sucursales": ", ".join(sobran),
        })
    return pd.DataFrame(salida).sort_values(["En nuestra base", "Sucursales SEPA"], ascending=[False, False])


def contraste(com, suc, letras=("W", "M", "C")):
    """Banderas con sucursales SEPA en cada provincia vs lo que dijo verificar_ubicacion."""
    filas = []
    for letra in letras:
        folder = LETRA_A_FOLDER[letra]
        display, region = etl.cargar_provincias()[folder]
        excels = os.path.join(etl.RAIZ, region, folder, "excels")
        vf = os.path.join(excels, f"verificacion_{folder}.xlsx")
        ver = pd.read_excel(vf) if os.path.exists(vf) else pd.DataFrame(columns=["Empresa", "URL", "Verificacion"])
        ver["dom"] = ver["URL"].map(dominio)
        with pd.ExcelFile(os.path.join(excels, f"{folder}_full.xlsx")) as xl:
            final = xl.parse(xl.sheet_names[0])
        doms_final = set(final["URL"].map(dominio))
        n = suc[suc["letra"] == letra].groupby(["id_comercio", "id_bandera"]).size()
        for (idc, idb), cant in n.items():
            c = com[(com["id_comercio"] == idc) & (com["id_bandera"] == idb)].iloc[0]
            dom = dominio(c.get("comercio_bandera_url", "")) if str(c.get("comercio_bandera_url", "")) != "nan" else ""
            m = ver[(ver["dom"] == dom) | (ver["dom"].map(etiqueta_dominio) == etiqueta_dominio(dom))] if dom else ver.iloc[0:0]
            filas.append({"Provincia": display, "Bandera": c["comercio_bandera_nombre"], "Sucursales SEPA": cant,
                          "Dominio": dom, "Nuestra verificacion": m["Verificacion"].iloc[0] if len(m) else "no estaba relevada",
                          "Queda en Excel final": "Si" if dom and dom in doms_final else "No"})
    return pd.DataFrame(filas).sort_values(["Provincia", "Sucursales SEPA"], ascending=[True, False])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("zip")
    ap.add_argument("--out", default=os.path.join(etl.RAIZ, "reportes", "sepa_vs_bases.xlsx"))
    a = ap.parse_args()
    com, suc = leer_sepa(a.zip)
    base = leer_bases()
    res = cruzar(com, suc, base)
    # sucursales SEPA por provincia, para Corrientes / Mendoza / CABA en detalle
    det = suc[suc["letra"].isin(["W", "M", "C"])].merge(
        com[["id_comercio", "id_bandera", "comercio_bandera_nombre"]], on=["id_comercio", "id_bandera"], how="left")
    det = det[["comercio_bandera_nombre", "sucursales_provincia", "sucursales_localidad", "sucursales_nombre",
               "sucursales_tipo", "sucursales_calle", "sucursales_numero", "sucursales_latitud", "sucursales_longitud"]]
    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    with pd.ExcelWriter(a.out, engine="openpyxl") as xl:
        res.to_excel(xl, sheet_name="Banderas SEPA vs base", index=False)
        con = contraste(com, suc)
        con.to_excel(xl, sheet_name="Contraste Ctes-Mza-CABA", index=False)
        det.sort_values(["sucursales_provincia", "comercio_bandera_nombre"]).to_excel(
            xl, sheet_name="Sucursales Ctes-Mza-CABA", index=False)
        for sh in xl.sheets.values():
            for col, w in zip("ABCDEFGHIJK", (24, 34, 14, 30, 10, 50, 10, 10, 50, 40, 34)):
                sh.column_dimensions[col].width = w
            sh.freeze_panes = "A2"
            sh.auto_filter.ref = sh.dimensions
    print(f"Guardado: {a.out}")
    print(con.to_string(index=False))
    print(f"Banderas SEPA: {len(res)} | en nuestra base: {(res['En nuestra base'] == 'Si').sum()}")
    print(res[["Bandera", "Sucursales SEPA", "En nuestra base", "Match por", "Donde la tenemos",
               "Provincias SEPA sin la bandera en hoja principal"]].to_string(index=False, max_colwidth=60))


if __name__ == "__main__":
    main()
