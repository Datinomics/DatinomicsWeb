# -*- coding: utf-8 -*-
"""Historico de precios en SQLite.

Una fila de `precio` por producto y por dia: si se corre dos veces el mismo
dia, la segunda reemplaza a la primera (no duplica). Cada tienda procesada
deja una fila en `corrida`, con la cantidad de productos y el motivo si fallo.

Uso:
    py _Nacional/historico.py importar <precios_*.xlsx> [rubro] [provincia]
    py _Nacional/historico.py resumen
    py _Nacional/historico.py serie "texto del producto"
"""
import datetime
import os
import re
import sqlite3
import sys
import unicodedata

DB_DEFAULT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "historico.db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS tienda (
  id INTEGER PRIMARY KEY,
  dominio TEXT NOT NULL UNIQUE,
  nombre TEXT NOT NULL,
  plataforma TEXT,
  rubro TEXT,
  provincia TEXT
);
CREATE TABLE IF NOT EXISTS producto (
  id INTEGER PRIMARY KEY,
  tienda_id INTEGER NOT NULL REFERENCES tienda(id),
  clave TEXT NOT NULL,
  sku TEXT,
  nombre TEXT NOT NULL,
  categoria TEXT,
  UNIQUE (tienda_id, clave)
);
CREATE TABLE IF NOT EXISTS corrida (
  id INTEGER PRIMARY KEY,
  tienda_id INTEGER NOT NULL REFERENCES tienda(id),
  inicio TEXT NOT NULL,
  productos INTEGER,
  con_precio INTEGER,
  motivo TEXT
);
CREATE TABLE IF NOT EXISTS precio (
  producto_id INTEGER NOT NULL REFERENCES producto(id),
  fecha TEXT NOT NULL,
  precio REAL,
  corrida_id INTEGER REFERENCES corrida(id),
  PRIMARY KEY (producto_id, fecha)
) WITHOUT ROWID;
CREATE INDEX IF NOT EXISTS ix_precio_fecha ON precio(fecha);
CREATE INDEX IF NOT EXISTS ix_corrida_tienda ON corrida(tienda_id, inicio);
"""


def conectar(path=None):
    path = os.path.abspath(path or DB_DEFAULT)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    con = sqlite3.connect(path, timeout=30)
    con.execute("PRAGMA journal_mode = WAL")
    con.execute("PRAGMA foreign_keys = ON")
    con.executescript(SCHEMA)
    return con


def _norm(s):
    s = unicodedata.normalize("NFKD", str(s or "")).encode("ascii", "ignore").decode()
    return re.sub(r"\s+", " ", s).strip().lower()


def _sku(v):
    if v is None:
        return ""
    if isinstance(v, float):
        if v != v:  # NaN
            return ""
        if v.is_integer():
            v = int(v)
    return str(v).strip()


def _num(v):
    try:
        v = float(v)
    except (TypeError, ValueError):
        return None
    return None if v != v else v


def _tienda_id(con, dominio, nombre, plataforma, rubro, provincia):
    con.execute(
        """INSERT INTO tienda (dominio, nombre, plataforma, rubro, provincia)
           VALUES (?, ?, ?, ?, ?)
           ON CONFLICT(dominio) DO UPDATE SET
             nombre = excluded.nombre,
             plataforma = COALESCE(NULLIF(excluded.plataforma, ''), plataforma),
             rubro = COALESCE(NULLIF(excluded.rubro, ''), rubro),
             provincia = COALESCE(NULLIF(excluded.provincia, ''), provincia)""",
        (dominio, nombre, plataforma or "", rubro or "", provincia or ""))
    return con.execute("SELECT id FROM tienda WHERE dominio = ?", (dominio,)).fetchone()[0]


def registrar(con, dominio, nombre, filas, fecha=None, plataforma="", rubro="",
              provincia="", motivo=""):
    """Guarda las observaciones de una tienda. `filas` son los dicts del scraper
    (SKU, Nombre, Precio, Fecha, Categoria). Devuelve el id de la corrida."""
    hoy = fecha or datetime.date.today().isoformat()
    tid = _tienda_id(con, dominio, nombre, plataforma, rubro, provincia)
    con_precio = sum(1 for f in filas if _num(f.get("Precio")) is not None)
    cid = con.execute(
        "INSERT INTO corrida (tienda_id, inicio, productos, con_precio, motivo) VALUES (?, ?, ?, ?, ?)",
        (tid, datetime.datetime.now().isoformat(timespec="seconds"),
         len(filas), con_precio, motivo or None)).lastrowid
    for f in filas:
        nom = str(f.get("Nombre") or "").strip()
        if not nom:
            continue
        sku = _sku(f.get("SKU"))
        clave = ("s:" + sku) if sku else ("n:" + _norm(nom))
        con.execute(
            """INSERT INTO producto (tienda_id, clave, sku, nombre, categoria)
               VALUES (?, ?, ?, ?, ?)
               ON CONFLICT(tienda_id, clave) DO UPDATE SET
                 nombre = excluded.nombre,
                 categoria = COALESCE(NULLIF(excluded.categoria, ''), categoria)""",
            (tid, clave, sku, nom, str(f.get("Categoria") or "")))
        pid = con.execute("SELECT id FROM producto WHERE tienda_id = ? AND clave = ?",
                          (tid, clave)).fetchone()[0]
        dia = str(f.get("Fecha") or hoy)[:10]
        con.execute("INSERT OR REPLACE INTO precio (producto_id, fecha, precio, corrida_id) VALUES (?, ?, ?, ?)",
                    (pid, dia, _num(f.get("Precio")), cid))
    con.commit()
    return cid


def importar_excel(con, path, rubro="", provincia=""):
    import pandas as pd
    xl = pd.ExcelFile(path)
    doms = {}
    if "Resumen" in xl.sheet_names:
        res = xl.parse("Resumen").fillna("")
        if "Dominio" in res.columns:
            doms = {str(r["Local"]): str(r["Dominio"]) for _, r in res.iterrows() if r["Dominio"]}
    n = 0
    for hoja in xl.sheet_names:
        if hoja == "Resumen":
            continue
        dominio = doms.get(hoja)
        if not dominio:
            print(f"  salteo '{hoja}': el Resumen no trae su dominio")
            continue
        filas = xl.parse(hoja).fillna("").to_dict("records")
        registrar(con, dominio, hoja, filas, rubro=rubro, provincia=provincia)
        print(f"  {hoja}: {len(filas)} filas")
        n += 1
    return n


def resumen(con):
    q = """SELECT t.nombre, COUNT(DISTINCT p.id), COUNT(DISTINCT pr.fecha),
                  MIN(pr.fecha), MAX(pr.fecha)
           FROM tienda t
           LEFT JOIN producto p ON p.tienda_id = t.id
           LEFT JOIN precio pr ON pr.producto_id = p.id
           GROUP BY t.id ORDER BY t.nombre"""
    for nombre, prods, dias, desde, hasta in con.execute(q):
        print(f"{nombre:30s} productos={prods:6d} dias={dias:3d} {desde} -> {hasta}")


def serie(con, texto, limite=5):
    q = """SELECT t.nombre, p.nombre, pr.fecha, pr.precio
           FROM producto p JOIN tienda t ON t.id = p.tienda_id
           JOIN precio pr ON pr.producto_id = p.id
           WHERE p.id IN (SELECT id FROM producto WHERE nombre LIKE ? LIMIT ?)
           ORDER BY t.nombre, p.nombre, pr.fecha"""
    for tienda, prod, fecha, precio in con.execute(q, (f"%{texto}%", limite)):
        print(f"{tienda:20s} {prod[:50]:50s} {fecha} {precio}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    cmd = sys.argv[1]
    con = conectar()
    if cmd == "importar":
        rubro = sys.argv[3] if len(sys.argv) > 3 else ""
        prov = sys.argv[4] if len(sys.argv) > 4 else ""
        print(f"{importar_excel(con, sys.argv[2], rubro, prov)} tiendas importadas")
    elif cmd == "resumen":
        resumen(con)
    elif cmd == "serie":
        serie(con, sys.argv[2])
    else:
        print(__doc__)