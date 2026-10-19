"""Uso: python -m depurar entrada/32/archivo.html [más archivos] [--config config/config.yaml]"""

import argparse
import os
import re
import sys

import yaml
from bs4 import BeautifulSoup

from .informe import Informe
from .pasos import PASOS

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def procesar(ruta_html, config, dir_config, dir_salida, sufijo="", dir_auxiliar=None):
    """Escribe el HTML final en dir_salida; la vista previa y el informe en dir_auxiliar
    (por defecto, el mismo dir_salida)."""
    informe = Informe()
    ctx = {
        "dir_entrada": os.path.dirname(os.path.abspath(ruta_html)),
        "ruta_html": os.path.abspath(ruta_html),
        "resolver": lambda r: r if os.path.isabs(r) else os.path.join(dir_config, r),
        "resolver_raiz": lambda r: r if os.path.isabs(r) else os.path.join(RAIZ, r),
    }
    activos = config.get("pasos", {})

    with open(ruta_html, encoding="utf-8") as f:
        texto = f.read()
    for nombre, paso in PASOS:
        if activos.get(nombre, True) and hasattr(paso, "pre"):
            texto = paso.pre(texto, config.get(nombre) or {}, ctx, informe)

    soup = BeautifulSoup(texto, "lxml")
    for nombre, paso in PASOS:
        if activos.get(nombre, True) and hasattr(paso, "aplicar"):
            paso.aplicar(soup, config.get(nombre) or {}, ctx, informe)

    dir_auxiliar = dir_auxiliar or dir_salida
    os.makedirs(dir_salida, exist_ok=True)
    os.makedirs(dir_auxiliar, exist_ok=True)
    base = os.path.splitext(os.path.basename(ruta_html))[0] + sufijo
    destino = os.path.join(dir_salida, base + ".html")
    with open(destino, "w", encoding="utf-8") as f:
        f.write(_compactar(ctx.get("resultado") or str(soup)))
    if ctx.get("vista_previa"):
        with open(os.path.join(dir_auxiliar, base + ".vista.html"), "w", encoding="utf-8") as f:
            f.write(_compactar(ctx["vista_previa"]))
    with open(os.path.join(dir_auxiliar, base + ".informe.txt"), "w", encoding="utf-8") as f:
        f.write(informe.texto() + "\n")
    return destino, informe


def _compactar(html):
    """Quita las líneas en blanco que dejan los div desenvueltos."""
    return re.sub(r"\n[ \t]*(?:\n[ \t]*)+", "\n", html)


def main(argv=None):
    ap = argparse.ArgumentParser(prog="depurar", description=__doc__)
    ap.add_argument("html", nargs="+", help="HTML exportado por InDesign")
    ap.add_argument("--config", default=os.path.join(RAIZ, "config", "config.yaml"))
    ap.add_argument("--salida", default=os.path.join(RAIZ, "salida"))
    args = ap.parse_args(argv)

    with open(args.config, encoding="utf-8") as f:
        config = yaml.safe_load(f) or {}
    dir_config = os.path.dirname(os.path.abspath(args.config))

    for ruta in args.html:
        destino, informe = procesar(ruta, config, dir_config, args.salida)
        print(f"== {ruta} -> {destino}")
        print(informe.texto())
    return 0


if __name__ == "__main__":
    sys.exit(main())
