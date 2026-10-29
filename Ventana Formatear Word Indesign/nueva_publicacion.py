#!/usr/bin/env python3
"""Publicación nueva a partir de su último InDesign maquetado.

    python3 nueva_publicacion.py "…/Revista GHHO N7.indd" --nombre "Revista GHHO"

1. Copia el maquetado a publicaciones/maquetas/<nombre>.indd y lo deja como maqueta: la
   primera página y una de interior, vacías y con los marcos de texto enlazados; estilos,
   muestras y maestras, los del maquetado (jsx/crear_maqueta.jsx).
2. Escribe publicaciones/<nombre>.toml partiendo de maqueta-base.toml: para cada papel (título,
   ladillos, viñetas, negrita…) busca en el maquetado el estilo que le corresponde. Lo que no
   encuentra lo deja avisado con «⚠» para revisarlo.

Si la publicación ya existe, solo rehace la maqueta (para partir de un número más reciente)
y avisa de los estilos de su configuración que ya no están en ella.

Actualizar una publicación desde un número más reciente (botón «Actualizar publicación…»),
en dos pasos para ver antes qué cambia:

    python3 nueva_publicacion.py "…/Revista GHHO N8.indd" --actualizar publicaciones/revista-ghho.toml
    python3 nueva_publicacion.py --confirmar publicaciones/revista-ghho.toml     (o --descartar)

El primero prepara la maqueta nueva junto a la actual («… (nueva).indd») y la compara con ella;
el segundo la pone en su lugar, guarda la anterior en publicaciones/maquetas/anteriores/ y
anota el maquetado nuevo en la configuración, que por lo demás no cambia.
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import tomllib
import unicodedata
from datetime import date

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)

from formatear.icml import partes_estilo      # noqa: E402

BASE = os.path.join(AQUI, 'publicaciones', 'maqueta-base.toml')

# Nombres con los que se suele llamar al estilo de cada papel, del más probable al menos.
# El de maqueta-base.toml se prueba siempre el primero.
SINONIMOS = {
    'parrafo': {
        'capitulo_titulo': ['titulo esp', 'titulo capitulo', 'titulo articulo', 'titulo'],
        'autores': ['autores', 'autor'],
        'ladillo1': ['ladillo 1', 'ladillo1', 'titulo 1', 'ladillo'],
        'ladillo2': ['ladillo 2', 'ladillo2', 'titulo 2'],
        'ladillo3': ['ladillo 3', 'ladillo3', 'titulo 3'],
        'texto': ['texto base', 'texto', 'cuerpo'],
        'texto_vineta': ['texto base vineta', 'texto vineta'],
        'vineta1': ['vineta 1', 'vineta', 'bullet'],
        'vineta2': ['vineta 2'],
        'vineta3': ['vineta 3'],
        'vineta4': ['vineta 4'],
        'titulo_ideas': ['titulo ideas basicas', 'ideas basicas'],
        'texto_ideas': ['texto ideas'],
        'titulo_bibliografia': ['titulo bibliografia'],
        'bibliografia': ['bibliografia', 'referencias'],
        'titulo_tabla': ['titulo tabla'],
        'pie_tabla': ['pie tabla', 'nota tabla'],
        'pie_figura': ['pie figura', 'pie de figura', 'leyenda'],
        'celda_cabecera': ['cabecera tabla'],
        'celda': ['celda izda', 'celda'],
    },
    # Cabecera de artículo de revista: solo se añaden si el maquetado tiene resumen o abstract.
    'cabecera': {
        'titulo_ing': ['titulo ing', 'titulo ingles', 'title'],
        'centro': ['centro', 'centros', 'filiacion', 'afiliacion'],
        'comunicacion': ['comunicacion presentadaa', 'comunicacion presentada', 'comunicacion'],
        'titulo_resumen': ['ladillo resumen abstract', 'ladillo resumen', 'titulo resumen'],
        'resumen': ['resumen esp', 'resumen'],
        'abstract': ['abstract ing', 'abstract'],
        'palabras_clave': ['palabras clave keywords', 'palabras clave', 'keywords'],
        'primer_texto': ['1a texto base despues resumen', 'texto despues resumen', 'primer parrafo'],
    },
    'caracter': {
        'negrita': ['negrita', 'bold', 'medium', 'semibold'],
        'cursiva': ['cursiva', 'italic', 'light italic'],
        'negrita_cursiva': ['negrita cursiva', 'bold italic', 'medium italic'],
        'superindice': ['super', 'superindice', 'superscript'],
        'no_partir': ['nopartir', 'no partir'],
        'etiqueta_figura': ['figura x', 'etiqueta figura', 'figura'],
        'estilo_simbolos': ['symbol', 'simbolos'],
    },
    'tabla': {
        'estilo': ['tabla'],
        'celda_titulo': ['encabezado', 'titulo'],
        'celda_cabecera': ['cabecera'],
        'celda': ['celda izquierda', 'celda'],
        'celda_pie': ['pie tabla', 'pie'],
    },
}
# Papel sin estilo propio en la maqueta: usa el de otro.
EN_SU_LUGAR = {
    'ladillo2': 'ladillo1', 'ladillo3': 'ladillo2', 'texto_vineta': 'texto',
    'vineta2': 'vineta1', 'vineta3': 'vineta2', 'vineta4': 'vineta3',
    'titulo_ideas': 'ladillo2', 'texto_ideas': 'texto', 'titulo_bibliografia': 'ladillo1',
    'celda_cabecera': 'texto', 'celda': 'texto', 'pie_tabla': 'texto', 'titulo_tabla': 'pie_figura',
    'negrita_cursiva': 'negrita',
}
CABECERA_COMENTARIOS = {
    'titulo_ing': 'título en inglés',
    'centro': 'centro de trabajo de los autores y autor para la correspondencia',
    'comunicacion': '«El presente trabajo se corresponde a una comunicación…»',
    'titulo_resumen': '«RESUMEN» / «ABSTRACT»',
    'resumen': '',
    'abstract': '',
    'palabras_clave': '«Palabras clave: …» / «Keywords: …»',
    'primer_texto': 'primer párrafo del texto, detrás del resumen',
}


def norm(s):
    s = unicodedata.normalize('NFD', s.replace('ª', 'a').replace('º', 'o'))
    s = ''.join(c for c in s if not unicodedata.combining(c)).lower()
    return ' '.join(re.sub(r'[^0-9a-z]+', ' ', s).split())


def buscar(estilos, actual, sinonimos):
    """El estilo de la maqueta para un papel: el mismo nombre, el mismo nombre sin grupo, un
    sinónimo como nombre o, si tiene más de una palabra, dentro del nombre."""
    propios = [e for e in estilos if not e.startswith('[')]
    if actual in propios:
        return actual
    hoja = lambda e: norm(partes_estilo(e)[-1])
    claves = ([norm(partes_estilo(actual)[-1])] if actual else []) + [norm(s) for s in sinonimos]
    for c in claves:
        hay = sorted((e for e in propios if hoja(e) == c), key=len)
        if hay:
            return hay[0]
    for c in claves:
        if ' ' in c:
            hay = sorted((e for e in propios if (' %s ' % c) in (' %s ' % norm(e.replace('/', ' ')))), key=len)
            if hay:
                return hay[0]
    return None


def cadena(v):
    return '"%s"' % v.replace('\\', '\\\\').replace('"', '\\"')


def crear_maqueta(maquetado, destino):
    """Lanza jsx/crear_maqueta.jsx y devuelve la información de la maqueta (estilos, página)."""
    return _crear_maqueta_jsx(maquetado, destino)


def leer_maqueta(maqueta):
    """Estilos, maestras y medidas de una maqueta, sin cambiarla."""
    return _crear_maqueta_jsx(maqueta, '')


def _crear_maqueta_jsx(maquetado, destino):
    with tempfile.NamedTemporaryFile(suffix='.json', delete=False) as f:
        info_json = f.name
    jsx = os.path.join(AQUI, 'jsx', 'crear_maqueta.jsx')
    script = ('with timeout of 1800 seconds\n'
              'tell application id "com.adobe.InDesign" to do script (POSIX file %s) '
              'language javascript with arguments {%s, %s, %s}\nend timeout') % (
                  cadena(jsx), cadena(maquetado), cadena(destino), cadena(info_json))
    r = subprocess.run(['osascript', '-e', script], capture_output=True, text=True)
    salida = (r.stdout + r.stderr).strip()
    if salida != 'OK':
        sys.exit(salida or 'InDesign no ha contestado')
    with open(info_json, encoding='utf-8') as f:
        info = json.load(f)
    os.unlink(info_json)
    return info


def proponer(info, maqueta_rel, maquetado, nombre):
    """Texto de la configuración: maqueta-base.toml con los estilos de la maqueta nueva."""
    with open(BASE, encoding='utf-8') as f:
        lineas = f.read().split('\n')
    base = tomllib.loads('\n'.join(lineas))
    listas = {'parrafo': info['parrafo'], 'caracter': info['caracter'],
              'tabla_estilo': info['tabla'], 'celda': info['celda']}
    avisos, elegidos = [], {}

    def resolver(seccion, clave, actual):
        if seccion == 'tabla':
            lista = listas['tabla_estilo'] if clave == 'estilo' else listas['celda']
            sin = SINONIMOS['tabla'].get(clave, [])
        elif seccion == 'caracter':
            lista, sin = listas['caracter'], SINONIMOS['caracter'].get(clave, [])
        else:
            lista, sin = listas['parrafo'], SINONIMOS['parrafo'].get(clave, []) + SINONIMOS['cabecera'].get(clave, [])
        e = buscar(lista, actual, sin)
        if e:
            elegidos[(seccion, clave)] = e
            return e, ''
        otro = EN_SU_LUGAR.get(clave)
        if otro and (seccion, otro) not in elegidos and otro in base.get(seccion, {}):
            resolver(seccion, otro, base[seccion][otro])       # aún no ha salido en el archivo
        if otro and (seccion, otro) in elegidos:
            elegidos[(seccion, clave)] = elegidos[(seccion, otro)]
            return elegidos[(seccion, otro)], 'no hay estilo propio: el de %s' % otro
        if seccion in ('tabla', 'caracter') or clave in ('estilo_objeto',):
            return '', 'no hay estilo en la maqueta: no se aplica'
        avisos.append('%s.%s' % (seccion, clave))
        return actual, '⚠ no está en la maqueta: InDesign lo creará vacío al importar'

    cab = {k: buscar(info['parrafo'], '', s) for k, s in SINONIMOS['cabecera'].items()}
    con_cabecera = bool(cab.get('resumen') or cab.get('abstract'))
    pagina = info['pagina']
    res, seccion = [], ''
    for ln in lineas:
        m_sec = re.match(r'^\[(\w+)\]', ln)
        if m_sec:
            if seccion == 'parrafo' and con_cabecera:
                # Cabecera del artículo: delante de la línea en blanco que cierra [parrafo].
                while res and not res[-1].strip():
                    res.pop()
                res.append('# Cabecera del artículo (título en inglés, centro, resumen, abstract…).')
                for k, e in cab.items():
                    if e:
                        elegidos[('parrafo', k)] = e
                        com = CABECERA_COMENTARIOS[k]
                        res.append('%-19s = %s%s' % (k, cadena(e), ('   # ' + com) if com else ''))
                    else:
                        res.append('# %-17s = (no hay estilo en la maqueta)' % k)
                res.append('')
            seccion = m_sec.group(1)
            res.append(ln)
            if seccion == 'caracter_por_grupo':
                res += ['# Los grupos de estilos con otra fuente que necesiten su negrita y cursiva propias.', '']
            continue
        if seccion == 'caracter_por_grupo':
            continue
        if ln.startswith('# Configuración de una publicación'):
            res += ['# Configuración de «%s», creada el %s a partir de su último maquetado:' % (nombre, date.today().isoformat()),
                    '#   %s' % maquetado,
                    '# Revisa las líneas con «⚠». Para rehacer la maqueta desde un número más reciente:',
                    '#   python3 nueva_publicacion.py <último .indd> --nombre %s' % cadena(nombre)]
            continue
        if ln.startswith('# Para una publicación nueva'):
            continue
        if con_cabecera and ln.startswith(('# Galerada: título y autores', '# se monta a mano con el elemento')):
            if ln.startswith('# Galerada'):
                res.append('# Galerada: la cabecera del artículo (título, autores, resumen…) va al principio del texto.')
            continue
        m = re.match(r'^(\s*)(\w+)(\s*=\s*)"((?:[^"\\]|\\.)*)"(.*)$', ln)
        if ln.startswith('maqueta '):
            res.append('maqueta   = %s' % cadena(maqueta_rel))
            res.append('maquetado = %s' % cadena(maquetado))
            continue
        if m and seccion in ('parrafo', 'caracter', 'tabla') and m.group(2) != 'simbolos' and m.group(2) != 'simbolos_superindice':
            actual = tomllib.loads('v = "%s"' % m.group(4))['v']
            nuevo, nota = resolver(seccion, m.group(2), actual)
            com = '' if m.group(2) == 'capitulo_titulo' else m.group(5)    # el ejemplo es de Ponencias
            if nota:
                com = '   # ' + nota
            res.append('%s%s%s%s%s' % (m.group(1), m.group(2), m.group(3), cadena(nuevo), com))
            continue
        if m and seccion == 'figuras' and m.group(2) == 'estilo_objeto':
            e = buscar(info['objeto'], m.group(4), ['marco figura', 'figura', 'imagen'])
            res.append('estilo_objeto = %s%s' % (cadena(e or ''), '' if e else '   # no hay estilo de objeto: no se aplica'))
            continue
        m_num = re.match(r'^(ancho\s*=\s*)[\d.]+(.*)$', ln)
        if m_num and seccion == 'figuras':
            res.append('%s%d       # mm: el ancho de una columna' % (m_num.group(1), round(pagina['ancho_columna'])))
            continue
        if m_num and seccion == 'tabla':
            res.append('%s%d      # mm: el ancho de la caja de texto' % (m_num.group(1), round(pagina['ancho_texto'])))
            continue
        if seccion == 'reglas' and ln.startswith('negritas_con_vineta') and con_cabecera:
            res.append(ln)
            res += ['# Artículos de revista: al principio, título, título en inglés, autores, centro, resumen,',
                    '# abstract y palabras clave, con los estilos de la cabecera de [parrafo].',
                    'cabecera = "articulo"',
                    '# Ladillos escritos en mayúsculas sin negrita («INTRODUCCIÓN»).',
                    'ladillos_mayusculas = true']
            continue
        res.append(ln)
    texto = '\n'.join(res)
    tomllib.loads(texto)            # que se pueda leer
    return texto, avisos, con_cabecera, base


def comprobar(conf, info):
    """Estilos de la configuración que no están en la maqueta."""
    falta = []
    for seccion, lista in (('parrafo', info['parrafo']), ('caracter', info['caracter'])):
        for k, v in conf.get(seccion, {}).items():
            if isinstance(v, str) and v and k not in ('simbolos', 'simbolos_superindice') and v not in lista:
                falta.append('%s.%s = %s' % (seccion, k, v))
    for k, v in conf.get('tabla', {}).items():
        if isinstance(v, str) and v and v not in (info['tabla'] if k == 'estilo' else info['celda']):
            falta.append('tabla.%s = %s' % (k, v))
    v = conf.get('figuras', {}).get('estilo_objeto')
    if v and v not in info['objeto']:
        falta.append('figuras.estilo_objeto = %s' % v)
    return falta


# ---- actualizar una publicación ------------------------------------------------------------
def pendiente_de(conf):
    """Rutas de la actualización: maqueta actual, la nueva provisional y su informe."""
    maqueta = os.path.join(AQUI, conf['maqueta'])
    base = os.path.splitext(maqueta)[0]
    return maqueta, base + ' (nueva).indd', base + ' (nueva).json'


def copia_anterior(maqueta):
    carpeta = os.path.join(AQUI, 'publicaciones', 'maquetas', 'anteriores')
    base = '%s %s' % (os.path.splitext(os.path.basename(maqueta))[0], date.today().isoformat())
    ruta, n = os.path.join(carpeta, base + '.indd'), 2
    while os.path.exists(ruta):
        ruta, n = os.path.join(carpeta, '%s-%d.indd' % (base, n)), n + 1
    return ruta


def mm(x):
    return '%g' % round(x, 1)


def comparar(conf, antes, info):
    """Líneas del informe: qué cambia de la maqueta actual a la nueva."""
    res, avisos = [], []
    pa, pn = (antes or {}).get('pagina'), info['pagina']
    desc = lambda p: '%s × %s mm; %d %s de %s mm; caja de texto de %s mm' % (
        mm(p['ancho']), mm(p['alto']), p['columnas'], 'columna' if p['columnas'] == 1 else 'columnas',
        mm(p['ancho_columna']), mm(p['ancho_texto']))
    if not antes:
        res.append('Página: ' + desc(pn) + '   (no había maqueta con la que comparar)')
    elif desc(pa) == desc(pn):
        res.append('Página: sin cambios (%s)' % desc(pn))
    else:
        res.append('Página: CAMBIA\n    antes: %s\n    ahora: %s' % (desc(pa), desc(pn)))
    ma = (antes or {}).get('maestra_inicio'), (antes or {}).get('maestra_interior')
    mn = info['maestra_inicio'], info['maestra_interior']
    txt = 'inicio «%s», interior «%s»' % mn
    if antes and ma != mn:
        res.append('Maestras: CAMBIAN\n    antes: inicio «%s», interior «%s»\n    ahora: %s' % (ma + (txt,)))
    else:
        res.append('Maestras: %s%s' % ('sin cambios (' if antes else '', txt + (')' if antes else '')))
    res.append('Estilos:')
    for clave, nombre in (('parrafo', 'de párrafo'), ('caracter', 'de carácter'), ('objeto', 'de objeto'),
                          ('tabla', 'de tabla'), ('celda', 'de celda')):
        if not antes:
            res.append('    %s: %d' % (nombre, len(info[clave])))
            continue
        nuevos = [e for e in info[clave] if e not in antes[clave]]
        fuera = [e for e in antes[clave] if e not in info[clave]]
        if not nuevos and not fuera:
            res.append('    %s: sin cambios (%d)' % (nombre, len(info[clave])))
            continue
        res.append('    %s: %d (antes %d)' % (nombre, len(info[clave]), len(antes[clave])))
        for etiqueta, lista in (('nuevos', nuevos), ('ya no están', fuera)):
            if lista:
                res.append('        %s: %s' % (etiqueta, ', '.join('«%s»' % e for e in lista[:15]) +
                                                 (' y %d más' % (len(lista) - 15) if len(lista) > 15 else '')))
    falta = comprobar(conf, info)
    if falta:
        avisos.append('Estilos de la configuración que no están en la maqueta nueva (al importar, InDesign '
                      'los crearía vacíos; hay que corregir esas líneas del .toml):\n    ' + '\n    '.join(falta))
    for seccion, clave, medida, que in (('figuras', 'ancho', 'ancho_columna', 'una columna'),
                                        ('tabla', 'ancho', 'ancho_texto', 'la caja de texto')):
        v = conf.get(seccion, {}).get(clave)
        if isinstance(v, (int, float)) and abs(v - pn[medida]) > 1:
            avisos.append('El ancho de %s en la configuración es %s mm y %s de la maqueta nueva mide %s mm '
                          '(no se cambia solo: dime si hay que ajustarlo).' % (
                              'las figuras' if seccion == 'figuras' else 'las tablas', mm(v), que, mm(pn[medida])))
    return res, avisos


def actualizar(toml_ruta, maquetado):
    with open(toml_ruta, 'rb') as f:
        conf = tomllib.load(f)
    maqueta, nueva, pendiente = pendiente_de(conf)
    antes = leer_maqueta(maqueta) if os.path.exists(maqueta) else None
    info = crear_maqueta(maquetado, nueva)
    res, avisos = comparar(conf, antes, info)
    anterior = copia_anterior(maqueta) if antes else ''
    toml_rel = os.path.relpath(toml_ruta, AQUI)
    cab = ['Maquetado de partida: %s' % maquetado]
    if conf.get('maquetado'):
        cab.append('    (el anterior: %s)' % conf['maquetado'])
    cab.append('De sus %d páginas se toman la primera y una de interior.' % info['paginas_maquetado'])
    implica = ['Al guardar:',
               '  · La maqueta nueva sustituye a la actual en:\n      %s' % maqueta]
    if anterior:
        implica.append('  · La actual se guarda como copia en:\n      %s' % anterior)
    implica += ['  · La configuración (%s) no cambia: solo se anota el maquetado nuevo.' % toml_rel,
                '  · Las galeradas ya montadas no cambian: la maqueta nueva se usa desde la próxima importación.']
    informe = '\n'.join(cab + [''] + res + ([''] + ['⚠ ' + a for a in avisos] if avisos else []) + [''] + implica)
    with open(pendiente, 'w', encoding='utf-8') as f:
        json.dump({'toml': toml_ruta, 'maqueta': maqueta, 'nueva': nueva, 'anterior': anterior,
                   'maquetado': maquetado, 'avisos': len(avisos), 'informe': informe}, f, ensure_ascii=False, indent=1)
    print(informe)


def poner_maquetado(toml_ruta, maquetado):
    """Anota el maquetado de partida en la configuración (tras «maqueta = …» si no estaba)."""
    with open(toml_ruta, encoding='utf-8') as f:
        lineas = f.read().split('\n')
    linea = 'maquetado = %s' % cadena(maquetado)
    i = next((n for n, ln in enumerate(lineas) if re.match(r'maquetado\s*=', ln)), None)
    if i is not None:
        lineas[i] = linea
    else:
        i = next(n for n, ln in enumerate(lineas) if re.match(r'maqueta\s*=', ln))
        lineas.insert(i + 1, linea)
    texto = '\n'.join(lineas)
    tomllib.loads(texto)
    with open(toml_ruta, 'w', encoding='utf-8') as f:
        f.write(texto)


def confirmar(toml_ruta):
    with open(toml_ruta, 'rb') as f:
        maqueta, nueva, pendiente = pendiente_de(tomllib.load(f))
    if not os.path.exists(pendiente) or not os.path.exists(nueva):
        sys.exit('No hay ninguna actualización preparada para %s' % os.path.relpath(toml_ruta, AQUI))
    with open(pendiente, encoding='utf-8') as f:
        p = json.load(f)
    if os.path.exists(maqueta):
        anterior = p['anterior'] or copia_anterior(maqueta)
        os.makedirs(os.path.dirname(anterior), exist_ok=True)
        shutil.move(maqueta, anterior)
        print('Maqueta anterior guardada en:\n  %s' % anterior)
    os.replace(nueva, maqueta)
    poner_maquetado(toml_ruta, p['maquetado'])
    os.unlink(pendiente)
    print('Maqueta actualizada:\n  %s\nMaquetado de partida anotado en %s' % (maqueta, os.path.relpath(toml_ruta, AQUI)))


def descartar(toml_ruta):
    with open(toml_ruta, 'rb') as f:
        _, nueva, pendiente = pendiente_de(tomllib.load(f))
    for r in (nueva, pendiente):
        if os.path.exists(r):
            os.unlink(r)
    print('Actualización descartada: la maqueta no ha cambiado.')


def nombre_archivo(nombre):
    s = unicodedata.normalize('NFD', nombre)
    s = ''.join(c for c in s if not unicodedata.combining(c)).lower()
    return re.sub(r'[^0-9a-z]+', '-', s).strip('-')


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('maquetado', nargs='?', help='el último .indd maquetado de la publicación')
    ap.add_argument('--nombre', help='nombre de la publicación nueva («Revista GHHO»)')
    ap.add_argument('--actualizar', metavar='TOML', help='prepara la maqueta de esa publicación desde el maquetado')
    ap.add_argument('--confirmar', metavar='TOML', help='pone en su lugar la maqueta preparada con --actualizar')
    ap.add_argument('--descartar', metavar='TOML', help='borra la maqueta preparada con --actualizar')
    args = ap.parse_args()
    if args.confirmar:
        return confirmar(os.path.abspath(args.confirmar))
    if args.descartar:
        return descartar(os.path.abspath(args.descartar))
    if not args.maquetado or not (args.nombre or args.actualizar):
        ap.error('hace falta el .indd maquetado y --nombre (o --actualizar)')

    maquetado = os.path.abspath(args.maquetado)
    if not maquetado.lower().endswith('.indd') or not os.path.isfile(maquetado):
        sys.exit('No es un .indd: %s' % maquetado)
    if args.actualizar:
        return actualizar(os.path.abspath(args.actualizar), maquetado)
    slug = nombre_archivo(args.nombre)
    if not slug or slug in ('maqueta-base', 'ortotipografia'):
        sys.exit('Elige otro nombre')
    toml_ruta = os.path.join(AQUI, 'publicaciones', slug + '.toml')
    maqueta_rel = os.path.join('publicaciones', 'maquetas', args.nombre + '.indd')
    os.makedirs(os.path.join(AQUI, 'publicaciones', 'maquetas'), exist_ok=True)

    info = crear_maqueta(maquetado, os.path.join(AQUI, maqueta_rel))
    print('Maqueta: %s (de las %d páginas del maquetado: «%s» y «%s»)' % (
        maqueta_rel, info['paginas_maquetado'], info['maestra_inicio'], info['maestra_interior']))

    if os.path.exists(toml_ruta):
        with open(toml_ruta, 'rb') as f:
            conf = tomllib.load(f)
        if conf.get('maqueta') != maqueta_rel:
            sys.exit('La configuración %s apunta a otra maqueta (%s): no la toco' % (toml_ruta, conf.get('maqueta')))
        falta = comprobar(conf, info)
        print('La publicación ya existía: solo se ha rehecho la maqueta. Configuración: publicaciones/%s.toml' % slug)
        if falta:
            print('⚠ Estilos de la configuración que no están en la maqueta nueva:\n  ' + '\n  '.join(falta))
        return

    texto, avisos, con_cabecera, _ = proponer(info, maqueta_rel, maquetado, args.nombre)
    with open(toml_ruta, 'w', encoding='utf-8') as f:
        f.write(texto)
    print('Configuración: publicaciones/%s.toml%s' % (slug, ' (con cabecera de artículo: resumen, abstract…)' if con_cabecera else ''))
    print('Página: %d × %d mm, %d columna(s) de %d mm' % (
        round(info['pagina']['ancho']), round(info['pagina']['alto']), info['pagina']['columnas'],
        round(info['pagina']['ancho_columna'])))
    if avisos:
        print('⚠ Papeles sin estilo en la maqueta (revisar): ' + ', '.join(avisos))


if __name__ == '__main__':
    main()
