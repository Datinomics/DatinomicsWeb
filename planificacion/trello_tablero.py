# -*- coding: utf-8 -*-
"""
Crea en Trello el tablero de trabajo de Datinomics (primero la version web):
listas por etapa, etiquetas por area y tarjetas con descripcion y checklist.

Credenciales (https://trello.com/power-ups/admin -> API key -> token), en el entorno o en .env:
  TRELLO_KEY=...
  TRELLO_TOKEN=...

Uso:
  py planificacion/trello_tablero.py --simular     # muestra lo que crearia, sin tocar Trello
  py planificacion/trello_tablero.py               # crea el tablero y muestra su URL
"""
import argparse
import os
import sys

import requests

RAIZ = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
API = "https://api.trello.com/1"
NOMBRE = "Datinomics - Plataforma web"

ETIQUETAS = {"Datos": "green", "Backend": "blue", "Front web": "purple", "Infra": "orange",
             "Producto": "yellow", "Legal": "red", "Fuente nueva": "sky"}

# (lista, [(titulo, etiquetas, descripcion, checklist)])
TABLERO = [
    ("Hecho", [
        ("Relevamiento y verificacion de ubicacion de comercios", ["Datos"],
         "Verificacion por evidencia (OSM, sitio, CPA, telefono, SEPA, localizadores). "
         "CABA, Mendoza y Corrientes curadas: 725 comercios verificados.", []),
        ("Scrapers por plataforma", ["Datos"],
         "Tiendanube, WooCommerce, VTEX, Shopify, Magento y PrestaShop (Playwright). "
         "Paralelismo por tienda con tope de tiempo.", []),
        ("Integracion SEPA", ["Datos", "Fuente nueva"],
         "Los comercios que informan a SEPA toman sus precios de SEPA; el resto se scrapea.", []),
        ("Fuentes externas: agro, combustibles, BCRA, inmuebles", ["Datos", "Fuente nueva"],
         "Granos (BCR), hacienda (Canuelas), frutas y hortalizas (Mercado Central), combustibles "
         "(Sec. Energia), BCRA, medicamentos (Alfabeta) y ZonaProp. Ejecutor: _Nacional/fuentes_externas.py", []),
        ("Prototipo del front", ["Front web"],
         "front/platform: Explorador, Empresas, Rubros, Comparador, Alertas, API y Ajustes con datos de ejemplo.", []),
    ]),
    ("En curso", [
        ("Curar las 21 provincias restantes", ["Datos"],
         "Correr curar_provincia.py --paralelo por region y revisar los reportes.",
         ["NOA", "NEA (resto)", "Cuyo (resto)", "Centro-Pampeana (resto)", "Patagonia"]),
        ("Shopify estable", ["Datos"],
         "Shopify limita el catalogo publico por tienda. Corrida aparte, de noche, 1-2 hilos, 3-5 s.",
         ["Corrida nocturna de las 9 tiendas de CABA", "Medir bloqueos con IP descansada"]),
        ("Corrida completa de fuentes externas", ["Datos"],
         "Primera corrida completa: tiempos por fuente y cantidad de precios.", []),
    ]),
    ("MVP web - Datos", [
        ("Base de datos como fuente de verdad", ["Datos", "Backend"],
         "Pasar de Excel/Parquet a PostgreSQL. Los Excel quedan como exportacion.",
         ["Modelo: comercio, sucursal, producto, precio, fuente, corrida", "Carga inicial desde Parquet/Excel",
          "Carga incremental diaria", "Indices para series y busqueda"]),
        ("Matching de productos entre comercios", ["Datos"],
         "Unificar el mismo producto en distintos comercios (EAN cuando hay; nombre + marca + presentacion si no).",
         ["Normalizar unidades y presentaciones", "Matching por EAN", "Matching difuso por nombre",
          "Revision manual de dudosos"]),
        ("Taxonomia comun de categorias", ["Datos"],
         "Categorias propias para todos los rubros y fuentes, mapeadas desde las categorias de cada tienda.", []),
        ("Series de precios e indices", ["Datos"],
         "Historial por producto y variaciones (diaria, mensual, interanual) e indices por rubro y provincia.",
         ["Variacion por producto", "Indice por rubro", "Indice por provincia", "Canasta de referencia"]),
        ("Orquestacion diaria", ["Datos", "Infra"],
         "Programar scrapers, SEPA y fuentes externas; reintentos y aviso de fallas.",
         ["Elegir orquestador (cron / Prefect)", "Ventanas por plataforma (Shopify de noche)",
          "Alertas de corrida fallida"]),
        ("Control de calidad de datos", ["Datos"],
         "Detectar precios en 0, saltos anomalos, duplicados y tiendas que dejan de responder.", []),
    ]),
    ("MVP web - Backend", [
        ("API REST", ["Backend"],
         "FastAPI sobre PostgreSQL. Es la que consume el front y la que se ofrece a clientes.",
         ["Empresas y comercios", "Rubros e indices", "Productos y busqueda", "Series de precios",
          "Comparador", "Exportacion CSV/Excel", "Documentacion OpenAPI"]),
        ("Usuarios, autenticacion y planes", ["Backend", "Producto"],
         "Registro, login, roles y limites por plan (incluye claves de API).", []),
        ("Busqueda de productos", ["Backend"],
         "Busqueda full-text con tolerancia a errores y filtros por rubro, provincia y comercio.", []),
        ("Alertas de precio", ["Backend"],
         "El usuario define umbrales por producto o rubro; aviso por email.", []),
        ("Pagos y suscripciones", ["Backend", "Producto"],
         "Suscripciones con Mercado Pago.", []),
    ]),
    ("MVP web - Front", [
        ("Conectar el front a la API", ["Front web"],
         "Reemplazar front/platform/data.js (datos de ejemplo) por llamadas a la API.", []),
        ("Explorador con datos reales", ["Front web"], "", []),
        ("Empresas: ficha de comercio", ["Front web"],
         "Productos, evolucion de precios, sucursales y fuente de los datos (scraping / SEPA).", []),
        ("Rubros e indices", ["Front web"], "Agro, combustibles, medicamentos e inmuebles como rubros nuevos.", []),
        ("Comparador de precios", ["Front web"], "Mismo producto entre comercios y provincias.", []),
        ("Alertas (pantalla)", ["Front web"], "", []),
        ("Portal de API para clientes", ["Front web"], "Claves, consumo y documentacion.", []),
        ("Landing, registro y ajustes de cuenta", ["Front web", "Producto"], "", []),
        ("Responsive, accesibilidad y rendimiento", ["Front web"], "", []),
    ]),
    ("MVP web - Infra y legal", [
        ("Hosting y entornos", ["Infra"],
         "Front, API y base en la nube; dominio y HTTPS; dev / staging / produccion.",
         ["Elegir proveedor", "Dominio y certificados", "CI/CD", "Backups de la base"]),
        ("Workers de scraping en la nube", ["Infra", "Datos"],
         "Ejecutar scrapers fuera de la PC local, con ritmo por plataforma.", []),
        ("Monitoreo y logs", ["Infra"], "", []),
        ("Revision legal de fuentes", ["Legal"],
         "Terminos de uso y robots.txt por fuente; que se puede mostrar o redistribuir (ZonaProp, Alfabeta, "
         "MercadoLibre, sitios scrapeados) y que queda solo para uso interno.", []),
        ("Terminos de servicio y politica de privacidad", ["Legal", "Producto"], "", []),
    ]),
    ("Fuentes por sumar", [
        ("MercadoLibre (API oficial)", ["Fuente nueva"],
         "Registrar aplicacion en developers.mercadolibre.com.ar y confirmar que permisos de busqueda da.", []),
        ("Alfabeta con cuenta registrada", ["Fuente nueva", "Legal"],
         "Limite diario anonimo (~100 paginas). Con cuenta gratuita se extiende; evaluar licencia del Manual Farmaceutico.",
         []),
        ("Argenprop", ["Fuente nueva"], "Bloquea con desafio anti-bots: requiere acuerdo o API.", []),
        ("Futuros de granos y precios FAS", ["Fuente nueva"], "A3 Mercados y Ministerio de Agricultura.", []),
        ("Tarifas de servicios", ["Fuente nueva"], "Luz (ENRE), gas (ENARGAS), agua, peajes, transporte.", []),
        ("Scrapers a medida de cadenas", ["Fuente nueva", "Datos"], "",
         ["Megatone", "Musimundo", "Dexter", "Ribeiro", "Makro"]),
    ]),
    ("Ideas (despues de la web)", [
        ("App mobile", ["Producto"], "Despues de validar la version web.", []),
        ("Calculadora de inflacion personal", ["Producto"], "Canasta propia del usuario.", []),
        ("Alertas por WhatsApp", ["Producto"], "", []),
        ("Mapa de precios de combustibles", ["Producto", "Front web"], "Con las coordenadas de cada estacion.", []),
    ]),
]


def credenciales():
    try:
        from dotenv import load_dotenv
        load_dotenv(os.path.join(RAIZ, ".env"))
    except ImportError:
        pass
    key, token = os.environ.get("TRELLO_KEY"), os.environ.get("TRELLO_TOKEN")
    if not (key and token):
        sys.exit("Faltan TRELLO_KEY y TRELLO_TOKEN (entorno o .env)")
    return {"key": key, "token": token}


def post(ruta, auth, **params):
    r = requests.post(f"{API}{ruta}", params={**auth, **params}, timeout=30)
    r.raise_for_status()
    return r.json()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--simular", action="store_true")
    a = ap.parse_args()
    if a.simular:
        for lista, tarjetas in TABLERO:
            print(f"\n[{lista}]")
            for titulo, etiquetas, _, checklist in tarjetas:
                print(f"  - {titulo}  ({', '.join(etiquetas)})" + (f"  [{len(checklist)} items]" if checklist else ""))
        print(f"\n{len(TABLERO)} listas, {sum(len(t) for _, t in TABLERO)} tarjetas")
        return
    auth = credenciales()
    tablero = post("/boards/", auth, name=NOMBRE, defaultLists="false", defaultLabels="false")
    ids_etiqueta = {n: post("/labels", auth, idBoard=tablero["id"], name=n, color=c)["id"]
                    for n, c in ETIQUETAS.items()}
    for lista, tarjetas in TABLERO:
        id_lista = post("/lists", auth, idBoard=tablero["id"], name=lista, pos="bottom")["id"]
        for titulo, etiquetas, desc, checklist in tarjetas:
            tarjeta = post("/cards", auth, idList=id_lista, name=titulo, desc=desc, pos="bottom",
                           idLabels=",".join(ids_etiqueta[e] for e in etiquetas))
            if checklist:
                cl = post("/checklists", auth, idCard=tarjeta["id"], name="Tareas")
                for item in checklist:
                    post(f"/checklists/{cl['id']}/checkItems", auth, name=item)
        print(f"  {lista}: {len(tarjetas)} tarjetas")
    print(f"Tablero creado: {tablero['url']}")


if __name__ == "__main__":
    main()
