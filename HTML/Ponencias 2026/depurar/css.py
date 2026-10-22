"""Lectura simple de la CSS que genera InDesign (sin @media ni reglas anidadas)."""

import os
import re
from urllib.parse import unquote


def leer_reglas(texto):
    """Devuelve [(selectores, {propiedad: valor}), ...]"""
    texto = re.sub(r"/\*.*?\*/", "", texto, flags=re.S)
    texto = re.sub(r"@[a-z-]+[^;{}]*;", "", desescapar(texto))  # @charset, @import
    reglas = []
    for selector, cuerpo in re.findall(r"([^{}]+)\{([^{}]*)\}", texto):
        decl = {}
        for d in cuerpo.split(";"):
            if ":" in d:
                k, v = d.split(":", 1)
                decl[k.strip()] = v.strip()
        reglas.append(([s.strip() for s in selector.split(",")], decl))
    return reglas


def escapar(texto):
    """Caracteres no ASCII como escapes CSS («Viñetas» → «Vi\\F1 etas»): la CSS se lee igual
    aunque Hélice o un editor la abran con otra codificación (salía «ViÃ±etas»)."""
    return "".join(c if ord(c) < 128 else "\\%X " % ord(c) for c in texto)


def desescapar(texto):
    return re.sub(r"\\([0-9a-fA-F]{1,6}) ?", lambda m: chr(int(m.group(1), 16)), texto)


def css_local(soup, dir_entrada, informe):
    """Reglas de las hojas de estilo locales (*-web-resources) enlazadas en el HTML."""
    reglas = []
    for link in soup.find_all("link", rel="stylesheet"):
        href = link.get("href", "")
        if href.startswith(("http://", "https://", "//")):
            continue
        ruta = os.path.join(dir_entrada, unquote(href))
        if not os.path.exists(ruta):
            informe.avisar(f"CSS local no encontrado: {href}")
            continue
        with open(ruta, encoding="utf-8") as f:
            reglas += leer_reglas(f.read())
    return reglas


def _leer_style(tag):
    actual = {}
    for d in tag.get("style", "").split(";"):
        if ":" in d:
            k, v = d.split(":", 1)
            actual[k.strip()] = v.strip()
    return actual


def _escribir_style(tag, decl):
    if decl:
        tag["style"] = "; ".join(f"{k}: {v}" for k, v in decl.items())
    elif tag.has_attr("style"):
        del tag["style"]


def anadir_style(tag, decl):
    """Añade declaraciones al atributo style, sustituyendo las que ya estuvieran."""
    _escribir_style(tag, {**_leer_style(tag), **decl})


def quitar_style(tag, propiedades):
    _escribir_style(tag, {k: v for k, v in _leer_style(tag).items() if k not in propiedades})
