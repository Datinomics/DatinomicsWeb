# -*- coding: utf-8 -*-
"""
Corrientes capital - TODOS los rubros. Retailers con TIENDA ONLINE PROPIA (precios).
Metodo: lista curada verificada + descubrimiento por rubro, con filtro estricto:
debe correr sobre plataforma e-commerce real Y mencionar Corrientes en la pagina.
-> corrientes_full.xlsx
"""
import concurrent.futures as cf
import html as _html
import re
import socket
import time

import pandas as pd
from ddgs import DDGS

from verificar_cadenas import _try_get, _candidatos, clasificar_tienda, ANTIBOT

socket.setdefaulttimeout(20)

EXCLUIR = ("facebook", "instagram", "linkedin", "tiktok", "youtube", "twitter",
           "mercadolibre", "tiendeo", "rappi", "pedidosya", "paginasamarillas",
           "guiaclarin", "cuitonline", "licuo", "infoisinfo", "kompass", "yelp",
           "argentino.com", "promosdelbanco", "wikipedia", "aloo.com", "jooble",
           "catalogosofertas", "ilacad", "gov.ar", "gob.ar", "google.", "wa.me",
           "mapcarta", "moovit", "doctuo", "guiaferreterias", "directoriomayorista",
           "nanumba", "modo.com.ar", "takingdev", "sumerlabs", "polomap",
           "aarg.ar", "guiasanmiguel", "redargentina", "vinotecaonline.com.ar",
           "tiendanube.com/blog", "ivrea.com", "computrabajo", "indeed",
           "clasificados", "olx", "demos", "blogspot", "wordpress.com")

FOREIGN_TLD = (".es", ".pl", ".ad", ".ao", ".mx", ".cl", ".co", ".pe", ".uy",
               ".br", ".it", ".fr", ".de", ".us", ".pt", ".ec", ".ve", ".bo",
               ".py", ".ru", ".in", ".nl", ".be", ".ch", ".at", ".gt", ".hn",
               ".sv", ".ni", ".pa", ".do", ".cr", ".com.gt", ".com.hn", ".com.co")
PATH_MALO = ("/producto", "/productos/", "/product/", "/es-es", "/es-mx",
             "/mx/", "/categoria/", "/etiqueta-producto", "/tag/", "/blog")
TITULO_MALO = ("aumentan", "explica", "seo ", "(caso", "donde comprar", "mejores ",
               "tiendas de", "ranking", "listado de", "guia de", "guía de",
               "comprar albenza", "comprar champix", "albendazole", "precios de venta",
               "un carnicero", "linktree", "just a moment", "access denied",
               "page not found", "database error", "error en", "404", "herbalife",
               "como crear", "qué es", "que es una")

# Lista CURADA verificada (web propia, opera en Corrientes)
CURADO = [
    # --- SUPERMERCADOS de Corrientes (anclados por nombre, van si o si) ---
    ("La Reina", "Supermercado", "https://www.lareinaonline.com.ar", "Local Corrientes"),
    ("Depot Express", "Supermercado", "https://depotexpress.com.ar", "Local Corrientes/NEA"),
    ("Cuchermercados", "Supermercado", "https://www.cuchermercados.com.ar", "Local Corrientes/Chaco"),
    ("Cluster Supermercados", "Supermercado", "https://www.clustersupermercados.com.ar", "Local Corrientes"),
    ("Supermax", "Supermercado", "https://supermaxsa.com.ar", "Local Corrientes (web en obra)"),
    ("Impulso", "Supermercado", "https://www.supermercadoimpulso.com.ar", "Local Corrientes (verificar web)"),
    ("Tatu Supermercados", "Supermercado", "https://www.facebook.com/tatusupermercados", "Local Corrientes (solo WhatsApp/RRSS)"),
    ("Parada Canga", "Supermercado", "http://paradacanga.com", "Local Corrientes (solo informativo)"),
    ("Carrefour", "Supermercado", "https://www.carrefour.com.ar", "Cadena en Ctes"),
    ("ChangoMas", "Supermercado", "https://www.masonline.com.ar", "Cadena en Ctes"),
    ("Coto", "Supermercado", "https://www.cotodigital.com.ar", "Cadena en Ctes"),
    ("Dia", "Supermercado", "https://diaonline.supermercadosdia.com.ar", "Cadena en Ctes"),
    ("Diarco", "Mayorista", "https://www.diarco.com.ar", "Cadena en Ctes"),
    ("Makro", "Mayorista", "https://www.makro.com.ar", "Cadena en Ctes"),
    ("DISANCO", "Mayorista", "https://www.disanco.com.ar", "Local Corrientes"),
    ("Farmar", "Farmacia", "https://www.farmar.com.ar", "Local Corrientes"),
    ("Central Oeste", "Farmacia", "https://www.centraloeste.com.ar", "Local Corrientes/NEA"),
    ("Farmalife", "Farmacia", "https://www.farmalife.com.ar", "Regional"),
    ("Cetrogar", "Electro", "https://www.cetrogar.com.ar", "Cadena NEA"),
    ("Naldo", "Electro", "https://www.naldo.com.ar", "Cadena NEA"),
    ("Megatone", "Electro", "https://www.megatone.net", "Cadena NEA"),
    ("Fravega", "Electro", "https://www.fravega.com", "Cadena en Ctes"),
    ("Musimundo", "Electro", "https://www.musimundo.com", "Cadena en Ctes"),
    ("Importadora Electro", "Electro", "https://www.importadoraelectro.com", "Local/regional"),
    ("Habitar", "Electro/Muebles", "https://habitar.com.ar", "Local NEA"),
    ("Edify", "Ferreteria/Construccion", "https://tienda.edify.com.ar", "Local Corrientes"),
    ("TURCOR", "Ferreteria/Construccion", "https://turcor.com.ar", "Local Corrientes"),
    ("Pinturerias MM", "Ferreteria/Construccion", "https://www.pintureriasmm.com.ar", "Local Corrientes"),
    ("Pintureria Giannoni", "Ferreteria/Construccion", "https://www.pintureriagiannoni.com", "Local Corrientes"),
    ("Beauty Shop Corrientes", "Perfumeria/Cosmetica", "https://beautyshopctes.com", "Local Corrientes"),
    ("RAFFE Perfumerias", "Perfumeria/Cosmetica", "https://raffeperfumerias.com", "Local/regional"),
    ("Jarana Calzados", "Indumentaria/Calzado", "https://www.jaranacalzados.com.ar", "Local/regional"),
    ("Chante Store", "Indumentaria", "https://www.chantestore.com.ar", "Local Corrientes"),
    ("La Muebleria Online", "Muebles/Hogar", "https://www.lamuebleriaonline.com.ar", "Local/regional"),
    ("Arandu Hogar", "Muebles/Hogar", "https://aranduhogar.com.ar", "Local/regional"),
    ("Recreare", "Libreria/Jugueteria", "https://www.recreare.com.ar", "Local/regional"),
    ("Ta te ti Jugueterias", "Libreria/Jugueteria", "https://tatetijugueterias.com.ar", "Local/regional"),
    ("Ciclon Mayorista", "Mayorista", "https://www.ciclonmayorista.com.ar", "Local Corrientes"),
    ("Parfum Corrientes", "Perfumeria/Cosmetica", "https://parfumcorrientes.mitiendanube.com", "Local Corrientes"),
    # --- Deportes (cadenas en shoppings de Corrientes, e-commerce nacional) ---
    ("Dexter", "Deportes", "https://www.dexter.com.ar", "Cadena en Ctes (shopping)"),
    ("Stock Center", "Deportes", "https://www.stockcenter.com.ar", "Cadena en Ctes (shopping)"),
    ("Open Sports", "Deportes", "https://www.opensports.com.ar", "Cadena en Ctes (shopping)"),
    ("Solo Deportes", "Deportes", "https://www.solodeportes.com.ar", "Cadena en Ctes"),
    # --- Electro faltante + perfumeria cadena ---
    ("Ribeiro", "Electro", "https://www.ribeiro.com.ar", "Cadena en Ctes"),
    ("Juleriaque", "Perfumeria/Cosmetica", "https://www.juleriaque.com.ar", "Cadena en Ctes (shopping)"),
    ("Pinturerias Blika", "Ferreteria/Construccion", "https://www.blika.com.ar", "Local/regional"),
]

SECTOR_QUERIES = {
    "Carniceria/Polleria": ["carniceria online corrientes comprar", "carnes pollo online corrientes envio"],
    "Panaderia/Confiteria": ["panaderia online corrientes comprar", "confiteria pasteleria bomboneria online corrientes"],
    "Verduleria/Fruteria": ["verduleria fruteria online corrientes comprar", "frutas verduras online corrientes envio"],
    "Fiambreria/Dietetica": ["fiambreria online corrientes", "dietetica suplementos online corrientes comprar"],
    "Bebidas/Vinoteca": ["vinoteca online corrientes comprar", "distribuidora bebidas online corrientes", "cervezas vinos online corrientes envio"],
    "Electro/Electrodomesticos": ["electrodomesticos corrientes tienda online", "electronica corrientes comprar online", "aire acondicionado heladeras corrientes online"],
    "Computacion/Tecnologia": ["computacion tecnologia corrientes tienda online comprar", "celulares telefonia corrientes tienda online"],
    "Ferreteria/Construccion": ["ferreteria online corrientes comprar", "corralon materiales construccion corrientes online", "pintureria corrientes tienda online", "sanitarios griferia corrientes online"],
    "Indumentaria/Calzado/Deportes": ["ropa indumentaria corrientes tienda online", "calzado zapatillas corrientes comprar online", "articulos deportivos corrientes tienda online", "lenceria corrientes tienda online", "ropa bebes ninos corrientes online"],
    "Perfumeria/Cosmetica": ["perfumeria cosmetica corrientes tienda online comprar", "maquillaje belleza corrientes tienda online"],
    "Muebles/Hogar/Bazar": ["muebleria online corrientes comprar", "bazar hogar corrientes tienda online", "colchones sommier corrientes online", "deco iluminacion corrientes tienda online", "blanqueria textil hogar corrientes online"],
    "Libreria/Jugueteria": ["libreria online corrientes comprar", "jugueteria corrientes tienda online", "articulos libreria mayorista corrientes online"],
    "Mascotas/Veterinaria": ["petshop veterinaria online corrientes comprar", "alimento balanceado mascotas corrientes online"],
    "Optica/Salud": ["optica online corrientes comprar anteojos", "ortopedia insumos medicos corrientes online"],
    "Mayorista/Distribuidora": ["distribuidora mayorista corrientes online comprar", "autoservicio mayorista corrientes online", "mayorista limpieza descartables corrientes online"],
    "Joyeria/Relojeria/Regalos": ["joyeria relojeria corrientes tienda online", "regaleria cotillon corrientes comprar online"],
    "Autos/Motos/Repuestos": ["repuestos autopartes corrientes tienda online", "motos bicicletas corrientes comprar online", "neumaticos gomeria corrientes online"],
    "Florerias/Vivero": ["floreria vivero plantas corrientes tienda online comprar"],
    "Instrumentos/Musica": ["instrumentos musicales corrientes tienda online comprar"],
    # busquedas genericas por plataforma e-commerce, scopeadas a Corrientes
    "General/Tienda online": ["tienda online corrientes envios comprar", "mitiendanube corrientes", "tienda nube corrientes argentina", "comprar online corrientes capital envios a todo el pais", "ecommerce corrientes comprar online"],
}


def dominio(u):
    try:
        return u.split("//")[-1].split("/")[0].lower().replace("www.", "")
    except Exception:
        return u


def es_extranjero(dom):
    return any(dom.endswith(t) for t in FOREIGN_TLD)


def descubrir():
    cands = {}
    with DDGS(timeout=20) as d:
        for sector, queries in SECTOR_QUERIES.items():
            for q in queries:
                try:
                    res = list(d.text(q, region="ar-es", max_results=18))
                except Exception as e:
                    print(f"    error '{q}': {e}", flush=True)
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
                    if dom not in cands:
                        cands[dom] = (u, sector, tit)
                print(f"  [{sector}] '{q[:40]}' -> {len(res)}", flush=True)
                time.sleep(3)
    return cands


def verificar(args):
    nombre, sector, url, origen = args
    status = None
    for cand in _candidatos(url):
        status, final, htmlc = _try_get(cand)
        if status is not None:
            break
    res = {"Empresa": nombre, "Sector": sector, "URL": url, "Origen": origen,
           "Estado": "", "Tienda online": "", "Plataforma": "", "Menciona Ctes": ""}
    if status is None:
        res["Estado"] = "No responde"; res["Tienda online"] = "No"
        return res
    res["Estado"] = "OK 200" if status == 200 else (
        f"Activo (anti-bot {status})" if status in ANTIBOT else f"HTTP {status}")
    res["URL"] = final or url
    res["Tienda online"], res["Plataforma"] = clasificar_tienda(status, htmlc)
    low = (htmlc or "").lower()
    res["Menciona Ctes"] = "Si" if "corriente" in low else ""
    if nombre == "?":
        m = re.search(r"<title[^>]*>(.*?)</title>", htmlc or "", re.I | re.S)
        if m:
            res["Empresa"] = _html.unescape(re.sub(r"\s+", " ", m.group(1)).strip())[:70]
    return res


def cargar_base():
    """Carga el Excel previo para acumular (no perder lo ya confirmado)."""
    import os
    base = {}
    if os.path.exists("corrientes_full.xlsx"):
        try:
            prev = pd.read_excel("corrientes_full.xlsx", sheet_name="Corrientes tienda propia").fillna("")
            for _, r in prev.iterrows():
                base[dominio(str(r["URL"]))] = r.to_dict()
        except Exception as e:
            print(f"  (no se pudo leer base previa: {e})", flush=True)
    return base


def main():
    base = cargar_base()
    print(f"Base previa (ya confirmados): {len(base)}", flush=True)
    print("1) Descubriendo por rubro (Corrientes)...", flush=True)
    cands = descubrir()
    print(f"   candidatos: {len(cands)}", flush=True)

    tareas = [(e, s, u, o) for e, s, u, o in CURADO if dominio(u) not in base]
    known = {dominio(u) for _, _, u, _ in CURADO} | set(base.keys())
    for dom, (u, sector, tit) in cands.items():
        if dom not in known:
            tareas.append(("?", sector, u, "Descubierto"))

    print(f"2) Verificando {len(tareas)} URLs...", flush=True)
    out = []
    with cf.ThreadPoolExecutor(max_workers=12) as ex:
        for i, r in enumerate(ex.map(verificar, tareas), 1):
            out.append(r)
    df = pd.DataFrame(out).drop_duplicates("URL")

    activo = df["Estado"].str.startswith(("OK", "Activo"))
    tienda = df["Tienda online"].isin(["Si", "Probable (anti-bot)"])
    plat = df["Plataforma"].astype(str).str.len() > 0
    ctes = df["Menciona Ctes"] == "Si"
    curado = df["Origen"] != "Descubierto"

    cols = ["Empresa", "Sector", "URL", "Tienda online", "Plataforma",
            "Menciona Ctes", "Estado", "Origen"]
    # Principal nuevo: TODOS los curados (con su estado real) + descubiertos con plataforma Y que mencionan Corrientes
    nuevos = df[curado | (~curado & activo & tienda & plat & ctes)][cols]
    # acumular con la base previa
    base_df = pd.DataFrame(list(base.values()))
    if not base_df.empty:
        base_df = base_df.reindex(columns=cols)
        principal = pd.concat([base_df, nuevos], ignore_index=True)
    else:
        principal = nuevos
    principal["_d"] = principal["URL"].map(dominio)
    principal = principal.drop_duplicates("_d").drop(columns="_d")
    principal = principal.sort_values(["Sector", "Empresa"], kind="stable")
    nuevos_n = len(principal) - len(base)
    # Candidatos: descubiertos con plataforma pero sin mencion clara de Corrientes
    revisar = df[(~curado) & activo & plat & ~ctes][cols].sort_values(["Sector", "Empresa"])

    salida = "corrientes_full.xlsx"
    try:
        open(salida, "ab").close()
    except PermissionError:
        salida = "corrientes_full_actualizado.xlsx"
        print(f"  (corrientes_full.xlsx abierto en Excel; guardo en {salida})", flush=True)
    with pd.ExcelWriter(salida, engine="openpyxl") as xl:
        principal.to_excel(xl, sheet_name="Corrientes tienda propia", index=False)
        revisar.to_excel(xl, sheet_name="Candidatos (revisar)", index=False)
        for sh in xl.sheets.values():
            for c, w in zip("ABCDEFGH", (34, 26, 46, 18, 16, 14, 18, 20)):
                sh.column_dimensions[c].width = w
            sh.freeze_panes = "A2"

    print(f"\nPRINCIPAL (Corrientes con tienda propia): {len(principal)}  (+{nuevos_n} nuevos vs base de {len(base)})")
    print(f"Candidatos a revisar: {len(revisar)}")
    print("por sector (principal):")
    print(principal["Sector"].value_counts().to_string())
    print(f"Guardado: {salida}")


if __name__ == "__main__":
    main()
