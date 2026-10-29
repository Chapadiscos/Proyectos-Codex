#!/usr/bin/env python3
"""Fase 1: clasifica los párrafos de uno o varios Word y genera un informe por capítulo.

    python3 clasificar.py                          # todas las carpetas de «Documentos Word»
    python3 clasificar.py "Documentos Word/Capitulo 5"
    python3 clasificar.py capitulo.docx --publicacion publicaciones/maqueta-base.toml
"""
import argparse
import glob
import os
import sys
import tomllib

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)

from formatear.docx import Documento          # noqa: E402
from formatear.clasificar import clasificar    # noqa: E402
from formatear import figuras, informe         # noqa: E402


def docx_de(ruta):
    if os.path.isdir(ruta):
        return sorted(f for f in glob.glob(os.path.join(ruta, '*.docx')) if not os.path.basename(f).startswith('~$'))
    return [ruta]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('rutas', nargs='*', help='carpetas de capítulo o archivos .docx')
    ap.add_argument('--publicacion', default=os.path.join(AQUI, 'publicaciones', 'maqueta-base.toml'))
    ap.add_argument('--salida', default=os.path.join(AQUI, 'informes'))
    args = ap.parse_args()

    with open(args.publicacion, 'rb') as f:
        conf = tomllib.load(f)
    rutas = args.rutas or sorted(glob.glob(os.path.join(AQUI, 'Documentos Word', '*')))
    os.makedirs(args.salida, exist_ok=True)
    for ruta in rutas:
        for docx in docx_de(ruta):
            carpeta = os.path.dirname(os.path.abspath(docx))
            nombre = os.path.basename(carpeta) if os.path.isdir(ruta) else os.path.splitext(os.path.basename(docx))[0]
            r = conf.get('reglas', {})
            elementos, modo = clasificar(Documento(docx), r.get('negritas_con_vineta', 'auto'), r.get('cabecera', ''),
                                         r.get('ladillos_mayusculas', False))
            figs, sobrantes = figuras.inventario(elementos, carpeta)
            destino = os.path.join(args.salida, nombre + '.html')
            with open(destino, 'w', encoding='utf-8') as f:
                f.write(informe.generar(nombre, docx, elementos, modo, figs, sobrantes, conf))
            dudas = sum(1 for e in elementos if e.dudas)
            print('%-12s %3d párrafos, %2d dudosos, negritas con viñeta → %-7s → %s' % (
                nombre, len(elementos), dudas, modo or '—', os.path.relpath(destino, AQUI)))


if __name__ == '__main__':
    main()
