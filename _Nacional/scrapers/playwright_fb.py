# -*- coding: utf-8 -*-
"""
Fallback con navegador headless (Playwright) para tiendas que NO tienen API
publica reconocible (Magento, Prestashop, Next.js a medida como Farmar/Cluster).
Renderiza la pagina de productos y extrae nombre+precio del DOM ya pintado.

Uso como modulo: scrape_playwright(url) -> [{SKU,Nombre,Precio,Fecha,Categoria}]
"""
import datetime
import re

HOY = datetime.date.today().isoformat()
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")

# Rutas candidatas donde suele estar el listado de productos
RUTAS = ["/productos", "/tienda", "/shop", "/catalogo", "/collections/all",
         "/categoria", "/products", "/"]

# Extractor DOM: busca tarjetas con precio AR ($1.234,56) y su nombre cercano
JS_EXTRACT = r"""
() => {
  const priceRe = /\$\s?\d{1,3}(?:\.\d{3})*(?:,\d{2})?/;
  const out = [], seen = new Set();
  const nodes = document.querySelectorAll('li, div, article, a');
  nodes.forEach(el => {
    const txt = (el.textContent || '').replace(/\s+/g, ' ').trim();
    if (!txt || txt.length > 220) return;
    const m = txt.match(priceRe);
    if (!m) return;
    let name = '';
    const ne = el.querySelector('h1,h2,h3,h4,h5,a,strong,[class*=name],[class*=title],[class*=nombre],[class*=titulo]');
    if (ne) name = (ne.textContent || '').replace(/\s+/g, ' ').trim();
    if (!name || name.length < 3) return;
    if (priceRe.test(name)) return;            // el nombre no debe ser el precio
    name = name.slice(0, 110);
    const key = name + '|' + m[0];
    if (seen.has(key)) return; seen.add(key);
    out.push({nombre: name, precio: m[0]});
  });
  return out;
}
"""


def _precio(s):
    s = re.sub(r"[^\d,]", "", s).replace(".", "").replace(",", ".")
    try:
        return round(float(s), 2)
    except ValueError:
        return None


def scrape_playwright(url, tienda="", max_scroll=6, paginar=8):
    from playwright.sync_api import sync_playwright
    base = re.match(r"(https?://[^/]+)", url if url.startswith("http") else "https://" + url)
    base = base.group(1) if base else url
    filas, vistos = [], set()
    with sync_playwright() as p:
        b = p.chromium.launch(headless=True)
        pg = b.new_page(user_agent=UA, viewport={"width": 1366, "height": 1000})
        # elegir ruta con productos
        ruta_ok = None
        for ruta in RUTAS:
            try:
                pg.goto(base + ruta, wait_until="domcontentloaded", timeout=45000)
                pg.wait_for_timeout(2500)
                prim = pg.evaluate(JS_EXTRACT)
                if len(prim) >= 3:
                    ruta_ok = ruta
                    break
            except Exception:
                continue
        if not ruta_ok:
            b.close()
            return []
        # paginar (?page=N) y scrollear cada pagina
        for page in range(1, paginar + 1):
            try:
                if page > 1:
                    sep = "&" if "?" in (base + ruta_ok) else "?"
                    pg.goto(f"{base}{ruta_ok}{sep}page={page}", wait_until="domcontentloaded", timeout=45000)
                    pg.wait_for_timeout(2000)
                for _ in range(max_scroll):
                    pg.mouse.wheel(0, 5000)
                    pg.wait_for_timeout(900)
                prods = pg.evaluate(JS_EXTRACT)
            except Exception:
                break
            nuevos = 0
            for x in prods:
                k = x["nombre"] + "|" + x["precio"]
                if k in vistos:
                    continue
                vistos.add(k)
                nuevos += 1
                filas.append({"SKU": "", "Nombre": x["nombre"], "Precio": _precio(x["precio"]),
                              "Fecha": HOY, "Categoria": "", "Tienda": tienda})
            if nuevos == 0:
                break
        b.close()
    return filas


if __name__ == "__main__":
    import sys
    u = sys.argv[1] if len(sys.argv) > 1 else "https://www.farmar.com.ar"
    rows = scrape_playwright(u, "test")
    print(f"productos: {len(rows)}")
    for r in rows[:12]:
        print(f"  {r['Nombre'][:60]:60s} -> {r['Precio']}")
