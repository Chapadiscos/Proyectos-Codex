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
Una fuente que ya tenía su URL de Hélice la conserva aunque el original se mueva o se borre
del Mac: la web la carga de Hélice.

Lo nuevo de cada capítulo (reglas y, si cambian, las fuentes) se apunta además en
<archivo>.pendiente.css: ./css_libro --copiar copia solo eso, para añadirlo al final de la
CSS que ya está en Hélice, y lo da por subido (queda en <archivo>.copiada.css por si acaso).
Con --todo copia la CSS entera, para rehacerla en Hélice.

Al copiarla queda en el portapapeles legible (con la «ñ»
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
    nuevo_libro = not actual.strip()

    fuentes, faltan = bloque_fuentes(cfg.get("fuentes_web") or {}, dir_fuentes, txt_urls, urls_previas(actual))
    actual_sin = re.sub(r'^@charset "UTF-8";\n*', "", actual)
    fuentes_antes = ""
    if INICIO_FUENTES in actual_sin:
        fuentes_antes, resto = actual_sin.split(FIN_FUENTES, 1)
        fuentes_antes += FIN_FUENTES
        resto = resto.lstrip("\n")
    else:
        resto = actual_sin
    fuentes_cambian = escapar(fuentes).strip() != fuentes_antes.strip()
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
    # Lo nuevo, aparte: es lo que hay que añadir a la CSS que ya está en Hélice
    delta = (fuentes if (fuentes_cambian or nuevo_libro) else "")
    if nuevas:
        delta += f"/* ----- Estilos nuevos de {os.path.basename(ruta_html)} ----- */\n" + "\n".join(nuevas) + "\n"
    if delta.strip():
        with open(pendiente(archivo), "a", encoding="utf-8") as f:
            f.write(escapar(delta.strip("\n")) + "\n\n")
    if informe is not None:
        if delta.strip():
            que = ", ".join(x for x in [f"{len(nuevas)} reglas nuevas" if nuevas else "", "fuentes" if fuentes_cambian else ""] if x)
            informe.avisar(f"la CSS del libro ha cambiado ({que or 'nueva'}): añade lo nuevo al final de la CSS de Hélice "
                           f"antes de pegar el HTML (./css_libro --copiar)")
        perdidas = [a[3] for a in (cfg.get("fuentes_web") or {}).get("archivos") or [] if not os.path.exists(a[3])]
        if faltan and perdidas:  # sin el original no se puede reconocer la subida a Hélice
            informe.avisar(f"no encuentro {len(perdidas)} fuentes originales (¿se han movido?): corrige su ruta en "
                           f"css_libro.fuentes_web.archivos: " + ", ".join(perdidas))
        elif faltan:
            informe.avisar(f"faltan las URL de Hélice de {faltan} fuentes: súbelas desde {dir_fuentes} y ejecuta ./css_libro --fuentes")
    return archivo, nuevas


def pendiente(archivo):
    """Lo nuevo de la CSS que aún no se ha copiado para Hélice."""
    return os.path.splitext(archivo)[0] + ".pendiente.css"


def _regla(selector, decl, familias):
    lineas = []
    for k, v in decl.items():
        if k == "font-family":
            primera = v.split(",")[0].strip().strip("\"'")
            v = f'"{familias.get(primera, primera)}", sans-serif'
        lineas.append(f"\t{k}: {v};")
    return selector + " {\n" + "\n".join(lineas) + "\n}"


def bloque_fuentes(fw, dir_fuentes, txt_urls, previas=None):
    """@font-face de las fuentes propias. Devuelve (texto, cuántas no tienen URL de Hélice).

    previas: {(familia, peso, estilo): (url, formato)} de la CSS anterior, para las fuentes
    cuyo original ya no está en el Mac."""
    archivos = fw.get("archivos") or []
    if not archivos:
        return "", 0
    previas = previas or {}
    woff2s = [convertir(a[3], dir_fuentes) for a in archivos]
    urls = urls_por_contenido(txt_urls, woff2s + [a[3] for a in archivos])
    partes, faltan = [INICIO_FUENTES], 0
    for (familia, peso, estilo, original), woff2 in zip(archivos, woff2s):
        if woff2 in urls:
            url, formato = urls[woff2], "woff2"
        elif original in urls:  # se subió el original
            url, formato = urls[original], FORMATOS.get(os.path.splitext(original)[1].lower(), "opentype")
        elif (familia, str(peso), estilo) in previas:  # la de Hélice que ya tenía
            url, formato = previas[(familia, str(peso), estilo)]
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
    """El .woff2 de una fuente (lo crea la primera vez, si está el original)."""
    os.makedirs(dir_fuentes, exist_ok=True)
    destino = os.path.join(dir_fuentes, os.path.splitext(os.path.basename(original))[0] + ".woff2")
    if not os.path.exists(destino) and os.path.exists(original):
        from fontTools.ttLib import TTFont

        fuente = TTFont(original)
        fuente.flavor = "woff2"
        fuente.save(destino)
    return destino


FONT_FACE = re.compile(r"@font-face\s*\{(.*?)\}", re.S)


def urls_previas(css):
    """{(familia, peso, estilo): (url, formato)} de los @font-face de la CSS que ya apuntan a Hélice."""
    r = {}
    for cuerpo in FONT_FACE.findall(desescapar(css)):
        campos = dict(re.findall(r"([\w-]+)\s*:\s*([^;]+);", cuerpo))
        src = re.search(r'url\("?(https?://[^")]+)"?\)\s*format\("([^"]+)"\)', campos.get("src", ""))
        if src:
            clave = (campos.get("font-family", "").strip().strip('"'), campos.get("font-weight", "").strip(),
                     campos.get("font-style", "").strip())
            r[clave] = (src.group(1), src.group(2))
    return r


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
    ap.add_argument("--copiar", action="store_true", help="copia lo nuevo de la CSS (legible) para añadirlo en Hélice")
    ap.add_argument("--todo", action="store_true", help="con --copiar, la CSS entera")
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

        origen = archivo if args.todo else pendiente(archivo)
        if not os.path.exists(origen) or not open(origen, encoding="utf-8").read().strip():
            print("No hay CSS nueva pendiente de subir a Hélice")
            return 0
        texto = re.sub(r'^@charset "UTF-8";\n*', "", desescapar(open(origen, encoding="utf-8").read())).strip() + "\n"
        subprocess.run(["pbcopy"], input=texto.encode("utf-8"), env=ENTORNO_UTF8, check=True)
        if args.todo:
            print(f"CSS entera del libro copiada al portapapeles ({len(texto)} caracteres): sustituye la de Hélice")
        else:
            os.replace(origen, os.path.splitext(archivo)[0] + ".copiada.css")
            print(f"CSS nueva copiada al portapapeles ({len(texto)} caracteres): añádela al final de la CSS de Hélice")
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
