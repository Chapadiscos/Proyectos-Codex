#!/usr/bin/env python3
"""Cierre de un capítulo ya corregido, en los documentos abiertos en InDesign:
la puntuación pegada a una palabra toma su formato (estilo de carácter o formato local), y las URLs y los DOI
(«doi: 10.1016/…», a https://doi.org/…) pasan a hipervínculos sin cambiar su formato.

    python3 finalizar.py                           # simula en los «Capitulo…» abiertos
    python3 finalizar.py --detalle                 # simula enseñando todos los casos
    python3 finalizar.py --aplicar                 # aplica (un Cmd+Z por documento lo deshace)
    python3 finalizar.py --documento "Capitulo 5.indd" --aplicar

No pasan a la puntuación el superíndice ni el estilo de los símbolos ([caracter] de la publicación).
"""
import argparse
import json
import os
import subprocess
import tempfile
import tomllib

AQUI = os.path.dirname(os.path.abspath(__file__))


def cadena(texto):
    """Cadena de AppleScript (json.dumps escribe «í» como \\u00ed y AppleScript no lo entiende)."""
    return '"%s"' % texto.replace('\\', '\\\\').replace('"', '\\"')


def estilos_excluidos(conf):
    """Estilos de carácter que no pasan a la puntuación vecina: el superíndice («10⁶.» no lleva
    el punto volado) y el de los símbolos."""
    c = conf.get('caracter', {})
    return [e for e in (c.get('superindice'), c.get('estilo_simbolos')) if e]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--documento', default='', help='nombre del documento abierto (por defecto, los «Capitulo…»)')
    ap.add_argument('--aplicar', action='store_true', help='hace los cambios (sin esto solo simula)')
    ap.add_argument('--detalle', action='store_true', help='al simular, enseña todos los casos')
    ap.add_argument('--publicacion', default=os.path.join(AQUI, 'publicaciones', 'maqueta-base.toml'))
    args = ap.parse_args()

    with open(args.publicacion, 'rb') as f:
        conf = tomllib.load(f)
    with tempfile.NamedTemporaryFile('w', suffix='.json', delete=False, encoding='utf-8') as f:
        json.dump({'excluir': estilos_excluidos(conf)}, f, ensure_ascii=False)
        ruta = f.name
    jsx = os.path.join(AQUI, 'jsx', 'finalizar.jsx')
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
