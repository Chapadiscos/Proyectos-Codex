#!/usr/bin/env python3
"""Fase 2: importa un Word a una copia de la maqueta base en InDesign.

    python3 importar.py "Documentos Word/Capitulo 5"
    python3 importar.py "Documentos Word/Capitulo 5" --solo-preparar   # sin abrir InDesign

Deja en salida/<capítulo>/ el .indd, los ICML y las imágenes que solo estaban dentro del
Word. Es una galerada: el texto va con los estilos de la maqueta (título y autores al
principio; la portadilla se monta a mano desde la Biblioteca); las dudas, resaltadas con
texto condicional (una condición por tipo); figuras y tablas, en la mesa de trabajo junto a
la página donde se citan por primera vez.
"""
import argparse
import glob
import json
import os
import re
import subprocess
import sys
import tomllib

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)

from formatear.docx import Documento          # noqa: E402
from formatear.clasificar import clasificar    # noqa: E402
from formatear import figuras, icml            # noqa: E402


def preparar(docx, conf, destino_dir, nombre):
    os.makedirs(destino_dir, exist_ok=True)
    enlaces = os.path.join(destino_dir, 'Enlaces')
    doc = Documento(docx)
    elementos, modo = clasificar(doc, conf.get('reglas', {}).get('negritas_con_vineta', 'auto'))
    gen = icml.Generador(conf)
    carpeta = os.path.dirname(os.path.abspath(docx))
    por_id = figuras.indice_archivos(carpeta)

    def escribir(nombre_archivo, contenido):
        ruta = os.path.join(destino_dir, nombre_archivo)
        with open(ruta, 'w', encoding='utf-8') as f:
            f.write(contenido)
        return ruta

    def extraer(rutas_docx, prefijo):
        os.makedirs(enlaces, exist_ok=True)
        res = []
        for k, r in enumerate(rutas_docx):
            ext = os.path.splitext(r)[1] or '.png'
            destino = os.path.join(enlaces, '%s_%d%s' % (prefijo, k + 1, ext))
            with open(destino, 'wb') as f:
                f.write(doc.imagen(r))
            res.append(destino)
        return res

    historia = escribir('historia.icml', gen.historia(elementos))

    cap = next((e for e in elementos if e.papel == 'capitulo'), None)
    autores = next((e for e in elementos if e.papel == 'autores'), None)

    # Figuras: cada pie con sus archivos (los pies partidos en dos párrafos se juntan).
    lista_fig, ultimo = [], None
    for k, e in enumerate(elementos):
        if e.papel != 'pie_figura':
            continue
        if 'figuras' not in e.datos and ultimo is not None:
            ultimo['extra'].append(e)
            continue
        ultimo = {'pie': e, 'extra': [], 'k': k}
        lista_fig.append(ultimo)
    salida_fig = []
    for n, f in enumerate(lista_fig):
        e, ids = f['pie'], f['pie'].datos['figuras']
        archivos, avisos = [], []
        for fid in ids:
            encontrados, aviso = figuras.buscar_archivos(fid, e.texto, por_id)
            archivos += [os.path.join(carpeta, a) for a in encontrados if os.path.join(carpeta, a) not in archivos]
            if aviso and encontrados:
                avisos.append('Figura %s: %s' % (fid, aviso))
        # Figura compuesta: de izquierda a derecha («izq» antes que «dcha»; si no, A, B…).
        archivos.sort(key=lambda a: (0 if re.search(r'izq', a, re.I) else 1 if re.search(r'dch|der', a, re.I) else 0, a))
        if not archivos:
            # Imagen incrustada junto al pie (delante o detrás).
            vecinas = [x for x in elementos[max(f['k'] - 1, 0):f['k'] + 2] if x.papel == 'imagen']
            if vecinas:
                archivos = extraer(vecinas[0].imagenes, 'figura_%s' % ids[0])
                avisos.append('Sin archivo suelto: imagen sacada del Word (puede tener poca resolución)')
            else:
                avisos.append('No se ha encontrado ninguna imagen para esta figura')
        pie = e
        if f['extra']:
            from dataclasses import replace
            trozos = list(e.trozos)
            for x in f['extra']:
                trozos += [replace(x.trozos[0], texto=' ')] + list(x.trozos)
            pie = replace(e, trozos=trozos)
        salida_fig.append({
            'buscar': re.match(r'\d+', ids[0]).group(0),
            'nombre': 'Figura ' + ', '.join(ids),
            'archivos': archivos,
            'pie': escribir('figura_%02d.icml' % (n + 1), gen.pie_figura(pie)),
            'avisos': avisos + e.dudas,
        })

    # Imágenes incrustadas sin pie (p. ej. un algoritmo dentro del texto).
    sueltas = []
    for k, e in enumerate(elementos):
        if e.papel != 'imagen':
            continue
        vecinos = [x.papel for x in elementos[max(k - 1, 0):k + 2] if x is not e]
        if 'pie_figura' in vecinos or 'etiqueta_imagen' in vecinos:
            continue
        siguiente = next((x for x in elementos[k + 1:] if x.texto.strip() and x.papel not in icml.FUERA_DEL_TEXTO), None)
        sobrantes = [os.path.join(carpeta, a) for a in figuras.inventario(elementos, carpeta)[1]]
        aviso = 'Imagen del Word sin pie (párrafo %d)' % e.origen
        if sobrantes:
            aviso += '. Archivos de la carpeta sin pie: ' + ', '.join(os.path.basename(a) for a in sobrantes)
        sueltas.append({
            'archivos': extraer(e.imagenes, 'imagen_parrafo_%d' % e.origen),
            'buscar_texto': siguiente.texto.strip()[:40] if siguiente else '',
            'avisos': [aviso],
        })

    # Tablas: título + tabla + notas.
    salida_tab = []
    for k, e in enumerate(elementos):
        if e.papel != 'tabla':
            continue
        titulo = elementos[k - 1] if k and elementos[k - 1].papel == 'titulo_tabla' else None
        pies = []
        for x in elementos[k + 1:]:
            if x.papel != 'pie_tabla':
                break
            pies.append(x)
        numero = titulo.datos.get('numero') if titulo else None
        salida_tab.append({
            'buscar': numero or '',
            'nombre': 'Tabla %s' % (numero or '(sin título)'),
            'icml': escribir('tabla_%02d.icml' % (len(salida_tab) + 1),
                             gen.tabla(titulo, e.tabla, pies, conf['tabla']['ancho'])),
            'avisos': [] if titulo else ['Tabla sin título en el Word'],
        })

    nombre_indd = os.path.join(destino_dir, nombre + '.indd')
    manifiesto = {
        'maqueta': os.path.join(AQUI, conf['maqueta']),
        'destino': nombre_indd,
        'historia': historia,
        'capitulo': {
            'numero': cap.datos['numero'] if cap else '',
            'titulo': cap.datos['titulo'] if cap else '',
            'autores': autores.texto.strip() if autores else '',
        },
        'figura': conf['figuras'],
        'tabla': {k: conf['tabla'].get(k, '') for k in ('ancho', 'estilo', 'celda_cabecera', 'celda', 'celda_pie')},
        'figuras': salida_fig,
        'tablas': salida_tab,
        'sueltas': sueltas,
        'dudas_en_texto': gen.n_dudas,
        'condicion_figuras': icml.condicion('figura'),
        'notas': gen.con_notas,
        'modo': modo,
    }
    ruta = escribir('manifiesto.json', json.dumps(manifiesto, ensure_ascii=False, indent=1))
    return ruta, manifiesto


def lanzar_indesign(manifiesto):
    jsx = os.path.join(AQUI, 'jsx', 'importar.jsx')
    script = ('with timeout of 1800 seconds\n'
              'tell application id "com.adobe.InDesign" to do script (POSIX file %s) '
              'language javascript with arguments {%s}\nend timeout') % (
                  json.dumps(jsx), json.dumps(manifiesto))
    r = subprocess.run(['osascript', '-e', script], capture_output=True, text=True)
    return (r.stdout + r.stderr).replace('\r', '\n').strip()


def resaltar(documento, conf):
    """Resalta las palabras de [resaltar] de la publicación (Tabla, Figura…) en un documento abierto."""
    r = conf.get('resaltar', {})
    if not r.get('palabras'):
        return ''
    jsx = os.path.join(AQUI, 'jsx', 'resaltar_palabras.jsx')
    script = ('with timeout of 600 seconds\n'
              'tell application id "com.adobe.InDesign" to do script (POSIX file "%s") '
              'language javascript with arguments {"%s", "%s", "%s", "%s"}\nend timeout') % tuple(
                  x.replace('\\', '\\\\').replace('"', '\\"')
                  for x in (jsx, '|'.join(r['palabras']), documento, r.get('condicion', 'Risk word'),
                            r.get('color', 'GREEN')))
    res = subprocess.run(['osascript', '-e', script], capture_output=True, text=True)
    return (res.stdout + res.stderr).replace('\r', '\n').strip()


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('ruta', help='carpeta del capítulo o archivo .docx')
    ap.add_argument('--publicacion', default=os.path.join(AQUI, 'publicaciones', 'maqueta-base.toml'))
    ap.add_argument('--salida', default=os.path.join(AQUI, 'salida'))
    ap.add_argument('--solo-preparar', action='store_true', help='genera los ICML sin abrir InDesign')
    args = ap.parse_args()

    with open(args.publicacion, 'rb') as f:
        conf = tomllib.load(f)
    if os.path.isdir(args.ruta):
        docs = [d for d in glob.glob(os.path.join(args.ruta, '*.docx')) if not os.path.basename(d).startswith('~$')]
        nombre = os.path.basename(os.path.normpath(args.ruta))
    else:
        docs, nombre = [args.ruta], os.path.splitext(os.path.basename(args.ruta))[0]
    if len(docs) != 1:
        sys.exit('Se esperaba un .docx en %s y hay %d' % (args.ruta, len(docs)))
    ruta, m = preparar(docs[0], conf, os.path.join(args.salida, nombre), nombre)
    print('Preparado: %s (%d dudas en el texto, %d figuras, %d tablas, %d imágenes sin pie)' % (
        os.path.relpath(ruta, AQUI), m['dudas_en_texto'], len(m['figuras']), len(m['tablas']), len(m['sueltas'])))
    if not args.solo_preparar:
        print(lanzar_indesign(ruta))
        print(resaltar(nombre + '.indd', conf))


if __name__ == '__main__':
    main()
