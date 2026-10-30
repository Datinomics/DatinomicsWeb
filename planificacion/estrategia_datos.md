# Datinomics: estrategia de datos

Cómo se consiguen los precios, cómo se controla que estén bien y dónde corre todo hasta
que haya servidor. Sirve para todas las provincias y también para cualquier rubro o
fuente nueva.

---

## 1. De dónde salen los precios

| Capa | Fuente | Cobertura | Frecuencia | Script |
|---|---|---|---|---|
| Oficial | **SEPA** (supermercados que informan por ley) | ~16 cadenas, todas las sucursales del país | diaria (~16:20) | `sepa.py --descargar` |
| Scraping | **Tiendas propias** (Tiendanube, WooCommerce, VTEX, Shopify, Magento, PrestaShop) | comercios curados de cada provincia | diaria (de noche) | `diario.py scrape` |
| Scraping | **Cadenas nacionales** (Frávega, Farmacity, Easy, marcas de ropa…) | una sola vez para todo el país | diaria | `diario.py scrape --provincias _cadenas` |
| Externas | Granos (BCR), hacienda (Cañuelas), frutas y hortalizas (Mercado Central), combustibles (Sec. Energía), BCRA, medicamentos (Alfabeta) | nacional | diaria | `diario.py fuentes` |
| Externas | Inmuebles (ZonaProp) | CABA, Mendoza, Corrientes | semanal (lunes) | `diario.py fuentes` |

Regla: **si el comercio informa a SEPA en esa provincia, se usan los precios de SEPA y no se
scrapea.** Todo lo demás se scrapea.

Lo que no se hace: no se esquivan bloqueos anti-bots (Argenprop, Shopify con límite,
ZonaProp después de la página 10). Esos casos van a la lista de **acuerdos o APIs**
(MercadoLibre, Argenprop, Alfabeta con cuenta).

---

## 2. Modelo de trabajo por provincia

Cada provincia pasa por el mismo circuito. Se repite cuando se suman zonas o rubros, y una
vez por mes para limpiar los comercios que cerraron o se mudaron.

```
 1 RELEVAR  ─►  2 VERIFICAR  ─►  3 UBICAR  ─►  4 SCRAPEAR  ─►  5 DEPURAR  ─►  6 CONTROLAR  ─►  7 APROBAR
 (buscar)      (¿está en la     (ciudad /     (precios)      (sin precios,   (calidad)        (humano)
               provincia?)      partido /                    huérfanos)
                                barrio)
```

| Paso | Qué hace | Comando | Criterio |
|---|---|---|---|
| **1. Relevar** | Busca comercios por rubro y zona (ver §3). Guarda la zona de la búsqueda. Acumula y no repite búsquedas. | `relevar_provincia.py <Prov> --por-zona` | Un candidato entra si tiene tienda online detectable. |
| **2. Verificar** | Junta evidencia de ubicación: coordenadas del mapa, CPA, JSON-LD, dirección con localidad oficial (Georef), característica telefónica, OSM, SEPA, localizadores de sucursales. | `curar_provincia.py <Prov>` | **VERIFICADA** si suma ≥ 2 puntos para la provincia (fuerte = 3, media = 2, débil = 1) y ninguna otra provincia la supera. Si tiene más evidencia de otra provincia, queda **OTRA_UBICACION (X)**. Si el sitio lista sucursales en 4 o más provincias sin ser cadena, queda **AGREGADOR**. |
| **3. Ubicar** | Asigna Localidad y Departamento: barrio y comuna en CABA, partido en Buenos Aires, ciudad y departamento en el resto. | automático en `curar_provincia.py` | Se usan coordenadas antes que JSON-LD, JSON-LD antes que dirección, y dirección antes que el título. Las cadenas quedan como "Varias". |
| **4. Scrapear** | Baja el catálogo de los verificados. | automático (o `diario.py scrape`) | Hace falta al menos 1 producto con precio > 0. "Consultar precio" no cuenta. |
| **5. Depurar** | Saca de los Excel de precios los comercios sin precios y los que dejaron de estar verificados. | `control_calidad.py <Prov> --depurar` | — |
| **6. Controlar** | Calidad por comercio (§4). | `control_calidad.py <Prov>` | OK / REVISAR / ERROR |
| **7. Aprobar** | Una persona revisa `verificacion_<Prov>.xlsx` (muestra de 20 descartados y 20 verificados) y `calidad_<Prov>.xlsx` (los REVISAR). | manual | Error de ubicación en la muestra < 5 %; ningún comercio en ERROR. Recién ahí la provincia "sale" en la web. |

Archivos que quedan por provincia (`<Region>/<Prov>/excels/`):

- `<Prov>_full.xlsx` tiene 3 hojas: **Tiendas con web** (verificadas y con precios, con Localidad y Departamento), **Descartados (ubicación)** con el motivo, y **Descartados (sin datos)**.
- `verificacion_<Prov>.xlsx` guarda la evidencia de cada comercio, para auditar.
- `reporte_curado_<Prov>.json` tiene embudo, tiempos y plataformas.
- `precios_<Rubro>_<Prov>.xlsx` y `precios_SEPA_<Prov>.xlsx` tienen los precios.

**Errores típicos que este circuito ataja** (todos vistos en los datos actuales):

- Comercios de otra provincia en el Excel: en Chaco quedaron 93 de 1.279, y en Catamarca 66 de 691.
- Rubro mal asignado, porque la búsqueda lo trajo por otra palabra: "Banderín San Telmo" figuraba como farmacia, "BENKA" como supermercado.
- Tiendas que publican todo a $0 ("consultar precio"): 32 comercios en CABA, Mendoza y Corrientes.
- Datos viejos en fuentes oficiales: el dataset de combustibles trae precios de 2016. Solo se toma lo informado en los últimos 60 días.

---

## 3. Granularidad: dónde se busca

| Provincia | Zonas de búsqueda | Cantidad |
|---|---|---|
| Buenos Aires | Todos los **partidos** (Georef/INDEC) | 135 |
| CABA | Todos los **barrios** (GCBA) | 48 |
| Resto | **Ciudades principales**, al menos 3 (censo 2022) | 3 a 8 por provincia |

En cada zona se buscan los 16 rubros principales, más verdulería, dietética y una búsqueda
general. Las tablas oficiales están en `_Nacional/geo/` y se actualizan con
`py geografia.py --descargar`.

La zona donde apareció un comercio en la búsqueda no prueba dónde está. La ubicación
que vale es la del paso 3, que sale de la evidencia.

---

## 4. Control de calidad

Por cada comercio, en cada corrida:

| Chequeo | Umbral | Resultado |
|---|---|---|
| Sin ningún precio > 0 | — | ERROR (se depura) |
| Comercio con datos pero ya no verificado | — | ERROR (se depura) |
| Menos de 5 productos | < 5 | REVISAR |
| Productos sin precio | > 30 % | REVISAR |
| SKU duplicado | > 10 % | REVISAR |
| Precio extremo respecto de la mediana del comercio | × 200 o ÷ 200 | REVISAR |
| Precio fuera de rango | < $10 o > $200 M | REVISAR |
| Rubro dudoso (palabras típicas del rubro) | < 10 % propio y ≥ 25 % de otro | REVISAR, con rubro sugerido |
| Sin relevar | > 7 días | REVISAR |

Contra la corrida anterior (`diario.py calidad`):

- comercios que dejaron de traer datos;
- productos con salto de precio mayor al 50 %;
- variación mediana del día.

Fuentes externas: filas, nulos, rango esperable por fuente y frescura.

Para SEPA se controlan precios en 0, mínimo mayor que máximo y dispersión entre sucursales
mayor a 5 veces.

---

## 5. Dónde corre (sin servidor)

**GitHub Actions** (`.github/workflows/extraccion_diaria.yml`), todos los días a las 21:30
de Argentina:

1. **fuentes-y-sepa**: fuentes externas y paquete SEPA del día (~10 min).
2. **scrape**: una tarea por provincia y otra para las cadenas nacionales, 10 en paralelo.
   Cada una tiene un tope de 5 horas. Corrientes completa tarda unos 6½ minutos.
3. **calidad**: une todo, controla y compara con el día anterior. El resumen queda en la página del run.

| Tema | Decisión |
|---|---|
| Costo | **$0**. El repo es público y en repos públicos los minutos de Actions son ilimitados. |
| Dónde quedan los datos | Siempre como *artifacts* del run, que duran 90 días. Para el histórico permanente: **Cloudflare R2**, con 10 GB gratis y sin costo de descarga. Se activa cargando los secrets `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`, `R2_ENDPOINT` y `R2_BUCKET`. |
| Formato | Parquet (zstd) por día: `diario/<fecha>/precios_<Prov>.parquet`. Los Excel son solo para revisar a mano. |
| Volumen estimado | 2 a 5 millones de filas por día en todo el país, unos 50 a 100 MB por día. Para que R2 alcance más tiempo, el histórico guarda **solo los cambios de precio** y una foto completa por semana. |
| Secretos | `ALFABETA_USUARIO` / `ALFABETA_CLAVE` y R2 se cargan en *Settings → Secrets*. Nunca van en el repo. |

**Atención: el repo es público.** Hoy los Excel de comercios y de precios del repo los
puede ver cualquiera. Opciones:

- **(a)** Dejar el código público y sacar los Excel del repo. Pasan a R2 o a un repo privado de datos.
- **(b)** Hacer privado el repo. En ese caso Actions da 2.000 minutos por mes, que no alcanzan para scrapear todo el país todos los días. Habría que rotar: supermercados y farmacias a diario, y el resto un séptimo por día con `--shard k/7`.

La recomendación es **(a)**.

Límites que hay que tener presentes:

- Algunos sitios bloquean las IPs de datacenter, como las de GitHub. Si un comercio
  falla siempre en Actions y anda desde la PC, va a la lista de acuerdos; no se esquiva
  el bloqueo.
- Shopify limita el catálogo por tienda. Por eso la corrida es de noche, con 3 a 5
  segundos entre pedidos.

---

## 6. Próximos pasos hacia la app

1. **Cerrar la curación nacional.** Las 20 provincias restantes están corriendo. Después
   vienen Buenos Aires (135 partidos) y CABA (48 barrios) con el relevamiento por zona.
   Al final, la aprobación manual de cada provincia (paso 7).
2. **Activar la corrida diaria.** Hay que commitear y pushear, cargar los secrets de R2 y
   hacer una corrida manual (*Run workflow*) para medir tiempos reales.
3. **Base de datos.** Se carga diariamente desde los parquet. Para empezar alcanza con
   **DuckDB sobre R2**, sin servidor. Cuando haya API pública: Postgres administrado
   (Supabase o Neon) con solo el último precio y los agregados; el histórico queda en
   parquet.
4. **Matching de productos.** Primero por EAN (SEPA y muchas tiendas lo tienen) y después
   por nombre, marca y presentación. Sin esto no hay comparador.
5. **API y front.** Una API (FastAPI) sobre esa base, y el front (`front/platform`)
   conectado a la API en lugar de `data.js`.
