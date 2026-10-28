"""Inventario de figuras: pies encontrados en el Word frente a los archivos de imagen
sueltos de la carpeta del capítulo (se prefieren a los incrustados en el .docx)."""
import os
import re
import unicodedata

EXTENSIONES = ('.jpg', '.jpeg', '.png', '.tif', '.tiff', '.psd', '.eps', '.ai', '.pdf')
RE_ARCHIVO = re.compile(r'fig(?:ura)?\s*\.?\s*(\d+)\s*([a-z])?(?![a-z])', re.I)


def archivos_imagen(carpeta):
    return sorted(f for f in os.listdir(carpeta)
                  if f.lower().endswith(EXTENSIONES) and not f.startswith('.'))


def id_archivo(nombre):
    base = os.path.splitext(nombre)[0]
    m = RE_ARCHIVO.search(base)
    if m:
        return m.group(1) + (m.group(2) or '').upper()
    if 'algoritmo' in base.lower():
        return 'algoritmo'
    return None


def indice_archivos(carpeta):
    por_id = {}
    for f in archivos_imagen(carpeta):
        por_id.setdefault(id_archivo(f), []).append(f)
    return por_id


def buscar_archivos(fid, texto_pie, por_id):
    """Archivos sueltos para la figura fid ('5A', '4'...) y aviso, si lo hay."""
    num = re.match(r'\d+', fid).group(0)
    encontrados, aviso = por_id.get(fid, []), ''
    if not encontrados and fid != num:
        encontrados = por_id.get(num, [])
        aviso = 'no hay archivo %s; uso el de la figura %s' % (fid, num) if encontrados else ''
    if not encontrados and fid == num:
        encontrados = [f for k, fs in por_id.items() if k and k[:-1] == num and k[-1].isalpha() for f in fs]
    if not encontrados and 'algoritmo' in texto_pie.lower():
        encontrados = por_id.get('algoritmo', [])
    if not encontrados:
        aviso = 'sin archivo suelto: se usará la imagen incrustada en el Word'
    elif len(encontrados) > 1:
        aviso = aviso or '%d archivos para una figura: ¿compuesta o hay que elegir?' % len(encontrados)
    return encontrados, aviso


# Palabras del nombre de archivo que no sirven para reconocerlo en el texto.
VACIAS = {'figura', 'fig', 'imagen', 'img', 'foto', 'jpg', 'del', 'las', 'los', 'con', 'por', 'para'}


def _palabras(texto):
    s = unicodedata.normalize('NFD', texto)
    s = ''.join(c for c in s if not unicodedata.combining(c)).lower()
    return re.findall(r'[a-z]+', s)


def _serie(nombre):
    """«Ventana 2.jpg» → «ventana»: archivos numerados de una misma figura."""
    base = os.path.splitext(nombre)[0]
    return re.sub(r'[\s_-]*\d+$', '', base).lower() if re.search(r'\d+$', base) else None


def por_nombre(libres, textos):
    """Archivos sueltos sin «Figura N» en el nombre para una imagen sin número: el primero de
    los textos (el pie, el párrafo de antes, el de después) en el que salga alguna palabra del
    nombre («Mario Padre.jpg» ↔ «Mario padre y Mario hijo»; «Ventana 1.jpg» ↔ «ventanal»).
    Gana el nombre con más palabras encontradas y, a igualdad, el que sale antes en el texto.
    Si es de una serie («Ventana 1», «Ventana 2»…), van todos. Devuelve (archivos, empate)."""
    for texto in textos:
        palabras = _palabras(texto or '')
        puntos = []
        for f in libres:
            nombre = [w for w in _palabras(os.path.splitext(f)[0]) if len(w) >= 3 and w not in VACIAS]
            pos = [next((i for i, p in enumerate(palabras) if p.startswith(w)), None) for w in nombre]
            hechas = [i for i in pos if i is not None]
            if hechas:
                puntos.append(((len(hechas) / len(nombre), len(hechas), -min(hechas)), f))
        if not puntos:
            continue
        mejor = max(c for c, _ in puntos)
        elegidos = [f for c, f in puntos if c == mejor]
        serie = _serie(elegidos[0])
        if serie:
            return sorted((f for f in libres if _serie(f) == serie), key=lambda f: int(re.search(r'(\d+)\.\w+$', f).group(1))), False
        return elegidos[:1], len(elegidos) > 1
    return [], False


def inventario(elementos, carpeta):
    """Lista de (figura, pie, archivos, aviso) y archivos sin pie."""
    archivos = archivos_imagen(carpeta)
    por_id = indice_archivos(carpeta)
    usados, filas = set(), []
    for e in elementos:
        if e.papel != 'pie_figura' or 'figuras' not in e.datos:
            continue
        for fid in e.datos['figuras']:
            encontrados, aviso = buscar_archivos(fid, e.texto, por_id)
            usados.update(encontrados)
            filas.append((fid, e.texto, encontrados, aviso))
    sobrantes = [f for f in archivos if f not in usados]
    # Imágenes incrustadas sin un pie pegado (ni delante ni detrás).
    for k, e in enumerate(elementos):
        vecinos = [x.papel for x in elementos[max(k - 1, 0):k + 2] if x is not e]
        if e.papel == 'imagen' and 'pie_figura' not in vecinos and 'etiqueta_imagen' not in vecinos:
            filas.append(('¿?', '(imagen incrustada sin pie, párrafo %d del Word)' % e.origen, [],
                          'sin pie: ¿algoritmo u otra figura? Archivos sin pie: %s' % (', '.join(sobrantes) or 'ninguno')))
    return filas, sobrantes
