# Datinomics - Crawler de comercios y precios de Argentina

Sistema de relevamiento + extracción de precios de comercios online en las 24 jurisdicciones de Argentina.

## Estructura

```
_Nacional/                       # codigo y registros compartidos
├── relevar_provincia.py        # paso 1: descubre tiendas por provincia (curado nacional + ddgs)
├── limpiar_relevamientos.py    # paso 2: limpia ruido del relevamiento
├── agregar_curado.py           # paso 2b: agrega cadenas curadas a una provincia
├── etl.py                      # paso 3: entry point UNICO de scraping de precios
├── scrape_provincia.py         # (legacy) scraper sin dispatcher por Plataforma
├── scrape_todas.py             # cola secuencial por todas las provincias
├── cadenas_nacionales.csv      # registro de cadenas masters (no re-scrapea)
├── empresas_argentina.csv      # dataset inicial
├── provincias.geojson          # geometria provincias
└── scrapers/                   # paquete de scrapers de plataforma + dispatcher
    ├── __init__.py             # dispatch(plataforma, url, tienda)
    ├── shopify.py
    ├── vtex.py
    ├── tiendanube.py
    ├── woo.py
    ├── coto.py                 # custom Constructor.io
    └── playwright_fb.py        # fallback DOM/SPA

<Region>/<Provincia>/
├── excels/
│   ├── <Provincia>_full.xlsx        # relevamiento (input del ETL)
│   ├── precios_<Rubro>_<Provincia>.xlsx   # outputs por rubro, 1 hoja por local
│   └── ...
└── scripts/                          # solo si la provincia tiene customizacion propia
```

Los scripts de `NEA/Corrientes/scripts/` importan los scrapers y utilidades
compartidas (`scrapers/`, `verificar_cadenas.py`) desde `_Nacional/`.

5 regiones: NOA, NEA, Cuyo, Centro-Pampeana, Patagonia. 24 jurisdicciones (23 provincias + CABA).

## Flujo ETL (de cero para una provincia nueva)

```bash
cd _Nacional

# 1) Relevamiento (descubre tiendas con e-commerce)
py relevar_provincia.py <Folder>          # ej: Mendoza, Buenos-Aires, CABA

# 2) Limpieza (saca ruido: TLDs extranjeros, software, demos)
py limpiar_relevamientos.py

# 3) Scraping de precios (parametrizado)
py etl.py <Folder>                        # toma <Folder>_full.xlsx y dispatcha por Plataforma
py etl.py <Folder> --rubro Carnicerias    # solo un rubro
py etl.py <Folder> --excel ruta.xlsx      # override del input
py etl.py todas --paralelo 3              # cola por todas, 3 a la vez
```

## Cómo funciona el dispatcher

`etl.py` lee la columna `Plataforma` del `<Folder>_full.xlsx`. Para cada tienda:

| Plataforma en Excel | Scraper que corre |
|---|---|
| `shopify` | `scrapers/shopify.py` via `/products.json` |
| `vtex` | `scrapers/vtex.py` via catalog API (HTTP 206 + arbol full) |
| `tiendanube` | `scrapers/tiendanube.py` via HTML `/productos` |
| `woocommerce` / `woo` | `scrapers/woo.py` via `/wp-json/wc/store/products` por categoria |
| `magento` | `scrapers/playwright_fb.py` (fallback DOM) |
| `prestashop` | Woo si responde, sino Playwright |
| vacio / desconocido | **auto-detect**: prueba Shopify -> VTEX -> Tiendanube -> Woo |

Salida por rubro: `precios_<Rubro>_<Provincia>.xlsx` con hoja **Resumen** + 1 hoja por local. Columnas: `SKU, Nombre, Precio, Fecha, Categoria`.

## Cadenas nacionales (dedup)

`cadenas_nacionales.csv` registra cadenas con catálogo único nacional. Una vez scrapeadas en una provincia (MasterScrape=Corrientes), `etl.py` las **saltea automáticamente** en otras provincias. Para forzar: `--skip-nacional 0`.

## Plataformas custom

- **Coto** (`scrapers/coto.py`) — Constructor.io, key extraída del JS, precios por sucursal
- **Farmar** (en `NEA/Corrientes/scripts/scraper_farmar.py`) — API gateada, scrape via Playwright DOM

## Resultados acumulados (snapshot)

- **Relevamiento nacional**: Más de 18.000 tiendas con web en 24 jurisdicciones
- **Precios scrapeados**: ~5.000 locales (CABA 1.650 + BA 1.529 + Corrientes 624k SKUs en 8 supers + resto en curso)
- **Cadenas nacionales master**: ~20 (Carrefour, Coto, Dia, Cuspide, Fravega, etc.)

## Instalación

```bash
pip install -r requirements.txt
playwright install chromium
```

## Configuración

Copiá `.env.example` a `.env` y completá tu email de contacto. Se usa en el
User-Agent de los scrapers para que los sitios puedan identificar quién consulta.

```bash
cp .env.example .env        # en PowerShell: Copy-Item .env.example .env
```

| Variable | Qué es |
|---|---|
| `SCRAPER_CONTACT_EMAIL` | Email que va en el User-Agent de los crawlers |

El archivo `.env` está en `.gitignore` y no se sube al repo.

## Notas

- ddgs (DuckDuckGo) tiene rate-limit agresivo; los relevamientos pueden tardar horas.
- Los Excels de precios (`precios_*.xlsx`) NO se versionan (.gitignore). Se regeneran corriendo el ETL.
- Los relevamientos (`<Folder>_full.xlsx`) SÍ se versionan — son la fuente del ETL.

## Fuentes de datos

- Comercios: © colaboradores de OpenStreetMap, licencia [ODbL](https://www.openstreetmap.org/copyright).
- Límites provinciales: IGN / datos.gob.ar (georef).