"""Bloque 2 de la ortotipografía: casos dudosos, que no se corrigen solos sino que se marcan
en InDesign con texto condicional para que los revise el usuario.

Entrada: los párrafos que exporta jsx/exportar_texto.jsx ({spec, estilo, texto, cursiva}).
Salida: lista de Duda(spec, inicio, fin, tipo, motivo, sugerencia).

Tipos:
  tilde          palabra a la que solo le falta (o sobra) una tilde: FUNGICAS → FÚNGICAS
  ortografia     error de ortografía o gramática según LanguageTool
  desconocida    palabra que LanguageTool no conoce y que solo sale una vez en los capítulos
                 (muchas son términos médicos correctos: van al diccionario de la publicación)
  extranjerismo  palabra inglesa sin cursiva: background, swab
  cursiva        la misma palabra va en cursiva en un sitio y en redonda en otro
  criterio       dos formas para lo mismo en el capítulo (guion o mayúsculas): gram-negativos / gramnegativos
  compuesto      palabra compuesta con guion (blanco-amarillento): que no se parta a final de línea
                 (blanco-amarillen-to); se propone «sin partir»
"""
import json
import os
import re
import subprocess
import time
import unicodedata
import urllib.parse
import urllib.request
from collections import Counter, defaultdict
from dataclasses import dataclass

LT_DIR = os.path.expanduser('~/.cache/language_tool_python/LanguageTool-6.8')
JAVA = '/Volumes/DATOS/Proyectos Codex/Correcciones ortotipograficas/tools/jre/Contents/Home/bin/java'
LT_PUERTO = 8091

PALABRA = re.compile(r"[^\W\d_]+(?:[-'][^\W\d_]+)*")


@dataclass
class Duda:
    spec: str
    inicio: int
    fin: int
    tipo: str
    motivo: str
    sugerencia: str = ''
    texto: str = ''
    estilo: str = ''        # estilo de párrafo
    contexto: str = ''      # «…antes [texto] después…», para Claude y la ventana de revisión


# ---- LanguageTool (servidor local) -------------------------------------------------------
class LanguageTool:
    def __init__(self, puerto=LT_PUERTO):
        self.url = 'http://localhost:%d/v2/check' % puerto
        self.proceso = None
        self.cache = {}
        if not self._vivo():
            self.proceso = subprocess.Popen(
                [JAVA, '-cp', os.path.join(LT_DIR, 'languagetool-server.jar'),
                 'org.languagetool.server.HTTPServer', '--port', str(puerto)],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            for _ in range(60):
                if self._vivo():
                    break
                time.sleep(1)
            else:
                raise RuntimeError('LanguageTool no arranca')

    def _vivo(self):
        try:
            urllib.request.urlopen(self.url.replace('/check', '/languages'), timeout=2)
            return True
        except OSError:
            return False

    def check(self, texto, idioma='es'):
        clave = (texto, idioma)
        if clave not in self.cache:
            self.cache[clave] = self._check(texto, idioma)
        return self.cache[clave]

    def _check(self, texto, idioma):
        datos = urllib.parse.urlencode({'text': texto, 'language': idioma}).encode()
        with urllib.request.urlopen(self.url, datos, timeout=120) as r:
            return json.load(r)['matches']

    def cerrar(self):
        if self.proceso:
            self.proceso.terminate()


# ---- utilidades ---------------------------------------------------------------------------
def sin_tildes(s):
    return ''.join(c for c in unicodedata.normalize('NFD', s) if unicodedata.category(c) != 'Mn')


def es_sigla(palabra):
    """PACD, PIO, AINEs, QB…: casi nunca son errores."""
    base = palabra[:-1] if palabra.endswith('s') else palabra
    letras = [c for c in base if c.isalpha()]
    return bool(letras) and len(base) <= 6 and all(c.isupper() for c in letras)


def en_cursiva(p, ini, fin):
    return any(a <= ini and fin <= b for a, b in p['cursiva'])


def cargar_diccionario(ruta):
    """Palabras que no son errores (términos médicos, nombres): una por línea, # comenta."""
    if not ruta or not os.path.exists(ruta):
        return set()
    with open(ruta, encoding='utf-8') as f:
        return {l.split('#')[0].strip().lower() for l in f if l.split('#')[0].strip()}


# Condición de InDesign de cada tipo: (nombre, color de UIColors). Distintas de las «Duda …»
# de la importación.
CONDICIONES = {
    'tilde':         ('Revisar tilde', 'MAGENTA'),
    'ortografia':    ('Revisar ortografía', 'PINK'),
    'desconocida':   ('Revisar palabra desconocida', 'LIGHT_GRAY'),
    'extranjerismo': ('Revisar extranjerismo', 'VIOLET'),
    'cursiva':       ('Revisar cursiva', 'TEAL'),
    'criterio':      ('Revisar criterio', 'BROWN'),
    'compuesto':     ('Revisar palabra compuesta', 'GOLD'),
}

COMPUESTA = re.compile(r'(?<![\w-])[^\W\d_]{2,}(?:-[^\W\d_]{2,})+(?![\w-])')


# ---- análisis ----------------------------------------------------------------------------
def analizar(parrafos, lt, excluir=('Bibliografia', 'Portadilla/Autores'), diccionario=frozenset(),
             frecuentes=frozenset()):
    """frecuentes: palabras desconocidas que se repiten en el conjunto de capítulos; se dan por
    términos correctos (estromal, moxifloxacino…). Ver desconocidas()."""
    dudas = []
    revisables = [p for p in parrafos if p['texto'].strip() and not any(
        p['estilo'] == e or p['estilo'].startswith(e + '/') for e in excluir)]

    # Palabras que el capítulo escribe en cursiva en algún sitio: si en otro van en redonda,
    # es duda de cursiva (y no de ortografía).
    # Solo tramos cortos: una frase entera en cursiva no dice nada de sus palabras.
    cursivas = set()
    for p in revisables:
        for a, b in p['cursiva']:
            ws = PALABRA.findall(p['texto'][a:b])
            if len(ws) <= 3:
                cursivas.update(w.lower() for w in ws)

    # 1. LanguageTool, párrafo a párrafo.
    desconocidas = []          # (párrafo, inicio, fin, palabra) que no conoce en español
    for p in revisables:
        texto = p['texto']
        for m in lt.check(texto):
            ini, fin = m['offset'], m['offset'] + m['length']
            frag = texto[ini:fin]
            regla, cat = m['rule']['id'], m['rule']['category']['id']
            sugerencias = [r['value'] for r in m['replacements'][:3]]
            if not frag.strip() or es_sigla(frag) or any(c.isdigit() for c in frag):
                continue
            if cat in ('TYPOGRAPHY', 'STYLE', 'REDUNDANCY', 'CASING', 'PUNCTUATION') or 'WHITESPACE' in regla:
                continue
            if frag.lower() in diccionario or en_cursiva(p, ini, fin):
                continue
            solo_tilde = sugerencias and sin_tildes(sugerencias[0]).lower() == sin_tildes(frag).lower() \
                and sugerencias[0].lower() != frag.lower()
            # Con mayúscula inicial suele ser un género o un nombre (Candida, Alternaria): solo
            # minúsculas o todo mayúsculas (FUNGICAS).
            nombre = frag[:1].isupper() and not frag.isupper()
            if cat == 'TYPOS' and solo_tilde and nombre:
                continue
            if cat == 'TYPOS' and solo_tilde:
                dudas.append(Duda(p['spec'], ini, fin, 'tilde', 'Falta o sobra una tilde', sugerencias[0], frag))
            elif cat == 'TYPOS' and frag.lower() in cursivas:
                dudas.append(Duda(p['spec'], ini, fin, 'cursiva',
                                  'En otro sitio del capítulo va en cursiva', '', frag))
            elif cat == 'TYPOS':
                desconocidas.append((p, ini, fin, frag, sugerencias))
            else:
                dudas.append(Duda(p['spec'], ini, fin, 'ortografia', m['message'], ', '.join(sugerencias), frag))

    # 2. Las desconocidas en español que son inglés → extranjerismo sin cursiva.
    unicas = sorted({d[3].lower() for d in desconocidas if d[3][:1].islower()})
    inglesas = set(unicas)
    if unicas:
        for m in lt.check('\n'.join(unicas), 'en-US'):
            if m['rule']['category']['id'] == 'TYPOS':
                inglesas.discard(m['context']['text'][m['context']['offset']:m['context']['offset'] + m['context']['length']].lower())
    for p, ini, fin, frag, sug in desconocidas:
        if frag.lower() in inglesas:
            dudas.append(Duda(p['spec'], ini, fin, 'extranjerismo', 'Palabra inglesa sin cursiva', '', frag))
        elif frag[:1].isupper():
            continue        # nombres propios, géneros… demasiado ruido para marcarlos todos
        elif frag.lower() not in frecuentes:
            dudas.append(Duda(p['spec'], ini, fin, 'desconocida', 'Palabra desconocida', ', '.join(sug), frag))

    # 3. Criterio: la misma palabra escrita de dos maneras (guion, tilde, mayúsculas).
    formas = defaultdict(Counter)
    sitios = defaultdict(list)
    for p in revisables:
        for m in PALABRA.finditer(p['texto']):
            w = m.group(0)
            if len(w) < 4 or es_sigla(w):
                continue
            clave = w.lower().replace('-', '')      # tildes no: esta / está son palabras distintas
            # La mayúscula inicial de principio de frase no es otra forma.
            forma = w if not (w[0].isupper() and w[1:].islower()) else w.lower()
            formas[clave][forma] += 1
            sitios[clave].append((p, m.start(), m.end(), forma, w))
    vistas = {(d.spec, d.inicio) for d in dudas}
    for clave, cnt in formas.items():
        if len(cnt) < 2:
            continue
        mayoritaria = cnt.most_common(1)[0][0]
        for p, ini, fin, forma, w in sitios[clave]:
            if forma != mayoritaria and (p['spec'], ini) not in vistas:
                otras = ' / '.join('%s (%d)' % (f, n) for f, n in cnt.most_common())
                dudas.append(Duda(p['spec'], ini, fin, 'criterio', 'Dos formas en el capítulo: ' + otras,
                                  mayoritaria, w))

    # 4. Palabras compuestas con guion (que no tengan ya otra duda encima).
    for p in revisables:
        for m in COMPUESTA.finditer(p['texto']):
            if not any(d.spec == p['spec'] and d.inicio < m.end() and m.start() < d.fin for d in dudas):
                dudas.append(Duda(p['spec'], m.start(), m.end(), 'compuesto',
                                  'Palabra compuesta con guion: que no se parta a final de línea', '', m.group(0)))

    # Contexto y estilo de cada duda, en orden de lectura.
    por_spec = {p['spec']: (k, p) for k, p in enumerate(parrafos)}
    for d in dudas:
        p = por_spec[d.spec][1]
        t = p['texto']
        a, b = max(0, d.inicio - 70), min(len(t), d.fin + 70)
        d.estilo = p['estilo']
        d.contexto = ('…' if a else '') + t[a:d.inicio] + '[' + t[d.inicio:d.fin] + ']' + t[d.fin:b] + ('…' if b < len(t) else '')
    dudas.sort(key=lambda d: (por_spec[d.spec][0], d.inicio))
    return dudas


def desconocidas(parrafos, lt, excluir=('Bibliografia', 'Portadilla/Autores')):
    """Contador de las palabras en minúscula que LanguageTool no conoce en español."""
    cnt = Counter()
    for p in parrafos:
        if not p['texto'].strip() or any(p['estilo'] == e or p['estilo'].startswith(e + '/') for e in excluir):
            continue
        for m in lt.check(p['texto']):
            if m['rule']['category']['id'] == 'TYPOS':
                frag = p['texto'][m['offset']:m['offset'] + m['length']]
                if frag[:1].islower():
                    cnt[frag.lower()] += 1
    return cnt
