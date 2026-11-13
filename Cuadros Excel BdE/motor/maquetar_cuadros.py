#!/usr/bin/env python3
"""Motor de «Cuadros Excel BdE»: maqueta paso a paso el Excel del cuadro que entrega el autor.

Réplica de «Gráficos Excel BdE» para cuadros. Trabaja sobre una copia; cada paso deja su versión en la
carpeta de pasos para poder ir hacia delante y hacia atrás. Toca el .xlsx por dentro (XML), sin Excel, y
deja intacto todo lo que el paso no cambia.

Uso (la salida es siempre JSON):
  maquetar_cuadros.py empezar <origen.xlsx>
  maquetar_cuadros.py estado  <trabajo.xlsx>
  maquetar_cuadros.py ir      <trabajo.xlsx> <n>
  maquetar_cuadros.py reiniciar <trabajo.xlsx>
  maquetar_cuadros.py paso1..paso4 <trabajo.xlsx> <id_publicacion>
  maquetar_cuadros.py terminar <trabajo.xlsx>
  maquetar_cuadros.py info    <archivo.xlsx>
  maquetar_cuadros.py publicaciones
  maquetar_cuadros.py guardar_publicacion '<json>'
  maquetar_cuadros.py borrar_publicacion <id>
  maquetar_cuadros.py paletas [actualizar]
"""
import colorsys
import difflib
from collections import Counter
import html
import io
import math
import json
import os
import re
import shutil
import struct
import sys
import uuid
import zipfile
from pathlib import Path, PurePosixPath

MOTOR = Path(__file__).resolve().parent
PROYECTO = MOTOR.parent
ARCHIVO_CONFIG = MOTOR / "publicaciones.json"
CONFIG = json.loads(ARCHIVO_CONFIG.read_text(encoding="utf-8"))

# Paletas de colores (temas) que Excel tiene instaladas
CARPETA_PALETAS = Path.home() / "Library/Group Containers/UBF8T346G9.Office/User Content.localized/Themes.localized/Theme Colors"
CLAVES_PALETA = ["dk1", "lt1", "dk2", "lt2", "accent1", "accent2", "accent3", "accent4", "accent5", "accent6"]
ANCLA = re.compile(r'<xdr:(twoCellAnchor|oneCellAnchor|absoluteAnchor)\b[^>]*>.*?</xdr:\1>', re.S)
EMU_PT = 12700


class Fallo(Exception):
    pass


# ---------------------------------------------------------------- archivos

def nombres(trabajo):
    trabajo = Path(trabajo)
    return trabajo, trabajo.with_name(trabajo.stem + " (pasos)")


def leer_estado(trabajo):
    _, pasos = nombres(trabajo)
    f = pasos / "estado.json"
    if not f.exists():
        raise Fallo(f"No hay pasos para {Path(trabajo).name}: empieza por «empezar».")
    return json.loads(f.read_text(encoding="utf-8"))


def guardar_estado(trabajo, estado):
    _, pasos = nombres(trabajo)
    (pasos / "estado.json").write_text(json.dumps(estado, ensure_ascii=False, indent=2), encoding="utf-8")


def idioma(nombre):
    # «Ing» suelto («C_Ing_…», «… Ing») o pegado a la letra del tipo de figura («CIng_…»)
    return "en" if re.search(r'(^|[ _\-.])[A-Z]?Ing([ _\-.]|$)', Path(nombre).stem) else "es"


RE_TABLE = re.compile(r'\s*Table\s+\S+\s*$')


def rotulo_en_ingles(origen):
    """¿El rótulo del cuadro es «Table N» (cuadro en inglés aunque el nombre del archivo no lo diga)?"""
    try:
        with zipfile.ZipFile(origen) as z:
            for n in z.namelist():
                if re.fullmatch(r'xl/drawings/drawing\d+\.xml', n):
                    for a in ANCLA.finditer(z.read(n).decode("utf-8")):
                        for linea in texto_forma(a.group(0)).split("\n"):
                            if RE_TABLE.match(html.unescape(linea)):
                                return True
    except (zipfile.BadZipFile, KeyError):
        pass
    return False


def nombre_trabajo(origen):
    """«X ORIGINAL(ES).xlsx» o «X.xlsx» → «X maquetado.xlsx», junto al original."""
    return origen.with_name(origen.stem + " maquetado.xlsx")


def empezar(origen):
    origen = Path(origen).resolve()
    if not origen.exists():
        raise Fallo(f"No existe {origen}")
    trabajo, pasos = nombres(nombre_trabajo(origen))
    if pasos.exists():
        raise Fallo(f"Ya hay una maquetación empezada: {pasos.name}. Bórrala o sigue con ella.")
    with zipfile.ZipFile(origen) as z:
        hoja, motivo_hoja = hoja_cuadro(z)
    pasos.mkdir()
    v0 = pasos / "00 Copia exacta.xlsx"
    shutil.copyfile(origen, v0)
    solo_lectura(v0)
    shutil.copyfile(origen, trabajo)
    lengua, motivo = idioma(origen.name), "por el nombre del archivo"
    if lengua == "es" and rotulo_en_ingles(origen):
        lengua, motivo = "en", "por «Table N» en el cuadro"
    estado = {"origen": str(origen), "idioma": lengua, "motivo_idioma": motivo, "hoja": hoja,
              "motivo_hoja": motivo_hoja, "actual": 0,
              "pasos": [{"n": 0, "titulo": "Copia exacta del original", "archivo": v0.name, "detalle": []}]}
    guardar_estado(trabajo, estado)
    return {"trabajo": str(trabajo), **estado}


def borrar_generados(trabajo):
    """Borra todo lo que genera la maquetación de un original: las dos copias de trabajo, la carpeta de pasos
    entera y los archivos de bloqueo de Excel («~$…») de las copias. El original del autor no se toca."""
    trabajo, pasos = nombres(trabajo)
    borrados = []
    copias = [trabajo, trabajo.with_name(trabajo.stem + " (2).xlsx")]
    for c in copias + [c.with_name("~$" + c.name) for c in copias]:
        if c.exists():
            if not c.name.startswith("~$"):
                borrados.append(c.name)
            os.chmod(c, 0o644)
            c.unlink()
    if pasos.is_dir() and pasos.name.endswith(" (pasos)"):
        for f in pasos.iterdir():
            os.chmod(f, 0o644)
        shutil.rmtree(pasos)
        borrados.append(pasos.name)
    return borrados


def reiniciar(trabajo):
    """Vuelve a empezar desde el original del autor, como si se abriera por primera vez: borra las copias de
    trabajo y la carpeta de pasos enteras (con lo guardado desde Excel) y hace de nuevo «00 Copia exacta»."""
    estado = leer_estado(trabajo)
    origen = Path(estado.get("origen", ""))
    if not origen.is_file():
        raise Fallo(f"No encuentro el original del autor ({origen}): no puedo reiniciar")
    borrados = borrar_generados(trabajo)
    return {**empezar(origen), "borrados": borrados}


def ir(trabajo, n):
    estado = leer_estado(trabajo)
    n = int(n)
    if not 0 <= n < len(estado["pasos"]):
        raise Fallo(f"No existe el paso {n}")
    _, pasos = nombres(trabajo)
    shutil.copyfile(pasos / estado["pasos"][n]["archivo"], trabajo)
    estado["actual"] = n
    guardar_estado(trabajo, estado)
    return {"trabajo": str(trabajo), **estado}


def solo_lectura(archivo):
    """Las versiones se ven en Excel tal cual: en solo lectura, para que guardar desde Excel no las cambie."""
    os.chmod(archivo, 0o444)


def nuevo_paso(trabajo, titulo, cambios, detalle, extra=None):
    """Aplica `cambios` (ruta interna → bytes) sobre la versión actual y la guarda como paso siguiente.
    Los pasos que hubiera por delante se descartan, como al deshacer y volver a hacer."""
    estado = leer_estado(trabajo)
    _, pasos = nombres(trabajo)
    actual = estado["actual"]
    for p in estado["pasos"][actual + 1:]:
        (pasos / p["archivo"]).unlink(missing_ok=True)
    del estado["pasos"][actual + 1:]
    n = actual + 1
    archivo = f"{n:02d} {titulo}.xlsx"
    reescribir_zip(pasos / estado["pasos"][actual]["archivo"], pasos / archivo, cambios)
    solo_lectura(pasos / archivo)
    shutil.copyfile(pasos / archivo, trabajo)
    estado["pasos"].append({"n": n, "titulo": titulo, "archivo": archivo, "detalle": detalle, **({"cuadro": extra} if extra else {})})
    estado["actual"] = n
    guardar_estado(trabajo, estado)
    return {"trabajo": str(trabajo), **estado}


def reescribir_zip(origen, destino, cambios):
    """Copia el .xlsx entrada a entrada, en el mismo orden y compresión; solo cambia las de `cambios`."""
    en_memoria = isinstance(destino, io.BytesIO)
    tmp = destino if en_memoria else Path(str(destino) + ".tmp")
    with zipfile.ZipFile(origen) as zin, zipfile.ZipFile(tmp, "w") as zout:
        for info in zin.infolist():
            datos = cambios.get(info.filename)
            zout.writestr(info, datos if datos is not None else zin.read(info.filename))
    if not en_memoria:
        os.replace(tmp, destino)


# ---------------------------------------------------------------- xlsx por dentro

def resolver(base, destino):
    if destino.startswith("/"):
        return destino.lstrip("/")
    partes = []
    for p in (PurePosixPath(base).parent / destino).parts:
        if p == "..":
            partes.pop()
        elif p != ".":
            partes.append(p)
    return "/".join(partes)


def rels(z, parte):
    p = PurePosixPath(parte)
    ruta = f"{p.parent}/_rels/{p.name}.rels"
    if ruta not in z.namelist():
        return {}
    xml = z.read(ruta).decode("utf-8")
    return {m.group(1): (m.group(2), resolver(parte, m.group(3)))
            for m in re.finditer(r'<Relationship\b(?=[^>]*\bId="([^"]+)")(?=[^>]*\bType="([^"]+)")(?=[^>]*\bTarget="([^"]+)")[^>]*/>', xml)}


def hojas_libro(z):
    """[(nombre, ruta, visible)] de las hojas de cálculo del libro, en su orden."""
    wb = z.read("xl/workbook.xml").decode("utf-8")
    relaciones = rels(z, "xl/workbook.xml")
    hojas = []
    for m in re.finditer(r'<sheet\b[^>]*/>', wb):
        nombre = re.search(r'\bname="([^"]*)"', m.group(0))
        rid = re.search(r'\br:id="([^"]+)"', m.group(0))
        if nombre and rid and rid.group(1) in relaciones and relaciones[rid.group(1)][1] in z.namelist() \
                and relaciones[rid.group(1)][0].endswith("/worksheet"):
            visible = not re.search(r'\bstate="(hidden|veryHidden)"', m.group(0))
            hojas.append((html.unescape(nombre.group(1)), relaciones[rid.group(1)][1], visible))
    return hojas


def hoja_de(z, nombre):
    for n, ruta, _ in hojas_libro(z):
        if n == nombre:
            return ruta
    raise Fallo(f"No hay hoja «{nombre}»")


def dibujo_de_hoja(z, hoja):
    for tipo, destino in rels(z, hoja_de(z, hoja)).values():
        if tipo.endswith("/drawing"):
            return destino
    return None


RE_CUADRO = re.compile(r'\s*(Cuadro|Table)\s+[A-Z]?\d', re.I)


def hoja_cuadro(z):
    """La hoja del cuadro: la primera visible con el rótulo «Cuadro N» en sus formas; si ninguna lo tiene, la
    primera visible (los autores la llaman «Cuadro datos», «Cua», «C1», «Cuadro 2»…)."""
    hojas = [h for h in hojas_libro(z) if h[2]]
    if not hojas:
        raise Fallo("El libro no tiene hojas visibles")
    for nombre, _, _ in hojas:
        dibujo = dibujo_de_hoja(z, nombre)
        if dibujo and dibujo in z.namelist():
            for a in ANCLA.finditer(z.read(dibujo).decode("utf-8")):
                if any(RE_CUADRO.match(html.unescape(l)) for l in texto_forma(a.group(0)).split("\n")):
                    return nombre, "tiene el rótulo «Cuadro N»"
    return hojas[0][0], "es la primera hoja visible (ninguna tiene el rótulo «Cuadro N»)"


def nombre_forma(ancla):
    return re.search(r'<xdr:cNvPr\b[^>]*\bname="([^"]*)"', ancla).group(1)


def tamano(ancla, escala_grupo=False):
    """Tamaño en EMU. Para la retícula, el de diseño (chExt)."""
    m = re.search(r'<a:chExt cx="(\d+)" cy="(\d+)"/>' if escala_grupo else r'<a:ext cx="(\d+)" cy="(\d+)"/>', ancla)
    return int(m.group(1)), int(m.group(2))


# Matices del color de la publicación, como los de Excel (Resumen cuadros, pág. 22): 1-3 más claros
# (80, 60 y 40 %) y 4-5 más oscuros (25 y 50 %). La pastilla es el matiz 1 (comprobado con el archivo de
# retículas: 004081 → B3D9FF, F06800 → FFE0C9, A32938 → F3CED3).
TINTES = {"solido": 0, "matiz1": 0.8, "matiz2": 0.6, "matiz3": 0.4, "matiz4": -0.25, "matiz5": -0.5}


def matiz(color, tinte):
    """Color con el tinte de Excel (luminosidad HLS: + aclara hacia el blanco, − oscurece)."""
    r, g, b = (int(color[i:i + 2], 16) / 255 for i in (0, 2, 4))
    h, l, s = colorsys.rgb_to_hls(r, g, b)
    l = l * (1 + tinte) if tinte < 0 else l * (1 - tinte) + tinte
    return "".join(f"{round(x * 255):02X}" for x in colorsys.hls_to_rgb(h, l, s))


def matices(color):
    return {k: matiz(color, t) for k, t in TINTES.items()}


def publicacion(pid):
    for p in CONFIG["publicaciones"]:
        if p["id"] == pid:
            return p
    raise Fallo(f"No conozco la publicación «{pid}»")


# ---------------------------------------------------------------- textos (de «Gráficos Excel BdE»)

ROBOTO, ROBOTO_MEDIUM, ROBOTO_LIGHT = "Roboto", "Roboto Medium", "Roboto Light"


PROPIEDADES_LETRA = re.compile(r'<a:(rPr|endParaRPr|defRPr)\b([^>]*?)(/>|>(.*?)</a:\1>)', re.S)


# Norma general (usuario, 2026-11-05): todos los textos del gráfico, en negro
NEGRO = '<a:solidFill><a:srgbClr val="000000"/></a:solidFill>'


RELLENOS_TEXTO = ("noFill", "solidFill", "gradFill", "blipFill", "pattFill", "grpFill")


YA_NEGROS = ('<a:srgbClr val="000000"/>', '<a:schemeClr val="tx1"/>', '<a:schemeClr val="dk1"/>',
             '<a:prstClr val="black"/>', '<a:sysClr val="windowText" lastClr="000000"/>')


def hijos_a(cuerpo):
    """Hijos directos <a:…> de un trozo de XML, como [nombre, texto]."""
    lista, i = [], 0
    while True:
        m = re.compile(r'<a:(\w+)\b[^>]*?(/?)>').search(cuerpo, i)
        if not m:
            return lista
        nombre, fin = m.group(1), m.end()
        if not m.group(2):
            nivel = 1
            for t in re.compile(rf'<(/?)a:{nombre}\b[^>]*?(/?)>').finditer(cuerpo, fin):
                if t.group(2):
                    continue
                nivel += -1 if t.group(1) else 1
                if not nivel:
                    fin = t.end()
                    break
        lista.append([nombre, cuerpo[m.start():fin]])
        i = fin


def textos_en_negro(xml):
    """Todas las propiedades de letra (rPr, defRPr, endParaRPr) con relleno negro. Devuelve el xml y los
    colores que tenía antes lo que no era negro (para el detalle)."""
    antes = []

    def cambiar(m):
        etiqueta, atributos, dentro = m.group(1), m.group(2), m.group(4) or ""
        h = hijos_a(dentro)
        relleno = next((t for n, t in h if n in RELLENOS_TEXTO), None)
        if relleno and any(r in relleno for r in YA_NEGROS) and "<a:lumMod" not in relleno and "<a:lumOff" not in relleno:
            return m.group(0)
        if relleno or etiqueta == "rPr":
            if relleno:
                c = re.search(r'<a:(srgbClr|schemeClr|sysClr|prstClr)\b[^>]*\b(?:val|lastClr)="([^"]+)"', relleno)
                antes.append(c.group(2) if c else ("sin relleno" if "noFill" in relleno else "degradado/trama"))
        h = [x for x in h if x[0] not in RELLENOS_TEXTO]
        pos = 1 if h and h[0][0] == "ln" else 0
        h.insert(pos, ["solidFill", NEGRO])
        return f"<a:{etiqueta}{atributos}>" + "".join(t for _, t in h) + f"</a:{etiqueta}>"
    return PROPIEDADES_LETRA.sub(cambiar, xml), antes


def fijar_letra(xml, sz, fuente, quitar_negrita=None):
    """Pone tamaño (centésimas de punto; None lo deja) y familia a todas las propiedades de letra. El formato local del
    autor se respeta (cursiva, subrayado, índices y la negrita de una parte del texto); si todo el texto va
    en negrita, se quita, porque el peso lo da la familia (Roboto Medium, Roboto Light). Las letras por
    defecto (defRPr, endParaRPr) van sin negrita."""
    if quitar_negrita is None:
        quitar_negrita = todo_negrita(xml)

    def cambiar(m):
        etiqueta, atributos, dentro = m.group(1), m.group(2), m.group(4) or ""
        if sz is not None:
            atributos = re.sub(r'\ssz="[^"]*"', "", atributos) + f' sz="{sz}"'
        if etiqueta != "rPr" or quitar_negrita:
            atributos = re.sub(r'\sb="[^"]*"', "", atributos) + ' b="0"'
        dentro = re.sub(r'<a:(latin|ea)\b[^>]*/>', "", dentro)
        # latin y ea van detrás de relleno, efectos y subrayado, y delante de cs, sym, enlaces…
        sigue = re.search(r'<a:(cs|sym|hlinkClick|hlinkMouseOver|rtl|extLst)\b', dentro)
        pos = sigue.start() if sigue else len(dentro)
        dentro = dentro[:pos] + f'<a:latin typeface="{fuente}"/><a:ea typeface="{fuente}"/>' + dentro[pos:]
        return f"<a:{etiqueta}{atributos}>{dentro}</a:{etiqueta}>"
    return PROPIEDADES_LETRA.sub(cambiar, xml)


def todo_negrita(xml):
    """¿Va en negrita todo el texto (y no solo una parte)?"""
    runs = [m.group(1) or "" for m in RUN.finditer(xml) if html.unescape(m.group(3)).strip()]
    return bool(runs) and all(re.search(r'\sb="1"', r[:r.find(">") + 1]) for r in runs)


RUN = re.compile(r'<a:r>(<a:rPr\b[^>]*/>|<a:rPr\b[^>]*>.*?</a:rPr>)?(<a:t>|<a:t [^>]*>)(.*?)</a:t></a:r>', re.S)


ELEMENTO_PARRAFO = re.compile(r'<a:(?:r|fld)\b[^>]*>(<a:rPr\b[^>]*/>|<a:rPr\b[^>]*>.*?</a:rPr>)?.*?'
                              r'(?:<a:t>|<a:t [^>]*>)(.*?)</a:t>.*?</a:(?:r|fld)>|<a:br\b[^>]*/>|<a:br\b[^>]*>.*?</a:br>', re.S)


RPR_VACIO = '<a:rPr lang="es-ES"/>'


def lineas_de(xml):
    """El texto en líneas (párrafos, saltos de línea y retornos dentro del texto); cada línea es una lista
    de trozos (rPr, texto) con el formato de cada trozo."""
    lineas = []
    for p in re.findall(r'<a:p\b[^>]*>.*?</a:p>', xml, re.S):
        actual = []
        for m in ELEMENTO_PARRAFO.finditer(p):
            if m.group(0).startswith("<a:br"):
                lineas.append(actual)
                actual = []
                continue
            texto = html.unescape(m.group(2)).replace("_x000D_", "\r")
            for k, trozo in enumerate(re.split(r"\r\n|\r|\n", texto)):
                if k:
                    lineas.append(actual)
                    actual = []
                if trozo:
                    actual.append((m.group(1) or RPR_VACIO, trozo))
        lineas.append(actual)
    return lineas


def texto_de(trozos):
    return "".join(t for _, t in trozos)


def tramo(trozos, ini, fin, cambiar_rpr=None, cambiar_texto=None):
    """Aplica cambiar_rpr y cambiar_texto a los caracteres [ini, fin), partiendo los trozos donde caigan los cortes."""
    salida, pos = [], 0
    for rpr, t in trozos:
        a, b = pos, pos + len(t)
        pos = b
        cortes = sorted({a, b, min(max(ini, a), b), min(max(fin, a), b)})
        for c1, c2 in zip(cortes, cortes[1:]):
            trozo = t[c1 - a:c2 - a]
            if ini <= c1 and c2 <= fin:
                rpr2 = cambiar_rpr(rpr) if cambiar_rpr else rpr
                trozo = cambiar_texto(trozo) if cambiar_texto else trozo
                salida.append((rpr2, trozo))
            else:
                salida.append((rpr, trozo))
    return [(r, t) for r, t in salida if t]


def sin_principio(trozos, n):
    """Quita los n primeros caracteres y los espacios que vengan detrás."""
    trozos = tramo(trozos, 0, n, cambiar_texto=lambda t: "")
    resto = len(texto_de(trozos)) - len(texto_de(trozos).lstrip(" \t\u00a0"))
    return tramo(trozos, 0, resto, cambiar_texto=lambda t: "") if resto else trozos


def runs_xml(trozos):
    return "".join(f"<a:r>{rpr}<a:t>{html.escape(t, quote=False)}</a:t></a:r>" for rpr, t in trozos)


def con_atributos(rpr, atributos):
    """El rPr con estos atributos (nombre → valor) puestos en su etiqueta de apertura."""
    m = re.match(r'<a:rPr\b([^>]*?)(/?>)', rpr)
    resto = m.group(1)
    for nombre, valor in atributos.items():
        resto = re.sub(rf'\s{nombre}="[^"]*"', "", resto) + f' {nombre}="{valor}"'
    return f"<a:rPr{resto}{m.group(2)}" + rpr[m.end():]


def formato_local(rpr, con_negrita):
    """Los atributos de formato local del autor: cursiva, subrayado, tachado, índices y, si toca, negrita."""
    apertura = rpr[:rpr.find(">") + 1]
    nombres = ["i", "u", "strike", "baseline"] + (["b"] if con_negrita else [])
    return {n: v for n, v in re.findall(r'\s(\w+)="([^"]*)"', apertura) if n in nombres}


def texto_forma(xml):
    return "\n".join(texto_de(linea) for linea in lineas_de(xml))


ROTULO = re.compile(r'\s*(FUENTES|FUENTE|SOURCES|SOURCE|NOTAS|NOTA)\s*(:|\.|\s|$)', re.I)


# Nota con letra: «a.», «a)», «(a)», «a» + tabulador o «a» + espacio y mayúscula («a El ahorro…», 1.4)
NOTA_LETRA = re.compile(r'\s*\(?([a-z])(?:\.|\)|\t|[ \u00a0]+(?=[A-ZÁÉÍÓÚÑ«"“(]))[\t \u00a0]*')


SANGRIA_NOTA = round(8.5 * EMU_PT)


PPR_FUENTES = '<a:pPr marL="0" indent="0" algn="l"/>'


PPR_NOTA_LETRA = (f'<a:pPr marL="{SANGRIA_NOTA}" indent="-{SANGRIA_NOTA}" algn="l"><a:tabLst>'
                  f'<a:tab pos="{SANGRIA_NOTA}" algn="l"/></a:tabLst></a:pPr>')


EN_INGLES = {"FUENTE": "SOURCE", "FUENTES": "SOURCES"}


RE_FORMULA = re.compile(r'<a14:m>.*?</a14:m>', re.S)


def fuentes_con_formulas(ancla, idioma):
    """FUENTES con fórmulas de Office (ecuaciones: el cuadro va dos veces, con la fórmula y en texto de
    reserva, dentro de <mc:AlternateContent>). Rehacer los párrafos rompía el XML y Excel daba el libro por
    dañado («G_DO26XX_04»): aquí solo se cambia la letra (Roboto Light 7 pt; el rótulo, en Medium; las
    fórmulas no se tocan) y se avisa para revisar el resto a mano."""
    trozos, ultimo = [], 0
    for m in RE_FORMULA.finditer(ancla):
        trozos.append(fijar_letra(ancla[ultimo:m.start()], 700, ROBOTO_LIGHT, True))
        trozos.append(m.group(0))
        ultimo = m.end()
    trozos.append(fijar_letra(ancla[ultimo:], 700, ROBOTO_LIGHT, True))
    ancla = "".join(trozos)
    rotulos = []

    def rotulo(mc):
        # El rótulo de cada copia del cuadro (con fórmula y de reserva), en Roboto Medium y con «: »
        cuerpo = mc.group(0)
        r = re.search(r'<a:r>(<a:rPr\b.*?(?:/>|</a:rPr>))<a:t>([^<]*)</a:t></a:r>', cuerpo, re.S)
        if not r:
            return cuerpo
        texto = html.unescape(r.group(2))
        m = ROTULO.match(texto)
        if not m:
            return cuerpo
        nombre = m.group(1).upper()
        if idioma == "en":
            nombre = EN_INGLES.get(nombre, nombre)
        resto = texto[m.end():].lstrip()
        rpr = r.group(1)
        nuevo = (f'<a:r>{fijar_letra(rpr, 700, ROBOTO_MEDIUM, True) if not nombre.startswith("NOTA") else rpr}'
                 f'<a:t>{nombre}:</a:t></a:r><a:r>{rpr}<a:t> {html.escape(resto, quote=False)}</a:t></a:r>')
        rotulos.append(nombre + ":")
        return cuerpo.replace(r.group(0), nuevo, 1)
    ancla = re.sub(r'<xdr:txBody>.*?</xdr:txBody>', rotulo, ancla, flags=re.S)
    notas = [f"rótulo {', '.join(dict.fromkeys(rotulos))}" if rotulos else "sin rótulo reconocido",
             "Aviso: FUENTES lleva fórmulas: solo se ha cambiado la letra (las fórmulas, intactas); revisa a mano "
             "las notas con letra, las líneas en blanco y las comillas"]
    return ancla, notas


def maquetar_fuentes(ancla, idioma):
    """El marco de FUENTES con las reglas de «Gráficos Illus BdE»:
    - Rótulo FUENTE(S)/SOURCE(S)/NOTA(S) en mayúsculas y con dos puntos; en inglés, FUENTE → SOURCE.
      FUENTE(S)/SOURCE(S) en Roboto Medium y NOTA(S) en Light. Si la primera línea no lo tiene, «FUENTE:».
    - Notas con letra («a.» o «a» + tabulador): letra en Medium, tabulador y sangría francesa de 8,5 pt;
      las líneas siguientes sin letra ni rótulo se unen a la nota.
    - Una línea en blanco tras la fuente (salvo que siga una NOTA) y tras cada NOTA.
    Además, todo en Roboto Light 7 pt respetando el formato local del autor y, en castellano, comillas
    españolas y espacio (que no parte línea) entre la cifra y «%»; en inglés, «%» sin espacio."""
    if "<mc:AlternateContent" in ancla or "oMath" in ancla:
        return fuentes_con_formulas(ancla, idioma)
    quitar = todo_negrita(ancla)
    ancla = fijar_letra(ancla, 700, ROBOTO_LIGHT, quitar)

    def medium(rpr):
        return fijar_letra(rpr, 700, ROBOTO_MEDIUM, True)
    notas, cuenta = [], {"comillas": 0, "porcentajes": 0}
    abierta = [False]

    def ortotipografia(texto):
        if idioma == "es":
            salida = []
            for c in texto:
                if c == "“" or (c == '"' and not abierta[0]):
                    salida.append("«")
                    abierta[0] = True
                    cuenta["comillas"] += 1
                elif c == "”" or c == '"':
                    salida.append("»")
                    abierta[0] = False
                else:
                    salida.append(c)
            texto, n = re.subn(r"(\d)(?:[ \u202f]?)%", "\\1\u00a0%", "".join(salida))
        else:
            texto, n = re.subn(r"(\d)[ \u00a0\u202f]+%", r"\1%", texto)
        cuenta["porcentajes"] += n
        return texto
    lineas = [[(r, ortotipografia(t)) for r, t in linea] for linea in lineas_de(ancla)]
    lineas = [linea for linea in lineas if texto_de(linea).strip()]
    if not lineas:
        return ancla, notas

    parrafos = []          # [tipo, trozos]; tipo: fuente, nota, letra u otro
    rotulos, letras = [], 0
    for k, linea in enumerate(lineas):
        texto = texto_de(linea)
        rpr = linea[0][0]
        r = ROTULO.match(texto)
        if r or k == 0:
            nombre = r.group(1).upper() if r else "FUENTE"
            if idioma == "en":
                nombre = EN_INGLES.get(nombre, nombre)
            es_nota = nombre.startswith("NOTA")
            resto = sin_principio(linea, r.end()) if r else sin_principio(linea, 0)
            rotulo = [(rpr if es_nota else medium(rpr), nombre + ":"), (rpr, " ")]
            parrafos.append(["nota" if es_nota else "fuente", rotulo + resto])
            rotulos.append(nombre + ":" + ("" if r else " (añadido)"))
            continue
        n = NOTA_LETRA.match(texto)
        if n:
            parrafos.append(["letra", [(medium(rpr), n.group(1)), (rpr, "\t")] + sin_principio(linea, n.end())])
            letras += 1
        elif parrafos[-1][0] == "letra":
            parrafos[-1][1] += [(rpr, " ")] + sin_principio(linea, 0)
        else:
            parrafos.append(["otro", linea])

    # La fuente acaba en punto (plantilla y ejemplos: «FUENTE: Banco de España.»)
    for tipo, trozos in parrafos:
        if tipo == "fuente" and trozos and not texto_de(trozos).rstrip().endswith((".", ":")):
            rpr, t = trozos[-1]
            trozos[-1] = (rpr, t.rstrip() + ".")
            cuenta["punto"] = cuenta.get("punto", 0) + 1
    fin_parrafo = fijar_letra('<a:endParaRPr lang="es-ES"/>', 700, ROBOTO_LIGHT, True)
    vacio = f"<a:p>{PPR_FUENTES}{fin_parrafo}</a:p>"
    xml, blancos = "", 0
    for k, (tipo, trozos) in enumerate(parrafos):
        ppr = PPR_NOTA_LETRA if tipo == "letra" else PPR_FUENTES
        xml += f"<a:p>{ppr}{runs_xml(trozos)}{fin_parrafo}</a:p>"
        if k + 1 < len(parrafos):
            blanco = parrafos[k + 1][0] != "nota" if k == 0 else tipo == "nota"
            if blanco:
                xml += vacio
                blancos += 1
    ancla = re.sub(r'(<a:lstStyle/>|<a:lstStyle>.*?</a:lstStyle>)(.*)(</xdr:txBody>)',
                   lambda m: m.group(1) + xml + m.group(3), ancla, count=1, flags=re.S)

    notas.append(", ".join(f"«{r}»" for r in rotulos) + " en mayúsculas")
    if letras:
        notas.append(f"notas con letra y sangría de 8,5 pt ({letras})")
    if blancos:
        notas.append(f"líneas en blanco entre párrafos ({blancos})")
    if cuenta["comillas"]:
        notas.append(f"comillas españolas ({cuenta['comillas']})")
    if cuenta["porcentajes"]:
        notas.append(("espacio antes de «%»" if idioma == "es" else "«%» sin espacio") + f" ({cuenta['porcentajes']})")
    if cuenta.get("punto"):
        notas.append("punto final en la fuente")
    if quitar:
        notas.append("sin la negrita general del autor")
    return ancla, notas


def posicion(ancla):
    m = re.search(r'<a:off x="(-?\d+)" y="(-?\d+)"/>', ancla)
    return (int(m.group(1)), int(m.group(2))) if m else (0, 0)


def altos_filas(z, nombre):
    """Alto de cada fila en EMU (las que no están, el alto por defecto; las ocultas, 0)."""
    hoja = z.read(hoja_de(z, nombre)).decode("utf-8")
    formato = re.search(r'<sheetFormatPr\b[^>]*\bdefaultRowHeight="([\d.]+)"', hoja)
    defecto = round(float(formato.group(1) if formato else 15) * EMU_PT)
    altos = {}
    for m in re.finditer(r'<row\b[^>]*>', hoja):
        fila = m.group(0)
        r = int(re.search(r'\br="(\d+)"', fila).group(1)) - 1
        ht = re.search(r'\bht="([\d.]+)"', fila)
        altos[r] = 0 if 'hidden="1"' in fila else round(float(ht.group(1)) * EMU_PT) if ht else defecto
    return altos, defecto


def celda_de(filas, y):
    """Fila y desplazamiento (EMU) donde cae la altura y."""
    altos, defecto = filas
    r = 0
    while y >= altos.get(r, defecto) and r < 1048575:
        y -= altos.get(r, defecto)
        r += 1
    return r, y


def margenes(ancla):
    """Márgenes internos del cuadro de texto (EMU): izquierda, arriba, derecha, abajo."""
    body = re.search(r'<a:bodyPr\b[^>]*>', ancla)
    valores = []
    for nombre, defecto in (("lIns", 91440), ("tIns", 45720), ("rIns", 91440), ("bIns", 45720)):
        m = body and re.search(rf'\b{nombre}="(\d+)"', body.group(0))
        valores.append(int(m.group(1)) if m else defecto)
    return valores


def lineas_parrafos(parrafos, ancho_pt, sz, medir):
    """Líneas que ocupan los párrafos, partiendo por palabras como Excel, en un ancho dado."""
    total = 0
    espacio = medir(" ", sz)
    for texto in parrafos:
        lineas, actual = 1, 0.0
        for palabra in texto.split():
            w = medir(palabra, sz)
            if actual and actual + espacio + w > ancho_pt:
                lineas, actual = lineas + 1, w
            else:
                actual += (espacio if actual else 0) + w
        total += lineas
    return total


def textos_lineas(ancla):
    return [html.unescape(texto_de(linea)) for linea in lineas_de(ancla) if texto_de(linea).strip()]


def interlineado(ancla, pt, fuente):
    """Distancia entre líneas (pt) del párrafo del cuadro: el alto de línea de la fuente (hhea, como Excel)
    por el interlineado del párrafo (sencillo si no lleva)."""
    ruta = next((c / fuente for c in CARPETAS_FUENTES if (c / fuente).exists()), None)
    factor = 1.171875   # Roboto: (1900 + 500) / 2048
    if ruta:
        d = ruta.read_bytes()
        tablas = {struct.unpack(">4sIII", d[12 + 16 * i:28 + 16 * i])[0]: struct.unpack(">4sIII", d[12 + 16 * i:28 + 16 * i])[2]
                  for i in range(struct.unpack(">H", d[4:6])[0])}
        em = struct.unpack(">H", d[tablas[b"head"] + 18:tablas[b"head"] + 20])[0]
        sube, baja, hueco = struct.unpack(">hhh", d[tablas[b"hhea"] + 4:tablas[b"hhea"] + 10])
        factor = (sube - baja + hueco) / em
    linea = re.search(r'<a:lnSpc>\s*<a:(spcPct|spcPts) val="(\d+)"', ancla)
    if linea and linea.group(1) == "spcPts":
        return int(linea.group(2)) / 100
    return pt * factor * (int(linea.group(2)) / 100000 if linea else 1)


_medidores = {}
CARPETAS_FUENTES = [Path.home() / "Library/Fonts", Path("/Library/Fonts"), Path("/System/Library/Fonts/Supplemental"),
                    Path("/Applications/Microsoft Excel.app/Contents/Resources/DFonts")]


def medidor(archivo="Roboto-Regular.ttf"):
    """Función (texto, puntos) → ancho en puntos, con los avances de la fuente instalada (sin kerning).
    None si la fuente no está."""
    if archivo in _medidores:
        return _medidores[archivo]
    ruta = next((c / archivo for c in CARPETAS_FUENTES if (c / archivo).exists()), None)
    medir = None
    if ruta:
        d = ruta.read_bytes()
        tablas = {}
        for i in range(struct.unpack(">H", d[4:6])[0]):
            etiqueta, _, desp, _ = struct.unpack(">4sIII", d[12 + 16 * i:28 + 16 * i])
            tablas[etiqueta.decode("latin-1")] = desp
        em = struct.unpack(">H", d[tablas["head"] + 18:tablas["head"] + 20])[0]
        n = struct.unpack(">H", d[tablas["hhea"] + 34:tablas["hhea"] + 36])[0]
        avances = struct.unpack(f">{2 * n}H", d[tablas["hmtx"]:tablas["hmtx"] + 4 * n])[::2]
        glifos = cmap_unicode(d, tablas["cmap"])
        medir = lambda texto, pt: sum(avances[min(glifos.get(ord(c), 0), n - 1)] for c in texto) / em * pt
    _medidores[archivo] = medir
    return medir


def cmap_unicode(d, c):
    """Carácter → glifo, de la subtabla Unicode BMP (plataforma 3, formato 4)."""
    glifos = {}
    for i in range(struct.unpack(">H", d[c + 2:c + 4])[0]):
        plataforma, _, desp = struct.unpack(">HHI", d[c + 4 + 8 * i:c + 12 + 8 * i])
        s = c + desp
        if plataforma != 3 or struct.unpack(">H", d[s:s + 2])[0] != 4:
            continue
        k = struct.unpack(">H", d[s + 6:s + 8])[0] // 2
        fines = struct.unpack(f">{k}H", d[s + 14:s + 14 + 2 * k])
        b = s + 16 + 2 * k
        inicios = struct.unpack(f">{k}H", d[b:b + 2 * k])
        deltas = struct.unpack(f">{k}h", d[b + 2 * k:b + 4 * k])
        r = b + 4 * k
        rangos = struct.unpack(f">{k}H", d[r:r + 2 * k])
        for j in range(k):
            for ch in range(inicios[j], min(fines[j], 0xFFFE) + 1):
                if rangos[j] == 0:
                    glifos[ch] = (ch + deltas[j]) & 0xFFFF
                else:
                    p = r + 2 * j + rangos[j] + 2 * (ch - inicios[j])
                    g = struct.unpack(">H", d[p:p + 2])[0]
                    glifos[ch] = (g + deltas[j]) & 0xFFFF if g else 0
        break
    return glifos


def anclar_arriba_izquierda(ancla, cx, cy):
    """Ancla de una celda en A1 con el tamaño exacto, sea cual sea el ancho de columnas y alto de filas."""
    cuerpo = re.search(r'</xdr:to>(.*)</xdr:twoCellAnchor>', ancla, re.S).group(1)
    cuerpo = re.sub(r'(<a:xfrm>\s*<a:off) x="\d+" y="\d+"/>\s*<a:ext cx="\d+" cy="\d+"/>',
                    rf'\1 x="0" y="0"/><a:ext cx="{cx}" cy="{cy}"/>', cuerpo, count=1)
    return ('<xdr:oneCellAnchor><xdr:from><xdr:col>0</xdr:col><xdr:colOff>0</xdr:colOff>'
            '<xdr:row>0</xdr:row><xdr:rowOff>0</xdr:rowOff></xdr:from>'
            f'<xdr:ext cx="{cx}" cy="{cy}"/>{cuerpo}</xdr:oneCellAnchor>')


def renumerar(ancla, siguiente_id, nombre):
    """Ids nuevos (no pueden repetirse en el dibujo), creationId nuevos y nombre de la forma principal."""
    contador = [siguiente_id]

    def nuevo_id(m):
        contador[0] += 1
        return f'{m.group(1)}id="{contador[0] - 1}"'
    ancla = re.sub(r'(<xdr:cNvPr\s)id="\d+"', nuevo_id, ancla)
    ancla = re.sub(r'(<a16:creationId\b[^>]*\bid=")\{[^}]+\}',
                   lambda m: m.group(1) + "{" + str(uuid.uuid4()).upper() + "}", ancla)
    ancla = re.sub(r'(<xdr:cNvPr\b[^>]*\bname=")[^"]*', lambda m: m.group(1) + nombre, ancla, count=1)
    return ancla, contador[0]


def color_relleno(ancla, color):
    def cambiar(m):
        return re.sub(r'<a:solidFill>.*?</a:solidFill>', f'<a:solidFill><a:srgbClr val="{color}"/></a:solidFill>',
                      m.group(0), count=1, flags=re.S)
    return re.sub(r'<xdr:spPr>.*?</xdr:spPr>', cambiar, ancla, count=1, flags=re.S)


def color_de(ancla):
    sppr = re.search(r'<xdr:spPr>.*?</xdr:spPr>', ancla, re.S)
    m = sppr and re.search(r'<a:solidFill>\s*<a:(srgbClr val="(\w+)"|schemeClr val="(\w+)")', sppr.group(0))
    return (m.group(2) or m.group(3)) if m else None


def partes_dibujo(dibujo):
    """El dibujo troceado en texto suelto y anclas, para cambiar solo algunas anclas."""
    pos = 0
    for m in ANCLA.finditer(dibujo):
        yield dibujo[pos:m.start()]
        yield m.group(0)
        pos = m.end()
    yield dibujo[pos:]


def requiere(estado, titulos, paso):
    """Los pasos van en orden: el anterior tiene que estar en la versión de la que se parte. `titulos` admite
    también los nombres de antes (las versiones ya hechas con los pasos separados siguen valiendo)."""
    if not any(p["titulo"] in titulos for p in estado["pasos"][:estado["actual"] + 1]):
        raise Fallo(f"Antes hay que hacer el paso «{titulos[0]}»: {paso} parte de él")


def medidas_hoja(z, hoja_nombre, dibujo):
    """Función ancla → (x, y, ancho, alto) en EMU desde A1, por las celdas de anclaje (las que usa Excel; el
    xfrm de dentro puede estar desfasado). Las filas, por su alto; las columnas, con lo que mide una unidad
    de ancho de columna en este dibujo (como en anchos_graficos)."""
    filas = altos_filas(z, hoja_nombre)
    altos, defecto = filas
    hoja = z.read(hoja_de(z, hoja_nombre)).decode("utf-8")
    cols = [(int(a), int(b), float(w)) for a, b, w in
            re.findall(r'<col\b[^>]*?\bmin="(\d+)"[^>]*?\bmax="(\d+)"[^>]*?\bwidth="([\d.]+)"', hoja)]
    dc = re.search(r'\bdefaultColWidth="([\d.]+)"', hoja)
    dc = float(dc.group(1)) if dc else 8.43

    def suma_cols(c):
        return sum(next((w for a, b, w in cols if a <= i + 1 <= b), dc) for i in range(c))
    medidas = []
    for m in ANCLA.finditer(dibujo):
        c = re.search(r'<xdr:from><xdr:col>(\d+)</xdr:col><xdr:colOff>(-?\d+)</xdr:colOff>.*?'
                      r'<xdr:to><xdr:col>(\d+)</xdr:col><xdr:colOff>(-?\d+)</xdr:colOff>', m.group(0), re.S)
        ext = re.search(r'<a:ext cx="(\d+)"', m.group(0))
        if c and ext and int(ext.group(1)) > 0:
            c1, o1, c2, o2 = map(int, c.groups())
            if suma_cols(c2) > suma_cols(c1):
                medidas.append((int(ext.group(1)) - o2 + o1) / (suma_cols(c2) - suma_cols(c1)))
    unidad = sorted(medidas)[len(medidas) // 2] if medidas else 7 * 9525

    def fila_y(r, off):
        return sum(altos.get(i, defecto) for i in range(r)) + off

    def medir(ancla):
        pos = re.search(r'<xdr:pos x="(-?\d+)" y="(-?\d+)"/>\s*<xdr:ext cx="(\d+)" cy="(\d+)"/>', ancla)
        if pos:
            return tuple(map(int, pos.groups()))
        d = re.search(r'<xdr:from><xdr:col>(\d+)</xdr:col><xdr:colOff>(-?\d+)</xdr:colOff>'
                      r'<xdr:row>(\d+)</xdr:row><xdr:rowOff>(-?\d+)</xdr:rowOff></xdr:from>', ancla)
        c, co, r, ro = map(int, d.groups())
        x, y = round(unidad * suma_cols(c)) + co, fila_y(r, ro)
        h = re.search(r'<xdr:to><xdr:col>(\d+)</xdr:col><xdr:colOff>(-?\d+)</xdr:colOff>'
                      r'<xdr:row>(\d+)</xdr:row><xdr:rowOff>(-?\d+)</xdr:rowOff></xdr:to>', ancla)
        if h:
            c2, co2, r2, ro2 = map(int, h.groups())
            return x, y, round(unidad * suma_cols(c2)) + co2 - x, fila_y(r2, ro2) - y
        e = re.search(r'<xdr:ext cx="(\d+)" cy="(\d+)"/>', ancla)
        return x, y, int(e.group(1)), int(e.group(2))

    def a_celda(x, y):
        """(col, colOff, fila, rowOff) del punto (x, y) en EMU desde A1."""
        c = 0
        while round(unidad * suma_cols(c + 1)) <= x and c < 16000:
            c += 1
        r = 0
        while fila_y(r + 1, 0) <= y and r < 100000:
            r += 1
        return c, round(x - round(unidad * suma_cols(c))), r, round(y - fila_y(r, 0))
    medir.a_celda = a_celda
    medir.unidad = unidad
    return medir


# ---------------------------------------------------------------- pasos

RETICULA_Y_TEXTOS = "Retícula, pastilla y textos"
MM = 72 / 25.4                 # puntos por milímetro
EMU_MM = 36000
# Final de párrafo del título que va en Roboto Regular (como en Gráficos): letras de nota entre paréntesis
# («(a)», «(a) (b)», «(a, b)») o la continuación, en castellano «(cont.)» y en inglés «(cont'd)»
FINAL_TITULO = re.compile(r"\s*((?:\((?:[a-zñ](?:\s*,\s*[a-zñ])*|cont\.|cont['’]d)\)\s*)+)$", re.I)
RE_CUADRO_LINEA = re.compile(r'\s*(Cuadro|Table)\s+[A-Z]?\d+(?:\.\d+)*\s*$', re.I)


def caja_mm(ancla, caja):
    return tuple(v / EMU_MM for v in caja(ancla))


def sin_texto(ancla):
    return not re.search(r'<a:t>\s*[^<\s]', ancla)


def sin_relleno(trozo):
    sppr = re.search(r'<xdr:spPr\b.*?</xdr:spPr>', trozo, re.S)
    return not sppr or "<a:solidFill>" not in re.sub(r'<a:ln\b.*?</a:ln>', "", sppr.group(0), flags=re.S)


def es_reticula(ancla):
    """Retícula (de la plantilla nueva o antigua): un rectángulo o un grupo de rectángulos, sin texto ni relleno,
    de página entera (al menos 15 × 20 cm). La antigua puede ir suelta («7 Rectángulo» rojo) o en grupo con
    los colores del tema."""
    if not sin_texto(ancla) or "<c:chart " in ancla or "<xdr:pic" in ancla:
        return False
    tam = re.search(r'<a:(?:chExt|ext) cx="(\d+)" cy="(\d+)"/>', ancla)
    if not tam or int(tam.group(1)) < 150 * EMU_MM or int(tam.group(2)) < 200 * EMU_MM:
        return False
    formas = re.findall(r'<xdr:sp\b.*?</xdr:sp>', ancla, re.S)
    return bool(formas) and all('prst="rect"' in f and sin_relleno(f) for f in formas)


def es_pastilla(ancla):
    """Rectángulo de color sin texto pegado arriba a la izquierda (hasta 1 mm del origen): la pastilla."""
    if "<xdr:sp" not in ancla[:800] or "<xdr:grpSp>" in ancla[:1500] or not sin_texto(ancla) or 'prst="rect"' not in ancla:
        return False
    if sin_relleno(ancla):
        return False
    desde = re.search(r'<xdr:from>\s*<xdr:col>(\d+)</xdr:col>\s*<xdr:colOff>(\d+)</xdr:colOff>\s*<xdr:row>(\d+)</xdr:row>'
                      r'\s*<xdr:rowOff>(\d+)</xdr:rowOff>', ancla)
    pos = re.search(r'<xdr:pos x="(\d+)" y="(\d+)"/>', ancla)
    if desde:
        return desde.group(1) == "0" and desde.group(3) == "0" and int(desde.group(2)) <= EMU_MM and int(desde.group(4)) <= EMU_MM
    return bool(pos) and int(pos.group(1)) <= EMU_MM and int(pos.group(2)) <= EMU_MM


def plantilla():
    """Las formas de la hoja «Cuadro» del archivo de retículas, por nombre."""
    ret = CONFIG["reticula"]
    with zipfile.ZipFile(PROYECTO / ret["archivo"]) as zr:
        dibujo = zr.read(dibujo_de_hoja(zr, ret["hoja"])).decode("utf-8")
    anclas = {nombre_forma(a.group(0)): a.group(0) for a in ANCLA.finditer(dibujo)}
    for clave in ("grupo", "pastilla_modelo", "marco_cuadro", "marco_titulo", "marco_fuentes"):
        if ret[clave] not in anclas:
            raise Fallo(f"No encuentro «{ret[clave]}» en la hoja «{ret['hoja']}» del archivo de retículas")
    return {clave: anclas[ret[clave]] for clave in ("grupo", "pastilla_modelo", "marco_cuadro", "marco_titulo", "marco_fuentes")}


def paso1(trabajo, pid):
    """Retícula, pastilla y textos en un solo paso: primero la retícula y la pastilla y, sobre eso, los textos."""
    estado = leer_estado(trabajo)
    _, pasos = nombres(trabajo)
    base = pasos / estado["pasos"][estado["actual"]]["archivo"]
    hoja = estado.get("hoja") or "Cuadro datos"
    pub = publicacion(pid)
    with zipfile.ZipFile(base) as z:
        cambios, detalle = reticula_y_pastilla(z, hoja, pub)
    intermedio = io.BytesIO()
    reescribir_zip(base, intermedio, cambios)
    with zipfile.ZipFile(intermedio) as z:
        cambios_textos, detalle_textos = textos(z, hoja, estado)
    return nuevo_paso(trabajo, RETICULA_Y_TEXTOS, {**cambios, **cambios_textos}, detalle + detalle_textos)


def reticula_y_pastilla(z, hoja, pub):
    """Retícula y pastilla de la hoja «Cuadro» del archivo de retículas, al fondo y en A1, con la pastilla en el
    matiz 1 del color de la publicación; se borran las del autor (la retícula, también si la apartó)."""
    pl = plantilla()
    ruta = dibujo_de_hoja(z, hoja)
    if not ruta:
        raise Fallo(f"La hoja «{hoja}» no tiene formas (ni pastilla ni títulos): no la puedo maquetar")
    dibujo = z.read(ruta).decode("utf-8")
    detalle, quitar = [], []
    for m in ANCLA.finditer(dibujo):
        a = m.group(0)
        if es_reticula(a):
            quitar.append(m.span())
            cx, cy = tamano(a)
            detalle.append(f"Borrada la retícula del autor «{nombre_forma(a)}» ({cx / 360000:.2f} × {cy / 360000:.2f} cm)")
        elif es_pastilla(a):
            quitar.append(m.span())
            detalle.append(f"Borrada la pastilla del autor «{nombre_forma(a)}» (color {color_de(a)})")
    if not any("retícula" in d for d in detalle):
        detalle.append("Aviso: el autor no tenía retícula")
    if not any("pastilla" in d for d in detalle):
        detalle.append("Aviso: el autor no tenía pastilla")
    for ini, fin in reversed(quitar):
        dibujo = dibujo[:ini] + dibujo[fin:]
    sig = max([int(i) for i in re.findall(r'<xdr:cNvPr\s+id="(\d+)"', dibujo)] or [0]) + 1
    cx, cy = tamano(pl["grupo"], escala_grupo=True)
    nueva_ret, sig = renumerar(anclar_arriba_izquierda(pl["grupo"], cx, cy), sig, "Retícula")
    color = matiz(pub["color"], TINTES["matiz1"])
    px, py = tamano(pl["pastilla_modelo"])
    nueva_pas, sig = renumerar(anclar_arriba_izquierda(color_relleno(pl["pastilla_modelo"], color), px, py), sig, "Pastilla")
    detalle.append(f"Retícula de la hoja «Cuadro» en A1, al fondo ({cx / 360000:.2f} × {cy / 360000:.2f} cm)")
    detalle.append(f"Pastilla de {pub['nombre']} en A1, encima de la retícula: matiz 1 de #{pub['color']} = #{color} "
                   f"({px / 360000:.2f} × {py / 360000:.2f} cm)")
    m = re.search(r'<xdr:wsDr\b[^>]*>', dibujo)
    dibujo = dibujo[:m.end()] + nueva_ret + nueva_pas + dibujo[m.end():]
    return {ruta: dibujo.encode("utf-8")}, detalle


def con_parrafos(ancla, lineas):
    """La forma con estas líneas (listas de trozos), un párrafo por línea, con el pPr del primer párrafo."""
    p = re.search(r'<a:p>(.*?)</a:p>', ancla, re.S)
    ppr = re.search(r'<a:pPr\b[^>]*/>|<a:pPr\b[^>]*>.*?</a:pPr>', p.group(1), re.S) if p else None
    ppr = ppr.group(0) if ppr else ""
    parrafos = "".join(f"<a:p>{ppr}{runs_xml(linea)}</a:p>" for linea in lineas)
    return re.sub(r'(<a:lstStyle/>|<a:lstStyle>.*?</a:lstStyle>)(.*)(</xdr:txBody>)',
                  lambda m: m.group(1) + parrafos + m.group(3), ancla, count=1, flags=re.S)


def separar_cuadro_y_titulo(partes, sig):
    """Si «Cuadro N» y el título van en el mismo cuadro de texto (1.5, Memoria 3.1), se parte en dos: el
    rótulo se queda en su cuadro y el título pasa a uno nuevo (que luego toma el marco de la plantilla)."""
    for k, a in enumerate(partes):
        if not ANCLA.fullmatch(a):
            continue
        lineas = [l for l in lineas_de(a) if texto_de(l).strip()]
        if len(lineas) > 1 and RE_CUADRO_LINEA.match(html.unescape(texto_de(lineas[0]))):
            rotulo = con_parrafos(a, lineas[:1])
            titulo, _ = renumerar(con_parrafos(a, lineas[1:]), sig, "Título del cuadro")
            partes[k:k + 1] = [rotulo, "", titulo]
            return partes, html.unescape(texto_de(lineas[0])).strip()
    return partes, None


def con_marco(ancla, marco, filas, final_regular=None):
    """El marco de la plantilla (posición, tamaño, márgenes y letra) con el texto del autor, cada línea en un
    párrafo con el formato de la plantilla y el formato local del autor. Si `final_regular`, el final de cada
    párrafo que case (p. ej. «(a)» o «(cont.)») va en Roboto Regular. Conserva el id y el nombre del autor."""
    x, y = posicion(marco)
    if x != 0:
        raise Fallo("Los marcos de la plantilla tienen que empezar en la columna A")
    cx, cy = tamano(marco)
    fila, desp = celda_de(filas, y)
    cuerpo = re.search(r'</xdr:to>(.*)</xdr:twoCellAnchor>', marco, re.S).group(1)
    p = re.search(r'<a:p>(.*?)</a:p>', cuerpo, re.S).group(1)
    ppr = re.search(r'<a:pPr\b[^>]*/>|<a:pPr\b[^>]*>.*?</a:pPr>', p, re.S)
    ppr = ppr.group(0) if ppr else ""
    rpr = re.search(r'<a:rPr\b[^>]*/>|<a:rPr\b[^>]*>.*?</a:rPr>', p, re.S).group(0)
    sz = re.search(r'\bsz="(\d+)"', rpr).group(1)
    con_negrita = not todo_negrita(ancla)
    lineas = [[(con_atributos(rpr, formato_local(r, con_negrita)), t) for r, t in linea]
              for linea in lineas_de(ancla) if texto_de(linea).strip()]
    finales = []
    if final_regular:
        for k, linea in enumerate(lineas):
            final = final_regular.search(texto_de(linea))
            if final:
                finales.append(final.group(1).strip())
                lineas[k] = tramo(linea, final.start(1), len(texto_de(linea)),
                                  cambiar_rpr=lambda r: fijar_letra(r, sz, ROBOTO, False))
    parrafos = "".join(f"<a:p>{ppr}{runs_xml(linea)}</a:p>" for linea in lineas)
    cuerpo = re.sub(r'(<a:lstStyle/>|<a:lstStyle>.*?</a:lstStyle>)(.*)(</xdr:txBody>)',
                    lambda m: m.group(1) + parrafos + m.group(3), cuerpo, count=1, flags=re.S)
    autor = re.search(r'<xdr:cNvPr\b[^>]*?\bid="(\d+)"[^>]*?\bname="([^"]*)"', ancla)
    cuerpo = re.sub(r'(<xdr:cNvPr\b[^>]*?\bid=")\d+("[^>]*?\bname=")[^"]*',
                    lambda m: m.group(1) + autor.group(1) + m.group(2) + autor.group(2), cuerpo, count=1)
    cuerpo = re.sub(r'(<a16:creationId\b[^>]*\bid=")\{[^}]+\}',
                    lambda m: m.group(1) + "{" + str(uuid.uuid4()).upper() + "}", cuerpo)
    return ('<xdr:oneCellAnchor><xdr:from><xdr:col>0</xdr:col><xdr:colOff>0</xdr:colOff>'
            f'<xdr:row>{fila}</xdr:row><xdr:rowOff>{desp}</xdr:rowOff></xdr:from>'
            f'<xdr:ext cx="{cx}" cy="{cy}"/>{cuerpo}</xdr:oneCellAnchor>'), finales


def anclar_en(ancla, x, y, cx, cy, caja):
    """La forma con su esquina de arriba a la izquierda anclada a la celda donde cae (x, y) y tamaño fijo: así
    sigue a su fila si cambian los altos de las filas de encima (lo que hará el paso «Celdas")."""
    c, co, r, ro = caja.a_celda(x, y)
    cuerpo = re.search(r'(?:</xdr:to>|<xdr:ext\b[^>]*/>)(.*)</xdr:(?:twoCellAnchor|oneCellAnchor|absoluteAnchor)>',
                       ancla, re.S).group(1)
    cuerpo = re.sub(r'(<a:off) x="-?\d+" y="-?\d+"/>(\s*<a:ext) cx="\d+" cy="\d+"/>',
                    rf'\1 x="{x}" y="{y}"/>\2 cx="{cx}" cy="{cy}"/>', cuerpo, count=1)
    return (f'<xdr:oneCellAnchor><xdr:from><xdr:col>{c}</xdr:col><xdr:colOff>{co}</xdr:colOff><xdr:row>{r}</xdr:row>'
            f'<xdr:rowOff>{ro}</xdr:rowOff></xdr:from><xdr:ext cx="{cx}" cy="{cy}"/>{cuerpo}</xdr:oneCellAnchor>')


def crecer(ancla, extra):
    """Una forma de ancla de una celda, `extra` EMU más alta."""
    ancla = re.sub(r'(<xdr:ext cx="\d+" cy=")(\d+)', lambda m: m.group(1) + str(int(m.group(2)) + extra), ancla, count=1)
    return re.sub(r'(<a:xfrm\b[^>]*>\s*<a:off\b[^>]*/>\s*<a:ext cx="\d+" cy=")(\d+)',
                  lambda m: m.group(1) + str(int(m.group(2)) + extra), ancla, count=1)


def mayusculas(texto):
    letras = [c for c in texto if c.isalpha()]
    return len(letras) > 3 and all(c.isupper() for c in letras)


def textos(z, hoja, estado):
    """«Cuadro N» y título con el marco de la plantilla (el título con el final «(a)» / «(cont.)» en Regular y,
    si ocupa más de una línea, la pastilla crece); unidades en Roboto Light 6 pt; FUENTES en Roboto Light 7 pt
    con las reglas de Gráficos, en el ancho de la plantilla. Todo en negro."""
    pl = plantilla()
    ancho_ret = tamano(pl["grupo"], escala_grupo=True)[0]
    alto_pastilla = tamano(pl["pastilla_modelo"])[1]
    ruta = dibujo_de_hoja(z, hoja)
    dibujo = z.read(ruta).decode("utf-8")
    filas = altos_filas(z, hoja)
    caja = medidas_hoja(z, hoja, dibujo)
    detalle = []
    sig = max([int(i) for i in re.findall(r'<xdr:cNvPr\s+id="(\d+)"', dibujo)] or [0]) + 1
    partes, separado = separar_cuadro_y_titulo(list(partes_dibujo(dibujo)), sig)
    if separado:
        detalle.append(f"«{separado}» iba en el mismo cuadro que el título: separado en su propio cuadro")

    # Qué es cada texto, por su contenido y su sitio
    tipos = {}
    for k, a in enumerate(partes):
        if not ANCLA.fullmatch(a) or sin_texto(a) or "<xdr:grpSp>" in a[:1500]:
            continue
        x, y, w, h = caja(a)
        primera = html.unescape(texto_forma(a)).strip().split("\n")[0]
        if x >= ancho_ret:
            tipos[k] = "fuera"
        elif RE_CUADRO_LINEA.match(primera) and y < alto_pastilla:
            tipos[k] = "cuadro"
        elif ROTULO.match(primera):
            tipos[k] = "fuentes"
        elif y < alto_pastilla * 0.75 and "titulo" not in tipos.values():
            tipos[k] = "titulo"
        elif y < alto_pastilla + 12 * EMU_MM:
            tipos[k] = "unidades"
        else:
            tipos[k] = "otro"

    medir_medium = medidor("Roboto-Medium.ttf")
    medir_light = medidor("Roboto-Light.ttf")
    titulo_k = None
    for k, tipo in tipos.items():
        a = partes[k]
        corto = html.unescape(texto_forma(a)).replace("\n", " / ")[:70]
        if tipo == "fuera":
            detalle.append(f"Sin tocar, fuera de la retícula: «{corto}»")
            continue
        if tipo == "cuadro":
            a, _ = con_marco(a, pl["marco_cuadro"], filas)
            detalle.append(f"«{corto}»: Roboto Regular 7 pt, marco y posición de la plantilla")
            if mayusculas(corto):
                detalle.append(f"Aviso: el rótulo «{corto}» va en mayúsculas")
        elif tipo == "titulo":
            a, finales = con_marco(a, pl["marco_titulo"], filas, final_regular=FINAL_TITULO)
            titulo_k = k
            detalle.append(f"Título «{corto}»: Roboto Medium 8,5 pt, marco y posición de la plantilla")
            for f in finales:
                detalle.append(f"  «{f}» al final del párrafo, en Roboto Regular")
            if mayusculas(corto):
                detalle.append("Aviso: el título va en mayúsculas: pásalo a minúsculas a mano")
        elif tipo == "fuentes":
            a, notas = maquetar_fuentes(a, estado.get("idioma", "es"))
            # En el ancho de la plantilla, desde la columna A; el alto, el que pida el texto
            x, y, w, h = caja(a)
            ancho = tamano(pl["marco_fuentes"])[0]
            alto = h
            if medir_light:
                l, t, r, b = margenes(a)
                lineas = lineas_parrafos(textos_lineas(a), (ancho - l - r) / EMU_PT, 7, medir_light)
                blancos = len(re.findall(r'<a:p>(?:<a:pPr\b[^>]*/>)?<a:endParaRPr\b[^>]*?(?:/>|>.*?</a:endParaRPr>)</a:p>', a, re.S))
                alto = t + b + round((lineas + blancos) * interlineado(a, 7, "Roboto-Light.ttf") * EMU_PT) + 2 * EMU_PT
            a = anclar_en(a, 0, y, ancho, alto, caja)
            detalle.append(f"Fuentes «{corto[:50]}»: Roboto Light 7 pt" + "".join(f"; {n}" for n in notas if not n.startswith("Aviso")))
            detalle.append(f"  en el ancho de la plantilla ({ancho / EMU_MM:.1f} mm) desde la columna A, donde la dejó el autor"
                           .replace(".", ","))
            detalle += [n for n in notas if n.startswith("Aviso")]
        elif tipo == "unidades":
            a = fijar_letra(a, 600, ROBOTO_LIGHT)
            detalle.append(f"Unidades «{corto}»: Roboto Light 6 pt, donde las dejó el autor")
        else:
            detalle.append(f"Sin tocar (no sé qué texto es): «{corto}»")
            continue
        a, _ = textos_en_negro(a)
        partes[k] = a
    if "cuadro" not in tipos.values():
        detalle.append("Aviso: no encuentro el rótulo «Cuadro N»")
    if titulo_k is None:
        detalle.append("Aviso: no encuentro el título del cuadro")
    elif medir_medium:
        # Título de varias líneas: el marco del título, la pastilla y las unidades bajan un interlineado por línea de más
        l, _, r, _ = margenes(partes[titulo_k])
        ancho = (tamano(pl["marco_titulo"])[0] - l - r) / EMU_PT
        n = min(3, max(1, lineas_parrafos(textos_lineas(partes[titulo_k]), ancho, 8.5, medir_medium)))
        if n > 1:
            extra = round((n - 1) * interlineado(partes[titulo_k], 8.5, "Roboto-Medium.ttf") * EMU_PT)
            partes[titulo_k] = crecer(partes[titulo_k], extra)
            for k, a in enumerate(partes):
                if ANCLA.fullmatch(a) and nombre_forma(a) == "Pastilla":
                    partes[k] = crecer(a, extra)
            for k, tipo in tipos.items():
                if tipo == "unidades":
                    x, y, w, h = caja(partes[k])
                    partes[k] = anclar_en(partes[k], x, y + extra, w, h, caja)
            detalle.append(f"Título de {n} líneas: marco del título y pastilla {extra / EMU_MM:.1f} mm más altos y las "
                           "unidades más abajo (un interlineado del título por línea de más)".replace(".", ",", 1))
        else:
            detalle.append("Título de 1 línea")
    return {ruta: "".join(partes).encode("utf-8")}, detalle

# ---------------------------------------------------------------- paso 2: celdas

CELDAS = "Celdas"
CUERPO_CELDA = 7.5
LETRA_CELDA = "Roboto Light"
LETRA_CELDA_NEGRITA = "Roboto Medium"      # lo que el autor puso en negrita (TOTAL…): el peso lo da la variante


def es_negrita(fuente):
    """¿La fuente (de styles.xml o de un rPr) va en negrita o en una variante gruesa (Medium, Bold, Black…)?"""
    b = re.search(r'<b\b[^>]*/>', fuente)
    nombre = re.search(r'<(?:name|rFont) val="([^"]*)"', fuente)
    return bool(b and not re.search(r'val="(0|false)"', b.group(0))) or bool(
        nombre and re.search(r'Medium|Bold|Black|Heavy|Semibold|Negrita', nombre.group(1), re.I))
ALTOS_FILA = {1: 14, 2: 28, 3: 40, 4: 50}   # guía: 14 (1 línea), 28 (2), 40 (3), 50 (4), etc.
ALTO_LINEA_DE_MAS = 10                     # «etc.»: a partir de 4 líneas, 10 pt por línea de más (confirmado por el usuario)
RELLENO_CELDA_PT = 2.5                     # lo que Excel deja libre a cada lado del texto en la celda
# El Excel de Mac dibuja el texto de las celdas un 5 % más ancho que la suma de avances de la fuente (medido en
# Excel, 2026-11-13: «Régimen de tenencia de la vivienda», 114,7 pt, cabe en una línea desde 125 pt de columna;
# «País de nacimiento», 62,4 pt, desde 70)
ESCALA_TEXTO_EXCEL = 1.05
LARGO_TEXTO_IZQUIERDA = 80                 # columnas de texto largo (media de caracteres) a la izquierda; umbral en pruebas
SANGRIA = 4                                # espacios por nivel: 4 (1.º), 8 (2.º), 12 (3.º)
VINETA = re.compile(r'^[-–—•·]\s+')
RE_REF = re.compile(r'([A-Z]+)(\d+)')


def alto_fila(n):
    return ALTOS_FILA.get(n, ALTOS_FILA[4] + ALTO_LINEA_DE_MAS * (n - 4)) if n > 0 else ALTOS_FILA[1]


def ref(c, r):
    """(columna, fila) desde 1 → «B3»."""
    letras = ""
    while c:
        c, resto = divmod(c - 1, 26)
        letras = chr(65 + resto) + letras
    return f"{letras}{r}"


def col_num(letras):
    n = 0
    for ch in letras:
        n = n * 26 + ord(ch) - 64
    return n


def leer_compartidos(z):
    if "xl/sharedStrings.xml" not in z.namelist():
        return "", []
    xml = z.read("xl/sharedStrings.xml").decode("utf-8")
    return xml, re.findall(r'<si>.*?</si>|<si/>', xml, re.S)


def texto_si(si):
    """Texto de un <si> (sin las lecturas fonéticas)."""
    si = re.sub(r'<rPh\b.*?</rPh>', "", si, flags=re.S)
    return html.unescape("".join(re.findall(r'<t(?:\s[^>]*)?>(.*?)</t>', si, re.S))).replace("_x000D_", "")


class Estilos:
    """styles.xml: fuentes y formatos de celda (cellXfs), para crear los nuevos que hagan falta sin tocar los
    que ya hay (otras celdas del libro pueden usarlos)."""

    def __init__(self, xml):
        self.xml = xml
        self.fuentes = re.findall(r'<font\b.*?</font>|<font/>', re.search(r'<fonts\b[^>]*>(.*?)</fonts>', xml, re.S).group(1), re.S)
        self.xfs = re.findall(r'<xf\b[^>]*/>|<xf\b[^>]*>.*?</xf>', re.search(r'<cellXfs\b[^>]*>(.*?)</cellXfs>', xml, re.S).group(1), re.S)
        self.nuevas_fuentes, self.nuevos_xfs, self.cache = [], [], {}
        self.rellenos = re.findall(r'<fill\b.*?</fill>|<fill/>', re.search(r'<fills\b[^>]*>(.*?)</fills>', xml, re.S).group(1), re.S)
        self.bordes = re.findall(r'<border\b.*?</border>|<border/>', re.search(r'<borders\b[^>]*>(.*?)</borders>', xml, re.S).group(1), re.S)
        self.nuevos_rellenos, self.nuevos_bordes = [], []

    def xf(self, i):
        return self.xfs[i] if i < len(self.xfs) else self.xfs[0]

    def fuente_de(self, i):
        f = re.search(r'\bfontId="(\d+)"', self.xf(i))
        n = int(f.group(1)) if f else 0
        return (self.fuentes + self.nuevas_fuentes)[n] if n < len(self.fuentes) + len(self.nuevas_fuentes) else self.fuentes[0]

    def alineacion(self, i):
        a = re.search(r'<alignment\b[^>]*/>', self.xf(i))
        return dict(re.findall(r'(\w+)="([^"]*)"', a.group(0))) if a else {}

    def relleno(self, rgb):
        """Índice de un relleno sólido de este color (nuevo si no lo hay)."""
        nuevo = (f'<fill><patternFill patternType="solid"><fgColor rgb="FF{rgb}"/><bgColor indexed="64"/></patternFill></fill>'
                 if rgb else '<fill><patternFill patternType="none"/></fill>')
        todos = self.rellenos + self.nuevos_rellenos
        if nuevo in todos:
            return todos.index(nuevo)
        self.nuevos_rellenos.append(nuevo)
        return len(todos)

    def borde(self, lados):
        """Índice de un borde con estos lados ({"left": ("thin", "FFFFFF"), …}; los que falten, sin línea)."""
        partes = []
        for lado in ("left", "right", "top", "bottom"):
            if lado in lados:
                estilo, rgb = lados[lado]
                partes.append(f'<{lado} style="{estilo}"><color rgb="FF{rgb}"/></{lado}>')
            else:
                partes.append(f"<{lado}/>")
        nuevo = "<border>" + "".join(partes) + "<diagonal/></border>"
        todos = self.bordes + self.nuevos_bordes
        if nuevo in todos:
            return todos.index(nuevo)
        self.nuevos_bordes.append(nuevo)
        return len(todos)

    def con_letra(self, i, color):
        """La fuente del formato `i` con este color de letra (nueva si hace falta)."""
        fuente = self.fuente_de(i)
        fuente = re.sub(r'<color\b[^>]*/>', "", fuente)
        fuente = re.sub(r'(<sz\b[^>]*/>)', rf'\1<color rgb="FF{color}"/>', fuente, count=1) if color else fuente
        todas = self.fuentes + self.nuevas_fuentes
        if fuente in todas:
            return todas.index(fuente)
        self.nuevas_fuentes.append(fuente)
        return len(todas)

    def variante(self, i, relleno=None, borde=None, letra=None):
        """Índice de un formato como el `i` con otro relleno, borde o color de letra (lo demás, igual)."""
        clave = ("v", i, relleno, tuple(sorted(borde.items())) if borde is not None else None, letra)
        if clave in self.cache:
            return self.cache[clave]
        xf = self.xf(i)
        apertura = re.match(r'<xf\b[^>]*?(/?)>', xf)
        atributos = apertura.group(0)[3:-(2 if apertura.group(1) else 1)]
        dentro = "" if apertura.group(1) else xf[apertura.end():xf.rindex("</xf>")]
        cambios = []
        if relleno is not None:
            cambios += [("fillId", self.relleno(relleno)), ("applyFill", 1)]
        if borde is not None:
            cambios += [("borderId", self.borde(borde)), ("applyBorder", 1)]
        if letra is not None:
            cambios += [("fontId", self.con_letra(i, letra)), ("applyFont", 1)]
        for nombre, valor in cambios:
            atributos = re.sub(rf'\s{nombre}="[^"]*"', "", atributos) + f' {nombre}="{valor}"'
        nuevo = f"<xf{atributos}>{dentro}</xf>" if dentro else f"<xf{atributos}/>"
        todos = self.xfs + self.nuevos_xfs
        if nuevo in todos:
            n = todos.index(nuevo)
        else:
            self.nuevos_xfs.append(nuevo)
            n = len(todos)
        self.cache[clave] = n
        return n

    def fuente_celda(self, fuente):
        """Roboto Light 7,5 pt (o Roboto Medium si el autor la puso en negrita) con el formato local de la fuente
        del autor (cursiva, subrayado, tachado, índices, color), sin negrita de Excel: el peso lo da la familia."""
        partes = []
        for etiqueta in ("i", "strike", "u", "vertAlign"):
            m = re.search(rf'<{etiqueta}\b[^>]*/>', fuente)
            if m and 'val="0"' not in m.group(0) and 'val="false"' not in m.group(0):
                partes.append(m.group(0))
        partes.append(f'<sz val="{CUERPO_CELDA:g}"/>')
        color = re.search(r'<color\b[^>]*/>', fuente)
        if color:
            partes.append(color.group(0))
        partes.append(f'<name val="{LETRA_CELDA_NEGRITA if es_negrita(fuente) else LETRA_CELDA}"/><family val="2"/>')
        nueva = "<font>" + "".join(partes) + "</font>"
        todas = self.fuentes + self.nuevas_fuentes
        if nueva in todas:
            return todas.index(nueva)
        self.nuevas_fuentes.append(nueva)
        return len(todas)

    def nuevo(self, i, alineacion):
        """Índice de un formato como el `i` del autor con la fuente de celda y esta alineación."""
        clave = (i, tuple(sorted(alineacion.items())))
        if clave in self.cache:
            return self.cache[clave]
        xf = self.xf(i)
        fid = self.fuente_celda(self.fuente_de(i))
        apertura = re.match(r'<xf\b[^>]*?(/?)>', xf)
        atributos = apertura.group(0)[3:-(2 if apertura.group(1) else 1)]
        for nombre, valor in (("fontId", fid), ("applyFont", 1), ("applyAlignment", 1)):
            atributos = re.sub(rf'\s{nombre}="[^"]*"', "", atributos) + f' {nombre}="{valor}"'
        dentro = "" if apertura.group(1) else xf[apertura.end():xf.rindex("</xf>")]
        dentro = re.sub(r'<alignment\b[^>]*/>', "", dentro)
        al = "<alignment" + "".join(f' {k}="{v}"' for k, v in alineacion.items()) + "/>"
        nuevo = f"<xf{atributos}>{al}{dentro}</xf>"
        todos = self.xfs + self.nuevos_xfs
        if nuevo in todos:
            n = todos.index(nuevo)
        else:
            self.nuevos_xfs.append(nuevo)
            n = len(todos)
        self.cache[clave] = n
        return n

    def resultado(self):
        xml = self.xml
        if self.nuevas_fuentes:
            total = len(self.fuentes) + len(self.nuevas_fuentes)
            xml = re.sub(r'(<fonts\b[^>]*?)\scount="\d+"', rf'\1 count="{total}"', xml, count=1)
            xml = xml.replace("</fonts>", "".join(self.nuevas_fuentes) + "</fonts>", 1)
        for etiqueta, viejos, nuevos in (("fills", self.rellenos, self.nuevos_rellenos), ("borders", self.bordes, self.nuevos_bordes)):
            if nuevos:
                xml = re.sub(rf'(<{etiqueta}\b[^>]*?)\scount="\d+"', rf'\1 count="{len(viejos) + len(nuevos)}"', xml, count=1)
                xml = xml.replace(f"</{etiqueta}>", "".join(nuevos) + f"</{etiqueta}>", 1)
        if self.nuevos_xfs:
            total = len(self.xfs) + len(self.nuevos_xfs)
            xml = re.sub(r'(<cellXfs\b[^>]*?)\scount="\d+"', rf'\1 count="{total}"', xml, count=1)
            xml = xml.replace("</cellXfs>", "".join(self.nuevos_xfs) + "</cellXfs>", 1)
        return xml


def celdas_hoja(hoja_xml, compartidos):
    """{(col, fila): {"xml", "s", "texto", "numero"}} de las celdas de la hoja."""
    celdas = {}
    for m in re.finditer(r'<c\b[^>]*?(?:/>|>.*?</c>)', hoja_xml, re.S):
        c = m.group(0)
        r = RE_REF.match(re.search(r'\br="([^"]+)"', c).group(1))
        tipo = re.search(r'\bt="(\w+)"', c[:c.find(">") + 1])
        tipo = tipo.group(1) if tipo else "n"
        s = re.search(r'\bs="(\d+)"', c[:c.find(">") + 1])
        v = re.search(r'<v>(.*?)</v>', c, re.S)
        texto, numero = "", False
        if tipo == "s" and v:
            texto = texto_si(compartidos[int(v.group(1))])
        elif tipo == "inlineStr":
            texto = texto_si(c)
        elif v:
            texto = html.unescape(v.group(1))
            numero = tipo in ("n",) and texto != ""
        celdas[(col_num(r.group(1)), int(r.group(2)))] = {"xml": c, "s": int(s.group(1)) if s else 0, "texto": texto,
                                                         "numero": numero, "tipo": tipo}
    return celdas


def combinadas(hoja_xml):
    """[(c1, f1, c2, f2)] de las celdas combinadas."""
    rangos = []
    for a, b in re.findall(r'<mergeCell\b[^>]*\bref="([A-Z]+\d+):([A-Z]+\d+)"', hoja_xml):
        m1, m2 = RE_REF.match(a), RE_REF.match(b)
        rangos.append((col_num(m1.group(1)), int(m1.group(2)), col_num(m2.group(1)), int(m2.group(2))))
    return rangos


SEPARACION_PT = 3     # columnas de separación de la cabecera: 3 pt (Memoria 3.4 TERMINADO: Excel enseña «0,25»)
MULTIPLO_PT = 3       # anchos de columna en múltiplos de 3 pt: la medida en que coinciden el Mac (puntos) y Windows
                      # (píxeles de 0,75 pt); el cuadro mide 468 pt (retícula 468,9), «visualmente ni se aprecia»


def digito_windows(estilos_xml):
    """Lo mismo para el Excel de Windows: píxeles a 96 ppp (Calibri 11 → 7, Arial 12 → 9). Calculado, no medido."""
    f0 = re.search(r'<font\b.*?</font>', re.search(r'<fonts\b[^>]*>(.*?)</fonts>', estilos_xml, re.S).group(1), re.S).group(0)
    nombre = re.search(r'<name val="([^"]*)"', f0)
    nombre = nombre.group(1) if nombre else "Calibri"
    sz = float(re.search(r'<sz val="([\d.]+)"', f0).group(1)) if re.search(r'<sz val="([\d.]+)"', f0) else 11
    for archivo in (nombre.replace(" ", "-") + ".ttf", nombre + ".ttf", nombre.lower() + ".ttf"):
        medir = medidor(archivo)
        if medir:
            return max(1, round(max(medir(d, sz) for d in "0123456789") * 96 / 72))
    return max(1, round(7 * sz / 11))


def ancho_comun(pt, mdw_mac, mdw_win):
    """Ancho guardado que mide `pt` en el Excel de Mac (puntos enteros) y lo mismo en el de Windows (píxeles a
    96 ppp, 1 px = 0,75 pt), si lo hay; si no, el del Mac."""
    desde = max(1, int((pt - 0.5) / mdw_mac * 1000))
    for i in range(desde, int((pt + 0.5) / mdw_mac * 1000) + 2):
        w = i / 1000
        mac = round(w * mdw_mac)
        win = int(((256 * w + int(128 / mdw_win)) / 256) * mdw_win) * 0.75
        if mac == pt and abs(win - pt) < 0.01:
            return w
    return round(pt / mdw_mac, 8)


def digito_maximo(estilos_xml):
    """Ancho (en puntos enteros) del dígito más ancho de la fuente por defecto del libro: la unidad con la que el
    Excel de Mac mide las columnas (medido en Excel, 2026-11-13: Calibri 11 → 6, Arial 12 → 7; ancho en puntos
    = ancho guardado × esa unidad, redondeado). El de Windows usa píxeles a 96 ppp y sale un 14 % más estrecho."""
    f0 = re.search(r'<font\b.*?</font>', re.search(r'<fonts\b[^>]*>(.*?)</fonts>', estilos_xml, re.S).group(1), re.S).group(0)
    nombre = re.search(r'<name val="([^"]*)"', f0)
    nombre = nombre.group(1) if nombre else "Calibri"
    sz = float(re.search(r'<sz val="([\d.]+)"', f0).group(1)) if re.search(r'<sz val="([\d.]+)"', f0) else 11
    for archivo in (nombre.replace(" ", "-") + ".ttf", nombre + ".ttf", nombre.lower() + ".ttf"):
        medir = medidor(archivo)
        if medir:
            return max(1, round(max(medir(d, sz) for d in "0123456789")))
    return max(1, round(6 * sz / 11))


FORMATOS_INTERNOS = {0: "General", 1: "0", 2: "0.00", 3: "#,##0", 4: "#,##0.00", 9: "0%", 10: "0.00%", 11: "0.00E+00",
                     37: "#,##0 ;(#,##0)", 38: "#,##0 ;[Red](#,##0)", 39: "#,##0.00;(#,##0.00)", 40: "#,##0.00;[Red](#,##0.00)"}
COLUMNA_ESTRECHA = 3          # columnas de menos de este ancho (en caracteres): separaciones del autor


def formato_numero(estilos, s):
    """Código de formato de número del formato de celda `s`."""
    m = re.search(r'\bnumFmtId="(\d+)"', estilos.xf(s))
    n = int(m.group(1)) if m else 0
    propio = re.search(rf'<numFmt\b[^>]*\bnumFmtId="{n}"[^>]*\bformatCode="([^"]*)"', estilos.xml)
    return html.unescape(propio.group(1)) if propio else FORMATOS_INTERNOS.get(n, "General")


def cifra_vista(valor, codigo):
    """Cómo enseña Excel el número (en castellano: punto de millares y coma decimal), para medir su ancho."""
    try:
        v = float(valor)
    except ValueError:
        return valor
    seccion = codigo.split(";")[1 if v < 0 and ";" in codigo else 0]
    seccion = re.sub(r'\[[^\]]*\]|"[^"]*"|\\.', "", seccion)
    relleno = len(re.findall(r'_.', seccion))
    seccion = re.sub(r'_.', "", seccion)
    if seccion.strip().lower() in ("general", "") or not re.search(r'[0#?]', seccion):
        texto = f"{v:.10g}".replace(".", ",")
        return texto
    if "%" in seccion:
        v *= 100
    entera, _, decimal = seccion.partition(".")
    dec = len(re.findall(r'[0#?]', decimal))
    texto = f"{abs(v) if ';' in codigo and v < 0 else v:,.{dec}f}"
    if "," not in entera:
        texto = texto.replace(",", "")
    texto = texto.replace(",", "\x00").replace(".", ",").replace("\x00", ".")
    return texto + ("%" if "%" in seccion else "") + " " * relleno


def poner_anchos(hoja_xml, anchos):
    """Escribe en <cols> los anchos (columna → ancho en caracteres), partiendo los rangos que haga falta."""
    rangos = []
    for m in re.finditer(r'<col\b[^>]*/>', hoja_xml):
        a = int(re.search(r'\bmin="(\d+)"', m.group(0)).group(1))
        b = int(re.search(r'\bmax="(\d+)"', m.group(0)).group(1))
        rangos.append([a, b, m.group(0)])
    for c, w in sorted(anchos.items()):
        nuevos = []
        hecho = False
        for a, b, x in rangos:
            if a <= c <= b:
                if a < c:
                    nuevos.append([a, c - 1, re.sub(r'\bmax="\d+"', f'max="{c - 1}"', x)])
                propia = re.sub(r'\bmin="\d+"', f'min="{c}"', re.sub(r'\bmax="\d+"', f'max="{c}"', x))
                propia = re.sub(r'\s(width|customWidth|bestFit)="[^"]*"', "", propia)
                propia = propia[:-2].rstrip() + f' width="{w}" customWidth="1"/>'
                nuevos.append([c, c, propia])
                if c < b:
                    nuevos.append([c + 1, b, re.sub(r'\bmin="\d+"', f'min="{c + 1}"', x)])
                hecho = True
            else:
                nuevos.append([a, b, x])
        if not hecho:
            nuevos.append([c, c, f'<col min="{c}" max="{c}" width="{w}" customWidth="1"/>'])
        rangos = sorted(nuevos)
    cols = "<cols>" + "".join(x for _, _, x in rangos) + "</cols>"
    if "<cols>" in hoja_xml:
        return re.sub(r'<cols>.*?</cols>', cols, hoja_xml, count=1, flags=re.S)
    return re.sub(r'(<sheetData\b)', cols + r'\1', hoja_xml, count=1)


def anchos_columnas(hoja_xml):
    cols = [(int(a), int(b), float(w)) for a, b, w in
            re.findall(r'<col\b[^>]*?\bmin="(\d+)"[^>]*?\bmax="(\d+)"[^>]*?\bwidth="([\d.]+)"', hoja_xml)]
    dc = re.search(r'\bdefaultColWidth="([\d.]+)"', hoja_xml)
    dc = float(dc.group(1)) if dc else 8.43
    ocultas = {i for a, b in re.findall(r'<col\b[^>]*?\bmin="(\d+)"[^>]*?\bmax="(\d+)"[^>]*?\bhidden="1"', hoja_xml)
               for i in range(int(a), int(b) + 1)}
    return lambda c: 0.0 if c in ocultas else next((w for a, b, w in cols if a <= c <= b), dc)


def buscar_tabla(celdas, rangos, ancho_col, a_emu, ancho_ret, estilos):
    """El bloque del cuadro: celdas ocupadas (con texto, borde o relleno) unidas entre sí, empezando por la
    columna más a la izquierda que esté dentro de la retícula. Devuelve (c1, f1, c2, f2)."""
    def ocupada(k):
        d = celdas.get(k)
        if not d:
            return False
        if d["texto"].strip():
            return True
        xf = estilos.xf(d["s"])
        return bool(re.search(r'\bborderId="[1-9]', xf) or re.search(r'\bfillId="([2-9]|\d\d+)"', xf))
    ocupadas = {k for k in celdas if ocupada(k)}
    for c1, f1, c2, f2 in rangos:
        if any((c, f) in ocupadas for c in range(c1, c2 + 1) for f in range(f1, f2 + 1)):
            ocupadas |= {(c, f) for c in range(c1, c2 + 1) for f in range(f1, f2 + 1)}
    x = {}
    pos = 0.0
    for c in range(1, max([k[0] for k in ocupadas] or [1]) + 2):
        x[c] = pos
        pos += a_emu(ancho_col(c))
    dentro = {k for k in ocupadas if x.get(k[0], 0) < ancho_ret}
    if not dentro:
        raise Fallo("No encuentro el cuadro (celdas con texto) dentro de la retícula")
    vistos, grupos = set(), []
    for inicio in sorted(dentro, key=lambda k: (k[0], k[1])):
        if inicio in vistos:
            continue
        grupo, pila = set(), [inicio]
        while pila:
            k = pila.pop()
            if k in vistos or k not in ocupadas:
                continue
            vistos.add(k)
            grupo.add(k)
            c, f = k
            pila += [(c + 1, f), (c - 1, f), (c, f + 1), (c, f - 1)]
            # Columnas estrechas vacías (separaciones del autor, de menos de 3 de ancho): se saltan
            for paso in (1, -1):
                salto = c + paso
                while 0 < salto and ancho_col(salto) < 3 and (salto, f) not in ocupadas and abs(salto - c) <= 3:
                    salto += paso
                if salto != c + paso:
                    pila.append((salto, f))
        grupos.append(grupo)
    con_texto = [g for g in grupos if any(celdas.get(k, {}).get("texto", "").strip() for k in g)]
    if not con_texto:
        raise Fallo("No encuentro el cuadro (celdas con texto) dentro de la retícula")
    minimo = min(k[0] for g in con_texto for k in g if celdas.get(k, {}).get("texto", "").strip())
    grupo = max((g for g in con_texto if any(k[0] == minimo for k in g)),
                key=lambda g: sum(1 for k in g if celdas.get(k, {}).get("texto", "").strip()))
    # Sin las filas y columnas de los bordes que no tienen texto (bordes o rellenos sueltos del autor)
    texto = {k for k in grupo if celdas.get(k, {}).get("texto", "").strip()}
    return (min(k[0] for k in texto), min(k[1] for k in texto), max(k[0] for k in texto), max(k[1] for k in texto))


def es_cifra(d):
    """¿Es un dato numérico (número, o texto que es una cifra: «67 (a)», «-0,054***», «(0,015)», «—»)?"""
    if d["numero"]:
        return True
    t = d["texto"].strip()
    return bool(t) and bool(re.fullmatch(r'[-–—+]?\(?[-–—+]?[\d.,\s]*\d[\d.,]*\s*%?\)?\**\s*(\([a-z]\))?|[-–—]|n\.?\s?d\.?|n\.?\s?a\.?', t, re.I))


def partir(texto, ancho, medir, sangria=""):
    """Líneas de un texto en un ancho (pt), partiendo por palabras como Excel; cada salto de línea manual
    empieza línea. Con `sangria`, las líneas que siguen la llevan delante (sangría hecha con espacios)."""
    salida = []
    espacio = medir(" ", CUERPO_CELDA)
    for parrafo in texto.split("\n"):
        palabras = parrafo.split(" ")
        actual = ""
        for palabra in palabras:
            prueba = (actual + " " + palabra) if actual.strip() else (actual + palabra if actual else palabra)
            if actual.strip() and medir(prueba, CUERPO_CELDA) > ancho:
                salida.append(actual)
                actual = sangria + palabra
            else:
                actual = prueba
        salida.append(actual)
    return salida


def paso2(trabajo, pid=None):
    """Celdas del cuadro: Roboto Light 7,5 pt sin negrita; alto de fila por líneas (14, 28, 40, 50…);
    cabecera: la primera a la izquierda y las demás al centro; primera columna a la izquierda, con las
    sangrías hechas con 4, 8 o 12 espacios; cifras al centro; textos al centro (cortos) o a la izquierda
    (largos); centrado en altura, o arriba si en la fila hay textos de 2 o más líneas en las columnas de datos."""
    estado = leer_estado(trabajo)
    requiere(estado, [RETICULA_Y_TEXTOS], "«Celdas»")
    _, pasos = nombres(trabajo)
    base = pasos / estado["pasos"][estado["actual"]]["archivo"]
    hoja = estado.get("hoja") or "Cuadro datos"
    with zipfile.ZipFile(base) as z:
        cambios, detalle, cuadro = celdas(z, hoja)
    return nuevo_paso(trabajo, CELDAS, cambios, detalle, cuadro)


def celdas(z, hoja):
    ruta_hoja = hoja_de(z, hoja)
    hoja_xml = z.read(ruta_hoja).decode("utf-8")
    comp_xml, compartidos = leer_compartidos(z)
    estilos = Estilos(z.read("xl/styles.xml").decode("utf-8"))
    dibujo = z.read(dibujo_de_hoja(z, hoja)).decode("utf-8") if dibujo_de_hoja(z, hoja) else ""
    mdw = digito_maximo(estilos.xml)

    def unidades_a_emu(w):
        """Ancho de columna (en caracteres, como lo guarda Excel) → EMU, como lo dibuja el Excel de Mac."""
        return round(round(w * mdw) * EMU_PT) if w > 0 else 0
    unidad = None
    pl = plantilla()
    ancho_ret = tamano(pl["grupo"], escala_grupo=True)[0]
    medir_fuente = medidor("Roboto-Light.ttf")
    if not medir_fuente:
        raise Fallo("No encuentro la fuente Roboto Light instalada: hace falta para medir los textos")
    medir = lambda t, pt: medir_fuente(t, pt) * ESCALA_TEXTO_EXCEL
    medir_m = medidor("Roboto-Medium.ttf") or medir_fuente
    medir_medium = lambda t, pt: medir_m(t, pt) * ESCALA_TEXTO_EXCEL
    todas = celdas_hoja(hoja_xml, compartidos)
    rangos = combinadas(hoja_xml)
    ancho_col = anchos_columnas(hoja_xml)
    c1, f1, c2, f2 = buscar_tabla(todas, rangos, ancho_col, unidades_a_emu, ancho_ret, estilos)
    detalle = []
    # La FUENTE y las notas que el autor escribió en celdas, debajo del cuadro, no son parte de él
    for f in range(f1 + 1, f2 + 1):
        fila_txt = [todas.get((c, f), {}).get("texto", "").strip() for c in range(c1, c2 + 1)]
        primero = next((t for t in fila_txt if t), "")
        if primero and ROTULO.match(primero) and len([t for t in fila_txt if t]) == 1:
            detalle.append(f"Aviso: la fuente y las notas van en celdas bajo el cuadro (desde la fila {f}): no son parte del "
                           "cuadro y no se maquetan; pásalas al cuadro de texto de FUENTES")
            f2 = f - 1
            while f2 > f1 and not any(todas.get((c, f2), {}).get("texto", "").strip() for c in range(c1, c2 + 1)):
                f2 -= 1
            break
    detalle.insert(0, f"Cuadro en {ref(c1, f1)}:{ref(c2, f2)} ({f2 - f1 + 1} filas, {c2 - c1 + 1} columnas)")

    # Celdas combinadas: la de arriba a la izquierda manda; las demás se saltan
    tapadas, ancho_comb, filas_comb = set(), {}, {}
    for a1, b1, a2, b2 in rangos:
        if a1 >= c1 and a2 <= c2 and b1 >= f1 and b2 <= f2:
            ancho_comb[(a1, b1)] = sum(ancho_col(c) for c in range(a1, a2 + 1))
            filas_comb[(a1, b1)] = b2 - b1 + 1
            tapadas |= {(c, f) for c in range(a1, a2 + 1) for f in range(b1, b2 + 1)} - {(a1, b1)}

    def d(c, f):
        return todas.get((c, f), {"xml": None, "s": 0, "texto": "", "numero": False, "tipo": "n"})

    # Columnas con datos: la primera columna con texto es la de los conceptos
    primera = next((c for c in range(c1, c2 + 1) if ancho_col(c) > 0 and any(d(c, f)["texto"].strip() for f in range(f1, f2 + 1))), c1)
    ocultas = [ref(c, 1)[:-1] for c in range(c1, c2 + 1) if ancho_col(c) == 0]
    if ocultas:
        detalle.append("Columnas ocultas del autor, sin tocar su ancho: " + ", ".join(ocultas))

    # Cabecera: las filas de arriba hasta la primera con cifras (sin contar títulos de bloque, que no llevan
    # datos), más las que abarquen sus celdas combinadas; si no hay cifras, la primera fila
    def datos(f):
        return [d(c, f) for c in range(primera + 1, c2 + 1) if (c, f) not in tapadas and d(c, f)["texto"].strip()]
    # (una fila de datos lleva concepto en la primera columna: así los años de la cabecera no cuentan)
    con_cifras = [f for f in range(f1, f2 + 1) if d(primera, f)["texto"].strip()
                  and any(es_cifra(x) and re.search(r"\d", x["texto"]) for x in datos(f))]
    if con_cifras:
        fin_cab = con_cifras[0] - 1
        while fin_cab > f1 and not datos(fin_cab) and d(primera, fin_cab)["texto"].strip():
            fin_cab -= 1
    else:
        fin_cab = f1
    fin_cab = max(fin_cab, f1)
    for (a, b), n in filas_comb.items():
        if b <= fin_cab:
            fin_cab = max(fin_cab, b + n - 1)
    detalle.append(f"Cabecera: filas {f1}-{fin_cab}" if fin_cab > f1 else f"Cabecera: fila {f1}")

    # Sangrías de la primera columna: niveles (sangría de Excel y espacios del autor) → 4, 8, 12 espacios
    def sangria_autor(f):
        x = d(primera, f)
        t = x["texto"]
        espacios = len(t) - len(t.lstrip("  "))
        nivel = int(estilos.alineacion(x["s"]).get("indent", 0))
        return nivel * 3 + espacios
    valores = sorted({sangria_autor(f) for f in range(fin_cab + 1, f2 + 1) if d(primera, f)["texto"].strip()} - {0})
    if len(valores) > 3:
        detalle.append(f"Aviso: la primera columna tiene {len(valores)} niveles de sangría; la guía prevé 3")
    nivel_de = {v: min(i + 1, 3) for i, v in enumerate(valores)}

    # Anchos de columna: el cuadro llega al borde derecho de la retícula. Manda la primera columna (el ancho de su
    # texto más largo en una línea); las demás, si se puede, iguales. Si no caben, la primera cede (su texto pasa a
    # varias líneas) hasta lo que pida su palabra más larga. Las estrechas de separación y las ocultas, igual.
    anchos_viejos = {c: ancho_col(c) for c in range(1, c2 + 1)}
    otras = [c for c in range(primera + 1, c2 + 1) if COLUMNA_ESTRECHA <= ancho_col(c)]
    fijas = [c for c in range(primera + 1, c2 + 1) if c not in otras]
    # Columnas de separación (estrechas, visibles y sin texto): 3 pt, iguales en Mac y en Windows
    separaciones = [c for c in fijas if ancho_col(c) > 0 and not any(d(c, f)["texto"].strip() for f in range(f1, f2 + 1))]
    if separaciones:
        w_sep = ancho_comun(SEPARACION_PT, mdw, digito_windows(estilos.xml))
        ancho_previo = ancho_col
        ancho_col = lambda c, _v=ancho_previo, _s=set(separaciones), _w=w_sep: _w if c in _s else _v(c)
    espacio_pt = (ancho_ret - sum(unidades_a_emu(ancho_col(c)) for c in list(range(1, primera)) + fijas)) / EMU_PT
    def medir_de(c, f):
        """La medida de la variante que llevará la celda: Roboto Medium si el autor la puso en negrita."""
        return medir_medium if es_negrita(estilos.fuente_de(d(c, f)["s"])) else medir
    palabra = lambda t, m=medir: max([m(w, CUERPO_CELDA) for w in re.split(r"[ \n]+", t) if w] or [0])

    def vista(c, f):
        x = d(c, f)
        return cifra_vista(x["texto"], formato_numero(estilos, x["s"])) if x["numero"] else x["texto"]
    necesita = {c: 0.0 for c in otras}
    for f in range(f1, f2 + 1):
        for c in otras:
            if (c, f) in tapadas or not d(c, f)["texto"].strip():
                continue
            t = vista(c, f).strip()
            mc = medir_de(c, f)
            w = mc(t, CUERPO_CELDA) if es_cifra(d(c, f)) and f > fin_cab else palabra(t, mc)
            tramo_cols = [k for k in otras if k == c or ((k, f) in tapadas and k > c and all((j, f) in tapadas for j in range(c + 1, k + 1)))]
            necesita[c] = max(necesita[c], w / max(1, len(tramo_cols)) + 2 * RELLENO_CELDA_PT)
    natural = minimo = 0.0
    for f in range(f1, f2 + 1):
        t = d(primera, f)["texto"]
        if not t.strip() or (primera, f) in tapadas:
            continue
        espacios = " " * (SANGRIA * nivel_de.get(sangria_autor(f), 0)) if f > fin_cab else ""
        cuerpo = VINETA.sub("", t.strip(" \u00a0"))
        mc = medir_de(primera, f)
        natural = max(natural, max(mc(espacios + l.strip(), CUERPO_CELDA) for l in cuerpo.split("\n")))
        minimo = max(minimo, mc(espacios, CUERPO_CELDA) + palabra(cuerpo, mc))
    natural += 2 * RELLENO_CELDA_PT + 1.5   # holgura: el redondeo a píxeles no debe partir el texto más largo
    minimo += 2 * RELLENO_CELDA_PT
    if otras:
        hace_falta = max(necesita.values())
        primera_pt = max(minimo, min(natural, espacio_pt - len(otras) * hace_falta))
        resto = (espacio_pt - primera_pt) / len(otras)
        if resto < hace_falta - 0.1:
            detalle.append(f"Aviso: el cuadro no cabe en la retícula a {CUERPO_CELDA:g} pt: las columnas necesitan "
                           f"{hace_falta:.0f} pt y solo hay {resto:.0f}; la guía permite bajar la letra hasta 6 pt".replace(".", ",", 1))
    else:
        primera_pt, resto = espacio_pt, 0
    if primera_pt < natural - 0.1:
        detalle.append("La primera columna cede ancho: algún texto suyo pasa a varias líneas")

    # Cabeceras compensadas (petición del usuario, 1.4): si los textos de la cabecera de las demás columnas ocupan
    # varias líneas, esas columnas se estrechan hasta el ancho mínimo en que siguen ocupando las mismas líneas (así
    # las líneas quedan parejas) y lo que sobra pasa a la primera columna. Solo si ninguna celda gana líneas.
    def lineas_texto(t, w, m=medir):
        return len(partir(t, w - 2 * RELLENO_CELDA_PT, m))
    tramos = {}
    for a1, b1, a2, b2 in rangos:
        tramos[(a1, b1)] = max(1, len([k for k in otras if a1 <= k <= a2]))
    celdas_otras = [(c, f, d(c, f)["texto"], tramos.get((c, f), 1), medir_de(c, f)) for f in range(f1, f2 + 1) for c in otras
                    if (c, f) not in tapadas and d(c, f)["texto"].strip()
                    and not (f > fin_cab and es_cifra(d(c, f)))]
    if otras and resto > 0 and any(f <= fin_cab and lineas_texto(t, k * resto, m) > 1 for c, f, t, k, m in celdas_otras):
        antes = {(c, f): lineas_texto(t, k * resto, m) for c, f, t, k, m in celdas_otras}

        def sirve(w):
            return w >= hace_falta and all(lineas_texto(t, k * w, m) <= antes[(c, f)] for c, f, t, k, m in celdas_otras)
        bajo, alto = max(hace_falta, 1.0), resto
        if sirve(bajo):
            alto = bajo
        else:
            for _ in range(30):
                medio = (bajo + alto) / 2
                if sirve(medio):
                    alto = medio
                else:
                    bajo = medio
        nuevo_resto = alto + 0.5   # medio punto de holgura por el redondeo a puntos enteros
        if nuevo_resto < resto - 1:
            detalle.append(f"Cabecera compensada: las columnas de datos pasan de {resto / MM:.1f} a {nuevo_resto / MM:.1f} mm "
                           "(mismas líneas, más parejas) y la primera columna gana el resto".replace(".", ","))
            primera_pt += (resto - nuevo_resto) * len(otras)
            resto = nuevo_resto

    # Columnas de textos largos: si con anchos iguales sus filas salen mucho más altas, ganan ancho a costa de las que
    # tienen holgura (sin que estas pasen a tener más líneas que la más alta), hasta que ya no mejora
    largas = []
    for c in otras:
        textos = [d(c, f)["texto"] for f in range(fin_cab + 1, f2 + 1)
                  if (c, f) not in tapadas and d(c, f)["texto"].strip() and not es_cifra(d(c, f))]
        if textos and sum(len(t) for t in textos) / len(textos) > LARGO_TEXTO_IZQUIERDA:
            largas.append(c)
    anchos_pt = {c: resto for c in otras}
    if largas and len(otras) > 1:
        def lineas_col(c, w):
            return max([len(partir(d(c, f)["texto"], w - 2 * RELLENO_CELDA_PT, medir_de(c, f))) for f in range(fin_cab + 1, f2 + 1)
                        if (c, f) not in tapadas and d(c, f)["texto"].strip()] or [1])
        paso_pt = 2.0
        for _ in range(400):
            lin = {c: lineas_col(c, anchos_pt[c]) for c in otras}
            alta = max(largas, key=lambda c: lin[c])
            donantes = [c for c in otras if c != alta and anchos_pt[c] - paso_pt >= necesita[c]
                        and lineas_col(c, anchos_pt[c] - paso_pt) < lin[alta] - 1]
            if not donantes or lin[alta] <= 2:
                break
            donante = min(donantes, key=lambda c: (lin[c], -anchos_pt[c]))
            anchos_pt[donante] -= paso_pt
            anchos_pt[alta] += paso_pt
        if any(abs(anchos_pt[c] - resto) > 0.5 for c in otras):
            cortas = [anchos_pt[c] / MM for c in otras if c not in largas]
            detalle.append(("Columnas de textos largos más anchas para no alargar las filas ("
                            + ", ".join(f"{ref(c, 1)[:-1]} {anchos_pt[c] / MM:.1f} mm" for c in largas) + ")"
                            + (f"; las demás, {min(cortas):.1f}-{max(cortas):.1f} mm" if cortas else "")).replace(".", ","))

    def a_caracteres(pt):
        """Puntos → ancho guardado en el archivo (el Excel de Mac lo redondea a puntos enteros)."""
        return round(max(0, round(pt)) / mdw, 8)
    # Anchos en múltiplos de 3 pt: las columnas de datos hacia arriba (no pierden ancho) y la primera, el resto
    mdw_win = digito_windows(estilos.xml)
    otros_pt = {c: max(MULTIPLO_PT, MULTIPLO_PT * math.ceil(anchos_pt[c] / MULTIPLO_PT - 1e-6)) for c in otras}
    disponible = MULTIPLO_PT * math.floor(espacio_pt / MULTIPLO_PT + 1e-6)
    primera_final = disponible - sum(otros_pt.values())
    if primera_final < MULTIPLO_PT:
        primera_final = MULTIPLO_PT * max(1, round(primera_pt / MULTIPLO_PT))
    nuevos_anchos = {primera: ancho_comun(primera_final, mdw, mdw_win)}
    for c in separaciones:
        nuevos_anchos[c] = w_sep
    for c in otras:
        nuevos_anchos[c] = ancho_comun(otros_pt[c], mdw, mdw_win)
    ancho_col_viejo = ancho_col
    ancho_col = lambda c, _v=ancho_col_viejo: nuevos_anchos.get(c, _v(c))
    total_pt = sum(round(ancho_col(c) * mdw) for c in range(1, c2 + 1))
    detalle.append(f"Anchos de columna en múltiplos de {MULTIPLO_PT} pt: el cuadro mide {total_pt} pt (retícula "
                   f"{ancho_ret / EMU_PT:.1f} pt); primera columna {primera_final} pt".replace(".", ",")
                   + (f" y columnas de datos de {', '.join(str(v) for v in sorted(set(otros_pt.values())))} pt" if otras else "")
                   + (f"; {len(separaciones)} columna{'s' if len(separaciones) > 1 else ''} de separación de {SEPARACION_PT} pt"
                      if separaciones else "")
                   + (f"; {len(fijas) - len(separaciones)} columna{'s' if len(fijas) - len(separaciones) > 1 else ''} estrecha{'s' if len(fijas) - len(separaciones) > 1 else ''} con texto, sin tocar"
                      if len(fijas) > len(separaciones) else ""))

    # Textos nuevos (sangrías, viñetas, TOTAL) y líneas de cada celda
    nuevos_textos, lineas, cambios_txt = {}, {}, []
    for f in range(f1, f2 + 1):
        for c in range(c1, c2 + 1):
            if (c, f) in tapadas:
                continue
            x = d(c, f)
            t = x["texto"]
            if not t.strip():
                continue
            if (c, f) in ancho_comb:
                ancho_emu = sum(unidades_a_emu(ancho_col(k)) for k in range(c, c + 50) if (k, f) in tapadas or k == c)
            else:
                ancho_emu = unidades_a_emu(ancho_col(c))
            ancho = ancho_emu / EMU_PT - 2 * RELLENO_CELDA_PT
            if es_cifra(x) and f > fin_cab:
                lineas[(c, f)] = 1
                continue
            nuevo = t
            if f <= fin_cab and re.fullmatch(r'\s*total\s*', t, re.I) and t.strip() != "TOTAL":
                # «TOTAL» también en la cabecera (guía: ejemplos A4.6 y 4.2; Memoria 3.4 TERMINADO)
                cambios_txt.append(f"«{t.strip()}» → «TOTAL» (cabecera)")
                nuevo = t = "TOTAL"
            if c == primera and f > fin_cab:
                cuerpo = t.strip("  ")
                sin_vineta = VINETA.sub("", cuerpo)
                if sin_vineta != cuerpo:
                    cambios_txt.append(f"«{cuerpo[:30]}» sin viñeta")
                cuerpo = sin_vineta
                if re.fullmatch(r'total', cuerpo, re.I) and cuerpo != "TOTAL":
                    cambios_txt.append(f"«{cuerpo}» → «TOTAL»")
                    cuerpo = "TOTAL"
                espacios = " " * (SANGRIA * nivel_de.get(sangria_autor(f), 0))
                mc = medir_de(c, f)
                partes = partir("\n".join(l.strip() for l in cuerpo.split("\n")), ancho - mc(espacios, CUERPO_CELDA), mc)
                if espacios and len(partes) > 1:
                    # Con varias líneas, la sangría se repite en cada una (saltos de línea manuales)
                    nuevo = "\n".join(espacios + l for l in partes)
                else:
                    nuevo = espacios + cuerpo
                lineas[(c, f)] = len(partes)
            else:
                lineas[(c, f)] = len(partir(t, ancho, medir_de(c, f)))
            if nuevo != x["texto"]:
                nuevos_textos[(c, f)] = nuevo
    if cambios_txt:
        detalle.append("Textos: " + "; ".join(cambios_txt[:8]))
    if nivel_de:
        detalle.append("Sangrías con espacios: " + ", ".join(f"nivel {n} = {SANGRIA * n} espacios" for n in sorted(set(nivel_de.values()))))

    # Alineación de las columnas de datos con texto: a la izquierda las de textos largos
    izquierda = set()
    for c in range(primera + 1, c2 + 1):
        textos = [d(c, f)["texto"] for f in range(fin_cab + 1, f2 + 1)
                  if (c, f) not in tapadas and d(c, f)["texto"].strip() and not es_cifra(d(c, f))]
        if textos and sum(len(t) for t in textos) / len(textos) > LARGO_TEXTO_IZQUIERDA:
            izquierda.add(c)
    if izquierda:
        detalle.append("Columnas de textos largos, a la izquierda: " + ", ".join(ref(c, 1)[:-1] for c in sorted(izquierda)))

    # Altos de fila y alineación en altura
    altos, arriba = {}, set()
    for f in range(f1, f2 + 1):
        n = max([lineas.get((c, f), 0) for c in range(c1, c2 + 1) if filas_comb.get((c, f), 1) == 1] or [0])
        if n == 0 and not any(d(c, f)["texto"].strip() for c in range(c1, c2 + 1)):
            continue   # fila vacía (separación del autor): se queda como está
        altos[f] = alto_fila(max(n, 1))
        if f > fin_cab and any(lineas.get((c, f), 0) > 1 for c in range(primera + 1, c2 + 1)):
            arriba.add(f)
    cuenta = Counter(altos.values())
    detalle.append("Alto de fila: " + ", ".join(f"{h:g} pt ({n} fila{'s' if n > 1 else ''})" for h, n in sorted(cuenta.items())))
    if arriba:
        detalle.append(f"Alineadas arriba (textos de 2 o más líneas en los datos): fila{'s' if len(arriba) > 1 else ''} "
                       + ", ".join(str(f) for f in sorted(arriba)))

    # Formatos nuevos de cada celda del cuadro
    nuevos_s = {}
    for f in range(f1, f2 + 1):
        for c in range(c1, c2 + 1):
            x = d(c, f)
            if x["xml"] is None and (c, f) not in tapadas:
                continue
            if f <= fin_cab:
                h = "left" if c == primera else "center"
            elif c == primera:
                h = "left"
            elif es_cifra(x) or not x["texto"].strip():
                h = "center"
            else:
                h = "left" if c in izquierda else "center"
            al = {"horizontal": h, "vertical": "top" if f in arriba else "center"}
            if not es_cifra(x) or f <= fin_cab:
                al["wrapText"] = "1"
            nuevos_s[(c, f)] = estilos.nuevo(x["s"], al)
    negritas = [ref(c, f) for (c, f) in nuevos_s if es_negrita(estilos.fuente_de(d(c, f)["s"])) and d(c, f)["texto"].strip()]
    detalle.append(f"Letra de las celdas: {LETRA_CELDA} {CUERPO_CELDA:g} pt".replace(".", ",")
                   + (f"; lo que iba en negrita, en {LETRA_CELDA_NEGRITA} ({len(negritas)} celda{'s' if len(negritas) > 1 else ''}: "
                      + ", ".join(negritas[:8]) + ("…" if len(negritas) > 8 else "") + ")" if negritas else ""))
    detalle.append("Alineación: cabecera, la primera a la izquierda y las demás al centro; primera columna a la "
                   "izquierda; cifras al centro; centrado en altura salvo las filas de arriba")

    # Textos enriquecidos (con varios formatos) de las celdas del cuadro: también en Roboto Light 7,5, sin negrita
    usados = {int(re.search(r'<v>(\d+)</v>', d(c, f)["xml"]).group(1))
              for (c, f) in nuevos_s if d(c, f)["tipo"] == "s" and d(c, f)["xml"] and "<v>" in d(c, f)["xml"]}
    nuevas_si = list(compartidos)
    for i in usados:
        if "<r>" in nuevas_si[i]:
            def rpr(m):
                letra = LETRA_CELDA_NEGRITA if es_negrita(m.group(1)) else LETRA_CELDA
                dentro = re.sub(r'<(rFont|sz|b|family|scheme)\b[^>]*/>', "", m.group(1))
                return f'<rPr><rFont val="{letra}"/>{dentro}<sz val="{CUERPO_CELDA:g}"/><family val="2"/></rPr>'
            nuevas_si[i] = re.sub(r'<rPr>(.*?)</rPr>', rpr, nuevas_si[i], flags=re.S)

    # Escribir: textos nuevos como cadenas compartidas nuevas, formatos y altos de fila
    def celda_nueva(c, f, xml):
        s_nuevo = nuevos_s.get((c, f))
        apertura = xml[:xml.find(">") + 1]
        cuerpo = xml[len(apertura):]
        if s_nuevo is not None:
            apertura = re.sub(r'\ss="\d+"', "", apertura)
            apertura = apertura.replace("<c ", f'<c s="{s_nuevo}" ', 1)
        if (c, f) in nuevos_textos:
            nuevas_si.append(f'<si><t xml:space="preserve">{html.escape(nuevos_textos[(c, f)], quote=False)}</t></si>')
            apertura = re.sub(r'\st="\w+"', "", apertura).replace("<c ", '<c t="s" ', 1)
            if apertura.endswith("/>"):
                apertura = apertura[:-2] + ">"
            cuerpo = f"<v>{len(nuevas_si) - 1}</v></c>"
        return apertura + cuerpo

    def cambiar_celda(m):
        xml = m.group(0)
        r = RE_REF.match(re.search(r'\br="([^"]+)"', xml).group(1))
        c, f = col_num(r.group(1)), int(r.group(2))
        if not (c1 <= c <= c2 and f1 <= f <= f2):
            return xml
        return celda_nueva(c, f, xml)
    hoja_xml = re.sub(r'<c\b[^>]*?(?:/>|>.*?</c>)', cambiar_celda, hoja_xml, flags=re.S)

    def cambiar_fila(m):
        fila = m.group(0)
        f = int(re.search(r'\br="(\d+)"', fila).group(1))
        if f not in altos:
            return fila
        fila = re.sub(r'\s(ht|customHeight)="[^"]*"', "", fila)
        return fila[:-1].rstrip("/") + f' ht="{altos[f]}" customHeight="1"' + ("/>" if fila.endswith("/>") else ">")
    hoja_xml = re.sub(r'<row\b[^>]*?/?>', cambiar_fila, hoja_xml)
    hoja_xml = poner_anchos(hoja_xml, nuevos_anchos)
    faltan = [f for f in altos if not re.search(rf'<row\b[^>]*\br="{f}"', hoja_xml)]
    if faltan:
        detalle.append(f"Aviso: filas sin definir en la hoja ({', '.join(map(str, faltan))}): su alto no se ha cambiado")

    cambios = {ruta_hoja: hoja_xml.encode("utf-8"), "xl/styles.xml": estilos.resultado().encode("utf-8")}
    if nuevas_si != compartidos or nuevos_textos:
        comp = comp_xml
        cuerpo = "".join(nuevas_si)
        comp = re.sub(r'(<sst\b[^>]*>).*(</sst>)', lambda m: m.group(1) + cuerpo + m.group(2), comp, count=1, flags=re.S)
        comp = re.sub(r'\buniqueCount="\d+"', f'uniqueCount="{len(nuevas_si)}"', comp, count=1)
        cambios["xl/sharedStrings.xml"] = comp.encode("utf-8")
    return cambios, detalle, {"c1": c1, "f1": f1, "c2": c2, "f2": f2, "primera": primera, "fin_cabecera": fin_cab}


# ---------------------------------------------------------------- paso 3: cabeceras

CABECERAS = "Cabeceras"
BLANCO = "FFFFFF"
# Nivel de la cabecera (1 = la fila de abajo) → matiz del color de la publicación y color del texto
# (Resumen cuadros, pág. 21: cabecera 1 matiz 1, 2 matiz 2, 3 matiz 3 con texto blanco, 4 sólido con texto blanco)
NIVELES_CABECERA = {1: ("matiz1", None), 2: ("matiz2", None), 3: ("matiz3", BLANCO), 4: ("solido", BLANCO)}
LINEA_BLANCA = ("thin", BLANCO)


def con_estilo(hoja_xml, estilos_celda):
    """La hoja con el formato `s` de estas celdas ((col, fila) → s); las que no existen se crean (vacías) en su
    fila, en orden de columna."""
    pendientes = dict(estilos_celda)

    def cambiar_celda(m):
        xml = m.group(0)
        r = RE_REF.match(re.search(r'\br="([^"]+)"', xml).group(1))
        k = (col_num(r.group(1)), int(r.group(2)))
        if k not in pendientes:
            return xml
        s_nuevo = pendientes.pop(k)
        apertura = xml[:xml.find(">") + 1]
        apertura2 = re.sub(r'\ss="\d+"', "", apertura).replace("<c ", f'<c s="{s_nuevo}" ', 1)
        return apertura2 + xml[len(apertura):]
    hoja_xml = re.sub(r'<c\b[^>]*?(?:/>|>.*?</c>)', cambiar_celda, hoja_xml, flags=re.S)
    if pendientes:
        por_fila = {}
        for (c, f), s_nuevo in pendientes.items():
            por_fila.setdefault(f, []).append((c, s_nuevo))

        def completar_fila(m):
            fila = m.group(0)
            f = int(re.search(r'\br="(\d+)"', fila[:fila.find(">") + 1]).group(1))
            if f not in por_fila:
                return fila
            nuevas = {c: f'<c r="{ref(c, f)}" s="{s_nuevo}"/>' for c, s_nuevo in por_fila.pop(f)}
            if fila.endswith("/>") and "</row>" not in fila:
                return fila[:-2] + ">" + "".join(nuevas[c] for c in sorted(nuevas)) + "</row>"
            apertura = fila[:fila.find(">") + 1]
            cuerpo = fila[len(apertura):-len("</row>")]
            celdas_fila = re.findall(r'<c\b[^>]*?(?:/>|>.*?</c>)', cuerpo, re.S)
            todas = [(col_num(RE_REF.match(re.search(r'\br="([^"]+)"', x).group(1)).group(1)), x) for x in celdas_fila]
            todas += list(nuevas.items())
            # Solo celdas en el cuerpo de la fila (no lleva nada más)
            return apertura + "".join(x for _, x in sorted(todas)) + "</row>"
        hoja_xml = re.sub(r'<row\b[^>]*?/>|<row\b[^>]*>.*?</row>', completar_fila, hoja_xml, flags=re.S)
        if por_fila:
            raise Fallo(f"Faltan filas en la hoja: {', '.join(map(str, sorted(por_fila)))}")
    return hoja_xml


def paso3(trabajo, pid):
    """Cabeceras: fondo con el color de la publicación por nivel (la fila de abajo, matiz 1; encima, matiz 2;
    matiz 3 y sólido con el texto en blanco) y líneas blancas finas entre celdas y entre niveles. La celda de la
    primera columna solo si tiene texto; las columnas estrechas de separación, sin relleno (hueco blanco)."""
    estado = leer_estado(trabajo)
    requiere(estado, [CELDAS], "«Cabeceras»")
    cuadro = next((p.get("cuadro") for p in reversed(estado["pasos"][:estado["actual"] + 1]) if p.get("cuadro")), None)
    if not cuadro:
        raise Fallo("No sé dónde está el cuadro: vuelve a hacer el paso «Celdas»")
    _, pasos = nombres(trabajo)
    base = pasos / estado["pasos"][estado["actual"]]["archivo"]
    hoja = estado.get("hoja") or "Cuadro datos"
    pub = publicacion(pid)
    with zipfile.ZipFile(base) as z:
        cambios, detalle = cabeceras(z, hoja, cuadro, pub)
    return nuevo_paso(trabajo, CABECERAS, cambios, detalle, cuadro)


def cabeceras(z, hoja, cuadro, pub):
    ruta_hoja = hoja_de(z, hoja)
    hoja_xml = z.read(ruta_hoja).decode("utf-8")
    _, compartidos = leer_compartidos(z)
    estilos = Estilos(z.read("xl/styles.xml").decode("utf-8"))
    todas = celdas_hoja(hoja_xml, compartidos)
    rangos = combinadas(hoja_xml)
    ancho_col = anchos_columnas(hoja_xml)
    c1, f1, c2, f2 = cuadro["c1"], cuadro["f1"], cuadro["c2"], cuadro["f2"]
    primera, fin_cab = cuadro["primera"], cuadro["fin_cabecera"]
    colores = matices(pub["color"])
    detalle = []

    def texto(c, f):
        return todas.get((c, f), {}).get("texto", "").strip()

    def estilo(c, f):
        return todas.get((c, f), {}).get("s", 0)
    # Celdas combinadas de la cabecera: la de arriba a la izquierda manda; su nivel, el de su fila de abajo
    combinada = {}
    for a1, b1, a2, b2 in rangos:
        if b1 <= fin_cab and b1 >= f1 and a1 >= c1 and a2 <= c2:
            for c in range(a1, a2 + 1):
                for f in range(b1, min(b2, fin_cab) + 1):
                    combinada[(c, f)] = (a1, b1, a2, min(b2, fin_cab))
    # Niveles: solo cuentan las filas con textos de cabecera en las columnas de datos (no las que solo lleva una
    # celda combinada de la primera columna, como las unidades de Memoria 4.1); la de abajo es el nivel 1
    filas_cab = sorted({combinada.get((c, f), (c, f))[1] for f in range(f1, fin_cab + 1) for c in range(primera + 1, c2 + 1)
                        if texto(*combinada.get((c, f), (c, f))[:2])}) or [fin_cab]

    def nivel_de(b2):
        return max(1, len([f for f in filas_cab if f > b2]) + 1) if b2 >= filas_cab[0] else len(filas_cab)
    if len(filas_cab) > 4:
        detalle.append(f"Aviso: la cabecera tiene {len(filas_cab)} niveles; la guía prevé 4 (los de arriba van en sólido)")
    nuevos, usados = {}, {}
    for f in range(f1, fin_cab + 1):
        for c in range(primera, c2 + 1):
            a1, b1, a2, b2 = combinada.get((c, f), (c, f, c, f))
            ancla = (a1, b1)
            estrecha = ancho_col(c) < COLUMNA_ESTRECHA and a1 == a2
            if estrecha or not texto(*ancla) and ancla not in [(k[0], k[1]) for k in combinada.values()]:
                continue
            if c == primera and not texto(*ancla):
                continue
            nivel = min(4, nivel_de(b2))
            clave_color, letra = NIVELES_CABECERA[nivel]
            # Líneas blancas: a los lados y debajo si hay otro nivel de cabecera debajo
            lados = {}
            if c == a1:
                lados["left"] = LINEA_BLANCA
            if c == a2:
                lados["right"] = LINEA_BLANCA
            if f == b2 and b2 < fin_cab:
                lados["bottom"] = LINEA_BLANCA
            if f == b1 and b1 > f1:
                lados["top"] = LINEA_BLANCA
            nuevos[(c, f)] = estilos.variante(estilo(c, f), relleno=colores[clave_color], borde=lados,
                                              letra=letra or "000000")
            usados.setdefault(nivel, set()).add(ancla)
    for nivel in sorted(usados):
        clave_color, letra = NIVELES_CABECERA[nivel]
        detalle.append(f"Cabecera {nivel}: {clave_color.replace('matiz', 'matiz ').replace('solido', 'sólido')} "
                       f"#{colores[clave_color]}" + (", texto en blanco" if letra else "") + f" ({len(usados[nivel])} celda{'s' if len(usados[nivel]) > 1 else ''})")
    detalle.append("Líneas blancas finas entre las celdas de la cabecera y entre sus niveles")
    estrechas = [ref(c, 1)[:-1] for c in range(primera + 1, c2 + 1) if 0 < ancho_col(c) < COLUMNA_ESTRECHA]
    if estrechas:
        detalle.append("Columnas de separación sin relleno (hueco blanco entre grupos): " + ", ".join(estrechas))
    if not texto(primera, fin_cab) and not any(texto(primera, f) for f in range(f1, fin_cab + 1)):
        detalle.append("Esquina de la primera columna sin relleno (no lleva texto)")
    hoja_xml = con_estilo(hoja_xml, nuevos)
    return {ruta_hoja: hoja_xml.encode("utf-8"), "xl/styles.xml": estilos.resultado().encode("utf-8")}, detalle


# ---------------------------------------------------------------- paso 4: líneas y fondos

LINEAS_Y_FONDOS = "Líneas y fondos"
# Matices del blanco (Resumen cuadros, pág. 21): 1 = −5 %, 2 = −15 %, 5 = −50 %
BLANCO_MATIZ_1, BLANCO_MATIZ_2, BLANCO_MATIZ_5 = "F2F2F2", "D9D9D9", "808080"
LINEA_FILAS = ("thin", BLANCO_MATIZ_2)      # separa filas
LINEA_OSCURA = ("thin", BLANCO_MATIZ_5)     # separa la fila TOTAL (y lo que se añada a mano)
RE_TOTAL = re.compile(r'\s*total\b', re.I)


def paso4(trabajo, pid=None):
    """Líneas y fondos del cuerpo del cuadro (Resumen cuadros, pág. 21, y Ejemplos)."""
    estado = leer_estado(trabajo)
    requiere(estado, [CABECERAS], "«Líneas y fondos»")
    cuadro = next((p.get("cuadro") for p in reversed(estado["pasos"][:estado["actual"] + 1]) if p.get("cuadro")), None)
    if not cuadro:
        raise Fallo("No sé dónde está el cuadro: vuelve a hacer el paso «Celdas»")
    _, pasos = nombres(trabajo)
    base = pasos / estado["pasos"][estado["actual"]]["archivo"]
    hoja = estado.get("hoja") or "Cuadro datos"
    with zipfile.ZipFile(base) as z:
        cambios, detalle = lineas_y_fondos(z, hoja, cuadro)
    return nuevo_paso(trabajo, LINEAS_Y_FONDOS, cambios, detalle, cuadro)


def lineas_y_fondos(z, hoja, cuadro):
    ruta_hoja = hoja_de(z, hoja)
    hoja_xml = z.read(ruta_hoja).decode("utf-8")
    _, compartidos = leer_compartidos(z)
    estilos = Estilos(z.read("xl/styles.xml").decode("utf-8"))
    todas = celdas_hoja(hoja_xml, compartidos)
    ancho_col = anchos_columnas(hoja_xml)
    c1, f1, c2, f2 = cuadro["c1"], cuadro["f1"], cuadro["c2"], cuadro["f2"]
    primera, fin_cab = cuadro["primera"], cuadro["fin_cabecera"]
    detalle = []

    def texto(c, f):
        return todas.get((c, f), {}).get("texto", "")

    def estilo(c, f):
        return todas.get((c, f), {}).get("s", 0)
    columnas = [c for c in range(primera, c2 + 1) if ancho_col(c) > 0]
    datos_cols = [c for c in columnas if c != primera]
    filas = list(range(fin_cab + 1, f2 + 1))
    if not filas:
        raise Fallo("El cuadro no tiene filas de datos bajo la cabecera")

    def sangrada(f):
        t = texto(primera, f)
        return t.strip() != "" and t.startswith(" ")

    def sin_datos(f):
        return not any(texto(c, f).strip() for c in datos_cols)
    # Filas de total: «TOTAL» (la principal, la última) y «Total …» (subtotales)
    totales = [f for f in filas if RE_TOTAL.match(texto(primera, f)) and not sangrada(f)]
    principal = next((f for f in reversed(totales) if texto(primera, f).strip().upper() == "TOTAL"), totales[-1] if totales else None)
    subtotales = [f for f in totales if f != principal]
    # Títulos de bloque: concepto sin sangría y sin datos en las demás columnas
    bloques = [f for f in filas if texto(primera, f).strip() and not sangrada(f) and sin_datos(f) and f not in totales]
    # Columna TOTAL: la de datos cuya cabecera dice «TOTAL»
    col_total = next((c for c in datos_cols if any(texto(c, f).strip().upper() == "TOTAL" for f in range(f1, fin_cab + 1))), None)
    # La fila TOTAL va en blanco matiz 2, o en matiz 5 si el 2 ya lo usan títulos de bloque o subtotales (Ejemplos,
    # 1.4 y A2.2); una columna TOTAL también va en matiz 2 y no lo cambia (Ejemplos, 4.2)
    usa_matiz_2 = bool(bloques or subtotales)
    fondo_total = BLANCO_MATIZ_5 if usa_matiz_2 else BLANCO_MATIZ_2
    letra_total = BLANCO if fondo_total == BLANCO_MATIZ_5 else None

    nuevos = {}
    ultima = filas[-1]
    for i, f in enumerate(filas):
        siguiente = filas[i + 1] if i + 1 < len(filas) else None
        es_total = f in totales
        for c in range(primera, c2 + 1):
            if ancho_col(c) == 0:
                continue
            lados, relleno, letra = {}, None, None
            # Línea de debajo: entre filas, gris claro; encima de la fila TOTAL, oscura; la última fila, sin línea
            if siguiente is not None:
                lados["bottom"] = LINEA_OSCURA if siguiente == principal else LINEA_FILAS
            if f == principal and i > 0:
                lados["top"] = LINEA_OSCURA
            if c == primera:
                relleno = BLANCO_MATIZ_1
                if f in bloques:
                    relleno = BLANCO_MATIZ_2
                # Primera columna: líneas blancas, salvo entre conceptos sangrados (sin línea)
                if siguiente is not None and siguiente != principal:
                    lados["bottom"] = None if sangrada(f) and sangrada(siguiente) else ("thin", BLANCO)
                    if lados["bottom"] is None:
                        del lados["bottom"]
            if c == col_total and not es_total:
                relleno = BLANCO_MATIZ_2
                lados["left"] = ("thin", BLANCO)
                if siguiente is not None and siguiente != principal:
                    lados["bottom"] = ("thin", BLANCO)
            if es_total:
                relleno = fondo_total if f == principal else BLANCO_MATIZ_2
                letra = letra_total if f == principal else None
            nuevos[(c, f)] = estilos.variante(estilo(c, f), relleno=relleno, borde=lados,
                                              letra=letra if letra else None)
    # Detalle
    detalle.append("Líneas horizontales finas entre filas en blanco matiz 2 (#D9D9D9); la última fila, sin línea")
    detalle.append("Primera columna: fondo blanco matiz 1 (#F2F2F2) con líneas blancas; sin línea entre conceptos sangrados")
    if bloques:
        detalle.append(f"Títulos de bloque (sin datos en las demás columnas), fondo blanco matiz 2: "
                       + ", ".join(f"«{texto(primera, f).strip()[:30]}»" for f in bloques[:6]) + ("…" if len(bloques) > 6 else ""))
    for f in subtotales:
        detalle.append(f"Subtotal «{texto(primera, f).strip()[:40]}»: fondo blanco matiz 2 en toda la fila")
    if principal:
        detalle.append(f"Fila TOTAL (fila {principal}): fondo blanco matiz {'5 (#808080) con el texto en blanco, porque el matiz 2 ya está usado' if fondo_total == BLANCO_MATIZ_5 else '2 (#D9D9D9)'}"
                       "; línea oscura encima (blanco matiz 5); sin hueco en las columnas de separación")
    else:
        detalle.append("Sin fila TOTAL")
    if col_total:
        detalle.append(f"Columna TOTAL ({ref(col_total, 1)[:-1]}): fondo blanco matiz 2 con línea blanca a la izquierda y entre filas")
    detalle.append("Aviso (recordatorio): la línea oscura (blanco matiz 5) solo va encima de la fila TOTAL; si hay que "
                   "separar otros conceptos importantes, añádela a mano en Excel")
    hoja_xml = con_estilo(hoja_xml, nuevos)
    return {ruta_hoja: hoja_xml.encode("utf-8"), "xl/styles.xml": estilos.resultado().encode("utf-8")}, detalle


# ---------------------------------------------------------------- comparar con el original (de Gráficos Excel BdE)

MAXIMO_EJEMPLOS = 6
RE_TRIMESTRE = re.compile(r'\b(?:[IV]{1,3}\s*TR|T\s?[1-4]|Q\s?[1-4]|[1-4]\s?[TQ])\b')


def celdas_libro(z):
    """{hoja: {ref: (valor, formato)}} de todas las celdas con valor."""
    _, compartidos = leer_compartidos(z)
    estilos = Estilos(z.read("xl/styles.xml").decode("utf-8")) if "xl/styles.xml" in z.namelist() else None
    todo = {}
    for nombre, ruta, _ in hojas_libro(z):
        hoja = z.read(ruta).decode("utf-8")
        celdas = {}
        for (c, f), d in celdas_hoja(hoja, compartidos).items():
            if d["texto"] == "":
                continue
            celdas[ref(c, f)] = (d["texto"], formato_numero(estilos, d["s"]) if estilos else "General")
        todo[nombre] = celdas
    return todo


def textos_libro(z):
    """Textos de los cuadros de texto (de las hojas y de dentro de los gráficos) y de los gráficos (títulos,
    títulos de ejes, etiquetas escritas a mano, nombres de serie escritos en el gráfico)."""
    textos = []
    for n in sorted(z.namelist()):
        if re.match(r'xl/drawings/drawing\d+\.xml$', n):
            for cuerpo in re.findall(r'<(?:xdr|cdr):txBody>(.*?)</(?:xdr|cdr):txBody>', z.read(n).decode("utf-8"), re.S):
                t = " ".join(html.unescape("".join(re.findall(r'<a:t>([^<]*)</a:t>', p_)))
                             for p_ in re.findall(r'<a:p>.*?</a:p>', cuerpo, re.S))
                textos.append(t)
        elif re.match(r'xl/charts/chart\d+\.xml$', n):
            xml = z.read(n).decode("utf-8")
            for rico in re.findall(r'<c:rich>(.*?)</c:rich>', xml, re.S):
                textos.append(" ".join(html.unescape("".join(re.findall(r'<a:t>([^<]*)</a:t>', p_)))
                                       for p_ in re.findall(r'<a:p>.*?</a:p>', rico, re.S)))
    return [t for t in (re.sub(r'\s+', " ", t).strip() for t in textos) if t]


def sin_ortotipografia(t):
    t = t.replace(" ", " ").replace(" ", " ")
    t = re.sub(r'[«»“”„"]', '"', t).replace("’", "'").replace("‘", "'")
    return re.sub(r'\s+', " ", t).strip()


def tipo_cambio(a, b):
    na, nb = sin_ortotipografia(a), sin_ortotipografia(b)
    if na == nb or re.sub(r'[^\w]', "", na) == re.sub(r'[^\w]', "", nb):
        return "ortotipografía"
    if na.lower() == nb.lower():
        return "mayúsculas"
    if RE_TRIMESTRE.search(a) or RE_TRIMESTRE.search(b):
        return "trimestres"
    if re.findall(r'\d+', a) != re.findall(r'\d+', b):
        return "cifras"
    return "texto"


def es_numero(v):
    try:
        float(v)
        return True
    except (TypeError, ValueError):
        return False


def recortar(t, n=70):
    return t if len(t) <= n else t[:n - 1] + "…"


def lista_corta(cosas):
    cosas = list(cosas)
    texto = ", ".join(cosas[:MAXIMO_EJEMPLOS])
    return texto + (f" y {len(cosas) - MAXIMO_EJEMPLOS} más" if len(cosas) > MAXIMO_EJEMPLOS else "")


def comparar_libros(zo, zf, idioma_="es"):
    """Avisos de lo que ha cambiado del original al maquetado en textos y cifras (no en la colocación ni en
    el formato de letra): datos que faltan, datos cambiados, formatos de número, series y textos."""
    faltan, cambios, info = [], [], []
    # 1. Datos de las hojas
    co, cf = celdas_libro(zo), celdas_libro(zf)
    for hoja, celdas in co.items():
        if hoja not in cf:
            faltan.append(f"falta la hoja «{hoja}» con {len(celdas)} datos")
            continue
        fin = cf[hoja]
        perdidas = [r for r in celdas if r not in fin]
        if perdidas:
            faltan.append((f"faltan {len(perdidas)} datos" if len(perdidas) > 1 else "falta 1 dato")
                          + f" en la hoja «{hoja}»: "
                          + lista_corta(f"{r} («{recortar(' '.join(celdas[r][0].split()), 25)}»)" for r in perdidas))
        cambiadas = [r for r in celdas if r in fin and celdas[r][0] != fin[r][0]
                     and not (es_numero(celdas[r][0]) and es_numero(fin[r][0])
                              and math.isclose(float(celdas[r][0]), float(fin[r][0]), rel_tol=1e-9, abs_tol=1e-12))]
        # Columnas enteras multiplicadas por 100 
        por_columna = {}
        for r in cambiadas:
            por_columna.setdefault(re.match(r'[A-Z]+', r).group(0), []).append(r)
        for col, refs in por_columna.items():
            if all(es_numero(celdas[r][0]) and es_numero(fin[r][0]) and float(celdas[r][0]) != 0
                   and math.isclose(float(fin[r][0]) / float(celdas[r][0]), 100, rel_tol=1e-6) for r in refs):
                cambios.append(f"cifras: datos de «{hoja}» {refs[0]}:{refs[-1]} multiplicados por 100 "
                               "(el % pasa a las unidades)")
                cambiadas = [r for r in cambiadas if r not in refs]
        por_tipo = {}
        for r in cambiadas:
            por_tipo.setdefault(tipo_cambio(celdas[r][0], fin[r][0]), []).append(r)
        for tipo, refs in por_tipo.items():
            cambios.append(f"{tipo} en «{hoja}»: " + lista_corta(
                f"{r} «{recortar(' '.join(celdas[r][0].split()), 40)}» → «{recortar(' '.join(fin[r][0].split()), 40)}»"
                for r in refs))
        formatos = {}
        for r in celdas:
            if r in fin and celdas[r][1] != fin[r][1]:
                formatos.setdefault((celdas[r][1], fin[r][1]), []).append(r)
        for (a, b), refs in formatos.items():
            que = "fechas" if re.search(r'[ymd]', re.sub(r'"[^"]*"|\[[^\]]*\]', "", b), re.I) else "formato de números"
            cambios.append(f"{que} en «{hoja}»: {len(refs)} celda(s) ({lista_corta(refs[:3])}) "
                           f"de «{a}» a «{b}»")
        nuevas = [r for r in fin if r not in celdas]
        if nuevas:
            columnas = sorted({re.match(r'[A-Z]+', r).group(0) for r in nuevas})
            info.append(f"Datos añadidos en «{hoja}»: {len(nuevas)} celda(s), columna(s) {', '.join(columnas)}")
    # 2. Textos de las formas (rótulo, título, unidades, FUENTES…)
    to, tf = textos_libro(zo), textos_libro(zf)
    resto_o, resto_f = list(to), list(tf)
    for t in to:
        if t in resto_f:
            resto_o.remove(t)
            resto_f.remove(t)
    resto_o.sort(key=len, reverse=True)
    sueltos = []

    def parecido(t, u):
        return difflib.SequenceMatcher(None, t.lower(), u.lower(), autojunk=False).ratio()

    def separado(palabras):
        """Las primeras palabras que forman, ellas solas, otro texto del maquetado (p. ej. «Gráfico 2.6», que el
        paso 1 separa del título): se dan por buenas y se quitan. Devuelve cuántas."""
        for k in range(len(palabras), 0, -1):
            trozo = sin_ortotipografia(" ".join(palabras[:k])).lower()
            otro = next((u for u in resto_f if sin_ortotipografia(u).lower() == trozo), None)
            if otro:
                resto_f.remove(otro)
                return k
        return 0

    for t in resto_o:
        mejor = max(resto_f, key=lambda u: parecido(t, u), default=None)
        if mejor is None or parecido(t, mejor) < 0.6:
            sueltos.append(t)
            continue
        resto_f.remove(mejor)
        a, b = t.split(" "), mejor.split(" ")
        for op, i1, i2, j1, j2 in difflib.SequenceMatcher(None, [w.lower() for w in a], [w.lower() for w in b],
                                                          autojunk=False).get_opcodes():
            if op == "equal":
                # Mismas palabras sin mirar mayúsculas: avisar de las que cambian de caja
                distintas = [(x, y) for x, y in zip(a[i1:i2], b[j1:j2]) if x != y]
                if distintas:
                    cambios.append("mayúsculas: " + ", ".join(f"«{x}» → «{y}»" for x, y in distintas[:MAXIMO_EJEMPLOS])
                                   + f" (en «{recortar(mejor, 50)}»)")
                continue
            if op in ("delete", "replace"):
                i1 += separado(a[i1:i2])
                if i1 == i2 and op == "delete":
                    continue
            sa, sb = " ".join(a[i1:i2]), " ".join(b[j1:j2])
            if not sa and not sb:
                continue
            if not sb:
                faltan.append(f"falta «{recortar(sa)}» en «{recortar(t, 50)}»")
            elif not sa:
                info.append(f"Añadido «{recortar(sb)}» en «{recortar(mejor, 50)}»")
            else:
                # Letra a letra: si solo se han quitado letras o cifras (además de signos), es que falta algo
                ops = difflib.SequenceMatcher(None, sa, sb, autojunk=False).get_opcodes()
                quitado = "".join(sa[x1:x2] for o, x1, x2, _, _ in ops if o == "delete")
                if all(o in ("equal", "delete") for o, *_ in ops) and re.search(r'\w\w', quitado):
                    faltan.append(f"falta «{recortar(quitado.strip())}» en «{recortar(t, 50)}»")
                else:
                    cambios.append(f"{tipo_cambio(sa, sb)}: «{recortar(sa)}» → «{recortar(sb)}»")
    for t in sueltos:
        # Un texto repartido en varios cuadros: están todas sus palabras
        palabras = Counter(w.lower() for u in resto_f for w in u.split(" "))
        if all(palabras[w.lower()] for w in t.split(" ")):
            continue
        faltan.append(f"falta el texto «{recortar(t)}»")
    for t in resto_f:
        if not any(t.lower() in u.lower() for u in to):
            info.append(f"Texto nuevo: «{recortar(t)}»")
    lineas = [f"Aviso: {f}" for f in faltan]
    if cambios:
        lineas.append(f"Aviso: {len(cambios)} cambio(s) de textos o cifras respecto al original; revísalos:")
        lineas += [f"Cambio de {c}" for c in cambios]
    lineas += info
    if not faltan and not cambios:
        lineas.insert(0, "No falta ningún dato ni texto del original y no ha cambiado ninguna cifra")
    return lineas


def comparar(trabajo):
    """Compara la copia de trabajo (lo guardado: la más reciente de las dos) con el Excel del autor: datos de
    todas las hojas y textos de las formas; no la colocación ni el formato. No crea versión."""
    estado = leer_estado(trabajo)
    _, pasos = nombres(trabajo)
    origen = Path(estado.get("origen", ""))
    if not origen.is_file():
        origen = pasos / estado["pasos"][0]["archivo"]
    actual = copia_actual(trabajo)
    with zipfile.ZipFile(origen) as zo, zipfile.ZipFile(actual) as zf:
        lineas = comparar_libros(zo, zf, estado.get("idioma", "es"))
    return {"trabajo": str(trabajo), **estado, "comparacion": lineas, "comparado": str(actual), "original": str(origen)}



def pendiente(nombre):
    def paso(trabajo, pid=None):
        raise Fallo(f"El paso «{nombre}» todavía no está hecho: lo construimos a continuación.")
    return paso


def nombre_terminado(origen, carpeta):
    stem = origen.stem
    if re.search(r'\bORIGINALES\b', stem):
        base = re.sub(r'\bORIGINALES\b', "TERMINADOS", stem)
    elif re.search(r'\bORIGINAL\b', stem):
        base = re.sub(r'\bORIGINAL\b', "TERMINADO", stem)
    else:
        base = stem + " TERMINADO"
    destino, n = carpeta / f"{base}.xlsx", 2
    while destino.exists():   # nunca se pisa un TERMINADO que ya exista
        destino, n = carpeta / f"{base} ({n}).xlsx", n + 1
    return destino


def copia_actual(trabajo):
    """La copia de trabajo más reciente (el usuario puede haber guardado cambios en «(2)»)."""
    trabajo = Path(trabajo)
    b = trabajo.with_name(trabajo.stem + " (2).xlsx")
    return max([c for c in (trabajo, b) if c.exists()], key=lambda c: c.stat().st_mtime)


def terminar(trabajo):
    """Guarda la copia de trabajo como «… TERMINADO.xlsx» junto al original y borra todo lo generado: las dos
    copias de trabajo y la carpeta de pasos. El original del autor no se toca."""
    trabajo, pasos = nombres(trabajo)
    estado = leer_estado(trabajo)
    origen = Path(estado.get("origen", ""))
    carpeta = origen.parent if origen.parent.is_dir() else trabajo.parent
    destino = nombre_terminado(origen if origen.name else trabajo, carpeta)
    shutil.copyfile(copia_actual(trabajo), destino)
    os.chmod(destino, 0o644)
    return {"terminado": str(destino), "borrados": borrar_generados(trabajo)}


# ---------------------------------------------------------------- configuración

def medidas_reticula():
    """Ancho y alto de la retícula en puntos, para que la app encuadre Excel en el cuadro."""
    global _medidas_reticula
    if _medidas_reticula is None:
        ret = CONFIG["reticula"]
        with zipfile.ZipFile(PROYECTO / ret["archivo"]) as z:
            dibujo = z.read(dibujo_de_hoja(z, ret["hoja"])).decode("utf-8")
        grupo = next(a.group(0) for a in ANCLA.finditer(dibujo) if nombre_forma(a.group(0)) == ret["grupo"])
        cx, cy = tamano(grupo, escala_grupo=True)
        _medidas_reticula = [round(cx / EMU_PT, 1), round(cy / EMU_PT, 1)]
    return _medidas_reticula


_medidas_reticula = None


def guardar_publicacion(datos):
    """Alta o cambio de una publicación: {"id"?, "nombre", "color" (el sólido), "tema" (paleta, opcional)}."""
    pub = json.loads(datos)
    nombre = pub.get("nombre", "").strip()
    color = pub.get("color", "").strip().lstrip("#").upper()
    if not nombre:
        raise Fallo("Falta el nombre de la publicación")
    if not re.fullmatch(r"[0-9A-F]{6}", color):
        raise Fallo(f"El color «{color}» no es un hexadecimal de 6 cifras")
    pid = pub.get("id") or re.sub(r"[^a-z0-9]+", "-", nombre.lower().translate(str.maketrans("áéíóúüñ", "aeiouun"))).strip("-")
    nueva = {"id": pid, "nombre": nombre, "color": color, "tema": (pub.get("tema") or "").strip() or None}
    lista = CONFIG["publicaciones"]
    for i, p in enumerate(lista):
        if p["id"] == pid:
            lista[i] = nueva
            break
    else:
        lista.append(nueva)
    escribir_config()
    return {"publicacion": pid}


def borrar_publicacion(pid):
    publicacion(pid)
    CONFIG["publicaciones"] = [p for p in CONFIG["publicaciones"] if p["id"] != pid]
    escribir_config()
    return {}


def escribir_config():
    texto = json.dumps(CONFIG, ensure_ascii=False, indent=2)
    # Una publicación por línea, como estaba a mano
    texto = re.sub(r'\{\n\s+("(?:id|nombre)".*?)\n\s+\}', lambda m: "{" + re.sub(r",\n\s+", ", ", m.group(1)) + "}", texto, flags=re.S)
    ARCHIVO_CONFIG.write_text(texto + "\n", encoding="utf-8")


ARCHIVO_PALETAS = MOTOR / "paletas.json"


def paletas(actualizar=None):
    """Las paletas de Excel con sus 10 colores, en el orden del menú de Excel. Se leen de una copia junto al
    motor: la carpeta de Excel es de otra app y macOS frena o pide permiso a quien entra en ella (y a la app
    la trata como nueva cada vez que se compila). Con «actualizar» se vuelven a leer de Excel."""
    if ARCHIVO_PALETAS.exists() and not actualizar:
        return {"paletas": json.loads(ARCHIVO_PALETAS.read_text(encoding="utf-8")), "carpeta": str(CARPETA_PALETAS)}
    lista = []
    for archivo in sorted(CARPETA_PALETAS.glob("*.xml"), key=lambda f: f.name.lower()):
        xml = archivo.read_text(encoding="utf-8", errors="replace")
        nombre = re.search(r'<a:clrScheme\b[^>]*\bname="([^"]*)"', xml)
        colores = []
        for clave in CLAVES_PALETA:
            m = re.search(rf'<a:{clave}>\s*<a:(?:srgbClr val|sysClr\b[^>]*\blastClr)="([0-9A-Fa-f]{{6}})"', xml)
            colores.append({"clave": clave, "hex": m.group(1).upper() if m else "000000"})
        # Se identifica por el archivo: el nombre de dentro puede repetirse con otros colores
        lista.append({"id": archivo.stem, "nombre": nombre.group(1) if nombre else archivo.stem,
                      "archivo": archivo.name, "colores": colores})
    ARCHIVO_PALETAS.write_text(json.dumps(lista, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return {"paletas": lista, "carpeta": str(CARPETA_PALETAS)}


def info(archivo):
    with zipfile.ZipFile(archivo) as z:
        hoja, motivo = hoja_cuadro(z)
        hojas = [h[0] for h in hojas_libro(z)]
        dibujo = dibujo_de_hoja(z, hoja)
        formas = []
        if dibujo and dibujo in z.namelist():
            for i, m in enumerate(ANCLA.finditer(z.read(dibujo).decode("utf-8"))):
                formas.append({"orden": i, "nombre": nombre_forma(m.group(0)), "texto": texto_forma(m.group(0))[:60]})
    return {"archivo": str(archivo), "idioma": idioma(archivo), "hojas": hojas, "hoja": hoja, "motivo_hoja": motivo,
            "formas": formas}


ORDENES = {"empezar": empezar, "estado": lambda t: {"trabajo": t, **leer_estado(t)}, "ir": ir, "reiniciar": reiniciar,
           "paso1": paso1, "paso2": paso2,
           "paso3": paso3, "paso4": paso4,
           "comparar": comparar, "terminar": terminar, "info": info, "publicaciones": lambda: {},
           "guardar_publicacion": guardar_publicacion, "borrar_publicacion": borrar_publicacion, "paletas": paletas}


def main(args):
    if not args or args[0] not in ORDENES:
        print(__doc__, file=sys.stderr)
        return 2
    try:
        res = ORDENES[args[0]](*args[1:])
        res["publicaciones"] = [{**p, "matices": matices(p["color"])} for p in CONFIG["publicaciones"]]
        if args[0] in ("empezar", "estado", "ir", "reiniciar") or args[0].startswith("paso"):
            res["reticula_pt"] = medidas_reticula()
        res["muestrario"] = CONFIG.get("muestrario", [])
        print(json.dumps({"ok": True, **res}, ensure_ascii=False))
        return 0
    except (Fallo, OSError, zipfile.BadZipFile, KeyError) as e:
        print(json.dumps({"ok": False, "error": str(e)}, ensure_ascii=False))
        return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
