# -*- coding: utf-8 -*-
"""
Tablas de referencia geografica para verificar donde esta un comercio.

Por provincia (letra ISO 3166-2:AR, que coincide con la letra del CPA):
  - localidades sin ambiguedad (para direcciones "calle 123, Localidad")
  - caracteristicas telefonicas (ENACOM)
Ademas: point-in-polygon contra provincias.geojson (IGN).
"""
import json
import os
import re
import unicodedata

AQUI = os.path.dirname(os.path.abspath(__file__))

# folder del repo -> letra ISO
FOLDER_A_LETRA = {
    "CABA": "C", "Buenos-Aires": "B", "Catamarca": "K", "Chaco": "H", "Chubut": "U",
    "Cordoba": "X", "Corrientes": "W", "Entre-Rios": "E", "Formosa": "P", "Jujuy": "Y",
    "La-Pampa": "L", "La-Rioja": "F", "Mendoza": "M", "Misiones": "N", "Neuquen": "Q",
    "Rio-Negro": "R", "Salta": "A", "San-Juan": "J", "San-Luis": "D", "Santa-Cruz": "Z",
    "Santa-Fe": "S", "Santiago-del-Estero": "G", "Tierra-del-Fuego": "V", "Tucuman": "T",
}
LETRA_A_NOMBRE = {
    "C": "CABA", "B": "Buenos Aires", "K": "Catamarca", "H": "Chaco", "U": "Chubut",
    "X": "Cordoba", "W": "Corrientes", "E": "Entre Rios", "P": "Formosa", "Y": "Jujuy",
    "L": "La Pampa", "F": "La Rioja", "M": "Mendoza", "N": "Misiones", "Q": "Neuquen",
    "R": "Rio Negro", "A": "Salta", "J": "San Juan", "D": "San Luis", "Z": "Santa Cruz",
    "S": "Santa Fe", "G": "Santiago del Estero", "V": "Tierra del Fuego", "T": "Tucuman",
    "EXT": "Exterior",
}

# Localidades que, puestas despues de una direccion, identifican la provincia.
# Se excluyen a proposito nombres repetidos entre provincias (San Martin, Las Heras,
# Maipu, Rivadavia, Mercedes, Esquina, Santa Rosa, Rawson, Junin, Flores...).
LOCALIDADES = {
    "C": ["caba", "c.a.b.a", "capital federal", "cap. fed", "cap fed",
          "ciudad autonoma de buenos aires", "ciudad autonoma de bs as",
          "ciudad de buenos aires", "palermo", "recoleta", "belgrano", "caballito",
          "villa crespo", "almagro", "nunez", "villa urquiza", "villa devoto", "barrio norte",
          "boedo", "san telmo", "colegiales", "villa del parque", "liniers", "mataderos",
          "villa lugano", "parque patricios", "monserrat", "montserrat", "balvanera",
          "chacarita", "floresta", "barracas", "la boca", "puerto madero", "san cristobal",
          "parque chacabuco", "villa luro", "villa ortuzar", "agronomia", "nueva pompeya",
          "villa pueyrredon", "coghlan", "parque chas", "la paternal", "villa santa rita",
          "villa general mitre", "monte castro", "velez sarsfield", "villa soldati",
          "villa riachuelo", "parque avellaneda", "microcentro"],
    "B": ["la plata", "mar del plata", "bahia blanca", "quilmes", "moron", "lomas de zamora",
          "tigre", "pilar", "lanus", "san isidro", "vicente lopez", "olivos", "tandil",
          "berazategui", "florencio varela", "adrogue", "banfield", "ramos mejia", "martinez",
          "escobar", "campana", "zarate", "necochea", "olavarria", "pergamino", "castelar",
          "haedo", "caseros", "hurlingham", "ezeiza", "temperley", "bernal", "munro",
          "beccar", "nordelta", "san fernando", "provincia de buenos aires", "pcia. de buenos aires",
          "gba", "la matanza", "san justo", "moreno", "jose c. paz", "lujan"],
    "K": ["catamarca", "san fernando del valle"],
    "H": ["resistencia", "chaco", "saenz pena", "barranqueras"],
    "U": ["comodoro rivadavia", "trelew", "puerto madryn", "esquel", "chubut"],
    "X": ["cordoba", "rio cuarto", "villa maria", "villa carlos paz", "carlos paz",
          "alta gracia", "rio tercero", "jesus maria"],
    "W": ["corrientes", "ctes", "goya", "paso de los libres", "curuzu cuatia", "santo tome",
          "monte caseros", "virasoro", "saladas", "empedrado"],
    "E": ["parana", "concordia", "gualeguaychu", "concepcion del uruguay", "entre rios"],
    "P": ["formosa", "clorinda"],
    "Y": ["jujuy", "san salvador de jujuy", "palpala"],
    "L": ["general pico", "la pampa", "toay"],
    "F": ["la rioja", "chilecito"],
    "M": ["mendoza", "godoy cruz", "guaymallen", "lujan de cuyo", "san rafael", "tunuyan",
          "tupungato", "malargue", "chacras de coria"],
    "N": ["posadas", "obera", "eldorado", "puerto iguazu", "misiones"],
    "Q": ["neuquen", "san martin de los andes", "plottier", "cutral co", "zapala"],
    "R": ["bariloche", "general roca", "cipolletti", "viedma", "rio negro"],
    "A": ["salta", "oran", "tartagal", "cafayate"],
    "J": ["san juan", "chimbas"],
    "D": ["san luis", "villa mercedes"],
    "Z": ["rio gallegos", "caleta olivia", "el calafate"],
    "S": ["rosario", "santa fe", "rafaela", "venado tuerto", "reconquista"],
    "G": ["santiago del estero", "la banda", "termas de rio hondo"],
    "V": ["ushuaia", "tierra del fuego", "tolhuin"],
    "T": ["tucuman", "yerba buena", "tafi viejo"],
    "EXT": ["espana", "madrid", "barcelona", "valencia", "mexico", "cdmx", "chile",
            "santiago de chile", "montevideo", "uruguay", "colombia", "bogota", "lima",
            "peru", "paraguay", "asuncion", "miami", "florida usa", "brasil", "sao paulo"],
}

# Caracteristicas telefonicas -> provincias (ENACOM). Las compartidas mapean a varias.
CARACTERISTICAS = {
    "11": "CB",
    "220": "B", "221": "B", "223": "B", "230": "B", "236": "B", "237": "B", "249": "B",
    "291": "B", "336": "B", "2226": "B", "2241": "B", "2242": "B", "2257": "B", "2261": "B",
    "2262": "B", "2264": "B", "2266": "B", "2267": "B", "2268": "B", "2281": "B", "2283": "B",
    "2284": "B", "2285": "B", "2286": "B", "2291": "B", "2292": "B", "2314": "B", "2316": "B",
    "2317": "B", "2320": "B", "2323": "B", "2324": "B", "2325": "B", "2342": "B", "2344": "B",
    "2345": "B", "2346": "B", "2352": "B", "2353": "B", "2354": "B", "2355": "B", "2356": "B",
    "2357": "B", "2358": "B", "2392": "B", "2393": "B", "2394": "B", "2395": "B", "2396": "B",
    "2473": "B", "2474": "B", "2475": "B", "2477": "B", "2478": "B", "3329": "B", "3388": "B",
    "3487": "B", "3488": "B", "3489": "B",
    "351": "X", "353": "X", "358": "X", "3521": "X", "3522": "X", "3524": "X", "3525": "X",
    "3532": "X", "3533": "X", "3537": "X", "3541": "X", "3542": "X", "3543": "X", "3544": "X",
    "3546": "X", "3547": "X", "3548": "X", "3549": "X", "3562": "X", "3563": "X", "3564": "X",
    "3571": "X", "3572": "X", "3573": "X", "3574": "X", "3575": "X", "3576": "X", "3582": "X",
    "3583": "X", "3584": "X", "3585": "X", "3467": "X", "3468": "X", "3472": "X",
    "341": "S", "342": "S", "3400": "S", "3401": "S", "3402": "S", "3404": "S", "3405": "S",
    "3406": "S", "3408": "S", "3409": "S", "3460": "S", "3462": "S", "3463": "S", "3464": "S",
    "3465": "S", "3466": "S", "3469": "S", "3471": "S", "3476": "S", "3482": "S", "3483": "S",
    "3491": "S", "3492": "S", "3493": "S", "3496": "S", "3497": "S", "3498": "S",
    "260": "M", "261": "M", "263": "M", "2622": "M", "2624": "M", "2625": "M", "2626": "M",
    "264": "J", "2646": "J", "2647": "J", "2648": "J",
    "266": "D", "2651": "D", "2655": "D", "2656": "D", "2657": "D", "2658": "D",
    "379": "W", "3756": "W", "3772": "W", "3773": "W", "3774": "W", "3775": "W", "3777": "W",
    "3781": "W", "3782": "W", "3786": "W",
    "362": "H", "364": "H", "3725": "H", "3731": "H", "3732": "H", "3734": "H", "3735": "H",
    "376": "N", "3741": "N", "3743": "N", "3751": "N", "3754": "N", "3755": "N", "3757": "N",
    "3758": "N",
    "370": "P", "3711": "P", "3715": "P", "3716": "P", "3718": "P",
    "343": "E", "345": "E", "3435": "E", "3436": "E", "3437": "E", "3438": "E", "3442": "E",
    "3444": "E", "3445": "E", "3446": "E", "3447": "E", "3454": "E", "3455": "E", "3456": "E",
    "3458": "E",
    "381": "T", "3862": "T", "3863": "T", "3865": "T", "3867": "T", "3869": "T", "3891": "T",
    "3892": "T", "3894": "T",
    "387": "A", "3876": "A", "3877": "A", "3878": "A",
    "388": "Y", "3885": "Y", "3886": "Y", "3887": "Y", "3888": "Y",
    "383": "K", "3832": "K", "3835": "K", "3837": "K", "3838": "K",
    "380": "F", "3825": "F", "3826": "F", "3827": "F",
    "385": "G", "3841": "G", "3843": "G", "3844": "G", "3845": "G", "3846": "G", "3854": "G",
    "3855": "G", "3856": "G", "3857": "G", "3858": "G",
    "2302": "L", "2331": "L", "2333": "L", "2334": "L", "2335": "L", "2336": "L", "2337": "L",
    "2338": "L", "2952": "L", "2953": "L", "2954": "L",
    "299": "QR", "2942": "Q", "2948": "Q", "2972": "Q",
    "294": "R", "298": "R", "2920": "R", "2931": "R", "2934": "R", "2940": "R",
    "280": "U", "297": "UZ", "2945": "U", "2965": "U",
    "2966": "Z", "2962": "Z", "2963": "Z", "2902": "Z",
    "2901": "V", "2964": "V",
}

# Codigos postales numericos (4 digitos) por rango -> provincia. Solo rangos seguros.
CP_RANGOS = [((1000, 1499), "C"), ((3400, 3499), "W"), ((5500, 5699), "M"),
             ((5000, 5299), "X"), ((2000, 2199), "S"), ((3000, 3099), "S")]


def norm(s):
    s = unicodedata.normalize("NFKD", str(s))
    return "".join(c for c in s if not unicodedata.combining(c)).lower()


# --------------------------------------------------------------------------
# Poligonos
# --------------------------------------------------------------------------
_POLIS = None


def _cargar_poligonos():
    global _POLIS
    if _POLIS is not None:
        return _POLIS
    with open(os.path.join(AQUI, "provincias.geojson"), encoding="utf-8") as f:
        g = json.load(f)
    _POLIS = []
    for feat in g["features"]:
        letra = feat["properties"]["iso_id"].split("-")[-1]
        geom = feat["geometry"]
        polys = [geom["coordinates"]] if geom["type"] == "Polygon" else geom["coordinates"]
        for poly in polys:
            xs = [p[0] for p in poly[0]]
            ys = [p[1] for p in poly[0]]
            _POLIS.append((letra, (min(xs), min(ys), max(xs), max(ys)), poly))
    return _POLIS


def _dentro_anillo(x, y, anillo):
    dentro = False
    j = len(anillo) - 1
    for i in range(len(anillo)):
        xi, yi = anillo[i][0], anillo[i][1]
        xj, yj = anillo[j][0], anillo[j][1]
        if (yi > y) != (yj > y) and x < (xj - xi) * (y - yi) / ((yj - yi) or 1e-12) + xi:
            dentro = not dentro
        j = i
    return dentro


def provincia_de_punto(lat, lon):
    """Letra de la provincia que contiene (lat, lon), o None."""
    for letra, (x0, y0, x1, y1), poly in _cargar_poligonos():
        if not (x0 <= lon <= x1 and y0 <= lat <= y1):
            continue
        if _dentro_anillo(lon, lat, poly[0]) and not any(_dentro_anillo(lon, lat, h) for h in poly[1:]):
            return letra
    return None


def provincias_de_telefono(digitos):
    """Recibe los digitos de un telefono y devuelve las letras de provincia posibles
    segun la caracteristica, o '' si no se reconoce."""
    d = re.sub(r"\D", "", digitos)
    if d.startswith("54"):
        d = d[2:]
    if d.startswith("9"):
        d = d[1:]
    d = d.lstrip("0")
    if len(d) != 10:
        # formato viejo con 15 en el medio (ej 0379 15 4123456) -> sacar el 15
        m = re.match(r"^(\d{2,4})15(\d{6,8})$", d)
        if m and len(m.group(1) + m.group(2)) == 10:
            d = m.group(1) + m.group(2)
        else:
            return ""
    for n in (4, 3, 2):
        if d[:n] in CARACTERISTICAS:
            return CARACTERISTICAS[d[:n]]
    return ""


def provincia_de_cp(cp):
    """CP numerico de 4 digitos -> letra (solo rangos seguros)."""
    try:
        n = int(cp)
    except ValueError:
        return None
    for (a, b), letra in CP_RANGOS:
        if a <= n <= b:
            return letra
    return None
