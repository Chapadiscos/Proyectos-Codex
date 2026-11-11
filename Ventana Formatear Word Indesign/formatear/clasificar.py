"""Clasificación de los párrafos de un Word en papeles (ladillo, texto, viñeta,
bibliografía, pie de figura...). Solo reglas: lo que no está claro se marca como dudoso.
"""
import re
from dataclasses import dataclass, field, replace

from .docx import Parrafo, Tabla, Trozo

RE_CAPITULO = re.compile(r'^\s*Cap[ií]tulo\s+(\d+)\s*[.:\-–]?\s*(.*)$', re.I | re.S)
RE_AUTORES = re.compile(r'^\s*Autor(?:es|as|a)?\s*:\s*', re.I)
# También con el número del ladillo escrito delante: «5. BIBLIOGRAFÍA»
RE_BIBLIO = re.compile(r'^\s*(?:\d+(?:\.\d+)*\.?\s+)?(bibliograf[ií]a(\s+recomendada|\s+de\s+consulta)?|referencias?(\s+bibliogr[aá]ficas?)?)\s*\.?\s*:?\s*$', re.I)
RE_IDEAS = re.compile(r'^\s*ideas\s+b[aá]sicas', re.I)
RE_MATERIAL = re.compile(r'^\s*((leyendas?|pies?)(\s+de\s+(las\s+)?(figuras?|im[aá]genes))?|figuras(\s+y\s+tablas)?|tablas(\s+y\s+figuras)?)\s*\.?\s*:?\s*$', re.I)
RE_FIGURA = re.compile(r'^\s*Fig(?:ura|s)?\.?\s*(\d+(?:\.\d+)*)\s*([A-Za-z])?\b', re.I)   # «Figura 3», «Figura 16.10A»
RE_ETIQUETAS = re.compile(r'^\s*(Fig(?:ura)?\.?\s*\d+(?:\.\d+)*\s*[A-Za-z]?\s*)+$', re.I)
RE_TABLA = re.compile(r'^\s*Tabla\s+(\d+(?:\.\d+)*)', re.I)   # «Tabla 4», «Tabla 16.1»
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


def clasificar(doc, negritas_con_vineta='auto', cabecera='', ladillos_mayusculas=False,
               ladillos_estilo_word=False, ladillos_numerados=False, quitar_filiaciones=True,
               capitulo_a_titulo=False, ladillos_sin_numero=False, casos_por_columnas=False):
    """Devuelve (elementos, modo): modo es cómo se han tratado las negritas con viñeta.
    cabecera="articulo": el Word empieza con título, autores, resumen… de un artículo de revista.
    ladillos_mayusculas: una línea corta toda en mayúsculas, aunque no vaya en negrita, es ladillo.
    ladillos_estilo_word: los párrafos con estilo «Título 2/3/4» de Word son ladillos 1/2/3
    aunque no vayan en negrita; ladillos_numerados: con su número de Word («1. Indicación»).
    quitar_filiaciones: de los autores solo quedan nombres y apellidos (sin llamadas voladas ni
    centro de trabajo, ni los párrafos de filiación de debajo).
    capitulo_a_titulo: «CAPÍTULO 15» (con o sin el título detrás) no va en el texto: el título
    del capítulo es el suyo o el párrafo siguiente, y los autores el de después.
    ladillos_sin_numero: los ladillos numerados a mano («3.1 INTRODUCCIÓN», «1.- …») van sin el
    número y con el nivel que dice («3.1» ladillo 1 y «3.1.1» ladillo 2 si todos empiezan por el
    número del capítulo; si no, «1.-» ladillo 1 y «1.1» ladillo 2).
    casos_por_columnas: en un Word con secciones de dos columnas (el texto), lo que va a una
    columna con título propio, imagen y texto es un caso clínico (titulo_caso, texto_caso)."""
    elementos = []
    zona = 'texto'          # 'texto' | 'ideas' | 'bibliografia' | 'material'
    bloques = _expandir_figuras(doc.bloques)
    hubo_capitulo = False
    contadores = {}         # numId → {nivel: cuenta}, para el número que pone Word a cada párrafo
    titulo_word, rango_titulos = _titulos_word(bloques) if ladillos_estilo_word else (None, {})

    def siguiente_es_tabla(k):
        for b in bloques[k + 1:]:
            if isinstance(b, Tabla):
                return True
            if b.texto.strip() or b.imagenes:
                return False
        return False

    for k, b in enumerate(bloques):
        if isinstance(b, Tabla):
            elementos.append(Elemento('tabla', origen=b.indice, procedencia=b.origen, tabla=b,
                                      datos={'columnas': getattr(b, 'columnas', 0)}))
            continue
        vacio = not b.texto.strip()
        if vacio and not b.imagenes:
            if zona == 'ideas':
                zona = 'texto'
            continue
        if b.imagenes:
            elementos.append(Elemento('imagen', origen=b.indice, procedencia=b.origen,
                                      imagenes=list(b.imagenes), datos={'columnas': b.columnas}))
            if vacio:
                continue

        lineas = partir_lineas(b.trozos)
        for n_linea, linea in enumerate(lineas):
            linea, sangrado = limpiar_bordes(linea)
            texto = ''.join(t.texto for t in linea)
            if not texto.strip():
                continue
            el = Elemento('texto', linea, origen=b.indice, procedencia=b.origen)
            el.datos['columnas'] = b.columnas
            if n_linea and RE_VINETA_FALSA.match(texto):
                el.notas.append('venía en el párrafo anterior, tras un salto de línea')
            elif n_linea:
                el.dudas.append('venía en el mismo párrafo que el anterior, separado con salto de línea')
            if sangrado and '\t' in ''.join(t.texto for t in b.trozos)[:sangrado + 1]:
                el.notas.append('quitado el sangrado con tabuladores/espacios')
            el.datos['lista'] = b.lista if not n_linea else None
            el.datos['sangria'] = b.sangria
            if b.lista and not n_linea:
                el.datos['etiqueta_word'] = _etiqueta_word(b.lista, contadores)
            # Estilos de título de Word: el del capítulo, o el nivel de ladillo que le toca
            if b is titulo_word and not n_linea:
                el.datos['titulo_word'] = True
            el.datos['nivel_titulo'] = rango_titulos.get(_nivel_titulo(b.estilo_word), 0)
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
            if 'detras' in el.datos:            # p. ej. los autores que venían con el título
                elementos.append(el.datos.pop('detras'))

    if cabecera == 'articulo':
        elementos[:] = _cabecera_articulo(elementos)
    _notas_de_maquetacion(elementos)
    if capitulo_a_titulo:
        _capitulo_a_titulo(elementos)
    if ladillos_sin_numero:
        _ladillos_sin_numero(elementos)
    if quitar_filiaciones:
        _quitar_filiaciones(elementos)
    _titulo_capitulo(elementos)
    if casos_por_columnas:
        _casos_por_columnas(elementos)
    _pies_sin_rotulo(elementos)
    _titulos_bajo_tabla(elementos)
    _saltos_sobrantes(elementos)
    if ladillos_numerados:
        _ladillos_de_su_lista(elementos)
    _ladillos_en_listas(elementos)
    modo = _negritas_con_vineta(elementos, negritas_con_vineta)
    _caja_ladillos(elementos)
    if ladillos_numerados:
        _numerar_ladillos(elementos)
    _numeradas_a_mano(elementos)
    _niveles_vinetas(elementos, modo)
    _ladillos_sin_signo_final(elementos)
    return elementos, modo


def _es_title(estilo):
    """Estilo «Title» / «Título» (sin número) de Word: el título del documento."""
    return bool(re.match(r'^\s*(title|t[ií]tulo)\s*$', estilo or '', re.I))


RE_NOTA_MAQUETA = re.compile(r'(?i)\bc[oó]digos?\s+QR\b|\bal\s+maquetar\b|\bespacio\s+para\b')


def _notas_de_maquetacion(elementos):
    """Notas del autor para quien maqueta («ESPACIO PARA EL CÓDIGO QR DEL VIDEO 3.2», «AL MAQUETAR
    HAY QUE DEJAR…»): no son ladillos; se quedan como texto con una duda (norma para todas)."""
    for e in elementos:
        if e.papel in ('ladillo1', 'ladillo2', 'ladillo3', 'texto') and RE_NOTA_MAQUETA.search(e.texto) \
                and (mayusculas(e.texto) > 0.5 or e.papel != 'texto'):
            e.papel = 'texto'
            e.datos['nota_maqueta'] = True
            e.dudas.append('nota del autor para la maquetación: ¿qué hay que poner aquí?')


def _capitulo_a_titulo(elementos):
    """«CAPÍTULO 3.- TÉCNICA GONIOSCÓPICA» → título «TÉCNICA GONIOSCÓPICA»; «CAPÍTULO 15» solo →
    el título es el párrafo siguiente. Detrás, un párrafo de nombres propios son los autores."""
    k = next((i for i, e in enumerate(elementos[:4]) if e.papel == 'capitulo'), None)
    if k is None:
        return
    cap = elementos[k]
    resto = re.sub(r'^[\s.:\-–—]+', '', cap.datos.get('titulo', ''))
    if resto:
        m = re.search(re.escape(resto[:20]), cap.texto)
        cap.trozos = limpiar_bordes(quitar_inicio(cap.trozos, m.start() if m else len(cap.texto) - len(resto)))[0]
        numero = cap.datos.get('numero', '')
        cap.papel = 'titulo'
        cap.datos = {}
        cap.notas.append('«Capítulo %s» quitado: el número lo pone el libro' % numero)
        sig = k + 1
    else:
        del elementos[k]
        sig = next((i for i in range(k, min(k + 3, len(elementos))) if elementos[i].texto.strip()), None)
        if sig is None:
            return
        t = elementos[sig]
        t.papel = 'titulo'
        t.datos.pop('versales', None)
        t.notas.append('párrafo detrás de «CAPÍTULO N»: título del capítulo')
        if t.texto.rstrip().endswith('.'):
            t.trozos = _quitar_final(t.trozos, 1)
        sig += 1
    if sig < len(elementos) and elementos[sig].papel != 'autores' and parece_autores(elementos[sig].texto) \
            and not RE_LADILLO_NUM.match(elementos[sig].texto) and not elementos[sig].papel.startswith('ladillo') \
            and negrita(elementos[sig].trozos) < 0.9:
        elementos[sig].papel = 'autores'
        elementos[sig].notas.append('nombres detrás del título: autores')


RE_LADILLO_NUM = re.compile(r'^\s*(\d+(?:\.\d+)*)\.?\s*(?:[-–—)]\s*)?(?=[^\W\d_])')


def _ladillos_sin_numero(elementos):
    """Ladillos con el número escrito a mano: fuera el número y nivel según el número. También
    las negritas cortas numeradas que se habían quedado como texto («3.3 … PASOS A SEGUIR:»)."""
    cands = []
    for e in elementos:
        m = RE_LADILLO_NUM.match(e.texto)
        if not m:
            continue
        lad = e.papel in ('ladillo1', 'ladillo2', 'ladillo3')
        entrada = e.papel == 'texto' and negrita(e.trozos) > 0.9 and len(e.texto) <= 160 \
            and not e.datos.get('nota_maqueta')
        if lad or entrada:
            cands.append((e, m))
    if not cands:
        return
    partes = [m.group(1).split('.') for _, m in cands]
    base = 1 if all(len(p) >= 2 for p in partes) and len({p[0] for p in partes}) == 1 else 0
    for e, m in cands:
        nivel = min(max(len(m.group(1).split('.')) - base, 1), 3)
        e.papel = 'ladillo%d' % nivel
        e.trozos = limpiar_bordes(quitar_inicio(e.trozos, m.end()))[0]
        e.notas = [n for n in e.notas if not n.startswith('frase de entrada')]
        e.notas.append('número «%s» quitado: ladillo %d' % (m.group(1), nivel))


def _casos_por_columnas(elementos):
    """Casos clínicos marcados por el autor con secciones de Word: el texto va a dos columnas y
    el caso, a una. Un título a una columna seguido de imagen, pie o texto a una columna es el
    título del caso; si detrás viene texto a dos columnas, es un ladillo. El texto a una columna
    (después del primer texto a dos) es texto del caso, y los pies de figura llevan su estilo."""
    if not any(e.datos.get('columnas') == 2 for e in elementos):
        return
    inicio = next(i for i, e in enumerate(elementos) if e.datos.get('columnas') == 2)
    titulos = ('ladillo1', 'ladillo2', 'ladillo3', 'texto')
    for k in range(inicio, len(elementos)):
        e = elementos[k]
        if e.datos.get('columnas') != 1:
            continue
        sig = next((x for x in elementos[k + 1:] if x.papel == 'imagen' or x.texto.strip()), None)
        if e.papel in titulos and (e.papel != 'texto' or negrita(e.trozos) > 0.9) and len(e.texto) <= 120 \
                and (e.papel != 'texto' or not e.texto.rstrip().endswith('.')):
            if sig is not None and sig.datos.get('columnas') == 1 and sig.papel in ('imagen', 'pie_figura', 'texto', 'etiqueta_imagen'):
                e.papel = 'titulo_caso'
                e.notas.append('a una columna en el Word, con imagen o texto detrás: título de caso clínico')
                continue
        if e.papel in ('texto', 'primer_texto', 'vineta', 'lista_num'):
            e.papel = 'texto_caso'
            e.nivel = 0
            e.notas.append('a una columna en el Word: texto de caso clínico')
        elif e.papel == 'pie_figura':
            e.datos['caso'] = True


RE_NUM_TITULO = re.compile(r'^\s*\d+(?:\.\d+)*\.?\s+(?=\S)')


def _titulo_capitulo(elementos):
    """Título del capítulo. Si no se ha reconocido por su estilo y el primer párrafo va justo
    antes de los autores («5.1 Técnicas de…» en «Normal» + «Autores: …»), es el título. Y el
    título va sin la numeración del Word («4.1 Trabeculectomía…» → «Trabeculectomía…»): el
    número del capítulo no se pone en la portadilla (norma para todas las publicaciones)."""
    textos = [e for e in elementos if e.texto.strip()]
    if not any(e.papel in ('titulo', 'capitulo') for e in textos[:3]) and len(textos) > 1 \
            and textos[1].papel == 'autores' and textos[0].papel in ('texto', 'ladillo1', 'ladillo2', 'ladillo3') \
            and len(textos[0].texto) <= 400:
        t = textos[0]
        t.papel = 'titulo'
        t.notas.append('primer párrafo, justo antes de los autores: título del capítulo')
        if t.texto.rstrip().endswith('.'):
            t.trozos = _quitar_final(t.trozos, 1)
    for e in textos[:3]:
        if e.papel == 'titulo':
            m = RE_NUM_TITULO.match(e.texto)
            if m:
                e.trozos = limpiar_bordes(quitar_inicio(e.trozos, m.end()))[0]
                e.notas.append('quitado el número «%s» del título' % m.group(0).strip())
            break


RE_PIE_SERIE = re.compile(r'^\s*Fig(?:ura)?\.?\s*(\d+(?:\.\d+)*)\s*[A-Za-z]?\s*[.:\-–]\s*\S')


def _pies_sin_rotulo(elementos):
    """Pies de figura al final del texto sin rótulo («Figura 1. Blefarostato…», «Figura 2. …»):
    una serie de dos o más párrafos seguidos que empiezan por «Figura N.» con N creciente."""
    k = 0
    while k < len(elementos):
        serie, j, ultimo = [], k, ()
        while j < len(elementos) and elementos[j].papel == 'texto':
            m = RE_PIE_SERIE.match(elementos[j].texto)
            n = tuple(int(x) for x in m.group(1).split('.')) if m else None     # «16.10» → (16, 10)
            if not m or n < ultimo:
                break
            ultimo = n
            serie.append(elementos[j])
            j += 1
        if len(serie) >= 2:
            for e in serie:
                e.papel = 'pie_figura'
                e.datos['figuras'] = ids_figura(e.texto)
                e.notas.append('serie de pies «Figura N.» sin rótulo delante')
            k = j
        else:
            k += 1


def _nivel_titulo(estilo):
    """«heading 2» / «Título 2» de Word → 2; otro estilo → 0."""
    m = re.match(r'^\s*(heading|t[ií]tulo)\s*(\d)\s*$', estilo or '', re.I)
    return int(m.group(2)) if m else 0


def _titulos_word(bloques):
    """(párrafo del título del capítulo, {nivel de título de Word: nivel de ladillo}).
    El título es el primer «Título 1» si no hay texto antes. Cada autor usa los niveles a su
    manera (Título 2 para los ladillos, o Título 1 como el título): el nivel más alto que queda
    es el ladillo 1, el siguiente el 2 y el siguiente el 3."""
    parrafos = [b for b in bloques if isinstance(b, Parrafo) and b.texto.strip()]
    titulo = None
    if parrafos and _es_title(parrafos[0].estilo_word):
        return parrafos[0], _rango_titulos(parrafos, parrafos[0])     # «Title»: el título
    for b in parrafos:
        n = _nivel_titulo(b.estilo_word)
        if n == 1:
            titulo = b
        if n or titulo:
            break
    return titulo, _rango_titulos(parrafos, titulo)


def _rango_titulos(parrafos, titulo):
    niveles = sorted({_nivel_titulo(b.estilo_word) for b in parrafos if b is not titulo} - {0})
    return {n: min(k + 1, 3) for k, n in enumerate(niveles)}


def _etiqueta_word(lista, contadores):
    """El número que Word muestra delante del párrafo («1.», «2.3.»), o '' si no es numérica."""
    nid, nivel, formato, texto, inicio = (tuple(lista) + ('', '', 1))[:5]
    c = contadores.setdefault(nid, {})
    c[nivel] = c.get(nivel, (inicio or 1) - 1) + 1
    for n in [n for n in c if n > nivel]:
        del c[n]
    if formato != 'decimal':
        return ''
    return re.sub(r'%(\d)', lambda m: str(c.get(int(m.group(1)) - 1, 1)), texto or '%1.')


LADILLOS = ('ladillo1', 'ladillo2', 'ladillo3', 'titulo_bibliografia')
RE_NUM_LADILLO = re.compile(r'^\s*(\d{1,2})\s*[.:]\s+(?=\S)')


def _ladillos_de_su_lista(elementos):
    """Negrita corta en la misma lista numerada de Word que un ladillo de título («1.
    Indicación» con «Título 1» y «2. Material quirúrgico» con «Párrafo de lista»): otro ladillo
    de la serie, con su número."""
    listas = {e.datos['lista'][0] for e in elementos
              if e.datos.get('nivel_titulo') and e.papel in LADILLOS and e.datos.get('etiqueta_word')}
    for e in elementos:
        l = e.datos.get('lista')
        if l and l[0] in listas and e.datos.get('etiqueta_word') and e.papel in ('negrita_lista', 'vineta', 'lista_num') \
                and negrita(e.trozos) > 0.9 and len(e.texto) <= 120:
            e.papel = 'ladillo1'
            e.datos['de_lista'] = True
            e.notas.append('negrita en la lista numerada de los ladillos: ladillo')


def _numerar_ladillos(elementos):
    """Los ladillos que en el Word son «Título N» numerados llevan delante su número, y su
    nivel es el del número («3.» ladillo 1, «3.1.» ladillo 2) aunque el autor mezcle estilos.
    Una negrita con el número siguiente escrito a mano («4: Concepto clave:») también es
    ladillo de la serie."""
    ultimo = 0          # último número de primer nivel de la serie
    for e in elementos:
        etiqueta = e.datos.get('etiqueta_word')
        if (e.datos.get('nivel_titulo') or e.datos.get('de_lista')) and etiqueta and e.trozos and e.papel in LADILLOS:
            e.trozos = [replace(e.trozos[0], texto=etiqueta + ' ', nota=0, duda='')] + e.trozos
            e.notas.append('número del Word «%s» conservado' % etiqueta)
            partes = [x for x in etiqueta.split('.') if x.strip()]
            if e.papel != 'titulo_bibliografia' and all(x.strip().isdigit() for x in partes):
                nuevo = 'ladillo%d' % min(len(partes), 3)
                if nuevo != e.papel:
                    e.notas.append('%s por su número (el estilo de Word era de otro nivel)' % nuevo)
                    e.papel = nuevo
                if len(partes) == 1:
                    ultimo = int(partes[0])
            continue
        m = RE_NUM_LADILLO.match(e.texto)
        if ultimo and m and int(m.group(1)) == ultimo + 1 and e.papel in ('texto', 'ladillo2', 'ladillo3') \
                and negrita(e.trozos) > 0.9 and len(e.texto) <= 120:
            e.trozos = [replace(e.trozos[0], texto='%s. ' % m.group(1), nota=0, duda='')] + quitar_inicio(e.trozos, m.end())
            e.papel = 'ladillo1'
            e.notas = [n for n in e.notas if not n.startswith('frase de entrada')]
            e.notas.append('negrita con el número siguiente de los ladillos («%s»): ladillo 1' % m.group(0).strip())
            ultimo += 1


def _ladillos_sin_signo_final(elementos):
    """Norma para todas las publicaciones: un ladillo no termina en signo de puntuación
    («Indicación:» → «Indicación», «Material.» → «Material»). Se quedan «?», «!», «…» y los
    cierres de paréntesis o comillas, que son parte del texto."""
    for e in elementos:
        if e.papel not in LADILLOS:
            continue
        texto = e.texto.rstrip()
        fin = len(texto) - len(texto.rstrip('.:,;'))
        if fin and not texto.endswith('...') and texto[:-fin].strip() and not re.fullmatch(r'[\d.\s]*', texto[:-fin]):
            e.trozos = _quitar_final(e.trozos, fin)
            e.notas.append('quitado «%s» al final del ladillo' % texto[-fin:])


RE_PASO = re.compile(r'^\s*(\d{1,2})\s*[-.)]\s*(?=[^\W\d_])')


def _numeradas_a_mano(elementos):
    """Pasos numerados a mano («1-Vitrectomía…», «2- Elección…») en párrafos normales: lista
    numerada (sin el número escrito; lo pone InDesign). Solo si empiezan en 1 y hay al menos
    dos; si se salta un número, duda (InDesign numera seguido)."""
    k = 0
    while k < len(elementos):
        e = elementos[k]
        m = RE_PASO.match(e.texto)
        if e.papel != 'texto' or not m or m.group(1) != '1' or negrita(e.trozos) > 0.5:
            k += 1
            continue
        serie, j, n = [k], k + 1, 1
        while j < len(elementos):
            x = elementos[j]
            if x.papel in CORTAN_LISTA:
                break
            mx = RE_PASO.match(x.texto)
            if x.papel == 'texto' and mx and n < int(mx.group(1)) <= n + 2 and negrita(x.trozos) <= 0.5:
                serie.append(j)
                n = int(mx.group(1))
            j += 1
        if len(serie) < 2:
            k += 1
            continue
        esperado = 1
        for i in serie:
            x = elementos[i]
            mx = RE_PASO.match(x.texto)
            numero = int(mx.group(1))
            x.papel = 'lista_num'
            x.datos['falsa'] = 'num'
            x.trozos = quitar_inicio(x.trozos, mx.end())
            x.notas.append('número escrito a mano «%s» convertido en lista numerada' % mx.group(0).strip())
            if numero != esperado:
                x.dudas.append('en el Word es el %d: falta el %d (InDesign numera seguido)' % (numero, esperado))
            esperado = numero + 1
        k = serie[-1] + 1


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
        m = RE_BIBLIO.match(texto)
        if not m.group(1).lower().startswith('bibliograf'):
            # «Referencia», «Referencias (bibliográficas)» → «Bibliografía» (norma para todas
            # las publicaciones); el número de delante, si lo hay, se queda
            antes = _quitar_final(t, len(texto) - m.start(1)) if m.start(1) else []
            el.trozos = antes + [replace(t[0], texto=(' ' if antes else '') + 'Bibliografía', nota=0, duda='')]
            el.notas.append('«%s» unificado a «Bibliografía»' % m.group(1))
        elif texto.rstrip().endswith(('.', ':')):
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
    if zona == 'material' and re.match(r'^\s*Fig(?:ura)?\.?\s*[:.\-–]', texto, re.I):
        el.papel = 'pie_figura'
        el.datos['sin_numero'] = True
        el.dudas.append('pie de figura sin número en el Word')
        return
    if zona == 'material' and ult and ult.papel == 'pie_figura' and not RE_FIGURA.match(texto):
        el.papel = 'pie_figura'
        el.dudas.append('parece continuación del pie anterior')
        return
    # Pie sin «Figura N» (revistas): la línea corta justo debajo de una imagen y, si va pegada
    # y también es corta, la siguiente («Mario Esteban de Antonio» + «(Sevilla, 1928…)»).
    if zona == 'texto' and corto and not RE_FIGURA.match(texto) and not texto.isupper() and ult:
        if ult.papel == 'imagen' and 0 <= el.origen - ult.origen <= 3 and ult.procedencia == el.procedencia:
            el.papel = 'pie_figura'
            el.datos['sin_numero'] = True
            return
        if ult.papel == 'pie_figura' and ult.datos.get('sin_numero') and 0 <= el.origen - ult.origen <= 1 \
                and previos[-2].papel == 'imagen':
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
    # Estilos de título de Word, si la publicación lo pide: el primer «Título 1» es el título del
    # capítulo (Portadilla/Titulo, sin el punto final) y «Título 2/3/4» son ladillos de su nivel,
    # aunque no vayan en negrita.
    if el.datos.get('titulo_word') and len(texto) <= 400:
        el.papel = 'titulo'
        el.notas.append('estilo de Word «%s»: título del capítulo' % b.estilo_word)
        # «TÍTULO. Autores: …» en el mismo párrafo: los autores, en su párrafo detrás
        m = re.search(r'\s*\bAutor(?:es|as|a)?\s*:\s*', texto, re.I)
        if m and m.start() > 0:
            autores = quitar_inicio(t, m.end())
            if ''.join(x.texto for x in autores).rstrip().endswith('.'):
                autores = _quitar_final(autores, 1)
            el.datos['detras'] = Elemento('autores', autores, origen=el.origen, procedencia=el.procedencia,
                                          notas=['venía en el párrafo del título, tras «Autores:»'])
            t = el.trozos = _quitar_final(t, len(texto) - m.start())
        if ''.join(x.texto for x in t).rstrip().endswith('.'):
            el.trozos = _quitar_final(t, 1)
        return
    if ult and ult.papel == 'titulo' and ult.datos.get('titulo_word') and not el.datos.get('nivel_titulo') \
            and parece_autores(texto):
        el.papel = 'autores'            # los nombres, en su párrafo justo debajo del título
        return
    if el.datos.get('nivel_titulo') and corto and RE_VINETA_FALSA.match(texto) and not b.lista:
        el.datos['nivel_titulo'] = 0    # «- Plataforma…» con estilo de título: es una viñeta más
        el.notas.append('estilo de Word «%s», pero empieza por «%s»: viñeta' % (b.estilo_word, texto.strip()[0]))
    if el.datos.get('nivel_titulo') and corto:
        el.papel = 'ladillo%d' % el.datos['nivel_titulo']
        el.notas.append('estilo de Word «%s»' % b.estilo_word)
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
    if letra and not re.match(r'^\s*Fig(?:ura|s)?\.?\s*\d+(?:\.\d+)*\s*[A-Za-z]{2,}', texto, re.I):
        ids = [num + letra]
        ids += [num + l.upper() for l in re.findall(r'(?:\b%s|[.;]\s*)([A-Za-z])\s*[:.]' % re.escape(num), texto[m.end():])
                if num + l.upper() not in ids]
        return ids
    return [num]


# ---- renumerar figuras y tablas con el número del capítulo -----------------------
# Una referencia: «Figura 16.10A», «Figuras 16.10A y 16.10B», «Tabla 16.1», «(Fig. 16.2)».
RE_REFERENCIAS = re.compile(r'\b(Fig(?:ura)?s?\.?|Tablas?|V[ií]deos?|Algoritmos?)(\s*)'
                            r'((?:\d+\.\d{1,2}(?!\d)[A-Za-z]?(?:\s*(?:,|y|e|-|–|a|al)\s*(?=\d))?)+)', re.I)


def _sustituir(trozos, cambios):
    """Cambia los tramos [(inicio, fin, texto nuevo)] del texto de los trozos; el texto nuevo
    toma el formato del primer carácter del tramo."""
    letras = [(c, t) for t in trozos for c in t.texto]
    for ini, fin, nuevo in sorted(cambios, reverse=True):
        t = letras[ini][1] if ini < len(letras) else trozos[-1]
        letras[ini:fin] = [(c, t) for c in nuevo]
    res = []
    for c, t in letras:
        if res and res[-1][1] is t:
            res[-1][0].append(c)
        else:
            res.append(([c], t))
    return [replace(t, texto=''.join(cs)) for cs, t in res]


def renumerar_referencias(elementos, nuevo):
    """Figuras y tablas numeradas con el capítulo del Word («Figura 16.3», el capítulo era el 16)
    pasan al número del capítulo actual («Figura 15.3»). El capítulo antiguo es el que llevan los
    pies y títulos de tabla; solo se cambian los números con ese prefijo detrás de «Figura»,
    «Tabla», «Vídeo»… (no «16.000 pacientes»). Devuelve el número antiguo, o None."""
    prefijos = [f.split('.')[0] for e in elementos if e.papel == 'pie_figura' for f in e.datos.get('figuras', []) if '.' in f]
    prefijos += [e.datos['numero'].split('.')[0] for e in elementos
                 if e.papel == 'titulo_tabla' and '.' in e.datos.get('numero', '')]
    if not prefijos:
        return None
    viejo = max(set(prefijos), key=prefijos.count)
    if viejo == str(nuevo):
        return None
    patron = re.compile(r'(?<![\d.,])%s\.(?=\d)' % re.escape(viejo))
    for e in elementos:
        texto = e.texto
        cambios = []
        for m in RE_REFERENCIAS.finditer(texto):
            for n in patron.finditer(m.group(3)):
                ini = m.start(3) + n.start()
                cambios.append((ini, ini + len(viejo), str(nuevo)))
        if cambios:
            e.trozos = _sustituir(e.trozos, cambios)
            e.notas.append('figuras y tablas %s.x renumeradas como %s.x' % (viejo, nuevo))
        if e.papel == 'titulo_tabla' and e.datos.get('numero', '').startswith(viejo + '.'):
            e.datos['numero'] = str(nuevo) + e.datos['numero'][len(viejo):]
    return viejo


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


# ---- filiaciones de los autores ---------------------------------------------------------
RE_MARCA_SUP = re.compile(r'^[\d\s,;*†‡§#a-z]+$')       # llamadas voladas: «1,2», «*», «a»
RE_CORRESPONDENCIA = re.compile(r'correspondencia|correo|e-?mail|@', re.I)
RE_EMAIL = re.compile(r'\S+@\S+')


def es_centro(texto):
    """Nombra un centro de trabajo: «Hospital…», «Clínica Baviera», «Servicio de…» (con
    inicial mayúscula: «relevancia clínica» o el ladillo «RELEVANCIA CLÍNICA» no lo son) o un
    correo electrónico."""
    if RE_EMAIL.search(texto):
        return True
    return any(m.group()[0].isupper() and not m.group().isupper() for m in RE_CENTRO.finditer(texto))


RE_SEPARADOR = re.compile(r'\s*(?:[,;]|\s[–—-]\s|\.\s)\s*')


def _filtrar(trozos, quitar):
    """Los trozos sin los caracteres de las posiciones de `quitar` (conservan su formato)."""
    res, pos = [], 0
    for t in trozos:
        txt = ''.join(c for k, c in enumerate(t.texto, pos) if k not in quitar)
        pos += len(t.texto)
        if txt:
            if res and replace(res[-1], texto='') == replace(t, texto=''):
                res[-1] = replace(res[-1], texto=res[-1].texto + txt)
            else:
                res.append(replace(t, texto=txt))
    return res


def _quitar_tramos(trozos, patron, cond=lambda m: True):
    texto = ''.join(t.texto for t in trozos)
    quitar = set()
    for m in re.finditer(patron, texto):
        if cond(m):
            quitar.update(range(m.start(), m.end()))
    return _filtrar(trozos, quitar) if quitar else trozos


def solo_nombres(trozos):
    """«Alex Fonollosa,¹˒² Roberto Rodríguez (Hospital Cruces), Ana Gil, Servicio de
    Oftalmología, Hospital X» → «Alex Fonollosa, Roberto Rodríguez, Ana Gil»: sin llamadas
    voladas, sin paréntesis con el centro (o con números) y, en cada grupo separado por «;»,
    sin lo que va desde el primer tramo que es un centro de trabajo."""
    pos, quitar = 0, set()
    for t in trozos:                                    # llamadas voladas
        if t.pos == 'sup' and RE_MARCA_SUP.match(t.texto):
            quitar.update(range(pos, pos + len(t.texto)))
        pos += len(t.texto)
    trozos = _filtrar(trozos, quitar)
    trozos = _quitar_tramos(trozos, r'\s*\(([^()]*)\)',
                            lambda m: es_centro(m.group(1)) or re.fullmatch(r'[\d\s,*]+', m.group(1)))
    texto = ''.join(t.texto for t in trozos)
    quitar = set()
    for grupo in re.finditer(r'[^;]+', texto):          # cada grupo de autores, hasta «;»
        a = grupo.start()
        for m in list(RE_SEPARADOR.finditer(texto, grupo.start(), grupo.end())) + [None]:
            fin = m.start() if m else grupo.end()
            if es_centro(texto[a:fin]):          # desde su separador hasta el «;»
                quitar.update(range(desde if a > grupo.start() else a, grupo.end()))
                break
            desde, a = fin, m.end() if m else fin
    if quitar:          # los grupos ya solo tienen nombres: «Juan Pérez; Ana Gil» → con coma
        trozos = [replace(t, texto=t.texto.replace(';', ',')) for t in _filtrar(trozos, quitar)]
    # Limpieza: sin espacios dobles ni antes de coma, ni separadores al principio o al final
    trozos = _quitar_tramos(trozos, r'\s+(?=[,;])|(?<=\s)\s+|^[\s,;.]+|[\s,;.:]+$')
    return trozos


def _es_filiacion(e):
    t = e.texto.strip()
    if not t or len(t) > 400 or e.papel in ('titulo', 'capitulo', 'tabla', 'imagen', 'titulo_bibliografia'):
        return False
    if e.trozos and e.trozos[0].pos == 'sup' and RE_MARCA_SUP.match(e.trozos[0].texto):
        return bool(RE_CENTRO.search(t))        # «¹HOSPITAL…», con su llamada delante
    return es_centro(t) and len(t) < 250


def _quitar_filiaciones(elementos):
    """Norma para todas las publicaciones: de los autores solo interesan nombre y apellidos,
    no dónde trabajan. Se limpian los párrafos de autores y se quitan los de filiación que
    van justo debajo (en las revistas, el «centro», salvo la dirección de correspondencia)."""
    k = 0
    while k < min(len(elementos), 12):
        e = elementos[k]
        if e.papel == 'centro' and not RE_CORRESPONDENCIA.search(e.texto):
            del elementos[k]
            continue
        if e.papel != 'autores':
            k += 1
            continue
        antes = e.texto
        e.trozos = solo_nombres(e.trozos)
        if e.texto != antes.strip().rstrip('.,;:'):
            e.notas.append('quitadas las filiaciones (antes: «%s»)' % antes.strip())
        while k + 1 < len(elementos) and _es_filiacion(elementos[k + 1]) \
                and not RE_CORRESPONDENCIA.search(elementos[k + 1].texto):
            e.notas.append('quitada la filiación «%s»' % elementos[k + 1].texto.strip())
            del elementos[k + 1]
        k += 1


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
        if e.papel in ('texto', 'vineta', 'lista_num', 'texto_vineta', 'texto_ideas', 'primer_texto', 'resumen') \
                and mayusculas(e.texto) < 0.5:      # en un párrafo todo en mayúsculas no son siglas
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
                'titulo_caso', 'texto_caso',
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
        if e.datos.get('falsa') == 'num':
            e.nivel = 1             # paso numerado a mano: siempre el primer nivel
            previo = e
            continue
        if e.datos.get('falsa'):
            if previo is None:
                e.nivel = 1
            elif previo.datos.get('falsa') == 'num':
                e.nivel = previo.nivel + 1      # viñeta bajo un paso numerado
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
