# -*- coding: utf-8 -*-
"""
Verifica el universo de cadenas (cadenas_argentina.py):
  - que la URL este viva (HTTP 200, sigue redirects)
  - que parezca tener tienda online / publicar precios
Genera cadenas_argentina_retailers.xlsx
"""
import concurrent.futures as cf
import socket

import requests
import pandas as pd

from cadenas_argentina import CADENAS

socket.setdefaulttimeout(20)
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")
HDRS = {"User-Agent": UA,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "es-AR,es;q=0.9,en;q=0.8"}
# codigos que indican sitio VIVO pero con proteccion anti-bot (igual scrapeable)
ANTIBOT = {401, 403, 406, 429, 503}

# senales de e-commerce / precios
SIG_PRECIO = ("$", "precio", "agregar al carrito", "añadir al carrito",
              "comprar", "carrito", "add to cart", "oferta", "cuotas")
SIG_PLATAFORMA = ("vtex", "tiendanube", "mercadoshops", "woocommerce",
                  "magento", "shopify", "prestashop")


def _try_get(url):
    """GET con manejo; devuelve (status, url_final, html) o (None, '', '')."""
    try:
        r = requests.get(url, headers=HDRS, timeout=18, allow_redirects=True)
        return r.status_code, r.url, r.text
    except Exception:
        return None, "", ""


def _candidatos(url):
    """Variantes a probar: original, toggle www, http."""
    yield url
    if "://www." in url:
        yield url.replace("://www.", "://")
    else:
        yield url.replace("://", "://www.")
    yield url.replace("https://", "http://")


def clasificar_tienda(status, html):
    if status == 200:
        h = html.lower()
        precio = sum(s in h for s in SIG_PRECIO)
        plat = [p for p in SIG_PLATAFORMA if p in h]
        if precio >= 2 or plat:
            return "Si", ", ".join(plat)
        return "Dudoso", ", ".join(plat)
    if status in ANTIBOT:
        return "Probable (anti-bot)", ""
    return "No", ""


def verificar(item):
    empresa, sector, url, cobertura, detalle = item
    res = {"Empresa": empresa, "Sector": sector, "URL": url,
           "Cobertura": cobertura, "Detalle": detalle,
           "Estado": "", "URL final": "", "Tienda online": "", "Plataforma": ""}
    status = None
    for cand in _candidatos(url):
        status, final, html = _try_get(cand)
        if status is not None:
            break

    # si no responde de ninguna forma, buscar la URL oficial con el buscador
    if status is None or (status >= 500 and status not in ANTIBOT):
        try:
            from descubrir_webs import buscar_web
            nuevo, _ = buscar_web(empresa, f"{empresa} {sector} Argentina tienda online")
            if nuevo:
                s2, f2, h2 = _try_get(nuevo)
                if s2 is not None:
                    res["URL"] = nuevo
                    status, final, html = s2, f2, h2
                    res["Detalle"] = (detalle + " [URL corregida]").strip()
        except Exception:
            pass

    if status is None:
        res["Estado"] = "No responde"
        res["Tienda online"] = "No"
        return res
    res["Estado"] = "OK 200" if status == 200 else (
        f"Activo (anti-bot {status})" if status in ANTIBOT else f"HTTP {status}")
    res["URL final"] = final
    res["Tienda online"], res["Plataforma"] = clasificar_tienda(status, html)
    return res


def main():
    print(f"Verificando {len(CADENAS)} retailers...", flush=True)
    resultados = []
    with cf.ThreadPoolExecutor(max_workers=12) as ex:
        for i, r in enumerate(ex.map(verificar, CADENAS), 1):
            estado = r["Estado"]
            print(f"  [{i}/{len(CADENAS)}] {r['Empresa']:28s} {estado:10s} tienda={r['Tienda online']}",
                  flush=True)
            resultados.append(r)

    df = pd.DataFrame(resultados, columns=[
        "Empresa", "Sector", "URL", "URL final", "Estado", "Tienda online",
        "Plataforma", "Cobertura", "Detalle"])
    df = df.sort_values(["Sector", "Empresa"], kind="stable")

    vivos = df[df["Estado"].str.startswith("OK")]
    con_tienda = vivos[vivos["Tienda online"] == "Si"]

    with pd.ExcelWriter("cadenas_argentina_retailers.xlsx", engine="openpyxl") as xl:
        df.to_excel(xl, sheet_name="Todos los retailers", index=False)
        con_tienda.to_excel(xl, sheet_name="Con tienda online (scrapeable)", index=False)
        for sh in xl.sheets.values():
            for col, w in zip("ABCDEFGHI", (30, 20, 40, 40, 12, 14, 16, 14, 22)):
                sh.column_dimensions[col].width = w
            sh.freeze_panes = "A2"

    print(f"\nTotal: {len(df)} | vivos: {len(vivos)} | con tienda online: {len(con_tienda)}")
    print("Caidos/errores:")
    for _, r in df[~df["Estado"].str.startswith("OK")].iterrows():
        print(f"  {r['Empresa']:28s} {r['Estado']}  ({r['URL']})")
    print("\nGuardado: cadenas_argentina_retailers.xlsx")


if __name__ == "__main__":
    main()
