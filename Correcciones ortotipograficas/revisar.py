#!/usr/bin/env python3
"""
Revisión ortotipográfica de PDFs para edición editorial.

Analiza uno o varios PDF y genera, para cada uno:
  - salida/<nombre>_comentarios.pdf  -> copia del PDF con anotaciones
    (resaltado + comentario) importables en Adobe Acrobat / InDesign.
  - salida/<nombre>_informe.csv      -> listado de todas las incidencias
    detectadas (página, categoría, texto, sugerencia).

Uso:
    python3 revisar.py entrada/mi_libro.pdf
    python3 revisar.py entrada/*.pdf
    python3 revisar.py entrada/mi_libro.pdf --sin-gramatica   (omite LanguageTool)

Requiere: pymupdf, language_tool_python (con el JRE incluido en tools/jre).
"""

import argparse
import csv
import os
import re
import sys
from collections import Counter, defaultdict

import fitz  # PyMuPDF

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
JAVA_HOME = os.path.join(BASE_DIR, "tools", "jre", "Contents", "Home")
if os.path.isdir(JAVA_HOME):
    os.environ["JAVA_HOME"] = JAVA_HOME
    os.environ["PATH"] = os.path.join(JAVA_HOME, "bin") + os.pathsep + os.environ.get("PATH", "")

SALIDA_DIR = os.path.join(BASE_DIR, "salida")

AUTOR_COMENTARIO = "Revisión ortotipográfica"

# Colores de resaltado por categoría (RGB 0-1) para distinguir tipos de incidencia
COLOR = {
    "ortografia": (1, 0.6, 0.6),
    "criterio": (1, 0.85, 0.3),
    "tabla": (0.6, 0.8, 1),
    "ladillo": (0.7, 1, 0.7),
    "mayusculas": (0.85, 0.7, 1),
    "numeros": (1, 0.7, 0.4),
}


class Incidencia:
    __slots__ = ("pagina", "categoria", "texto", "mensaje", "rects")

    def __init__(self, pagina, categoria, texto, mensaje, rects):
        self.pagina = pagina
        self.categoria = categoria
        self.texto = texto
        self.mensaje = mensaje
        self.rects = rects


# ---------------------------------------------------------------------------
# Reconstrucción de texto por página con mapa de posiciones exactas.
#
# PyMuPDF separa el texto en "palabras" con su caja delimitadora. Cuando una
# palabra queda partida por un guion blando (\xad) al final de línea, se junta
# con la siguiente antes de analizar ortografía/gramática/regex, para no
# generar falsos errores como "perifé" + "rico". Cada fragmento del texto
# reconstruido conserva la lista de cajas (rects) del PDF a las que
# corresponde, para poder resaltar exactamente esa posición y ninguna otra
# (en vez de volver a buscar el texto literal, que puede repetirse en la
# página y desplazar el resaltado a una ocurrencia equivocada).
# ---------------------------------------------------------------------------

def construir_pagina(page):
    palabras = page.get_text("words")
    palabras.sort(key=lambda w: (w[5], w[6], w[7]))

    tokens = []
    pend_texto = ""
    pend_rects = []
    for x0, y0, x1, y1, palabra, *_ in palabras:
        continua = palabra.endswith("\xad")
        limpio = palabra.rstrip("\xad")
        rect = fitz.Rect(x0, y0, x1, y1)
        if pend_texto:
            pend_texto += limpio
            pend_rects.append(rect)
        else:
            pend_texto = limpio
            pend_rects = [rect]
        if not continua:
            if pend_texto:
                tokens.append((pend_texto, pend_rects))
            pend_texto, pend_rects = "", []
    if pend_texto:
        tokens.append((pend_texto, pend_rects))

    texto = ""
    mapa = []  # (inicio, fin, rects) por token, ordenado por inicio
    for tok_texto, rects in tokens:
        inicio = len(texto)
        texto += tok_texto
        mapa.append((inicio, len(texto), rects))
        texto += " "
    return texto.rstrip(), mapa


def rects_en_rango(mapa, inicio, fin):
    """Cajas del PDF cubiertas por el rango de caracteres [inicio, fin)."""
    rects = []
    for s, e, rs in mapa:
        if e <= inicio or s >= fin:
            continue
        rects.extend(rs)
    return rects


# ---------------------------------------------------------------------------
# Reglas de unificación de criterio: Fig./Figura, Tab./Tabla, etc.
# ---------------------------------------------------------------------------

CRITERIOS_ALTERNANCIA = [
    r"\bFig(?:\.|ura)\s*\d+(?:\.\d+)*",
    r"\bTab(?:\.|la)\s*\d+(?:\.\d+)*",
    r"\bGráf(?:\.|ico)\s*\d+(?:\.\d+)*",
]

PIE_FIGURA_TABLA = re.compile(
    r"^(Figura|Fig|Tabla|Tab|Gr[aá]fico|Gr[aá]f|Esquema|Algoritmo)\b\.?\s*\d*\.?",
    re.IGNORECASE,
)


def detectar_alternancia_criterio(paginas):
    """Unifica Fig./Figura, Tab./Tabla, Gráf./Gráfico -- pero por separado
    para los pies de figura/tabla ("Figura 6.1: ...") y para las referencias
    dentro del texto ("ver Fig. 6.1"), porque es habitual editorialmente usar
    la forma completa en el pie y la abreviada en el cuerpo del texto: no es
    una inconsistencia real, sino dos convenciones distintas que conviven."""
    incidencias = []
    for patron in CRITERIOS_ALTERNANCIA:
        regex = re.compile(patron, re.IGNORECASE)
        grupos = {"pie": (Counter(), []), "referencia": (Counter(), [])}
        for num_pag, texto, mapa in paginas:
            for m in regex.finditer(texto):
                encontrado = m.group(0)
                forma = "abreviada" if re.match(r"^\w+\.", encontrado) else "completa"
                resto = texto[m.end(): m.end() + 2].lstrip()
                contexto = "pie" if resto.startswith(":") else "referencia"
                conteo, ocurrencias = grupos[contexto]
                conteo[forma] += 1
                ocurrencias.append((num_pag, mapa, m, forma))

        for contexto, (conteo, ocurrencias) in grupos.items():
            if not ocurrencias or len(conteo) < 2:
                continue  # no hay alternancia en este contexto, nada que unificar
            forma_dominante = conteo.most_common(1)[0][0]
            for num_pag, mapa, m, forma in ocurrencias:
                if forma != forma_dominante:
                    rects = rects_en_rango(mapa, m.start(), m.end())
                    if not rects:
                        continue
                    etiqueta = "pie de figura/tabla" if contexto == "pie" else "referencia en el texto"
                    incidencias.append(
                        Incidencia(
                            num_pag,
                            "criterio",
                            m.group(0),
                            f'Unificar criterio en {etiqueta}: se usa mayoritariamente la forma '
                            f'"{forma_dominante}" en este contexto; aquí aparece "{m.group(0)}".',
                            rects,
                        )
                    )
    return incidencias


# ---------------------------------------------------------------------------
# Celdas de tabla que terminan en "."
# ---------------------------------------------------------------------------

def detectar_puntos_en_tablas(doc):
    incidencias = []
    for num_pag in range(len(doc)):
        page = doc[num_pag]
        try:
            tablas = page.find_tables()
        except Exception:
            continue
        for tabla in tablas.tables if hasattr(tablas, "tables") else tablas:
            try:
                filas = tabla.extract()
            except Exception:
                continue
            # Tablas de 1 fila o 1 columna suelen ser párrafos mal detectados
            # como tabla (falso positivo del detector de estructura visual).
            if len(filas) < 2 or len(tabla.rows) != len(filas):
                continue
            if any(len(fila) < 2 for fila in filas):
                continue
            for fila_texto, fila_row in zip(filas, tabla.rows):
                for celda, rect in zip(fila_texto, fila_row.cells):
                    if not celda or rect is None:
                        continue
                    texto = celda.strip()
                    if not texto or len(texto) > 80 or "\n" in texto:
                        continue  # probablemente no es un valor de celda real
                    if PIE_FIGURA_TABLA.match(texto):
                        continue  # es un pie de figura/tabla, no una celda de datos
                    if texto.endswith(".") and not texto.endswith(".."):
                        incidencias.append(
                            Incidencia(
                                num_pag,
                                "tabla",
                                texto,
                                "Las celdas de tabla no deben terminar en punto: "
                                f'"{texto}".',
                                [fitz.Rect(rect)],
                            )
                        )
    return incidencias


# ---------------------------------------------------------------------------
# Ladillos (encabezados marginales/laterales cortos) que terminan en "."
# Heurística: línea aislada, corta, en negrita, que ocupa poco ancho de página.
# ---------------------------------------------------------------------------

def detectar_puntos_en_ladillos(doc):
    incidencias = []
    for num_pag in range(len(doc)):
        page = doc[num_pag]
        pw = page.rect.width
        datos = page.get_text("dict")
        for block in datos.get("blocks", []):
            if block.get("type") != 0:
                continue
            lineas = block.get("lines", [])
            if len(lineas) != 1:
                continue  # un ladillo suele ser una línea corta y aislada
            linea = lineas[0]
            spans = linea.get("spans", [])
            if not spans:
                continue
            texto = "".join(s["text"] for s in spans).strip()
            if not texto or not texto.endswith(".") or texto.endswith(".."):
                continue
            if len(texto) > 60:
                continue
            if PIE_FIGURA_TABLA.match(texto):
                continue  # es un pie de figura/tabla (debe llevar punto), no un ladillo
            ancho_bloque = block["bbox"][2] - block["bbox"][0]
            es_negrita = any("Bold" in s.get("font", "") for s in spans)
            estrecho = ancho_bloque < pw * 0.45
            if es_negrita and estrecho:
                incidencias.append(
                    Incidencia(
                        num_pag,
                        "ladillo",
                        texto,
                        f'Posible ladillo terminado en punto: "{texto}". '
                        "Revisar si debe eliminarse el punto final (verificar visualmente).",
                        [fitz.Rect(block["bbox"])],
                    )
                )
    return incidencias


# ---------------------------------------------------------------------------
# Consistencia de mayúsculas/minúsculas en títulos
# ---------------------------------------------------------------------------

def clasificar_caja(texto):
    letras = [c for c in texto if c.isalpha()]
    if not letras:
        return None
    if all(c.isupper() for c in letras):
        return "MAYUSCULAS"
    palabras = texto.split()
    palabras_alpha = [p for p in palabras if any(c.isalpha() for c in p)]
    if not palabras_alpha:
        return None
    capitalizadas = sum(1 for p in palabras_alpha if p[0].isupper())
    if capitalizadas / len(palabras_alpha) > 0.7 and len(palabras_alpha) > 1:
        return "Cada Palabra En Mayuscula"
    return "Frase normal"


def detectar_inconsistencia_titulos(doc):
    incidencias = []
    candidatos = defaultdict(list)  # (tamaño, negrita) -> [(pagina, texto, bbox)]
    for num_pag in range(len(doc)):
        page = doc[num_pag]
        datos = page.get_text("dict")
        for block in datos.get("blocks", []):
            if block.get("type") != 0:
                continue
            for linea in block.get("lines", []):
                spans = linea.get("spans", [])
                if not spans:
                    continue
                texto = "".join(s["text"] for s in spans).strip()
                if not texto or len(texto) > 90 or len(texto.split()) < 2:
                    continue
                tam = round(spans[0]["size"])
                es_negrita = any("Bold" in s.get("font", "") for s in spans)
                if tam >= 12 or es_negrita:
                    clave = (tam, es_negrita)
                    candidatos[clave].append((num_pag, texto, linea["bbox"]))

    for clave, items in candidatos.items():
        if len(items) < 3:
            continue  # necesitamos varias muestras del mismo "nivel" para hablar de un patrón
        cajas = [clasificar_caja(t) for _, t, _ in items]
        cajas_validas = [c for c in cajas if c]
        if not cajas_validas:
            continue
        dominante, n_dominante = Counter(cajas_validas).most_common(1)[0]
        if n_dominante / len(cajas_validas) < 0.6:
            continue  # no hay un patrón claro, no forzamos nada
        for (num_pag, texto, bbox), caja in zip(items, cajas):
            if caja and caja != dominante:
                incidencias.append(
                    Incidencia(
                        num_pag,
                        "mayusculas",
                        texto,
                        f'Inconsistencia de caja en título/encabezado (patrón dominante: "{dominante}"): '
                        f'"{texto}".',
                        [fitz.Rect(bbox)],
                    )
                )
    return incidencias


# ---------------------------------------------------------------------------
# Formato numérico (separadores de miles/decimales) y fechas
# ---------------------------------------------------------------------------

NUM_MILES_PUNTO = re.compile(r"\b[1-9]\d{0,2}(?:\.\d{3})+(?:,\d+)?\b")   # 100.000 / 1.234.567,89
NUM_MILES_COMA = re.compile(r"\b[1-9]\d{0,2}(?:,\d{3})+(?:\.\d+)?\b")     # 100,000 / 1,234,567.89
NUM_SIN_SEPARADOR = re.compile(r"(?<!\d[.,])\b\d{4,}\b(?![.,]\d)")   # 1234567
# Un número con exactamente 3 cifras tras el separador es ambiguo con el
# formato de miles (100.000), salvo que la parte entera sea "0" (0.001, un
# valor decimal claro, nunca una cifra de miles). (?!\d*/) descarta DOIs
# bibliográficos del tipo "10.1016/j.oftal....".
NUM_DECIMAL_PUNTO = re.compile(r"(?<![\d.,])-?(?:\d+\.\d{1,2}(?!\d)|0\.\d{3,})(?!\d*/)\b")
NUM_DECIMAL_COMA = re.compile(r"(?<![\d.,])-?(?:\d+,\d{1,2}(?!\d)|0,\d{3,})\b")
DOI_PATRON = re.compile(r"\b10\.\d{4,9}/\S+")

FECHA_BARRAS = re.compile(r"\b\d{1,2}/\d{1,2}/\d{2,4}\b")
FECHA_GUIONES = re.compile(r"\b\d{1,2}-\d{1,2}-\d{2,4}\b")
FECHA_LARGA = re.compile(r"\b\d{1,2}\s+de\s+[a-zA-Zá-úÁ-Ú]+\s+de\s+\d{4}\b")


def enmascarar_referencias(texto):
    """Sustituye por espacios las referencias tipo "Figura 6.1" y los DOI
    bibliográficos ("10.1016/j.oftal...") para que sus números no se
    confundan con decimales/formatos numéricos a unificar."""
    resultado = list(texto)
    for patron in list(CRITERIOS_ALTERNANCIA) + [DOI_PATRON.pattern]:
        for m in re.finditer(patron, texto, re.IGNORECASE):
            for i in range(m.start(), m.end()):
                resultado[i] = " "
    return "".join(resultado)


def detectar_formato_numeros_fechas(paginas):
    incidencias = []

    for grupos, categoria_msg in (
        (
            ((NUM_MILES_PUNTO, "miles con punto (1.234.567)"), (NUM_MILES_COMA, "miles con coma (1,234,567)")),
            "Formato numérico inconsistente",
        ),
        (
            ((NUM_DECIMAL_PUNTO, "decimal con punto (4.2)"), (NUM_DECIMAL_COMA, "decimal con coma (4,2)")),
            "Separador decimal inconsistente",
        ),
        (
            (
                (FECHA_BARRAS, "dd/mm/aaaa"),
                (FECHA_GUIONES, "dd-mm-aaaa"),
                (FECHA_LARGA, "dd de mes de aaaa"),
            ),
            "Formato de fecha inconsistente",
        ),
    ):
        conteo = Counter()
        ocurrencias = []  # (num_pag, mapa, match, estilo)
        for num_pag, texto, mapa in paginas:
            texto_masc = enmascarar_referencias(texto)
            for regex, estilo in grupos:
                for m in regex.finditer(texto_masc):
                    conteo[estilo] += 1
                    ocurrencias.append((num_pag, mapa, m, estilo))

        if len(conteo) < 2:
            continue
        estilo_dominante = conteo.most_common(1)[0][0]
        for num_pag, mapa, m, estilo in ocurrencias:
            if estilo == estilo_dominante:
                continue
            rects = rects_en_rango(mapa, m.start(), m.end())
            if not rects:
                continue
            incidencias.append(
                Incidencia(
                    num_pag,
                    "numeros",
                    m.group(0),
                    f'{categoria_msg} (se usa mayoritariamente "{estilo_dominante}"): "{m.group(0)}".',
                    rects,
                )
            )

    return incidencias


# ---------------------------------------------------------------------------
# Ortografía y gramática (LanguageTool, motor local)
# ---------------------------------------------------------------------------

def es_probable_sigla(fragmento):
    """Siglas/abreviaturas técnicas (PACD, PIO, SAP...) casi nunca son errores
    reales; LanguageTool las marca por no conocerlas. Se descartan para evitar
    ruido: si el texto va todo en mayúsculas y es corto, se asume sigla."""
    letras = [c for c in fragmento if c.isalpha()]
    return bool(letras) and len(fragmento) <= 6 and all(c.isupper() for c in letras)


def detectar_ortografia_gramatica(paginas):
    import language_tool_python

    incidencias = []
    tool = language_tool_python.LanguageTool("es")
    try:
        for num_pag, texto, mapa in paginas:
            if not texto.strip():
                continue
            try:
                matches = tool.check(texto)
            except Exception as e:
                print(f"  [aviso] LanguageTool falló en página {num_pag + 1}: {e}", file=sys.stderr)
                continue
            for m in matches:
                fragmento = texto[m.offset: m.offset + m.error_length]
                if not fragmento.strip() or es_probable_sigla(fragmento):
                    continue
                rects = rects_en_rango(mapa, m.offset, m.offset + m.error_length)
                if not rects:
                    continue
                sugerencias = ", ".join(m.replacements[:3]) if m.replacements else "(sin sugerencia)"
                incidencias.append(
                    Incidencia(
                        num_pag,
                        "ortografia",
                        fragmento,
                        f"{m.message} Sugerencia: {sugerencias}.",
                        rects,
                    )
                )
    finally:
        tool.close()
    return incidencias


# ---------------------------------------------------------------------------
# Motor principal
# ---------------------------------------------------------------------------

def construir_paginas(doc):
    return [(i, *construir_pagina(doc[i])) for i in range(len(doc))]


def anotar_pdf(doc, incidencias):
    for inc in incidencias:
        page = doc[inc.pagina]
        if not inc.rects:
            continue
        try:
            annot = page.add_highlight_annot(inc.rects)
        except Exception:
            continue
        color = COLOR.get(inc.categoria, (1, 1, 0))
        annot.set_colors(stroke=color)
        annot.set_info(title=AUTOR_COMENTARIO, content=f"[{inc.categoria.upper()}] {inc.mensaje}")
        annot.set_opacity(0.4)
        annot.update()


def escribir_informe_csv(ruta_csv, incidencias):
    with open(ruta_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["pagina", "categoria", "texto", "comentario"])
        for inc in sorted(incidencias, key=lambda i: (i.pagina, i.categoria)):
            writer.writerow([inc.pagina + 1, inc.categoria, inc.texto, inc.mensaje])


def procesar_pdf(ruta_pdf, con_gramatica=True, con_mayusculas=True):
    print(f"\n== Procesando: {os.path.basename(ruta_pdf)} ==")
    doc = fitz.open(ruta_pdf)
    paginas = construir_paginas(doc)

    incidencias = []

    print("- Unificando criterios (Fig./Figura, Tab./Tabla...)")
    incidencias += detectar_alternancia_criterio(paginas)

    print("- Revisando puntos finales en celdas de tabla")
    incidencias += detectar_puntos_en_tablas(doc)

    print("- Revisando puntos finales en ladillos")
    incidencias += detectar_puntos_en_ladillos(doc)

    if con_mayusculas:
        print("- Revisando consistencia de mayúsculas en títulos")
        incidencias += detectar_inconsistencia_titulos(doc)

    print("- Revisando formato de números y fechas")
    incidencias += detectar_formato_numeros_fechas(paginas)

    if con_gramatica:
        print("- Revisando ortografía y gramática (LanguageTool, puede tardar)")
        incidencias += detectar_ortografia_gramatica(paginas)

    print(f"- Total incidencias detectadas: {len(incidencias)}")

    os.makedirs(SALIDA_DIR, exist_ok=True)
    base = os.path.splitext(os.path.basename(ruta_pdf))[0]

    anotar_pdf(doc, incidencias)
    ruta_pdf_salida = os.path.join(SALIDA_DIR, f"{base}_comentarios.pdf")
    doc.save(ruta_pdf_salida, garbage=4, deflate=True)
    doc.close()
    print(f"- PDF con comentarios: {ruta_pdf_salida}")

    ruta_csv = os.path.join(SALIDA_DIR, f"{base}_informe.csv")
    escribir_informe_csv(ruta_csv, incidencias)
    print(f"- Informe CSV: {ruta_csv}")


def encontrar_pdfs_por_defecto():
    """Sin argumentos: busca PDF sueltos en la carpeta del proyecto y en entrada/."""
    import glob

    rutas = []
    for patron in (
        os.path.join(BASE_DIR, "*.pdf"),
        os.path.join(BASE_DIR, "entrada", "*.pdf"),
    ):
        rutas.extend(glob.glob(patron))
    # evita duplicados manteniendo el orden
    vistos = set()
    unicas = []
    for r in rutas:
        if r not in vistos:
            vistos.add(r)
            unicas.append(r)
    return unicas


def main():
    parser = argparse.ArgumentParser(description="Revisión ortotipográfica de PDFs.")
    parser.add_argument(
        "pdfs",
        nargs="*",
        help="Rutas a los PDF a procesar. Si se omite, busca PDF en la carpeta "
        "del proyecto y en entrada/.",
    )
    parser.add_argument(
        "--sin-gramatica",
        action="store_true",
        help="Omite la revisión ortográfica/gramatical (LanguageTool), útil para pruebas rápidas "
        "o para libros de vocabulario muy técnico donde genera mucho ruido",
    )
    parser.add_argument(
        "--sin-mayusculas",
        action="store_true",
        help="Omite la revisión de consistencia de mayúsculas en títulos. Recomendable en libros "
        "corales con muchos autores, donde esta heurística puede confundir nombres/cargos con títulos",
    )
    args = parser.parse_args()

    rutas = args.pdfs or encontrar_pdfs_por_defecto()
    if not rutas:
        print("No se ha encontrado ningún PDF. Coloca uno en esta carpeta o en entrada/.")
        return

    for ruta in rutas:
        if not os.path.isfile(ruta):
            print(f"[error] No existe el archivo: {ruta}", file=sys.stderr)
            continue
        procesar_pdf(
            ruta,
            con_gramatica=not args.sin_gramatica,
            con_mayusculas=not args.sin_mayusculas,
        )


if __name__ == "__main__":
    main()
