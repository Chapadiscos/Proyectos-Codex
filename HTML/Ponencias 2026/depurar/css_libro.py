"""CSS de Hélice de un libro nuevo, generada a partir de la CSS que exporta InDesign.

Con «css_libro.generar» en la configuración del libro, cada capítulo que se depura
completa la CSS del libro (css_libro.archivo) con las reglas de los estilos que aún no
tenía: los selectores llevan el sufijo del libro (renombrar_clases) y las fuentes, el
nombre de su familia web (estilos_capitulo.fuentes). Las reglas que ya están no se tocan
(se pueden retocar a mano). Si la CSS cambia, hay que subirla de nuevo a Hélice.

Fuentes propias (sin Adobe Fonts): se convierten a .woff2 en css_libro.fuentes_web.carpeta
para subirlas a Hélice (o se suben los .otf/.ttf originales); la CSS lleva un @font-face
por archivo. Como Hélice cambia el nombre de lo que se sube, sus URL se emparejan por
contenido con los .woff2 o con los originales:
    ./css_libro --fuentes        (con las URL copiadas por el marcador «Enlaces Hélice»)
Mientras no estén, el @font-face apunta a los archivos locales (sirve para la vista previa).

Para pegarla en Hélice: ./css_libro --copiar la deja en el portapapeles legible (con la «ñ»
y el «•» tal cual; en el archivo van como escapes CSS, «\\F1 », para que no dependa de la
codificación con que se abra).

Uso: ./css_libro [--libro ponencias2025] [--fuentes] [--copiar] [ruta/al/capitulo.html …]
"""

import argparse
import glob
import hashlib
import os
import pathlib
import re
import subprocess
import sys

from . import libros
from .css import desescapar, escapar, leer_reglas
from .pasos.p00_renombrar_clases import renombrador
from .pasos.p01_estilos_capitulo import SELECTOR_CLASE

INICIO_FUENTES = "/* ===== Fuentes (generado: no editar) ===== */"
FIN_FUENTES = "/* ===== Fin de las fuentes ===== */"
FORMATOS = {".otf": "opentype", ".ttf": "truetype", ".woff": "woff", ".woff2": "woff2"}
URL_FUENTE = re.compile(r"https?://[^\s\"'<>)]+/uploads/[^\s\"'<>)]+\.(?:woff2?|otf|ttf)", re.I)


def rutas(config):
    cfg = config.get("css_libro") or {}
    carpeta = (config.get("libro") or {}).get("carpeta", "")
    archivo = cfg.get("archivo", "{carpeta}/helice.css").format(carpeta=carpeta)
    fw = cfg.get("fuentes_web") or {}
    dir_fuentes = fw.get("carpeta", "{carpeta}/Fuentes").format(carpeta=carpeta)
    return archivo, dir_fuentes, os.path.join(os.path.dirname(archivo), "fuentes_helice.txt")


def actualizar(config, ruta_html, informe=None):
    """Completa la CSS del libro con lo nuevo de este capítulo. Devuelve (archivo, reglas nuevas)."""
    cfg = config.get("css_libro") or {}
    if not cfg.get("generar"):
        return None, []
    archivo, dir_fuentes, txt_urls = rutas(config)
    os.makedirs(os.path.dirname(archivo), exist_ok=True)
    actual = open(archivo, encoding="utf-8").read() if os.path.exists(archivo) else ""

    fuentes, faltan = bloque_fuentes(cfg.get("fuentes_web") or {}, dir_fuentes, txt_urls)
    actual_sin = re.sub(r'^@charset "UTF-8";\n*', "", actual)
    if INICIO_FUENTES in actual_sin:
        resto = actual_sin.split(FIN_FUENTES, 1)[1].lstrip("\n")
    else:
        resto = actual_sin
    existentes = {s for selectores, _ in leer_reglas(resto) for s in selectores}

    nuevas = []
    renombrar = renombrador(config.get("renombrar_clases") or {}) or (lambda c: c)
    familias = (config.get("estilos_capitulo") or {}).get("fuentes") or {}
    for css in sorted(glob.glob(os.path.join(os.path.dirname(ruta_html), "*-web-resources", "css", "*.css"))):
        for selectores, decl in leer_reglas(open(css, encoding="utf-8").read()):
            for s in selectores:
                m = SELECTOR_CLASE.fullmatch(s)
                if not m or renombrar(m.group(2)) == m.group(2):
                    continue  # no es un estilo del libro (anulaciones, _idGen…)
                selector = (m.group(1) or "") + "." + renombrar(m.group(2))
                if selector in existentes:
                    continue
                existentes.add(selector)
                nuevas.append(_regla(selector, decl, familias))

    resto = re.sub(r'^@charset "UTF-8";\n*', "", resto)
    contenido = '@charset "UTF-8";\n' + fuentes + resto.rstrip("\n")
    if nuevas:
        nombre = os.path.basename(ruta_html)
        contenido += f"\n\n/* ----- Estilos nuevos de {nombre} ----- */\n" + "\n".join(nuevas)
    contenido = escapar(contenido.strip("\n")) + "\n"  # también lo ya escrito sin escapar
    cambiada = contenido != actual
    if cambiada:
        with open(archivo, "w", encoding="utf-8") as f:
            f.write(contenido)
    if informe is not None:
        if cambiada:
            que = f"{len(nuevas)} reglas nuevas" if nuevas else "fuentes"
            informe.avisar(f"la CSS del libro ha cambiado ({que}): súbela a Hélice antes de pegar el HTML: {archivo}")
        if faltan:
            informe.avisar(f"faltan las URL de Hélice de {faltan} fuentes: súbelas desde {dir_fuentes} y ejecuta ./css_libro --fuentes")
    return archivo, nuevas


def _regla(selector, decl, familias):
    lineas = []
    for k, v in decl.items():
        if k == "font-family":
            primera = v.split(",")[0].strip().strip("\"'")
            v = f'"{familias.get(primera, primera)}", sans-serif'
        lineas.append(f"\t{k}: {v};")
    return selector + " {\n" + "\n".join(lineas) + "\n}"


def bloque_fuentes(fw, dir_fuentes, txt_urls):
    """@font-face de las fuentes propias. Devuelve (texto, cuántas no tienen URL de Hélice)."""
    archivos = fw.get("archivos") or []
    if not archivos:
        return "", 0
    woff2s = [convertir(a[3], dir_fuentes) for a in archivos]
    urls = urls_por_contenido(txt_urls, woff2s + [a[3] for a in archivos])
    partes, faltan = [INICIO_FUENTES], 0
    for (familia, peso, estilo, original), woff2 in zip(archivos, woff2s):
        if woff2 in urls:
            url, formato = urls[woff2], "woff2"
        elif original in urls:  # se subió el original
            url, formato = urls[original], FORMATOS.get(os.path.splitext(original)[1].lower(), "opentype")
        else:
            faltan += 1
            url, formato = pathlib.Path(woff2).as_uri(), "woff2"  # vista previa en local hasta tener la de Hélice
        partes.append(
            f'@font-face {{\n\tfont-family: "{familia}";\n\tfont-weight: {peso};\n\tfont-style: {estilo};\n'
            f'\tfont-display: swap;\n\tsrc: url("{url}") format("{formato}");\n}}'
        )
    partes.append(FIN_FUENTES)
    return "\n".join(partes) + "\n\n", faltan


def convertir(original, dir_fuentes):
    """El .woff2 de una fuente (lo crea la primera vez)."""
    os.makedirs(dir_fuentes, exist_ok=True)
    destino = os.path.join(dir_fuentes, os.path.splitext(os.path.basename(original))[0] + ".woff2")
    if not os.path.exists(destino):
        from fontTools.ttLib import TTFont

        fuente = TTFont(original)
        fuente.flavor = "woff2"
        fuente.save(destino)
    return destino


def urls_por_contenido(txt_urls, archivos):
    """{ruta local: URL de Hélice}, emparejando por contenido (Hélice renombra lo que se sube)."""
    if not os.path.exists(txt_urls):
        return {}
    import requests

    locales = {}
    for f in archivos:
        if os.path.exists(f):
            locales[hashlib.md5(open(f, "rb").read()).hexdigest()] = f
    r = {}
    for url in open(txt_urls, encoding="utf-8").read().split():
        try:
            datos = requests.get(url, timeout=30).content
        except requests.RequestException:
            continue
        nombre = locales.get(hashlib.md5(datos).hexdigest())
        if nombre:
            r[nombre] = url
    return r


def main(argv=None):
    ap = argparse.ArgumentParser(prog="css_libro", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("html", nargs="*", help="capítulos exportados (por defecto, solo se rehacen las fuentes)")
    ap.add_argument("--libro", help="libro de config/libros (por defecto, según la ruta del HTML)")
    ap.add_argument("--fuentes", action="store_true", help="guarda las URL de fuentes del portapapeles (marcador)")
    ap.add_argument("--copiar", action="store_true", help="copia la CSS al portapapeles, legible, para pegarla en Hélice")
    args = ap.parse_args(argv)
    libro = libros.elegir(args.libro, args.html[0] if args.html else None)
    archivo, dir_fuentes, txt_urls = rutas(libro.config)
    if args.fuentes:
        from .capitulo import pegar

        urls = list(dict.fromkeys(URL_FUENTE.findall(pegar())))
        if not urls:
            sys.exit("No hay URL de fuentes en el portapapeles: abre en Hélice la carpeta de las fuentes y pulsa el marcador «Enlaces Hélice».")
        previas = open(txt_urls, encoding="utf-8").read().split() if os.path.exists(txt_urls) else []
        os.makedirs(os.path.dirname(txt_urls), exist_ok=True)
        with open(txt_urls, "w", encoding="utf-8") as f:
            f.write("\n".join(dict.fromkeys(urls + previas)) + "\n")
        print(f"{len(urls)} URL de fuentes guardadas en {txt_urls}")
    if args.copiar:
        from .capitulo import ENTORNO_UTF8

        texto = re.sub(r'^@charset "UTF-8";\n*', "", desescapar(open(archivo, encoding="utf-8").read()))
        subprocess.run(["pbcopy"], input=texto.encode("utf-8"), env=ENTORNO_UTF8, check=True)
        print(f"CSS del libro copiada al portapapeles ({len(texto)} caracteres): pégala en Hélice")
        return 0
    from .informe import Informe

    informe = Informe()
    for html in args.html or [os.path.join(os.path.dirname(archivo), "-")]:
        _, nuevas = actualizar(libro.config, html, informe)
        if args.html:
            print(f"{os.path.basename(html)}: {len(nuevas)} reglas nuevas")
    print(informe.texto())
    print(f"CSS del libro: {archivo}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
