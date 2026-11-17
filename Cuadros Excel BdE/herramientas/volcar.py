#!/usr/bin/env python3
"""Vuelca un .xlsx para comparar versiones: por hoja, anchos de columna, celdas combinadas, altos de fila y cada
celda con su valor y su formato [letra|relleno|bordes|alineación|número]; al final, las formas de cada dibujo.
Uso: volcar.py <libro.xlsx> [hoja]"""
import sys, zipfile, html
import xml.etree.ElementTree as ET
NS = {'m': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main',
      'r': 'http://schemas.openxmlformats.org/officeDocument/2006/relationships',
      'xdr': 'http://schemas.openxmlformats.org/drawingml/2006/spreadsheetDrawing',
      'a': 'http://schemas.openxmlformats.org/drawingml/2006/main'}


def q(t):
    p, n = t.split(':')
    return '{%s}%s' % (NS[p], n)


z = zipfile.ZipFile(sys.argv[1])
solo = sys.argv[2] if len(sys.argv) > 2 else None
ss = []
if 'xl/sharedStrings.xml' in z.namelist():
    for si in ET.fromstring(z.read('xl/sharedStrings.xml')).findall('m:si', NS):
        ss.append(''.join(t.text or '' for t in si.iter(q('m:t'))))
st = ET.fromstring(z.read('xl/styles.xml'))


def col(e):
    if e is None:
        return ''
    a = e.attrib
    s = a.get('rgb') or ('th%s' % a['theme'] if 'theme' in a else ('ix%s' % a['indexed'] if 'indexed' in a else ('auto' if a.get('auto') else '')))
    if 'tint' in a:
        s += '%+.2f' % float(a['tint'])
    return s


fonts = []
for f in st.find('m:fonts', NS):
    n = f.find('m:name', NS); s = f.find('m:sz', NS)
    d = [(n.get('val') if n is not None else '?') + ' ' + (s.get('val') if s is not None else '?')]
    for k in ('b', 'i', 'u'):
        if f.find('m:' + k, NS) is not None and f.find('m:' + k, NS).get('val', '1') != '0':
            d.append(k)
    c = col(f.find('m:color', NS))
    if c:
        d.append('c=' + c)
    fonts.append(' '.join(d))
fills = []
for f in st.find('m:fills', NS):
    p = f.find('m:patternFill', NS)
    if p is None:
        fills.append('?'); continue
    t = p.get('patternType', 'none')
    fills.append('' if t == 'none' else (t if t != 'solid' else '') + '#' + col(p.find('m:fgColor', NS)))
borders = []
for b in st.find('m:borders', NS):
    d = []
    for side in ('left', 'right', 'top', 'bottom'):
        e = b.find('m:' + side, NS)
        if e is not None and e.get('style'):
            d.append(side[0] + ':' + e.get('style') + '/' + col(e.find('m:color', NS)))
    borders.append(' '.join(d))
numfmts = {n.get('numFmtId'): n.get('formatCode') for n in st.iter(q('m:numFmt'))}
xfs = []
for x in st.find('m:cellXfs', NS):
    a = x.attrib
    al = x.find('m:alignment', NS)
    ald = ' '.join('%s=%s' % (k, v) for k, v in al.attrib.items()) if al is not None else ''
    nf = a.get('numFmtId', '0')
    xfs.append(dict(font=fonts[int(a.get('fontId', 0))], fill=fills[int(a.get('fillId', 0))],
                    border=borders[int(a.get('borderId', 0))], al=ald, nf=numfmts.get(nf, nf)))
wb = ET.fromstring(z.read('xl/workbook.xml'))
rmap = {r.get('Id'): r.get('Target') for r in ET.fromstring(z.read('xl/_rels/workbook.xml.rels'))}
for s in wb.find('m:sheets', NS):
    if solo and s.get('name') != solo:
        continue
    tgt = 'xl/' + rmap[s.get(q('r:id'))].lstrip('/').replace('xl/', '')
    print('##### HOJA', s.get('name'), '|', tgt, s.get('state', ''))
    sh = ET.fromstring(z.read(tgt))
    fmt = sh.find('m:sheetFormatPr', NS)
    print('formato', fmt.attrib if fmt is not None else '')
    cols = sh.find('m:cols', NS)
    if cols is not None:
        print('COLS', ' | '.join('%s-%s:%s%s' % (c.get('min'), c.get('max'), c.get('width'), ' oculta' if c.get('hidden') else '') for c in cols))
    mc = sh.find('m:mergeCells', NS)
    if mc is not None:
        print('MERGE', ' '.join(m.get('ref') for m in mc))
    for row in sh.iter(q('m:row')):
        cells = []
        for c in row.findall('m:c', NS):
            v = c.find('m:v', NS); f = c.find('m:f', NS)
            val = v.text if v is not None else ''
            if c.get('t') == 's' and val:
                val = ss[int(val)]
            isel = c.find('m:is', NS)
            if isel is not None:
                val = ''.join(t.text or '' for t in isel.iter(q('m:t')))
            x = xfs[int(c.get('s', 0))]
            if not val and not x['fill'] and not x['border']:
                continue
            cells.append('  %s %r%s\n      [%s|%s|%s|%s|%s]' % (c.get('r'), val[:60], ' f=' + f.text[:40] if f is not None and f.text else '',
                                                             x['font'], x['fill'], x['border'], x['al'], x['nf']))
        if cells or row.get('ht'):
            print('FILA', row.get('r'), 'alto', row.get('ht'), 'oculta' if row.get('hidden') else '')
            for c in cells:
                print(c)
    srels = 'xl/worksheets/_rels/' + tgt.split('/')[-1] + '.rels'
    if srels in z.namelist():
        for r in ET.fromstring(z.read(srels)):
            if 'drawing' in r.get('Type'):
                dr = ET.fromstring(z.read('xl/drawings/' + r.get('Target').split('/')[-1]))
                for anc in dr:
                    nombres = [n.get('name') for n in anc.iter(q('xdr:cNvPr'))]
                    fr = anc.find('xdr:from', NS)
                    pos = '%s:%s+%s,%s' % tuple(fr.find('xdr:' + k, NS).text for k in ('col', 'row', 'colOff', 'rowOff')) if fr is not None else ''
                    off = anc.find('.//a:xfrm/a:off', NS); ext = anc.find('.//a:xfrm/a:ext', NS)
                    caja = ('%.1f,%.1f %.1fx%.1f mm' % (int(off.get('x')) / 36000, int(off.get('y')) / 36000, int(ext.get('cx')) / 36000, int(ext.get('cy')) / 36000)) if off is not None and ext is not None else ''
                    txt = ' / '.join(''.join(t.text or '' for t in p.iter(q('a:t'))) for p in anc.iter(q('a:p')))
                    print('FORMA', anc.tag.split('}')[1], nombres[:3], pos, caja, repr(txt[:120]))
