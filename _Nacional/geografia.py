# -*- coding: utf-8 -*-
"""
Referencia geografica oficial para ubicar comercios a nivel ciudad / partido / barrio.

Fuentes (cacheadas en _Nacional/geo/, se regeneran con `py geografia.py --descargar`):
  - localidades.csv    Georef (INDEC): 4.037 localidades con departamento y municipio
  - departamentos.csv  Georef: 529 departamentos (en Buenos Aires = los 135 partidos)
  - barrios_caba.geojson  GCBA: los 48 barrios con su comuna (poligonos)

Usos:
  - localidades_de_texto(): localidades nombradas en una direccion (para verificar_ubicacion)
  - zonas_relevamiento(folder): donde buscar comercios (partidos en Buenos Aires,
    barrios en CABA, ciudades principales en el resto)
  - zona_de_evidencia(evidencia, folder): ciudad / partido / barrio de un comercio ya
    verificado, a partir de la evidencia que junto verificar_ubicacion
"""
import csv
import json
import os
import re
import sys
import threading
from collections import defaultdict

import requests

from ubicaciones import FOLDER_A_LETRA, _dentro_anillo, norm

AQUI = os.path.dirname(os.path.abspath(__file__))
GEO = os.path.join(AQUI, "geo")
GEOREF = "https://apis.datos.gob.ar/georef/api"
URL_BARRIOS = "https://cdn.buenosaires.gob.ar/datosabiertos/datasets/ministerio-de-educacion/barrios/barrios.geojson"

# codigo de provincia INDEC -> letra ISO (la del CPA)
INDEC_A_LETRA = {"02": "C", "06": "B", "10": "K", "14": "X", "18": "W", "22": "H", "26": "U", "30": "E",
                 "34": "P", "38": "Y", "42": "L", "46": "F", "50": "M", "54": "N", "58": "Q", "62": "R",
                 "66": "A", "70": "J", "74": "D", "78": "Z", "82": "S", "86": "G", "90": "T", "94": "V"}

# Ciudades donde se releva en cada provincia (las mas pobladas, censo 2022). Buenos Aires
# y CABA no estan: se relevan todos sus partidos y barrios.
CIUDADES_PRINCIPALES = {
    "Catamarca": ["San Fernando del Valle de Catamarca", "Valle Viejo", "Tinogasta", "Andalgala"],
    "Chaco": ["Resistencia", "Presidencia Roque Saenz Pena", "Barranqueras", "Villa Angela", "Charata"],
    "Chubut": ["Comodoro Rivadavia", "Trelew", "Puerto Madryn", "Rawson", "Esquel"],
    "Cordoba": ["Cordoba", "Rio Cuarto", "Villa Maria", "Villa Carlos Paz", "San Francisco"],
    "Corrientes": ["Corrientes", "Goya", "Paso de los Libres", "Mercedes Corrientes"],
    "Entre-Rios": ["Parana", "Concordia", "Gualeguaychu", "Concepcion del Uruguay"],
    "Formosa": ["Formosa", "Clorinda", "Pirane"],
    "Jujuy": ["San Salvador de Jujuy", "Palpala", "San Pedro de Jujuy", "Libertador General San Martin"],
    "La-Pampa": ["Santa Rosa La Pampa", "General Pico", "Toay"],
    "La-Rioja": ["La Rioja", "Chilecito", "Aimogasta"],
    "Mendoza": ["Mendoza", "Godoy Cruz", "Guaymallen", "Las Heras Mendoza", "Maipu Mendoza",
                "Lujan de Cuyo", "San Rafael", "San Martin Mendoza"],
    "Misiones": ["Posadas", "Obera", "Eldorado", "Puerto Iguazu"],
    "Neuquen": ["Neuquen", "Cutral Co", "Plottier", "San Martin de los Andes", "Zapala"],
    "Rio-Negro": ["San Carlos de Bariloche", "General Roca", "Cipolletti", "Viedma"],
    "Salta": ["Salta", "San Ramon de la Nueva Oran", "Tartagal", "General Guemes"],
    "San-Juan": ["San Juan", "Rivadavia San Juan", "Chimbas", "Rawson San Juan", "Santa Lucia San Juan"],
    "San-Luis": ["San Luis", "Villa Mercedes", "Merlo San Luis"],
    "Santa-Cruz": ["Rio Gallegos", "Caleta Olivia", "El Calafate", "Pico Truncado"],
    "Santa-Fe": ["Rosario", "Santa Fe", "Rafaela", "Venado Tuerto", "Reconquista"],
    "Santiago-del-Estero": ["Santiago del Estero", "La Banda", "Termas de Rio Hondo"],
    "Tierra-del-Fuego": ["Ushuaia", "Rio Grande", "Tolhuin"],
    "Tucuman": ["San Miguel de Tucuman", "Yerba Buena", "Tafi Viejo", "Banda del Rio Sali", "Concepcion Tucuman"],
}

# Nombres de uso comun en CABA que no son barrios oficiales -> barrio oficial
ALIAS_CABA = {"microcentro": "San Nicolas", "barrio norte": "Recoleta", "once": "Balvanera",
              "abasto": "Balvanera", "congreso": "Balvanera", "las canitas": "Palermo",
              "palermo soho": "Palermo", "palermo hollywood": "Palermo", "tribunales": "San Nicolas",
              "retiro": "Retiro", "la paternal": "Paternal", "montserrat": "Monserrat",
              "villa pueyrredon": "Villa Pueyrredon", "constitucion": "Constitucion"}

# Nombres de localidad que tambien son palabras comunes: no sirven como evidencia
NO_LOCALIDAD = set("""
centro norte sur este oeste industrial estacion colonia puerto villa barrio pueblo paraje
libertad union esperanza victoria progreso porvenir providencia trabajo fortuna america
belgrano rivadavia sarmiento moreno alberdi mitre lavalle urquiza alem pellegrini
independencia constitucion florida las flores la plata general centenario bicentenario
los pinos las rosas el sol la paz el carmen san jose santa ana la estrella el dorado
""".split()) | {"la paz", "las flores", "san jose", "santa ana", "la estrella", "el dorado", "el carmen",
               "los pinos", "las rosas", "el sol", "la florida", "la granja", "el paraiso", "la union",
               "san pedro", "santa lucia", "san antonio", "san martin", "general belgrano"}

_lock = threading.Lock()
_cache = {}


def _n(s):
    return " ".join(re.sub(r"[^a-z0-9 ]", " ", norm(s)).split())


def descargar():
    os.makedirs(GEO, exist_ok=True)
    s = requests.Session()
    for nombre, url in (
        ("localidades.csv", f"{GEOREF}/localidades?max=5000&aplanar=true&formato=csv&campos=nombre,provincia.id,"
                            "departamento.nombre,municipio.nombre,localidad_censal.nombre,centroide.lat,"
                            "centroide.lon,categoria"),
        ("departamentos.csv", f"{GEOREF}/departamentos?max=600&aplanar=true&formato=csv&campos=id,nombre,"
                              "provincia.id,centroide.lat,centroide.lon"),
        ("barrios_caba.geojson", URL_BARRIOS),
    ):
        r = s.get(url, timeout=120)
        r.raise_for_status()
        with open(os.path.join(GEO, nombre), "wb") as f:
            f.write(r.content)
        print(f"  {nombre}: {len(r.content):,} bytes")


def _leer_csv(nombre):
    with open(os.path.join(GEO, nombre), encoding="utf-8") as f:
        return list(csv.DictReader(f))


def localidades():
    """[(letra, nombre_norm, localidad, departamento, municipio)] (con cache)."""
    if "loc" not in _cache:
        filas = []
        for r in _leer_csv("localidades.csv"):
            letra = INDEC_A_LETRA.get(r["provincia_id"].zfill(2))
            if not letra:
                continue
            for nom in {r["localidad_nombre"], r["municipio_nombre"], r["localidad_censal_nombre"]}:
                if nom:
                    filas.append((letra, _n(nom), r["localidad_nombre"], r["departamento_nombre"],
                                  r["municipio_nombre"]))
        _cache["loc"] = filas
    return _cache["loc"]


def indice_unico(min_len=5):
    """nombre normalizado -> letra, solo nombres que existen en UNA sola provincia y no son
    palabras comunes. Es lo que se puede usar como evidencia de provincia."""
    if "unico" not in _cache:
        letras = defaultdict(set)
        for letra, n, *_ in localidades():
            if letra != "C":  # en CABA los barrios ya estan en ubicaciones.LOCALIDADES
                letras[n].add(letra)

        def sirve(n, ls):
            if len(ls) != 1 or n in NO_LOCALIDAD or n.startswith(("comuna ", "barrio ")):
                return False
            return len(n) >= (10 if n.startswith("villa ") else min_len)

        _cache["unico"] = {n: next(iter(ls)) for n, ls in letras.items() if sirve(n, ls)}
    return _cache["unico"]


def _ngramas(texto, maximo=6):
    """Prefijos de 1..maximo palabras de un texto ya normalizado (el mas largo primero)."""
    palabras = texto.split()[:maximo]
    return [" ".join(palabras[:k]) for k in range(len(palabras), 0, -1)]


RE_NUM = re.compile(r"\b\d{1,5}\b")
RE_SEP = re.compile(r"[,\-–|]\s*(?:ciudad de |provincia de |pcia\.? de |partido de )?")


def localidades_de_texto(t_norm, indice=None):
    """Busca 'numero ..., Localidad' (como en una direccion) y devuelve [(letra, nombre, fragmento)].
    La localidad no puede ir seguida de un numero ('Av. Corrientes 1234' no es la ciudad)."""
    indice = indice or indice_unico()
    out, vistos = [], set()
    for m in RE_NUM.finditer(t_norm):
        tramo = t_norm[m.end():m.end() + 110]
        for s in RE_SEP.finditer(tramo[:47]):
            resto = tramo[s.end():]
            limpio = " ".join(re.sub(r"[^a-z0-9 ]", " ", resto).split())
            for cand in _ngramas(limpio):
                if cand in indice:
                    sigue = limpio[len(cand):].lstrip()
                    if sigue[:1].isdigit():
                        break
                    letra = indice[cand]
                    if (letra, cand) not in vistos:
                        vistos.add((letra, cand))
                        out.append((letra, cand, t_norm[m.start():m.end() + s.end() + len(cand) + 2]))
                    break
    return out


def localidad_exacta(nombre):
    """Letra de una localidad escrita sola (ej addressLocality de JSON-LD), si es unica."""
    return indice_unico().get(_n(nombre))


# ---------------------------------------------------------------------------
# Zonas a relevar
# ---------------------------------------------------------------------------
def partidos_bsas():
    return sorted(r["departamento_nombre"] for r in _leer_csv("departamentos.csv") if r["provincia_id"] == "06")


def _barrios():
    if "barrios" not in _cache:
        with open(os.path.join(GEO, "barrios_caba.geojson"), encoding="utf-8") as f:
            g = json.load(f)
        bs = []
        for feat in g["features"]:
            p, geom = feat["properties"], feat["geometry"]
            polys = [geom["coordinates"]] if geom["type"] == "Polygon" else geom["coordinates"]
            bs.append((p["nombre"].title(), f"Comuna {p['comuna']}", polys))
        _cache["barrios"] = bs
    return _cache["barrios"]


def barrios_caba():
    return sorted(b for b, _, _ in _barrios())


def zonas_relevamiento(folder):
    """Donde se buscan comercios: todos los partidos en Buenos Aires, todos los barrios en
    CABA, las ciudades principales en el resto. Se devuelven ya listas para la busqueda."""
    if folder == "Buenos-Aires":
        return [f"{p} Buenos Aires" for p in partidos_bsas()]
    if folder == "CABA":
        return [f"{b} CABA" for b in barrios_caba()]
    return CIUDADES_PRINCIPALES.get(folder, [])


# ---------------------------------------------------------------------------
# Zona de un comercio
# ---------------------------------------------------------------------------
def barrio_de_punto(lat, lon):
    for nombre, comuna, polys in _barrios():
        for poly in polys:
            if _dentro_anillo(lon, lat, poly[0]) and not any(_dentro_anillo(lon, lat, h) for h in poly[1:]):
                return nombre, comuna
    return None


def ubicacion_georef(lat, lon):
    """(departamento, municipio) de un punto segun Georef. Cacheado en geo/cache_ubicacion.json."""
    clave = f"{lat:.4f},{lon:.4f}"
    with _lock:
        if "ubic" not in _cache:
            p = os.path.join(GEO, "cache_ubicacion.json")
            _cache["ubic"] = json.load(open(p, encoding="utf-8")) if os.path.exists(p) else {}
        if clave in _cache["ubic"]:
            return tuple(_cache["ubic"][clave]) if _cache["ubic"][clave] else None
    try:
        u = requests.get(f"{GEOREF}/ubicacion", params={"lat": lat, "lon": lon}, timeout=20).json()["ubicacion"]
        res = ((u.get("departamento") or {}).get("nombre"), (u.get("municipio") or {}).get("nombre"))
        res = res if res[0] else None
    except Exception:
        return None
    with _lock:
        _cache["ubic"][clave] = res
        with open(os.path.join(GEO, "cache_ubicacion.json"), "w", encoding="utf-8") as f:
            json.dump(_cache["ubic"], f, ensure_ascii=False)
    return res


def _indice_provincia(letra):
    """nombre normalizado -> (localidad, departamento) de UNA provincia (admite nombres que
    se repiten en otras: aca ya se sabe la provincia)."""
    k = f"prov_{letra}"
    if k not in _cache:
        idx = {}
        for l, n, loc, dep, mun in localidades():
            # en CABA solo sirven los barrios (municipio = comuna y localidad censal = toda la ciudad)
            if l == letra != "C" and len(n) >= 4 and n not in idx:
                idx[n] = (mun or loc, dep)
        if letra == "C":
            for b, comuna, _ in _barrios():
                idx[_n(b)] = (b, comuna)
            comunas = {_n(b): c for b, c, _ in _barrios()}
            for alias, b in ALIAS_CABA.items():
                idx[alias] = (b, comunas.get(_n(b), ""))
        _cache[k] = idx
    return _cache[k]


RE_EVID = re.compile(r"(\w+):([A-Z]+)\((\d)\) ([^|]*)")
PRIORIDAD = {"coordenadas": 0, "jsonld_direccion": 1, "direccion": 2, "localidad_argentina": 2,
             "titulo": 3, "busqueda_web": 4, "localizador_sucursales": 4, "osm_dominio": 5, "osm_nombre": 6}


def zona_de_evidencia(evidencia, folder, es_cadena=False):
    """{'Localidad', 'Departamento', 'Metodo zona'} de un comercio verificado en `folder`.
    Localidad = ciudad (en CABA, el barrio). Departamento = partido en Buenos Aires,
    comuna en CABA, departamento en el resto."""
    letra = FOLDER_A_LETRA[folder]
    vacio = {"Localidad": "Varias (cadena)" if es_cadena else "", "Departamento": "", "Metodo zona": ""}
    if not isinstance(evidencia, str) or not evidencia:
        return vacio
    idx = _indice_provincia(letra)
    items = sorted(((PRIORIDAD.get(t, 9), t, d) for t, ls, _, d in RE_EVID.findall(evidencia)
                    if letra in ls), key=lambda x: x[0])
    for _, tipo, det in items:
        if tipo == "coordenadas":
            try:
                lat, lon = (float(x) for x in det.strip().split(",")[:2])
            except ValueError:
                continue
            if letra == "C":
                b = barrio_de_punto(lat, lon)
                if b:
                    return {"Localidad": b[0], "Departamento": b[1], "Metodo zona": "coordenadas"}
            else:
                u = ubicacion_georef(lat, lon)
                if u:
                    return {"Localidad": u[1] or u[0], "Departamento": u[0], "Metodo zona": "coordenadas"}
            continue
        palabras = " ".join(re.sub(r"[^a-z0-9 ]", " ", norm(det)).split()).split()
        cands = []  # (posicion, nombre): la localidad va despues de la calle, gana la ultima
        i = 0
        while i < len(palabras):
            for cand in _ngramas(" ".join(palabras[i:])):
                k = len(cand.split())
                if cand in idx and not (i + k < len(palabras) and palabras[i + k].isdigit()):
                    cands.append((i, cand))
                    i += k - 1
                    break
            i += 1
        nombre_prov = _n(LETRA_A_NOMBRE_LARGO.get(letra, ""))
        utiles = [c for c in cands if c[1] != nombre_prov] or cands
        if utiles:
            loc, dep = idx[utiles[-1][1]]
            return {"Localidad": loc, "Departamento": dep, "Metodo zona": tipo}
    return vacio


LETRA_A_NOMBRE_LARGO = {"W": "corrientes", "M": "mendoza", "X": "cordoba", "S": "santa fe", "H": "chaco",
                        "N": "misiones", "P": "formosa", "Y": "jujuy", "A": "salta", "T": "tucuman",
                        "K": "catamarca", "F": "la rioja", "J": "san juan", "D": "san luis",
                        "G": "santiago del estero", "L": "la pampa", "Q": "neuquen", "R": "rio negro",
                        "U": "chubut", "Z": "santa cruz", "V": "tierra del fuego", "E": "entre rios",
                        "B": "buenos aires", "C": "caba"}


if __name__ == "__main__":
    if "--descargar" in sys.argv:
        descargar()
    u = indice_unico()
    print(f"{len(localidades())} nombres, {len(u)} unicos por provincia; "
          f"{len(partidos_bsas())} partidos; {len(barrios_caba())} barrios")
