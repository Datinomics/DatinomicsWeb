# -*- coding: utf-8 -*-
"""
Scrapea precios de TODOS los comercios de corrientes_full.xlsx (menos super/mayoristas
ya hechos), auto-detectando la plataforma (Shopify / VTEX / Tiendanube / WooCommerce).
Genera UN EXCEL POR RUBRO, con UNA HOJA POR LOCAL.
Columnas: SKU, Nombre, Precio, Fecha, Categoria.

Uso: py scrape_categorias.py [--rubro farmacia] [--limite N]
Salida: ../excels/precios_<rubro>.xlsx
"""
import argparse
import datetime
import os
import re
import socket
import time

import pandas as pd
import requests

from scraper_vtex import scrape_vtex
from scraper_woo import scrape_woo

socket.setdefaulttimeout(30)
HOY = datetime.date.today().isoformat()
H = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
     "(KHTML, like Gecko) Chrome/124.0 Safari/537.36", "Accept": "*/*"}
_S = requests.Session()
_S.mount("https://", requests.adapters.HTTPAdapter(pool_connections=20, pool_maxsize=20, max_retries=2))
FULL = "../excels/corrientes_full.xlsx"
OUTDIR = "../excels"


def base_url(u):
    u = str(u)
    if not u.startswith("http"):
        u = "https://" + u
    m = re.match(r"(https?://[^/]+)", u)
    return m.group(1) if m else u


def precio_ar(s):
    s = re.sub(r"[^\d,]", "", str(s))
    if not s:
        return None
    s = s.replace(".", "").replace(",", ".")
    try:
        return round(float(s), 2)
    except ValueError:
        return None


def rubro_de(sector):
    s = str(sector).lower()
    tabla = [
        (("farmacia",), "Farmacias"),
        (("ferreteria", "construccion", "pintureria", "corralon"), "Ferreteria-Construccion"),
        (("electro", "tecnolog", "computacion", "celular"), "Electro-Tecnologia"),
        (("indumentaria", "calzado", "deporte", "ropa", "lenceria"), "Indumentaria-Calzado-Deportes"),
        (("perfumeria", "cosmetica", "belleza", "maquillaje"), "Perfumeria-Cosmetica"),
        (("muebles", "hogar", "bazar", "colchon", "deco"), "Muebles-Hogar-Bazar"),
        (("libreria", "jugueteria", "papeleria"), "Libreria-Jugueteria"),
        (("carniceria", "polleria"), "Carnicerias"),
        (("panaderia", "confiteria", "pasteleria"), "Panaderias-Confiterias"),
        (("bebida", "vinoteca", "cerveza"), "Bebidas-Vinotecas"),
        (("mascota", "veterinaria", "petshop"), "Mascotas-Veterinarias"),
        (("optica", "salud"), "Opticas-Salud"),
        (("joyeria", "relojeria", "regalo"), "Joyerias-Regalos"),
        (("auto", "moto", "repuesto", "neumatico", "bicicleta"), "Autos-Motos-Repuestos"),
        (("floreria", "vivero"), "Florerias-Viveros"),
        (("instrumento", "musica"), "Instrumentos-Musica"),
    ]
    for claves, nombre in tabla:
        if any(k in s for k in claves):
            return nombre
    return "Otros"


# ---------------- scrapers por plataforma ----------------
def scrape_shopify(base, tienda, max_pages=10):
    rows = []
    for page in range(1, max_pages + 1):
        try:
            r = _S.get(f"{base}/products.json", params={"limit": 250, "page": page},
                             headers=H, timeout=25)
        except Exception:
            break
        if r.status_code != 200:
            break
        try:
            prods = r.json().get("products", [])
        except Exception:
            break
        if not prods:
            break
        for p in prods:
            cat = p.get("product_type", "") or ""
            for v in (p.get("variants") or [{}]):
                rows.append({"SKU": v.get("sku") or v.get("id"), "Nombre": p.get("title", ""),
                             "Precio": precio_ar(v.get("price")), "Fecha": HOY,
                             "Categoria": cat, "Tienda": tienda})
        time.sleep(0.2)
    return rows


def scrape_tiendanube(base, tienda, max_pages=40):
    rows, seen = [], set()
    for page in range(1, max_pages + 1):
        try:
            r = _S.get(f"{base}/productos", params={"page": page}, headers=H, timeout=25)
        except Exception:
            break
        if r.status_code != 200 or "js-item-product" not in r.text:
            break
        h = r.text
        ids = [(m.start(), m.group(1)) for m in re.finditer(r'data-product-id="(\d+)"', h)]
        if not ids:
            break
        nuevos = 0
        for i, (pos, pid) in enumerate(ids):
            if pid in seen:
                continue
            chunk = h[pos: ids[i + 1][0] if i + 1 < len(ids) else pos + 4000]
            nm = re.search(r'js-item-name[^>]*>\s*([^<]+?)\s*<', chunk)
            pr = re.search(r'js-price-display[^>]*>\s*([^<]+?)\s*<', chunk)
            if not nm:
                continue
            seen.add(pid)
            nuevos += 1
            rows.append({"SKU": pid, "Nombre": nm.group(1).strip(),
                         "Precio": precio_ar(pr.group(1)) if pr else None,
                         "Fecha": HOY, "Categoria": "", "Tienda": tienda})
        if nuevos == 0:
            break
        time.sleep(0.3)
    return rows


def detectar_y_scrapear(tienda, url):
    """Auto-detecta plataforma probando en orden y devuelve (filas, plataforma)."""
    base = base_url(url)
    # 1) Shopify
    try:
        r = _S.get(f"{base}/products.json", params={"limit": 1}, headers=H, timeout=15)
        if r.status_code == 200 and isinstance(r.json().get("products"), list) and r.json()["products"]:
            return scrape_shopify(base, tienda), "shopify"
    except Exception:
        pass
    # 2) VTEX (206)
    try:
        r = _S.get(f"{base}/api/catalog_system/pub/category/tree/1", headers={**H, "Accept": "application/json"}, timeout=15)
        if r.status_code in (200, 206) and isinstance(r.json(), list):
            return scrape_vtex(base, tienda, max_cats=40), "vtex"
    except Exception:
        pass
    # 3) Tiendanube (HTML)
    try:
        r = _S.get(f"{base}/productos", headers=H, timeout=15)
        if r.status_code == 200 and "js-item-product" in r.text:
            return scrape_tiendanube(base, tienda), "tiendanube"
    except Exception:
        pass
    # 4) WooCommerce
    try:
        r = _S.get(f"{base}/wp-json/wc/store/products", params={"per_page": 1},
                         headers={**H, "Accept": "application/json"}, timeout=15)
        if r.status_code == 200 and isinstance(r.json(), list):
            return scrape_woo(base, tienda, max_pages=25), "woocommerce"
    except Exception:
        pass
    return [], "no-soportada"


def sheet_name(s, usados):
    s = re.sub(r"[\[\]:\*\?/\\]", "", str(s))[:28].strip() or "Local"
    n, base = s, s
    k = 2
    while n in usados:
        n = f"{base[:26]}_{k}"; k += 1
    usados.add(n)
    return n


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rubro", default="", help="filtrar un rubro (substring)")
    ap.add_argument("--limite", type=int, default=0, help="max locales por rubro (test)")
    args = ap.parse_args()

    df = pd.read_excel(FULL, sheet_name=0).fillna("")
    df = df[df["Tienda online"].astype(str).str.contains("Si|Probable", case=False, na=False)]
    df["rubro"] = df["Sector"].map(rubro_de)
    # excluir super/mayoristas (ya hechos) y filtrar rubro si se pidio
    df = df[~df["Sector"].astype(str).str.contains("Supermercado|Mayorista", case=False, na=False)]
    if args.rubro:
        df = df[df["rubro"].str.contains(args.rubro, case=False)]

    for rubro, grupo in df.groupby("rubro"):
        locales = grupo.drop_duplicates("URL")
        if args.limite:
            locales = locales.head(args.limite)
        print(f"\n===== RUBRO: {rubro} ({len(locales)} locales) =====", flush=True)
        hojas = []
        usados = set()
        for _, r in locales.iterrows():
            nombre = str(r["Empresa"])[:40]
            try:
                filas, plat = detectar_y_scrapear(nombre, r["URL"])
            except Exception as e:
                filas, plat = [], f"error:{type(e).__name__}"
            con = sum(1 for f in filas if f.get("Precio"))
            print(f"  {nombre[:34]:34s} [{plat:12s}] {len(filas):5d} prod ({con} c/precio)", flush=True)
            time.sleep(0.4)
            if filas:
                d = pd.DataFrame(filas).reindex(columns=["SKU", "Nombre", "Precio", "Fecha", "Categoria"])
                hojas.append((sheet_name(nombre, usados), d))
        if not hojas:
            print("  (sin datos para este rubro)", flush=True)
            continue
        out = os.path.join(OUTDIR, f"precios_{rubro}.xlsx")
        try:
            with pd.ExcelWriter(out, engine="openpyxl") as xl:
                resumen = pd.DataFrame([(n, len(d), int(d["Precio"].notna().sum())) for n, d in hojas],
                                       columns=["Local", "Productos", "Con precio"])
                resumen.to_excel(xl, sheet_name="Resumen", index=False)
                for nombre, d in hojas:
                    d.to_excel(xl, sheet_name=nombre, index=False)
            print(f"  -> Guardado {out} ({len(hojas)} hojas/locales)", flush=True)
        except Exception as e:
            print(f"  ERROR guardando {out}: {e}", flush=True)


if __name__ == "__main__":
    main()
