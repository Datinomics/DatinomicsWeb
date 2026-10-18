// ─────────────────────────────────────────────────────────────
// Datinomics — mock data store
// ─────────────────────────────────────────────────────────────

// Empresas: 23 argentinas reales-ish, distribuidas por rubro
window.EMPRESAS = [
  // Retail / supermercados
  { id: 'coto',      nm: 'Coto',          rubro: 'Alimentos',    region: 'CABA',          ticker: 'COTO',  skus: 18, mom: 2.4, yoy: 47.1, color: '#C8102E' },
  { id: 'carrefour', nm: 'Carrefour',     rubro: 'Alimentos',    region: 'Multi',         ticker: 'CRFR',  skus: 22, mom: 2.1, yoy: 45.8, color: '#0061B0' },
  { id: 'dia',       nm: 'Día Argentina', rubro: 'Alimentos',    region: 'CABA / GBA',    ticker: 'DIA',   skus: 14, mom: 1.9, yoy: 43.2, color: '#D52B1E' },
  { id: 'jumbo',     nm: 'Jumbo',         rubro: 'Alimentos',    region: 'Multi',         ticker: 'JMBO',  skus: 16, mom: 2.6, yoy: 48.0, color: '#00833E' },
  { id: 'disco',     nm: 'Disco',         rubro: 'Alimentos',    region: 'CABA',          ticker: 'DSCO',  skus: 12, mom: 2.2, yoy: 44.5, color: '#E60012' },

  // Indumentaria
  { id: 'frav',  nm: 'Frávega',     rubro: 'Hogar',          region: 'Multi',         ticker: 'FRAV',  skus: 8,  mom: 1.4, yoy: 38.2, color: '#1E40AF' },
  { id: 'garb',  nm: 'Garbarino',   rubro: 'Tecnología',     region: 'Multi',         ticker: 'GARB',  skus: 9,  mom: 1.7, yoy: 39.4, color: '#FF6900' },
  { id: 'falab', nm: 'Falabella',   rubro: 'Indumentaria',   region: 'CABA / Córdoba',ticker: 'FALA',  skus: 24, mom: 3.4, yoy: 47.2, color: '#118939' },
  { id: 'cb',    nm: 'Cheeky',      rubro: 'Indumentaria',   region: 'Multi',         ticker: 'CBKY',  skus: 12, mom: 3.1, yoy: 46.0, color: '#E91E63' },

  // Combustibles
  { id: 'ypf',   nm: 'YPF',         rubro: 'Combustibles',   region: 'Nacional',      ticker: 'YPFD',  skus: 6,  mom: -0.4, yoy: 34.2, color: '#0033A0' },
  { id: 'shell', nm: 'Shell',       rubro: 'Combustibles',   region: 'Nacional',      ticker: 'SHEL',  skus: 6,  mom: -0.2, yoy: 33.8, color: '#DD1D21' },
  { id: 'axion', nm: 'Axion',       rubro: 'Combustibles',   region: 'Nacional',      ticker: 'AXIN',  skus: 5,  mom: 0.3,  yoy: 35.1, color: '#003F7F' },

  // Construcción / industria
  { id: 'ln',    nm: 'Loma Negra',  rubro: 'Construcción',   region: 'Nacional',      ticker: 'LOMA',  skus: 4,  mom: 1.7, yoy: 47.0, color: '#FFD200' },
  { id: 'aluar', nm: 'Aluar',       rubro: 'Construcción',   region: 'Nacional',      ticker: 'ALUA',  skus: 3,  mom: 1.5, yoy: 45.3, color: '#A50034' },
  { id: 'acin',  nm: 'Acindar',     rubro: 'Construcción',   region: 'Nacional',      ticker: 'ACIN',  skus: 5,  mom: 1.9, yoy: 46.4, color: '#003366' },

  // Tecnología
  { id: 'meli',  nm: 'Mercado Libre', rubro: 'Tecnología',   region: 'Nacional',      ticker: 'MELI',  skus: 12, mom: 2.0, yoy: 46.5, color: '#FFE600' },
  { id: 'gpat',  nm: 'Globant',       rubro: 'Servicios',    region: 'CABA',          ticker: 'GLOB',  skus: 4,  mom: 2.3, yoy: 44.1, color: '#62B4FA' },

  // Salud
  { id: 'roe',   nm: 'Roemmers',    rubro: 'Salud',          region: 'Nacional',      ticker: 'ROEM',  skus: 9,  mom: 3.8, yoy: 48.7, color: '#00529B' },
  { id: 'farm',  nm: 'Farmacity',   rubro: 'Salud',          region: 'CABA / GBA',    ticker: 'FRMC',  skus: 11, mom: 3.5, yoy: 47.4, color: '#E10073' },

  // Servicios
  { id: 'edesur',nm: 'Edesur',      rubro: 'Servicios',      region: 'CABA / GBA',    ticker: 'EDSU',  skus: 3,  mom: 2.4, yoy: 44.8, color: '#003DA5' },
  { id: 'edenor',nm: 'Edenor',      rubro: 'Servicios',      region: 'GBA Norte',     ticker: 'EDN',   skus: 3,  mom: 2.5, yoy: 45.2, color: '#FFCC00' },

  // Turismo
  { id: 'aero',  nm: 'Aerolíneas Arg.', rubro: 'Turismo',  region: 'Nacional',      ticker: 'AERO',  skus: 4,  mom: 4.1, yoy: 38.4, color: '#0066CC' },
  { id: 'desp',  nm: 'Despegar',        rubro: 'Turismo',  region: 'Nacional',      ticker: 'DESP',  skus: 6,  mom: 3.8, yoy: 37.9, color: '#5C2D91' },
];

// Rubros
window.RUBROS = [
  { id: 'indu',  nm: 'Indumentaria',  mom: 3.4, yoy: 47.2, empresas: 2 },
  { id: 'cons',  nm: 'Construcción',  mom: 1.7, yoy: 47.0, empresas: 3 },
  { id: 'alim',  nm: 'Alimentos',     mom: 2.4, yoy: 46.8, empresas: 5 },
  { id: 'tec',   nm: 'Tecnología',    mom: 2.0, yoy: 46.5, empresas: 2 },
  { id: 'salud', nm: 'Salud',         mom: 3.8, yoy: 48.7, empresas: 2 },
  { id: 'serv',  nm: 'Servicios',     mom: 2.3, yoy: 44.1, empresas: 3 },
  { id: 'hog',   nm: 'Hogar',         mom: 2.1, yoy: 43.7, empresas: 1 },
  { id: 'tran',  nm: 'Transporte',    mom: 2.8, yoy: 42.9, empresas: 0 },
  { id: 'edu',   nm: 'Educación',     mom: 1.9, yoy: 41.5, empresas: 0 },
  { id: 'esp',   nm: 'Esparcimiento', mom: 1.2, yoy: 39.8, empresas: 0 },
  { id: 'tur',   nm: 'Turismo',       mom: 4.1, yoy: 38.4, empresas: 2 },
  { id: 'comb',  nm: 'Combustibles',  mom: -0.4,yoy: 34.2, empresas: 3 },
];

// Series mensual: jun 25 → may 26 (12 puntos), índice general base 100 en jun 25
// Plus per-empresa series for detail view
window.SERIE_GENERAL = [100, 103.2, 106.8, 110.4, 114.1, 118.0, 122.3, 126.8, 131.4, 136.2, 141.1, 145.3];
window.MESES = ['jun 25','jul 25','ago 25','sep 25','oct 25','nov 25','dic 25','ene 26','feb 26','mar 26','abr 26','may 26'];

// per-empresa monthly serie (12 puntos) — synthetic but coherent with yoy
window.makeSerie = function(yoy) {
  // start at 100, end at 100*(1+yoy/100), with small noise
  const end = 100 * (1 + yoy/100);
  const out = [];
  for (let i=0; i<12; i++){
    const t = i/11;
    // smoothed log-ish growth
    const lin = 100 + (end-100) * Math.pow(t, 0.95);
    const noise = (Math.sin(i*1.7 + yoy) * 0.6);
    out.push(+(lin + noise).toFixed(2));
  }
  return out;
};

// SKUs por empresa (sample, generated)
window.SKUS_BY_EMPRESA = {
  coto: [
    { nm: 'Leche entera La Serenísima 1L', precio: 1850, mom: 2.6, yoy: 47.8 },
    { nm: 'Yerba Taragüi 1kg',              precio: 4980, mom: 3.1, yoy: 52.4 },
    { nm: 'Aceite Natura 1.5L',             precio: 3450, mom: 2.2, yoy: 44.1 },
    { nm: 'Azúcar Ledesma 1kg',             precio: 1290, mom: 1.8, yoy: 41.3 },
    { nm: 'Pan lactal Bimbo 540g',          precio: 2680, mom: 2.4, yoy: 46.0 },
    { nm: 'Fideos Matarazzo 500g',          precio: 1320, mom: 2.1, yoy: 43.8 },
    { nm: 'Arroz Gallo Oro 1kg',            precio: 2180, mom: 2.9, yoy: 48.2 },
    { nm: 'Café Cabrales 250g',             precio: 6450, mom: 3.4, yoy: 51.7 },
  ],
  carrefour: [
    { nm: 'Leche entera La Serenísima 1L', precio: 1820, mom: 2.1, yoy: 45.4 },
    { nm: 'Coca-Cola 2.25L',                precio: 3490, mom: 2.0, yoy: 44.6 },
    { nm: 'Pan lactal Bimbo 540g',          precio: 2710, mom: 2.3, yoy: 45.8 },
    { nm: 'Detergente Magistral 750ml',     precio: 2890, mom: 1.7, yoy: 42.1 },
    { nm: 'Papel higiénico Elite x4',       precio: 3640, mom: 1.9, yoy: 43.2 },
  ],
  ypf: [
    { nm: 'Nafta Súper · litro',            precio: 1190, mom: -0.4, yoy: 34.2 },
    { nm: 'Nafta Infinia · litro',          precio: 1390, mom: -0.3, yoy: 33.8 },
    { nm: 'Gasoil Grado 2 · litro',         precio: 1090, mom: -0.5, yoy: 33.1 },
    { nm: 'Gasoil Infinia Diesel · litro',  precio: 1290, mom: -0.4, yoy: 33.9 },
  ],
  falab: [
    { nm: 'Jean Levi\'s 511',               precio: 89900, mom: 3.4, yoy: 47.2 },
    { nm: 'Buzo Nike Tech Fleece',          precio: 145900, mom: 3.6, yoy: 48.1 },
    { nm: 'Zapatillas Adidas Forum',        precio: 159900, mom: 3.2, yoy: 46.4 },
    { nm: 'Campera Columbia Bugaboo',       precio: 279900, mom: 3.8, yoy: 49.2 },
    { nm: 'Remera Tommy Hilfiger',          precio: 54900, mom: 3.0, yoy: 45.8 },
  ],
  ln: [
    { nm: 'Cemento Loma Negra · 50kg',      precio: 11800, mom: 1.7, yoy: 47.0 },
    { nm: 'Cemento Plasticor · 50kg',       precio: 12400, mom: 1.8, yoy: 47.5 },
    { nm: 'Cal Hidráulica · 25kg',          precio: 6800,  mom: 1.5, yoy: 46.2 },
  ],
  meli: [
    { nm: 'Samsung Galaxy S24 256GB',       precio: 1149000, mom: 2.0, yoy: 46.5 },
    { nm: 'iPhone 15 128GB',                precio: 1849000, mom: 2.2, yoy: 47.1 },
    { nm: 'Smart TV Samsung 55"',           precio: 689000,  mom: 1.8, yoy: 45.2 },
    { nm: 'Notebook Lenovo i5',             precio: 1290000, mom: 1.9, yoy: 45.8 },
  ],
  roe: [
    { nm: 'Ibupirac 600mg x10',             precio: 4280, mom: 3.8, yoy: 48.7 },
    { nm: 'Amoxidal 500mg x16',             precio: 8940, mom: 3.6, yoy: 47.9 },
    { nm: 'Bagóvit A x100g',                precio: 6180, mom: 3.7, yoy: 48.2 },
  ],
};

// Default SKU list for empresas without explicit data
window.defaultSkus = (emp) => {
  const base = ['Producto A', 'Producto B', 'Producto C', 'Producto D'];
  return base.map((nm, i) => ({
    nm: `${nm} · ${emp.nm}`,
    precio: 1000 + i*500 + Math.round(emp.yoy*30),
    mom: emp.mom + (Math.random()-0.5)*0.6,
    yoy: emp.yoy + (Math.random()-0.5)*2,
  }));
};

// Alertas activas
window.ALERTAS_ACTIVAS = [
  { id: 1, nivel: 'crit',  tipo: 'Umbral mensual',     target: 'Loma Negra · Cemento 50kg',   trigger: 'mom > 5%', actual: '+6.8%', fecha: 'hace 2h',   estado: 'disparada' },
  { id: 2, nivel: 'warn',  tipo: 'Variación diaria',   target: 'YPF · Nafta súper',           trigger: 'day > 2%',  actual: '+2.1%', fecha: 'hace 6h',   estado: 'disparada' },
  { id: 3, nivel: 'crit',  tipo: 'Spike interanual',   target: 'Roemmers · Ibupirac',         trigger: 'yoy > 48%', actual: '+48.7%',fecha: 'hace 1d',   estado: 'disparada' },
  { id: 4, nivel: 'info',  tipo: 'Tendencia rubro',    target: 'Indumentaria',                trigger: '3m > 10%',  actual: '+11.4%',fecha: 'hace 2d',   estado: 'reconocida' },
  { id: 5, nivel: 'warn',  tipo: 'Umbral mensual',     target: 'Coto · Yerba Taragüi',        trigger: 'mom > 3%',  actual: '+3.1%', fecha: 'hace 3d',   estado: 'reconocida' },
  { id: 6, nivel: 'info',  tipo: 'Anomalía estacional',target: 'Aerolíneas · cabotaje',       trigger: 'z > 2.5',   actual: 'z=2.7',  fecha: 'hace 4d',   estado: 'cerrada' },
];

window.ALERTAS_REGLAS = [
  { id: 'r1', nm: 'Inflación supermercados',    tipo: 'Rubro', target: 'Alimentos',     cond: 'mom > 2.5%',  canales: ['email','slack'], activa: true },
  { id: 'r2', nm: 'Combustibles · cambios',      tipo: 'Rubro', target: 'Combustibles',  cond: 'day > 1.0%',  canales: ['email','webhook'], activa: true },
  { id: 'r3', nm: 'Roemmers laboratorio',        tipo: 'Empresa', target: 'Roemmers',    cond: 'mom > 3%',    canales: ['slack'],          activa: true },
  { id: 'r4', nm: 'Construcción mayor.',         tipo: 'Rubro', target: 'Construcción',  cond: 'yoy > 45%',   canales: ['email'],          activa: true },
  { id: 'r5', nm: 'Indumentaria — pico',         tipo: 'Rubro', target: 'Indumentaria',  cond: 'z > 2.0',     canales: ['email','slack'],  activa: false },
];

// helpers
window.fmtMoney = (n) => '$' + n.toLocaleString('es-AR', { maximumFractionDigits: 0 });
window.fmtPct = (n, withSign=true) => (n>0 && withSign ? '+' : '') + n.toFixed(1) + '%';
window.fmtNum = (n) => n.toLocaleString('es-AR');
