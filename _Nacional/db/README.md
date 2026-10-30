# Base de datos de Datinomics (PostgreSQL)

Todo vive en el esquema `datinomics`. La definición está en [schema.sql](schema.sql) y la
carga en [cargar_db.py](cargar_db.py).

```
py _Nacional/db/cargar_db.py --crear-db          # primera vez: crea la base, el esquema y carga todo
py _Nacional/db/cargar_db.py                     # recarga (idempotente: upsert)
py _Nacional/db/cargar_db.py --provincias CABA --solo comercios precios
py _Nacional/diario.py scrape calidad db         # corrida diaria + carga
```

La conexión se toma de `DATABASE_URL` en `.env`.

## Modelo

```
provincia 1─* localidad                      (ciudad / partido / barrio + departamento o comuna)
    │
    └─* comercio_provincia *─1 comercio *─1 rubro
              (estado, verificación,           (dominio único; fuente = scraping | sepa)
               evidencia, localidad)                │
                                                    1
                                                    *
                                                 producto 1─* precio      (serie diaria, particionada por mes)

corrida            cada carga: tipo, alcance, filas, detalle
calidad_comercio   control de calidad por día y comercio (OK / REVISAR / ERROR + alertas)
granos · hacienda · frutas_hortalizas · combustible · bcra · medicamento · inmueble   (fuentes externas)
```

| Tabla | Clave | Qué guarda |
|---|---|---|
| `provincia` | `id` (código INDEC) | 24 provincias. El `id` 0 se usa para el precio online único. |
| `localidad` | `(provincia_id, departamento, nombre)` | Datos de Georef y barrios de CABA. |
| `comercio` | `dominio` | Un sitio web o una bandera SEPA (`sepa:<bandera>`). |
| `comercio_provincia` | `(comercio_id, provincia_id)` | Resultado del curado: `activo`, `descartado_ubicacion`, `descartado_sin_datos` o `candidato`. |
| `producto` | `(comercio_id, sku)` | Catálogo de cada comercio. En SEPA el `sku` es el EAN. |
| `precio` | `(producto_id, provincia_id, fecha)` | Precio del día. En scraping va con `provincia_id = 0`. En SEPA hay un registro por provincia, con precio = mediana más mínimo y máximo entre sucursales. |

## Vistas para el backend

| Vista | Uso |
|---|---|
| `v_comercio` | Comercios activos con rubro, provincia, localidad, cantidad de productos y último relevo. Sirve para las pantallas *Empresas* y *Explorador*. |
| `v_precio_actual` | Último precio de cada producto (por provincia en SEPA). |
| `v_producto` | Producto con su comercio, rubro y precio vigente. Sirve para *Comparador* y búsqueda. |
| `v_resumen_provincia_rubro` | Comercios y productos por provincia y rubro, para el tablero. |

Consultas típicas:

```sql
SET search_path TO datinomics;

-- buscar un producto en una provincia (SEPA de la provincia + tiendas online)
SELECT nombre, comercio, precio, fecha FROM v_producto
WHERE nombre ILIKE '%yerba%500%' AND (provincia_id = 18 OR provincia_id IS NULL)
ORDER BY precio;

-- serie de precios de un producto
SELECT fecha, precio FROM precio WHERE producto_id = $1 AND provincia_id = 0 ORDER BY fecha;

-- comercios de un barrio de CABA
SELECT nombre, rubro, productos FROM v_comercio WHERE provincia_id = 2 AND localidad = 'Palermo';
```

Para crecer: cuando el volumen pese, `v_precio_actual` puede pasar a vista
materializada que se refresca en el paso `db` de la corrida diaria. El histórico viejo
puede quedar en parquet (R2), y en Postgres solo los últimos meses, que es fácil de hacer
porque `precio` está particionada por mes.
