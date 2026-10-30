# -*- coding: utf-8 -*-
"""Precios de MercadoLibre por la API oficial, con el token de aplicacion (client_credentials).

La busqueda de publicaciones (/sites/MLA/search) esta cerrada para apps comunes (403); lo
que si se puede es el catalogo: /products/search encuentra el producto de catalogo y
/products/{id}/items devuelve las ofertas de cada vendedor con su precio. Una fila por
oferta: producto, marca, GTIN, vendedor, precio, condicion, envio gratis, tienda oficial.

Credenciales (entorno o .env): ML_CLIENT_ID, ML_CLIENT_SECRET.
Las consultas salen de CANASTA (o se pasan con consultas=[...])."""
import concurrent.futures as cf
import os
import time

import pandas as pd

from . import HOY, RAIZ, Ritmo, sesion

API = "https://api.mercadolibre.com"
CANASTA = [
    # alimentos y bebidas
    "yerba mate 1kg", "aceite girasol 1.5 litros", "arroz largo fino 1kg", "fideos spaghetti 500g",
    "harina 000 1kg", "azucar 1kg", "leche larga vida 1 litro", "cafe molido 500g", "galletitas de agua",
    "dulce de leche 400g", "atun en lata", "gaseosa cola 2.25 litros", "agua mineral 2 litros",
    # bebidas alcoholicas
    "vino malbec 750ml", "cerveza lata 473ml", "fernet 750ml",
    # limpieza y cuidado personal
    "detergente 750ml", "jabon en polvo 3kg", "lavandina 2 litros", "papel higienico 4 rollos",
    "shampoo 400ml", "pasta dental 90g", "desodorante aerosol", "panales talle g",
    # hogar y electro
    "heladera no frost", "lavarropas automatico 8kg", "smart tv 50 pulgadas", "aire acondicionado split 3000",
    "microondas 20 litros", "notebook 15 pulgadas", "celular samsung galaxy a", "auriculares bluetooth",
    "colchon 2 plazas", "juego de sabanas 2 plazas",
    # indumentaria
    "zapatillas running hombre", "jean hombre", "remera algodon",
    # salud, mascotas, auto, construccion
    "ibuprofeno 400", "alimento perro adulto 15kg", "piedras sanitarias gato",
    "neumatico 175/65 r14", "aceite motor 10w40 4 litros", "bateria auto 12x65",
    "cemento 50kg", "pintura latex interior 20 litros", "taladro percutor",
]


def _token(s):
    try:
        from dotenv import load_dotenv
        load_dotenv(os.path.join(RAIZ, ".env"))
    except ImportError:
        pass
    cid, sec = os.environ.get("ML_CLIENT_ID"), os.environ.get("ML_CLIENT_SECRET")
    if not (cid and sec):
        raise RuntimeError("Faltan ML_CLIENT_ID / ML_CLIENT_SECRET (entorno o .env)")
    r = s.post(f"{API}/oauth/token", data={"grant_type": "client_credentials", "client_id": cid,
                                            "client_secret": sec}, timeout=30)
    r.raise_for_status()
    return r.json()["access_token"]


def _get(s, ritmo, path, params=None):
    for intento in range(4):
        ritmo.esperar()
        r = s.get(f"{API}{path}", params=params, timeout=30)
        if r.status_code == 429:  # se respeta el limite de la API
            time.sleep(10 * (intento + 1))
            continue
        return r
    return r


def _producto(s, ritmo, consulta, p):
    r = _get(s, ritmo, f"/products/{p['id']}/items")
    if r.status_code != 200:
        return []
    attrs = {a.get("id"): a.get("value_name") for a in p.get("attributes", [])}
    return [{"Fecha": HOY, "Consulta": consulta, "Producto_id": p["id"], "Producto": p.get("name"),
             "Dominio": p.get("domain_id"), "Marca": attrs.get("BRAND"), "Modelo": attrs.get("MODEL"),
             "GTIN": attrs.get("GTIN"), "Item_id": it.get("item_id"), "Precio": it.get("price"),
             "Precio_original": it.get("original_price"), "Moneda": it.get("currency_id"),
             "Vendedor_id": it.get("seller_id"), "Condicion": it.get("condition"),
             "Envio_gratis": (it.get("shipping") or {}).get("free_shipping"),
             "Tienda_oficial": it.get("official_store_id"), "Tipo_publicacion": it.get("listing_type_id"),
             "Provincia_vendedor": ((it.get("seller_address") or {}).get("state") or {}).get("name")}
            for it in r.json().get("results", [])]


def descargar(consultas=None, productos_por_consulta=20, hilos=4, segundos=0.25, limite=0, **_):
    """limite: solo las primeras N consultas (prueba)."""
    s = sesion(hilos)
    s.headers["Authorization"] = f"Bearer {_token(s)}"
    ritmo = Ritmo(segundos)
    consultas_ = list(consultas or CANASTA)[: limite or None]
    tareas = []
    for q in consultas_:
        r = _get(s, ritmo, "/products/search", {"site_id": "MLA", "q": q, "status": "active",
                                                 "limit": productos_por_consulta})
        if r.status_code != 200:
            print(f"  mercadolibre '{q}': HTTP {r.status_code}", flush=True)
            continue
        tareas += [(q, p) for p in r.json().get("results", [])]
    with cf.ThreadPoolExecutor(hilos) as ex:
        filas = [f for parte in ex.map(lambda t: _producto(s, ritmo, *t), tareas) for f in parte]
    df = pd.DataFrame(filas)
    if not df.empty:
        df["Fuente"] = "MercadoLibre (API)"
    print(f"  mercadolibre: {len(consultas_)} consultas, {len(tareas)} productos de catalogo, "
          f"{len(df)} ofertas", flush=True)
    return df
