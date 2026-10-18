# -*- coding: utf-8 -*-
"""
Limpia los <provincia>_full.xlsx: saca del listado "Tiendas con web" el ruido que
dejo el descubrimiento amplio (TLD extranjeros, software/ERP, demos de theme,
directorios, homepages de plataformas) y lo manda a una hoja 'Descartados'.
"""
import glob
import os
import re

import pandas as pd

# TLD/dominios extranjeros o claramente no-comercio AR
BAD_TLD = (".es", ".mx", ".cl", ".co", ".pe", ".uy", ".br", ".it", ".de", ".fr",
           ".us", ".gt", ".hn", ".sv", ".pa", ".do", ".cr", ".ve", ".bo", ".py",
           ".ec", ".madrid", ".ai", ".barcelona", ".paris", ".cat", ".pt", ".ru",
           ".in", ".pl", ".nl", ".uk")
# substrings de dominio que son ruido (software, demos, directorios, plataformas)
BAD_DOM = ("flexxus", "naturalsoftware", "themevolty", "themeforest", "pollo.ai",
           "wordpress.com", "tiendanube.com", "shopify.com", "prestashop.com",
           "ecwid.com", "mercadoshops.com", "urbanococinaamericana", "aarg.ar",
           "demo.", "softwarepar", "/demo", "themedemo", "bootstrap", "envato",
           "wix.com", "weebly", "godaddysites", "negocio.site", "sumerlabs")
# substrings de nombre/titulo que delatan software/plantilla/demo
BAD_NAME = ("software", " erp", "erp ", "plantilla", "template", "theme ", "demo de",
            "sistema de gestion", "gestion para", "ai video", "ai image",
            "diseño web", "diseno web", "agencia digital", "marketing digital")


def dom(u):
    try:
        return u.split("//")[-1].split("/")[0].lower().replace("www.", "")
    except Exception:
        return str(u).lower()


def es_ruido(empresa, url):
    d = dom(url)
    if any(d.endswith(t) for t in BAD_TLD):
        return True
    if any(b in d for b in BAD_DOM):
        return True
    if any(b in str(empresa).lower() for b in BAD_NAME):
        return True
    return False


def main():
    files = sorted(glob.glob("../*/*/excels/*_full.xlsx"))
    print(f"Limpiando {len(files)} provincias...\n")
    print(f"{'Provincia':22s}{'Antes':>7}{'Limpias':>9}{'Descart.':>9}")
    print("-" * 47)
    tot_a = tot_l = 0
    for f in files:
        prov = os.path.basename(f).replace("_full.xlsx", "")
        try:
            xl = pd.ExcelFile(f)
            shp = "Tiendas con web" if "Tiendas con web" in xl.sheet_names else xl.sheet_names[0]
            df = xl.parse(shp).fillna("")
            otras = {s: xl.parse(s) for s in xl.sheet_names if s != shp and "descart" not in s.lower()}
        except Exception as e:
            print(f"{prov:22s}  (error: {type(e).__name__})")
            continue
        ucol = "URL" if "URL" in df.columns else df.columns[2]
        ecol = "Empresa" if "Empresa" in df.columns else df.columns[0]
        ruido = df.apply(lambda r: es_ruido(r[ecol], r[ucol]), axis=1)
        limpio = df[~ruido]
        descart = df[ruido]
        tot_a += len(df); tot_l += len(limpio)
        print(f"{prov:22s}{len(df):>7}{len(limpio):>9}{len(descart):>9}")
        with pd.ExcelWriter(f, engine="openpyxl") as w:
            limpio.to_excel(w, sheet_name=shp[:31], index=False)
            for s, d in otras.items():
                d.to_excel(w, sheet_name=s[:31], index=False)
            if len(descart):
                descart.to_excel(w, sheet_name="Descartados", index=False)
    print("-" * 47)
    print(f"{'TOTAL':22s}{tot_a:>7}{tot_l:>9}{tot_a - tot_l:>9}")


if __name__ == "__main__":
    main()
