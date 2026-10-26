"""Compara la clasificación con los estilos de los capítulos ya maquetados.

1. En InDesign: pruebas/volcar_maquetados.jsx (abre ocultos los .indd de «Maquetados»,
   vuelca párrafos y estilos a pruebas/volcados/ y los cierra sin guardar).
2. python3 pruebas/comparar_maquetados.py
"""
import sys, os, glob, re, unicodedata, tomllib, collections
RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(RAIZ)
sys.path.insert(0, RAIZ)
from formatear.docx import Documento
from formatear.clasificar import clasificar
from formatear.informe import estilo_de
conf = tomllib.load(open('publicaciones/maqueta-base.toml', 'rb'))
S = os.path.join(RAIZ, 'pruebas', 'volcados')
def clave(t):
    t = unicodedata.normalize('NFKD', t.lower())
    return re.sub(r'[^a-z0-9]', '', t)[:22]
tot = ok = 0
for c in ['5', '7', '8', '9']:
    lin = open('%s/%02d Maquetado.txt' % (S, int(c)), encoding='utf-8').read().replace('\r', '\n').split('\n')
    maq = collections.defaultdict(list)
    for l in lin:
        m = re.match(r'^\[([^\]]+)\](?: \[[^\]]*\])? ?(.*)$', l)
        if m and clave(m.group(2).replace('<anclado>', '')):
            maq[clave(m.group(2).replace('<anclado>', ''))].append(m.group(1).split('/')[-1] + (' +num' if 'lista local' in l else ''))
    els, modo = clasificar(Documento(glob.glob('Documentos Word/Capitulo %s/*.docx' % c)[0]))
    fallos = []
    n = k = 0
    for e in els:
        if e.papel in ('tabla', 'imagen', 'rotulo_material', 'etiqueta_imagen', 'capitulo', 'pie_figura', 'titulo_tabla', 'pie_tabla'):
            continue
        mio = estilo_de(e, conf).split('/')[-1].replace(' + numeración', ' +num')
        cands = maq.get(clave(e.texto))
        if not cands:
            continue
        suyo = cands.pop(0)
        n += 1
        if suyo == mio:
            k += 1
        else:
            fallos.append('   %3d %-22s maquetado: %-22s %s' % (e.origen, mio, suyo, e.texto[:60]))
    tot += n; ok += k
    print('Cap %s (%s): %d/%d coinciden (%.0f %%)' % (c, modo, k, n, 100 * k / n))
    print('\n'.join(fallos))
print('TOTAL %d/%d (%.0f %%)' % (ok, tot, 100 * ok / tot))
