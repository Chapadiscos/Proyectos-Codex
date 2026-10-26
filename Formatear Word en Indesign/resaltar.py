#!/usr/bin/env python3
"""Resalta con la condición «Risk word» las palabras de la publicación (Tabla, Figura,
Algoritmo…) en los documentos abiertos en InDesign. La importación ya lo hace sola; esto sirve
para repetirlo tras cambiar la lista ([resaltar] palabras, en publicaciones/maqueta-base.toml).

    python3 resaltar.py                            # todos los «Capitulo…» abiertos
    python3 resaltar.py --documento "Capitulo 5.indd"
"""
import argparse
import os
import subprocess
import sys
import tomllib

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)

from importar import resaltar     # noqa: E402


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--documento', default='', help='nombre del documento abierto (por defecto, los «Capitulo…»)')
    ap.add_argument('--publicacion', default=os.path.join(AQUI, 'publicaciones', 'maqueta-base.toml'))
    args = ap.parse_args()
    with open(args.publicacion, 'rb') as f:
        conf = tomllib.load(f)
    if args.documento:
        nombres = [args.documento]
    else:
        r = subprocess.run(['osascript', '-e', 'tell application id "com.adobe.InDesign" to get name of every document'],
                           capture_output=True, text=True)
        nombres = [n.strip() for n in r.stdout.split(',') if n.strip().startswith('Capitulo')]
    if not nombres:
        print('No hay documentos «Capitulo…» abiertos en InDesign.')
    for n in nombres:
        print(resaltar(n, conf))


if __name__ == '__main__':
    main()
