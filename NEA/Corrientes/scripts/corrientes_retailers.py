# -*- coding: utf-8 -*-
"""
Retailers de CORRIENTES con tienda online / precios (para scrapear precios).
Combina:
  1) cadenas nacionales que operan en Corrientes/NEA
  2) retailers correntinos locales (descubiertos con busqueda dirigida por rubro)
Verifica que cada URL este viva y publique precios. -> corrientes_retailers.xlsx
"""
import concurrent.futures as cf
import re
import socket
import time

import pandas as pd
from ddgs import DDGS

from descubrir_webs import EXCLUIR_DOM
from verificar_cadenas import _try_get, _candidatos, clasificar_tienda, ANTIBOT

socket.setdefaulttimeout(20)

# Lista CURADA para Corrientes: cadenas que operan en la provincia + locales
# correntinos con tienda online ya verificados. (empresa, sector, url, origen)
CURADOS = [
    # --- Cadenas nacionales/regionales que operan en Corrientes ---
    ("Carrefour", "Supermercado", "https://www.carrefour.com.ar", "Cadena nacional"),
    ("Dia", "Supermercado", "https://diaonline.supermercadosdia.com.ar", "Cadena nacional"),
    ("ChangoMas", "Supermercado", "https://www.masonline.com.ar", "Cadena nacional"),
    ("Makro", "Mayorista", "https://www.makro.com.ar", "Cadena nacional"),
    ("Diarco", "Mayorista", "https://www.diarco.com.ar", "Cadena nacional"),
    ("Farmacity", "Farmacia", "https://www.farmacity.com", "Cadena nacional"),
    ("Farmaplus", "Farmacia", "https://www.farmaplus.com.ar", "Cadena nacional"),
    ("Farmalife", "Farmacia", "https://www.farmalife.com.ar", "Cadena nacional"),
    ("Farmaonline", "Farmacia", "https://www.farmaonline.com", "Cadena nacional"),
    ("Openfarma", "Farmacia", "https://www.openfarma.com.ar", "Cadena nacional"),
    ("Fravega", "Electro", "https://www.fravega.com", "Cadena nacional"),
    ("Musimundo", "Electro", "https://www.musimundo.com", "Cadena nacional"),
    ("Cetrogar", "Electro", "https://www.cetrogar.com.ar", "Cadena (NEA)"),
    ("Naldo", "Electro", "https://www.naldo.com.ar", "Cadena (NEA)"),
    ("Megatone", "Electro", "https://www.megatone.net", "Cadena (NEA)"),
    ("Ribeiro", "Electro", "https://www.ribeiro.com.ar", "Cadena nacional"),
    ("El Mundo del Juguete", "Jugueteria", "https://www.elmundodeljuguete.com.ar", "Cadena nacional"),
    # --- Locales / regionales de Corrientes con tienda online ---
    ("La Reina", "Supermercado", "https://www.lareinacorrientes.com.ar", "Local Corrientes"),
    ("Central Oeste", "Farmacia", "https://www.centraloeste.com.ar", "Local Corrientes/NEA"),
    ("DISANCO Distribuidora", "Mayorista", "https://www.disanco.com.ar", "Local Corrientes"),
    ("Beauty Shop Corrientes", "Perfumeria/Cosmetica", "https://beautyshopctes.com", "Local Corrientes"),
    ("RAFFE Perfumerias", "Perfumeria/Cosmetica", "https://raffeperfumerias.com", "Local/regional"),
    ("Edify (materiales)", "Ferreteria/Construccion", "https://tienda.edify.com.ar", "Local Corrientes"),
    ("TURCOR", "Ferreteria/Construccion", "https://turcor.com.ar", "Local Corrientes"),
    ("Pinturerias MM", "Ferreteria/Construccion", "https://www.pintureriasmm.com.ar", "Local Corrientes"),
    ("Jarana Calzados", "Indumentaria/Calzado", "https://www.jaranacalzados.com.ar", "Local/regional"),
    ("La Muebleria Online", "Muebles/Hogar/Bazar", "https://www.lamuebleriaonline.com.ar", "Local/regional"),
    ("Habitar", "Electro/Muebles", "https://habitar.com.ar", "Local NEA"),
    ("Importadora Electro", "Electro/Electrodomesticos", "https://www.importadoraelectro.com", "Local/regional"),
    ("Gianelli Distribuidora", "Mayorista/Distribuidora", "https://gianellidistribuidoramayorista.com.ar", "Local/regional"),
    ("Recreare", "Libreria/Jugueteria", "https://www.recreare.com.ar", "Local/regional"),
    ("Ta te ti Jugueterias", "Libreria/Jugueteria", "https://tatetijugueterias.com.ar", "Local/regional"),
    ("Mariana Maquillajes Corrientes", "Perfumeria/Cosmetica", "https://marianamaquillajes.wixsite.com/website", "Local Corrientes"),
]

# Busquedas dirigidas para descubrir LOCALES correntinos con tienda online
SECTOR_QUERIES = {
    "Supermercado": ["supermercado online corrientes comprar", "supermercado corrientes envio a domicilio online"],
    "Farmacia": ["farmacia online corrientes comprar", "farmacia corrientes pedidos online"],
    "Electro/Electrodomesticos": ["electrodomesticos corrientes comprar online", "tienda electro corrientes online"],
    "Ferreteria/Construccion": ["ferreteria online corrientes", "corralon materiales construccion corrientes online", "pintureria corrientes comprar online"],
    "Indumentaria/Calzado": ["tienda ropa online corrientes", "calzado corrientes comprar online"],
    "Bebidas/Vinoteca": ["vinoteca online corrientes", "distribuidora bebidas corrientes online"],
    "Perfumeria/Cosmetica": ["perfumeria online corrientes comprar", "cosmetica corrientes tienda online"],
    "Mayorista/Distribuidora": ["distribuidora mayorista corrientes online", "autoservicio mayorista corrientes online"],
    "Muebles/Hogar/Bazar": ["muebleria online corrientes", "bazar hogar corrientes comprar online"],
    "Libreria/Jugueteria": ["libreria online corrientes comprar", "jugueteria corrientes online"],
}

EXCLUIR = tuple(set(EXCLUIR_DOM) | {
    "mercadolibre", "tiendamia", "alibaba", "amazon", "aliexpress",
    "groupon", "ofertasimbatibles", "facebook", "instagram", "wikipedia",
    "corrienteshoy", "corrientesaldia", "ellitoral", "diarioepoca",
    "paginasamarillas", "guiaclarin", "cuitonline", "argentina.gob",
})


FOREIGN_TLD = (".es", ".pl", ".ad", ".ao", ".mx", ".cl", ".co", ".pe", ".uy",
               ".br", ".it", ".fr", ".de", ".us", ".pt", ".ec", ".ve", ".bo",
               ".py", ".ru", ".in", ".nl", ".be", ".ch", ".at", ".gt", ".hn",
               ".sv", ".ni", ".pa", ".do", ".cr", ".gt", ".com.gt", ".com.hn")
# fragmentos de URL que indican pagina de producto suelta o locale extranjero
PATH_MALO = ("/producto", "/productos/", "/product/", "/es-es", "/es-mx",
             "/mx/", "/p/", "/categoria/", "/etiqueta-producto")
# titulos que delatan articulo/blog/error, no una tienda
TITULO_MALO = ("aumentan", "explica", "seo ", "(caso", "donde comprar",
               "donde comprar", "mejores ", "tiendas de electrodom", "ranking",
               "listado de", "guia de", "guía de", "comprar albenza",
               "comprar champix", "comprar albendazole", "precios de venta",
               "un carnicero", "linktree", "just a moment", "access denied",
               "page not found", "database error", "error en", "404", "herbalife")


def dominio(url):
    try:
        d = url.split("//")[-1].split("/")[0].lower().replace("www.", "")
        return d
    except Exception:
        return url


def es_extranjero(dom):
    return any(dom.endswith(t) for t in FOREIGN_TLD)


def descubrir():
    """Busca candidatos locales por rubro. Devuelve dict url -> (sector, titulo)."""
    cands = {}
    with DDGS(timeout=20) as d:
        for sector, queries in SECTOR_QUERIES.items():
            for q in queries:
                try:
                    res = list(d.text(q, region="ar-es", max_results=12))
                except Exception as e:
                    print(f"    error busqueda '{q}': {e}", flush=True)
                    time.sleep(8)
                    continue
                for r in res:
                    u = r.get("href") or ""
                    dom = dominio(u)
                    titulo = (r.get("title") or "")
                    if not u or any(x in dom for x in EXCLUIR):
                        continue
                    if es_extranjero(dom):
                        continue
                    if any(k in titulo.lower() for k in TITULO_MALO):
                        continue
                    if any(p in u.lower() for p in PATH_MALO):
                        continue
                    if dom not in cands:
                        cands[dom] = (u, sector, titulo)
                print(f"  [{sector}] '{q}' -> {len(res)} result.", flush=True)
                time.sleep(3)
    return cands


def verificar_url(args):
    empresa, sector, url, origen = args
    status = None
    for cand in _candidatos(url):
        status, final, html = _try_get(cand)
        if status is not None:
            break
    if status is None:
        return {"Empresa": empresa, "Sector": sector, "URL": url, "Origen": origen,
                "Estado": "No responde", "Tienda online": "No", "URL final": "", "Plataforma": ""}
    estado = "OK 200" if status == 200 else (
        f"Activo (anti-bot {status})" if status in ANTIBOT else f"HTTP {status}")
    tienda, plat = clasificar_tienda(status, html)
    titulo = ""
    m = re.search(r"<title[^>]*>(.*?)</title>", html, re.I | re.S)
    if m:
        titulo = re.sub(r"\s+", " ", m.group(1)).strip()[:80]
    if empresa == "?" and titulo:
        empresa = titulo
    return {"Empresa": empresa, "Sector": sector, "URL": url, "Origen": origen,
            "Estado": estado, "Tienda online": tienda, "URL final": final,
            "Plataforma": plat, "Titulo": titulo}


def main():
    print("1) Descubriendo retailers locales de Corrientes por rubro...", flush=True)
    cands = descubrir()
    print(f"   candidatos locales unicos: {len(cands)}", flush=True)

    tareas = [(e, s, u, origen) for e, s, u, origen in CURADOS]
    doms_known = {dominio(u) for _, _, u, _ in tareas}
    for dom, (u, sector, titulo) in cands.items():
        if dom not in doms_known:
            tareas.append(("?", sector, u, "Descubierto (revisar)"))

    print(f"2) Verificando {len(tareas)} URLs (cadenas + locales)...", flush=True)
    resultados = []
    with cf.ThreadPoolExecutor(max_workers=12) as ex:
        for i, r in enumerate(ex.map(verificar_url, tareas), 1):
            resultados.append(r)
            print(f"  [{i}/{len(tareas)}] {str(r['Empresa'])[:30]:30s} {r['Estado']:18s} tienda={r['Tienda online']}",
                  flush=True)

    import html as _html
    df = pd.DataFrame(resultados)
    df = df.reindex(columns=["Empresa", "Sector", "URL", "URL final", "Estado",
                             "Tienda online", "Plataforma", "Origen", "Titulo"]).fillna("")
    df["Empresa"] = df["Empresa"].map(lambda s: _html.unescape(str(s)).strip())
    df["Titulo"] = df["Titulo"].map(lambda s: _html.unescape(str(s)).strip())
    # dedupe por dominio
    df["_dom"] = df["URL"].map(dominio)
    df = df.drop_duplicates("_dom").drop(columns="_dom")

    df = df.sort_values(["Origen", "Sector", "Empresa"], kind="stable")
    activo = df["Estado"].str.startswith(("OK", "Activo"))
    tienda = df["Tienda online"].isin(["Si", "Probable (anti-bot)"])
    curado = ~df["Origen"].str.startswith("Descubierto")
    plataforma = df["Plataforma"].astype(str).str.len() > 0

    cols = ["Empresa", "Sector", "URL", "Tienda online", "Plataforma", "Estado", "Origen"]
    # Principal: lista curada (cadenas + locales verificados)
    principal = df[curado & activo][cols].sort_values(["Sector", "Empresa"])
    # Candidatos: descubiertos por busqueda que corren sobre plataforma e-commerce
    candidatos = df[(~curado) & activo & tienda & plataforma][cols]

    with pd.ExcelWriter("corrientes_retailers.xlsx", engine="openpyxl") as xl:
        principal.to_excel(xl, sheet_name="Corrientes (curado)", index=False)
        candidatos.to_excel(xl, sheet_name="Candidatos descubiertos", index=False)
        for sh in xl.sheets.values():
            for col, w in zip("ABCDEFG", (34, 24, 46, 18, 18, 20, 22)):
                sh.column_dimensions[col].width = w
            sh.freeze_panes = "A2"

    print(f"\nCURADO (cadenas + locales) verificado: {len(principal)}")
    print(f"Candidatos descubiertos (con plataforma e-commerce): {len(candidatos)}")
    print("Guardado: corrientes_retailers.xlsx")


if __name__ == "__main__":
    main()
