"""Informe HTML de la clasificación de un capítulo, para revisarlo antes de importar."""
import html
from collections import Counter

from . import citas as mod_citas

NOMBRES = {
    'capitulo': 'Capítulo', 'autores': 'Autores', 'ladillo1': 'Ladillo 1', 'ladillo2': 'Ladillo 2',
    'ladillo3': 'Ladillo 3', 'texto': 'Texto', 'texto_vineta': 'Texto de viñeta', 'vineta': 'Viñeta',
    'lista_num': 'Lista numerada',
    'titulo_ideas': 'Título Ideas', 'texto_ideas': 'Texto Ideas', 'titulo_bibliografia': 'Título bibliografía',
    'bibliografia': 'Bibliografía', 'titulo_tabla': 'Título tabla', 'tabla': 'Tabla', 'pie_tabla': 'Pie tabla',
    'pie_figura': 'Pie figura', 'imagen': 'Imagen', 'rotulo_material': 'Rótulo (se omite)',
    'etiqueta_imagen': 'Etiqueta (se omite)',
}
COLORES = {
    'capitulo': '#7b1fa2', 'autores': '#7b1fa2', 'ladillo1': '#c62828', 'ladillo2': '#ef6c00',
    'ladillo3': '#f9a825', 'texto': '#9e9e9e', 'texto_vineta': '#81c784', 'vineta': '#2e7d32', 'lista_num': '#558b2f',
    'titulo_ideas': '#00838f', 'texto_ideas': '#00838f', 'titulo_bibliografia': '#1565c0',
    'bibliografia': '#1565c0', 'titulo_tabla': '#6d4c41', 'tabla': '#6d4c41', 'pie_tabla': '#6d4c41',
    'pie_figura': '#ad1457', 'imagen': '#ad1457', 'rotulo_material': '#bdbdbd', 'etiqueta_imagen': '#bdbdbd',
}
OMITIDOS = ('rotulo_material', 'etiqueta_imagen')


def estilo_de(e, conf):
    p = conf['parrafo']
    if e.papel == 'capitulo':
        return '%s + %s + %s' % (p['capitulo_palabra'], p['capitulo_numero'], p['capitulo_titulo'])
    if e.papel == 'vineta':
        return p['vineta%d' % max(e.nivel, 1)]
    if e.papel == 'lista_num':
        return p['vineta%d' % max(e.nivel, 1)] + ' + numeración'
    return p.get(e.papel, '')


def trozos_html(trozos):
    out = []
    for t in trozos:
        s = html.escape(t.texto).replace('\t', '<span class="tab">⇥</span>')
        if t.pos == 'sup':
            s = '<sup>%s</sup>' % s
        elif t.pos == 'sub':
            s = '<sub>%s</sub>' % s
        if t.i:
            s = '<i>%s</i>' % s
        if t.b:
            s = '<b>%s</b>' % s
        out.append(s)
    return ''.join(out)


def generar(nombre, ruta_docx, elementos, modo, figuras, sobrantes, conf):
    n_bib = sum(1 for e in elementos if e.papel == 'bibliografia')
    conf_c = conf.get('citas', {})
    todas_citas = []
    filas = []
    for e in elementos:
        if e.papel == 'tabla':
            t = e.tabla
            ncol = max((len(f) for f in t.filas), default=0)
            cab = ' · '.join(' '.join(p.texto for p in c)[:30] for c in t.filas[0]) if t.filas else ''
            contenido = '<span class="meta">%d filas × %d columnas — 1.ª fila: %s</span>' % (
                len(t.filas), ncol, html.escape(cab))
        elif e.papel == 'imagen':
            contenido = '<span class="meta">%d imagen(es) incrustada(s): %s</span>' % (
                len(e.imagenes), html.escape(', '.join(i.split('/')[-1] for i in e.imagenes)))
        else:
            trozos, citas = (e.trozos, [])
            if e.papel not in ('bibliografia', 'titulo_tabla', 'pie_figura', 'capitulo') + OMITIDOS:
                trozos, citas = mod_citas.normalizar(e.trozos, n_bib, conf_c.get('rango_minimo', 3),
                                                     conf_c.get('guion', '\u2013'))
            todas_citas.extend((e.origen, c) for c in citas)
            contenido = trozos_html(trozos)
            if citas:
                contenido += '<div class="citas">' + ' '.join(
                    '<span class="cita%s">%s → %s%s</span>' % (
                        ' dudosa' if c.dudosa else '', html.escape(c.original), html.escape(c.nuevo),
                        (' — ' + html.escape(c.dudosa)) if c.dudosa else '')
                    for c in citas) + '</div>'
            if e.papel == 'capitulo':
                contenido += '<div class="meta">«Capítulo» · «%s» · «%s»</div>' % (
                    html.escape(e.datos['numero']), html.escape(e.datos['titulo']))
            if e.datos.get('versales'):
                contenido += '<div class="meta">en Word, todo en mayúsculas</div>'
        avisos = ''.join('<div class="duda">⚠ %s</div>' % html.escape(d) for d in e.dudas)
        avisos += ''.join('<div class="nota">✎ %s</div>' % html.escape(n) for n in e.notas)
        papel = NOMBRES.get(e.papel, e.papel) + (' %d' % e.nivel if e.papel == 'vineta' else '')
        filas.append('<tr class="%s%s"><td class="n">%d%s</td><td class="papel" style="border-left-color:%s">%s'
                     '<div class="estilo">%s</div></td><td class="txt nivel%d">%s%s</td></tr>' % (
                         e.papel, ' conduda' if e.dudas else '', e.origen,
                         '<br><span class="meta">nota</span>' if e.procedencia != 'cuerpo' else '',
                         COLORES.get(e.papel, '#999'), papel, html.escape(estilo_de(e, conf)),
                         e.nivel if e.papel in ('vineta', 'lista_num') else 0, contenido, avisos))

    cuenta = Counter(NOMBRES.get(e.papel, e.papel) for e in elementos)
    n_dudas = sum(1 for e in elementos if e.dudas)
    tipos = Counter(c.tipo for _, c in todas_citas)
    dudosas = [(o, c) for o, c in todas_citas if c.dudosa]

    fig_html = ''.join('<tr><td>%s</td><td>%s</td><td>%s</td><td class="aviso">%s</td></tr>' % (
        html.escape(fid), html.escape(pie[:110]), html.escape(', '.join(a)) or '—', html.escape(av))
        for fid, pie, a, av in figuras)
    tablas = [e for e in elementos if e.papel == 'titulo_tabla']

    return PLANTILLA.format(
        titulo=html.escape(nombre), docx=html.escape(ruta_docx),
        resumen=' · '.join('%s: %d' % kv for kv in sorted(cuenta.items(), key=lambda x: -x[1])),
        modo={None: 'No hay negritas con viñeta.',
              'ladillo': 'Las negritas cortas que en Word llevan viñeta se tratan como <b>ladillos</b> '
                         '(detrás suele ir texto corrido).',
              'vineta': 'Las negritas cortas que en Word llevan viñeta se tratan como <b>viñetas en negrita</b> '
                        '(detrás suelen ir más viñetas); el texto corrido de esas secciones va como «Texto de viñeta».'}[modo],
        n_dudas=n_dudas,
        citas='%d citas (%s); referencias en la bibliografía: %d' % (
            len(todas_citas), ', '.join('%s: %d' % kv for kv in tipos.items()) or '—', n_bib),
        citas_dudosas=''.join('<li>Párrafo %d: %s → %s — %s</li>' % (o, html.escape(c.original),
                                                                     html.escape(c.nuevo), html.escape(c.dudosa))
                              for o, c in dudosas) or '<li>Ninguna</li>',
        figuras=fig_html or '<tr><td colspan="4">No se han encontrado pies de figura</td></tr>',
        sobrantes=html.escape(', '.join(sobrantes)) or 'ninguno',
        tablas=''.join('<li>%s</li>' % html.escape(e.texto[:120]) for e in tablas) or '<li>Ninguna</li>',
        filas='\n'.join(filas))


PLANTILLA = '''<!doctype html>
<html lang="es"><head><meta charset="utf-8"><title>{titulo} · clasificación</title>
<style>
:root {{ color-scheme: light dark; --fondo:#fff; --texto:#222; --suave:#777; --linea:#e4e4e4; --duda:#fff4d6; }}
@media (prefers-color-scheme: dark) {{ :root {{ --fondo:#1e1e1e; --texto:#ddd; --suave:#999; --linea:#333; --duda:#3a3220; }} }}
body {{ font: 14px/1.45 -apple-system, "Helvetica Neue", sans-serif; background:var(--fondo); color:var(--texto); margin:24px; }}
h1 {{ font-size:20px; margin:0 0 4px; }} h2 {{ font-size:16px; margin:28px 0 8px; }}
.sub {{ color:var(--suave); margin-bottom:16px; }}
table {{ border-collapse:collapse; width:100%; }}
td, th {{ border-bottom:1px solid var(--linea); padding:6px 8px; vertical-align:top; text-align:left; }}
td.n {{ color:var(--suave); width:36px; font-variant-numeric:tabular-nums; }}
td.papel {{ width:170px; border-left:5px solid; font-weight:600; }}
.estilo {{ font-weight:400; color:var(--suave); font-size:12px; }}
.meta {{ color:var(--suave); font-size:12px; }}
.nivel2 {{ padding-left:28px; }} .nivel3 {{ padding-left:48px; }} .nivel4 {{ padding-left:68px; }}
tr.conduda td.txt {{ background:var(--duda); }}
.duda {{ color:#b26a00; font-size:12px; margin-top:3px; }} .nota {{ color:var(--suave); font-size:12px; margin-top:3px; }}
.citas {{ margin-top:3px; }} .cita {{ font-size:12px; background:rgba(21,101,192,.12); border-radius:3px; padding:0 4px; margin-right:4px; }}
.cita.dudosa {{ background:rgba(230,120,0,.2); }}
.tab {{ color:var(--suave); }} td.aviso {{ color:#b26a00; }}
tr.rotulo_material td, tr.etiqueta_imagen td {{ opacity:.5; }}
.filtro {{ margin:8px 0; }}
</style></head><body>
<h1>{titulo}</h1><div class="sub">{docx}</div>
<p>{resumen}</p>
<p>{modo}</p>
<p><b>{n_dudas}</b> párrafos con dudas (fondo amarillo). <label class="filtro"><input type="checkbox" id="solo"> Ver solo los dudosos</label></p>
<h2>Citas</h2><p>{citas}</p><ul>{citas_dudosas}</ul>
<h2>Figuras</h2>
<table><tr><th>Figura</th><th>Pie</th><th>Archivo suelto</th><th>Aviso</th></tr>{figuras}</table>
<p class="meta">Archivos de imagen sin pie: {sobrantes}</p>
<h2>Tablas</h2><ul>{tablas}</ul>
<h2>Párrafos</h2>
<table id="parrafos"><tr><th>Word</th><th>Papel → estilo</th><th>Texto tal como quedará</th></tr>
{filas}
</table>
<script>
document.getElementById('solo').addEventListener('change', function () {{
  document.querySelectorAll('#parrafos tr:not(.conduda)').forEach(function (tr, i) {{
    if (i) tr.style.display = this.checked ? 'none' : '';
  }}, this);
}});
</script>
</body></html>
'''
