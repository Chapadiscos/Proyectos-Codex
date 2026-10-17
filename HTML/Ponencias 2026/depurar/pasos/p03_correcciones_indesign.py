"""Correcciones de errores de la exportación HTML de InDesign.

Los reemplazos simples se configuran en config.yaml. Las correcciones que necesitan
mirar la estructura van como funciones en CORRECCIONES, una por error detectado.
"""

import re

from bs4 import Tag

from ..bloques import es_bloque_imagen, es_figura, hermano, tiene_clase

# Caracteres invisibles que InDesign deja en el texto exportado.
INVISIBLES = {
    "﻿": "BOM / marcador de orden de bytes",
    "​": "espacio de ancho cero",
    "⁠": "unión de palabras",
}


def pre(texto, cfg, ctx, informe):
    if cfg.get("quitar_invisibles", True):
        for car, nombre in INVISIBLES.items():
            informe.contar(f"caracteres invisibles eliminados ({nombre})", texto.count(car))
            texto = texto.replace(car, "")
    for r in cfg.get("reemplazos", []):
        texto, n = re.subn(r["buscar"], r["sustituir"], texto, flags=re.S)
        informe.contar(f"reemplazo: {r.get('nombre', r['buscar'])}", n)
    return texto


def aplicar(soup, cfg, ctx, informe):
    activas = cfg.get("activas", list(CORRECCIONES))
    for nombre in activas:
        CORRECCIONES[nombre](soup, cfg, informe)


def _br_al_final_de_parrafo(soup, cfg, informe):
    """InDesign deja <br /> sueltos al final de párrafos con salto forzado final."""
    for br in soup.select("p > br:last-child"):
        if br.next_sibling is None or not str(br.next_sibling).strip():
            br.decompose()
            informe.contar("<br> al final de párrafo eliminados")


def _pie_debajo(soup, cfg, informe):
    """El pie de figura va siempre debajo de su imagen; InDesign a veces lo pone antes."""
    clase = cfg.get("clase_pie", "Pie-Figura")
    for pie in soup.find_all("p"):
        if not tiene_clase(pie, clase):
            continue
        padre = pie.parent
        if padre.name == "div" and es_figura(padre, clase):
            # Figura agrupada: el pie va detrás del último elemento con imagen
            hijos = [h for h in padre.children if isinstance(h, Tag)]
            con_img = [h for h in hijos if es_bloque_imagen(h)]
            if con_img and hijos.index(con_img[-1]) > hijos.index(pie):
                con_img[-1].insert_after(pie.extract())
                informe.contar("pies de figura movidos debajo de la imagen")
        elif es_bloque_imagen(hermano(pie, +1)) and not es_bloque_imagen(hermano(pie, -1)):
            # Pie suelto justo antes de una imagen que no tiene otra imagen delante
            hermano(pie, +1).insert_after(pie.extract())
            informe.contar("pies de figura movidos debajo de la imagen")


def _jerarquia_vinetas(soup, cfg, informe):
    """Reúne listas que InDesign parte al meter imágenes entre viñetas.

    <ul>V1 a</ul> <img> <ul>V2 b</ul>  ->  <ul><li>a <img> <ul><li>b</li></ul></li></ul>
    El nivel de cada viñeta sale de su clase (Viñeta-N).
    """
    patron = re.compile(cfg.get("nivel_vineta", r"Viñeta-(\d+)"))
    clase_pie = cfg.get("clase_pie", "Pie-Figura")

    def nivel(li, defecto):
        for c in li.get("class", []):
            if m := patron.search(c):
                return int(m.group(1))
        return defecto

    for ul in soup.find_all("ul"):
        if ul.parent is None or ul.find_parent(["ul", "ol"]):
            continue
        tramos, pendientes = [], []
        sig = hermano(ul, +1)
        while isinstance(sig, Tag):
            primero = sig.find("li") if sig.name == "ul" else None
            if primero is not None and nivel(primero, 1) > 1:
                tramos.append((pendientes, sig))
                pendientes = []
            elif es_bloque_imagen(sig) or tiene_clase(sig, clase_pie):
                pendientes.append(sig)
            else:
                break
            sig = hermano(sig, +1)
        if not tramos:
            continue

        fichas = _aplanar(ul, 1, nivel)
        for bloques, continuacion in tramos:
            fichas += [("bloque", b.extract()) for b in bloques]
            fichas += _aplanar(continuacion.extract(), 1, nivel)
        _reconstruir(soup, ul, fichas)
        informe.contar("listas de viñetas reunidas")


def _aplanar(ul, profundidad, nivel):
    fichas = []
    for li in [h for h in ul.children if isinstance(h, Tag) and h.name == "li"]:
        anidadas = [h.extract() for h in li.find_all("ul", recursive=False)]
        fichas.append(("li", nivel(li, profundidad), li.extract()))
        for sub in anidadas:
            fichas += _aplanar(sub, profundidad + 1, nivel)
    return fichas


def _reconstruir(soup, raiz, fichas):
    raiz.clear()
    pila, pendientes = [raiz], []
    for ficha in fichas:
        if ficha[0] == "bloque":
            pendientes.append(ficha[1])
            continue
        _, nivel, li = ficha
        nivel = max(1, min(nivel, len(pila) + 1))
        if pendientes:
            # Las imágenes van dentro de la viñeta madre, antes de las subviñetas
            del pila[max(1, nivel - 1):]
            madre = pila[-1].find_all("li", recursive=False)[-1]
            for b in pendientes:
                madre.append(b)
            pendientes = []
        del pila[nivel:]
        while len(pila) < nivel:
            ultimos = pila[-1].find_all("li", recursive=False)
            if not ultimos:
                break
            nuevo = soup.new_tag("ul")
            ultimos[-1].append(nuevo)
            pila.append(nuevo)
        pila[-1].append(li)
    for b in pendientes:
        raiz.find_all("li", recursive=False)[-1].append(b)


# Añadir aquí las correcciones que salgan del análisis de cada capítulo.
CORRECCIONES = {
    "br_al_final_de_parrafo": _br_al_final_de_parrafo,
    "pie_debajo": _pie_debajo,
    "jerarquia_vinetas": _jerarquia_vinetas,
}
