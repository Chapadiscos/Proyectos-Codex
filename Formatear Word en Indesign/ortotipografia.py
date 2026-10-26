#!/usr/bin/env python3
"""Fase 3: correcciones ortotipográficas seguras en los documentos abiertos en InDesign.

    python3 ortotipografia.py                      # simula en todos los abiertos: cuenta y enseña ejemplos
    python3 ortotipografia.py --detalle            # simula enseñando todos los casos
    python3 ortotipografia.py --aplicar            # aplica (un Cmd+Z por documento lo deshace)
    python3 ortotipografia.py --documento "Capitulo 5.indd" --aplicar

Las reglas están en publicaciones/ortotipografia.toml.
"""
import argparse
import json
import os
import subprocess
import tempfile
import tomllib

AQUI = os.path.dirname(os.path.abspath(__file__))


def cadena(texto):
    """Cadena de AppleScript. No vale json.dumps: escribe «í» como \\u00ed y AppleScript no lo entiende."""
    return '"%s"' % texto.replace('\\', '\\\\').replace('"', '\\"')


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--reglas', default=os.path.join(AQUI, 'publicaciones', 'ortotipografia.toml'))
    ap.add_argument('--maqueta', default=os.path.join(AQUI, 'publicaciones', 'maqueta-base.toml'),
                    help='de aquí salen los estilos de carácter (cursiva…) de las reglas con «estilo»')
    ap.add_argument('--documento', default='', help='nombre del documento abierto (por defecto, todos)')
    ap.add_argument('--aplicar', action='store_true', help='hace los cambios (sin esto solo simula)')
    ap.add_argument('--detalle', action='store_true', help='al simular, enseña todos los casos de cada regla')
    args = ap.parse_args()

    with open(args.reglas, 'rb') as f:
        reglas = tomllib.load(f)['regla']
    with open(args.maqueta, 'rb') as f:
        maqueta = tomllib.load(f)
    estilos = {'caracter': maqueta.get('caracter', {}), 'por_grupo': maqueta.get('caracter_por_grupo', {})}
    with tempfile.NamedTemporaryFile('w', suffix='.json', delete=False, encoding='utf-8') as f:
        json.dump({'reglas': reglas, 'estilos': estilos}, f, ensure_ascii=False)
        ruta = f.name
    jsx = os.path.join(AQUI, 'jsx', 'ortotipografia.jsx')
    script = ('with timeout of 1800 seconds\n'
              'tell application id "com.adobe.InDesign" to do script (POSIX file %s) '
              'language javascript with arguments {%s, %s, %s, %s}\nend timeout') % (
                  cadena(jsx), cadena(ruta), cadena('aplicar' if args.aplicar else 'simular'),
                  cadena(args.documento), cadena('detalle' if args.detalle else ''))
    r = subprocess.run(['osascript', '-e', script], capture_output=True, text=True)
    os.unlink(ruta)
    print((r.stdout + r.stderr).replace('\r', '\n').strip())


if __name__ == '__main__':
    main()
