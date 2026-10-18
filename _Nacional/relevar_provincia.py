# -*- coding: utf-8 -*-
"""
Relevamiento estilo corrientes_full PARA CADA PROVINCIA.
Para una provincia y sus ciudades principales: cadenas nacionales (curadas) +
descubrimiento por rubro/ciudad (ddgs) + verificacion de e-commerce.
Genera <region>/<provincia>/excels/<provincia>_full.xlsx (hoja 'Tiendas con web'
+ 'Candidatos (revisar)'). Acumulativo.

Uso: py relevar_provincia.py [Folder1 Folder2 ...]   (sin args = todas)
"""
import concurrent.futures as cf
import html as _html
import os
import re
import socket
import time
import unicodedata

import pandas as pd
from ddgs import DDGS

from verificar_cadenas import _try_get, _candidatos, clasificar_tienda, ANTIBOT

socket.setdefaulttimeout(20)

# folder: (display, region_folder, [ciudades principales])
PROVINCIAS = {
    "Jujuy": ("Jujuy", "NOA", ["San Salvador de Jujuy", "Palpala"]),
    "Salta": ("Salta", "NOA", ["Salta", "Oran", "Tartagal"]),
    "Tucuman": ("Tucuman", "NOA", ["San Miguel de Tucuman", "Yerba Buena"]),
    "Catamarca": ("Catamarca", "NOA", ["San Fernando del Valle de Catamarca"]),
    "La-Rioja": ("La Rioja", "NOA", ["La Rioja"]),
    "Santiago-del-Estero": ("Santiago del Estero", "NOA", ["Santiago del Estero", "La Banda"]),
    "Formosa": ("Formosa", "NEA", ["Formosa", "Clorinda"]),
    "Chaco": ("Chaco", "NEA", ["Resistencia", "Saenz Pena"]),
    "Misiones": ("Misiones", "NEA", ["Posadas", "Obera", "Eldorado"]),
    "Mendoza": ("Mendoza", "Cuyo", ["Mendoza", "San Rafael", "Godoy Cruz"]),
    "San-Juan": ("San Juan", "Cuyo", ["San Juan"]),
    "San-Luis": ("San Luis", "Cuyo", ["San Luis", "Villa Mercedes"]),
    "Buenos-Aires": ("Buenos Aires", "Centro-Pampeana", ["La Plata", "Mar del Plata", "Bahia Blanca", "San Isidro", "Quilmes", "Moron", "Lomas de Zamora", "Tigre", "Pilar", "Avellaneda", "Lanus", "San Justo La Matanza", "Vicente Lopez", "Olivos", "Tandil", "Berazategui", "Florencio Varela", "Almirante Brown Adrogue", "Tres de Febrero Caseros", "San Miguel BsAs", "Hurlingham", "Ituzaingo BsAs", "Escobar", "Campana", "Zarate", "San Fernando", "Banfield", "Lujan BsAs", "Junin BsAs", "Necochea", "Olavarria", "Pergamino", "Chivilcoy", "Azul BsAs", "San Pedro BsAs"]),
    "CABA": ("Ciudad de Buenos Aires", "Centro-Pampeana", ["Palermo CABA", "Belgrano CABA", "Recoleta", "Microcentro Buenos Aires", "Caballito", "Flores CABA", "Once Buenos Aires", "Villa Crespo", "Almagro", "Nunez CABA", "avenida Santa Fe Buenos Aires", "avenida Cabildo", "avenida Corrientes CABA", "avenida Rivadavia", "Villa Urquiza", "Villa Devoto", "Barrio Norte"]),
    "Cordoba": ("Cordoba", "Centro-Pampeana", ["Cordoba", "Rio Cuarto", "Villa Maria"]),
    "Santa-Fe": ("Santa Fe", "Centro-Pampeana", ["Rosario", "Santa Fe", "Rafaela"]),
    "Entre-Rios": ("Entre Rios", "Centro-Pampeana", ["Parana", "Concordia", "Gualeguaychu"]),
    "La-Pampa": ("La Pampa", "Centro-Pampeana", ["Santa Rosa", "General Pico"]),
    "Neuquen": ("Neuquen", "Patagonia", ["Neuquen", "San Martin de los Andes"]),
    "Rio-Negro": ("Rio Negro", "Patagonia", ["Bariloche", "General Roca", "Cipolletti"]),
    "Chubut": ("Chubut", "Patagonia", ["Comodoro Rivadavia", "Trelew", "Puerto Madryn"]),
    "Santa-Cruz": ("Santa Cruz", "Patagonia", ["Rio Gallegos", "Caleta Olivia", "El Calafate"]),
    "Tierra-del-Fuego": ("Tierra del Fuego", "Patagonia", ["Ushuaia", "Rio Grande"]),
}

# Ciudades/zonas extra para subir cobertura (se suman a las de PROVINCIAS).
ZONAS_EXTRA = {
    "CABA": ["Boedo", "San Telmo", "Colegiales", "Saavedra CABA", "Villa del Parque",
             "Liniers", "Mataderos", "Villa Lugano", "Parque Patricios", "Monserrat",
             "Balvanera", "Chacarita", "Villa Pueyrredon", "Floresta CABA", "Barracas CABA",
             "La Boca", "Retiro Buenos Aires", "Constitucion CABA", "Coghlan",
             "avenida Pueyrredon", "avenida Triunvirato", "avenida Avellaneda Flores",
             "avenida Warnes", "avenida Juan B Justo", "avenida Nazca", "avenida Cordoba CABA",
             "Puerto Madero", "San Nicolas CABA", "San Cristobal CABA", "Paternal",
             "Parque Chacabuco", "Villa Luro", "Villa Ortuzar", "Agronomia",
             "Nueva Pompeya", "Versalles CABA", "Villa Real", "Villa Soldati",
             "Velez Sarsfield CABA", "Villa Riachuelo", "Parque Avellaneda",
             "Parque Chas", "Abasto Buenos Aires", "Las Canitas",
             "shopping Alto Palermo", "shopping Abasto", "shopping Galerias Pacifico",
             "shopping Recoleta Mall", "shopping Patio Bullrich", "shopping Distrito Arcos",
             "shopping Alcorta", "shopping Dot Baires"],
    "Cordoba": ["Villa Carlos Paz", "Alta Gracia", "San Francisco Cordoba", "Nueva Cordoba", "Cerro de las Rosas", "Rio Tercero", "Jesus Maria"],
    "Santa-Fe": ["Venado Tuerto", "Reconquista", "Esperanza Santa Fe", "Pichincha Rosario", "Villa Gobernador Galvez", "Canada de Gomez"],
    "Mendoza": ["Guaymallen", "Las Heras Mendoza", "Maipu Mendoza", "San Martin Mendoza", "Lujan de Cuyo", "Tunuyan"],
    "Tucuman": ["Tafi Viejo", "Banda del Rio Sali", "Concepcion Tucuman", "Aguilares"],
    "Salta": ["Metan", "Cafayate", "Rosario de la Frontera", "General Guemes"],
    "Neuquen": ["Plottier", "Centenario Neuquen", "Cutral Co", "Zapala"],
    "Rio-Negro": ["Viedma", "Villa Regina", "Cinco Saltos", "Allen Rio Negro"],
    "Chubut": ["Rawson Chubut", "Esquel", "Gaiman", "Rada Tilly"],
    "Misiones": ["Puerto Iguazu", "Apostoles", "Leandro N Alem", "Garupa"],
    "Chaco": ["Barranqueras", "Villa Angela", "Charata", "Fontana"],
    "Entre-Rios": ["Concepcion del Uruguay", "Victoria Entre Rios", "Villaguay", "Colon Entre Rios"],
    "San-Juan": ["Rivadavia San Juan", "Rawson San Juan", "Chimbas", "Pocito"],
    "Santiago-del-Estero": ["Termas de Rio Hondo", "Frias", "Anatuya"],
    "Jujuy": ["San Pedro de Jujuy", "Libertador General San Martin", "Perico"],
    "Formosa": ["Pirane", "El Colorado"],
    "Catamarca": ["Valle Viejo", "Recreo Catamarca"],
    "La-Rioja": ["Chilecito", "Aimogasta"],
    "San-Luis": ["Merlo San Luis", "La Punta"],
    "La-Pampa": ["General Pico", "Toay", "Realico"],
    "Santa-Cruz": ["Caleta Olivia", "El Calafate", "Pico Truncado", "Puerto Deseado"],
    "Tierra-del-Fuego": ["Tolhuin"],
}

# Cadenas nacionales con e-commerce (presencia amplia). Se marcan; el usuario poda.
CURADO_NACIONAL = [
    ("Carrefour", "Supermercado", "https://www.carrefour.com.ar"),
    ("Dia", "Supermercado", "https://diaonline.supermercadosdia.com.ar"),
    ("ChangoMas", "Supermercado", "https://www.masonline.com.ar"),
    ("Coto", "Supermercado", "https://www.cotodigital.com.ar"),
    ("Makro", "Mayorista", "https://www.makro.com.ar"),
    ("Diarco", "Mayorista", "https://www.diarco.com.ar"),
    ("Farmacity", "Farmacia", "https://www.farmacity.com"),
    ("Farmaplus", "Farmacia", "https://www.farmaplus.com.ar"),
    ("Farmalife", "Farmacia", "https://www.farmalife.com.ar"),
    ("Fravega", "Electro", "https://www.fravega.com"),
    ("Musimundo", "Electro", "https://www.musimundo.com"),
    ("Cetrogar", "Electro", "https://www.cetrogar.com.ar"),
    ("Naldo", "Electro", "https://www.naldo.com.ar"),
    ("Megatone", "Electro", "https://www.megatone.net"),
    ("Ribeiro", "Electro", "https://www.ribeiro.com.ar"),
    ("Dexter", "Deportes", "https://www.dexter.com.ar"),
    ("Stock Center", "Deportes", "https://www.stockcenter.com.ar"),
    ("Open Sports", "Deportes", "https://www.opensports.com.ar"),
    ("Solo Deportes", "Deportes", "https://www.solodeportes.com.ar"),
    ("Juleriaque", "Perfumeria/Cosmetica", "https://www.juleriaque.com.ar"),
    ("Pigmento", "Perfumeria/Cosmetica", "https://www.pigmento.com.ar"),
    ("Easy", "Ferreteria/Construccion", "https://www.easy.com.ar"),
    ("Sodimac", "Ferreteria/Construccion", "https://www.sodimac.com.ar"),
    ("Cuspide", "Libreria/Jugueteria", "https://www.cuspide.com"),
    ("Yenny-El Ateneo", "Libreria/Jugueteria", "https://www.yenny-elateneo.com"),
    ("Puppis", "Mascotas", "https://www.puppis.com.ar"),
    # --- marcas de shoppings (indumentaria/accesorios) ---
    ("Le Utthe", "Indumentaria/Calzado/Deportes", "https://www.leutthe.com.ar"),
    ("Cher", "Indumentaria/Calzado/Deportes", "https://www.cher.com.ar"),
    ("Rapsodia", "Indumentaria/Calzado/Deportes", "https://www.rapsodia.com"),
    ("Las Pepas", "Indumentaria/Calzado/Deportes", "https://www.laspepas.com.ar"),
    ("Prune", "Indumentaria/Calzado/Deportes", "https://www.prune.com.ar"),
    ("47 Street", "Indumentaria/Calzado/Deportes", "https://www.47street.com"),
    ("Akiabara", "Indumentaria/Calzado/Deportes", "https://www.akiabara.com"),
    ("Vitamina", "Indumentaria/Calzado/Deportes", "https://www.vitamina.com.ar"),
    ("Markova", "Indumentaria/Calzado/Deportes", "https://www.markova.com.ar"),
    ("Wanama", "Indumentaria/Calzado/Deportes", "https://www.wanama.com"),
    ("Yagmour", "Indumentaria/Calzado/Deportes", "https://www.yagmour.com.ar"),
    ("Caro Cuore", "Indumentaria/Calzado/Deportes", "https://www.carocuore.com"),
    ("Mistral", "Indumentaria/Calzado/Deportes", "https://www.mistral.com.ar"),
    ("Tucci", "Indumentaria/Calzado/Deportes", "https://www.tucci.com.ar"),
    ("Etiqueta Negra", "Indumentaria/Calzado/Deportes", "https://www.etiquetanegra.com"),
    ("Kosiuko", "Indumentaria/Calzado/Deportes", "https://www.kosiuko.com"),
    ("Bensimon", "Indumentaria/Calzado/Deportes", "https://www.bensimon.com.ar"),
    ("Ona Saez", "Indumentaria/Calzado/Deportes", "https://www.onasaez.com"),
    ("Portsaid", "Indumentaria/Calzado/Deportes", "https://www.portsaid.com.ar"),
    ("Ayres", "Indumentaria/Calzado/Deportes", "https://www.ayres.com.ar"),
    ("Kevingston", "Indumentaria/Calzado/Deportes", "https://www.kevingston.com"),
    ("John L. Cook", "Indumentaria/Calzado/Deportes", "https://www.johnlcook.com"),
    ("Penguin", "Indumentaria/Calzado/Deportes", "https://www.originalpenguin.com.ar"),
    ("Sweet Victorian", "Indumentaria/Calzado/Deportes", "https://www.sweetvictorian.com.ar"),
    ("Pampero", "Indumentaria/Calzado/Deportes", "https://www.pampero.com.ar"),
    ("Topper", "Indumentaria/Calzado/Deportes", "https://www.topper.com.ar"),
    ("Levi's", "Indumentaria/Calzado/Deportes", "https://www.levi.com.ar"),
    ("Wrangler", "Indumentaria/Calzado/Deportes", "https://www.wrangler.com.ar"),
    ("Lee", "Indumentaria/Calzado/Deportes", "https://www.lee.com.ar"),
    ("Mimo & Co", "Indumentaria/Calzado/Deportes", "https://www.mimo.com.ar"),
    ("Cheeky", "Indumentaria/Calzado/Deportes", "https://www.cheeky.com.ar"),
    ("Grimoldi", "Indumentaria/Calzado/Deportes", "https://www.grimoldi.com"),
    ("Paruolo", "Indumentaria/Calzado/Deportes", "https://www.paruolo.com.ar"),
    ("Ricky Sarkany", "Indumentaria/Calzado/Deportes", "https://www.rickysarkany.com"),
    ("Adidas", "Indumentaria/Calzado/Deportes", "https://www.adidas.com.ar"),
    ("Nike", "Indumentaria/Calzado/Deportes", "https://www.nike.com.ar"),
    ("Puma", "Indumentaria/Calzado/Deportes", "https://ar.puma.com"),
    ("Reef", "Indumentaria/Calzado/Deportes", "https://www.reef.com.ar"),
    ("Quiksilver", "Indumentaria/Calzado/Deportes", "https://www.quiksilver.com.ar"),
    ("Billabong", "Indumentaria/Calzado/Deportes", "https://www.billabong.com.ar"),
    ("Rip Curl", "Indumentaria/Calzado/Deportes", "https://www.ripcurl.com.ar"),
    ("Lacoste", "Indumentaria/Calzado/Deportes", "https://www.lacoste.com.ar"),
    ("Tommy Hilfiger", "Indumentaria/Calzado/Deportes", "https://www.tommyhilfiger.com.ar"),
    ("Hush Puppies", "Indumentaria/Calzado/Deportes", "https://www.hushpuppies.com.ar"),
    ("Tascani", "Indumentaria/Calzado/Deportes", "https://www.tascani.com"),
    ("Desiderata", "Indumentaria/Calzado/Deportes", "https://www.desiderata.com.ar"),
    ("Maria Cher", "Indumentaria/Calzado/Deportes", "https://www.mariacher.com"),
    ("Rochas", "Indumentaria/Calzado/Deportes", "https://www.rochasoficial.com.ar"),
    ("Activity", "Indumentaria/Calzado/Deportes", "https://www.activity.com.ar"),
    ("Como Quieres", "Indumentaria/Calzado/Deportes", "https://www.comoquieres.com.ar"),
    ("Sweet Lady", "Indumentaria/Calzado/Deportes", "https://www.sweetlady.com.ar"),
    ("Sweater", "Indumentaria/Calzado/Deportes", "https://www.sweater.com.ar"),
    ("La Martina", "Indumentaria/Calzado/Deportes", "https://www.lamartina.com.ar"),
    ("Legacy", "Indumentaria/Calzado/Deportes", "https://www.legacy.com.ar"),
    ("Bowen", "Indumentaria/Calzado/Deportes", "https://www.bowenmarket.com"),
    ("Mancini", "Indumentaria/Calzado/Deportes", "https://www.mancinishop.com.ar"),
    ("Uma", "Indumentaria/Calzado/Deportes", "https://www.uma.com.ar"),
    ("Jazmin Chebar", "Indumentaria/Calzado/Deportes", "https://www.jazminchebar.com.ar"),
    ("Salsipuedes", "Indumentaria/Calzado/Deportes", "https://www.salsipuedes.com.ar"),
    ("Penguin Kids", "Indumentaria/Calzado/Deportes", "https://www.penguinkids.com.ar"),
    ("Mami Boutique", "Indumentaria/Calzado/Deportes", "https://www.mamiboutique.com.ar"),
    ("Sarkany", "Indumentaria/Calzado/Deportes", "https://www.sarkanybrand.com"),
    ("Lupe", "Indumentaria/Calzado/Deportes", "https://www.lupe.com.ar"),
    ("47 Street Kids", "Indumentaria/Calzado/Deportes", "https://www.47street.com/kids"),
    ("Felix", "Indumentaria/Calzado/Deportes", "https://www.felix.com.ar"),
    ("Brooksfield", "Indumentaria/Calzado/Deportes", "https://www.brooksfield.com.ar"),
    ("Christian Lacroix", "Indumentaria/Calzado/Deportes", "https://www.christianlacroix.com.ar"),
    ("Tex Brand", "Indumentaria/Calzado/Deportes", "https://www.tex-online.com.ar"),
    ("Square", "Indumentaria/Calzado/Deportes", "https://www.square.com.ar"),
]

RUBROS = {
    "Supermercado": "supermercado online {c} comprar envios",
    "Farmacia": "farmacia online {c} comprar",
    "Carniceria": "carniceria pollo online {c} comprar",
    "Panaderia": "panaderia confiteria online {c} comprar",
    "Bebidas/Vinoteca": "vinoteca distribuidora bebidas online {c} comprar",
    "Electro/Electrodomesticos": "electrodomesticos electronica {c} tienda online",
    "Ferreteria/Construccion": "ferreteria corralon pintureria {c} tienda online",
    "Indumentaria/Calzado/Deportes": "ropa indumentaria calzado {c} tienda online comprar",
    "Perfumeria/Cosmetica": "perfumeria cosmetica maquillaje {c} tienda online",
    "Muebles/Hogar/Bazar": "muebleria bazar hogar {c} tienda online comprar",
    "Libreria/Jugueteria": "libreria jugueteria {c} tienda online comprar",
    "Mascotas/Veterinaria": "petshop veterinaria {c} tienda online comprar",
    "Optica/Salud": "optica {c} tienda online comprar anteojos",
    "Joyeria/Regalos": "joyeria regaleria {c} tienda online comprar",
    "Autos/Motos/Repuestos": "repuestos autopartes motos {c} tienda online comprar",
    "Mayorista/Distribuidora": "distribuidora mayorista {c} online comprar",
    # --- sub-rubros extra para MAXIMIZAR cobertura ---
    "Verduleria/Fruteria": "verduleria fruteria frutas verduras online {c} comprar envio",
    "Pescaderia": "pescaderia mariscos online {c} comprar",
    "Dietetica": "dietetica suplementos productos naturales online {c} comprar",
    "Celulares/Telefonia": "celulares telefonia accesorios online {c} comprar tienda",
    "Computacion": "computacion notebooks pc gaming online {c} comprar tienda",
    "Herramientas": "herramientas electricas maquinas online {c} comprar tienda",
    "Pinturas": "pintureria pinturas online {c} comprar tienda",
    "Sanitarios/Griferia": "sanitarios griferia bachas cocinas online {c} comprar",
    "Ropa deportiva": "indumentaria deportiva ropa deportiva online {c} comprar",
    "Ropa bebe/ninos": "ropa bebe ninos indumentaria infantil online {c} comprar",
    "Lenceria": "lenceria ropa interior online {c} comprar tienda",
    "Colchones/Sommier": "colchones sommier online {c} comprar tienda",
    "Bazar/Deco": "bazar deco regaleria hogar online {c} comprar tienda",
    "Iluminacion": "iluminacion lamparas online {c} comprar tienda",
    "Blanqueria": "blanqueria sabanas toallas acolchados online {c} comprar",
    "Cervezas": "cerveceria cervezas artesanales growler online {c} comprar",
    "Bicicleterias": "bicicleteria bicicletas rodados online {c} comprar tienda",
    "Neumaticos": "neumaticos cubiertas gomeria online {c} comprar tienda",
    "Vivero/Plantas": "vivero plantas jardineria online {c} comprar tienda",
    "Cotillon": "cotillon articulos fiesta globos online {c} comprar tienda",
    "Articulos escolares": "articulos escolares papeleria comercial online {c} comprar",
    "Relojeria": "relojeria relojes bijou accesorios online {c} comprar tienda",
    "General": "tienda online {c} envios comprar mitiendanube",
    "General2": "comprar online {c} envios a todo el pais tienda",
}

EXCLUIR = ("facebook", "instagram", "linkedin", "tiktok", "youtube", "twitter",
           "mercadolibre", "tiendeo", "rappi", "pedidosya", "paginasamarillas",
           "guiaclarin", "cuitonline", "licuo", "infoisinfo", "kompass", "yelp",
           "argentino.com", "promosdelbanco", "wikipedia", "aloo.com", "jooble",
           "catalogosofertas", "ilacad", "gov.ar", "gob.ar", "google.", "wa.me",
           "mapcarta", "moovit", "doctuo", "computrabajo", "indeed", "olx",
           "clasificados", "blogspot", "wordpress.com", "tiendanube.com/blog",
           "redargentina", "demos", "nuevaeranet", "sucursales24", "cybo")
FOREIGN_TLD = (".es", ".pl", ".mx", ".cl", ".co", ".pe", ".uy", ".br", ".it",
               ".fr", ".de", ".us", ".pt", ".ec", ".ve", ".bo", ".py", ".gt",
               ".hn", ".sv", ".pa", ".do", ".cr", ".com.gt", ".com.hn", ".com.co")
PATH_MALO = ("/es-es", "/es-mx", "/mx/", "/tag/", "/blog")
TITULO_MALO = ("aumentan", "explica", "seo ", "(caso", "donde comprar", "mejores ",
               "tiendas de", "ranking", "listado de", "guia de", "guía de",
               "linktree", "just a moment", "access denied", "page not found",
               "database error", "404", "como crear", "qué es")


def norm(s):
    s = unicodedata.normalize("NFKD", str(s))
    return "".join(c for c in s if not unicodedata.combining(c)).lower()


def dominio(u):
    try:
        return u.split("//")[-1].split("/")[0].lower().replace("www.", "")
    except Exception:
        return u


def es_extranjero(d):
    return any(d.endswith(t) for t in FOREIGN_TLD)


def descubrir(ciudades):
    cands = {}
    with DDGS(timeout=20) as d:
        for rubro, plantilla in RUBROS.items():
            for c in ciudades:
                q = plantilla.format(c=c)
                try:
                    res = list(d.text(q, region="ar-es", max_results=25))
                except Exception:
                    time.sleep(8)
                    continue
                for r in res:
                    u = r.get("href") or ""
                    dom = dominio(u)
                    tit = (r.get("title") or "")
                    if not u or any(x in dom for x in EXCLUIR) or es_extranjero(dom):
                        continue
                    if any(k in tit.lower() for k in TITULO_MALO):
                        continue
                    if any(p in u.lower() for p in PATH_MALO):
                        continue
                    cands.setdefault(dom, (u, rubro, tit))
                time.sleep(2.5)
    return cands


def hacer_verificar(terminos):
    """terminos: lista de strings (provincia + ciudades, normalizados) para 'menciona'."""
    def verificar(args):
        nombre, sector, url, origen = args
        status = None
        for cand in _candidatos(url):
            status, final, htmlc = _try_get(cand)
            if status is not None:
                break
        res = {"Empresa": nombre, "Sector": sector, "URL": url, "Origen": origen,
               "Estado": "", "Tienda online": "", "Plataforma": "", "Menciona": ""}
        if status is None:
            res["Estado"] = "No responde"; res["Tienda online"] = "No"
            return res
        res["Estado"] = "OK 200" if status == 200 else (
            f"Activo (anti-bot {status})" if status in ANTIBOT else f"HTTP {status}")
        res["URL"] = final or url
        res["Tienda online"], res["Plataforma"] = clasificar_tienda(status, htmlc)
        low = norm(htmlc or "")
        res["Menciona"] = "Si" if any(t in low for t in terminos) else ""
        if nombre == "?":
            m = re.search(r"<title[^>]*>(.*?)</title>", htmlc or "", re.I | re.S)
            if m:
                res["Empresa"] = _html.unescape(re.sub(r"\s+", " ", m.group(1)).strip())[:70]
        return res
    return verificar


def relevar(folder, display, region, ciudades):
    out_dir = os.path.join("..", region, folder, "excels")
    os.makedirs(out_dir, exist_ok=True)
    salida = os.path.join(out_dir, f"{folder}_full.xlsx")
    print(f"\n========== {display} ({region}) ciudades={ciudades} ==========", flush=True)
    cands = descubrir(ciudades)
    print(f"  candidatos descubiertos: {len(cands)}", flush=True)

    tareas = [(n, s, u, "Cadena nacional") for n, s, u in CURADO_NACIONAL]
    known = {dominio(u) for _, _, u in CURADO_NACIONAL}
    for dom, (u, rubro, tit) in cands.items():
        if dom not in known:
            tareas.append(("?", rubro, u, "Descubierto"))

    terminos = [norm(display)] + [norm(c) for c in ciudades]
    verificar = hacer_verificar(terminos)
    out = []
    with cf.ThreadPoolExecutor(max_workers=12) as ex:
        for r in ex.map(verificar, tareas):
            out.append(r)
    df = pd.DataFrame(out).drop_duplicates("URL")
    activo = df["Estado"].str.startswith(("OK", "Activo"))
    tienda = df["Tienda online"].isin(["Si", "Probable (anti-bot)"])
    plat = df["Plataforma"].astype(str).str.len() > 0
    menc = df["Menciona"] == "Si"
    curado = df["Origen"] != "Descubierto"
    cols = ["Empresa", "Sector", "URL", "Tienda online", "Plataforma", "Menciona", "Estado", "Origen"]
    # principal: curados + descubiertos con plataforma e-commerce (queries ya scopeadas por zona)
    principal = df[curado | (~curado & activo & tienda & plat)][cols]
    revisar = df[(~curado) & activo & ~(tienda & plat)][cols]
    # acumular con lo ya existente (re-runs con mas zonas SUMAN, no pisan)
    if os.path.exists(salida):
        try:
            xlp = pd.ExcelFile(salida)
            prev = pd.concat([xlp.parse(s) for s in xlp.sheet_names if "revisar" not in s.lower()],
                             ignore_index=True).reindex(columns=cols)
            principal = pd.concat([prev, principal], ignore_index=True)
        except Exception:
            pass
    principal["_d"] = principal["URL"].map(dominio)
    principal = principal.drop_duplicates("_d").drop(columns="_d").sort_values(["Sector", "Empresa"])
    revisar["_d"] = revisar["URL"].map(dominio)
    revisar = revisar[~revisar["_d"].isin(principal["URL"].map(dominio))].drop_duplicates("_d").drop(columns="_d").sort_values(["Sector", "Empresa"])
    try:
        with pd.ExcelWriter(salida, engine="openpyxl") as xl:
            principal.to_excel(xl, sheet_name="Tiendas con web", index=False)
            revisar.to_excel(xl, sheet_name="Candidatos (revisar)", index=False)
            for sh in xl.sheets.values():
                for c, w in zip("ABCDEFGH", (32, 24, 44, 16, 16, 12, 16, 18)):
                    sh.column_dimensions[c].width = w
                sh.freeze_panes = "A2"
        print(f"  -> {salida}: {len(principal)} tiendas (+{len(revisar)} a revisar)", flush=True)
    except Exception as e:
        print(f"  ERROR guardando {salida}: {e}", flush=True)


def main():
    import sys
    sel = sys.argv[1:]
    items = [(f, v[0], v[1], v[2] + ZONAS_EXTRA.get(f, []))
             for f, v in PROVINCIAS.items() if not sel or f in sel]
    print(f"Relevando {len(items)} provincias...", flush=True)
    for folder, display, region, ciudades in items:
        try:
            relevar(folder, display, region, ciudades)
        except Exception as e:
            print(f"  FALLO {folder}: {type(e).__name__}: {e}", flush=True)


if __name__ == "__main__":
    main()
