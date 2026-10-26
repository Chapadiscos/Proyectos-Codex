"""Citas bibliográficas: localizar las que vienen en superíndice, en caracteres Unicode
(⁹), como llamada de nota final o entre paréntesis, y escribirlas todas igual:
entre paréntesis, ordenadas y con los rangos abreviados → (1,3–6,12).
"""
import re
from dataclasses import dataclass, replace

SUPER = '⁰¹²³⁴⁵⁶⁷⁸⁹'
A_SUPER = str.maketrans(SUPER + '⁻˒', '0123456789-,')
RE_UNICODE = re.compile('[%s]+(?:[⁻˒,–-][%s]+)*' % (SUPER, SUPER))
RE_PARENTESIS = re.compile(r'\(\s*(\d{1,3}(?:\s*[,–-]\s*\d{1,3})*)\s*\)')
RE_NUMEROS = re.compile(r'^[\d\s,–-]+$')
UNIDADES = re.compile(r'(?:\b(?:m|mm|cm|km|µm|dm|mg|kg)|\d)$')


@dataclass
class Cita:
    original: str
    numeros: list
    nuevo: str
    tipo: str            # 'superíndice' | 'unicode' | 'nota final' | 'paréntesis'
    dudosa: str = ''     # motivo, si conviene revisarla


def numeros(texto):
    """'3,5-7' → [3, 5, 6, 7]"""
    res = []
    for parte in re.split(r'\s*,\s*', texto.strip(' ,')):
        if not parte:
            continue
        m = re.match(r'^(\d+)\s*[–-]\s*(\d+)$', parte)
        if m and int(m.group(1)) < int(m.group(2)):
            res.extend(range(int(m.group(1)), int(m.group(2)) + 1))
        elif parte.isdigit():
            res.append(int(parte))
    return res


def compactar(nums, rango_minimo=3, guion='\u2013'):
    """[1,3,4,5,6,12] → '1,3-6,12'. Dos seguidos (3,4) se dejan con coma."""
    nums = sorted(set(nums))
    trozos, i = [], 0
    while i < len(nums):
        j = i
        while j + 1 < len(nums) and nums[j + 1] == nums[j] + 1:
            j += 1
        if j - i + 1 >= rango_minimo:
            trozos.append('%d%s%d' % (nums[i], guion, nums[j]))
        else:
            trozos.extend(str(n) for n in nums[i:j + 1])
        i = j + 1
    return ','.join(trozos)


def normalizar(trozos, n_bibliografia=0, rango_minimo=3, guion='\u2013'):
    """Devuelve (trozos nuevos, citas encontradas). Los trozos de cita pierden el
    superíndice; la puntuación que iba delante de la cita pasa detrás: «texto.³» → «texto (3).»"""
    # 1. Unir en una sola marca los superíndices numéricos y las llamadas de nota seguidas.
    piezas = []   # (texto, trozo base, es_cita, tipo)
    for t in trozos:
        if t.nota:
            tipo = 'nota final'
        elif t.pos == 'sup' and RE_NUMEROS.match(t.texto) and any(c.isdigit() for c in t.texto):
            tipo = 'superíndice'
        else:
            tipo = None
        if tipo and piezas and piezas[-1][2]:
            texto_prev, base, _, tipo_prev = piezas[-1]
            sep = '' if texto_prev.endswith(',') or t.texto.startswith(',') else ','
            piezas[-1] = (texto_prev + sep + t.texto, base, True, tipo_prev)
        else:
            piezas.append((t.texto, t, bool(tipo), tipo))

    # 2. Buscar las citas Unicode y entre paréntesis dentro del texto normal.
    expandidas = []
    for texto, base, es_cita, tipo in piezas:
        if es_cita or base.pos:
            expandidas.append((texto, base, es_cita, tipo))
            continue
        pos = 0
        patrones = [(m, 'unicode') for m in RE_UNICODE.finditer(texto)] + \
                   [(m, 'paréntesis') for m in RE_PARENTESIS.finditer(texto)]
        for m, tp in sorted(patrones, key=lambda x: x[0].start()):
            if m.start() < pos:
                continue
            expandidas.append((texto[pos:m.start()], base, False, None))
            expandidas.append((m.group(0), base, True, tp))
            pos = m.end()
        expandidas.append((texto[pos:], base, False, None))

    # 3. Reescribir cada cita y mover la puntuación previa detrás de ella.
    salida, citas = [], []
    for k, (texto, base, es_cita, tipo) in enumerate(expandidas):
        if not es_cita:
            if texto:
                salida.append(replace(base, texto=texto))
            continue
        crudo = texto.translate(A_SUPER) if tipo == 'unicode' else texto
        if tipo == 'paréntesis':
            crudo = RE_PARENTESIS.match(crudo).group(1)
        nums = numeros(crudo)
        nuevo = '(%s)' % compactar(nums, rango_minimo, guion)
        anterior = ''.join(t.texto for t in salida)
        siguiente = next((x[0] for x in expandidas[k + 1:] if x[0]), '')
        dudosa = ''
        if tipo in ('superíndice', 'unicode') and UNIDADES.search(anterior):
            dudosa = 'va pegada a una cifra o unidad: ¿exponente?'
        elif siguiente[:1].isalpha():
            dudosa = 'va en medio de una palabra'
        elif n_bibliografia and any(n > n_bibliografia for n in nums):
            dudosa = 'número mayor que las %d referencias' % n_bibliografia
        elif tipo == 'paréntesis' and len(nums) == 1 and n_bibliografia == 0:
            dudosa = 'número suelto entre paréntesis'
        citas.append(Cita(texto, nums, nuevo, tipo, dudosa))
        if dudosa.startswith('va pegada'):
            salida.append(replace(base, texto=texto, duda='¿Cita o exponente? ' + dudosa))
            continue
        if dudosa == 'va en medio de una palabra':
            # «inmunodeprimido¹s.» → «inmunodeprimidos (1).»: el resto de la palabra pasa delante.
            for j in range(k + 1, len(expandidas)):
                resto = expandidas[j][0]
                if resto:
                    m = len(resto) - len(resto.lstrip('abcdefghijklmnopqrstuvwxyzáéíóúüñABCDEFGHIJKLMNOPQRSTUVWXYZÁÉÍÓÚÜÑ'))
                    salida.append(replace(expandidas[j][1], texto=resto[:m]))
                    expandidas[j] = (resto[m:],) + expandidas[j][1:]
                    break
            dudosa = 'iba en medio de la palabra: revisar'
            citas[-1].dudosa = dudosa
        # Puntuación final del texto anterior → detrás de la cita.
        puntuacion = ''
        while salida and salida[-1].texto[-1:] in tuple('.,;:'):
            puntuacion = salida[-1].texto[-1] + puntuacion
            salida[-1] = replace(salida[-1], texto=salida[-1].texto[:-1])
            if not salida[-1].texto:
                salida.pop()
        if salida and salida[-1].texto and not salida[-1].texto[-1].isspace():
            nuevo = ' ' + nuevo
        salida.append(replace(base, texto=nuevo, pos='', nota=0, duda=('Cita: ' + dudosa) if dudosa else ''))
        if puntuacion:
            salida.append(replace(base, texto=puntuacion, pos='', nota=0))
    return [t for t in salida if t.texto], citas
