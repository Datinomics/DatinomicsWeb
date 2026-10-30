# -*- coding: utf-8 -*-
"""Precios de venta al publico de medicamentos (Alfabeta, Manual Farmaceutico).
Las paginas /precio/<producto>.html se listan en el sitemap (robots.txt las permite;
el buscador /precio/srv? no). Una fila por presentacion: producto, laboratorio,
droga, accion terapeutica, presentacion, precio y fecha de vigencia.
El sitio declara su contenido protegido: los datos son para uso interno.

Alfabeta limita las consultas anonimas por dia (~100 paginas) y extiende el limite
a usuarios registrados (gratis): con ALFABETA_USUARIO / ALFABETA_CLAVE (entorno o .env)
se inicia sesion. Al aparecer el aviso de limite se corta la corrida. Lo relevado se
acumula en datos/fuentes/medicamentos/acumulado.parquet y cada corrida sigue por las
paginas que faltan (y despues por las relevadas hace mas tiempo)."""
import concurrent.futures as cf
import os
import re
import threading
import time
from html import unescape

import pandas as pd

from . import RAIZ, HOY, Ritmo, num_ar, sesion

try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(RAIZ, ".env"))
except ImportError:
    pass

SITEMAP = "https://www.alfabeta.net/sitemap.xml"
LOGIN = "https://www.alfabeta.net/usuarios/login.jsp"
ACUMULADO = os.path.join(RAIZ, "datos", "fuentes", "medicamentos", "acumulado.parquet")
AVISO_LIMITE = "mite m&aacute;ximo diario"
RE_TOKEN = re.compile(
    r'class="tproducto">(?P<prod>[^<]*)</span>.*?class="textor">\s*<span class="defecto">(?P<lab>[^<]*)'
    r'|class="sproducto">.*?<i>(?P<droga>[^<]*)</i>.*?<i>(?P<accion>[^<]*)</i>'
    r'|class="tddesc">(?P<pres>.*?)</td><td class="tdprecio">(?P<precio>[^<]*)</td><td class="tdfecha">(?P<fecha>[^<]*)',
    re.S)


def _limpio(s):
    return re.sub(r"\s+", " ", unescape(re.sub(r"<[^>]+>", "", s or ""))).strip()


def _pagina(s, ritmo, url, cortar):
    if cortar.is_set():
        return [], url
    for intento in range(3):
        ritmo.esperar()
        try:
            r = s.get(url, timeout=40)
            if r.status_code == 200:
                break
        except Exception:
            pass
        time.sleep(5 * (intento + 1))
    else:
        return [], url
    if AVISO_LIMITE in r.text:
        cortar.set()
        return [], url
    filas, prod, lab, droga, accion = [], "", "", "", ""
    for m in RE_TOKEN.finditer(r.text):
        if m.group("prod") is not None:
            prod, lab, droga, accion = _limpio(m.group("prod")), _limpio(m.group("lab")), "", ""
        elif m.group("droga") is not None:
            droga, accion = _limpio(m.group("droga")), _limpio(m.group("accion"))
        else:
            fecha = re.search(r"(\d{2})/(\d{2})/(\d{2})", m.group("fecha"))
            filas.append({"Producto": prod, "Laboratorio": lab, "Droga": droga, "Accion": accion,
                          "Presentacion": _limpio(m.group("pres")), "Precio": num_ar(m.group("precio")),
                          "Vigencia": f"20{fecha.group(3)}-{fecha.group(2)}-{fecha.group(1)}" if fecha else None,
                          "URL": url, "Relevado": HOY})
    return filas, None


def _login(s):
    usuario, clave = os.environ.get("ALFABETA_USUARIO"), os.environ.get("ALFABETA_CLAVE")
    if not (usuario and clave):
        print("  alfabeta: sin ALFABETA_USUARIO/ALFABETA_CLAVE, consultas anonimas (limite diario bajo)", flush=True)
        return False
    r = s.post(LOGIN, data={"usuario": usuario, "clave": clave}, timeout=40)
    ok = r.status_code == 200 and "Login" not in re.sub(r"(?s)<script.*?</script>", "", r.text)[:20000]
    print(f"  alfabeta: login {'ok' if ok else 'FALLIDO (se sigue anonimo)'}", flush=True)
    return ok


def descargar(hilos=4, segundos=0.2, limite=0, **_):
    """hilos/segundos: ritmo de pedidos (por defecto ~5 por segundo). limite: solo N paginas (prueba).
    Devuelve el acumulado completo (lo de esta corrida reemplaza lo anterior de esas paginas)."""
    s = sesion(hilos)
    _login(s)
    urls = [u for u in re.findall(r"<loc>([^<]+)</loc>", s.get(SITEMAP, timeout=60).text)
            if "/precio/" in u and u.endswith(".html")]
    previo = pd.read_parquet(ACUMULADO) if os.path.exists(ACUMULADO) else pd.DataFrame(columns=["URL", "Relevado"])
    ultima = previo.groupby("URL")["Relevado"].max().to_dict()
    urls.sort(key=lambda u: ultima.get(u, ""))  # primero las nunca relevadas, despues las mas viejas
    total = len(urls)
    if limite:
        urls = urls[:limite]
    ritmo, filas, fallidas, cortar = Ritmo(segundos), [], [], threading.Event()
    with cf.ThreadPoolExecutor(hilos) as ex:
        for i, (f, fallo) in enumerate(ex.map(lambda u: _pagina(s, ritmo, u, cortar), urls), 1):
            filas += f
            if fallo:
                fallidas.append(fallo)
            if i % 500 == 0:
                print(f"  alfabeta {i}/{len(urls)} paginas, {len(filas)} presentaciones", flush=True)
    if cortar.is_set():
        print(f"  alfabeta: limite diario de consultas alcanzado ({len(urls) - len(fallidas)} paginas leidas)", flush=True)
    elif fallidas:
        print(f"  alfabeta: {len(fallidas)} paginas sin respuesta", flush=True)
    nuevo = pd.DataFrame(filas)
    if not nuevo.empty:
        nuevo["Fuente"] = "Alfabeta"
    df = pd.concat([previo[~previo["URL"].isin(set(nuevo.get("URL", [])))], nuevo], ignore_index=True)
    os.makedirs(os.path.dirname(ACUMULADO), exist_ok=True)
    df.to_parquet(ACUMULADO, index=False, compression="zstd")
    print(f"  alfabeta: {nuevo.get('URL', pd.Series()).nunique()} paginas nuevas; acumulado "
          f"{df['URL'].nunique()}/{total} productos", flush=True)
    return df
