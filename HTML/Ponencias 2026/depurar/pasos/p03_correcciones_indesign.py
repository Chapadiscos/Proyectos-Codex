"""Correcciones de errores de la exportación HTML de InDesign.

Los reemplazos simples se configuran en config.yaml. Las correcciones que necesitan
mirar la estructura van como funciones en CORRECCIONES, una por error detectado.
"""

import re

from bs4 import Tag

from ..bloques import es_bloque_imagen, es_figura, hermano, tiene_clase
from ..css import anadir_style
from .p01_estilos_capitulo import ATRIBUTO_NIVEL

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
    """Reúne listas que InDesign parte al meter imágenes o párrafos entre viñetas.

    <ul>V1 a</ul> <img> <ul>V2 b</ul>  ->  <ul><li>a <img> <ul><li>b</li></ul></li></ul>
    Igual con un párrafo de texto de viñeta (Texto-base---Viñeta) entre la viñeta
    madre y sus subviñetas (capítulo 46), y si la madre es numerada (<ol>, capítulo 65).
    El nivel de cada viñeta sale de su clase.
    """
    patron = re.compile(cfg.get("nivel_vineta", r"Viñeta-(\d+)"))
    clase_pie = cfg.get("clase_pie", "Pie-Figura")
    clase_texto = cfg.get("clase_texto_vineta", "Texto-base---Viñeta")
    estilo_texto = cfg.get("estilo_texto_vineta_en_lista", {"margin-left": "0"})

    def nivel(li, defecto):
        for c in li.get("class", []):
            if m := patron.search(c):
                return int(m.group(1))
        return defecto

    for ul in soup.find_all(["ul", "ol"]):
        if ul.parent is None or ul.find_parent(["ul", "ol"]):
            continue
        tramos, pendientes = [], []
        sig = hermano(ul, +1)
        while isinstance(sig, Tag):
            primero = sig.find("li") if sig.name == "ul" else None
            if primero is not None and nivel(primero, 1) > 1:
                tramos.append((pendientes, sig))
                pendientes = []
            elif es_bloque_imagen(sig) or tiene_clase(sig, clase_pie) or tiene_clase(sig, clase_texto):
                pendientes.append(sig)
            else:
                break
            sig = hermano(sig, +1)
        # Texto de viñeta con nivel conocido al final (sin más subviñetas detrás): también dentro
        cola = []
        for b in pendientes:
            if not b.has_attr(ATRIBUTO_NIVEL):
                break
            cola.append(b)
        if not tramos and not cola:
            continue

        def ficha_bloque(b):
            if tiene_clase(b, clase_texto):
                # Dentro de la viñeta ya queda alineado con su texto: sin el margen propio
                anadir_style(b, estilo_texto)
                if b.has_attr(ATRIBUTO_NIVEL):
                    return ("texto", int(b[ATRIBUTO_NIVEL]), b.extract())
            return ("bloque", b.extract())

        fichas = _aplanar(ul, 1, nivel)
        for bloques, continuacion in tramos:
            fichas += [ficha_bloque(b) for b in bloques]
            fichas += _aplanar(continuacion.extract(), 1, nivel)
        fichas += [ficha_bloque(b) for b in cola]
        _reconstruir(soup, ul, fichas)
        informe.contar("listas de viñetas reunidas")
    for p in soup.find_all(attrs={ATRIBUTO_NIVEL: True}):
        del p[ATRIBUTO_NIVEL]


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
        if ficha[0] == "texto":
            # Párrafo sangrado: dentro de la última viñeta de su nivel (cap. 5, 23: nivel 2)
            _, nivel, b = ficha
            nivel = max(1, min(nivel, len(pila)))
            ultimos = pila[nivel - 1].find_all("li", recursive=False)
            if ultimos:
                for p in pendientes + [b]:
                    ultimos[-1].append(p)
                pendientes = []
            else:
                pendientes.append(b)
            del pila[nivel:]
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


def _nivel_de(li, patron):
    for c in li.get("class", []) if isinstance(li, Tag) else []:
        if m := patron.search(c):
            return int(m.group(1))
    return None


def _subvinetas_del_mismo_nivel(soup, cfg, informe):
    """Saca de una viñeta las sublistas que en realidad son del mismo nivel o superior.

    Capítulo 70: tras «a. b. c. d.» (Viñeta-2 numerada) viene «- Reposición…», también
    Viñeta-2, pero InDesign la mete dentro de la «d.»: se pasa detrás de su lista.
    """
    patron = re.compile(cfg.get("nivel_vineta", r"Viñeta-(\d+)"))
    cambiado = True
    while cambiado:
        cambiado = False
        for sub in soup.find_all(["ul", "ol"]):
            li = sub.parent
            if not (isinstance(li, Tag) and li.name == "li" and li.parent is not None):
                continue
            nivel_li = _nivel_de(li, patron)
            nivel_sub = _nivel_de(sub.find("li", recursive=False), patron)
            if nivel_li and nivel_sub and nivel_sub <= nivel_li:
                li.parent.insert_after(sub.extract())
                informe.contar("subviñetas sacadas a su nivel")
                cambiado = True
                break


def _numeradas_sin_marca_propia(soup, cfg, informe):
    """Viñetas numeradas (a., b.…) con un estilo que dibuja su marca con ::before.

    En la CSS de Hélice, Viñeta-2 y Viñeta-3 quitan la marca nativa y ponen «-» o «›»
    con ::before, que un style="" no puede quitar (capítulo 70: salía «-a»). Se les
    cambia la clase por una sin ::before y se conserva su sangría.
    """
    clases = cfg.get("clases_con_marca_propia") or {}
    sustituta = cfg.get("clase_numerada")
    if not sustituta:
        return
    for li in soup.find_all("li"):
        estilo = li.get("style", "")
        m = re.search(r"list-style-type:\s*([\w-]+)", estilo)
        if not m or m.group(1) in ("none", "disc", "circle", "square"):
            continue
        for clase in li.get("class", []):
            if clase in clases:
                li["class"] = [sustituta if c == clase else c for c in li["class"]]
                anadir_style(li, clases[clase] or {})
                informe.contar("viñetas numeradas sin la marca de su estilo")
                break


def _subvinetas_sin_madre(soup, cfg, informe):
    """Lista de nivel 2 o más sin viñeta madre (capítulo 5: «Órdenes terapéuticas…» y guiones).

    Suelta, la CSS de Hélice la deja menos sangrada que el nivel 1. Se mete dentro de
    una viñeta de nivel 1 vacía y sin marca, que la coloca a la sangría de su nivel.
    """
    patron = re.compile(cfg.get("nivel_vineta", r"Viñeta-(\d+)"))
    clase_madre = cfg.get("clase_madre_vacia")
    if not clase_madre:
        return
    for lista in soup.find_all(["ul", "ol"]):
        if lista.parent is None or lista.find_parent(["ul", "ol", "li"]):
            continue
        nivel = _nivel_de(lista.find("li", recursive=False), patron)
        if not nivel or nivel < 2:
            continue
        # Sangría de cada nivel vacío: la de los estilos con marca propia (Viñeta-2: -28px)
        sangrias = {_nivel_de(soup.new_tag("li", attrs={"class": c}), patron): d
                    for c, d in (cfg.get("clases_con_marca_propia") or {}).items()}
        for k in range(nivel - 1, 0, -1):
            ul, li = soup.new_tag("ul"), soup.new_tag("li")
            li["class"] = [clase_madre]
            li["style"] = "list-style-type: none"
            if k > 1 and sangrias.get(k):
                anadir_style(li, sangrias[k])
            lista.wrap(li)
            li.wrap(ul)
            lista = ul
        informe.contar("subviñetas sin madre colocadas en su nivel")


# Añadir aquí las correcciones que salgan del análisis de cada capítulo (van en este orden).
CORRECCIONES = {
    "br_al_final_de_parrafo": _br_al_final_de_parrafo,
    "pie_debajo": _pie_debajo,
    "subvinetas_del_mismo_nivel": _subvinetas_del_mismo_nivel,
    "jerarquia_vinetas": _jerarquia_vinetas,
    "subvinetas_sin_madre": _subvinetas_sin_madre,
    "numeradas_sin_marca_propia": _numeradas_sin_marca_propia,
}
