"""Lectura de un .docx a una lista de bloques (párrafos, tablas) sin dependencias externas.

Cada párrafo conserva sus trozos de texto con el formato efectivo (negrita, cursiva,
subrayado, posición, cuerpo), la numeración de lista de Word y las imágenes que contiene.
Se leen también los controles de contenido (w:sdt) y las notas finales: hay autores que
meten ahí la bibliografía, las leyendas y hasta las imágenes.
"""
import posixpath
import zipfile
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field

W = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'
R = '{http://schemas.openxmlformats.org/officeDocument/2006/relationships}'
A = '{http://schemas.openxmlformats.org/drawingml/2006/main}'
REL = '{http://schemas.openxmlformats.org/package/2006/relationships}'


@dataclass
class Trozo:
    texto: str
    b: bool = False
    i: bool = False
    u: bool = False
    pos: str = ''          # 'sup' | 'sub' | ''
    pt: float = 0.0
    nota: int = 0          # número de nota final si el trozo es su llamada


@dataclass
class Parrafo:
    trozos: list
    estilo_word: str = ''
    lista: tuple = None    # (numId, nivel, formato, símbolo) si tiene numeración de Word
    sangria: int = 0       # sangría izquierda efectiva en twips (1 cm = 567)
    imagenes: list = field(default_factory=list)   # rutas dentro del .docx
    origen: str = 'cuerpo'  # 'cuerpo' | 'nota final N'
    indice: int = 0

    @property
    def texto(self):
        return ''.join(t.texto for t in self.trozos)


@dataclass
class Tabla:
    filas: list            # filas → celdas → lista de Parrafo
    origen: str = 'cuerpo'
    indice: int = 0


def _val(el, tag, defecto=None):
    e = el.find(W + tag) if el is not None else None
    return e.get(W + 'val') if e is not None else defecto


def _sangria(ppr):
    """Sangría izquierda en twips, o None si el párrafo no la define."""
    ind = ppr.find(W + 'ind') if ppr is not None else None
    if ind is None:
        return None
    v = ind.get(W + 'left') or ind.get(W + 'start')
    return int(v) if v and v.lstrip('-').isdigit() else None


def _activo(el, tag):
    """Propiedad conmutable (w:b, w:i...): None si no está, True/False si está."""
    e = el.find(W + tag) if el is not None else None
    if e is None:
        return None
    return e.get(W + 'val') not in ('0', 'false', 'none')


class Documento:
    def __init__(self, ruta):
        self.ruta = ruta
        self.z = zipfile.ZipFile(ruta)
        self.nombres = self.z.namelist()
        self._leer_estilos()
        self._leer_numeracion()
        self.bloques = []
        self.notas_finales = {}   # id → número ordinal de la nota
        self._leer_cuerpo()

    # ---- estilos --------------------------------------------------------
    def _xml(self, nombre):
        return ET.fromstring(self.z.read(nombre)) if nombre in self.nombres else None

    def _leer_estilos(self):
        self.estilos = {}
        self.rpr_defecto = None
        raiz = self._xml('word/styles.xml')
        if raiz is None:
            return
        dd = raiz.find(W + 'docDefaults')
        if dd is not None:
            self.rpr_defecto = dd.find(W + 'rPrDefault/' + W + 'rPr')
        for s in raiz.iter(W + 'style'):
            self.estilos[s.get(W + 'styleId')] = {
                'nombre': _val(s, 'name', s.get(W + 'styleId')),
                'base': _val(s, 'basedOn'),
                'rpr': s.find(W + 'rPr'),
                'numpr': s.find(W + 'pPr/' + W + 'numPr'),
                'sangria': _sangria(s.find(W + 'pPr')),
            }

    def _cadena(self, sid):
        """Estilo y sus padres, del más concreto al más general."""
        vistos = []
        while sid and sid in self.estilos and sid not in vistos:
            vistos.append(sid)
            sid = self.estilos[sid]['base']
        return [self.estilos[s] for s in vistos]

    def _leer_numeracion(self):
        self.listas = {}
        raiz = self._xml('word/numbering.xml')
        if raiz is None:
            return
        abstractos, enlaces = {}, {}
        for a in raiz.iter(W + 'abstractNum'):
            niveles = {}
            for lvl in a.findall(W + 'lvl'):
                niveles[int(lvl.get(W + 'ilvl'))] = (_val(lvl, 'numFmt', ''), _val(lvl, 'lvlText', ''),
                                                     _sangria(lvl.find(W + 'pPr')))
            abstractos[a.get(W + 'abstractNumId')] = niveles
            if _val(a, 'numStyleLink'):
                enlaces[a.get(W + 'abstractNumId')] = _val(a, 'numStyleLink')
        num_abs = {n.get(W + 'numId'): _val(n, 'abstractNumId') for n in raiz.iter(W + 'num')}
        for nid, aid in num_abs.items():
            # Una lista que enlaza a un estilo de numeración toma los niveles del
            # num que ese estilo tiene asignado.
            if aid in enlaces and enlaces[aid] in self.estilos:
                numpr = self.estilos[enlaces[aid]]['numpr']
                aid = num_abs.get(_val(numpr, 'numId'), aid)
            self.listas[nid] = abstractos.get(aid, {})

    # ---- cuerpo ---------------------------------------------------------
    def _leer_cuerpo(self):
        raiz = self._xml('word/document.xml')
        rels = self._rels('word/_rels/document.xml.rels')
        self._recorrer(raiz.find(W + 'body'), rels, 'cuerpo')
        # Notas finales: su llamada en el texto se convierte en cita numerada y su
        # contenido se añade al final, en orden de aparición.
        notas = self._xml('word/endnotes.xml')
        if notas is not None and self.notas_finales:
            rels_n = self._rels('word/_rels/endnotes.xml.rels')
            por_id = {n.get(W + 'id'): n for n in notas.findall(W + 'endnote')}
            for nid, num in sorted(self.notas_finales.items(), key=lambda x: x[1]):
                if nid in por_id:
                    self._recorrer(por_id[nid], rels_n, 'nota final %d' % num)
        for k, b in enumerate(self.bloques):
            b.indice = k + 1

    def _rels(self, nombre):
        raiz = self._xml(nombre)
        if raiz is None:
            return {}
        return {r.get('Id'): posixpath.normpath(posixpath.join('word', r.get('Target')))
                for r in raiz.iter(REL + 'Relationship')}

    def _recorrer(self, contenedor, rels, origen):
        for el in contenedor:
            if el.tag == W + 'p':
                self.bloques.append(self._parrafo(el, rels, origen))
            elif el.tag == W + 'tbl':
                filas = []
                for tr in el.findall(W + 'tr'):
                    celdas = []
                    for tc in tr.findall(W + 'tc'):
                        celdas.append([self._parrafo(p, rels, origen) for p in tc.iter(W + 'p')])
                    filas.append(celdas)
                self.bloques.append(Tabla(filas, origen))
            elif el.tag == W + 'sdt':
                c = el.find(W + 'sdtContent')
                if c is not None:
                    self._recorrer(c, rels, origen)

    def _parrafo(self, p, rels, origen):
        ppr = p.find(W + 'pPr')
        sid = _val(ppr, 'pStyle', '')
        cadena_p = self._cadena(sid) if sid else self._cadena(self._estilo_normal())
        par = Parrafo([], estilo_word=cadena_p[0]['nombre'] if cadena_p else '', origen=origen)
        numpr = ppr.find(W + 'numPr') if ppr is not None else None
        if numpr is None:
            numpr = next((e['numpr'] for e in cadena_p if e['numpr'] is not None), None)
        if numpr is not None:
            nid = _val(numpr, 'numId')
            nivel = int(_val(numpr, 'ilvl', '0'))
            if nid and nid != '0':
                fmt = self.listas.get(nid, {}).get(nivel, ('', '', None))
                par.lista = (nid, nivel, fmt[0], fmt[1])
                if fmt[2] is not None:
                    par.sangria = fmt[2]
        directa = _sangria(ppr)
        if directa is None:
            directa = next((e['sangria'] for e in cadena_p if e['sangria'] is not None), None)
        if directa is not None and not (par.lista and _sangria(ppr) is None):
            par.sangria = directa
        self._runs(p, par, cadena_p, rels)
        # Word parte el texto en trozos con el mismo formato (revisiones, ortografía):
        # se unen para que «(3,4)» o una palabra no queden cortados.
        unidos = []
        for t in par.trozos:
            if unidos and not t.nota and not unidos[-1].nota and \
                    (t.b, t.i, t.u, t.pos, t.pt) == (unidos[-1].b, unidos[-1].i, unidos[-1].u, unidos[-1].pos, unidos[-1].pt):
                unidos[-1].texto += t.texto
            else:
                unidos.append(t)
        par.trozos = unidos
        return par

    def _estilo_normal(self):
        for sid, e in self.estilos.items():
            if e['nombre'] == 'Normal':
                return sid
        return None

    def _runs(self, nodo, par, cadena_p, rels):
        for el in nodo:
            if el.tag == W + 'r':
                self._run(el, par, cadena_p, rels)
            elif el.tag in (W + 'hyperlink', W + 'smartTag', W + 'ins', W + 'fldSimple', W + 'customXml'):
                self._runs(el, par, cadena_p, rels)
            elif el.tag == W + 'sdt':
                c = el.find(W + 'sdtContent')
                if c is not None:
                    self._runs(c, par, cadena_p, rels)

    def _formato(self, rpr, cadena_p):
        cadena_r = []
        rs = _val(rpr, 'rStyle')
        if rs:
            cadena_r = self._cadena(rs)
        fuentes = [rpr] + [e['rpr'] for e in cadena_r] + [e['rpr'] for e in cadena_p] + [self.rpr_defecto]

        def primero(fn):
            for f in fuentes:
                if f is None:
                    continue
                v = fn(f)
                if v is not None:
                    return v
            return None

        u = primero(lambda f: _val(f, 'u'))
        va = primero(lambda f: _val(f, 'vertAlign'))
        sz = primero(lambda f: _val(f, 'sz'))
        return dict(
            b=bool(primero(lambda f: _activo(f, 'b'))),
            i=bool(primero(lambda f: _activo(f, 'i'))),
            u=bool(u and u != 'none'),
            pos={'superscript': 'sup', 'subscript': 'sub'}.get(va, ''),
            pt=int(sz) / 2 if sz else 0.0,
        )

    def _run(self, r, par, cadena_p, rels):
        f = self._formato(r.find(W + 'rPr'), cadena_p)
        texto = []
        for x in r:
            if x.tag == W + 't':
                texto.append(x.text or '')
            elif x.tag == W + 'tab':
                texto.append('\t')
            elif x.tag in (W + 'br', W + 'cr'):
                if x.get(W + 'type') in (None, 'textWrapping'):
                    texto.append('\n')
            elif x.tag == W + 'noBreakHyphen':
                texto.append('‑')
            elif x.tag == W + 'sym':
                texto.append(chr(int(x.get(W + 'char'), 16)) if x.get(W + 'char') else '')
            elif x.tag == W + 'endnoteReference':
                nid = x.get(W + 'id')
                num = self.notas_finales.setdefault(nid, len(self.notas_finales) + 1)
                par.trozos.append(Trozo(str(num), nota=num, **f))
            elif x.tag in (W + 'drawing', W + 'pict', '{http://schemas.openxmlformats.org/markup-compatibility/2006}AlternateContent'):
                for blip in x.iter(A + 'blip'):
                    destino = rels.get(blip.get(R + 'embed'))
                    if destino:
                        par.imagenes.append(destino)
        if texto:
            par.trozos.append(Trozo(''.join(texto), **f))

    def imagen(self, ruta):
        return self.z.read(ruta)
