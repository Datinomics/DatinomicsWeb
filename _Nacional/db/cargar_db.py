# -*- coding: utf-8 -*-
"""
Carga en PostgreSQL todo lo relevado (modelo en db/schema.sql). Es idempotente: se puede
correr de nuevo y actualiza (upsert); los precios de un mismo producto/dia/provincia se pisan.

Lee:
  - geografia      _Nacional/geo/ (Georef + barrios de CABA)
  - comercios      <Region>/<Prov>/excels/<Prov>_full.xlsx (todas las hojas, con su estado)
  - precios        precios_<Rubro>_<Prov>.xlsx y datos/diario/<fecha>/precios_*.parquet
  - SEPA           precios_SEPA_<Prov>.xlsx (min / mediana / max por provincia y bandera)
  - fuentes        datos/fuentes/<fuente>/<fuente>_<fecha>.parquet (todo el historico)
  - calidad        reportes/calidad/calidad_<Prov>.xlsx

Conexion: DATABASE_URL (entorno o .env), ej.
  DATABASE_URL=postgresql://postgres:<clave>@localhost:5432/datinomics

Uso:
  py db/cargar_db.py --crear-db                 # crea la base si no existe + esquema + carga todo
  py db/cargar_db.py --provincias CABA Mendoza  # solo esas provincias
  py db/cargar_db.py --solo fuentes             # geografia | comercios | precios | sepa | fuentes | calidad
"""
import argparse
import datetime
import glob
import hashlib
import io
import json
import os
import re
import sys
import time

import pandas as pd
import psycopg2
from psycopg2.extras import execute_values

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(AQUI))

import etl  # noqa: E402
import geografia  # noqa: E402
from ubicaciones import FOLDER_A_LETRA, LETRA_A_NOMBRE  # noqa: E402
from verificar_ubicacion import dominio  # noqa: E402

RAIZ = etl.RAIZ
LETRA_A_INDEC = {v: int(k) for k, v in geografia.INDEC_A_LETRA.items()}
PASOS = ["geografia", "comercios", "precios", "sepa", "fuentes", "calidad"]
ESTADO_HOJA = {"tiendas con web": "activo", "candidatos (revisar)": "candidato",
               "descartados (ubicacion)": "descartado_ubicacion", "descartados (sin datos)": "descartado_sin_datos",
               "descartados": "descartado_ubicacion"}
PRIORIDAD_ESTADO = {"activo": 0, "descartado_sin_datos": 1, "descartado_ubicacion": 2, "candidato": 3}


def conectar(crear_db=False):
    try:
        from dotenv import load_dotenv
        load_dotenv(os.path.join(RAIZ, ".env"))
    except ImportError:
        pass
    url = os.environ.get("DATABASE_URL")
    if not url:
        sys.exit("Falta DATABASE_URL (entorno o .env), ej postgresql://postgres:clave@localhost:5432/datinomics")
    if crear_db:
        base, nombre = url.rsplit("/", 1)
        nombre = nombre.split("?")[0]
        c = psycopg2.connect(f"{base}/postgres")
        c.autocommit = True
        with c.cursor() as cur:
            cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (nombre,))
            if not cur.fetchone():
                cur.execute(f'CREATE DATABASE "{nombre}" ENCODING \'UTF8\'')
                print(f"  base {nombre} creada", flush=True)
        c.close()
    conn = psycopg2.connect(url)
    with conn.cursor() as cur:
        cur.execute("SET search_path TO datinomics, public")
    return conn


def esquema(conn):
    with conn.cursor() as cur:
        cur.execute(open(os.path.join(AQUI, "schema.sql"), encoding="utf-8").read())
        cur.execute("SET search_path TO datinomics, public")
    conn.commit()


def copiar(cur, tabla, df, columnas):
    """COPY de un DataFrame a una tabla (temporal) via CSV en memoria."""
    buf = io.StringIO()
    df[columnas].to_csv(buf, index=False, header=False, na_rep="\\N")
    buf.seek(0)
    cur.copy_expert(f"COPY {tabla} ({', '.join(columnas)}) FROM STDIN WITH (FORMAT csv, NULL '\\N')", buf)


def corrida(cur, tipo, alcance, filas, detalle=None, inicio=None):
    cur.execute("INSERT INTO corrida (tipo, alcance, fecha, inicio, fin, filas, estado, detalle) "
                "VALUES (%s, %s, current_date, %s, now(), %s, 'ok', %s) RETURNING id",
                (tipo, alcance, inicio or datetime.datetime.now(), filas, json.dumps(detalle or {}, default=str)))
    return cur.fetchone()[0]


def _txt(v):
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return None
    s = str(v).strip()
    return s or None


# --------------------------------------------------------------------- geografia
def cargar_geografia(conn):
    provs = etl.cargar_provincias()
    filas = [(LETRA_A_INDEC[FOLDER_A_LETRA[f]], FOLDER_A_LETRA[f], f, LETRA_A_NOMBRE[FOLDER_A_LETRA[f]], region)
             for f, (_, region) in provs.items()]
    locs = {}
    for r in geografia._leer_csv("localidades.csv"):
        letra = geografia.INDEC_A_LETRA.get(r["provincia_id"].zfill(2))
        if letra and letra != "C":
            k = (LETRA_A_INDEC[letra], r["departamento_nombre"] or "", r["localidad_nombre"])
            locs[k] = (*k, "localidad", float(r["localidad_centroide_lat"] or 0) or None,
                       float(r["localidad_centroide_lon"] or 0) or None)
    for nombre, comuna, _ in geografia._barrios():
        k = (LETRA_A_INDEC["C"], comuna, nombre)
        locs[k] = (*k, "barrio", None, None)
    with conn.cursor() as cur:
        execute_values(cur, "INSERT INTO provincia (id, letra, folder, nombre, region) VALUES %s "
                            "ON CONFLICT (id) DO UPDATE SET folder = EXCLUDED.folder, nombre = EXCLUDED.nombre, "
                            "region = EXCLUDED.region", filas)
        cur.execute("INSERT INTO provincia (id, letra, folder, nombre, region) VALUES (0, '-', '-', 'Online (precio unico)', '-') "
                    "ON CONFLICT DO NOTHING")
        execute_values(cur, "INSERT INTO localidad (provincia_id, departamento, nombre, tipo, lat, lon) VALUES %s "
                            "ON CONFLICT (provincia_id, departamento, nombre) DO NOTHING", list(locs.values()),
                       page_size=2000)
    conn.commit()
    print(f"  geografia: {len(filas)} provincias, {len(locs)} localidades/barrios", flush=True)


def _ids(cur, sql):
    cur.execute(sql)
    return {tuple(r[:-1]) if len(r) > 2 else r[0]: r[-1] for r in cur.fetchall()}


# --------------------------------------------------------------------- comercios
def leer_comercios(folder):
    display, region = etl.cargar_provincias()[folder]
    full = os.path.join(RAIZ, region, folder, "excels", f"{folder}_full.xlsx")
    if not os.path.exists(full):
        return pd.DataFrame()
    partes = []
    with pd.ExcelFile(full) as xl:
        curada = "Verificacion" in xl.parse("Tiendas con web", nrows=0).columns if "Tiendas con web" in xl.sheet_names else False
        for s in xl.sheet_names:
            estado = ESTADO_HOJA.get(s.lower())
            if not estado:
                continue
            d = xl.parse(s)
            if d.empty or "URL" not in d:
                continue
            d["estado"] = "candidato" if (estado == "activo" and not curada) else estado
            partes.append(d)
    if not partes:
        return pd.DataFrame()
    df = pd.concat(partes, ignore_index=True)
    df = df[df["URL"].notna()]
    df["dominio"] = df["URL"].map(dominio)
    df["_p"] = df["estado"].map(PRIORIDAD_ESTADO)
    df = df.sort_values("_p").drop_duplicates("dominio")
    if "Evidencia" in df and ("Localidad" not in df or df["Localidad"].isna().all()):
        # provincias curadas antes de que existiera la zona: se calcula de la evidencia
        origen = df["Origen"].astype(str) if "Origen" in df else pd.Series("", index=df.index)
        zonas = [geografia.zona_de_evidencia(e, folder, o in ("Cadena nacional", "SEPA")) if st == "activo" else {}
                 for e, st, o in zip(df["Evidencia"], df["estado"], origen)]
        z = pd.DataFrame(zonas, index=df.index).reindex(columns=["Localidad", "Departamento", "Metodo zona"])
        df = pd.concat([df.drop(columns=z.columns, errors="ignore"), z], axis=1)
    return df


def cargar_comercios(conn, folders):
    with conn.cursor() as cur:
        prov_id = _ids(cur, "SELECT folder, id FROM provincia")
        total = 0
        for folder in folders:
            t0 = datetime.datetime.now()
            df = leer_comercios(folder)
            if df.empty:
                continue
            pid = prov_id[folder]
            col = lambda c: df[c] if c in df else pd.Series([None] * len(df), index=df.index)  # noqa: E731
            rubros = sorted({etl.rubro_de(s) for s in col("Sector").fillna("")})
            execute_values(cur, "INSERT INTO rubro (nombre) VALUES %s ON CONFLICT DO NOTHING", [(r,) for r in rubros])
            rubro_id = _ids(cur, "SELECT nombre, id FROM rubro")
            plataforma = col("Plataforma usada").where(col("Plataforma usada").notna(), col("Plataforma"))
            filas = [(dom, (_txt(n) or dom)[:200], _txt(u), rubro_id[etl.rubro_de(s if isinstance(s, str) else "")],
                      _txt(s), _txt(p), str(o) in ("Cadena nacional", "SEPA"))
                     for dom, n, u, s, p, o in zip(df["dominio"], col("Empresa"), df["URL"], col("Sector"),
                                                   plataforma, col("Origen"))]
            execute_values(cur, """
                INSERT INTO comercio (dominio, nombre, url, rubro_id, sector, plataforma, es_cadena) VALUES %s
                ON CONFLICT (dominio) DO UPDATE SET
                    nombre = EXCLUDED.nombre, url = EXCLUDED.url,
                    rubro_id = COALESCE(comercio.rubro_id, EXCLUDED.rubro_id),
                    sector = COALESCE(comercio.sector, EXCLUDED.sector),
                    plataforma = COALESCE(EXCLUDED.plataforma, comercio.plataforma),
                    es_cadena = comercio.es_cadena OR EXCLUDED.es_cadena, actualizado = now()""", filas,
                           page_size=1000)
            com_id = _ids(cur, "SELECT dominio, id FROM comercio")
            # zonas: se suman las que no estan (ej. municipio 'Guaymallen' como localidad)
            zonas = {(pid, _txt(d) or "", _txt(l)) for l, d, e in zip(col("Localidad"), col("Departamento"), df["estado"])
                     if _txt(l) and _txt(l) != "Varias (cadena)" and e == "activo"}
            if zonas:
                execute_values(cur, "INSERT INTO localidad (provincia_id, departamento, nombre) VALUES %s "
                                    "ON CONFLICT DO NOTHING", list(zonas))
            loc_id = _ids(cur, f"SELECT provincia_id, departamento, nombre, id FROM localidad WHERE provincia_id = {pid}")
            motivo = col("Motivo descarte")
            filas = []
            for i in range(len(df)):
                loc = _txt(col("Localidad").iloc[i])
                dep = _txt(col("Departamento").iloc[i]) or ""
                filas.append((com_id[df["dominio"].iloc[i]], pid, df["estado"].iloc[i],
                              _txt(col("Verificacion").iloc[i]), _txt(motivo.iloc[i]),
                              (_txt(col("Evidencia").iloc[i]) or "")[:4000] or None,
                              loc_id.get((pid, dep, loc)) if loc else None,
                              _txt(col("Metodo zona").iloc[i]), _txt(col("Zona busqueda").iloc[i])))
            execute_values(cur, """
                INSERT INTO comercio_provincia (comercio_id, provincia_id, estado, verificacion, motivo, evidencia,
                                                localidad_id, metodo_zona, zona_busqueda) VALUES %s
                ON CONFLICT (comercio_id, provincia_id) DO UPDATE SET
                    estado = EXCLUDED.estado, verificacion = EXCLUDED.verificacion, motivo = EXCLUDED.motivo,
                    evidencia = EXCLUDED.evidencia, localidad_id = EXCLUDED.localidad_id,
                    metodo_zona = EXCLUDED.metodo_zona,
                    zona_busqueda = COALESCE(EXCLUDED.zona_busqueda, comercio_provincia.zona_busqueda),
                    actualizado = now()""", filas, page_size=1000)
            estados = df["estado"].value_counts().to_dict()
            corrida(cur, "curado", folder, len(df), estados, t0)
            conn.commit()
            total += len(df)
            print(f"  comercios {folder}: {len(df)} -> {estados}", flush=True)
    return total


# --------------------------------------------------------------------- precios
STG = """CREATE TEMP TABLE IF NOT EXISTS stg_precio (
    comercio_id integer, sku text, nombre text, categoria text, ean text, marca text, presentacion text,
    fecha date, provincia_id smallint, precio numeric, precio_min numeric, precio_max numeric,
    sucursales integer, en_promo integer) ON COMMIT DELETE ROWS"""
COLS_STG = ["comercio_id", "sku", "nombre", "categoria", "ean", "marca", "presentacion", "fecha", "provincia_id",
            "precio", "precio_min", "precio_max", "sucursales", "en_promo"]


def _particiones(cur):
    cur.execute("SELECT DISTINCT date_trunc('month', fecha)::date FROM stg_precio WHERE fecha IS NOT NULL")
    for (mes,) in cur.fetchall():
        fin = (mes.replace(day=28) + datetime.timedelta(days=4)).replace(day=1)
        cur.execute(f"CREATE TABLE IF NOT EXISTS precio_{mes:%Y_%m} PARTITION OF precio "
                    f"FOR VALUES FROM ('{mes}') TO ('{fin}')")


def volcar(cur, df, corrida_id):
    """df con COLS_STG -> producto (upsert) + precio (upsert). Devuelve (productos, precios)."""
    for c in COLS_STG:
        if c not in df:
            df[c] = None
    df = df[df["sku"].notna() & df["nombre"].notna() & df["fecha"].notna()]
    if df.empty:
        return 0, 0
    copiar(cur, "stg_precio", df, COLS_STG)
    _particiones(cur)
    cur.execute("""
        INSERT INTO producto (comercio_id, sku, nombre, categoria, ean, marca, presentacion, primera_vez, ultima_vez)
        SELECT DISTINCT ON (comercio_id, sku) comercio_id, sku, left(nombre, 500), categoria, ean, marca,
               presentacion, min(fecha) OVER w, max(fecha) OVER w
        FROM stg_precio WINDOW w AS (PARTITION BY comercio_id, sku)
        ORDER BY comercio_id, sku, fecha DESC
        ON CONFLICT (comercio_id, sku) DO UPDATE SET
            nombre = EXCLUDED.nombre,
            categoria = COALESCE(EXCLUDED.categoria, producto.categoria),
            ean = COALESCE(EXCLUDED.ean, producto.ean), marca = COALESCE(EXCLUDED.marca, producto.marca),
            presentacion = COALESCE(EXCLUDED.presentacion, producto.presentacion),
            primera_vez = LEAST(producto.primera_vez, EXCLUDED.primera_vez),
            ultima_vez = GREATEST(producto.ultima_vez, EXCLUDED.ultima_vez)""")
    n_prod = cur.rowcount
    cur.execute(f"""
        INSERT INTO precio (producto_id, fecha, provincia_id, precio, precio_min, precio_max, sucursales,
                            en_promo, corrida_id)
        SELECT DISTINCT ON (p.id, s.provincia_id, s.fecha) p.id, s.fecha, s.provincia_id, round(s.precio, 2),
               round(s.precio_min, 2), round(s.precio_max, 2), s.sucursales, s.en_promo, {int(corrida_id)}
        FROM stg_precio s JOIN producto p ON p.comercio_id = s.comercio_id AND p.sku = s.sku
        WHERE s.precio > 0 AND s.precio < 1e12
        ORDER BY p.id, s.provincia_id, s.fecha
        ON CONFLICT (producto_id, provincia_id, fecha) DO UPDATE SET
            precio = EXCLUDED.precio, precio_min = EXCLUDED.precio_min, precio_max = EXCLUDED.precio_max,
            sucursales = EXCLUDED.sucursales, en_promo = EXCLUDED.en_promo, corrida_id = EXCLUDED.corrida_id""")
    n_precio = cur.rowcount
    cur.execute("TRUNCATE stg_precio")
    return n_prod, n_precio


def _sku(sku, nombre):
    s = _txt(sku)
    if s and s.endswith(".0") and s[:-2].isdigit():
        s = s[:-2]
    return s or ("n:" + hashlib.md5(str(nombre).encode()).hexdigest()[:16])


def _fecha_archivo(path):
    return datetime.date.fromtimestamp(os.path.getmtime(path)).isoformat()


def cargar_precios(conn, folders):
    with conn.cursor() as cur:
        cur.execute(STG)
        com_id = _ids(cur, "SELECT dominio, id FROM comercio")
        provs = etl.cargar_provincias()
        for folder in [*folders, "_cadenas"]:  # _cadenas: cadenas nacionales de la corrida diaria
            region = provs[folder][1] if folder in provs else ""
            archivos = [p for p in sorted(glob.glob(os.path.join(RAIZ, region, folder, "excels",
                                                                 f"precios_*_{folder}.xlsx")))
                        if not p.endswith(f"precios_SEPA_{folder}.xlsx")] if region else []
            t0, partes, huerfanos = datetime.datetime.now(), [], 0
            for path in archivos:
                hojas, doms = etl.cargar_hojas_previas(path)
                for hoja, d in hojas.items():
                    cid = com_id.get(doms.get(hoja, ""))
                    if not cid or d.empty or "Nombre" not in d:
                        huerfanos += bool(len(d))
                        continue
                    partes.append(pd.DataFrame({
                        "comercio_id": cid, "sku": [_sku(s, n) for s, n in zip(d.get("SKU", d["Nombre"]), d["Nombre"])],
                        "nombre": d["Nombre"].astype(str).str.strip(), "categoria": d.get("Categoria"),
                        "fecha": pd.to_datetime(d.get("Fecha"), errors="coerce").dt.date.fillna(
                            datetime.date.fromisoformat(_fecha_archivo(path))),
                        "provincia_id": 0, "precio": pd.to_numeric(d["Precio"], errors="coerce")}))
            # corridas diarias (datos/diario/<fecha>/precios_<Prov>*.parquet)
            for path in sorted(glob.glob(os.path.join(RAIZ, "datos", "diario", "*", f"precios_{folder}*.parquet"))):
                d = pd.read_parquet(path)
                d["comercio_id"] = d["Dominio"].map(com_id)
                d = d[d["comercio_id"].notna()]
                partes.append(pd.DataFrame({
                    "comercio_id": d["comercio_id"].astype(int),
                    "sku": [_sku(s, n) for s, n in zip(d["SKU"], d["Nombre"])], "nombre": d["Nombre"],
                    "categoria": d["Categoria"], "fecha": pd.to_datetime(d["Fecha"], errors="coerce").dt.date,
                    "provincia_id": 0, "precio": d["Precio"]}))
            if not partes:
                continue
            df = pd.concat(partes, ignore_index=True)
            cid = corrida(cur, "scraping", folder, len(df), {"archivos": len(archivos), "hojas_sin_comercio": huerfanos}, t0)
            n_prod, n_pre = volcar(cur, df, cid)
            conn.commit()
            print(f"  precios {folder}: {len(df):,} filas -> {n_prod:,} productos, {n_pre:,} precios "
                  f"({(datetime.datetime.now() - t0).seconds}s)", flush=True)


def cargar_sepa(conn, folders):
    with conn.cursor() as cur:
        cur.execute(STG)
        execute_values(cur, "INSERT INTO rubro (nombre) VALUES %s ON CONFLICT DO NOTHING", [("Supermercados",)])
        sup = _ids(cur, "SELECT nombre, id FROM rubro")["Supermercados"]
        prov_id = _ids(cur, "SELECT folder, id FROM provincia")
        for folder in folders:
            display, region = etl.cargar_provincias()[folder]
            path = os.path.join(RAIZ, region, folder, "excels", f"precios_SEPA_{folder}.xlsx")
            if not os.path.exists(path):
                continue
            t0, partes, pid = datetime.datetime.now(), [], prov_id[folder]
            with pd.ExcelFile(path) as xl:
                for bandera in xl.sheet_names:
                    if bandera == "Resumen":
                        continue
                    d = xl.parse(bandera)
                    dom = "sepa:" + re.sub(r"[^a-z0-9]+", "-", geografia._n(bandera)).strip("-")
                    cur.execute("""INSERT INTO comercio (dominio, nombre, rubro_id, plataforma, es_cadena, fuente)
                                   VALUES (%s, %s, %s, 'sepa', true, 'sepa')
                                   ON CONFLICT (dominio) DO UPDATE SET nombre = EXCLUDED.nombre RETURNING id""",
                                (dom, bandera, sup))
                    cid = cur.fetchone()[0]
                    suc = int(pd.to_numeric(d.get("Sucursales"), errors="coerce").max() or 0) if len(d) else 0
                    cur.execute("""INSERT INTO comercio_provincia (comercio_id, provincia_id, estado, verificacion, sucursales)
                                   VALUES (%s, %s, 'activo', 'SEPA', %s)
                                   ON CONFLICT (comercio_id, provincia_id) DO UPDATE SET estado = 'activo',
                                   sucursales = EXCLUDED.sucursales, actualizado = now()""", (cid, pid, suc))
                    ean = d["EAN"].map(lambda x: _sku(x, "")) if "EAN" in d else None
                    partes.append(pd.DataFrame({
                        "comercio_id": cid, "sku": [_sku(s, n) for s, n in zip(d["SKU"], d["Nombre"])],
                        "nombre": d["Nombre"], "ean": ean, "marca": d.get("Marca"), "presentacion": d.get("Presentacion"),
                        "fecha": pd.to_datetime(d["Fecha"], errors="coerce").dt.date, "provincia_id": pid,
                        "precio": d["Precio_mediana"], "precio_min": d["Precio_min"], "precio_max": d["Precio_max"],
                        "sucursales": d["Sucursales"], "en_promo": d.get("Sucursales_en_promo")}))
            if not partes:
                continue
            df = pd.concat(partes, ignore_index=True)
            cid = corrida(cur, "sepa", folder, len(df), {"banderas": len(partes)}, t0)
            n_prod, n_pre = volcar(cur, df, cid)
            conn.commit()
            print(f"  SEPA {folder}: {len(partes)} banderas, {len(df):,} filas -> {n_pre:,} precios "
                  f"({(datetime.datetime.now() - t0).seconds}s)", flush=True)


# --------------------------------------------------------------------- fuentes externas
def _parquets(fuente):
    archivos = sorted(glob.glob(os.path.join(RAIZ, "datos", "fuentes", fuente, f"{fuente}_*.parquet")))
    return pd.concat([pd.read_parquet(p) for p in archivos], ignore_index=True) if archivos else pd.DataFrame()


def _upsert(cur, tabla, df, columnas, clave):
    df = df.drop_duplicates(subset=clave, keep="last")
    df = df.astype(object).where(df.notna(), None)
    actualizar = [c for c in columnas if c not in clave]
    sql = (f"INSERT INTO {tabla} ({', '.join(columnas)}) VALUES %s ON CONFLICT ({', '.join(clave)}) DO "
           + (f"UPDATE SET {', '.join(f'{c} = EXCLUDED.{c}' for c in actualizar)}" if actualizar else "NOTHING"))
    execute_values(cur, sql, [tuple(r) for r in df[columnas].itertuples(index=False)], page_size=2000)
    return len(df)


def cargar_fuentes(conn):
    nombre_a_id = {geografia._n(LETRA_A_NOMBRE[l]): i for l, i in LETRA_A_INDEC.items()}
    nombre_a_id.update({"capital federal": 2, "ciudad autonoma de buenos aires": 2, "caba": 2})
    with conn.cursor() as cur:
        res = {}
        d = _parquets("granos")
        if len(d):
            d = d.rename(columns=str.lower)
            d["fecha"] = pd.to_datetime(d["fecha"], dayfirst=True, errors="coerce").dt.date
            res["granos"] = _upsert(cur, "granos", d, ["fecha", "grano", "plaza", "precio_ars_tn", "precio_usd_tn",
                                                       "estimado"], ["fecha", "grano", "plaza"])
        d = _parquets("hacienda")
        if len(d):
            d = d.rename(columns=str.lower)
            d["grupo"] = d["grupo"].fillna("")
            d["fecha"] = pd.to_datetime(d["fecha"], dayfirst=True, errors="coerce").dt.date
            res["hacienda"] = _upsert(cur, "hacienda", d, ["fecha", "plaza", "grupo", "categoria", "minimo", "maximo",
                                                           "promedio", "mediana", "cabezas", "importe", "kgs",
                                                           "kgs_prom", "unidad"],
                                      ["fecha", "plaza", "grupo", "categoria"])
        d = _parquets("frutas_hortalizas")
        if len(d):
            d = d.rename(columns=str.lower)
            for c in ("variedad", "procedencia", "envase", "calidad", "tamano", "grado"):
                d[c] = d[c].fillna("").astype(str).str.strip()
            d["fecha"] = pd.to_datetime(d["fecha"], errors="coerce").dt.date
            for c in ("kg_bulto", "max_bulto", "frecuente_bulto", "min_bulto", "max_kg", "frecuente_kg", "min_kg"):
                d[c] = pd.to_numeric(d[c], errors="coerce")
            res["frutas_hortalizas"] = _upsert(
                cur, "frutas_hortalizas", d,
                ["fecha", "rubro", "especie", "variedad", "procedencia", "envase", "calidad", "tamano", "grado",
                 "kg_bulto", "max_bulto", "frecuente_bulto", "min_bulto", "max_kg", "frecuente_kg", "min_kg"],
                ["fecha", "rubro", "especie", "variedad", "procedencia", "envase", "calidad", "tamano", "grado"])
        d = _parquets("combustibles")
        if len(d):
            d = d.rename(columns={"tipohorario": "horario", "empresabandera": "bandera", "latitud": "lat",
                                  "longitud": "lon"})
            d["fecha_vigencia"] = pd.to_datetime(d["fecha_vigencia"], errors="coerce")
            d["provincia_id"] = d["provincia"].map(lambda p: nombre_a_id.get(geografia._n(p)))
            d = d[d["fecha_vigencia"].notna() & (d["precio"] > 0)]
            res["combustibles"] = _upsert(cur, "combustible", d,
                                          ["fecha_vigencia", "idempresa", "producto", "horario", "precio", "empresa",
                                           "bandera", "cuit", "direccion", "localidad", "provincia_id", "lat", "lon"],
                                          ["idempresa", "producto", "horario", "fecha_vigencia"])
        d = _parquets("bcra")
        if len(d):
            d["serie"] = d["idVariable"].where(d["idVariable"].notna(), d.get("codigoMoneda")).map(
                lambda x: str(int(x)) if isinstance(x, float) else str(x))
            d["fecha"] = pd.to_datetime(d["Fecha"], errors="coerce").dt.date
            d = d.rename(columns={"Tipo": "tipo", "Descripcion": "descripcion", "Valor": "valor", "Unidad": "unidad"})
            d = d[d["fecha"].notna()]
            res["bcra"] = _upsert(cur, "bcra", d, ["fecha", "tipo", "serie", "descripcion", "valor", "unidad",
                                                   "categoria", "periodicidad"], ["tipo", "serie", "fecha"])
        p = os.path.join(RAIZ, "datos", "fuentes", "medicamentos", "acumulado.parquet")
        d = pd.read_parquet(p) if os.path.exists(p) else _parquets("medicamentos")
        if len(d):
            d = d.rename(columns=str.lower)
            d["vigencia"] = pd.to_datetime(d["vigencia"], errors="coerce").dt.date
            d["relevado"] = pd.to_datetime(d["relevado"], errors="coerce").dt.date
            res["medicamentos"] = _upsert(cur, "medicamento", d,
                                          ["url", "presentacion", "vigencia", "producto", "laboratorio", "droga",
                                           "accion", "precio", "relevado"], ["url", "presentacion"])
        for fuente in ("zonaprop", "argenprop"):
            archivos = sorted(glob.glob(os.path.join(RAIZ, "datos", "fuentes", fuente, f"{fuente}_*.parquet")))
            partes = []
            for a in archivos:
                x = pd.read_parquet(a)
                x["relevado"] = re.search(r"(\d{4}-\d{2}-\d{2})", a).group(1)
                partes.append(x)
            if not partes:
                continue
            d = pd.concat(partes, ignore_index=True)
            d = d.rename(columns={"Id": "aviso_id"}).rename(columns=str.lower)
            d["fuente"] = fuente
            d = d[d["aviso_id"].notna()]
            d["aviso_id"] = d["aviso_id"].astype(str)
            cols = ["fuente", "aviso_id", "relevado", "operacion", "tipo", "busqueda", "titulo", "precio", "moneda",
                    "expensas", "sup_total_m2", "sup_cubierta_m2", "ambientes", "dormitorios", "banos", "direccion",
                    "barrio", "ciudad", "lat", "lon", "inmobiliaria", "url"]
            for c in cols:
                if c not in d:
                    d[c] = None
            for c in ("precio", "expensas", "sup_total_m2", "sup_cubierta_m2", "ambientes", "dormitorios", "banos",
                      "lat", "lon"):
                d[c] = pd.to_numeric(d[c], errors="coerce")
            res[fuente] = _upsert(cur, "inmueble", d, cols, ["fuente", "aviso_id", "relevado"])
        for f, n in res.items():
            corrida(cur, f"fuente:{f}", f, n)
        conn.commit()
    print(f"  fuentes: {res}", flush=True)


# --------------------------------------------------------------------- calidad
def cargar_calidad(conn, folders):
    with conn.cursor() as cur:
        com_id = _ids(cur, "SELECT dominio, id FROM comercio")
        prov_id = _ids(cur, "SELECT folder, id FROM provincia")
        for folder in folders:
            path = os.path.join(RAIZ, "reportes", "calidad", f"calidad_{folder}.xlsx")
            if not os.path.exists(path):
                continue
            d = pd.read_excel(path, sheet_name="Comercios")
            d = d[d["Dominio"].map(com_id).notna()]
            fecha = _fecha_archivo(path)
            metricas = [c for c in d.columns if c not in ("Rubro", "Comercio", "Dominio", "Estado", "Alertas",
                                                         "Productos", "Rubro sugerido")]
            filas = [(fecha, com_id[r["Dominio"]], prov_id[folder], r["Estado"], _txt(r["Alertas"]),
                      int(r["Productos"]), _txt(r.get("Rubro sugerido")),
                      json.dumps({m: (None if pd.isna(r[m]) else r[m]) for m in metricas}, default=str))
                     for _, r in d.drop_duplicates("Dominio").iterrows()]
            execute_values(cur, """INSERT INTO calidad_comercio (fecha, comercio_id, provincia_id, estado, alertas,
                                   productos, rubro_sugerido, metricas) VALUES %s
                                   ON CONFLICT (fecha, comercio_id, provincia_id) DO UPDATE SET
                                   estado = EXCLUDED.estado, alertas = EXCLUDED.alertas, productos = EXCLUDED.productos,
                                   rubro_sugerido = EXCLUDED.rubro_sugerido, metricas = EXCLUDED.metricas""", filas)
            conn.commit()
            print(f"  calidad {folder}: {len(filas)} comercios", flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--crear-db", action="store_true", help="crea la base si no existe")
    ap.add_argument("--provincias", nargs="*", default=None)
    ap.add_argument("--solo", nargs="*", choices=PASOS, default=None)
    a = ap.parse_args()
    t0 = time.time()
    conn = conectar(a.crear_db)
    esquema(conn)
    folders = a.provincias or list(etl.cargar_provincias())
    pasos = a.solo or PASOS
    if "geografia" in pasos:
        cargar_geografia(conn)
    if "comercios" in pasos:
        cargar_comercios(conn, folders)
    if "precios" in pasos:
        cargar_precios(conn, folders)
    if "sepa" in pasos:
        cargar_sepa(conn, folders)
    if "fuentes" in pasos:
        cargar_fuentes(conn)
    if "calidad" in pasos:
        cargar_calidad(conn, folders)
    with conn.cursor() as cur:
        cur.execute("ANALYZE")
        cur.execute("""SELECT (SELECT count(*) FROM comercio), (SELECT count(*) FROM comercio_provincia WHERE estado='activo'),
                              (SELECT count(*) FROM producto), (SELECT count(*) FROM precio)""")
        c, a_, p, pr = cur.fetchone()
    conn.commit()
    conn.close()
    print(f"listo en {time.time() - t0:.0f}s: {c:,} comercios ({a_:,} activos), {p:,} productos, {pr:,} precios")


if __name__ == "__main__":
    main()
