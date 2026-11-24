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
  maquetar_cuadros.py aplicar <trabajo.xlsx> <id_publicacion> <paso:propuesta>
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


def nuevo_paso(trabajo, titulo, cambios, detalle, extra=None, propuestas=None, aplica=None):
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
    # ¿Se sale el cuadro de la retícula? (petición del usuario, 2026-11-21: avisar para ver cómo reducirlo)
    if extra and isinstance(extra, dict) and "c1" in extra:
        detalle = list(detalle) + desborde(pasos / archivo, estado.get("hoja"), extra)
    solo_lectura(pasos / archivo)
    shutil.copyfile(pasos / archivo, trabajo)
    estado["pasos"].append({"n": n, "titulo": titulo, "archivo": archivo, "detalle": detalle, **({"cuadro": extra} if extra else {}),
                            **({"propuestas": propuestas} if propuestas else {}), **({"aplica": aplica} if aplica else {})})
    estado["actual"] = n
    guardar_estado(trabajo, estado)
    return {"trabajo": str(trabajo), **estado}


def reescribir_zip(origen, destino, cambios):
    """Copia el .xlsx entrada a entrada, en el mismo orden y compresión; solo cambia las de `cambios`."""
    en_memoria = isinstance(destino, io.BytesIO)
    tmp = destino if en_memoria else Path(str(destino) + ".tmp")
    with zipfile.ZipFile(origen) as zin, zipfile.ZipFile(tmp, "w") as zout:
        # Si una hoja pierde fórmulas (Arg_02: las cabeceras «II S» eran =D2!$D$3 y pasan a texto), la cadena de
        # cálculo del libro (calcChain.xml) apunta a fórmulas que ya no están y Excel da el libro por dañado: se
        # quita y Excel la rehace al abrir
        nombres_zip = zin.namelist()
        quitar_calc = "xl/calcChain.xml" in nombres_zip and any(
            n.startswith("xl/worksheets/") and n in nombres_zip and datos is not None
            and len(re.findall(rb"<f[ >]", datos)) < len(re.findall(rb"<f[ >]", zin.read(n)))
            for n, datos in cambios.items())
        for info in zin.infolist():
            if quitar_calc and info.filename == "xl/calcChain.xml":
                continue
            datos = cambios.get(info.filename)
            datos = datos if datos is not None else zin.read(info.filename)
            if quitar_calc and info.filename == "[Content_Types].xml":
                datos = re.sub(rb'<Override\b[^>]*PartName="/xl/calcChain\.xml"[^>]*/>', b"", datos)
            if quitar_calc and info.filename == "xl/_rels/workbook.xml.rels":
                datos = re.sub(rb'<Relationship\b[^>]*Target="(?:/xl/)?calcChain\.xml"[^>]*/>', b"", datos)
            zout.writestr(info, datos)
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


def pub_de(pid):
    """Los ajustes de la publicación, o ninguno si no se sabe cuál es (pruebas sin publicación)."""
    try:
        return publicacion(pid) if pid else {}
    except Fallo:
        return {}


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


def textos_en_negro(xml, color=None):
    """Todas las propiedades de letra (rPr, defRPr, endParaRPr) con relleno negro (o con `color`, hex). Devuelve el
    xml y los colores que tenía antes lo que no era negro (para el detalle)."""
    antes = []
    relleno_nuevo = f'<a:solidFill><a:srgbClr val="{color}"/></a:solidFill>' if color else NEGRO

    def cambiar(m):
        etiqueta, atributos, dentro = m.group(1), m.group(2), m.group(4) or ""
        h = hijos_a(dentro)
        relleno = next((t for n, t in h if n in RELLENOS_TEXTO), None)
        if not color and relleno and any(r in relleno for r in YA_NEGROS) and "<a:lumMod" not in relleno and "<a:lumOff" not in relleno:
            return m.group(0)
        if relleno or etiqueta == "rPr":
            if relleno:
                c = re.search(r'<a:(srgbClr|schemeClr|sysClr|prstClr)\b[^>]*\b(?:val|lastClr)="([^"]+)"', relleno)
                antes.append(c.group(2) if c else ("sin relleno" if "noFill" in relleno else "degradado/trama"))
        h = [x for x in h if x[0] not in RELLENOS_TEXTO]
        pos = 1 if h and h[0][0] == "ln" else 0
        h.insert(pos, ["solidFill", relleno_nuevo])
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


def entidades_fuente(texto, idioma="es"):
    """Las entidades que cita una fuente: lo que va antes de «con datos de», «a partir de»…, sin paréntesis,
    partido por comas, punto y coma, «y» / «e» («and» en inglés)."""
    t = re.sub(r'\([^)]*\)', "", texto)
    t = re.split(r',?\s+(?:con datos|a partir de|según|elaboración propia|with data|based on)\b', t, flags=re.I)[0]
    t = t.strip().rstrip(".")
    separadores = r'\s*[,;]\s*|\s+(?:y|e)\s+' if idioma == "es" else r'\s*[,;]\s*|\s+and\s+'
    return [p for p in re.split(separadores, t) if p.strip()]


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

    # FUENTE o FUENTES según las entidades citadas (decisión del usuario, 2026-11-17): «Instituto Nacional de
    # Estadística y Banco de España» → FUENTES; «Banco de España, con datos del INE…» → FUENTE (un solo autor)
    for tipo, trozos in parrafos:
        if tipo == "fuente" and len(trozos) > 2:
            nombre = texto_de(trozos[:1]).rstrip(":")
            plural = len(entidades_fuente(texto_de(trozos[2:]), idioma)) >= 2
            base = "SOURCE" if nombre.startswith("SOURCE") else "FUENTE"
            nuevo = base + ("S" if plural else "")
            if nuevo != nombre:
                trozos[0] = (trozos[0][0], nuevo + ":")
                cuenta["numero"] = f"«{nombre}» → «{nuevo}» ({'varias entidades' if plural else 'una sola entidad'})"
                rotulos[:] = [r.replace(nombre + ":", nuevo + ":", 1) for r in rotulos]
    # La fuente y las notas acaban en punto (plantilla y ejemplos: «FUENTE: Banco de España.»)
    for tipo, trozos in parrafos:
        if tipo in ("fuente", "letra", "nota") and trozos and not texto_de(trozos).rstrip().endswith((".", ":", "?", "!")):
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
    if cuenta.get("numero"):
        notas.append(cuenta["numero"])
    if cuenta.get("punto"):
        notas.append(f"punto final en la fuente o las notas ({cuenta['punto']})")
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


def interlineado(ancla, pt, fuente, windows=False):
    """Distancia entre líneas (pt) del párrafo del cuadro: el alto de línea de la fuente (hhea, como Excel)
    por el interlineado del párrafo (sencillo si no lleva). Con `windows`, la mayor entre la del Mac (hhea) y la de
    Windows (OS/2 winAscent + winDescent: Roboto 1,200 frente a 1,172; en Windows FUENTES se cortaba, Arg_01)."""
    ruta = next((c / fuente for c in CARPETAS_FUENTES if (c / fuente).exists()), None)
    factor = 1.171875   # Roboto: (1900 + 500) / 2048
    if ruta:
        d = ruta.read_bytes()
        tablas = {struct.unpack(">4sIII", d[12 + 16 * i:28 + 16 * i])[0]: struct.unpack(">4sIII", d[12 + 16 * i:28 + 16 * i])[2]
                  for i in range(struct.unpack(">H", d[4:6])[0])}
        em = struct.unpack(">H", d[tablas[b"head"] + 18:tablas[b"head"] + 20])[0]
        sube, baja, hueco = struct.unpack(">hhh", d[tablas[b"hhea"] + 4:tablas[b"hhea"] + 10])
        factor = (sube - baja + hueco) / em
        if windows and b"OS/2" in tablas:
            win_sube, win_baja = struct.unpack(">HH", d[tablas[b"OS/2"] + 74:tablas[b"OS/2"] + 78])
            factor = max(factor, (win_sube + win_baja) / em)
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
    # Las ocultas miden 0 (Arg_02: A y B ocultas con su ancho guardado)
    cols = [(int(a), int(b), 0.0 if re.search(r'\bhidden="(1|true)"', c) else float(w)) for c, a, b, w in
            re.findall(r'(<col\b[^>]*?\bmin="(\d+)"[^>]*?\bmax="(\d+)"[^>]*?\bwidth="([\d.]+)"[^>]*>)', hoja)]
    dc = re.search(r'\bdefaultColWidth="([\d.]+)"', hoja)
    dc = float(dc.group(1)) if dc else 8.43

    # Sumas acumuladas (Arg_02: una forma del autor más allá de la columna 11.000 hacía que sumar columna a columna
    # tardara minutos)
    acumulado = [0.0]

    def suma_cols(c):
        while len(acumulado) <= c:
            i = len(acumulado) - 1
            acumulado.append(acumulado[-1] + next((w for a, b, w in cols if a <= i + 1 <= b), dc))
        return acumulado[c]
    medidas = []
    for m in ANCLA.finditer(dibujo):
        c = re.search(r'<xdr:from><xdr:col>(\d+)</xdr:col><xdr:colOff>(-?\d+)</xdr:colOff>.*?'
                      r'<xdr:to><xdr:col>(\d+)</xdr:col><xdr:colOff>(-?\d+)</xdr:colOff>', m.group(0), re.S)
        ext = re.search(r'<a:ext cx="(\d+)"', m.group(0))
        if c and ext and int(ext.group(1)) > 0:
            c1, o1, c2, o2 = map(int, c.groups())
            if suma_cols(c2) > suma_cols(c1):
                medidas.append((int(ext.group(1)) - o2 + o1) / (suma_cols(c2) - suma_cols(c1)))
    # Solo las medidas que tienen sentido (Arg_02: con formas del autor de ancho cero o descolocadas salía 0 y todo
    # caía en la última columna de Excel, que no existe: el libro salía dañado)
    medidas = [x for x in medidas if x > 0]
    unidad = sorted(medidas)[len(medidas) // 2] if medidas else 7 * 9525

    acum_filas = [0]

    def fila_y(r, off):
        while len(acum_filas) <= r:
            acum_filas.append(acum_filas[-1] + altos.get(len(acum_filas) - 1, defecto))
        return acum_filas[r] + off

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
        while c < 16383 and round(unidad * suma_cols(c + 1)) <= x:
            c += 1
        r = 0
        while r < 1048576 and fila_y(r + 1, 0) <= y:
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
        cambios_normal, detalle_normal = letra_normal_roboto(z)
    previo = io.BytesIO()
    reescribir_zip(base, previo, cambios_normal)
    with zipfile.ZipFile(previo) as z:
        cambios, detalle = reticula_y_pastilla(z, hoja, pub)
    cambios = {**cambios_normal, **cambios}
    detalle = detalle_normal + detalle
    intermedio = io.BytesIO()
    reescribir_zip(previo, intermedio, cambios)
    with zipfile.ZipFile(intermedio) as z:
        propuestas = []
        cambios_textos, detalle_textos = textos(z, hoja, estado, propuestas, pub)
    return nuevo_paso(trabajo, RETICULA_Y_TEXTOS, {**cambios, **cambios_textos}, detalle + detalle_textos,
                      propuestas=propuestas)


LETRA_NORMAL = ("Roboto Light", 11)


def letra_normal_roboto(z):
    """Estilo «Normal» del libro en Roboto Light 11 (petición del usuario, 2026-11-19, cuadros abiertos en Windows).
    Los anchos de columna se guardan en «caracteres» de esa letra y cada Excel los convierte a su manera: el de Mac,
    con el dígito en puntos enteros; el de Windows, en píxeles de pantalla (según el escalado). Con Arial 12 o Calibri
    11 las columnas salían un 4-12 % más estrechas en Windows mientras las formas (en mm) no cambiaban. El dígito de
    Roboto Light 11 mide 6 pt en Mac y 8/10/12/14/16 px (= 6 pt) en Windows al 100/125/150/175/200 %: el mismo ancho
    guardado da los mismos puntos. Las columnas que ya había se recalculan para que midan en Mac lo mismo que antes."""
    estilos_xml = z.read("xl/styles.xml").decode("utf-8")
    m = re.search(r'(<fonts\b[^>]*>)(.*?)(</fonts>)', estilos_xml, re.S)
    f0 = re.search(r'<font\b.*?</font>|<font/>', m.group(2), re.S)
    nombre, sz = LETRA_NORMAL
    if re.search(r'<name val="%s"/>' % re.escape(nombre), f0.group(0)) and re.search(r'<sz val="%g"/>' % sz, f0.group(0)) \
            and "<scheme" not in f0.group(0):
        return {}, []
    antes = re.search(r'<name val="([^"]*)"', f0.group(0))
    antes_sz = re.search(r'<sz val="([\d.]+)"', f0.group(0))
    mdw_antes = digito_maximo(estilos_xml)
    nueva_f0 = f'<font><sz val="{sz:g}"/><color theme="1"/><name val="{nombre}"/><family val="2"/></font>'
    cuerpo = m.group(2)[:f0.start()] + nueva_f0 + m.group(2)[f0.end():]
    nuevo_estilos = estilos_xml[:m.start()] + m.group(1) + cuerpo + m.group(3) + estilos_xml[m.end():]
    mdw, mdw_win = digito_maximo(nuevo_estilos), digito_windows(nuevo_estilos)
    cambios = {"xl/styles.xml": nuevo_estilos.encode("utf-8")}

    def convertir(w):
        pt = round(float(w) * mdw_antes)
        return f"{ancho_comun(pt, mdw, mdw_win):g}" if pt > 0 else w
    for _, ruta, _ in hojas_libro(z):
        x = z.read(ruta).decode("utf-8")
        nuevo = re.sub(r'(<col\b[^>]*\bwidth=")([\d.]+)(")', lambda k: k.group(1) + convertir(k.group(2)) + k.group(3), x)
        fmt = re.search(r'<sheetFormatPr\b[^>]*>', nuevo)
        if fmt:
            dcw = re.search(r'\bdefaultColWidth="([\d.]+)"', fmt.group(0))
            if dcw:
                etiqueta = fmt.group(0).replace(dcw.group(0), f'defaultColWidth="{convertir(dcw.group(1))}"')
            else:
                base_cw = re.search(r'\bbaseColWidth="(\d+)"', fmt.group(0))
                ancho_def = (int(base_cw.group(1)) if base_cw else 8) + 5 / mdw_antes
                etiqueta = fmt.group(0).replace("<sheetFormatPr", f'<sheetFormatPr defaultColWidth="{convertir(ancho_def)}"', 1)
            nuevo = nuevo.replace(fmt.group(0), etiqueta, 1)
        if nuevo != x:
            cambios[ruta] = nuevo.encode("utf-8")
    return cambios, [f"Letra «Normal» del libro: {antes.group(1) if antes else '—'} {antes_sz.group(1) if antes_sz else ''} → "
                     f"{nombre} {sz:g}, para que las columnas midan lo mismo en el Excel de Mac y en el de Windows "
                     "(los anchos que ya había, recalculados: en Mac no cambian)"]


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


UNIDADES_PT = 6
RE_UNIDADES = re.compile(r'\s*(datos|millones|miles|millardos|porcentajes?|%|tasas?|n[úu]mero|euros?|en\s|unidades|'
                         r'puntos|variaci[óo]n|data|millions|thousands|billions|percentages?|rates?|number|units|'
                         r'eur\b|€|points|change|year-end)', re.I)


def textos(z, hoja, estado, propuestas=None, pub=None):
    """«Cuadro N» y título con el marco de la plantilla (el título con el final «(a)» / «(cont.)» en Regular y,
    si ocupa más de una línea, la pastilla crece); unidades en Roboto Light 6 pt; FUENTES en Roboto Light 7 pt
    con las reglas de Gráficos, en el ancho de la plantilla. Todo en negro."""
    pl = plantilla()
    ancho_ret, alto_ret = tamano(pl["grupo"], escala_grupo=True)
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
        if x >= ancho_ret or y >= alto_ret:
            # A la derecha o por debajo de la retícula (DO26XX_03: una FUENTES vieja a 256 mm)
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

    # Varias FUENTES (copias del autor): se maqueta la de más texto; las demás, sin tocar y avisadas
    fuentes_k = [k for k, t in tipos.items() if t == "fuentes"]
    if len(fuentes_k) > 1:
        buena = max(fuentes_k, key=lambda k: len(html.unescape(texto_forma(partes[k])).strip()))
        for k in fuentes_k:
            if k != buena:
                tipos[k] = "copia_fuentes"
    # «Cuadro N» y unidades escritos en celdas encima del cuadro (Memoria 2.1: D1 «Cuadro 2.1», D3 «Datos a 31 de
    # diciembre»): pasan a cuadros de texto, como en el Informe Anual, y la celda se vacía
    cambios_hoja = {}
    if "cuadro" not in tipos.values() or "unidades" not in tipos.values():
        ruta_hoja = hoja_de(z, hoja)
        hoja_xml = z.read(ruta_hoja).decode("utf-8")
        _, compartidos = leer_compartidos(z)
        mdw = digito_maximo(z.read("xl/styles.xml").decode("utf-8"))
        ancho_col = anchos_columnas(hoja_xml)
        altos, defecto = filas
        pasadas = []
        todas_c = celdas_hoja(hoja_xml, compartidos)
        # Solo por encima del cuadro: antes de la primera fila con dos o más textos en columnas visibles
        por_fila = Counter(f for (c, f), x in todas_c.items() if x["texto"].strip() and ancho_col(c) > 0)
        inicio_tabla = min([f for f, n in por_fila.items() if n >= 2] or [10 ** 6])
        for (c, f), x in sorted(todas_c.items(), key=lambda kv: (kv[0][1], kv[0][0])):
            t = x["texto"].strip()
            if f >= inicio_tabla or por_fila[f] != 1:
                continue
            if not t or x["numero"] or ancho_col(c) == 0 or altos.get(f - 1, defecto) == 0 or "<f>" in (x["xml"] or "") or "<f " in (x["xml"] or ""):
                continue
            # Combinada sobre dos o más columnas con textos debajo, en su ancho: es la cabecera de grupo del cuadro, no
            # unas unidades (Economía Latinoamericana 01: B3:G3 «Tasas de variación interanual» sobre B4:G4)
            span = next((r for r in combinadas(hoja_xml) if r[0] == c and r[1] == f and r[2] > c), None)
            if span and sum(1 for k in range(c, span[2] + 1) if todas_c.get((k, span[3] + 1), {}).get("texto", "").strip()) >= 2:
                continue
            cx = sum(round(round(ancho_col(k) * mdw) * EMU_PT) for k in range(1, c))
            cy = sum(altos.get(r, defecto) for r in range(f - 1))
            if cx >= ancho_ret or cy >= alto_pastilla + 12 * EMU_MM:
                continue
            if RE_CUADRO_LINEA.match(t) and "cuadro" not in tipos.values():
                tipo, marco = "cuadro", pl["marco_cuadro"]
                ancho_f, alto_f = tamano(marco)
            elif cy >= alto_pastilla * 0.75 and RE_UNIDADES.match(t) and "unidades" not in tipos.values():
                tipo, marco = "unidades", pl["marco_fuentes"]
                ancho_f, alto_f = ancho_ret // 2, round(5 * EMU_MM)
            else:
                continue
            linea = next((l for l in lineas_de(marco) if texto_de(l).strip()), [("<a:rPr lang=\"es-ES\"/>", "")])
            nueva = con_parrafos(marco, [[(linea[0][0], t)]])
            r_, desp = celda_de(filas, cy)
            nueva, sig = renumerar(anclar_celda(nueva, 0, cx, r_, desp, ancho_f, alto_f), sig,
                                   "Cuadro" if tipo == "cuadro" else "Unidades")
            partes.insert(len(partes) - 1, nueva)
            tipos[partes.index(nueva)] = tipo
            hoja_xml = re.sub(rf'<c r="{ref(c, f)}"([^>]*?)(?:/>|>.*?</c>)',
                              lambda m: "<c r=\"" + ref(c, f) + "\"" + re.sub(r'\st="\w+"', "", m.group(1)) + "/>", hoja_xml, count=1, flags=re.S)
            pasadas.append(f"{ref(c, f)} «{t[:40]}»")
        if pasadas:
            cambios_hoja[ruta_hoja] = hoja_xml.encode("utf-8")
            detalle.append("Textos del autor en celdas encima del cuadro, pasados a cuadros de texto (como en el Informe "
                           "Anual) y vaciadas sus celdas: " + "; ".join(pasadas))

    # FUENTE y notas escritas en celdas bajo el cuadro (Memoria 3.2: A22 «FUENTE: …», A23 «(*)…», A24 «(a)…»): pasan
    # al cuadro de texto de FUENTES, como en los demás cuadros, y las celdas se vacían (petición del usuario, 2026-11-17)
    if "fuentes" not in tipos.values():
        ruta_hoja = hoja_de(z, hoja)
        hoja_xml = cambios_hoja[ruta_hoja].decode("utf-8") if ruta_hoja in cambios_hoja else z.read(ruta_hoja).decode("utf-8")
        _, compartidos = leer_compartidos(z)
        mdw = digito_maximo(z.read("xl/styles.xml").decode("utf-8"))
        ancho_col = anchos_columnas(hoja_xml)
        altos, defecto = filas
        todas_c = celdas_hoja(hoja_xml, compartidos)

        def x_de(c):
            return sum(round(round(ancho_col(k) * mdw) * EMU_PT) for k in range(1, c))
        visibles = {k: x for k, x in todas_c.items() if x["texto"].strip() and ancho_col(k[0]) > 0
                    and altos.get(k[1] - 1, defecto) != 0 and x_de(k[0]) < ancho_ret}
        por_fila = Counter(f for (c, f) in visibles)
        fin_tabla = max([f for f, n in por_fila.items() if n >= 2] or [0])
        rotulo = next(((c, f) for (c, f), x in sorted(visibles.items(), key=lambda kv: (kv[0][1], kv[0][0]))
                       if f > fin_tabla and por_fila[f] == 1 and not x["numero"] and "<f" not in x["xml"]
                       and ROTULO.match(x["texto"])), None)
        if rotulo:
            tomadas, huecos = [], 0
            for f in range(rotulo[1], rotulo[1] + 16):
                if por_fila[f] == 0:
                    huecos += 1
                    if huecos >= 2:
                        break
                    continue
                if por_fila[f] >= 2:
                    break
                huecos = 0
                k = next(k for k in visibles if k[1] == f)
                if visibles[k]["numero"] or "<f" in visibles[k]["xml"]:
                    break
                tomadas.append(k)
            marco = pl["marco_fuentes"]
            linea = next((l for l in lineas_de(marco) if texto_de(l).strip()), [("<a:rPr lang=\"es-ES\"/>", "")])
            parrafos = [[(linea[0][0], l.strip())] for k in tomadas for l in visibles[k]["texto"].split("\n") if l.strip()]
            nueva = con_parrafos(marco, parrafos)
            cy = sum(altos.get(r, defecto) for r in range(rotulo[1] - 1))
            r_, desp = celda_de(filas, cy)
            nueva, sig = renumerar(anclar_celda(nueva, 0, 0, r_, desp, tamano(marco)[0], tamano(marco)[1]), sig, "FUENTES")
            partes.insert(len(partes) - 1, nueva)
            tipos[partes.index(nueva)] = "fuentes"
            for c, f in tomadas:
                hoja_xml = re.sub(rf'<c r="{ref(c, f)}"([^>]*?)(?:/>|>.*?</c>)',
                                  lambda m: "<c r=\"" + ref(c, f) + "\"" + re.sub(r'\st="\w+"', "", m.group(1)) + "/>",
                                  hoja_xml, count=1, flags=re.S)
            cambios_hoja[ruta_hoja] = hoja_xml.encode("utf-8")
            detalle.append("FUENTE y notas del autor en celdas bajo el cuadro, pasadas al cuadro de texto de FUENTES (como "
                           "en los demás cuadros) y vaciadas sus celdas: " + ", ".join(ref(c, f) for c, f in tomadas)
                           + marca(forma="FUENTES"))

    medir_medium = medidor("Roboto-Medium.ttf")
    medir_light = medidor("Roboto-Light.ttf")
    titulo_k = None
    for k, tipo in tipos.items():
        a = partes[k]
        corto = html.unescape(texto_forma(a)).replace("\n", " / ")[:70]
        if tipo == "fuera":
            detalle.append(f"Sin tocar, fuera de la retícula: «{corto}»")
            continue
        if tipo == "copia_fuentes":
            detalle.append(f"Aviso: hay otro cuadro de FUENTES del autor, con menos texto: sin tocar (¿una copia vieja?): «{corto}»"
                           + marca(forma=nombre_forma(a)))
            continue
        if tipo == "cuadro":
            a, _ = con_marco(a, pl["marco_cuadro"], filas)
            detalle.append(f"«{corto}»: Roboto Regular 7 pt, marco y posición de la plantilla")
            # Siempre «Cuadro» (o «Table»), en todas las publicaciones (decisión del usuario, 2026-11-17, Memoria 3.2)
            todo = html.unescape(texto_forma(a))
            bien = re.sub(r'(?i)\b(cuadro|table)\b', lambda m: m.group(1).capitalize(), todo, count=1)
            if bien != todo:
                cambiado = recasar_xml(a, todo, bien)
                if cambiado:
                    a = cambiado
                    detalle.append(f"«{corto}» → «{bien.split(chr(10))[0].strip()}» (siempre «{bien.strip().split()[0]}»)")
        elif tipo == "titulo":
            a, finales = con_marco(a, pl["marco_titulo"], filas, final_regular=FINAL_TITULO)
            titulo_k = k
            detalle.append(f"Título «{corto}»: Roboto Medium 8,5 pt, marco y posición de la plantilla")
            for f in finales:
                detalle.append(f"  «{f}» al final del párrafo, en Roboto Regular")
            titulo_mayus = mayusculas(corto)
        elif tipo == "fuentes":
            a, notas = maquetar_fuentes(a, estado.get("idioma", "es"))
            # En el ancho de la plantilla, desde la columna A; el alto, el que pida el texto
            x, y, w, h = caja(a)
            ancho = tamano(pl["marco_fuentes"])[0]
            alto = h
            if medir_light:
                l, t, r, b = margenes(a)
                # Sin la sangría de las notas (8,5 pt), que estrecha sus líneas
                lineas = lineas_parrafos(textos_lineas(a), (ancho - l - r) / EMU_PT - 8.5, 7, medir_light)
                blancos = len(re.findall(r'<a:p>(?:<a:pPr\b[^>]*/>)?<a:endParaRPr\b[^>]*?(?:/>|>.*?</a:endParaRPr>)</a:p>', a, re.S))
                # (+1 línea de reserva: en Windows el texto sale algo más ancho y una nota larga puede partirse en una
                # línea más que en el Mac; el texto va arriba, así que en el Mac no se nota)
                alto = t + b + round((lineas + blancos + 1) * interlineado(a, 7, "Roboto-Light.ttf", windows=True) * EMU_PT) + 2 * EMU_PT
            a = anclar_en(a, 0, y, ancho, alto, caja)
            detalle.append(f"Fuentes «{corto[:50]}»: Roboto Light 7 pt" + "".join(f"; {n}" for n in notas if not n.startswith("Aviso")))
            detalle.append(f"  en el ancho de la plantilla ({ancho / EMU_MM:.1f} mm) desde la columna A, donde la dejó el autor"
                           .replace(".", ","))
            detalle += [n + marca(forma=nombre_forma(a)) for n in notas if n.startswith("Aviso")]
        elif tipo == "unidades":
            a = fijar_letra(a, 600, ROBOTO_LIGHT)
            detalle.append(f"Unidades «{corto}»: Roboto Light 6 pt, donde las dejó el autor")
        else:
            detalle.append(f"Sin tocar (no sé qué texto es): «{corto}»")
            continue
        if tipo != "cuadro":
            a, hechos_c = corregir_forma(a, estado.get("idioma", "es"))
            if hechos_c:
                detalle.append("Aviso (corrección ortotipográfica), revísalas: " + "; ".join(hechos_c[:6]) + marca(forma=nombre_forma(a)))
        # «Cuadro N» y título en el color de la publicación si lo pide (Documentos Ocasionales: naranja F06800,
        # como sus publicados; Informe Anual y Memoria, en negro)
        en_color = tipo in ("cuadro", "titulo") and (pub or {}).get("rotulo_y_titulo_en_color")
        a, _ = textos_en_negro(a, pub["color"].upper() if en_color else None)
        if en_color:
            rotulo = re.sub(r'(\s*/\s*)+$', '', corto)[:40]
            detalle.append(f"«{rotulo}», en el color de la publicación (#{pub['color'].upper()})")
        partes[k] = a
        if tipo == "titulo" and titulo_mayus:
            # Propuesta con botón «Aplicar» en la app (petición del usuario, 2026-11-17, Memoria 3.2)
            todo = html.unescape(texto_forma(a))
            frase = frase_desde_mayusculas(todo, estado.get("idioma", "es"))
            if propuestas is not None and frase != todo and recasar_xml(a, todo, frase):
                propuestas.append({"tipo": "forma", "hoja": hoja, "forma": nombre_forma(a), "de": todo, "a": frase,
                                   "que": "título en minúsculas"})
                detalle.append("Aviso (propuesta, sin aplicar): el título va en mayúsculas. En minúsculas: "
                               + f"«{recortar(frase.replace(chr(10), ' ').strip(), 140)}»"
                               + f" ⟦aplicar:{len(propuestas) - 1}⟧" + marca(forma=nombre_forma(a)))
            else:
                detalle.append("Aviso: el título va en mayúsculas: pásalo a minúsculas a mano" + marca(forma=nombre_forma(a)))
    if "fuentes" not in tipos.values():
        # Sin FUENTE (1.2): el marco de la plantilla, con su texto de muestra, para escribirla (el paso 2 lo coloca
        # 5 mm bajo el cuadro)
        marco = pl["marco_fuentes"]
        lineas = [l for l in lineas_de(marco) if texto_de(l).strip()][:1]
        marco = con_parrafos(marco, lineas) if lineas else marco
        fila, desp = celda_de(filas, posicion(marco)[1])
        cx, cy = tamano(marco)
        sig_f = max([int(i) for i in re.findall(r'<xdr:cNvPr\s+id="(\d+)"', "".join(partes))] or [0]) + 1
        marco, _ = renumerar(anclar_celda(marco, 0, 0, fila, desp, cx, cy), sig_f, "FUENTES")
        partes.insert(len(partes) - 1, marco)
        detalle.append("Aviso: el autor no puso FUENTE: añadido el marco de la plantilla («FUENTE: Xxxxxxxxxx.»); "
                       "escribe la fuente (y las notas, si las hay)" + marca(forma="FUENTES"))
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
    return {ruta: "".join(partes).encode("utf-8"), **cambios_hoja}, detalle

# ---------------------------------------------------------------- paso 2: celdas

CELDAS = "Celdas"
RE_TOTAL = re.compile(r'\s*total\b', re.I)
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
DATO_JUSTO_MINIMO = 60                     # columnas de datos «a lo justo» (Documentos Ocasionales): no menos de esto (pt)
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
        self.nuevos_formatos = []   # [(id, código)] de numFmt nuevos (cifras sin el relleno «_m_m_m» del autor)

    def xf(self, i):
        # También los formatos nuevos (Indicadores 01: las líneas del bloque de arriba sobre un formato recién hecho
        # tomaban el formato 0 del libro, con la letra Normal de 11 pt y sin alineación)
        todos = self.xfs + self.nuevos_xfs
        return todos[i] if i < len(todos) else self.xfs[0]

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

    def borde_de(self, i):
        """Los lados del borde del formato `i` como {"top": ("thin", "D9D9D9"), …} (colores RGB; los del tema, sin
        color: se dejan como estaban si no se tocan)."""
        b = re.search(r'\bborderId="(\d+)"', self.xf(i))
        n = int(b.group(1)) if b else 0
        borde = (self.bordes + self.nuevos_bordes)[n] if n < len(self.bordes) + len(self.nuevos_bordes) else ""
        lados = {}
        for lado in ("left", "right", "top", "bottom"):
            m = re.search(rf'<{lado} style="(\w+)">(.*?)</{lado}>', borde, re.S)
            if m:
                rgb = re.search(r'rgb="FF(\w{6})"', m.group(2))
                lados[lado] = (m.group(1), rgb.group(1) if rgb else BLANCO_MATIZ_2)
        return lados

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

    def fuente_celda(self, fuente, negrita=False, cuerpo=None):
        """Roboto Light 7,5 pt (o Roboto Medium si el autor la puso en negrita) con el formato local de la fuente
        del autor (cursiva, subrayado, tachado, índices, color), sin negrita de Excel: el peso lo da la familia."""
        partes = []
        for etiqueta in ("i", "strike", "u", "vertAlign"):
            m = re.search(rf'<{etiqueta}\b[^>]*/>', fuente)
            if m and 'val="0"' not in m.group(0) and 'val="false"' not in m.group(0):
                partes.append(m.group(0))
        partes.append(f'<sz val="{cuerpo or CUERPO_CELDA:g}"/>')
        # Siempre en negro: el color del autor (cifras en gris, Memoria 3.2) no se queda; las cabeceras las colorea
        # el paso 3 (decisión del usuario, 2026-11-17)
        partes.append('<color rgb="FF000000"/>')
        partes.append(f'<name val="{LETRA_CELDA_NEGRITA if negrita or es_negrita(fuente) else LETRA_CELDA}"/><family val="2"/>')
        nueva = "<font>" + "".join(partes) + "</font>"
        todas = self.fuentes + self.nuevas_fuentes
        if nueva in todas:
            return todas.index(nueva)
        self.nuevas_fuentes.append(nueva)
        return len(todas)

    def sin_relleno(self, i):
        """numFmtId del formato de número de `i` sin el relleno a los lados («0.00_m_m_m» → «0.00»): ese hueco
        invisible descentra las cifras (TERMINADO 3.1 publicado: «#,##0.00» sin relleno). None si no lo lleva."""
        codigo = formato_numero(self, i)
        if "*" in codigo:
            return None   # contabilidad («_-* #,##0…»): el relleno es parte del formato
        nuevo = ";".join(re.sub(r'(?:_.|\\ )+$', "", re.sub(r'^(?:_.)+', "", sec)) for sec in codigo.split(";"))
        if nuevo == codigo:
            return None
        internos = {v: k for k, v in FORMATOS_INTERNOS.items()}
        if nuevo in internos:
            return internos[nuevo]
        propios = dict((html.unescape(c), int(n)) for n, c in re.findall(r'<numFmt\b[^>]*\bnumFmtId="(\d+)"[^>]*\bformatCode="([^"]*)"', self.xml))
        propios.update({c: n for n, c in self.nuevos_formatos})
        if nuevo in propios:
            return propios[nuevo]
        ids = [int(n) for n in re.findall(r'<numFmt\b[^>]*\bnumFmtId="(\d+)"', self.xml)] + [n for n, _ in self.nuevos_formatos]
        n = max(ids + [163]) + 1
        self.nuevos_formatos.append((n, nuevo))
        return n

    def nuevo(self, i, alineacion, negrita=False, cuerpo=None):
        """Índice de un formato como el `i` del autor con la fuente de celda y esta alineación (y el formato de
        número sin relleno a los lados)."""
        clave = (i, tuple(sorted(alineacion.items())), negrita, cuerpo)
        if clave in self.cache:
            return self.cache[clave]
        xf = self.xf(i)
        fid = self.fuente_celda(self.fuente_de(i), negrita, cuerpo)
        apertura = re.match(r'<xf\b[^>]*?(/?)>', xf)
        atributos = apertura.group(0)[3:-(2 if apertura.group(1) else 1)]
        nf = self.sin_relleno(i)
        cambios = [("fontId", fid), ("applyFont", 1), ("applyAlignment", 1)]
        if nf is not None:
            cambios += [("numFmtId", nf), ("applyNumberFormat", 1)]
        for nombre, valor in cambios:
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
        if self.nuevos_formatos:
            nuevos = "".join(f'<numFmt numFmtId="{n}" formatCode="{html.escape(c)}"/>' for n, c in self.nuevos_formatos)
            if "<numFmts" in xml:
                total = len(re.findall(r'<numFmt\b', xml)) + len(self.nuevos_formatos)
                xml = re.sub(r'(<numFmts\b[^>]*?)\scount="\d+"', rf'\1 count="{total}"', xml, count=1)
                xml = xml.replace("</numFmts>", nuevos + "</numFmts>", 1)
            else:
                xml = re.sub(r'(<styleSheet\b[^>]*>)', rf'\1<numFmts count="{len(self.nuevos_formatos)}">{nuevos}</numFmts>', xml, count=1)
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
        v = re.search(r'<v\b[^>]*>(.*?)</v>', c, re.S)
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


def cifras_ocultas(hoja_xml, estilos_xml):
    """Celdas {(col, fila)} de un formato condicional que pone la letra del color del fondo (Arg_02, mapa de calor: las
    cifras no se ven, solo el color): no cuentan para los anchos."""
    dxfs = re.findall(r'<dxf>.*?</dxf>|<dxf/>', estilos_xml, re.S)

    def esconde(i):
        if i >= len(dxfs):
            return False
        letra = re.search(r'<font>.*?<color rgb="(\w+)"', dxfs[i], re.S)
        fondo = re.search(r'<bgColor rgb="(\w+)"', dxfs[i])
        return bool(letra and fondo and letra.group(1)[-6:].upper() == fondo.group(1)[-6:].upper())
    ocultas = set()
    for m in re.finditer(r'<conditionalFormatting\b[^>]*\bsqref="([^"]+)"[^>]*>(.*?)</conditionalFormatting>', hoja_xml, re.S):
        if not any(esconde(int(i)) for i in re.findall(r'\bdxfId="(\d+)"', m.group(2))):
            continue
        for rango in m.group(1).split():
            a, _, b = rango.partition(":")
            ma, mb = RE_REF.match(a), RE_REF.match(b or a)
            for c in range(col_num(ma.group(1)), col_num(mb.group(1)) + 1):
                for f in range(int(ma.group(2)), int(mb.group(2)) + 1):
                    ocultas.add((c, f))
    return ocultas


def sin_filas_ocultas(todas, hoja_xml):
    """Las celdas sin las de las filas que el autor ocultó (LATAM Arg_03: filas 4-7 con «#REF!» y 9-16, un bloque
    entero): no se ven en el publicado, así que no cuentan para la cabecera, los bloques, las sangrías ni los anchos."""
    ocultas = {int(r) for r in re.findall(r'<row\b[^>]*?\br="(\d+)"[^>]*?\bhidden="1"', hoja_xml)}
    ocultas |= {int(r) for r in re.findall(r'<row\b[^>]*?\bhidden="1"[^>]*?\br="(\d+)"', hoja_xml)}
    return {k: v for k, v in todas.items() if k[1] not in ocultas} if ocultas else todas


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
    96 ppp, 1 px = 0,75 pt), si lo hay; si no, el del Mac. Entre los que valen, el que también da `pt` con la
    pantalla de Windows escalada (125, 150, 175 y 200 %: el dígito en píxeles crece en proporción)."""
    desde = max(1, int((pt - 0.5) / mdw_mac * 1000))
    mejor, aciertos_mejor = None, -1
    for i in range(desde, int((pt + 0.5) / mdw_mac * 1000) + 2):
        w = i / 1000
        if round(w * mdw_mac) != pt:
            continue
        win = int(((256 * w + int(128 / mdw_win)) / 256) * mdw_win) * 0.75
        if abs(win - pt) >= 0.01:
            continue
        aciertos = 0
        for escala in (1.25, 1.5, 1.75, 2):
            md = round(mdw_win * escala)
            px = int(((256 * w + int(128 / md)) / 256) * md)
            aciertos += abs(px * 0.75 / escala - pt) < 0.01
        if aciertos > aciertos_mejor:
            mejor, aciertos_mejor = w, aciertos
        if aciertos == 4:
            break
    return mejor if mejor is not None else round(pt / mdw_mac, 8)


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


def sin_relleno_codigo(codigo):
    """El código de formato sin el relleno de los lados (lo que quita el paso 2): para comparar formatos."""
    if "*" in codigo:
        return codigo
    return ";".join(re.sub(r'(?:_.|\\ )+$', "", re.sub(r'^(?:_.)+', "", sec)) for sec in codigo.split(";"))


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
                propia = re.sub(r'\shidden="[^"]*"', "", propia)
                propia = propia[:-2].rstrip() + f' width="{w}" customWidth="1"' + (' hidden="1"' if w == 0 else "") + "/>"
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
    # La columna de partida, la primera VISIBLE con texto (DO26XX_01: un código suelto en la columna A, oculta, en A74,
    # se tomaba por el cuadro); si todas están ocultas, la primera
    visibles = [k[0] for g in con_texto for k in g if celdas.get(k, {}).get("texto", "").strip() and ancho_col(k[0]) > 0]
    minimo = min(visibles or [k[0] for g in con_texto for k in g if celdas.get(k, {}).get("texto", "").strip()])
    candidatos = [g for g in con_texto if any(k[0] == minimo for k in g)]
    # Varias tablas de verdad (texto en 3 filas y 3 columnas al menos) en esa columna: la de arriba, la que va bajo
    # la pastilla (Economía Latinoamericana 01: la trimestral publicada en A3 y debajo, en A43, la mensual del autor)
    tablas = [g for g in candidatos
              if len({k[1] for k in g if celdas.get(k, {}).get("texto", "").strip()}) >= 3
              and len({k[0] for k in g if celdas.get(k, {}).get("texto", "").strip()}) >= 3]
    if len(tablas) > 1:
        grupo = min(tablas, key=lambda g: min(k[1] for k in g if celdas.get(k, {}).get("texto", "").strip()))
    else:
        grupo = max(candidatos, key=lambda g: sum(1 for k in g if celdas.get(k, {}).get("texto", "").strip()))
    # Sin las filas y columnas de los bordes que no tienen texto (bordes o rellenos sueltos del autor)
    texto = {k for k in grupo if celdas.get(k, {}).get("texto", "").strip()}
    c1, f1, c2, f2 = min(k[0] for k in texto), min(k[1] for k in texto), max(k[0] for k in texto), max(k[1] for k in texto)
    # Columna del borde derecho con un solo texto suelto, sin cifras (Memoria 4.1: E16 «CAMBIADOS LOS NOMBRES», nota
    # del autor pegada al cuadro): no es del cuadro (petición del usuario, 2026-11-18); el paso 2 avisa de ella
    while c2 > c1 and f2 - f1 >= 3:
        en_col = [k for k in texto if k[0] == c2]
        if len(en_col) > 1 or any(celdas[k].get("numero") for k in en_col):
            break
        texto -= set(en_col)
        c2 = max(k[0] for k in texto)
    return c1, f1, c2, f2


def indice_rico(d, compartidos):
    """Índice de la cadena compartida de la celda si su texto lleva formato (trozos <r>: superíndices, cursivas…)."""
    if d.get("tipo") != "s" or not d.get("xml"):
        return None
    m = re.search(r'<v>(\d+)</v>', d["xml"])
    return int(m.group(1)) if m and int(m.group(1)) < len(compartidos) and "<r>" in compartidos[int(m.group(1))] else None


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


CABECERA_BAJO_UNIDADES = 4 * MM     # de las unidades (su cuadro) a la cabecera del cuadro (TERMINADO 1.4: 3,95 mm)
UNIDADES_BAJO_PASTILLA = 0.3 * MM   # el cuadro de las unidades, justo bajo la pastilla (TERMINADO 1.4)
ALTO_UNIDADES = 5 * MM              # cuadro de unidades de una línea (TERMINADO 1.4)
LINEA_UNIDADES = 6 * 1.171875       # cada línea de más de las unidades (Roboto 6 pt, interlineado sencillo)
CABECERA_BAJO_PASTILLA = 4 * MM     # sin unidades, de la pastilla a la cabecera (TERMINADO 1.2: 3,8 mm; usuario: 4)
FUENTES_BAJO_CUADRO = 5 * MM        # del final del cuadro al cuadro de FUENTES (como en los gráficos)


def asegurar_filas(hoja_xml, filas):
    """Crea (vacías) las filas que no estén en sheetData, en su orden."""
    for f in filas:
        if re.search(rf'<row\b[^>]*\br="{f}"', hoja_xml):
            continue
        siguiente = next((m for m in re.finditer(r'<row\b[^>]*\br="(\d+)"', hoja_xml) if int(m.group(1)) > f), None)
        nueva = f'<row r="{f}"/>'
        if siguiente:
            hoja_xml = hoja_xml[:siguiente.start()] + nueva + hoja_xml[siguiente.start():]
        elif "<sheetData/>" in hoja_xml:
            hoja_xml = hoja_xml.replace("<sheetData/>", f"<sheetData>{nueva}</sheetData>", 1)
        else:
            hoja_xml = hoja_xml.replace("</sheetData>", nueva + "</sheetData>", 1)
    return hoja_xml


def anclar_celda(ancla, c, co, r, ro, cx, cy):
    """La forma anclada (una celda) en la celda (c, r) con esos desplazamientos y tamaño fijo."""
    cuerpo = re.search(r'(?:</xdr:to>|<xdr:ext\b[^>]*/>)(.*)</xdr:(?:twoCellAnchor|oneCellAnchor|absoluteAnchor)>',
                       ancla, re.S).group(1)
    return (f'<xdr:oneCellAnchor><xdr:from><xdr:col>{c}</xdr:col><xdr:colOff>{co}</xdr:colOff><xdr:row>{r}</xdr:row>'
            f'<xdr:rowOff>{ro}</xdr:rowOff></xdr:from><xdr:ext cx="{cx}" cy="{cy}"/>{cuerpo}</xdr:oneCellAnchor>')


def colocar_y(ancla, y):
    """Marca la forma con la altura (EMU desde A1) a la que hay que anclarla al recolocar."""
    return ancla.replace("<xdr:oneCellAnchor>", f'<xdr:oneCellAnchor y_nueva="{y}">', 1).replace(
        "<xdr:twoCellAnchor>", f'<xdr:twoCellAnchor y_nueva="{y}">', 1).replace(
        '<xdr:twoCellAnchor editAs="oneCell">', f'<xdr:twoCellAnchor editAs="oneCell" y_nueva="{y}">', 1)


def colocar_cuadro(dibujo, caja, filas_viejas, altos_nuevos, f1, f2):
    """Alto de la fila de encima del cuadro para que la cabecera empiece donde toca (4 mm bajo las unidades o 5 mm
    bajo la pastilla) y FUENTES 5 mm bajo el cuadro. Devuelve (dibujo, notas, alto de esa fila en pt o None)."""
    altos_emu, defecto = filas_viejas

    def alto_viejo(f):          # f desde 1, en EMU
        return altos_emu.get(f - 1, defecto)
    partes = list(partes_dibujo(dibujo))
    notas = []
    pastilla = next((a for a in partes if ANCLA.fullmatch(a) and nombre_forma(a) == "Pastilla"), None)
    fondo_pastilla = caja(pastilla)[1] + caja(pastilla)[3] if pastilla else 0
    inicio_viejo = sum(alto_viejo(f) for f in range(1, f1))
    # Unidades: cuadros de texto en 6 pt (así los deja el paso 1) entre la pastilla y el cuadro
    unidades = []
    for k, a in enumerate(partes):
        if not ANCLA.fullmatch(a) or sin_texto(a) or "<xdr:grpSp>" in a[:1500]:
            continue
        tamanos = set(re.findall(r'<a:rPr\b[^>]*\bsz="(\d+)"', a))
        y = caja(a)[1]
        if tamanos == {"600"} and fondo_pastilla - 3 * EMU_MM <= y < inicio_viejo + 2 * EMU_MM:
            unidades.append(k)
    if unidades:
        # Las unidades, en un sitio fijo bajo la pastilla (el autor las deja donde cae); la cabecera, 4 mm bajo un
        # cuadro de unidades de 5 mm (y 2,5 mm más por cada línea de más)
        medir_l = medidor("Roboto-Light.ttf")
        lineas = 1
        for k in unidades:
            l, _, r, _ = margenes(partes[k])
            if medir_l:
                lineas = max(lineas, lineas_parrafos(textos_lineas(partes[k]), (caja(partes[k])[2] - l - r) / EMU_PT, 6, medir_l))
        arriba_unidades = fondo_pastilla + round(UNIDADES_BAJO_PASTILLA * EMU_PT)
        for k in unidades:
            x, y, w, h = caja(partes[k])
            partes[k] = colocar_y(partes[k], arriba_unidades)
        objetivo = arriba_unidades + round((ALTO_UNIDADES + CABECERA_BAJO_UNIDADES + (lineas - 1) * LINEA_UNIDADES) * EMU_PT)
        motivo = "4 mm bajo las unidades" + (f" ({lineas} líneas)" if lineas > 1 else "")
    else:
        objetivo = fondo_pastilla + round(CABECERA_BAJO_PASTILLA * EMU_PT)
        motivo = "4 mm bajo la pastilla"
    # Altos nuevos de las filas de encima del cuadro: las de arriba se quedan como están y la de justo encima toma el
    # hueco; si las de arriba ya ocupan más, se encogen todas por igual (dejando 1 pt a la de encima)
    encima = sum(alto_viejo(f) for f in range(1, f1 - 1))
    altos_encima = {f: alto_viejo(f) for f in range(1, f1 - 1)}
    if objetivo - encima < EMU_PT and encima > 0:
        escala = (objetivo - EMU_PT) / encima
        altos_encima = {f: v * escala for f, v in altos_encima.items()}
        notas.append(f"Filas 1-{f1 - 2} encogidas para que el cuadro quede {motivo}")
    altos_encima = {f: round(v / EMU_PT * 4) / 4 for f, v in altos_encima.items()}
    alto_hueco = max(1.0, round((objetivo / EMU_PT - sum(altos_encima.values())) * 4) / 4)
    notas.append(f"Cuadro {motivo}: la fila {f1 - 1} pasa a {alto_hueco:g} pt".replace(".", ","))

    def alto_nuevo(f):
        if f in altos_nuevos:
            return round(altos_nuevos[f] * EMU_PT)
        if f == f1 - 1:
            return round(alto_hueco * EMU_PT)
        if f in altos_encima:
            return round(altos_encima[f] * EMU_PT)
        return alto_viejo(f)

    def fila_de(y):
        """(fila desde 0, desplazamiento) de la altura y (EMU) con los altos nuevos."""
        f = 1
        while y >= alto_nuevo(f) and f < 100000:
            y -= alto_nuevo(f)
            f += 1
        return f - 1, y
    # Todo lo que queda por encima del cuadro, anclado otra vez donde está (con los altos nuevos) y tamaño fijo:
    # así no se mueve al cambiar las filas
    for k, a in enumerate(partes):
        if not ANCLA.fullmatch(a):
            continue
        marca = re.match(r'<xdr:\w+Anchor\b[^>]*\by_nueva="(\d+)"', a)
        a = re.sub(r'\sy_nueva="\d+"', "", a, count=1)
        x, y, w, h = caja(a)
        if marca:
            y = int(marca.group(1))
        if (y < inicio_viejo or marca) and nombre_forma(a) not in ("Retícula", "Pastilla"):
            c, co, _, _ = caja.a_celda(x, y)
            r, ro = fila_de(y)
            partes[k] = anclar_celda(a, c, co, r, ro, w, h)
    # FUENTES, 5 mm bajo el final del cuadro (con los altos nuevos)
    fin_cuadro = sum(alto_nuevo(f) for f in range(1, f2 + 1))
    # Solo la FUENTES de más texto dentro de la retícula (DO26XX_03: una copia vieja a 256 mm se quedaba encima)
    alto_ret = tamano(plantilla()["grupo"], escala_grupo=True)[1]
    candidatas = [k for k, a in enumerate(partes) if ANCLA.fullmatch(a) and not sin_texto(a)
                  and ROTULO.match(html.unescape(texto_forma(a)).strip().split("\n")[0])
                  and inicio_viejo <= caja(a)[1] < alto_ret]
    buena = max(candidatas, key=lambda k: len(html.unescape(texto_forma(partes[k])).strip()), default=None)
    for k, a in enumerate(partes):
        if not ANCLA.fullmatch(a) or sin_texto(a):
            continue
        x, y, w, h = caja(a)
        if k == buena:
            f, resto = f2 + 1, round(FUENTES_BAJO_CUADRO * EMU_PT)
            while resto >= alto_nuevo(f) and f < f2 + 500:
                resto -= alto_nuevo(f)
                f += 1
            partes[k] = anclar_celda(a, 0, 0, f - 1, resto, w, h)
            notas.append("FUENTES, 5 mm bajo el final del cuadro")
    return "".join(partes), notas, (alto_hueco, altos_encima)


COMPENSAR_CABECERA = False
NEXOS_FUERTES = {"en", "entre", "y", "e", "o", "u", "para", "por", "con", "sin", "sobre", "según", "hasta", "desde",
                 "frente", "and", "or", "in", "for", "with", "by", "on", "from", "to", "vs", "vs."}
NEXOS_DEBILES = {"de", "del", "a", "al", "of", "the"}


def salto_cabecera(texto, ancho, medir):
    """El texto de una cabecera de 2 líneas con el salto puesto como en los publicados: antes de un nexo («en las
    importaciones», «entre 2017», «y eficacia») o tras dos puntos («Impacto: / inflación»); si no, antes de «de»
    («Disrupción / de oferta»); entre los posibles, el que deja las líneas más parejas. None si no cabe en 2."""
    palabras = texto.split(" ")
    candidatos = []
    for i in range(1, len(palabras)):
        l1, l2 = " ".join(palabras[:i]), " ".join(palabras[i:])
        w1, w2 = medir(l1, CUERPO_CELDA), medir(l2, CUERPO_CELDA)
        if w1 > ancho or w2 > ancho:
            continue
        sig = palabras[i].lower().strip("(«\"")
        if sig in NEXOS_FUERTES or palabras[i - 1].endswith(":"):
            prioridad = 0
        elif sig in NEXOS_DEBILES:
            prioridad = 1
        else:
            prioridad = 2
        candidatos.append((prioridad, abs(w1 - w2), l1 + "\n" + l2))
    return min(candidatos)[2] if candidatos else None


ALTO_FILA_PUNTOS = 21       # filas con puntos dibujados (publicado de Economía Latinoamericana 04)
MARCADOR_MAX = 4 * EMU_MM   # formas pequeñas (puntos de un gráfico en celdas): se mueven sin cambiar de tamaño
RE_EXTREMO = re.compile(r'<xdr:(from|to)>\s*<xdr:col>(\d+)</xdr:col>\s*<xdr:colOff>(-?\d+)</xdr:colOff>\s*'
                        r'<xdr:row>(\d+)</xdr:row>\s*<xdr:rowOff>(-?\d+)</xdr:rowOff>\s*</xdr:(?:from|to)>')


def reubicar_formas(dibujo, c1, c2, f1, f2, ancho_viejo, ancho_nuevo, alto_viejo, alto_nuevo):
    """Formas ancladas en celdas del cuadro (puntos y flechas dibujados sobre las celdas, Economía Latinoamericana 04):
    cada extremo guarda su sitio relativo dentro de su celda al cambiar anchos y altos (anclas en EMU desde el borde
    de la celda). Los marcadores pequeños se mueven por su centro sin cambiar de tamaño, y los extremos de flecha que
    tocaban un marcador siguen tocándolo. Devuelve (dibujo, nombres de las formas movidas)."""
    def nuevo(eje, i, off):
        v, n = (ancho_viejo(i), ancho_nuevo(i)) if eje == "col" else (alto_viejo(i), alto_nuevo(i))
        return off if v <= 0 or abs(v - n) < 1 else round(off * n / v)

    anclas = [m for m in ANCLA.finditer(dibujo) if m.group(1) == "twoCellAnchor"]
    info = []
    for m in anclas:
        ext = {e[0]: (int(e[1]), int(e[2]), int(e[3]), int(e[4])) for e in RE_EXTREMO.findall(m.group(0))}
        # Solo formas sin texto: los cuadros de texto (rótulo, unidades, FUENTES, cabeceras de símbolos) los coloca su regla
        if set(ext) != {"from", "to"} or es_reticula(m.group(0)) or es_pastilla(m.group(0)) \
                or html.unescape(texto_forma(m.group(0))).strip() \
                or ("<xdr:cxnSp" not in m.group(0) and re.search(r'<a:ext cx="0"|<a:ext cx="\d+" cy="0"', m.group(0))):
            info.append(None)
            continue
        (ca, oa, ra, pa), (cb, ob, rb, pb) = ext["from"], ext["to"]
        if not (c1 <= ca + 1 <= c2 and c1 <= cb + 1 <= c2 and f1 <= ra + 1 <= f2 and f1 <= rb + 1 <= f2):
            info.append(None)
            continue
        info.append(ext)
    # Marcadores: en una sola celda y pequeños
    marcadores = []
    for m, ext in zip(anclas, info):
        if ext and ext["from"][0] == ext["to"][0] and ext["from"][2] == ext["to"][2] \
                and 0 <= ext["to"][1] - ext["from"][1] <= MARCADOR_MAX and 0 <= ext["to"][3] - ext["from"][3] <= MARCADOR_MAX \
                and "<xdr:cxnSp" not in m.group(0):
            (c, oa, r, pa), (_, ob, _, pb) = ext["from"], ext["to"]
            cx_, cy_ = (nuevo("col", c, (oa + ob) / 2), nuevo("row", r, (pa + pb) / 2))
            w, h = ob - oa, pb - pa
            marcadores.append({"c": c, "r": r, "viejo": (oa, ob, pa, pb),
                               "nuevo": (round(cx_ - w / 2), round(cx_ - w / 2) + w, round(cy_ - h / 2), round(cy_ - h / 2) + h)})
    TOCA = 12700   # 1 pt

    def extremo_x(c, r, off):
        for mk in marcadores:
            if mk["c"] == c and mk["r"] == r:
                for k in (0, 1):
                    if abs(off - mk["viejo"][k]) <= TOCA:
                        return mk["nuevo"][k]
        return nuevo("col", c, off)
    piezas, ultimo, movidas = [], 0, []
    for m, ext in zip(anclas, info):
        if not ext:
            continue
        anc = m.group(0)
        mk = next((x for x in marcadores if x["c"] == ext["from"][0] and x["r"] == ext["from"][2]
                   and x["viejo"] == (ext["from"][1], ext["to"][1], ext["from"][3], ext["to"][3])), None)
        for lado in ("from", "to"):
            c, off, r, roff = ext[lado]
            if mk:
                nx = mk["nuevo"][0 if lado == "from" else 1]
                ny = mk["nuevo"][2 if lado == "from" else 3]
            else:
                nx, ny = extremo_x(c, r, off), nuevo("row", r, roff)
            anc = re.sub(rf'<xdr:{lado}>\s*<xdr:col>{c}</xdr:col>\s*<xdr:colOff>-?\d+</xdr:colOff>\s*<xdr:row>{r}</xdr:row>\s*'
                         rf'<xdr:rowOff>-?\d+</xdr:rowOff>\s*</xdr:{lado}>',
                         f"<xdr:{lado}><xdr:col>{c}</xdr:col><xdr:colOff>{max(0, nx)}</xdr:colOff><xdr:row>{r}</xdr:row>"
                         f"<xdr:rowOff>{max(0, ny)}</xdr:rowOff></xdr:{lado}>", anc, count=1)
        if anc != m.group(0):
            movidas.append(nombre_forma(anc))
        piezas.append(dibujo[ultimo:m.start()] + anc)
        ultimo = m.end()
    return "".join(piezas) + dibujo[ultimo:], movidas


def col_reticula_autor(trabajo, estado):
    """Última columna (1, 2…) que cubre la retícula del autor en el original («00 Copia exacta»), o None."""
    _, pasos = nombres(trabajo)
    try:
        with zipfile.ZipFile(pasos / estado["pasos"][0]["archivo"]) as z:
            hoja = estado.get("hoja") or hoja_cuadro(z)[0]
            ruta = dibujo_de_hoja(z, hoja)
            if not ruta or ruta not in z.namelist():
                return None
            for m in ANCLA.finditer(z.read(ruta).decode("utf-8")):
                if es_reticula(m.group(0)):
                    hasta = re.search(r'<xdr:to>\s*<xdr:col>(\d+)</xdr:col>', m.group(0))
                    return int(hasta.group(1)) + 1 if hasta else None
    except (OSError, KeyError, IndexError, zipfile.BadZipFile, Fallo):
        return None
    return None


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
    # Letra de las celdas de la publicación (LATAM/Indicadores Macrofinancieros: 6,5 pt, como sus publicados); si no,
    # la de la guía (7,5)
    global CUERPO_CELDA
    anterior = CUERPO_CELDA
    CUERPO_CELDA = float(pub_de(pid).get("cuerpo_celda", CUERPO_CELDA))
    try:
        with zipfile.ZipFile(base) as z:
            # Los mapas de calor (cifras escondidas por el formato condicional), con su letra (Indicadores: 7 pt en todos
            # los 02 publicados de los grandes; los demás cuadros, 6,5)
            if pub_de(pid).get("cuerpo_mapa_calor") and cifras_ocultas(z.read(hoja_de(z, hoja)).decode("utf-8"),
                                                                       z.read("xl/styles.xml").decode("utf-8")):
                CUERPO_CELDA = float(pub_de(pid)["cuerpo_mapa_calor"])
            propuestas = []
            cambios, detalle, cuadro = celdas(z, hoja, estado.get("idioma", "es"), propuestas, pub_de(pid),
                                              col_reticula_autor(trabajo, estado))
    finally:
        CUERPO_CELDA = anterior
    return nuevo_paso(trabajo, CELDAS, cambios, detalle, cuadro, propuestas=propuestas)


def celdas(z, hoja, idioma="es", propuestas_salida=None, pub=None, fin_autor=None):
    ruta_hoja = hoja_de(z, hoja)
    hoja_xml = z.read(ruta_hoja).decode("utf-8")
    comp_xml, compartidos = leer_compartidos(z)
    estilos = Estilos(z.read("xl/styles.xml").decode("utf-8"))
    dibujo = z.read(dibujo_de_hoja(z, hoja)).decode("utf-8") if dibujo_de_hoja(z, hoja) else ""
    cambios_dibujo = {}
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
    # Cabecera abajo (LATAM/Economía Latinoamericana, publicado 05: «Promedio⏎2007-2024» y «2025», combinadas por el
    # autor de la fila de los grupos a la de abajo pasando por filas ocultas, van solo en la fila de abajo, con «2026»,
    # «2027» y los trimestres): se descombinan y el texto baja. Solo si la combinada pasa por filas ocultas (en el 04,
    # «Expectativas de mercado a 1 año» ocupa sus dos filas visibles, como en su publicado)
    bajadas = []
    if pub.get("cabecera_abajo"):
        ocultas_h = {int(r) for r in re.findall(r'<row\b(?=[^>]*\bhidden="1")[^>]*?\br="(\d+)"', hoja_xml)}
        for a1, b1, a2, b2 in list(rangos):
            if not (a1 == a2 and c1 < a1 <= c2 and f1 <= b1 < b2 <= f2) or not any(b1 < f < b2 for f in ocultas_h):
                continue
            otras_abajo = any(todas.get((c, b2), {}).get("texto", "").strip() for c in range(c1, c2 + 1) if c != a1)
            otras_arriba = any(todas.get((c, b1), {}).get("texto", "").strip() for c in range(c1, c2 + 1) if c != a1)
            arriba = todas.get((a1, b1))
            if not (otras_abajo and otras_arriba and arriba and arriba["texto"].strip()):
                continue
            ra, rb = ref(a1, b1), ref(a1, b2)
            nueva = re.sub(r'\br="[A-Z]+\d+"', f'r="{rb}"', arriba["xml"], count=1)
            vacia = re.sub(r'\st="\w+"', "", re.match(r'<c\b[^>]*?(?=/?>)', arriba["xml"]).group(0)) + "/>"
            if not re.search(rf'<c r="{rb}"[^>]*?(?:/>|>.*?</c>)', hoja_xml, re.S):
                continue
            hoja_xml = re.sub(rf'<c r="{ra}"[^>]*?(?:/>|>.*?</c>)', lambda m: vacia, hoja_xml, count=1, flags=re.S)
            hoja_xml = re.sub(rf'<c r="{rb}"[^>]*?(?:/>|>.*?</c>)', lambda m: nueva, hoja_xml, count=1, flags=re.S)
            hoja_xml = re.sub(rf'<mergeCell ref="{ra}:{rb}"\s*/>', "", hoja_xml)
            bajadas.append(f"{ra} «{arriba['texto'].strip().replace(chr(10), ' ')[:30]}» → {rb}")
        if bajadas:
            n_comb = len(re.findall(r'<mergeCell\b', hoja_xml))
            hoja_xml = re.sub(r'<mergeCells count="\d+"', f'<mergeCells count="{n_comb}"', hoja_xml)
            hoja_xml = re.sub(r'<mergeCells count="0"\s*>\s*</mergeCells>|<mergeCells count="0"\s*/>', "", hoja_xml)
            todas = celdas_hoja(hoja_xml, compartidos)
            rangos = combinadas(hoja_xml)
    # El cuadro se busca con todas las celdas (las filas ocultas lo mantienen unido); para lo demás, sin las ocultas
    filas_ocultas = {f for (_, f) in todas} - {f for (_, f) in sin_filas_ocultas(todas, hoja_xml)}
    no_se_ven = cifras_ocultas(hoja_xml, estilos.xml)
    todas = sin_filas_ocultas(todas, hoja_xml)
    while f1 < f2 and not any(todas.get((c, f1), {}).get("texto", "").strip() for c in range(c1, c2 + 1)):
        f1 += 1
    # Columnas a la derecha de la retícula del autor, separadas del cuadro por columnas vacías (Economía Latinoamericana
    # 04: BB «actual», con los tipos de interés, que el publicado deja fuera): no son del cuadro
    fuera_autor = []
    if fin_autor and c1 < fin_autor < c2:
        con_txt = lambda c: ancho_col(c) > 0 and any(todas.get((c, f), {}).get("texto", "").strip() for f in range(f1, f2 + 1))
        dentro = [c for c in range(c1, fin_autor + 1) if con_txt(c)]
        despues = [c for c in range(fin_autor + 1, c2 + 1) if con_txt(c)]
        if len(dentro) >= 2 and despues and any(ancho_col(c) > 0 and not con_txt(c) for c in range(max(dentro) + 1, min(despues))):
            fuera_autor = despues
            c2 = max(dentro)
    # Cabecera hecha con cuadros de texto (DO26XX_02: símbolos de ecuación 𝑡, 𝛽, 𝜌, 𝜎² sobre las celdas vacías de la
    # fila 11): la fila de justo encima del cuadro, sin textos en celdas y con cuadros de texto anclados en sus
    # columnas, es la cabecera (el publicado la colorea como tal)
    # Texto encima de la cabecera, separado de ella por filas ocultas o vacías, en una columna que tiene cabecera
    # debajo (Arg_02: AB3 «Respecto al resto de los emergentes» sobre AB8 «Último dato (b)»): es la primera fila de
    # la cabecera (el publicado le da sus tres líneas)
    encima_cab = []
    if f1 > 2:
        visibles_c = [c for c in range(c1, c2 + 1) if ancho_col(c) > 0]
        r = f1 - 1
        while r > max(1, f1 - 8) and (r in filas_ocultas or not any(todas.get((c, r), {}).get("texto", "").strip() for c in visibles_c)):
            r -= 1
        if r < f1 - 1 and r not in filas_ocultas:
            con_t = [c for c in visibles_c if todas.get((c, r), {}).get("texto", "").strip()]
            primera_vis = next((c for c in visibles_c if any(todas.get((c, f), {}).get("texto", "").strip() for f in range(f1, f2 + 1))), c1)
            if 1 <= len(con_t) <= 2 and all(c != primera_vis and todas.get((c, f1), {}).get("texto", "").strip() for c in con_t) \
                    and not any(RE_UNIDADES.match(todas[(c, r)]["texto"]) or ROTULO.match(todas[(c, r)]["texto"]) for c in con_t):
                encima_cab = [(c, r) for c in con_t]
                f1 = r
    # Bloque de arriba (LATAM/Indicadores Macrofinancieros 01: «PIB per cápita… 2026» y «Esperanza de vida… 2024», dos
    # tablitas lado a lado encima de la tabla, separadas de ella por filas vacías): es parte del cuadro, con su año
    # arriba, los conceptos a la izquierda y los valores a la derecha; cada tablita lleva sus líneas en su ancho
    bloque = None
    if pub.get("bloque_arriba"):
        # Pegado a la tabla por una fila vacía (Br_01: bloque en 2-6, fila 7 vacía, tabla desde la 8): la tabla
        # empieza después de la fila vacía si lo de encima tiene forma de bloque (3 filas con 2 textos al menos)
        hay_txt = lambda f: any(todas.get((c, f), {}).get("texto", "").strip() for c in range(c1, c2 + 1) if ancho_col(c) > 0)
        for r in range(f1 + 3, min(f2, f1 + 12)):
            if r not in filas_ocultas and not hay_txt(r):
                encima_r = [f for f in range(f1, r) if sum(1 for c in range(c1, c2 + 1) if ancho_col(c) > 0
                                                          and todas.get((c, f), {}).get("texto", "").strip()) >= 2]
                siguiente_r = next((f for f in range(r + 1, f2 + 1) if hay_txt(f)), None)
                if len(encima_r) >= 3 and siguiente_r:
                    f1 = siguiente_r
                break
        txt = lambda c, f: todas.get((c, f), {}).get("texto", "").strip() and ancho_col(c) > 0
        filas_b = [f for f in range(max(1, f1 - 12), f1) if f not in filas_ocultas and sum(1 for c in range(c1, c2 + 1) if txt(c, f)) >= 1]
        # el tramo de filas seguidas (con huecos de una fila como mucho) que acaba más cerca de la tabla
        tramo = []
        for f in reversed(filas_b):
            if tramo and tramo[0] - f > 2:
                break
            tramo.insert(0, f)
        es_num = lambda c, f: es_cifra(todas[(c, f)]) or bool(re.match(r'\s*[\d.,]+\s*(%|\(p\))?', todas[(c, f)]["texto"]))
        cuerpo_b = [f for f in tramo if sum(1 for c in range(c1, c2 + 1) if txt(c, f)) >= 2]
        if len(cuerpo_b) >= 3:
            etiquetas = sorted({c for f in cuerpo_b for c in range(c1, c2 + 1) if txt(c, f) and not es_num(c, f)})
            etiquetas = [c for c in etiquetas if sum(1 for f in cuerpo_b if txt(c, f) and not es_num(c, f)) >= 2]
            valores = sorted({c for f in cuerpo_b for c in range(c1, c2 + 1) if txt(c, f) and c not in etiquetas})
            grupos = []
            for i, e in enumerate(etiquetas):
                limite = etiquetas[i + 1] if i + 1 < len(etiquetas) else c2 + 1
                v = [c for c in valores if e < c < limite]
                if v:
                    grupos.append((e, max(v)))
            if grupos:
                cabeza_b = tramo[0] if tramo[0] not in cuerpo_b or not any(txt(c, tramo[0]) for c in etiquetas) else None
                bloque = {"filas": tramo, "cabecera": cabeza_b, "grupos": grupos, "valores": valores, "movidas": []}
                # Una tablita que empieza en la primera columna de datos de la tabla (Br_01: «Esperanza de vida…» en G,
                # pegada a la de la izquierda en cuanto se oculta la separación F): sus conceptos pasan a la siguiente
                # columna de datos, como en el PDF publicado (decisión del usuario, 2026-11-24)
                datos_tabla = [c for c in range(c1, c2 + 1) if ancho_col(c) > 0
                               and any(es_cifra(todas[(c, f)]) for f in range(f1, f2 + 1) if (c, f) in todas and todas[(c, f)]["texto"].strip())]
                for i, (e, v) in enumerate(list(grupos)):
                    if i == 0 or not datos_tabla or e != datos_tabla[0] or grupos[i - 1][1] in datos_tabla:
                        continue
                    nueva_e = next((c for c in datos_tabla if c > e and c < v), None)
                    if nueva_e is None:
                        continue
                    for f in tramo:
                        orig = todas.get((e, f))
                        if not orig or not orig["texto"].strip() or todas.get((nueva_e, f), {}).get("texto", "").strip():
                            continue
                        ra, rb = ref(e, f), ref(nueva_e, f)
                        nueva_c = re.sub(r'\br="[A-Z]+\d+"', f'r="{rb}"', orig["xml"], count=1)
                        vacia_c = re.sub(r'\st="\w+"', "", re.match(r'<c\b[^>]*?(?=/?>)', orig["xml"]).group(0)) + "/>"
                        hoja_xml = re.sub(rf'<c r="{ra}"[^>]*?(?:/>|>.*?</c>)', lambda m_: vacia_c, hoja_xml, count=1, flags=re.S)
                        if re.search(rf'<c r="{rb}"[^>]*?(?:/>|>.*?</c>)', hoja_xml, re.S):
                            hoja_xml = re.sub(rf'<c r="{rb}"[^>]*?(?:/>|>.*?</c>)', lambda m_: nueva_c, hoja_xml, count=1, flags=re.S)
                        else:
                            hoja_xml = asegurar_filas(hoja_xml, [f])
                            hoja_xml = con_estilo(hoja_xml, {(nueva_e, f): orig["s"]})
                            hoja_xml = re.sub(rf'<c r="{rb}"[^>]*?/>', lambda m_: nueva_c, hoja_xml, count=1)
                        bloque["movidas"].append(f"{ra}→{rb}")
                    grupos[i] = (nueva_e, v)
                if bloque["movidas"]:
                    todas = sin_filas_ocultas(celdas_hoja(hoja_xml, compartidos), hoja_xml)
    formas_fila, cabecera_formas, filas_formas = {}, [], set()
    for anc in ANCLA.finditer(dibujo):
        desde = re.search(r'<xdr:from>\s*<xdr:col>(\d+)</xdr:col>.*?<xdr:row>(\d+)</xdr:row>', anc.group(0), re.S)
        if desde and html.unescape(texto_forma(anc.group(0))).strip():
            formas_fila.setdefault(int(desde.group(2)) + 1, set()).add(int(desde.group(1)) + 1)
    while f1 > 1 and not any(todas.get((c, f1 - 1), {}).get("texto", "").strip() for c in range(c1, c2 + 1)) \
            and len({c for c in formas_fila.get(f1 - 1, set()) if c1 < c <= c2}) >= 2:
        f1 -= 1
        filas_formas.add(f1)
        cabecera_formas.append(f"Cabecera con cuadros de texto (fórmulas o símbolos) en la fila {f1}, sobre celdas vacías: es parte del cuadro"
                               + marca([ref(c, f1) for c in sorted(formas_fila[f1]) if c1 <= c <= c2]))
    detalle = []
    # La FUENTE y las notas que el autor escribió en celdas, debajo del cuadro, no son parte de él
    for f in range(f1 + 1, f2 + 1):
        fila_txt = [todas.get((c, f), {}).get("texto", "").strip() for c in range(c1, c2 + 1)]
        primero = next((t for t in fila_txt if t), "")
        if primero and ROTULO.match(primero) and len([t for t in fila_txt if t]) == 1:
            en_celdas = [ref(cc, ff) for (cc, ff), x in sorted(todas.items(), key=lambda kv: (kv[0][1], kv[0][0]))
                         if ff >= f and x["texto"].strip() and ROTULO.match(x["texto"]) is not None or (ff > f and x["texto"].strip() and c1 <= cc <= c2 and ff <= f + 12)]
            detalle.append(f"Aviso: la fuente y las notas van en celdas bajo el cuadro (desde la fila {f}): no son parte del "
                           "cuadro y no se maquetan; pásalas al cuadro de texto de FUENTES" + marca(en_celdas[:20]))
            f2 = f - 1
            while f2 > f1 and not any(todas.get((c, f2), {}).get("texto", "").strip() for c in range(c1, c2 + 1)):
                f2 -= 1
            break
    detalle.insert(0, f"Cuadro en {ref(c1, f1)}:{ref(c2, f2)} ({f2 - f1 + 1} filas, {c2 - c1 + 1} columnas)")
    if encima_cab:
        detalle.insert(1, "Texto encima de la cabecera, separado por filas ocultas, unido a ella: " + ", ".join(
            f"{ref(*k)} «{todas[k]['texto'].strip()[:35]}»" for k in encima_cab) + marca([ref(*k) for k in encima_cab]))
    if bajadas:
        detalle.insert(1, "Cabecera: textos combinados por el autor desde la fila de los grupos, bajados a la última fila de "
                       "la cabecera, como el publicado: " + "; ".join(bajadas))
    if fuera_autor:
        detalle.insert(1, "Columnas a la derecha de la retícula del autor, separadas por columnas vacías: fuera del cuadro, "
                       "sin tocar (como el publicado): " + ", ".join(ref(c, 1)[:-1] for c in fuera_autor)
                       + marca([ref(c, f1) for c in fuera_autor]))
    detalle[1:1] = cabecera_formas
    # Textos en celdas fuera del cuadro y dentro de la retícula (3.4: A28, que el TERMINADO borró)
    x_col, pos = {}, 0
    for c in range(1, max([k[0] for k in todas] or [1]) + 1):
        x_col[c] = pos
        pos += unidades_a_emu(ancho_col(c))
    fuera = [(c, f) for (c, f), x in sorted(todas.items(), key=lambda kv: (kv[0][1], kv[0][0]))
             if x["texto"].strip() and not (c1 <= c <= c2 and f1 <= f <= f2) and ancho_col(c) > 0
             and (x_col.get(c, ancho_ret) < ancho_ret or (f1 <= f <= f2 and c2 < c <= c2 + 3
                  and sum(1 for (cc, ff), y in todas.items() if cc == c and f1 <= ff <= f2 and y["texto"].strip()) == 1))
             and not (f > f2 and ROTULO.match(x["texto"]))
             and not (bloque and f in bloque["filas"])]
    # Otra tabla del autor debajo del cuadro (Economía Latinoamericana 01: la mensual en A43:G59, que el publicado
    # borró): sus filas se ocultan, sin borrar nada, para que no se vean dentro de la retícula
    abajo = [(c, f) for c, f in fuera if f > f2 + 1]
    filas_otra = set()
    if len({f for _, f in abajo}) >= 3 and len({c for c, _ in abajo}) >= 3:
        filas_otra = set(range(min(f for _, f in abajo), max(f for _, f in abajo) + 1))
        detalle.append(f"Otra tabla del autor debajo del cuadro (filas {min(filas_otra)}-{max(filas_otra)}): filas ocultas, "
                       "sin borrar nada (el publicado la quitó)" + marca([ref(c, f) for c, f in abajo]))
        fuera = [k for k in fuera if k not in abajo]
    if fuera:
        detalle.append("Aviso: hay textos en celdas fuera del cuadro, dentro de la retícula o pegados a él (¿notas o restos del autor?): "
                       + ", ".join(f"{ref(c, f)} «{todas[(c, f)]['texto'].strip()[:30]}»" for c, f in fuera[:5])
                       + ("…" if len(fuera) > 5 else "") + marca([ref(c, f) for c, f in fuera]))

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
        while fin_cab > f1 and not datos(fin_cab) and (d(primera, fin_cab)["texto"].strip() or fin_cab in filas_ocultas):
            fin_cab -= 1
    else:
        fin_cab = f1
    fin_cab = max(fin_cab, f1)
    for (a, b), n in filas_comb.items():
        if b <= fin_cab:
            fin_cab = max(fin_cab, b + n - 1)
    detalle.append(f"Cabecera: filas {f1}-{fin_cab}" if fin_cab > f1 else f"Cabecera: fila {f1}")

    # Textos de la cabecera repetidos por el autor en filas de datos (1.3: «Cuota de Oriente Medio…» otra vez en el
    # segundo bloque): se borran, como en el TERMINADO, y la fila queda como título de bloque
    textos_cab = {c: {d(c, f)["texto"].strip() for f in range(f1, fin_cab + 1) if d(c, f)["texto"].strip()} for c in range(c1, c2 + 1)}
    repetidos = [(c, f) for f in range(fin_cab + 1, f2 + 1) for c in range(primera + 1, c2 + 1)
                 if (c, f) not in tapadas and d(c, f)["texto"].strip() and not d(c, f)["numero"]
                 and d(c, f)["texto"].strip() in textos_cab.get(c, set())]
    for k in repetidos:
        todas[k] = {**todas[k], "texto": "", "borrar": True}
    if repetidos:
        detalle.append("Aviso: textos de la cabecera repetidos en filas de datos, borrados: "
                       + ", ".join(ref(c, f) for c, f in repetidos[:8]) + marca([ref(c, f) for c, f in repetidos]))

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

    # Hijos de un título de bloque (concepto sin sangría ni datos, como «Edad»): van sangrados al menos un nivel
    # aunque el autor no los sangrara, si en el cuadro hay otros hijos sangrados (TERMINADO 1.4)
    def es_bloque(f):
        t = d(primera, f)["texto"].strip()
        return bool(t) and sangria_autor(f) == 0 and not RE_TOTAL.match(t) and \
            not any(d(c, f)["texto"].strip() for c in range(primera + 1, c2 + 1) if (c, f) not in tapadas)
    # En Documentos Ocasionales (publicado DO26XX_04) el TOTAL justo bajo el título de bloque es la cabeza del bloque:
    # no lo cierra, y lo que viene detrás («Jubilación», «Supervivientes»…) va sangrado aunque el autor no lo sangrara
    apartados_pub = bool((pub or {}).get("bloques_con_apartados"))
    hijos, bloque_abierto, anterior = set(), False, None
    for f in range(fin_cab + 1, f2 + 1):
        t = d(primera, f)["texto"].strip()
        if es_bloque(f):
            bloque_abierto = True
        elif bloque_abierto and t and not RE_TOTAL.match(t):
            hijos.add(f)
        elif RE_TOTAL.match(t):
            bloque_abierto = apartados_pub and anterior is not None and es_bloque(anterior)
        if t:
            anterior = f
    sangrar_hijos = any(sangria_autor(f) > 0 for f in hijos) or (apartados_pub and bool(hijos))
    if not nivel_de and sangrar_hijos:
        nivel_de = {}

    def nivel_fila(f):
        n = nivel_de.get(sangria_autor(f), 0)
        return max(n, 1) if sangrar_hijos and f in hijos else n
    sin_sangria = [f for f in sorted(hijos) if sangrar_hijos and nivel_de.get(sangria_autor(f), 0) == 0]

    # Anchos de columna: el cuadro llega al borde derecho de la retícula. Manda la primera columna (el ancho de su
    # texto más largo en una línea); las demás, si se puede, iguales. Si no caben, la primera cede (su texto pasa a
    # varias líneas) hasta lo que pida su palabra más larga. Las estrechas de separación y las ocultas, igual.
    anchos_viejos = {c: ancho_col(c) for c in range(1, c2 + 1)}
    otras = [c for c in range(primera + 1, c2 + 1) if COLUMNA_ESTRECHA <= ancho_col(c)]
    # Columnas anchas sin ningún texto (ni en la cabecera) entre otras: separaciones como las estrechas (Economía
    # Latinoamericana 04: AV, de 69 pt, entre la escala y «Expectativas»; el publicado la deja en 1 pt)
    celdas_forma = set()   # celdas con alguna forma encima (puntos, flechas, símbolos): no están vacías
    for anc in ANCLA.finditer(dibujo):
        if es_reticula(anc.group(0)) or es_pastilla(anc.group(0)):
            continue
        for col_, fil_ in re.findall(r'<xdr:(?:from|to)>\s*<xdr:col>(\d+)</xdr:col>.*?<xdr:row>(\d+)</xdr:row>', anc.group(0), re.S):
            celdas_forma.add((int(col_) + 1, int(fil_) + 1))
    vacias_anchas = [c for c in otras if primera + 1 < c < c2
                     and not (bloque and any(todas.get((c, f), {}).get("texto", "").strip() for f in bloque["filas"]))
                     and not any(d(c, f)["texto"].strip() or (c, f) in celdas_forma for f in range(f1, f2 + 1))]
    if vacias_anchas and len(otras) - len(vacias_anchas) >= 1:
        otras = [c for c in otras if c not in vacias_anchas]
        detalle.append("Columnas vacías dentro del cuadro, como columnas de separación: " + ", ".join(ref(c, 1)[:-1] for c in vacias_anchas))
    fijas = [c for c in range(primera + 1, c2 + 1) if c not in otras and ancho_col(c) > 0]
    # Columnas de separación (estrechas, visibles y sin texto): 3 pt, iguales en Mac y en Windows
    separaciones = [c for c in fijas if ancho_col(c) > 0 and not any(d(c, f)["texto"].strip() for f in range(f1, f2 + 1))]
    # La de justo detrás de la primera columna no separa grupos: sobra (TERMINADO 1.5 publicado la quitó); se oculta
    pegada = [c for c in separaciones if c == primera + 1]
    # En un mapa de calor (celdas de solo color, Arg_02) sí separa los conceptos de los colores: se queda
    if no_se_ven:
        pegada = []
    separaciones = [c for c in separaciones if c not in pegada]
    if pegada:
        detalle.append(f"Columna de separación entre la primera columna y los datos ({ref(pegada[0], 1)[:-1]}): oculta, "
                       "no separa grupos (como el publicado del 1.5)")
    # Las demás solo se quedan si separan grupos: una cabecera combinada sobre varias columnas que acaba justo antes
    # o empieza justo después. Entre columnas sueltas sobran (publicado 3.1: las quitó) y se ocultan
    grupos = [(a1, a2) for a1, b1, a2, b2 in rangos if a2 > a1 and f1 <= b1 <= fin_cab]
    # (con las columnas estrechas que llevan texto: Arg_02, los semestres «I S»/«II S» bajo cada año)
    con_datos = [k for k in range(primera + 1, c2 + 1) if k not in separaciones and ancho_col(k) > 0]

    def separa_grupos(c):
        antes = max([k for k in con_datos if k < c] or [0])
        despues = min([k for k in con_datos if k > c] or [0])
        return any(a2 == antes or a1 == despues for a1, a2 in grupos if not (a1 < c < a2))
    # (en un mapa de calor se quedan todas: Arg_02, la de entre «2026» y «Último dato» se ve en el publicado)
    sueltas_sep = [] if no_se_ven else [c for c in separaciones if not separa_grupos(c)]
    if sueltas_sep:
        separaciones = [c for c in separaciones if c not in sueltas_sep]
        pegada = pegada + sueltas_sep
        detalle.append("Columnas de separación entre columnas sueltas (sin cabecera de grupo): ocultas, como el publicado "
                       "del 3.1: " + ", ".join(ref(c, 1)[:-1] for c in sueltas_sep))
    if separaciones or pegada:
        w_sep = ancho_comun(SEPARACION_PT, mdw, digito_windows(estilos.xml))
        ancho_previo = ancho_col
        ancho_col = lambda c, _v=ancho_previo, _s=set(separaciones), _w=w_sep, _p=set(pegada): 0.0 if c in _p else (_w if c in _s else _v(c))
    # Columnas estrechas con texto que no les cabe en una línea (Arg_02: semestres de 14 pt y «II S» pide 14,3): se
    # ensanchan lo justo, en múltiplos de 3 pt, a costa de la primera; así no se parten («II⏎S»)
    ensanchadas = {}
    for c in fijas:
        if c in separaciones or c in pegada or ancho_col(c) == 0:
            continue
        pide = max([medir(l.strip(), CUERPO_CELDA) + 2 * RELLENO_CELDA_PT for f in range(f1, fin_cab + 1)
                    if (c, f) not in tapadas and d(c, f)["texto"].strip() and not any(a1 == c and b1 == f and a2 > a1 for a1, b1, a2, b2 in rangos)
                    for l in d(c, f)["texto"].split("\n")] or [0])
        # medio punto de tolerancia: el relleno de celda es una estimación algo holgada (a 7 pt «II S» pide 15,1)
        if pide > round(ancho_col(c) * mdw) + 0.5:
            ensanchadas[c] = ancho_comun(MULTIPLO_PT * math.ceil((pide - 0.5) / MULTIPLO_PT - 1e-6), mdw, digito_windows(estilos.xml))
    if ensanchadas:
        detalle.append("Columnas estrechas con texto que no cabía en una línea, ensanchadas lo justo: " + ", ".join(
            f"{ref(c, 1)[:-1]} {round(ancho_col(c) * mdw)}→{round(w * mdw)} pt" for c, w in sorted(ensanchadas.items())))
        ancho_previo2 = ancho_col
        ancho_col = lambda c, _v=ancho_previo2, _e=dict(ensanchadas): _e.get(c, _v(c))
    espacio_pt = (ancho_ret - sum(unidades_a_emu(ancho_col(c)) for c in list(range(1, primera)) + fijas)) / EMU_PT
    # Filas de suma (Memoria 2.1 publicado): sus cifras son la SUMA de las filas de justo debajo; van en Roboto
    # Medium como un subtotal (decisión del usuario, 2026-11-17), sin fondo
    def es_suma(f):
        for c in range(primera + 1, c2 + 1):
            m = re.search(r'<f>\s*SUM\(\$?([A-Z]+)\$?(\d+):\$?([A-Z]+)\$?(\d+)\)\s*</f>', d(c, f)["xml"] or "")
            if m and m.group(1) == m.group(3) and int(m.group(2)) == f + 1 and int(m.group(4)) > f + 1:
                return True
        return False
    filas_suma = {f for f in range(fin_cab + 1, f2 + 1) if es_suma(f)}
    # La fila TOTAL, entera en Roboto Medium (cifras incluidas), en todas las publicaciones (decisión del usuario,
    # 2026-11-17: así todos los Memoria publicados)
    filas_total = {f for f in range(fin_cab + 1, f2 + 1) if re.fullmatch(r'\s*total\s*', d(primera, f)["texto"], re.I)
                   and not d(primera, f)["texto"].startswith(" ")}
    filas_suma |= filas_total
    # Filas madre: con datos y con filas más sangradas justo debajo («A entidades de crédito españolas» y sus
    # «Lideradas por…», publicado Memoria 3.1): su texto de la primera columna, en Roboto Medium (decisión del usuario)
    con_texto = [f for f in range(fin_cab + 1, f2 + 1) if d(primera, f)["texto"].strip()]
    # Solo las de nivel intermedio (sangradas, con otras más sangradas debajo): así los publicados (Memoria 3.1, en
    # Medium; 1.5 y Memoria 3.2 y 4.2, madres sin sangría, en Light). Que sumen o no a sus hijas no decide
    madres = {f for f, g in zip(con_texto, con_texto[1:]) if nivel_fila(f) >= 1 and nivel_fila(g) > nivel_fila(f)
              and not RE_TOTAL.match(d(primera, f)["texto"])}

    def medir_de(c, f):
        """La medida de la variante que llevará la celda: Roboto Medium si el autor la puso en negrita."""
        return medir_medium if f in filas_suma or (c == primera and f in madres) or es_negrita(estilos.fuente_de(d(c, f)["s"])) else medir
    palabra = lambda t, m=medir: max([m(w, CUERPO_CELDA) for w in re.split(r"[ \n]+", t) if w] or [0])

    def vista(c, f):
        x = d(c, f)
        nf = estilos.sin_relleno(x["s"])
        codigo = formato_numero(estilos, x["s"])
        if nf is not None:
            codigo = FORMATOS_INTERNOS.get(nf) or dict(estilos.nuevos_formatos).get(nf, codigo)
        return cifra_vista(x["texto"], codigo) if x["numero"] else x["texto"]
    necesita = {c: 0.0 for c in otras}
    for f in range(f1, f2 + 1):
        for c in otras:
            if (c, f) in tapadas or not d(c, f)["texto"].strip():
                continue
            t = vista(c, f).strip()
            mc = medir_de(c, f)
            if (c, f) in no_se_ven:
                continue
            w = mc(t, CUERPO_CELDA) if es_cifra(d(c, f)) and f > fin_cab else palabra(t, mc)
            tramo_cols = [k for k in otras if k == c or ((k, f) in tapadas and k > c and all((j, f) in tapadas for j in range(c + 1, k + 1)))]
            necesita[c] = max(necesita[c], w / max(1, len(tramo_cols)) + 2 * RELLENO_CELDA_PT)
    if bloque:
        for f in bloque["filas"]:
            for c in bloque["valores"]:
                if c in necesita and d(c, f)["texto"].strip():
                    necesita[c] = max(necesita[c], medir_de(c, f)(vista(c, f).strip(), CUERPO_CELDA) + 2 * RELLENO_CELDA_PT)
    # Columnas de nombres propios (Memoria 6.1, «Entidad»: «Banco Bilbao Vizcaya Argentaria, SA»): solo textos, de
    # una línea, y cada uno con 2 o más palabras, todas en mayúscula inicial salvo los conectores. El publicado las
    # pone en una línea y a la izquierda; las de conceptos («Relajación, concentración», DO 05) siguen al centro
    def textos_cuerpo(c):
        return [vista(c, f).strip() for f in range(fin_cab + 1, f2 + 1) if (c, f) not in tapadas and d(c, f)["texto"].strip()]

    def es_nombre(t):
        palabras = [w for w in re.findall(r"[^\W\d_][\w.&'-]*", t) if w.upper() not in CONECTORES_PROPIOS]
        return "\n" not in t and len(palabras) >= 2 and all(w[0].isupper() for w in palabras)
    nombres = {c for c in otras if len(textos_cuerpo(c)) >= 2
               and not any(es_cifra(d(c, f)) for f in range(fin_cab + 1, f2 + 1) if (c, f) not in tapadas and d(c, f)["texto"].strip())
               and all(es_nombre(t) for t in textos_cuerpo(c))}
    en_linea = {c: max(medir_de(c, f)(vista(c, f).strip(), CUERPO_CELDA) for f in range(fin_cab + 1, f2 + 1)
                       if (c, f) not in tapadas and d(c, f)["texto"].strip()) + 2 * RELLENO_CELDA_PT for c in nombres}
    nombres = {c for c in nombres if en_linea[c] <= espacio_pt / 3}
    natural = minimo = 0.0
    textos_primera = []
    # Títulos de bloque que desbordan (LATAM/Economía Latinoamericana, publicado 05: «PIB (variación respecto al
    # período anterior) (a) (b)», «PRO MEMORIA…» pasan por encima de las celdas vacías de su fila): sin sangría y sin
    # datos en la fila; no cuentan para el ancho de la primera columna y van en una línea, sin ajustar texto
    desbordan = set()
    if pub.get("titulos_bloque_desbordan") and any(es_cifra(d(c, f)) for f in range(fin_cab + 1, f2 + 1)
                                                    for c in range(primera + 1, c2 + 1) if d(c, f)["texto"].strip()):
        # Solo en cuadros de cifras: en los de textos (02, El Niño) el título de bloque va dentro de su columna
        desbordan = {f for f in range(fin_cab + 1, f2 + 1) if d(primera, f)["texto"].strip() and nivel_fila(f) == 0
                     and (primera, f) not in tapadas and not any((primera, f) == (a1, b1) and a2 > a1 for a1, b1, a2, b2 in rangos)
                     and not any(d(c, f)["texto"].strip() for c in range(primera + 1, c2 + 1) if ancho_col(c) > 0)}
    for f in range(f1, f2 + 1):
        t = d(primera, f)["texto"]
        if not t.strip() or (primera, f) in tapadas or f in desbordan:
            continue
        espacios = " " * (SANGRIA * nivel_fila(f)) if f > fin_cab else ""
        cuerpo = VINETA.sub("", t.strip(" \u00a0"))
        mc = medir_de(primera, f)
        filas_juntas = next((b2 - b1 + 1 for a1, b1, a2, b2 in rangos if a1 == a2 == primera and b1 == f and b2 > b1), 1)
        if filas_juntas > 1 and f > fin_cab:
            # Combinada en vertical con N filas (DO 02: «Indicadores directos de actividad neuronal» en A7:A9): cabe
            # en N líneas sin alargar el cuadro; su ancho natural es el mínimo con el que no pasa de N líneas
            w = palabra(cuerpo, mc)
            while len(partir(cuerpo, w, mc)) > filas_juntas and w < espacio_pt:
                w += 1
            natural = max(natural, mc(espacios, CUERPO_CELDA) + w)
        else:
            natural = max(natural, max(mc(espacios + l.strip(), CUERPO_CELDA) for l in cuerpo.split("\n")))
        textos_primera.append((f, espacios, "\n".join(l.strip() for l in cuerpo.split("\n")), mc))
        minimo = max(minimo, mc(espacios, CUERPO_CELDA) + palabra(cuerpo, mc))
    natural += 2 * RELLENO_CELDA_PT + 1.5   # holgura: el redondeo a píxeles no debe partir el texto más largo
    minimo += 2 * RELLENO_CELDA_PT
    a_medida, medida, por_nombres = False, {}, False

    def ancho_justo(cols):
        """Lo que pide la cabecera más larga en una línea o la cifra más ancha (sin las cabeceras combinadas sobre
        varias columnas)."""
        pide = [necesita[c] for c in cols]
        for c in cols:
            for f in range(f1, fin_cab + 1):
                if (c, f) in tapadas or not d(c, f)["texto"].strip() or (c, f) in encima_cab:
                    continue
                if any(a1 == c and b1 == f and a2 > a1 for a1, b1, a2, b2 in rangos):
                    continue
                pide.append(max(medir_de(c, f)(l.strip(), CUERPO_CELDA) for l in d(c, f)["texto"].split("\n")) + 2 * RELLENO_CELDA_PT)
        return max(pide or [0])
    if nombres:
        # Los nombres en una línea, si caben sin partir la primera columna; si no, se parten como cualquier texto
        con_linea = {c: max(necesita[c], en_linea.get(c, 0)) for c in otras}
        if espacio_pt - sum(con_linea.values()) >= natural:
            por_nombres = any(con_linea[c] > necesita[c] for c in otras)
            necesita = con_linea
    # Cuadros de textos (sin cifras en los datos) de las publicaciones con «cuadros_de_texto» (Documentos
    # Ocasionales, publicados DO 02-09): la primera columna a su medida (hasta un tercio), las columnas cortas a la
    # medida de su texto en una línea y las de descripciones, el resto a partes iguales; si todo cabe en una línea,
    # lo que sobra, a partes iguales entre las de datos
    pub = pub or {}
    textos_cuadro = bool(otras) and pub.get("cuadros_de_texto") and not por_nombres and not any(
        es_cifra(d(c, f)) for f in range(fin_cab + 1, f2 + 1) for c in otras if (c, f) not in tapadas and d(c, f)["texto"].strip())
    # Columnas de formas (Economía Latinoamericana 04: la escala DOVISH-NEUTRAL-HAWKISH, sin textos en el cuerpo y con
    # puntos y flechas dibujados encima): las de texto, a su medida en una línea; la primera, no más estrecha que
    # ellas; la escala, el resto a partes iguales (publicado: 78 / 101 ×3 / 85 pt)
    columnas_forma = [c for c in otras if not any(d(c, f)["texto"].strip() for f in range(fin_cab + 1, f2 + 1))
                      and any((c, f) in celdas_forma for f in range(fin_cab + 1, f2 + 1))]
    if columnas_forma and len(columnas_forma) < len(otras):
        de_texto = [c for c in otras if c not in columnas_forma]
        linea_t = {c: max([max(medir_de(c, f)(l.strip(), CUERPO_CELDA) for l in vista(c, f).split("\n")) + 2 * RELLENO_CELDA_PT
                           for f in range(fin_cab + 1, f2 + 1) if (c, f) not in tapadas and d(c, f)["texto"].strip()]
                          + [necesita[c]]) for c in de_texto}
        primera_f = max(natural, max(linea_t.values()))
        queda = espacio_pt - primera_f - sum(linea_t.values())
        if queda / len(columnas_forma) >= max(necesita[c] for c in columnas_forma):
            textos_cuadro = False
            a_medida = True
            # Las de formas, redondeadas hacia abajo (al subir a múltiplos de 3 quitaban sitio a la primera)
            de_forma = MULTIPLO_PT * math.floor((queda - sum(MULTIPLO_PT * math.ceil(v / MULTIPLO_PT) - v for v in linea_t.values())
                                                 - (MULTIPLO_PT * math.ceil(primera_f / MULTIPLO_PT) - primera_f)) / len(columnas_forma) / MULTIPLO_PT)
            medida = {**{c: MULTIPLO_PT * math.ceil(v / MULTIPLO_PT) for c, v in linea_t.items()}, **{c: de_forma for c in columnas_forma}}
            necesita = {c: max(necesita[c], medida[c]) if c in linea_t else necesita[c] for c in otras}
            primera_pt = primera_f
            resto = max(medida.values())
            detalle.append("Columnas con puntos o flechas dibujados (" + ", ".join(ref(c, 1)[:-1] for c in columnas_forma)
                           + f"): el resto del ancho, {de_forma:.0f} pt cada una; las de texto, a su medida "
                           f"en una línea, y la primera, no más estrecha que ellas ({primera_f:.0f} pt)")
    else:
        columnas_forma = []
    if columnas_forma:
        pass
    elif textos_cuadro:
        linea = dict(necesita)
        for f in range(fin_cab + 1, f2 + 1):
            for c in otras:
                if (c, f) in tapadas or not d(c, f)["texto"].strip():
                    continue
                tramo_cols = [k for k in otras if k == c or ((k, f) in tapadas and k > c and all((j, f) in tapadas for j in range(c + 1, k + 1)))]
                w = max(medir_de(c, f)(l.strip(), CUERPO_CELDA) for l in vista(c, f).split("\n"))
                linea[c] = max(linea[c], w / len(tramo_cols) + 2 * RELLENO_CELDA_PT)
        hace_falta = max(necesita.values())
        # Primera columna: como mínimo un octavo del cuadro (los publicados DO no bajan de 57 pt: «Modo», «M1»)
        primera_pt = max(minimo, min(max(natural, espacio_pt / 8), espacio_pt / 3))
        if sum(linea.values()) <= espacio_pt - primera_pt:
            primera_pt = max(primera_pt, min(natural, espacio_pt - sum(linea.values())))
            # Lo que sobra, a las columnas de datos (DO 05: «Color» 87 pt y la otra, 420). Si hay columnas de
            # descripciones (a la izquierda) y columnas cortas, las de descripciones se quedan con lo justo y las cortas
            # suben a un mismo ancho (DO 09: «Modo del billete» y «Modo del cerebro», 109 y 109; «Descripción», 231)
            sobra = espacio_pt - primera_pt - sum(linea.values())

            def media_textos(c):
                ts = [d(c, f)["texto"] for f in range(fin_cab + 1, f2 + 1) if (c, f) not in tapadas and d(c, f)["texto"].strip()]
                return sum(map(len, ts)) / len(ts) if ts else 0
            largas_t = {c for c in otras if media_textos(c) > pub.get("texto_izquierda", LARGO_TEXTO_IZQUIERDA)}
            cortas_t = [c for c in otras if c not in largas_t]
            if largas_t and cortas_t:
                # Nivel común de las cortas: el que gasta justo lo que sobra
                bajo_n, alto_n = 0.0, max(linea[c] for c in cortas_t) + sobra
                for _ in range(40):
                    nivel = (bajo_n + alto_n) / 2
                    if sum(max(0, nivel - linea[c]) for c in cortas_t) > sobra:
                        alto_n = nivel
                    else:
                        bajo_n = nivel
                medida = {c: (max(linea[c], bajo_n) if c in cortas_t else linea[c]) for c in otras}
            else:
                medida = {c: linea[c] + sobra / len(otras) for c in otras}
        else:
            medida, pendientes, queda = {}, sorted(otras, key=lambda c: linea[c]), espacio_pt - primera_pt
            while pendientes:
                parte = queda / len(pendientes)
                if linea[pendientes[0]] <= parte:
                    c = pendientes.pop(0)
                    medida[c] = linea[c]
                    queda -= linea[c]
                else:
                    medida.update({c: max(parte, necesita[c]) for c in pendientes})
                    break
        a_medida = True
        resto = min(medida.values())
        # Al redondear a múltiplos de 3 pt, que ninguna baje de lo que le hace falta a su texto en una línea (si lo tenía)
        necesita = {c: max(necesita[c], min(linea[c], medida[c])) for c in otras}
        detalle.append("Cuadro de textos: primera columna a su medida, las columnas cortas a la medida de su texto y las "
                       "de descripciones, el resto (como los publicados de " + pub.get("nombre", "la publicación") + ")")
    elif otras and pub.get("datos_cada_uno_a_lo_justo") and not textos_cuadro \
            and sum(max(ancho_justo([c]), necesita[c]) for c in otras) + minimo <= espacio_pt:
        # Cada columna de datos a lo justo (LATAM/Indicadores Macrofinancieros, Illustrator de Arg_03 y CARD_02: «Área
        # del euro» ~41 pt y «España» ~32 en una línea) y la primera columna, el resto
        a_medida = True
        medida = {c: max(ancho_justo([c]), necesita[c]) for c in otras}
        # Columnas que solo llevan valores del bloque de arriba (Arg_01: D, «14.643,7»): a lo justo, aparte
        solo_bloque = [c for c in otras if not any(d(c, f)["texto"].strip() for f in range(f1, f2 + 1))]
        # …y las de solo color (mapa de calor, Arg_02: «2026» y «Último dato (b)», con las cifras escondidas): a lo
        # justo de su cabecera; lo que sobra, a la primera columna
        solo_bloque += [c for c in otras if c not in solo_bloque and all(
            (c, f) in no_se_ven for f in range(fin_cab + 1, f2 + 1) if d(c, f)["texto"].strip())
            and any(d(c, f)["texto"].strip() for f in range(fin_cab + 1, f2 + 1))]
        reparten = [c for c in otras if c not in solo_bloque]
        if natural + sum(medida.values()) <= espacio_pt and reparten:
            # La primera columna cabe en una línea (01: «Deuda local en manos de no residentes (% del total)»): a su
            # medida, y las de datos se reparten el resto a partes iguales (sin bajar de lo justo)
            primera_pt = natural
            arriba3 = lambda v: MULTIPLO_PT * math.ceil(v / MULTIPLO_PT - 1e-6)
            libre = espacio_pt - arriba3(natural) - sum(arriba3(medida[c]) for c in solo_bloque)
            fijas_r = []
            while True:
                parte = (libre - sum(arriba3(medida[c]) for c in fijas_r)) / max(1, len(reparten) - len(fijas_r))
                nuevas = [c for c in reparten if c not in fijas_r and medida[c] > parte]
                if not nuevas:
                    break
                fijas_r += nuevas
            # hacia abajo en múltiplos de 3 (al subir quitaban sitio a la primera y partían sus textos), y las
            # fijas hacia arriba
            for c in reparten:
                medida[c] = MULTIPLO_PT * math.ceil(medida[c] / MULTIPLO_PT - 1e-6) if c in fijas_r \
                    else max(MULTIPLO_PT * math.floor(parte / MULTIPLO_PT + 1e-6), MULTIPLO_PT)
            for c in solo_bloque:
                medida[c] = MULTIPLO_PT * math.ceil(medida[c] / MULTIPLO_PT - 1e-6)
            detalle.append(f"Primera columna a su medida ({natural:.0f} pt) y las de datos, el resto a partes iguales "
                           f"({parte:.0f} pt)" + (", salvo las del bloque de arriba, a lo justo" if solo_bloque else ""))
        else:
            primera_pt = espacio_pt - sum(medida.values())
            detalle.append("Cada columna de datos a lo justo (su cabecera en una línea o su cifra más ancha) y la primera, el "
                       f"resto ({primera_pt:.0f} pt), como los publicados de " + pub.get("nombre", "la publicación"))
        necesita = dict(medida)
        resto = max(medida.values())
    elif otras and pub.get("datos_a_lo_justo") and ancho_justo(otras) * len(otras) + minimo <= espacio_pt:
        # Columnas de datos a lo justo (Documentos Ocasionales, decisión del usuario, 2026-11-19, publicados DO26XX_03
        # y 04): todas iguales, del ancho de la cabecera más larga en una línea (o de la cifra más ancha) y la primera,
        # el resto
        # Como mínimo DATO_JUSTO_MINIMO (DO26XX_02: con la cabecera de símbolos, solo las cifras darían 31 pt; el
        # publicado, 75) y sin que la primera columna parta sus textos (publicado DO26XX_01: la cabecera en dos líneas)
        hace_falta = max(ancho_justo(otras), DATO_JUSTO_MINIMO)
        resto = hace_falta
        motivo_justo = "la cabecera más larga en una línea"
        if espacio_pt - len(otras) * resto < natural:
            resto = max(max(necesita.values()), (espacio_pt - natural) / len(otras))
            motivo_justo = "lo que deja la primera columna con sus textos en una línea"
        primera_pt = espacio_pt - len(otras) * resto
        necesita = {c: max(necesita[c], resto) for c in otras}   # al redondear a 3 pt, que no bajen de aquí
        detalle.append(f"Columnas de datos a lo justo ({resto:.0f} pt: {motivo_justo}) y la primera, el resto (como los "
                       "publicados de " + pub.get("nombre", "la publicación") + ")")
    elif otras:
        hace_falta = max(necesita.values())
        primera_pt = max(minimo, min(natural, espacio_pt - len(otras) * hace_falta))
        # Como mínimo un tercio del cuadro para la primera columna en cuadros de cifras o de pocas columnas (los
        # publicados 1.3, 1.4, 1.5, 2.7 y 2.9 le dan el 31-34 %), si las demás siguen cabiendo (decisión del usuario)
        de_cifras = all(es_cifra(d(c, f)) for f in range(fin_cab + 1, f2 + 1) for c in otras
                        if (c, f) not in tapadas and d(c, f)["texto"].strip())
        tercio = espacio_pt / 3
        if primera_pt < tercio and (de_cifras or len(otras) <= 3) and (espacio_pt - tercio) / len(otras) >= hace_falta:
            detalle.append(f"Primera columna a un tercio del cuadro ({tercio / MM:.1f} mm), como los publicados".replace(".", ","))
            primera_pt = tercio
        # Primera columna de textos cortos, al menos como las de datos (LATAM/Economía Latinoamericana 01: fechas
        # «mar-26» de 36 pt; decisión del usuario, 2026-11-20): todas iguales y lo que sobra al redondear, a la primera
        igual = espacio_pt / (len(otras) + 1)
        if pub.get("primera_como_datos") and primera_pt < igual and igual >= hace_falta:
            detalle.append(f"Primera columna de textos cortos, como las de datos ({igual:.0f} pt; las de " + pub.get("nombre", "la publicación")
                           + " no quedan más estrechas que los datos)")
            primera_pt = igual
        resto = (espacio_pt - primera_pt) / len(otras)
        if resto < hace_falta - 0.1:
            # Con columnas iguales no cabe: cada columna de datos a su medida (su palabra o cifra más larga) y la
            # primera, el resto, como el publicado del Memoria 4.2 (decisión del usuario, 2026-11-18). Si aun así no
            # cabe, se avisa para bajar la letra
            suma = sum(necesita.values())
            if espacio_pt - suma >= minimo:
                a_medida = True
                primera_pt = max(minimo, min(natural, espacio_pt - suma))
                # Con nombres en una línea, lo que sobra va a las demás columnas de datos (publicado del 6.1)
                reciben = [c for c in otras if not (por_nombres and c in nombres)] or otras
                sobra = (espacio_pt - primera_pt - suma) / len(reciben)
                medida = {c: necesita[c] + (sobra if c in reciben else 0) for c in otras}
                if por_nombres:
                    # El sobrante, para bajar líneas de cabecera: cada vez, a la que ocupa más líneas, la que cuesta
                    # menos quitarle una; lo que quede, a partes iguales. Así el publicado del 6.1: «Designación (b)»
                    # en una línea y estrecha, «Colchón de capital…» en dos y anchas
                    def cab_lineas(c, w):
                        return max([len(partir(d(c, f)["texto"], w - 2 * RELLENO_CELDA_PT, medir_de(c, f)))
                                    for f in range(f1, fin_cab + 1) if (c, f) not in tapadas and d(c, f)["texto"].strip()] or [1])

                    def ancho_para(c, n, w):
                        while cab_lineas(c, w) > n and w < espacio_pt:
                            w += 1
                        return w
                    medida = {c: necesita[c] for c in otras}
                    queda = espacio_pt - primera_pt - suma
                    while True:
                        lin = {c: cab_lineas(c, medida[c]) for c in reciben}
                        opciones = [(lin[c], -(ancho_para(c, lin[c] - 1, medida[c]) - medida[c]), c) for c in reciben if lin[c] > 1]
                        opciones = [o for o in opciones if -o[1] <= queda]
                        if not opciones:
                            break
                        _, coste, c = max(opciones)
                        medida[c] -= coste
                        queda += coste
                    for c in reciben:
                        medida[c] += queda / len(reciben)
                resto = min(medida.values())
                if por_nombres:
                    detalle.append("Columna" + ("s" if len(nombres) > 1 else "") + " de nombres ("
                                   + ", ".join(ref(c, 1)[:-1] for c in sorted(nombres)) + ") en una línea: cada columna de "
                                   "datos a su medida y la primera, el resto, como el publicado del Memoria 6.1")
                else:
                    detalle.append(f"Con columnas de datos iguales el cuadro no cabe a {CUERPO_CELDA:g} pt (necesitan {hace_falta:.0f} pt "
                                   "cada una)".replace(".", ",", 1) + ": cada una a su medida (su palabra o cifra más larga) y "
                                   "la primera, el resto, como el publicado del Memoria 4.2")
            else:
                detalle.append(f"Aviso: el cuadro no cabe en la retícula a {CUERPO_CELDA:g} pt ni con las columnas a su medida: "
                               f"necesitan {suma:.0f} pt y solo hay {espacio_pt - minimo:.0f}; baja la letra con «Probar letra» "
                               "(7 o 6,5 pt; la guía permite hasta 6 pt)".replace(".", ",", 1))
    else:
        primera_pt, resto = espacio_pt, 0
    if primera_pt < natural - 0.1:
        detalle.append("La primera columna cede ancho: algún texto suyo pasa a varias líneas")

    # Cabeceras compensadas (petición del usuario, 1.4; desactivado el 2026-11-17, ver COMPENSAR_CABECERA): si los textos de la cabecera de las demás columnas ocupan
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
    # Desactivada (2026-11-17): los publicados (1.3, 1.4) dejan las columnas de datos anchas y parten la cabecera a
    # mano por una frase; ahora se hace eso (salto de línea en la cabecera, más abajo)
    if COMPENSAR_CABECERA and otras and resto > 0 and any(f <= fin_cab and lineas_texto(t, k * resto, m) > 1 for c, f, t, k, m in celdas_otras):
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

    # Cabecera de datos muy alta (más de 3 líneas, 3.4): la primera columna cede ancho, hasta que sus textos ocupen 2
    # líneas como mucho; se queda el reparto con el cuadro más bajo (decisión del usuario, 2026-11-17)
    def lineas_primera(t, espacios, m, w):
        return len(partir(t, w - 2 * RELLENO_CELDA_PT - m(espacios, CUERPO_CELDA), m))
    if otras and resto > 0 and textos_primera and not a_medida:
        maximo_cab = max([lineas_texto(t, k * resto, m) for c, f, t, k, m in celdas_otras if f <= fin_cab] or [1])
        if maximo_cab > 3:
            def alto_cuadro(wp, wr):
                """(alto de la cabecera, alto del cuadro): primero se busca la cabecera más baja (lo que pidió el
                usuario y hace el TERMINADO del 3.4) y, a igualdad, el cuadro más bajo."""
                filas_l = {}
                for f, espacios, t, m in textos_primera:
                    filas_l[f] = max(filas_l.get(f, 1), lineas_primera(t, espacios, m, wp))
                for c, f, t, k, m in celdas_otras:
                    filas_l[f] = max(filas_l.get(f, 1), lineas_texto(t, k * wr, m))
                return (sum(alto_fila(n) for f, n in filas_l.items() if f <= fin_cab), sum(alto_fila(n) for n in filas_l.values()))
            # Lo más que puede ceder: que sus textos ocupen 2 líneas como mucho o, si ya ocupan 2 (porque la primera ya
            # cedió para que quepan las cifras, 3.4), una más (el TERMINADO del 3.4 llega a 3)
            tope = max(2, max(lineas_primera(t, e, m, primera_pt) for _, e, t, m in textos_primera) + 1)
            minimo_2 = minimo
            while minimo_2 < primera_pt and any(lineas_primera(t, e, m, minimo_2) > tope for _, e, t, m in textos_primera):
                minimo_2 += 1
            mejor = (alto_cuadro(primera_pt, resto), -primera_pt, primera_pt)
            wp = primera_pt - MULTIPLO_PT
            while wp >= minimo_2:
                wr = (espacio_pt - wp) / len(otras)
                mejor = min(mejor, (alto_cuadro(wp, wr), -wp, wp))
                wp -= MULTIPLO_PT
            if mejor[2] < primera_pt:
                antes = alto_cuadro(primera_pt, resto)[0]
                detalle.append(f"Cabecera de datos muy alta ({maximo_cab} líneas): la primera columna cede de {primera_pt / MM:.1f} "
                               f"a {mejor[2] / MM:.1f} mm (sus textos, en {tope} líneas como mucho) y la cabecera baja de "
                               f"{antes:g} a {mejor[0][0]:g} pt".replace(".", ",", 2))
                primera_pt = mejor[2]
                resto = (espacio_pt - primera_pt) / len(otras)

    # 1) Muchas columnas de datos: aviso para valorar bajar la letra a 7 pt (decisión del usuario, 2026-11-17)
    if otras and (len(otras) >= 10 or resto < 30 or (a_medida and not por_nombres and not textos_cuadro and not columnas_forma)):
        detalle.append(f"Aviso: el cuadro tiene {len(otras)} columnas de datos" + ("" if a_medida else f" de {resto:.0f} pt")
                       + ": valora bajar la letra con «Probar letra a 7 pt» o «Probar letra a 6,5 pt» (la guía permite de 6 a "
                       "7,5 pt según el tamaño del cuadro; el publicado del Memoria 4.2 va a 6,5 pt)")

    # Columnas de textos largos: si con anchos iguales sus filas salen mucho más altas, ganan ancho a costa de las que
    # tienen holgura (sin que estas pasen a tener más líneas que la más alta), hasta que ya no mejora
    largas = []
    # Las combinadas sobre varias columnas en una fila sin concepto en la primera columna (Economía Latinoamericana 01:
    # B8:G8 «Percentiles de distribución…», un subtítulo a lo ancho de los datos) no son textos de su primera columna.
    # Con concepto sí lo son (DO 06: B6:C6 «Percepción de un solo color…», a la izquierda en el publicado)
    sobre_varias = {(a1, b1) for a1, b1, a2, b2 in rangos if a2 > a1 and a1 > primera and not d(primera, b1)["texto"].strip()}
    for c in otras:
        textos = [d(c, f)["texto"] for f in range(fin_cab + 1, f2 + 1)
                  if (c, f) not in tapadas and (c, f) not in sobre_varias and d(c, f)["texto"].strip() and not es_cifra(d(c, f))]
        if textos and sum(len(t) for t in textos) / len(textos) > LARGO_TEXTO_IZQUIERDA:
            largas.append(c)
    anchos_pt = dict(medida) if a_medida else {c: resto for c in otras}
    if largas and len(otras) > 1 and not a_medida:
        def lineas_col(c, w):
            return max([len(partir(d(c, f)["texto"], w - 2 * RELLENO_CELDA_PT, medir_de(c, f))) for f in range(fin_cab + 1, f2 + 1)
                        if (c, f) not in tapadas and (c, f) not in sobre_varias and d(c, f)["texto"].strip()] or [1])
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
    if primera_final < primera_pt - 0.01:
        # Redondear hacia arriba las de datos quitaba sitio a la primera (1.3: su texto pasaba a 2 líneas): hacia
        # abajo, si su contenido sigue cabiendo
        abajo = {c: max(MULTIPLO_PT, MULTIPLO_PT * math.floor(anchos_pt[c] / MULTIPLO_PT + 1e-6)) for c in otras}
        if all(abajo[c] >= necesita[c] for c in otras):
            otros_pt = abajo
            primera_final = disponible - sum(otros_pt.values())
    # Cabeceras de datos que se parten por muy poco (DO 02: «Resolución temporal» necesita 76 pt y la columna es de
    # 75): esas columnas suben un múltiplo (todas, si eran iguales) y la primera cede ese ancho, si sus textos no
    # hacen el cuadro más alto (las combinadas en vertical caben en tantas líneas como filas; decisión del usuario)
    def cab_una_linea(c):
        return max([max(medir_de(c, f)(l.strip(), CUERPO_CELDA) for l in d(c, f)["texto"].split("\n")) + 2 * RELLENO_CELDA_PT
                    for f in range(f1, fin_cab + 1) if (c, f) not in tapadas and d(c, f)["texto"].strip()
                    and tramos.get((c, f), 1) == 1] or [0])
    por_poco = [c for c in otras if otros_pt[c] < cab_una_linea(c) <= otros_pt[c] + MULTIPLO_PT]
    if por_poco:
        suben = list(otras) if len(set(otros_pt.values())) == 1 else por_poco
        nueva_primera = primera_final - MULTIPLO_PT * len(suben)

        def lineas_filas(wp, wd):
            """Líneas de cada fila con la primera columna a wp y las de datos a wd (combinadas en vertical: no cuentan
            si caben en sus filas)."""
            filas_l = {}
            for f, espacios, t, m in textos_primera:
                n = len(partir(t, wp - 2 * RELLENO_CELDA_PT - m(espacios, CUERPO_CELDA), m))
                juntas = next((b2 - b1 + 1 for a1, b1, a2, b2 in rangos if a1 == a2 == primera and b1 == f and b2 > b1), 1)
                filas_l[f] = max(filas_l.get(f, 1), 1 if n <= juntas else n)
            for c, f, t, k, m in celdas_otras:
                filas_l[f] = max(filas_l.get(f, 1), max(len(partir(l, k * wd[c] - 2 * RELLENO_CELDA_PT, m)) for l in t.split("\n")))
            return sum(alto_fila(n) for n in filas_l.values())
        nuevos_otros = {c: otros_pt[c] + (MULTIPLO_PT if c in suben else 0) for c in otras}
        if nueva_primera >= minimo and lineas_filas(nueva_primera, nuevos_otros) <= lineas_filas(primera_final, otros_pt):
            for c in suben:
                otros_pt[c] += MULTIPLO_PT
            primera_final = nueva_primera
            detalle.append("Cabecera en una línea por " + str(MULTIPLO_PT) + " pt más: " + ", ".join(
                f"«{d(c, next(f for f in range(f1, fin_cab + 1) if d(c, f)['texto'].strip()))['texto'].strip()[:30]}»" for c in por_poco)
                + "; la primera columna cede ese ancho (el cuadro no crece)")
    if primera_final < MULTIPLO_PT:
        primera_final = MULTIPLO_PT * max(1, round(primera_pt / MULTIPLO_PT))
    nuevos_anchos = {primera: ancho_comun(primera_final, mdw, mdw_win)}
    for c in separaciones:
        nuevos_anchos[c] = w_sep
    for c in pegada:
        nuevos_anchos[c] = 0
    for c in otras:
        nuevos_anchos[c] = ancho_comun(otros_pt[c], mdw, mdw_win)
    nuevos_anchos.update(ensanchadas)
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
    nuevos_textos, lineas, cambios_txt, porcentajes, correcciones, saltos, sangrados, propuestas = {}, {}, [], [], [], [], [], []
    juntadas = []
    sangrar_ricos, ricos_sin_tocar, asteriscos, decimales = {}, [], [], []
    for f in range(f1, f2 + 1):
        for c in range(c1, c2 + 1):
            if (c, f) in tapadas or ancho_col(c) == 0:
                continue   # columnas ocultas (Memoria 2.1: textos de traducción en A-C): ni se miden ni se tocan
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
                # Asteriscos de significatividad pegados a la cifra: «0,237 ***» → «0,237***» (publicado 3.3)
                pegados = re.sub(r'(?<=[\d)])\s+(\*{1,3})(?=\s*$)', r'\1', t)
                if not x["numero"] and pegados != t and indice_rico(x, compartidos) is None:
                    nuevos_textos[(c, f)] = pegados
                    asteriscos.append(ref(c, f))
                # Decimales escritos como texto con punto y sin el cero: «(.0002)» → «(0,0002)» (publicado DO26XX_02);
                # solo los que no pueden ser millares (sin cifra delante, o con «0.» delante)
                if idioma == "es" and not x["numero"] and indice_rico(x, compartidos) is None:
                    con_coma = re.sub(r'(?<![\d.,])(0?)\.(\d+)', r'0,\2', nuevos_textos.get((c, f), t))
                    if con_coma != nuevos_textos.get((c, f), t):
                        nuevos_textos[(c, f)] = con_coma
                        decimales.append(ref(c, f))
                continue
            nuevo = t
            # «<34» → «< 34»: espacio tras los signos de comparación (TERMINADO 1.4); «7%» → «7 %» con espacio que no
            # parte línea, como en FUENTES (TERMINADO 1.2)
            con_espacio = re.sub(r'([<>≤≥])(?=[\w(])', r'\1 ', t)
            # …y también antes: «ROA< 0» → «ROA < 0» (publicado 3.2)
            con_espacio = re.sub(r'(?<=[\w)])([<>≤≥])', r' \1', con_espacio)
            if con_espacio != t:
                cambios_txt.append(f"«{t.strip()[:20]}» → «{con_espacio.strip()[:20]}»")
            con_por = re.sub(r'(\d)[ \u202f]?%', '\\1\u00a0%', con_espacio)
            corregido, tipos_c = corregir_texto(con_por, idioma, cabecera=f <= fin_cab, provincias=f > fin_cab)
            if tipos_c:
                correcciones.append(f"{ref(c, f)} «{con_por.strip()[:35]}» → «{corregido.strip()[:35]}» ({', '.join(tipos_c)})")
                con_por = corregido
            if con_por != con_espacio:
                porcentajes.append(ref(c, f))
            if con_por != t:
                nuevo = t = con_por
            if f <= fin_cab and re.fullmatch(r'\s*total\s*', t, re.I) and t.strip() != "Total":
                # En la cabecera (fondo del color de la publicación), «Total» en minúscula; «TOTAL» solo sobre fondo
                # gris, la fila TOTAL (decisión del usuario, 2026-11-17, publicado Memoria 3.1; antes iba en mayúscula)
                cambios_txt.append(f"«{t.strip()}» → «Total» (cabecera, sobre el color de la publicación)")
                nuevo = t = "Total"
            if c == primera and f > fin_cab:
                cuerpo = t.strip("  ")
                sin_vineta = VINETA.sub("", cuerpo)
                if sin_vineta != cuerpo:
                    cambios_txt.append(f"«{cuerpo[:30]}» sin viñeta")
                cuerpo = sin_vineta
                # Minúsculas de título en la primera columna: no se cambian (puede haber nombres de entidades), se
                # proponen en un aviso (decisión del usuario, 2026-11-17, publicado del 1.5)
                propuesta = minuscula_titulo(cuerpo, idioma)
                if propuesta != cuerpo:
                    propuestas.append((ref(c, f), cuerpo, propuesta))
                if re.fullmatch(r'total', cuerpo, re.I) and cuerpo != "TOTAL":
                    cambios_txt.append(f"«{cuerpo}» → «TOTAL»")
                    cuerpo = "TOTAL"
                espacios = " " * (SANGRIA * nivel_fila(f))
                mc = medir_de(c, f)
                partes = partir("\n".join(l.strip() for l in cuerpo.split("\n")), ancho - mc(espacios, CUERPO_CELDA), mc)
                if espacios and not x["texto"].startswith(espacios + cuerpo.split("\n")[0][:1]):
                    sangrados.append(ref(c, f))
                if espacios and len(partes) > 1:
                    # Con varias líneas, la sangría se repite en cada una (saltos de línea manuales)
                    nuevo = "\n".join(espacios + l for l in partes)
                else:
                    nuevo = espacios + cuerpo
                lineas[(c, f)] = len(partes)
            else:
                mc = medir_de(c, f)
                # (salvo en las publicaciones que los respetan: LATAM/Economía Latinoamericana 05, «Promedio⏎2007-2024»)
                if f <= fin_cab and pub.get("respetar_saltos_cabecera") and re.search(r"[ \t]*\r?\n[ \t]*", t.strip()) \
                        and indice_rico(x, compartidos) is None:
                    # Salto del autor respetado, sin los espacios de alrededor («Promedio⏎ 2007-2024»)
                    limpio = re.sub(r"[ \t]*\r?\n[ \t]*", "\n", t.strip())
                    if limpio != t:
                        nuevo = t = limpio
                if f <= fin_cab and "\n" in t.strip() and not re.search(r"\n\s*\(", t) and not pub.get("respetar_saltos_cabecera"):
                    # Salto de línea del autor en una cabecera que cabe en una línea: sobra (publicado 3.1,
                    # «Peso VAB⏎2023» → «Peso VAB 2023»); el de antes de un paréntesis se queda (publicado 1.5,
                    # «Deflactor del VAB⏎(crecimiento interanual promedio)»)
                    junta = re.sub(r"\s*\n\s*", " ", t.strip())
                    if len(partir(junta, ancho, mc)) == 1:
                        nuevo = t = junta
                        juntadas.append(f"{ref(c, f)} «{junta[:40]}»")
                # (con el mismo medio punto de tolerancia con que se ensanchan las columnas estrechas: «II S» a 7 pt)
                partes = partir(t, ancho + (0.5 if c in ensanchadas else 0), mc)
                if f <= fin_cab and len(partes) == 2 and "\n" not in t.strip():
                    # Cabecera de 2 líneas: el salto, puesto a mano por una frase (como los publicados)
                    dos = salto_cabecera(t.strip(), ancho, mc)
                    if dos and dos != t.strip():
                        nuevo = t = dos
                        saltos.append(f"«{dos.replace(chr(10), ' / ')[:60]}»")
                lineas[(c, f)] = len(partes)
            if c == primera and f in desbordan:
                lineas[(c, f)] = 1   # desborda por encima de las celdas vacías de su fila: una línea
            if nuevo != x["texto"]:
                rico = indice_rico(x, compartidos)
                if rico is None:
                    nuevos_textos[(c, f)] = nuevo
                elif nuevo.strip() == x["texto"].strip():
                    pass   # solo espacios a los lados: el texto con formato (R², publicado 3.3) se queda como está
                elif nuevo.rstrip().lstrip(" ") == x["texto"].strip():
                    sangrar_ricos[(c, f)] = (rico, nuevo[:len(nuevo) - len(nuevo.lstrip(" "))])
                else:
                    ricos_sin_tocar.append(f"{ref(c, f)} «{x['texto'].strip()[:25]}» → «{nuevo.strip()[:25]}»")
    if asteriscos:
        cambios_txt.append(f"asteriscos de significatividad pegados a la cifra («0,237 ***» → «0,237***», {len(asteriscos)} celda{'s' if len(asteriscos) > 1 else ''})")
    if ricos_sin_tocar:
        detalle.append("Aviso: celdas con formato en el texto (superíndices, cursivas…) sin corregir para no perderlo; "
                       "corrígelas a mano: " + "; ".join(ricos_sin_tocar[:6]) + marca([r.split(" ", 1)[0] for r in ricos_sin_tocar]))
    if juntadas:
        detalle.append("Cabecera: salto de línea del autor quitado, el texto cabe en una línea: " + "; ".join(juntadas[:6])
                       + marca([j.split(" ", 1)[0] for j in juntadas]))
    if saltos:
        detalle.append("Cabecera en 2 líneas, con el salto por una frase (como los publicados): " + "; ".join(saltos[:6]))
    if sangrados:
        de_bloque = [ref(primera, f) for f in sin_sangria]
        detalle.append(f"Aviso (corrección ortotipográfica): sangría con espacios ({', '.join(f'{SANGRIA * n} espacios' for n in sorted(set(nivel_de.values())) or [1])} "
                       f"según el nivel) en {len(sangrados)} celda{'s' if len(sangrados) > 1 else ''}: " + ", ".join(sangrados[:10])
                       + ("…" if len(sangrados) > 10 else "")
                       + (f"; de ellas, sangradas por ser de un bloque (el autor no las sangró): {', '.join(de_bloque[:8])}" if de_bloque else "")
                       + marca(sangrados))
    if propuestas:
        detalle.append("Aviso (propuesta, sin aplicar): en la primera columna, ¿minúscula en las palabras con mayúscula de "
                       "título? " + "; ".join(f"{r} «{a[:35]}» → «{b[:35]}»" for r, a, b in propuestas[:8])
                       + (f" y {len(propuestas) - 8} más" if len(propuestas) > 8 else "")
                       # Con botón «Aplicar» en la app (petición del usuario, 2026-11-17, Memoria 3.2)
                       + (f" ⟦aplicar:{len(propuestas_salida)}⟧" if propuestas_salida is not None else "")
                       + marca([r for r, _, _ in propuestas]))
        if propuestas_salida is not None:
            propuestas_salida.append({"tipo": "celdas", "hoja": hoja, "cambios": [list(p) for p in propuestas],
                                      "que": "minúsculas en la primera columna"})
    if correcciones:
        detalle.append("Aviso (corrección ortotipográfica), revísalas: " + "; ".join(correcciones[:10])
                       + (f" y {len(correcciones) - 10} más" if len(correcciones) > 10 else "")
                       + marca([l.split(" ", 1)[0] for l in correcciones]))
    if decimales:
        detalle.append(f"Decimales escritos como texto, con coma y el cero delante: «(.0002)» → «(0,0002)» ({len(decimales)} "
                       f"celda{'s' if len(decimales) > 1 else ''}, como el publicado del DO26XX_02)" + marca(decimales))
    if porcentajes:
        cambios_txt.append(f"espacio que no parte línea antes de «%» ({len(porcentajes)} celda{'s' if len(porcentajes) > 1 else ''})")
    if cambios_txt:
        detalle.append("Textos: " + "; ".join(cambios_txt[:8]))
    if nivel_de:
        detalle.append("Sangrías con espacios: " + ", ".join(f"nivel {n} = {SANGRIA * n} espacios" for n in sorted(set(nivel_de.values()))))

    # Alineación de las columnas de datos con texto: a la izquierda las de textos largos
    izquierda = set()
    for c in range(primera + 1, c2 + 1):
        textos = [d(c, f)["texto"] for f in range(fin_cab + 1, f2 + 1)
                  if (c, f) not in tapadas and (c, f) not in sobre_varias and d(c, f)["texto"].strip() and not es_cifra(d(c, f))]
        if textos and sum(len(t) for t in textos) / len(textos) > pub.get("texto_izquierda", LARGO_TEXTO_IZQUIERDA):
            izquierda.add(c)
    if izquierda:
        detalle.append("Columnas de textos largos, a la izquierda: " + ", ".join(ref(c, 1)[:-1] for c in sorted(izquierda)))
    if nombres - izquierda:
        detalle.append("Columna" + ("s" if len(nombres - izquierda) > 1 else "") + " de nombres, a la izquierda (como el "
                       "publicado del Memoria 6.1; la cabecera, al centro): " + ", ".join(ref(c, 1)[:-1] for c in sorted(nombres - izquierda)))
        izquierda |= nombres

    # Altos de fila y alineación en altura
    altos, arriba, filas_dos = {}, set(), []
    for f in range(f1, f2 + 1):
        n = max([lineas.get((c, f), 0) for c in range(c1, c2 + 1) if filas_comb.get((c, f), 1) == 1] or [0])
        if n == 0 and not any(d(c, f)["texto"].strip() for c in range(c1, c2 + 1)):
            continue   # fila vacía (separación del autor): se queda como está
        altos[f] = alto_fila(max(n, 1))
        # Filas de dos líneas a 6,5 pt (LATAM/Indicadores Macrofinancieros, Arg_03: 24 pt, como el original y el
        # publicado; petición del usuario, 2026-11-21, en principio solo para esta publicación)
        if pub.get("alto_dos_lineas_65") and max(n, 1) == 2 and abs(CUERPO_CELDA - 6.5) < 0.01:
            filas_dos.append(f)
        if f > fin_cab and not pub.get("centrado_en_altura") and any(lineas.get((c, f), 0) > 1 for c in range(primera + 1, c2 + 1)):
            arriba.add(f)
    estilos_bloque = {}
    if bloque:
        for f in bloque["filas"]:
            altos[f] = alto_fila(1)
        # hueco entre el bloque y la tabla: 4 mm en las filas vacías visibles de en medio
        entre = [f for f in range(bloque["filas"][-1] + 1, f1) if f not in filas_ocultas]
        for f in entre:
            altos[f] = round(CABECERA_BAJO_PASTILLA / len(entre) * 4) / 4
        color_b = pub.get("color", "A32938").upper()
        linea_b = ("thin", matiz(color_b, TINTES["matiz1"])) if pub.get("solo_lineas") else LINEA_FILAS
        cabeza_linea = ("thin", color_b) if pub.get("solo_lineas") else LINEA_OSCURA
        cuerpo_filas = [f for f in bloque["filas"] if f != bloque["cabecera"]]
        for e, v in bloque["grupos"]:
            for f in bloque["filas"]:
                for c in range(e, v + 1):
                    if ancho_col(c) == 0:
                        continue
                    x = d(c, f)
                    # años y valores centrados, como en el original y en la tabla (petición del usuario, 2026-11-21)
                    al = {"horizontal": "left" if c == e else "center", "vertical": "center"}
                    s_ = estilos.nuevo(x["s"], al, cuerpo=CUERPO_CELDA)
                    lados = {}
                    if f == bloque["cabecera"]:
                        lados["bottom"] = cabeza_linea
                    elif f != cuerpo_filas[-1]:
                        lados["bottom"] = linea_b
                    estilos_bloque[(c, f)] = estilos.variante(s_, relleno="", borde=lados, letra="000000")
        # Lo que queda entre las tablitas (y a sus lados), sin líneas ni fondo del autor (Br_01: la línea gris en G)
        en_tablitas = {c for e, v in bloque["grupos"] for c in range(e, v + 1)}
        for f in bloque["filas"]:
            for c in range(c1, c2 + 1):
                if c not in en_tablitas and (c, f) in todas and ancho_col(c) > 0:
                    estilos_bloque[(c, f)] = estilos.variante(d(c, f)["s"], relleno="", borde={})
        detalle.append("Bloque de arriba (filas " + f"{bloque['filas'][0]}-{bloque['filas'][-1]}" + "): parte del cuadro, "
                       + str(len(bloque["grupos"])) + " tablita" + ("s" if len(bloque["grupos"]) > 1 else "") + " ("
                       + ", ".join(f"{ref(e, 1)[:-1]}-{ref(v, 1)[:-1]}" for e, v in bloque["grupos"])
                       + f"), conceptos a la izquierda y años y valores centrados, letra de {CUERPO_CELDA:g} pt".replace(".", ",")
                       + "; línea bajo el año y entre filas, cada tablita en su ancho; a 4 mm de la tabla")
        if bloque["movidas"]:
            detalle.append("Bloque de arriba: la segunda tablita empezaba en la primera columna de datos y quedaba pegada a la "
                           "otra; sus conceptos, una columna de datos a la derecha, como en el PDF publicado ("
                           + ", ".join(bloque["movidas"]) + ")")
    # Filas con puntos o flechas dibujados (Economía Latinoamericana 04): 21 pt, como el publicado, con aire para ellos
    con_puntos = [f for f in altos if f > fin_cab and any((c, f) in celdas_forma for c in columnas_forma)]
    for f in con_puntos:
        altos[f] = max(altos[f], ALTO_FILA_PUNTOS)
    if con_puntos:
        detalle.append(f"Filas con puntos o flechas dibujados, de {ALTO_FILA_PUNTOS} pt como mínimo (como el publicado): "
                       + ", ".join(map(str, con_puntos)))
    # Cuadros que no caben en la altura de la retícula (Economía Latinoamericana 05: 57 filas de 14 pt son unos 800 pt
    # y la retícula mide 702; el publicado va a 9 pt): las filas bajan en proporción, sin bajar de 1,5 veces la letra
    pl_ = plantilla()
    alto_util = tamano(pl_["grupo"], escala_grupo=True)[1] / EMU_PT - tamano(pl_["pastilla_modelo"])[1] / EMU_PT \
        - CABECERA_BAJO_PASTILLA - FUENTES_BAJO_CUADRO
    for anc in ANCLA.finditer(dibujo):
        lineas_f = html.unescape(texto_forma(anc.group(0))).strip().split("\n")
        if ROTULO.match(lineas_f[0]):
            # Por su texto, no por su marco (el de la plantilla mide 30 mm aunque lleve una línea): líneas de 7 pt con
            # interlineado de 8,5, unas 150 letras por línea en el ancho de la retícula
            alto_util -= sum(max(1, math.ceil(len(l) / 150)) for l in lineas_f) * 8.5 + 4
            break
    total_altos = sum(altos.values())
    if filas_dos and not total_altos > alto_util > 0:
        # (solo si el cuadro cabe en altura: si no, se comprimen todas por igual, como hasta ahora)
        for f in filas_dos:
            altos[f] = float(pub["alto_dos_lineas_65"])
        total_altos = sum(altos.values())
    if total_altos > alto_util > 0:
        unidad = max(1.5 * CUERPO_CELDA, math.floor(ALTOS_FILA[1] * alto_util / total_altos * 4) / 4)
        altos = {f: round(h * unidad / ALTOS_FILA[1] * 4) / 4 for f, h in altos.items()}
        detalle.append(f"El cuadro no cabe en la altura de la retícula ({total_altos:g} pt de filas y caben {alto_util:.0f}): "
                       f"filas de {unidad:g} pt por línea en vez de {ALTOS_FILA[1]}".replace(".", ",")
                       + ("" if unidad > 1.5 * CUERPO_CELDA else " (el mínimo, 1,5 veces la letra" + (": valora bajar la letra)" if CUERPO_CELDA > 6 else ")")))
    cuenta = Counter(altos.values())
    detalle.append("Alto de fila: " + ", ".join(f"{h:g} pt ({n} fila{'s' if n > 1 else ''})" for h, n in sorted(cuenta.items())))
    if arriba:
        detalle.append(f"Alineadas arriba (textos de 2 o más líneas en los datos): fila{'s' if len(arriba) > 1 else ''} "
                       + ", ".join(str(f) for f in sorted(arriba)))

    # Unidades escritas en la esquina de la cabecera (Memoria 4.1: «Datos a 31 de diciembre» en A5:A9): como unas
    # unidades, Roboto Light 6 pt arriba a la izquierda y sin relleno (publicado; petición del usuario, 2026-11-18)
    esquina_unidades = {(c, f) for f in range(f1, fin_cab + 1) for c in [primera]
                        if RE_UNIDADES.match(d(c, f)["texto"] or "") and (c, f) not in tapadas}
    esquina_unidades |= {(a, b) for a1, b1, a2, b2 in rangos if (a1, b1) in esquina_unidades
                         for a in range(a1, a2 + 1) for b in range(b1, b2 + 1)}
    if esquina_unidades:
        k = min(esquina_unidades, key=lambda k: (k[1], k[0]))
        detalle.append(f"Unidades en la esquina de la cabecera ({ref(*k)} «{d(*k)['texto'].strip()[:40]}»): Roboto Light "
                       f"{UNIDADES_PT:g} pt, arriba a la izquierda y sin relleno" + marca([ref(*k)]))

    a_todo_ancho = {(a, b) for a1, b1, a2, b2 in rangos if a1 == primera and a2 >= c2 and b1 <= fin_cab
                    for a in range(a1, a2 + 1) for b in range(b1, b2 + 1)}
    if any(d(*k)["texto"].strip() for k in a_todo_ancho):
        k = min(a_todo_ancho, key=lambda k: (k[1], k[0]))
        detalle.append(f"Cabecera combinada a todo el ancho del cuadro, al centro: «{d(*k)['texto'].strip()[:40]}»" + marca([ref(*k)]))
    # Formatos nuevos de cada celda del cuadro
    nuevos_s = {}
    for f in range(f1, f2 + 1):
        for c in range(c1, c2 + 1):
            x = d(c, f)
            if x["xml"] is None and (c, f) not in tapadas:
                continue
            if ancho_col(c) == 0 and c not in pegada:
                continue   # columna oculta del autor: su formato se queda
            if f <= fin_cab:
                # La primera, a la izquierda, salvo si va combinada a todo el ancho del cuadro (DO 06: «Alteraciones
                # del color» en A5:C5, centrada en el publicado)
                h = "left" if c == primera and (c, f) not in a_todo_ancho else "center"
            elif c == primera:
                h = "left"
            elif es_cifra(x) or not x["texto"].strip():
                h = "center"
            else:
                # Un subtítulo combinado a lo ancho de los datos, al centro (Economía Latinoamericana 01, B8:G8)
                h = "left" if c in izquierda and (c, f) not in sobre_varias else "center"
            al = {"horizontal": h, "vertical": "top" if f in arriba else "center"}
            # (en las columnas estrechas ensanchadas lo justo, sin ajustar texto: si no, Excel partía «II S» por una
            # décima, Arg_02)
            if (not es_cifra(x) or f <= fin_cab) and not (c == primera and f in desbordan) and c not in ensanchadas:
                al["wrapText"] = "1"
            if (c, f) in esquina_unidades:
                nuevos_s[(c, f)] = estilos.nuevo(x["s"], {"horizontal": "left", "vertical": "top", "wrapText": "1"},
                                                 cuerpo=UNIDADES_PT)
                continue
            nuevos_s[(c, f)] = estilos.nuevo(x["s"], al, negrita=f in filas_suma or (c == primera and f in madres))
    negritas = [ref(c, f) for (c, f) in nuevos_s if es_negrita(estilos.fuente_de(d(c, f)["s"])) and d(c, f)["texto"].strip()]
    sumas_txt = [f for f in sorted(filas_suma) if not RE_TOTAL.match(d(primera, f)["texto"])]
    if filas_total:
        detalle.append("Fila TOTAL entera (también las cifras) en " + LETRA_CELDA_NEGRITA + ": fila "
                       + ", ".join(map(str, sorted(filas_total))) + marca([ref(primera, f) for f in sorted(filas_total)]))
    madres_txt = [f for f in sorted(madres) if f not in filas_suma]
    if madres_txt:
        detalle.append("Conceptos de nivel intermedio (sangrados, con otros más sangrados debajo): su texto en " + LETRA_CELDA_NEGRITA + ": "
                       + ", ".join(f"«{d(primera, f)['texto'].strip()[:30]}» (fila {f})" for f in madres_txt)
                       + marca([ref(primera, f) for f in madres_txt]))
    if sumas_txt:
        detalle.append("Filas que suman las de debajo, en " + LETRA_CELDA_NEGRITA + " como un subtotal: "
                       + ", ".join(f"«{d(primera, f)['texto'].strip()[:30]}» (fila {f})" for f in sumas_txt)
                       + marca([ref(primera, f) for f in sumas_txt]))
    detalle.append(f"Letra de las celdas: {LETRA_CELDA} {CUERPO_CELDA:g} pt".replace(".", ",")
                   + (f"; lo que iba en negrita, en {LETRA_CELDA_NEGRITA} ({len(negritas)} celda{'s' if len(negritas) > 1 else ''}: "
                      + ", ".join(negritas[:8]) + ("…" if len(negritas) > 8 else "") + ")" if negritas else ""))
    detalle.append("Alineación: cabecera, la primera a la izquierda y las demás al centro; primera columna a la "
                   "izquierda; cifras al centro; " + ("centrado en altura, también las filas de varias líneas (como los "
                   "publicados de " + pub.get("nombre", "") + ")" if pub.get("centrado_en_altura") else "centrado en altura salvo las filas de arriba"))

    # Textos enriquecidos (con varios formatos) de las celdas del cuadro: también en Roboto Light 7,5, sin negrita
    usados = {int(re.search(r'<v>(\d+)</v>', d(c, f)["xml"]).group(1))
              for (c, f) in nuevos_s if d(c, f)["tipo"] == "s" and d(c, f)["xml"] and "<v>" in d(c, f)["xml"]}
    nuevas_si = list(compartidos)
    for i in usados:
        if "<r>" in nuevas_si[i]:
            def rpr(m):
                letra = LETRA_CELDA_NEGRITA if es_negrita(m.group(1)) else LETRA_CELDA
                # Sin color propio: el trozo toma el de la celda (negro; en la cabecera, el del paso 3)
                dentro = re.sub(r'<(rFont|sz|b|family|scheme|color)\b[^>]*/>', "", m.group(1))
                return f'<rPr><rFont val="{letra}"/>{dentro}<sz val="{CUERPO_CELDA:g}"/><family val="2"/></rPr>'
            nuevas_si[i] = re.sub(r'<rPr>(.*?)</rPr>', rpr, nuevas_si[i], flags=re.S)
    # Sangría en celdas con texto con formato: los espacios van al principio del primer trozo (cadena nueva)
    for (c, f), (i, espacios) in list(sangrar_ricos.items()):
        si = nuevas_si[i]
        u = list(re.finditer(r'<t\b[^>]*>([^<]*)</t>', si))[-1]
        si = si[:u.start(1)] + u.group(1).rstrip() + si[u.end(1):]
        p_ = re.search(r'<t\b[^>]*>([^<]*)</t>', si)
        si = si[:p_.start()] + f'<t xml:space="preserve">{espacios}{p_.group(1).lstrip()}</t>' + si[p_.end():]
        nuevas_si.append(si)
        sangrar_ricos[(c, f)] = len(nuevas_si) - 1

    # Escribir: textos nuevos como cadenas compartidas nuevas, formatos y altos de fila
    def celda_nueva(c, f, xml):
        s_nuevo = nuevos_s.get((c, f))
        apertura = xml[:xml.find(">") + 1]
        cuerpo = xml[len(apertura):]
        if s_nuevo is not None:
            apertura = re.sub(r'\ss="\d+"', "", apertura)
            apertura = apertura.replace("<c ", f'<c s="{s_nuevo}" ', 1)
        if todas.get((c, f), {}).get("borrar"):
            apertura = re.sub(r'\st="\w+"', "", apertura)
            return (apertura if apertura.endswith("/>") else apertura[:-1] + "/>")
        if (c, f) in nuevos_textos:
            nuevas_si.append(f'<si><t xml:space="preserve">{html.escape(nuevos_textos[(c, f)], quote=False)}</t></si>')
            apertura = re.sub(r'\st="\w+"', "", apertura).replace("<c ", '<c t="s" ', 1)
            if apertura.endswith("/>"):
                apertura = apertura[:-2] + ">"
            cuerpo = f"<v>{len(nuevas_si) - 1}</v></c>"
        elif (c, f) in sangrar_ricos:
            cuerpo = f"<v>{sangrar_ricos[(c, f)]}</v></c>"
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
        if f == (bloque["filas"][0] if bloque else f1) - 1:
            # La fila del hueco bajo la pastilla tiene que verse (DO26XX_04: el autor la ocultó y el alto nuevo no
            # contaba: la cabecera quedaba pegada a la pastilla)
            fila = re.sub(r'\shidden="[^"]*"', "", fila)
        return fila[:-1].rstrip("/") + f' ht="{altos[f]}" customHeight="1"' + ("/>" if fila.endswith("/>") else ">")

    def ocultar_otra(m):
        fila = m.group(0)
        if int(re.search(r'\br="(\d+)"', fila).group(1)) not in filas_otra or 'hidden="1"' in fila:
            return fila
        return fila[:-1].rstrip("/") + ' hidden="1"' + ("/>" if fila.endswith("/>") else ">")
    if filas_otra:
        # Su alto pasa a la fila de debajo: lo que el autor dejó más abajo no se mueve (01: una copia de la FUENTE en
        # la fila 62, fuera de la retícula, subía a 191 mm, dentro del cuadro)
        alto_orig, alto_def = altos_filas(z, hoja)
        bajo = max(filas_otra) + 1
        suma = sum(alto_orig.get(f - 1, alto_def) for f in filas_otra | {bajo}) / EMU_PT
        hoja_xml = re.sub(r'<row\b[^>]*?/?>', ocultar_otra, hoja_xml)
        hoja_xml = asegurar_filas(hoja_xml, [bajo])

        def alto_bajo(m):
            fila = m.group(0)
            if int(re.search(r'\br="(\d+)"', fila).group(1)) != bajo:
                return fila
            fila = re.sub(r'\s(ht|customHeight|hidden)="[^"]*"', "", fila)
            return fila[:-1].rstrip("/") + f' ht="{round(suma, 2):g}" customHeight="1"' + ("/>" if fila.endswith("/>") else ">")
        hoja_xml = re.sub(r'<row\b[^>]*?/?>', alto_bajo, hoja_xml)
    hoja_xml = re.sub(r'<row\b[^>]*?/?>', cambiar_fila, hoja_xml)
    hoja_xml = poner_anchos(hoja_xml, nuevos_anchos)
    if estilos_bloque:
        hoja_xml = con_estilo(hoja_xml, estilos_bloque)

    # Sitio del cuadro (decisión del usuario, 2026-11-17): la cabecera empieza 4 mm bajo las unidades o, si no hay,
    # 5 mm bajo la pastilla; FUENTES, 5 mm bajo el final del cuadro. Lo ajusta la fila de encima del cuadro.
    ruta_dibujo = dibujo_de_hoja(z, hoja)
    if ruta_dibujo and f1 > 1:
        caja = medidas_hoja(z, hoja, dibujo)
        f_ini = bloque["filas"][0] if bloque else f1
        dibujo_nuevo, notas_sitio, alto_hueco = colocar_cuadro(dibujo, caja, altos_filas(z, hoja), altos, f_ini, f2)
        alto_hueco, altos_encima = alto_hueco
        cambiadas = {f: v for f, v in altos_encima.items() if abs(v * EMU_PT - altos_filas(z, hoja)[0].get(f - 1, altos_filas(z, hoja)[1])) > 0.5 * EMU_PT}
        altos.update(cambiadas)
        altos[f_ini - 1] = alto_hueco
        hoja_xml = asegurar_filas(hoja_xml, [f_ini - 1] + list(cambiadas))
        hoja_xml = re.sub(r'<row\b[^>]*?/?>', cambiar_fila, hoja_xml)
        if dibujo_nuevo != dibujo:
            cambios_dibujo[ruta_dibujo] = dibujo_nuevo.encode("utf-8")
        detalle += notas_sitio
    elif f1 <= 1:
        detalle.append("Aviso: el cuadro empieza en la fila 1: no hay fila encima para separarlo de la pastilla")
    # Cuadros de texto de la cabecera (DO26XX_02: 𝑡, 𝛽, 𝜌, 𝜎²), centrados en su celda con los anchos y altos nuevos
    # (anclados a una distancia fija del borde izquierdo de la celda, se descentraban al cambiar el ancho)
    if ruta_dibujo and filas_formas:
        actual = cambios_dibujo[ruta_dibujo].decode("utf-8") if ruta_dibujo in cambios_dibujo else dibujo
        altos_emu, alto_def = altos_filas(z, hoja)
        centradas = []

        def centrar(m):
            anc = m.group(0)
            desde = re.search(r'<xdr:from>\s*<xdr:col>(\d+)</xdr:col>\s*<xdr:colOff>-?\d+</xdr:colOff>\s*<xdr:row>(\d+)</xdr:row>'
                              r'\s*<xdr:rowOff>-?\d+</xdr:rowOff>\s*</xdr:from>', anc)
            if not desde or m.group(1) == "absoluteAnchor" or not html.unescape(texto_forma(anc)).strip():
                return anc
            c, f = int(desde.group(1)) + 1, int(desde.group(2)) + 1
            if f not in filas_formas or not (c1 < c <= c2):
                return anc
            ancho_c = unidades_a_emu(ancho_col(c))
            alto_f = round(altos[f] * EMU_PT) if f in altos else altos_emu.get(f - 1, alto_def)
            if m.group(1) == "oneCellAnchor":
                ext = re.search(r'<xdr:ext cx="(\d+)" cy="(\d+)"/>', anc)
                if not ext:
                    return anc
                cx, cy = int(ext.group(1)), int(ext.group(2))
            else:
                hasta = re.search(r'<xdr:to>\s*<xdr:col>(\d+)</xdr:col>\s*<xdr:colOff>(-?\d+)</xdr:colOff>\s*<xdr:row>(\d+)</xdr:row>'
                                  r'\s*<xdr:rowOff>(-?\d+)</xdr:rowOff>\s*</xdr:to>', anc)
                ext = re.search(r'<a:ext cx="(\d+)" cy="(\d+)"/>', anc)
                if not hasta or not ext or hasta.group(1) != desde.group(1) or hasta.group(3) != desde.group(2):
                    return anc
                cx, cy = int(ext.group(1)), int(ext.group(2))
            x, y = max(0, (ancho_c - cx) // 2), max(0, (alto_f - cy) // 2)
            nuevo_desde = (f"<xdr:from><xdr:col>{c - 1}</xdr:col><xdr:colOff>{x}</xdr:colOff><xdr:row>{f - 1}</xdr:row>"
                           f"<xdr:rowOff>{y}</xdr:rowOff></xdr:from>")
            anc = anc.replace(desde.group(0), nuevo_desde, 1)
            if m.group(1) == "twoCellAnchor":
                anc = anc.replace(hasta.group(0), f"<xdr:to><xdr:col>{c - 1}</xdr:col><xdr:colOff>{x + cx}</xdr:colOff>"
                                  f"<xdr:row>{f - 1}</xdr:row><xdr:rowOff>{y + cy}</xdr:rowOff></xdr:to>", 1)
            centradas.append(ref(c, f))
            return anc
        centrado = ANCLA.sub(centrar, actual)
        if centradas:
            cambios_dibujo[ruta_dibujo] = centrado.encode("utf-8")
            detalle.append(f"Cuadros de texto de la cabecera, centrados en su celda ({len(centradas)})" + marca(centradas))
    # Puntos y flechas dibujados sobre las celdas: en su sitio con los anchos y altos nuevos
    if ruta_dibujo:
        actual = cambios_dibujo[ruta_dibujo].decode("utf-8") if ruta_dibujo in cambios_dibujo else dibujo
        altos_emu_v, alto_def_v = altos_filas(z, hoja)
        movido, n_mov = reubicar_formas(
            actual, c1, c2, f1, f2,
            lambda i: unidades_a_emu(anchos_viejos.get(i + 1, ancho_col_viejo(i + 1))),
            lambda i: unidades_a_emu(ancho_col(i + 1)),
            lambda i: altos_emu_v.get(i, alto_def_v),
            lambda i: round(altos[i + 1] * EMU_PT) if i + 1 in altos else altos_emu_v.get(i, alto_def_v))
        if n_mov:
            cambios_dibujo[ruta_dibujo] = movido.encode("utf-8")
            detalle.append(f"Formas dibujadas sobre las celdas (puntos, flechas), en su sitio con los anchos y altos nuevos ({len(n_mov)}: "
                           + ", ".join(f"«{n}»" for n in n_mov[:6]) + ("…" if len(n_mov) > 6 else "") + ")")
    faltan = [f for f in altos if not re.search(rf'<row\b[^>]*\br="{f}"', hoja_xml)]
    if faltan:
        detalle.append(f"Aviso: filas sin definir en la hoja ({', '.join(map(str, faltan))}): su alto no se ha cambiado")

    cambios = {ruta_hoja: hoja_xml.encode("utf-8"), "xl/styles.xml": estilos.resultado().encode("utf-8"), **cambios_dibujo}
    if nuevas_si != compartidos or nuevos_textos:
        comp = comp_xml
        cuerpo = "".join(nuevas_si)
        comp = re.sub(r'(<sst\b[^>]*>).*(</sst>)', lambda m: m.group(1) + cuerpo + m.group(2), comp, count=1, flags=re.S)
        comp = re.sub(r'\buniqueCount="\d+"', f'uniqueCount="{len(nuevas_si)}"', comp, count=1)
        cambios["xl/sharedStrings.xml"] = comp.encode("utf-8")
    return cambios, detalle, {"c1": c1, "f1": f1, "c2": c2, "f2": f2, "primera": primera, "fin_cabecera": fin_cab,
                              "bloque_arriba": bloque["filas"] if bloque else [],
                              "bloque_cabecera": bloque["cabecera"] if bloque else None,
                              "bloque_grupos": [list(g) for g in bloque["grupos"]] if bloque else [],
                              "cabecera_formas": [[c, f] for f in sorted(filas_formas) for c in sorted(formas_fila.get(f, set()))
                                                  if c1 <= c <= c2 and not todas.get((c, f), {}).get("texto", "").strip()]}


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
    todas = sin_filas_ocultas(celdas_hoja(hoja_xml, compartidos), hoja_xml)
    rangos = combinadas(hoja_xml)
    ancho_col = anchos_columnas(hoja_xml)
    c1, f1, c2, f2 = cuadro["c1"], cuadro["f1"], cuadro["c2"], cuadro["f2"]
    primera, fin_cab = cuadro["primera"], cuadro["fin_cabecera"]
    colores = matices(pub["color"])
    detalle = []

    # Celdas vacías con un cuadro de texto encima (fórmulas o símbolos de la cabecera, DO26XX_02): cuentan como texto
    con_forma = {tuple(k) for k in cuadro.get("cabecera_formas", [])}

    def texto(c, f):
        return todas.get((c, f), {}).get("texto", "").strip() or ("\u25a1" if (c, f) in con_forma else "")

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
    nuevos, usados, grupos_7 = {}, {}, set()
    mapa_calor_cab = bool(cifras_ocultas(hoja_xml, estilos.xml))
    # Fila de cabecera de debajo de una fila de textos sueltos (1 o 2, sin combinar, con cabecera debajo en su columna)
    fila_bajo_nota = None
    textos_f1 = [c for c in range(c1, c2 + 1) if texto(c, f1)]
    if 1 <= len(textos_f1) <= 2 and not any((c, f1) in combinada and combinada[(c, f1)][2] > combinada[(c, f1)][0] for c in textos_f1):
        fila_bajo_nota = next((g for g in range(f1 + 1, fin_cab + 1) if sum(1 for c in range(c1, c2 + 1) if texto(c, g)) >= 2), None)
    for f in range(f1, fin_cab + 1):
        for c in range(primera, c2 + 1):
            a1, b1, a2, b2 = combinada.get((c, f), (c, f, c, f))
            ancla = (a1, b1)
            if ancho_col(c) == 0 and texto(*ancla):
                continue   # columna oculta del autor con texto («Descuadre», Memoria 2.1): no se toca
            estrecha = ancho_col(c) < COLUMNA_ESTRECHA and a1 == a2
            vacia = not texto(*ancla) and ancla not in [(k[0], k[1]) for k in combinada.values()]
            unidades = c == primera and RE_UNIDADES.match(texto(*ancla)) is not None
            # Esquina vacía de una cabecera de una sola fila, con el color de la cabecera (publicado de LATAM/Economía
            # Latinoamericana 02; con dos o más filas, sin relleno: 01, 04 y 05)
            esquina_llena = pub.get("esquina_una_fila") and c == primera and f1 == fin_cab and not texto(*ancla) \
                and not estrecha and ancho_col(c) > 0
            if pub.get("solo_lineas"):
                # Solo líneas (LATAM/Indicadores Macrofinancieros, publicados Arg_03, CARD_02…): sin fondo y en negro,
                # línea del color de la publicación bajo cada texto de cabecera (los grupos, solo en su ancho) y bajo
                # toda la última fila; las columnas de separación, sin línea (hueco entre grupos)
                lados = {}
                # Sin línea bajo un texto suelto que va encima de otra cabecera de su columna (Arg_02: «Respecto al resto
                # de los emergentes» sobre «Último dato (b)»; el publicado no la lleva)
                debajo_c = next((g for g in range(b2 + 1, fin_cab + 1) if texto(c, g)), None)
                nota = (a1 == a2 and texto(*ancla) and debajo_c is not None
                        and sum(1 for k in range(c1, c2 + 1) if texto(k, b1)) <= 2)
                # (las estrechas con texto, como los semestres «I S», sí la llevan: solo las de separación vacías no)
                separacion_vacia = estrecha and not any(texto(c, g) for g in range(f1, fin_cab + 1))
                if not separacion_vacia and not nota and (f == fin_cab or (texto(*ancla) and f == b2 and not unidades)):
                    lados["bottom"] = ("thin", pub["color"].upper())
                # La línea final de la cabecera cruza también las separaciones (publicado Arg_03), salvo en el mapa de
                # calor, donde los huecos blancos la cortan (publicado Arg_02)
                if separacion_vacia and f == fin_cab and not mapa_calor_cab:
                    lados["bottom"] = ("thin", pub["color"].upper())
                # Con un texto suelto encima (Arg_02: «Respecto al resto de los emergentes»), la primera fila de verdad de
                # la cabecera lleva línea encima en todas las columnas de datos, también las separaciones (publicado)
                if c > primera and f == fila_bajo_nota:
                    lados["top"] = ("thin", pub["color"].upper())
                base_s = estilo(c, f)
                # Cabeceras de grupo (combinadas sobre varias columnas, por encima de la última fila: «mm de dólares»,
                # «Porcentaje del PIB»…), con su letra (Indicadores: 7 pt, como el original y el publicado de Arg_03)
                if pub.get("cuerpo_grupos_cabecera") and a2 > a1 and f < fin_cab and texto(*ancla):
                    base_s = estilos.nuevo(base_s, estilos.alineacion(base_s), cuerpo=float(pub["cuerpo_grupos_cabecera"]))
                    grupos_7.add(ref(*ancla))
                nuevos[(c, f)] = estilos.variante(base_s, relleno="", borde=lados, letra="000000")
                continue
            if not esquina_llena and (estrecha or vacia or (c == primera and not texto(*ancla)) or unidades):
                # Sin relleno ni líneas (el autor puede haber dejado alguna: 3.4, línea azul en A4 y G4)
                nuevos[(c, f)] = estilos.variante(estilo(c, f), relleno="", borde={})
                continue
            nivel = min(4, nivel_de(b2))
            clave_color, letra = NIVELES_CABECERA[nivel]
            if nivel in pub.get("cabecera_letra_blanca", []):
                letra = BLANCO   # por publicación (Memoria Supervisión: nivel 2 en blanco, publicados 3.1 y 3.4)
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
    if grupos_7:
        detalle.append(f"Cabeceras de grupo a {float(pub['cuerpo_grupos_cabecera']):g} pt (como el original y el publicado): ".replace(".", ",")
                       + ", ".join(sorted(grupos_7)))
    if pub.get("solo_lineas"):
        detalle.append(f"Cabecera sin fondo, en negro, con línea #{pub['color'].upper()} bajo cada texto (los grupos, solo en su "
                       "ancho) y bajo toda la última fila (como los publicados de " + pub.get("nombre", "la publicación") + ")")
    for nivel in sorted(usados):
        clave_color, letra = NIVELES_CABECERA[nivel]
        if nivel in pub.get("cabecera_letra_blanca", []):
            letra = BLANCO
        detalle.append(f"Cabecera {nivel}: {clave_color.replace('matiz', 'matiz ').replace('solido', 'sólido')} "
                       f"#{colores[clave_color]}" + (", texto en blanco" if letra else "") + f" ({len(usados[nivel])} celda{'s' if len(usados[nivel]) > 1 else ''})")
    if not pub.get("solo_lineas"):
        detalle.append("Líneas blancas finas entre las celdas de la cabecera y entre sus niveles")
    estrechas = [ref(c, 1)[:-1] for c in range(primera + 1, c2 + 1) if 0 < ancho_col(c) < COLUMNA_ESTRECHA]
    if estrechas:
        detalle.append("Columnas de separación sin relleno (hueco blanco entre grupos): " + ", ".join(estrechas))
    if pub.get("esquina_una_fila") and f1 == fin_cab and not texto(primera, f1):
        detalle.append("Cabecera de una fila: la esquina de la primera columna, con su color aunque no lleve texto (como los "
                       "publicados de " + pub.get("nombre", "la publicación") + ")")
    elif not texto(primera, fin_cab) and not any(texto(primera, f) for f in range(f1, fin_cab + 1)):
        detalle.append("Esquina de la primera columna sin relleno (no lleva texto)")
    elif any(RE_UNIDADES.match(texto(primera, f)) for f in range(f1, fin_cab + 1)):
        detalle.append("Esquina de la primera columna sin relleno (lleva las unidades)")
    hoja_xml = con_estilo(hoja_xml, nuevos)
    return {ruta_hoja: hoja_xml.encode("utf-8"), "xl/styles.xml": estilos.resultado().encode("utf-8")}, detalle


# ---------------------------------------------------------------- paso 4: líneas y fondos

LINEAS_Y_FONDOS = "Líneas y fondos"
# Matices del blanco (Resumen cuadros, pág. 21): 1 = −5 %, 2 = −15 %, 5 = −50 %
BLANCO_MATIZ_1, BLANCO_MATIZ_2, BLANCO_MATIZ_5 = "F2F2F2", "D9D9D9", "808080"
LINEA_BLOQUES = ("thin", "A6A6A6")   # entre bloques (LATAM/Economía Latinoamericana, publicado 05: blanco −35 %)
LINEA_FILAS = ("thin", BLANCO_MATIZ_2)      # separa filas
LINEA_OSCURA = ("thin", BLANCO_MATIZ_5)     # separa la fila TOTAL (y lo que se añada a mano)


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
        cambios, detalle = lineas_y_fondos(z, hoja, cuadro, pub_de(pid))
    return nuevo_paso(trabajo, LINEAS_Y_FONDOS, cambios, detalle, cuadro)


RE_ESTADISTICOS = re.compile(r'\s*(n\.?\s?º\s+de\s+)?(observaciones|observations|number of observations|'
                             r'pseudo[- ]?r\s?2|r\s?2|r²|r\s?2\s+ajustado|adjusted\s+r\s?2)\b', re.I)


def con_combinadas(hoja_xml, refs):
    """La hoja con estas celdas combinadas más (sin repetir las que ya lo están)."""
    ya = set(re.findall(r'<mergeCell\b[^>]*\bref="([^"]+)"', hoja_xml))
    refs = [r for r in refs if r not in ya]
    if not refs:
        return hoja_xml
    nuevas = "".join(f'<mergeCell ref="{r}"/>' for r in refs)
    if "<mergeCells" in hoja_xml:
        hoja_xml = re.sub(r'(<mergeCells\b[^>]*?)\scount="\d+"', lambda m: f'{m.group(1)} count="{len(ya) + len(refs)}"', hoja_xml, count=1)
        return hoja_xml.replace("</mergeCells>", nuevas + "</mergeCells>", 1)
    # Va tras sheetData y lo que el esquema pone antes (protección, filtros…)
    fin = hoja_xml.index("</sheetData>") + len("</sheetData>")
    for etiqueta in ("sheetCalcPr", "sheetProtection", "protectedRanges", "scenarios", "autoFilter", "sortState",
                     "dataConsolidate", "customSheetViews"):
        m = re.search(rf'<{etiqueta}\b(?:[^>]*/>|.*?</{etiqueta}>)', hoja_xml[fin:], re.S)
        if m:
            fin += m.end()
    return hoja_xml[:fin] + f'<mergeCells count="{len(refs)}">{nuevas}</mergeCells>' + hoja_xml[fin:]


def lineas_y_fondos(z, hoja, cuadro, pub=None):
    ruta_hoja = hoja_de(z, hoja)
    hoja_xml = z.read(ruta_hoja).decode("utf-8")
    _, compartidos = leer_compartidos(z)
    estilos = Estilos(z.read("xl/styles.xml").decode("utf-8"))
    todas = sin_filas_ocultas(celdas_hoja(hoja_xml, compartidos), hoja_xml)
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
    # Varias filas «TOTAL» (una por bloque, DO26XX_04): son totales de bloque, todas en matiz 2 como subtotales; no
    # hay una TOTAL principal (el publicado no pone la última en matiz 5)
    totales_bloque = [f for f in totales if texto(primera, f).strip().upper() == "TOTAL"]
    if len(totales_bloque) > 1:
        principal = None
    else:
        totales_bloque = []
    subtotales = [f for f in totales if f != principal]
    # Títulos de bloque: concepto sin sangría y sin datos en las demás columnas
    bloques = [f for f in filas if texto(primera, f).strip() and not sangrada(f) and sin_datos(f) and f not in totales]
    # «España» en una lista de provincias o países (sin sangría y con datos): toda la fila destacada en blanco matiz 2
    # (publicados 2.7 y 2.9, Ejemplos 2.3; en el 1.4 es un concepto sangrado de un bloque y no se destaca)
    destacadas = [f for f in filas if re.fullmatch(r'\s*(España|Spain)\s*', texto(primera, f)) and not sangrada(f)
                  and not sin_datos(f) and f not in totales]
    # Columna TOTAL: la de datos cuya cabecera dice «TOTAL»
    col_total = next((c for c in datos_cols if any(texto(c, f).strip().upper() == "TOTAL" for f in range(f1, fin_cab + 1))), None)
    # La fila TOTAL va en blanco matiz 2, o en matiz 5 si el 2 ya lo usan títulos de bloque o subtotales (Ejemplos,
    # 1.4 y A2.2); una columna TOTAL también va en matiz 2 y no lo cambia (Ejemplos, 4.2)
    # Bloques con apartados (Documentos Ocasionales, publicados DO26XX_01, 03 y 04): el título de bloque va con el
    # fondo de la primera columna (no en matiz 2), sin línea con su primer apartado, para que los conceptos sangrados
    # se lean como apartados suyos; entre bloques, línea oscura encima del título; la fila vacía que el autor dejaba
    # antes de un bloque se oculta (el publicado del 03 la quita)
    apartados = bool((pub or {}).get("bloques_con_apartados")) and bool(bloques)
    vacias_sep = []
    if apartados:
        vacias_sep = [f for f in filas if f + 1 in bloques and not texto(primera, f).strip() and sin_datos(f)]
        filas = [f for f in filas if f not in vacias_sep]
    # Títulos de bloque sin fondo propio, con el de la primera columna (LATAM/Economía Latinoamericana, publicados 02 y 05)
    sin_fondo_bloque = bool((pub or {}).get("bloques_sin_fondo")) and bool(bloques) and not apartados
    usa_matiz_2 = bool((bloques and not apartados and not sin_fondo_bloque) or subtotales)
    linea_bloques = bool((pub or {}).get("linea_entre_bloques")) and not apartados
    solo_lineas = bool((pub or {}).get("solo_lineas"))
    mapa_calor = False
    grupos_autor = set()
    if solo_lineas:
        linea_rosa = ("thin", matiz(pub["color"], TINTES["matiz1"]))
        linea_bloques_solida = ("thin", pub["color"].upper())
        # Grupos que el autor marcó con una línea más oscura que las demás bajo la primera columna (Arg_02: «Diferencial
        # soberano (cambio trimestral)», «Sobrevaloración cambiaria»… en granate y las demás en rosa): se respetan
        tema = colores_tema(z)
        mapa_calor = bool(cifras_ocultas(hoja_xml, estilos.xml))

        def luz_inferior(f):
            xf = estilos.xf(estilo(primera, f))
            b = re.search(r'\bborderId="(\d+)"', xf)
            borde = (estilos.bordes + estilos.nuevos_bordes)[int(b.group(1))] if b and int(b.group(1)) < len(estilos.bordes) + len(estilos.nuevos_bordes) else ""
            m_ = re.search(r'<bottom style="\w+">(.*?)</bottom>', colores_a_rgb(borde, tema), re.S)
            rgb = re.search(r'rgb="\w{2}(\w{6})"', m_.group(1)) if m_ else None
            if not rgb:
                return None
            r_, g_, b_ = (int(rgb.group(1)[i:i + 2], 16) / 255 for i in (0, 2, 4))
            return 0.299 * r_ + 0.587 * g_ + 0.114 * b_
        luces = {f: luz_inferior(f) for f in filas[:-1]}
        comunes = Counter(round(v, 2) for v in luces.values() if v is not None)
        if comunes:
            habitual = comunes.most_common(1)[0][0]
            grupos_autor = {f for f, v in luces.items() if v is not None and v < habitual - 0.2}
    fondo_total = BLANCO_MATIZ_5 if usa_matiz_2 else BLANCO_MATIZ_2
    letra_total = BLANCO if fondo_total == BLANCO_MATIZ_5 else None

    separaciones = {c for c in datos_cols if ancho_col(c) < COLUMNA_ESTRECHA
                    and not any(texto(c, f).strip() for f in range(f1, f2 + 1))}
    # Regresiones (publicado 3.3): la fila del coeficiente y la de su error estándar entre paréntesis (sin concepto)
    # son un solo concepto: la primera columna se combina en las dos filas y entre ellas no hay línea. Los
    # estadísticos (observaciones, R²) van separados de las estimaciones por una línea oscura
    def es_error(f):
        vals = [texto(c, f).strip() for c in datos_cols if texto(c, f).strip()]
        return not texto(primera, f).strip() and bool(vals) and all(re.fullmatch(r'\(.*\)\**', v) for v in vals)
    errores = [f for f in filas[1:] if es_error(f) and texto(primera, f - 1).strip() and not sin_datos(f - 1)]
    coeficientes = {f - 1 for f in errores}
    estadisticos = next((f for f in filas if RE_ESTADISTICOS.match(texto(primera, f)) and f > min(errores)), None) if errores else None
    nuevos = {}
    ultima = filas[-1]
    for i, f in enumerate(filas):
        siguiente = filas[i + 1] if i + 1 < len(filas) else None
        es_total = f in totales
        for c in range(primera, c2 + 1):
            if ancho_col(c) == 0:
                continue
            # (en Indicadores las líneas cruzan las separaciones, salvo en el mapa de calor: ahí los huecos blancos las
            # cortan, como el publicado Arg_02)
            if c in separaciones and not es_total and (not solo_lineas or mapa_calor):
                # Columnas de separación: sin líneas ni fondo (las líneas se cortan entre grupos, TERMINADO 3.4);
                # en la fila TOTAL sí, sin hueco (guía)
                nuevos[(c, f)] = estilos.variante(estilo(c, f), relleno="", borde={})
                continue
            lados, relleno, letra = {}, None, None
            # Línea de debajo: entre filas, gris claro; la última fila, sin línea. Encima de la fila TOTAL no va línea
            # oscura sino blanca (decisión del usuario, 2026-11-17, publicado Memoria 3.1; antes iba oscura)
            if siguiente is not None and siguiente != principal:
                lados["bottom"] = LINEA_FILAS
            if f == principal and i > 0:
                lados["top"] = ("thin", BLANCO)
            if f in coeficientes:
                lados.pop("bottom", None)
            if estadisticos and siguiente == estadisticos:
                lados["bottom"] = LINEA_OSCURA
            if f == estadisticos:
                lados["top"] = LINEA_OSCURA
            if apartados and f in bloques and siguiente is not None and sangrada(siguiente):
                lados.pop("bottom", None)
            if apartados and f in bloques and i > 0:
                lados["top"] = LINEA_OSCURA
            if c == primera:
                relleno = BLANCO_MATIZ_1
                if f in bloques:
                    relleno = BLANCO_MATIZ_2
                # Primera columna: líneas blancas entre todas las filas, también entre conceptos sangrados
                # (TERMINADO 1.4; la guía decía que no, decisión del usuario 2026-11-17)
                # Sin línea blanca hacia un concepto sangrado: es del mismo grupo (LATAM/Economía Latinoamericana 02,
                # petición del usuario, 2026-11-20); la de antes de cada título de bloque se queda
                mismo_grupo = (pub or {}).get("apartados_sin_linea_blanca") and siguiente is not None and sangrada(siguiente)
                if siguiente is not None and siguiente != principal and f not in coeficientes and siguiente != estadisticos \
                        and not (apartados and f in bloques and sangrada(siguiente)) and not mismo_grupo:
                    lados["bottom"] = ("thin", BLANCO)
                elif mismo_grupo:
                    lados.pop("bottom", None)
                if (apartados or sin_fondo_bloque) and f in bloques:
                    relleno = BLANCO_MATIZ_1
            # Columna TOTAL: sin fondo; su cabecera va en el color de la publicación, así que ni gris ni mayúsculas
            # (decisión del usuario, 2026-11-17, publicado Memoria 3.1; antes iba en blanco matiz 2)
            if f in destacadas:
                relleno = BLANCO_MATIZ_2
                lados["bottom"] = ("thin", BLANCO)
                if i > 0:
                    lados["top"] = ("thin", BLANCO)
            if es_total:
                relleno = fondo_total if f == principal else BLANCO_MATIZ_2
                letra = letra_total if f == principal else None
            if apartados and siguiente in bloques:
                lados["bottom"] = LINEA_OSCURA
            # Línea más oscura entre grupos, de lado a lado (petición del usuario, 2026-11-20, como el publicado 05)
            if linea_bloques and siguiente in bloques:
                lados["bottom"] = LINEA_BLOQUES
            if f in grupos_autor:
                lados["bottom"] = LINEA_BLOQUES
            if solo_lineas:
                # Solo líneas (LATAM/Indicadores Macrofinancieros): sin fondos propios (los del autor en los datos, como
                # los colores del mapa de calor, se quedan); entre filas, matiz 1 del color; entre bloques, el sólido
                if c == primera or relleno is not None:
                    relleno = ""
                lados = {k: (linea_bloques_solida if v in (LINEA_BLOQUES, LINEA_OSCURA) else linea_rosa) for k, v in lados.items()}
                # Mapa de calor (Arg_02): bajo los colores, solo las líneas de grupo; las rosas, solo bajo los conceptos
                if mapa_calor and c != primera:
                    lados = {k: v for k, v in lados.items() if v == linea_bloques_solida}
                letra = None
            nuevos[(c, f)] = estilos.variante(estilo(c, f), relleno=relleno, borde=lados,
                                              letra=letra if letra else None)
    # Detalle
    if grupos_autor:
        detalle.append(f"Grupos que el autor separó con una línea más oscura, en #{linea_bloques_solida[1]} de lado a lado: "
                       "bajo " + ", ".join(f"«{texto(primera, f).strip()[:25]}»" for f in sorted(grupos_autor))
                       + marca([ref(primera, f) for f in sorted(grupos_autor)]))
    if solo_lineas:
        detalle.append(f"Solo líneas (como los publicados de {pub.get('nombre', 'la publicación')}): entre filas, matiz 1 "
                       f"{linea_rosa[1]}, también en la primera columna, que va sin fondo; la última fila, sin línea"
                       + (f"; entre grupos, #{linea_bloques_solida[1]}" if linea_bloques else ""))
    else:
        detalle.append("Líneas horizontales finas entre filas en blanco matiz 2 (#D9D9D9); la última fila, sin línea")
        detalle.append("Primera columna: fondo blanco matiz 1 (#F2F2F2) con líneas blancas entre todas las filas")
    if apartados:
        detalle.append("Títulos de bloque con apartados (sin datos en las demás columnas), con el fondo de la primera columna "
                       "y sin línea con su primer apartado; línea oscura (blanco matiz 5) encima de cada bloque salvo el primero"
                       " (como los publicados de " + (pub or {}).get("nombre", "la publicación") + "): "
                       + ", ".join(f"«{texto(primera, f).strip()[:30]}»" for f in bloques[:6]) + ("…" if len(bloques) > 6 else "")
                       + marca([ref(primera, f) for f in bloques]))
        if vacias_sep:
            detalle.append("Filas vacías entre bloques, ocultas (la línea oscura ya los separa): " + ", ".join(map(str, vacias_sep))
                           + marca([ref(primera, f) for f in vacias_sep]))
    if (pub or {}).get("apartados_sin_linea_blanca") and any(sangrada(f) for f in filas):
        detalle.append("Primera columna: sin línea blanca encima de los conceptos sangrados (son del mismo grupo que el de "
                       "arriba); solo entre grupos")
    if apartados:
        pass
    elif sin_fondo_bloque:
        detalle.append("Títulos de bloque (sin datos en las demás columnas), con el fondo de la primera columna, sin destacar "
                       "(como los publicados de " + (pub or {}).get("nombre", "la publicación") + "): "
                       + ", ".join(f"«{texto(primera, f).strip()[:30]}»" for f in bloques[:6]) + ("…" if len(bloques) > 6 else ""))
    elif bloques:
        detalle.append(f"Títulos de bloque (sin datos en las demás columnas), fondo blanco matiz 2: "
                       + ", ".join(f"«{texto(primera, f).strip()[:30]}»" for f in bloques[:6]) + ("…" if len(bloques) > 6 else ""))
    if linea_bloques and any(f in bloques for f in filas[1:]):
        detalle.append("Línea gris oscura (#A6A6A6) entre grupos, de lado a lado, encima de cada título de bloque salvo el "
                       "primero (como el publicado 05)" + marca([ref(primera, f) for f in filas[1:] if f in bloques]))
    for f in destacadas:
        detalle.append(f"Fila «{texto(primera, f).strip()}» destacada en blanco matiz 2 (agregado nacional en una lista de "
                       f"provincias o países, como los publicados)" + marca([ref(c, f) for c in (primera, c2)]))
    if totales_bloque:
        detalle.append(f"Un «TOTAL» en cada bloque (filas {', '.join(map(str, totales_bloque))}): totales de bloque, toda la fila en "
                       "blanco matiz 2 y Roboto Medium; no hay fila TOTAL principal (como el publicado del DO26XX_04)"
                       + marca([ref(primera, f) for f in totales_bloque]))
    for f in subtotales:
        if f in totales_bloque:
            continue
        detalle.append(f"Subtotal «{texto(primera, f).strip()[:40]}»: fondo blanco matiz 2 en toda la fila")
    if principal:
        detalle.append(f"Fila TOTAL (fila {principal}): fondo blanco matiz {'5 (#808080) con el texto en blanco, porque el matiz 2 ya está usado' if fondo_total == BLANCO_MATIZ_5 else '2 (#D9D9D9)'}"
                       "; línea blanca encima (sin línea oscura); sin hueco en las columnas de separación")
    elif not totales_bloque:
        detalle.append("Sin fila TOTAL")
    if separaciones and not solo_lineas:
        detalle.append("Columnas de separación sin líneas en las filas de datos (las líneas se cortan entre grupos): "
                       + ", ".join(ref(c, 1)[:-1] for c in sorted(separaciones)))
    if col_total:
        detalle.append(f"Columna TOTAL ({ref(col_total, 1)[:-1]}): sin fondo, como las demás (su cabecera va en el color de la publicación)")
    if errores:
        detalle.append("Regresión: coeficiente y error estándar (entre paréntesis) como un solo concepto, sin línea entre "
                       "ellos y con la primera columna combinada (" + ", ".join(f"{ref(primera, f - 1)}:{ref(primera, f)}" for f in errores) + ")"
                       + (f"; línea oscura antes de «{texto(primera, estadisticos).strip()}» (separa los estadísticos)" if estadisticos else "")
                       + ", como el publicado del 3.3" + marca([ref(primera, f) for f in errores]))
    # Formato suelto del autor a la derecha del cuadro (líneas, rellenos en celdas vacías: 1.2, columnas I-K), fuera
    sueltas = [(c, f) for (c, f), x in todas.items() if f1 <= f <= f2 and c > c2 and not x["texto"].strip()
               and (re.search(r'\bborderId="[1-9]', estilos.xf(x["s"])) or re.search(r'\bfillId="([2-9]|\d\d+)"', estilos.xf(x["s"])))]
    for k in sueltas:
        nuevos[k] = estilos.variante(estilo(*k), relleno="", borde={})
    if sueltas:
        columnas_s = sorted({c for c, _ in sueltas})
        detalle.append("Quitadas líneas y fondos sueltos del autor a la derecha del cuadro (columnas "
                       + ", ".join(ref(c, 1)[:-1] for c in columnas_s) + ")")
    # …y encima del cuadro (entre la pastilla y la cabecera) y en las columnas ocultas (publicado 3.3: el autor
    # dejó líneas azules en la fila 2 y en las separaciones)
    con_formato = lambda x: re.search(r'\bborderId="[1-9]', estilos.xf(x["s"])) or re.search(r'\bfillId="([2-9]|\d\d+)"', estilos.xf(x["s"]))
    encima = [(c, f) for (c, f), x in todas.items() if f < f1 and c1 <= c <= c2 and not x["texto"].strip() and con_formato(x)
              and f not in cuadro.get("bloque_arriba", [])]
    ocultas = [(c, f) for (c, f), x in todas.items() if f1 <= f <= f2 and c1 <= c <= c2 and ancho_col(c) == 0
               and not x["texto"].strip() and con_formato(x)]
    # …y debajo (DO 05: la línea azul del autor encima de la FUENTE, en A14:B14, que se queda al pasar la FUENTE al
    # cuadro de texto; el publicado la quita)
    def se_ve(x):
        """Línea o fondo que se ven (no un borde vacío ni un relleno sin trama, como las celdas del 1.3 y 1.4)."""
        xf = estilos.xf(x["s"])
        b = re.search(r'\bborderId="(\d+)"', xf)
        r = re.search(r'\bfillId="(\d+)"', xf)
        borde = estilos.bordes[int(b.group(1))] if b and int(b.group(1)) < len(estilos.bordes) else ""
        relleno = estilos.rellenos[int(r.group(1))] if r and int(r.group(1)) < len(estilos.rellenos) else ""
        return 'style="' in borde or bool(re.search(r'patternType="(?!none|gray125)', relleno))
    debajo = [(c, f) for (c, f), x in todas.items() if f2 < f <= f2 + 10 and c1 <= c <= c2 and not x["texto"].strip()
              and con_formato(x) and se_ve(x)]
    for k in encima + ocultas + debajo:
        nuevos[k] = estilos.variante(estilo(*k), relleno="", borde={})
    if encima:
        detalle.append("Quitadas líneas y fondos sueltos del autor encima del cuadro (fila"
                       + ("s " if len({f for _, f in encima}) > 1 else " ") + ", ".join(str(f) for f in sorted({f for _, f in encima})) + ")")
    if debajo:
        detalle.append("Quitadas líneas y fondos sueltos del autor debajo del cuadro (fila"
                       + ("s " if len({f for _, f in debajo}) > 1 else " ") + ", ".join(str(f) for f in sorted({f for _, f in debajo})) + ")"
                       + marca([ref(*min(debajo, key=lambda k: (k[1], k[0])))]))
    hoja_xml = con_estilo(hoja_xml, nuevos)
    for f in vacias_sep:
        hoja_xml = asegurar_filas(hoja_xml, [f])
        hoja_xml = re.sub(rf'<row\b[^>]*\br="{f}"[^>]*?/?>',
                          lambda m: m.group(0) if 'hidden="1"' in m.group(0) else
                          m.group(0)[:-2 if m.group(0).endswith("/>") else -1].rstrip() + ' hidden="1"' + ("/>" if m.group(0).endswith("/>") else ">"),
                          hoja_xml, count=1)
    if errores:
        hoja_xml = con_combinadas(hoja_xml, [f"{ref(primera, f - 1)}:{ref(primera, f)}" for f in errores])
    return {ruta_hoja: hoja_xml.encode("utf-8"), "xl/styles.xml": estilos.resultado().encode("utf-8")}, detalle


# ---------------------------------------------------------------- comparar con el original (de Gráficos Excel BdE)

MAXIMO_EJEMPLOS = 6


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
    # Solo los espacios normales y saltos se juntan: el espacio que no parte línea se queda (para el aviso)
    return [t for t in (re.sub(r'[ \t\r\n]+', " ", t).strip(" ") for t in textos) if t]


def sin_ortotipografia(t):
    t = t.replace(" ", " ").replace(" ", " ")
    t = re.sub(r'[«»“”„"]', '"', t).replace("’", "'").replace("‘", "'")
    return re.sub(r'\s+', " ", t).strip()


INVISIBLES = {"\n": "⏎", "\u00a0": "⍽", "\u202f": "⍽", "\u2009": "⍽", "\u200a": "⍽", "\t": "⇥", " ": "␣"}


def resaltar(a, b, contexto=24):
    """«…⟪x⟫…» → «…⟪y⟫…»: solo lo que cambia entre ⟪ ⟫ (la app lo pinta en rojo), con los espacios, saltos de
    línea y espacios que no parten línea a la vista (␣ ⏎ ⍽), y algo de texto alrededor."""
    ops = difflib.SequenceMatcher(None, a, b, autojunk=False).get_opcodes()

    def lado(t, cual):
        trozos = []
        for op, i1, i2, j1, j2 in ops:
            seg = t[i1:i2] if cual == 0 else t[j1:j2]
            if op == "equal":
                trozos.append((False, seg.replace("\n", " ")))
            elif seg:
                trozos.append((True, "".join(INVISIBLES.get(ch, ch) for ch in seg)))
        salida = []
        for k, (marcado, seg) in enumerate(trozos):
            if marcado:
                salida.append("⟪" + seg + "⟫")
                continue
            primero, ultimo = k == 0, k == len(trozos) - 1
            # Los espacios del principio y los pegados a lo que cambia, también a la vista (sangrías)
            if primero or trozos[k - 1][0]:
                seg = re.sub(r'^ +', lambda m: "␣" * len(m.group(0)), seg)
            if not ultimo and trozos[k + 1][0]:
                seg = re.sub(r' +$', lambda m: "␣" * len(m.group(0)), seg)
            if primero and not ultimo and len(seg) > contexto:
                seg = "…" + seg[-contexto:]
            elif ultimo and not primero and len(seg) > contexto:
                seg = seg[:contexto] + "…"
            elif not primero and not ultimo and len(seg) > 2 * contexto:
                seg = seg[:contexto] + "…" + seg[-contexto:]
            elif primero and ultimo:
                seg = recortar(seg)
            salida.append(seg)
        return "".join(salida)
    return f"«{lado(a, 0)}» → «{lado(b, 1)}»"


def explicar(a, b):
    """Qué clase de cambio invisible es (sangría, saltos de línea, espacios), para el aviso."""
    motivos = []
    sa, sb = len(a) - len(a.lstrip(" ")), len(b) - len(b.lstrip(" "))
    if a.strip() == b.strip() and sa != sb:
        motivos.append(f"sangría de {sa} a {sb} espacios")
    na, nb = a.count("\n"), b.count("\n")
    if na > nb:
        motivos.append("salto de línea quitado" if na - nb == 1 else f"{na - nb} saltos de línea quitados")
    elif nb > na:
        motivos.append("salto de línea añadido" if nb - na == 1 else f"{nb - na} saltos de línea añadidos")
    duros = lambda t: sum(t.count(ch) for ch in "\u00a0\u202f\u2009\u200a")
    if duros(b) > duros(a):
        motivos.append("espacio que no parte línea")
    if re.search(r'\S  +\S', a) and not re.search(r'\S  +\S', b):
        motivos.append("espacio doble quitado")
    if a.rstrip(" ") != a and b.rstrip(" ") == b and a.strip() != b.strip() or (a != a.rstrip() and b == b.rstrip() and a.strip() == b.strip() and sa == sb):
        motivos.append("espacio final quitado")
    if re.search(r'["“”]', a) and "«" in b:
        motivos.append("comillas españolas")
    return f" ({', '.join(motivos)})" if motivos else ""


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


def nombres_textos(z, hoja):
    """Texto → nombre de la forma que lo lleva, en el dibujo de la hoja del cuadro (para marcar los cambios)."""
    ruta = dibujo_de_hoja(z, hoja) if hoja else None
    nombres = {}
    if ruta and ruta in z.namelist():
        for a in ANCLA.finditer(z.read(ruta).decode("utf-8")):
            for cuerpo in re.findall(r'<xdr:txBody>(.*?)</xdr:txBody>', a.group(0), re.S):
                t = " ".join(html.unescape("".join(re.findall(r'<a:t>([^<]*)</a:t>', p_)))
                             for p_ in re.findall(r'<a:p>.*?</a:p>', cuerpo, re.S))
                nombres[re.sub(r'\s+', " ", t).strip()] = nombre_forma(a.group(0))
    return nombres


def comparar_libros(zo, zf, idioma_="es", hoja_cuadro=None):
    """Avisos de lo que ha cambiado del original al maquetado en textos y cifras (no en la colocación ni en
    el formato de letra): datos que faltan, datos cambiados, formatos de número, series y textos. Los de la hoja
    del cuadro llevan marca (celdas o forma) para verlos en Excel."""
    faltan, cambios, info = [], [], []
    forma_de = nombres_textos(zf, hoja_cuadro)

    def m_celdas(hoja, refs):
        return marca(refs) if hoja == hoja_cuadro else ""

    def m_forma(texto):
        return marca(forma=forma_de[texto]) if texto in forma_de else ""
    # 1. Datos de las hojas
    co, cf = celdas_libro(zo), celdas_libro(zf)
    for hoja, celdas in co.items():
        if hoja not in cf:
            faltan.append(f"falta la hoja «{hoja}» con {len(celdas)} datos")
            continue
        fin = cf[hoja]
        perdidas = [r for r in celdas if r not in fin]
        # Las que el paso 1 pasó a cuadros de texto («Cuadro 2.1», unidades: Memoria 2.1; FUENTE y notas: Memoria 3.2)
        # no se han perdido. Se buscan dentro del texto de las formas solo por letras y cifras: FUENTES se maqueta
        # («(a) Se…» → «a⇥Se…», punto final, «FUENTE:» en mayúsculas)
        def clave(t):
            return re.sub(r'[\W_]+', "", t).lower()
        en_formas = [clave(t) for t in textos_libro(zf)]
        movidas = [r for r in perdidas if hoja == hoja_cuadro and len(clave(celdas[r][0])) >= 3
                   and any(clave(celdas[r][0]) in t for t in en_formas)]
        if movidas:
            info.append("pasados de celdas a cuadros de texto: " + lista_corta(f"{r} («{recortar(celdas[r][0].strip(), 25)}»)" for r in movidas))
            perdidas = [r for r in perdidas if r not in movidas]
        if perdidas:
            faltan.append((f"faltan {len(perdidas)} datos" if len(perdidas) > 1 else "falta 1 dato")
                          + f" en la hoja «{hoja}»: "
                          + lista_corta(f"{r} («{recortar(' '.join(celdas[r][0].split()), 25)}»)" for r in perdidas)
                          + m_celdas(hoja, perdidas))
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
                f"{r} {resaltar(celdas[r][0], fin[r][0])}{explicar(celdas[r][0], fin[r][0])}"
                for r in refs) + m_celdas(hoja, refs))
        formatos = {}
        for r in celdas:
            if r in fin and sin_relleno_codigo(celdas[r][1]) != sin_relleno_codigo(fin[r][1]):
                formatos.setdefault((celdas[r][1], fin[r][1]), []).append(r)
        for (a, b), refs in formatos.items():
            que = "fechas" if re.search(r'[ymd]', re.sub(r'"[^"]*"|\[[^\]]*\]', "", b), re.I) else "formato de números"
            cambios.append(f"{que} en «{hoja}»: {len(refs)} celda(s) ({lista_corta(refs[:3])}) "
                           f"de «{a}» a «{b}»" + m_celdas(hoja, refs))
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
                                   + f" (en «{recortar(mejor, 50)}»)" + m_forma(mejor))
                continue
            if op in ("delete", "replace"):
                i1 += separado(a[i1:i2])
                if i1 == i2 and op == "delete":
                    continue
            sa, sb = " ".join(a[i1:i2]), " ".join(b[j1:j2])
            if not sa and not sb:
                continue
            if not sb:
                faltan.append(f"falta «{recortar(sa)}» en «{recortar(t, 50)}»" + m_forma(mejor))
            elif not sa:
                info.append(f"Añadido «{recortar(sb)}» en «{recortar(mejor, 50)}»" + m_forma(mejor))
            else:
                # Letra a letra: si solo se han quitado letras o cifras (además de signos), es que falta algo
                ops = difflib.SequenceMatcher(None, sa, sb, autojunk=False).get_opcodes()
                quitado = "".join(sa[x1:x2] for o, x1, x2, _, _ in ops if o == "delete")
                if all(o in ("equal", "delete") for o, *_ in ops) and re.search(r'\w\w', quitado):
                    faltan.append(f"falta «{recortar(quitado.strip())}» en «{recortar(t, 50)}»" + m_forma(mejor))
                else:
                    cambios.append(f"{tipo_cambio(sa, sb)}: {resaltar(sa, sb)}" + m_forma(mejor))
    for t in sueltos:
        # Un texto repartido en varios cuadros: están todas sus palabras
        palabras = Counter(w.lower() for u in resto_f for w in u.split(" "))
        if all(palabras[w.lower()] for w in t.split(" ")):
            continue
        faltan.append(f"falta el texto «{recortar(t)}»")
    movidos = {re.sub(r'\s+', " ", v[0]).strip().lower() for c_ in co.values() for v in c_.values()}
    # Un cuadro de texto hecho con celdas del original (FUENTES desde celdas bajo el cuadro): no es nuevo
    claves_celdas = [k for k in (re.sub(r'[\W_]+', "", v[0]).lower() for c_ in co.values() for v in c_.values()) if len(k) >= 3]
    for t in resto_f:
        if any(k in re.sub(r'[\W_]+', "", t).lower() for k in claves_celdas) and re.match(r'\s*(FUENTES?|SOURCES?|NOTAS?)\b', t, re.I):
            continue
        if not any(t.lower() in u.lower() for u in to) and t.lower() not in movidos:
            info.append(f"Texto nuevo: «{recortar(t)}»" + m_forma(t))
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
        lineas = comparar_libros(zo, zf, estado.get("idioma", "es"), estado.get("hoja"))
    return {"trabajo": str(trabajo), **estado, "comparacion": lineas, "comparado": str(actual), "original": str(origen)}


# ---------------------------------------------------------------- herramienta: probar la letra a 7 pt

LETRA_PEQUENA = 7


def letra7(trabajo, pid=None):
    return letra_pequena(trabajo, pid, 7)


def letra65(trabajo, pid=None):
    """Lo mismo a 6,5 pt (petición del usuario, 2026-11-18: el publicado del Memoria 4.2 va a 6,5 pt)."""
    return letra_pequena(trabajo, pid, 6.5)


def letra6(trabajo, pid=None):
    """Lo mismo a 6 pt, el mínimo de la guía (petición del usuario, 2026-11-21: Economía Latinoamericana 05 publicado)."""
    return letra_pequena(trabajo, pid, 6)


def letra_pequena(trabajo, pid=None, cuerpo=LETRA_PEQUENA):
    """Rehace los pasos 2, 3 y 4 (los que haya hasta la versión elegida) con la letra de las celdas a 7 pt, desde
    la versión del paso 1, y lo guarda como una versión nueva: las de 7,5 pt se quedan para volver a ellas
    (petición del usuario, 2026-11-17: probar 7 pt en cuadros con muchas columnas y quedarse con lo mejor)."""
    global CUERPO_CELDA
    estado = leer_estado(trabajo)
    hechos = [p["titulo"] for p in estado["pasos"][:estado["actual"] + 1]]
    if CELDAS not in hechos:
        raise Fallo("Antes hay que hacer el paso «Celdas»: la prueba de letra lo rehace con la letra más pequeña")
    _, pasos = nombres(trabajo)
    n1 = max(p["n"] for p in estado["pasos"][:estado["actual"] + 1] if p["titulo"] == RETICULA_Y_TEXTOS)
    base = pasos / estado["pasos"][n1]["archivo"]
    hoja = estado.get("hoja") or "Cuadro datos"
    anterior = CUERPO_CELDA
    CUERPO_CELDA = cuerpo
    try:
        with zipfile.ZipFile(base) as z:
            propuestas = []
            cambios, detalle, cuadro = celdas(z, hoja, estado.get("idioma", "es"), propuestas, pub_de(pid),
                                              col_reticula_autor(trabajo, estado))
        todo = dict(cambios)
        if CABECERAS in hechos:
            intermedio = io.BytesIO()
            reescribir_zip(base, intermedio, todo)
            with zipfile.ZipFile(intermedio) as z:
                cambios, det = cabeceras(z, hoja, cuadro, publicacion(pid))
            todo.update(cambios)
            detalle += det
        if LINEAS_Y_FONDOS in hechos:
            intermedio = io.BytesIO()
            reescribir_zip(base, intermedio, todo)
            with zipfile.ZipFile(intermedio) as z:
                cambios, det = lineas_y_fondos(z, hoja, cuadro, pub_de(pid))
            todo.update(cambios)
            detalle += det
        # Las propuestas ya aplicadas (título en minúsculas…) se vuelven a aplicar; las del paso «Celdas» rehecho
        # que son las mismas quedan como aplicadas (sin botón)
        reaplicadas = []
        for prop in propuestas_aplicadas(estado):
            intermedio = io.BytesIO()
            reescribir_zip(base, intermedio, todo)
            with zipfile.ZipFile(intermedio) as z:
                try:
                    cambios, det = aplicar_en(z, prop)
                except Fallo:
                    continue
            todo.update(cambios)
            reaplicadas.append(prop)
            detalle += [l.replace("Propuesta aplicada", "Propuesta aplicada antes, aplicada de nuevo", 1) for l in det]
    finally:
        CUERPO_CELDA = anterior
    rehechos = ["Celdas"] + [t for t in (CABECERAS, LINEAS_Y_FONDOS) if t in hechos]
    detalle.insert(0, f"Letra de las celdas a {str(cuerpo).replace('.0', '').replace('.', ',')} pt: rehechos desde la versión {n1} los pasos "
                      + ", ".join(f"«{t}»" for t in rehechos) + ". Si no te convence, vuelve a la versión anterior (⌘←)")
    # Los avisos de bajar a 7 pt ya no vienen al caso
    detalle = [l for l in detalle if not l.startswith("Aviso: el cuadro tiene")]
    aplica = [f"{estado['actual'] + 1}:{k}" for k, p in enumerate(propuestas) if p in reaplicadas]
    return nuevo_paso(trabajo, f"Letra {str(cuerpo).replace('.0', '').replace('.', ',')} pt", todo, detalle, cuadro, propuestas=propuestas, aplica=aplica)


# ---------------------------------------------------------------- correcciones ortotipográficas (decisión del usuario,
# 2026-11-17, del TERMINADO 1.2): trimestres como en Gráficos, «EE.UU.» → «EEUU», «Mb/d» → «mb/d», años abreviados
# «1973–74» → «1973–1974» y, en la cabecera, minúscula en las palabras con mayúscula de título

SIGLAS = {"EEUU", "EE.UU.", "EE", "UU", "UEM", "UE", "EA", "PIB", "IPC", "IPCA", "IAPC", "IPRI", "BCE", "BDE", "FMI",
          "OCDE", "OPEP", "IA", "TIC", "PYME", "PYMES", "VAB", "EPA", "PMI", "CNMV", "TAE", "TIN", "ICO", "IRPF",
          "IVA", "I+D", "SA", "EBAE", "ROE", "ROA", "NPL", "BBVA", "CCAA", "AAPP", "ISFLSH", "PER", "ETF", "EURIBOR",
          "FED", "INE", "AEAT", "BIS", "BPI", "UK", "US", "USA", "USD", "EUR", "GBP", "JPY", "CNY", "ESG", "TR", "EMU",
          "GDP", "CPI", "HICP", "ECB", "IMF", "OECD", "SME", "SMES", "AI", "UN", "CET1", "LTV", "LTI", "DTI", "DSTI", "SMI", "OIS"}

SIGLAS_ESCRITAS = {"BDE": "BdE", "PYMES": "pymes", "PYME": "pyme", "ROE": "RoE", "EURIBOR": "euríbor", "SMES": "SMEs",
                   "FED": "Fed"}

SIGLAS_SOLO_EN = {"UN", "US"}

NOMBRES_PROPIOS = {
    "ESPAÑA", "EUROPA", "ALEMANIA", "FRANCIA", "ITALIA", "PORTUGAL", "JAPÓN", "CHINA", "INDIA", "BRASIL", "MÉXICO",
    "REINO", "UNIDO", "ESTADOS", "UNIDOS", "LATINOAMÉRICA", "AMÉRICA", "ASIA", "ÁFRICA", "GRECIA", "IRLANDA",
    "BÉLGICA", "AUSTRIA", "SUIZA", "RUSIA", "TURQUÍA", "CANADÁ", "AUSTRALIA", "COREA", "ARGENTINA", "CHILE",
    "COLOMBIA", "PERÚ", "MADRID", "CATALUÑA", "ANDALUCÍA", "OCEANÍA", "NORUEGA", "SUECIA", "DINAMARCA", "FINLANDIA",
    "POLONIA", "HOLANDA", "UCRANIA", "ISRAEL", "ÁFRICA", "SPAIN", "EUROPE", "GERMANY", "FRANCE", "ITALY", "JAPAN",
    "UNITED", "STATES", "KINGDOM", "LATIN", "AMERICA", "EURO", "AREA", "JANUARY", "FEBRUARY", "MARCH", "APRIL",
    "MAY", "JUNE", "JULY", "AUGUST", "SEPTEMBER", "OCTOBER", "NOVEMBER", "DECEMBER",
    # Más países y regiones (leyendas de tartas por países: «G_DO2608_06»)
    "ARABIA", "SAUDÍ", "ARGELIA", "NIGERIA", "LIBIA", "EGIPTO", "MARRUECOS", "TÚNEZ", "ANGOLA", "IRÁN", "IRAK",
    "KUWAIT", "CATAR", "QATAR", "OMÁN", "EMIRATOS", "ÁRABES", "VENEZUELA", "ECUADOR", "URUGUAY", "PARAGUAY",
    "BOLIVIA", "CUBA", "PANAMÁ", "GUATEMALA", "HONDURAS", "NICARAGUA", "AZERBAIYÁN", "KAZAJISTÁN", "INDONESIA",
    "MALASIA", "TAILANDIA", "VIETNAM", "FILIPINAS", "SINGAPUR", "PAKISTÁN", "BANGLADÉS", "SUDÁFRICA", "HUNGRÍA",
    "RUMANÍA", "BULGARIA", "CROACIA", "ESLOVENIA", "ESLOVAQUIA", "CHEQUIA", "LITUANIA", "LETONIA", "ESTONIA",
    "LUXEMBURGO", "MALTA", "CHIPRE", "ISLANDIA", "NEERLANDÉS", "BAJOS", "TRINIDAD", "TOBAGO", "GUINEA", "ECUATORIAL",
    "NIGERIA", "CAMERÚN", "SENEGAL", "GHANA", "KENIA", "ETIOPÍA", "ESCANDINAVIA", "BÁLTICOS", "MAGREB", "GOLFO"}

CON_TILDE = {"MEXICO": "MÉXICO", "SAUDI": "SAUDÍ", "PERU": "PERÚ", "JAPON": "JAPÓN", "CANADA": "CANADÁ",
             "TURQUIA": "TURQUÍA", "BELGICA": "BÉLGICA", "AFRICA": "ÁFRICA", "LATINOAMERICA": "LATINOAMÉRICA",
             "OCEANIA": "OCEANÍA", "TUNEZ": "TÚNEZ", "IRAN": "IRÁN", "OMAN": "OMÁN", "PANAMA": "PANAMÁ",
             "AZERBAIYAN": "AZERBAIYÁN", "KAZAJISTAN": "KAZAJISTÁN", "PAKISTAN": "PAKISTÁN", "SUDAFRICA": "SUDÁFRICA",
             "HUNGRIA": "HUNGRÍA", "RUMANIA": "RUMANÍA", "CAMERUN": "CAMERÚN", "ETIOPIA": "ETIOPÍA", "ARABES": "ÁRABES",
             "ANDALUCIA": "ANDALUCÍA", "CATALUÑA": "CATALUÑA", "BALTICOS": "BÁLTICOS"}

NOMBRES_PROPIOS_SOLO_EN = {"EURO", "AREA", "MAY", "MARCH", "UNITED", "STATES", "KINGDOM", "LATIN", "AMERICA"}

RE_TRIMESTRE = re.compile(
    r'(?<![\w/])(?:(?P<a1>(?:19|20)\d{2})\s*[-/ ]?\s*)?'
    r'(?:(?P<n1>[1-4])\s*(?:er|º|o|ª)?\.?\s*(?:TR|Tr|tr|TRIM\.?|Trim\.?|trim\.?|[Tt]rimestre|TRIMESTRE|T|Q)'
    r'|(?:TR|T|Q)\s*(?P<n2>[1-4])'
    r'|(?P<r>IV|III|II|I)\s*(?:TR|Tr|TRIM\.?|Trim\.?|trim\.?|[Tt]rimestre|TRIMESTRE|T))'
    r'(?:\s*[-/ ]?\s*(?P<a2>(?:19|20)\d{2}|\d{2})(?!\d))?(?![\w])')

ROMANO_TRIMESTRE = {"1": "I", "2": "II", "3": "III", "4": "IV", "I": "I", "II": "II", "III": "III", "IV": "IV"}

NUMERO_TRIMESTRE = {"I": "1", "II": "2", "III": "3", "IV": "4"}

def trimestres(texto, idioma):
    def cambiar(m):
        n = m.group("n1") or m.group("n2") or NUMERO_TRIMESTRE[m.group("r")]
        anio = m.group("a1") or m.group("a2")
        base = f"{ROMANO_TRIMESTRE[n]} TR" if idioma != "en" else f"Q{n}"
        return base + (f" {anio}" if anio else "")
    return RE_TRIMESTRE.sub(cambiar, texto)


# Nombres oficiales de provincias (publicado 2.7, decisión del usuario 2026-11-17)
PROVINCIAS_OFICIALES = [
    (r'(?<![/\w])Vizcaya\b', "Bizkaia"), (r'(?<![/\w])Guipúzcoa\b', "Gipuzkoa"), (r'(?<![/\w])Guipuzcoa\b', "Gipuzkoa"),
    (r'(?<![/\w])Álava\b(?!/)', "Araba/Álava"), (r'(?<![/\w])Orense\b', "Ourense"), (r'(?<![/\w])Gerona\b', "Girona"),
    (r'(?<![/\w])Lérida\b', "Lleida"), (r'(?<![\w])La Coruña\b', "A Coruña"),
    (r'(?<![\w])(?:Islas |Illes )?Baleares\b', "Illes Balears")]

RE_ANIOS_CORTOS = re.compile(r'(?<![\d.,])((?:19|20)\d\d)\s?([–-])\s?(\d\d)(?![\d.,%])')


SIMBOLOS_GRIEGOS = set("ΔΣΠΩΦΨΛΘΓαβγδεσμπρτφχψωλθ")


def minuscula_titulo(texto, idioma="es"):
    """«Respuesta de Política y Eficacia» → «Respuesta de política y eficacia»: las palabras con mayúscula de título
    pasan a minúscula, salvo la primera, las siglas, los nombres propios y los números romanos."""
    propios = (NOMBRES_PROPIOS | LUGARES_Y_INSTITUCIONES | {"ORIENTE", "OCCIDENTE", "PRÓXIMO"}) - (set() if idioma == "en" else NOMBRES_PROPIOS_SOLO_EN)
    primera = [True]
    anterior_propio = [False]

    def palabra(m):
        w = m.group(0)
        mayus = w.upper()
        es_sigla = mayus in SIGLAS and w == mayus
        es_propio = mayus in propios or CON_TILDE.get(mayus, mayus) in propios
        if primera[0] and len(w) == 1 and w in SIMBOLOS_GRIEGOS:
            return w   # «Δ Acum. intangibles»: el símbolo no es la primera palabra (publicado 3.3)
        if primera[0]:
            primera[0] = False
            anterior_propio[0] = es_sigla or es_propio
            return w
        # Tras un nombre propio o una sigla, la palabra con mayúscula forma parte del nombre («Oriente Medio»,
        # «ICO Crecimiento»): se deja. Tras un punto que cierra frase («…bancaria. Proporción»), también; tras una
        # abreviatura («Act. Profesionales»), no
        seguido = anterior_propio[0] and texto[m.start() - 1:m.start()] == " "
        antes = texto[:m.start()].rstrip()
        if antes.endswith((").", "?", "!")) or (antes.endswith(".") and len(re.findall(r"[^\W\d_]+$", antes[:-1])[0] if re.findall(r"[^\W\d_]+$", antes[:-1]) else "") > 4):
            seguido = True
        titulo = len(w) > 1 and w[0].isupper() and w[1:].islower()
        anterior_propio[0] = es_sigla or es_propio or (titulo and seguido)
        if titulo and not es_propio and not es_sigla and not seguido and not ROMANOS_RE.match(w):
            return w.lower()
        return w
    return re.sub(r"[^\W\d_]+", palabra, texto)


CONECTORES_PROPIOS = {"DE", "DEL", "LA", "LAS", "LOS", "Y", "E", "EL", "OF", "THE", "AND"}


def frase_desde_mayusculas(texto, idioma="es"):
    """«PROCEDIMIENTOS CON PARTICIPACIÓN DEL BANCO DE ESPAÑA» → «Procedimientos con participación del Banco de
    España»: todo en minúscula salvo la primera palabra (y la de después de un punto), las siglas, los números
    romanos y los nombres propios. Las palabras de instituciones y lugares («Banco», «Central», «Comunidad»…) solo
    van con mayúscula en cadena («Banco de España», «Banco Central Europeo»); sueltas son palabras corrientes."""
    propios_fuertes = NOMBRES_PROPIOS - (set() if idioma == "en" else NOMBRES_PROPIOS_SOLO_EN)
    propios = propios_fuertes | LUGARES_Y_INSTITUCIONES
    palabras = list(re.finditer(r"[^\W\d_]+", texto))
    es_propio = [CON_TILDE.get(m.group(0).upper(), m.group(0).upper()) in propios for m in palabras]
    # Cadenas de palabras propias unidas por espacios y conectores («de», «del»…)
    mayuscula = [False] * len(palabras)
    k = 0
    while k < len(palabras):
        if not es_propio[k]:
            k += 1
            continue
        cadena, j = [k], k + 1
        while j < len(palabras):
            if es_propio[j] and not texto[palabras[j - 1].end():palabras[j].start()].strip():
                cadena.append(j)
                j += 1
            elif palabras[j].group(0).upper() in CONECTORES_PROPIOS and j + 1 < len(palabras) and es_propio[j + 1] \
                    and not texto[palabras[j - 1].end():palabras[j + 1].start()].replace(palabras[j].group(0), "").strip():
                j += 1
            else:
                break
        fuertes = any(CON_TILDE.get(palabras[i].group(0).upper(), palabras[i].group(0).upper()) in propios_fuertes for i in cadena)
        if fuertes or len(cadena) >= 2:
            for i in cadena:
                mayuscula[i] = True
        k = j
    salida, pos = [], 0
    for i, m in enumerate(palabras):
        w = m.group(0)
        salida.append(texto[pos:m.start()])
        pos = m.end()
        mayus = w.upper()
        antes = texto[:m.start()].rstrip()
        if mayus in SIGLAS and w == mayus and not (idioma != "en" and mayus in SIGLAS_SOLO_EN):
            nueva = SIGLAS_ESCRITAS.get(mayus, w)
            nueva = nueva if len(nueva) == len(w) else w
        elif len(w) > 1 and w == mayus and ROMANOS_RE.match(w):
            nueva = w
        elif i == 0 or mayuscula[i] or antes.endswith((".", "?", "!")):
            nueva = w[0].upper() + w[1:].lower()
        else:
            nueva = w.lower()
        salida.append(nueva if len(nueva) == len(w) else w)
    salida.append(texto[pos:])
    return "".join(salida)


def recasar_textos(textos, de, a):
    """Cambia mayúsculas y minúsculas en estos trozos de texto (los <t> de una celda o una forma, en orden) para que
    lo que decía `de` diga `a`, sin mirar los espacios y saltos (la celda pudo partirse en líneas o sangrarse).
    None si el texto ya no es el de la propuesta."""
    if len(de) != len(a) or any(x.isspace() != y.isspace() or x.lower() != y.lower() for x, y in zip(de, a)):
        return None
    pares = [(x, y) for x, y in zip(de, a) if not x.isspace()]
    salida, i = [], 0
    for t in textos:
        trozo = []
        for ch in t:
            if ch.isspace():
                trozo.append(ch)
                continue
            if i >= len(pares) or pares[i][0] != ch:
                return None
            trozo.append(pares[i][1])
            i += 1
        salida.append("".join(trozo))
    return salida if i == len(pares) else None


def recasar_xml(xml, de, a, forma=True):
    """El XML (una forma o un <si>) con el cambio de mayúsculas `de` → `a` en sus textos; None si no cuadra."""
    patron = r'(<a:t>|<a:t\b[^>]*>)(.*?)(</a:t>)' if forma else r'(<t>|<t\b[^>]*[^/]>)(.*?)(</t>)'
    limpio = re.sub(r'<rPh\b.*?</rPh>', "", xml, flags=re.S) if not forma else xml
    trozos = [html.unescape(m.group(2)) for m in re.finditer(patron, limpio, re.S)]
    nuevos = recasar_textos(trozos, de, a)
    if nuevos is None:
        return None
    it = iter(nuevos)
    return re.sub(patron, lambda m: m.group(1) + html.escape(next(it), quote=False) + m.group(3), limpio, flags=re.S)


# Más nombres propios para cuadros: provincias, comunidades e islas (2.7, 2.9) e instituciones (Memoria 3.1)
LUGARES_Y_INSTITUCIONES = {
    "ÁLAVA", "ALBACETE", "ALICANTE", "ALMERÍA", "ASTURIAS", "ÁVILA", "BADAJOZ", "BARCELONA", "BURGOS", "CÁCERES",
    "CÁDIZ", "CANTABRIA", "CASTELLÓN", "CIUDAD", "REAL", "CÓRDOBA", "CUENCA", "GIRONA", "GRANADA", "GUADALAJARA",
    "GIPUZKOA", "GUIPÚZCOA", "HUELVA", "HUESCA", "JAÉN", "CORUÑA", "RIOJA", "PALMAS", "LEÓN", "LLEIDA", "LUGO",
    "MÁLAGA", "MURCIA", "NAVARRA", "OURENSE", "ORENSE", "PALENCIA", "PONTEVEDRA", "SALAMANCA", "SEGOVIA", "SEVILLA",
    "SORIA", "TARRAGONA", "TENERIFE", "TERUEL", "TOLEDO", "VALENCIA", "VALLADOLID", "BIZKAIA", "VIZCAYA", "ZAMORA",
    "ZARAGOZA", "CEUTA", "MELILLA", "BALEARS", "BALEARES", "ILLES", "CANARIAS", "ARAGÓN", "CASTILLA", "MANCHA",
    "EXTREMADURA", "GALICIA", "PAÍS", "VASCO", "EUSKADI", "COMUNIDAD", "VALENCIANA", "ARABA", "CRUZ", "SANTA",
    "BANCO", "CENTRAL", "EUROPEO", "EUROPEA", "FEDERAL", "RESERVA", "MONETARIO", "INTERNACIONAL", "MUNDIAL",
    "COMISIÓN", "CONSEJO", "PARLAMENTO", "TESORO", "MINISTERIO", "TRIBUNAL", "AUTORIDAD", "BANCARIA", "ORMUZ",
    "HORMUZ", "IRAQ", "UE", "OPEP"}
ROMANOS_RE = re.compile(r'(?=[IVXLC]+$)M*(C[MD]|D?C{0,3})(X[CL]|L?X{0,3})(I[XV]|V?I{0,3})$')


def corregir_texto(texto, idioma="es", cabecera=False, provincias=False):
    """Las correcciones ortotipográficas automáticas; devuelve el texto y la lista de lo que ha cambiado."""
    cambios = []
    nuevo = trimestres(texto, idioma)
    if nuevo != texto:
        cambios.append("trimestres")
    if idioma != "en":
        n2 = re.sub(r'\bEE\.\s?UU\.?', "EEUU", nuevo)
        if n2 != nuevo:
            cambios.append("EEUU")
        nuevo = n2
    if idioma != "en" and provincias:
        # Solo si la celda es la provincia sola (con su llamada a nota o asterisco): «Banco Bilbao Vizcaya Argentaria»
        # no se toca
        solo = re.fullmatch(r'(\s*)(.+?)(\s*(?:\([a-z]\)|\*)?\s*)', nuevo)
        if solo:
            nombre = solo.group(2)
            for viejo, oficial in PROVINCIAS_OFICIALES:
                if re.fullmatch(viejo, nombre):
                    nuevo = solo.group(1) + oficial + solo.group(3)
                    cambios.append("nombre oficial de provincia")
                    break
    # Barra entre expresiones de varias palabras, con espacios: «Deuda total/Activo total» → «Deuda total / Activo
    # total» (publicado 3.2); entre palabras sueltas, pegada («mb/d», «Deuda/PIB»)
    def barra(m):
        return f"{m.group(1)} / {m.group(2)}" if " " in m.group(1).strip() and " " in m.group(2).strip() else m.group(0)
    n2 = re.sub(r'([^()\[\],;:/\n]*\S)/(\S[^()\[\],;:/\n]*)', barra, nuevo)
    if n2 != nuevo:
        cambios.append("espacios a los lados de la barra")
    nuevo = n2
    n2 = re.sub(r'\bMb/d\b', "mb/d", nuevo)
    if n2 != nuevo:
        cambios.append("mb/d")
    nuevo = n2
    n2 = RE_ANIOS_CORTOS.sub(lambda m: f"{m.group(1)}{m.group(2)}{m.group(1)[:2]}{m.group(3)}"
                             if int(m.group(3)) > int(m.group(1)[2:]) else m.group(0), nuevo)
    if n2 != nuevo:
        cambios.append("años completos")
    nuevo = n2
    if cabecera:
        n2 = minuscula_titulo(nuevo, idioma)
        if n2 != nuevo:
            cambios.append("minúsculas")
        nuevo = n2
    return nuevo, cambios


def corregir_forma(xml, idioma="es"):
    """Las correcciones en cada trozo de texto de una forma (título, unidades, FUENTES)."""
    hechos = []

    def t(m):
        antes = html.unescape(m.group(2))
        nuevo, cambios = corregir_texto(antes, idioma)
        if cambios:
            hechos.append(f"«{antes.strip()[:40]}» → «{nuevo.strip()[:40]}»")
        return m.group(1) + html.escape(nuevo, quote=False) + m.group(3)
    return re.sub(r'(<a:t(?:\s[^>]*)?>)([^<]*)(</a:t>)', t, xml), hechos



def marca(celdas=(), forma=None):
    """Marca invisible al final de un aviso con lo que hay que enseñar en Excel: la app la quita al mostrarlo y, al
    pulsar el aviso, selecciona esas celdas (o esa forma) en Excel (petición del usuario, 2026-11-17)."""
    if forma:
        return f" ⟦forma:{forma}⟧"
    celdas = [c for c in celdas if c]
    return f" ⟦{' '.join(celdas)}⟧" if celdas else ""

# ---------------------------------------------------------------- herramienta: línea oscura para separar conceptos

LINEAS_OSCURAS = "Líneas oscuras"


def linea_oscura(trabajo, pid=None, filas=""):
    """Pone la línea oscura (blanco matiz 5) encima de estas filas del cuadro («7,10,13»), en todo su ancho salvo las
    columnas de separación, para separar conceptos (petición del usuario, 2026-11-17: publicado del 2.9). Las filas
    salen de la selección de Excel. Deja una versión nueva."""
    estado = leer_estado(trabajo)
    requiere(estado, [LINEAS_Y_FONDOS], "«Línea oscura»")
    cuadro = next((p.get("cuadro") for p in reversed(estado["pasos"][:estado["actual"] + 1]) if p.get("cuadro")), None)
    if not cuadro:
        raise Fallo("No sé dónde está el cuadro: vuelve a hacer el paso «Celdas»")
    # De cada zona de la selección («$A$7», «$A$7:$C$9», «$A$7;$A$10»), su primera fila
    pedidas = sorted({int(m.group(1)) for m in (re.search(r'(\d+)', zona) for zona in re.split(r'[;,]', filas)) if m})
    c1, f1, c2, f2 = cuadro["c1"], cuadro["f1"], cuadro["c2"], cuadro["f2"]
    primera, fin_cab = cuadro["primera"], cuadro["fin_cabecera"]
    validas = [f for f in pedidas if fin_cab + 1 < f <= f2]
    if not validas:
        raise Fallo(f"Selecciona en Excel alguna celda de la fila que empieza el concepto nuevo (filas {fin_cab + 2} a {f2} "
                    "del cuadro): la línea oscura va encima de ella")
    _, pasos = nombres(trabajo)
    base = pasos / estado["pasos"][estado["actual"]]["archivo"]
    hoja = estado.get("hoja") or "Cuadro datos"
    with zipfile.ZipFile(base) as z:
        ruta_hoja = hoja_de(z, hoja)
        hoja_xml = z.read(ruta_hoja).decode("utf-8")
        _, compartidos = leer_compartidos(z)
        estilos = Estilos(z.read("xl/styles.xml").decode("utf-8"))
        todas = celdas_hoja(hoja_xml, compartidos)
        ancho_col = anchos_columnas(hoja_xml)
        separaciones = {c for c in range(primera + 1, c2 + 1) if ancho_col(c) < COLUMNA_ESTRECHA
                        and not any(todas.get((c, f), {}).get("texto", "").strip() for f in range(f1, f2 + 1))}
        nuevos = {}
        for f in validas:
            for c in range(primera, c2 + 1):
                if ancho_col(c) == 0 or c in separaciones:
                    continue
                for fila, lado in ((f, "top"), (f - 1, "bottom")):
                    s_ = nuevos.get((c, fila), todas.get((c, fila), {}).get("s", 0))
                    lados = estilos.borde_de(s_)
                    lados[lado] = LINEA_OSCURA
                    nuevos[(c, fila)] = estilos.variante(s_, borde=lados)
        hoja_xml = con_estilo(hoja_xml, nuevos)
        cambios = {ruta_hoja: hoja_xml.encode("utf-8"), "xl/styles.xml": estilos.resultado().encode("utf-8")}
    detalle = [f"Línea oscura (blanco matiz 5) para separar conceptos, encima de {'las filas' if len(validas) > 1 else 'la fila'} "
               + ", ".join(map(str, validas)) + marca([ref(primera, f) for f in validas])]
    fuera = [f for f in pedidas if f not in validas]
    if fuera:
        detalle.append(f"Aviso: sin línea en la{'s' if len(fuera) > 1 else ''} fila{'s' if len(fuera) > 1 else ''} "
                       + ", ".join(map(str, fuera)) + " (fuera del cuerpo del cuadro o primera fila de datos)")
    return nuevo_paso(trabajo, LINEAS_OSCURAS, cambios, detalle, cuadro)



# ---------------------------------------------------------------- herramienta: aplicar una propuesta de un aviso

PROPUESTA_APLICADA = "Propuesta aplicada"


def aplicar(trabajo, pid=None, cual=""):
    """Aplica la propuesta «n:k» (paso n, propuesta k) que un aviso dejó sin hacer —título en mayúsculas, minúsculas
    de título en la primera columna— sobre la versión actual, como una versión nueva (petición del usuario,
    2026-11-17: un botón para aprobar el cambio propuesto)."""
    estado = leer_estado(trabajo)
    try:
        n, k = (int(x) for x in cual.split(":"))
        paso = next(p for p in estado["pasos"][:estado["actual"] + 1] if p["n"] == n)
        prop = paso["propuestas"][k]
    except (ValueError, StopIteration, KeyError, IndexError):
        raise Fallo("Esa propuesta no está en la versión actual: vuelve a la versión del aviso o rehaz el paso")
    if any(cual in p.get("aplica", []) for p in estado["pasos"][:estado["actual"] + 1]):
        raise Fallo("Esa propuesta ya está aplicada")
    _, pasos = nombres(trabajo)
    base = pasos / estado["pasos"][estado["actual"]]["archivo"]
    with zipfile.ZipFile(base) as z:
        cambios, detalle = aplicar_en(z, prop)
    cuadro = next((p.get("cuadro") for p in reversed(estado["pasos"][:estado["actual"] + 1]) if p.get("cuadro")), None)
    return nuevo_paso(trabajo, PROPUESTA_APLICADA, cambios, detalle, cuadro, aplica=[cual])


def propuestas_aplicadas(estado):
    """Las propuestas aplicadas hasta la versión actual (para rehacerlas si se rehacen los pasos: «letra a 7 pt»)."""
    hechas = []
    for p in estado["pasos"][:estado["actual"] + 1]:
        for cual in p.get("aplica", []):
            n, k = (int(x) for x in cual.split(":"))
            origen = next((q for q in estado["pasos"] if q["n"] == n), None)
            if origen and k < len(origen.get("propuestas", [])):
                hechas.append(origen["propuestas"][k])
    return hechas


def aplicar_en(z, prop):
    """(cambios, detalle) de aplicar la propuesta sobre el libro abierto `z`."""
    cambios, detalle = {}, []
    if prop["tipo"] == "forma":
        ruta = dibujo_de_hoja(z, prop["hoja"])
        dibujo = z.read(ruta).decode("utf-8")
        anclas = [a for a in ANCLA.finditer(dibujo) if nombre_forma(a.group(0)) == prop["forma"]]
        nueva = recasar_xml(anclas[0].group(0), prop["de"], prop["a"]) if len(anclas) == 1 else None
        if nueva is None:
            raise Fallo(f"El texto de «{prop['forma']}» ya no es el de la propuesta (¿lo has cambiado a mano?): no lo toco")
        cambios[ruta] = (dibujo[:anclas[0].start()] + nueva + dibujo[anclas[0].end():]).encode("utf-8")
        detalle.append(f"Propuesta aplicada ({prop['que']}): «{recortar(prop['a'].replace(chr(10), ' ').strip(), 140)}»"
                       + marca(forma=prop["forma"]))
    else:
        ruta_hoja = hoja_de(z, prop["hoja"])
        hoja_xml = z.read(ruta_hoja).decode("utf-8")
        comp_xml, compartidos = leer_compartidos(z)
        todas = celdas_hoja(hoja_xml, compartidos)
        nuevas_si, hechas, no = list(compartidos), [], []
        for r, de, a in prop["cambios"]:
            m = RE_REF.match(r)
            x = todas.get((col_num(m.group(1)), int(m.group(2))))
            v = re.search(r'<v>(\d+)</v>', x["xml"]) if x and x["tipo"] == "s" else None
            nueva = recasar_xml(compartidos[int(v.group(1))], de, a, forma=False) if v else None
            if nueva is None:
                no.append(r)
                continue
            nuevas_si.append(nueva)
            celda = x["xml"].replace(v.group(0), f"<v>{len(nuevas_si) - 1}</v>", 1)
            hoja_xml = hoja_xml.replace(x["xml"], celda, 1)
            hechas.append(f"{r} «{a.strip()[:35]}»")
        if not hechas:
            raise Fallo("Los textos ya no son los de la propuesta (¿los has cambiado a mano?): no toco nada")
        comp = re.sub(r'(<sst\b[^>]*>).*(</sst>)', lambda m: m.group(1) + "".join(nuevas_si) + m.group(2), comp_xml,
                      count=1, flags=re.S)
        comp = re.sub(r'\buniqueCount="\d+"', f'uniqueCount="{len(nuevas_si)}"', comp, count=1)
        cambios = {ruta_hoja: hoja_xml.encode("utf-8"), "xl/sharedStrings.xml": comp.encode("utf-8")}
        detalle.append(f"Propuesta aplicada ({prop['que']}): " + "; ".join(hechas[:8])
                       + (f" y {len(hechas) - 8} más" if len(hechas) > 8 else "") + marca([h.split(" ", 1)[0] for h in hechas]))
        if no:
            detalle.append("Aviso: sin tocar, su texto ya no es el de la propuesta: " + ", ".join(no) + marca(no))
    return cambios, detalle


def pendiente(nombre):
    def paso(trabajo, pid=None):
        raise Fallo(f"El paso «{nombre}» todavía no está hecho: lo construimos a continuación.")
    return paso


def nombre_terminado(origen, carpeta):
    stem = origen.stem
    if re.search(r'\bORIGINALES\b', stem):
        base = re.sub(r'\bORIGINALES\b', "EXCEL", stem)
    elif re.search(r'\bORIGINAL\b', stem):
        base = re.sub(r'\bORIGINAL\b', "EXCEL", stem)
    else:
        base = stem + " EXCEL"   # «… EXCEL.xlsx» (petición del usuario, 2026-11-18; antes «TERMINADO(S)»)
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
    """Guarda la copia de trabajo como «… EXCEL.xlsx» junto al original y borra todo lo generado: las dos
    copias de trabajo y la carpeta de pasos. El original del autor no se toca."""
    trabajo, pasos = nombres(trabajo)
    estado = leer_estado(trabajo)
    origen = Path(estado.get("origen", ""))
    carpeta = origen.parent if origen.parent.is_dir() else trabajo.parent
    destino = nombre_terminado(origen if origen.name else trabajo, carpeta)
    shutil.copyfile(copia_actual(trabajo), destino)
    os.chmod(destino, 0o644)
    return {"terminado": str(destino), "original": str(origen) if origen.name else None,
            "ancla_original": ancla_reticula_original(origen, estado.get("hoja")),
            "encuadre_pt": encuadre_cuadro(destino, estado.get("hoja")), "borrados": borrar_generados(trabajo)}


def desborde(archivo, hoja, cuadro):
    """Avisos si el cuadro se sale de la retícula: de ancho (las columnas del cuadro) o de alto (hasta el final de la
    tabla o del cuadro de FUENTES, lo que acabe más abajo)."""
    avisos = []
    try:
        with zipfile.ZipFile(archivo) as z:
            hoja = hoja or hoja_cuadro(z)[0]
            x = z.read(hoja_de(z, hoja)).decode("utf-8")
            mdw = digito_maximo(z.read("xl/styles.xml").decode("utf-8"))
            ancho_col = anchos_columnas(x)
            altos, defecto = altos_filas(z, hoja)
            ancho_ret, alto_ret = (v / EMU_PT for v in tamano(plantilla()["grupo"], escala_grupo=True))
            ancho = sum(round(ancho_col(c) * mdw) for c in range(1, cuadro["c2"] + 1))
            fin_tabla = sum(altos.get(f, defecto) for f in range(cuadro["f2"])) / EMU_PT
            fin_fuentes = 0.0
            ruta = dibujo_de_hoja(z, hoja)
            if ruta and ruta in z.namelist():
                dibujo = z.read(ruta).decode("utf-8")
                medir = medidas_hoja(z, hoja, dibujo)
                for m in ANCLA.finditer(dibujo):
                    a = m.group(0)
                    lineas_f = html.unescape(texto_forma(a)).strip().split("\n")
                    if es_reticula(a) or not ROTULO.match(lineas_f[0]):
                        continue
                    xx, y, w, h = medir(a)
                    # por su texto, no por su marco (el de la plantilla mide 30 mm aunque lleve una línea), como al
                    # comprimir las filas
                    alto_texto = sum(max(1, math.ceil(len(l) / 150)) for l in lineas_f) * 8.5 + 4
                    if y / EMU_PT < alto_ret:
                        fin_fuentes = max(fin_fuentes, y / EMU_PT + min(h / EMU_PT, alto_texto))
    except (OSError, zipfile.BadZipFile, KeyError, Fallo, AttributeError):
        return avisos
    if ancho > ancho_ret + 1:
        avisos.append(f"Aviso: el cuadro mide {ancho:.0f} pt de ancho y la retícula {ancho_ret:.0f}: se sale {ancho - ancho_ret:.0f} pt "
                      "(prueba una letra más pequeña o revisa las columnas a su medida)")
    abajo = max(fin_tabla, fin_fuentes)
    if abajo > alto_ret + 1:
        que = "FUENTES acaba" if fin_fuentes >= fin_tabla else "la tabla acaba"
        avisos.append(f"Aviso: el cuadro no cabe en la retícula: {que} a {abajo:.0f} pt y la retícula mide {alto_ret:.0f}; "
                      f"sobran {abajo - alto_ret:.0f} pt (prueba una letra más pequeña, acorta las notas de FUENTES o "
                      "quita filas vacías)")
    return avisos


def encuadre_cuadro(archivo, hoja=None):
    """[ancho, alto] en pt de lo que ocupa el cuadro desde A1: el ancho de la retícula y, de alto, hasta el final del
    cuadro de FUENTES (o de la forma más baja dentro de la retícula). La app encuadra Excel en eso, no en la retícula
    entera, que es tan alta como la página (petición del usuario, 2026-11-21). None si no se puede medir."""
    try:
        with zipfile.ZipFile(archivo) as z:
            hoja = hoja or hoja_cuadro(z)[0]
            ruta = dibujo_de_hoja(z, hoja)
            if not ruta or ruta not in z.namelist():
                return None
            dibujo = z.read(ruta).decode("utf-8")
            medir = medidas_hoja(z, hoja, dibujo)
            ancho_ret, alto_ret = (v / EMU_PT for v in tamano(plantilla()["grupo"], escala_grupo=True))
            abajo = 0.0
            for m in ANCLA.finditer(dibujo):
                a = m.group(0)
                if es_reticula(a):
                    continue
                x, y, w, h = medir(a)
                if y / EMU_PT < alto_ret and x / EMU_PT < ancho_ret:
                    abajo = max(abajo, (y + h) / EMU_PT)
            return [round(ancho_ret, 1), round(min(max(abajo, 100), alto_ret), 1)] if abajo else None
    except (OSError, zipfile.BadZipFile, KeyError, Fallo, AttributeError):
        return None


def ancla_reticula_original(origen, hoja=None):
    """[fila, columna] (desde 1) donde empieza la retícula del autor (o su pastilla) en el original: la app desplaza
    ahí el original para que se vea el mismo cuadro que el EXCEL (petición del usuario, 2026-11-21). [1, 1] si no."""
    try:
        with zipfile.ZipFile(origen) as z:
            hoja = hoja or hoja_cuadro(z)[0]
            ruta = dibujo_de_hoja(z, hoja)
            if not ruta or ruta not in z.namelist():
                return [1, 1]
            anclas = [m.group(0) for m in ANCLA.finditer(z.read(ruta).decode("utf-8"))]
            for buscar in (es_reticula, es_pastilla):
                for a in anclas:
                    if buscar(a):
                        d = re.search(r'<xdr:from>\s*<xdr:col>(\d+)</xdr:col>.*?<xdr:row>(\d+)</xdr:row>', a, re.S)
                        if d:
                            return [int(d.group(2)) + 1, int(d.group(1)) + 1]
    except (OSError, zipfile.BadZipFile, KeyError, Fallo):
        pass
    return [1, 1]


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
            lista[i] = {**p, **nueva}   # los ajustes propios de la publicación (cabecera_letra_blanca…) se quedan
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


# ---------------------------------------------------------------- herramienta: igualar al modelo

IGUAL_AL_MODELO = "Igual que el modelo"
RE_PAISES = re.compile(r"argentin\w*|brasil\w*|brazil\w*|chile\w*|chilen\w*|colombi\w*|m[eé]xic\w*|per[uú]\w*|peruan\w*|"
                       r"costa\s+rica|costarric\w*|guatemal\w*|hondur\w*|nicarag\w*|rep[uú]blica\s+dominicana|dominican\w*|"
                       r"el\s+salvador|salvadore\w*|\bcard\b", re.I)


def norm_texto(t):
    """Texto comparable entre países y semestres: sin países, cifras, años ni espacios de más, en minúsculas."""
    t = RE_PAISES.sub("X", html.unescape(t or "").lower())
    t = re.sub(r"\d[\d.,\-–]*", "N", t)
    return re.sub(r"\s+", " ", t).strip()


def palabras_libro(z, hoja):
    x = z.read(hoja_de(z, hoja)).decode("utf-8")
    textos = [v["texto"] for v in celdas_hoja(x, leer_compartidos(z)[1]).values() if v["texto"].strip() and not es_cifra(v)]
    return {w for t in textos for w in re.findall(r"[a-záéíóúñü]{3,}", norm_texto(t))}


def buscar_modelo(trabajo, estado):
    """El EXCEL terminado más parecido (mismo cuadro de otro país u otro semestre): en la carpeta del original y en
    «Modelos» (junto a ella o en el proyecto). (ruta, parecido) o (None, 0)."""
    origen = Path(estado["origen"])
    base = re.sub(r"\s+(ORIGINALES|ORIGINAL)\b.*$", "", origen.stem)
    carpetas = [origen.parent, origen.parent / "Modelos", PROYECTO / "Modelos"]
    candidatos = []
    for carpeta in carpetas:
        if not carpeta.is_dir():
            continue
        for f in carpeta.glob("*.xlsx"):
            if f.name.startswith("~$") or f.stem.startswith(base) or (carpeta == origen.parent and " EXCEL" not in f.stem):
                continue
            candidatos.append(f)
    if not candidatos:
        return None, 0
    with zipfile.ZipFile(origen) as z:
        mias = palabras_libro(z, estado.get("hoja") or hoja_cuadro(z)[0])
    mejor = (0, 0, None)
    for f in candidatos:
        try:
            with zipfile.ZipFile(f) as z:
                suyas = palabras_libro(z, hoja_cuadro(z)[0])
        except (zipfile.BadZipFile, KeyError, Fallo, OSError):
            continue
        parecido = len(mias & suyas) / max(1, len(mias | suyas))
        mejor = max(mejor, (round(parecido, 2), f.stat().st_mtime, f))
    return (mejor[2], mejor[0]) if mejor[2] and mejor[0] >= 0.5 else (None, mejor[0])


def colores_tema(z):
    """Colores del tema del libro en el orden de los índices de Excel (0 lt1, 1 dk1, 2 lt2, 3 dk2, 4-9 acentos…)."""
    ruta = next((n for n in z.namelist() if re.match(r"xl/theme/theme\d*\.xml$", n)), None)
    if not ruta:
        return []
    xml = z.read(ruta).decode("utf-8")
    col = {}
    for clave in ("dk1", "lt1", "dk2", "lt2", "accent1", "accent2", "accent3", "accent4", "accent5", "accent6", "hlink", "folHlink"):
        m = re.search(rf'<a:{clave}>\s*<a:(?:srgbClr val|sysClr\b[^>]*\blastClr)="([0-9A-Fa-f]{{6}})"', xml)
        col[clave] = m.group(1).upper() if m else "000000"
    return [col[k] for k in ("lt1", "dk1", "lt2", "dk2", "accent1", "accent2", "accent3", "accent4", "accent5", "accent6", "hlink", "folHlink")]


def colores_a_rgb(xml, tema):
    """Colores del tema (theme="n" tint="t") pasados a RGB: el modelo y el cuadro pueden llevar temas distintos."""
    def cambiar(m):
        etiqueta = m.group(0)
        t = re.search(r'\btheme="(\d+)"', etiqueta)
        if not t or int(t.group(1)) >= len(tema):
            return etiqueta
        tinte = re.search(r'\btint="([-\d.Ee]+)"', etiqueta)
        rgb = matiz(tema[int(t.group(1))], float(tinte.group(1))) if tinte else tema[int(t.group(1))]
        nombre = re.match(r"<(\w+)", etiqueta).group(1)
        return f'<{nombre} rgb="FF{rgb}"/>'
    return re.sub(r'<(?:color|fgColor|bgColor)\b[^>]*/>', cambiar, xml)


def formato_de(est, tema, i):
    """(fuente, relleno, borde, alineación) del formato `i`, con los colores en RGB."""
    xf = est.xf(i)
    fid = re.search(r'\bfillId="(\d+)"', xf)
    bid = re.search(r'\bborderId="(\d+)"', xf)
    rell = est.rellenos[int(fid.group(1))] if fid and int(fid.group(1)) < len(est.rellenos) else est.rellenos[0]
    bord = est.bordes[int(bid.group(1))] if bid and int(bid.group(1)) < len(est.bordes) else est.bordes[0]
    return (colores_a_rgb(est.fuente_de(i), tema), colores_a_rgb(rell, tema), colores_a_rgb(bord, tema), est.alineacion(i))


def con_formato_de(est, i, formato):
    """Índice de un formato como el `i` (su formato de número) con la fuente, el relleno, el borde y la alineación
    de otro libro."""
    fuente, rell, bord, al = formato
    ids = []
    for lista, nuevos, xml in ((est.fuentes, est.nuevas_fuentes, fuente), (est.rellenos, est.nuevos_rellenos, rell),
                               (est.bordes, est.nuevos_bordes, bord)):
        todos = lista + nuevos
        if xml in todos:
            ids.append(todos.index(xml))
        else:
            nuevos.append(xml)
            ids.append(len(todos))
    xf = est.xf(i)
    apertura = re.match(r'<xf\b[^>]*?(/?)>', xf)
    atributos = apertura.group(0)[3:-(2 if apertura.group(1) else 1)]
    dentro = "" if apertura.group(1) else xf[apertura.end():xf.rindex("</xf>")]
    for nombre, valor in (("fontId", ids[0]), ("fillId", ids[1]), ("borderId", ids[2]), ("applyFont", 1), ("applyFill", 1),
                          ("applyBorder", 1), ("applyAlignment", 1)):
        atributos = re.sub(rf'\s{nombre}="[^"]*"', "", atributos) + f' {nombre}="{valor}"'
    dentro = re.sub(r'<alignment\b[^>]*/>', "", dentro)
    dentro = "<alignment" + "".join(f' {k}="{v}"' for k, v in al.items()) + "/>" + dentro if al else dentro
    nuevo = f"<xf{atributos}>{dentro}</xf>" if dentro else f"<xf{atributos}/>"
    todos = est.xfs + est.nuevos_xfs
    if nuevo in todos:
        return todos.index(nuevo)
    est.nuevos_xfs.append(nuevo)
    return len(todos)


def estructura(z, hoja, cuadro):
    """Las piezas del cuadro para emparejarlo con otro: filas (cabecera, cuerpo con su concepto, bloque de arriba) y
    columnas por su papel (primera, de datos, solo del bloque, separaciones)."""
    x = z.read(hoja_de(z, hoja)).decode("utf-8")
    todas = sin_filas_ocultas(celdas_hoja(x, leer_compartidos(z)[1]), x)
    ancho = anchos_columnas(x)
    c1, f1, c2, f2 = cuadro["c1"], cuadro["f1"], cuadro["c2"], cuadro["f2"]
    primera, fin_cab = cuadro["primera"], cuadro["fin_cabecera"]
    bloque = cuadro.get("bloque_arriba", [])
    txt = lambda c, f: todas.get((c, f), {}).get("texto", "").strip()
    vis = [c for c in range(c1, c2 + 1) if ancho(c) > 0]
    datos = [c for c in vis if c != primera and any(txt(c, f) for f in range(f1, f2 + 1))]
    solo_bloque = [c for c in vis if c != primera and c not in datos and any(txt(c, f) for f in bloque)]
    cuerpo = [(f, norm_texto(txt(primera, f))) for f in range(fin_cab + 1, f2 + 1)
              if any(txt(c, f) for c in range(c1, c2 + 1))]
    return {"todas": todas, "vis": vis, "primera": primera, "datos": datos, "solo_bloque": solo_bloque,
            "separaciones": [c for c in vis if c != primera and c not in datos and c not in solo_bloque],
            "cabecera": [f for f in range(f1, fin_cab + 1) if any(txt(c, f) for c in range(c1, c2 + 1))],
            "cuerpo": cuerpo, "bloque": bloque, "bloque_grupos": cuadro.get("bloque_grupos", [])}


def igualar_modelo(trabajo, pid=None):
    """Copia del EXCEL terminado del mismo cuadro (otro país u otro semestre, con sus retoques a mano) los anchos, los
    altos y el formato de cada celda, emparejando filas por concepto y columnas por su papel; los textos y los
    datos son los del cuadro (petición del usuario, 2026-11-21)."""
    estado = leer_estado(trabajo)
    hechos = [p["titulo"] for p in estado["pasos"][:estado["actual"] + 1]]
    if LINEAS_Y_FONDOS not in hechos:
        raise Fallo("Antes hay que hacer los cuatro pasos: el modelo se copia sobre el cuadro ya maquetado")
    modelo, parecido = buscar_modelo(trabajo, estado)
    if not modelo:
        raise Fallo("No encuentro un EXCEL terminado del mismo cuadro (en la carpeta del original o en «Modelos»)"
                    + (f": el más parecido lo es solo en un {parecido:.0%}" if parecido else ""))
    _, pasos = nombres(trabajo)
    base = pasos / estado["pasos"][estado["actual"]]["archivo"]
    hoja = estado.get("hoja") or "Cuadro datos"
    cuadro_t = next((p.get("cuadro") for p in reversed(estado["pasos"][:estado["actual"] + 1]) if p.get("cuadro")), None)
    pub = pub_de(pid)
    with zipfile.ZipFile(modelo) as zm:
        hoja_m = hoja_cuadro(zm)[0]
        _, _, cuadro_m = celdas(zm, hoja_m, idioma(modelo.name), [], pub)
        em = estructura(zm, hoja_m, cuadro_m)
        est_m = Estilos(zm.read("xl/styles.xml").decode("utf-8"))
        tema_m = colores_tema(zm)
        xm = zm.read(hoja_de(zm, hoja_m)).decode("utf-8")
        ancho_m, mdw_m = anchos_columnas(xm), digito_maximo(est_m.xml)
        altos_m, defecto_m = altos_filas(zm, hoja_m)
        celdas_m = celdas_hoja(xm, leer_compartidos(zm)[1])
    detalle, avisos = [f"Modelo: «{modelo.name}» ({parecido:.0%} de palabras en común)"], []
    with zipfile.ZipFile(base) as z:
        ruta_hoja = hoja_de(z, hoja)
        hoja_xml = z.read(ruta_hoja).decode("utf-8")
        est = Estilos(z.read("xl/styles.xml").decode("utf-8"))
        et = estructura(z, hoja, cuadro_t)
        mdw = digito_maximo(est.xml)
        todas_t = celdas_hoja(hoja_xml, leer_compartidos(z)[1])
        ancho_t = anchos_columnas(hoja_xml)
        dibujo = z.read(dibujo_de_hoja(z, hoja)).decode("utf-8") if dibujo_de_hoja(z, hoja) else ""
        altos_v = altos_filas(z, hoja)
        caja = medidas_hoja(z, hoja, dibujo) if dibujo else None
    # Columnas por su papel
    cols = {et["primera"]: em["primera"]}
    for papel in ("datos", "solo_bloque"):
        if len(et[papel]) == len(em[papel]):
            cols.update(zip(et[papel], em[papel]))
        elif et[papel] or em[papel]:
            avisos.append(f"columnas {'de datos' if papel == 'datos' else 'del bloque de arriba'}: {len(et[papel])} aquí y "
                          f"{len(em[papel])} en el modelo, sin copiar")
    # Filas: cabecera de abajo arriba, cuerpo por concepto, bloque por orden
    filas = dict(zip(reversed(et["cabecera"]), reversed(em["cabecera"])))
    filas.update(zip(et["bloque"], em["bloque"]))
    a, b = [t for _, t in em["cuerpo"]], [t for _, t in et["cuerpo"]]
    sin_pareja = []
    for op, i1, i2, j1, j2 in difflib.SequenceMatcher(None, a, b, autojunk=False).get_opcodes():
        if op == "equal" or (op == "replace" and i2 - i1 == j2 - j1):
            filas.update({et["cuerpo"][j][0]: em["cuerpo"][i][0] for i, j in zip(range(i1, i2), range(j1, j2))})
        elif j2 > j1:
            sin_pareja += [et["cuerpo"][j][0] for j in range(j1, j2)]
    # Anchos
    nuevos_anchos = {}
    for ct, cm in cols.items():
        pt = round(ancho_m(cm) * mdw_m)
        nuevos_anchos[ct] = ancho_comun(pt, mdw, digito_windows(est.xml))
    # Lo que falte o sobre para medir lo mismo que el modelo (Cos_01 no tiene columna aparte para el valor del bloque
    # de arriba y Arg_01 sí), a la primera columna
    pt_de = lambda w, d_: round(w * d_)
    total_m = sum(pt_de(ancho_m(c), mdw_m) for c in em["vis"])
    total_t = sum(pt_de(nuevos_anchos[c], mdw) if c in nuevos_anchos else pt_de(ancho_t(c), mdw) for c in et["vis"])
    if abs(total_m - total_t) >= 1 and et["primera"] in nuevos_anchos:
        pt_primera = pt_de(nuevos_anchos[et["primera"]], mdw) + total_m - total_t
        nuevos_anchos[et["primera"]] = ancho_comun(pt_primera, mdw, digito_windows(est.xml))
        detalle.append(f"La primera columna, {total_m - total_t:+.0f} pt para medir lo mismo que el modelo ({total_m:.0f} pt)")
    hoja_xml = poner_anchos(hoja_xml, nuevos_anchos)
    # Altos
    altos = {ft: round(altos_m.get(fm - 1, defecto_m) / EMU_PT, 2) for ft, fm in filas.items()}
    entre_t = [f for f in range(et["bloque"][-1] + 1, cuadro_t["f1"])] if et["bloque"] else []
    entre_m = [f for f in range(em["bloque"][-1] + 1, cuadro_m["f1"])] if em["bloque"] else []
    hueco_m = sum(altos_m.get(f - 1, defecto_m) for f in entre_m) / EMU_PT
    for f in entre_t:
        if altos_v[0].get(f - 1, altos_v[1]) > 0:
            altos[f] = round(hueco_m / max(1, sum(1 for g in entre_t if altos_v[0].get(g - 1, altos_v[1]) > 0)), 2)

    def poner_alto(m):
        fila = m.group(0)
        f = int(re.search(r'\br="(\d+)"', fila).group(1))
        if f not in altos:
            return fila
        fila = re.sub(r'\s(ht|customHeight)="[^"]*"', "", fila)
        return fila[:-1].rstrip("/") + f' ht="{altos[f]:g}" customHeight="1"' + ("/>" if fila.endswith("/>") else ">")
    hoja_xml = re.sub(r'<row\b[^>]*?/?>', poner_alto, hoja_xml)
    # Formato de cada celda emparejada
    formatos = {}
    pares_col = dict(cols)
    for st, sm in zip(et["separaciones"], em["separaciones"]):
        pares_col.setdefault(st, sm)
    for ft, fm in filas.items():
        if ft in et["bloque"]:
            continue
        for ct, cm in pares_col.items():
            formatos[(ct, ft)] = con_formato_de(est, todas_t.get((ct, ft), {}).get("s", 0),
                                                formato_de(est_m, tema_m, celdas_m.get((cm, fm), {}).get("s", 0)))
    # Bloque de arriba: por tablitas (concepto ↔ concepto, valor ↔ valor, lo de en medio como lo de en medio)
    for (et_e, et_v), (em_e, em_v) in zip(et["bloque_grupos"], em["bloque_grupos"]):
        medio_m = [c for c in range(em_e + 1, em_v) if ancho_m(c) > 0]
        for ft in et["bloque"]:
            fm = filas.get(ft)
            if fm is None:
                continue
            for ct in range(et_e, et_v + 1):
                cm = em_e if ct == et_e else em_v if ct == et_v else (medio_m[0] if medio_m else em_e)
                formatos[(ct, ft)] = con_formato_de(est, todas_t.get((ct, ft), {}).get("s", 0),
                                                    formato_de(est_m, tema_m, celdas_m.get((cm, fm), {}).get("s", 0)))
    hoja_xml = con_estilo(hoja_xml, formatos)
    cambios = {ruta_hoja: hoja_xml.encode("utf-8"), "xl/styles.xml": est.resultado().encode("utf-8")}
    # Sitio del cuadro y de FUENTES con los altos nuevos
    if dibujo and caja:
        f_ini = et["bloque"][0] if et["bloque"] else cuadro_t["f1"]
        todos_altos = {f: v for f, v in altos.items()}
        dibujo_nuevo, notas, (alto_hueco, altos_encima) = colocar_cuadro(dibujo, caja, altos_v, todos_altos, f_ini, cuadro_t["f2"])
        if dibujo_nuevo != dibujo:
            cambios[dibujo_de_hoja_ruta(z_ruta=base, hoja=hoja)] = dibujo_nuevo.encode("utf-8")
    detalle.append(f"Copiados del modelo: anchos de {len(nuevos_anchos)} columnas, altos de {len(altos)} filas y formato de "
                   f"{len(formatos)} celdas (letra, alineación, fondos y líneas); los textos y las cifras son los de este cuadro")
    if sin_pareja:
        detalle.append("Aviso: filas sin pareja en el modelo (conceptos nuevos o cambiados), como las deja la app: "
                       + ", ".join(f"«{todas_t.get((et['primera'], f), {}).get('texto', '').strip()[:30]}»" for f in sin_pareja[:6])
                       + ("…" if len(sin_pareja) > 6 else "") + marca([ref(et["primera"], f) for f in sin_pareja]))
    for a_ in avisos:
        detalle.append("Aviso: " + a_)
    return nuevo_paso(trabajo, IGUAL_AL_MODELO, cambios, detalle, cuadro_t)


def dibujo_de_hoja_ruta(z_ruta, hoja):
    with zipfile.ZipFile(z_ruta) as z:
        return dibujo_de_hoja(z, hoja)


ORDENES = {"empezar": empezar, "estado": lambda t: {"trabajo": t, **leer_estado(t)}, "ir": ir, "reiniciar": reiniciar,
           "paso1": paso1, "paso2": paso2,
           "paso3": paso3, "paso4": paso4, "letra7": letra7, "letra65": letra65, "letra6": letra6, "modelo": igualar_modelo, "linea_oscura": linea_oscura, "aplicar": aplicar,
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
