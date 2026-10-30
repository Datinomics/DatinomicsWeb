# -*- coding: utf-8 -*-
"""
Sube el historico a Cloudflare R2 (compatible S3; 10 GB gratis, sin costo de descarga).

Estructura del bucket:
  sepa/sepa_<fecha>.parquet          detalle por sucursal de cada dia
  sepa/zips/sepa_<fecha>.zip         paquete original (solo con --con-zip)
  fuentes/<fuente>/<fuente>_<fecha>.parquet
  diario/<fecha>/precios_<Prov>.parquet, calidad.json, ...

Solo sube lo que no esta o cambio de tamaño. Credenciales en el entorno o .env:
  R2_ENDPOINT=https://<account_id>.r2.cloudflarestorage.com
  R2_ACCESS_KEY_ID=...   R2_SECRET_ACCESS_KEY=...   R2_BUCKET=datinomics

Uso:
  py subir_r2.py                 # sube lo nuevo
  py subir_r2.py --simular       # muestra que subiria y cuanto pesa, sin credenciales
  py subir_r2.py --con-zip       # ademas el zip original de SEPA
"""
import argparse
import glob
import os
import time

import etl

RAIZ = etl.RAIZ
DATOS = os.path.join(RAIZ, "datos")


def archivos(con_zip=False):
    """[(ruta local, clave en el bucket)]"""
    out = [(p, "sepa/" + os.path.basename(p)) for p in glob.glob(os.path.join(DATOS, "sepa", "sepa_*.parquet"))]
    for carpeta in ("fuentes", "diario"):
        for p in glob.glob(os.path.join(DATOS, carpeta, "**", "*"), recursive=True):
            if os.path.isfile(p) and not p.endswith((".tmp", ".part")):
                out.append((p, os.path.relpath(p, DATOS).replace(os.sep, "/")))
    if con_zip:
        out += [(p, "sepa/zips/" + os.path.basename(p)) for p in glob.glob(os.path.join(RAIZ, "sepa_20*.zip"))]
    return sorted(out, key=lambda x: x[1])


def cliente():
    try:
        from dotenv import load_dotenv
        load_dotenv(os.path.join(RAIZ, ".env"))
    except ImportError:
        pass
    faltan = [k for k in ("R2_ENDPOINT", "R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY", "R2_BUCKET") if not os.environ.get(k)]
    if faltan:
        raise SystemExit(f"Faltan {', '.join(faltan)} (entorno o .env). Ver el docstring.")
    import boto3
    s3 = boto3.client("s3", endpoint_url=os.environ["R2_ENDPOINT"], region_name="auto",
                      aws_access_key_id=os.environ["R2_ACCESS_KEY_ID"],
                      aws_secret_access_key=os.environ["R2_SECRET_ACCESS_KEY"])
    return s3, os.environ["R2_BUCKET"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--simular", action="store_true")
    ap.add_argument("--con-zip", action="store_true")
    a = ap.parse_args()
    lista = archivos(a.con_zip)
    total = sum(os.path.getsize(p) for p, _ in lista)
    if a.simular:
        por = {}
        for p, k in lista:
            por[k.split("/")[0]] = por.get(k.split("/")[0], 0) + os.path.getsize(p)
        for k, v in por.items():
            print(f"  {k:10s} {v / 1e6:8.1f} MB")
        print(f"  {len(lista)} archivos, {total / 1e6:.1f} MB")
        return
    s3, bucket = cliente()
    remotos = {}
    for pag in s3.get_paginator("list_objects_v2").paginate(Bucket=bucket):
        remotos.update({o["Key"]: o["Size"] for o in pag.get("Contents", [])})
    t0, subidos, bytes_ = time.time(), 0, 0
    for p, k in lista:
        if remotos.get(k) == os.path.getsize(p):
            continue
        s3.upload_file(p, bucket, k)
        subidos += 1
        bytes_ += os.path.getsize(p)
    seg = time.time() - t0
    print(f"  R2: {subidos} archivos nuevos, {bytes_ / 1e6:.1f} MB en {seg:.0f}s "
          f"({bytes_ / 1e6 / max(seg, 1):.1f} MB/s); en el bucket: {len(remotos) + subidos} objetos")


if __name__ == "__main__":
    main()
