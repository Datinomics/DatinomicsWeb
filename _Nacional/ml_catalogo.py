# -*- coding: utf-8 -*-
"""
Extraccion del catalogo de MercadoLibre a PostgreSQL (tablas ml_* de db/schema.sql),
por la API oficial con token de aplicacion (ML_CLIENT_ID / ML_CLIENT_SECRET).

La API no deja listar el catalogo: /products/search pide una palabra o un GTIN y pagina
hasta offset 100 (150 productos por palabra). Por eso se recorre con una cola de busquedas
(ml_busqueda) que se puede cortar y retomar:

  categorias   baja el arbol completo (/sites/MLA/categories/all, 12 mil categorias) y encola
               una busqueda por cada hoja
  buscar       corre las palabras pendientes; si una palabra tiene mas de 150 resultados,
               encola "<palabra> <marca>" con las marcas que aparecieron (un nivel)
  gtin         busca por codigo de barras los EAN que ya tenemos (SEPA y tiendas): da el
               cruce directo producto de catalogo <-> producto SEPA
  ofertas      precios: /products/{id}/items de los productos nunca consultados o consultados
               hace mas tiempo (una consulta por producto y dia)
  sincronizar  vuelca el precio del dia (min / mediana / max entre ofertas) al modelo general:
               comercio 'mercadolibre.com.ar' -> producto -> precio

Uso:
  py ml_catalogo.py categorias
  py ml_catalogo.py buscar gtin ofertas sincronizar --horas 6 --hilos 8
  py ml_catalogo.py estado
"""
import argparse
import concurrent.futures as cf
import datetime
import json
import os
import sys
import threading
import time

import requests
from psycopg2.extras import execute_values

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(AQUI, "db"))
from cargar_db import RAIZ, conectar  # noqa: E402

API = "https://api.mercadolibre.com"
TOPE_OFFSET = 100        # la API no acepta offset > 100
POR_PAGINA = 50
MARCAS_POR_PALABRA = 25  # cuantas marcas se encolan cuando una palabra supera el tope
LOTE = 200               # tareas por lote (se escribe a la base al terminar cada lote)


class Cliente:
    """Sesion con token de aplicacion; lo renueva antes de que venza (dura 6 h)."""

    def __init__(self, hilos):
        try:
            from dotenv import load_dotenv
            load_dotenv(os.path.join(RAIZ, ".env"))
        except ImportError:
            pass
        self.s = requests.Session()
        self.s.mount("https://", requests.adapters.HTTPAdapter(pool_connections=hilos, pool_maxsize=hilos))
        self.lock = threading.Lock()
        self.vence = 0
        self.pedidos = 0
        self.limitados = 0

    def _token(self):
        with self.lock:
            if time.time() < self.vence:
                return
            r = self.s.post(f"{API}/oauth/token", timeout=30, data={
                "grant_type": "client_credentials", "client_id": os.environ["ML_CLIENT_ID"],
                "client_secret": os.environ["ML_CLIENT_SECRET"]})
            r.raise_for_status()
            j = r.json()
            self.s.headers["Authorization"] = f"Bearer {j['access_token']}"
            self.vence = time.time() + j.get("expires_in", 21600) - 600

    def get(self, path, params=None):
        for intento in range(5):
            self._token()
            try:
                r = self.s.get(f"{API}{path}", params=params, timeout=40)
            except requests.RequestException:
                time.sleep(5 * (intento + 1))
                continue
            self.pedidos += 1
            if r.status_code == 401:
                self.vence = 0
                continue
            if r.status_code == 429 or r.status_code >= 500:  # se respeta el limite: se espera
                self.limitados += r.status_code == 429
                time.sleep(15 * (intento + 1))
                continue
            return r
        return None


def _attr(p, clave):
    for a in p.get("attributes") or []:
        if a.get("id") == clave:
            return a.get("value_name")
    return None


def _fila_producto(p, hallado):
    return (p["id"], (p.get("name") or "")[:500], p.get("domain_id"), p.get("parent_id"), p.get("status"),
            _attr(p, "BRAND"), _attr(p, "MODEL"), _attr(p, "GTIN"),
            json.dumps({a.get("id"): a.get("value_name") for a in p.get("attributes") or []}, ensure_ascii=False),
            hallado)


def guardar_productos(cur, filas):
    if not filas:
        return
    filas = list({f[0]: f for f in filas}.values())
    execute_values(cur, """
        INSERT INTO ml_producto (id, nombre, dominio_id, padre_id, estado, marca, modelo, gtin, atributos, hallado_por)
        VALUES %s ON CONFLICT (id) DO UPDATE SET
            nombre = EXCLUDED.nombre, estado = EXCLUDED.estado, marca = COALESCE(EXCLUDED.marca, ml_producto.marca),
            modelo = COALESCE(EXCLUDED.modelo, ml_producto.modelo), gtin = COALESCE(EXCLUDED.gtin, ml_producto.gtin),
            atributos = EXCLUDED.atributos, ultima_vez = current_date""", filas, page_size=500)


# ------------------------------------------------------------------ categorias
def paso_categorias(conn, cli):
    r = cli.get("/sites/MLA/categories/all")
    d = r.json()
    filas = []
    for c in d.values():
        ruta = c.get("path_from_root") or []
        filas.append((c["id"], c["name"], ruta[-2]["id"] if len(ruta) > 1 else None,
                      " > ".join(x["name"] for x in ruta), (c.get("settings") or {}).get("catalog_domain"),
                      not c.get("children_categories"), c.get("total_items_in_this_category")))
    with conn.cursor() as cur:
        execute_values(cur, """INSERT INTO ml_categoria (id, nombre, padre_id, ruta, dominio_id, hoja, total_items)
                               VALUES %s ON CONFLICT (id) DO UPDATE SET nombre = EXCLUDED.nombre, ruta = EXCLUDED.ruta,
                               dominio_id = EXCLUDED.dominio_id, hoja = EXCLUDED.hoja,
                               total_items = EXCLUDED.total_items""", filas, page_size=2000)
        # una palabra por hoja (nombres repetidos entre ramas se buscan una sola vez)
        palabras = {(f[1].strip().lower(), f"categoria:{f[0]}") for f in filas if f[5]}
        execute_values(cur, "INSERT INTO ml_busqueda (tipo, clave, origen) VALUES %s ON CONFLICT DO NOTHING",
                       [("palabra", p, o) for p, o in palabras])
    conn.commit()
    print(f"  categorias: {len(filas):,} ({sum(f[5] for f in filas):,} hojas); "
          f"{len({p for p, _ in palabras}):,} palabras en cola", flush=True)


# ------------------------------------------------------------------ busquedas
def _buscar(cli, tipo, clave):
    params = {"site_id": "MLA", "limit": POR_PAGINA, "status": "active"}
    params.update({"q": clave} if tipo == "palabra" else {"product_identifier": clave})
    productos, total, offset = [], None, 0
    while offset <= TOPE_OFFSET:
        r = cli.get("/products/search", {**params, "offset": offset})
        if r is None or r.status_code != 200:
            return None if not productos else (productos, total)
        j = r.json()
        total = (j.get("paging") or {}).get("total", 0)
        productos += j.get("results") or []
        offset += POR_PAGINA
        if tipo == "gtin" or offset >= total:
            break
    return productos, total


def paso_buscar(conn, cli, tipo, hilos, hasta):
    with conn.cursor() as cur:
        hechas = 0
        while time.time() < hasta:
            cur.execute("SELECT clave, origen FROM ml_busqueda WHERE tipo = %s AND estado = 'pendiente' "
                        "ORDER BY origen LIKE 'marca:%%', clave LIMIT %s", (tipo, LOTE))
            pendientes = cur.fetchall()
            claves = [c for c, _ in pendientes]
            es_subdivision = {c for c, o in pendientes if (o or "").startswith("marca:")}
            if not claves:
                break
            with cf.ThreadPoolExecutor(hilos) as ex:
                res = list(ex.map(lambda k: (k, _buscar(cli, tipo, k)), claves))
            filas, estados, nuevas = [], [], []
            for clave, r in res:
                if r is None:
                    estados.append(("error", None, 0, tipo, clave))
                    continue
                prods, total = r
                filas += [_fila_producto(p, f"{tipo}:{clave}") for p in prods]
                estados.append(("ok", total, len(prods), tipo, clave))
                # palabra con mas resultados que el tope: se subdivide por marca (un solo nivel)
                if tipo == "palabra" and total and total > len(prods) and clave not in es_subdivision:
                    marcas = {}
                    for p in prods:
                        m = _attr(p, "BRAND")
                        if m and m.lower() not in clave:
                            marcas[m.lower()] = marcas.get(m.lower(), 0) + 1
                    nuevas += [("palabra", f"{clave} {m}", f"marca:{clave}")
                               for m, _ in sorted(marcas.items(), key=lambda x: -x[1])[:MARCAS_POR_PALABRA]]
            guardar_productos(cur, filas)
            execute_values(cur, """UPDATE ml_busqueda b SET estado = v.e, total = v.t::int, hallados = v.h::int,
                                   actualizado = now() FROM (VALUES %s) v(e, t, h, tipo, clave)
                                   WHERE b.tipo = v.tipo AND b.clave = v.clave""", estados)
            if nuevas:
                execute_values(cur, "INSERT INTO ml_busqueda (tipo, clave, origen) VALUES %s ON CONFLICT DO NOTHING",
                               nuevas)
            conn.commit()
            hechas += len(claves)
            print(f"  {tipo}: +{len(claves)} busquedas ({hechas} en esta corrida), {len(filas)} productos, "
                  f"+{len(nuevas)} subdivisiones | pedidos {cli.pedidos:,}, 429: {cli.limitados}", flush=True)


def encolar_gtin(conn):
    with conn.cursor() as cur:
        cur.execute("""INSERT INTO ml_busqueda (tipo, clave, origen)
                       SELECT DISTINCT 'gtin', ean, CASE WHEN c.fuente = 'sepa' THEN 'sepa' ELSE 'scraping' END
                       FROM producto x JOIN comercio c ON c.id = x.comercio_id
                       WHERE x.ean ~ '^[0-9]{8,14}$' AND c.fuente <> 'api'
                       ON CONFLICT DO NOTHING""")
        n = cur.rowcount
    conn.commit()
    print(f"  gtin: {n:,} codigos nuevos en cola", flush=True)


# ------------------------------------------------------------------ ofertas
def _ofertas(cli, pid):
    r = cli.get(f"/products/{pid}/items")
    if r is None:
        return pid, None
    if r.status_code == 404:  # "No winners found": sin ofertas activas
        return pid, []
    if r.status_code != 200:
        return pid, None
    return pid, r.json().get("results") or []


def paso_ofertas(conn, cli, hilos, hasta):
    hoy = datetime.date.today()
    with conn.cursor() as cur:
        total = 0
        while time.time() < hasta:
            # primero los del cruce con SEPA/tiendas (gtin), despues el resto; nunca consultados primero
            # ~88 % de las fichas no tiene ofertas activas: esas se revisan una vez por semana;
            # las que tienen ofertas, todos los dias
            cur.execute("""SELECT id FROM ml_producto
                           WHERE ofertas_fecha IS NULL
                              OR (ofertas > 0 AND ofertas_fecha < %s)
                              OR (ofertas = 0 AND ofertas_fecha < %s - 7)
                           ORDER BY ofertas_fecha NULLS FIRST, (hallado_por LIKE 'gtin:%%') DESC LIMIT %s""",
                        (hoy, hoy, LOTE))
            ids = [i for (i,) in cur.fetchall()]
            if not ids:
                break
            with cf.ThreadPoolExecutor(hilos) as ex:
                res = list(ex.map(lambda i: _ofertas(cli, i), ids))
            filas, marcados = [], []
            for pid, items in res:
                if items is None:
                    continue
                marcados.append((pid, len(items), hoy))
                filas += [(it.get("item_id"), hoy, pid, it.get("price"), it.get("original_price"), it.get("currency_id"),
                           it.get("seller_id"), it.get("condition"), (it.get("shipping") or {}).get("free_shipping"),
                           it.get("official_store_id"), it.get("listing_type_id"),
                           ((it.get("seller_address") or {}).get("state") or {}).get("name"))
                          for it in items if it.get("item_id")]
            if filas:
                execute_values(cur, """INSERT INTO ml_oferta (item_id, fecha, producto_id, precio, precio_original, moneda,
                                       vendedor_id, condicion, envio_gratis, tienda_oficial, tipo_publicacion,
                                       provincia_vendedor) VALUES %s ON CONFLICT (item_id, fecha) DO UPDATE SET
                                       precio = EXCLUDED.precio, precio_original = EXCLUDED.precio_original""",
                               list({(f[0], f[1]): f for f in filas}.values()), page_size=1000)
            if marcados:
                execute_values(cur, """UPDATE ml_producto p SET ofertas_fecha = v.f::date, ofertas = v.n::int
                                       FROM (VALUES %s) v(id, n, f) WHERE p.id = v.id""", marcados)
            conn.commit()
            total += len(ids)
            print(f"  ofertas: +{len(ids)} productos ({total} en esta corrida), {len(filas)} ofertas "
                  f"| pedidos {cli.pedidos:,}, 429: {cli.limitados}", flush=True)


# ------------------------------------------------------------------ modelo general
def sincronizar(conn):
    """Precio del dia de cada producto de catalogo -> comercio/producto/precio (provincia 0)."""
    with conn.cursor() as cur:
        cur.execute("""INSERT INTO comercio (dominio, nombre, url, plataforma, es_cadena, fuente)
                       VALUES ('mercadolibre.com.ar', 'MercadoLibre', 'https://www.mercadolibre.com.ar', 'api', true, 'api')
                       ON CONFLICT (dominio) DO UPDATE SET fuente = 'api' RETURNING id""")
        cid = cur.fetchone()[0]
        cur.execute("""INSERT INTO comercio_provincia (comercio_id, provincia_id, estado, verificacion)
                       VALUES (%s, 0, 'activo', 'API oficial') ON CONFLICT DO NOTHING""", (cid,))
        cur.execute("""INSERT INTO producto (comercio_id, sku, nombre, ean, marca, categoria, primera_vez, ultima_vez)
                       SELECT %s, id, nombre, gtin, marca, dominio_id, primera_vez, ultima_vez FROM ml_producto
                       WHERE ofertas > 0
                       ON CONFLICT (comercio_id, sku) DO UPDATE SET nombre = EXCLUDED.nombre,
                           ean = COALESCE(EXCLUDED.ean, producto.ean), ultima_vez = EXCLUDED.ultima_vez""", (cid,))
        cur.execute("SELECT DISTINCT date_trunc('month', fecha)::date FROM ml_oferta")
        for (mes,) in cur.fetchall():
            fin = (mes.replace(day=28) + datetime.timedelta(days=4)).replace(day=1)
            cur.execute(f"CREATE TABLE IF NOT EXISTS precio_{mes:%Y_%m} PARTITION OF precio "
                        f"FOR VALUES FROM ('{mes}') TO ('{fin}')")
        cur.execute("""INSERT INTO precio (producto_id, fecha, provincia_id, precio, precio_min, precio_max, sucursales)
                       SELECT x.id, v.fecha, 0, round(v.precio_mediana::numeric, 2), v.precio_min, v.precio_max, v.ofertas
                       FROM v_ml_precio v JOIN producto x ON x.comercio_id = %s AND x.sku = v.producto_id
                       ON CONFLICT (producto_id, provincia_id, fecha) DO UPDATE SET precio = EXCLUDED.precio,
                           precio_min = EXCLUDED.precio_min, precio_max = EXCLUDED.precio_max,
                           sucursales = EXCLUDED.sucursales""", (cid,))
        n = cur.rowcount
    conn.commit()
    print(f"  sincronizar: {n:,} precios de MercadoLibre en el modelo general", flush=True)


def estado(conn):
    with conn.cursor() as cur:
        cur.execute("""SELECT tipo, estado, count(*), sum(hallados) FROM ml_busqueda GROUP BY 1, 2 ORDER BY 1, 2""")
        for r in cur.fetchall():
            print(f"  busquedas {r[0]:8s} {r[1]:10s} {r[2]:>9,}  productos {r[3] or 0:>10,}")
        cur.execute("""SELECT count(*), count(gtin), count(ofertas_fecha), count(*) FILTER (WHERE ofertas > 0),
                              (SELECT count(*) FROM ml_oferta), (SELECT count(DISTINCT dominio_id) FROM ml_producto)
                       FROM ml_producto""")
        p, g, c, con, o, d = cur.fetchone()
        print(f"  productos de catalogo {p:,} (con GTIN {g:,}, {d:,} dominios) | ofertas consultadas {c:,}, "
              f"con ofertas {con:,} | filas de oferta {o:,}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("pasos", nargs="+", choices=["categorias", "buscar", "gtin", "ofertas", "sincronizar", "estado"])
    ap.add_argument("--horas", type=float, default=2, help="tiempo maximo por paso de cola")
    ap.add_argument("--hilos", type=int, default=8)
    a = ap.parse_args()
    conn = conectar()
    cli = Cliente(a.hilos)
    t0 = time.time()
    for paso in a.pasos:
        hasta = time.time() + a.horas * 3600
        if paso == "categorias":
            paso_categorias(conn, cli)
        elif paso == "buscar":
            paso_buscar(conn, cli, "palabra", a.hilos, hasta)
        elif paso == "gtin":
            encolar_gtin(conn)
            paso_buscar(conn, cli, "gtin", a.hilos, hasta)
        elif paso == "ofertas":
            paso_ofertas(conn, cli, a.hilos, hasta)
        elif paso == "sincronizar":
            sincronizar(conn)
        elif paso == "estado":
            estado(conn)
    print(f"listo en {time.time() - t0:.0f}s, {cli.pedidos:,} pedidos a la API, 429: {cli.limitados}")


if __name__ == "__main__":
    main()
