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

JS_MAGENTO = r"""
() => {
  const out = [], seen = new Set();
  document.querySelectorAll('.product-item-info').forEach(card => {
    const pr = card.querySelector('[data-price-type="finalPrice"]');
    if (!pr) return;
    const precio = parseFloat(pr.getAttribute('data-price-amount'));
    if (!isFinite(precio)) return;
    const a = card.querySelector('a[href$=".html"]');
    const href = a ? (a.getAttribute('href') || '') : '';
    if (!href || seen.has(href)) return;
    seen.add(href);
    const link = card.querySelector('a.product-item-link, .product-item-name a');
    const img = card.querySelector('img');
    let nombre = link ? (link.textContent || '').replace(/\s+/g, ' ').trim() : '';
    if (!nombre && img) nombre = (img.getAttribute('alt') || '').replace(/\s+/g, ' ').trim();
    const m = href.match(/\/(\d{8,14})-([^\/]+?)\.html/);
    if (!nombre && m) nombre = m[2].replace(/-/g, ' ');
    if (!nombre) return;
    const holder = pr.closest('[data-product-id]');
    const sku = m ? m[1] : (holder ? holder.getAttribute('data-product-id') : '');
    out.push({nombre: nombre.slice(0, 110), precio: precio, sku: sku});
  });
  return out;
}
"""
JS_CATS_MAGENTO = r"""
() => {
  const vistos = new Set(), out = [];
  document.querySelectorAll('a[href]').forEach(a => {
    let u;
    try { u = new URL(a.getAttribute('href'), location.href); } catch (e) { return; }
    if (u.origin !== location.origin) return;
    const path = u.pathname.replace(/\/+$/, '');
    const partes = path.split('/').filter(Boolean);
    if (partes.length !== 1 || !path.endsWith('.html')) return;
    if (/^\d{8,}/.test(partes[0])) return;
    const limpio = u.origin + path;
    if (vistos.has(limpio)) return;
    vistos.add(limpio);
    out.push(limpio);
  });
  return out;
}
"""
JS_HIJOS = r"""
(path) => {
  const vistos = new Set(), out = [];
  const base = path.replace(/\.html$/, '');
  const n = base.split('/').filter(Boolean).length;
  document.querySelectorAll('a[href]').forEach(a => {
    let u;
    try { u = new URL(a.getAttribute('href'), location.href); } catch (e) { return; }
    if (u.origin !== location.origin) return;
    const p = u.pathname.replace(/\/+$/, '');
    if (!p.endsWith('.html') || !p.startsWith(base + '/')) return;
    if (/^\d{8,}/.test(p.split('/').pop())) return;
    if (p.split('/').filter(Boolean).length !== n + 1) return;
    if (vistos.has(p)) return;
    vistos.add(p);
    out.push(p);
  });
  return out;
}
"""

def _precio(s):
    if isinstance(s, (int, float)):
        return round(float(s), 2)
    s = re.sub(r"[^\d,]", "", s).replace(".", "").replace(",", ".")
    try:
        return round(float(s), 2)
    except ValueError:
        return None

def _fallo(motivo):
    try:
        from . import diag
        diag.fallo(motivo)
    except ImportError:  # al correr este archivo directo 
        pass

def _extraer(pg):
    prods = pg.evaluate(JS_EXTRACT)
    if len(prods) >= 3:
        return prods
    mag = pg.evaluate(JS_MAGENTO)
    return mag if len(mag) >= 3 else prods

def _total_listado(pg):
    tb = pg.locator(".toolbar-amount")
    if not tb.count():
        return None
    m = re.search(r"(\d[\d.]*)\s*art", tb.first.text_content() or "", re.I)
    return int(m.group(1).replace(".", "")) if m else None

def _magento_catalogo(pg, tienda, max_nodos=400, max_pag=300,
                      excluir=("ofertas", "cyber-monday"), inicio=None, log=None,
                      bajar_hijos=False):
    filas, vistos = [], set()

    def clave(x):
        return x.get("sku") or (x["nombre"] + "|" + str(x["precio"]))

    def sumar(prods, cat):
        for x in prods:
            k = clave(x)
            if k in vistos:
                continue
            vistos.add(k)
            filas.append({"SKU": x.get("sku", ""), "Nombre": x["nombre"],
                          "Precio": _precio(x["precio"]), "Fecha": HOY,
                          "Categoria": cat, "Tienda": tienda})

    def ruta(href):
        return re.sub(r"^https?://[^/]+", "", href).rstrip("/")

    base = re.match(r"https?://[^/]+", pg.url).group(0)
    inicial = pg.evaluate(JS_MAGENTO)
    if inicio:
        cola = list(inicio)
    else:
        cola = [ruta(h) for h in pg.evaluate(JS_CATS_MAGENTO)]
        cola = [p for p in cola if p.split("/")[-1].replace(".html", "") not in excluir]
    visitados, nodos = set(), 0
    while cola and nodos < max_nodos:
        path = cola.pop(0)
        if path in visitados:
            continue
        visitados.add(path)
        nodos += 1
        cat = path.strip("/").replace(".html", "")
        vistos_cat, total, hijos = set(), None, []
        for page in range(1, max_pag + 1):
            try:
                url = base + path if page == 1 else f"{base}{path}?p={page}"
                resp = pg.goto(url, wait_until="domcontentloaded", timeout=45000)
                if resp is not None and resp.status >= 400:
                    break
                pg.wait_for_timeout(2000)
                if page == 1:
                    total = _total_listado(pg)
                    if total is None:
                        break  # sin contador: no es un listado de categoria
                    hijos = pg.evaluate(JS_HIJOS, path) if bajar_hijos else []
                prods = pg.evaluate(JS_MAGENTO)
            except Exception as e:
                _fallo(f"magento {cat} pag {page}: {type(e).__name__}")
                break
            nuevos = [x for x in prods if clave(x) not in vistos_cat]
            if not nuevos:
                break  # la pagina repite o esta vacia: se acabo ESTA categoria
            vistos_cat.update(clave(x) for x in nuevos)
            sumar(nuevos, cat)
            if len(vistos_cat) >= total:
                break
        if bajar_hijos and hijos and total is not None and len(vistos_cat) < total:
            cola.extend(h for h in hijos if h not in visitados)
        if log:
            log(f"{cat}: anuncia={total} trajo={len(vistos_cat)} cola={len(cola)}")
    sumar(inicial, "")
    return filas


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
        es_magento = False
        ultimo_err = None
        for ruta in RUTAS:
            try:
                resp = pg.goto(base + ruta, wait_until="domcontentloaded", timeout=45000)
                if resp is not None and resp.status >= 400:
                    ultimo_err = f"HTTP {resp.status}"
                    continue
                pg.wait_for_timeout(2500)
                prim = _extraer(pg)
                if len(prim) >= 3:
                    ruta_ok = ruta
                    es_magento = len(pg.evaluate(JS_EXTRACT)) < 3
                    break
            except Exception as e:
                ultimo_err = type(e).__name__
                continue
        if not ruta_ok:
            if ultimo_err:
                _fallo(f"playwright: ninguna ruta cargo bien (ultimo error: {ultimo_err})")
            else:
                _fallo("playwright: paginas cargan pero no hay 3+ productos con precio")
            b.close()
            return []
        if es_magento:
            filas = _magento_catalogo(pg, tienda)
            b.close()
            return filas
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
                prods = _extraer(pg)
            except Exception as e:
                _fallo(f"playwright pagina {page}: {type(e).__name__}")
                break
            nuevos = 0
            for x in prods:
                k = x["nombre"] + "|" + str(x["precio"])
                if k in vistos:
                    continue
                vistos.add(k)
                nuevos += 1
                filas.append({"SKU": x.get("sku", ""), "Nombre": x["nombre"], "Precio": _precio(x["precio"]),
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
