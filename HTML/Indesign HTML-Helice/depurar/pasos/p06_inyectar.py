"""Inyecta código propio (fuentes, CSS, scripts) e incrusta el CSS local de InDesign."""

import os
from urllib.parse import unquote

from bs4 import BeautifulSoup

DESTINOS = ("head", "inicio_body", "fin_body")


def aplicar(soup, cfg, ctx, informe):
    if cfg.get("incrustar_css_local", False):
        _incrustar_css_local(soup, ctx, informe)

    for destino in DESTINOS:
        for item in cfg.get(destino) or []:
            nodo = _crear(item, ctx)
            _insertar(soup, destino, nodo)
            informe.contar(f"fragmentos inyectados en {destino}")


def _crear(item, ctx):
    if "archivo" in item:
        with open(ctx["resolver"](item["archivo"]), encoding="utf-8") as f:
            contenido = f.read()
        if item.get("como", "style") == "style":
            contenido = f"<style>\n{contenido}\n</style>"
    elif "css_url" in item:
        contenido = f'<link rel="stylesheet" href="{item["css_url"]}">'
    else:
        contenido = item["html"]
    return BeautifulSoup(contenido, "html.parser")


def _insertar(soup, destino, nodo):
    if destino == "head":
        _asegurar(soup, "head").append(nodo)
    elif destino == "inicio_body":
        _asegurar(soup, "body").insert(0, nodo)
    else:
        _asegurar(soup, "body").append(nodo)


def _asegurar(soup, nombre):
    tag = soup.find(nombre)
    if tag is None:
        tag = soup.new_tag(nombre)
        (soup.html or soup).insert(0 if nombre == "head" else len((soup.html or soup).contents), tag)
    return tag


def _incrustar_css_local(soup, ctx, informe):
    """Sustituye <link> a CSS de *-web-resources por <style> con su contenido."""
    for link in soup.find_all("link", rel="stylesheet"):
        href = link.get("href", "")
        if href.startswith(("http://", "https://", "//")):
            continue
        ruta = os.path.join(ctx["dir_entrada"], unquote(href))
        if not os.path.exists(ruta):
            informe.avisar(f"CSS local no encontrado: {href}")
            continue
        with open(ruta, encoding="utf-8") as f:
            style = soup.new_tag("style")
            style.string = "\n" + f.read() + "\n"
        link.replace_with(style)
        informe.contar("hojas de estilo locales incrustadas")
