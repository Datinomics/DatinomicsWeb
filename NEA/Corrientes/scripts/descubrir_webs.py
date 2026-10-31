# -*- coding: utf-8 -*-
"""
Descubrimiento intensivo de paginas web de comercios, por provincia.

Paso 1: trae de OpenStreetMap TODOS los comercios con nombre de la provincia
        (cualquier shop/office/craft + amenities comerciales).
Paso 2: para los que no tienen web en OSM, la busca con DuckDuckGo (ddgs).
Paso 3: asigna ciudad (mas cercana de la lista) y nivel de confianza.
Paso 4: guarda checkpoint y, al final, un Excel SOLO con los que tienen web.

Uso:
    py descubrir_webs.py --provincia Corrientes --sample 40   # piloto
    py descubrir_webs.py --provincia Corrientes               # completo
"""

import argparse
import math
import os
import re
import shutil
import socket
import time
import unicodedata


import requests
from dotenv import load_dotenv

# Red: ningun socket puede colgarse indefinidamente
socket.setdefaulttimeout(30)

# --------------------------------------------------------------------------
OVERPASS = ["https://overpass-api.de/api/interpreter",
            "https://overpass.kumi.systems/api/interpreter"]
load_dotenv()
CONTACT_EMAIL = os.environ.get("SCRAPER_CONTACT_EMAIL", "")
HEADERS = {"User-Agent": f"empresas-ar-crawler/1.2 (contacto: {CONTACT_EMAIL})"}
# Ciudades de referencia por provincia (para asignar localidad y contexto de busqueda)
CIUDADES = {
    "Corrientes": [
        ("Corrientes", -27.4806, -58.8341),
        ("Goya", -29.1400, -59.2667),
        ("Mercedes", -29.1833, -58.0833),
        ("Curuzu Cuatia", -29.7906, -58.0539),
        ("Paso de los Libres", -29.7128, -57.0881),
        ("Santo Tome", -28.5500, -56.0500),
        ("Ituzaingo", -27.5894, -56.6814),
        ("Bella Vista", -28.5089, -59.0428),
        ("Esquina", -30.0150, -59.5256),
        ("Saladas", -28.2556, -58.6261),
    ],
}

EXCLUIR_DOM = (
    # redes sociales / mapas / genericos
    "facebook.", "instagram.", "linkedin.", "twitter.", "x.com", "tiktok.",
    "youtube.", "pinterest.", "spotify.", "wikipedia.", "wa.me", "google.",
    "bing.com", "waze.com", "openstreetmap", "mapcarta", "moovit", "moovitapp",
    "wikimapia", "foursquare", "yelp.", "where.com",
    # directorios / agregadores de empresas
    "mercadolibre.", "paginasamarillas", "paginasblancas", "guiaclarin",
    "guia.clarin", "cylex", "cybo.com", "dateas.", "cuitonline", "firmania",
    "todosnegocios", "redargentina", "infoisinfo", "hotfrog", "opendi",
    "yalwa", "find-open", "open-closed", "licuo", "nuevaeranet", "sucursales24",
    "enotri", "tucalle", "callejero", "demapas", "nombrescalles", "clasipar",
    "vivanuncios", "olx.", "opcionis", "empresia", "informacion-empresas",
    "universodempresas", "soloempresas", "argentinaempresas", "guiatelefonica",
    "laguia", "iguia", "evisos", "clasiar", "tuugo", "kompass", "axesor",
    "serviciotecnico24", "laelectronicaonline", "urbanococina", "todoresto",
    "educacionfisica.com", "ituzaingocorrientes", "ciudaddecorrientes",
    # turismo / reservas / noticias / inmobiliarias / empleo
    "tripadvisor", "booking.", "expedia.", "despegar.", "trivago", "hoteles.com",
    "airbnb.", "atrapalo", "cozycozy", "kayak.", "hostelworld",
    "zonaprop", "argenprop", "inmuebles24", "properati", "remax",
    "indeed.", "computrabajo", "bumeran", "zonajobs", "omnilineas", "virail",
    "plataforma10", "central-de-pasajes", "voyenbus",
    "corrienteshoy", "regionlitoral", "elsantotomesino", "ellitoral",
    "diarioepoca", "primeraedicion", "infobae", "lanacion", "clarin.com",
    # estatales / educativos
    ".gob.ar", ".gov.ar", "argentina.gob", "unsam.edu", ".edu.ar",
)

# Valores OSM a excluir por pedido: bancos y dependencias de gobierno
EXCLUIR_VALS = {"bank", "government", "townhall", "courthouse", "public_building",
                "political_party", "diplomatic", "prison", "register_office"}

# Palabras que no sirven como token identificador del nombre
STOP_TOKENS = {"la", "el", "los", "las", "de", "del", "y", "e", "san", "santa",
               "srl", "sa", "sas", "sh", "casa", "super", "mini", "auto", "shop",
               "store", "the", "don", "doña", "dona", "centro", "grupo", "local",
               "almacen", "kiosco", "bar", "hotel", "farmacia", "banco", "para"}

# etiquetas OSM -> sector legible (las mas comunes; el resto usa el valor crudo)
SECTOR_LABEL = {
    "supermarket": "Supermercado", "convenience": "Autoservicio/Almacen",
    "wholesale": "Mayorista", "kiosk": "Kiosco", "bakery": "Panaderia",
    "butcher": "Carniceria", "greengrocer": "Verduleria", "pharmacy": "Farmacia",
    "restaurant": "Restaurante", "fast_food": "Comida rapida", "cafe": "Cafe/Bar",
    "bar": "Cafe/Bar", "pub": "Cafe/Bar", "clothes": "Indumentaria",
    "shoes": "Calzado", "hardware": "Ferreteria", "doityourself": "Ferreteria",
    "furniture": "Mueblerias", "electronics": "Electronica", "mobile_phone": "Telefonia",
    "car": "Concesionaria", "car_repair": "Taller mecanico", "car_parts": "Repuestos",
    "tyres": "Gomeria", "motorcycle": "Motos", "bicycle": "Bicicleteria",
    "fuel": "Estacion de servicio", "bank": "Banco", "hotel": "Hotel",
    "jewelry": "Joyeria", "hairdresser": "Peluqueria", "beauty": "Belleza",
    "optician": "Optica", "books": "Libreria", "stationery": "Libreria/Papeleria",
    "florist": "Floreria", "toys": "Jugueteria", "sports": "Deportes",
    "pet": "Pet shop", "veterinary": "Veterinaria", "estate_agent": "Inmobiliaria",
    "lawyer": "Estudio juridico", "accountant": "Estudio contable",
    "insurance": "Seguros", "company": "Empresa/Oficina", "hospital": "Hospital",
    "clinic": "Clinica", "dentist": "Dentista", "doctors": "Consultorio medico",
    "computer": "Computacion", "travel_agency": "Agencia de viajes",
    "hardware_store": "Ferreteria", "confectionery": "Confiteria",
    "deli": "Fiambreria", "beverages": "Bebidas", "alcohol": "Vinoteca",
    "cosmetics": "Cosmetica", "perfumery": "Perfumeria", "gift": "Regaleria",
    "variety_store": "Bazar/Variedades", "department_store": "Tienda departamental",
    "mall": "Centro comercial", "hostel": "Hostel", "guest_house": "Hosped./Posada",
    "apartment": "Alquiler temporario", "motel": "Motel",
}


def norm(s):
    if not s:
        return ""
    s = unicodedata.normalize("NFKD", s)
    return "".join(c for c in s if not unicodedata.combining(c)).strip().lower()


def overpass(query):
    last = None
    for i in range(5):
        ep = OVERPASS[i % len(OVERPASS)]
        try:
            r = requests.post(ep, data={"data": query}, headers=HEADERS, timeout=300)
            if r.status_code == 200 and r.text.strip().startswith("{"):
                return r.json()["elements"]
            last = f"HTTP {r.status_code}"
        except Exception as e:
            last = str(e)
        time.sleep(15)
    raise RuntimeError(f"Overpass fallo: {last}")


def traer_comercios(provincia):
    q = f"""
[out:json][timeout:300];
area["boundary"="administrative"]["admin_level"="4"]["name"="{provincia}"]->.p;
(
  nwr["shop"]["name"](area.p);
  nwr["office"]["name"](area.p);
  nwr["craft"]["name"](area.p);
  nwr["tourism"~"^(hotel|motel|hostel|guest_house|apartment)$"]["name"](area.p);
  nwr["leisure"="fitness_centre"]["name"](area.p);
  nwr["amenity"~"^(restaurant|cafe|bar|pub|fast_food|pharmacy|bank|fuel|hospital|clinic|dentist|doctors|veterinary|cinema|theatre|nightclub|casino|driving_school|ice_cream|bureau_de_change|marketplace)$"]["name"](area.p);
);
out tags center;
"""
    els = overpass(q)
    out = {}
    for e in els:
        t = e.get("tags", {})
        nombre = (t.get("name") or t.get("official_name") or t.get("brand") or "").strip()
        if not nombre:
            continue
        uid = f"{e['type']}/{e['id']}"
        if uid in out:
            continue
        if e["type"] == "node":
            lon, lat = e.get("lon"), e.get("lat")
        else:
            c = e.get("center", {})
            lon, lat = c.get("lon"), c.get("lat")
        val = (t.get("shop") or t.get("amenity") or t.get("office")
               or t.get("craft") or t.get("tourism") or t.get("leisure") or "")
        sector = SECTOR_LABEL.get(val, val.replace("_", " ").capitalize() or "Otro")
        if val in EXCLUIR_VALS:
            continue
        web = (t.get("website") or t.get("contact:website")
               or t.get("url") or t.get("brand:website") or "").strip()
        if web and not web.lower().startswith(("http://", "https://")):
            web = "http://" + web
        out[uid] = {
            "Nombre": nombre, "Sector": sector, "WebOSM": web,
            "Telefono": (t.get("phone") or t.get("contact:phone") or "").strip(),
            "CiudadOSM": (t.get("addr:city") or t.get("addr:town")
                          or t.get("addr:village") or "").strip(),
            "lon": lon, "lat": lat,
        }
    return list(out.values())


def clave(nombre, lat, lon):
    """Clave estable de un comercio para reanudar (nombre + coordenadas)."""
    try:
        la = round(float(lat), 5) if lat not in (None, "") else None
        lo = round(float(lon), 5) if lon not in (None, "") else None
    except (TypeError, ValueError):
        la = lo = None
    return (norm(str(nombre)), la, lo)


def haversine(lat1, lon1, lat2, lon2):
    R = 6371
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * R * math.asin(math.sqrt(a))


def ciudad_cercana(lat, lon, ciudades):
    if lat is None or lon is None:
        return "", None
    best, bestd = "", 1e9
    for nombre, cla, clo in ciudades:
        d = haversine(lat, lon, cla, clo)
        if d < bestd:
            best, bestd = nombre, d
    return best, bestd


def dominio(url):
    try:
        d = url.split("/")[2] if "://" in url else url.split("/")[0]
        return d.lower().replace("www.", "")
    except Exception:
        return url.lower()


def tokens_nombre(nombre):
    """Tokens identificadores del nombre (>=4 chars, sin stopwords)."""
    return [t for t in re.split(r"[^a-z0-9]+", norm(nombre))
            if len(t) >= 4 and t not in STOP_TOKENS]


def coincide_dominio(nombre, url):
    """True si algun token del nombre aparece en el dominio (match fuerte)."""
    dom = dominio(url)
    host = re.sub(r"[^a-z0-9]", "", dom.split("/")[0])  # solo el host, sin puntuacion
    # quitar tld comunes del final para no matchear basura
    for t in tokens_nombre(nombre):
        if t in host:
            return True
    return False


_ddgs = None
def buscar_web(nombre, consulta):
    """Devuelve (url, confianza). Solo acepta resultados cuyo dominio contiene
    el nombre del comercio (precision alta). Si ninguno coincide, ('', '')."""
    global _ddgs
    from ddgs import DDGS
    for intento in range(3):
        try:
            if _ddgs is None:
                _ddgs = DDGS(timeout=20)
            res = list(_ddgs.text(consulta, region="ar-es", max_results=8))
            for r in res:
                u = r.get("href") or ""
                if not u:
                    continue
                dom = dominio(u)
                if any(x in dom for x in EXCLUIR_DOM):
                    continue
                host = dom.split("/")[0]
                if host.endswith((".pe", ".mx", ".cl", ".es", ".br", ".uy",
                                  ".py", ".bo", ".co", ".pl", ".ru", ".de",
                                  ".fr", ".it", ".uk", ".us", ".ca", ".pt",
                                  ".ve", ".ec", ".pe/")):
                    continue
                if coincide_dominio(nombre, u):
                    return u, "Alta"
            return "", ""
        except Exception:
            _ddgs = None
            time.sleep(8 * (intento + 1))
    return "", "__ERROR__"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--provincia", required=True)
    ap.add_argument("--sample", type=int, default=0, help="0 = todos")
    ap.add_argument("--delay", type=float, default=4.0)
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    prov = args.provincia
    ciudades = CIUDADES.get(prov, [])
    base = args.out or f"webs_{norm(prov).replace(' ', '_')}"
    if args.sample:
        base += f"_piloto{args.sample}"

    print(f"Trayendo comercios de OSM ({prov})...", flush=True)
    comercios = traer_comercios(prov)
    print(f"  {len(comercios)} comercios con nombre", flush=True)

    # asignar ciudad
    for c in comercios:
        ciudad, dist = ciudad_cercana(c["lat"], c["lon"], ciudades)
        c["Ciudad"] = c["CiudadOSM"] or (ciudad if dist and dist < 35 else "")
        c["_ciudad_busqueda"] = ciudad or c["CiudadOSM"] or prov

    # ordenar por PRIORIDAD de rubro (supermercados y retail clave primero),
    # luego el resto. Dentro de cada grupo, por nombre.
    PRIORIDAD = ["Supermercado", "Autoservicio/Almacen", "Mayorista", "Farmacia",
                 "Electronica", "Telefonia", "Computacion", "Indumentaria",
                 "Calzado", "Mueblerias", "Ferreteria", "Panaderia", "Carniceria",
                 "Hotel", "Restaurante", "Confiteria", "Heladeria", "Joyeria",
                 "Optica", "Libreria", "Jugueteria", "Deportes", "Perfumeria",
                 "Cosmetica", "Bicicleteria", "Motos", "Regaleria"]
    rank = {s: i for i, s in enumerate(PRIORIDAD)}
    comercios.sort(key=lambda x: (rank.get(x["Sector"], 999), x["Nombre"]))
    if args.sample:
        # muestra variada: algunos con web OSM y muchos sin
        sin = [c for c in comercios if not c["WebOSM"]]
        con = [c for c in comercios if c["WebOSM"]]
        comercios = (con[:max(3, args.sample // 10)] + sin)[:args.sample]

    # --- Reanudar desde checkpoint si existe ---
    done = {}
    ckpt = f"{base}_checkpoint.csv"
    if os.path.exists(ckpt):
        import pandas as pd
        shutil.copy(ckpt, ckpt + ".bak")  # respaldo por las dudas
        prev = pd.read_csv(ckpt).fillna("")
        for _, r in prev.iterrows():
            done[clave(r["Nombre"], r.get("Latitud", ""), r.get("Longitud", ""))] = (
                str(r["Pagina web"]), str(r["Confianza"]), str(r["Fuente web"]))
        print(f"Reanudando: {len(done)} comercios ya estaban en el checkpoint", flush=True)

    print(f"Descubriendo webs de {len(comercios)} comercios (delay {args.delay}s)...", flush=True)
    resultados = []
    t0 = time.time()
    for i, c in enumerate(comercios, 1):
        k = clave(c["Nombre"], c["lat"], c["lon"])
        if k in done:                              # ya procesado: reusar
            web, conf, fuente = done[k]
        elif c["WebOSM"]:
            web, conf, fuente = c["WebOSM"], "Alta", "OSM"
        else:
            consulta = f'{c["Nombre"]} {c["Sector"]} {c["_ciudad_busqueda"]} {prov}'
            web, conf = buscar_web(c["Nombre"], consulta)
            fuente = "Web" if web else ""
            time.sleep(args.delay)
        c.update({"Pagina web": web, "Confianza": conf, "Fuente web": fuente})
        resultados.append(c)
        if i % 10 == 0 or i == len(comercios):
            con_web = sum(1 for r in resultados if r["Pagina web"])
            print(f"  [{i}/{len(comercios)}] con web: {con_web} "
                  f"({con_web*100//i}%) | {int(time.time()-t0)}s", flush=True)
            guardar(resultados, base, prov, final=False)

    guardar(resultados, base, prov, final=True)


def guardar(resultados, base, prov, final):
    import pandas as pd
    cols = ["Nombre", "Sector", "Pagina web", "Confianza", "Fuente web",
            "Ciudad", "Telefono", "lat", "lon"]
    df = pd.DataFrame(resultados)
    for col in cols:
        if col not in df:
            df[col] = ""
    df = df[cols].rename(columns={"lat": "Latitud", "lon": "Longitud"})
    df.to_csv(f"{base}_checkpoint.csv", index=False, encoding="utf-8-sig")
    if final:
        con_web = df[df["Pagina web"].astype(str).str.len() > 0].copy()
        con_web = con_web.sort_values(
            ["Confianza", "Ciudad", "Sector", "Nombre"],
            key=lambda s: s.map({"Alta": 0, "Media": 1, "Baja": 2}).fillna(s),
            kind="stable")
        xlsx = f"{base}.xlsx"
        with pd.ExcelWriter(xlsx, engine="openpyxl") as xl:
            con_web.to_excel(xl, sheet_name="Con pagina web", index=False)
            ws = xl.sheets["Con pagina web"]
            for col, w in zip("ABCDEFGHI", (38, 22, 40, 12, 12, 22, 18, 12, 12)):
                ws.column_dimensions[col].width = w
            ws.freeze_panes = "A2"
        print(f"\n== FINAL ==\nComercios procesados: {len(df)}", flush=True)
        print(f"Con pagina web: {len(con_web)}  ({len(con_web)*100//max(1,len(df))}%)", flush=True)
        print(f"  Confianza Alta:  {(con_web['Confianza']=='Alta').sum()}", flush=True)
        print(f"  Confianza Media: {(con_web['Confianza']=='Media').sum()}", flush=True)
        print(f"  Confianza Baja:  {(con_web['Confianza']=='Baja').sum()}", flush=True)
        print(f"Guardado: {xlsx}", flush=True)


if __name__ == "__main__":
    main()
