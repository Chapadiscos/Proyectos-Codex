"""Pasa a style="" lo que solo existe en la CSS propia del capítulo.

En Hélice solo está la CSS de los estilos del libro (Texto-base-PO26...). Las
anulaciones locales (CharOverride-N, ParaOverride-N...) se numeran por capítulo
y no están en Hélice, así que se convierten en estilos en línea antes de que la
limpieza quite las clases.
"""

import os
import re

from ..css import anadir_style, css_local, leer_reglas

SELECTOR_CLASE = re.compile(r"([a-z0-9]+)?\.([^\s.#:>+~\[]+)")


def aplicar(soup, cfg, ctx, informe):
    por_clase = {}
    for selectores, decl in css_local(soup, ctx["dir_entrada"], informe):
        for s in selectores:
            if m := SELECTOR_CLASE.fullmatch(s):
                por_clase.setdefault((m.group(1), m.group(2)), {}).update(decl)

    pesos = Pesos(cfg, ctx, informe)
    _anulaciones(soup, cfg, por_clase, pesos, informe)
    _clases_a_estilo(soup, cfg.get("clases_a_estilo") or {}, informe)
    _imagenes(soup, cfg, informe)


INVISIBLES = re.compile("[\ufeff\ufffc\u200b\u2060\u00ad]")


def _normalizar(texto):
    return " ".join(INVISIBLES.sub("", texto).split())


class Pesos:
    """Peso real de los textos con ajustes de InDesign.

    La CSS que genera InDesign exporta como "font-weight: normal" todo lo que no es
    Bold: Light, Regular, Medium… (cap. 52: cita del ladillo en BC Civitas Light;
    cap. 43: pie en BC Civitas Medium; cap. 35: Neue Haas Medium Italic). Por eso:
    1. Si existe "<capítulo>.fuentes.tsv" (lo escribe exportar_html.jsx con la fuente
       real de cada tramo), el peso sale de ahí.
    2. Si no, regla de respaldo: si el texto tiene su propio estilo de carácter con
       peso, manda ese estilo; si hereda una negrita (p. ej. ladillo), "normal" es la
       versión Light de su familia; si no, hereda el peso del párrafo.
    """

    def __init__(self, cfg, ctx, informe):
        self.cfg = cfg
        self.informe = informe
        self.helice = self._helice(cfg, ctx)  # clase -> {"familia", "peso"} según la CSS de Hélice
        self.tramos = self._tramos(cfg, ctx, informe)  # texto -> [(familia InDesign, estilo), ...]

    @staticmethod
    def _helice(cfg, ctx):
        css = cfg.get("css_helice")
        if not css:
            return {}
        with open(ctx["resolver"](css), encoding="utf-8") as f:
            reglas = leer_reglas(f.read())
        datos = {}
        for selectores, decl in reglas:
            for s in selectores:
                if m := SELECTOR_CLASE.fullmatch(s):
                    d = datos.setdefault(m.group(2), {})
                    if "font-family" in decl:
                        d["familia"] = decl["font-family"].split(",")[0].strip().strip('"')
                    if "font-weight" in decl:
                        d["peso"] = decl["font-weight"]
        return datos

    @staticmethod
    def _tramos(cfg, ctx, informe):
        nombre = os.path.splitext(os.path.basename(ctx.get("ruta_html", "")))[0] + ".fuentes.tsv"
        for carpeta in [ctx["resolver_raiz"](c) for c in cfg.get("carpetas_fuentes", ["salida"])] + [ctx["dir_entrada"]]:
            ruta = os.path.join(carpeta, nombre)
            if os.path.exists(ruta):
                tramos = {}
                with open(ruta, encoding="utf-8") as f:
                    for linea in f:
                        partes = linea.rstrip("\n").split("\t")
                        if len(partes) == 3:
                            tramos.setdefault(_normalizar(partes[0]), []).append((partes[1], partes[2]))
                informe.informar(f"pesos tipográficos tomados de InDesign ({nombre})")
                return tramos
        return None

    def heredado(self, tag, clave, incluir_propio=True):
        nodos = [tag, *tag.parents] if incluir_propio else list(tag.parents)
        for nodo in nodos:
            for clase in (nodo.get("class", []) if hasattr(nodo, "get") else []) or []:
                if clave in self.helice.get(clase, {}):
                    return self.helice[clase][clave]
        return None

    def de_indesign(self, tag):
        """Peso web según la fuente real del tramo en InDesign, o None si no se sabe."""
        if self.tramos is None:
            return None
        lista = self.tramos.get(_normalizar(tag.get_text()))
        if not lista:
            self.informe.contar("pesos: texto no encontrado en InDesign (regla de respaldo)")
            return None
        familia, estilo = lista.pop(0) if len(lista) > 1 else lista[0]
        if familia not in self.cfg.get("pesos_indesign", {}):
            return None  # fuente de símbolos u otra sin peso propio: se hereda
        tabla = self.cfg["pesos_indesign"][familia]
        claves = sorted((k for k in tabla if k.lower() in estilo.lower()), key=len, reverse=True)
        if not claves:
            self.informe.avisar(f"estilo de InDesign sin peso en pesos_indesign: {familia} {estilo}")
            return None
        self.informe.contar("pesos tomados de InDesign")
        return str(tabla[claves[0]])

    def para_normal(self, tag, familia_propia=None):
        """Peso para un "font-weight: normal" de InDesign (None = no ponerlo y heredar)."""
        peso = self.de_indesign(tag)
        if peso:
            return peso
        propio = any("peso" in self.helice.get(c, {}) for c in tag.get("class", []))
        if propio:
            return None  # su estilo de carácter (p. ej. _5-Medium) ya dice el peso
        heredado = self.heredado(tag, "peso", incluir_propio=False)
        if heredado and heredado in ("bold", "bolder") or (heredado or "").isdigit() and int(heredado) >= 600:
            familia = familia_propia or self.heredado(tag, "familia")
            return self.cfg.get("peso_normal_por_familia", {}).get(familia)
        return None


def _anulaciones(soup, cfg, por_clase, pesos, informe):
    patrones = [re.compile(p) for p in cfg.get("clases_anulacion", [])]
    propiedades = cfg.get("propiedades", {})
    fuentes = cfg.get("fuentes", {})
    descartar = cfg.get("fuentes_descartar", [])
    a_clase = cfg.get("fuentes_a_clase") or {}
    valores_descartar = cfg.get("valores_descartar", {})
    equivalencias = cfg.get("equivalencias", {})
    sangrados = cfg.get("parrafos_sangrados") or {}
    for tag in soup.find_all(class_=True):
        permitidas = propiedades.get(tag.name, [])
        for clase in list(tag["class"]):
            if not any(p.fullmatch(clase) for p in patrones):
                continue
            decl = {**por_clase.get((None, clase), {}), **por_clase.get((tag.name, clase), {})}
            _parrafo_sangrado(tag, decl, por_clase, sangrados, informe)
            familia = decl.get("font-family", "").split(",")[0].strip().strip('"')
            if familia in a_clase:
                # Adorno: lo dibuja su clase en la CSS de Hélice (el espacio evita que se quite por vacío)
                tag["class"] = tag["class"] + [a_clase[familia]]
                tag.string = " "
                informe.contar(f"adornos de {familia} pasados a {a_clase[familia]}")
                break
            nuevas = {
                k: equivalencias.get(k, {}).get(v, v)
                for k, v in decl.items()
                if k in permitidas and v not in valores_descartar.get(k, [])
            }
            if "font-family" in nuevas:
                familia = nuevas["font-family"].split(",")[0].strip().strip('"')
                if familia in fuentes:
                    nuevas["font-family"] = f"{fuentes[familia]}, sans-serif"
                else:
                    del nuevas["font-family"]
                    if familia not in descartar:
                        informe.avisar(f"fuente sin equivalente en Typekit ({clase}): {familia}")
            if "font-weight" in permitidas and decl.get("font-weight") in ("normal", "400"):
                peso = pesos.para_normal(tag, nuevas.get("font-family", "").split(",")[0].strip() or None)
                if peso:
                    nuevas["font-weight"] = peso
            if nuevas.get("text-align") in ("center", "right", "left"):
                # Los estilos del libro llevan text-align-last: left, que ganaría en párrafos de una línea
                nuevas["text-align-last"] = nuevas["text-align"]
            if nuevas:
                anadir_style(tag, nuevas)
                informe.contar(f"anulaciones pasadas a style ({tag.name})")


ATRIBUTO_NIVEL = "data-nivel-vineta"


def _parrafo_sangrado(tag, decl, por_clase, cfg, informe):
    """Texto base sangrado a mano (cap. 5, 23, 45…): en InDesign es el texto de la viñeta
    de encima. Pasa al estilo de texto de viñeta y anota a qué nivel pertenece según su
    sangría, para que la regla de jerarquía lo meta dentro de esa viñeta."""
    if not cfg or tag.name != "p":
        return
    for base, destino in (cfg.get("clases") or {}).items():
        if base in tag.get("class", []):
            # La sangría de 1.ª línea puede venir del propio estilo (Texto base: 5 mm)
            sangria_1 = decl.get("text-indent") or por_clase.get(("p", base), {}).get("text-indent")
            sangria = _px(decl.get("margin-left")) + max(_px(sangria_1), 0)
            if _px(decl.get("margin-left")) < cfg.get("margen_minimo_px", 6):
                return
            niveles = cfg.get("sangria_por_nivel_px", [23, 31, 40])
            nivel = min(range(len(niveles)), key=lambda i: abs(niveles[i] - sangria)) + 1
            tag["class"] = [destino if c == base else c for c in tag["class"]]
            tag[ATRIBUTO_NIVEL] = str(nivel)
            informe.contar(f"párrafos sangrados de {base} pasados a {destino}")
            return


def _px(valor):
    m = re.fullmatch(r"\s*(-?[\d.]+)px\s*", valor or "")
    return float(m.group(1)) if m else 0


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
