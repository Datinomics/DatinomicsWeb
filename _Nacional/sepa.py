# -*- coding: utf-8 -*-
"""
Ingesta de SEPA (Sistema Electronico de Publicidad de Precios Argentino).

Regla del producto: los comercios que informan a SEPA toman sus precios de SEPA;
todo lo demas (supermercado o no) se scrapea. Este modulo:

  1) Lee el paquete SEPA (zip de zips: comercio.csv / sucursales.csv / productos.csv).
  2) Guarda el detalle por sucursal en datos/sepa/sepa_<fecha>.parquet.
  3) Por provincia escribe <Region>/<Folder>/excels/precios_SEPA_<Folder>.xlsx:
     hoja Resumen + una hoja por bandera, una fila por producto con precio
     minimo / mediana / maximo entre las sucursales de esa provincia.
  4) cobertura(): que dominios web cubre SEPA y en que provincias tiene sucursales
     (lo usa etl.py para no scrapear esas tiendas).

Uso:
  py sepa.py [ruta/sepa_*.zip]     (sin ruta: el sepa_*.zip mas nuevo de la raiz)
  py sepa.py --descargar           (baja el paquete del dia de datos.produccion.gob.ar e ingesta)
"""
import argparse
import glob
import io
import json
import os
import re
import time
import zipfile

import pandas as pd

import etl
from ubicaciones import FOLDER_A_LETRA, LETRA_A_NOMBRE, norm
from verificar_ubicacion import dominio, etiqueta_dominio

AQUI = os.path.dirname(os.path.abspath(__file__))
DIR_DATOS = os.path.join(etl.RAIZ, "datos", "sepa")
LETRA_A_FOLDER = {v: k for k, v in FOLDER_A_LETRA.items()}
COLS_PROD = ["id_comercio", "id_bandera", "id_sucursal", "id_producto", "productos_ean",
             "productos_descripcion", "productos_cantidad_presentacion",
             "productos_unidad_medida_presentacion", "productos_marca", "productos_precio_lista",
             "productos_precio_referencia", "productos_cantidad_referencia",
             "productos_unidad_medida_referencia", "productos_precio_unitario_promo1",
             "productos_leyenda_promo1"]


CKAN = "https://datos.produccion.gob.ar/api/3/action/package_show?id=sepa-precios"


def descargar():
    """Baja el paquete publicado mas reciente (uno por dia de la semana, ~300 MB, se
    actualiza cerca de las 16:20) a la raiz del repo. Si ya esta, no lo vuelve a bajar."""
    import requests
    recursos = [r for r in requests.get(CKAN, timeout=60).json()["result"]["resources"]
                if r["url"].endswith(".zip") and "/sepa_" in r["url"]]
    ultimo = max(recursos, key=lambda r: r.get("last_modified") or r.get("created") or "")
    fecha = (ultimo.get("last_modified") or ultimo["created"])[:10]
    destino = os.path.join(etl.RAIZ, f"sepa_{fecha}.zip")
    if os.path.exists(destino):
        print(f"  SEPA {fecha}: ya descargado", flush=True)
        return destino
    t = time.time()
    with requests.get(ultimo["url"], stream=True, timeout=(30, 300)) as r:
        r.raise_for_status()
        with open(destino + ".part", "wb") as f:
            for trozo in r.iter_content(1 << 20):
                f.write(trozo)
    os.replace(destino + ".part", destino)
    print(f"  SEPA {fecha} ({ultimo['name']}): {os.path.getsize(destino) / 1e6:.0f} MB en {time.time() - t:.0f}s",
          flush=True)
    return destino


NUMERICAS = {"productos_precio_lista", "productos_precio_referencia", "productos_precio_unitario_promo1"}


def zip_mas_nuevo():
    zips = sorted(glob.glob(os.path.join(etl.RAIZ, "sepa_*.zip")), key=os.path.getmtime)
    return os.environ.get("SEPA_ZIP") or (zips[-1] if zips else None)


def _csv(texto, **kw):
    """CSV de SEPA: separador |, BOM, y una linea final 'Ultima actualizacion: ...'."""
    return pd.read_csv(io.StringIO(texto), sep="|", dtype=str, on_bad_lines="skip", **kw)


def _letra(prov, por_nombre):
    p = str(prov).strip()
    if p.startswith("AR-"):
        return p[3:]
    return por_nombre.get(norm(p), "?")


def iterar(path):
    """Por cada comercio del paquete: (comercio_df, sucursales_df, abrir_productos)."""
    por_nombre = {norm(v): k for k, v in LETRA_A_NOMBRE.items()}
    por_nombre.update({"capital federal": "C", "ciudad autonoma de buenos aires": "C"})
    with zipfile.ZipFile(path) as z:
        for n in z.namelist():
            if not n.endswith(".zip"):
                continue
            try:
                iz = zipfile.ZipFile(io.BytesIO(z.read(n)))
                com = _csv(iz.read("comercio.csv").decode("utf-8-sig", "replace"))
                suc = _csv(iz.read("sucursales.csv").decode("utf-8-sig", "replace"))
            except (zipfile.BadZipFile, KeyError, pd.errors.ParserError) as e:
                print(f"  AVISO: {os.path.basename(n)} ilegible ({type(e).__name__}), se saltea", flush=True)
                continue
            com = com.dropna(subset=["id_bandera"])
            suc = suc.dropna(subset=["id_sucursal"])
            suc["letra"] = [_letra(p, por_nombre) for p in suc["sucursales_provincia"]]
            yield n, com, suc, iz


def leer_productos(iz):
    texto = iz.read("productos.csv").decode("utf-8-sig", "replace")
    df = _csv(texto, usecols=lambda c: c in COLS_PROD)
    df = df.dropna(subset=["id_sucursal", "id_producto"])
    for c in ("productos_precio_lista", "productos_precio_referencia", "productos_precio_unitario_promo1"):
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    return df


def fecha_paquete(path):
    with zipfile.ZipFile(path) as z:
        for n in z.namelist():
            m = re.search(r"(\d{4}-\d{2}-\d{2})", n)
            if m:
                return m.group(1)
    return time.strftime("%Y-%m-%d")


COBERTURA_JSON = os.path.join(DIR_DATOS, "cobertura.json")


def cobertura(path=None):
    """etiqueta de dominio -> {letra: sucursales}. Solo comercio/sucursales (rapido).
    Sin zip a mano usa datos/sepa/cobertura.json (lo deja ingestar(); asi los workers de
    scraping no necesitan bajar el paquete de 300 MB)."""
    path = path or zip_mas_nuevo()
    out = {}
    if not path:
        if os.path.exists(COBERTURA_JSON):
            with open(COBERTURA_JSON, encoding="utf-8") as f:
                return json.load(f)
        return out
    for _, com, suc, _ in iterar(path):
        n = suc.groupby(["id_comercio", "id_bandera", "letra"]).size()
        for _, c in com.iterrows():
            url = str(c.get("comercio_bandera_url", ""))
            if url in ("", "nan"):
                continue
            cuenta = out.setdefault(etiqueta_dominio(dominio(url)), {})
            try:
                for letra, k in n.loc[(c["id_comercio"], c["id_bandera"])].items():
                    cuenta[letra] = cuenta.get(letra, 0) + int(k)
            except KeyError:
                pass
    return out


def banderas_en(letra, path=None):
    """Banderas con sucursales en la provincia: [{Empresa, URL, sucursales}] (con web)."""
    path = path or zip_mas_nuevo()
    out = {}
    if not path:
        return []
    for _, com, suc, _ in iterar(path):
        n = suc[suc["letra"] == letra].groupby(["id_comercio", "id_bandera"]).size()
        for (idc, idb), k in n.items():
            c = com[(com["id_comercio"] == idc) & (com["id_bandera"] == idb)]
            if not len(c):
                continue
            url = str(c["comercio_bandera_url"].iloc[0])
            if url in ("", "nan"):
                continue
            etq = etiqueta_dominio(dominio(url))
            prev = out.get(etq)
            nombre = str(c["comercio_bandera_nombre"].iloc[0]).strip()
            # varias banderas con la misma web (Carrefour Express/Market/...) -> una fila
            out[etq] = {"Empresa": prev["Empresa"] if prev else nombre, "URL": url,
                        "sucursales": (prev["sucursales"] if prev else 0) + int(k)}
    return list(out.values())


def clave_cobertura(dom, cob):
    """Busca el dominio en la cobertura SEPA (cotodigital.com.ar ~ coto.com.ar)."""
    etq = etiqueta_dominio(dom)
    if etq in cob:
        return etq
    return next((k for k in cob if len(k) >= 4 and etq.startswith(k)), None)


def ingestar(path):
    fecha = fecha_paquete(path)
    os.makedirs(DIR_DATOS, exist_ok=True)
    parquet = os.path.join(DIR_DATOS, f"sepa_{fecha}.parquet")
    import pyarrow as pa
    import pyarrow.parquet as pq

    t0 = time.time()
    agregados = []          # una fila por (provincia, bandera, producto)
    resumen = []
    writer = None
    try:
        for n, com, suc, iz in iterar(path):
            t = time.time()
            prod = leer_productos(iz)
            banderas = com.set_index(["id_comercio", "id_bandera"])
            sucs = suc[["id_comercio", "id_bandera", "id_sucursal", "letra", "sucursales_localidad",
                        "sucursales_nombre", "sucursales_tipo"]]
            det = prod.merge(sucs, on=["id_comercio", "id_bandera", "id_sucursal"], how="left")
            det["bandera"] = [banderas["comercio_bandera_nombre"].get((a, b), "") for a, b in
                              zip(det["id_comercio"], det["id_bandera"])] if len(banderas) else ""
            det["bandera"] = det["bandera"].astype(str).str.strip()
            det["fecha"] = fecha
            # esquema fijo: si una columna viene vacia en el primer comercio, pyarrow la tipa
            # como null y despues no puede castear el texto de los siguientes
            cols = COLS_PROD + ["letra", "sucursales_localidad", "sucursales_nombre", "sucursales_tipo",
                                "bandera", "fecha"]
            salida = det.reindex(columns=cols)
            tabla = pa.Table.from_pandas(salida, preserve_index=False, schema=pa.schema(
                [(c, pa.float64() if c in NUMERICAS else pa.string()) for c in cols]))
            if writer is None:
                writer = pq.ParquetWriter(parquet, tabla.schema, compression="zstd")
            writer.write_table(tabla)

            det["presentacion"] = (det["productos_cantidad_presentacion"].fillna("") + " " +
                                   det["productos_unidad_medida_presentacion"].fillna("")).str.strip()
            det["en_promo"] = det["productos_precio_unitario_promo1"].notna()
            g = det.groupby(["letra", "id_comercio", "id_bandera", "bandera", "id_producto"], sort=False).agg(
                EAN=("productos_ean", "first"), Nombre=("productos_descripcion", "first"),
                Marca=("productos_marca", "first"), Presentacion=("presentacion", "first"),
                Precio_min=("productos_precio_lista", "min"), Precio_mediana=("productos_precio_lista", "median"),
                Precio_max=("productos_precio_lista", "max"), Sucursales=("id_sucursal", "nunique"),
                Sucursales_en_promo=("en_promo", "sum")).reset_index()
            agregados.append(g)
            for _, c in com.iterrows():
                url = str(c.get("comercio_bandera_url", ""))
                resumen.append({"id_comercio": c["id_comercio"], "id_bandera": c["id_bandera"],
                                "Bandera": str(c["comercio_bandera_nombre"]).strip(),
                                "Razon social": c["comercio_razon_social"], "CUIT": c["comercio_cuit"],
                                "Dominio": dominio(url) if url not in ("", "nan") else ""})
            print(f"  {os.path.basename(n)[:40]:40s} {len(det):>9,d} filas  {time.time() - t:5.1f}s", flush=True)
            del det, prod
    finally:
        if writer is not None:
            writer.close()
    agg = pd.concat(agregados, ignore_index=True)
    res = pd.DataFrame(resumen).drop_duplicates(["id_comercio", "id_bandera"])
    print(f"  detalle -> {parquet} ({os.path.getsize(parquet) / 1e6:.0f} MB)", flush=True)

    # un Excel por provincia
    for letra, por_prov in agg.groupby("letra"):
        folder = LETRA_A_FOLDER.get(letra)
        if not folder:
            continue
        display, region = etl.cargar_provincias()[folder]
        out = os.path.join(etl.RAIZ, region, folder, "excels", f"precios_SEPA_{folder}.xlsx")
        os.makedirs(os.path.dirname(out), exist_ok=True)
        hojas, filas_res, usados = {}, [], set()
        for (idc, idb, band), d in por_prov.groupby(["id_comercio", "id_bandera", "bandera"]):
            info = res[(res["id_comercio"] == idc) & (res["id_bandera"] == idb)]
            dom = info["Dominio"].iloc[0] if len(info) else ""
            sh = etl.sheet_name(band, usados)
            hojas[sh] = d.drop(columns=["letra", "id_comercio", "id_bandera", "bandera"]) \
                .rename(columns={"id_producto": "SKU"}).assign(Fecha=fecha) \
                .sort_values("Nombre")
            # productos_ean es un indicador: "1" = el id_producto es un EAN
            hojas[sh]["EAN"] = hojas[sh]["SKU"].where(hojas[sh]["EAN"].astype(str).str.strip() == "1", "")
            filas_res.append({"Local": sh, "Dominio": dom, "Productos": len(d),
                              "Con precio": int(d["Precio_mediana"].notna().sum()),
                              "Sucursales": int(d["Sucursales"].max()),
                              "Razon social": info["Razon social"].iloc[0] if len(info) else "",
                              "Fuente": f"SEPA {fecha}"})
        tmp = out + ".tmp.xlsx"
        with pd.ExcelWriter(tmp, engine="openpyxl") as xl:
            pd.DataFrame(filas_res).to_excel(xl, sheet_name="Resumen", index=False)
            for sh, d in hojas.items():
                d.to_excel(xl, sheet_name=sh[:31], index=False)
        os.replace(tmp, out)
        print(f"  {display:24s} {len(hojas):2d} banderas {len(por_prov):>8,d} productos -> {os.path.basename(out)}",
              flush=True)
    with open(COBERTURA_JSON, "w", encoding="utf-8") as f:
        json.dump(cobertura(path), f, ensure_ascii=False)
    print(f"listo en {time.time() - t0:.0f}s", flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("zip", nargs="?", default=None)
    ap.add_argument("--descargar", action="store_true")
    a = ap.parse_args()
    path = a.zip or (descargar() if a.descargar else zip_mas_nuevo())
    if not path:
        raise SystemExit("no encontre ningun sepa_*.zip")
    ingestar(path)


if __name__ == "__main__":
    main()
