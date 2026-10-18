# -*- coding: utf-8 -*-
"""
Limpia un checkpoint de descubrimiento de webs y arma un Excel.

Regla: una web es "especifica" (buena) si en el dominio aparece un token
PROPIO del nombre (no una palabra generica del rubro). Si solo coincide una
palabra generica (policonsultorio, instituto, sanatorio, etc.), va a "Dudosos".
Las webs que vienen de OSM se consideran confiables.

Uso:  py limpiar_webs.py <checkpoint.csv> [salida.xlsx]
"""
import re
import sys
import unicodedata
import pandas as pd

GENERICOS = {
    "policonsultorio", "consultorio", "instituto", "sanatorio", "asociacion",
    "sociedad", "clinica", "hospital", "farmacia", "banco", "hotel", "motel",
    "supermercado", "autoservicio", "almacen", "kiosco", "panaderia", "carniceria",
    "verduleria", "restaurante", "parrilla", "pizzeria", "escuela", "colegio",
    "universidad", "jardin", "ferreteria", "muebleria", "inmobiliaria", "estudio",
    "agencia", "centro", "club", "cooperativa", "mutual", "fundacion", "camara",
    "distribuidora", "comercial", "automotores", "automotor", "externo",
    "odontologico", "odontologica", "medico", "medica", "veterinaria", "optica",
    "libreria", "papeleria", "joyeria", "relojeria", "peluqueria", "gimnasio",
    "deportes", "pinturas", "pintureria", "corralon", "vivero", "floreria",
    "heladeria", "confiteria", "fiambreria", "pescaderia", "bazar", "regaleria",
    "turismo", "viajes", "remis", "remises", "taller", "gomeria", "lavadero",
    "tienda", "shopping", "galeria", "mercado", "feria", "negocio", "empresa",
    "servicios", "construccion", "materiales", "hogar", "electro", "electronica",
    "telefonia", "computacion", "informatica", "indumentaria", "calzado",
    # geograficos (provincia, ciudades, regiones) y palabras comunes que
    # generan matches con dominios ajenos
    "corrientes", "litoral", "argentina", "capital", "provincia", "nacional",
    "region", "ciudad", "pueblo", "villa", "barrio", "norte", "sur", "este",
    "oeste", "goya", "mercedes", "curuzu", "cuatia", "libres", "paso", "santo",
    "tome", "ituzaingo", "bella", "vista", "esquina", "saladas", "alvear",
    "empedrado", "alta", "gracia", "nuevo", "nueva", "plaza", "real", "central",
    "liga", "casino", "casinos", "relax", "sucursal", "sucursales", "local",
}

# Dominios que NO son el sitio oficial de un negocio (noticias, directorios,
# agregadores) aunque hayan colado un token del nombre.
DIRECTORIOS = (
    "aldia", "noticias", "diario", "infobae", "lanacion", "clarin", "ellitoral",
    "ligasde", "findcasino", "clinicasen", "establecimientosdesalud", "guia",
    "paginas", "infoisinfo", "cylex", "cybo", "opendi", "hotfrog", "yalwa",
    "tripadvisor", "booking", "despegar", "trivago", "zonaprop", "argenprop",
    "mapcarta", "moovit", "cuitonline", "dateas", "blogspot", "wordpress.com",
    "corrientesaldia", "corrientesya", "corrienteshoy", "primeraedicion",
    "labancaria", "edu.ar", "gob.ar", "gov.ar", "wikipedia", ".madrid",
)


def norm(s):
    s = unicodedata.normalize("NFKD", str(s))
    return "".join(c for c in s if not unicodedata.combining(c)).strip().lower()


LEGALES = {"srl", "sa", "sas", "sh", "scs", "ltda", "coop", "saci", "sacif"}
SUFIJOS = (".com.ar", ".org.ar", ".net.ar", ".gob.ar", ".edu.ar", ".tur.ar",
           ".gov.ar", ".com", ".net", ".org", ".info", ".site", ".online",
           ".store", ".app", ".ar", ".io", ".co", ".biz", ".tienda", ".shop",
           ".lat", ".one")


def host_de(url):
    try:
        d = url.split("//")[-1].split("/")[0]
        return re.sub(r"[^a-z0-9]", "", d.lower().replace("www.", ""))
    except Exception:
        return ""


def core_dominio(url):
    """Nucleo registrable del dominio (la etiqueta antes del sufijo publico)."""
    host = url.split("//")[-1].split("/")[0].lower()
    if host.startswith("www."):
        host = host[4:]
    for suf in sorted(SUFIJOS, key=len, reverse=True):
        if host.endswith(suf):
            host = host[:-len(suf)]
            break
    label = host.split(".")[-1] if host else ""   # ignora subdominios
    return re.sub(r"[^a-z0-9]", "", label)


# Sufijos que suelen ir pegados al nombre en el dominio: lugares (lareina+corrientes)
# y palabras de sitio (lareina+web / +online / +oficial)
GEO_SUF = ("corrientes", "litoral", "goya", "mercedes", "curuzucuatia", "curuzu",
           "cuatia", "pasodeloslibres", "libres", "santotome", "tome", "ituzaingo",
           "bellavista", "esquina", "saladas", "capital", "argentina", "arg",
           "web", "online", "oficial", "tienda", "shop", "store", "digital",
           "online", "ventas", "ecommerce")


def quitar_geo_sufijo(core):
    """Quita un nombre de lugar pegado al final del nucleo (nombre+lugar)."""
    for g in sorted(GEO_SUF, key=len, reverse=True):
        if core.endswith(g) and len(core) > len(g) + 2:
            return core[:-len(g)]
    return core


def clasificar(nombre, url, fuente):
    if fuente == "OSM":
        return "Alta", "OSM"
    host_full = url.split("//")[-1].split("/")[0].lower()
    if any(d in host_full for d in DIRECTORIOS):
        return "Dudoso", "directorio/noticia"

    core = core_dominio(url)
    core2 = quitar_geo_sufijo(core)   # nucleo sin el lugar pegado
    toks = [t for t in re.split(r"[^a-z0-9]+", norm(nombre)) if t]
    dist = [t for t in toks if t not in GENERICOS and t not in LEGALES and len(t) >= 3]
    concat_all = "".join(t for t in toks if t not in LEGALES)
    concat_dist = "".join(dist)

    # Confiable: el nucleo del dominio ES el nombre (completo, sin genericas, o nombre+lugar)
    # Se compara con y->i para tolerar variantes (reyna/reina, etc.)
    yi = lambda s: s.replace("y", "i")
    objetivos = {yi(concat_all), yi(concat_dist)}
    objetivos.discard("")
    if core and (yi(core) in objetivos or yi(core2) in objetivos):
        return "Alta", "nucleo = nombre"
    # Para revisar: un token propio (>=5, no generico/geografico) esta en el nucleo
    propios = [t for t in dist if len(t) >= 5 and t in core]
    if propios:
        return "Media", "coincidencia parcial"
    return "Dudoso", "sin match claro"


def main():
    ckpt = sys.argv[1] if len(sys.argv) > 1 else "webs_corrientes_checkpoint.csv"
    salida = sys.argv[2] if len(sys.argv) > 2 else "webs_corrientes_avance.xlsx"

    df = pd.read_csv(ckpt).fillna("")
    total = len(df)
    # excluir bancos y gobierno (por pedido)
    EXCL_SECT = {"banco", "government", "gobierno", "townhall", "courthouse",
                 "public building", "political party"}
    sect = df["Sector"].astype(str).str.lower()
    df = df[~sect.isin(EXCL_SECT)].copy()

    tiene_web = df["Pagina web"].astype(str).str.len() > 0

    # clasificar solo los que tienen web; el resto queda en blanco
    def fila(r):
        if str(r["Pagina web"]).strip() == "":
            return pd.Series(["", "sin web"])
        return pd.Series(clasificar(r["Nombre"], r["Pagina web"], r["Fuente web"]))
    df[["Conf2", "Motivo"]] = df.apply(fila, axis=1)

    # dominios compartidos por muchos negocios DISTINTOS (sospechoso) -> Dudoso
    df["host"] = df["Pagina web"].map(host_de)
    web = df[tiene_web]
    npm = web.groupby("host")["Nombre"].apply(lambda s: s.map(norm).nunique())
    df["host_compartido"] = df["host"].map(npm).fillna(0)
    mask = (tiene_web & (df["host_compartido"] >= 4) & (df["Conf2"] != "Alta"))
    df.loc[mask, "Conf2"] = "Dudoso"
    df.loc[mask, "Motivo"] = "dominio compartido por muchos negocios"

    cols = ["Nombre", "Sector", "Pagina web", "Conf2", "Motivo", "Fuente web",
            "Ciudad", "Telefono"]
    ren = {"Conf2": "Confianza"}
    todos = df[cols].rename(columns=ren).sort_values(
        ["Sector", "Ciudad", "Nombre"], kind="stable")
    bueno = df[df["Conf2"] == "Alta"][cols].rename(columns=ren).sort_values(
        ["Ciudad", "Sector", "Nombre"], kind="stable")
    revisar = df[df["Conf2"].isin(["Media", "Dudoso"])][cols].rename(
        columns=ren).sort_values(["Confianza", "Ciudad", "Nombre"], kind="stable")

    with pd.ExcelWriter(salida, engine="openpyxl") as xl:
        todos.to_excel(xl, sheet_name="Todos los comercios", index=False)
        bueno.to_excel(xl, sheet_name="Con web (confiable)", index=False)
        revisar.to_excel(xl, sheet_name="Para revisar", index=False)
        for sh in xl.sheets.values():
            for col, w in zip("ABCDEFGH", (36, 20, 42, 10, 28, 12, 18, 16)):
                sh.column_dimensions[col].width = w
            sh.freeze_panes = "A2"

    media = (revisar["Confianza"] == "Media").sum()
    print(f"Comercios (sin bancos/gobierno):   {len(df)}  (de {total} procesados)")
    print(f"  con alguna web:        {tiene_web.sum()}")
    print(f"  sin web:               {(~tiene_web).sum()}")
    print(f"  CONFIABLES (Alta):     {len(bueno)}")
    print(f"     - desde OSM:        {(bueno['Fuente web']=='OSM').sum()}")
    print(f"     - nucleo=nombre web:{(bueno['Fuente web']=='Web').sum()}")
    print(f"  Para revisar (Media):  {media}")
    print(f"  Descartables (Dudoso): {len(revisar)-media}")
    print(f"Guardado: {salida}")


if __name__ == "__main__":
    main()
