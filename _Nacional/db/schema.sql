-- Datinomics: modelo de datos (PostgreSQL 14+). Idempotente: se puede correr de nuevo.
--
--   geografia      provincia -> localidad (ciudad / partido / barrio)
--   comercios      rubro, comercio (un sitio / una bandera SEPA), comercio_provincia
--                  (donde esta verificado, con su zona y evidencia)
--   precios        producto (catalogo de cada comercio) y precio (serie diaria,
--                  particionada por mes)
--   fuentes        tablas propias por fuente externa (granos, hacienda, ...)
--   operacion      corrida (cada carga) y calidad_comercio (control de calidad)
--   lectura        vistas v_* pensadas para el backend
CREATE SCHEMA IF NOT EXISTS datinomics;
SET search_path TO datinomics, public;
CREATE EXTENSION IF NOT EXISTS pg_trgm;   -- busqueda de productos por nombre

-- ---------------------------------------------------------------- geografia
CREATE TABLE IF NOT EXISTS provincia (
    id          smallint PRIMARY KEY,           -- codigo INDEC (02 CABA, 06 Buenos Aires, ...)
    letra       char(1)  NOT NULL UNIQUE,       -- ISO 3166-2:AR / letra del CPA
    folder      text     NOT NULL UNIQUE,       -- carpeta del repo (Buenos-Aires, CABA, ...)
    nombre      text     NOT NULL,
    region      text     NOT NULL              -- NOA, NEA, Cuyo, Centro-Pampeana, Patagonia
);

CREATE TABLE IF NOT EXISTS localidad (
    id            serial PRIMARY KEY,
    provincia_id  smallint NOT NULL REFERENCES provincia(id),
    departamento  text NOT NULL DEFAULT '',    -- partido (Buenos Aires), comuna (CABA), departamento
    nombre        text NOT NULL,               -- ciudad / localidad; en CABA el barrio
    tipo          text NOT NULL DEFAULT 'localidad' CHECK (tipo IN ('localidad', 'barrio')),
    lat           double precision,
    lon           double precision,
    UNIQUE (provincia_id, departamento, nombre)
);

-- ---------------------------------------------------------------- comercios
CREATE TABLE IF NOT EXISTS rubro (
    id      smallserial PRIMARY KEY,
    nombre  text NOT NULL UNIQUE                -- Supermercados, Farmacias, ...
);

CREATE TABLE IF NOT EXISTS comercio (
    id          serial PRIMARY KEY,
    dominio     text NOT NULL UNIQUE,           -- clave natural: dominio web o 'sepa:<bandera>'
    nombre      text NOT NULL,
    url         text,
    rubro_id    smallint REFERENCES rubro(id),
    sector      text,                           -- sector original del relevamiento
    plataforma  text,                           -- tiendanube, vtex, woocommerce, shopify, sepa, ...
    es_cadena   boolean NOT NULL DEFAULT false,
    fuente      text NOT NULL DEFAULT 'scraping' CHECK (fuente IN ('scraping', 'sepa')),
    creado      timestamptz NOT NULL DEFAULT now(),
    actualizado timestamptz NOT NULL DEFAULT now()
);

-- presencia de un comercio en una provincia, con el resultado del curado
CREATE TABLE IF NOT EXISTS comercio_provincia (
    comercio_id   integer  NOT NULL REFERENCES comercio(id) ON DELETE CASCADE,
    provincia_id  smallint NOT NULL REFERENCES provincia(id),
    estado        text NOT NULL CHECK (estado IN ('activo', 'descartado_ubicacion', 'descartado_sin_datos',
                                                  'candidato')),
    verificacion  text,                         -- VERIFICADA, OTRA_UBICACION (X), SIN_EVIDENCIA, ...
    motivo        text,
    evidencia     text,
    localidad_id  integer REFERENCES localidad(id),
    metodo_zona   text,                         -- coordenadas, direccion, jsonld_direccion, ...
    zona_busqueda text,                         -- donde aparecio en el relevamiento
    sucursales    integer,                      -- SEPA: sucursales en la provincia
    actualizado   timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (comercio_id, provincia_id)
);
CREATE INDEX IF NOT EXISTS comercio_provincia_prov ON comercio_provincia (provincia_id, estado);

-- ---------------------------------------------------------------- precios
CREATE TABLE IF NOT EXISTS producto (
    id           bigserial PRIMARY KEY,
    comercio_id  integer NOT NULL REFERENCES comercio(id) ON DELETE CASCADE,
    sku          text NOT NULL,                 -- SKU del sitio; EAN en SEPA; md5(nombre) si no hay
    nombre       text NOT NULL,
    ean          text,
    marca        text,
    presentacion text,
    categoria    text,
    primera_vez  date NOT NULL DEFAULT current_date,
    ultima_vez   date NOT NULL DEFAULT current_date,
    UNIQUE (comercio_id, sku)
);
CREATE INDEX IF NOT EXISTS producto_ean ON producto (ean) WHERE ean IS NOT NULL;
CREATE INDEX IF NOT EXISTS producto_nombre_trgm ON producto USING gin (nombre gin_trgm_ops);

-- una fila por producto, dia y provincia. provincia_id = 0: precio unico online (scraping);
-- SEPA trae un precio por provincia (min / mediana / max entre sucursales).
CREATE TABLE IF NOT EXISTS precio (
    producto_id   bigint   NOT NULL,
    fecha         date     NOT NULL,
    provincia_id  smallint NOT NULL DEFAULT 0,
    precio        numeric(14, 2) NOT NULL CHECK (precio > 0),   -- scraping: precio; SEPA: mediana
    precio_min    numeric(14, 2),
    precio_max    numeric(14, 2),
    sucursales    integer,
    en_promo      integer,                      -- SEPA: sucursales con promocion
    corrida_id    integer,
    PRIMARY KEY (producto_id, provincia_id, fecha)
) PARTITION BY RANGE (fecha);
CREATE INDEX IF NOT EXISTS precio_fecha ON precio (fecha);
-- las particiones mensuales (precio_2026_10, ...) las crea cargar_db.py segun las fechas que carga

-- ---------------------------------------------------------------- operacion
CREATE TABLE IF NOT EXISTS corrida (
    id        serial PRIMARY KEY,
    tipo      text NOT NULL,                    -- curado, scraping, sepa, fuente:<nombre>, calidad
    alcance   text,                             -- provincia o fuente
    fecha     date NOT NULL,
    inicio    timestamptz NOT NULL DEFAULT now(),
    fin       timestamptz,
    filas     integer,
    estado    text NOT NULL DEFAULT 'en curso',
    detalle   jsonb
);

CREATE TABLE IF NOT EXISTS calidad_comercio (
    fecha         date     NOT NULL,
    comercio_id   integer  NOT NULL REFERENCES comercio(id) ON DELETE CASCADE,
    provincia_id  smallint NOT NULL REFERENCES provincia(id),
    estado        text NOT NULL CHECK (estado IN ('OK', 'REVISAR', 'ERROR')),
    alertas       text,
    productos     integer,
    rubro_sugerido text,
    metricas      jsonb,
    PRIMARY KEY (fecha, comercio_id, provincia_id)
);

-- ---------------------------------------------------------------- fuentes externas
CREATE TABLE IF NOT EXISTS granos (
    fecha date NOT NULL, grano text NOT NULL, plaza text NOT NULL,
    precio_ars_tn numeric(14, 2), precio_usd_tn numeric(14, 2), estimado boolean,
    PRIMARY KEY (fecha, grano, plaza)
);

CREATE TABLE IF NOT EXISTS hacienda (
    fecha date NOT NULL, plaza text NOT NULL, grupo text NOT NULL DEFAULT '', categoria text NOT NULL,
    minimo numeric(14, 2), maximo numeric(14, 2), promedio numeric(14, 2), mediana numeric(14, 2),
    cabezas integer, importe numeric(18, 2), kgs numeric(14, 2), kgs_prom numeric(10, 2), unidad text,
    PRIMARY KEY (fecha, plaza, grupo, categoria)
);

CREATE TABLE IF NOT EXISTS frutas_hortalizas (
    fecha date NOT NULL, rubro text NOT NULL, especie text NOT NULL, variedad text NOT NULL DEFAULT '',
    procedencia text NOT NULL DEFAULT '', envase text NOT NULL DEFAULT '', calidad text NOT NULL DEFAULT '',
    tamano text NOT NULL DEFAULT '', grado text NOT NULL DEFAULT '', kg_bulto numeric(10, 2),
    max_bulto numeric(14, 2), frecuente_bulto numeric(14, 2), min_bulto numeric(14, 2),
    max_kg numeric(14, 2), frecuente_kg numeric(14, 2), min_kg numeric(14, 2),
    PRIMARY KEY (fecha, rubro, especie, variedad, procedencia, envase, calidad, tamano, grado)
);

CREATE TABLE IF NOT EXISTS combustible (
    fecha_vigencia timestamp NOT NULL, idempresa integer NOT NULL, producto text NOT NULL,
    horario text NOT NULL, precio numeric(10, 3) NOT NULL,
    empresa text, bandera text, cuit text, direccion text, localidad text,
    provincia_id smallint REFERENCES provincia(id), lat double precision, lon double precision,
    PRIMARY KEY (idempresa, producto, horario, fecha_vigencia)
);

CREATE TABLE IF NOT EXISTS bcra (
    fecha date NOT NULL, tipo text NOT NULL, serie text NOT NULL,   -- serie = idVariable o moneda
    descripcion text, valor numeric(24, 6), unidad text, categoria text, periodicidad text,
    PRIMARY KEY (tipo, serie, fecha)
);

CREATE TABLE IF NOT EXISTS medicamento (
    url text NOT NULL, presentacion text NOT NULL, vigencia date,
    producto text, laboratorio text, droga text, accion text, precio numeric(14, 2), relevado date,
    PRIMARY KEY (url, presentacion)
);

CREATE TABLE IF NOT EXISTS inmueble (
    fuente text NOT NULL, aviso_id text NOT NULL, relevado date NOT NULL,
    operacion text, tipo text, busqueda text, titulo text,
    precio numeric(16, 2), moneda text, expensas numeric(14, 2),
    sup_total_m2 numeric(12, 2), sup_cubierta_m2 numeric(12, 2),
    ambientes numeric(5, 1), dormitorios numeric(5, 1), banos numeric(5, 1),
    direccion text, barrio text, ciudad text, lat double precision, lon double precision,
    inmobiliaria text, url text,
    PRIMARY KEY (fuente, aviso_id, relevado)
);

-- ---------------------------------------------------------------- vistas para el backend
-- ultimo precio de cada producto (por provincia en SEPA; provincia 0 = online)
CREATE OR REPLACE VIEW v_precio_actual AS
SELECT DISTINCT ON (p.producto_id, p.provincia_id)
       p.producto_id, p.provincia_id, p.fecha, p.precio, p.precio_min, p.precio_max, p.sucursales
FROM precio p
ORDER BY p.producto_id, p.provincia_id, p.fecha DESC;

-- comercios activos con su ubicacion y tamaño de catalogo
CREATE OR REPLACE VIEW v_comercio AS
SELECT c.id AS comercio_id, c.nombre, c.dominio, c.url, c.plataforma, c.fuente, c.es_cadena,
       r.nombre AS rubro, pr.id AS provincia_id, pr.nombre AS provincia, pr.region,
       l.nombre AS localidad, l.departamento, cp.metodo_zona, cp.verificacion, cp.sucursales,
       (SELECT count(*) FROM producto x WHERE x.comercio_id = c.id) AS productos,
       (SELECT max(x.ultima_vez) FROM producto x WHERE x.comercio_id = c.id) AS ultimo_relevo
FROM comercio_provincia cp
JOIN comercio c ON c.id = cp.comercio_id
JOIN provincia pr ON pr.id = cp.provincia_id
LEFT JOIN rubro r ON r.id = c.rubro_id
LEFT JOIN localidad l ON l.id = cp.localidad_id
WHERE cp.estado = 'activo';

-- producto con su comercio y precio vigente (lo que muestra el explorador / comparador)
CREATE OR REPLACE VIEW v_producto AS
SELECT pa.producto_id, x.nombre, x.ean, x.marca, x.presentacion, x.categoria,
       c.id AS comercio_id, c.nombre AS comercio, c.fuente, r.nombre AS rubro,
       NULLIF(pa.provincia_id, 0) AS provincia_id, pa.fecha, pa.precio, pa.precio_min, pa.precio_max
FROM v_precio_actual pa
JOIN producto x ON x.id = pa.producto_id
JOIN comercio c ON c.id = x.comercio_id
LEFT JOIN rubro r ON r.id = c.rubro_id;

-- tablero: comercios y productos por provincia y rubro
CREATE OR REPLACE VIEW v_resumen_provincia_rubro AS
SELECT provincia_id, provincia, rubro, count(*) AS comercios, sum(productos) AS productos,
       max(ultimo_relevo) AS ultimo_relevo
FROM v_comercio
GROUP BY provincia_id, provincia, rubro;

-- ---------------------------------------------------------------- MercadoLibre (catalogo)
-- Productos del catalogo (una ficha por producto, con muchos vendedores) y sus ofertas
-- diarias. Lo llena ml_catalogo.py; sincronizar() lo vuelca tambien al modelo general
-- (comercio 'mercadolibre.com.ar' -> producto -> precio con min / mediana / max entre ofertas).
ALTER TABLE comercio DROP CONSTRAINT IF EXISTS comercio_fuente_check;
ALTER TABLE comercio ADD CONSTRAINT comercio_fuente_check CHECK (fuente IN ('scraping', 'sepa', 'api'));

CREATE TABLE IF NOT EXISTS ml_categoria (
    id          text PRIMARY KEY,               -- MLA1403
    nombre      text NOT NULL,
    padre_id    text,
    ruta        text,                           -- Alimentos y Bebidas > Almacen > ...
    dominio_id  text,                           -- dominio de catalogo de la hoja (MLA-YERBA_MATE)
    hoja        boolean NOT NULL,
    total_items bigint
);

CREATE TABLE IF NOT EXISTS ml_producto (
    id            text PRIMARY KEY,             -- MLA24392121
    nombre        text NOT NULL,
    dominio_id    text,
    padre_id      text,                         -- familia (ej. mismo modelo en varios colores)
    estado        text,
    marca         text,
    modelo        text,
    gtin          text,
    atributos     jsonb,
    hallado_por   text,                         -- busqueda:<palabra> | gtin:<ean>
    primera_vez   date NOT NULL DEFAULT current_date,
    ultima_vez    date NOT NULL DEFAULT current_date,
    ofertas_fecha date,                         -- ultima vez que se consultaron sus ofertas
    ofertas       integer                       -- cuantas ofertas tenia esa vez
);
CREATE INDEX IF NOT EXISTS ml_producto_gtin ON ml_producto (gtin) WHERE gtin IS NOT NULL;
CREATE INDEX IF NOT EXISTS ml_producto_dominio ON ml_producto (dominio_id);
CREATE INDEX IF NOT EXISTS ml_producto_pend ON ml_producto (ofertas_fecha NULLS FIRST);
CREATE INDEX IF NOT EXISTS ml_producto_nombre_trgm ON ml_producto USING gin (nombre gin_trgm_ops);

CREATE TABLE IF NOT EXISTS ml_oferta (
    item_id            text NOT NULL,           -- publicacion del vendedor (MLA123...)
    fecha              date NOT NULL,
    producto_id        text NOT NULL REFERENCES ml_producto(id) ON DELETE CASCADE,
    precio             numeric(14, 2),
    precio_original    numeric(14, 2),
    moneda             text,
    vendedor_id        bigint,
    condicion          text,
    envio_gratis       boolean,
    tienda_oficial     integer,
    tipo_publicacion   text,
    provincia_vendedor text,
    PRIMARY KEY (item_id, fecha)
);
CREATE INDEX IF NOT EXISTS ml_oferta_producto ON ml_oferta (producto_id, fecha);

-- cola de trabajo del crawler: que se busco, con que resultado (permite cortar y retomar)
CREATE TABLE IF NOT EXISTS ml_busqueda (
    tipo        text NOT NULL CHECK (tipo IN ('palabra', 'gtin')),
    clave       text NOT NULL,
    origen      text,                           -- categoria:<id> | marca:<palabra> | sepa | scraping
    estado      text NOT NULL DEFAULT 'pendiente',
    total       integer,                        -- resultados que informa la API
    hallados    integer,                        -- productos traidos (tope 150 por palabra)
    actualizado timestamptz,
    PRIMARY KEY (tipo, clave)
);

-- precio del dia por producto de catalogo
CREATE OR REPLACE VIEW v_ml_precio AS
SELECT producto_id, fecha, count(*) AS ofertas, min(precio) AS precio_min,
       percentile_cont(0.5) WITHIN GROUP (ORDER BY precio) AS precio_mediana, max(precio) AS precio_max,
       count(*) FILTER (WHERE tienda_oficial IS NOT NULL) AS de_tiendas_oficiales
FROM ml_oferta WHERE precio > 0 AND moneda = 'ARS'
GROUP BY producto_id, fecha;
