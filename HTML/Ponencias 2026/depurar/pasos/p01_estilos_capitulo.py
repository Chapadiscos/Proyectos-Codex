"""Pasa a style="" lo que solo existe en la CSS propia del capítulo.

En Hélice solo está la CSS de los estilos del libro (Texto-base-PO26...). Las
anulaciones locales (CharOverride-N, ParaOverride-N...) se numeran por capítulo
y no están en Hélice, así que se convierten en estilos en línea antes de que la
limpieza quite las clases.
"""

import re

from ..css import anadir_style, css_local

SELECTOR_CLASE = re.compile(r"([a-z0-9]+)?\.([^\s.#:>+~\[]+)")


def aplicar(soup, cfg, ctx, informe):
    por_clase = {}
    for selectores, decl in css_local(soup, ctx["dir_entrada"], informe):
        for s in selectores:
            if m := SELECTOR_CLASE.fullmatch(s):
                por_clase.setdefault((m.group(1), m.group(2)), {}).update(decl)

    _anulaciones(soup, cfg, por_clase, informe)
    _clases_a_estilo(soup, cfg.get("clases_a_estilo") or {}, informe)
    _imagenes(soup, cfg, informe)


def _anulaciones(soup, cfg, por_clase, informe):
    patrones = [re.compile(p) for p in cfg.get("clases_anulacion", [])]
    propiedades = cfg.get("propiedades", {})
    fuentes = cfg.get("fuentes", {})
    descartar = cfg.get("fuentes_descartar", [])
    for tag in soup.find_all(class_=True):
        permitidas = propiedades.get(tag.name, [])
        for clase in tag["class"]:
            if not any(p.fullmatch(clase) for p in patrones):
                continue
            decl = {**por_clase.get((None, clase), {}), **por_clase.get((tag.name, clase), {})}
            nuevas = {k: v for k, v in decl.items() if k in permitidas}
            if "font-family" in nuevas:
                familia = nuevas["font-family"].split(",")[0].strip().strip('"')
                if familia in fuentes:
                    nuevas["font-family"] = f"{fuentes[familia]}, sans-serif"
                else:
                    del nuevas["font-family"]
                    if familia not in descartar:
                        informe.avisar(f"fuente sin equivalente en Typekit ({clase}): {familia}")
            if nuevas:
                anadir_style(tag, nuevas)
                informe.contar(f"anulaciones pasadas a style ({tag.name})")


def _clases_a_estilo(soup, mapa, informe):
    """Clases sin regla en Hélice que conviene conservar como estilo (p. ej. noPartir)."""
    for clase, decl in mapa.items():
        for tag in soup.find_all(class_=clase):
            anadir_style(tag, decl)
            informe.contar(f"{clase} pasado a style")


def _imagenes(soup, cfg, informe):
    """Tamaño natural, sin pasar del ancho del visor y centradas.

    Los tamaños fijos de InDesign (#_idContainerNNN) no se usan: el % de ancho de
    una imagen, si hace falta, se pone a mano (salvo las IB, ver reglas_helice).
    """
    estilo = cfg.get("estilo_imagen", {"display": "block", "max-width": "100%", "height": "auto", "margin": "0 auto"})
    for img in soup.find_all("img"):
        anadir_style(img, estilo)
        informe.contar("imágenes a tamaño natural, centradas")
