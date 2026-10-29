#!/usr/bin/env python3
"""
Extrae del PDF de un informe (Cuadros, Gráficos, Esquemas, Recuadros) los datos
necesarios para construir el índice: número, título y página.

Uso:
    python3 extraer_indice.py InformeAnual_2025.pdf salida.json
    python3 extraer_indice.py --a-jsx salida.json   (solo regenera el .jsx
                                                      tras retocar el .json)

Funciona con cualquier PDF que siga el patrón editorial del Banco de España:
la etiqueta ("Gráfico 1.1", "Cuadro 2.3", "Esquema 1.1", "Recuadro 3.2") va
en una línea propia y el título en las líneas que la siguen, alineadas con
ella. Se trabaja línea a línea y en el sentido de lectura de cada una (también
en páginas apaisadas con el texto girado), sin fiarse de cómo agrupa el PDF el
texto en bloques: a veces junta título y etiqueta en el mismo bloque y con el
título delante.

Los títulos de los recuadros, que en el PDF van en mayúsculas, se pasan a
minúsculas conservando nombres propios y siglas tal como los escribe el propio
PDF en su texto corrido (ver pasar_a_minusculas).
"""

import sys
import json
import re
from collections import Counter, defaultdict

import fitz  # PyMuPDF

CATEGORIAS = [
    "Cuadro", "Gráfico", "Esquema", "Figura", "Recuadro",
    "Table", "Chart", "Schema", "Figure", "Box",
]
INGLES = {"Table", "Chart", "Schema", "Figure", "Box"}

# Línea con la etiqueta sola: "Cuadro 1.1", "Table A1.2", "Recuadro 3.2"...
ETIQUETA_RE = re.compile(
    r"^(Cuadro|Gr[aá]fico|Esquema|Figura|Recuadro|Table|Chart|Schema|Figure|Box)\s+([A-Za-z]?\d+\.\d+)$"
)

# Los recuadros/boxes se repiten en cada página que ocupan añadiendo
# "(cont.)"/"(cont'd)" al título.
CONT_RE = re.compile(r"\s*\(cont[.’']?d?\.?\)\s*$")

# Título de "placeholder" de maquetación sin traducir que a veces queda
# entre la etiqueta y el título real (p. ej. "X.a  Título del panel").
PLACEHOLDER_RE = re.compile(r"^X\.[a-z]\s+T[ií]tulo del panel$", re.IGNORECASE)

# Ligaduras tipográficas que algunos PDF dan como un solo carácter.
LIGADURAS = str.maketrans({"ﬀ": "ff", "ﬁ": "fi", "ﬂ": "fl", "ﬃ": "ffi", "ﬄ": "ffl"})

# Líneas que nunca son el título real (pie de página, nota de fuentes...):
# en tablas apaisadas el título va ANTES de la etiqueta, no después, así que
# entonces se busca por encima de ella.
NO_TITULO_RE = re.compile(
    r"^(\d+\s*Banco de España|SOURCES?:|FUENTES?:)", re.IGNORECASE
)

# Cuando en un documento en un idioma aparece suelta alguna etiqueta en el
# otro idioma (typo de maquetación), se fusiona con su categoría equivalente.
SINONIMOS = {
    "Cuadro": "Table", "Gráfico": "Chart", "Esquema": "Schema", "Figura": "Figure",
    "Recuadro": "Box",
}

# Palabras cortas que no deben quedarse al final de una línea en el índice:
# el espacio que las sigue pasa a ser de no separación al entregar los datos a
# InDesign. El .json se queda con espacios normales para poder corregirlo.
PALABRAS_UNIDAS = {
    "es": "a al ante bajo con contra de del desde e el en entre hacia hasta la las "
          "lo los mediante ni o para por que según sin so sobre su sus tras u un "
          "una unas unos y",
    "en": "a an and as at by for from in into of on or the to via with",
}
UNIR_RE = {
    idioma: re.compile(r"(?<![^\s>])(" + "|".join(palabras.split()) + r") (?=\S)", re.IGNORECASE)
    for idioma, palabras in PALABRAS_UNIDAS.items()
}
ESPACIO_NO_SEPARACION = "\u00a0"

# Cursivas del PDF, marcadas en el título como <i>…</i>; poblar_indice.jsx
# las quita y aplica el estilo de carácter «Light Italic».
MARCA_RE = re.compile(r"</?i>")


def es_cursiva(span):
    return bool(span["flags"] & 2) or "Italic" in span["font"] or span["font"].endswith("It")


def texto_con_cursivas(spans):
    """Texto de una línea con los tramos en cursiva entre <i> y </i>, y con los
    espacios normalizados (los espacios de los bordes quedan fuera de la marca)."""
    letras = [(ch.translate(LIGADURAS), es_cursiva(s)) for s in spans for ch in s["text"]]
    salida, en_cursiva, espacios = "", False, ""
    for ch, cursiva in letras:
        if ch.isspace():
            espacios = " " if salida else ""
            continue
        if cursiva != en_cursiva:
            salida += ("</i>" + espacios) if en_cursiva else (espacios + "<i>")
            en_cursiva = cursiva
        else:
            salida += espacios
        espacios = ""
        salida += ch
    return salida + ("</i>" if en_cursiva else "")


def sin_marcas(titulo):
    return MARCA_RE.sub("", titulo)


def blocks_en_orden_visual(page):
    """Devuelve los bloques de texto de una página ordenados de arriba a
    abajo y, dentro de una misma franja horizontal, de izquierda a derecha."""
    blocks = page.get_text("blocks")
    return sorted(blocks, key=lambda b: (round(b[1] / 5), b[0]))


def numero_pagina_impreso(page, indice_pdf, avisos=None):
    """Intenta leer el número de página impreso en el pie de página real;
    si no lo encuentra, usa el índice del PDF (1-based) como respaldo."""
    blocks = blocks_en_orden_visual(page)
    if blocks:
        pie = blocks[-1][4].strip()
        primera_linea = pie.split("\n")[0].strip()
        if primera_linea.isdigit():
            return int(primera_linea)
    if avisos is not None:
        avisos.append(
            f"Página {indice_pdf + 1} del PDF: no se encuentra el número "
            f"impreso en el pie; se usa {indice_pdf + 1}"
        )
    return indice_pdf + 1


def lineas_de_pagina(page):
    """Líneas de texto de la página con su posición medida en su propio
    sentido de lectura: «ini» a lo largo de la línea y «arriba»/«abajo»
    en perpendicular. Así una página apaisada con el texto girado se trata
    igual que una normal."""
    lineas = []
    for b in page.get_text("dict")["blocks"]:
        if b["type"] != 0:
            continue
        for l in b["lines"]:
            marcado = texto_con_cursivas(l["spans"])
            texto = sin_marcas(marcado)
            if not texto:
                continue
            cos, sin = l["dir"]
            x0, y0, x1, y1 = l["bbox"]
            esquinas = [(x0, y0), (x1, y0), (x0, y1), (x1, y1)]
            a_lo_largo = [x * cos + y * sin for x, y in esquinas]
            en_perpendicular = [-x * sin + y * cos for x, y in esquinas]
            principal = max(l["spans"], key=lambda s: len(s["text"].strip()))
            lineas.append({
                "texto": texto,
                "marcado": marcado,
                "dir": (round(cos, 2), round(sin, 2)),
                "ini": min(a_lo_largo),
                "arriba": min(en_perpendicular),
                "abajo": max(en_perpendicular),
                # Para saber si una línea sigue el título: cuerpo y negrita, que
                # no cambian cuando parte del título va en cursiva (la fuente sí).
                "fuente": (round(principal["size"], 1), bool(principal["flags"] & 16)),
                "cuerpo": principal["size"],
            })
    return lineas


def vecina(ref, lineas, despues, distancia):
    """La línea más cercana justo después (o antes) de `ref`, en su mismo
    sentido de lectura, alineada con ella y a menos de `distancia`."""
    mejor = None
    for l in lineas:
        if l is ref or l["dir"] != ref["dir"] or abs(l["ini"] - ref["ini"]) > 15:
            continue
        # Las cajas de líneas seguidas pueden solaparse un poco (interlineado
        # justo): basta con que la línea empiece claramente después.
        if despues:
            avance, hueco = l["arriba"] - ref["arriba"], l["arriba"] - ref["abajo"]
        else:
            avance, hueco = ref["abajo"] - l["abajo"], ref["arriba"] - l["abajo"]
        if avance > 0.3 * ref["cuerpo"] and hueco <= distancia and (mejor is None or hueco < mejor[0]):
            mejor = (hueco, l)
    return mejor[1] if mejor else None


def titulo_junto_a(etiqueta, lineas, despues):
    """Título pegado a la etiqueta (después o antes): la primera línea
    alineada con ella y las que la siguen con la misma fuente."""
    distancia = 2 * etiqueta["cuerpo"]
    primera = vecina(etiqueta, lineas, despues, distancia)
    while primera is not None and PLACEHOLDER_RE.match(primera["texto"]):
        primera = vecina(primera, lineas, despues, distancia)
    if (primera is None or NO_TITULO_RE.match(primera["texto"])
            or ETIQUETA_RE.match(primera["texto"])):
        return ""
    partes = [primera]
    while True:
        otra = vecina(partes[-1], lineas, despues, 0.8 * partes[-1]["cuerpo"])
        if otra is None or otra["fuente"] != primera["fuente"]:
            break
        partes.append(otra)
    if not despues:
        partes.reverse()
    titulo = " ".join(p["marcado"] for p in partes)
    return re.sub(r"</i>(\s*)<i>", r"\1", titulo)  # cursiva que sigue en la línea siguiente


def extraer(pdf_path, avisos):
    doc = fitz.open(pdf_path)
    entradas = defaultdict(list)  # categoria -> lista de dicts
    vistos = set()  # (categoria, numero) ya indexados, para no duplicar
                     # etiquetas que se repiten en páginas de continuación

    for i in range(doc.page_count):
        page = doc[i]
        lineas = lineas_de_pagina(page)
        pagina = None

        for etiqueta in lineas:
            m = ETIQUETA_RE.match(etiqueta["texto"])
            if not m:
                continue
            categoria, numero = m.group(1), m.group(2)
            clave = (categoria, numero)
            if clave in vistos:
                continue  # continuación de una etiqueta ya indexada
            vistos.add(clave)
            if pagina is None:
                pagina = numero_pagina_impreso(page, i, avisos)

            titulo = (titulo_junto_a(etiqueta, lineas, despues=True)
                      or titulo_junto_a(etiqueta, lineas, despues=False))
            titulo = CONT_RE.sub("", titulo).replace("<i></i>", "")

            entradas[categoria].append(
                {"numero": numero, "titulo": titulo, "pagina": pagina}
            )

    # Fusiona etiquetas sueltas en el idioma "equivalente" cuando el resto
    # del documento usa el otro (typos de maquetación como "Cuadro 1.2" en
    # un informe en inglés).
    for origen, destino in SINONIMOS.items():
        if origen in entradas and destino in entradas:
            entradas[destino].extend(entradas.pop(origen))

    return entradas


def clave_orden(numero):
    """Ordena '1.1' < '1.2' < '2.1' < 'A1.1' < 'A1.2' ..."""
    prefijo = re.match(r"^([A-Za-z]*)(\d.*)$", numero)
    letras, resto = prefijo.group(1), prefijo.group(2)
    partes = [int(p) if p.isdigit() else p for p in resto.split(".")]
    return (letras, partes)


# Títulos que no parecen el título real de la figura: muy cortos, que
# empiezan en minúscula o que son notas/fuentes.
TITULO_SOSPECHOSO_RE = re.compile(
    r"^([a-záéíóúñ]|(Fuentes?|Sources?|Notas?|Notes?)\b)"
)


def revisar(resultado, avisos):
    """Añade a `avisos` lo que conviene mirar a mano antes de maquetar:
    títulos vacíos o raros, huecos en la numeración y páginas que retroceden."""
    for cat, lista in resultado.items():
        por_capitulo = defaultdict(list)
        pagina_anterior = None
        for e in lista:
            etiqueta = f"{cat} {e['numero']} (pág. {e['pagina']})"
            titulo = sin_marcas(e["titulo"])
            if not titulo:
                avisos.append(f"{etiqueta}: sin título")
            elif len(titulo) < 10 or TITULO_SOSPECHOSO_RE.match(titulo):
                avisos.append(f"{etiqueta}: título sospechoso: «{titulo}»")
            if pagina_anterior is not None and e["pagina"] < pagina_anterior:
                avisos.append(
                    f"{etiqueta}: la página es menor que la de la entrada anterior"
                )
            pagina_anterior = e["pagina"]
            capitulo, _, orden = e["numero"].rpartition(".")
            if orden.isdigit():
                por_capitulo[capitulo].append(int(orden))
        for capitulo, ordenes in por_capitulo.items():
            faltan = sorted(set(range(1, max(ordenes) + 1)) - set(ordenes))
            if faltan:
                lista_faltan = ", ".join(f"{capitulo}.{n}" for n in faltan)
                avisos.append(f"{cat}: faltan {lista_faltan}")


def unir_palabras_cortas(titulo, idioma):
    return UNIR_RE[idioma].sub(r"\1" + ESPACIO_NO_SEPARACION, titulo)


# Recuadros a minúsculas. Cada palabra se escribe como la escribe el texto
# corrido del propio PDF: así «Banco de España», «Mecanismo Único de
# Supervisión», «DANA» o «ES_DataLab» se conservan sin mantener listas a mano.
CATEGORIAS_MINUSCULAS = {"Recuadro", "Box"}
PALABRA_RE = re.compile(r"[^\W\d]+")  # letras y guion bajo, sin cifras
TOKEN_TITULO_RE = re.compile(r"</?i>|[^\W\d]+|.", re.S)
# Lo que hay justo antes de una palabra que empieza frase: ahí su mayúscula no
# dice nada.
INICIO_FRASE = set(".!?:;«“\"(•–—")
# Palabras que van siempre en minúscula dentro del título.
FUNCIONALES = set(" ".join(PALABRAS_UNIDAS.values()).split()) | {"its", "their", "s"}
MAX_TRAMO = 6  # palabras del tramo más largo que se busca en el PDF
UMBRAL_MAYUSCULA = 0.8  # proporción de apariciones que deben ir así


def palabras_del_cuerpo(doc):
    """Palabras del texto corrido del PDF como (forma, informativa): no es
    informativa la que empieza frase o bloque ni la que va en una racha de
    mayúsculas (títulos, cabeceras), porque su mayúscula no dice nada."""
    palabras = []
    for page in doc:
        for b in page.get_text("blocks"):
            texto = b[4].translate(LIGADURAS)
            texto = re.sub(r"-\n(?=[a-záéíóúñ])", "", texto)  # guiones de partición
            anterior = None  # último carácter no blanco
            for linea in texto.split("\n"):
                letras = [c for c in linea if c.isalpha()]
                if len(letras) >= 4 and all(c.isupper() for c in letras):
                    anterior = None
                    continue
                pos = 0
                for m in PALABRA_RE.finditer(linea):
                    hueco = linea[pos:m.start()].strip()
                    if hueco:
                        anterior = hueco[-1]
                    palabras.append((m.group(), anterior is not None and anterior not in INICIO_FRASE))
                    anterior = m.group()[-1]
                    pos = m.end()
                resto = linea[pos:].strip()
                if resto:
                    anterior = resto[-1]

    def en_mayusculas(p):
        return len(p) > 1 and p.isupper()
    for i, (p, _) in enumerate(palabras):
        if en_mayusculas(p) and ((i > 0 and en_mayusculas(palabras[i - 1][0])) or
                                 (i + 1 < len(palabras) and en_mayusculas(palabras[i + 1][0]))):
            palabras[i] = (p, False)
    return palabras


def indice_de_tramos(palabras):
    """Posiciones de cada secuencia de 1 a MAX_TRAMO palabras (en minúsculas)."""
    claves = [p.lower() for p, _ in palabras]
    indice = defaultdict(list)
    for i in range(len(claves)):
        for n in range(1, min(MAX_TRAMO, len(claves) - i) + 1):
            indice[tuple(claves[i:i + n])].append(i)
    return indice


def a_minusculas(titulo, palabras, indice):
    """Pasa a minúsculas un título en mayúsculas, con mayúscula inicial, tras
    punto y al abrir cursiva (título de obra). Las marcas <i></i> se
    conservan, así que el estilo «Light Italic» se sigue aplicando igual."""
    tokens = TOKEN_TITULO_RE.findall(titulo)
    pos_palabras = [k for k, t in enumerate(tokens) if PALABRA_RE.fullmatch(t)]
    claves = [tokens[k].lower() for k in pos_palabras]
    formas = list(claves)
    contenido = [len(c) > 1 and c not in FUNCIONALES for c in claves]

    # Nombres propios de varias palabras: tramos del título que en el PDF
    # llevan casi siempre en mayúscula todas sus palabras de contenido.
    for n in range(MAX_TRAMO, 1, -1):
        for ini in range(len(claves) - n + 1):
            dentro = [ini + k for k in range(n) if contenido[ini + k]]
            if len(dentro) < 2:
                continue
            total, propias = 0, Counter()
            for j in indice.get(tuple(claves[ini:ini + n]), ()):
                vistas = [palabras[j + i - ini][0] for i in dentro if palabras[j + i - ini][1]]
                if not vistas:
                    continue
                total += 1
                if all(f[:1].isupper() for f in vistas):
                    propias[tuple(palabras[j + i - ini][0] for i in dentro)] += 1
            if total and sum(propias.values()) >= UMBRAL_MAYUSCULA * total:
                for i, forma in zip(dentro, propias.most_common(1)[0][0]):
                    if formas[i] == claves[i]:
                        formas[i] = forma

    # Palabras sueltas que casi siempre van con mayúscula (España, DANA...).
    for i, clave in enumerate(claves):
        if not contenido[i] or formas[i] != clave:
            continue
        votos = Counter(palabras[j][0] for j in indice.get((clave,), ()) if palabras[j][1])
        total = sum(votos.values())
        if total >= 2:
            forma, veces = votos.most_common(1)[0]
            if forma != clave and veces >= UMBRAL_MAYUSCULA * total:
                formas[i] = forma

    for k, forma in zip(pos_palabras, formas):
        tokens[k] = forma
    inicio = True
    for k, t in enumerate(tokens):
        if PALABRA_RE.fullmatch(t):
            if inicio:
                tokens[k] = t[0].upper() + t[1:]
            inicio = False
        elif t in ".!?" or t == "<i>":
            inicio = True
    return "".join(tokens)


def pasar_a_minusculas(resultado, pdf_path):
    """Pasa a minúsculas los títulos de recuadros que vienen en mayúsculas.
    Devuelve cuántos ha cambiado."""
    pendientes = [
        e for cat in CATEGORIAS_MINUSCULAS for e in resultado.get(cat, [])
        if sin_marcas(e["titulo"]) == sin_marcas(e["titulo"]).upper()
    ]
    if not pendientes:
        return 0
    palabras = palabras_del_cuerpo(fitz.open(pdf_path))
    indice = indice_de_tramos(palabras)
    for e in pendientes:
        e["titulo"] = a_minusculas(e["titulo"], palabras, indice)
    return len(pendientes)


def guardar_jsx(resultado, salida_jsx):
    # ExtendScript (el motor de scripts de InDesign) no tiene JSON.parse, así
    # que dejamos el mismo contenido como objeto literal .jsx listo para que
    # poblar_indice.jsx lo cargue con $.evalFile().
    para_indesign = {
        cat: [
            dict(e, titulo=unir_palabras_cortas(e["titulo"], "en" if cat in INGLES else "es"))
            for e in lista
        ]
        for cat, lista in resultado.items()
    }
    with open(salida_jsx, "w", encoding="utf-8") as f:
        f.write("var INDICE_DATA = ")
        json.dump(para_indesign, f, ensure_ascii=False)
        f.write(";\n")


def ruta_jsx(salida_json):
    return salida_json[: -len(".json")] + ".jsx"


def main():
    if len(sys.argv) >= 3 and sys.argv[1] == "--a-jsx":
        salida = sys.argv[2]
        with open(salida, encoding="utf-8") as f:
            resultado = json.load(f)
        guardar_jsx(resultado, ruta_jsx(salida))
        print(f"Guardado {ruta_jsx(salida)} a partir de {salida}")
        return

    if len(sys.argv) < 2:
        print("Uso: python3 extraer_indice.py <archivo.pdf> [salida.json]")
        print("     python3 extraer_indice.py --a-jsx <salida.json>")
        sys.exit(1)

    pdf_path = sys.argv[1]
    salida = sys.argv[2] if len(sys.argv) > 2 else "indice_extraido.json"
    if not salida.endswith(".json"):
        salida += ".json"

    avisos = []
    entradas = extraer(pdf_path, avisos)

    for categoria in entradas:
        entradas[categoria].sort(key=lambda e: clave_orden(e["numero"]))

    resultado = {cat: entradas.get(cat, []) for cat in CATEGORIAS if entradas.get(cat)}
    revisar(resultado, avisos)
    pasados = pasar_a_minusculas(resultado, pdf_path)

    with open(salida, "w", encoding="utf-8") as f:
        json.dump(resultado, f, ensure_ascii=False, indent=2)
    guardar_jsx(resultado, ruta_jsx(salida))

    print(f"Guardado {salida}")
    print(f"Guardado {ruta_jsx(salida)} (para poblar_indice.jsx)")
    if not resultado:
        print("  !! No se ha encontrado ninguna etiqueta (Cuadro 1.1, Chart 1.1...)")
    for cat, lista in resultado.items():
        print(f"  {cat}: {len(lista)} entradas")
    if pasados:
        print(f"  Recuadros: {pasados} título(s) pasados a minúsculas; revisa nombres propios y siglas")
    if avisos:
        print(f"\nAvisos para revisar ({len(avisos)}):")
        for a in avisos:
            print(f"  - {a}")


if __name__ == "__main__":
    main()
