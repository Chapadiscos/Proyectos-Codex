#!/usr/bin/env python3
"""Fase 2: importa un Word a una copia de la maqueta base en InDesign.

    python3 importar.py "Documentos Word/Capitulo 5"
    python3 importar.py "Documentos Word/Capitulo 5" --solo-preparar   # sin abrir InDesign
    python3 importar.py texto.docx tablas.docx       # varios Word del mismo capítulo

Con varios Word, el de texto es el que más texto tiene; de los demás (tablas y figuras en un
Word aparte) se toman las tablas, las figuras y sus pies, y el resto de su texto va al final
con una duda. El nombre del capítulo es el de la carpeta de los Word.

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
import zipfile

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)

from formatear.docx import Documento          # noqa: E402
from formatear.clasificar import clasificar    # noqa: E402
from formatear import figuras, icml            # noqa: E402


def leer_words(docxs, conf):
    """Clasifica cada Word y los junta: primero el de texto (el que más texto tiene) y detrás los
    demás. De esos, lo que no es tabla ni figura va con una duda. Devuelve (elementos, modo,
    origen), con origen = {id(elemento): Documento} para sacar las imágenes de cada Word."""
    r = conf.get('reglas', {})
    opciones = dict(negritas_con_vineta=r.get('negritas_con_vineta', 'auto'),
                    ladillos_mayusculas=r.get('ladillos_mayusculas', False))
    leidos = []
    for d in docxs:
        doc = Documento(d)
        els, modo = clasificar(doc, **opciones)
        texto = sum(len(e.texto) for e in els if e.papel not in icml.FUERA_DEL_TEXTO)
        leidos.append((texto, d, doc, els, modo))
    leidos.sort(key=lambda x: -x[0])
    if r.get('cabecera'):
        # La cabecera del artículo (título, resumen…) solo en el Word de texto.
        texto, d, doc, _, _ = leidos[0]
        leidos[0] = (texto, d, doc) + clasificar(doc, cabecera=r['cabecera'], **opciones)
    elementos, origen = [], {}
    for k, (_, d, doc, els, _) in enumerate(leidos):
        for e in els:
            if k and e.papel not in icml.FUERA_DEL_TEXTO and e.texto.strip():
                e.dudas.append('Venía en el Word aparte «%s» (no es tabla ni figura): ¿dónde va?' % os.path.basename(d))
            origen[id(e)] = doc
        elementos += els
    return elementos, leidos[0][4], origen, [x[1] for x in leidos]


def convertir_doc(doc, destino_dir):
    """Un .doc (Word 97-2003) pasado a .docx con textutil, de macOS (Word no: se quedaría
    esperando con un diálogo mientras se trabaja en él). textutil escribe los hipervínculos
    como texto («HYPERLINK "mailto:…"»): se quitan."""
    carpeta = os.path.join(destino_dir, 'Word convertido')
    os.makedirs(carpeta, exist_ok=True)
    destino = os.path.join(carpeta, os.path.splitext(os.path.basename(doc))[0] + '.docx')
    r = subprocess.run(['textutil', '-convert', 'docx', '-output', destino, doc], capture_output=True, text=True)
    if r.returncode or not os.path.exists(destino):
        sys.exit('No se pudo convertir %s: %s' % (os.path.basename(doc), r.stderr.strip()))
    with zipfile.ZipFile(destino) as z:
        partes = {n: z.read(n) for n in z.namelist()}
    xml = partes['word/document.xml'].decode('utf-8')
    xml = re.sub(r'(<w:t[^>]*>)\s*HYPERLINK\s+"[^"]*"(?:\s*\\\w\s*"[^"]*")*\s*(</w:t>)', r'\1\2', xml)
    partes['word/document.xml'] = xml.encode('utf-8')
    with zipfile.ZipFile(destino, 'w', zipfile.ZIP_DEFLATED) as z:
        for n, datos in partes.items():
            z.writestr(n, datos)
    return destino


def preparar(docxs, conf, destino_dir, nombre):
    os.makedirs(destino_dir, exist_ok=True)
    enlaces = os.path.join(destino_dir, 'Enlaces')
    carpeta = os.path.dirname(os.path.abspath(docxs[0]))      # la de los Word originales: figuras
    convertidos = {}
    for d in docxs:
        if d.lower().endswith('.doc'):
            convertidos[convertir_doc(d, destino_dir)] = d
    docxs = [next((c for c, o in convertidos.items() if o == d), d) for d in docxs]
    elementos, modo, origen, docxs = leer_words(docxs, conf)
    gen = icml.Generador(conf)
    por_id = figuras.indice_archivos(carpeta)

    def escribir(nombre_archivo, contenido):
        ruta = os.path.join(destino_dir, nombre_archivo)
        with open(ruta, 'w', encoding='utf-8') as f:
            f.write(contenido)
        return ruta

    def extraer(e, prefijo):
        """Las imágenes incrustadas de un elemento, sacadas de su Word a Enlaces/."""
        os.makedirs(enlaces, exist_ok=True)
        doc, res = origen[id(e)], []
        for k, r in enumerate(e.imagenes):
            ext = os.path.splitext(r)[1] or '.png'
            destino = os.path.join(enlaces, '%s_%d%s' % (prefijo, k + 1, ext))
            while os.path.exists(destino) and destino in usados:      # dos Word con el mismo párrafo
                destino = destino.replace(ext, '_b' + ext)
            usados.add(destino)
            with open(destino, 'wb') as f:
                f.write(doc.imagen(r))
            res.append(destino)
        return res

    usados = set()
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
                archivos = extraer(vecinas[0], 'figura_%s' % ids[0])
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
            'archivos': extraer(e, 'imagen_parrafo_%d' % e.origen),
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
            'titulo': titulo is not None,       # en la primera fila de la tabla (celda_titulo)
        })

    # Motivo de cada duda, para la ventana «Recorrer marcas» de InDesign.
    marca_fig = icml.condicion('figura').replace('-', ' ')
    marcas = list(gen.registro)
    for f in salida_fig:
        if f['avisos']:
            marcas.append({'condicion': marca_fig, 'texto': f['nombre'], 'motivo': ' · '.join(f['avisos'])})
    for t in salida_tab:
        if t['avisos']:
            marcas.append({'condicion': marca_fig, 'texto': t['nombre'], 'motivo': ' · '.join(t['avisos'])})
    for su in sueltas:
        marcas.append({'condicion': marca_fig, 'texto': 'Imagen sin pie', 'motivo': ' · '.join(su['avisos'])})
    os.makedirs(os.path.join(AQUI, 'informes'), exist_ok=True)
    with open(os.path.join(AQUI, 'informes', nombre + '-marcas.json'), 'w', encoding='utf-8') as f:
        json.dump({'documento': nombre + '.indd', 'marcas': marcas}, f, ensure_ascii=False, indent=1)

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
        'tabla': {k: conf['tabla'].get(k, '') for k in ('ancho', 'estilo', 'celda_titulo', 'celda_cabecera', 'celda', 'celda_pie')},
        'figuras': salida_fig,
        'tablas': salida_tab,
        'sueltas': sueltas,
        'dudas_en_texto': gen.n_dudas,
        'condicion_figuras': icml.condicion('figura'),
        'notas': gen.con_notas,
        'modo': modo,
        'words': [convertidos.get(d, d) for d in docxs],
        'convertidos': list(convertidos.values()),
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
    ap.add_argument('rutas', nargs='+', help='carpeta del capítulo (con un solo Word) o los Word (.docx o .doc) del capítulo')
    ap.add_argument('--publicacion', default=os.path.join(AQUI, 'publicaciones', 'maqueta-base.toml'))
    ap.add_argument('--salida', default=os.path.join(AQUI, 'salida'))
    ap.add_argument('--solo-preparar', action='store_true', help='genera los ICML sin abrir InDesign')
    args = ap.parse_args()

    with open(args.publicacion, 'rb') as f:
        conf = tomllib.load(f)
    if len(args.rutas) == 1 and os.path.isdir(args.rutas[0]):
        carpeta = args.rutas[0]
        docs = sorted(d for d in glob.glob(os.path.join(carpeta, '*.doc')) + glob.glob(os.path.join(carpeta, '*.docx'))
                      if not os.path.basename(d).startswith('~$'))
        docs = [d for d in docs if not (d.lower().endswith('.doc') and os.path.exists(d + 'x'))]   # mejor el .docx
        if len(docs) != 1:
            sys.exit('En %s hay %d Word: elige cuáles importar (%s)' % (
                carpeta, len(docs), ', '.join(os.path.basename(d) for d in docs)))
    else:
        docs = args.rutas
        carpetas = {os.path.dirname(os.path.abspath(d)) for d in docs}
        if len(carpetas) != 1:
            sys.exit('Los Word de un capítulo tienen que estar en la misma carpeta')
        carpeta = carpetas.pop()
    nombre = os.path.basename(os.path.normpath(carpeta))
    ruta, m = preparar(docs, conf, os.path.join(args.salida, nombre), nombre)
    print('Word: ' + ' + '.join('%s%s' % (os.path.basename(d), ' (texto)' if k == 0 and len(m['words']) > 1 else '')
                                for k, d in enumerate(m['words'])))
    if m['convertidos']:
        print('⚠ Convertido de .doc a .docx con textutil (%s): las imágenes incrustadas y las notas al pie del '
              '.doc pueden perderse; si el autor manda .docx, mejor ese' % ', '.join(os.path.basename(d) for d in m['convertidos']))
    print('Preparado: %s (%d dudas en el texto, %d figuras, %d tablas, %d imágenes sin pie)' % (
        os.path.relpath(ruta, AQUI), m['dudas_en_texto'], len(m['figuras']), len(m['tablas']), len(m['sueltas'])))
    if not args.solo_preparar:
        print(lanzar_indesign(ruta))
        print(resaltar(nombre + '.indd', conf))


if __name__ == '__main__':
    main()
