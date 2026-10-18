# -*- coding: utf-8 -*-
"""
Crawler de empresas/comercios de Argentina usando OpenStreetMap (Overpass API).

Extrae, por sector, el nombre, la pagina web, el telefono y la ubicacion
(ciudad). Luego, a partir de las coordenadas de cada comercio, asigna la
PROVINCIA y la REGION usando los limites oficiales del IGN (georef).

Fuentes:
  - Comercios: OpenStreetMap, licencia ODbL (openstreetmap.org/copyright)
  - Limites provinciales: IGN / datos.gob.ar (georef)
"""

import json
import os
import sys
import time
import argparse
import unicodedata
from collections import defaultdict
import requests
from dotenv import load_dotenv

load_dotenv()
CONTACT_EMAIL = os.environ.get("SCRAPER_CONTACT_EMAIL", "")
# --------------------------------------------------------------------------
# Configuracion Overpass
# --------------------------------------------------------------------------

OVERPASS_ENDPOINTS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://maps.mail.ru/osm/tools/overpass/api/interpreter",
]

HEADERS = {
    "User-Agent": f"empresas-ar-crawler/1.1 (educational; contacto: {CONTACT_EMAIL})"
}

QUERY_TIMEOUT = 300
REQUEST_TIMEOUT = 360
PAUSE_BETWEEN = 6
MAX_RETRIES = 4

GEOJSON_PROVINCIAS = "provincias.geojson"

# --------------------------------------------------------------------------
# Categorias (sector -> filtros OSM). Cada filtro es (clave, valor).
# --------------------------------------------------------------------------

CATEGORIES = {
    # --- Alimentos / consumo masivo ---
    "Supermercado":            [("shop", "supermarket")],
    "Autoservicio/Almacen":    [("shop", "convenience")],
    "Mayorista":               [("shop", "wholesale")],
    "Kiosco":                  [("shop", "kiosk")],
    "Panaderia":               [("shop", "bakery")],
    "Carniceria":              [("shop", "butcher")],
    "Verduleria":              [("shop", "greengrocer")],
    "Pescaderia":              [("shop", "seafood")],
    "Fiambreria/Delicatessen": [("shop", "deli")],
    "Confiteria/Pasteleria":   [("shop", "confectionery"), ("shop", "pastry")],
    "Diet/Organicos":          [("shop", "health_food"), ("shop", "nutrition_supplements")],
    "Heladeria":               [("amenity", "ice_cream")],
    "Bebidas/Vinoteca":        [("shop", "alcohol"), ("shop", "beverages")],
    "Agropecuaria/Agro":       [("shop", "agrarian"), ("shop", "farm")],
    # --- Gastronomia ---
    "Restaurante":             [("amenity", "restaurant")],
    "Comida rapida":           [("amenity", "fast_food")],
    "Cafe/Bar":                [("amenity", "cafe"), ("amenity", "bar"), ("amenity", "pub")],
    # --- Salud ---
    "Farmacia":                [("amenity", "pharmacy")],
    "Salud (clinica/hospital)":[("amenity", "hospital"), ("amenity", "clinic")],
    "Dentista":                [("amenity", "dentist")],
    "Medico/Consultorio":      [("amenity", "doctors")],
    "Optica":                  [("shop", "optician")],
    "Pet shop/Veterinaria":    [("shop", "pet"), ("amenity", "veterinary")],
    # --- Finanzas / servicios profesionales ---
    "Banco":                   [("amenity", "bank")],
    "Casa de cambio":          [("amenity", "bureau_de_change")],
    "Seguros":                 [("office", "insurance")],
    "Inmobiliaria":            [("office", "estate_agent")],
    "Estudio juridico":        [("office", "lawyer")],
    "Estudio contable":        [("office", "accountant")],
    "Agencia de empleo":       [("office", "employment_agency")],
    "Oficinas/Empresas":       [("office", "company"), ("office", "it"),
                                ("office", "consulting"), ("office", "coworking")],
    "Telecomunicaciones":      [("office", "telecommunication")],
    # --- Indumentaria / cuidado personal ---
    "Indumentaria":            [("shop", "clothes")],
    "Calzado":                 [("shop", "shoes")],
    "Joyeria/Relojeria":       [("shop", "jewelry"), ("shop", "watches")],
    "Peluqueria/Belleza":      [("shop", "hairdresser"), ("shop", "beauty")],
    "Cosmetica/Perfumeria":    [("shop", "cosmetics"), ("shop", "perfumery")],
    "Tatuajes/Piercing":       [("shop", "tattoo")],
    # --- Tecnologia / electro ---
    "Electronica/Electro":     [("shop", "electronics"), ("shop", "appliance")],
    "Telefonia":               [("shop", "mobile_phone")],
    "Computacion/Informatica": [("shop", "computer")],
    "Videojuegos":             [("shop", "video_games")],
    "Fotografia":              [("shop", "photo")],
    # --- Hogar / construccion ---
    "Ferreteria/Construccion": [("shop", "hardware"), ("shop", "doityourself"), ("shop", "trade")],
    "Materiales/Corralon":     [("shop", "building_materials")],
    "Pintureria":              [("shop", "paint")],
    "Mueblerias":              [("shop", "furniture")],
    "Bazar/Hogar/Deco":        [("shop", "houseware"), ("shop", "interior_decoration"),
                                ("shop", "kitchen"), ("shop", "bed"), ("shop", "curtain"),
                                ("shop", "lighting"), ("shop", "carpet")],
    "Vivero/Jardineria":       [("shop", "garden_centre")],
    "Floreria":                [("shop", "florist")],
    # --- Automotor ---
    "Concesionaria/Autos":     [("shop", "car")],
    "Taller mecanico":         [("shop", "car_repair")],
    "Repuestos auto":          [("shop", "car_parts")],
    "Gomeria/Neumaticos":      [("shop", "tyres")],
    "Motos":                   [("shop", "motorcycle")],
    "Bicicleterias":           [("shop", "bicycle")],
    "Estacion de servicio":    [("amenity", "fuel")],
    # --- Comercio general / varios ---
    "Centro comercial":        [("shop", "mall"), ("shop", "department_store")],
    "Tienda variedades/Bazar": [("shop", "variety_store")],
    "Libreria/Papeleria":      [("shop", "books"), ("shop", "stationery")],
    "Jugueteria":              [("shop", "toys")],
    "Deportes":                [("shop", "sports")],
    "Tienda de regalos":       [("shop", "gift")],
    "Musica/Instrumentos":     [("shop", "musical_instrument"), ("shop", "music")],
    "Diario/Revistas":         [("shop", "newsagent")],
    "Tabaqueria":              [("shop", "tobacco")],
    "Quiniela/Loteria":        [("shop", "lottery")],
    # --- Servicios varios ---
    "Lavanderia/Tintoreria":   [("shop", "laundry"), ("shop", "dry_cleaning")],
    "Sastreria/Arreglos":      [("shop", "tailor")],
    "Cerrajeria":              [("shop", "locksmith")],
    "Imprenta/Grafica":        [("shop", "copyshop")],
    "Funeraria":               [("shop", "funeral_directors")],
    "Agencia de viajes":       [("shop", "travel_agency")],
    "Gimnasio":                [("leisure", "fitness_centre")],
    # --- Educacion ---
    "Educacion - Escuela":     [("amenity", "school")],
    "Educacion - Universidad": [("amenity", "university"), ("amenity", "college")],
    "Educacion - Jardin":      [("amenity", "kindergarten")],
    "Autoescuela":             [("amenity", "driving_school")],
    # --- Turismo / entretenimiento ---
    "Hotel/Alojamiento":       [("tourism", "hotel"), ("tourism", "motel"),
                                ("tourism", "hostel"), ("tourism", "guest_house"),
                                ("tourism", "apartment")],
    "Cine":                    [("amenity", "cinema")],
    "Teatro":                  [("amenity", "theatre")],
    "Boliche/Nightclub":       [("amenity", "nightclub")],
    "Casino":                  [("amenity", "casino")],
}

# --------------------------------------------------------------------------
# Mapeo provincia -> region (5 grandes regiones argentinas)
# --------------------------------------------------------------------------

REGION_POR_PROVINCIA = {
    # NOA
    "jujuy": "NOA", "salta": "NOA", "tucuman": "NOA", "catamarca": "NOA",
    "la rioja": "NOA", "santiago del estero": "NOA",
    # NEA
    "formosa": "NEA", "chaco": "NEA", "corrientes": "NEA", "misiones": "NEA",
    # Cuyo
    "mendoza": "Cuyo", "san juan": "Cuyo", "san luis": "Cuyo",
    # Centro / Pampeana
    "buenos aires": "Centro/Pampeana",
    "ciudad autonoma de buenos aires": "Centro/Pampeana",
    "cordoba": "Centro/Pampeana", "santa fe": "Centro/Pampeana",
    "entre rios": "Centro/Pampeana", "la pampa": "Centro/Pampeana",
    # Patagonia
    "neuquen": "Patagonia", "rio negro": "Patagonia", "chubut": "Patagonia",
    "santa cruz": "Patagonia",
    "tierra del fuego, antartida e islas del atlantico sur": "Patagonia",
}


def norm(s):
    if not s:
        return ""
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    return s.strip().lower()


def region_de(provincia):
    return REGION_POR_PROVINCIA.get(norm(provincia), "")


# --------------------------------------------------------------------------
# Clasificador geografico (punto-en-poligono, sin dependencias)
# --------------------------------------------------------------------------

class GeoClasificador:
    def __init__(self, path):
        data = json.load(open(path, encoding="utf-8"))
        self.provincias = []  # [(nombre, bbox, [poligonos])]
        for f in data["features"]:
            nombre = f["properties"]["nombre"]
            geom = f["geometry"]
            polys = []
            if geom["type"] == "Polygon":
                polys.append(geom["coordinates"])
            elif geom["type"] == "MultiPolygon":
                polys.extend(geom["coordinates"])
            # bbox global de la provincia
            minx = miny = float("inf")
            maxx = maxy = float("-inf")
            for poly in polys:
                for ring in poly:
                    for x, y in ring:
                        minx = min(minx, x); maxx = max(maxx, x)
                        miny = min(miny, y); maxy = max(maxy, y)
            self.provincias.append((nombre, (minx, miny, maxx, maxy), polys))

    @staticmethod
    def _en_anillo(x, y, ring):
        inside = False
        n = len(ring)
        j = n - 1
        for i in range(n):
            xi, yi = ring[i]
            xj, yj = ring[j]
            if ((yi > y) != (yj > y)) and \
               (x < (xj - xi) * (y - yi) / (yj - yi) + xi):
                inside = not inside
            j = i
        return inside

    def provincia_de(self, lon, lat):
        if lon is None or lat is None:
            return ""
        for nombre, (minx, miny, maxx, maxy), polys in self.provincias:
            if not (minx <= lon <= maxx and miny <= lat <= maxy):
                continue
            for poly in polys:
                if self._en_anillo(lon, lat, poly[0]):
                    en_hueco = any(self._en_anillo(lon, lat, h) for h in poly[1:])
                    if not en_hueco:
                        return nombre
        return ""


# --------------------------------------------------------------------------
# Overpass
# --------------------------------------------------------------------------

def build_query(filters):
    parts = []
    for key, value in filters:
        for kind in ("node", "way", "relation"):
            parts.append(f'  {kind}["{key}"="{value}"]["name"](area.ar);')
    body = "\n".join(parts)
    return (
        f"[out:json][timeout:{QUERY_TIMEOUT}];\n"
        f'area["ISO3166-1"="AR"][admin_level=2]->.ar;\n'
        f"(\n{body}\n);\n"
        f"out tags center;\n"
    )


def fetch(query):
    last_err = None
    for attempt in range(MAX_RETRIES):
        endpoint = OVERPASS_ENDPOINTS[attempt % len(OVERPASS_ENDPOINTS)]
        try:
            resp = requests.post(endpoint, data={"data": query},
                                 headers=HEADERS, timeout=REQUEST_TIMEOUT)
            if resp.status_code == 200:
                return resp.json()
            if resp.status_code in (429, 504):
                wait = 20 * (attempt + 1)
                print(f"    {resp.status_code} en {endpoint}; espero {wait}s...", flush=True)
                time.sleep(wait)
                continue
            print(f"    HTTP {resp.status_code} en {endpoint}", flush=True)
            last_err = f"HTTP {resp.status_code}"
        except (requests.RequestException, json.JSONDecodeError) as e:
            last_err = str(e)
            wait = 15 * (attempt + 1)
            print(f"    Error: {e}; reintento en {wait}s...", flush=True)
            time.sleep(wait)
    raise RuntimeError(f"Fallo la consulta tras {MAX_RETRIES} intentos: {last_err}")


def pick(tags, *keys):
    for k in keys:
        v = tags.get(k)
        if v:
            return v.strip()
    return ""


def coords_de(el):
    if el.get("type") == "node":
        return el.get("lon"), el.get("lat")
    c = el.get("center")
    if c:
        return c.get("lon"), c.get("lat")
    return None, None


def extract(elements, sector, sink):
    nuevos = 0
    for el in elements:
        tags = el.get("tags", {})
        nombre = pick(tags, "name", "official_name", "brand")
        if not nombre:
            continue
        uid = f"{el['type']}/{el['id']}"
        if uid in sink:
            continue
        web = pick(tags, "website", "contact:website", "url", "brand:website")
        if web and not web.lower().startswith(("http://", "https://")):
            web = "http://" + web
        lon, lat = coords_de(el)
        sink[uid] = {
            "Nombre": nombre,
            "Sector": sector,
            "Pagina web": web,
            "Ciudad": pick(tags, "addr:city", "addr:town", "addr:village"),
            "_provincia_osm": pick(tags, "addr:province", "addr:state"),
            "Telefono": pick(tags, "phone", "contact:phone"),
            "_lon": lon, "_lat": lat,
        }
        nuevos += 1
    return nuevos


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--test", action="store_true")
    parser.add_argument("--out", default="empresas_argentina")
    args = parser.parse_args()

    if not os.path.exists(GEOJSON_PROVINCIAS):
        print(f"ERROR: falta {GEOJSON_PROVINCIAS}", file=sys.stderr)
        sys.exit(1)

    cats = list(CATEGORIES.items())
    if args.test:
        cats = cats[:2]

    sink = {}
    por_sector = defaultdict(int)
    total = len(cats)

    for i, (sector, filters) in enumerate(cats, 1):
        print(f"[{i}/{total}] {sector} ...", flush=True)
        try:
            data = fetch(build_query(filters))
        except RuntimeError as e:
            print(f"    SALTEADO ({e})", flush=True)
            continue
        elements = data.get("elements", [])
        nuevos = extract(elements, sector, sink)
        por_sector[sector] += nuevos
        print(f"    {len(elements)} elementos -> {nuevos} nuevos "
              f"(total acumulado: {len(sink)})", flush=True)
        if i < total:
            time.sleep(PAUSE_BETWEEN)

    filas = list(sink.values())
    print(f"\nClasificando provincia/region de {len(filas)} comercios...", flush=True)
    geo = GeoClasificador(GEOJSON_PROVINCIAS)
    sin_prov = 0
    for r in filas:
        prov = geo.provincia_de(r["_lon"], r["_lat"]) or r["_provincia_osm"]
        r["Provincia"] = prov
        r["Region"] = region_de(prov)
        if not prov:
            sin_prov += 1
    print(f"  sin provincia asignada: {sin_prov}", flush=True)

    print(f"\nTotal de empresas/comercios unicos: {len(filas)}", flush=True)
    for sector, n in sorted(por_sector.items(), key=lambda x: -x[1]):
        print(f"  {sector:32s} {n}", flush=True)

    guardar(filas, por_sector, args.out, geo)


def guardar(filas, por_sector, base, geo):
    import pandas as pd

    for r in filas:
        r["Latitud"] = r.pop("_lat")
        r["Longitud"] = r.pop("_lon")
        r.pop("_provincia_osm", None)

    cols = ["Nombre", "Sector", "Pagina web", "Region", "Provincia",
            "Ciudad", "Telefono", "Latitud", "Longitud"]
    df = pd.DataFrame(filas, columns=cols)
    df = df.sort_values(["Region", "Provincia", "Sector", "Nombre"],
                        kind="stable").reset_index(drop=True)

    resumen = pd.DataFrame(sorted(por_sector.items(), key=lambda x: -x[1]),
                           columns=["Sector", "Cantidad"])
    por_region = (df.groupby("Region").size().reset_index(name="Cantidad")
                    .sort_values("Cantidad", ascending=False))
    tabla = (df.pivot_table(index="Provincia", columns="Region",
                            values="Nombre", aggfunc="count", fill_value=0))

    xlsx = f"{base}.xlsx"
    with pd.ExcelWriter(xlsx, engine="openpyxl") as xl:
        df.to_excel(xl, sheet_name="Empresas", index=False)
        resumen.to_excel(xl, sheet_name="Resumen por sector", index=False)
        por_region.to_excel(xl, sheet_name="Resumen por region", index=False)
        ws = xl.sheets["Empresas"]
        for col, width in zip("ABCDEFGHI",
                              (40, 24, 38, 16, 22, 22, 18, 12, 12)):
            ws.column_dimensions[col].width = width
        ws.freeze_panes = "A2"
    df.to_csv(f"{base}.csv", index=False, encoding="utf-8-sig")
    print(f"\nGuardado: {xlsx}  ({len(df)} filas)", flush=True)
    print(f"Guardado: {base}.csv", flush=True)


if __name__ == "__main__":
    main()
