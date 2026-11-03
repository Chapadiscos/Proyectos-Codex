#!/usr/bin/env python3
"""Motor de «Gráficos Excel BdE»: maqueta paso a paso el Excel del autor.

Trabaja sobre una copia; cada paso deja su versión en la carpeta de pasos
para poder ir hacia delante y hacia atrás. Toca el .xlsx por dentro (XML),
sin Excel, y deja intacto todo lo que el paso no cambia.

Uso (la salida es siempre JSON):
  maquetar_excel.py empezar <origen.xlsx>
  maquetar_excel.py estado  <trabajo.xlsx>
  maquetar_excel.py ir      <trabajo.xlsx> <n>
  maquetar_excel.py reiniciar <trabajo.xlsx>
  maquetar_excel.py paso1   <trabajo.xlsx> <id_publicacion>
  maquetar_excel.py paso2   <trabajo.xlsx> [id_publicacion]
  maquetar_excel.py info    <archivo.xlsx>
  maquetar_excel.py publicaciones
  maquetar_excel.py guardar_publicacion '<json>'
  maquetar_excel.py borrar_publicacion <id>
  maquetar_excel.py paletas [actualizar]
"""
import html
import io
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

HOJA_GRAFICO = "Gráfico"
# Paletas de colores (temas) que Excel tiene instaladas
CARPETA_PALETAS = Path.home() / "Library/Group Containers/UBF8T346G9.Office/User Content.localized/Themes.localized/Theme Colors"
CLAVES_PALETA = ["dk1", "lt1", "dk2", "lt2", "accent1", "accent2", "accent3", "accent4", "accent5", "accent6"]
ANCLA = re.compile(r'<xdr:(twoCellAnchor|oneCellAnchor|absoluteAnchor)\b[^>]*>.*?</xdr:\1>', re.S)


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
    return "en" if re.search(r'(^|[ _\-.])Ing([ _\-.]|$)', Path(nombre).stem) else "es"


def empezar(origen):
    origen = Path(origen).resolve()
    if not origen.exists():
        raise Fallo(f"No existe {origen}")
    trabajo, pasos = nombres(origen.with_name(origen.stem + " maquetado.xlsx"))
    if pasos.exists():
        raise Fallo(f"Ya hay una maquetación empezada: {pasos.name}. Bórrala o sigue con ella.")
    pasos.mkdir()
    v0 = pasos / "00 Copia exacta.xlsx"
    shutil.copyfile(origen, v0)
    solo_lectura(v0)
    shutil.copyfile(origen, trabajo)
    estado = {"origen": str(origen), "idioma": idioma(origen.name), "actual": 0,
              "pasos": [{"n": 0, "titulo": "Copia exacta del original", "archivo": v0.name, "detalle": []}]}
    guardar_estado(trabajo, estado)
    return {"trabajo": str(trabajo), **estado}


def reiniciar(trabajo):
    """Vuelve a empezar desde el original del autor: borra todas las versiones, rehace «00 Copia exacta»
    con el original (si sigue en su sitio) y la copia de trabajo pasa a ser esa versión."""
    estado = leer_estado(trabajo)
    _, pasos = nombres(trabajo)
    for p in estado["pasos"]:
        (pasos / p["archivo"]).unlink(missing_ok=True)
    v0 = pasos / "00 Copia exacta.xlsx"
    origen = Path(estado.get("origen", ""))
    if not origen.is_file():
        raise Fallo(f"No encuentro el original del autor ({origen}): no puedo reiniciar")
    shutil.copyfile(origen, v0)
    solo_lectura(v0)
    shutil.copyfile(origen, trabajo)
    estado["actual"] = 0
    estado["pasos"] = [{"n": 0, "titulo": "Copia exacta del original", "archivo": v0.name, "detalle": []}]
    guardar_estado(trabajo, estado)
    return {"trabajo": str(trabajo), **estado}


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


def nuevo_paso(trabajo, titulo, cambios, detalle):
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
    estado["pasos"].append({"n": n, "titulo": titulo, "archivo": archivo, "detalle": detalle})
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


def dibujo_de_hoja(z, hoja):
    wb = z.read("xl/workbook.xml").decode("utf-8")
    m = re.search(r'<sheet\b(?=[^>]*\bname="' + re.escape(hoja) + r'")(?=[^>]*\br:id="([^"]+)")[^>]*/>', wb)
    if not m:
        raise Fallo(f"No hay hoja «{hoja}»")
    hoja_xml = rels(z, "xl/workbook.xml")[m.group(1)][1]
    for tipo, destino in rels(z, hoja_xml).values():
        if tipo.endswith("/drawing"):
            return destino
    raise Fallo(f"La hoja «{hoja}» no tiene dibujos")


def nombre_forma(ancla):
    return re.search(r'<xdr:cNvPr\b[^>]*\bname="([^"]*)"', ancla).group(1)


def es_reticula(ancla):
    cuerpo = ancla[ancla.find("</xdr:from>"):]
    return cuerpo.lstrip().find("<xdr:grpSp>") >= 0 and ancla.count('prst="line"') >= 40


def es_pastilla(ancla):
    """Rectángulo de color sin texto pegado arriba a la izquierda: la pastilla de la publicación."""
    if "<xdr:sp " not in ancla[:600] and "<xdr:sp>" not in ancla[:600]:
        return False
    if re.search(r'<a:t>\s*[^<\s]', ancla) or 'prst="rect"' not in ancla:
        return False
    sppr = re.search(r'<xdr:spPr>.*?</xdr:spPr>', ancla, re.S)
    desde = re.search(r'<xdr:from>\s*<xdr:col>(\d+)</xdr:col>\s*<xdr:colOff>(\d+)</xdr:colOff>\s*<xdr:row>(\d+)</xdr:row>', ancla)
    return bool(sppr and "<a:solidFill>" in sppr.group(0) and desde and desde.groups() == ("0", "0", "0"))


def tamano(ancla, escala_grupo=False):
    """Tamaño en EMU. Para la retícula, el de diseño (chExt): la del archivo de retículas está al 99 %."""
    if escala_grupo:
        m = re.search(r'<a:chExt cx="(\d+)" cy="(\d+)"/>', ancla)
    else:
        m = re.search(r'<a:ext cx="(\d+)" cy="(\d+)"/>', ancla)
    return int(m.group(1)), int(m.group(2))


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


def publicacion(pid):
    for p in CONFIG["publicaciones"]:
        if p["id"] == pid:
            return p
    raise Fallo(f"No conozco la publicación «{pid}»")


# ---------------------------------------------------------------- pasos

RETICULA_Y_TEXTOS = "Retícula, pastilla y textos"


def paso1(trabajo, pid):
    """Retícula, pastilla y textos en un solo paso (una sola versión): primero la retícula y la pastilla y,
    sobre el resultado, los textos."""
    estado = leer_estado(trabajo)
    _, pasos = nombres(trabajo)
    base = pasos / estado["pasos"][estado["actual"]]["archivo"]
    with zipfile.ZipFile(base) as z:
        cambios, detalle = reticula_y_pastilla(z, pid)
    intermedio = io.BytesIO()
    reescribir_zip(base, intermedio, cambios)
    with zipfile.ZipFile(intermedio) as z:
        cambios_textos, detalle_textos = textos(z, estado)
    return nuevo_paso(trabajo, RETICULA_Y_TEXTOS, {**cambios, **cambios_textos}, detalle + detalle_textos)


def reticula_y_pastilla(z, pid):
    """Retícula y pastilla de la publicación desde el archivo de retículas, al fondo y en A1;
    se borran las del autor por si las ha tocado."""
    pub = publicacion(pid)

    ret = CONFIG["reticula"]
    with zipfile.ZipFile(PROYECTO / ret["archivo"]) as zr:
        dibujo_ret = zr.read(dibujo_de_hoja(zr, ret["hoja"])).decode("utf-8")
    anclas_ret = {nombre_forma(a.group(0)): a.group(0) for a in ANCLA.finditer(dibujo_ret)}
    if ret["grupo"] not in anclas_ret or ret["pastilla_modelo"] not in anclas_ret:
        raise Fallo("No encuentro la retícula o la pastilla en el archivo de retículas")
    grupo, modelo = anclas_ret[ret["grupo"]], anclas_ret[ret["pastilla_modelo"]]

    ruta = dibujo_de_hoja(z, HOJA_GRAFICO)
    dibujo = z.read(ruta).decode("utf-8")

    detalle = []
    quitar = []
    for m in ANCLA.finditer(dibujo):
        a = m.group(0)
        if es_reticula(a):
            quitar.append(m.span())
            detalle.append(f"Borrada la retícula del autor «{nombre_forma(a)}» ({tamano(a)[0] / 360000:.2f} × {tamano(a)[1] / 360000:.2f} cm)")
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
    cx, cy = tamano(grupo, escala_grupo=True)
    nueva_ret, sig = renumerar(anclar_arriba_izquierda(grupo, cx, cy), sig, "Retícula")
    px, py = tamano(modelo)
    nueva_pas, sig = renumerar(anclar_arriba_izquierda(color_relleno(modelo, pub["color"]), px, py), sig, "Pastilla")
    detalle.append(f"Retícula del archivo de retículas en A1, al fondo ({cx / 360000:.2f} × {cy / 360000:.2f} cm)")
    detalle.append(f"Pastilla de {pub['nombre']} en A1, encima de la retícula (color {pub['color']}, {px / 360000:.2f} × {py / 360000:.2f} cm)")

    # Primero en el dibujo = al fondo; la pastilla va justo encima de la retícula.
    m = re.search(r'<xdr:wsDr\b[^>]*>', dibujo)
    dibujo = dibujo[:m.end()] + nueva_ret + nueva_pas + dibujo[m.end():]
    return {ruta: dibujo.encode("utf-8")}, detalle


def requiere(estado, titulos, paso):
    """Los pasos van en orden: el anterior tiene que estar en la versión de la que se parte. `titulos` admite
    también los nombres de antes (las versiones ya hechas con los pasos separados siguen valiendo)."""
    if not any(p["titulo"] in titulos for p in estado["pasos"][:estado["actual"] + 1]):
        raise Fallo(f"Antes hay que hacer el paso «{titulos[0]}»: {paso} parte de él")


def textos(z, estado):
    """Textos en Roboto: «Gráfico NN» y título con el marco de la plantilla, en su sitio; títulos de panel,
    ejes, leyendas, unidades, interior del gráfico y fuentes con su letra, donde los dejó el autor."""
    ret = CONFIG["reticula"]
    with zipfile.ZipFile(PROYECTO / ret["archivo"]) as zr:
        dibujo_ret = zr.read(dibujo_de_hoja(zr, ret["hoja"])).decode("utf-8")
    anclas_ret = {nombre_forma(a.group(0)): a.group(0) for a in ANCLA.finditer(dibujo_ret)}
    marco_grafico, marco_titulo = anclas_ret.get(ret["marco_grafico"]), anclas_ret.get(ret["marco_titulo"])
    if not marco_grafico or not marco_titulo:
        raise Fallo("No encuentro los marcos «Gráfico X» y «Título del gráfico» en el archivo de retículas")
    ancho_ret = tamano(anclas_ret[ret["grupo"]], escala_grupo=True)[0]
    alto_pastilla = tamano(anclas_ret[ret["pastilla_modelo"]])[1]

    cambios, detalle = {}, []
    ruta = dibujo_de_hoja(z, HOJA_GRAFICO)
    dibujo = z.read(ruta).decode("utf-8")
    filas = altos_filas(z, HOJA_GRAFICO)

    # Textos de la hoja
    hechos = set()
    partes = []
    for a in partes_dibujo(dibujo):
        if not ANCLA.fullmatch(a) or es_reticula(a) or es_pastilla(a) or "<c:chart " in a or "<xdr:txBody>" not in a:
            partes.append(a)
            continue
        texto = texto_forma(a)
        if not texto.strip():
            partes.append(a)
            continue
        x, y = posicion(a)
        corto = html.unescape(texto).replace("\n", " / ")[:60]
        if x >= ancho_ret:
            detalle.append(f"Sin tocar, fuera de la retícula: «{corto}»")
        elif "grafico" not in hechos and RE_GRAFICO.match(texto):
            hechos.add("grafico")
            a = con_marco(a, marco_grafico, filas)
            detalle.append(f"Gráfico NN «{corto}»: Roboto Regular 7 pt, marco y posición de la plantilla")
        elif "titulo" not in hechos and y < alto_pastilla:
            hechos.add("titulo")
            a = con_marco(a, marco_titulo, filas, final_regular=FINAL_TITULO)
            detalle.append(f"Título «{corto}»: Roboto Medium 8,5 pt, marco y posición de la plantilla")
            final = FINAL_TITULO.search(html.unescape(texto))
            if final:
                detalle.append(f"  «{final.group(0).strip()}» al final del título, en Roboto Regular")
        elif RE_FUENTE.match(texto):
            a, notas = maquetar_fuentes(a, estado["idioma"])
            detalle.append(f"Fuentes «{corto}»: Roboto Light 7 pt" + "".join(f"; {n}" for n in notas))
        else:
            a = fijar_letra(a, 800, ROBOTO)
            detalle.append(f"Título de panel «{corto}»: Roboto Regular 8 pt")
        partes.append(a)
    for falta, nombre in (("grafico", "«Gráfico NN»"), ("titulo", "título del gráfico")):
        if falta not in hechos:
            detalle.append(f"Aviso: no encuentro el {nombre}")
    cambios[ruta] = "".join(partes).encode("utf-8")

    # Textos de cada gráfico y de sus formas (unidades)
    relaciones = rels(z, ruta)
    anchos = anchos_graficos(z, dibujo)
    for i, rid in enumerate(re.findall(r'<c:chart\b[^>]*\br:id="([^"]+)"', dibujo), 1):
        ruta_graf = relaciones[rid][1]
        graf, cuentas = maquetar_grafico(z.read(ruta_graf).decode("utf-8"), anchos.get(rid))
        cambios[ruta_graf] = graf.encode("utf-8")
        linea = f"Panel {i}: general e interior Roboto Regular 6 pt"
        if cuentas:
            linea += "; " + ", ".join(cuentas)
        for tipo, ruta_formas in rels(z, ruta_graf).values():
            if tipo.endswith("/chartUserShapes"):
                formas, unidades, otros = maquetar_formas_grafico(z.read(ruta_formas).decode("utf-8"))
                cambios[ruta_formas] = formas.encode("utf-8")
                if unidades:
                    linea += "; unidades 7 pt: " + ", ".join(f"«{u}»" for u in unidades)
                if otros:
                    linea += "; textos interiores 6 pt: " + ", ".join(f"«{u}»" for u in otros)
        detalle.append(linea)
    return cambios, detalle


# ---------------------------------------------------------------- textos

EMU_PT = 12700
ROBOTO, ROBOTO_MEDIUM, ROBOTO_LIGHT = "Roboto", "Roboto Medium", "Roboto Light"
RE_GRAFICO = re.compile(r'\s*(Gráfico|Grafico|Chart|Figure)\s+\S+\s*$', re.I)
RE_FUENTE = re.compile(r'\s*(FUENTES?|SOURCES?|NOTAS?)\b', re.I)
PROPIEDADES_LETRA = re.compile(r'<a:(rPr|endParaRPr|defRPr)\b([^>]*?)(/>|>(.*?)</a:\1>)', re.S)


def fijar_letra(xml, sz, fuente, quitar_negrita=None):
    """Pone tamaño (centésimas de punto) y familia a todas las propiedades de letra. El formato local del
    autor se respeta (cursiva, subrayado, índices y la negrita de una parte del texto); si todo el texto va
    en negrita, se quita, porque el peso lo da la familia (Roboto Medium, Roboto Light). Las letras por
    defecto (defRPr, endParaRPr) van sin negrita."""
    if quitar_negrita is None:
        quitar_negrita = todo_negrita(xml)

    def cambiar(m):
        etiqueta, atributos, dentro = m.group(1), m.group(2), m.group(4) or ""
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


# Final del título que va en Regular: una letra, «cont.» o «cont'd» entre paréntesis
FINAL_TITULO = re.compile(r"\s*(\((?:[A-Za-zÑñ]|cont\.|cont['’]d)\))\s*$", re.I)
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


# ---------------------------------------------------------------- FUENTES (reglas de Gráficos Illus BdE)

ROTULO = re.compile(r'\s*(FUENTES|FUENTE|SOURCES|SOURCE|NOTAS|NOTA)\s*(:|\.|\s|$)', re.I)
NOTA_LETRA = re.compile(r'\s*([a-z])(?:\.|\t)[\t ]*')
SANGRIA_NOTA = round(8.5 * EMU_PT)
PPR_FUENTES = '<a:pPr marL="0" indent="0" algn="l"/>'
PPR_NOTA_LETRA = (f'<a:pPr marL="{SANGRIA_NOTA}" indent="-{SANGRIA_NOTA}" algn="l"><a:tabLst>'
                  f'<a:tab pos="{SANGRIA_NOTA}" algn="l"/></a:tabLst></a:pPr>')
EN_INGLES = {"FUENTE": "SOURCE", "FUENTES": "SOURCES"}


def maquetar_fuentes(ancla, idioma):
    """El marco de FUENTES con las reglas de «Gráficos Illus BdE»:
    - Rótulo FUENTE(S)/SOURCE(S)/NOTA(S) en mayúsculas y con dos puntos; en inglés, FUENTE → SOURCE.
      FUENTE(S)/SOURCE(S) en Roboto Medium y NOTA(S) en Light. Si la primera línea no lo tiene, «FUENTE:».
    - Notas con letra («a.» o «a» + tabulador): letra en Medium, tabulador y sangría francesa de 8,5 pt;
      las líneas siguientes sin letra ni rótulo se unen a la nota.
    - Una línea en blanco tras la fuente (salvo que siga una NOTA) y tras cada NOTA.
    Además, todo en Roboto Light 7 pt respetando el formato local del autor y, en castellano, comillas
    españolas y espacio (que no parte línea) entre la cifra y «%»; en inglés, «%» sin espacio."""
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
    if quitar:
        notas.append("sin la negrita general del autor")
    return ancla, notas


def posicion(ancla):
    m = re.search(r'<a:off x="(-?\d+)" y="(-?\d+)"/>', ancla)
    return (int(m.group(1)), int(m.group(2))) if m else (0, 0)


def hoja_de(z, nombre):
    wb = z.read("xl/workbook.xml").decode("utf-8")
    m = re.search(r'<sheet\b(?=[^>]*\bname="' + re.escape(nombre) + r'")(?=[^>]*\br:id="([^"]+)")[^>]*/>', wb)
    if not m:
        raise Fallo(f"No hay hoja «{nombre}»")
    return rels(z, "xl/workbook.xml")[m.group(1)][1]


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


def con_marco(ancla, marco, filas, final_regular=None):
    """El marco de la plantilla (posición, tamaño, márgenes y letra) con el texto del autor.
    Conserva el id y el nombre de la forma del autor."""
    x, y = posicion(marco)
    if x != 0:
        raise Fallo("Los marcos de la plantilla tienen que empezar en la columna A")
    cx, cy = tamano(marco)
    fila, desp = celda_de(filas, y)
    cuerpo = re.search(r'</xdr:to>(.*)</xdr:twoCellAnchor>', marco, re.S).group(1)
    # Cada línea del autor, un párrafo con el formato de la plantilla y el formato local del autor
    p = re.search(r'<a:p>(.*?)</a:p>', cuerpo, re.S).group(1)
    ppr = re.search(r'<a:pPr\b[^>]*/>|<a:pPr\b[^>]*>.*?</a:pPr>', p, re.S)
    ppr = ppr.group(0) if ppr else ""
    rpr = re.search(r'<a:rPr\b[^>]*/>|<a:rPr\b[^>]*>.*?</a:rPr>', p, re.S).group(0)
    sz = re.search(r'\bsz="(\d+)"', rpr).group(1)
    con_negrita = not todo_negrita(ancla)
    lineas = [[(con_atributos(rpr, formato_local(r, con_negrita)), t) for r, t in linea]
              for linea in lineas_de(ancla) if texto_de(linea).strip()]
    # La última línea puede acabar en algo que va en Roboto Regular, como «(cont.)» en el título
    final = final_regular.search(texto_de(lineas[-1])) if final_regular else None
    if final:
        lineas[-1] = tramo(lineas[-1], final.start(1), len(texto_de(lineas[-1])),
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
            f'<xdr:ext cx="{cx}" cy="{cy}"/>{cuerpo}</xdr:oneCellAnchor>')


def txpr(sz, fuente):
    return (f'<c:txPr><a:bodyPr/><a:lstStyle/><a:p><a:pPr><a:defRPr sz="{sz}" b="0"><a:latin typeface="{fuente}"/>'
            f'<a:ea typeface="{fuente}"/></a:defRPr></a:pPr><a:endParaRPr lang="es-ES"/></a:p></c:txPr>')


def con_txpr(bloque, antes_de, sz, fuente):
    """Si el bloque no tiene su propio c:txPr, lo añade delante de la primera etiqueta de `antes_de`
    (o al final); luego fija la letra en todo el bloque."""
    etiqueta = re.match(r'<(c:\w+)', bloque).group(1)
    # Sin los títulos de dentro, que llevan su propio txPr
    propio = re.sub(r'<c:title>.*?</c:title>|<c:dLbl>.*?</c:dLbl>|<c:legendEntry>.*?</c:legendEntry>', "", bloque, flags=re.S)
    if "<c:txPr>" not in propio and '<c:delete val="1"/>' not in propio:
        sitio = None
        for siguiente in antes_de:
            m = re.search(rf'<c:{siguiente}\b', propio)
            if m:
                sitio = bloque.index(m.group(0), bloque.rfind("</c:dLbl>") + 1 if "</c:dLbl>" in bloque else 0)
                break
        if sitio is None:
            sitio = bloque.rindex(f"</{etiqueta}>")
        bloque = bloque[:sitio] + txpr(sz, fuente) + bloque[sitio:]
    return fijar_letra(bloque, sz, fuente)


def maquetar_grafico(xml, ancho_pt=None):
    cuentas = []
    # Letra general del gráfico (lo que no tenga la suya): interior, 6 pt
    m = re.search(r'</c:chart>\s*(<c:spPr>.*?</c:spPr>)?\s*(<c:txPr>.*?</c:txPr>)?', xml, re.S)
    if m.group(2):
        xml = xml[:m.start(2)] + fijar_letra(m.group(2), 600, ROBOTO) + xml[m.end(2):]
    else:
        xml = xml[:m.end()] + txpr(600, ROBOTO) + xml[m.end():]

    def contar(nombre, n):
        if n:
            cuentas.append(f"{nombre} {n}")

    # Título del propio gráfico: es el título del panel
    n = [0]

    def titulo(m):
        n[0] += 1
        return m.group(1) + con_txpr(m.group(2), ["extLst"], 800, ROBOTO)
    xml = re.sub(r'(<c:chart>\s*)(<c:title>.*?</c:title>)', titulo, xml, count=1, flags=re.S)
    contar("título del panel 8 pt", n[0])

    # Eje de categorías: 7 pt, salvo que se pierda texto (horizontal y alguna palabra que no cabe)
    def categorias(m):
        eje = m.group(0)
        sz, nota = 700, None
        if re.search(r'<c:axPos val="[bt]"/>', eje) and '<c:delete val="1"/>' not in eje:
            sz, nota = cuerpo_categorias(xml, ancho_pt)
        cuentas.append(f"eje de categorías {sz / 100:g} pt".replace(".", ",") + (f" ({nota})" if nota else ""))
        eje = con_txpr(eje, ["crossAx"], sz, ROBOTO)
        # Su título (unidades) sigue a 7 pt
        return re.sub(r'<c:title>.*?</c:title>', lambda t: fijar_letra(t.group(0), 700, ROBOTO), eje, flags=re.S)
    xml = re.sub(r'<c:catAx>.*?</c:catAx>', categorias, xml, flags=re.S)

    for etiqueta, antes, sz, nombre in (
            ("legend", ["extLst"], 700, "leyenda 7 pt"),
            ("valAx", ["crossAx"], 700, "eje de valores 7 pt"),
            ("dateAx", ["crossAx"], 700, "eje de valores 7 pt"), ("serAx", ["crossAx"], 700, "eje de valores 7 pt"),
            ("dLbls", ["dLblPos", "showLegendKey"], 600, "etiquetas de datos 6 pt"),
            ("dTable", ["extLst"], 600, "tabla de datos 6 pt")):
        n = [0]

        def cambiar(m):
            n[0] += 1
            return con_txpr(m.group(0), antes, sz, ROBOTO)
        xml = re.sub(rf'<c:{etiqueta}>.*?</c:{etiqueta}>', cambiar, xml, flags=re.S)
        contar(nombre, n[0])
    # Los ejes se cuentan juntos
    ejes = sum(int(c.split()[-1]) for c in cuentas if c.startswith("eje de valores"))
    cuentas = [c for c in cuentas if not c.startswith("eje de valores")] + ([f"eje de valores 7 pt {ejes}"] if ejes else [])
    return xml, [re.sub(r" (\d+)$", r" (\1)", c) for c in cuentas]



# ---------------------------------------------------------------- paso 3: tamaño y colocación

# Distribución de «Graficos Illus BdE» (Generador V3), en puntos desde arriba de la retícula, con el título del
# gráfico en una línea: dónde empieza el panel 1 si no tiene título de panel (con título, el título va a
# PASTILLA_A_TITULO_PANEL de la pastilla). Cada línea más del título lo baja todo un interlineado del título.
INICIO_SIN_TITULO_PANEL = 50.57
INTERLINEA_TITULO_PANEL = 9.6
MM = 72 / 25.4
SUBIDA_GRAFICO = 0.5 * MM
ENTRE_PANELES = 8.5 * MM
HASTA_FUENTES = 5 * MM
FILAS_PANEL, FILAS_MIN_TRAZADO = 9, 7
TITULO_PANEL_A_GRAFICO = 7.377 * MM   # del final del título de panel al gráfico (Illus, título de 1 línea)
SUBIDA_CON_UNIDADES = 0.7 * MM
UNIDADES_A_GRAFICO = 2 * MM          # del final de las unidades al borde de arriba del trazado
LEYENDA_A_LA_IZQUIERDA = 3 * MM      # el cuadro de la leyenda tiene aire alrededor: así su texto cae en la columna 2
CUERPO_TITULO = 8.5
PASTILLA_A_TITULO_PANEL = 3.8 * MM   # del borde de abajo de la pastilla al texto del título del panel 1 (TERMINADO)
CUERPO_UNIDADES = 7
ALTO_UNIDADES = CUERPO_UNIDADES * 1.2 + 1   # cuadro de una línea (pt)
BASE_UNIDADES = CUERPO_UNIDADES * 0.93      # de arriba del cuadro a la línea de base (ascendente de Roboto)
SEPARACION_CATEGORIAS = 6.0   # del eje a las etiquetas de categorías (pt, medido en Excel)
MARGEN_CATEGORIAS = 4.0       # debajo de la última línea (pt)
NIVEL_CATEGORIAS = 5.0        # además de su línea, cada nivel de más (pt, medido en Excel)
MEDIA_ETIQUETA = 7 * 1.2 / 2  # el número de arriba del eje sobresale medio alto por encima del trazado (pt)
INTERLINEA = 1.2              # alto de línea / cuerpo


def guias_reticula(dibujo):
    """Las dos columnas de la retícula (x, ancho) y el paso de sus filas, en EMU de la hoja."""
    ret = next((a.group(0) for a in ANCLA.finditer(dibujo) if es_reticula(a.group(0))), None)
    if not ret:
        raise Fallo("No hay retícula: haz antes el paso 1")
    g = re.search(r'<a:off x="(-?\d+)" y="(-?\d+)"/>\s*<a:ext cx="(\d+)" cy="(\d+)"/>\s*'
                  r'<a:chOff x="(-?\d+)" y="(-?\d+)"/>\s*<a:chExt cx="(\d+)" cy="(\d+)"/>', ret)
    ox, oy, ex, ey, cx0, cy0, ccx, ccy = map(int, g.groups())
    columnas, filas = [], []
    for f in re.finditer(r'<xdr:(sp|cxnSp)\b.*?</xdr:\1>', ret, re.S):
        t = f.group(0)
        o = re.search(r'<a:off x="(-?\d+)" y="(-?\d+)"/>\s*<a:ext cx="(\d+)" cy="(\d+)"/>', t)
        color = re.search(r'srgbClr val="(\w+)"', t)
        x, y, w, h = map(int, o.groups())
        if color and color.group(1) == "0070C0":
            columnas.append((round(ox + (x - cx0) * ex / ccx), round(w * ex / ccx)))
        elif 'prst="line"' in t and h == 0:
            filas.append(oy + (y - cy0) * ey / ccy)
    if len(columnas) < 2 or len(filas) < 2:
        raise Fallo("La retícula no tiene las dos columnas y las filas que espero")
    filas.sort()
    return sorted(columnas)[:2], round((filas[-1] - filas[0]) / (len(filas) - 1))


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


def alargar(ancla, extra, caja):
    """El objeto `extra` EMU más alto. Con su caja real (la de las celdas, que es la que usa Excel) y ancla
    absoluta: en un ancla de dos celdas, cambiar solo el tamaño de dentro no lo cambia en Excel."""
    x, y, cx, cy = caja(ancla)
    return colocar(ancla, x, y, cx, cy + extra)


def colocar(ancla, x, y, cx, cy):
    """El objeto en una posición y tamaño fijos (EMU desde A1), con ancla absoluta."""
    cuerpo = re.search(r'(?:</xdr:to>|<xdr:ext\b[^>]*/>)(.*)</xdr:(?:twoCellAnchor|oneCellAnchor|absoluteAnchor)>',
                       ancla, re.S).group(1)
    cuerpo = re.sub(r'(<a:off) x="-?\d+" y="-?\d+"/>(\s*<a:ext) cx="\d+" cy="\d+"/>',
                    rf'\1 x="{x}" y="{y}"/>\2 cx="{cx}" cy="{cy}"/>', cuerpo, count=1)
    return (f'<xdr:absoluteAnchor><xdr:pos x="{x}" y="{y}"/><xdr:ext cx="{cx}" cy="{cy}"/>'
            f'{cuerpo}</xdr:absoluteAnchor>')


def medidas_hoja(z, dibujo):
    """Función ancla → (x, y, ancho, alto) en EMU desde A1, por las celdas de anclaje (las que usa Excel; el
    xfrm de dentro puede estar desfasado). Las filas, por su alto; las columnas, con lo que mide una unidad
    de ancho de columna en este dibujo (como en anchos_graficos)."""
    filas = altos_filas(z, HOJA_GRAFICO)
    altos, defecto = filas
    hoja = z.read(hoja_de(z, HOJA_GRAFICO)).decode("utf-8")
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
    return medir


def ancho_numeros_eje(xml, medir):
    """Lo que ocupan a la izquierda los números del eje de valores (pt, aproximado por el dato mayor)."""
    valores = [abs(float(v)) for v in re.findall(r'<c:val>.*?</c:val>', xml, re.S)
               for v in re.findall(r'<c:v>(-?[\d.Ee+-]+)</c:v>', v)]
    negativos = any(float(v) < 0 for v in re.findall(r'<c:val>.*?<c:v>(-[\d.]+)</c:v>', xml, re.S))
    mayor = f"{round(max(valores) * 1.1) if valores else 100:,}".replace(",", ".")
    # Excel deja unos 8 pt entre el número y el eje; si no caben, corre todo el trazado a la derecha
    return medir(("-" if negativos else "") + mayor, 7) + 8


def nombres_series(xml):
    return [html.unescape(v) for v in re.findall(r'<c:ser>.*?<c:tx>.*?<c:v>([^<]*)</c:v>', xml, re.S)]


def disposicion(xml, ancho, alto, dentro, leyenda, medir):
    """Área de trazado interior en `dentro` = (x, y, ancho, alto) y leyenda en `leyenda` = (x, y, ancho
    máximo), todo en pt dentro del gráfico de `ancho` × `alto` pt. La leyenda, con el ancho justo de su
    entrada más larga (una entrada por línea) y el alto de sus entradas."""
    x, y, w, h = dentro
    trazado = ('<c:layout><c:manualLayout><c:layoutTarget val="inner"/><c:xMode val="edge"/><c:yMode val="edge"/>'
               f'<c:x val="{x / ancho:.6f}"/><c:y val="{y / alto:.6f}"/><c:w val="{w / ancho:.6f}"/>'
               f'<c:h val="{h / alto:.6f}"/></c:manualLayout></c:layout>')
    xml = re.sub(r'(<c:plotArea>\s*)(<c:layout>.*?</c:layout>|<c:layout/>)?', lambda m: m.group(1) + trazado,
                 xml, count=1, flags=re.S)
    lx, ly, lmax = leyenda
    clave = 7 + 4 + 6   # muestra de color, separación y márgenes de la leyenda (pt)
    nombres = nombres_series(xml) or ["Serie"]
    lw = min(lmax, max(medir(n, 7) for n in nombres) + clave + 2)
    lineas = sum(lineas_parrafos([n], lw - clave, 7, medir) for n in nombres)
    lh = lineas * 7 * INTERLINEA + len(nombres) * 1.5 + 4

    def cambiar(m):
        lay = ('<c:layout><c:manualLayout><c:xMode val="edge"/><c:yMode val="edge"/>'
               f'<c:x val="{lx / ancho:.6f}"/><c:y val="{ly / alto:.6f}"/><c:w val="{lw / ancho:.6f}"/>'
               f'<c:h val="{min(lh, alto - ly) / alto:.6f}"/></c:manualLayout></c:layout>')
        bloque = re.sub(r'<c:layout>.*?</c:layout>|<c:layout/>', "", m.group(0), count=1, flags=re.S)
        return re.sub(r'(<c:legendPos val="\w+"/>)', lambda p: p.group(1) + lay, bloque, count=1)
    return re.sub(r'<c:legend>.*?</c:legend>', cambiar, xml, count=1, flags=re.S)


def unidades_de(formas):
    """Las anclas de las unidades en las formas del gráfico: cuadros de texto en el 20 % de arriba."""
    return [a for a in re.findall(r'<cdr:relSizeAnchor\b.*?</cdr:relSizeAnchor>', formas, re.S)
            if texto_forma(a).strip()
            and float(re.search(r'<cdr:from>.*?<cdr:y>([^<]+)</cdr:y>', a, re.S).group(1)) < 0.2]


def colocar_unidades(formas, ancla, x, y, ancho, alto, medir):
    """Las unidades en (`x`, `y`) pt dentro del gráfico (x, la línea del eje), en una línea y con el texto
    pegado arriba."""
    texto = html.unescape(texto_forma(ancla)).strip()
    w = min(medir(texto, CUERPO_UNIDADES) + 4, ancho - x)
    nueva = re.sub(r'<cdr:from>.*?</cdr:to>',
                   f'<cdr:from><cdr:x>{x / ancho:.5f}</cdr:x><cdr:y>{y / alto:.5f}</cdr:y></cdr:from>'
                   f'<cdr:to><cdr:x>{(x + w) / ancho:.5f}</cdr:x><cdr:y>{(y + ALTO_UNIDADES) / alto:.5f}</cdr:y></cdr:to>',
                   ancla, count=1, flags=re.S)
    nueva = re.sub(r'(<a:bodyPr\b[^>]*?)\s+anchor="\w+"', r'\1', nueva, count=1)
    nueva = re.sub(r'<a:bodyPr\b', '<a:bodyPr anchor="t" tIns="0" bIns="0"', nueva, count=1) \
        if 'tIns=' not in re.search(r'<a:bodyPr\b[^>]*>', nueva).group(0) else \
        re.sub(r'<a:bodyPr\b', '<a:bodyPr anchor="t"', nueva, count=1)
    return formas.replace(ancla, nueva)


def filas_categorias(xml, trazado, paso_pt):
    """Cuerpo de las categorías (regla del paso 2, con el ancho nuevo del trazado, en pt) y filas de la
    retícula que ocupan debajo del eje: la palabra más larga tiene que caber en su hueco; cada etiqueta se
    parte por palabras."""
    medir = medidor()
    sz, nota = cuerpo_categorias(xml, trazado, sin_disposicion=True)
    lineas = 1
    etiquetas = etiquetas_categorias(xml)
    horizontal = re.search(r'<c:catAx>.*?<c:axPos val="[bt]"/>', xml, re.S)
    if medir and etiquetas and horizontal:
        hueco = trazado / len(etiquetas) - HOLGURA_PT
        lineas = max(lineas_parrafos([e], hueco, sz / 100, medir) for e in etiquetas)
    # Con varios niveles (y sin juntarlos), cada nivel de más va en otra línea debajo
    niveles = niveles_categorias(xml) if horizontal and '<c:noMultiLvlLbl val="1"/>' not in xml else 1
    linea = sz / 100 * INTERLINEA
    alto = SEPARACION_CATEGORIAS + lineas * linea + (niveles - 1) * (linea + NIVEL_CATEGORIAS) + MARGEN_CATEGORIAS
    return sz, nota, lineas + niveles - 1, max(1, int(-(-alto // paso_pt))), alto


def niveles_categorias(xml):
    """Niveles del eje de categorías. Por el rango (la caché puede tener menos: Excel la rehace al abrir):
    con las categorías en filas, cada columna es un nivel."""
    cat = re.search(r'<c:cat>.*?</c:cat>', xml, re.S)
    if not cat or "<c:multiLvlStrRef>" not in cat.group(0):
        return 1
    guardados = max(1, len(re.findall(r'<c:lvl\b', cat.group(0))))
    f = re.search(r'<c:f>([^<]*)</c:f>', cat.group(0))
    rangos = re.findall(r'\$?([A-Z]+)\$?(\d+):\$?([A-Z]+)\$?(\d+)', f.group(1)) if f else []
    if not rangos:
        return guardados

    def columna(letras):
        n = 0
        for c in letras:
            n = n * 26 + ord(c) - 64
        return n
    # Puede ser una unión de trozos: las categorías son las filas (o columnas) de todos juntos
    columnas = columna(rangos[0][2]) - columna(rangos[0][0]) + 1
    filas = sum(int(f2) - int(f1) + 1 for _, f1, _, f2 in rangos)
    return max(guardados, columnas if filas >= columnas else filas)

    def columna(letras):
        n = 0
        for c in letras:
            n = n * 26 + ord(c) - 64
        return n
    c1, f1, c2, f2 = rango.groups()
    columnas, filas = columna(c2) - columna(c1) + 1, int(f2) - int(f1) + 1
    return max(guardados, columnas if filas >= columnas else filas)


def paso2(trabajo, pid=None):
    """Tamaño y colocación de los paneles, uno debajo de otro como en «Graficos Illus BdE»: el área de trazado
    en la primera columna de la retícula y la leyenda en la segunda; 9 filas de alto desde arriba hasta las
    categorías (el trazado, como mínimo 7); títulos de panel encima y FUENTES debajo."""
    estado = leer_estado(trabajo)
    _, pasos = nombres(trabajo)
    base = pasos / estado["pasos"][estado["actual"]]["archivo"]
    requiere(estado, (RETICULA_Y_TEXTOS, "Textos"), "«Tamaño y colocación»")
    ret = CONFIG["reticula"]
    with zipfile.ZipFile(PROYECTO / ret["archivo"]) as z:
        dibujo_ret = z.read(dibujo_de_hoja(z, ret["hoja"])).decode("utf-8")
    anclas_ret = {nombre_forma(a.group(0)): a.group(0) for a in ANCLA.finditer(dibujo_ret)}
    alto_pastilla = tamano(anclas_ret[ret["pastilla_modelo"]])[1]
    medir, medir_medium = medidor(), medidor("Roboto-Medium.ttf")
    if not medir or not medir_medium:
        raise Fallo("No encuentro la Roboto instalada (Regular y Medium) para medir los textos")

    cambios, detalle = {}, []
    with zipfile.ZipFile(base) as z:
        ruta = dibujo_de_hoja(z, HOJA_GRAFICO)
        dibujo = z.read(ruta).decode("utf-8")
        relaciones = rels(z, ruta)
        columnas, paso_fila = guias_reticula(dibujo)
        (x1, w1), (x2, w2) = columnas
        ancho_ret = tamano(next(a.group(0) for a in ANCLA.finditer(dibujo) if es_reticula(a.group(0))), True)[0]
        paso_pt = paso_fila / EMU_PT
        detalle.append(f"Retícula: columna 1 de {x1 / 36000:.1f} a {(x1 + w1) / 36000:.1f} mm, columna 2 de "
                       f"{x2 / 36000:.1f} a {(x2 + w2) / 36000:.1f} mm; filas de {paso_fila / 36000:.2f} mm".replace(".", ","))

        # Qué es cada cosa
        partes = list(partes_dibujo(dibujo))
        caja = medidas_hoja(z, dibujo)
        titulo, fuentes, graficos, titulos_panel = None, None, [], []
        for i, a in enumerate(partes):
            if not ANCLA.fullmatch(a) or es_reticula(a) or es_pastilla(a):
                continue
            x, y, _, _ = caja(a)
            if x >= ancho_ret:
                continue
            graf = re.search(r'<c:chart\b[^>]*\br:id="([^"]+)"', a)
            if graf:
                graficos.append((y, i, graf.group(1)))
                continue
            texto = texto_forma(a)
            if "<xdr:txBody>" not in a or not texto.strip() or RE_GRAFICO.match(texto):
                continue
            if titulo is None and y < alto_pastilla:
                titulo = i
            elif RE_FUENTE.match(texto):
                fuentes = i
            else:
                titulos_panel.append((y, i))
        if not graficos:
            raise Fallo("No hay gráficos en la hoja «Gráfico»")
        graficos.sort()
        if len(graficos) > 3:
            detalle.append(f"Aviso: hay {len(graficos)} gráficos; la distribución de Illus prevé hasta 3 paneles")

        # Líneas del título del gráfico (Roboto Medium 8,5 pt en su marco)
        lineas_titulo = 1
        if titulo is not None:
            l, _, r, _ = margenes(partes[titulo])
            ancho = (caja(partes[titulo])[2] - l - r) / EMU_PT
            lineas_titulo = min(3, max(1, lineas_parrafos(textos_lineas(partes[titulo]), ancho, 8.5, medir_medium)))
        detalle.append(f"Título del gráfico: {lineas_titulo} línea{'s' if lineas_titulo > 1 else ''}")
        # Con más líneas, el marco del título, la pastilla y todo lo de debajo bajan un interlineado del título
        # por línea de más: así la pastilla queda siempre a la misma distancia por debajo del texto
        crece = 0.0
        pastilla = next((caja(a) for a in partes if ANCLA.fullmatch(a) and es_pastilla(a)), None)
        fondo_pastilla = (pastilla[1] + pastilla[3] if pastilla else alto_pastilla) / EMU_PT
        if lineas_titulo > 1:
            crece = (lineas_titulo - 1) * interlineado(partes[titulo], CUERPO_TITULO, "Roboto-Medium.ttf")
            partes[titulo] = alargar(partes[titulo], round(crece * EMU_PT), caja)
            for i, a in enumerate(partes):
                if ANCLA.fullmatch(a) and es_pastilla(a):
                    partes[i] = alargar(a, round(crece * EMU_PT), caja)
            detalle.append(f"  marco del título, pastilla y paneles {crece / MM:.1f} mm más abajo "
                           f"({lineas_titulo - 1} interlineado{'s' if lineas_titulo > 2 else ''} del título)".replace(".", ","))

        # Cada título de panel va con el primer gráfico que tiene debajo
        de_panel = {}
        for y, i in sorted(titulos_panel):
            for yg, ig, _ in graficos:
                if yg > y and ig not in de_panel:
                    de_panel[ig] = i
                    break

        ancho_util = x2 + w2 - x1
        ancho_graf = ancho_util
        W = ancho_graf / EMU_PT
        fondo = None
        for n, (_, ig, rid) in enumerate(graficos, 1):
            linea = f"Panel {n}:"
            ruta_graf = relaciones[rid][1]
            xml = z.read(ruta_graf).decode("utf-8")
            ruta_formas = next((d for t, d in rels(z, ruta_graf).values() if t.endswith("/chartUserShapes")), None)
            formas = z.read(ruta_formas).decode("utf-8") if ruta_formas else ""
            unidades = unidades_de(formas)
            subida = SUBIDA_GRAFICO + (SUBIDA_CON_UNIDADES if unidades else 0)

            # Dónde empieza el gráfico (lo más alto de su trazado), con o sin título de panel
            it = de_panel.get(ig)
            if it is not None:
                a = partes[it]
                l, t, r, b = margenes(a)
                lineas_tp = max(1, lineas_parrafos(textos_lineas(a), ancho_util / EMU_PT, 8, medir))
                if n == 1:
                    arriba = fondo_pastilla + crece + PASTILLA_A_TITULO_PANEL
                else:
                    arriba = fondo + ENTRE_PANELES
                final_tp = arriba + lineas_tp * INTERLINEA_TITULO_PANEL
                alto_tp = t + b + round(lineas_tp * INTERLINEA_TITULO_PANEL * EMU_PT)
                partes[it] = colocar(a, x1 - l, round(arriba * EMU_PT) - t, ancho_util + l + r, alto_tp)
                inicio = final_tp + TITULO_PANEL_A_GRAFICO - subida
                linea += f" título a {arriba / MM:.1f} mm ({lineas_tp} línea{'s' if lineas_tp > 1 else ''});".replace(".", ",")
            else:
                inicio = (INICIO_SIN_TITULO_PANEL + crece if n == 1 else fondo + ENTRE_PANELES) - subida

            # Alto: 9 filas hasta el final de las categorías (el trazado, como mínimo 7)
            numeros = ancho_numeros_eje(xml, medir)
            trazado = w1 / EMU_PT - numeros
            sz, nota, lineas_cat, filas_cat, alto_cat = filas_categorias(xml, trazado, paso_pt)
            filas = max(FILAS_PANEL, FILAS_MIN_TRAZADO + filas_cat)
            alto_panel = filas * paso_pt
            # Unidades: su línea de base, 2 mm por encima del borde de arriba del trazado
            ini_unidades = inicio + MEDIA_ETIQUETA - UNIDADES_A_GRAFICO - BASE_UNIDADES
            arriba_marco = min(ini_unidades, inicio) if unidades else inicio
            H = inicio + alto_panel - arriba_marco
            dentro = (numeros, inicio - arriba_marco + MEDIA_ETIQUETA, trazado,
                      alto_panel - MEDIA_ETIQUETA - alto_cat)
            xml = disposicion(xml, W, H, dentro, ((x2 - x1) / EMU_PT - LEYENDA_A_LA_IZQUIERDA, inicio - arriba_marco, w2 / EMU_PT), medir)
            # Cuerpo de las categorías con el ancho nuevo (regla del paso 2)
            xml = re.sub(r'<c:catAx>.*?</c:catAx>',
                         lambda m: re.sub(r'(<c:txPr>.*?</c:txPr>)', lambda t: fijar_letra(t.group(1), sz, ROBOTO),
                                          m.group(0), count=1, flags=re.S) if re.search(r'<c:axPos val="[bt]"/>', m.group(0)) else m.group(0),
                         xml, flags=re.S)
            cambios[ruta_graf] = xml.encode("utf-8")
            for u in unidades:
                formas = colocar_unidades(formas, u, numeros, ini_unidades - arriba_marco, W, H, medir)
            if unidades:
                cambios[ruta_formas] = formas.encode("utf-8")
                linea += f" unidades a {ini_unidades / MM:.1f} mm, en la línea del eje y 2 mm sobre el trazado;".replace(".", ",")
            partes[ig] = colocar(partes[ig], x1, round(arriba_marco * EMU_PT), ancho_graf, round(H * EMU_PT))
            fondo = inicio + alto_panel
            linea += (f" gráfico a {inicio / MM:.1f} mm, {filas} filas ({alto_panel / MM:.1f} mm;"
                      f" categorías {sz / 100:g} pt en {lineas_cat} línea{'s' if lineas_cat > 1 else ''},"
                      f" {filas_cat} fila{'s' if filas_cat > 1 else ''})").replace(".", ",")
            if nota:
                linea += f" — {nota}"
            detalle.append(linea)

        if fuentes is not None:
            a = partes[fuentes]
            l, t, r, _ = margenes(a)
            y = fondo + HASTA_FUENTES
            partes[fuentes] = colocar(a, x1 - l, round(y * EMU_PT) - t, ancho_util + l + r, caja(a)[3])
            detalle.append(f"FUENTES a {y / MM:.1f} mm, a lo ancho de las dos columnas".replace(".", ","))
        else:
            detalle.append("Aviso: no encuentro FUENTES")
        cambios[ruta] = "".join(partes).encode("utf-8")
    return nuevo_paso(trabajo, "Tamaño y colocación", cambios, detalle)

# ---------------------------------------------------------------- medir textos

CARPETAS_FUENTES = [Path.home() / "Library/Fonts", Path("/Library/Fonts"), Path("/System/Library/Fonts/Supplemental")]
HOLGURA_PT = 5.0   # lo que Excel deja libre en cada hueco: si la palabra no cabe, agranda el trazado
_medidores = {}


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


def anchos_graficos(z, dibujo):
    """Ancho en puntos de cada gráfico de la hoja (por su r:id), a partir de las columnas que ocupa.
    Lo que mide una unidad de ancho de columna se saca de las formas del propio dibujo."""
    hoja = z.read(hoja_de(z, HOJA_GRAFICO)).decode("utf-8")
    cols = [(int(a), int(b), float(w)) for a, b, w in
            re.findall(r'<col\b[^>]*?\bmin="(\d+)"[^>]*?\bmax="(\d+)"[^>]*?\bwidth="([\d.]+)"', hoja)]
    defecto = re.search(r'\bdefaultColWidth="([\d.]+)"', hoja)
    defecto = float(defecto.group(1)) if defecto else 8.43

    def suma(c1, c2):
        return sum(next((w for a, b, w in cols if a <= c + 1 <= b), defecto) for c in range(c1, c2))
    celdas = r'<xdr:from><xdr:col>(\d+)</xdr:col><xdr:colOff>(-?\d+)</xdr:colOff>.*?<xdr:to><xdr:col>(\d+)</xdr:col><xdr:colOff>(-?\d+)</xdr:colOff>'
    medidas, graficos = [], {}
    for m in ANCLA.finditer(dibujo):
        a = m.group(0)
        c = re.search(celdas, a, re.S)
        if not c:
            continue
        c1, o1, c2, o2 = map(int, c.groups())
        ext = re.search(r'<a:ext cx="(\d+)"', a)
        if ext and int(ext.group(1)) > 0 and suma(c1, c2) > 0:
            medidas.append((int(ext.group(1)) - o2 + o1) / suma(c1, c2))
        graf = re.search(r'<c:chart\b[^>]*\br:id="([^"]+)"', a)
        if graf:
            graficos[graf.group(1)] = (c1, o1, c2, o2)
    if not medidas:
        return {}
    unidad = sorted(medidas)[len(medidas) // 2]
    return {rid: (unidad * suma(c1, c2) - o1 + o2) / EMU_PT for rid, (c1, o1, c2, o2) in graficos.items()}


def etiquetas_categorias(xml):
    """Los textos del eje de categorías tal como los pone Excel (con noMultiLvlLbl, los niveles van juntos)."""
    cat = re.search(r'<c:cat>.*?</c:cat>', xml, re.S)
    if not cat or "<c:numRef>" in cat.group(0):
        return []
    niveles = [dict((int(i), v) for i, v in re.findall(r'<c:pt idx="(\d+)">\s*<c:v>([^<]*)</c:v>', n))
               for n in (re.findall(r'<c:lvl>(.*?)</c:lvl>', cat.group(0), re.S) or [cat.group(0)])]
    n = int(re.search(r'<c:ptCount val="(\d+)"', cat.group(0)).group(1))
    etiquetas = [niveles[0].get(i, "") for i in range(n)]
    if len(niveles) > 1 and '<c:noMultiLvlLbl val="1"/>' in xml:
        for nivel in niveles[1:]:
            for i in range(n):
                grupo = max((j for j in nivel if j <= i), default=None)
                if grupo is not None:
                    etiquetas[i] += " " + nivel[grupo]
    return etiquetas


def cuerpo_categorias(xml, ancho_pt, sin_disposicion=False):
    """7 pt; si alguna palabra no cabe en el hueco de su categoría (Excel la corta o gira las etiquetas),
    6,5 pt, y si tampoco, 6 pt."""
    medir = medidor()
    etiquetas = etiquetas_categorias(xml)
    if not medir or not ancho_pt or not etiquetas:
        return 700, None if etiquetas else None
    lay = re.search(r'<c:plotArea>\s*<c:layout>\s*<c:manualLayout>(.*?)</c:manualLayout>', xml, re.S)
    w = lay and re.search(r'<c:w val="([^"]+)"', lay.group(1))
    hueco = (ancho_pt if sin_disposicion else ancho_pt * (float(w.group(1)) if w else 0.8)) / len(etiquetas) - HOLGURA_PT
    palabras = [p for e in etiquetas for p in e.split()]
    if not palabras:
        return 700, None
    larga = max(palabras, key=lambda p: medir(p, 7))
    for sz in (700, 650, 600):
        if medir(larga, sz / 100) <= hueco:
            break
    if sz == 700:
        return 700, None
    nota = f"«{larga}» mide {medir(larga, 7):.1f} pt a 7 pt y el hueco es de {hueco:.1f} pt".replace(".", ",")
    if medir(larga, sz / 100) > hueco:
        nota += "; no cabe ni a 6 pt"
    return sz, nota + ("" if w or sin_disposicion else "; hueco aproximado")


def maquetar_formas_grafico(xml):
    """Cuadros de texto dentro del gráfico: arriba, las unidades (7 pt); el resto, interior (6 pt)."""
    unidades, otros = [], []

    def cambiar(m):
        a = m.group(0)
        texto = texto_forma(a).strip()
        if not texto:
            return a
        y = float(re.search(r'<cdr:from>.*?<cdr:y>([^<]+)</cdr:y>', a, re.S).group(1))
        if y < 0.2:
            unidades.append(texto[:40])
            return fijar_letra(a, 700, ROBOTO)
        otros.append(texto[:40])
        return fijar_letra(a, 600, ROBOTO)
    xml = re.sub(r'<cdr:(relSizeAnchor|absSizeAnchor)\b.*?</cdr:\1>', cambiar, xml, flags=re.S)
    return xml, unidades, otros


def medidas_reticula():
    """Ancho y alto de la retícula en puntos, para que la app encuadre Excel en el gráfico."""
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


def partes_dibujo(dibujo):
    """El dibujo troceado en texto suelto y anclas, para cambiar solo algunas anclas."""
    pos = 0
    for m in ANCLA.finditer(dibujo):
        yield dibujo[pos:m.start()]
        yield m.group(0)
        pos = m.end()
    yield dibujo[pos:]


def guardar_publicacion(datos):
    """Alta o cambio de una publicación: {"id"?, "nombre", "color", "tema"}."""
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
        # (BdE_2026.xml se llama «Colores 2026_2», igual que la paleta de los Excel del autor)
        lista.append({"id": archivo.stem, "nombre": nombre.group(1) if nombre else archivo.stem,
                      "archivo": archivo.name, "colores": colores})
    ARCHIVO_PALETAS.write_text(json.dumps(lista, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return {"paletas": lista, "carpeta": str(CARPETA_PALETAS)}


def info(archivo):
    with zipfile.ZipFile(archivo) as z:
        ruta = dibujo_de_hoja(z, HOJA_GRAFICO)
        dibujo = z.read(ruta).decode("utf-8")
        hojas = re.findall(r'<sheet\b[^>]*\bname="([^"]*)"', z.read("xl/workbook.xml").decode("utf-8"))
    formas = []
    for i, m in enumerate(ANCLA.finditer(dibujo)):
        a = m.group(0)
        tipo = "retícula" if es_reticula(a) else "pastilla" if es_pastilla(a) else "gráfico" if "<c:chart " in a else "forma"
        formas.append({"orden": i, "nombre": nombre_forma(a), "tipo": tipo, "color": color_de(a) if tipo == "pastilla" else None})
    return {"archivo": str(archivo), "idioma": idioma(archivo), "hojas": hojas, "formas": formas}


def main(args):
    ordenes = {"empezar": empezar, "estado": lambda t: {"trabajo": t, **leer_estado(t)}, "ir": ir, "reiniciar": reiniciar, "paso1": paso1, "paso2": paso2, "info": info,
               "publicaciones": lambda: {}, "guardar_publicacion": guardar_publicacion, "borrar_publicacion": borrar_publicacion, "paletas": paletas}
    if not args or args[0] not in ordenes:
        print(__doc__, file=sys.stderr)
        return 2
    try:
        res = ordenes[args[0]](*args[1:])
        res["publicaciones"] = CONFIG["publicaciones"]
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
