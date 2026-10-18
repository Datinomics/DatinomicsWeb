# -*- coding: utf-8 -*-
"""
Universo de retailers argentinos con TIENDA ONLINE / catalogo de precios,
por rubro. Objetivo: targets directamente scrapeables para precios.

Cada entrada: (Empresa, Sector, URL, Cobertura, Detalle)
Cobertura: Nacional / Regional(provincia) / Marketplace
"""

CADENAS = [
    # ---------------- SUPERMERCADOS (nacionales) ----------------
    ("Carrefour", "Supermercado", "https://www.carrefour.com.ar", "Nacional", ""),
    ("Coto", "Supermercado", "https://www.cotodigital3.com.ar", "Nacional", ""),
    ("Dia", "Supermercado", "https://diaonline.supermercadosdia.com.ar", "Nacional", ""),
    ("Jumbo", "Supermercado", "https://www.jumbo.com.ar", "Nacional", ""),
    ("Disco", "Supermercado", "https://www.disco.com.ar", "Nacional", ""),
    ("Vea", "Supermercado", "https://www.veadigital.com.ar", "Nacional", ""),
    ("ChangoMas (Walmart)", "Supermercado", "https://www.masonline.com.ar", "Nacional", ""),
    ("La Anonima", "Supermercado", "https://www.laanonimaonline.com", "Nacional", "fuerte en Patagonia"),
    ("Hiper Libertad", "Supermercado", "https://www.hiperlibertad.com.ar", "Nacional", ""),
    ("Cooperativa Obrera", "Supermercado", "https://www.lacoopeencasa.coop", "Regional", "Bs As/Patagonia"),
    ("Atomo Conviene", "Supermercado", "https://www.atomoconviene.com", "Regional", "Cuyo/Centro"),
    ("Supermercados Toledo", "Supermercado", "https://www.toledodigital.com.ar", "Regional", "Mar del Plata"),
    ("Super Mami", "Supermercado", "https://www.supermami.com.ar", "Regional", "Cordoba"),
    ("Cordiez", "Supermercado", "https://www.cordiez.com.ar", "Regional", "Cordoba"),
    ("La Reina", "Supermercado", "https://www.lareinaonline.com.ar", "Regional", "Corrientes"),
    ("La Gallega", "Supermercado", "https://www.lagallega.com.ar", "Regional", "Santa Fe/Rosario"),
    ("Super A", "Supermercado", "https://www.superaonline.com.ar", "Regional", ""),
    ("Hipermercado Comodin", "Supermercado", "https://www.comodinencasa.com.ar", "Regional", "NOA"),
    ("Modo Mas / Maxiconsumo", "Mayorista", "https://www.maxiconsumo.com", "Nacional", "mayorista"),
    ("Diarco", "Mayorista", "https://www.diarco.com.ar", "Nacional", "mayorista"),
    ("Vital", "Mayorista", "https://www.vital.com.ar", "Nacional", "mayorista"),
    ("Yaguar", "Mayorista", "https://www.yaguar.com", "Nacional", "mayorista"),
    ("Makro", "Mayorista", "https://www.makro.com.ar", "Nacional", "mayorista"),
    ("Nini Mayorista", "Mayorista", "https://www.ninimayorista.com.ar", "Regional", "Bs As"),

    # ---------------- FARMACIAS / SALUD ----------------
    ("Farmacity", "Farmacia", "https://www.farmacity.com", "Nacional", ""),
    ("Farmaplus", "Farmacia", "https://www.farmaplus.com.ar", "Nacional", ""),
    ("Dr. Ahorro", "Farmacia", "https://www.farmaciasdrahorro.com.ar", "Nacional", ""),
    ("Farmaonline", "Farmacia", "https://www.farmaonline.com", "Nacional", ""),
    ("Simplicity", "Farmacia", "https://www.simplicity.com.ar", "Nacional", ""),
    ("Dr. Simi", "Farmacia", "https://www.drsimi.com.ar", "Nacional", ""),
    ("Farmaweb", "Farmacia", "https://www.farmaweb.com.ar", "Regional", ""),
    ("Farmacias del Pueblo", "Farmacia", "https://www.farmaciasdelpueblo.com.ar", "Regional", ""),
    ("Open Farma", "Farmacia", "https://www.openfarma.com.ar", "Regional", ""),
    ("Central Oeste", "Farmacia", "https://www.centraloeste.com.ar", "Regional", "Corrientes/NEA"),

    # ---------------- PERFUMERIA / COSMETICA ----------------
    ("Juleriaque", "Perfumeria", "https://www.juleriaque.com.ar", "Nacional", ""),
    ("Pigmento", "Perfumeria", "https://www.pigmento.com.ar", "Nacional", ""),
    ("Get The Look", "Perfumeria", "https://www.getthelook.com.ar", "Nacional", ""),
    ("Punto Belleza", "Perfumeria", "https://www.puntobelleza.com.ar", "Nacional", ""),
    ("Natura", "Cosmetica", "https://www.natura.com.ar", "Nacional", ""),
    ("Avon", "Cosmetica", "https://www.avon.com.ar", "Nacional", ""),
    ("The Body Shop", "Cosmetica", "https://www.thebodyshop.com.ar", "Nacional", ""),
    ("Idraet", "Cosmetica", "https://www.idraetstore.com", "Nacional", ""),

    # ---------------- ELECTRO / ELECTRODOMESTICOS / TECNO ----------------
    ("Fravega", "Electro", "https://www.fravega.com", "Nacional", ""),
    ("Garbarino", "Electro", "https://www.garbarino.com", "Nacional", ""),
    ("Musimundo", "Electro", "https://www.musimundo.com", "Nacional", ""),
    ("Cetrogar", "Electro", "https://www.cetrogar.com.ar", "Nacional", ""),
    ("Naldo", "Electro", "https://www.naldo.com.ar", "Nacional", ""),
    ("Megatone", "Electro", "https://www.megatone.net", "Nacional", ""),
    ("On City", "Electro", "https://www.oncity.com", "Nacional", ""),
    ("Rodo", "Electro", "https://www.rodo.com.ar", "Nacional", ""),
    ("Ribeiro", "Electro", "https://www.ribeiro.com.ar", "Nacional", ""),
    ("Compumundo", "Electro", "https://www.compumundo.com.ar", "Nacional", ""),
    ("Newsan / Electronicos", "Electro", "https://www.newsan.com.ar", "Nacional", ""),
    ("Venex", "Tecnologia", "https://www.venex.com.ar", "Nacional", "computacion"),
    ("Compra Gamer", "Tecnologia", "https://www.compragamer.com", "Nacional", "computacion"),
    ("Maximus", "Tecnologia", "https://www.maximus.com.ar", "Nacional", "computacion"),
    ("Gezatek", "Tecnologia", "https://www.gezatek.com.ar", "Nacional", "computacion"),
    ("Full H4rd", "Tecnologia", "https://www.fullh4rd.com.ar", "Nacional", "computacion"),

    # ---------------- HOGAR / CONSTRUCCION / FERRETERIA ----------------
    ("Easy", "Hogar/Construccion", "https://www.easy.com.ar", "Nacional", ""),
    ("Sodimac", "Hogar/Construccion", "https://www.sodimac.com.ar", "Nacional", ""),
    ("Pinturerias Rex", "Pintureria", "https://www.pintureriasrex.com.ar", "Nacional", ""),
    ("Prestigio Pinturas", "Pintureria", "https://www.prestigiopinturas.com.ar", "Regional", ""),
    ("Ferreteria Industrial Mass", "Ferreteria", "https://www.ferreteriamass.com.ar", "Regional", ""),
    ("Hierros y Aceros", "Construccion", "https://www.hierrosyaceros.com.ar", "Regional", ""),
    ("Barugel Azulay", "Construccion", "https://www.barugelazulay.com.ar", "Nacional", "sanitarios"),
    ("Blanco", "Construccion", "https://www.blanco.com.ar", "Nacional", "sanitarios/cocinas"),

    # ---------------- MUEBLES / DECO / BAZAR ----------------
    ("Sodimac Homecenter", "Muebles/Deco", "https://www.sodimac.com.ar", "Nacional", ""),
    ("Mc Mobili", "Muebles", "https://www.mcmobili.com.ar", "Nacional", ""),
    ("Mosconi Muebles", "Muebles", "https://www.mosconi.com.ar", "Regional", ""),
    ("Morph", "Muebles/Deco", "https://www.morph.com.ar", "Nacional", ""),
    ("Falabella Hogar", "Muebles/Deco", "https://www.falabella.com.ar", "Nacional", "verificar si opera"),
    ("Bazar Nuba", "Bazar", "https://www.nuba.com.ar", "Nacional", ""),

    # ---------------- INDUMENTARIA / CALZADO / DEPORTES ----------------
    ("Dexter", "Deportes", "https://www.dexter.com.ar", "Nacional", ""),
    ("Stock Center", "Deportes", "https://www.stockcenter.com.ar", "Nacional", ""),
    ("Sporting", "Deportes", "https://www.sporting.com.ar", "Nacional", ""),
    ("Open Sports", "Deportes", "https://www.opensports.com.ar", "Nacional", ""),
    ("Solo Deportes", "Deportes", "https://www.solodeportes.com.ar", "Nacional", ""),
    ("Adidas Argentina", "Indumentaria", "https://www.adidas.com.ar", "Nacional", ""),
    ("Nike Argentina", "Indumentaria", "https://www.nike.com.ar", "Nacional", ""),
    ("Cheeky", "Indumentaria", "https://www.cheeky.com.ar", "Nacional", ""),
    ("Mimo & Co", "Indumentaria", "https://www.mimo.com.ar", "Nacional", ""),
    ("Yagmour", "Indumentaria", "https://www.yagmour.com.ar", "Nacional", ""),
    ("Rapsodia", "Indumentaria", "https://www.rapsodia.com.ar", "Nacional", ""),
    ("47 Street", "Indumentaria", "https://www.47street.com.ar", "Nacional", ""),
    ("Las Pepas", "Indumentaria", "https://www.laspepas.com.ar", "Nacional", ""),
    ("Prune", "Indumentaria", "https://www.prune.com.ar", "Nacional", "marroquineria"),
    ("Grimoldi", "Calzado", "https://www.grimoldi.com", "Nacional", ""),
    ("Ricky Sarkany", "Calzado", "https://www.rickysarkany.com", "Nacional", ""),

    # ---------------- BEBIDAS / VINOTECAS ----------------
    ("Winery", "Bebidas", "https://www.winery.com.ar", "Nacional", "vinos"),
    ("Tonel Privado", "Bebidas", "https://www.tonelprivado.com", "Nacional", "vinos"),
    ("Lo de Joaquin", "Bebidas", "https://www.lodejoaquin.com.ar", "Regional", ""),
    ("La Cava del Sommelier", "Bebidas", "https://www.lacavadelsommelier.com.ar", "Nacional", ""),
    ("Pacval", "Bebidas", "https://www.pacval.com.ar", "Regional", "distribuidora"),
    ("Bebidas Online", "Bebidas", "https://www.bebidasonline.com.ar", "Nacional", ""),
    ("Craft Society", "Bebidas", "https://www.craftsociety.com.ar", "Nacional", "cervezas"),

    # ---------------- KIOSCO / GOLOSINAS / ALIMENTOS MAYORISTA ----------------
    ("Golosinas Mariano", "Golosinas", "https://www.golosinasmariano.com.ar", "Nacional", "mayorista golosinas"),
    ("Kioscos Mayorista La Golosa", "Golosinas", "https://www.lagolosamayorista.com.ar", "Regional", ""),
    ("Mayorista Sol", "Golosinas", "https://www.mayoristasol.com.ar", "Regional", ""),

    # ---------------- MASCOTAS ----------------
    ("Puppis", "Petshop", "https://www.puppis.com.ar", "Nacional", ""),
    ("Kiwoko / Tienda Mascotas", "Petshop", "https://www.tiendamascotas.com.ar", "Nacional", ""),

    # ---------------- LIBRERIA / JUGUETERIA ----------------
    ("Cuspide", "Libreria", "https://www.cuspide.com", "Nacional", ""),
    ("Yenny / El Ateneo", "Libreria", "https://www.yenny-elateneo.com", "Nacional", ""),
    ("Libreria Rayuela", "Libreria", "https://www.libreriarayuela.com.ar", "Regional", ""),
    ("La Cumbre Juguetes", "Jugueteria", "https://www.lacumbreonline.com.ar", "Nacional", ""),

    # ---------------- MARKETPLACES (multi-rubro, precios) ----------------
    ("Mercado Libre", "Marketplace", "https://www.mercadolibre.com.ar", "Marketplace", "todo rubro"),
    ("Tiendamia", "Marketplace", "https://www.tiendamia.com.ar", "Marketplace", "importados"),
    ("Avenida+ (Avenida)", "Marketplace", "https://www.avenida.com.ar", "Marketplace", ""),
]
