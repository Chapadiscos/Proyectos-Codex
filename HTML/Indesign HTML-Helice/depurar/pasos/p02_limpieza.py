"""Limpieza genérica de lo que InDesign añade y no aporta en la web."""

import re

from bs4 import Tag


def aplicar(soup, cfg, ctx, informe):
    clases = [re.compile(p) for p in cfg.get("clases_eliminar", [])]
    ids = [re.compile(p) for p in cfg.get("ids_eliminar", [])]

    _quitar_clases(soup, clases, informe)
    _quitar_ids(soup, ids, informe)
    if cfg.get("quitar_style_inline"):
        for tag in soup.find_all(style=True):
            del tag["style"]
            informe.contar("atributos style eliminados")
    if cfg.get("quitar_enlaces_vacios", True):
        # Enlaces sin destino (índice, 00F): InDesign los exporta con href="" y salen en azul;
        # en Hélice los crea el usuario a mano. Los enlaces con URL (bibliografía) se conservan.
        for a in soup.find_all("a"):
            if not a.get("href", "").strip() and not a.get("id"):
                a.unwrap()
                informe.contar("enlaces vacíos quitados")
    _quitar_spans(soup, informe)
    if cfg.get("desenvolver_divs_sin_atributos", True):
        for div in soup.find_all("div"):
            if not div.attrs:
                div.unwrap()
                informe.contar("divs sin atributos desenvueltos")
    if cfg.get("fusionar_spans_iguales", True):
        _fusionar_spans(soup, informe)
    if cfg.get("eliminar_parrafos_vacios"):
        for p in soup.find_all("p"):
            if not p.get_text(strip=True) and not p.find(["img", "br", "svg"]):
                p.decompose()
                informe.contar("párrafos vacíos eliminados")
    for patron in cfg.get("css_eliminar", []):
        for link in soup.find_all("link", rel="stylesheet", href=re.compile(patron)):
            link.decompose()
            informe.contar(f"hojas de estilo eliminadas ({patron})")


def _quitar_clases(soup, patrones, informe):
    if not patrones:
        return
    for tag in soup.find_all(class_=True):
        antes = tag["class"]
        quedan = [c for c in antes if not any(p.fullmatch(c) for p in patrones)]
        informe.contar("clases eliminadas", len(antes) - len(quedan))
        if quedan:
            tag["class"] = quedan
        else:
            del tag["class"]


def _quitar_ids(soup, patrones, informe):
    """Quita ids autogenerados salvo que algún enlace interno apunte a ellos."""
    if not patrones:
        return
    usados = {a["href"][1:] for a in soup.find_all("a", href=re.compile(r"^#"))}
    for tag in soup.find_all(id=True):
        if tag["id"] not in usados and any(p.fullmatch(tag["id"]) for p in patrones):
            del tag["id"]
            informe.contar("ids eliminados")


def _quitar_spans(soup, informe):
    for span in soup.find_all("span"):
        if span.decomposed:
            continue
        if not span.contents:
            span.decompose()
            informe.contar("spans vacíos eliminados")
        elif not span.attrs:
            span.unwrap()
            informe.contar("spans sin atributos desenvueltos")


def _fusionar_spans(soup, informe):
    """<span class="a">x</span><span class="a">y</span> -> <span class="a">xy</span>"""
    for span in soup.find_all("span"):
        if span.decomposed or span.parent is None:
            continue
        sig = span.next_sibling
        while isinstance(sig, Tag) and sig.name == "span" and sig.attrs == span.attrs:
            for hijo in list(sig.contents):
                span.append(hijo.extract())
            sig.decompose()
            informe.contar("spans contiguos fusionados")
            sig = span.next_sibling
