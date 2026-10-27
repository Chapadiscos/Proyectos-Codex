"""Generación de ICML (formato de InCopy) con los estilos de la maqueta.

InDesign coloca el ICML aplicando los estilos del documento que tengan el mismo nombre
(los de grupo se escriben «Grupo:Estilo»). Las dudas van con la condición «Dudas»
(resaltado que no se imprime) y una nota de InDesign con el motivo.
"""
import re
import unicodedata
from xml.sax.saxutils import escape, quoteattr

from . import citas as mod_citas

SIN_ESTILO = 'CharacterStyle/$ID/[No character style]'
# Una condición (texto condicional) por tipo de duda: el color dice qué revisar. El motivo
# concreto de cada una está en el informe HTML (y en una nota, si [dudas] notas = true).
# En el ICML, AppliedConditions es una lista separada por espacios: un nombre con espacios
# se lee como varias referencias (con «Duda: carácter» InDesign se cerraba al colocar el
# archivo). Por eso aquí van con guion; importar.jsx las renombra al final («Duda estilo»).
CONDICIONES = [            # (nombre, color de InDesign, palabras del motivo)
    ('Duda-caracter', 'Red', ('carácter extraño',)),
    ('Duda-cita', 'LightBlue', ('cita',)),
    ('Duda-salto', 'Orange', ('salto',)),
    ('Duda-figura', 'Cyan', ('figura', 'imagen', 'tabla', 'archivo')),
    ('Duda-estilo', 'Yellow', ()),        # el resto: ¿ladillo, viñeta o texto?
]


def condicion(motivo):
    m = motivo.lower()
    return next(n for n, _, palabras in CONDICIONES if not palabras or any(p in m for p in palabras))


# Lo que no va en el texto corrido: se coloca en la mesa de trabajo o se omite.
FUERA_DEL_TEXTO = ('pie_figura', 'imagen', 'rotulo_material', 'etiqueta_imagen', 'titulo_tabla', 'tabla', 'pie_tabla')
SIN_CITAS = ('bibliografia', 'titulo_tabla', 'pie_figura', 'capitulo', 'autores')


def ref_estilo(tipo, nombre):
    """'Ladillos/Ladillo 1' → 'ParagraphStyle/Ladillos%3aLadillo 1'"""
    return '%s/%s' % (tipo, nombre.replace('/', '%3a'))


def ref_condicion(nombre):
    """'Duda-cita' → 'Condition/Duda-cita'. Sin espacios ni «:» (ver CONDICIONES)."""
    assert ' ' not in nombre and ':' not in nombre, nombre
    return 'Condition/' + nombre


class Generador:
    def __init__(self, conf):
        self.conf = conf
        self.parrafo = conf['parrafo']
        self.caracter = conf['caracter']
        self.usados_p, self.usados_c = set(), set()
        self.estilo_actual = ''
        self.n_dudas = 0
        self.registro = []      # cada duda con su texto y su motivo (informes/<capítulo>-marcas.json)
        self.con_notas = conf.get('dudas', {}).get('notas', False)

    # ---- piezas -------------------------------------------------------------
    def estilo_caracter(self, t):
        # Los estilos de párrafo con otra fuente (Avenir, BC Civitas) tienen sus propios
        # estilos de negrita y cursiva; un valor vacío deja ese formato sin aplicar.
        car = dict(self.caracter)
        grupo = self.estilo_actual.rpartition('/')[0] or self.estilo_actual
        car.update(self.conf.get('caracter_por_grupo', {}).get(grupo, {}))
        if t.b and t.i:
            return car.get('negrita_cursiva') or car.get('negrita') or None
        if t.b:
            return car.get('negrita') or None
        if t.i:
            return car.get('cursiva') or None
        if t.pos == 'sup':
            return self.caracter['superindice']
        return None

    def rango(self, t, quitar_negrita=False, duda_extra=''):
        from dataclasses import replace
        raro = next((c for c in t.texto if _caracter_raro(c)), None)
        if raro and not t.duda:
            t = replace(t, duda='Carácter extraño %s (U+%04X): ¿qué debería ser?' % (
                unicodedata.name(raro, 'sin nombre'), ord(raro)))
        if quitar_negrita:
            # Ladillos, títulos y cabeceras: el formato lo pone el estilo de párrafo.
            t = replace(t, b=False, i=False)
        simbolos = self.caracter.get('simbolos', '')
        volados = self.caracter.get('simbolos_superindice', '')
        aparte = simbolos + volados
        if aparte and any(c in aparte for c in t.texto) and len(t.texto) > 1:
            # Los símbolos van en su propio rango: con el estilo que tiene el glifo (→) o en
            # superíndice (™ ®).
            trozos = re.split('([%s])' % re.escape(aparte), t.texto)
            return ''.join(self.rango(replace(t, texto=x, duda=t.duda if k == 0 else ''), False, duda_extra)
                           for k, x in enumerate(trozos) if x)
        if volados and t.texto and all(c in volados for c in t.texto):
            t = replace(t, pos='sup', b=False, i=False)    # → estilo de superíndice (Super)
        if simbolos and t.texto and all(c in simbolos for c in t.texto):
            estilo = self.caracter['estilo_simbolos']
            self.usados_c.add(estilo)
            duda = t.duda or duda_extra
            if t.duda:
                self.anotar(t.duda, t.texto)
            return '<CharacterStyleRange AppliedCharacterStyle=%s%s><Content>%s</Content></CharacterStyleRange>' % (
                quoteattr(ref_estilo('CharacterStyle', estilo)),
                (' AppliedConditions=%s' % quoteattr(ref_condicion(condicion(duda)))) if duda else '',
                escape(t.texto))
        estilo = self.estilo_caracter(t)
        attrs = ' AppliedCharacterStyle=%s' % quoteattr(ref_estilo('CharacterStyle', estilo) if estilo else SIN_ESTILO)
        if estilo:
            self.usados_c.add(estilo)
        if t.pos == 'sub' or (t.pos == 'sup' and estilo != self.caracter['superindice']):
            attrs += ' Position="%s"' % ('Subscript' if t.pos == 'sub' else 'Superscript')
        duda = t.duda or duda_extra
        if duda:
            attrs += ' AppliedConditions=%s' % quoteattr(ref_condicion(condicion(duda)))
        nota = self.nota(t.duda) if t.duda else ''
        texto = t.texto.replace('\n', ' ')
        if t.duda:
            self.anotar(t.duda, texto)
        return '<CharacterStyleRange%s>%s<Content>%s</Content></CharacterStyleRange>' % (attrs, nota, escape(texto))

    def anotar(self, motivo, texto):
        """Apunta una duda para la ventana «Recorrer marcas» (el nombre de la condición, ya con
        espacio, como queda en InDesign)."""
        self.registro.append({'condicion': condicion(motivo).replace('-', ' '), 'texto': texto, 'motivo': motivo})

    def nota(self, texto):
        self.n_dudas += 1
        if not self.con_notas:
            return ''
        return ('<Note><ParagraphStyleRange><CharacterStyleRange><Content>%s</Content>'
                '</CharacterStyleRange></ParagraphStyleRange></Note>') % escape(texto)

    def parrafo_xml(self, estilo, trozos, dudas=(), attrs='', ultimo=False, quitar_negrita=False):
        trozos = espacios(trozos)
        self.usados_p.add(estilo)
        self.estilo_actual = estilo
        cuerpo = []
        duda_parrafo = ' · '.join(dudas)
        if duda_parrafo:
            self.anotar(duda_parrafo, ''.join(t.texto for t in trozos).replace('\n', ' '))
            nota = self.nota(duda_parrafo)
            if nota:
                cuerpo.append('<CharacterStyleRange AppliedCharacterStyle="%s" AppliedConditions=%s>%s'
                              '<Content></Content></CharacterStyleRange>' % (
                                  SIN_ESTILO, quoteattr(ref_condicion(condicion(duda_parrafo))), nota))
        cuerpo += [self.rango(t, quitar_negrita, duda_parrafo) for t in trozos if t.texto]
        fin = '' if ultimo else '<CharacterStyleRange AppliedCharacterStyle="%s"><Br/></CharacterStyleRange>' % SIN_ESTILO
        return '<ParagraphStyleRange AppliedParagraphStyle=%s%s>%s%s</ParagraphStyleRange>' % (
            quoteattr(ref_estilo('ParagraphStyle', estilo)), attrs, ''.join(cuerpo), fin)

    # ---- historia principal -------------------------------------------------
    def historia(self, elementos):
        n_bib = sum(1 for e in elementos if e.papel == 'bibliografia')
        cc = self.conf.get('citas', {})
        partes, anterior = [], None
        visibles = [e for e in elementos if e.papel not in FUERA_DEL_TEXTO]
        for k, e in enumerate(visibles):
            trozos = e.trozos
            if e.papel not in SIN_CITAS:
                trozos, _ = mod_citas.normalizar(trozos, n_bib, cc.get('rango_minimo', 3), cc.get('guion', '–'))
            trozos = referencias_sin_formato(puntuacion_tras_referencias(trozos))
            attrs = ''
            if e.papel == 'vineta':
                estilo = self.parrafo['vineta%d' % max(e.nivel, 1)]
            elif e.papel == 'lista_num':
                estilo = self.parrafo['vineta%d' % max(e.nivel, 1)]
                attrs = ' BulletsAndNumberingListType="NumberedList"'
                if anterior is None or anterior.papel != 'lista_num':
                    attrs += ' NumberingContinue="false"'
            elif e.papel == 'capitulo':
                # Galerada: título y autores al principio del texto, con sus estilos, para
                # copiarlos en la portadilla de la Biblioteca de la publicación.
                from dataclasses import replace
                estilo = self.parrafo['capitulo_titulo']
                trozos = [replace(e.trozos[0], texto='%s. %s' % (e.datos['numero'], e.datos['titulo']), b=False, i=False)]
            else:
                estilo = self.parrafo[e.papel]
            # En ladillos y títulos la negrita la pone el estilo.
            quitar = e.papel in ('ladillo1', 'ladillo2', 'ladillo3', 'titulo_bibliografia', 'titulo_ideas', 'autores')
            partes.append(self.parrafo_xml(estilo, trozos, e.dudas, attrs, ultimo=k == len(visibles) - 1,
                                           quitar_negrita=quitar))
            anterior = e
        return self.documento(''.join(partes))

    # ---- piezas sueltas -----------------------------------------------------
    def pie_figura(self, e):
        """Pie con «Figura N.» en el estilo de carácter de la etiqueta."""
        trozos = espacios(list(e.trozos))       # antes de separar la etiqueta («Figura 1B .»)
        m = re.match(r'^\s*(Fig(?:ura|s)?\.?\s*\d+\s*[A-Za-z]?\s*[.:]?)', ''.join(t.texto for t in trozos))
        etiqueta = self.caracter.get('etiqueta_figura')
        if m and etiqueta:
            from dataclasses import replace
            n, resto = len(m.group(1)), []
            primero = []
            for t in trozos:
                if n <= 0:
                    resto.append(t)
                elif len(t.texto) <= n:
                    primero.append(t)
                    n -= len(t.texto)
                else:
                    primero.append(replace(t, texto=t.texto[:n]))
                    resto.append(replace(t, texto=t.texto[n:]))
                    n = 0
            texto_etq = ''.join(t.texto for t in primero)
            self.usados_c.add(etiqueta)
            etq = '<CharacterStyleRange AppliedCharacterStyle=%s><Content>%s</Content></CharacterStyleRange>' % (
                quoteattr(ref_estilo('CharacterStyle', etiqueta)), escape(texto_etq))
            estilo = self.parrafo['pie_figura']
            self.usados_p.add(estilo)
            self.estilo_actual = estilo
            cuerpo = etq + ''.join(self.rango(replace(t, b=False)) for t in resto if t.texto)
            xml = '<ParagraphStyleRange AppliedParagraphStyle=%s>%s</ParagraphStyleRange>' % (
                quoteattr(ref_estilo('ParagraphStyle', estilo)), cuerpo)
        else:
            xml = self.parrafo_xml(self.parrafo['pie_figura'], trozos, ultimo=True)
        return self.documento(xml)

    def tabla(self, titulo, tabla, pies, ancho_mm):
        """Título, tabla y notas al pie de la tabla. Celdas combinadas de Word respetadas."""
        t = self.conf.get('tabla', {})
        partes = []
        if titulo is not None:
            partes.append(self.parrafo_xml(self.parrafo['titulo_tabla'], titulo.trozos, titulo.dudas,
                                           quitar_negrita=True))
        partes.append(self.tabla_xml(tabla, ancho_mm, t, pies))
        return self.documento(''.join(partes))

    def tabla_xml(self, tabla, ancho_mm, t, pies=()):
        """La tabla; las notas que van debajo en el Word, en una fila de pie dentro de ella."""
        ident = 'tb%d' % tabla.indice
        ncol = len(tabla.anchos) or max(sum(c[0] for c in fila) for fila in tabla.combinadas)
        total = sum(tabla.anchos) or ncol
        anchos_pt = [(a or total / ncol) / total * ancho_mm * 72 / 25.4 for a in (tabla.anchos or [1] * ncol)]
        # Rejilla: para cada celda real, su columna, filas que ocupa (vMerge) y columnas.
        celdas = []
        for r, (fila, comb) in enumerate(zip(tabla.filas, tabla.combinadas)):
            col = 0
            for parrafos, (span, vm) in zip(fila, comb):
                if vm == 'continue':
                    col += span
                    continue
                rowspan = 1
                if vm == 'restart':
                    for r2 in range(r + 1, len(tabla.filas)):
                        c2, hecho = 0, False
                        for (sp2, vm2) in tabla.combinadas[r2]:
                            if c2 == col:
                                hecho = vm2 == 'continue'
                                break
                            c2 += sp2
                        if not hecho:
                            break
                        rowspan += 1
                celdas.append((r, col, rowspan, span, parrafos))
                col += span
        nfilas = len(tabla.filas)
        npie = 1 if pies else 0
        est_tabla = t.get('estilo', '')
        xml = ['<CharacterStyleRange AppliedCharacterStyle="%s"><Table Self="%s" HeaderRowCount="1" FooterRowCount="%d" '
               'BodyRowCount="%d" ColumnCount="%d"%s TableDirection="LeftToRightDirection">' % (
                   SIN_ESTILO, ident, npie, max(nfilas - 1, 0), ncol,
                   (' AppliedTableStyle=%s' % quoteattr(ref_estilo('TableStyle', est_tabla))) if est_tabla else '')]
        for r in range(nfilas + npie):
            xml.append('<Row Self="%sRow%d" Name="%d" AutoGrow="true"/>' % (ident, r, r))
        for c in range(ncol):
            xml.append('<Column Self="%sColumn%d" Name="%d" SingleColumnWidth="%.3f"/>' % (ident, c, c, anchos_pt[c]))
        for r, col, rowspan, span, parrafos in celdas:
            cab = r == 0
            est_celda = t.get('celda_cabecera' if cab else 'celda', '')
            est_par = self.parrafo['celda_cabecera' if cab else 'celda']
            ps = [p for p in parrafos] or []
            while len(ps) > 1 and not ps[-1].texto.strip():
                ps.pop()
            contenido = ''.join(
                self.parrafo_xml(est_par, _limpios(p.trozos), ultimo=k == len(ps) - 1, quitar_negrita=cab)
                for k, p in enumerate(ps))
            xml.append('<Cell Self="%si%di%d" Name="%d:%d" RowSpan="%d" ColumnSpan="%d"%s>%s</Cell>' % (
                ident, col, r, col, r, rowspan, span,
                (' AppliedCellStyle=%s' % quoteattr(ref_estilo('CellStyle', est_celda))) if est_celda else '',
                contenido))
        if pies:
            est_celda = t.get('celda_pie', '')
            contenido = ''.join(self.parrafo_xml(self.parrafo['pie_tabla'], _limpios(p.trozos), p.dudas,
                                                 ultimo=k == len(pies) - 1) for k, p in enumerate(pies))
            xml.append('<Cell Self="%si0i%d" Name="0:%d" RowSpan="1" ColumnSpan="%d"%s>%s</Cell>' % (
                ident, nfilas, nfilas, ncol,
                (' AppliedCellStyle=%s' % quoteattr(ref_estilo('CellStyle', est_celda))) if est_celda else '',
                contenido))
        xml.append('</Table></CharacterStyleRange>')
        estilo = self.parrafo['texto']
        self.usados_p.add(estilo)
        return '<ParagraphStyleRange AppliedParagraphStyle=%s>%s</ParagraphStyleRange>' % (
            quoteattr(ref_estilo('ParagraphStyle', estilo)), ''.join(xml))

    def texto_simple(self, estilo, texto, estilo_caracter=None):
        self.usados_p.add(estilo)
        if estilo_caracter:
            self.usados_c.add(estilo_caracter)
        return self.documento('<ParagraphStyleRange AppliedParagraphStyle=%s><CharacterStyleRange '
                              'AppliedCharacterStyle=%s><Content>%s</Content></CharacterStyleRange>'
                              '</ParagraphStyleRange>' % (
                                  quoteattr(ref_estilo('ParagraphStyle', estilo)),
                                  quoteattr(ref_estilo('CharacterStyle', estilo_caracter) if estilo_caracter else SIN_ESTILO),
                                  escape(texto)))

    # ---- envoltorio ---------------------------------------------------------
    def documento(self, cuerpo):
        grupos = {}
        for nombre in sorted(self.usados_p):
            grupo, _, hoja = nombre.rpartition('/')
            grupos.setdefault(grupo, []).append(nombre)
        defs_p = []
        for grupo, nombres in grupos.items():
            estilos = ''.join('<ParagraphStyle Self=%s Name=%s/>' % (
                quoteattr(ref_estilo('ParagraphStyle', n)), quoteattr(n.replace('/', ':'))) for n in nombres)
            if grupo:
                # Solo un nivel de grupo, como en la maqueta.
                defs_p.append('<ParagraphStyleGroup Self=%s Name=%s>%s</ParagraphStyleGroup>' % (
                    quoteattr('ParagraphStyleGroup/' + grupo), quoteattr(grupo), estilos))
            else:
                defs_p.append(estilos)
        # Solo las condiciones que lleva algún texto: las demás saldrían vacías en el panel.
        defs_cond = ''.join(
            '<Condition Self=%s Name=%s IndicatorColor="%s" IndicatorMethod="UseHighlight" '
            'UnderlineIndicatorAppearance="Wavy" Visible="true"/>' % (
                quoteattr(ref_condicion(n)), quoteattr(n), color) for n, color, _ in CONDICIONES
            if quoteattr(ref_condicion(n)) in cuerpo)
        defs_c = ''.join('<CharacterStyle Self=%s Name=%s/>' % (
            quoteattr(ref_estilo('CharacterStyle', n)), quoteattr(n)) for n in sorted(self.usados_c))
        return ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
                '<?aid style="50" type="snippet" readerVersion="6.0" featureSet="513" product="8.0(370)" ?>\n'
                '<?aid SnippetType="InCopyInterchange"?>\n'
                '<Document DOMVersion="8.0" Self="d">\n'
                '%s\n'
                '<RootCharacterStyleGroup Self="rcs"><CharacterStyle Self="%s" Name="$ID/[No character style]"/>'
                '%s</RootCharacterStyleGroup>\n'
                '<RootParagraphStyleGroup Self="rps">%s</RootParagraphStyleGroup>\n'
                '<Story Self="historia" AppliedTOCStyle="n" TrackChanges="false" StoryTitle="$ID/" AppliedNamedGrid="n">\n'
                '%s\n</Story>\n</Document>\n') % (defs_cond, SIN_ESTILO, defs_c, ''.join(defs_p), cuerpo)


ALFABETOS_RAROS = ('HEBREW', 'ARABIC', 'CYRILLIC', 'CJK', 'HANGUL', 'THAI', 'DEVANAGARI')


def _caracter_raro(c):
    """Caracteres que en un texto en español suelen ser un error del autor o de Word."""
    if c in '\t\n\u2028':
        return False
    cat = unicodedata.category(c)
    if cat in ('Co', 'Cn', 'Cc', 'Cs'):
        return True
    nombre = unicodedata.name(c, '')
    return any(nombre.startswith(a) for a in ALFABETOS_RAROS)


# Llamadas a tabla o figura entre paréntesis: «(Tabla 4)», «(ver Figuras 5A y 5B)», «(Fig. 2)».
RE_REFERENCIA = re.compile(r'\((?:[^()]*?\s)?(?:Tablas?|Figuras?|Figs?\.)\s*\d[^()]*\)')


# Limpiezas de espacios que se hacen siempre al importar (antes eran reglas de
# ortotipografia.toml; allí siguen para las galeradas anteriores y por si algo se escapa).
UNIDADES = r'%|mm|cm|µm|μm|nm|km|m|mg|µg|μg|ng|kg|g|ml|mL|dl|dL|l|L|h|min|s|mmHg|UI|°C|ºC|Hz'
RE_CIFRA_UNIDAD = re.compile(r'(?<=\d)([  ]?)(?:%s)(?![^\W_])' % UNIDADES)


def espacios(trozos):
    """Dos o más espacios → uno; sin espacio antes de . , ; : ) ] ni después de ( [; y espacio
    de no separación entre la cifra y su unidad («10%», «4 mm» → «10 %», «4 mm»)."""
    from dataclasses import replace
    texto = ''.join(t.texto for t in trozos)
    if not re.search(r' {2}| [.,;:)\]]|[(\[] |\d[  ]?(?:%s)' % UNIDADES, texto):
        return trozos
    # Carácter a carácter, cada uno con su trozo; luego se vuelven a juntar.
    chars = [(c, t) for t in trozos for c in t.texto]

    def cambiar(patron, nuevo):
        """nuevo(m, chars) → [(inicio, fin, [(carácter, trozo)…])], de atrás adelante."""
        txt = ''.join(c for c, _ in chars)
        for m in reversed(list(patron.finditer(txt))):
            for ini, fin, pon in nuevo(m):
                chars[ini:fin] = pon

    cambiar(re.compile(r' {2,}'), lambda m: [(m.start() + 1, m.end(), [])])
    cambiar(re.compile(r' +(?=[.,;:)\]])'), lambda m: [(m.start(), m.end(), [])])
    cambiar(re.compile(r'(?<=[(\[]) +'), lambda m: [(m.start(), m.end(), [])])

    def cifra(m):
        cifra_t, unidad_t = chars[m.start() - 1][1], chars[m.end(1)][1]
        # No en una llamada volada («visión² m…») ni con la unidad en superíndice.
        if cifra_t.pos or unidad_t.pos or cifra_t.nota:
            return []
        if m.group(1) == ' ':
            return []
        return [(m.start(1), m.end(1), [(' ', chars[m.start(1)][1] if m.group(1) else unidad_t)])]
    cambiar(RE_CIFRA_UNIDAD, cifra)

    res = []
    for c, t in chars:
        if res and res[-1][1] is t:
            res[-1][0].append(c)
        else:
            res.append(([c], t))
    return [replace(t, texto=''.join(cs)) for cs, t in res]


def puntuacion_tras_referencias(trozos):
    """«inflamatorias. (Figura 10)» → «inflamatorias (Figura 10).», como con las citas. Si detrás
    sigue minúscula no se mueve y queda como duda."""
    from dataclasses import replace
    texto = ''.join(t.texto for t in trozos)
    casos = [m for m in re.finditer(r'([.,;:])(\s+)(' + RE_REFERENCIA.pattern + ')', texto)]
    if not casos:
        return trozos
    # Carácter a carácter, cada uno con su trozo; luego se vuelven a juntar.
    chars = [(c, t) for t in trozos for c in t.texto]
    for m in reversed(casos):
        p, ref = m.start(1), m.start(3)
        signo = chars[p]
        if texto[m.end():].lstrip()[:1].islower():
            con_duda = {}
            for k in range(ref, m.end()):
                t = chars[k][1]
                if id(t) not in con_duda:
                    con_duda[id(t)] = replace(t, duda=t.duda or
                                              'Llamada a figura o tabla con «%s» delante: ¿pasa detrás?' % signo[0])
                chars[k] = (chars[k][0], con_duda[id(t)])
            continue
        # El espacio nuevo toma el formato del signo, que venía del texto de delante.
        chars[p:m.end()] = [(' ', signo[1])] + chars[ref:m.end()] + [signo]
    res = []
    for c, t in chars:
        if res and res[-1][1] is t:
            res[-1][0].append(c)
        else:
            res.append(([c], t))
    return [replace(t, texto=''.join(cs)) for cs, t in res]


def referencias_sin_formato(trozos):
    """Las llamadas a tabla o figura entre paréntesis van en redonda, sin estilo de carácter:
    se les quita negrita, cursiva, subrayado y superíndice aunque los traigan del Word."""
    from dataclasses import replace
    texto = ''.join(t.texto for t in trozos)
    zonas = [m.span() for m in RE_REFERENCIA.finditer(texto)]
    if not zonas:
        return trozos
    res, ini = [], 0
    for t in trozos:
        fin = ini + len(t.texto)
        cortes = sorted({ini, fin} | {x for z in zonas for x in z if ini < x < fin})
        for a, b in zip(cortes, cortes[1:]):
            dentro = any(z0 <= a and b <= z1 for z0, z1 in zonas)
            res.append(replace(t, texto=t.texto[a - ini:b - ini], b=False, i=False, u=False, pos='')
                       if dentro else replace(t, texto=t.texto[a - ini:b - ini]))
        ini = fin
    return res


def _limpios(trozos):
    from .clasificar import limpiar_bordes
    return limpiar_bordes(list(trozos))[0]
