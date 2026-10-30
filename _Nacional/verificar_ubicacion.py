# -*- coding: utf-8 -*-
"""
Verifica que cada comercio de <Folder>_full.xlsx este REALMENTE en esa provincia.

Junta evidencia de dos fuentes independientes:
  1) OpenStreetMap (empresas_argentina.csv): mismo dominio web, o misma marca
     (cadenas) / mismo nombre que el dominio, con coordenadas dentro de la provincia.
  2) El sitio del comercio (home + paginas de contacto/sucursales):
     - coordenadas de Google Maps / JSON-LD  -> point-in-polygon      (fuerte)
     - CPA (ej W3400ABC: la letra es la provincia)                     (fuerte)
     - JSON-LD PostalAddress (addressRegion / addressLocality)         (fuerte)
     - direccion "Calle 123, Localidad" con localidad sin ambiguedad   (media)
     - caracteristica telefonica / WhatsApp de la provincia            (media)
       (el 11 es AMBA: solo cuenta como debil para CABA)

Pesos: fuerte=3, media=2, debil=1. Una tienda queda VERIFICADA si suma >= 2
para la provincia objetivo. Si no, se clasifica como OTRA_UBICACION (hay
evidencia de otra provincia / exterior), DEBIL, SIN_EVIDENCIA o NO_RESPONDE.

Uso como modulo: verificar_provincia(folder, workers=32) -> DataFrame
"""
import concurrent.futures as cf
import html as _html
import json
import os
import re
import threading
import time
import warnings
from collections import defaultdict

import pandas as pd
import requests
import urllib3

import geografia
from ubicaciones import (FOLDER_A_LETRA, LETRA_A_NOMBRE, LOCALIDADES, norm,
                         provincia_de_cp, provincia_de_punto, provincias_de_telefono)

warnings.filterwarnings("ignore", category=urllib3.exceptions.InsecureRequestWarning)
AQUI = os.path.dirname(os.path.abspath(__file__))

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")
HDRS = {"User-Agent": UA, "Accept-Language": "es-AR,es;q=0.9",
        "Accept": "text/html,application/xhtml+xml,*/*;q=0.8"}
MAX_BYTES = 1_500_000
MAX_SUBPAGINAS = 3
FUERTE, MEDIA, DEBIL = 3, 2, 1

# dominios que nunca son el sitio propio de un comercio
NO_COMERCIO = ("facebook.", "instagram.", "pinterest.", "linkedin.", "tiktok.", "youtube.",
               "twitter.", "x.com", "mercadolibre.", "statscrop.", "wikipedia.", "google.",
               "comoponerunnegocio", "tiendeo.", "rappi.", "pedidosya.", "linktr.ee",
               "blogspot.", "wordpress.com", "wa.me", "whatsapp.", "alamaula.", "propdata.",
               "argentina-directorio", "gomeriasenargentina", "cylex", "guiaempresas", "wixsite.",
               "aeropuertosargentina", "adslzone.", "infobae.", "clarin.", "lanacion.", "tripadvisor.")
# un comercio con evidencia de tantas provincias distintas es un directorio / agregador
PROVINCIAS_AGREGADOR = 4

PALABRAS_SUBPAGINA = ("contacto", "contact", "sucursal", "locales", "nuestras-tiendas",
                      "tiendas", "nosotros", "quienes", "about", "donde", "ubicacion",
                      "store-locator", "encontranos", "como-llegar")
RUTAS_FIJAS = ("/contacto", "/sucursales")

# ---------------------------------------------------------------------------
# Regex de evidencia
# ---------------------------------------------------------------------------
RE_COORDS = [
    (re.compile(r"!3d(-\d{1,2}\.\d{3,})!4d(-\d{1,2}\.\d{3,})"), "latlon"),
    (re.compile(r"!2d(-\d{1,2}\.\d{3,})!3d(-\d{1,2}\.\d{3,})"), "lonlat"),
    (re.compile(r"maps[^\"'\s]{0,200}?@(-\d{1,2}\.\d{3,}),(-\d{1,2}\.\d{3,})"), "latlon"),
    (re.compile(r"maps[^\"'\s]{0,200}?[?&;](?:q|ll|center|daddr|query)=(-\d{1,2}\.\d{3,})(?:,|%2C)\s*(-\d{1,2}\.\d{3,})"), "latlon"),
    (re.compile(r"\"latitude\"\s*:\s*\"?(-\d{1,2}\.\d{3,})\"?\s*,\s*\"longitude\"\s*:\s*\"?(-\d{1,2}\.\d{3,})"), "latlon"),
]
RE_CPA = re.compile(r"\b([A-HJ-NP-Z])(\d{4})([A-Z]{3})\b")
RE_CP_NUM = re.compile(r"(?:\bc\.?\s?p\.?|codigo postal|cod\.? postal)\s*:?\s*\(?([a-z]?)(\d{4})\b", re.I)
RE_TEL_HREF = re.compile(r"(?:tel:|wa\.me/|whatsapp\.com/send/?\?phone=|phone=)\+?([\d\s\-\(\)\.%20]{8,22})", re.I)
RE_TEL_TXT = re.compile(r"(?:tel[eé]?f?o?n?o?s?|whats?app|wsp|cel(?:ular)?|llamanos|ll[aá]manos)\.?\s*:?\s*"
                        r"(\+?[\d][\d\s\-\(\)\.]{8,20}\d)", re.I)
RE_JSONLD = re.compile(r"<script[^>]+application/ld\+json[^>]*>(.*?)</script>", re.I | re.S)
RE_TAGS = re.compile(r"<(script|style|noscript|svg)[^>]*>.*?</\1>", re.I | re.S)
RE_HREF = re.compile(r"href=[\"']([^\"'#]+)[\"']", re.I)
RE_ZONA = re.compile(r"<(?:footer|address)[^>]*>"
                     r"|<(?:div|section)[^>]*(?:class|id)=[\"'][^\"']*(?:footer|contact|direcci|address)[^\"']*[\"'][^>]*>",
                     re.I)
VENTANA_ZONA = 6000


def _armar_re_localidades():
    """Una regex por provincia: 'numero ... , Localidad' (localidad no seguida de numero,
    para no confundir 'Av. Corrientes 1234' con la ciudad de Corrientes)."""
    out = {}
    for letra, locs in LOCALIDADES.items():
        alt = "|".join(re.escape(l) for l in sorted(locs, key=len, reverse=True))
        out[letra] = re.compile(
            r"\b\d{1,5}\b[^\n<>|]{0,45}?[,\-–|]\s*(?:" + r"(?:ciudad de |provincia de |pcia\.? de )?"
            r")(" + alt + r")\b(?![\s\.]*\d)", re.I)
    return out


RE_LOC = _armar_re_localidades()
RE_LOC_ARG = {letra: re.compile(r"\b(" + "|".join(re.escape(l) for l in locs) + r")\s*[,\-]\s*(?:argentina|rep[uú]blica argentina)\b", re.I)
              for letra, locs in LOCALIDADES.items() if letra != "EXT"}
RE_TITULO = re.compile(r"<title[^>]*>(.*?)</title>|<meta[^>]+name=[\"']description[\"'][^>]+content=[\"']([^\"']*)", re.I | re.S)
RE_SPAM = re.compile(r"(slot|gacor|togel|judi|casino online|sabung|bet88|apuestas online|viagra)", re.I)
# tel: necesita + o 00 (tel:1157688894 es CABA sin el 54, no EE.UU.). En wa.me/phone= el numero
# va siempre con codigo de pais; ningun codigo de area AR empieza con 5, asi que 5x no se confunde.
RE_EXT_TEL = re.compile(r"tel:(?:\+|%2B|00)\s?(34|52|56|57|51|598|595|55|1)\d{7,}"
                        r"|(?:wa\.me/|phone=)(34|52|56|57|51|598|595|55)\d{7,}", re.I)


def dominio(u):
    try:
        return str(u).split("//")[-1].split("/")[0].lower().replace("www.", "").split(":")[0]
    except Exception:
        return str(u).lower()


def etiqueta_dominio(d):
    """'www.gomeriacentral.com.ar' -> 'gomeriacentral'."""
    partes = [p for p in d.split(".") if p not in ("www", "com", "ar", "net", "org", "shop", "store",
                                                     "tienda", "online", "mitiendanube", "myshopify")]
    return max(partes, key=len) if partes else d


GENERICOS = set("""
tienda tiendas online shop store oficial inicio home productos producto ofertas envios envio
todo pais argentina comprar venta ventas mayorista minorista distribuidora distribuidor
supermercado supermercados almacen autoservicio farmacia farmacias perfumeria cosmetica
libreria librerias papeleria jugueteria ferreteria corralon pintureria pinturerias construccion
electro electrodomesticos electronica tecnologia computacion celulares telefonia indumentaria
ropa calzado calzados zapateria deportes deportiva muebles muebleria mueblerias hogar bazar deco
decoracion blanqueria colchones iluminacion optica opticas joyeria relojeria regaleria regalos
carniceria polleria pescaderia panaderia confiteria verduleria fruteria dietetica bebidas vinoteca
vinos cerveceria cervezas mascotas petshop veterinaria autopartes repuestos neumaticos gomeria
motos bicicleteria bicicletas vivero cotillon lenceria sanitarios herramientas articulos escolares
centro casa mundo club el la los las de del y
""".split())


def es_generico(seg):
    palabras = re.sub(r"[^a-z0-9 ]", " ", norm(seg)).split()
    return not palabras or all(p in GENERICOS for p in palabras)


def compacto(s):
    return re.sub(r"[^a-z0-9]", "", norm(s))


# ---------------------------------------------------------------------------
# Indice OSM
# ---------------------------------------------------------------------------
class IndiceOSM:
    """Indice sobre empresas_argentina.csv: dominio -> provincias, nombre -> provincias."""

    def __init__(self, path=os.path.join(AQUI, "empresas_argentina.csv")):
        df = pd.read_csv(path, usecols=["Nombre", "Sector", "Pagina web", "Latitud", "Longitud"])
        df = df.dropna(subset=["Latitud", "Longitud"])
        # provincia por point-in-polygon (no confiamos en la columna de texto)
        df["letra"] = [provincia_de_punto(la, lo) for la, lo in zip(df["Latitud"], df["Longitud"])]
        df = df.dropna(subset=["letra"])
        self.por_dominio = defaultdict(lambda: defaultdict(int))
        for web, letra in zip(df["Pagina web"], df["letra"]):
            if isinstance(web, str) and web.strip():
                self.por_dominio[dominio(web if "//" in web else "//" + web)][letra] += 1
        self.por_nombre = defaultdict(lambda: defaultdict(int))
        self.nombres_norm = []
        for nom, letra in zip(df["Nombre"], df["letra"]):
            n = " ".join(re.sub(r"[^a-z0-9 ]", " ", norm(nom)).split())
            if n:
                self.por_nombre[n.replace(" ", "")][letra] += 1
                self.nombres_norm.append((n, letra))

    def por_marca(self, marca):
        """Sucursales de una cadena por provincia: nombre OSM == marca, o empieza con
        'marca ', o es '<algo> marca' (ej 'Supermercado Dia', 'Farmacity Palermo')."""
        m = " ".join(re.sub(r"[^a-z0-9 ]", " ", norm(marca)).split())
        if not m:
            return {}
        corta = len(m.replace(" ", "")) <= 4
        cuenta = defaultdict(int)
        for n, letra in self.nombres_norm:
            if n == m or n.startswith(m + " ") or (not corta and (n.endswith(" " + m) or f" {m} " in n)):
                cuenta[letra] += 1
            elif corta and n in (f"supermercado {m}", f"supermercados {m}", f"farmacia {m}"):
                cuenta[letra] += 1
        return dict(cuenta)


_OSM = None


def indice_osm():
    global _OSM
    if _OSM is None:
        t = time.time()
        _OSM = IndiceOSM()
        print(f"  indice OSM listo ({time.time() - t:.0f}s)", flush=True)
    return _OSM


# SEPA (precios oficiales): sucursales declaradas por las propias cadenas.
# Se toma el sepa_*.zip mas nuevo de la raiz del repo (o la ruta en SEPA_ZIP).
_SEPA = None
_SEPA_LOCK = threading.Lock()


def indice_sepa():
    """etiqueta de dominio de la bandera -> {letra provincia: sucursales}."""
    global _SEPA
    with _SEPA_LOCK:  # lo piden todos los hilos a la vez: se arma una sola vez
        if _SEPA is None:
            import sepa
            path = sepa.zip_mas_nuevo()
            _SEPA = sepa.cobertura(path) if path else {}
            if path:
                print(f"  indice SEPA listo ({os.path.basename(path)}, {len(_SEPA)} dominios)", flush=True)
    return _SEPA


# ---------------------------------------------------------------------------
# Descarga
# ---------------------------------------------------------------------------
def _get(session, url):
    try:
        r = session.get(url, headers=HDRS, timeout=(8, 15), allow_redirects=True, stream=True,
                        verify=False)
        ctype = r.headers.get("content-type", "")
        if "html" not in ctype and "json" not in ctype and ctype:
            r.close()
            return r.status_code, r.url, ""
        cuerpo = r.raw.read(MAX_BYTES, decode_content=True)
        r.close()
        enc = r.encoding if r.encoding and r.encoding.lower() != "iso-8859-1" else "utf-8"
        return r.status_code, r.url, cuerpo.decode(enc, errors="replace")
    except Exception:
        return None, url, ""


def descargar_sitio(url):
    """Home (+ URL original si es distinta) + hasta MAX_SUBPAGINAS de contacto/sucursales.
    Devuelve (status_home, url_final, [(html, es_pagina_de_contacto)])."""
    s = requests.Session()
    url = url if str(url).startswith("http") else "https://" + str(url)
    base = re.match(r"(https?://[^/]+)", url).group(1)
    status, final, home = None, url, ""
    for cand in (base + "/", base.replace("://", "://www.") + "/" if "://www." not in base else base.replace("://www.", "://") + "/",
                 base.replace("https://", "http://") + "/"):
        status, final, home = _get(s, cand)
        if status is not None:
            break
    if status is None:
        return None, url, []
    htmls = [(home, False)]
    base_final = re.match(r"(https?://[^/]+)", final).group(1) if final else base
    vistos = {final.rstrip("/"), base_final}
    if url.rstrip("/") not in vistos and dominio(url) == dominio(final):
        _, _, h = _get(s, url)
        htmls.append((h, False))
        vistos.add(url.rstrip("/"))
    # subpaginas enlazadas desde el home
    subs = []
    for href in RE_HREF.findall(home):
        h = _html.unescape(href)
        low = h.lower()
        if not any(p in low for p in PALABRAS_SUBPAGINA):
            continue
        if h.startswith("/"):
            h = base_final + h
        elif not h.startswith("http") or dominio(h) != dominio(base_final):
            continue
        h = h.split("?")[0].rstrip("/")
        if h not in vistos and not re.search(r"\.(jpg|png|pdf|css|js)$", h, re.I):
            vistos.add(h)
            subs.append(h)
    for ruta in RUTAS_FIJAS:
        if len(subs) >= MAX_SUBPAGINAS:
            break
        if base_final + ruta not in vistos:
            subs.append(base_final + ruta)
    for sub in subs[:MAX_SUBPAGINAS]:
        st, _, h = _get(s, sub)
        if st == 200 and h:
            htmls.append((h, True))
    s.close()
    return status, final, htmls


# ---------------------------------------------------------------------------
# Extraccion de evidencia de un HTML
# ---------------------------------------------------------------------------
def _texto(html):
    t = RE_TAGS.sub(" ", html)
    t = re.sub(r"<br\s*/?>|</(p|div|li|span|td|h\d)>", "\n", t, flags=re.I)
    t = re.sub(r"<[^>]+>", " ", t)
    t = _html.unescape(t)
    return re.sub(r"[ \t\r\f\v]+", " ", t)


def _jsonld_direcciones(html):
    out = []
    for bloque in RE_JSONLD.findall(html):
        try:
            data = json.loads(bloque.strip())
        except Exception:
            continue
        pila = [data]
        while pila:
            x = pila.pop()
            if isinstance(x, list):
                pila.extend(x)
            elif isinstance(x, dict):
                if str(x.get("@type", "")).lower() == "postaladdress":
                    out.append(x)
                pila.extend(v for v in x.values() if isinstance(v, (dict, list)))
    return out


def _zona_direccion(html, completo):
    """Texto donde tiene sentido buscar direcciones/telefonos. En el home solo el
    footer/<address>/bloques de contacto (si no, el ultimo tramo del texto): asi
    'Malbec 750ml, Lujan de Cuyo, Mendoza' en una ficha de producto no cuenta."""
    if completo:
        return _texto(html)
    trozos = [html[m.start():m.start() + VENTANA_ZONA] for m in list(RE_ZONA.finditer(html))[:6]]
    if trozos:
        return _texto(" \n ".join(trozos))
    return _texto(html)[-4000:]


def evidencias_html(html, completo=False):
    """Lista de (tipo, letras, peso, detalle) encontradas en un HTML.
    completo=True para paginas de contacto/sucursales (se mira todo el texto)."""
    ev = []
    if not html:
        return ev
    # coordenadas
    for rx, orden in RE_COORDS:
        for a, b in rx.findall(html)[:5]:
            lat, lon = (float(a), float(b)) if orden == "latlon" else (float(b), float(a))
            if -56 < lat < -21 and -74 < lon < -53:
                letra = provincia_de_punto(lat, lon)
                if letra:
                    ev.append(("coordenadas", letra, FUERTE, f"{lat:.4f},{lon:.4f}"))
    # JSON-LD
    for adr in _jsonld_direcciones(html):
        campo = norm(" ".join(str(adr.get(k, "")) for k in ("addressLocality", "addressRegion", "postalCode")))
        pais = adr.get("addressCountry", "")
        if isinstance(pais, dict):  # {"@type": "Country", "name": "AR"}
            pais = pais.get("name", "")
        pais = norm(pais)
        if pais and pais not in ("ar", "arg", "argentina") and "argentina" not in pais:
            ev.append(("jsonld_pais", "EXT", FUERTE, pais[:20]))
            continue
        for letra, locs in LOCALIDADES.items():
            if any(re.search(r"\b" + re.escape(l) + r"\b", campo) for l in locs):
                ev.append(("jsonld_direccion", letra, FUERTE, campo[:60]))
        loc = adr.get("addressLocality")
        letra = geografia.localidad_exacta(loc) if isinstance(loc, str) else None
        if letra and not any(e[0] == "jsonld_direccion" and e[1] == letra for e in ev):
            ev.append(("jsonld_direccion", letra, FUERTE, campo[:60]))
    texto = _texto(html)
    zona = _zona_direccion(html, completo)
    # el propio comercio dice donde esta: "Libreria artistica en Belgrano"
    cab = norm(" ".join(a or b for a, b in RE_TITULO.findall(html[:200000])[:3]))
    for letra, locs in LOCALIDADES.items():
        for l in locs:
            m = re.search(r"(?<!envios )(?<!envio )(?<!entregas )(?:en|de) " + re.escape(l) + r"(?![\s\.]*\d)", cab)
            if m:
                ev.append(("titulo", letra, MEDIA, cab[max(0, m.start() - 25):m.end()][:60]))
                break
    # CPA (letra + 4 digitos + 3 letras): la letra es la provincia
    for letra, num, _ in RE_CPA.findall(texto)[:5]:
        ev.append(("cpa", letra, FUERTE, f"{letra}{num}"))
    for letra_cp, num in RE_CP_NUM.findall(texto)[:5]:
        if letra_cp and letra_cp.upper() in LETRA_A_NOMBRE:
            ev.append(("cp", letra_cp.upper(), FUERTE, f"{letra_cp.upper()}{num}"))
        else:
            letra = provincia_de_cp(num)
            if letra:
                ev.append(("cp", letra, MEDIA, num))
    # direcciones "Calle 123, Localidad"
    t_norm = norm(zona)
    for letra, rx in RE_LOC.items():
        m = rx.search(t_norm)
        if m:
            ev.append(("direccion", letra, MEDIA if letra != "EXT" else FUERTE,
                       t_norm[max(0, m.start()):m.end()].strip()[:70]))
        elif letra in RE_LOC_ARG:
            m = RE_LOC_ARG[letra].search(t_norm)
            if m:
                ev.append(("localidad_argentina", letra, MEDIA, m.group(0)[:50]))
    # localidades oficiales (Georef) que existen en una sola provincia: 'Calle 123, Rafaela'
    ya = {e[1] for e in ev if e[0] in ("direccion", "localidad_argentina")}
    for letra, _, frag in geografia.localidades_de_texto(t_norm):
        if letra not in ya:
            ya.add(letra)
            ev.append(("direccion", letra, MEDIA, frag.strip()[:70]))
    # telefonos
    tels = set(RE_TEL_HREF.findall(html)[:10]) | set(RE_TEL_TXT.findall(zona)[:10])
    for tel in tels:
        letras = provincias_de_telefono(tel.replace("%20", ""))
        if letras:
            peso = MEDIA if len(letras) == 1 else DEBIL
            ev.append(("telefono", letras, peso, re.sub(r"\D", "", tel)[:14]))
    if RE_EXT_TEL.search(html):
        ev.append(("telefono_exterior", "EXT", MEDIA, RE_EXT_TEL.search(html).group(0)[:25]))
    return ev


# ---------------------------------------------------------------------------
# Decision
# ---------------------------------------------------------------------------
def puntajes(evidencias):
    """Suma por letra, contando cada tipo de evidencia una sola vez por letra."""
    mejor = defaultdict(dict)
    for tipo, letras, peso, _ in evidencias:
        for letra in (letras if letras != "EXT" else ["EXT"]):
            mejor[letra][tipo] = max(mejor[letra].get(tipo, 0), peso)
    return {letra: sum(t.values()) for letra, t in mejor.items()}


def decidir(objetivo, evidencias, respondio, es_cadena=False):
    p = puntajes(evidencias)
    obj = p.get(objetivo, 0)
    otras = {k: v for k, v in p.items() if k != objetivo and v >= MEDIA}
    if not es_cadena:
        # el sitio lista direcciones de medio pais -> directorio/agregador, no un comercio
        prov_sitio = {l for t, ls, _, _ in evidencias if not t.startswith("osm") for l in ls if l != "EXT"}
        if len(prov_sitio) >= PROVINCIAS_AGREGADOR:
            return "AGREGADOR_O_DIRECTORIO", obj
        # un comercio local con mas evidencia de otra provincia que de esta: esta alla
        if obj >= MEDIA and otras and max(otras.values()) > obj:
            top = max(otras, key=otras.get)
            return f"OTRA_UBICACION ({LETRA_A_NOMBRE.get(top, top)})", obj
    if obj >= MEDIA:
        return "VERIFICADA", obj
    if otras:
        top = max(otras, key=otras.get)
        return f"OTRA_UBICACION ({LETRA_A_NOMBRE.get(top, top)})", obj
    if obj > 0:
        return "DEBIL", obj
    indicios = {k: v for k, v in p.items() if k != objetivo}
    if indicios:
        top = max(indicios, key=indicios.get)
        nombre = "AMBA" if set(indicios) == {"C", "B"} else LETRA_A_NOMBRE.get(top, top)
        return f"OTRA_UBICACION ({nombre}, indicio)", obj
    return ("SIN_EVIDENCIA" if respondio else "NO_RESPONDE"), obj


LUGARES_COMPACTOS = {compacto(l) for locs in LOCALIDADES.values() for l in locs}
# localidad que se pone en la busqueda de sucursales de cada provincia
BUSQUEDA_LOCALIDAD = {"C": "CABA", "B": "Buenos Aires", "W": "Corrientes", "M": "Mendoza"}

# sitios que listan sucursales por ciudad en la URL (solo se usan para cadenas)
LOCALIZADORES = ("tiendeo.com.ar", "sucursales24.com.ar", "firmania.com.ar", "sucursales.net")

_BUSQ_LOCK = threading.Lock()
_BUSQ_PAUSA = 2.0
_busq_ultima = [0.0]


LOCALIZADOR_URL = "https://www.sucursales24.com.ar/{ciudad}/{marca}/"
LOCALIZADOR_MAX_CIUDADES = 6


def evidencia_localizador(empresa, objetivo):
    """sucursales24 publica un JSON-LD Place (direccion + coordenadas) por cada sucursal
    real de la marca en la ciudad; si la marca no tiene local, la pagina viene vacia o 404.
    Cuenta solo sucursales cuyas coordenadas caen dentro de la provincia."""
    marca = re.sub(r"[^a-z0-9]+", "-", norm(empresa)).strip("-")
    if len(marca) < 3:
        return []
    ciudades = [l for l in LOCALIDADES.get(objetivo, []) if "." not in l][:LOCALIZADOR_MAX_CIUDADES]
    s = requests.Session()
    for ciudad in ciudades:
        url = LOCALIZADOR_URL.format(ciudad=ciudad.replace(" ", "-"), marca=marca)
        st, _, h = _get(s, url)
        if st != 200:
            continue
        dentro = []
        for bloque in RE_JSONLD.findall(h):
            try:
                data = json.loads(bloque.strip())
            except Exception:
                continue
            for x in (data if isinstance(data, list) else [data]):
                if not isinstance(x, dict):
                    continue
                geo = x.get("geo") or {}
                try:
                    lat, lon = float(geo.get("latitude")), float(geo.get("longitude"))
                except (TypeError, ValueError):
                    continue
                if provincia_de_punto(lat, lon) == objetivo:
                    dentro.append((x.get("address") or {}).get("streetAddress", ""))
        if dentro:
            s.close()
            return [("localizador_sucursales", objetivo, MEDIA, f"{url} -> {', '.join(dentro[:3])}")]
    s.close()
    return []


def evidencia_busqueda(empresa, dom, objetivo):
    """Busca '<cadena> sucursal <provincia>' y acepta solo resultados del dominio de
    la propia cadena cuyo titulo/texto nombre una localidad de la provincia."""
    try:
        from ddgs import DDGS
    except ImportError:
        return []
    lugar = BUSQUEDA_LOCALIDAD.get(objetivo, LETRA_A_NOMBRE.get(objetivo, ""))
    raiz = etiqueta_dominio(dom)
    for q in (f"{empresa} sucursal {lugar}", f"{empresa} {lugar} direccion local"):
        ev = _buscar_una(q, empresa, raiz, objetivo)
        if ev:
            return ev
    return []


def _buscar_una(q, empresa, raiz, objetivo):
    with _BUSQ_LOCK:  # ddgs corta con rafagas: una busqueda a la vez, con pausa
        espera = _BUSQ_PAUSA - (time.time() - _busq_ultima[0])
        if espera > 0:
            time.sleep(espera)
        try:
            with DDGS(timeout=15) as d:
                res = list(d.text(q, region="ar-es", max_results=10))
        except Exception:
            res = []
        _busq_ultima[0] = time.time()
    rx = re.compile(r"\b(" + "|".join(re.escape(l) for l in LOCALIDADES[objetivo]) + r")\b(?![\s\.]*\d)")
    slugs = {l.replace(" ", "-").replace(".", "") for l in LOCALIDADES[objetivo]}
    marca = compacto(empresa)
    for r in res:
        href = r.get("href", "")
        d = dominio(href)
        txt = norm(f"{r.get('title', '')} {r.get('body', '')}")
        if etiqueta_dominio(d) == raiz:
            m = rx.search(txt)
            if m:
                return [("busqueda_web", objetivo, MEDIA, f"{d}: {txt[max(0, m.start() - 40):m.end() + 20]}")]
        elif any(d.endswith(l) for l in LOCALIZADORES) and len(marca) >= 3:
            # ficha de UNA sucursal: /Tiendas/corrientes/fravega-junin/2375 (con id numerico).
            # Las paginas /Tiendas/corrientes/coto existen para cualquier marca (catalogos).
            segs = [norm(s) for s in href.split("//")[-1].split("?")[0].split("/")[1:]]
            if any(s in slugs for s in segs) and any(marca in compacto(s) for s in segs)                     and any(re.search(r"\d{3,}", s) for s in segs):
                return [("localizador_sucursales", objetivo, MEDIA, href[:90])]
    return []


def verificar_tienda(row, objetivo, es_cadena):
    t0 = time.time()
    url = str(row.get("URL", "")).strip()
    dom = dominio(url)
    ev = []
    osm = indice_osm()

    # 1) OSM por dominio
    # (facebook.com & cia figuran como "web" de miles de locales en OSM: no identifican a nadie)
    if not any(x in dom for x in NO_COMERCIO):
        for letra, n in osm.por_dominio.get(dom, {}).items():
            ev.append(("osm_dominio", letra, FUERTE, f"{n} local(es)"))
    # 1b) SEPA: sucursales oficiales de la cadena (mismo dominio)
    from sepa import clave_cobertura
    cob = indice_sepa()
    for letra, n in cob.get(clave_cobertura(dom, cob), {}).items():
        if letra in LETRA_A_NOMBRE:
            ev.append(("sepa_sucursales", letra, FUERTE, f"{n} sucursal(es)"))
    # 2) OSM por marca (cadenas) o por nombre == etiqueta del dominio
    if es_cadena:
        # una sola coincidencia aislada puede ser otro comercio con el mismo nombre
        for letra, n in osm.por_marca(row.get("Empresa", "")).items():
            ev.append(("osm_marca", letra, FUERTE if n >= 2 else DEBIL, f"{n} sucursal(es)"))
    else:
        # nombre OSM == etiqueta del dominio: media. == un segmento del titulo: debil.
        # Nunca nombres de lugar ('mendoza', 'tunuyan') ni genericos ('informatica').
        etq = etiqueta_dominio(dom)
        nombres = {etq: MEDIA}
        for seg in re.split(r"\s[-|–:·]\s|\|", str(row.get("Empresa", ""))):
            if not es_generico(seg):
                nombres.setdefault(compacto(seg), DEBIL)
        for nom, peso in nombres.items():
            if len(nom) >= 8 and nom not in LUGARES_COMPACTOS and not es_generico(nom):
                for letra, n in osm.por_nombre.get(nom, {}).items():
                    ev.append(("osm_nombre", letra, peso, f"{n} local(es) '{nom}'"))

    status, final = None, url
    if any(x in dom for x in NO_COMERCIO):
        motivo = "NO_ES_SITIO_PROPIO"
    else:
        status, final, htmls = descargar_sitio(url)
        motivo = None
        df_ = dominio(final)
        if status is not None and etiqueta_dominio(df_) != etiqueta_dominio(dom)                 and not re.search(r"\.(ar|com|net|org|shop|store|online|site|app|io)$", df_):
            motivo = "REDIRIGE_A_OTRO_DOMINIO"      # dominio vencido / vendido a un tercero
        elif htmls and RE_SPAM.search(" ".join(a or b for a, b in RE_TITULO.findall(htmls[0][0][:200000])[:2])):
            motivo = "SITIO_SPAM"
        else:
            for h, completo in htmls:
                ev.extend(evidencias_html(h, completo))

    # 3) cadenas sin evidencia suficiente (OSM incompleto): buscar en la web una pagina
    #    del PROPIO dominio de la cadena que nombre una localidad de la provincia
    if es_cadena and not motivo and puntajes(ev).get(objetivo, 0) < MEDIA:
        ev.extend(evidencia_localizador(row.get("Empresa", ""), objetivo)
                  or evidencia_busqueda(row.get("Empresa", ""), dom, objetivo))

    # con sucursales oficiales en SEPA es una cadena real, aunque venga como "Descubierto"
    es_cadena = es_cadena or any(t == "sepa_sucursales" for t, *_ in ev)
    decision, puntaje = decidir(objetivo, ev, status is not None, es_cadena)
    if motivo:
        decision = motivo if decision != "VERIFICADA" else decision
    # dedup para el reporte
    vistos, ev_txt = set(), []
    for tipo, letras, peso, det in ev:
        k = (tipo, letras, det)
        if k not in vistos:
            vistos.add(k)
            ev_txt.append(f"{tipo}:{letras}({peso}) {det}")
    return {
        "Verificacion": decision,
        "Puntaje": puntaje,
        "Evidencia": " | ".join(ev_txt)[:1500],
        "HTTP": status if status is not None else "",
        "URL final": final,
        "seg_verif": round(time.time() - t0, 1),
    }


def verificar_df(df, folder, workers=32, progreso=True):
    """Agrega columnas de verificacion a df (una fila por comercio)."""
    objetivo = FOLDER_A_LETRA[folder]
    indice_osm()
    # cadenas y comercios curados a mano traen un nombre limpio -> se buscan por marca en OSM
    origen = df["Origen"].astype(str) if "Origen" in df.columns else pd.Series([""] * len(df), index=df.index)
    es_cadena = ~origen.str.strip().str.lower().isin(["descubierto", "", "nan"])
    filas = list(df.to_dict("records"))
    resultados = [None] * len(filas)
    t0 = time.time()
    with cf.ThreadPoolExecutor(max_workers=workers) as ex:
        futs = {ex.submit(verificar_tienda, f, objetivo, bool(c)): i
                for i, (f, c) in enumerate(zip(filas, es_cadena))}
        for k, fut in enumerate(cf.as_completed(futs), 1):
            i = futs[fut]
            try:
                resultados[i] = fut.result()
            except Exception as e:
                resultados[i] = {"Verificacion": f"ERROR {type(e).__name__}", "Puntaje": 0,
                                 "Evidencia": str(e)[:200], "HTTP": "", "URL final": "", "seg_verif": 0}
            if progreso and (k % 50 == 0 or k == len(filas)):
                print(f"    verificadas {k}/{len(filas)} ({time.time() - t0:.0f}s)", flush=True)
    # un corte de red momentaneo no puede sacar a un comercio: segunda vuelta, mas despacio
    reintentar = [i for i, r in enumerate(resultados) if r["Verificacion"] in ("NO_RESPONDE", "SIN_EVIDENCIA")
                  or str(r["Verificacion"]).startswith("ERROR")]
    if reintentar:
        with cf.ThreadPoolExecutor(max_workers=max(1, workers // 4)) as ex:
            segunda = list(ex.map(lambda i: verificar_tienda(filas[i], objetivo, bool(es_cadena.iloc[i])), reintentar))
        rescatadas = 0
        for i, r in zip(reintentar, segunda):
            if r["Verificacion"] not in ("NO_RESPONDE", "SIN_EVIDENCIA"):
                rescatadas += r["Verificacion"] == "VERIFICADA"
                resultados[i] = r
        if progreso:
            print(f"    reintento de {len(reintentar)} sin respuesta/evidencia: {rescatadas} verificadas", flush=True)
    res = pd.DataFrame(resultados, index=df.index)
    return pd.concat([df, res], axis=1)


if __name__ == "__main__":
    import sys
    # prueba rapida: py verificar_ubicacion.py <Folder> <url> [cadena]
    folder, url = sys.argv[1], sys.argv[2]
    r = verificar_tienda({"URL": url, "Empresa": sys.argv[3] if len(sys.argv) > 3 else ""},
                         FOLDER_A_LETRA[folder], len(sys.argv) > 3)
    for k, v in r.items():
        print(f"{k}: {v}")
