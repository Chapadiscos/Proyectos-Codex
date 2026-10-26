#!/usr/bin/env python3
"""Fase 3, bloque 2: casos ortotipográficos dudosos en los documentos abiertos en InDesign.
No corrige nada: los marca con texto condicional («Revisar tilde», «Revisar cursiva»…).

    python3 dudas.py                           # simula: cuenta y enseña las dudas
    python3 dudas.py --detalle                 # simula enseñándolas todas
    python3 dudas.py --marcar                  # las marca en InDesign (un Cmd+Z por documento)
    python3 dudas.py --documento "Capitulo 5.indd" --marcar
    python3 dudas.py --marcar --claude         # y Claude propone qué hacer con cada una (bloque 3)
    python3 dudas.py --marcar --tipos compuesto   # solo esos tipos: se suman a las dudas que ya
                                                  # hay, sin tocar las demás ni lo ya revisado

Se revisan juntos todos los documentos abiertos que empiezan por «Capitulo» (o el indicado):
una palabra desconocida que se repite en el conjunto se da por término correcto.
Las palabras que no son errores van a publicaciones/diccionario.txt.
Cada documento deja su lista en informes/<documento>-dudas.json, que lee la ventana
«Revisar dudas» de InDesign (jsx/revisar_dudas.jsx).
"""
import argparse
import json
import os
import subprocess
import sys
import tempfile
import tomllib
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)

from formatear import claude as mod_claude    # noqa: E402
from formatear import dudas as mod_dudas      # noqa: E402
ETIQUETA = {'tilde': 'Tildes', 'ortografia': 'Ortografía y gramática', 'desconocida': 'Palabras desconocidas',
            'extranjerismo': 'Extranjerismos sin cursiva', 'cursiva': 'Cursiva sin criterio fijo',
            'criterio': 'Dos formas de escribir lo mismo', 'compuesto': 'Palabras compuestas con guion'}

# Propuestas que no necesitan a Claude.
AUTOMATICAS = {'compuesto': {'accion': 'cambiar', 'texto_nuevo': '', 'formato': 'no_partir', 'diccionario': False,
                             'motivo': 'Palabra compuesta con guion: sin partir a final de línea.'}}


def cadena(texto):
    """Cadena de AppleScript (json.dumps escribe «í» como \\u00ed y AppleScript no lo entiende)."""
    return '"%s"' % texto.replace('\\', '\\\\').replace('"', '\\"')


def indesign(jsx, *args):
    script = ('with timeout of 1800 seconds\ntell application id "com.adobe.InDesign" to do script '
              '(POSIX file %s) language javascript with arguments {%s}\nend timeout') % (
                  cadena(os.path.join(AQUI, 'jsx', jsx)), ', '.join(cadena(a) for a in args))
    r = subprocess.run(['osascript', '-e', script], capture_output=True, text=True)
    return (r.stdout + r.stderr).replace('\r', '\n').strip()


def documentos_abiertos():
    r = subprocess.run(['osascript', '-e', 'tell application id "com.adobe.InDesign" to get name of every document'],
                       capture_output=True, text=True)
    return [n.strip() for n in r.stdout.strip().split(',') if n.strip()]


def estilo_caracter(maqueta, estilo_parrafo, clave):
    """Estilo de carácter («cursiva», «negrita», «negrita_cursiva») para un párrafo de ese
    estilo, según maqueta-base.toml."""
    grupo = estilo_parrafo.split('/')[0]
    por_grupo = maqueta.get('caracter_por_grupo', {})
    pg = por_grupo.get(grupo, por_grupo.get(estilo_parrafo, {}))
    return pg.get(clave, maqueta.get('caracter', {}).get(clave, ''))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--documento', default='', help='nombre del documento abierto (por defecto, los «Capitulo…»)')
    ap.add_argument('--marcar', action='store_true', help='marca las dudas en InDesign (sin esto solo simula)')
    ap.add_argument('--detalle', action='store_true', help='enseña todas las dudas, no solo unos ejemplos')
    ap.add_argument('--claude', action='store_true', help='Claude propone qué hacer con cada duda')
    ap.add_argument('--tipos', default='', help='solo estos tipos (separados por comas), sumados a las dudas que ya hay')
    ap.add_argument('--diccionario', default=os.path.join(AQUI, 'publicaciones', 'diccionario.txt'))
    ap.add_argument('--maqueta', default=os.path.join(AQUI, 'publicaciones', 'maqueta-base.toml'))
    args = ap.parse_args()

    nombres = [args.documento] if args.documento else [n for n in documentos_abiertos() if n.startswith('Capitulo')]
    if not nombres:
        print('No hay documentos «Capitulo…» abiertos en InDesign.')
        return
    tmp = tempfile.mkdtemp()
    textos = {}
    for n in nombres:
        ruta = os.path.join(tmp, n + '.json')
        r = indesign('exportar_texto.jsx', ruta, n)
        if r.startswith('ERROR'):
            print(r)
            return
        with open(ruta, encoding='utf-8') as f:
            textos[n] = json.load(f)

    lt = mod_dudas.LanguageTool()
    try:
        dic = mod_dudas.cargar_diccionario(args.diccionario)
        total = Counter()
        for ps in textos.values():
            total += mod_dudas.desconocidas(ps, lt)
        frecuentes = {w for w, k in total.items() if k >= 2}
        os.makedirs(os.path.join(AQUI, 'informes'), exist_ok=True)
        with open(args.maqueta, 'rb') as f:
            maqueta = tomllib.load(f)
        tipos = [t.strip() for t in args.tipos.split(',') if t.strip()]
        analisis = {n: [d for d in mod_dudas.analizar(ps, lt, diccionario=dic, frecuentes=frecuentes)
                        if not tipos or d.tipo in tipos]
                    for n, ps in sorted(textos.items())}
        listas = {n: [dict(asdict(d), id=k, propuesta=None,
                           **{'estilo_' + c: estilo_caracter(maqueta, d.estilo, c)
                              for c in ('cursiva', 'negrita', 'negrita_cursiva', 'no_partir')})
                      for k, d in enumerate(ds)] for n, ds in analisis.items()}
        for l in listas.values():
            for d in l:
                if d['tipo'] in AUTOMATICAS:
                    d['propuesta'] = dict(AUTOMATICAS[d['tipo']], id=d['id'])
        if args.claude:
            print('Claude revisa las dudas de %d capítulos…' % len(listas), flush=True)
            with ThreadPoolExecutor(max_workers=4) as ex:
                futuros = {n: ex.submit(mod_claude.proponer, [d for d in l if d['tipo'] not in AUTOMATICAS],
                                        n.replace('.indd', ''))
                           for n, l in listas.items() if any(d['tipo'] not in AUTOMATICAS for d in l)}
                for n, fu in futuros.items():
                    try:
                        props = fu.result()
                    except Exception as e:
                        print('   %s: Claude falló: %s' % (n, e))
                        continue
                    for d in listas[n]:
                        if d['tipo'] not in AUTOMATICAS:
                            d['propuesta'] = props.get(d['id'])
        for n, dudas in analisis.items():
            ruta = os.path.join(AQUI, 'informes', n.replace('.indd', '') + '-dudas.json')
            todas = listas[n]
            if tipos and os.path.exists(ruta):
                # Solo algunos tipos: se suman a las dudas que ya había, con ids nuevos.
                with open(ruta, encoding='utf-8') as f:
                    previas = [d for d in json.load(f)['dudas'] if d['tipo'] not in tipos]
                base = max((d['id'] for d in previas), default=-1) + 1
                for d in todas:
                    d['id'] += base
                    if d['propuesta']:
                        d['propuesta']['id'] = d['id']
                todas = previas + todas
            with open(ruta, 'w', encoding='utf-8') as f:
                json.dump({'documento': n, 'condiciones': mod_dudas.CONDICIONES, 'diccionario': args.diccionario,
                           'dudas': todas}, f, ensure_ascii=False, indent=1)
            print('== %s: %d dudas' % (n, len(dudas)))
            if args.claude:
                props = [d['propuesta'] for d in listas[n] if d['propuesta']]
                print('   Claude: cambiar %d · omitir %d (al diccionario %d)' % (
                    sum(p['accion'] == 'cambiar' for p in props), sum(p['accion'] == 'omitir' for p in props),
                    sum(p['diccionario'] for p in props)))
            for tipo in mod_dudas.CONDICIONES:
                de_tipo = [d for d in dudas if d.tipo == tipo]
                if not de_tipo:
                    continue
                print('   %s (%s): %d' % (ETIQUETA[tipo], mod_dudas.CONDICIONES[tipo][0], len(de_tipo)))
                vistos = []
                for d in de_tipo:
                    linea = '      %s%s · %s' % (d.texto.strip(), ' → ' + d.sugerencia if d.sugerencia else '', d.motivo)
                    if linea not in vistos:
                        vistos.append(linea)
                for linea in vistos if args.detalle else vistos[:4]:
                    print(linea)
            if args.marcar:
                ruta = os.path.join(tmp, n + '-marcar.json')
                with open(ruta, 'w', encoding='utf-8') as f:
                    # Con --tipos solo se tocan esas condiciones; las demás marcas se quedan.
                    conds = {t: c for t, c in mod_dudas.CONDICIONES.items() if not tipos or t in tipos}
                    json.dump({'condiciones': conds, 'dudas': [asdict(d) for d in dudas]}, f, ensure_ascii=False)
                print('   → ' + indesign('marcar_dudas.jsx', ruta, n))
    finally:
        lt.cerrar()


if __name__ == '__main__':
    main()
