#!/usr/bin/env python3
"""
Extrae del PDF de un informe (Cuadros, Gráficos, Esquemas, Recuadros) los datos
necesarios para construir el índice: número, título y página.

Uso:
    python3 extraer_indice.py InformeAnual_2025.pdf salida.json
    python3 extraer_indice.py --a-jsx salida.json   (solo regenera el .jsx
                                                      tras retocar el .json)

Funciona con cualquier PDF que siga el patrón editorial del Banco de España:
en cada página, el bloque de texto con la etiqueta ("Gráfico 1.1", "Cuadro 2.3",
"Esquema 1.1", "Recuadro 3.2") va inmediatamente seguido (en orden visual,
de arriba abajo) por el bloque con el título descriptivo.
"""

import sys
import json
import re
from collections import defaultdict

import fitz  # PyMuPDF

CATEGORIAS = [
    "Cuadro", "Gráfico", "Esquema", "Recuadro",
    "Table", "Chart", "Figure", "Box",
]

# Categorías cuya etiqueta ("Cuadro 1.1", "Table 1.1"...) va en su propio
# bloque de texto, seguida del título en el bloque inmediatamente siguiente.
LABEL_RE = re.compile(
    r"^(Cuadro|Gr[aá]fico|Esquema|Table|Chart|Figure)\s+([A-Za-z]?\d+\.\d+)\s*$"
)

# Los recuadros/boxes llevan la etiqueta y el título en el mismo bloque de
# texto (a diferencia de las categorías anteriores), y se repiten en cada
# página que ocupan añadiendo "(cont.)"/"(cont'd)" al título.
RECUADRO_RE = re.compile(
    r"^(Recuadro|Box)\s+([A-Za-z]?\d+\.\d+)\s*\n(.+)$", re.DOTALL
)
CONT_RE = re.compile(r"\s*\(cont[.’']?d?\.?\)\s*$")

# Resto de un título de "placeholder" de maquetación sin traducir que a
# veces queda pegado delante del título real (p. ej. "X.a  Título del
# panel\n<título real>").
PLACEHOLDER_RE = re.compile(r"^X\.[a-z]\s+T[ií]tulo del panel\s*\n", re.IGNORECASE)

# Bloques que nunca son el título real (pie de página, nota de fuentes...):
# en tablas apaisadas el título va ANTES de la etiqueta, no después, así que
# hay que saltar hacia atrás por encima de estos hasta dar con el título.
NO_TITULO_RE = re.compile(
    r"^(\d+\s*Banco de España|SOURCES?:|FUENTES?:)", re.IGNORECASE
)

# Cuando en un documento en un idioma aparece suelta alguna etiqueta en el
# otro idioma (typo de maquetación), se fusiona con su categoría equivalente.
SINONIMOS = {
    "Cuadro": "Table", "Gráfico": "Chart", "Esquema": "Figure", "Recuadro": "Box",
}


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


def extraer(pdf_path, avisos):
    doc = fitz.open(pdf_path)
    entradas = defaultdict(list)  # categoria -> lista de dicts
    vistos = set()  # (categoria, numero) ya indexados, para no duplicar
                     # etiquetas que se repiten en páginas de continuación

    for i in range(doc.page_count):
        page = doc[i]
        blocks = blocks_en_orden_visual(page)
        pagina = None

        for idx, b in enumerate(blocks):
            texto = b[4].strip()

            m = LABEL_RE.match(texto)
            if m:
                categoria, numero = m.group(1), m.group(2)
                clave = (categoria, numero)
                if clave in vistos:
                    continue  # continuación de una etiqueta ya indexada
                vistos.add(clave)
                if pagina is None:
                    pagina = numero_pagina_impreso(page, i, avisos)

                titulo = ""
                if idx + 1 < len(blocks):
                    titulo = blocks[idx + 1][4]
                    titulo = PLACEHOLDER_RE.sub("", titulo)
                    titulo = " ".join(titulo.split())
                if not titulo or NO_TITULO_RE.match(titulo):
                    # Tablas apaisadas: el título real va ANTES de la
                    # etiqueta, no después (que es pie de página/fuentes).
                    j = idx - 1
                    while j >= 0 and NO_TITULO_RE.match(blocks[j][4].strip()):
                        j -= 1
                    if j >= 0:
                        titulo = " ".join(blocks[j][4].split())

                entradas[categoria].append(
                    {"numero": numero, "titulo": titulo, "pagina": pagina}
                )
                continue

            mr = RECUADRO_RE.match(texto)
            if mr:
                categoria, numero = mr.group(1), mr.group(2)
                clave = (categoria, numero)
                if clave in vistos:
                    continue  # ya indexado en una página anterior (cont.)
                vistos.add(clave)
                if pagina is None:
                    pagina = numero_pagina_impreso(page, i, avisos)

                titulo = " ".join(mr.group(3).split())
                titulo = CONT_RE.sub("", titulo)

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
            titulo = e["titulo"]
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


def guardar_jsx(resultado, salida_jsx):
    # ExtendScript (el motor de scripts de InDesign) no tiene JSON.parse, así
    # que dejamos el mismo contenido como objeto literal .jsx listo para que
    # poblar_indice.jsx lo cargue con $.evalFile().
    with open(salida_jsx, "w", encoding="utf-8") as f:
        f.write("var INDICE_DATA = ")
        json.dump(resultado, f, ensure_ascii=False)
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

    with open(salida, "w", encoding="utf-8") as f:
        json.dump(resultado, f, ensure_ascii=False, indent=2)
    guardar_jsx(resultado, ruta_jsx(salida))

    print(f"Guardado {salida}")
    print(f"Guardado {ruta_jsx(salida)} (para poblar_indice.jsx)")
    if not resultado:
        print("  !! No se ha encontrado ninguna etiqueta (Cuadro 1.1, Chart 1.1...)")
    for cat, lista in resultado.items():
        print(f"  {cat}: {len(lista)} entradas")
    if avisos:
        print(f"\nAvisos para revisar ({len(avisos)}):")
        for a in avisos:
            print(f"  - {a}")


if __name__ == "__main__":
    main()
