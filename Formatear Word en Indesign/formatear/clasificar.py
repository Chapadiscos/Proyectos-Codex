"""Clasificación de los párrafos de un Word en papeles (ladillo, texto, viñeta,
bibliografía, pie de figura...). Solo reglas: lo que no está claro se marca como dudoso.
"""
import re
from dataclasses import dataclass, field, replace

from .docx import Parrafo, Tabla, Trozo

RE_CAPITULO = re.compile(r'^\s*Cap[ií]tulo\s+(\d+)\s*[.:\-–]?\s*(.*)$', re.I | re.S)
RE_AUTORES = re.compile(r'^\s*Autor(?:es|as|a)?\s*:\s*', re.I)
RE_BIBLIO = re.compile(r'^\s*(bibliograf[ií]a|referencias(\s+bibliogr[aá]ficas)?)\s*\.?\s*:?\s*$', re.I)
RE_IDEAS = re.compile(r'^\s*ideas\s+b[aá]sicas', re.I)
RE_MATERIAL = re.compile(r'^\s*((leyendas?|pies?)\s+de\s+(las\s+)?(figuras|im[aá]genes)|figuras(\s+y\s+tablas)?|tablas(\s+y\s+figuras)?)\s*\.?\s*:?\s*$', re.I)
RE_FIGURA = re.compile(r'^\s*Fig(?:ura|s)?\.?\s*(\d+)\s*([A-Za-z])?\b', re.I)
RE_ETIQUETAS = re.compile(r'^\s*(Fig(?:ura)?\.?\s*\d+\s*[A-Za-z]?\s*)+$', re.I)
RE_TABLA = re.compile(r'^\s*Tabla\s+(\d+)', re.I)
RE_TABLA_TITULO = re.compile(r'^\s*Tabla\s+\d+\s*[.:\-–—]', re.I)   # «Tabla 2. …», no «Tabla 2 resume…»
RE_VINETA_FALSA = re.compile(r'^\s*([-–—•·▪]|\.(?=\S))\s*')
RE_NUM_MANUAL = re.compile(r'^\s*(\d{1,3})\s*[.)\-]?\s*')


@dataclass
class Elemento:
    papel: str
    trozos: list = field(default_factory=list)
    nivel: int = 0                      # viñetas: 1..4
    dudas: list = field(default_factory=list)
    notas: list = field(default_factory=list)   # cambios hechos al texto, para el informe
    origen: int = 0                     # nº de párrafo en el Word
    procedencia: str = 'cuerpo'
    tabla: object = None
    imagenes: list = field(default_factory=list)
    datos: dict = field(default_factory=dict)

    @property
    def texto(self):
        return ''.join(t.texto for t in self.trozos)


# ---- utilidades sobre trozos ---------------------------------------------
def _letras(trozos, cond):
    """Proporción de letras que cumplen cond, sin contar lo que va entre paréntesis
    (llamadas a figuras o citas que el autor no puso en negrita)."""
    total = si = prof = 0
    for t in trozos:
        for c in t.texto:
            prof += (c == '(') - (c == ')')
            if c.isalnum() and prof <= 0 and not t.pos:
                total += 1
                si += bool(cond(t))
    return si / total if total else 0.0


def negrita(trozos):
    return _letras(trozos, lambda t: t.b)


def cuerpo_max(trozos):
    return max((t.pt for t in trozos if t.texto.strip()), default=0)


def mayusculas(texto):
    letras = [c for c in texto if c.isalpha()]
    return sum(c.isupper() for c in letras) / len(letras) if letras else 0


def quitar_inicio(trozos, n):
    """Quita los n primeros caracteres de la lista de trozos."""
    res = []
    for t in trozos:
        if n >= len(t.texto):
            n -= len(t.texto)
            continue
        res.append(replace(t, texto=t.texto[n:]) if n else t)
        n = 0
    return res


def limpiar_bordes(trozos):
    """Quita espacios y tabuladores al principio y al final del párrafo."""
    texto = ''.join(t.texto for t in trozos)
    ini = len(texto) - len(texto.lstrip(' \t '))
    trozos = quitar_inicio(trozos, ini)
    while trozos and not trozos[-1].texto.rstrip(' \t '):
        trozos = trozos[:-1]
    if trozos:
        trozos[-1] = replace(trozos[-1], texto=trozos[-1].texto.rstrip(' \t '))
    return trozos, ini


def partir_lineas(trozos):
    """Separa los trozos por saltos de línea manuales (Mayús+Intro en Word)."""
    lineas, actual = [], []
    for t in trozos:
        partes = t.texto.split('\n')
        for k, p in enumerate(partes):
            if k:
                lineas.append(actual)
                actual = []
            if p:
                actual.append(replace(t, texto=p))
    lineas.append(actual)
    return lineas


# ---- clasificación ---------------------------------------------------------
def _tabla_de_figuras(tabla):
    """Tabla de Word usada para colocar figuras: lleva imágenes y pies «Figura N»."""
    ps = [p for fila in tabla.filas for celda in fila for p in celda]
    return any(p.imagenes for p in ps) and any(RE_FIGURA.match(p.texto) for p in ps)


def _expandir_figuras(bloques):
    """Las tablas de figuras se deshacen en sus párrafos, columna a columna (imagen y su pie
    debajo: «imagen 1, Figura 1, imagen 2, Figura 2»), para que salgan como figuras."""
    res = []
    for b in bloques:
        if not (isinstance(b, Tabla) and _tabla_de_figuras(b)):
            res.append(b)
            continue
        for c in range(max(len(f) for f in b.filas)):
            for fila in b.filas:
                for p in (fila[c] if c < len(fila) else []):
                    p.indice = b.indice
                    res.append(p)
    return res


def clasificar(doc, negritas_con_vineta='auto', cabecera='', ladillos_mayusculas=False):
    """Devuelve (elementos, modo): modo es cómo se han tratado las negritas con viñeta.
    cabecera="articulo": el Word empieza con título, autores, resumen… de un artículo de revista.
    ladillos_mayusculas: una línea corta toda en mayúsculas, aunque no vaya en negrita, es ladillo."""
    elementos = []
    zona = 'texto'          # 'texto' | 'ideas' | 'bibliografia' | 'material'
    bloques = _expandir_figuras(doc.bloques)
    hubo_capitulo = False

    def siguiente_es_tabla(k):
        for b in bloques[k + 1:]:
            if isinstance(b, Tabla):
                return True
            if b.texto.strip() or b.imagenes:
                return False
        return False

    for k, b in enumerate(bloques):
        if isinstance(b, Tabla):
            elementos.append(Elemento('tabla', origen=b.indice, procedencia=b.origen, tabla=b))
            continue
        vacio = not b.texto.strip()
        if vacio and not b.imagenes:
            if zona == 'ideas':
                zona = 'texto'
            continue
        if b.imagenes:
            elementos.append(Elemento('imagen', origen=b.indice, procedencia=b.origen,
                                      imagenes=list(b.imagenes)))
            if vacio:
                continue

        lineas = partir_lineas(b.trozos)
        for n_linea, linea in enumerate(lineas):
            linea, sangrado = limpiar_bordes(linea)
            texto = ''.join(t.texto for t in linea)
            if not texto.strip():
                continue
            el = Elemento('texto', linea, origen=b.indice, procedencia=b.origen)
            if n_linea and RE_VINETA_FALSA.match(texto):
                el.notas.append('venía en el párrafo anterior, tras un salto de línea')
            elif n_linea:
                el.dudas.append('venía en el mismo párrafo que el anterior, separado con salto de línea')
            if sangrado and '\t' in ''.join(t.texto for t in b.trozos)[:sangrado + 1]:
                el.notas.append('quitado el sangrado con tabuladores/espacios')
            el.datos['lista'] = b.lista if not n_linea else None
            el.datos['sangria'] = b.sangria
            _papel(el, b, texto, zona, hubo_capitulo, siguiente_es_tabla(k), elementos, ladillos_mayusculas)
            if el.papel == 'capitulo':
                hubo_capitulo = True
            elif el.papel == 'titulo_bibliografia':
                zona = 'bibliografia'
            elif el.papel == 'titulo_ideas':
                zona = 'ideas'
            elif el.papel == 'rotulo_material':
                zona = 'material'
            elif zona == 'bibliografia' and el.papel in ('ladillo1', 'ladillo2', 'ladillo3'):
                zona = 'texto'
            elementos.append(el)

    if cabecera == 'articulo':
        elementos[:] = _cabecera_articulo(elementos)
    _titulos_bajo_tabla(elementos)
    _saltos_sobrantes(elementos)
    _ladillos_en_listas(elementos)
    modo = _negritas_con_vineta(elementos, negritas_con_vineta)
    _niveles_vinetas(elementos, modo)
    _caja_ladillos(elementos)
    return elementos, modo


def _papel(el, b, texto, zona, hubo_capitulo, antes_de_tabla, previos, ladillos_mayusculas=False):
    t = el.trozos
    corto = len(texto) <= 120 and len(texto.split()) <= 16
    neg = negrita(t)
    ult = previos[-1] if previos else None

    if not hubo_capitulo and RE_CAPITULO.match(texto):
        m = RE_CAPITULO.match(texto)
        el.papel = 'capitulo'
        el.datos.update(numero=m.group(1), titulo=m.group(2).strip())
        return
    if RE_AUTORES.match(texto):
        el.papel = 'autores'
        el.trozos = quitar_inicio(t, RE_AUTORES.match(texto).end())
        el.notas.append('quitado «Autores:»')
        return
    if RE_MATERIAL.match(texto):
        el.papel = 'rotulo_material'
        return
    if RE_BIBLIO.match(texto):
        el.papel = 'titulo_bibliografia'
        if texto.rstrip().endswith(('.', ':')):
            el.trozos = _quitar_final(t, 1)
        return
    if RE_IDEAS.match(texto) and corto:
        el.papel = 'titulo_ideas'
        return
    if RE_TABLA.match(texto) and (antes_de_tabla or zona == 'material'):
        el.papel = 'titulo_tabla'
        el.datos['numero'] = RE_TABLA.match(texto).group(1)
        if not antes_de_tabla:
            el.dudas.append('título de tabla sin tabla detrás')
        return
    # Título debajo de la tabla («Tabla 1. …» justo detrás de una tabla que no lo lleva encima):
    # se toma como su título y luego se pasa delante (_titulos_bajo_tabla).
    if ult and ult.papel == 'tabla' and RE_TABLA_TITULO.match(texto) and \
            not (len(previos) > 1 and previos[-2].papel == 'titulo_tabla'):
        el.papel = 'titulo_tabla'
        el.datos['numero'] = RE_TABLA.match(texto).group(1)
        el.datos['bajo_tabla'] = True
        return
    if ult and ult.papel in ('tabla', 'pie_tabla') and (texto.lstrip().startswith('*') or cuerpo_max(t) and cuerpo_max(t) <= 10) \
            and zona == 'material':
        el.papel = 'pie_tabla'
        return
    if RE_ETIQUETAS.match(texto):
        el.papel = 'etiqueta_imagen'
        return
    if RE_FIGURA.match(texto) and (zona == 'material' or (ult and ult.papel in ('imagen', 'pie_figura'))
                                   or b.imagenes or b.origen != 'cuerpo'):
        el.papel = 'pie_figura'
        el.datos['figuras'] = ids_figura(texto)
        return
    if zona == 'material' and ult and ult.papel == 'pie_figura' and not RE_FIGURA.match(texto):
        el.papel = 'pie_figura'
        el.dudas.append('parece continuación del pie anterior')
        return
    if zona == 'bibliografia':
        if not (corto and neg > 0.9):
            el.papel = 'bibliografia'
            m = RE_NUM_MANUAL.match(texto)
            if m and not b.lista:
                el.trozos = quitar_inicio(t, m.end())
                el.notas.append('quitado el número «%s» escrito a mano' % m.group(1))
            return
    if zona == 'ideas':
        el.papel = 'texto_ideas'
        return

    subr = _letras(t, lambda x: x.u)
    cursiva = _letras(t, lambda x: x.i)
    if neg > 0.9 and corto and (subr > 0.5 or cuerpo_max(t) >= 14):
        el.papel = 'ladillo1'
        if mayusculas(texto) > 0.8:
            el.datos['versales'] = True
        return
    if neg > 0.9 and corto and el.datos.get('lista'):
        el.papel = 'negrita_lista'      # ladillo o viñeta: se decide para todo el capítulo
        return
    if neg > 0.9 and corto and texto.rstrip().endswith(':'):
        el.notas.append('frase de entrada en negrita: se deja como texto')
        el.papel = 'texto'
        return
    if neg > 0.9 and corto and not texto.rstrip().endswith('.'):
        el.papel = 'ladillo3' if cursiva > 0.9 else 'ladillo2'
        return
    if neg > 0.9 and corto:
        el.papel = 'ladillo2'
        el.dudas.append('negrita corta acabada en punto: ¿ladillo o texto?')
        return
    if b.lista and el.datos.get('lista'):
        el.papel = 'lista_num' if b.lista[2] not in ('bullet', 'none', '') else 'vineta'
        return
    if RE_VINETA_FALSA.match(texto):
        el.papel = 'vineta'
        el.datos['falsa'] = RE_VINETA_FALSA.match(texto).group(1)
        el.trozos = quitar_inicio(t, RE_VINETA_FALSA.match(texto).end())
        el.notas.append('viñeta escrita a mano «%s» convertida en viñeta' % el.datos['falsa'])
        if el.datos['falsa'] == '.':
            el.dudas.append('párrafo que empieza por punto: ¿viñeta?')
        return
    if ladillos_mayusculas and corto and zona == 'texto' and not b.lista and mayusculas(texto) > 0.9 \
            and len(texto.split()) <= 12 and not texto.rstrip().endswith('.') and sum(c.isalpha() for c in texto) > 3:
        el.papel = 'ladillo1'
        el.notas.append('línea corta en mayúsculas: ladillo')
        return
    if neg > 0.9 and len(texto) > 120:
        el.dudas.append('párrafo largo entero en negrita')
    el.papel = 'texto'


def ids_figura(texto):
    """'Figura 5A. ... 5B: ...' → ['5A', '5B']; 'Figura 4 Algoritmo' → ['4']"""
    m = RE_FIGURA.match(texto)
    num, letra = m.group(1), (m.group(2) or '').upper()
    if letra and not re.match(r'^\s*Fig(?:ura|s)?\.?\s*\d+\s*[A-Za-z]{2,}', texto, re.I):
        ids = [num + letra]
        ids += [num + l.upper() for l in re.findall(r'(?:\b%s|[.;]\s*)([A-Za-z])\s*[:.]' % num, texto[m.end():])
                if num + l.upper() not in ids]
        return ids
    return [num]


# ---- cabecera de un artículo de revista ---------------------------------------
RE_RESUMEN = re.compile(r'^\s*(resumen|abstract|summary)\s*(?:/\s*(abstract|resumen|summary))?\s*([:.])?\s*', re.I)
RE_CLAVE = re.compile(r'^\s*(palabras?[\s-]+claves?|key[\s-]*words?)\s*(?:/\s*(key[\s-]*words?|palabras?[\s-]+claves?))?\s*([:.])?\s*', re.I)
RE_IDIOMA = re.compile(r'^\s*(espa[nñ]ol|castellano|english|ingl[eé]s)\s*:?\s*$', re.I)
RE_TEXTO_ARTICULO = re.compile(r'^\s*texto\s+del\s+art[ií]culo\s*:?\s*$', re.I)
RE_CENTRO = re.compile(r'hospital|universi|cl[ií]nica|instituto|servicio|departament|facultad|centro\b|fundaci[oó]n|'
                       r'especialista|jubilad|correspondencia|correo|e-?mail|@', re.I)
RE_COMUNICACION = re.compile(r'^\s*el presente trabajo|(comunicaci[oó]n|p[oó]ster|ponencia)\b.*\b(presentad|expuest)', re.I)
RE_CONFLICTO = re.compile(r'conflictos?\s+de\s+inter|certifican?\s+que\s+este\s+trabajo|cesi[oó]n\s+de\s+derechos', re.I)
PALABRAS_ES = set('el la de que y en los las del se por con una su para es al lo como más sus fue'.split())
PALABRAS_EN = set('the of and to in is was that with for as by on his this from are an which were its'.split())
MINUSCULAS_NOMBRE = set('y e de del la las los da das do dos van von der di le i'.split())


def ingles(texto):
    pal = re.findall(r'[a-záéíóúüñ]+', texto.lower())
    return sum(p in PALABRAS_EN for p in pal) > sum(p in PALABRAS_ES for p in pal)


def parece_autores(texto):
    """«Pablo Tejada González, Francisco Javier Ascaso Puyuelo¹…»: nombres propios."""
    if RE_CENTRO.search(texto) or len(texto) > 400 or texto.rstrip().endswith('.'):
        return False
    pal = re.findall(r'[^\W\d_]+', texto)
    pal = [p for p in pal if p.lower() not in MINUSCULAS_NOMBRE]
    return bool(pal) and sum(p[0].isupper() for p in pal) / len(pal) > 0.8


def _con_texto(e, papel, texto):
    """Elemento nuevo de la cabecera con un texto fijo («Resumen») y el formato del primer trozo."""
    base = e.trozos[0] if e.trozos else Trozo('')
    return Elemento(papel, [replace(base, texto=texto, b=False, i=False, u=False, pos='', nota=0, duda='')],
                    origen=e.origen, procedencia=e.procedencia)


def _cabecera_articulo(elementos):
    """Título, título en inglés, autores, centro, resumen, abstract y palabras clave del
    principio del artículo, con el orden de la revista (resumen y sus palabras clave; abstract
    y sus keywords). Cada autor lo manda a su manera: «Resumen/abstract:» con los dos idiomas
    seguidos, «Palabras clave/keywords:» con «ESPAÑOL:» e «INGLÉS:»… Las etiquetas del
    formulario («Texto del artículo:») se quitan."""
    titulo, titulo_ing, autores, centro, comunic, otros = [], None, [], [], [], []
    resumen = {'es': [], 'en': []}
    claves = {'es': None, 'en': None}
    fase, modo, idioma_clave, fin = 'titulo', None, None, len(elementos)

    def clave(e, idioma, inicio):
        etiqueta = 'Palabras clave: ' if idioma == 'es' else 'Keywords: '
        n = _con_texto(e, 'palabras_clave', etiqueta)
        n.trozos += limpiar_bordes(quitar_inicio(e.trozos, inicio))[0]
        n.notas = list(e.notas)
        claves[idioma] = n

    k = 0
    while k < len(elementos):
        e = elementos[k]
        t = e.texto.strip()
        if e.papel in ('imagen', 'tabla', 'etiqueta_imagen', 'pie_figura', 'titulo_tabla', 'pie_tabla'):
            otros.append(e)
            k += 1
            continue
        if RE_TEXTO_ARTICULO.match(t):
            fin = k + 1
            break
        m = RE_RESUMEN.match(t)
        if m and (m.end() == len(t) or m.group(3)):
            dos = m.group(2)
            modo = 'mixto' if dos else ('es' if m.group(1).lower() == 'resumen' else 'en')
            fase = 'resumen'
            resto = t[m.end():].strip()
            if resto:
                e = replace(e, trozos=limpiar_bordes(quitar_inicio(e.trozos, len(e.texto) - len(e.texto.lstrip()) + m.end()))[0])
                resumen['en' if (modo == 'en' or (modo == 'mixto' and ingles(resto))) else 'es'].append(e)
            k += 1
            continue
        m = RE_CLAVE.match(t)
        if m and (m.end() == len(t) or m.group(3)):
            resto = t[m.end():].strip()
            fase = 'claves'
            if m.group(2) and not resto:
                idioma_clave = 'mixto'
            else:
                idioma = 'en' if m.group(1).lower().startswith('key') else 'es'
                if resto:
                    clave(e, idioma, len(e.texto) - len(e.texto.lstrip()) + m.end())
                idioma_clave = idioma
            k += 1
            continue
        if fase == 'claves' and RE_IDIOMA.match(t):
            idioma_clave = 'en' if RE_IDIOMA.match(t).group(1).lower().startswith(('en', 'ing')) else 'es'
            k += 1
            continue
        if fase == 'claves' and idioma_clave and e.papel == 'texto' and len(t) < 400 \
                and (idioma_clave != 'mixto' or None in claves.values()):
            idioma = idioma_clave if idioma_clave != 'mixto' else ('es' if claves['es'] is None else 'en')
            if claves[idioma] is None:
                clave(e, idioma, 0)
                k += 1
                continue
        if fase in ('resumen', 'claves') and e.papel == 'texto' and modo and fase == 'resumen':
            resumen['en' if (modo == 'en' or (modo == 'mixto' and ingles(t))) else 'es'].append(e)
            k += 1
            continue
        if fase in ('resumen', 'claves'):
            fin = k
            break
        # Antes del resumen: títulos y datos del artículo.
        if RE_CONFLICTO.search(t):
            e.dudas.append('conflicto de intereses / originalidad: ¿va en la revista?')
            otros.append(e)
        elif RE_COMUNICACION.search(t):
            comunic.append(e)
        elif fase == 'titulo' and titulo and titulo_ing is None and not autores and ingles(t):
            titulo_ing = e
        elif e.papel == 'autores' or (fase != 'titulo' or titulo) and not autores and parece_autores(t):
            autores.append(e)
            fase = 'datos'
        elif titulo and (RE_CENTRO.search(t) or re.match(r'^\s*\d', t) or (e.trozos and e.trozos[0].pos == 'sup')):
            centro.append(e)
            fase = 'datos'
        elif fase == 'titulo' and not titulo:
            titulo.append(e)
        elif fase == 'titulo' and titulo_ing is None and e.papel.startswith('ladillo'):
            titulo.append(e)            # título partido en varias líneas
        elif len(t) > 300 or e.papel.startswith('ladillo') or fase == 'datos' and not autores:
            fin = k                     # sin resumen: ya es el texto
            break
        else:
            e.dudas.append('al principio del artículo, entre el título y el texto: ¿qué es?')
            otros.append(e)
        k += 1
    else:
        fin = len(elementos)

    if not titulo:
        return elementos
    res = []
    t0 = titulo[0]
    trozos = []
    for n, e in enumerate(titulo):
        if n:
            trozos.append(replace(e.trozos[0], texto=' '))
        trozos += e.trozos
    res.append(Elemento('titulo', trozos, origen=t0.origen, procedencia=t0.procedencia,
                        notas=['título del artículo'] + (['juntadas %d líneas' % len(titulo)] if len(titulo) > 1 else [])))
    if titulo_ing is not None:
        titulo_ing.papel = 'titulo_ing'
        res.append(titulo_ing)
    for e in autores:
        e.papel = 'autores'
    for e in centro:
        e.papel = 'centro'
    for e in comunic:
        e.papel = 'comunicacion'
    res += autores + centro + comunic
    for idioma, rotulo in (('es', 'Resumen'), ('en', 'Abstract')):
        if resumen[idioma]:
            ref = resumen[idioma][0]
            res.append(_con_texto(ref, 'titulo_resumen', rotulo))
            for e in resumen[idioma]:
                e.papel = 'resumen' if idioma == 'es' else 'abstract'
                e.dudas = [d for d in e.dudas if not d.startswith('parece continuación')]
            res += resumen[idioma]
        if claves[idioma] is not None:
            res.append(claves[idioma])
    res += otros
    cuerpo = elementos[fin:]
    nombre_titulo = re.sub(r'\W+', ' ', res[0].texto).strip().lower()
    for e in cuerpo[:3]:
        if e.papel.startswith('ladillo') and re.sub(r'\W+', ' ', e.texto).strip().lower() == nombre_titulo:
            e.dudas.append('repite el título del artículo: ¿quitar?')
    if (resumen['es'] or resumen['en']) and cuerpo and cuerpo[0].papel == 'texto':
        cuerpo[0].papel = 'primer_texto'
    return res + cuerpo


def _titulos_bajo_tabla(elementos):
    """El título que venía debajo de su tabla pasa delante, como los demás."""
    for k, e in enumerate(elementos):
        if e.datos.get('bajo_tabla') and k and elementos[k - 1].papel == 'tabla':
            elementos[k - 1], elementos[k] = e, elementos[k - 1]
            e.notas.append('el título venía debajo de la tabla')


def _saltos_sobrantes(elementos):
    """Párrafo que empieza en minúscula o con «)» tras otro que no acaba en punto:
    seguramente el autor metió un Intro de más."""
    for previo, e in zip(elementos, elementos[1:]):
        if e.papel != 'texto' or previo.papel not in ('texto', 'vineta', 'lista_num'):
            continue
        ini, fin = e.texto.lstrip()[:1], previo.texto.rstrip()[-1:]
        if (ini.islower() or ini in '),;') and fin not in '.:!?':
            e.dudas.append('parece continuación del párrafo anterior: ¿salto de párrafo sobrante?')


def _ladillos_en_listas(elementos):
    """Una negrita corta con viñeta seguida de un hermano de la misma lista (misma
    sangría) es un elemento más de la lista, no un encabezado."""
    def clave(e):
        l = e.datos.get('lista')
        return (l[0], e.datos.get('sangria')) if l else None

    hermanas = set()
    for k, e in enumerate(elementos):
        if e.papel != 'negrita_lista':
            continue
        vecinos = (elementos[k - 1] if k else None, elementos[k + 1] if k + 1 < len(elementos) else None)
        if any(x is not None and x.papel in ('negrita_lista', 'vineta', 'lista_num') and clave(x) == clave(e)
               for x in vecinos):
            hermanas.add(k)
    for k in hermanas:
        e = elementos[k]
        e.papel = 'lista_num' if e.datos['lista'][2] not in ('bullet', 'none', '') else 'vineta'


SIMBOLO_NIVEL = {'\uf0b7': 0, '•': 0, '·': 0, 'o': 1, '◦': 1, '\uf0a7': 2, '▪': 2, '§': 2}


def _negritas_con_vineta(elementos, modo):
    """Negritas cortas que en Word llevan viñeta: según el capítulo son ladillos (si
    detrás suele ir texto corrido) o viñetas en negrita (si detrás suelen ir viñetas).
    Con modo 'auto' se decide por mayoría; 'ladillo' o 'vineta' lo fuerzan."""
    candidatas = [k for k, e in enumerate(elementos) if e.papel == 'negrita_lista']
    if not candidatas:
        return None
    if modo == 'auto':
        texto = lista = 0
        for k in candidatas:
            sig = elementos[k + 1].papel if k + 1 < len(elementos) else ''
            texto += sig == 'texto'
            lista += sig in ('vineta', 'lista_num', 'negrita_lista')
        modo = 'ladillo' if texto > lista else 'vineta'

    if modo == 'ladillo':
        def rango(e):
            simbolo = e.datos['lista'][3] if len(e.datos['lista']) > 3 else ''
            return (SIMBOLO_NIVEL.get(simbolo, 0), e.datos.get('sangria') or 0)
        rangos = sorted({rango(elementos[k]) for k in candidatas})
        for k in candidatas:
            e = elementos[k]
            e.papel = 'ladillo2' if rango(e) == rangos[0] else 'ladillo3'
            e.notas.append('en Word llevaba viñeta')
            fin = e.texto.rstrip()
            if fin.endswith(':') or (fin.endswith('.') and not fin.endswith('..')):
                e.trozos = _quitar_final(e.trozos, 1)
                e.notas.append('quitado «%s» final' % fin[-1])
        return modo

    seccion = None      # encabezado (viñeta en negrita) de la sección abierta
    for e in elementos:
        if e.papel == 'negrita_lista':
            e.papel = 'vineta'
            e.datos['encabezado'] = True
            seccion = e
        elif seccion is not None and e.papel == 'ladillo2' and not e.datos.get('lista') \
                and any(d.startswith('negrita corta acabada en punto') for d in e.dudas):
            # «Candida spp.» dentro de una sección de viñetas: subencabezado de la sección.
            e.papel = 'vineta'
            e.datos['encabezado'] = True
            e.datos['sangria'] = (seccion.datos.get('sangria') or 0) + 100
            e.datos['lista'] = ('sub%d' % id(seccion), 0)
            e.dudas = [d for d in e.dudas if not d.startswith('negrita corta acabada en punto')]
            e.notas.append('negrita corta dentro de una sección de viñetas: subencabezado')
        elif e.papel in ('ladillo1', 'ladillo2', 'ladillo3', 'titulo_bibliografia', 'titulo_ideas', 'rotulo_material'):
            seccion = None
        elif e.papel == 'texto' and seccion is not None and not any(n.startswith('frase de entrada') for n in e.notas):
            e.papel = 'texto_vineta'
    return modo


def _quitar_final(trozos, n):
    """Quita los n últimos caracteres visibles (sin contar espacios finales)."""
    trozos, _ = limpiar_bordes(trozos)
    while n and trozos:
        t = trozos[-1]
        corte = min(n, len(t.texto))
        trozos[-1] = replace(t, texto=t.texto[:-corte])
        n -= corte
        if not trozos[-1].texto:
            trozos.pop()
    return limpiar_bordes(trozos)[0]


def _caja_ladillos(elementos):
    """Ladillos y título escritos en mayúsculas → minúsculas con inicial mayúscula;
    la caja la pone el estilo. Se respetan las siglas que el texto usa en mayúsculas."""
    siglas, propios = set(), {}
    for e in elementos:
        if e.papel in ('texto', 'vineta', 'lista_num', 'texto_vineta', 'texto_ideas', 'primer_texto', 'resumen'):
            siglas.update(re.findall(r'\b[A-ZÁÉÍÓÚÜÑ]{2,}\b', e.texto))
            # Nombres propios: con mayúscula inicial en mitad de una frase («de Córdoba»).
            for m in re.finditer(r'(?<=[\w,;)»”] )([A-ZÁÉÍÓÚÜÑ][a-záéíóúüñ]+)\b|(?<=-)([A-ZÁÉÍÓÚÜÑ][a-záéíóúüñ]+)\b', e.texto):
                pal = m.group(1) or m.group(2)
                propios.setdefault(pal.lower(), pal)

    def frase(texto, primero):
        res = []
        for m in re.finditer(r'\w+|\W+', texto):
            pal = m.group(0)
            if pal in siglas or pal in ('Figura', 'Figuras', 'Tabla', 'Tablas') or not pal[0].isalpha():
                res.append(pal)
            elif pal.lower() in propios:
                res.append(propios[pal.lower()])
            elif primero:
                res.append(pal[0].upper() + pal[1:].lower())
            else:
                res.append(pal.lower())
            if pal[0].isalpha():
                primero = False
        return ''.join(res)

    for e in elementos:
        if e.papel == 'capitulo' and mayusculas(e.datos['titulo']) > 0.8:
            e.datos['titulo'] = frase(e.datos['titulo'], True)
        if e.papel not in ('ladillo1', 'ladillo2', 'ladillo3', 'titulo_bibliografia', 'titulo', 'titulo_ing') \
                or mayusculas(e.texto) <= 0.6:
            continue
        nuevos, primero = [], True
        for t in e.trozos:
            nuevos.append(replace(t, texto=frase(t.texto, primero)))
            if any(c.isalpha() for c in t.texto):
                primero = False
        e.trozos = nuevos
        e.datos.pop('versales', None)
        if e.papel in ('titulo', 'titulo_ing'):
            e.dudas.append('título en mayúsculas pasado a minúsculas: revisa los nombres propios')
        else:
            e.notas.append('pasado a minúsculas: la caja la pone el estilo')


CORTAN_LISTA = ('ladillo1', 'ladillo2', 'ladillo3', 'titulo_bibliografia', 'bibliografia', 'titulo_ideas',
                'texto_ideas', 'titulo_tabla', 'tabla', 'pie_tabla', 'pie_figura', 'imagen', 'rotulo_material',
                'etiqueta_imagen', 'capitulo', 'autores', 'titulo', 'titulo_ing', 'centro', 'comunicacion',
                'titulo_resumen', 'resumen', 'abstract', 'palabras_clave')


def _niveles_vinetas(elementos, modo):
    """Nivel 1..4 de cada viñeta, como en un esquema: baja un nivel si tiene más sangría
    que la anterior y sube hasta la que tenga su misma sangría. Un ladillo reinicia; el
    texto corrido entre viñetas no. Las viñetas escritas a mano cuelgan de la anterior."""
    pila, previo, sangria_encabezado = [], None, {}
    for e in elementos:
        if e.papel in CORTAN_LISTA:
            pila, previo, sangria_encabezado = [], None, {}
            continue
        if e.papel in ('texto', 'texto_vineta'):
            # En secciones de viñetas, un párrafo sin viñeta pero sangrado como ellas es
            # una viñeta a la que el autor no puso símbolo.
            sangria = e.datos.get('sangria') or 0
            if modo == 'vineta' and previo is not None and sangria > 0 and negrita(e.trozos) < 0.9 \
                    and sangria >= (previo.datos.get('sangria') or 0):
                e.papel = 'vineta'
                e.datos['falsa'] = 'sangrado'
                e.notas.append('párrafo sangrado sin viñeta: se trata como viñeta')
            else:
                continue
        if e.papel not in ('vineta', 'lista_num'):
            continue
        if e.datos.get('falsa'):
            if previo is None:
                e.nivel = 1
            else:
                e.nivel = previo.nivel + (0 if previo.datos.get('falsa') else 1)
            e.nivel = min(max(e.nivel, 1), 4)
            previo = e
            continue
        lista = e.datos.get('lista') or (None, 0)
        sangria = round((e.datos.get('sangria') or 0) / 45) * 45     # 1068 ≈ 1080
        if lista[0] in sangria_encabezado and not e.datos.get('encabezado'):
            sangria = sangria_encabezado[lista[0]]   # «Otros (…)»: hermano de los encabezados de su lista
        elif e.datos.get('encabezado'):
            # El encabezado queda justo por encima de sus hijas aunque tengan su misma sangría.
            sangria -= 1
            if lista[0]:
                sangria_encabezado[lista[0]] = sangria
            if previo is not None and not previo.datos.get('encabezado'):
                # Tras las viñetas de otra sección: se pone al nivel del encabezado anterior
                # de su misma lista; si no lo hay, solo se anida si está claramente más sangrado.
                while pila and not pila[-1][2]:
                    pila.pop()
                if any(x[3] == lista[0] for x in pila):
                    while pila[-1][3] != lista[0]:
                        pila.pop()
                    sangria = pila[-1][0]
                else:
                    while pila and pila[-1][0] + 360 > sangria:
                        pila.pop()
        clave = (sangria, lista[1], bool(e.datos.get('encabezado')), lista[0])
        while pila and pila[-1][:2] > clave[:2]:
            pila.pop()
        if not pila or pila[-1][:2] < clave[:2]:
            pila.append(clave)
        e.nivel = min(len(pila), 4)
        previo = e
