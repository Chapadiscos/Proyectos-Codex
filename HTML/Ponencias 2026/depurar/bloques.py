"""Utilidades para reconocer bloques del HTML de InDesign (imágenes, pies, ladillos)."""

import re

from bs4 import NavigableString, Tag

CONTENEDORES = ("body", "li")
PIE = "Pie-Figura"


def es_bloque_imagen(tag):
    return isinstance(tag, Tag) and (tag.name == "img" or (tag.name in ("div", "a") and tag.find("img") is not None))


def tiene_clase(tag, patron):
    return isinstance(tag, Tag) and any(re.search(patron, c) for c in tag.get("class", []))


def es_figura(tag, clase_pie=PIE):
    """Contenedor con solo imágenes y pies (no un marco con el texto del capítulo)."""
    hijos = [h for h in tag.children if isinstance(h, Tag)]
    return bool(hijos) and all(es_bloque_imagen(h) or tiene_clase(h, clase_pie) for h in hijos)


def bloque_de(img, clase_pie=PIE):
    """El elemento que contiene la imagen dentro del flujo de texto."""
    bloque = img
    while bloque.parent is not None and bloque.parent.name not in CONTENEDORES and es_figura(bloque.parent, clase_pie):
        bloque = bloque.parent
    return bloque


def hermano(tag, sentido):
    """Hermano anterior/siguiente ignorando espacios; devuelve texto si lo hay (contenido en línea)."""
    nodo = tag.previous_sibling if sentido < 0 else tag.next_sibling
    while isinstance(nodo, NavigableString) and not nodo.strip():
        nodo = nodo.previous_sibling if sentido < 0 else nodo.next_sibling
    return nodo
