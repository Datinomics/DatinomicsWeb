# -*- coding: utf-8 -*-
"""Corre scrape_provincia.py para todas las provincias, una por una.
Salta CABA y Buenos-Aires (van por su cuenta). Resumable: cada provincia
es resumable por si misma (precios_<rubro>.xlsx se actualiza)."""
import subprocess
import sys

EXCLUIR = {"CABA", "Buenos-Aires"}  # van en sus propios procesos
ORDEN = [
    # priorizar las grandes despues de las del usuario
    "Cordoba", "Santa-Fe", "Mendoza", "Salta", "Tucuman", "Entre-Rios",
    "Misiones", "Chaco", "Corrientes", "San-Juan", "Jujuy", "Neuquen",
    "Rio-Negro", "Chubut", "Formosa", "Santiago-del-Estero", "La-Pampa",
    "La-Rioja", "San-Luis", "Catamarca", "Santa-Cruz", "Tierra-del-Fuego",
]


def main():
    for prov in ORDEN:
        if prov in EXCLUIR:
            continue
        print(f"\n############### {prov} ###############", flush=True)
        try:
            subprocess.run([sys.executable, "-X", "utf8", "scrape_provincia.py", prov],
                           check=False)
        except Exception as e:
            print(f"  FALLO {prov}: {e}", flush=True)


if __name__ == "__main__":
    main()
