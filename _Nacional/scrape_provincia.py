# -*- coding: utf-8 -*-
"""
Scrapea precios de TODOS los locales de una provincia leyendo su
<provincia>_full.xlsx. Auto-detecta plataforma (Shopify/VTEX/Tiendanube/Woo).
Respeta cadenas_nacionales.csv: si el dominio del local figura como cadena
nacional con MasterScrape ya definido, NO re-scrapea (anota "ya scrapeado
master=<prov>"). Genera UN EXCEL POR RUBRO con UNA HOJA POR LOCAL.
Columnas: SKU, Nombre, Precio, Fecha, Categoria. Resumable: si la hoja del
local ya esta, salta.

Uso: py scrape_provincia.py <Folder> [--rubro X] [--limite N] [--skip-nacional 0|1]
Default: --skip-nacional 1 (dedup). Pass 0 si queres scrapear todo igual.
Ej:    py scrape_provincia.py CABA
       py scrape_provincia.py Buenos-Aires --rubro Carnicerias
"""
import argparse
import datetime
import os
import re
import socket
import sys
import time

import pandas as pd
import requests

# importar scrapers desde la carpeta de Corrientes
SCR_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "NEA", "Corrientes", "scripts"))
if SCR_DIR not in sys.path:
    sys.path.insert(0, SCR_DIR)
from scraper_vtex import scrape_vtex  # noqa: E402
from scraper_woo import scrape_woo  # noqa: E402

socket.setdefaulttimeout(30)
HOY = datetime.date.today().isoformat()
H = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
     "(KHTML, like Gecko) Chrome/124.0 Safari/537.36", "Accept": "*/*"}
_S = requests.Session()
_S.mount("https://", requests.adapters.HTTPAdapter(pool_connections=30, pool_maxsize=30, max_retries=2))
_S.mount("http://", requests.adapters.HTTPAdapter(pool_connections=30, pool_maxsize=30, max_retries=2))

NACIONALES_CSV = os.path.join(os.path.dirname(__file__), "cadenas_nacionales.csv")
RAIZ = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

# folder -> (display, region)
def cargar_provincias():
    from relevar_provincia import PROVINCIAS
    return {k: (v[0], v[1]) for k, v in PROVINCIAS.items()}


def cargar_nacionales():
    if not os.path.exists(NACIONALES_CSV):
        return {}
    df = pd.read_csv(NACIONALES_CSV)
    return {str(r["Dominio"]).lower().strip(): (r["Empresa"], r.get("MasterScrape", ""))
            for _, r in df.iterrows()}


def base_url(u):
    u = str(u).strip()
    if not u.startswith("http"):
        u = "https://" + u
    m = re.match(r"(https?://[^/]+)", u)
    return m.group(1) if m else u


def dominio(u):
    try:
        return u.split("//")[-1].split("/")[0].lower().replace("www.", "")
    except Exception:
        return str(u).lower()


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
        (("supermercado",), "Supermercados"),
        (("mayorista", "distribuidora"), "Mayoristas"),
        (("farmacia",), "Farmacias"),
        (("ferreteria", "construccion", "pintureria", "corralon", "sanitario", "griferia", "pintura"), "Ferreteria-Construccion"),
        (("electro", "tecnolog", "computacion", "celular", "telefonia"), "Electro-Tecnologia"),
        (("indumentaria", "calzado", "deporte", "ropa", "lenceria"), "Indumentaria-Calzado-Deportes"),
        (("perfumeria", "cosmetica", "belleza", "maquillaje"), "Perfumeria-Cosmetica"),
        (("muebles", "hogar", "bazar", "colchon", "deco", "blanqueria", "iluminacion"), "Muebles-Hogar-Bazar"),
        (("libreria", "jugueteria", "papeleria", "articulos escolares", "cotillon"), "Libreria-Jugueteria"),
        (("carniceria", "polleria", "pescaderia"), "Carnicerias-Pollerias"),
        (("panaderia", "confiteria", "pasteleria"), "Panaderias-Confiterias"),
        (("verduleria", "fruteria"), "Verdulerias"),
        (("dietetica",), "Dieteticas"),
        (("cerveza",), "Cervezas-Cervecerias"),
        (("bebida", "vinoteca"), "Bebidas-Vinotecas"),
        (("mascota", "veterinaria", "petshop"), "Mascotas-Veterinarias"),
        (("optica", "salud"), "Opticas-Salud"),
        (("joyeria", "relojeria", "regalo"), "Joyerias-Regalos"),
        (("auto", "moto", "repuesto", "neumatico", "bicicleta", "herramientas"), "Autos-Motos-Repuestos"),
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
            r = _S.get(f"{base}/products.json", params={"limit": 250, "page": page}, headers=H, timeout=25)
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
    base = base_url(url)
    try:
        r = _S.get(f"{base}/products.json", params={"limit": 1}, headers=H, timeout=15)
        if r.status_code == 200 and isinstance(r.json().get("products"), list) and r.json()["products"]:
            return scrape_shopify(base, tienda), "shopify"
    except Exception:
        pass
    try:
        r = _S.get(f"{base}/api/catalog_system/pub/category/tree/1", headers={**H, "Accept": "application/json"}, timeout=15)
        if r.status_code in (200, 206) and isinstance(r.json(), list):
            return scrape_vtex(base, tienda, max_cats=40), "vtex"
    except Exception:
        pass
    try:
        r = _S.get(f"{base}/productos", headers=H, timeout=15)
        if r.status_code == 200 and "js-item-product" in r.text:
            return scrape_tiendanube(base, tienda), "tiendanube"
    except Exception:
        pass
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


def cargar_hojas_previas(out_path):
    """Si existe el xlsx del rubro, devuelve dict {sheet_name: df}."""
    if not os.path.exists(out_path):
        return {}
    try:
        xl = pd.ExcelFile(out_path)
        return {s: xl.parse(s) for s in xl.sheet_names if s != "Resumen"}
    except Exception:
        return {}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("provincia", help="Folder de la provincia (ej: CABA, Buenos-Aires)")
    ap.add_argument("--rubro", default="", help="filtrar un rubro (substring)")
    ap.add_argument("--limite", type=int, default=0, help="max locales por rubro (test)")
    ap.add_argument("--skip-nacional", type=int, default=1, help="1=saltea cadenas con master, 0=todo")
    args = ap.parse_args()

    provs = cargar_provincias()
    if args.provincia not in provs:
        print(f"ERROR: {args.provincia} no esta en PROVINCIAS. Validos: {list(provs)}", flush=True)
        sys.exit(1)
    display, region = provs[args.provincia]
    full_xlsx = os.path.join(RAIZ, region, args.provincia, "excels", f"{args.provincia}_full.xlsx")
    out_dir = os.path.join(RAIZ, region, args.provincia, "excels")
    if not os.path.exists(full_xlsx):
        print(f"ERROR: no encontre {full_xlsx}", flush=True)
        sys.exit(1)

    nacionales = cargar_nacionales() if args.skip_nacional else {}
    print(f"\n#### {display} ({region}) - leyendo {full_xlsx}", flush=True)

    df = pd.read_excel(full_xlsx, sheet_name="Tiendas con web").fillna("")
    df = df[df["Tienda online"].astype(str).str.contains("Si|Probable", case=False, na=False)]
    df["rubro"] = df["Sector"].map(rubro_de)
    df["dom"] = df["URL"].map(dominio)
    total = len(df)
    if args.skip_nacional:
        es_nac = df["dom"].apply(lambda d: any(d == nd or d.endswith("." + nd) for nd in nacionales))
        skips = int(es_nac.sum())
        df = df[~es_nac]
        print(f"  Total tiendas: {total} | salteadas cadenas nacionales: {skips} | a scrapear: {len(df)}", flush=True)
    else:
        print(f"  Total tiendas: {total} (sin skip)", flush=True)

    if args.rubro:
        df = df[df["rubro"].str.contains(args.rubro, case=False)]
        print(f"  Filtrado por rubro '{args.rubro}': {len(df)} tiendas", flush=True)

    for rubro, grupo in df.groupby("rubro"):
        locales = grupo.drop_duplicates("dom")
        if args.limite:
            locales = locales.head(args.limite)
        out_path = os.path.join(out_dir, f"precios_{rubro}_{args.provincia}.xlsx")
        previas = cargar_hojas_previas(out_path)
        usados = set(previas.keys())
        nuevos = []
        print(f"\n===== RUBRO: {rubro} ({len(locales)} locales, {len(previas)} ya hechos) =====", flush=True)
        for _, r in locales.iterrows():
            nombre = str(r["Empresa"])[:40]
            sh = sheet_name(nombre, set(usados))
            if sh in usados:
                continue
            try:
                filas, plat = detectar_y_scrapear(nombre, r["URL"])
            except Exception as e:
                filas, plat = [], f"error:{type(e).__name__}"
            con = sum(1 for f in filas if f.get("Precio"))
            print(f"  {nombre[:34]:34s} [{plat:12s}] {len(filas):5d} prod ({con} c/precio)", flush=True)
            time.sleep(0.4)
            if filas:
                d = pd.DataFrame(filas).reindex(columns=["SKU", "Nombre", "Precio", "Fecha", "Categoria"])
                sh = sheet_name(nombre, usados)
                nuevos.append((sh, d))
        if not nuevos and not previas:
            print("  (sin datos para este rubro)", flush=True)
            continue
        todas = list(previas.items()) + nuevos
        try:
            with pd.ExcelWriter(out_path, engine="openpyxl") as xl:
                resumen = pd.DataFrame([(n, len(d), int(d["Precio"].notna().sum()) if "Precio" in d.columns else 0)
                                        for n, d in todas], columns=["Local", "Productos", "Con precio"])
                resumen.to_excel(xl, sheet_name="Resumen", index=False)
                for nombre, d in todas:
                    d.to_excel(xl, sheet_name=nombre[:31], index=False)
            print(f"  -> {out_path} ({len(todas)} locales, +{len(nuevos)} nuevos)", flush=True)
        except Exception as e:
            print(f"  ERROR guardando {out_path}: {e}", flush=True)


if __name__ == "__main__":
    main()
