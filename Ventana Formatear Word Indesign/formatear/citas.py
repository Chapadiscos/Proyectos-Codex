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


def crudo(texto):
    """Números de una cita tal como viene, de cualquier tipo o de varias unidas:
    '(4) (6,7,8)' → '4,6,7,8'   ·   '¹ ²' → '1,2'. Los espacios entre cifras valen como coma."""
    t = re.sub(r'[()]', ' ', texto.translate(A_SUPER)).strip()
    return re.sub(r'(?<=\d)\s+(?=\d)', ',', t)


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

    # 2b. Citas seguidas, separadas solo por espacios, en una sola (también entre tipos):
    #     «(4) (6,7,8) (12)» → (4,6–8,12)   ·   «texto¹ ²» → (1,2)
    #     No se une una cita en superíndice pegada a una cifra o unidad (¿exponente?).
    unidas = []
    for pieza in expandidas:
        if pieza[2]:
            j = len(unidas) - 1
            while j >= 0 and not unidas[j][2] and not unidas[j][0].strip():
                j -= 1
            if j >= 0 and unidas[j][2] and not (
                    unidas[j][3] in ('superíndice', 'unicode') and j and UNIDADES.search(unidas[j - 1][0])):
                hueco = ''.join(u[0] for u in unidas[j + 1:])
                texto_prev, base_prev, _, tipo_prev = unidas[j]
                del unidas[j:]
                unidas.append((texto_prev + hueco + pieza[0], base_prev, True, tipo_prev))
                continue
        unidas.append(pieza)
    expandidas = unidas

    # 3. Reescribir cada cita y mover la puntuación previa detrás de ella.
    salida, citas = [], []
    for k, (texto, base, es_cita, tipo) in enumerate(expandidas):
        if not es_cita:
            if texto:
                salida.append(replace(base, texto=texto))
            continue
        nums = numeros(crudo(texto))
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
        # Puntuación final del texto anterior → detrás de la cita. Con espacio en medio
        # («utilizado. (4)») también, salvo que siga en minúscula: «fases: (1) la primera…»
        # puede ser una enumeración → se deja y se marca como duda.
        previo = ''.join(t.texto for t in salida)
        if previo.rstrip()[-1:] in tuple('.,;:') and previo[-1:].isspace():
            if siguiente.lstrip()[:1].islower():
                if not dudosa:
                    dudosa = '«%s» delante: ¿pasa detrás o es una enumeración?' % previo.rstrip()[-1]
                    citas[-1].dudosa = dudosa
            else:
                while salida and salida[-1].texto[-1:].isspace():
                    salida[-1] = replace(salida[-1], texto=salida[-1].texto.rstrip())
                    if not salida[-1].texto:
                        salida.pop()
        puntuacion = ''
        while salida and salida[-1].texto[-1:] in tuple('.,;:'):
            puntuacion = salida[-1].texto[-1] + puntuacion
            salida[-1] = replace(salida[-1], texto=salida[-1].texto[:-1])
            if not salida[-1].texto:
                salida.pop()
        if salida and salida[-1].texto and not salida[-1].texto[-1].isspace():
            nuevo = ' ' + nuevo
        # La cita va en redonda, sin estilo de carácter, aunque en el Word fuera en negrita o cursiva.
        salida.append(replace(base, texto=nuevo, pos='', nota=0, b=False, i=False, u=False, duda=('Cita: ' + dudosa) if dudosa else ''))
        if puntuacion:
            salida.append(replace(base, texto=puntuacion, pos='', nota=0))
    return [t for t in salida if t.texto], citas
