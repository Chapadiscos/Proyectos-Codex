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
  maquetar_excel.py paso3   <trabajo.xlsx> [id_publicacion]
  maquetar_excel.py paso4   <trabajo.xlsx> [id_publicacion]
  maquetar_excel.py paso5   <trabajo.xlsx> [id_publicacion]
  maquetar_excel.py comparar <trabajo.xlsx>
  maquetar_excel.py terminar <trabajo.xlsx>
  maquetar_excel.py info    <archivo.xlsx>
  maquetar_excel.py publicaciones
  maquetar_excel.py guardar_publicacion '<json>'
  maquetar_excel.py borrar_publicacion <id>
  maquetar_excel.py paletas [actualizar]
"""
import datetime
import difflib
import html
from collections import Counter
import io
import json
import math
import os
import re
import shutil
import struct
import subprocess
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
    # «Ing» suelto («G_Ing_…», «… Ing») o pegado a la letra del tipo de figura («GIng_…», «CIng_…»)
    return "en" if re.search(r'(^|[ _\-.])[A-Z]?Ing([ _\-.]|$)', Path(nombre).stem) else "es"


RE_CHART = re.compile(r'\s*Chart\s+\S+\s*$')


def rotulo_en_ingles(origen):
    """¿El rótulo del gráfico es «Chart N» (gráfico en inglés aunque el nombre del archivo no lo diga)?"""
    try:
        with zipfile.ZipFile(origen) as z:
            for n in z.namelist():
                if re.fullmatch(r'xl/drawings/drawing\d+\.xml', n):
                    for a in ANCLA.finditer(z.read(n).decode("utf-8")):
                        for linea in texto_forma(a.group(0)).split("\n"):
                            if RE_CHART.match(html.unescape(linea)):
                                return True
    except (zipfile.BadZipFile, KeyError):
        pass
    return False


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
    lengua, motivo = idioma(origen.name), "por el nombre del archivo"
    if lengua == "es" and rotulo_en_ingles(origen):
        lengua, motivo = "en", "por «Chart N» en el gráfico"
    estado = {"origen": str(origen), "idioma": lengua, "motivo_idioma": motivo, "actual": 0,
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


def paneles(trabajo, modo, pid=None):
    """Control «Paneles» de la app (petición del usuario, 2026-11-27): «auto», «lado» o «apilados». La retícula se
    pone en el paso 1: se vuelve a la copia exacta y se rehacen los pasos de maquetación que ya estaban hechos (las
    versiones de las herramientas y los cambios a mano de después se pierden)."""
    if modo not in MODOS_PANELES:
        raise Fallo(f"Modo de paneles desconocido: «{modo}»")
    estado = leer_estado(trabajo)
    hechos = [p["titulo"] for p in estado["pasos"][1:estado["actual"] + 1]]
    estado["paneles"] = modo
    guardar_estado(trabajo, estado)
    orden_pasos = [(RETICULA_Y_TEXTOS, paso1), ("Tamaño y colocación", paso2), ("Ejes", paso3),
                   (LINEAS_INTERIORES, paso4), (TRAMAS_COLORES_LINEAS, paso5)]
    hasta = max([k for k, (t, _) in enumerate(orden_pasos) if t in hechos] or [-1])
    r = ir(trabajo, 0)
    for _, f in orden_pasos[:hasta + 1]:
        r = f(trabajo, pid)
    return r


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
    estado["pasos"].append({"n": n, "titulo": titulo, "archivo": archivo,
                            "detalle": marcar_detalle(pasos / archivo, detalle, orden_documento=(titulo == RETICULA_Y_TEXTOS))})
    estado["actual"] = n
    guardar_estado(trabajo, estado)
    return {"trabajo": str(trabajo), **estado}


INVISIBLES = {"\n": "⏎", "\u00a0": "⍽", "\u202f": "⍽", "\u2009": "⍽", "\u200a": "⍽", "\t": "⇥", " ": "␣"}


def resaltar(a, b, contexto=24):
    """«…⟪x⟫…» → «…⟪y⟫…»: solo lo que cambia entre ⟪ ⟫ (la app lo pinta en rojo), con los espacios, saltos de
    línea y espacios que no parten línea a la vista (␣ ⏎ ⍽), y algo de texto alrededor (como en Cuadros Excel BdE;
    petición del usuario, 2026-11-26)."""
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


RE_PAR_CAMBIO = re.compile(r'«([^«»⟪⟫]*)» → «([^«»⟪⟫]*)»')


def con_resaltes(linea):
    """Lo que la app pinta en rojo (petición del usuario, 2026-11-26): en los cambios «a» → «b», solo lo que cambia;
    en los avisos, lo que señalan (el texto entre «», y «sept» en el de septiembre). Lo que ya lleva ⟪ ⟫ se deja."""
    if "⟪" in linea:
        return linea
    cuerpo, marca_l = (linea.rsplit(" ⟦", 1) + [""])[:2] if linea.endswith("⟧") else (linea, "")
    marca_l = (" ⟦" + marca_l) if marca_l else ""
    if RE_PAR_CAMBIO.search(cuerpo):
        cuerpo = RE_PAR_CAMBIO.sub(lambda m: resaltar(m.group(1), m.group(2)) if m.group(1) != m.group(2) else m.group(0), cuerpo)
    elif cuerpo.startswith("Aviso"):
        cuerpo = re.sub(r'«([^«»]+)»', lambda m: f"«⟪{m.group(1)}⟫»", cuerpo)
    return cuerpo + marca_l


def marca(hoja, indice, forma):
    """Marca invisible al final de una línea del detalle con la forma que hay que enseñar en Excel (como en Cuadros
    Excel BdE): la app la quita al mostrarla y, al pulsar la línea, selecciona esa forma en su hoja (petición del
    usuario, 2026-11-25). La forma va por su número en la hoja (orden del dibujo, como el de «shape k» en Excel),
    porque los autores repiten nombres (los cuatro gráficos del 1.13 se llaman «Chart 1»), y por su nombre."""
    return f" ⟦forma:{hoja}|{indice}|{forma}⟧"


RE_LINEA_PANEL = re.compile(r'^(?:Aviso: (?:el )?panel|Panel) (\d+)\b', re.I)


def marcar_detalle(libro, detalle, orden_documento=False):
    """Añade a las líneas del detalle que hablan de un panel (o de FUENTES, si son avisos) la marca de su forma en
    la hoja del gráfico. Los paneles se cuentan como en cada paso: en el 1, en el orden del dibujo; en los demás,
    de arriba abajo."""
    try:
        with zipfile.ZipFile(libro) as z:
            ruta_hoja = hoja_de(z, HOJA_GRAFICO)
            wb = z.read("xl/workbook.xml").decode("utf-8")
            relaciones = rels(z, "xl/workbook.xml")
            hoja = next((html.unescape(n) for n, rid in re.findall(r'<sheet\b(?=[^>]*\bname="([^"]*)")(?=[^>]*\br:id="([^"]+)")', wb)
                         if relaciones.get(rid, ("", ""))[1] == ruta_hoja), None)
            dibujo = z.read(dibujo_de_hoja(z, HOJA_GRAFICO)).decode("utf-8")
            partes = list(partes_dibujo(dibujo))
            caja = medidas_hoja(z, dibujo)
    except (Fallo, KeyError, OSError, zipfile.BadZipFile):
        return [con_resaltes(l) for l in detalle]
    if not hoja:
        return [con_resaltes(l) for l in detalle]
    anclas = [a for a in partes if ANCLA.fullmatch(a)]
    graficos = [(caja(a)[1], k, nombre_forma(a)) for k, a in enumerate(anclas, 1) if "<c:chart " in a]
    nombres = [(k, n) for _, k, n in (graficos if orden_documento else sorted(graficos))]
    fuentes = next(((k, nombre_forma(a)) for k, a in enumerate(anclas, 1) if "<xdr:txBody>" in a
                    and re.match(r'\s*(FUENTES?|SOURCES?)\b', html.unescape(texto_forma(a)), re.I)), None)
    salida = []
    for linea in detalle:
        if not linea.endswith("⟧"):
            m = RE_LINEA_PANEL.match(linea)
            if m and 1 <= int(m.group(1)) <= len(nombres):
                linea += marca(hoja, *nombres[int(m.group(1)) - 1])
            elif fuentes and linea.startswith("Aviso") and re.search(r'(?i)\bfuentes?\b|\bsources?\b', linea):
                linea += marca(hoja, *fuentes)
        salida.append(con_resaltes(linea))
    return salida


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
    hoja_xml = hoja_de(z, hoja)
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
    """Rectángulo de color sin texto pegado arriba a la izquierda (hasta 1 mm del origen): la pastilla."""
    if "<xdr:sp " not in ancla[:600] and "<xdr:sp>" not in ancla[:600]:
        return False
    if re.search(r'<a:t>\s*[^<\s]', ancla) or 'prst="rect"' not in ancla:
        return False
    sppr = re.search(r'<xdr:spPr>.*?</xdr:spPr>', ancla, re.S)
    desde = re.search(r'<xdr:from>\s*<xdr:col>(\d+)</xdr:col>\s*<xdr:colOff>(\d+)</xdr:colOff>\s*<xdr:row>(\d+)</xdr:row>', ancla)
    return bool(sppr and "<a:solidFill>" in sppr.group(0) and desde and desde.group(1) == "0" and desde.group(3) == "0"
                and int(desde.group(2)) <= 36000 and int(re.search(r'<xdr:rowOff>(\d+)', ancla).group(1)) <= 36000)


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
    # Si el autor lo ha agrupado todo, primero se desagrupa (cada elemento queda en su sitio)
    with zipfile.ZipFile(base) as z:
        ruta = dibujo_de_hoja(z, HOJA_GRAFICO)
        dibujo, deshechos = desagrupar(z, z.read(ruta).decode("utf-8"))
        # Títulos de panel que el autor dejó dentro de un gráfico (cuadro de texto del gráfico): a la hoja
        dibujo, formas_cambiadas, sacados, vacias = sacar_titulos_de_graficos(z, ruta, dibujo)
    cambios0, detalle0 = {}, []
    if sacados or vacias:
        cambios0[ruta] = dibujo.encode("utf-8")
        cambios0.update(formas_cambiadas)
        detalle0 += [f"Aviso: el título de panel «{t}» estaba dentro del gráfico «{g}» (como texto del gráfico): pasa a "
                     "la hoja para tratarlo como título de panel" for t, g in sacados]
        por_grafico = {}
        for f, g in vacias:
            por_grafico.setdefault(g, []).append(f)
        detalle0 += [f"Aviso: quitadas de dentro del gráfico «{g}» {len(fs)} forma{'s' if len(fs) > 1 else ''} vacía"
                     f"{'s' if len(fs) > 1 else ''} e invisible{'s' if len(fs) > 1 else ''} (sin texto, relleno ni borde; "
                     f"restos de la plantilla del autor: {', '.join(f'«{x}»' for x in fs)}): tapaban el gráfico y no "
                     "dejaban seleccionar ni mover lo que había debajo" for g, fs in por_grafico.items()]
    if deshechos:
        cambios0[ruta] = dibujo.encode("utf-8")
        detalle0.append("Desagrupado lo que el autor había agrupado con el gráfico: " +
                        ", ".join(f"«{n}»" for n in deshechos) + " (cada elemento en su sitio)")
    if deshechos or sacados or vacias:
        previo = io.BytesIO()
        reescribir_zip(base, previo, cambios0)
    else:
        previo = base
    with zipfile.ZipFile(previo) as z:
        cambios, detalle = reticula_y_pastilla(z, pid, estado.get("paneles", "auto"), es_recuadro(trabajo))
    intermedio = io.BytesIO()
    reescribir_zip(previo, intermedio, cambios)
    with zipfile.ZipFile(intermedio) as z:
        cambios_textos, detalle_textos = textos(z, estado)
    return nuevo_paso(trabajo, RETICULA_Y_TEXTOS, {**cambios0, **cambios, **cambios_textos},
                      aviso_separador_ingles(estado) + detalle0 + detalle + detalle_textos)


def sacar_titulos_de_graficos(z, ruta, dibujo):
    """Un título de panel numerado («2.28.b …») que el autor puso dentro de un gráfico, como cuadro de texto del
    gráfico (G_IA2025_1.28: el del panel b, dentro del gráfico del panel a), pasa a la hoja en el mismo sitio, para
    tratarlo como título de panel (renumerarlo, 8 pt, colocarlo con su gráfico). Devuelve el dibujo, las capas de
    formas cambiadas y [(texto, gráfico)]."""
    partes = list(partes_dibujo(dibujo))
    caja = medidas_hoja(z, dibujo)
    relaciones = rels(z, ruta)
    sig = max([int(n) for n in re.findall(r'<xdr:cNvPr\s+id="(\d+)"', dibujo)] or [1]) + 1
    cambios, sacados, nuevas, vacias = {}, [], [], []
    for k, a in enumerate(partes):
        rid = re.search(r'<c:chart\b[^>]*\br:id="([^"]+)"', a) if ANCLA.fullmatch(a) else None
        if not rid or rid.group(1) not in relaciones:
            continue
        ruta_graf = relaciones[rid.group(1)][1]
        ruta_formas = next((d for t, d in rels(z, ruta_graf).values() if t.endswith("/chartUserShapes")), None)
        if not ruta_formas or ruta_formas not in z.namelist():
            continue
        formas = z.read(ruta_formas).decode("utf-8")
        antes = formas
        gx, gy, gw, gh = caja(a)
        for ancla in re.findall(r'<cdr:(?:relSizeAnchor|absSizeAnchor)\b.*?</cdr:(?:relSizeAnchor|absSizeAnchor)>', formas, re.S):
            texto = html.unescape(texto_forma(ancla)).strip()
            sp = re.search(r'<cdr:sp\b.*?</cdr:sp>', ancla, re.S)
            subtitulo = bool(RE_SUBPANEL.match(texto)) and len(texto) < 120
            if sp and forma_invisible(sp.group(0), texto):
                # Forma vacía e invisible encima del gráfico: tapa sus elementos y no deja seleccionarlos ni moverlos
                # (G_IA2025_2.5: «Rectangle 1», vinculado a «#REF!», sobre toda la parte de arriba)
                formas = formas.replace(ancla, "", 1)
                nombre = re.search(r'<cdr:cNvPr\b[^>]*\bname="([^"]*)"', ancla)
                vacias.append((nombre.group(1) if nombre else "sin nombre", nombre_forma(a)))
                continue
            if not sp or not (subtitulo or (RE_PANEL.match(texto) and RE_NUMERO_PANEL.match(texto))):
                continue
            x0, y0, x1, y1 = caja_rel(ancla)
            x, y, w, h = round(gx + x0 * gw), round(gy + y0 * gh), round((x1 - x0) * gw), round((y1 - y0) * gh)
            forma = sp.group(0).replace("<cdr:", "<xdr:").replace("</cdr:", "</xdr:")
            # En la capa del gráfico cada elemento repite «xmlns:a»; la hoja ya lo declara (y las reglas de los textos
            # buscan «<a:p>» a secas)
            forma = forma.replace(' xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"', "")
            forma = re.sub(r'(<xdr:cNvPr\s+id=")\d+(")', rf'\g<1>{sig}\2', forma, count=1)
            forma = re.sub(r'<a:off x="-?\d+" y="-?\d+"/>\s*<a:ext cx="\d+" cy="\d+"/>',
                           f'<a:off x="{x}" y="{y}"/><a:ext cx="{w}" cy="{h}"/>', forma, count=1)
            sig += 1
            nuevas.append((k, f'<xdr:absoluteAnchor><xdr:pos x="{x}" y="{y}"/><xdr:ext cx="{w}" cy="{h}"/>{forma}'
                              '<xdr:clientData/></xdr:absoluteAnchor>'))
            formas = formas.replace(ancla, "", 1)
            sacados.append((texto[:60], nombre_forma(a)))
        if formas != antes:
            cambios[ruta_formas] = formas.encode("utf-8")
    # El título propio de un gráfico (<c:title>) numerado como título de panel («3.2.a …»): Excel lo pinta dentro del
    # marco, sobre el trazado; pasa a la hoja como un título de panel más (G_MemoriaSupervision_3.2)
    for k, a in enumerate(partes):
        rid = re.search(r'<c:chart\b[^>]*\br:id="([^"]+)"', a) if ANCLA.fullmatch(a) else None
        if not rid or rid.group(1) not in relaciones:
            continue
        ruta_graf = relaciones[rid.group(1)][1]
        xml = z.read(ruta_graf).decode("utf-8")
        tit = re.search(r'<c:title>.*?</c:title>', xml, re.S)
        if not tit:
            continue
        texto = html.unescape("".join(re.findall(r'<a:t>([^<]*)</a:t>', tit.group(0)))).strip()
        if not texto or not (RE_SUBPANEL.match(texto) or (RE_PANEL.match(texto) and RE_NUMERO_PANEL.match(texto))):
            continue
        gx, gy, gw, gh = caja(a)
        x, y, w, h = gx, gy, round(gw * 0.95), round(6 * 36000)
        nuevas.append((k, f'<xdr:absoluteAnchor><xdr:pos x="{x}" y="{y}"/><xdr:ext cx="{w}" cy="{h}"/><xdr:sp macro="" '
                          f'textlink=""><xdr:nvSpPr><xdr:cNvPr id="{sig}" name="Título de panel {sig}"/><xdr:cNvSpPr txBox="1"/>'
                          f'</xdr:nvSpPr><xdr:spPr><a:xfrm><a:off x="{x}" y="{y}"/><a:ext cx="{w}" cy="{h}"/></a:xfrm>'
                          '<a:prstGeom prst="rect"><a:avLst/></a:prstGeom><a:noFill/></xdr:spPr><xdr:txBody><a:bodyPr '
                          'wrap="square" lIns="0" tIns="0" rIns="0" bIns="0" rtlCol="0" anchor="t"/><a:lstStyle/><a:p><a:r>'
                          '<a:rPr lang="es-ES" sz="800" b="0"><a:solidFill><a:srgbClr val="000000"/></a:solidFill>'
                          f'<a:latin typeface="{ROBOTO}"/><a:ea typeface="{ROBOTO}"/></a:rPr><a:t>{html.escape(texto, quote=False)}'
                          '</a:t></a:r></a:p></xdr:txBody></xdr:sp><xdr:clientData/></xdr:absoluteAnchor>'))
        sig += 1
        xml = xml.replace(tit.group(0), "", 1)
        xml = re.sub(r'<c:autoTitleDeleted val="0"/>', '<c:autoTitleDeleted val="1"/>', xml)
        if "<c:autoTitleDeleted" not in xml:
            xml = re.sub(r'(<c:chart>)', r'\1<c:autoTitleDeleted val="1"/>', xml, count=1)
        cambios[ruta_graf] = xml.encode("utf-8")
        sacados.append((texto[:60], nombre_forma(a)))
    for k, nueva in sorted(nuevas, reverse=True):
        partes.insert(k + 1, nueva)
        partes.insert(k + 1, "")
    return "".join(partes), cambios, sacados, vacias


def forma_invisible(sp, texto):
    """Una forma sin texto que no se ve: sin relleno y sin borde (los cuadros de texto, sin nada, no tienen ni uno
    ni otro)."""
    if texto or "<cdr:pic" in sp:
        return False
    sppr = re.search(r'<cdr:spPr\b.*?</cdr:spPr>', sp, re.S)
    sppr = sppr.group(0) if sppr else ""
    caja_texto = 'txBox="1"' in sp
    ln = re.search(r'<a:ln\b.*?</a:ln>|<a:ln\b[^>]*/>', sppr, re.S)
    relleno = re.sub(r'<a:ln\b.*?</a:ln>|<a:ln\b[^>]*/>', "", sppr, flags=re.S)
    sin_relleno = "<a:noFill" in relleno or (caja_texto and not re.search(r'<a:(?:solidFill|gradFill|pattFill|blipFill)', relleno))
    sin_borde = (ln and "<a:noFill" in ln.group(0)) or (caja_texto and not ln)
    sin_estilo = "<cdr:style>" not in sp or caja_texto
    return bool(sin_relleno and sin_borde and sin_estilo)


# ---- paneles lado a lado (Memoria de Supervisión: 2.1, 2.9, 3.1…; decisiones del usuario, 2026-11-27)

ALTO_MIN_PANEL = 25 * 36000          # EMU: un gráfico más bajo es una leyenda suelta (las del 3.5)
SEPARACION_LADO_A_LADO = 40 * 36000  # EMU: dos paneles de una fila empiezan al menos así de separados


MODOS_PANELES = ("auto", "lado", "apilados")


def es_recuadro(trabajo):
    """Los recuadros («Rec_…») se dejan para el final (decisión del usuario, 2026-11-27): no van lado a lado solos."""
    return Path(str(trabajo)).name.startswith("Rec_")


def filas_segun_modo(z, ruta, dibujo, modo="auto", recuadro=False):
    """Las filas de paneles lado a lado según el control «Paneles» de la app: «auto» (en todas las publicaciones, lo
    que se detecte; los recuadros no), «lado» (lo detectado o, si el autor los apiló, en filas de dos por orden: para
    los que no caben al publicar) o «apilados» (nunca). None: maqueta de siempre, uno debajo de otro."""
    if modo == "apilados":
        return None
    filas = filas_de_paneles(z, ruta, dibujo)
    if modo != "lado":
        return None if recuadro else filas
    return filas or filas_de_paneles(z, ruta, dibujo, forzar=True)


def es_solo_leyenda(xml, alto):
    """¿Un gráfico que solo enseña la leyenda (la leyenda común del 2.1 y el 8.3, las sueltas del 3.5)?"""
    ley = re.search(r'<c:legend>.*?</c:legend>', xml, re.S)
    if not ley:
        return False
    if alto < ALTO_MIN_PANEL:
        return True
    lay = dict(re.findall(r'<c:([wh]) val="([^"]+)"', ley.group(0)))
    return float(lay.get("w", 0)) > 0.9 and float(lay.get("h", 0)) > 0.5


def filas_de_paneles(z, ruta, dibujo, forzar=False):
    """Los gráficos de la hoja por filas, si hay paneles lado a lado (dos o más a la misma altura, en mitades
    distintas). Devuelve (filas, leyendas) con las posiciones en `partes_dibujo(dibujo)`: cada fila, sus paneles de
    izquierda a derecha; `leyendas`, {fila: [gráficos que solo son leyenda, debajo de ella]}. None si no hay."""
    relaciones = rels(z, ruta)
    caja = medidas_hoja(z, dibujo)
    paneles, sueltas = [], []
    # Solo lo de dentro de la página (la retícula): a la derecha el autor deja a veces gráficos de sobra (1.19)
    ret = next((a.group(0) for a in ANCLA.finditer(dibujo) if es_reticula(a.group(0))), None)
    limite = caja(ret)[0] + caja(ret)[2] if ret else 175 * 36000
    for i, a in enumerate(partes_dibujo(dibujo)):
        rid = ANCLA.fullmatch(a) and re.search(r'<c:chart\b[^>]*\br:id="([^"]+)"', a)
        if not rid or rid.group(1) not in relaciones:
            continue
        x, y, w, h = caja(a)
        if x >= limite - 10 * 36000:
            continue
        xml = z.read(relaciones[rid.group(1)][1]).decode("utf-8")
        (sueltas if es_solo_leyenda(xml, h) else paneles).append((i, x, y, w, h))
    filas = []
    for p in sorted(paneles, key=lambda p: p[2]):
        for fila in filas:
            arriba = max(q[2] for q in fila)
            abajo = min(q[2] + q[4] for q in fila)
            if min(abajo, p[2] + p[4]) - max(arriba, p[2]) > 0.5 * min(p[4], min(q[4] for q in fila)):
                fila.append(p)
                break
        else:
            filas.append([p])
    if forzar and len(paneles) > 1:
        # Forzado desde la app: los paneles, en su orden (de arriba abajo), en filas de dos
        # (por el centro: el marco de un panel puede empezar por encima del de arriba; 1.35, el b antes que el a)
        orden_p = sorted(paneles, key=lambda p: (p[2] + p[4] / 2, p[1]))
        filas = [orden_p[k:k + 2] for k in range(0, len(orden_p), 2)]
    elif not any(len(f) > 1 and max(q[1] for q in f) - min(q[1] for q in f) > SEPARACION_LADO_A_LADO for f in filas):
        return None
    if not (forzar and len(paneles) > 1):
        # (forzado, el orden de arriba abajo del autor: a, b, c…; si no, de izquierda a derecha)
        filas = [sorted(f, key=lambda p: p[1]) for f in filas]
    leyendas = {}
    for l in sueltas:
        # Con la fila de encima (la más baja de las que empiezan por encima de la leyenda)
        k = max((k for k, f in enumerate(filas) if min(q[2] for q in f) <= l[2]), default=0)
        leyendas.setdefault(k, []).append(l)
    return [[q[0] for q in f] for f in filas], {k: [q[0] for q in sorted(v, key=lambda q: q[1])] for k, v in leyendas.items()}


def reticula_y_pastilla(z, pid, modo="auto", recuadro=False):
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
    # Paneles lado a lado: la retícula de los recuadros (dos columnas iguales y sus filas); la pastilla, la de siempre
    lado_a_lado = filas_segun_modo(z, ruta, dibujo, modo, recuadro)
    if lado_a_lado and ret.get("grupo_lado_a_lado"):
        with zipfile.ZipFile(PROYECTO / ret["archivo"]) as zr:
            dibujo_lad = zr.read(dibujo_de_hoja(zr, ret["hoja_lado_a_lado"])).decode("utf-8")
        grupo = next(a.group(0) for a in ANCLA.finditer(dibujo_lad) if nombre_forma(a.group(0)) == ret["grupo_lado_a_lado"])

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
    detalle.append(f"Retícula del archivo de retículas en A1, al fondo ({cx / 360000:.2f} × {cy / 360000:.2f} cm)"
                   + (f": la de los recuadros, de dos columnas iguales, porque los paneles van lado a lado "
                      f"({sum(len(f) for f in lado_a_lado[0])} paneles en {len(lado_a_lado[0])} fila"
                      f"{'s' if len(lado_a_lado[0]) > 1 else ''})" if lado_a_lado else ""))
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


# Leyendas en minúscula salvo las siglas (y la primera letra, y los nombres propios). Solo se tocan los nombres
# que el autor escribió enteros en mayúsculas: en uno con minúsculas no se sabe qué palabra es sigla o propia.
SIGLAS = {"EEUU", "EE.UU.", "EE", "UU", "UEM", "UE", "EA", "PIB", "IPC", "IPCA", "IAPC", "IPRI", "BCE", "BDE", "FMI",
          "OCDE", "OPEP", "IA", "TIC", "PYME", "PYMES", "VAB", "EPA", "PMI", "CNMV", "TAE", "TIN", "ICO", "IRPF",
          "IVA", "I+D", "SA", "EBAE", "ROE", "ROA", "NPL", "BBVA", "CCAA", "AAPP", "ISFLSH", "PER", "ETF", "EURIBOR",
          "FED", "INE", "AEAT", "BIS", "BPI", "UK", "US", "USA", "USD", "EUR", "GBP", "JPY", "CNY", "ESG", "TR", "EMU",
          "GDP", "CPI", "HICP", "ECB", "IMF", "OECD", "SME", "SMES", "AI", "UN", "CET1", "LTV", "LTI", "DTI", "DSTI", "SMI", "OIS",
          "CLU", "EBE", "REB", "PFEMP", "PTF"}
# Siglas que el propio autor escribe en mayúsculas dentro de una leyenda en minúscula del mismo gráfico
# («PFEMP + margen de flexibilidad» → «PFEMP» también es sigla en la leyenda «PFEMP», G_IA2025_1.35 c). Las pone
# `leyendas_en_minuscula` para cada gráfico
SIGLAS_DEL_GRAFICO = set()
SIGLAS_ESCRITAS = {"BDE": "BdE", "PYMES": "pymes", "PYME": "pyme", "ROE": "RoE", "EURIBOR": "euríbor", "SMES": "SMEs",
                   "FED": "Fed"}
# «UN» es sigla en inglés (Naciones Unidas) pero artículo en español: según el idioma
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
# Nombres propios que en mayúsculas suelen venir sin tilde (en español se les pone)
CON_TILDE = {"MEXICO": "MÉXICO", "SAUDI": "SAUDÍ", "PERU": "PERÚ", "JAPON": "JAPÓN", "CANADA": "CANADÁ",
             "TURQUIA": "TURQUÍA", "BELGICA": "BÉLGICA", "AFRICA": "ÁFRICA", "LATINOAMERICA": "LATINOAMÉRICA",
             "OCEANIA": "OCEANÍA", "TUNEZ": "TÚNEZ", "IRAN": "IRÁN", "OMAN": "OMÁN", "PANAMA": "PANAMÁ",
             "AZERBAIYAN": "AZERBAIYÁN", "KAZAJISTAN": "KAZAJISTÁN", "PAKISTAN": "PAKISTÁN", "SUDAFRICA": "SUDÁFRICA",
             "HUNGRIA": "HUNGRÍA", "RUMANIA": "RUMANÍA", "CAMERUN": "CAMERÚN", "ETIOPIA": "ETIOPÍA", "ARABES": "ÁRABES",
             "ANDALUCIA": "ANDALUCÍA", "CATALUÑA": "CATALUÑA", "BALTICOS": "BÁLTICOS"}
NOMBRES_PROPIOS_SOLO_EN = {"EURO", "AREA", "MAY", "MARCH", "UNITED", "STATES", "KINGDOM", "LATIN", "AMERICA"}
ROMANOS = re.compile(r'(?=[IVXLC]+$)M*(C[MD]|D?C{0,3})(X[CL]|L?X{0,3})(I[XV]|V?I{0,3})$')


CONECTORES_MINUSCULA = {"y", "e", "o", "u", "a", "de", "del", "en", "and", "of", "in", "to"}


def sin_vocales(palabra):
    """Una palabra de dos o más letras sin vocales (ni «y»: «BY», «MY» en inglés) no es una palabra, es una sigla
    («PTF», «CNMV»;
    G_IA2025_3.1, «PTF» → «Ptf»)."""
    letras = [c for c in palabra if c.isalpha()]
    return len(letras) >= 2 and all(c.isupper() for c in letras) and not any(c in "AEIOUYÁÉÍÓÚÜaeiouyáéíóúü" for c in letras)


def en_minuscula(texto, idioma="es"):
    """Nombre de leyenda en minúscula salvo las siglas, los nombres propios, los números romanos y la primera
    letra (y la de después de un punto). Solo si está entero en mayúsculas; si no, como lo escribió el autor."""
    # Las llamadas a nota («(b)», en minúscula por norma) no cuentan para saber si está en mayúsculas
    # Ni las conjunciones y preposiciones cortas que el autor ya dejó en minúscula («… 2002-2007 y 2022-2025»,
    # G_IA2025_1.31)
    # (también las llamadas dobles: «(a, b)», «(a y b)», título del 1.33 b)
    sin_notas = re.sub(r'\(\w(?:\s*(?:,|y|and)\s*\w)*\)', "", texto)
    palabras = re.findall(r'[^\W\d_]+', sin_notas)
    letras = [c for p in palabras if p not in CONECTORES_MINUSCULA for c in p]
    if not letras or any(c.islower() for c in letras):
        return texto
    siglas = (SIGLAS | SIGLAS_DEL_GRAFICO) - (set() if idioma == "en" else SIGLAS_SOLO_EN)
    propios = NOMBRES_PROPIOS - (set() if idioma == "en" else NOMBRES_PROPIOS_SOLO_EN)
    # El guion también separa: «CLU-MANUFACTURAS» → «CLU-manufacturas» (1.33 a)
    partes = re.split(r'(\s+|(?<=[^\W\d_])-(?=[^\W\d_]))', texto)
    salida, mayuscula = [], True
    for parte in partes:
        if not parte or parte.isspace():
            salida.append(parte)
            continue
        limpia = parte.strip("()[]¿?¡!«»\"',;:.")
        # Letra suelta entre paréntesis («(O)», «(D)»): abreviatura, se deja
        if len(limpia) == 1 and parte.startswith("(") and limpia.isalpha():
            nueva = parte
        elif limpia in siglas or limpia.replace(".", "") in siglas or any(c.isdigit() for c in limpia) or (limpia and ROMANOS.match(limpia)) \
                or sin_vocales(limpia) \
                or re.fullmatch(r"[A-ZÁÉÍÓÚÑ]+(?:[&+][A-ZÁÉÍÓÚÑ]+)+", limpia):
            # (siglas con «&» o «+», «S&P», «I+D»: se dejan; antes «S&P 500» → «S&p 500», G_IA2025_1.13)
            escrita = SIGLAS_ESCRITAS.get(limpia, limpia)
            if mayuscula and escrita[:1].islower():
                escrita = escrita[0].upper() + escrita[1:]   # «pymes» al principio: «Pymes»
            nueva = parte.replace(limpia, escrita) if limpia else parte
        elif limpia in propios or (idioma != "en" and limpia in CON_TILDE):
            bien = CON_TILDE.get(limpia, limpia) if idioma != "en" else limpia
            nueva = parte.replace(limpia, bien[0] + bien[1:].lower())
        else:
            nueva = parte.lower()
            if mayuscula:
                i = next((k for k, c in enumerate(nueva) if c.isalpha()), None)
                if i is not None:
                    nueva = nueva[:i] + nueva[i].upper() + nueva[i + 1:]
        if any(c.isalpha() for c in parte):
            mayuscula = False
        # Tras los dos puntos, minúscula en castellano («IAPC de servicios: evolución…», como en el .ai del 1.31)
        if parte.rstrip("»\"')").endswith((".", "?", "!") if idioma != "en" else (".", ":", "?", "!")):
            mayuscula = True
        salida.append(nueva)
    return "".join(salida)


def textos_compartidos(z):
    if "xl/sharedStrings.xml" not in z.namelist():
        return []
    return [html.unescape("".join(re.findall(r'<t\b[^>]*>([^<]*)</t>', si)))
            for si in re.findall(r'<si>(.*?)</si>', z.read("xl/sharedStrings.xml").decode("utf-8"), re.S)]


def celda(hoja, ref):
    return re.search(rf'<c r="{ref}"(?=[\s>/])[^>]*?(?:/>|>.*?</c>)', hoja, re.S)


def texto_de_celda(c, compartidos):
    texto = c.group(0)
    v = re.search(r'<v>([^<]*)</v>', texto)
    if 't="s"' in texto and v:
        return compartidos[int(v.group(1))]
    if 't="inlineStr"' in texto:
        return html.unescape("".join(re.findall(r'<t\b[^>]*>([^<]*)</t>', texto)))
    return html.unescape(v.group(1)) if v else None


def poner_texto_celda(hoja, c, nuevo):
    """La celda con otro texto: si es una fórmula, solo su valor guardado; si no, texto propio de la celda (no
    se toca la lista de textos compartidos, que pueden usar otras celdas)."""
    texto = c.group(0)
    apertura = re.match(r'<c\b[^>]*?(?=/?>)', texto).group(0)
    apertura = re.sub(r'\s+t="\w+"', '', apertura)
    valor_xml = html.escape(nuevo, quote=False)
    formula = re.search(r'<f\b.*?</f>|<f\b[^>]*/>', texto, re.S)
    if formula:
        cuerpo = f'{apertura} t="str">{formula.group(0)}<v>{valor_xml}</v></c>'
    else:
        cuerpo = f'{apertura} t="inlineStr"><is><t xml:space="preserve">{valor_xml}</t></is></c>'
    return hoja[:c.start()] + cuerpo + hoja[c.end():]


def leyendas_en_minuscula(z, ruta_graf, xml, idioma, hojas):
    """Nombres de las series con las reglas de las leyendas (minúscula salvo siglas, «(Escala dcha.)»,
    trimestres): en la caché del gráfico y en las celdas de las que
    salen. Si la celda es una fórmula (p. ej. =SI(…;T(F9);T(F8))), también la celda de su columna con el mismo
    texto, que es su origen. `hojas` guarda las hojas de datos ya cambiadas. Devuelve el xml y lo cambiado."""
    compartidos = textos_compartidos(z)
    hechos = []
    SIGLAS_DEL_GRAFICO.clear()
    for nombre in re.findall(r'<c:tx>.*?<c:v>([^<]*)</c:v>', xml, re.S):
        nombre = html.unescape(nombre)
        if any(c.islower() for c in nombre):
            SIGLAS_DEL_GRAFICO.update(p for p in re.findall(r'[^\W\d_]{2,}', nombre) if p.isupper())

    def serie(m):
        ser = m.group(0)
        tx = re.search(r'<c:tx>.*?</c:tx>', ser, re.S)
        if not tx:
            return ser
        v = re.search(r'<c:v>([^<]*)</c:v>', tx.group(0))
        if not v:
            return ser
        antes = html.unescape(v.group(1))
        nuevo = nombre_leyenda(antes, idioma)
        if nuevo == antes:
            return ser
        f = re.search(r"<c:f>(?:'([^']+)'|([^!<]+))!\$([A-Z]+)\$(\d+)</c:f>", tx.group(0))
        if f:
            ruta_hoja = hoja_de(z, f.group(1) or f.group(2))
            hoja = hojas.get(ruta_hoja) or z.read(ruta_hoja).decode("utf-8")
            c = celda(hoja, f.group(3) + f.group(4))
            if c:
                if "<f" in c.group(0):
                    # El origen: una celda de la misma columna con el mismo texto
                    for o in re.finditer(rf'<c r="{f.group(3)}\d+"(?=[\s>/])[^>]*?(?:/>|>.*?</c>)', hoja, re.S):
                        if o.start() != c.start() and "<f" not in o.group(0) and texto_de_celda(o, compartidos) == antes:
                            hoja = poner_texto_celda(hoja, o, nuevo)
                            break
                    c = celda(hoja, f.group(3) + f.group(4))
                hoja = poner_texto_celda(hoja, c, nuevo)
                hojas[ruta_hoja] = hoja
        hechos.append(f"«{antes}» → «{nuevo}»")
        nuevo_tx = tx.group(0).replace(v.group(0), f"<c:v>{html.escape(nuevo, quote=False)}</c:v>", 1)
        return ser.replace(tx.group(0), nuevo_tx, 1)
    xml = re.sub(r'<c:ser>.*?</c:ser>', serie, xml, flags=re.S)
    # En las tartas la leyenda son las categorías: las mismas reglas, en la caché y en sus celdas
    if es_tarta(xml):
        xml, cambios, _ = cambiar_categorias(z, xml, hojas, lambda t: nombre_leyenda(t, idioma))
        hechos += cambios
    SIGLAS_DEL_GRAFICO.clear()
    return xml, hechos


RE_PANEL = re.compile(r'\s*\d+(?:\.\d+)*\.?\s*[a-zA-Z]\b'   # «1 a», «1.a», «2.6.a»: título de panel
                      r'|\s*[a-h][.)]?\s+[A-ZÁÉÍÓÚÑ]')        # y solo la letra: «a  Número de operaciones» (8.3)
RE_SOLO_LETRA = re.compile(r'\s*([a-h])[.)]?[ \t\u00a0]+(?=[A-ZÁÉÍÓÚÑ])')
# Subtítulo numerado de un panel lado a lado («1  Número anual de operaciones», «2  Importe…»: 8.1)
RE_SUBPANEL = re.compile(r'\s*\d\s+[^\W\d_]{2,}')


# Título de panel (todas las publicaciones): el número siempre como «N.x», letra en minúscula («1 a», «6.A.», «6.a)» → «1.a», «6.a»;
# «2.6.a» se queda), 2 espacios entre él y el título y, dentro del título, sin espacios dobles
RE_NUMERO_PANEL = re.compile(r'\s*(\d+(?:\.\d+)*)\.?\s*([a-zA-Z])(?![^\W\d_])[.)]?([ \t\u00a0]*)(?=\S)')
HUECO_PANEL = "  "

# Número del gráfico (todas las publicaciones, decisión del usuario 2026-11-25): el del nombre del archivo, que es
# el del .ai («G_IA2025_1.1» → «Gráfico 1.1», aunque el autor ponga su «Gráfico 2.1»), y los títulos de panel con
# ese número («2.1.a» → «1.1.a»). Solo si el nombre lleva un número con punto; los recuadros («Rec_…») aún no.
RE_NUMERO_ARCHIVO = re.compile(r'^[A-Za-z]+_[^_ ]+_(\d+(?:\.\d+)+)(?=$|[ _])')
RE_NUMERO_GRAFICO = re.compile(r'(Gráfico|Grafico|Chart|Figure)(\s+)(\S+)', re.I)


def numero_de_archivo(nombre):
    """El número del gráfico según el nombre del archivo («G_IA2025_1.16 …» → «1.16»), o None."""
    nombre = Path(nombre).stem
    if nombre.lower().startswith("rec"):
        return None
    m = RE_NUMERO_ARCHIVO.match(nombre)
    return m.group(1) if m else None


def cambiar_letras(ancla, cambiar):
    """Aplica cambiar(texto) -> (inicio, fin, nuevo) o None al primer párrafo con texto del cuadro, sin mover
    el formato: lo nuevo va en la carrera de la primera letra cambiada. Devuelve el ancla."""
    cuerpo = re.search(r'<xdr:txBody>.*?</xdr:txBody>', ancla, re.S)
    if not cuerpo:
        return ancla
    for parrafo in re.findall(r'<a:p>.*?</a:p>', cuerpo.group(0), re.S):
        trozos = list(re.finditer(r'<a:t>([^<]*)</a:t>', parrafo))
        textos_t = [html.unescape(t.group(1)) for t in trozos]
        if not "".join(textos_t).strip():
            continue
        letras = [(c, k) for k, t in enumerate(textos_t) for c in t]
        hecho = cambiar("".join(c for c, _ in letras))
        if not hecho:
            return ancla
        ini, fin, nuevo = hecho
        k0 = letras[ini][1] if ini < len(letras) else letras[-1][1]
        letras = letras[:ini] + [(c, k0) for c in nuevo] + letras[fin:]
        nuevos = ["".join(c for c, k in letras if k == j) for j in range(len(textos_t))]
        piezas, ultimo = [], 0
        for t, texto_nuevo in zip(trozos, nuevos):
            piezas.append(parrafo[ultimo:t.start()] + f'<a:t>{html.escape(texto_nuevo, quote=False)}</a:t>')
            ultimo = t.end()
        nuevo_cuerpo = cuerpo.group(0).replace(parrafo, "".join(piezas) + parrafo[ultimo:], 1)
        return ancla.replace(cuerpo.group(0), nuevo_cuerpo, 1)
    return ancla


def numero_grafico_de(texto):
    """El número de «Gráfico NN» tal como lo escribió el autor («Gráfico 2.1» → «2.1»)."""
    m = RE_NUMERO_GRAFICO.search(texto)
    return m.group(3).rstrip(".") if m else None


def renumerar_grafico(ancla, nuevo):
    """«Gráfico 2.1» → «Gráfico <nuevo>» (con el número del nombre del archivo)."""
    def cambiar(texto):
        m = RE_NUMERO_GRAFICO.search(texto)
        if not m or m.group(3) == nuevo:
            return None
        return m.start(3), m.end(3), nuevo
    return cambiar_letras(ancla, cambiar)


def renumerar_panel(ancla, viejo, nuevo):
    """«2.1.a  …» → «1.1.a  …» si el panel lleva el número viejo del gráfico o el de otro gráfico («4.3.c» en el
    3.3: errata del Excel); los paneles de la hoja del gráfico llevan siempre su número."""
    def cambiar(texto):
        m = RE_NUMERO_PANEL.match(texto)
        if not m or m.group(1) == nuevo or (m.group(1) != viejo and "." not in m.group(1)):
            return None
        return m.start(1), m.end(1), nuevo
    return cambiar_letras(ancla, cambiar)


def numerar_panel(ancla, numero):
    """«a  Número de operaciones» → «8.3.a  Número de operaciones»: el título de panel con solo la letra lleva
    el número del gráfico, como en el .ai (G_MemoriaSupervision_8.3)."""
    def cambiar(texto):
        m = RE_SOLO_LETRA.match(texto)
        if not m:
            return None
        return m.start(1), m.end(0), f"{numero}.{m.group(1)}{HUECO_PANEL}"
    return cambiar_letras(ancla, cambiar)


def sangria_panel(ancla):
    """Sangría francesa del título de panel (todas las publicaciones; petición del usuario, 2026-11-27, 8.2 b): las
    líneas siguientes a la primera (las que parte Excel y las de un salto manual) empiezan donde empieza el título,
    después de «8.2.b  », como en el .ai. Devuelve (ancla, sangría en pt o 0)."""
    cuerpo = re.search(r'<xdr:txBody>.*?</xdr:txBody>', ancla, re.S)
    medir = medidor()
    if not cuerpo or not medir:
        return ancla, 0
    parrafos = [p for p in re.findall(r'<a:p>.*?</a:p>', cuerpo.group(0), re.S)
                if "".join(re.findall(r'<a:t>([^<]*)</a:t>', p)).strip()]
    if not parrafos:
        return ancla, 0
    primero = html.unescape("".join(re.findall(r'<a:t>([^<]*)</a:t>', parrafos[0])))
    m = RE_NUMERO_PANEL.match(primero)
    if not m:
        return ancla, 0
    sangria = medir(primero[:m.end()], 8)
    emu = round(sangria * EMU_PT)

    def con_ppr(parrafo, indent):
        atributos = f'marL="{emu}" indent="{indent}"'
        directo = re.match(r'<a:p>\s*<a:pPr\b([^>]*?)(/?)>', parrafo)
        if directo:
            resto = re.sub(r'\s+(marL|indent)="[^"]*"', "", directo.group(1))
            return parrafo.replace(directo.group(0), f'<a:p><a:pPr {atributos}{resto}{directo.group(2)}>', 1)
        return parrafo.replace("<a:p>", f'<a:p><a:pPr {atributos}/>', 1)
    nuevo = cuerpo.group(0)
    for k, p in enumerate(parrafos):
        nuevo = nuevo.replace(p, con_ppr(p, -emu if k == 0 else 0), 1)
    return ancla.replace(cuerpo.group(0), nuevo, 1), sangria


def dos_espacios_panel(ancla, idioma="es"):
    """Número del panel como «N.x», 2 espacios hasta el título y los espacios dobles del título en uno, aunque
    el texto vaya repartido entre varias carreras (cada letra se queda en su carrera). Devuelve (ancla, lista
    de lo que ha cambiado)."""
    cuerpo = re.search(r'<xdr:txBody>.*?</xdr:txBody>', ancla, re.S)
    if not cuerpo:
        return ancla, []
    hechos, primero, nuevo_cuerpo = [], True, cuerpo.group(0)
    for parrafo in re.findall(r'<a:p>.*?</a:p>', cuerpo.group(0), re.S):
        trozos = list(re.finditer(r'<a:t>([^<]*)</a:t>', parrafo))
        textos_t = [html.unescape(t.group(1)) for t in trozos]
        if not "".join(textos_t).strip():
            continue
        # Cada letra con su carrera
        letras = [(c, k) for k, t in enumerate(textos_t) for c in t]
        todo = "".join(c for c, _ in letras)
        if primero:
            primero = False
            m = RE_NUMERO_PANEL.match(todo)
            if m:
                numero = f"{m.group(1)}.{m.group(2).lower()}"
                cabeza = numero + HUECO_PANEL
                if todo[:m.end()] != cabeza:
                    k_num = letras[m.start(1)][1]
                    letras = [(c, k_num) for c in cabeza] + letras[m.end():]
                    antes = todo[m.start(1):m.start(3)]
                    if antes != numero:
                        hechos.append(f"«{antes}» → «{numero}»")
                    if m.group(3) != HUECO_PANEL:
                        hechos.append("2 espacios entre el número y el título")
                fin_cabeza = len(cabeza)
            else:
                fin_cabeza = 0
        else:
            fin_cabeza = 0
        # Espacios dobles dentro del título: uno
        limpias, quitados, saltos = letras[:fin_cabeza], 0, 0
        for c, k in letras[fin_cabeza:]:
            # Saltos de línea manuales: un espacio. En un título enlazado a una celda, Excel hace de cada línea un
            # párrafo sin la sangría y la segunda línea volvía al borde; partida por Excel, la sangría la alinea
            # bajo el título (8.2 b, probado en Excel; petición del usuario, 2026-11-27)
            # (solo con número de panel delante: «Gráfico 1⏎El peso…» de los recuadros va así a propósito)
            if c in "\n\r\v" and fin_cabeza:
                saltos += 1
                c = " "
            if c == " " and limpias[len(limpias) - 1:] and limpias[-1][0] == " " and len(limpias) > fin_cabeza:
                quitados += 1
                continue
            limpias.append((c, k))
        if quitados > saltos:
            hechos.append("espacios dobles del título en uno")
        if saltos:
            hechos.append("Aviso: salto de línea manual del título cambiado por un espacio: Excel parte la línea él solo "
                          "y la sangría deja la segunda bajo el título (con el salto, volvía al borde)")
        # El título en minúscula salvo nombres propios y siglas (las reglas de las leyendas), si viene en
        # mayúsculas; cada letra sigue en su carrera
        titulo = "".join(c for c, _ in limpias[fin_cabeza:])
        nuevo_titulo = en_minuscula(titulo, idioma)
        if nuevo_titulo != titulo:
            hechos.append(f"en minúscula: «{nuevo_titulo.strip()[:50]}»")
            cola = limpias[fin_cabeza:]
            if len(nuevo_titulo) == len(cola):
                limpias = limpias[:fin_cabeza] + [(c, k) for c, (_, k) in zip(nuevo_titulo, cola)]
            else:
                k0 = cola[0][1] if cola else (limpias[-1][1] if limpias else 0)
                limpias = limpias[:fin_cabeza] + [(c, k0) for c in nuevo_titulo]
        nuevos = ["".join(c for c, k in limpias if k == j) for j in range(len(textos_t))]
        if nuevos == textos_t:
            continue
        piezas, ultimo = [], 0
        for t, texto_nuevo in zip(trozos, nuevos):
            piezas.append(parrafo[ultimo:t.start()] + f'<a:t>{html.escape(texto_nuevo, quote=False)}</a:t>')
            ultimo = t.end()
        nuevo_cuerpo = nuevo_cuerpo.replace(parrafo, "".join(piezas) + parrafo[ultimo:], 1)
    return ancla.replace(cuerpo.group(0), nuevo_cuerpo, 1), list(dict.fromkeys(hechos))


def clasificar_textos(partes, caja, alto_pastilla, ancho_ret):
    """Qué es cada cuadro de texto de la hoja: {índice: (tipo, índice del gráfico)}. Tipos: «fuera» (de la
    retícula), «grafico» (Gráfico NN), «titulo», «fuentes», «panel», «unidades» (texto suelto en la mitad de
    arriba de un gráfico, en su cuarto izquierdo) e «interior» (texto suelto sobre un gráfico, más a la
    derecha). Un texto numerado como título de panel («2.6.a …», «3.a …») lo es aunque esté encima de un
    gráfico o donde iría el título."""
    graficos = [(i, caja(a)) for i, a in enumerate(partes) if ANCLA.fullmatch(a) and "<c:chart " in a]
    tipos, vistos = {}, set()
    for i, a in enumerate(partes):
        if (not ANCLA.fullmatch(a) or es_reticula(a) or es_pastilla(a) or "<c:chart " in a
                or "<xdr:txBody>" not in a or not texto_forma(a).strip()):
            continue
        texto = texto_forma(a)
        x, y, _, _ = caja(a)
        if x >= ancho_ret:
            tipos[i] = ("fuera", None)
        elif "grafico" not in vistos and RE_GRAFICO.match(texto):
            vistos.add("grafico")
            tipos[i] = ("grafico", None)
        elif RE_PANEL.match(texto) or RE_SUBPANEL.match(texto):
            # Numerado: título de panel, aunque el autor lo ponga donde iría el título (gráficos sin título)
            tipos[i] = ("panel", None)
        elif "titulo" not in vistos and y < alto_pastilla:
            vistos.add("titulo")
            tipos[i] = ("titulo", None)
        elif RE_FUENTE.match(texto):
            tipos[i] = ("fuentes", None)
        else:
            # Hasta 7 mm por encima: tras «Tamaño y colocación» las unidades quedan sobre el marco del gráfico
            # (su cuadro, unos 5,5 mm con el margen de dentro); un título de panel queda a 10 mm o más
            encima = [(gi, g) for gi, g in graficos if g[1] - 7 * 36000 <= y <= g[1] + g[3] / 2]
            if encima:
                # El gráfico en cuya caja cae el texto (paneles lado a lado: dos a la misma altura; el más estrecho si
                # uno se ensancha para la leyenda común) y, si no, el más cercano a lo alto
                cx_t = x + caja(a)[2] / 2
                gi, g = min(encima, key=lambda t: (0 if t[1][0] <= cx_t <= t[1][0] + t[1][2] else 1,
                                                   round(abs(t[1][1] - y) / (15 * 36000)), t[1][2], abs(t[1][1] - y)))
                # Unidades: arriba (hasta 12 mm por debajo del borde) y a la izquierda; lo demás, interior (el
                # texto del hueco de un anillo, una etiqueta…)
                unidad = x < g[0] + g[2] / 4 and y <= g[1] + 12 * 36000
                tipos[i] = ("unidades" if unidad else "interior", gi)
            else:
                tipos[i] = ("panel", None)
    return tipos


def separar_grafico_y_titulo(partes, caja, alto_pastilla):
    """Si «Gráfico NN» y el título van en el mismo cuadro (dos párrafos), lo parte en dos cuadros."""
    if any(ANCLA.fullmatch(a) and "<xdr:txBody>" in a and RE_GRAFICO.match(texto_forma(a)) for a in partes):
        return partes, None
    for i, a in enumerate(partes):
        if not ANCLA.fullmatch(a) or "<xdr:txBody>" not in a or caja(a)[1] >= alto_pastilla:
            continue
        cuerpo = re.search(r'<xdr:txBody>.*?</xdr:txBody>', a, re.S).group(0)
        parrafos = re.findall(r'<a:p>.*?</a:p>|<a:p/>', cuerpo, re.S)
        llenos = [k for k, q in enumerate(parrafos) if texto_forma(q).strip()]
        if len(llenos) < 2 or not RE_GRAFICO.match(texto_forma(parrafos[llenos[0]])):
            continue
        inicio = cuerpo.index(parrafos[0])
        cabeza, cola = cuerpo[:inicio], cuerpo[inicio + len("".join(parrafos)):]
        grafico = a.replace(cuerpo, cabeza + parrafos[llenos[0]] + cola)
        titulo = a.replace(cuerpo, cabeza + "".join(parrafos[llenos[1]:]) + cola)
        sig = max(int(n) for n in re.findall(r'<xdr:cNvPr\s+id="(\d+)"', "".join(partes))) + 1
        grafico, _ = renumerar(grafico, sig, nombre_forma(a) + " (Gráfico NN)")
        return partes[:i] + [grafico, titulo] + partes[i + 1:], html.unescape(texto_forma(parrafos[llenos[0]])).strip()
    return partes, None


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
    partes = list(partes_dibujo(dibujo))
    caja = medidas_hoja(z, dibujo)
    partes, separado = separar_grafico_y_titulo(partes, caja, alto_pastilla)
    if separado:
        detalle.append(f"«{separado}» iba en el mismo cuadro que el título: separado en su propio cuadro")
    tipos = clasificar_textos(partes, caja, alto_pastilla, ancho_ret)
    relaciones_dibujo = rels(z, ruta)
    numero_nuevo = numero_de_archivo(estado.get("origen", ""))
    numero_viejo = next((numero_grafico_de(html.unescape(texto_forma(partes[k])))
                         for k, (t, _) in tipos.items() if t == "grafico"), None)
    if numero_nuevo and numero_viejo == numero_nuevo:
        numero_nuevo = None

    def es_tarta_parte(k):
        """¿Es una tarta el gráfico de la parte k del dibujo?"""
        rid = k is not None and re.search(r'<c:chart\b[^>]*\br:id="([^"]+)"', partes[k])
        return bool(rid) and es_tarta(z.read(relaciones_dibujo[rid.group(1)][1]).decode("utf-8"))
    for k, a in enumerate(partes):
        if k not in tipos:
            continue
        tipo = tipos[k][0]
        texto = texto_forma(a)
        corto = html.unescape(texto).replace("\n", " / ")[:60]
        if tipo == "fuera":
            detalle.append(f"Sin tocar, fuera de la retícula: «{corto}»")
        elif tipo == "grafico":
            hechos.add("grafico")
            a = con_marco(a, marco_grafico, filas)
            detalle.append(f"Gráfico NN «{corto}»: Roboto Regular 7 pt, marco y posición de la plantilla")
            if numero_nuevo:
                a = renumerar_grafico(a, numero_nuevo)
                detalle.append(f"  número del nombre del archivo: «{numero_viejo}» → «{numero_nuevo}»")
        elif tipo == "titulo":
            hechos.add("titulo")
            a = con_marco(a, marco_titulo, filas, final_regular=FINAL_TITULO)
            detalle.append(f"Título «{corto}»: Roboto Medium 8,5 pt, marco y posición de la plantilla")
            final = FINAL_TITULO.search(html.unescape(texto))
            if final:
                detalle.append(f"  «{final.group(0).strip()}» al final del título, en Roboto Regular")
        elif tipo == "fuentes":
            a, notas = maquetar_fuentes(a, estado["idioma"])
            detalle.append(f"Fuentes «{corto}»: Roboto Light 7 pt" + "".join(f"; {n}" for n in notas if not n.startswith("Aviso")))
            detalle += [n for n in notas if n.startswith("Aviso")]
        elif tipo == "unidades":
            a = fijar_letra(a, 700, ROBOTO)
            detalle.append(f"Unidades en la hoja «{corto}»: Roboto Regular 7 pt")
        elif tipo == "interior" and es_tarta_parte(tipos[k][1]):
            # El texto del hueco de un anillo (p. ej. «2,3 billones de euros»), como en el TERMINADO
            a = texto_centro_tarta(a)
            a = re.sub(r'<xdr:txBody>.*?</xdr:txBody>', lambda m: cuerpo_centro_tarta(texto_forma(a), "xdr"), a, count=1, flags=re.S)
            detalle.append(f"Texto en el centro de la tarta «{corto}»: la cifra en Roboto Black 24 pt y, debajo, el texto "
                           "en Roboto Regular 7 pt, centrados")
        elif tipo == "interior":
            a = fijar_letra(a, 700, ROBOTO)
            detalle.append(f"Texto sobre el gráfico, a la derecha «{corto}»: Roboto Regular 7 pt, donde lo dejó el autor")
        else:
            a = fijar_letra(a, 800, ROBOTO)
            numero = numero_nuevo or numero_viejo
            con_numero = []
            if numero and re.fullmatch(r'\d+(?:\.\d+)*', numero) and RE_SOLO_LETRA.match(html.unescape(texto_forma(a))):
                a = numerar_panel(a, numero)
                con_numero = [f"con el número del gráfico: «⟪{html.unescape(texto_forma(a)).strip()[:30]}⟫»"]
            a, cambios_panel = dos_espacios_panel(a, estado["idioma"])
            cambios_panel = con_numero + cambios_panel
            if numero and re.fullmatch(r'\d+(?:\.\d+)*', numero):
                renumerado = renumerar_panel(a, numero_viejo, numero)
                if renumerado != a:
                    antes_num = RE_NUMERO_PANEL.match(html.unescape(texto_forma(a))).group(1)
                    a = renumerado
                    cambios_panel.append(f"número del gráfico «{antes_num}» → «{numero}»")
            a, sangria = sangria_panel(a)
            avisos_panel = [c for c in cambios_panel if c.startswith("Aviso: ")]
            cambios_panel = [c for c in cambios_panel if not c.startswith("Aviso: ")]
            # (se dice si el título no cabe en una línea de media página: la sangría está siempre)
            if sangria and (avisos_panel or medidor()(html.unescape(texto_forma(a)).strip(), 8) > 215):
                cambios_panel.append(f"sangría de {sangria / MM:.1f} mm: las líneas siguientes empiezan bajo el título, "
                                     "después del número".replace(".", ",", 1))
            detalle.append(f"Título de panel «{corto}»: Roboto Regular 8 pt" + "".join(f"; {c}" for c in cambios_panel))
            detalle += [f"Aviso: título de panel «{corto}»: " + c[len("Aviso: "):] for c in avisos_panel]
        partes[k] = a
    # Todos los textos, en negro (norma general); lo de fuera de la retícula no se toca
    otros_colores = []
    for k, (tipo, _) in tipos.items():
        if tipo != "fuera":
            partes[k], antes_color = textos_en_negro(partes[k])
            otros_colores += antes_color
    for falta, nombre in (("grafico", "«Gráfico NN»"), ("titulo", "título del gráfico")):
        if falta not in hechos:
            detalle.append(f"Aviso: no encuentro el {nombre}")
    cambios[ruta] = "".join(partes).encode("utf-8")

    # Textos de cada gráfico y de sus formas (unidades)
    relaciones = rels(z, ruta)
    anchos = anchos_graficos(z, dibujo)
    hojas_datos, formas_vinculadas = {}, []
    estilos = z.read("xl/styles.xml").decode("utf-8")
    estilos_antes = estilos
    medir = medidor()
    (x1, w1), (x2, w2) = guias_reticula(dibujo)[0]
    # (lado a lado solo si el paso 1 ha puesto la retícula de los recuadros: dos columnas iguales)
    lado_textos = abs(w1 - w2) <= 0.05 * w1
    for i, rid in enumerate(re.findall(r'<c:chart\b[^>]*\br:id="([^"]+)"', dibujo), 1):
        ruta_graf = relaciones[rid][1]
        graf, cuentas = maquetar_grafico(z.read(ruta_graf).decode("utf-8"), anchos.get(rid))
        graf, minusculas = leyendas_en_minuscula(z, ruta_graf, graf, estado["idioma"], hojas_datos)
        # Textos especiales (guía, págs. 10 y 11), con el ancho que tendrá el trazado en «Tamaño y colocación»
        # (lado a lado, cada panel tiene solo su columna aunque vaya sin leyenda: 8.2 b, años amontonados)
        ancho_final = (x2 + w2 - x1 if anchos.get(rid) and sin_leyenda(graf, anchos[rid]) and not lado_textos
                       else w1) / EMU_PT
        trazado = ancho_final - (ancho_numeros_eje(graf, medir) if medir else 0)
        graf, estilos, especiales = textos_especiales(z, graf, estado["idioma"], hojas_datos, estilos, trazado, medir)
        # Barras y líneas con etiquetas en % (fracciones del autor con formato de porcentaje): como las tartas, los
        # datos no se tocan, «%» como unidad y aviso (decisión del usuario, 2026-11-26, G_MemoriaSupervision_1.1)
        quitado_otros = not es_tarta(graf) and etiquetas_con_porcentaje(graf)
        if quitado_otros:
            especiales.append("Aviso: eliminar el «⟪%⟫» de las cifras en Illustrator (etiquetas de datos con formato de "
                              "porcentaje: los datos del autor no se tocan; «%» como unidad)")
        if es_tarta(graf) or quitado_otros:
            if es_tarta(graf):
                graf, estilos, notas_tarta, quitado = tarta_paso1(z, graf, hojas_datos, estilos)
                especiales += notas_tarta
            else:
                quitado = True
            # «%» como unidad arriba a la izquierda, si el gráfico no la tiene ya
            k = next(j for j, a in enumerate(partes) if f'r:id="{rid}"' in a)
            formas_graf = next((z.read(d).decode("utf-8") for t, d in rels(z, ruta_graf).values()
                                if t.endswith("/chartUserShapes")), "")
            textos_unidades = [texto_forma(u) for u in unidades_de(formas_graf, graf)] + \
                              [texto_forma(partes[j]) for j, (t, g) in tipos.items() if t == "unidades" and g == k]
            if quitado and not any("%" in t for t in textos_unidades):
                sig = max(int(n) for n in re.findall(r'<xdr:cNvPr\s+id="(\d+)"', "".join(partes))) + 1
                partes.insert(k + 1, anclas_unidad_porcentaje(caja(partes[k]), sig))
                tipos = {(j + 1 if j > k else j): (t, (g + 1 if g is not None and g > k else g)) for j, (t, g) in tipos.items()}
                cambios[ruta] = "".join(partes).encode("utf-8")
                especiales.append("unidad «%» añadida arriba a la izquierda")
        # Etiquetas de datos: decimales de la guía y separador «: » (después de pasar las tartas a 0-100)
        graf, notas_etiquetas = etiquetas_datos(graf)
        graf, sin_marco = etiquetas_sin_marco(graf)
        if sin_marco:
            notas_etiquetas.append(f"etiquetas de datos sin borde ni fondo ({sin_marco})")
        graf, areas = areas_sin_fondo(graf)
        if areas:
            notas_etiquetas.append(" y ".join(areas) + " sin fondo ni borde")
        graf, orto = etiquetas_ortotipografia(z, graf, hojas_datos, estado["idioma"])
        if orto:
            notas_etiquetas.append("texto de las etiquetas con las reglas de FUENTES: " + ", ".join(orto[:4]))
        especiales += notas_etiquetas
        graf, antes_color = textos_en_negro(graf)
        otros_colores += antes_color
        cambios[ruta_graf] = graf.encode("utf-8")
        linea = f"Panel {i}: general e interior Roboto Regular 6 pt"
        if cuentas:
            linea += "; " + ", ".join(cuentas)
        for tipo, ruta_formas in rels(z, ruta_graf).values():
            if tipo.endswith("/chartUserShapes"):
                formas, unidades, otros = maquetar_formas_grafico(z.read(ruta_formas).decode("utf-8"), graf)
                formas, hechos = textos_trimestres(formas, estado["idioma"])
                if hechos:
                    especiales.append("trimestres: " + ", ".join(hechos[:4]))
                formas, antes_color = textos_en_negro(formas)
                otros_colores += antes_color
                cambios[ruta_formas] = formas.encode("utf-8")
                formas_vinculadas.append((z.read(ruta_formas).decode("utf-8"), formas))
                if unidades:
                    linea += "; unidades 7 pt: " + ", ".join(f"«{u}»" for u in unidades)
                if otros:
                    linea += "; textos interiores 6 pt: " + ", ".join(f"«{u}»" for u in otros)
        if minusculas:
            linea += "; leyendas: " + ", ".join(minusculas)
        avisos = [e for e in especiales if "Aviso" in e]
        if especiales:
            linea += "; " + "; ".join(e.split(" — Aviso")[0] for e in especiales if not e.startswith("Aviso"))
        detalle.append(linea)
        for a in avisos:
            detalle.append(f"Aviso: panel {i}: " + a.split("Aviso: ", 1)[1])
    # Trimestres en los textos de la hoja (títulos, paneles, unidades, notas…); lo de fuera de la retícula no
    hechos = []
    for k, (tipo, _) in tipos.items():
        if tipo != "fuera":
            partes[k], h = textos_trimestres(partes[k], estado["idioma"])
            hechos += h
    if hechos:
        cambios[ruta] = "".join(partes).encode("utf-8")
        detalle.append("Trimestres en los textos de la hoja: " + ", ".join(hechos[:6]))
    if otros_colores:
        cuenta = Counter(otros_colores)
        detalle.append("Textos en negro (norma general): había " + ", ".join(
            f"{c} ({n})" for c, n in cuenta.most_common(6)) + ". Comprueba que ninguno estaba así a propósito "
            "(p. ej., un texto en blanco sobre un fondo oscuro)")
    else:
        detalle.append("Textos en negro (norma general): ya lo estaban todos")
    # Cuadros de texto vinculados a una celda: Excel, al abrir, vuelve a poner el texto de la celda; si se ha
    # cambiado el texto del cuadro (título de panel, trimestres…), se escribe también en su celda
    pares = [(dibujo, "".join(partes))] + formas_vinculadas
    vinculos, avisos_vinculos = escribir_vinculos(z, pares, hojas_datos)
    if vinculos:
        detalle.append("Textos vinculados a celdas, cambiados también en su celda (si no, Excel los repone): "
                       + ", ".join(vinculos[:6]))
    detalle += avisos_vinculos
    for ruta_hoja, hoja in hojas_datos.items():
        cambios[ruta_hoja] = hoja.encode("utf-8")
    if estilos != estilos_antes:
        cambios["xl/styles.xml"] = estilos.encode("utf-8")
    return cambios, detalle


RE_FORMA_VINCULADA = re.compile(r'<(xdr|cdr):sp\b[^>]*\btextlink="([^"]+)".*?</\1:sp>', re.S)


def textos_vinculados(xml):
    """{id de la forma: (referencia, texto)} de los cuadros de texto vinculados a una celda."""
    salida = {}
    for m in RE_FORMA_VINCULADA.finditer(xml):
        ident = re.search(r'<(?:xdr|cdr):cNvPr\b[^>]*\bid="(\d+)"', m.group(0))
        if ident and "#REF!" not in m.group(2):
            salida[ident.group(1)] = (html.unescape(m.group(2)), html.unescape(texto_forma(m.group(0))))
    return salida


def escribir_vinculos(z, pares, hojas):
    """Por cada (xml antes, xml después) de un dibujo: los cuadros vinculados cuyo texto ha cambiado pasan su
    texto nuevo a la celda. Solo los que ha cambiado la app: si el autor tenía el cuadro distinto de la
    celda, manda la celda, como en Excel. Devuelve (cambios, avisos)."""
    hechos, avisos = [], []
    compartidos = None
    for antes, despues in pares:
        viejos = textos_vinculados(antes)
        for ident, (ref, texto) in textos_vinculados(despues).items():
            if ident not in viejos or viejos[ident] == (ref, texto):
                continue
            m = re.fullmatch(r"=?(?:'([^']+)'|([^!]+))!\$?([A-Z]+)\$?(\d+)", ref.strip())
            if not m:
                avisos.append(f"Aviso: «{texto[:40]}» va vinculado a «{ref}», que no es una celda: Excel puede "
                              "reponer el texto anterior al abrir el libro")
                continue
            try:
                ruta_hoja = hoja_de(z, m.group(1) or m.group(2))
            except Fallo:
                avisos.append(f"Aviso: «{texto[:40]}» va vinculado a «{ref}» y no encuentro esa hoja")
                continue
            hoja = hojas.get(ruta_hoja) or z.read(ruta_hoja).decode("utf-8")
            c = celda(hoja, m.group(3) + m.group(4))
            if not c:
                avisos.append(f"Aviso: «{texto[:40]}» va vinculado a la celda {ref}, que está vacía")
                continue
            if compartidos is None:
                compartidos = textos_compartidos(z)
            if texto_de_celda(c, compartidos) == texto:
                continue
            if "<f" in c.group(0):
                avisos.append(f"Aviso: la celda {ref} (de «{texto[:40]}») es una fórmula: solo se cambia su valor "
                              "guardado; si Excel la recalcula, vuelve el texto anterior")
            hojas[ruta_hoja] = poner_texto_celda(hoja, c, texto)
            hechos.append(f"{ref}: «{texto[:40]}»")
    return hechos, avisos


# ---------------------------------------------------------------- textos

EMU_PT = 12700
ROBOTO, ROBOTO_MEDIUM, ROBOTO_LIGHT = "Roboto", "Roboto Medium", "Roboto Light"
RE_GRAFICO = re.compile(r'\s*(Gráfico|Grafico|Chart|Figure)\s+\S+\s*$', re.I)
RE_FUENTE = re.compile(r'\s*(FUENTES?|SOURCES?|NOTAS?)\b', re.I)
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
NOTA_LETRA = re.compile(r'\s*([a-z])(?:\.|:|\t)[\t ]*')   # «a.», «a:» (G_IA2025_1.17) o «a» + tabulador
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
                # «¨» de apertura (teclado: la diéresis en lugar de las comillas, G_IA2025_1.1) también cuenta
                if c in "“¨" or (c == '"' and not abierta[0]):
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
    if m:
        return rels(z, "xl/workbook.xml")[m.group(1)][1]
    if nombre == HOJA_GRAFICO:
        # Hay autores que la llaman de otra forma («G1» y «D1» para los datos): la primera hoja con gráficos
        relaciones = rels(z, "xl/workbook.xml")
        for rid in re.findall(r'<sheet\b[^>]*\br:id="([^"]+)"', wb):
            hoja = relaciones[rid][1]
            for tipo, dibujo in rels(z, hoja).values():
                if tipo.endswith("/drawing") and any(t.endswith("/chart") for t, _ in rels(z, dibujo).values()):
                    return hoja
    raise Fallo(f"No hay hoja «{nombre}»")


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
BAJADA_SOLO_SIN_TITULO = 3 * 72 / 25.4   # un solo gráfico sin título de panel: todo 3 mm más abajo
INTERLINEA_TITULO_PANEL = 9.6
MM = 72 / 25.4
SUBIDA_GRAFICO = 0.5 * MM
ENTRE_PANELES = 8.5 * MM
HASTA_FUENTES = 5 * MM
FILAS_PANEL, FILAS_MIN_TRAZADO = 9, 7
# Las 9 filas se miden por lo que se ve: de lo alto de la letra del número más alto del eje a lo bajo de la de
# las categorías. Las cajas de texto de Excel sobran por arriba (1,7 pt) y por abajo (los 4 pt bajo las
# categorías y lo de debajo de la línea de base): medido en Excel con el 2.6, el panel quedaba 5,1 pt corto.
LETRA_ARRIBA, LETRA_ABAJO = 1.7, 3.4
LETRA_VISIBLE = LETRA_ARRIBA + LETRA_ABAJO
TITULO_PANEL_A_GRAFICO = 7.377 * MM   # del final del título de panel al gráfico (Illus, título de 1 línea)
SUBIDA_CON_UNIDADES = 0.7 * MM
UNIDADES_A_GRAFICO = 2 * MM          # del final de las unidades al borde de arriba del trazado
LEYENDA_A_LA_IZQUIERDA = 3 * MM      # el cuadro de la leyenda tiene aire alrededor: así su texto cae en la columna 2
# Ancho máximo del cuadro de la leyenda: empieza 3 mm antes de la columna 2 y llega hasta su final (antes acababa
# 3 mm antes y partía en dos líneas entradas que caben en una: G_IA2025_2.1, 1.33, 1.35; el texto sigue sin pasar
# del final de la columna, por el margen de dentro del cuadro)
ANCHO_LEYENDA = lambda w2: w2 / EMU_PT + LEYENDA_A_LA_IZQUIERDA
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
    return medir


# Hijos de un grupo de dibujo
RE_HIJO_GRUPO = re.compile(r'<(/?)xdr:(sp|grpSp|graphicFrame|cxnSp|pic)\b[^>]*?(/?)>')


def hijos_grupo(grp):
    """Los elementos de primer nivel dentro de un <xdr:grpSp> (sin su nvGrpSpPr ni grpSpPr)."""
    cuerpo = grp[grp.index(">") + 1:grp.rindex("</xdr:grpSp>")]
    hijos_, nivel, inicio = [], 0, None
    for t in RE_HIJO_GRUPO.finditer(cuerpo):
        if t.group(3):
            if nivel == 0:
                hijos_.append(t.group(0))
            continue
        if not t.group(1):
            if nivel == 0:
                inicio = t.start()
            nivel += 1
        else:
            nivel -= 1
            if nivel == 0:
                hijos_.append(cuerpo[inicio:t.end()])
    return hijos_


def aplanar_grupo(grp, caja_grupo):
    """[(elemento, (x, y, ancho, alto))] de las formas de un grupo (y de sus subgrupos) en EMU desde A1, con la
    escala del grupo (chOff/chExt → su caja real) y el xfrm de cada elemento puesto en su sitio."""
    gx, gy, gw, gh = caja_grupo
    xf = re.search(r'<xdr:grpSpPr\b.*?<a:xfrm\b[^>]*>(.*?)</a:xfrm>', grp, re.S).group(1)
    ch_o = tuple(map(int, re.search(r'<a:chOff x="(-?\d+)" y="(-?\d+)"/>', xf).groups()))
    ch_e = tuple(map(int, re.search(r'<a:chExt cx="(\d+)" cy="(\d+)"/>', xf).groups()))
    sx, sy = gw / (ch_e[0] or 1), gh / (ch_e[1] or 1)
    planas = []
    for h in hijos_grupo(grp):
        m = re.search(r'<a:off x="(-?\d+)" y="(-?\d+)"/>\s*<a:ext cx="(\d+)" cy="(\d+)"/>', h)
        if not m:
            continue
        ox, oy, ex, ey = map(int, m.groups())
        caja_h = (round(gx + (ox - ch_o[0]) * sx), round(gy + (oy - ch_o[1]) * sy), round(ex * sx), round(ey * sy))
        if h.startswith("<xdr:grpSp"):
            planas += aplanar_grupo(h, caja_h)
        else:
            x, y, w, hh = caja_h
            planas.append((h[:m.start()] + f'<a:off x="{x}" y="{y}"/><a:ext cx="{w}" cy="{hh}"/>' + h[m.end():], caja_h))
    return planas


def desagrupar(z, dibujo):
    """Grupos del autor que llevan un gráfico (todo agrupado: pastilla, títulos, gráfico, FUENTES…): cada
    elemento pasa a ser una forma suelta, anclada a sus celdas, en el mismo sitio. La retícula no se toca.
    Devuelve el dibujo y los nombres de los grupos deshechos."""
    medir = medidas_hoja(z, dibujo)
    deshechos = []
    for m in reversed(list(ANCLA.finditer(dibujo))):
        a = m.group(0)
        grp = re.search(r'<xdr:grpSp>.*</xdr:grpSp>', a, re.S)
        if not grp or es_reticula(a) or "<c:chart " not in a:
            continue
        nuevas = []
        for elem, (x, y, w, h) in aplanar_grupo(grp.group(0), medir(a)):
            c1, o1, r1, f1 = medir.a_celda(x, y)
            c2, o2, r2, f2 = medir.a_celda(x + w, y + h)
            nuevas.append(f'<xdr:twoCellAnchor><xdr:from><xdr:col>{c1}</xdr:col><xdr:colOff>{o1}</xdr:colOff>'
                          f'<xdr:row>{r1}</xdr:row><xdr:rowOff>{f1}</xdr:rowOff></xdr:from><xdr:to><xdr:col>{c2}</xdr:col>'
                          f'<xdr:colOff>{o2}</xdr:colOff><xdr:row>{r2}</xdr:row><xdr:rowOff>{f2}</xdr:rowOff></xdr:to>'
                          f'{elem}<xdr:clientData/></xdr:twoCellAnchor>')
        dibujo = dibujo[:m.start()] + "".join(nuevas) + dibujo[m.end():]
        deshechos.append(nombre_forma(a))
    return dibujo, deshechos


UNIDADES_EJE = {"hundreds": 1e2, "thousands": 1e3, "tenThousands": 1e4, "hundredThousands": 1e5, "millions": 1e6,
                "tenMillions": 1e7, "hundredMillions": 1e8, "billions": 1e9, "trillions": 1e12}


def factor_unidades(eje):
    """Entre cuánto divide Excel los números de un eje de valores con «Mostrar unidades» (1 sin ellas)."""
    unidad = re.search(r'<c:dispUnits>.*?</c:dispUnits>', eje, re.S)
    if not unidad:
        return 1
    fijo = re.search(r'<c:builtInUnit val="(\w+)"/>', unidad.group(0))
    propio = re.search(r'<c:custUnit val="([^"]+)"/>', unidad.group(0))
    return UNIDADES_EJE.get(fijo.group(1), 1) if fijo else (float(propio.group(1)) or 1) if propio else 1


def ancho_numeros_eje(xml, medir):
    """Lo que ocupan a la izquierda los números del eje de valores (pt, aproximado por el dato mayor). Si no hay
    eje de valores a la izquierda que se vea (borrado o sin cifras), nada: el trazado empieza al principio de la
    columna (G_IA2025_3.6, cifras sobre las barras y eje borrado, 2026-11-26)."""
    izquierdos = [e for e in re.findall(r'<c:valAx>.*?</c:valAx>', xml, re.S) if '<c:axPos val="l"/>' in e]
    # Sin eje vertical a la izquierda, o ninguno con cifras: el trazado empieza al principio de la columna 1
    if all('<c:delete val="1"/>' in e or '<c:tickLblPos val="none"/>' in e for e in izquierdos):
        return AIRE_TRAZADO_SIN_EJE
    # Con «Mostrar unidades» (miles…), los números como se ven (G_MemoriaSupervision_8.2 b: «320», no «313.500»;
    # el trazado empezaba 20 pt tarde)
    factor = next((factor_unidades(e) for e in izquierdos
                   if '<c:delete val="1"/>' not in e and '<c:tickLblPos val="none"/>' not in e), 1)
    valores = [abs(float(v)) / factor for v in re.findall(r'<c:val>.*?</c:val>', xml, re.S)
               for v in re.findall(r'<c:v>(-?[\d.Ee+-]+)</c:v>', v)]
    negativos = any(float(v) < 0 for v in re.findall(r'<c:val>.*?<c:v>(-[\d.]+)</c:v>', xml, re.S))
    mayor = f"{round(max(valores) * 1.1) if valores else 100:,}".replace(",", ".")
    # Excel deja unos 8 pt entre el número y el eje; si no caben, corre todo el trazado a la derecha
    return medir(("-" if negativos else "") + mayor, 7) + 8


def nombres_series(xml):
    return [nombre_serie(t) for t in re.findall(r'<c:ser>.*?</c:ser>', xml, re.S)
            if re.search(r'<c:v>', (re.search(r'<c:tx>.*?</c:tx>', t, re.S) or re.match("", "")).group(0))]


def disposicion(xml, ancho, alto, dentro, leyenda, medir):
    """Área de trazado interior en `dentro` = (x, y, ancho, alto) y leyenda en `leyenda` = (x, y, ancho
    máximo), todo en pt dentro del gráfico de `ancho` × `alto` pt. La leyenda, con el ancho justo de su
    entrada más larga (una entrada por línea) y el alto de sus entradas; con `leyenda` None, no se toca."""
    x, y, w, h = dentro
    trazado = ('<c:layout><c:manualLayout><c:layoutTarget val="inner"/><c:xMode val="edge"/><c:yMode val="edge"/>'
               f'<c:x val="{x / ancho:.6f}"/><c:y val="{y / alto:.6f}"/><c:w val="{w / ancho:.6f}"/>'
               f'<c:h val="{h / alto:.6f}"/></c:manualLayout></c:layout>')
    xml = re.sub(r'(<c:plotArea>\s*)(<c:layout>.*?</c:layout>|<c:layout/>)?', lambda m: m.group(1) + trazado,
                 xml, count=1, flags=re.S)
    if leyenda is None:
        return xml
    lx, ly, lmax = leyenda[:3]
    centrada = len(leyenda) > 3 and leyenda[3]   # ly es entonces el centro (tartas)
    entradas = entradas_leyenda(xml) or [("Serie", False)]
    # Muestra de color, separación y márgenes de la leyenda (pt); la de una línea mide unos 16 pt más
    con_lineas = any(linea for _, linea in entradas)
    clave = CLAVE_LEYENDA + (CLAVE_LINEA_DE_MAS if con_lineas else 0)
    if not centrada:
        # Que la muestra empiece medio milímetro después de la línea de la columna 2 (petición del usuario,
        # 2026-11-25, G_IA2025_1.1; medido en el PDF de Excel con la leyenda a 3 mm de la columna): si todas las
        # entradas son líneas, Excel pone muestras anchas que empezaban 1,3 mm antes de la línea; si hay barras
        # (también con la muestra ancha « »), muestras más estrechas que la rozaban (0,2 mm antes)
        solo_lineas = all(linea for _, linea in entradas)
        corrimiento = (MUESTRA_LINEA_ANTES if solo_lineas else MUESTRA_BARRA_ANTES) + 0.5 * MM
        lx += corrimiento
        lmax -= corrimiento   # y sigue sin pasar del final de la columna 2
    # Excel centra las entradas en el cuadro: con el ancho justo de la línea más larga (partiendo los nombres
    # que no caben en la columna 2), la muestra queda al principio
    # Excel dibuja el texto algo más ancho que la suma de los anchos de las letras (como en Cuadros, un 5 %): si el
    # cuadro se ajusta justo, parte en dos líneas entradas que aquí cabían en una y el alto ya no llega (las
    # entradas se montan o desaparecen; G_IA2025_1.22, 2026-11-26)
    medir_excel = lambda t, sz: medir(t, sz) * TEXTO_EXCEL_MAS_ANCHO
    # Si una entrada se parte en el ancho máximo: con lo que mide Excel de verdad (medido en el PDF: el texto, como
    # nuestra medida; del borde del cuadro al texto, 13 pt, y 16 más con muestra de línea). Con el margen de 1,06 y la
    # clave de 17 partía entradas que caben y Excel abría la leyenda a todo el alto (G_MemoriaSupervision_4.5,
    # G_IA2025_2.1). El ancho del cuadro, en cambio, con el margen (si no, Excel parte lo que cabía: 1.22)
    partidos = [partir_lineas(n, lmax - texto_desde(con_lineas) - HUECO_DERECHA_LEYENDA, 7, medir) for n, _ in entradas]
    lw = min(lmax, max(w * TEXTO_EXCEL_MAS_ANCHO for anchos in partidos for w in anchos) + clave + 2 + HOLGURA_LEYENDA)
    lh = alto_entradas(partidos)
    if centrada:
        ly = max(0, ly - lh / 2)

    def cambiar(m):
        lay = ('<c:layout><c:manualLayout><c:xMode val="edge"/><c:yMode val="edge"/>'
               f'<c:x val="{lx / ancho:.6f}"/><c:y val="{ly / alto:.6f}"/><c:w val="{lw / ancho:.6f}"/>'
               f'<c:h val="{min(lh, alto - ly) / alto:.6f}"/></c:manualLayout></c:layout>')
        bloque = re.sub(r'<c:layout>.*?</c:layout>|<c:layout/>', "", m.group(0), count=1, flags=re.S)
        # El esquema pide el layout detrás de las entradas (<c:legendEntry>)
        entradas = list(re.finditer(r'<c:legendEntry>.*?</c:legendEntry>', bloque, re.S))
        if entradas:
            return bloque[:entradas[-1].end()] + lay + bloque[entradas[-1].end():]
        return re.sub(r'(<c:legendPos val="\w+"/>)', lambda p: p.group(1) + lay, bloque, count=1)
    return re.sub(r'<c:legend>.*?</c:legend>', cambiar, xml, count=1, flags=re.S)


MUESTRA_LINEA_ANTES = 1.3 * MM   # lo que la muestra de línea empezaba antes de la columna 2 con la leyenda a 3 mm
MUESTRA_BARRA_ANTES = 0.2 * MM   # y la de las leyendas con barras
def alto_entradas(partidos):
    """Alto (pt) de una leyenda con esas entradas (cada una, los anchos de sus líneas). Excel reparte el cuadro a
    partes iguales entre las entradas y centra cada una en su hueco: con entradas de dos o más líneas, el hueco
    tiene que dejar aire o invaden la de al lado (G_IA2025_1.22, «energéticas» sobre «Combustibles»)."""
    lineas = max((len(a) for a in partidos), default=1)
    return len(partidos) * (lineas * 7 * INTERLINEA + (1.5 if lineas == 1 else AIRE_ENTRADA_VARIAS_LINEAS)) + 4


def alto_leyenda_necesario(xml, lmax, medir):
    """El alto que necesitará la leyenda en la columna 2 (lmax pt de ancho), como lo calcula `disposicion`."""
    entradas = entradas_leyenda(xml) or [("Serie", False)]
    con_lineas = any(linea for _, linea in entradas)
    clave = CLAVE_LEYENDA + (CLAVE_LINEA_DE_MAS if con_lineas else 0)
    solo_lineas = all(linea for _, linea in entradas)
    lmax -= (MUESTRA_LINEA_ANTES if solo_lineas else MUESTRA_BARRA_ANTES) + 0.5 * MM
    return alto_entradas([partir_lineas(n, lmax - texto_desde(con_lineas) - HUECO_DERECHA_LEYENDA, 7, medir)
                          for n, _ in entradas])


AIRE_ENTRADA_VARIAS_LINEAS = 9.0   # pt entre entradas de varias líneas (medido en Excel, 1.22: con menos se tocan)
TEXTO_DESDE_BORDE = 13            # pt del borde izquierdo de la leyenda al texto (muestra de barra; medido en Excel)
HUECO_DERECHA_LEYENDA = 3         # pt que deja Excel a la derecha del texto (2) y 1 de holgura


def texto_desde(con_lineas):
    return TEXTO_DESDE_BORDE + (CLAVE_LINEA_DE_MAS if con_lineas else 0)


TEXTO_EXCEL_MAS_ANCHO = 1.06   # lo que Excel dibuja el texto más ancho que la suma de las letras (medido en Cuadros: 5 %)
HOLGURA_LEYENDA = 3            # pt de más en el ancho de la leyenda, para que Excel no parta las líneas que caben
CLAVE_LEYENDA = 7 + 4 + 6
CLAVE_LINEA_DE_MAS = 16


def partir_lineas(texto, ancho_pt, sz, medir):
    """Anchos de las líneas en que se parte el texto, por palabras, como Excel."""
    espacio, lineas, actual = medir(" ", sz), [], 0.0
    for palabra in texto.split():
        w = medir(palabra, sz)
        if actual and actual + espacio + w > ancho_pt:
            lineas.append(actual)
            actual = w
        else:
            actual += (espacio if actual else 0) + w
    return lineas + [actual]


def entradas_leyenda(xml):
    """(nombre, ¿muestra de línea?) de cada entrada visible de la leyenda: las series sin las borradas de la
    leyenda. Muestra de línea: series de líneas o de dispersión con línea."""
    leyenda = re.search(r'<c:legend>.*?</c:legend>', xml, re.S)
    borradas = set(re.findall(r'<c:legendEntry><c:idx val="(\d+)"/><c:delete val="1"/>', leyenda.group(0))) if leyenda else set()
    entradas = []
    if es_tarta(xml):
        # En las tartas cada entrada es una categoría (porción)
        return [(e, False) for k, e in enumerate(etiquetas_categorias(xml)) if str(k) not in borradas]
    tipo = {s: g.group(1) for g in GRUPOS.finditer(xml) for s in re.findall(r'<c:ser>.*?</c:ser>', g.group(0), re.S)}
    for k, ser in enumerate(orden_leyenda(xml)):
        nombre = re.search(r'<c:tx>.*?<c:v>([^<]*)</c:v>.*?</c:tx>', ser, re.S)
        if str(k) in borradas or not nombre:
            continue
        sppr = hijo(hijos(ser), "spPr") or ""
        sin_linea = re.search(r'<a:ln\b[^>]*>\s*<a:noFill/>', sppr)
        # Series sin ningún dato: Excel no las enseña en la leyenda (el 1.14, panel a: contaban para su alto). La muestra
        # ancha de la app sí ocupa su hueco (texto en blanco): cuenta (1.28, panel a: si no, «Inmigrantes» no cabía)
        valores = re.search(r'<c:(?:val|yVal)>.*?</c:(?:val|yVal)>', ser, re.S)
        if valores and not es_muestra(ser) and not re.search(r'<c:pt idx="\d+">\s*<c:v>[^<]+</c:v>', valores.group(0)):
            continue
        # La línea de referencia del autor (todo 100 o 50): el paso 4 la hace línea base, fuera de la leyenda (3.2 a)
        if tipo[ser] in ("lineChart", "line3DChart") and es_constante_base(ser, xml=xml):
            continue
        entradas.append((html.unescape(nombre.group(1)),
                         tipo[ser] in ("lineChart", "line3DChart", "scatterChart", "radarChart") and not sin_linea))
    return entradas


def sin_leyenda(xml, ancho_pt):
    """Por qué el autor ha dejado el gráfico sin leyenda (None si la lleva): no la hay, ha borrado todas sus
    entradas o la ha encogido a menos de 10 pt de ancho, donde no se ve (en el 2.6, el panel a)."""
    leyenda = re.search(r'<c:legend>.*?</c:legend>', xml, re.S)
    if not leyenda:
        return "no tiene leyenda"
    series = {str(k) for k in range(len(orden_leyenda(xml)))}
    borradas = set(re.findall(r'<c:legendEntry><c:idx val="(\d+)"/><c:delete val="1"/>', leyenda.group(0)))
    if series and series <= borradas:
        return "ha borrado todas las entradas de la leyenda"
    w = re.search(r'<c:manualLayout>.*?<c:w val="([^"]+)"', leyenda.group(0), re.S)
    if w and float(w.group(1)) * ancho_pt < 10:
        return f"ha encogido la leyenda a {float(w.group(1)) * ancho_pt:.0f} pt de ancho, donde no se ve"
    return None


RE_NUMERO_SUELTO = re.compile(r'\s*\(?\s*[-+]?[\d.,]+\s*\)?\s*%?\s*$')


def es_horizontal(xml):
    """¿Gráfico de barras horizontales?"""
    return bool(re.search(r'<c:barDir val="bar"/>', xml or ""))


def girado(ancla):
    """¿Texto girado 90° (título del eje vertical)? Las unidades siempre van en horizontal."""
    xfrm = re.search(r'<a:xfrm\b[^>]*>', ancla)
    rot = re.search(r'\brot="(-?\d+)"', xfrm.group(0)) if xfrm else None
    if rot and int(rot.group(1)) % 21600000 in (5400000, 16200000):
        return True
    cuerpo = re.search(r'<a:bodyPr\b[^>]*>', ancla)
    vert = re.search(r'\bvert="(\w+)"', cuerpo.group(0)) if cuerpo else None
    return bool(vert and vert.group(1) != "horz")


def caja_rel(ancla):
    """(x0, y0, x1, y1) del ancla de una forma del gráfico, en fracciones del gráfico."""
    fr = re.search(r'<cdr:from>\s*<cdr:x>([^<]+)</cdr:x>\s*<cdr:y>([^<]+)</cdr:y>', ancla)
    to = re.search(r'<cdr:to>\s*<cdr:x>([^<]+)</cdr:x>\s*<cdr:y>([^<]+)</cdr:y>', ancla)
    return float(fr.group(1)), float(fr.group(2)), float(to.group(1)) if to else float(fr.group(1)), \
        float(to.group(2)) if to else float(fr.group(2))


def trazado_rel(xml):
    """(x, y, w, h) del área de trazado interior, en fracciones del gráfico, o None si no tiene disposición."""
    lay = re.search(r'<c:plotArea>\s*<c:layout>\s*<c:manualLayout>(.*?)</c:manualLayout>', xml or "", re.S)
    if not lay or '<c:layoutTarget val="inner"/>' not in lay.group(1):
        return None
    f = {k: float(v) for k, v in re.findall(r'<c:([xywh]) val="([^"]+)"/>', lay.group(1))}
    return (f["x"], f["y"], f["w"], f["h"]) if len(f) == 4 else None


def es_unidad_grafico(ancla, xml=None):
    """Unidades dentro del gráfico: siempre texto horizontal y no un número suelto («(2)»). En barras
    verticales y líneas, cuadro en el 20 % de arriba y el cuarto de la izquierda (donde empieza el eje; lo de
    más a la derecha es una etiqueta, como «Elecciones EEUU» sobre una barra). En barras horizontales, las del
    eje de valores: debajo del trazado."""
    texto = html.unescape(texto_forma(ancla)).strip()
    if girado(ancla) or RE_NUMERO_SUELTO.fullmatch(texto) and "%" not in texto:
        return False
    x, y, _, _ = caja_rel(ancla)
    if es_horizontal(xml):
        t = trazado_rel(xml)
        # Debajo del trazado o, como en un gráfico vertical, arriba a la izquierda (G_MemoriaSupervision_2.7 b: se
        # quedaba arriba, cortado; la guía y el .ai las ponen debajo de los números del eje)
        arriba = y < 0.2 and x < 0.25 and not re.match(r'(?:Gr[áa]fico|Chart)\s+\d|\d+(?:\.\d+)*\.[a-z]\b', texto)
        return y >= (t[1] + t[3] - 0.02 if t else 0.75) or arriba
    return y < 0.2 and x < 0.25


def unidades_de(formas, xml=None):
    """Las anclas de las unidades en las formas del gráfico."""
    return [a for a in re.findall(r'<cdr:relSizeAnchor\b.*?</cdr:relSizeAnchor>', formas, re.S)
            if texto_forma(a).strip() and es_unidad_grafico(a, xml)]


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


# Barras horizontales (guía; «GIng_DO2626_05 HORIZONTAL TERMINADO»)
UNIDADES_BAJO_NUMEROS = 2 * MM    # de los números del eje horizontal a las unidades, debajo
TITULO_GIRADO_A_CATEGORIAS = 2 * MM


def ancho_categorias_izquierda(xml, medir):
    """Lo que ocupan a la izquierda las categorías de unas barras horizontales (pt, más el aire hasta el eje)."""
    eje = next((e.group(0) for e in re.finditer(r'<c:catAx>.*?</c:catAx>', xml, re.S)
                if re.search(r'<c:axPos val="[lr]"/>', e.group(0)) and '<c:delete val="1"/>' not in e.group(0)), "")
    cuerpo = re.search(r'<a:defRPr\b[^>]*\bsz="(\d+)"', eje)
    sz = int(cuerpo.group(1)) / 100 if cuerpo else 7
    largo = max([medir(l, sz) for e in etiquetas_categorias(xml) for l in e.split("\n")] or [0])
    return largo + 8 if eje else 0


def media_ultima_categoria(xml, sz, medir, W=None):
    """Si las categorías van sobre las marcas (`crossBetween midCat`: líneas y áreas), la mitad (pt) de lo que
    sobresale por la derecha del trazado: la última categoría o la etiqueta de datos del último punto, la mayor.
    0 si van entre marcas (barras) o no hay eje de categorías abajo."""
    if not re.search(r'<c:crossBetween val="midCat"/>', xml):
        return 0
    eje = next((e.group(0) for e in re.finditer(r'<c:(?:catAx|dateAx)>.*?</c:(?:catAx|dateAx)>', xml, re.S)
                if re.search(r'<c:axPos val="b"/>', e.group(0)) and '<c:delete val="1"/>' not in e.group(0)
                and '<c:tickLblPos val="none"/>' not in e.group(0)), None)
    if not eje:
        return 0
    cat = re.search(r'<c:cat>.*?</c:cat>', xml, re.S)
    if not cat:
        return 0
    textos = etiquetas_categorias(xml)
    if textos:
        ultima = textos[-1]
    else:
        # Numéricas («2025») o fechas: el último valor; las fechas, con el ancho de «sept-25»
        vs = re.findall(r'<c:v>([^<]*)</c:v>', cat.group(0))
        formato = re.search(r'<c:numFmt formatCode="([^"]*)"', eje)
        fecha = "<c:dateAx>" in eje or (formato and re.search(r'[my]', re.sub(r'\[[^\]]*\]|"[^"]*"', "", html.unescape(formato.group(1)).lower())))
        ultima = "sept-25" if fecha else (cifra(float(vs[-1])) if vs and es_numero(vs[-1]) else (vs[-1] if vs else ""))
    mitad = max([medir(l, sz) for l in ultima.split("\n")] or [0]) / 2
    # La etiqueta de datos del último punto, si la hay (6 pt)
    n = re.search(r'<c:ptCount val="(\d+)"', cat.group(0))
    ultimo = int(n.group(1)) - 1 if n else None
    for ser in re.findall(r'<c:ser>.*?</c:ser>', xml, re.S):
        val = re.search(r'<c:val>.*?</c:val>', ser, re.S)
        v = val and re.search(rf'<c:pt idx="{ultimo}">\s*<c:v>([^<]*)</c:v>', val.group(0))
        if not v or not es_numero(v.group(1)):
            continue
        etiquetas = re.search(r'<c:dLbls>.*?</c:dLbls>', ser, re.S)
        if not etiquetas:
            continue
        propia = re.search(rf'<c:dLbl><c:idx val="{ultimo}"/>.*?</c:dLbl>', etiquetas.group(0), re.S)
        visible = ('<c:showVal val="1"/>' in propia.group(0) and '<c:delete val="1"/>' not in propia.group(0)) if propia \
            else '<c:showVal val="1"/>' in re.sub(r'<c:dLbl>.*?</c:dLbl>', "", etiquetas.group(0), flags=re.S)
        if visible:
            mitad = max(mitad, sobresale_etiqueta(ser, propia.group(0) if propia else "", etiquetas.group(0),
                                                  float(v.group(1)), xml, medir, W))
    return mitad


def sobresale_etiqueta(ser, propia, etiquetas, v, xml, medir, W):
    """Lo que sobresale por la derecha del último punto su etiqueta de datos (pt): con el formato que tiene
    («85,29», no «85,3») y su posición; en las líneas y dispersiones Excel la pone por defecto a la derecha del punto,
    entera fuera, no centrada; si el autor la movió a mano, su desplazamiento (fracción del ancho del gráfico, `W`)
    (G_IA2025_2.3, petición del usuario, 2026-11-26)."""
    general = re.sub(r'<c:dLbl>.*?</c:dLbl>', "", etiquetas, flags=re.S)
    nf = re.search(r'<c:numFmt formatCode="([^"]*)"', propia) or re.search(r'<c:numFmt formatCode="([^"]*)"', general)
    if nf:
        codigo = html.unescape(nf.group(1))
    else:
        cache = re.search(r'<c:val>.*?<c:formatCode>([^<]*)</c:formatCode>', ser, re.S)
        codigo = html.unescape(cache.group(1)) if cache else "General"
    primera = re.sub(r'"[^"]*"|\[[^\]]*\]', "", codigo.split(";")[0])
    dec = len(re.search(r'\.(0+)', primera).group(1)) if re.search(r'\.(0+)', primera) else (
        1 if "general" in primera.lower() else 0)
    # Con «Mostrar unidades» en su eje (miles…), Excel escribe la etiqueta en esas unidades (G_MemoriaSupervision_8.2 b:
    # «285,1», no «285.073,0»; el trazado se acortaba 8 mm)
    grupo = next((g for g in GRUPOS.finditer(xml) if ser in g.group(0)), None)
    ids = re.findall(r'<c:axId val="(\d+)"/>', grupo.group(0)) if grupo else []
    eje_v = next((e for e in re.findall(r'<c:valAx>.*?</c:valAx>', xml, re.S)
                  if re.search(r'<c:axId val="(\d+)"/>', e).group(1) in ids), "")
    v = v / factor_unidades(eje_v)
    texto = f"{v:,.{dec}f}".replace(",", " ").replace(".", ",").replace(" ", ".") + ("\u00a0%" if "%" in primera else "")
    sz = re.search(r'<a:defRPr\b[^>]*\bsz="(\d+)"', propia) or re.search(r'<a:defRPr\b[^>]*\bsz="(\d+)"', general)
    ancho = medir(texto, int(sz.group(1)) / 100 if sz else 6)
    pos = re.search(r'<c:dLblPos val="(\w+)"/>', propia) or re.search(r'<c:dLblPos val="(\w+)"/>', general)
    tipo = grupo.group(1) if grupo else ""
    pos = pos.group(1) if pos else ("r" if tipo in ("lineChart", "line3DChart", "scatterChart") else "ctr")
    fuera = {"r": AIRE_ETIQUETA_DERECHA + ancho, "l": 0}.get(pos, ancho / 2)
    x = re.search(r'<c:manualLayout>.*?<c:x val="(-?[\d.Ee+-]+)"/>', propia, re.S)
    if x and W:
        fuera += float(x.group(1)) * W
    return max(0, fuera)


AIRE_ETIQUETA_DERECHA = 4   # pt entre el punto y su etiqueta a la derecha (Excel, aprox.)


def media_ultima_cifra(xml, medir):
    """Barras horizontales: la última cifra del eje de valores va centrada en el borde derecho del trazado y
    sobresale la mitad; el gráfico acaba al final de esa cifra. Devuelve esa mitad (pt)."""
    eje = next((e.group(0) for e in re.finditer(r'<c:valAx>.*?</c:valAx>', xml, re.S)
                if re.search(r'<c:axPos val="[bt]"/>', e.group(0)) and '<c:delete val="1"/>' not in e.group(0)), None)
    if not eje:
        return 0
    fijo = re.search(r'<c:max val="([^"]+)"/>', eje)
    if fijo:
        mayor = float(fijo.group(1))
    else:
        valores = [float(v) for g in re.findall(r'<c:val>.*?</c:val>', xml, re.S)
                   for v in re.findall(r'<c:v>(-?[\d.Ee+-]+)</c:v>', g)]
        mayor = round(max(valores) * 1.1) if valores else 100
    fmt = re.search(r'<c:numFmt formatCode="([^"]*)"', eje)
    codigo = html.unescape(fmt.group(1)) if fmt else "General"
    d = re.search(r'\.(0+)', codigo.split(";")[0])
    texto = f"{mayor:,.{len(d.group(1)) if d else 0}f}" + ("%" if "%" in codigo else "")
    cuerpo = re.search(r'<a:defRPr\b[^>]*\bsz="(\d+)"', eje)
    return medir(texto, int(cuerpo.group(1)) / 100 if cuerpo else 7) / 2


def alto_titulo_girado(ancla, largo, medir):
    """Ancho que ocupa un título girado (sus líneas a 7 pt) si tiene `largo` pt para cada línea."""
    texto = html.unescape(texto_forma(ancla)).strip()
    lineas = max(1, lineas_parrafos([texto], largo, CUERPO_UNIDADES, medir)) if medir else 1
    return lineas * CUERPO_UNIDADES * INTERLINEA + 2


def colocar_rel(formas, ancla, x0, y0, x1, y1, ancho, alto, algn=None):
    """El ancla en (x0, y0)–(x1, y1) pt dentro del gráfico de `ancho` × `alto` pt; con `algn`, el texto así."""
    nueva = re.sub(r'<cdr:from>.*?</cdr:to>',
                   f'<cdr:from><cdr:x>{max(0, x0) / ancho:.5f}</cdr:x><cdr:y>{max(0, y0) / alto:.5f}</cdr:y></cdr:from>'
                   f'<cdr:to><cdr:x>{min(ancho, x1) / ancho:.5f}</cdr:x><cdr:y>{min(alto, y1) / alto:.5f}</cdr:y></cdr:to>',
                   ancla, count=1, flags=re.S)
    if algn:
        nueva = re.sub(r'<a:pPr\b([^>]*?)\s*algn="\w+"', r'<a:pPr\1', nueva)
        nueva = re.sub(r'<a:pPr\b', f'<a:pPr algn="{algn}"', nueva)
        nueva = re.sub(r'<a:p>(?!<a:pPr)', f'<a:p><a:pPr algn="{algn}"/>', nueva)
    return formas.replace(ancla, nueva), nueva


def etiquetas_de_barras(xml, formas, t):
    """Barras horizontales: los números sueltos que el autor puso a mano junto a cada barra («(2)») pasan a ser
    la etiqueta de datos de su barra, con su mismo texto y fuera, al final: así Excel la pone siempre a la
    derecha de la barra aunque cambie el tamaño. La barra es la de la categoría a cuya altura está el
    número (con la disposición del autor, `t`). Devuelve (xml, formas, convertidas, avisos)."""
    grupo = next((g for g in GRUPOS.finditer(xml) if g.group(1) == "barChart" and es_horizontal(g.group(0))), None)
    sueltos = [a for a in re.findall(r'<cdr:relSizeAnchor\b.*?</cdr:relSizeAnchor>', formas, re.S)
               if not girado(a) and RE_NUMERO_SUELTO.fullmatch(html.unescape(texto_forma(a)).strip() or "x")]
    if not sueltos or not grupo:
        return xml, formas, 0, []
    if not t:
        return xml, formas, 0, [f"Aviso: {len(sueltos)} números sueltos junto a las barras: el autor no fijó el "
                                "trazado y no sé a qué barra va cada uno; colócalos a mano"]
    if re.search(r'<c:grouping val="(stacked|percentStacked)"/>', grupo.group(0)):
        return xml, formas, 0, [f"Aviso: {len(sueltos)} números sueltos junto a barras apiladas: colócalos a mano "
                                "al final de cada barra"]
    series = [s for s in re.findall(r'<c:ser>.*?</c:ser>', grupo.group(0), re.S)]
    cat = re.search(r'<c:cat>.*?</c:cat>', series[0], re.S) if series else None
    npt = re.search(r'<c:ptCount val="(\d+)"', cat.group(0) if cat else series[0])
    n = int(npt.group(1)) if npt else 0
    if not n:
        return xml, formas, 0, []
    eje = next((e.group(0) for e in re.finditer(r'<c:catAx>.*?</c:catAx>', xml, re.S)), "")
    al_reves = '<c:orientation val="maxMin"/>' in eje
    fx, fy, fw, fh = t
    por_punto, avisos = {}, []
    for a in sueltos:
        x0, y0, x1, y1 = caja_rel(a)
        v = ((y0 + y1) / 2 - fy) / fh          # 0 arriba, 1 abajo, dentro del trazado
        k = int(v * n) if al_reves else n - 1 - int(v * n)
        if not (0 <= v < 1) or not (0 <= k < n):
            avisos.append(f"Aviso: «{texto_forma(a).strip()}» no está a la altura de ninguna barra: se deja")
            continue
        por_punto.setdefault(k, []).append(a)
    convertidas = 0
    # Con varias series agrupadas, la etiqueta va en la barra más larga de esa categoría
    def valor_en(ser, k):
        m = re.search(rf'<c:val>.*?<c:pt idx="{k}">\s*<c:v>([^<]*)</c:v>', ser, re.S)
        try:
            return float(m.group(1)) if m else None
        except ValueError:
            return None
    nuevas = {s: s for s in series}
    for k, anclas in sorted(por_punto.items()):
        if len(anclas) > 1:
            avisos.append(f"Aviso: varios números sueltos a la altura de la misma barra: se dejan a mano")
            continue
        texto = html.unescape(texto_forma(anclas[0])).strip()
        ser = max(series, key=lambda s: abs(valor_en(s, k) or 0))
        dlbl = (f'<c:dLbl><c:idx val="{k}"/><c:tx><c:rich><a:bodyPr/><a:lstStyle/><a:p><a:pPr><a:defRPr sz="600" b="0">'
                f'{NEGRO}<a:latin typeface="{ROBOTO}"/><a:ea typeface="{ROBOTO}"/></a:defRPr></a:pPr><a:r><a:rPr lang="en-US"/>'
                f'<a:t>{html.escape(texto, quote=False)}</a:t></a:r></a:p></c:rich></c:tx><c:dLblPos val="outEnd"/>'
                '<c:showLegendKey val="0"/><c:showVal val="1"/><c:showCatName val="0"/><c:showSerName val="0"/>'
                '<c:showPercent val="0"/><c:showBubbleSize val="0"/></c:dLbl>')
        actual = nuevas[ser]
        h = hijos(actual)
        dl = hijo(h, "dLbls")
        if dl:
            hd = hijos(dl)
            hd = [x for x in hd if not (x[0] == "dLbl" and valor(hijo(hijos(x[1]), "idx")) == str(k))]
            pos = next((i for i, x in enumerate(hd) if x[0] != "dLbl"), len(hd))
            hd.insert(pos, ["dLbl", dlbl])
            dl = "<c:dLbls>" + "".join(x[1] for x in hd) + "</c:dLbls>"
        else:
            dl = ("<c:dLbls>" + dlbl + '<c:showLegendKey val="0"/><c:showVal val="0"/><c:showCatName val="0"/>'
                  '<c:showSerName val="0"/><c:showPercent val="0"/><c:showBubbleSize val="0"/></c:dLbls>')
        poner(h, ORDEN_SERIE["barChart"], "dLbls", dl)
        nuevas[ser] = "<c:ser>" + "".join(x[1] for x in h) + "</c:ser>"
        formas = formas.replace(anclas[0], "", 1)
        convertidas += 1
    g = grupo.group(0)
    for viejo, nuevo in nuevas.items():
        g = g.replace(viejo, nuevo, 1)
    xml = xml.replace(grupo.group(0), g, 1)
    return xml, formas, convertidas, avisos


def recolocar_formas(formas, viejo_trazado, viejo_tam, dentro, ancho, alto, saltar=(), centro=False, lineas=False):
    """Los textos sueltos dentro del gráfico se mueven con el trazado: su esquina (o, con `centro`, su centro)
    conserva su sitio respecto al trazado (lo que señalan) y su tamaño en pt. Con `lineas`, también las líneas del
    autor, que se estiran con el trazado de extremo a extremo (las de los promedios del G_IA2025_3.2 c, que se
    quedaban sobre otras barras)."""
    fx, fy, fw, fh = viejo_trazado
    w0, h0 = viejo_tam
    movidos = []
    mapa = lambda x, y: (dentro[0] + (x - fx) / fw * dentro[2], dentro[1] + (y - fy) / fh * dentro[3])
    for a in re.findall(r'<cdr:relSizeAnchor\b.*?</cdr:relSizeAnchor>', formas, re.S):
        if a in saltar:
            continue
        x0, y0, x1, y1 = caja_rel(a)
        if lineas and "<cdr:cxnSp" in a:
            (nx0, ny0), (nx1, ny1) = mapa(x0, y0), mapa(x1, y1)
            formas, _ = colocar_rel(formas, a, nx0, ny0, nx1, ny1, ancho, alto)
            movidos.append("línea")
            continue
        if not texto_forma(a).strip():
            continue
        if centro:
            cx, cy = mapa((x0 + x1) / 2, (y0 + y1) / 2)
            mw, mh = (x1 - x0) * w0 / 2, (y1 - y0) * h0 / 2
            formas, _ = colocar_rel(formas, a, cx - mw, cy - mh, cx + mw, cy + mh, ancho, alto)
        else:
            nx, ny = mapa(x0, y0)
            formas, _ = colocar_rel(formas, a, nx, ny, nx + (x1 - x0) * w0, ny + (y1 - y0) * h0, ancho, alto)
        movidos.append(html.unescape(texto_forma(a)).strip()[:30])
    return formas, movidos


def filas_categorias(xml, trazado, paso_pt):
    """Cuerpo de las categorías (regla del paso 2, con el ancho nuevo del trazado, en pt) y filas de la
    retícula que ocupan debajo del eje: la palabra más larga tiene que caber en su hueco; cada etiqueta se
    parte por palabras."""
    medir = medidor()
    # (también los ejes de fechas: el 2.3 salía cortado, «m…», con sus fechas verticales)
    eje = next((e.group(0) for e in re.finditer(r'<c:(catAx|dateAx)>.*?</c:\1>', xml, re.S)
                if re.search(r'<c:axPos val="[bt]"/>', e.group(0)) and '<c:delete val="1"/>' not in e.group(0)), "")
    if es_vertical(eje) and medir:
        # Verticales (paso 1): ocupan a lo alto lo que mide su línea más larga, con el cuerpo que ya tienen
        cuerpo = re.search(r'<c:txPr>.*?<a:defRPr\b[^>]*\bsz="(\d+)"', eje, re.S)
        sz = int(cuerpo.group(1)) if cuerpo else 700
        textos = [l for e in etiquetas_categorias(xml) for l in e.split("\n")] or textos_eje_numerico(xml, eje)
        largo = max([medir(l, sz / 100) for l in textos] or [0])
        # Con varios niveles (y sin juntarlos), cada nivel de más va debajo, en horizontal («1990-2018»): si
        # no se cuentan, Excel sube el trazado para que quepan y las unidades quedan dentro («G_DO2608_01»)
        niveles = niveles_categorias(xml) if '<c:noMultiLvlLbl val="1"/>' not in xml else 1
        alto = (SEPARACION_CATEGORIAS + largo + MARGEN_CATEGORIAS
                + (niveles - 1) * (sz / 100 * INTERLINEA + NIVEL_CATEGORIAS))
        return sz, "etiquetas en vertical", niveles, max(1, math.ceil((alto - LETRA_ABAJO) / paso_pt - 1e-6)), alto
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
    # Filas que ocupan, por la letra que se ve (sin el aire de debajo de la caja)
    return sz, nota, lineas + niveles - 1, max(1, math.ceil((alto - LETRA_ABAJO) / paso_pt - 1e-6)), alto


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


ASCENSO_ROBOTO = 1900 / 2048   # alto de las letras sobre la línea de base, por cuerpo (hhea de la Roboto)


def sin_titulo(marco_grafico, marco_titulo):
    """Lo que va (pt) de la línea de base de «Gráfico NN» a la del título en la plantilla."""
    def base(marco, cuerpo):
        return (posicion(marco)[1] + margenes(marco)[1]) / EMU_PT + cuerpo * ASCENSO_ROBOTO
    return base(marco_titulo, CUERPO_TITULO) - base(marco_grafico, 7)


# Leyendas de los paneles lado a lado (decisiones del usuario, 2026-11-27)
LEYENDA_BAJO_PANEL = 3 * MM          # del final del panel (sus categorías) a la leyenda de debajo
MUESTRA_DESDE_BORDE = 3              # pt que deja Excel dentro del cuadro de la leyenda, a cada lado (medido)
PRIMERA_MUESTRA = 5.3                # pt del borde del cuadro (con el ancho de medidas_leyenda_horizontal) a la primera
                                     # muestra en Excel: su margen más lo que reparte del hueco que sobra (medido en el 3.2;
                                     # más justo, la serie invisible de las muestras anchas salta a otra fila)
PRIMERA_MUESTRA_POR_ENTRADAS = {1: 6.0, 2: 6.3}  # lo mismo con 1 o 2 entradas (medido en el 8.4 d y c)
PRIMERA_MUESTRA_VARIAS_FILAS = 7.25  # y con una entrada por fila en varias filas (8.4 b, con HOLGURA_VARIAS_FILAS)
HOLGURA_LEYENDA_COMUN = 12          # pt de más en la leyenda común centrada (8.2: sin ellos, Excel escondía una entrada)
HOLGURA_VARIAS_FILAS = 8             # pt de más en las leyendas de varias filas: si no, Excel parte el texto (8.4 b)
SUBTITULO_BAJO_TITULO = 2.5 * MM     # del título de la fila a los subtítulos de sus paneles («1  Número…», 8.1)
ENTRE_ENTRADAS_HORIZONTAL = 4       # pt entre las entradas de una leyenda en horizontal (medido en Excel)
MUESTRA_HORIZONTAL_LINEA = 21        # pt de la muestra y su separación hasta el texto, con muestras de línea
MUESTRA_HORIZONTAL_BARRA = 10        # y con muestras de barra
FILAS_TARTA_CON_LEYENDA = 8          # el anillo con su leyenda a la derecha, en media página, algo más pequeño
TARTA_DESDE_COLUMNA = 4 * MM         # sitio a la izquierda del anillo para sus etiquetas


def nombres_leyenda(xml):
    return tuple(re.sub(r"\s+", " ", n).strip().lower() for n, _ in entradas_leyenda(xml))


def firma_leyenda(xml):
    """Las entradas visibles de la leyenda con su nombre y su tipo (línea, trama o marcador), en orden. Dos paneles
    comparten leyenda solo si coinciden en las dos cosas: el paso 5 da el mismo estilo (color, trama, línea) a la
    serie del mismo nombre y el mismo tipo, así que también coinciden los colores (petición del usuario,
    2026-11-27)."""
    if es_tarta(xml):
        # En las tartas la leyenda son las categorías; el color va por su orden
        return tuple((n, "porción") for n in nombres_leyenda(xml))
    leyenda = re.search(r'<c:legend>.*?</c:legend>', xml, re.S)
    borradas = set(re.findall(r'<c:legendEntry><c:idx val="(\d+)"/><c:delete val="1"/>', leyenda.group(0))) if leyenda else set()
    tipo = {t: g.group(1) for g in GRUPOS.finditer(xml) for t in re.findall(r'<c:ser>.*?</c:ser>', g.group(0), re.S)}
    firma = []
    for k, ser in enumerate(orden_leyenda(xml)):
        if str(k) in borradas or not re.search(r'<c:tx>.*?<c:v>[^<]*</c:v>.*?</c:tx>', ser, re.S) or es_muestra(ser):
            continue
        valores = re.search(r'<c:(?:val|yVal)>.*?</c:(?:val|yVal)>', ser, re.S)
        if valores and not re.search(r'<c:pt idx="\d+">\s*<c:v>[^<]+</c:v>', valores.group(0)):
            continue
        nombre = re.sub(r"\s+", " ", nombre_serie(ser)).strip().lower()
        firma.append((nombre, clase_serie(tipo.get(ser, ""), ser) or tipo.get(ser, "")))
    return tuple(firma)


def medidas_leyenda_horizontal(xml, ancho_max, medir, con_borde=False):
    """Ancho y alto (pt) de una leyenda con las entradas una detrás de otra (las que no caben, en otra fila, en
    columnas del ancho de la mayor). Con `con_borde`, también a cuántos pt del borde izquierdo del cuadro dibuja
    Excel la primera muestra."""
    # Medido en los PDF de Excel (3.2 y 8.4, 2026-11-27): Excel centra las entradas en el cuadro (el hueco que sobra
    # se reparte entre los bordes y los huecos entre entradas); cada una ocupa su muestra y la separación hasta el
    # texto (unos 21 pt con muestra de línea), su texto (como lo medimos) y unos 4 pt hasta la siguiente. Más justo
    # que esto, la serie invisible de las muestras anchas salta a otra fila; y con una entrada por fila, Excel
    # parte su texto si no le dejamos unos pt de más (HOLGURA_VARIAS_FILAS)
    entradas = entradas_leyenda(xml) or [("Serie", False)]
    con_lineas = any(l for _, l in entradas)
    muestra = MUESTRA_HORIZONTAL_LINEA if con_lineas else MUESTRA_HORIZONTAL_BARRA
    anchos = [muestra + medir(n, 7) * 1.01 for n, _ in entradas]
    justo = sum(anchos) + (len(anchos) - 1) * ENTRE_ENTRADAS_HORIZONTAL + 2 * MUESTRA_DESDE_BORDE
    if justo <= ancho_max:
        medidas = justo, 7 * INTERLINEA + 4, 1
        borde = PRIMERA_MUESTRA_POR_ENTRADAS.get(len(anchos), PRIMERA_MUESTRA)
    else:
        mayor = max(anchos) + ENTRE_ENTRADAS_HORIZONTAL
        por_fila = max(1, int((ancho_max - 2 * MUESTRA_DESDE_BORDE - HOLGURA_VARIAS_FILAS + ENTRE_ENTRADAS_HORIZONTAL)
                              // mayor))
        filas = math.ceil(len(anchos) / por_fila)
        medidas = (por_fila * mayor - ENTRE_ENTRADAS_HORIZONTAL + 2 * MUESTRA_DESDE_BORDE + HOLGURA_VARIAS_FILAS,
                   filas * (7 * INTERLINEA + 2) + 4, filas)
        borde = (PRIMERA_MUESTRA_VARIAS_FILAS if por_fila == 1 else
                 PRIMERA_MUESTRA_POR_ENTRADAS.get(por_fila, PRIMERA_MUESTRA) + 1)
    return (*medidas, borde) if con_borde else medidas


def medidas_leyenda_vertical(xml, ancho_max, medir):
    """Ancho y alto (pt) de una leyenda con las entradas una debajo de otra, en `ancho_max` pt."""
    entradas = entradas_leyenda(xml) or [("Serie", False)]
    con_lineas = any(l for _, l in entradas)
    disponible = ancho_max - texto_desde(con_lineas) - HUECO_DERECHA_LEYENDA
    partidos = [partir_lineas(n, disponible, 7, medir) for n, _ in entradas]
    ancho = max(w * TEXTO_EXCEL_MAS_ANCHO for p in partidos for w in p) + CLAVE_LEYENDA + \
        (CLAVE_LINEA_DE_MAS if con_lineas else 0) + 2 + HOLGURA_LEYENDA
    return min(ancho_max, ancho), alto_entradas(partidos)


def poner_leyenda(xml, ancho, alto, x, y, w, h, posicion):
    """La leyenda en (x, y) pt, de w × h pt, dentro del gráfico de ancho × alto pt, con la posición de Excel dada
    («b»: entradas en horizontal; «r»: una debajo de otra)."""
    lay = ('<c:layout><c:manualLayout><c:xMode val="edge"/><c:yMode val="edge"/>'
           f'<c:x val="{max(0, x) / ancho:.6f}"/><c:y val="{max(0, y) / alto:.6f}"/><c:w val="{min(w, ancho) / ancho:.6f}"/>'
           f'<c:h val="{min(h, alto - y) / alto:.6f}"/></c:manualLayout></c:layout>')

    def cambiar(m):
        bloque = re.sub(r'<c:layout>.*?</c:layout>|<c:layout/>', "", m.group(0), count=1, flags=re.S)
        bloque = re.sub(r'<c:legendPos val="\w+"/>', f'<c:legendPos val="{posicion}"/>', bloque, count=1)
        entradas = list(re.finditer(r'<c:legendEntry>.*?</c:legendEntry>', bloque, re.S))
        if entradas:
            return bloque[:entradas[-1].end()] + lay + bloque[entradas[-1].end():]
        return re.sub(r'(<c:legendPos val="\w+"/>)', lambda p: p.group(1) + lay, bloque, count=1)
    return re.sub(r'<c:legend>.*?</c:legend>', cambiar, xml, count=1, flags=re.S)


def sin_trazado(xml):
    """Un gráfico que solo es leyenda: su trazado, invisible (un punto en una esquina) y sin etiquetas de datos (en el
    2.1 la tarta del gráfico de la leyenda salía en miniatura con sus cifras encima de la leyenda)."""
    lay = ('<c:layout><c:manualLayout><c:layoutTarget val="inner"/><c:xMode val="edge"/><c:yMode val="edge"/>'
           '<c:x val="0"/><c:y val="0"/><c:w val="0.0001"/><c:h val="0.0001"/></c:manualLayout></c:layout>')
    xml = re.sub(r'(<c:plotArea>\s*)(<c:layout>.*?</c:layout>|<c:layout/>)?', lambda m: m.group(1) + lay, xml, count=1, flags=re.S)
    xml = re.sub(r'<c:dLbls>.*?</c:dLbls>', "", xml, flags=re.S)
    # Sin ejes (el del 8.1 enseñaba «-3.500» al lado de la leyenda)
    xml = re.sub(r'<c:delete val="0"/>', '<c:delete val="1"/>', xml)

    # Y los datos fuera de la escala, para que no se dibuje ni un punto (8.1: un marcador junto a la leyenda)
    def fuera(m):
        h = hijos(m.group(0))
        escala = hijos(hijo(h, "scaling") or "<c:scaling></c:scaling>")
        orient = hijo(escala, "orientation") or '<c:orientation val="minMax"/>'
        poner(h, ORDEN_EJE["valAx"], "scaling", f'<c:scaling>{orient}<c:max val="1000000001"/><c:min val="1000000000"/></c:scaling>')
        return "<c:valAx>" + "".join(t for _, t in h) + "</c:valAx>"
    return re.sub(r'<c:valAx>.*?</c:valAx>', fuera, xml, flags=re.S)


def plan_leyendas_fila(z, relaciones, partes, fila, sueltas, medir):
    """Qué se hace con la leyenda de cada panel de una fila: «suelta» (la común va en gráficos aparte, debajo),
    «comun» (la lleva el primer panel, a lo ancho de las dos columnas y centrada), «quitar» (la común ya va en
    otro), «propia» (debajo de su panel, una entrada bajo otra), «derecha» (tarta: a la derecha del anillo) o
    None (sin leyenda)."""
    xmls = {}
    for ig in fila:
        rid = re.search(r'<c:chart\b[^>]*\br:id="([^"]+)"', partes[ig]).group(1)
        xmls[ig] = z.read(relaciones[rid][1]).decode("utf-8")
    con = [ig for ig in fila if re.search(r'<c:legend>', xmls[ig]) and entradas_leyenda(xmls[ig])]
    plan = {ig: None for ig in fila}
    if sueltas:
        for ig in con:
            plan[ig] = "quitar"
        return plan
    if not con:
        return plan
    firmas = {ig: firma_leyenda(xmls[ig]) for ig in fila}
    if len({firmas[ig] for ig in con}) == 1:
        # Los paneles sin leyenda: sus series, del mismo tipo y en el mismo orden (el paso 5 les da los colores por
        # orden y tipo: así son los de la leyenda común; 8.2 b)
        tipos_comun = tuple(t for _, t in firmas[con[0]])
        sin = [ig for ig in fila if ig not in con and firmas[ig]]
        if all(tuple(t for _, t in firmas[ig]) == tipos_comun for ig in sin):
            plan[con[0]] = "comun"
            for ig in con[1:]:
                plan[ig] = "quitar"
            return plan
    for ig in con:
        plan[ig] = "derecha" if es_tarta(xmls[ig]) else "propia"
    return plan


def avisos_leyendas_fila(plan, fila):
    """Aviso si en una fila hay paneles sin leyenda que no comparten la de otro (sus colores no coinciden)."""
    if any(v in ("propia", "derecha") for v in plan.values()) and any(plan[ig] is None for ig in fila):
        return ("Aviso: en una fila de paneles lado a lado hay paneles sin leyenda cuyas series no coinciden (en nombre, "
                "tipo u orden, y por tanto en colores) con las de la leyenda de otro panel: cada uno se queda con lo suyo; "
                "revisa si hace falta poner una leyenda al panel que no la tiene")
    return None


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
            graf = ANCLA.fullmatch(a) and re.search(r'<c:chart\b[^>]*\br:id="([^"]+)"', a)
            if graf and caja(a)[0] < ancho_ret:
                graficos.append((caja(a)[1], i, graf.group(1)))
        tipos = clasificar_textos(partes, caja, alto_pastilla, ancho_ret)
        for i, (tipo, _) in tipos.items():
            if tipo == "titulo":
                titulo = i
            elif tipo == "fuentes":
                fuentes = i
            elif tipo == "panel":
                titulos_panel.append((caja(partes[i])[1], i))
        if not graficos:
            raise Fallo("No hay gráficos en la hoja «Gráfico»")
        # De arriba abajo y, a la misma altura (paneles del autor lado a lado que se apilan), de izquierda a derecha
        graficos.sort(key=lambda g: (round(g[0] / (10 * 36000)), caja(partes[g[1]])[0]))
        # Paneles lado a lado: por filas, cada panel en una de las dos columnas iguales de la retícula de los recuadros
        lado = filas_segun_modo(z, ruta, dibujo, estado.get("paneles", "auto"), es_recuadro(trabajo))
        if lado and abs(w1 - w2) > 0.05 * w1:
            detalle.append("Aviso: los paneles van lado a lado, pero la retícula no es la de los recuadros (dos columnas "
                           "iguales): rehaz el paso 1 («Retícula, pastilla y textos») con esta versión de la app")
            lado = None
        if lado:
            filas_l, sueltas_l = lado
            columnas_l = [(x1, w1), (x2, w2)]
            # Los textos sueltos (unidades, texto del centro de una tarta…) van con el panel en cuya caja caen, no solo
            # con el más cercano a lo alto: en una fila hay dos a la misma altura (2.1: el «%» y el «4,5» del panel b)
            paneles_l = [ig for f in filas_l for ig in f]
            for i, (t, g) in list(tipos.items()):
                if t not in ("interior", "unidades") or g is None:
                    continue
                xt, yt, wt, ht = caja(partes[i])
                cx_t, cy_t = xt + wt / 2, yt + ht / 2
                dentro_de = [ig for ig in paneles_l if caja(partes[ig])[0] <= cx_t <= caja(partes[ig])[0] + caja(partes[ig])[2]]
                if dentro_de:
                    tipos[i] = (t, min(dentro_de, key=lambda ig: abs(caja(partes[ig])[1] + caja(partes[ig])[3] / 2 - cy_t)))
            detalle.append(f"Paneles lado a lado: {len(filas_l)} fila{'s' if len(filas_l) > 1 else ''} de "
                           + ", ".join(str(len(f)) for f in filas_l) + " paneles"
                           + (f"; {sum(len(v) for v in sueltas_l.values())} gráfico(s) que solo son leyenda" if sueltas_l else ""))
        elif len(graficos) > 3:
            detalle.append(f"Aviso: hay {len(graficos)} gráficos; la distribución de Illus prevé hasta 3 paneles")

        # Líneas del título del gráfico (Roboto Medium 8,5 pt en su marco)
        lineas_titulo = 1
        if titulo is not None:
            l, _, r, _ = margenes(partes[titulo])
            ancho = (caja(partes[titulo])[2] - l - r) / EMU_PT
            lineas_titulo = min(3, max(1, lineas_parrafos(textos_lineas(partes[titulo]), ancho, 8.5, medir_medium)))
        detalle.append(f"Título del gráfico: {lineas_titulo} línea{'s' if lineas_titulo > 1 else ''}" if titulo is not None
                       else "Sin título del gráfico")
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
        elif titulo is None:
            # Sin título, la pastilla acaba igual de lejos de «Gráfico NN» que, con título, del título: se acorta
            # lo que va de la línea de base de «Gráfico NN» a la del título en la plantilla (unos 4 mm)
            crece = -sin_titulo(anclas_ret[ret["marco_grafico"]], anclas_ret[ret["marco_titulo"]])
            for i, a in enumerate(partes):
                if ANCLA.fullmatch(a) and es_pastilla(a):
                    partes[i] = alargar(a, round(crece * EMU_PT), caja)
            detalle.append(f"  pastilla y paneles {-crece / MM:.1f} mm más arriba: sin título, la pastilla acaba a la "
                           "misma distancia de «Gráfico NN» que de un título".replace(".", ","))

        # Cada título de panel va con el gráfico que empieza más cerca de él (el autor a veces lo pone encima
        # del marco del gráfico, unos milímetros por debajo de su borde)
        de_panel = {}
        candidatos_tp = [ig for f in filas_l for ig in f] if lado else [ig for _, ig, _ in graficos]
        titulo_fila = {}
        if lado:
            # Con título de fila («8.1.a …», a lo ancho) y subtítulos numerados por panel («1  Número…», «2  Importe…»)
            libres_t = list(titulos_panel)
            for k, f in enumerate(filas_l):
                arriba_f = min(caja(partes[ig])[1] for ig in f)
                cerca = [(y, i) for y, i in libres_t if arriba_f - 25 * 36000 <= y <= arriba_f + 15 * 36000]
                subs = [(y, i) for y, i in cerca if RE_SUBPANEL.match(texto_forma(partes[i]))]
                nums = [(y, i) for y, i in cerca if (y, i) not in subs]
                if subs and nums:
                    titulo_fila[k] = min(nums)[1]
                    libres_t.remove(min(nums))
            titulos_panel = [t for t in titulos_panel if t[1] not in titulo_fila.values()]
        lineas_fila = {}
        for y, i in sorted(titulos_panel):
            # (lado a lado, también por la columna: los títulos de una fila están a la misma altura)
            # (también en horizontal, en todos los modos: un 2.9 del autor lado a lado que se apila tiene los dos
            # títulos y los dos gráficos a la misma altura y se cruzaban)
            libres = [(abs(caja(partes[ig])[1] - y) + abs(caja(partes[ig])[0] - caja(partes[i])[0]), ig)
                      for ig in candidatos_tp if ig not in de_panel]
            if libres:
                de_panel[min(libres)[1]] = i
        if lado:
            # En cada fila, los paneles empiezan debajo del título más largo: así sus ejes quedan a la misma altura
            # (8.2: el título del b en dos líneas)
            for k, f in enumerate(filas_l):
                lineas_fila[k] = max([max(1, lineas_parrafos(textos_lineas(partes[de_panel[ig]]),
                                                             (x2 + w2 - x1 if len(f) == 1 else columnas_l[j % 2][1]) / EMU_PT,
                                                             8, medir)) for j, ig in enumerate(f) if ig in de_panel] or [1])

        ancho_util = x2 + w2 - x1
        ancho_graf = ancho_util
        W = ancho_graf / EMU_PT
        fondo = None
        rid_de = {ig: rid for _, ig, rid in graficos}
        if lado:
            orden = [(None, ig, rid_de[ig], k, j) for k, f in enumerate(filas_l) for j, ig in enumerate(f)]
            orden = [(n, *o[1:]) for n, o in enumerate(orden, 1)]
            plan_l, fondo_filas = {}, {}
            # Los paneles de una fila, del mismo alto y con el final del trazado a la misma altura: las filas y el sitio
            # de las categorías, los del que más necesite (así las leyendas de debajo empiezan en la misma línea; 3.2,
            # como en el .ai; petición del usuario, 2026-11-27)
            igualar_fila = {}
            for k, f in enumerate(filas_l):
                maximos = []
                for j, ig in enumerate(f):
                    xg = z.read(relaciones[rid_de[ig]][1]).decode("utf-8")
                    if es_tarta(xg) or es_horizontal(xg):
                        continue
                    ancho_c = (x2 + w2 - x1) if len(f) == 1 else columnas_l[j % 2][1]
                    tr = ancho_c / EMU_PT - ancho_numeros_eje(xg, medir)
                    _, _, _, fc, ac = filas_categorias(xg, tr, paso_pt)
                    maximos.append((max(FILAS_PANEL, FILAS_MIN_TRAZADO + fc), ac))
                if len(maximos) > 1:
                    igualar_fila[k] = (max(m[0] for m in maximos), max(m[1] for m in maximos))
            for k, f in enumerate(filas_l):
                plan_f = plan_leyendas_fila(z, relaciones, partes, f, sueltas_l.get(k), medir)
                plan_l.update(plan_f)
                aviso_f = avisos_leyendas_fila(plan_f, f)
                if aviso_f:
                    detalle.append(aviso_f.replace("en una fila", f"en la fila {k + 1}"))
            completo = (x1, x2 + w2 - x1)
        else:
            orden = [(n, ig, rid, None, None) for n, (_, ig, rid) in enumerate(graficos, 1)]
        for n, ig, rid, fila_k, col_j in orden:
            es_primero = (n == 1) if fila_k is None else (fila_k == 0)
            modo_ley, extra_ley = None, 0
            if fila_k is not None:
                # Lado a lado: el panel en su columna (como si fuera la columna 1) y la fila empieza donde acabó la
                # anterior
                x1, w1 = columnas_l[col_j % 2]
                if len(filas_l[fila_k]) == 1:
                    # Solo en su fila (número impar de paneles; sobre todo en los recuadros): a todo el ancho de la
                    # retícula (petición del usuario, 2026-11-27)
                    x1, w1 = completo
                ancho_util = ancho_graf = w1
                fondo = fondo_filas.get(fila_k - 1)
                modo_ley = plan_l.get(ig)
                if modo_ley == "comun":
                    # La leyenda común, debajo de los dos paneles y centrada: el gráfico del primero se ensancha
                    ancho_graf = completo[1]
                W = ancho_graf / EMU_PT
            linea = f"Panel {n}:"
            ruta_graf = relaciones[rid][1]
            xml = z.read(ruta_graf).decode("utf-8")
            ruta_formas = next((d for t, d in rels(z, ruta_graf).values() if t.endswith("/chartUserShapes")), None)
            formas = z.read(ruta_formas).decode("utf-8") if ruta_formas else ""
            horizontal = es_horizontal(xml)
            unidades = unidades_de(formas, xml)
            # En barras horizontales las unidades son las del eje de valores, debajo: arriba no hay
            unidades_arriba = [] if horizontal else unidades
            girados = [a for a in re.findall(r'<cdr:relSizeAnchor\b.*?</cdr:relSizeAnchor>', formas, re.S)
                       if texto_forma(a).strip() and girado(a)] if horizontal else []
            subida = SUBIDA_GRAFICO + (SUBIDA_CON_UNIDADES if unidades_arriba else 0)

            # Dónde empieza el gráfico (lo más alto de su trazado), con o sin título de panel
            it = de_panel.get(ig)
            if it is not None:
                a = partes[it]
                l, t, r, b = margenes(a)
                lineas_tp = max(1, lineas_parrafos(textos_lineas(a), ancho_util / EMU_PT, 8, medir))
                if es_primero:
                    arriba = fondo_pastilla + crece + PASTILLA_A_TITULO_PANEL
                else:
                    arriba = fondo + ENTRE_PANELES
                tf = titulo_fila.get(fila_k) if fila_k is not None else None
                if tf is not None:
                    # Título de la fila, a lo ancho de las dos columnas; los subtítulos de los paneles, debajo
                    af = partes[tf]
                    lf, tf_m, rf, bf = margenes(af)
                    lineas_f = max(1, lineas_parrafos(textos_lineas(af), completo[1] / EMU_PT, 8, medir))
                    if col_j == 0:
                        partes[tf] = colocar(af, completo[0] - lf, round(arriba * EMU_PT) - tf_m, completo[1] + lf + rf,
                                             tf_m + bf + round(lineas_f * INTERLINEA_TITULO_PANEL * EMU_PT))
                        linea += f" título de la fila a {arriba / MM:.1f} mm, a lo ancho;".replace(".", ",")
                    arriba += lineas_f * INTERLINEA_TITULO_PANEL + SUBTITULO_BAJO_TITULO
                final_tp = arriba + max(lineas_tp, lineas_fila.get(fila_k, 1) if fila_k is not None else 1) * INTERLINEA_TITULO_PANEL
                alto_tp = t + b + round(lineas_tp * INTERLINEA_TITULO_PANEL * EMU_PT)
                partes[it] = colocar(a, x1 - l, round(arriba * EMU_PT) - t, ancho_util + l + r, alto_tp)
                inicio = final_tp + TITULO_PANEL_A_GRAFICO - subida
                techo_panel = final_tp
                linea += f" título a {arriba / MM:.1f} mm ({lineas_tp} línea{'s' if lineas_tp > 1 else ''});".replace(".", ",")
            else:
                inicio = (INICIO_SIN_TITULO_PANEL + crece if es_primero else fondo + ENTRE_PANELES) - subida
                techo_panel = fondo_pastilla + crece if es_primero else fondo + ENTRE_PANELES / 2
                # Un solo gráfico sin título de panel: unidades, gráfico y leyenda 3 mm más abajo (petición del
                # usuario, 2026-11-27, Memoria de Supervisión)
                if len(graficos) == 1:
                    inicio += BAJADA_SOLO_SIN_TITULO
                    techo_panel += BAJADA_SOLO_SIN_TITULO
                    linea += f" un solo gráfico sin título de panel: {BAJADA_SOLO_SIN_TITULO / MM:g} mm más abajo;"

            # Sin leyenda (el autor la ha quitado o escondido): el trazado ocupa las dos columnas, como en el
            # TERMINADO del 2.6, y la leyenda se deja como está
            motivo = sin_leyenda(xml, caja(partes[ig])[2] / EMU_PT)
            if fila_k is not None:
                # Lado a lado la leyenda se trata aparte (debajo de la fila, debajo del panel o a la derecha de la tarta)
                motivo = None if modo_ley == "derecha" else (motivo or "lado a lado")
            elif motivo and horizontal:
                # Barras horizontales: el trazado se queda en la columna 1 (sus unidades acaban al final de ella)
                detalle.append(f"Aviso: el panel {n} va sin leyenda (el autor {motivo}): barras horizontales, el "
                               "trazado se queda en la columna 1. Comprueba que lo que representa se explica en el "
                               "título del panel.")
            elif motivo:
                detalle.append(f"Aviso: el panel {n} va sin leyenda (el autor {motivo}): el trazado ocupa las dos "
                               "columnas. Comprueba que lo que representa se explica en el título del panel.")
            tarta = es_tarta(xml)
            xml_antes = xml
            if tarta:
                # Tarta: 9 filas de diámetro, centrada en la columna 1; las etiquetas, por fuera
                numeros, sz, nota, lineas_cat, filas_cat, alto_cat = 0, 700, None, 0, 0, 0
                filas = FILAS_TARTA_CON_LEYENDA if modo_ley == "derecha" else FILAS_PANEL
                diametro = filas * paso_pt
                alto_panel = MEDIA_ETIQUETA + diametro + ETIQUETA_TARTA
                trazado = diametro
            else:
                # Alto: 9 filas hasta el final de las categorías (el trazado, como mínimo 7)
                numeros = ancho_categorias_izquierda(xml, medir) if horizontal else ancho_numeros_eje(xml, medir)
                if not horizontal and numeros == AIRE_TRAZADO_SIN_EJE:
                    linea += " sin eje vertical con cifras: el trazado empieza al principio de la columna 1;"
                if modo_ley == "propia" and not horizontal:
                    # Su leyenda empieza en el eje vertical y Excel no deja la primera muestra pegada al borde
                    numeros = max(numeros, medidas_leyenda_horizontal(xml, w1 / EMU_PT, medir, con_borde=True)[3])
                trazado = (ancho_util if motivo and not horizontal else w1) / EMU_PT - numeros
                derecha = 0 if horizontal else ancho_numeros_derecha(xml, medir)
                if derecha:
                    trazado -= derecha
                    linea += (f" eje de la derecha: el trazado se estrecha {derecha / MM:.1f} mm para que sus números "
                              "quepan en la columna 1;").replace(".", ",")
                sz, nota, lineas_cat, filas_cat, alto_cat = filas_categorias(xml, trazado, paso_pt)
                if horizontal:
                    # El gráfico acaba al final de la última cifra del eje (que sobresale medio ancho del trazado)
                    sobresale = media_ultima_cifra(xml, medir)
                    trazado -= sobresale
                else:
                    # Líneas y áreas con las categorías sobre las marcas: la última categoría (y la etiqueta de su
                    # punto) va centrada en el borde derecho del trazado y sobresale la mitad: el trazado se acorta
                    # para que acabe en la columna (G_IA2025_2.6, «2025» y «22,4», petición del usuario, 2026-11-26)
                    sobresale = media_ultima_categoria(xml, (sz or 700) / 100, medir, W)
                    if sobresale:
                        trazado -= sobresale
                        linea += f" trazado {sobresale / MM:.1f} mm más corto: la última categoría acaba en la columna;".replace(".", ",")
                if horizontal and unidades:
                    # Las unidades del eje de valores, debajo de sus números
                    alto_cat += UNIDADES_BAJO_NUMEROS + ALTO_UNIDADES
                    filas_cat = max(1, math.ceil((alto_cat - LETRA_ABAJO) / paso_pt - 1e-6))
                if girados:
                    # El título girado del eje vertical, a la izquierda de las categorías
                    largo = FILAS_PANEL * paso_pt - alto_cat
                    ancho_girado = max(alto_titulo_girado(a, largo, medir) for a in girados)
                    numeros += ancho_girado + TITULO_GIRADO_A_CATEGORIAS
                    trazado -= ancho_girado + TITULO_GIRADO_A_CATEGORIAS
                filas = max(FILAS_PANEL, FILAS_MIN_TRAZADO + filas_cat)
                if fila_k is not None and fila_k in igualar_fila:
                    filas_f, alto_cat_f = igualar_fila[fila_k]
                    if filas_f > filas or alto_cat_f > alto_cat + 0.01:
                        linea += " del mismo alto que los demás paneles de la fila;"
                    filas, alto_cat = max(filas, filas_f), max(alto_cat, alto_cat_f)
                # Si la leyenda (en la columna 2) no cabe en el alto del panel, el panel crece las filas que falten
                # (G_IA2025_1.22, panel a: seis entradas, dos de dos líneas; si no, Excel las monta)
                if not motivo and not horizontal and medir and re.search(r'<c:legend>', xml):
                    necesario = alto_leyenda_necesario(xml, ANCHO_LEYENDA(w2), medir)
                    filas_ley = math.ceil((necesario - LETRA_VISIBLE) / paso_pt - 1e-6)
                    if filas_ley > filas:
                        linea += (f" el panel crece a {filas_ley} filas para que quepa la leyenda "
                                  f"({necesario / MM:.1f} mm);").replace(".", ",")
                        filas = filas_ley
                alto_panel = filas * paso_pt + LETRA_VISIBLE
            # Tarta: si sus etiquetas no caben por arriba sin líneas guía, el anillo (con sus 9 filas) baja una
            # fila de la retícula, como mucho FILAS_BAJADA_TARTA, y se queda con la primera que vale
            inicio0, pruebas = inicio, []
            for bajada in range(FILAS_BAJADA_TARTA + 1 if tarta else 1):
                inicio = inicio0 + bajada * paso_pt
                # Unidades: su línea de base, 2 mm por encima del borde de arriba del trazado
                ini_unidades = inicio + MEDIA_ETIQUETA - UNIDADES_A_GRAFICO - BASE_UNIDADES
                if tarta:
                    # En una tarta el trazado empieza muy arriba: las unidades, al menos debajo del título del panel
                    # (2.1 b: el «%» se montaba en el título)
                    ini_unidades = max(ini_unidades, techo_panel + 1 * MM)
                arriba_marco = min(ini_unidades, inicio) if unidades_arriba else inicio
                if tarta:
                    # Las etiquetas de arriba necesitan sitio por encima del anillo: el marco sube hasta la
                    # pastilla o el título del panel (el anillo no se mueve)
                    arriba_marco = min(arriba_marco, techo_panel + AIRE_SOBRE_ETIQUETAS)
                H = inicio + alto_panel - arriba_marco
                if not tarta:
                    break
                if modo_ley == "derecha":
                    # Lado a lado con su leyenda: el anillo a la izquierda de su media página y la leyenda a la derecha
                    dentro = (TARTA_DESDE_COLUMNA, inicio - arriba_marco + MEDIA_ETIQUETA, diametro, diametro)
                    x_ley = TARTA_DESDE_COLUMNA + diametro + LEYENDA_A_LA_IZQUIERDA + 3 * MM
                    leyenda_t = (x_ley, dentro[1] + diametro / 2, w1 / EMU_PT - x_ley, True)
                else:
                    dentro = ((w1 / EMU_PT - diametro) / 2, inicio - arriba_marco + MEDIA_ETIQUETA, diametro, diametro)
                    leyenda_t = None if motivo else ((x2 - x1) / EMU_PT - LEYENDA_A_LA_IZQUIERDA, None, ANCHO_LEYENDA(w2), True)
                centro = dentro[1] + diametro / 2
                if leyenda_t and leyenda_t[1] is None:
                    leyenda_t = (leyenda_t[0], centro, leyenda_t[2], True)
                xml_t = disposicion(xml, W, H, dentro, leyenda_t, medir)
                xml_t, notas_et, guias = etiquetas_tarta(xml_t, W, H, dentro, medir, leyenda_t[0] if leyenda_t else None)
                fallos = len(guias) + sum(nt.startswith("Aviso: ") for nt in notas_et)
                pruebas.append((fallos, bajada, inicio, ini_unidades, arriba_marco, H, dentro, centro, xml_t, notas_et, guias))
                if not fallos:
                    break
            if tarta:
                (_, bajada, inicio, ini_unidades, arriba_marco, H, dentro, centro, xml, notas_et,
                 guias) = min(pruebas, key=lambda p: p[:2])
                if bajada:
                    detalle.append(f"Panel {n}: la tarta baja {bajada} fila{'s' if bajada > 1 else ''} de la retícula "
                                   "para que sus etiquetas quepan por arriba (sigue con 9 filas de diámetro)")
                for nt in notas_et:
                    detalle.append(f"Aviso: panel {n}: " + nt.split("Aviso: ", 1)[1] if nt.startswith("Aviso: ")
                                   else f"Panel {n}: {nt}")
            else:
                # Solo barras: la serie invisible que da muestras anchas en la leyenda (antes de medirla); si el autor
                # ya puso la suya («linea» del 3.6), se convierte en la de la app
                xml, de_autor = muestra_del_autor(xml)
                if de_autor is not None:
                    detalle.append(f"Aviso: panel {n}: la serie «{de_autor}» (un dato o solo ceros, sin marcador) es la línea que puso "
                                   "el autor para ensanchar las muestras de la leyenda: pasa a ser la de la app, invisible "
                                   "y sin nombre en la leyenda; comprueba que no era una serie de datos")
                anchas = None if motivo else muestras_anchas(xml)
                if anchas:
                    xml = anchas
                    detalle.append(f"Panel {n}: muestras de la leyenda anchas, como las de las líneas, para que se "
                                   "vean las tramas de las barras (serie de línea blanca sin datos al final de la leyenda)")
                dentro = (numeros, inicio - arriba_marco + MEDIA_ETIQUETA, trazado,
                          alto_panel - MEDIA_ETIQUETA - alto_cat)
                if modo_ley in ("comun", "propia"):
                    # Lado a lado: la leyenda debajo del panel; el gráfico crece hacia abajo lo que ocupe
                    if modo_ley == "comun":
                        lw_l, lh_l, _ = medidas_leyenda_horizontal(xml, completo[1] / EMU_PT - HOLGURA_LEYENDA_COMUN, medir)
                        # Centrada: unos pt de más no la mueven y evitan que Excel pase la última entrada a otra
                        # fila, que no se ve (8.2: «Compras en TPV» desaparecía)
                        lw_l += HOLGURA_LEYENDA_COMUN
                        lx_l = (completo[1] / EMU_PT - lw_l) / 2
                    else:
                        # Cada panel con su leyenda: a la izquierda, empezando en su eje vertical, y las entradas de
                        # izquierda a derecha y después hacia abajo (el orden natural; petición del usuario, 2026-11-27).
                        lw_l, lh_l, _, borde = medidas_leyenda_horizontal(xml, w1 / EMU_PT - max(0, numeros - PRIMERA_MUESTRA),
                                                                          medir, con_borde=True)
                        lx_l = max(0, numeros - borde)
                    extra_ley = LEYENDA_BAJO_PANEL + lh_l
                    H += extra_ley
                xml = disposicion(xml, W, H, dentro, None if motivo else
                                  ((x2 - x1) / EMU_PT - LEYENDA_A_LA_IZQUIERDA, inicio - arriba_marco, ANCHO_LEYENDA(w2)), medir)
                if modo_ley in ("comun", "propia"):
                    ly_l = inicio - arriba_marco + alto_panel + LEYENDA_BAJO_PANEL
                    xml = poner_leyenda(xml, W, H, lx_l, ly_l, lw_l, lh_l, "b")
                    linea += (" leyenda común debajo de los paneles, centrada, con las entradas en horizontal;"
                              if modo_ley == "comun" else " leyenda debajo del panel, desde su eje vertical, con las "
                              "entradas de izquierda a derecha y después hacia abajo;")
            # Cuerpo de las categorías con el ancho nuevo (regla del paso 2)
            xml = re.sub(r'<c:catAx>.*?</c:catAx>',
                         lambda m: re.sub(r'(<c:txPr>.*?</c:txPr>)', lambda t: fijar_letra(t.group(1), sz, ROBOTO),
                                          m.group(0), count=1, flags=re.S) if re.search(r'<c:axPos val="[bt]"/>', m.group(0)) else m.group(0),
                         xml, flags=re.S)
            if horizontal and not tarta and formas:
                # Números sueltos junto a las barras → etiquetas de datos; textos sueltos, con el trazado
                xml, formas, convertidas, avisos_b = etiquetas_de_barras(xml, formas, trazado_rel(xml_antes))
                if convertidas:
                    linea += (f" {convertidas} números sueltos junto a las barras pasan a ser sus etiquetas de datos "
                              "(su mismo texto, fuera al final de la barra, 6 pt);")
                detalle += [f"Aviso: panel {n}: " + a.split("Aviso: ", 1)[1] for a in avisos_b]
                # Unidades del eje de valores: debajo de sus números, alineadas a la derecha al final del eje
                # horizontal (no de la última cifra, que sobresale)
                fin_x = numeros + trazado
                y_u = dentro[1] + dentro[3] + SEPARACION_CATEGORIAS + 7 * INTERLINEA + UNIDADES_BAJO_NUMEROS
                for u in unidades:
                    ancho_u = medir(html.unescape(texto_forma(u)).strip(), CUERPO_UNIDADES) + 2
                    # Sin márgenes ni ajuste de línea: una línea que acaba justo al final del trazado
                    cuerpo_u = re.search(r'<a:bodyPr\b[^>]*?(?=/?>)', u).group(0)
                    u2 = u.replace(cuerpo_u, re.sub(r'\s+(?:anchor|wrap|lIns|rIns|tIns|bIns)="[^"]*"', "", cuerpo_u), 1)
                    u2 = u2.replace("<a:bodyPr", '<a:bodyPr wrap="none" lIns="0" rIns="0" tIns="0" bIns="0" anchor="t"', 1)
                    formas = formas.replace(u, u2, 1)
                    formas, nueva_u = colocar_rel(formas, u2, fin_x - ancho_u, y_u, fin_x, y_u + ALTO_UNIDADES, W, H, "r")
                    linea += f" unidades «{html.unescape(texto_forma(u)).strip()}» debajo de los números, al final del eje;"
                # Título girado del eje vertical: a la izquierda, a lo alto del trazado
                for a in girados:
                    ancho_g = alto_titulo_girado(a, dentro[3], medir)
                    formas, _ = colocar_rel(formas, a, 0, dentro[1], ancho_g, dentro[1] + dentro[3], W, H)
                    linea += f" título del eje vertical «{html.unescape(texto_forma(a)).strip()[:30]}» girado, a la izquierda;"
                viejo = trazado_rel(xml_antes)
                if viejo:
                    fijos = set(unidades) | set(girados)
                    actuales = re.findall(r'<cdr:relSizeAnchor\b.*?</cdr:relSizeAnchor>', formas, re.S)
                    saltar = [a for a in actuales if girado(a) or es_unidad_grafico(a, xml_antes) or a in fijos]
                    gx0, gy0, gw0, gh0 = caja(partes[ig])
                    formas, movidos = recolocar_formas(formas, viejo, (gw0 / EMU_PT, gh0 / EMU_PT), dentro, W, H, saltar)
                    if movidos:
                        linea += " se mueven con el trazado: " + ", ".join(f"«{m}»" for m in movidos) + ";"
                cambios[ruta_formas] = formas.encode("utf-8")
            # Etiquetas de datos de tamaño fijo en las que ya no cabe su texto (6 pt): crecen (petición del
            # usuario, 2026-11-25: «no puede desaparecer texto»; G_IA2025_1.1, «Aranceles a …»)
            xml, crecidas = etiquetas_que_caben(xml, W, H, medir)
            if crecidas:
                linea += f" {crecidas} etiqueta(s) de datos agrandada(s) para que se vea todo su texto;"
            cambios[ruta_graf] = xml.encode("utf-8")
            # Textos y líneas del autor dentro del gráfico (no barras horizontales, que ya lo hacen arriba): se mueven
            # con el trazado nuevo (G_IA2025_3.2 c: los promedios y sus líneas se quedaban sobre otras barras)
            viejo = trazado_rel(xml_antes)
            if formas and viejo and not tarta and not horizontal:
                actuales = re.findall(r'<cdr:relSizeAnchor\b.*?</cdr:relSizeAnchor>', formas, re.S)
                saltar = [a for a in actuales if girado(a) or es_unidad_grafico(a, xml_antes) or a in unidades_arriba]
                gx0, gy0, gw0, gh0 = caja(partes[ig])
                formas, movidos = recolocar_formas(formas, viejo, (gw0 / EMU_PT, gh0 / EMU_PT), dentro, W, H, saltar,
                                                   centro=True, lineas=True)
                if movidos:
                    cambios[ruta_formas] = formas.encode("utf-8")
                    textos_m = [m for m in movidos if m != "línea"]
                    n_lineas = movidos.count("línea")
                    linea += (" se mueven con el trazado: " + ", ".join(f"«{m}»" for m in textos_m)
                              + (f"{' y ' if textos_m else ''}{n_lineas} línea{'s' if n_lineas > 1 else ''} del autor"
                                 if n_lineas else "") + ";")
            for u in unidades_arriba:
                formas = colocar_unidades(formas, u, numeros, ini_unidades - arriba_marco, W, H, medir)
            if tarta and guias:
                if ruta_formas:
                    sig = max([int(v) for v in re.findall(r'<cdr:cNvPr id="(\d+)"', formas)] or [1]) + 1
                    formas = formas.replace("</c:userShapes>", "".join(
                        linea_guia_grafico(*g, W, H, sig + k) for k, g in enumerate(guias)) + "</c:userShapes>")
                    cambios[ruta_formas] = formas.encode("utf-8")
                else:
                    detalle.append(f"Aviso: panel {n}: {len(guias)} etiqueta(s) lejos de su porción necesitan línea guía "
                                   "y el gráfico no tiene capa de formas: ponlas a mano (blanco matiz 5, 0,5 pt)")
            if unidades_arriba:
                cambios[ruta_formas] = formas.encode("utf-8")
                linea += f" unidades a {ini_unidades / MM:.1f} mm, en la línea del eje y 2 mm sobre el trazado;".replace(".", ",")
            # Unidades que el autor puso en la hoja (no dentro del gráfico): igual, en la línea del eje y con la
            # línea de base 2 mm sobre el trazado
            for iu in [i for i, (t, g) in tipos.items() if t == "unidades" and g == ig]:
                a = partes[iu]
                l, t, r, b = margenes(a)
                ancho_txt = max([medir(tx, CUERPO_UNIDADES) for tx in textos_lineas(a)] or [0])
                cx = max(caja(a)[2], round((ancho_txt + 2) * EMU_PT) + l + r)
                a = re.sub(r'(<a:bodyPr\b[^>]*?)\s+anchor="\w+"', r'\1', a, count=1).replace("<a:bodyPr", '<a:bodyPr anchor="t"', 1)
                partes[iu] = colocar(a, x1 + round(numeros * EMU_PT) - l, round(ini_unidades * EMU_PT) - t, cx,
                                     t + b + round(ALTO_UNIDADES * EMU_PT))
                linea += (f" unidades de la hoja «{html.unescape(texto_forma(a)).strip()}» a {ini_unidades / MM:.1f} mm,"
                          f" en la línea del eje y 2 mm sobre el trazado;").replace(".", ",")
            # Textos sueltos sobre el gráfico: se mueven con él (en una tarta, con su centro: el texto del hueco)
            gx, gy, gw, gh = caja(partes[ig])
            mover = (0, round(arriba_marco * EMU_PT) - gy)
            if tarta:
                lay = re.search(r'<c:plotArea>\s*<c:layout>\s*<c:manualLayout>(.*?)</c:manualLayout>', xml_antes, re.S)
                f = {k: float(v) for k, v in re.findall(r'<c:([xywh]) val="([^"]+)"/>', lay.group(1))} if lay else {}
                viejo = (gx + (f.get("x", 0.1) + f.get("w", 0.8) / 2) * gw, gy + (f.get("y", 0.1) + f.get("h", 0.8) / 2) * gh)
                nuevo_c = (x1 + (dentro[0] + diametro / 2) * EMU_PT, (arriba_marco + dentro[1] + diametro / 2) * EMU_PT)
                mover = (round(nuevo_c[0] - viejo[0]), round(nuevo_c[1] - viejo[1]))
            if tarta:
                # Texto del centro (cifra y texto, en una caja o en varias, en la hoja o dentro del gráfico): una sola caja
                # con la cifra a 24 pt y el texto debajo a 7 pt, centrados en la tarta (petición del usuario, 2026-11-27)
                centro_hoja = sorted((caja(partes[i])[1], i) for i, (t, g) in tipos.items() if t == "interior" and g == ig
                                     and abs(caja(partes[i])[0] + caja(partes[i])[2] / 2 - viejo[0]) < gw / 4
                                     and abs(caja(partes[i])[1] + caja(partes[i])[3] / 2 - viejo[1]) < gh / 4
                                     and texto_forma(partes[i]).strip())
                centro_graf = []
                if formas and lay:
                    cxr, cyr = f.get("x", 0.1) + f.get("w", 0.8) / 2, f.get("y", 0.1) + f.get("h", 0.8) / 2
                    for an in re.findall(r'<cdr:relSizeAnchor\b.*?</cdr:relSizeAnchor>', formas, re.S):
                        x0r, y0r, x1r, y1r = caja_rel(an)
                        if (texto_forma(an).strip() and not girado(an) and abs((x0r + x1r) / 2 - cxr) < 0.25
                                and abs((y0r + y1r) / 2 - cyr) < 0.25 and an not in unidades):
                            centro_graf.append((y0r, an))
                    centro_graf.sort(key=lambda p: p[0])
                textos_c = [html.unescape(texto_forma(partes[i])) for _, i in centro_hoja] + \
                           [html.unescape(texto_forma(an)) for _, an in centro_graf]
                if len(textos_c) > 1 or centro_graf:
                    junto = " ".join(t.strip() for t in textos_c)
                    ancho_c, alto_c = medidas_centro_tarta(junto, medir)
                    cxp, cyp = dentro[0] + diametro / 2, dentro[1] + diametro / 2 - SUBIDA_CENTRO_TARTA
                    if centro_hoja:
                        # Se queda la primera caja de la hoja; las demás (y las del gráfico) se quitan
                        i0 = centro_hoja[0][1]
                        a = re.sub(r'<xdr:txBody>.*?</xdr:txBody>', lambda m: cuerpo_centro_tarta(junto, "xdr"),
                                   partes[i0], count=1, flags=re.S)
                        partes[i0] = colocar(a, round(nuevo_c[0] - ancho_c * EMU_PT / 2),
                                             round(nuevo_c[1] - (alto_c / 2 + SUBIDA_CENTRO_TARTA) * EMU_PT),
                                             round(ancho_c * EMU_PT), round(alto_c * EMU_PT))
                        for _, i in centro_hoja[1:]:
                            partes[i] = ""
                            tipos.pop(i, None)
                        for _, an in centro_graf:
                            formas = formas.replace(an, "", 1)
                        tipos.pop(i0, None)
                    else:
                        an0 = centro_graf[0][1]
                        nueva = re.sub(r'<cdr:txBody>.*?</cdr:txBody>', lambda m: cuerpo_centro_tarta(junto, "cdr", True),
                                       an0, count=1, flags=re.S)
                        formas = formas.replace(an0, nueva, 1)
                        formas, _ = colocar_rel(formas, nueva, cxp - ancho_c / 2, cyp - alto_c / 2, cxp + ancho_c / 2,
                                                cyp + alto_c / 2, W, H)
                        for _, an in centro_graf[1:]:
                            formas = formas.replace(an, "", 1)
                    if ruta_formas and formas:
                        cambios[ruta_formas] = formas.encode("utf-8")
                    linea += f" «{junto}» centrado en la tarta (cifra 24 pt Roboto Black, texto 7 pt debajo);"
            for ii in [i for i, (t, g) in tipos.items() if t == "interior" and g == ig]:
                xi, yi, wi, hi = caja(partes[ii])
                if tarta and abs(xi + wi / 2 - viejo[0]) < gw / 4 and abs(yi + hi / 2 - viejo[1]) < gh / 4:
                    # El texto del hueco: centrado en la tarta, también a lo alto (el texto, en el medio del cuadro)
                    a = re.sub(r'(<a:bodyPr\b[^>]*?)\s+anchor="\w+"', r'\1', partes[ii], count=1)
                    a = a.replace("<a:bodyPr", '<a:bodyPr anchor="ctr"', 1)
                    partes[ii] = colocar(a, round(nuevo_c[0] - wi / 2),
                                         round(nuevo_c[1] - hi / 2 - SUBIDA_CENTRO_TARTA * EMU_PT), wi, hi)
                    linea += f" «{html.unescape(texto_forma(a)).strip()}» centrado en la tarta;"
                    continue
                partes[ii] = colocar(partes[ii], xi + mover[0], yi + mover[1], wi, hi)
                linea += (f" «{html.unescape(texto_forma(partes[ii])).strip()}» se mueve con el "
                          f"{'centro de la tarta' if tarta else 'gráfico'};")
            if modo_ley == "quitar":
                # La leyenda común va en otro gráfico de la fila: esta, fuera
                xml = re.sub(r'<c:legend>.*?</c:legend>', "", xml, count=1, flags=re.S)
                cambios[ruta_graf] = xml.encode("utf-8")
                detalle.append(f"Aviso: panel {n}: leyenda quitada: la común de la fila ya va debajo de los paneles")
            partes[ig] = colocar(partes[ig], x1, round(arriba_marco * EMU_PT), ancho_graf, round(H * EMU_PT))
            fondo = inicio + alto_panel + extra_ley
            if fila_k is not None:
                fondo_filas[fila_k] = max(fondo_filas.get(fila_k, 0), fondo)
                if col_j == len(filas_l[fila_k]) - 1 and sueltas_l.get(fila_k):
                    # Las leyendas que son un gráfico aparte: debajo de la fila, juntas y centradas
                    y_l = fondo_filas[fila_k] + LEYENDA_BAJO_PANEL
                    medidas = []
                    for il in sueltas_l[fila_k]:
                        rl = re.search(r'<c:chart\b[^>]*\br:id="([^"]+)"', partes[il]).group(1)
                        xl = z.read(relaciones[rl][1]).decode("utf-8")
                        medidas.append((il, relaciones[rl][1], xl, *medidas_leyenda_horizontal(xl, completo[1] / EMU_PT, medir)))
                    total = sum(m[3] for m in medidas)
                    xs = completo[0] + round((completo[1] / EMU_PT - total) / 2 * EMU_PT)
                    alto_l = max(m[4] for m in medidas)
                    for il, rgl, xl, lw_s, lh_s, _ in medidas:
                        xl = poner_leyenda(xl, lw_s, alto_l, 0, 0, lw_s, alto_l, "b")
                        xl = sin_trazado(xl)
                        cambios[rgl] = xl.encode("utf-8")
                        partes[il] = colocar(partes[il], xs, round(y_l * EMU_PT), round(lw_s * EMU_PT), round(alto_l * EMU_PT))
                        xs += round(lw_s * EMU_PT)
                    fondo_filas[fila_k] = y_l + alto_l
                    detalle.append(f"Fila {fila_k + 1}: leyenda común (gráfico aparte) debajo de los paneles, centrada, "
                                   f"a {y_l / MM:.1f} mm".replace(".", ","))
                fondo = fondo_filas[fila_k]
            if tarta:
                linea += (f" tarta a {(inicio + MEDIA_ETIQUETA) / MM:.1f} mm, {filas} filas de diámetro "
                          f"({diametro / MM:.1f} mm), centrada en la columna 1; leyenda centrada a su altura").replace(".", ",")
            else:
                linea += (f" gráfico a {inicio / MM:.1f} mm, {filas} filas ({alto_panel / MM:.1f} mm;"
                          f" categorías {sz / 100:g} pt en {lineas_cat} línea{'s' if lineas_cat > 1 else ''},"
                          f" {filas_cat} fila{'s' if filas_cat > 1 else ''})").replace(".", ",")
            if nota:
                linea += f" — {nota}"
            detalle.append(linea)

        if lado:
            # FUENTES, a lo ancho de las dos columnas, debajo de la última fila
            x1, ancho_util = completo
            fondo = max(fondo_filas.values())
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


# Líneas de los ejes y de división como en el TERMINADO: blanco oscurecido (matiz 5 = 50 %, matiz 4 = 35 %),
# remate plano (sin relieve) y unión angular. Grosor en EMU (0,5 pt = 6350).
LINEA_EJE = ('<a:ln w="6350" cap="flat"><a:solidFill><a:srgbClr val="FFFFFF"><a:lumMod val="50000"/></a:srgbClr>'
             '</a:solidFill><a:miter lim="800000"/></a:ln>')
LINEA_DIVISION = ('<a:ln w="3810" cap="flat"><a:solidFill><a:srgbClr val="FFFFFF"><a:lumMod val="65000"/></a:srgbClr>'
                  '</a:solidFill><a:prstDash val="solid"/><a:miter lim="800000"/></a:ln>')
EJES = re.compile(r'<c:(catAx|valAx|dateAx|serAx)>.*?</c:\1>', re.S)
GRUPOS = re.compile(r'<c:(\w+Chart)>.*?</c:\1>', re.S)
# Orden de los hijos de cada eje en el esquema (Excel no abre el gráfico si no se respeta)
_COMUN = ["axId", "scaling", "delete", "axPos", "majorGridlines", "minorGridlines", "title", "numFmt", "majorTickMark",
          "minorTickMark", "tickLblPos", "spPr", "txPr", "crossAx", "crosses", "crossesAt"]
ORDEN_EJE = {
    "catAx": _COMUN + ["auto", "lblAlgn", "lblOffset", "tickLblSkip", "tickMarkSkip", "noMultiLvlLbl", "extLst"],
    "dateAx": _COMUN + ["auto", "lblOffset", "baseTimeUnit", "majorUnit", "majorTimeUnit", "minorUnit", "minorTimeUnit", "extLst"],
    "valAx": _COMUN + ["crossBetween", "majorUnit", "minorUnit", "dispUnits", "extLst"],
    "serAx": _COMUN + ["tickLblSkip", "tickMarkSkip", "extLst"],
}
ORDEN_ESCALA = ["logBase", "orientation", "max", "min", "extLst"]


def con_linea(sppr, linea):
    """spPr con la línea dada: sustituye la que haya o la pone tras el relleno (el orden del esquema)."""
    if sppr is None:
        return f'<c:spPr>{linea}</c:spPr>'
    if re.search(r'<a:ln\b', sppr):
        return re.sub(r'<a:ln\b[^>]*/>|<a:ln\b.*?</a:ln>', linea, sppr, count=1, flags=re.S)
    relleno = re.search(r'<a:(noFill|solidFill|gradFill|blipFill|pattFill|grpFill)\b[^>]*(/>|>.*?</a:\1>)', sppr, re.S)
    pos = relleno.end() if relleno else sppr.index(">") + 1
    return sppr[:pos] + linea + sppr[pos:]


def hijos(xml):
    """Los hijos directos de un elemento <c:…>, como lista de [nombre, texto] (los de dentro no se separan)."""
    cuerpo = xml[xml.index(">") + 1:xml.rindex("</")]
    lista, i = [], 0
    while True:
        m = re.compile(r'<c:(\w+)\b[^>]*?(/?)>').search(cuerpo, i)
        if not m:
            return lista
        nombre, fin = m.group(1), m.end()
        if not m.group(2):
            # Cierre que le corresponde, contando los del mismo nombre que haya dentro
            nivel = 1
            for t in re.compile(rf'<(/?)c:{nombre}\b[^>]*?(/?)>').finditer(cuerpo, fin):
                if t.group(2):
                    continue
                nivel += -1 if t.group(1) else 1
                if not nivel:
                    fin = t.end()
                    break
        lista.append([nombre, cuerpo[m.start():fin]])
        i = fin


def poner(lista, orden, nombre, texto):
    """Pone (o sustituye) un hijo en su sitio del orden del esquema; texto None lo quita."""
    for h in lista:
        if h[0] == nombre:
            if texto is None:
                lista.remove(h)
            else:
                h[1] = texto
            return
    if texto is None:
        return
    pos = orden.index(nombre)
    i = next((k for k, h in enumerate(lista) if h[0] in orden and orden.index(h[0]) > pos), len(lista))
    lista.insert(i, [nombre, texto])


def hijo(lista, nombre):
    return next((h[1] for h in lista if h[0] == nombre), None)


def valor(texto):
    m = texto and re.search(r'\bval="([^"]*)"', texto)
    return m.group(1) if m else None


def numeros(xml):
    out = []
    for v in re.findall(r'<c:v>([^<]*)</c:v>', xml):
        try:
            out.append(float(v))
        except ValueError:
            pass
    return out


def cifra(x):
    return f"{x:.10g}"


def valores_por_eje(xml):
    """Valores de las series de cada eje de valores (por su axId); en dispersión, X al eje de abajo/arriba."""
    ejes = {valor(re.search(r'<c:axId\b[^>]*/>', e.group(0)).group(0)): e for e in EJES.finditer(xml)}
    datos = {}
    for g in GRUPOS.finditer(xml):
        ids = re.findall(r'<c:axId val="(\d+)"/>', g.group(0))
        series = re.findall(r'<c:ser>.*?</c:ser>', g.group(0), re.S)
        for i in ids:
            e = ejes.get(i)
            if not e or e.group(1) != "valAx":
                continue
            horizontal = valor(re.search(r'<c:axPos[^>]*/>', e.group(0)).group(0)) in ("b", "t")
            partes = ["xVal" if horizontal else "yVal"] if g.group(1) == "scatterChart" else ["val"]
            for s in series:
                for parte in partes:
                    for bloque in re.findall(rf'<c:{parte}>.*?</c:{parte}>', s, re.S):
                        datos.setdefault(i, []).extend(numeros(bloque))
            # Apiladas: lo que llega a cada categoría es la suma (las positivas hacia arriba y las negativas hacia
            # abajo; G_IA2025_2.1, áreas apiladas hasta 0,9 con series de 0,2)
            if re.search(r'<c:grouping val="stacked"/>', g.group(0)):
                arriba, abajo = {}, {}
                for s in series:
                    val = re.search(r'<c:val>.*?</c:val>', s, re.S)
                    for k, v in re.findall(r'<c:pt idx="(\d+)">\s*<c:v>([^<]+)</c:v>', val.group(0) if val else ""):
                        try:
                            x = float(v)
                        except ValueError:
                            continue
                        (arriba if x >= 0 else abajo)[k] = (arriba if x >= 0 else abajo).get(k, 0) + x
                datos.setdefault(i, []).extend(list(arriba.values()) + list(abajo.values()))
    return datos


def divisiones_al_eje_de_valores(xml):
    """Las líneas de división van con el eje de valores (las verticales en barras horizontales, como en el TERMINADO
    «GIng_DO2626_05 HORIZONTAL» y el .ai). Si el autor las puso en el eje de categorías visible y el de valores que
    cruza con él no las tiene, pasan a ese (G_MemoriaSupervision_3.4: líneas entre categorías). Devuelve el xml y un
    aviso (o None)."""
    ejes = {valor(re.search(r'<c:axId\b[^>]*/>', e.group(0)).group(0)): e for e in EJES.finditer(xml)}
    for i, e in ejes.items():
        if e.group(1) not in ("catAx", "dateAx") or '<c:delete val="1"/>' in e.group(0) or "<c:majorGridlines" not in e.group(0):
            continue
        h = hijos(e.group(0))
        otro = ejes.get(valor(hijo(h, "crossAx")))
        if not otro or otro.group(1) != "valAx" or '<c:delete val="1"/>' in otro.group(0) or "<c:majorGridlines" in otro.group(0):
            continue
        lineas = hijo(h, "majorGridlines")
        poner(h, ORDEN_EJE[e.group(1)], "majorGridlines", None)
        poner(h, ORDEN_EJE[e.group(1)], "minorGridlines", None)
        h2 = hijos(otro.group(0))
        poner(h2, ORDEN_EJE["valAx"], "majorGridlines", lineas)
        xml = xml.replace(e.group(0), f"<c:{e.group(1)}>" + "".join(t for _, t in h) + f"</c:{e.group(1)}>", 1)
        xml = xml.replace(otro.group(0), "<c:valAx>" + "".join(t for _, t in h2) + "</c:valAx>", 1)
        return xml, ("Aviso: las ⟪líneas de división⟫ estaban en el eje de categorías: pasan al eje de valores "
                     "(como en la guía y el .ai)")
    return xml, None


def formato_ejes(xml):
    """Ejes según la guía (página 15) y el TERMINADO: línea de cada eje y de sus líneas de división; eje en
    cero; marcas de graduación; etiquetas en Bajo y a distancia 100; el máximo y el mínimo fijos, en un tramo
    del eje (el gráfico se cierra con una línea de división). Devuelve el xml y lo hecho, para el detalle."""
    cuentas = []
    xml, movidas = divisiones_al_eje_de_valores(xml)
    if movidas:
        cuentas.append(movidas)
    # Ejes de dispersión: los dos de valores de un grupo scatterChart. En un gráfico combinado la dispersión puede
    # ir sobre un eje de categorías (columnas y puntos): entonces no es un gráfico de dispersión
    tipos = {valor(re.search(r'<c:axId\b[^>]*/>', e.group(0)).group(0)): e.group(1) for e in EJES.finditer(xml)}
    de_dispersion = set()
    for g in GRUPOS.finditer(xml):
        ids = re.findall(r'<c:axId val="(\d+)"/>', g.group(0))
        if g.group(1) == "scatterChart" and all(tipos.get(i) == "valAx" for i in ids):
            de_dispersion.update(ids)
    datos = valores_por_eje(xml)
    info = {}
    for e in EJES.finditer(xml):
        h = hijos(e.group(0))
        escala = hijos(hijo(h, "scaling") or "<c:scaling></c:scaling>")
        info[valor(hijo(h, "axId"))] = {
            "tipo": e.group(1), "pos": valor(hijo(h, "axPos")), "datos": datos.get(valor(hijo(h, "axId")), []),
            "min": valor(hijo(escala, "min")), "max": valor(hijo(escala, "max")),
            "orientacion": valor(hijo(escala, "orientation")) or "minMax", "log": hijo(escala, "logBase") is not None,
            "unidad": valor(hijo(h, "majorUnit"))}

    def eje(m):
        a, tipo = m.group(0), m.group(1)
        orden = ORDEN_EJE[tipo]
        h = hijos(a)
        nombre = ("eje de categorías" if tipo in ("catAx", "dateAx") else "eje de valores" if tipo == "valAx"
                  else "eje de series")
        hecho = []
        if valor(hijo(h, "delete")) == "1":
            # Oculto: no se toca (en el TERMINADO quedan como los dejó el autor), salvo sus líneas de división: sin eje
            # no van (G_MemoriaSupervision_3.2, como en el .ai; decisión del usuario, 2026-11-27)
            divisiones = sum(hijo(h, d) is not None for d in ("majorGridlines", "minorGridlines"))
            if divisiones:
                poner(h, ORDEN_EJE[tipo], "majorGridlines", None)
                poner(h, ORDEN_EJE[tipo], "minorGridlines", None)
                cuentas.append(f"Aviso: el {nombre} va oculto: quitadas sus ⟪líneas de división⟫ (sin eje no van)")
                return f"<c:{tipo}>" + "".join(t for _, t in h) + f"</c:{tipo}>"
            cuentas.append(nombre + " (oculto): sin tocar")
            return a
        if valor(hijo(h, "tickLblPos")) == "none":
            # Sin cifras: el autor lo tiene para apoyar algo (series vacías, otra escala), no para verlo. Sin línea ni
            # marcas: con el estilo restablecido se perdía su línea invisible y salía gris con marcas (G_IA2025_1.14)
            poner(h, orden, "majorTickMark", '<c:majorTickMark val="none"/>')
            poner(h, orden, "minorTickMark", '<c:minorTickMark val="none"/>')
            sppr = hijo(h, "spPr")
            poner(h, orden, "spPr", con_linea(sppr.replace("<c:spPr/>", "<c:spPr></c:spPr>") if sppr
                                              else "<c:spPr><a:noFill/></c:spPr>", '<a:ln><a:noFill/></a:ln>'))
            cuentas.append(nombre + " sin cifras: sin línea ni marcas")
            return f"<c:{tipo}>" + "".join(t for _, t in h) + f"</c:{tipo}>"
        dispersion = valor(hijo(h, "axId")) in de_dispersion

        # Línea del eje y de sus líneas de división
        sppr = hijo(h, "spPr")
        poner(h, orden, "spPr", con_linea(sppr.replace("<c:spPr/>", "<c:spPr></c:spPr>") if sppr
                                          else "<c:spPr><a:noFill/></c:spPr>", LINEA_EJE))
        divisiones = 0
        for d in ("majorGridlines", "minorGridlines"):
            texto = hijo(h, d)
            if texto is not None:
                divisiones += 1
                dentro = re.search(r'<c:spPr>.*?</c:spPr>', texto, re.S)
                poner(h, orden, d, f'<c:{d}>{con_linea(dentro.group(0) if dentro else None, LINEA_DIVISION)}</c:{d}>')
        if divisiones:
            hecho.append(f"{divisiones} de división")

        horizontal = valor(hijo(h, "axPos")) in ("b", "t")
        otro = info.get(valor(hijo(h, "crossAx")), {})
        vals = otro.get("datos", [])
        minimo = float(otro["min"]) if otro.get("min") is not None else None
        maximo = float(otro["max"]) if otro.get("max") is not None else None
        negativos = any(v < 0 for v in vals) or (minimo is not None and minimo < 0)
        # También si el eje llega por debajo de 0 sin datos negativos: con el máximo fijo del autor (130, saltos de
        # 20) Excel baja el mínimo a −10 para que los saltos casen (G_IA2025_1.1, petición del usuario, 2026-11-25:
        # el 0 señalado con el eje y marcas en Cruz)
        if not negativos and vals and otro.get("tipo") == "valAx" and not otro.get("log"):
            esc = escala_eje(vals, minimo, maximo, float(otro["unidad"]) if otro.get("unidad") else None)
            negativos = bool(esc) and esc[0] < 0
        # Eje arriba: el otro eje acaba en 0 (todo negativo), y este se cruza en 0
        tope = maximo if maximo is not None else (max(vals) if vals else None)
        arriba = (negativos and tope is not None and tope <= 0 and otro.get("orientacion") == "minMax")

        # Eje en cero: el de categorías (y los dos de dispersión) cruzan el otro eje en 0
        cruza = valor(hijo(h, "crosses"))
        if (tipo in ("catAx", "dateAx") or dispersion) and cruza != "max" and not otro.get("log"):
            if valor(hijo(h, "crossesAt")) != "0":
                hecho.append("cruza en 0")
            poner(h, orden, "crosses", None)
            poner(h, orden, "crossesAt", '<c:crossesAt val="0"/>')
        elif cruza == "max":
            hecho.append("aviso: cruza en el máximo (eje derecho o de arriba), se deja así")

        # Marcas de graduación
        if horizontal:
            marca = "out" if arriba else "cross" if negativos else "in"
        else:
            marca = "cross" if dispersion and negativos else "in"
        secundaria = "out" if horizontal and arriba else "none"
        nombres_marca = {"in": "Interior", "out": "Exterior", "cross": "Cruz", "none": "Ninguno"}
        poner(h, orden, "majorTickMark", f'<c:majorTickMark val="{marca}"/>')
        poner(h, orden, "minorTickMark", f'<c:minorTickMark val="{secundaria}"/>')
        hecho.append(f"marcas {nombres_marca[marca]}" + (f" y secundarias {nombres_marca[secundaria]}"
                                                         if secundaria != "none" else ""))
        # Marcas: una por valor; pero si las etiquetas van saltadas («una cada 4»), las marcas con ellas: con 104
        # trimestres, una marca por valor llena el eje (G_IA2025_3.1 b, petición del usuario, 2026-11-26; el .ai, una
        # por año)
        salto_etiquetas = valor(hijo(h, "tickLblSkip"))
        marcas_con = salto_etiquetas if salto_etiquetas not in (None, "1") else "1"
        if tipo == "catAx" and horizontal and (valor(hijo(h, "tickMarkSkip")) or "1") != marcas_con:
            hecho.append(f"una marca cada {marcas_con} valor{'es' if marcas_con != '1' else ''}" +
                         (" (con las etiquetas)" if marcas_con != "1" else "") +
                         f" (antes cada {valor(hijo(h, 'tickMarkSkip')) or '1'})")
            poner(h, orden, "tickMarkSkip", f'<c:tickMarkSkip val="{marcas_con}"/>')

        # Etiquetas: en Bajo (las de los ejes horizontales y, en dispersión, también las del vertical) y a
        # distancia 100 del eje
        if horizontal or dispersion:
            # «Bajo» es el lado del mínimo del eje que cruza: si ese eje va invertido (categorías de arriba abajo,
            # «maxMin»), el mínimo queda arriba y las cifras subían; entonces «Alto», que queda abajo
            # (G_MemoriaSupervision_3.4, barras horizontales)
            if otro.get("orientacion") == "maxMin":
                poner(h, orden, "tickLblPos", '<c:tickLblPos val="high"/>')
                hecho.append("etiquetas en Alto (el otro eje va invertido: así quedan abajo / a la izquierda)")
            else:
                poner(h, orden, "tickLblPos", '<c:tickLblPos val="low"/>')
                hecho.append("etiquetas en Bajo")
        if tipo in ("catAx", "dateAx"):
            if valor(hijo(h, "lblOffset")) not in (None, "100"):
                hecho.append(f"etiquetas a distancia 100 del eje (antes {valor(hijo(h, 'lblOffset'))})")
            poner(h, orden, "lblOffset", '<c:lblOffset val="100"/>')

        # Eje cortado: el máximo y el mínimo fijos van a un tramo del eje, para cerrar con una línea de división
        if tipo == "valAx":
            escala = hijos(hijo(h, "scaling") or "<c:scaling></c:scaling>")
            unidad = valor(hijo(h, "majorUnit"))
            for lim, redondeo in (("max", math.ceil), ("min", math.floor)):
                fijo = valor(hijo(escala, lim))
                if fijo is None:
                    continue
                if unidad is None:
                    hecho.append(f"aviso: {'máximo' if lim == 'max' else 'mínimo'} fijo ({cifra(float(fijo))}) "
                                 "con el intervalo automático: comprobar que cierra en una línea de división")
                    continue
                u, f = float(unidad), float(fijo)
                tramos = f / u
                if abs(tramos - round(tramos)) > 1e-9:
                    nuevo = redondeo(tramos) * u
                    poner(escala, ORDEN_ESCALA, lim, f'<c:{lim} val="{cifra(nuevo)}"/>')
                    hecho.append(f"{'máximo' if lim == 'max' else 'mínimo'} de {cifra(f)} a {cifra(nuevo)} "
                                 f"(tramos de {cifra(u)})".replace(".", ","))
            poner(h, orden, "scaling", "<c:scaling>" + "".join(t for _, t in escala) + "</c:scaling>")

        cuentas.append(nombre + ": " + ", ".join(hecho))
        return f"<c:{tipo}>" + "".join(t for _, t in h) + f"</c:{tipo}>"
    return EJES.sub(eje, xml), cuentas


def paso3(trabajo, pid=None):
    """Ejes según la guía de gráficos (página 15) y el TERMINADO: línea de los ejes 0,5 pt y de las líneas de
    división 0,3 pt, en blanco oscurecido, sin relieve y con unión angular; eje en cero, marcas de graduación,
    etiquetas en Bajo y a distancia 100, y límites fijos en un tramo del eje."""
    estado = leer_estado(trabajo)
    _, pasos = nombres(trabajo)
    base = pasos / estado["pasos"][estado["actual"]]["archivo"]
    requiere(estado, ("Tamaño y colocación",), "«Ejes»")
    cambios, detalle = {}, []
    with zipfile.ZipFile(base) as z:
        ruta = dibujo_de_hoja(z, HOJA_GRAFICO)
        dibujo = z.read(ruta).decode("utf-8")
        relaciones = rels(z, ruta)
        for i, rid in enumerate(re.findall(r'<c:chart\b[^>]*\br:id="([^"]+)"', dibujo), 1):
            ruta_graf = relaciones[rid][1]
            xml, cuentas = formato_ejes(z.read(ruta_graf).decode("utf-8"))
            cambios[ruta_graf] = xml.encode("utf-8")
            avisos_ejes = [c for c in cuentas if c.startswith("Aviso: ")]
            cuentas = [c for c in cuentas if not c.startswith("Aviso: ")]
            detalle.append(f"Panel {i}: " + ("; ".join(cuentas) if cuentas else "sin ejes"))
            detalle += [f"Aviso: panel {i}: " + c[len("Aviso: "):] for c in avisos_ejes]
    detalle.append("Ejes 0,5 pt en blanco oscuro 50 % (matiz 5); líneas de división 0,3 pt en blanco oscuro 35 % "
                   "(matiz 4); sin relieve y unión angular")
    return nuevo_paso(trabajo, "Ejes", cambios, detalle)

# ---------------------------------------------------------------- textos especiales (guía, págs. 10 y 11)

# Fechas del eje en el formato del idioma (guía: [$-es-US,1]mmm-aa;@ y [$-en-US,1]mmm-aa;@; en el archivo, por
# su número de idioma y con «yy»)
FECHA_EJE = {"es": "[$-1540A]mmm\\-yy;@", "en": "[$-10409]mmm\\-yy;@"}
ESCALA_DCHA = {"es": "(Escala dcha.)", "en": "(Right-hand scale)"}
RE_ESCALA_DCHA = re.compile(
    r'\s*\(?\s*\b(?:escala|eje|esc\.)\s*(?:derecha|derecho|dcha\.?|dcho\.?|dch\.?|der\.?)\s*\)?'
    r'|\s*\(?\s*\b(?:right[- ]hand\s+(?:scale|axis)|right\s+(?:scale|axis)|rhs)\b\s*\)?', re.I)
# Trimestres: «1T», «T1», «1er trim.», «I T», «Q1», «2024T1», «1T24»… → «I TR 2024» (es) / «Q1 2024» (en)
RE_TRIMESTRE = re.compile(
    r'(?<![\w/])(?:(?P<a1>(?:19|20)\d{2})\s*[-/ ]?\s*)?'
    r'(?:(?P<n1>[1-4])\s*(?:er|º|o|ª)?\.?\s*(?:TR|Tr|tr|TRIM\.?|Trim\.?|trim\.?|[Tt]rimestre|TRIMESTRE|T|Q)'
    r'|(?:TR|T|Q)\s*(?P<n2>[1-4])'
    r'|(?P<r>IV|III|II|I)\s*(?P<rt>TR|Tr|TRIM\.?|Trim\.?|trim\.?|[Tt]rimestre|TRIMESTRE|T))'
    r'(?:\s*[-/ ]?\s*(?P<a2>(?:19|20)\d{2}|\d{2})(?!\d))?(?![\w])')
ROMANO_TRIMESTRE = {"1": "I", "2": "II", "3": "III", "4": "IV", "I": "I", "II": "II", "III": "III", "IV": "IV"}
NUMERO_TRIMESTRE = {"I": "1", "II": "2", "III": "3", "IV": "4"}


def trimestres(texto, idioma):
    def cambiar(m):
        # «IT» a secas, sin año, es Italia (G_IA2025_3.2 c: salía «I TR»), no el primer trimestre
        if m.group(0) == "IT":
            return m.group(0)
        n = m.group("n1") or m.group("n2") or NUMERO_TRIMESTRE[m.group("r")]
        anio = m.group("a1") or m.group("a2")
        base = f"{ROMANO_TRIMESTRE[n]} TR" if idioma != "en" else f"Q{n}"
        return base + (f" {anio}" if anio else "")
    return RE_TRIMESTRE.sub(cambiar, texto)


def escala_derecha(texto, idioma):
    if not RE_ESCALA_DCHA.search(texto):
        return texto
    return RE_ESCALA_DCHA.sub("", texto).rstrip() + " " + ESCALA_DCHA["en" if idioma == "en" else "es"]


def nombre_leyenda(texto, idioma):
    """Las reglas de los nombres de las series: minúscula salvo siglas, escala derecha y trimestres."""
    return trimestres(escala_derecha(en_minuscula(texto, idioma), idioma), idioma)


def celdas_de_rango(f):
    """[(hoja, celda)] de una referencia (puede ser una unión de rangos)."""
    out = []
    for h1, h2, c1, r1, c2, r2 in re.findall(r"(?:'([^']+)'|([^!,()'\s]+))!\$?([A-Z]+)\$?(\d+)(?::\$?([A-Z]+)\$?(\d+))?", f):
        c2, r2 = c2 or c1, r2 or r1
        for c in range(columna_num(c1), columna_num(c2) + 1):
            for r in range(int(r1), int(r2) + 1):
                out.append((h1 or h2, f"{columna_letras(c)}{r}"))
    return out


def cambiar_categorias(z, xml, hojas, funcion):
    """Aplica `funcion` (texto → texto) a las etiquetas del eje de categorías: en la caché del gráfico y en las
    celdas del rango de las que salen (las que tienen ese mismo texto). Devuelve el xml, los cambios y cuántas
    son fórmulas (solo se cambia su valor guardado)."""
    cat = re.search(r'<c:cat>.*?</c:cat>', xml, re.S)
    if not cat or ("<c:strRef>" not in cat.group(0) and "<c:multiLvlStrRef>" not in cat.group(0)):
        return xml, [], 0
    cambios = {}

    def punto(m):
        antes = html.unescape(m.group(2))
        nuevo = funcion(antes)
        if nuevo != antes:
            cambios[antes] = nuevo
        return m.group(1) + html.escape(nuevo, quote=False) + m.group(3)
    nueva_cat = re.sub(r'(<c:pt idx="\d+">\s*<c:v>)([^<]*)(</c:v>)', punto, cat.group(0))
    if not cambios:
        return xml, [], 0
    xml = xml.replace(cat.group(0), nueva_cat, 1)
    f = re.search(r'<c:f>([^<]*)</c:f>', cat.group(0))
    formulas = 0
    if f:
        compartidos = textos_compartidos(z)
        for nombre, ref in celdas_de_rango(html.unescape(f.group(1))):
            ruta_hoja = hoja_de(z, nombre)
            hoja = hojas.get(ruta_hoja) or z.read(ruta_hoja).decode("utf-8")
            c = celda(hoja, ref)
            if not c:
                continue
            texto = texto_de_celda(c, compartidos)
            if texto in cambios:
                formulas += "<f" in c.group(0)
                hojas[ruta_hoja] = poner_texto_celda(hoja, c, cambios[texto])
    return xml, [f"«{a}» → «{n}»".replace("\n", "⏎") for a, n in cambios.items()], formulas


def poner_celda_texto(hoja, ref, texto):
    """La celda `ref` con el texto (la crea, con su fila si hace falta, en su sitio)."""
    c = celda(hoja, ref)
    if c:
        return poner_texto_celda(hoja, c, texto)
    col, fila = re.match(r'([A-Z]+)(\d+)', ref).groups()
    nueva = f'<c r="{ref}" t="inlineStr"><is><t xml:space="preserve">{html.escape(texto, quote=False)}</t></is></c>'
    f = re.search(rf'<row r="{fila}"(?=[\s>/])[^>]*?(?:/>|>.*?</row>)', hoja, re.S)
    if not f:
        siguiente = next((m for m in re.finditer(r'<row r="(\d+)"', hoja) if int(m.group(1)) > int(fila)), None)
        fila_xml = f'<row r="{fila}">{nueva}</row>'
        if siguiente:
            return hoja[:siguiente.start()] + fila_xml + hoja[siguiente.start():]
        return hoja.replace("</sheetData>", fila_xml + "</sheetData>", 1).replace("<sheetData/>", f"<sheetData>{fila_xml}</sheetData>", 1)
    fx = f.group(0)
    if fx.endswith("/>"):
        nueva_fila = fx[:-2] + ">" + nueva + "</row>"
    else:
        despues = next((m for m in re.finditer(r'<c r="([A-Z]+)\d+"', fx) if columna_num(m.group(1)) > columna_num(col)), None)
        nueva_fila = fx[:despues.start()] + nueva + fx[despues.start():] if despues else fx[:-6] + nueva + "</row>"
    return hoja[:f.start()] + nueva_fila + hoja[f.end():]


def trimestres_en_dos_niveles(z, xml, hojas):
    """Categorías de una sola columna como «I TR 2022», «II TR», «III TR», «IV TR», «I TR 2023»… (el año solo en el
    primer trimestre): en dos niveles, como en el .ai (G_IA2025_1.33 panel c, petición del usuario, 2026-11-26): los
    trimestres en la columna del autor y los años en la de su izquierda, si está vacía; el eje los pone debajo,
    centrados bajo sus trimestres, y todo en horizontal. Devuelve el xml y un aviso (cambia las celdas del autor)."""
    cat = re.search(r'<c:cat>\s*<c:strRef>\s*<c:f>([^<]*)</c:f>.*?</c:cat>', xml, re.S)
    if not cat:
        return xml, None
    f = html.unescape(cat.group(1))
    rango = re.fullmatch(r"((?:'[^']+'|[^!]+))!\$?([A-Z]+)\$?(\d+):\$?([A-Z]+)\$?(\d+)", f)
    if not rango or rango.group(2) != rango.group(4) or columna_num(rango.group(2)) < 2:
        return xml, None
    puntos = {int(i): html.unescape(v) for i, v in re.findall(r'<c:pt idx="(\d+)">\s*<c:v>([^<]*)</c:v>', cat.group(0))}
    trimestre = r'(?:I{1,3}|IV)\s*TR|Q[1-4]'
    partes = {}
    for i, v in puntos.items():
        m = re.fullmatch(rf'\s*({trimestre})(?:\s+((?:19|20)\d{{2}}))?\s*', v.replace("\n", " "))
        if not m:
            return xml, None
        partes[i] = (m.group(1), m.group(2))
    anos = [i for i, (_, a) in partes.items() if a]
    if not anos or len(anos) == len(partes):
        return xml, None
    hoja_nombre, col, r1, r2 = rango.group(1), rango.group(2), int(rango.group(3)), int(rango.group(5))
    izq = columna_letras(columna_num(col) - 1)
    try:
        ruta_hoja = hoja_de(z, hoja_nombre.strip("'"))
    except Fallo:
        return xml, None
    hoja = hojas.get(ruta_hoja) or z.read(ruta_hoja).decode("utf-8")
    compartidos = textos_compartidos(z)
    for r in range(r1, r2 + 1):
        c = celda(hoja, f"{izq}{r}")
        if c and (texto_de_celda(c, compartidos) or "").strip():
            return xml, (f"Aviso: las categorías llevan el año solo en el primer trimestre («{puntos[anos[0]]}»); no se "
                         f"han puesto en dos niveles porque la columna {izq} no está vacía: revisar a mano")
    for i, (t, a) in partes.items():
        fila = r1 + i
        c = celda(hoja, f"{col}{fila}")
        if c and a:
            hoja = poner_texto_celda(hoja, c, t)
        if a:
            hoja = poner_celda_texto(hoja, f"{izq}{fila}", a)
    hojas[ruta_hoja] = hoja
    n = r2 - r1 + 1
    hoja_ref = hoja_nombre
    nueva_f = f"{hoja_ref}!${izq}${r1}:${col}${r2}"
    interior = "".join(f'<c:pt idx="{i}"><c:v>{html.escape(t, quote=False)}</c:v></c:pt>' for i, (t, _) in sorted(partes.items()))
    exterior = "".join(f'<c:pt idx="{i}"><c:v>{a}</c:v></c:pt>' for i, (_, a) in sorted(partes.items()) if a)
    nueva_cat = (f'<c:cat><c:multiLvlStrRef><c:f>{html.escape(nueva_f, quote=False)}</c:f><c:multiLvlStrCache>'
                 f'<c:ptCount val="{n}"/><c:lvl>{interior}</c:lvl><c:lvl>{exterior}</c:lvl></c:multiLvlStrCache>'
                 '</c:multiLvlStrRef></c:cat>')
    # Todas las series que usan esas categorías
    xml = re.sub(r'<c:cat>\s*<c:strRef>\s*<c:f>' + re.escape(cat.group(1)) + r'</c:f>.*?</c:cat>', lambda m: nueva_cat, xml, flags=re.S)
    xml = xml.replace('<c:noMultiLvlLbl val="1"/>', '<c:noMultiLvlLbl val="0"/>')
    return xml, (f"Aviso: categorías en dos niveles: los trimestres en la columna {col} («{puntos[anos[0]]}» → "
                 f"«⟪{partes[anos[0]][0]}⟫») y los años en la {izq}, debajo y centrados bajo sus trimestres (como en "
                 "el .ai); cambiadas las celdas del autor ⟦celdas:" + hoja_nombre.strip("'") + f"|{izq}{r1}:{col}{r2}⟧")


def textos_trimestres(xml, idioma):
    """Trimestres en los textos de un dibujo (hoja o gráfico) o de los títulos del gráfico: en cada <a:t>."""
    hechos = []

    def t(m):
        antes = html.unescape(m.group(2))
        nuevo = trimestres(antes, idioma)
        if nuevo != antes:
            hechos.append(f"«{antes.strip()}» → «{nuevo.strip()}»")
        return m.group(1) + html.escape(nuevo, quote=False) + m.group(3)
    return re.sub(r'(<a:t(?:\s[^>]*)?>)([^<]*)(</a:t>)', t, xml), hechos


# ---- números de los ejes

def unidad_nice(raw):
    if raw <= 0:
        return 1
    e = 10 ** math.floor(math.log10(raw))
    for k in (1, 2, 5, 10):
        if k * e >= raw - 1e-12:
            return k * e
    return 10 * e


def escala_eje(valores, minimo=None, maximo=None, unidad=None):
    """Mínimo, máximo y salto del eje como los pone Excel (aprox.): el salto más pequeño de 1, 2 o 5 × 10^n que
    deja como mucho 9 tramos; un 5 % de aire por arriba (y por abajo con negativos); el 0 como mínimo salvo que
    los datos empiecen por encima de 5/6 del máximo. Comprobado con los gráficos de prueba."""
    if not valores:
        return None
    dmin, dmax = min(valores), max(valores)
    rango = (dmax - dmin) or abs(dmax) or 1
    base = math.floor(math.log10(rango / 20))
    candidatos = [unidad] if unidad else [k * 10 ** e for e in range(base, base + 5) for k in (1, 2, 5)]
    for u in sorted(set(candidatos)):
        if minimo is not None:
            amin = minimo
        elif dmin >= 0 and dmin < dmax * 5 / 6:
            amin = 0
        else:
            amin = math.floor((dmin - 0.05 * rango) / u) * u if dmin < 0 else math.floor(dmin / u) * u
        amax = maximo if maximo is not None else math.ceil((dmax + 0.05 * rango) / u - 1e-9) * u
        if maximo is not None and minimo is None:
            # Con el máximo fijo y el mínimo automático, Excel baja el mínimo para que los saltos acaben justo en el
            # máximo (máximo 130 con saltos de 20: de −10 a 130; G_IA2025_1.1)
            tramos = math.ceil((amax - amin) / u - 1e-9)
            amin = amax - tramos * u
        if unidad or (amax - amin) / u <= 9 + 1e-9:
            return amin, amax, u
    return None


def avisos_escala(xml, h, ide, datos, todos, fmin, fmax, unidad):
    """Avisos de la escala de un eje de valores visible que hacen el gráfico más pequeño de lo que podría ser
    (petición del usuario, 2026-11-27, G_MemoriaSupervision_2.6): tramos vacíos, solo un extremo fijado o el eje sin
    los datos (que van en un eje oculto de otra escala)."""
    avisos = []
    c = lambda x: cifra(round(x, 2)).replace(".", ",").replace("-", "−")
    # El eje que se ve no tiene datos: las series van en un eje oculto con otra escala (2.6 a)
    if not datos.get(ide):
        for e2 in re.finditer(r'<c:valAx>.*?</c:valAx>', xml, re.S):
            h2 = hijos(e2.group(0))
            o = valor(hijo(h2, "axId"))
            if o == ide or valor(hijo(h2, "delete")) != "1" or not datos.get(o):
                continue
            if valor(hijo(h2, "axPos")) in ("b", "t") or valor(hijo(h, "axPos")) in ("b", "t"):
                continue
            esc2 = hijos(hijo(h2, "scaling") or "<c:scaling></c:scaling>")
            n2 = lambda n: float(valor(hijo(esc2, n))) if hijo(esc2, n) else None
            u2 = float(valor(hijo(h2, "majorUnit"))) if hijo(h2, "majorUnit") else None
            oculto = escala_eje(datos[o], n2("min"), n2("max"), u2)
            visible = escala_eje(datos[o], fmin, fmax, unidad)
            if oculto and visible and (abs(oculto[0] - visible[0]) > 1e-9 or abs(oculto[1] - visible[1]) > 1e-9):
                avisos.append(f"Aviso: el ⟪eje de valores que se ve no tiene datos⟫ ({c(visible[0])} a {c(visible[1])}): las "
                              f"series van en el eje oculto, de {c(oculto[0])} a {c(oculto[1])}; los números del eje no "
                              "corresponden a dónde se dibujan los datos: igualar las dos escalas a mano")
            break
        return avisos
    if not todos:
        return avisos
    # Solo un extremo fijado y el salto automático: el otro extremo y los saltos los elige Excel según el alto del
    # gráfico y pueden dejar tramos vacíos (2.6 b: mínimo −60 fijo; Excel puso saltos de 50 y llegó a 90 con los datos
    # en 49; el .ai, de −60 a 60 con saltos de 20)
    if (fmin is None) != (fmax is None) and unidad is None:
        justo = escala_eje(todos, fmin, fmax, None)
        # Con el extremo libre en 0 (datos de un solo signo) Excel lo pone ahí: no queda hueco
        libre = justo[1] if justo and fmin is not None else (justo[0] if justo else None)
        if justo and abs(libre) > 1e-12:
            fijo = f"el mínimo ({c(fmin)})" if fmin is not None else f"el máximo ({c(fmax)})"
            otro = "el máximo" if fmin is not None else "el mínimo"
            # La app la fija (decisión del usuario, 2026-11-27: mejor que solo avisar)
            avisos.append(("fijar", justo))
            avisos.append(f"Aviso: eje de valores ⟪fijado de {c(justo[0])} a {c(justo[1])} con saltos de {c(justo[2])}⟫: el "
                          f"autor solo fijó {fijo} y {otro} y los saltos los elegía Excel según el alto del gráfico, con "
                          f"tramos vacíos (los datos van de {c(min(todos))} a {c(max(todos))})")
            return avisos
    e = escala_eje(todos, fmin, fmax, unidad)
    if e:
        aviso = tramos_vacios(todos, *e, fmin is not None, fmax is not None)
        if aviso:
            avisos.append(aviso)
    return avisos


def tramos_vacios(valores, amin, amax, u, min_fijo, max_fijo):
    """Aviso si el mínimo o el máximo que fijó el autor deja al menos un tramo entero del eje sin datos (más allá del
    aire normal): el gráfico podría verse más grande (petición del usuario, 2026-11-27, G_MemoriaSupervision_2.6 b:
    mínimo −60 con el dato más bajo en −22,6). Solo avisa: a veces el autor iguala la escala de varios paneles."""
    if not valores or not u or not (min_fijo or max_fijo):
        return None
    dmin, dmax = min(valores), max(valores)
    if dmax - dmin < 1e-12:
        return None   # un solo valor: series auxiliares (la línea de ceros del 1.21), no datos
    # Lo que pondría Excel solo (con su propio salto)
    ideal = escala_eje(valores)
    c = lambda x: cifra(round(x, 2)).replace(".", ",").replace("-", "−")
    partes = []
    # Abajo: no cuenta el 0 con todos los datos positivos (la base del eje)
    # Los tramos, con el salto que pondría Excel solo (2.6 b: con el −60 del autor el salto es 20 y sobra uno de 10)
    if ideal:
        u = ideal[2]
    if min_fijo and not (amin == 0 and dmin >= 0) and ideal and ideal[0] - amin >= u - 1e-9:
        n = int((ideal[0] - amin) / u + 1e-9)
        partes.append(f"por abajo llega a {c(amin)} y el dato más bajo es {c(dmin)} ({n} tramo{'s' if n > 1 else ''} "
                      f"vacío{'s' if n > 1 else ''}: el mínimo podría ser {c(ideal[0])})")
    if max_fijo and not (amax == 0 and dmax <= 0) and ideal and amax - ideal[1] >= u - 1e-9:
        n = int((amax - ideal[1]) / u + 1e-9)
        partes.append(f"por arriba llega a {c(amax)} y el dato más alto es {c(dmax)} ({n} tramo{'s' if n > 1 else ''} "
                      f"vacío{'s' if n > 1 else ''}: el máximo podría ser {c(ideal[1])})")
    if not partes:
        return None
    return ("Aviso: el gráfico ⟪puede aumentar de tamaño⟫: el eje de valores " + "; ".join(partes) +
            ". Comprueba si el autor lo fijó para igualar la escala con otro panel")


def decimales(x):
    t = f"{abs(x):.6f}".rstrip("0")
    return len(t.split(".")[1]) if "." in t else 0


def formato_numeros(formato, amin, u):
    """Formato del eje según la guía: sin decimales si todos son ceros, uno si hay decimales y dos en las
    centésimas; con separador de miles. Respeta el % del autor. None si el formato es de fecha o con texto."""
    if re.search(r'"|[dmyhs@]', re.sub(r'\[[^\]]*\]', '', formato.lower())) and formato.lower() != "general":
        return None
    pct = "%" in formato
    f = 100 if pct else 1
    d = min(2, max(decimales(u * f), decimales(amin * f)))
    return "#,##0" + ("." + "0" * d if d else "") + ("%" if pct else "")


def poner_formato_celdas(estilos, hoja, refs, codigo):
    """Formato de número `codigo` a las celdas `refs` de la hoja: un formato propio (numFmt) y, por cada estilo
    de celda que usen, una copia con ese formato. Devuelve (estilos, hoja)."""
    codigo_xml = html.escape(codigo)
    m = re.search(rf'<numFmt numFmtId="(\d+)" formatCode="{re.escape(codigo_xml)}"/>', estilos)
    if m:
        num_id = int(m.group(1))
    else:
        num_id = max([int(i) for i in re.findall(r'<numFmt numFmtId="(\d+)"', estilos)] + [163]) + 1
        nuevo = f'<numFmt numFmtId="{num_id}" formatCode="{codigo_xml}"/>'
        if "<numFmts" in estilos:
            estilos = re.sub(r'(<numFmts\b[^>]*>)', lambda x: x.group(1) + nuevo, estilos, count=1)
            estilos = re.sub(r'<numFmts count="(\d+)"', lambda x: f'<numFmts count="{int(x.group(1)) + 1}"', estilos, count=1)
        else:
            estilos = re.sub(r'(<styleSheet\b[^>]*>)', lambda x: x.group(1) + f'<numFmts count="1">{nuevo}</numFmts>', estilos, count=1)
    bloque = re.search(r'<cellXfs\b[^>]*>(.*?)</cellXfs>', estilos, re.S)
    xfs = re.findall(r'<xf\b[^>]*/>|<xf\b[^>]*>.*?</xf>', bloque.group(1), re.S)
    copias, nuevos = {}, []
    for ref in refs:
        c = celda(hoja, ref)
        if not c:
            continue
        sm = re.search(r'\bs="(\d+)"', c.group(0)[:c.group(0).index(">")])
        s_viejo = int(sm.group(1)) if sm else 0
        if s_viejo not in copias:
            xf = xfs[s_viejo]
            xf = re.sub(r'\bnumFmtId="\d+"', f'numFmtId="{num_id}"', xf, count=1)
            xf = xf if "applyNumberFormat" in xf else xf.replace("<xf ", '<xf applyNumberFormat="1" ', 1)
            xf = re.sub(r'applyNumberFormat="\d"', 'applyNumberFormat="1"', xf)
            copias[s_viejo] = len(xfs) + len(nuevos)
            nuevos.append(xf)
        texto = c.group(0)
        if sm:
            texto = texto.replace(f's="{s_viejo}"', f's="{copias[s_viejo]}"', 1)
        else:
            texto = texto.replace(f'<c r="{ref}"', f'<c r="{ref}" s="{copias[s_viejo]}"', 1)
        hoja = hoja[:c.start()] + texto + hoja[c.end():]
    if nuevos:
        cuerpo = bloque.group(1) + "".join(nuevos)
        cabeza = re.sub(r'count="\d+"', f'count="{len(xfs) + len(nuevos)}"', re.match(r'<cellXfs\b[^>]*>', bloque.group(0)).group(0))
        estilos = estilos.replace(bloque.group(0), cabeza + cuerpo + "</cellXfs>", 1)
    return estilos, hoja


# ---- dirección de las etiquetas del eje horizontal

ROT_VERTICAL = "-5400000"   # girar 270°: se lee de abajo arriba


def partir_en(texto, k, medir, sz):
    """El texto en k líneas (por palabras) con la línea más larga lo más corta posible."""
    palabras = texto.split()
    if k <= 1 or len(palabras) < 2:
        return [texto]
    mejor = None

    def probar(resto, k, hechas):
        nonlocal mejor
        if k == 1:
            lineas = hechas + [" ".join(resto)]
            largo = max(medir(l, sz) for l in lineas)
            if mejor is None or largo < mejor[0]:
                mejor = (largo, lineas)
            return
        for i in range(1, len(resto) - k + 2):
            probar(resto[i:], k - 1, hechas + [" ".join(resto[:i])])
    probar(palabras, min(k, len(palabras)), [])
    return mejor[1]


def es_vertical(eje):
    return bool(re.search(rf'<a:bodyPr\b[^>]*\brot="{ROT_VERTICAL}"', eje)) or 'vert="vert270"' in eje


def poner_rotacion(eje, rot):
    """La rotación del texto del eje (en su txPr): 0 horizontal o vertical de abajo arriba."""
    def body(m):
        b = re.sub(r'\s+(rot|vert)="[^"]*"', "", m.group(0))
        return b.replace("<a:bodyPr", f'<a:bodyPr rot="{rot}" vert="horz"', 1)
    if "<c:txPr>" in eje:
        return re.sub(r'<a:bodyPr\b[^>]*?/?>', body, eje, count=1)
    return eje


MESES_EJE = {"es": ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"],
             "en": ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]}
# Saltos «redondos» entre etiquetas verticales: meses (trimestre, semestre, año), años y el resto
SALTOS_EJE = {"months": [1, 3, 6, 12], "years": [1, 2, 5, 10], None: [1, 2, 3, 4, 5, 6, 10, 12, 20, 25, 50]}


def textos_eje_numerico(xml, texto_eje):
    """Los textos de un eje de categorías de fechas o números, como los escribe su formato (para medirlos)."""
    cat = re.search(r'<c:cat>.*?</c:cat>', xml, re.S)
    nf = re.search(r'<c:numFmt formatCode="([^"]*)"', texto_eje)
    codigo = html.unescape(nf.group(1)) if nf else ""
    if (not nf or 'sourceLinked="1"' in nf.group(0)) and cat:
        cache = re.search(r'<c:formatCode>([^<]*)</c:formatCode>', cat.group(0))
        codigo = html.unescape(cache.group(1)) if cache else codigo
    limpio = re.sub(r'\[[^\]]*\]|"[^"]*"', "", codigo.lower())
    if "mmm" in limpio:
        idioma = "en" if "10409" in codigo else "es"
        return [m + ("-00" if "y" in limpio else "") for m in MESES_EJE[idioma]] + (["sept-00"] if idioma == "es" else [])
    if "y" in limpio and "m" not in limpio and "d" not in limpio:
        return ["2000" if "yyy" in limpio else "00"]
    # Números: como los escribe el formato del eje («#,##0» → «-43», «3.100»), no el valor en bruto (1.8, 2.4)
    primera = re.sub(r'"[^"]*"|\[[^\]]*\]', "", codigo.split(";")[0])
    decimales = len(re.search(r'\.(0+)', primera).group(1)) if re.search(r'\.(0+)', primera) else (
        None if "general" in primera.lower() or not primera else 0)

    def escrito(v):
        if decimales is None:
            return cifra(round(v, 2)).replace(".", ",")
        t = f"{v:,.{decimales}f}" if "," in primera else f"{v:.{decimales}f}"
        return t.replace(",", " ").replace(".", ",").replace(" ", ".")
    return ([escrito(v) for v in numeros(cat.group(0))] if cat else []) or ["0000"]


def direccion_fechas(xml, eje, trazado, medir):
    """Etiquetas de fechas o números en el eje horizontal (guía, pág. 11): nunca en oblicuo. En horizontal si caben
    todas; si no, verticales de abajo arriba y, si el autor no fijó el salto, una cada 3 meses, 6, 12… (la menor
    que deja aire entre ellas; en el .ai del G_IA2025_1.31, una por trimestre). Devuelve el xml y una nota."""
    texto_eje = eje.group(0)
    tipo = eje.group(1)
    cat = re.search(r'<c:cat>.*?</c:cat>', xml, re.S)
    cuenta = re.search(r'<c:ptCount val="(\d+)"', cat.group(0)) if cat else None
    n = int(cuenta.group(1)) if cuenta else 0
    if n < 2:
        return xml, None
    sz = re.search(r'<a:defRPr\b[^>]*\bsz="(\d+)"', texto_eje)
    sz = int(sz.group(1)) / 100 if sz else 7
    muestras = textos_eje_numerico(xml, texto_eje)
    codigo = html.unescape(re.search(r'<c:numFmt formatCode="([^"]*)"', texto_eje).group(1)) \
        if re.search(r'<c:numFmt formatCode="', texto_eje) else ""
    limpio = re.sub(r'\[[^\]]*\]|"[^"]*"', "", codigo.lower())
    ancho = max(medir(t, sz) for t in muestras)
    hueco = trazado / n
    base = re.search(r'<c:baseTimeUnit val="(\w+)"/>', texto_eje)
    base = base.group(1) if base and tipo == "dateAx" else None
    unidad = re.search(r'<c:majorUnit val="([\d.]+)"/>', texto_eje)
    salto_lbl = re.search(r'<c:tickLblSkip val="(\d+)"/>', texto_eje)
    fijo = float(unidad.group(1)) if unidad and tipo == "dateAx" else (int(salto_lbl.group(1)) if salto_lbl else None)
    # Distancia entre etiquetas: en un eje de fechas, el salto va en días, meses o años, no en puntos (1.1 y 1.12:
    # datos diarios, una etiqueta cada 3 o 4 meses, en horizontal en el .ai)
    separacion = hueco * (fijo or 1)
    if tipo == "dateAx":
        dias = {"days": 1, "months": 30.44, "years": 365.25}
        fechas = numeros(cat.group(0))
        escala = re.search(r'<c:scaling>.*?</c:scaling>', texto_eje, re.S)
        lim = lambda n, defecto: float(re.search(rf'<c:{n} val="([\d.]+)"/>', escala.group(0)).group(1)) \
            if escala and re.search(rf'<c:{n} val="', escala.group(0)) else defecto
        inicio, fin = lim("min", min(fechas, default=0)), lim("max", max(fechas, default=0))
        tramo = max(fin - inicio, 1)
        unidad_base = dias.get(base or "days", 1)
        u_salto = re.search(r'<c:majorTimeUnit val="(\w+)"/>', texto_eje)
        if fijo:
            separacion = trazado * fijo * dias.get(u_salto.group(1), 1) / tramo if u_salto else None
        else:
            separacion = trazado * unidad_base / (tramo + unidad_base)
        hueco = trazado * unidad_base / (tramo + unidad_base)
        # Salto del autor sin unidad, o datos diarios sin salto: Excel elige qué fechas pone; en horizontal (sin
        # inclinar), como en el .ai del 1.1 y el 1.12
        if separacion is None or (not fijo and (base or "days") == "days"):
            separacion = float("inf")
    if ancho <= separacion - HOLGURA_PT:
        rot = rot_de(texto_eje)
        if rot == "0":
            return xml, None
        nota = "etiquetas del eje horizontal en horizontal (estaban giradas)" if rot else None
        return xml.replace(texto_eje, poner_rotacion(eje_con_txpr(texto_eje), "0"), 1), nota
    nuevo = poner_rotacion(eje_con_txpr(texto_eje), ROT_VERTICAL)
    nota = "etiquetas del eje horizontal en vertical, de abajo arriba (no caben en horizontal; nunca en oblicuo)"
    if not fijo:
        alto = sz * INTERLINEA * 1.2
        lista = SALTOS_EJE.get(base, SALTOS_EJE[None]) if tipo == "dateAx" else SALTOS_EJE[None]
        salto = next((k for k in lista if hueco * k >= alto), lista[-1])
        if salto > 1:
            h = hijos(nuevo)
            if tipo == "dateAx":
                poner(h, ORDEN_EJE["dateAx"], "majorUnit", f'<c:majorUnit val="{salto}"/>')
                if base:
                    poner(h, ORDEN_EJE["dateAx"], "majorTimeUnit", f'<c:majorTimeUnit val="{base}"/>')
            else:
                poner(h, ORDEN_EJE["catAx"], "tickLblSkip", f'<c:tickLblSkip val="{salto}"/>')
            nuevo = f"<c:{tipo}>" + "".join(t for _, t in h) + f"</c:{tipo}>"
            que = {"months": "meses", "years": "años"}.get(base, "categorías")
            nota += f", una cada {salto} {que}"
    return xml.replace(texto_eje, nuevo, 1), nota


def rot_de(eje):
    r = re.search(r'<a:bodyPr\b[^>]*\brot="(-?\d+)"', eje)
    return r.group(1) if r else None


def eje_con_txpr(eje):
    """El eje con txPr (sin él no hay dónde poner la rotación)."""
    if "<c:txPr>" in eje:
        return eje
    tipo = re.match(r'<c:(\w+)>', eje).group(1)
    h = hijos(eje)
    poner(h, ORDEN_EJE[tipo], "txPr", '<c:txPr><a:bodyPr/><a:lstStyle/><a:p><a:pPr><a:defRPr/></a:pPr>'
                                     '<a:endParaRPr lang="es-ES"/></a:p></c:txPr>')
    return f"<c:{tipo}>" + "".join(t for _, t in h) + f"</c:{tipo}>"


def direccion_categorias(z, xml, trazado, hojas, medir):
    """Etiquetas del eje horizontal (guía, pág. 11): horizontales si caben (nunca en oblicuo); si no caben ni a
    6 pt, verticales de abajo arriba y, si el hueco deja, en 2 o 3 líneas (saltos en las celdas). Devuelve el
    xml y una nota (o un aviso si no se puede sin cortar texto)."""
    # (también los ejes de fechas: el 1.31 panel b salía en oblicuo)
    eje = next((e for e in re.finditer(r'<c:(catAx|dateAx)>.*?</c:\1>', xml, re.S)
                if re.search(r'<c:axPos val="[bt]"/>', e.group(0)) and '<c:delete val="1"/>' not in e.group(0)), None)
    if not eje:
        return xml, None
    etiquetas = etiquetas_categorias(xml)
    rot = re.search(r'<a:bodyPr\b[^>]*\brot="(-?\d+)"', eje.group(0))
    if not etiquetas and medir and trazado:
        return direccion_fechas(xml, eje, trazado, medir)
    if not etiquetas or not medir:
        # Numéricas o fechas: Excel salta etiquetas si no caben; solo se quita la inclinación
        if rot and rot.group(1) not in ("0", ROT_VERTICAL):
            return xml.replace(eje.group(0), poner_rotacion(eje.group(0), "0"), 1), "etiquetas del eje horizontal sin inclinar"
        return xml, None
    hueco = trazado / len(etiquetas)
    palabras = [p for e in etiquetas for p in e.split()]
    larga = max(palabras, key=lambda p: medir(p, 6)) if palabras else ""
    # Primero en horizontal: Excel las deja enteras con unos 3 pt libres en el hueco (G_MemoriaSupervision_3.5:
    # «provisiones», 30,7 pt a 6 pt en 33,7, entra; venía en oblicuo y salía girada; en el .ai va en horizontal)
    if medir(larga, 6) <= hueco - HOLGURA_HORIZONTAL:
        if rot and rot.group(1) != "0":
            return xml.replace(eje.group(0), poner_rotacion(eje.group(0), "0"), 1), "etiquetas del eje horizontal en horizontal (estaban giradas)"
        # Explícito: así Excel no las inclina por su cuenta
        return xml.replace(eje.group(0), poner_rotacion(eje.group(0), "0"), 1), None
    # Verticales: cuántas líneas caben a lo ancho del hueco (7 pt; si no cabe ni una, 6 pt)
    sz = next((t for t in (7, 6) if hueco >= t * INTERLINEA), None)
    if sz is None:
        return xml, (f"Aviso: las etiquetas del eje horizontal no caben ni en horizontal ni en vertical a 6 pt "
                     f"(hueco de {hueco:.1f} pt por categoría): hay que resolverlo a mano").replace(".", ",")
    caben = min(3, int(hueco // (sz * INTERLINEA)))
    # Largo objetivo: el menor posible para la etiqueta más difícil; las demás solo se parten si pasan de ahí
    def mejor(e):
        return min(max(medir(l, sz) for l in partir_en(e, k, medir, sz)) for k in range(1, caben + 1))
    objetivo = max(mejor(e) for e in etiquetas)

    def partir(e):
        for k in range(1, caben + 1):
            lineas = partir_en(e.replace("\n", " "), k, medir, sz)
            if max(medir(l, sz) for l in lineas) <= objetivo + 0.01:
                return "\n".join(lineas)
        return e
    nuevo_eje = poner_rotacion(eje.group(0), ROT_VERTICAL)
    nuevo_eje = re.sub(r'(<c:txPr>.*?</c:txPr>)', lambda t: fijar_letra(t.group(1), sz * 100, ROBOTO), nuevo_eje, count=1, flags=re.S)
    xml = xml.replace(eje.group(0), nuevo_eje, 1)
    xml, partidas, formulas = cambiar_categorias(z, xml, hojas, partir)
    nota = (f"etiquetas del eje horizontal en vertical, de abajo arriba, a {sz} pt («{larga}» no cabe en horizontal ni "
            f"a 6 pt)" + (f"; en {caben} líneas como mucho: " + ", ".join(partidas) if partidas else ""))
    if formulas:
        nota += f" — Aviso: {formulas} etiqueta(s) salen de fórmulas: los saltos de línea solo quedan en su valor guardado"
    return xml, nota


def escala_visible(xml, eje, datos):
    """(mínimo, máximo, salto, formato) con los que se ve un eje de valores: lo fijado por el autor o lo de Excel."""
    h = hijos(eje)
    escala = hijos(hijo(h, "scaling") or "<c:scaling></c:scaling>")
    num = lambda n: float(valor(hijo(escala, n))) if hijo(escala, n) else None
    unidad = float(valor(hijo(h, "majorUnit"))) if hijo(h, "majorUnit") else None
    e = escala_eje(datos.get(valor(hijo(h, "axId")), []), num("min"), num("max"), unidad)
    nf = re.search(r'<c:numFmt formatCode="([^"]*)" sourceLinked="(\d)"/>', eje)
    if not nf or nf.group(2) == "1":
        ide = valor(hijo(h, "axId"))
        g = next((g.group(0) for g in GRUPOS.finditer(xml) if ide in re.findall(r'<c:axId val="(\d+)"/>', g.group(0))), "")
        cache = re.search(r'<c:val>.*?<c:formatCode>([^<]*)</c:formatCode>', g, re.S)
        codigo = html.unescape(cache.group(1)) if cache else "General"
    else:
        codigo = html.unescape(nf.group(1))
    return (e, codigo) if e else None


def quitar_eje_derecho_duplicado(xml):
    """Eje de valores de la derecha que es copia exacta del de la izquierda (misma escala, salto y formato): repite la
    información y en el .ai no está (G_IA2025_2.1, petición del usuario, 2026-11-26). Se borra, con su escala fijada
    igual que la del izquierdo para que sus series no se muevan. Devuelve el xml y un aviso."""
    ejes = [e.group(0) for e in re.finditer(r'<c:valAx>.*?</c:valAx>', xml, re.S)]
    visible = lambda e: '<c:delete val="1"/>' not in e and '<c:tickLblPos val="none"/>' not in e
    izq = next((e for e in ejes if '<c:axPos val="l"/>' in e and visible(e)), None)
    der = next((e for e in ejes if '<c:axPos val="r"/>' in e and visible(e)), None)
    if not izq or not der:
        return xml, None
    datos = valores_por_eje(xml)
    a, b = escala_visible(xml, izq, datos), escala_visible(xml, der, datos)
    if not a or not b:
        return xml, None
    # El salto automático depende del alto del gráfico y la estimación falla (2.1: Excel pone 0,1 en los dos): basta
    # con que coincidan mínimo, máximo y formato si el salto del derecho lo elige Excel
    (amin, amax, u), fa = a
    (bmin, bmax, v), fb = b
    salto_auto = "<c:majorUnit " not in der
    if (amin, amax, fa) != (bmin, bmax, fb) or (u != v and not salto_auto):
        return xml, None
    h = hijos(der)
    escala = hijos(hijo(h, "scaling") or "<c:scaling></c:scaling>")
    orientacion = hijo(escala, "orientation") or '<c:orientation val="minMax"/>'
    poner(h, ORDEN_EJE["valAx"], "scaling", f'<c:scaling>{orientacion}<c:max val="{cifra(amax)}"/>'
                                            f'<c:min val="{cifra(amin)}"/></c:scaling>')
    poner(h, ORDEN_EJE["valAx"], "delete", '<c:delete val="1"/>')
    poner(h, ORDEN_EJE["valAx"], "majorUnit", f'<c:majorUnit val="{cifra(u)}"/>')
    xml = xml.replace(der, "<c:valAx>" + "".join(t for _, t in h) + "</c:valAx>", 1)
    c = lambda x: cifra(x).replace(".", ",")
    return xml, (f"Aviso: el ⟪eje de la derecha⟫ era copia exacta del de la izquierda ({c(amin)} a {c(amax)}, "
                 f"saltos de {c(u)}): quitado, repite la información (en el .ai no está); sus series siguen con "
                 "la misma escala")


def ancho_numeros_derecha(xml, medir):
    """Lo que ocupan a la derecha del trazado los números de un eje de valores de la derecha que se vea (doble
    escala): el trazado se estrecha para que quepan dentro de la columna 1 (G_IA2025_2.1)."""
    datos = valores_por_eje(xml)
    for e in re.findall(r'<c:valAx>.*?</c:valAx>', xml, re.S):
        if '<c:axPos val="r"/>' not in e or '<c:delete val="1"/>' in e or '<c:tickLblPos val="none"/>' in e:
            continue
        vista = escala_visible(xml, e, datos)
        if not vista:
            return medir("100", 7) + 8
        (amin, amax, u), codigo = vista
        factor = factor_unidades(e)
        amin, amax, u = amin / factor, amax / factor, u / factor if u else u
        primera = re.sub(r'"[^"]*"|\[[^\]]*\]', "", codigo.split(";")[0])
        dec = len(re.search(r'\.(0+)', primera).group(1)) if re.search(r'\.(0+)', primera) else (
            max(0, -math.floor(math.log10(u))) if u and u < 1 else 0)
        textos = [f"{v:,.{dec}f}".replace(",", " ").replace(".", ",").replace(" ", ".") for v in (amin, amax)]
        return max(medir(t, 7) for t in textos) + 8
    return 0


def textos_especiales(z, xml, idioma, hojas, estilos, trazado, medir):
    """Reglas de las págs. 10 y 11 de la guía en un gráfico. Devuelve xml, estilos y las notas."""
    notas = []
    # Fechas del eje
    def fecha(m):
        eje = m.group(0)
        nf = re.search(r'<c:numFmt formatCode="([^"]*)" sourceLinked="(\d)"/>', eje)
        cat = re.search(r'<c:cat>.*?<c:formatCode>([^<]*)</c:formatCode>', xml, re.S)
        codigo = html.unescape(nf.group(1)) if nf and nf.group(2) == "0" else (html.unescape(cat.group(1)) if cat else "")
        limpio = re.sub(r'\[[^\]]*\]|"[^"]*"', "", codigo.lower())
        if not ("m" in limpio and ("y" in limpio or "d" in limpio)):
            return eje
        nuevo = FECHA_EJE["en" if idioma == "en" else "es"]
        if nf and html.unescape(nf.group(1)) == nuevo and nf.group(2) == "0":
            return eje
        notas.append(f"fechas del eje en {'inglés' if idioma == 'en' else 'español'} ({nuevo})")
        nuevo_nf = f'<c:numFmt formatCode="{html.escape(nuevo)}" sourceLinked="0"/>'
        h = hijos(eje)
        poner(h, ORDEN_EJE[m.group(1)], "numFmt", nuevo_nf)
        return f"<c:{m.group(1)}>" + "".join(t for _, t in h) + f"</c:{m.group(1)}>"
    xml = re.sub(r'<c:(catAx|dateAx)>.*?</c:\1>', fecha, xml, flags=re.S)
    # Septiembre: con el código de la guía, Excel para Mac escribe «sept» (los otros once meses, con 3 letras, y en
    # inglés todos); no hay código que lo evite, así que se avisa (petición del usuario, 2026-11-25)
    if idioma != "en" and re.search(r'<c:(?:catAx|dateAx)>(?:(?!</c:(?:catAx|dateAx)>).)*?formatCode="'
                                    + re.escape(html.escape(FECHA_EJE["es"])) + '"', xml, re.S):
        cat = re.search(r'<c:cat>.*?</c:cat>', xml, re.S)
        meses = set()
        for v in re.findall(r'<c:pt idx="\d+">\s*<c:v>([\d.]+)</c:v>', cat.group(0) if cat else ""):
            try:
                meses.add((datetime.date(1899, 12, 30) + datetime.timedelta(days=int(float(v)))).month)
            except (OverflowError, ValueError):
                pass
        if 9 in meses:
            notas.append("Aviso: el eje de fechas tiene septiembre y Excel para Mac lo escribe «⟪sept⟫» (la guía pide "
                         "3 letras, mmm-aa): si sale en el eje, hay que corregirlo a mano en el PDF")

    # Números de los ejes de valores
    datos = valores_por_eje(xml)
    def numeros(m):
        nonlocal estilos
        eje = m.group(0)
        h = hijos(eje)
        if valor(hijo(h, "delete")) == "1":
            return eje
        ide = valor(hijo(h, "axId"))
        escala = hijos(hijo(h, "scaling") or "<c:scaling></c:scaling>")
        num = lambda n: float(valor(hijo(escala, n))) if hijo(escala, n) else None
        unidad = float(valor(hijo(h, "majorUnit"))) if hijo(h, "majorUnit") else None
        # Con datos en un eje de valores oculto (el secundario borrado del 1.1 b, «China»), el visible los enseña
        # también: cuentan
        ocultos = [valor(re.search(r'<c:axId\b[^>]*/>', e2.group(0)).group(0)) for e2 in re.finditer(r'<c:valAx>.*?</c:valAx>', xml, re.S)
                   if '<c:delete val="1"/>' in e2.group(0)]
        todos = datos.get(ide, []) + [v for o in ocultos if o != ide for v in datos.get(o, [])]
        for av in avisos_escala(xml, h, ide, datos, todos, num("min"), num("max"), unidad):
            if isinstance(av, tuple):
                # Escala justa en un eje con un solo extremo fijado (G_MemoriaSupervision_2.6 b)
                jmin, jmax, ju = av[1]
                orientacion = hijo(escala, "orientation") or '<c:orientation val="minMax"/>'
                poner(h, ORDEN_EJE["valAx"], "scaling", f'<c:scaling>{orientacion}<c:max val="{cifra(jmax)}"/>'
                                                        f'<c:min val="{cifra(jmin)}"/></c:scaling>')
                poner(h, ORDEN_EJE["valAx"], "majorUnit", f'<c:majorUnit val="{cifra(ju)}"/>')
                eje = "<c:valAx>" + "".join(t for _, t in h) + "</c:valAx>"
                h = hijos(eje)
                escala = hijos(hijo(h, "scaling"))
                unidad = ju
            else:
                notas.append(av)
        e = escala_eje(datos.get(ide, []), num("min"), num("max"), unidad)
        if not e:
            return eje
        amin, amax, u = e
        nf = re.search(r'<c:numFmt formatCode="([^"]*)" sourceLinked="(\d)"/>', eje)
        enlazado = not nf or nf.group(2) == "1"
        actual = html.unescape(nf.group(1)) if nf else "General"
        if enlazado:
            cache = re.search(r'<c:val>.*?<c:formatCode>([^<]*)</c:formatCode>', xml, re.S)
            actual = html.unescape(cache.group(1)) if cache else "General"
        codigo = formato_numeros(actual, amin, u)
        if not codigo or codigo == actual:
            return eje
        texto_u = cifra(u).replace(".", ",")
        if enlazado:
            # Formato enlazado a los datos: se cambia en las celdas de las series de ese eje
            for g in GRUPOS.finditer(xml):
                if ide not in re.findall(r'<c:axId val="(\d+)"/>', g.group(0)):
                    continue
                for f in re.findall(r'<c:(?:val|yVal)>\s*<c:numRef>\s*<c:f>([^<]*)</c:f>', g.group(0)):
                    por_hoja = {}
                    for nombre, ref in celdas_de_rango(html.unescape(f)):
                        por_hoja.setdefault(nombre, []).append(ref)
                    for nombre, refs in por_hoja.items():
                        ruta_hoja = hoja_de(z, nombre)
                        hoja = hojas.get(ruta_hoja) or z.read(ruta_hoja).decode("utf-8")
                        estilos, hojas[ruta_hoja] = poner_formato_celdas(estilos, hoja, refs, codigo)
            notas.append(f"números del eje de valores {codigo} (saltos de {texto_u}; el eje toma el formato de los "
                         "datos: cambiado en sus celdas)")
            return eje
        poner(h, ORDEN_EJE[m.group(1)], "numFmt", f'<c:numFmt formatCode="{html.escape(codigo)}" sourceLinked="0"/>')
        notas.append(f"números del eje de valores {codigo} (saltos de {texto_u}; antes {actual})")
        return f"<c:{m.group(1)}>" + "".join(t for _, t in h) + f"</c:{m.group(1)}>"
    xml = re.sub(r'<c:(valAx)>.*?</c:\1>', numeros, xml, flags=re.S)
    xml, nota = quitar_eje_derecho_duplicado(xml)
    if nota:
        notas.append(nota)

    # Saltos de línea y espacios sobrantes al principio o al final de las categorías («Jefatura⏎ »): Excel los cuenta
    # como una línea más y corta la etiqueta («Jefatura…», G_MemoriaSupervision_1.1)
    xml, limpias, _ = cambiar_categorias(z, xml, hojas, lambda t: re.sub(r'^[\s\u00a0]+|[\s\u00a0]+$', "", t))
    if limpias:
        notas.append(f"Aviso: categorías con saltos de línea o espacios sobrantes al principio o al final, quitados "
                     f"(Excel las cortaba): " + ", ".join(limpias[:4]) + (" …" if len(limpias) > 4 else ""))
    # Trimestres en las categorías y en los títulos del gráfico
    xml, cambios, _ = cambiar_categorias(z, xml, hojas, lambda t: trimestres(t, idioma))
    if cambios:
        notas.append("trimestres en las categorías: " + ", ".join(cambios[:4]) + (" …" if len(cambios) > 4 else ""))
    xml, hechos = textos_trimestres(xml, idioma)
    if hechos:
        notas.append("trimestres: " + ", ".join(hechos[:4]))
    # Trimestres con el año solo en el primero: en dos niveles (año debajo, abarcando sus trimestres)
    xml, nota = trimestres_en_dos_niveles(z, xml, hojas)
    if nota:
        notas.append(nota)
    # Dirección de las etiquetas del eje horizontal
    xml, nota = direccion_categorias(z, xml, trazado, hojas, medir)
    if nota:
        notas.append(nota)
    return xml, estilos, notas


# ---------------------------------------------------------------- etiquetas de datos (guía, págs. 10 y 16)

# Hijos de las etiquetas de datos en el orden del esquema
ORDEN_DLBLS = ["dLbl", "delete", "numFmt", "spPr", "txPr", "dLblPos", "showLegendKey", "showVal", "showCatName",
               "showSerName", "showPercent", "showBubbleSize", "separator", "showLeaderLines", "leaderLines", "extLst"]
ORDEN_DLBL = ["idx", "delete", "layout", "tx", "numFmt", "spPr", "txPr", "dLblPos", "showLegendKey", "showVal",
              "showCatName", "showSerName", "showPercent", "showBubbleSize", "separator", "extLst"]
SEPARADOR_ETIQUETAS = ": "   # guía, pág. 16: texto y número separados por dos puntos y un espacio


def valores_con_etiqueta(ser, h):
    """{idx: valor} de los puntos de la serie que enseñan su valor en la etiqueta (`h`, los hijos de su dLbls)."""
    val = re.search(r'<c:(?:val|yVal)>.*?</c:(?:val|yVal)>', ser, re.S)
    if not val:
        return {}
    puntos = {int(i): float(v) for i, v in re.findall(r'<c:pt idx="(\d+)">\s*<c:v>(-?[\d.Ee+-]+)</c:v>', val.group(0))}
    todas = valor(hijo(h, "showVal")) == "1"
    sueltas = {int(valor(hijo(hijos(t), "idx"))): t for n, t in h if n == "dLbl"}
    con = {}
    for i, v in puntos.items():
        t = sueltas.get(i)
        if t is None:
            si = todas
        else:
            si = '<c:delete val="1"/>' not in t and ('showVal val="1"' in t or (todas and 'showVal val="0"' not in t))
        if si:
            con[i] = v
    return con


def eje_valores_de(xml, ser):
    """El eje de valores de la serie (su texto, o "")."""
    grupo = next((g.group(0) for g in GRUPOS.finditer(xml) if ser in g.group(0)), "")
    ids = re.findall(r'<c:axId val="(\d+)"/>', grupo)
    return next((e for e in re.findall(r'<c:valAx>.*?</c:valAx>', xml, re.S)
                 if re.search(r'<c:axId val="(\d+)"/>', e).group(1) in ids), "")


def decimal_cero(xml, ser, h):
    """(formato sin decimales, formato de antes, cifra de ejemplo) si las etiquetas de la serie llevan decimales y en
    todas sus cifras, como las escribe Excel (con las unidades del eje), salen 0 («3.817,0»); None si no."""
    nf = re.search(r'<c:numFmt formatCode="([^"]*)"', hijo(h, "numFmt") or "")
    if not nf:
        return None
    codigo = html.unescape(nf.group(1))
    limpio = re.sub(r'"[^"]*"|\[[^\]]*\]', "", codigo)
    dec = re.search(r'\.(0+)', limpio.split(";")[0])
    if not dec or re.search(r'[dmyhs@]', limpio, re.I):
        return None
    con = valores_con_etiqueta(ser, h)
    if not con:
        return None
    d = len(dec.group(1))
    f = 100 if "%" in limpio.split(";")[0] else 1
    vistos = [v * f / factor_unidades(eje_valores_de(xml, ser)) for v in con.values()]
    if any(abs(round(v, d) - round(v)) > 1e-9 for v in vistos):
        return None
    sin = re.sub(r'(0)\.0+', r'\1', codigo)
    if sin == codigo:
        return None
    ejemplo = max(vistos, key=abs)
    texto = f"{ejemplo:,.{d}f}".replace(",", " ").replace(".", ",").replace(" ", ".") + ("\u00a0%" if f == 100 else "")
    return sin, codigo, texto


def decimal_irrelevante(xml, ser, h, nombre):
    """(nombre, cifra de ejemplo, decimales) si las etiquetas de la serie llevan decimales y todas sus cifras pasan de la centena (como las escribe
    Excel, con las unidades del eje): el decimal no aporta nada (petición del usuario, 2026-11-27; 8.2: «9.725,4»).
    Solo avisa: los decimales los decide la guía."""
    nf = re.search(r'<c:numFmt formatCode="([^"]*)"', hijo(h, "numFmt") or "")
    codigo = html.unescape(nf.group(1)) if nf else ""
    primera = re.sub(r'"[^"]*"|\[[^\]]*\]', "", codigo.split(";")[0])
    dec = re.search(r'\.(0+)', primera)
    if not dec or "%" in primera:
        return None
    con = valores_con_etiqueta(ser, h)
    if not con:
        return None
    grupo = next((g.group(0) for g in GRUPOS.finditer(xml) if ser in g.group(0)), "")
    ids = re.findall(r'<c:axId val="(\d+)"/>', grupo)
    eje_v = next((e for e in re.findall(r'<c:valAx>.*?</c:valAx>', xml, re.S)
                  if re.search(r'<c:axId val="(\d+)"/>', e).group(1) in ids), "")
    vistos = [v / factor_unidades(eje_v) for v in con.values()]
    if min(abs(v) for v in vistos) < 100:
        return None
    d = len(dec.group(1))
    ejemplo = max(vistos, key=abs)
    texto = f"{ejemplo:,.{d}f}".replace(",", " ").replace(".", ",").replace(" ", ".")
    return nombre.strip(), texto, d


def decimales_etiquetas(valores, pct=False):
    """Decimales de las etiquetas según la guía (pág. 10): ninguno si todos son ceros, uno si los hay y dos
    si son centésimas (si con uno alguna cifra que no es cero se quedaría en 0,0)."""
    f = 100 if pct else 1
    vs = [v * f for v in valores]
    if all(abs(v - round(v)) < 1e-9 for v in vs):
        return 0
    if any(v and round(v, 1) == 0 for v in vs):
        return 2
    # Cifras distintas que con un decimal se escribirían igual (0,84 y 0,80 → 0,8): dos, para que se distingan
    # (G_IA2025_1.17, petición del usuario, 2026-11-26: el autor lo quería así)
    if len({round(v, 1) for v in vs}) < len({round(v, 2) for v in vs}):
        return 2
    return 1


RE_FORMA_ETIQUETA = re.compile(r'<(c|c15):spPr\b[^>]*>.*?</\1:spPr>', re.S)
RE_RELLENO = re.compile(r'<a:(solidFill|gradFill|pattFill|blipFill)\b.*?</a:\1>|<a:(solidFill|gradFill|pattFill|blipFill)\b[^>]*/>', re.S)


SIN_FONDO = '<c:spPr><a:noFill/><a:ln><a:noFill/></a:ln></c:spPr>'
ORDEN_DLBLS = ["dLbl", "delete", "numFmt", "spPr", "txPr", "dLblPos", "showLegendKey", "showVal", "showCatName",
               "showSerName", "showPercent", "showBubbleSize", "separator", "showLeaderLines", "leaderLines", "extLst"]
ORDEN_DLBL = ["idx", "delete", "layout", "tx", "numFmt", "spPr", "txPr", "dLblPos", "showLegendKey", "showVal",
              "showCatName", "showSerName", "showPercent", "showBubbleSize", "separator", "extLst"]
ORDEN_PLOTAREA_FIN = ["spPr", "extLst"]


def sin_relleno_ni_borde(sppr):
    """La misma forma (c:spPr o c15:spPr) sin relleno y sin borde, conservando lo demás (geometría, efectos).
    None si ya estaba así."""
    cuerpo = sppr[sppr.index(">") + 1:sppr.rindex("<")] if not sppr.endswith("/>") else ""
    borde = re.search(r'<a:ln\b[^>]*/>|<a:ln\b.*?</a:ln>', cuerpo, re.S)
    sin_ln = re.sub(r'<a:ln\b[^>]*/>|<a:ln\b.*?</a:ln>', "", cuerpo, flags=re.S)
    rellenos = list(RE_RELLENO.finditer(sin_ln))
    ya_sin_relleno = "<a:noFill/>" in sin_ln and not rellenos
    if ya_sin_relleno and borde and "<a:noFill/>" in borde.group(0):
        return None
    nuevo = RE_RELLENO.sub("", sin_ln).replace("<a:noFill/>", "")
    # El relleno va tras la geometría (xfrm, custGeom/prstGeom) y antes de la línea
    geo = list(re.finditer(r'<a:xfrm\b.*?</a:xfrm>|<a:(custGeom|prstGeom)\b.*?</a:\1>|<a:prstGeom\b[^>]*/>', nuevo, re.S))
    corte = geo[-1].end() if geo else 0
    nuevo = nuevo[:corte] + '<a:noFill/><a:ln><a:noFill/></a:ln>' + nuevo[corte:]
    apertura = sppr[:sppr.index(">") + 1].replace("/>", ">")
    cierre = re.match(r'<(\w+:spPr)', sppr).group(1)
    return f"{apertura}{nuevo}</{cierre}>"


def etiquetas_sin_marco(xml):
    """Etiquetas de datos sin borde ni fondo, en todas las publicaciones (petición del usuario, 2026-11-25: en el
    G_IA2025_1.1 el autor las puso en recuadros blancos con borde gris; en el .ai van sin nada). Se toca la forma
    de las etiquetas (c:spPr y la c15:spPr de las etiquetas con forma), no sus líneas guía. Si no tienen forma
    propia se les pone una sin relleno ni borde: con el estilo del gráfico restablecido, Excel les da fondo
    blanco y borde gris (G_IA2025_1.1 MODIFICADO, 2026-11-26). Devuelve (xml, cuántas formas se han cambiado)."""
    cuenta = 0

    def forma(m):
        nonlocal cuenta
        nueva = sin_relleno_ni_borde(m.group(0))
        if nueva is None:
            return m.group(0)
        cuenta += 1
        return nueva

    def con_forma(elemento, etiqueta, orden):
        """El dLbls o dLbl con su c:spPr (sin relleno ni borde) aunque no la tuviera; los borrados no."""
        nonlocal cuenta
        h = hijos(elemento)
        if valor(hijo(h, "delete")) in ("1", "true") or hijo(h, "spPr") is not None:
            return elemento
        apertura = elemento[:elemento.index(">") + 1]
        poner(h, orden, "spPr", SIN_FONDO)
        cuenta += 1
        return apertura + "".join(t for _, t in h) + f"</c:{etiqueta}>"

    def bloque(m):
        texto = m.group(0)
        # Las líneas guía (c:leaderLines, c15:leaderLines) no se tocan
        guias = []

        def guardar(g):
            guias.append(g.group(0))
            return f"\x00{len(guias) - 1}\x00"
        texto = re.sub(r'<(c|c15):leaderLines\b.*?</\1:leaderLines>', guardar, texto, flags=re.S)
        texto = RE_FORMA_ETIQUETA.sub(forma, texto)
        texto = re.sub(r'\x00(\d+)\x00', lambda g: guias[int(g.group(1))], texto)
        texto = re.sub(r'<c:dLbl>.*?</c:dLbl>', lambda d: con_forma(d.group(0), "dLbl", ORDEN_DLBL), texto, flags=re.S)
        return con_forma(texto, "dLbls", ORDEN_DLBLS)
    xml = re.sub(r'<c:dLbls>.*?</c:dLbls>', bloque, xml, flags=re.S)
    return xml, cuenta


def areas_sin_fondo(xml):
    """Área del gráfico y área de trazado sin relleno ni borde, en todas las publicaciones: escrito siempre, porque
    si no hay forma Excel pone la del estilo del gráfico (fondo blanco y borde gris con el estilo restablecido,
    G_IA2025_1.1 MODIFICADO, petición del usuario, 2026-11-26). Devuelve (xml, lista de lo cambiado)."""
    hechos = []
    m = re.search(r'</c:chart>(\s*<c:spPr\b.*?</c:spPr>|\s*<c:spPr/>)?', xml, re.S)
    if m:
        if m.group(1):
            nueva = sin_relleno_ni_borde(m.group(1).strip())
            if nueva:
                xml = xml[:m.start(1)] + nueva + xml[m.end(1):]
                hechos.append("área del gráfico")
        else:
            xml = xml[:m.end()] + SIN_FONDO + xml[m.end():]
            hechos.append("área del gráfico")
    pa = re.search(r'<c:plotArea>.*</c:plotArea>', xml, re.S)
    if pa:
        h = hijos(pa.group(0))
        actual = hijo(h, "spPr")
        nueva = SIN_FONDO if actual is None else sin_relleno_ni_borde(actual)
        if nueva:
            poner(h, ORDEN_PLOTAREA_FIN, "spPr", nueva)
            xml = xml.replace(pa.group(0), "<c:plotArea>" + "".join(t for _, t in h) + "</c:plotArea>", 1)
            hechos.append("área de trazado")
    return xml, hechos


def orto_texto(texto, idioma):
    """Las reglas de FUENTES para un texto suelto (etiquetas de datos, petición del usuario, 2026-11-25): en
    castellano comillas angulares («¨», «“», «"» de apertura → «; «”», «"» de cierre → ») y espacio de no separación
    entre cifra y %; en inglés, sin espacio; y sin espacios dobles."""
    if idioma == "es":
        salida, abierta = [], False
        for c in texto:
            if c in "“¨" or (c == '"' and not abierta):
                salida.append("«")
                abierta = True
            elif c == "”" or c == '"':
                salida.append("»")
                abierta = False
            else:
                salida.append(c)
        texto = re.sub(r"(\d)(?:[ \u202f]?)%", "\\1\u00a0%", "".join(salida))
    else:
        texto = re.sub(r"(\d)[ \u00a0\u202f]+%", r"\1%", texto)
    return re.sub(r"(?<=\S) {2,}(?=\S)", " ", texto)


def texto_de_etiqueta(texto, idioma):
    """El texto de una etiqueta de datos: en minúscula si viene entero en mayúsculas (las reglas de las leyendas), con
    coma decimal en castellano («(29.0%)» → «(29,0 %)») y las reglas de FUENTES (G_IA2025_1.31, petición del usuario,
    2026-11-26)."""
    texto = en_minuscula(texto, idioma)
    if idioma != "en":
        # Punto decimal: no el de millares (tres cifras detrás)
        texto = re.sub(r'(?<![\d.,])(\d+)\.(\d{1,2}|\d{4,})(?![\d.,])', r'\1,\2', texto)
    return orto_texto(texto, idioma)


def etiquetas_ortotipografia(z, xml, hojas, idioma):
    """Las reglas de FUENTES (`orto_texto`) en el texto de las etiquetas de datos: el escrito en la etiqueta y el que
    sale de un rango de celdas («Valor de las celdas»: en la caché y en sus celdas, porque Excel lo repone de ellas).
    Devuelve (xml, cambios)."""
    hechos = []

    def t(m):
        antes = html.unescape(m.group(2))
        nuevo = texto_de_etiqueta(antes, idioma)
        if nuevo != antes:
            hechos.append(f"«{antes.strip()[:30]}» → «{nuevo.strip()[:30]}»")
        return m.group(1) + html.escape(nuevo, quote=False) + m.group(3)

    def etiquetas(m):
        return re.sub(r'(<c:tx>\s*<c:rich>.*?</c:rich>)', lambda r: re.sub(r'(<a:t>)([^<]*)(</a:t>)', t, r.group(1)),
                      m.group(0), flags=re.S)
    xml = re.sub(r'<c:dLbls>.*?</c:dLbls>', etiquetas, xml, flags=re.S)
    # Rangos de celdas de las etiquetas
    compartidos = None
    for rango in re.findall(r'<c15:datalabelsRange>.*?</c15:datalabelsRange>', xml, re.S):
        f = re.search(r'<c15:f>([^<]*)</c15:f>', rango)
        cambios = {}

        def punto(m):
            antes = html.unescape(m.group(3))
            nuevo = texto_de_etiqueta(antes, idioma)
            if nuevo != antes:
                cambios[int(m.group(1))] = (antes, nuevo)
                hechos.append(f"«{antes.strip()[:30]}» → «{nuevo.strip()[:30]}»")
            return m.group(2) + html.escape(nuevo, quote=False) + m.group(4)
        nuevo_rango = re.sub(r'<c:pt idx="(\d+)">(\s*<c:v>)([^<]*)(</c:v>)',
                             lambda m: f'<c:pt idx="{m.group(1)}">' + punto(m), rango)
        if not cambios:
            continue
        xml = xml.replace(rango, nuevo_rango, 1)
        if not f:
            continue
        if compartidos is None:
            compartidos = textos_compartidos(z)
        celdas = list(celdas_de_rango(html.unescape(f.group(1))))
        for k, (antes, nuevo) in cambios.items():
            if k >= len(celdas):
                continue
            nombre, ref = celdas[k]
            try:
                ruta_hoja = hoja_de(z, nombre)
            except Fallo:
                continue
            hoja = hojas.get(ruta_hoja) or z.read(ruta_hoja).decode("utf-8")
            c = celda(hoja, ref)
            if c and texto_de_celda(c, compartidos) == antes:
                hojas[ruta_hoja] = poner_texto_celda(hoja, c, nuevo)
    return xml, hechos


def etiquetas_que_caben(xml, W, H, medir):
    """Las etiquetas de datos con texto propio y tamaño fijo (c15:layout con w y h) en las que el texto ya no cabe
    con la letra que tienen (Excel lo corta con «…»): se deja el ancho del autor (o el de la palabra más larga) y
    crece el alto hasta que caben todas las líneas. W y H: tamaño del gráfico en pt. Devuelve (xml, cuántas)."""
    cuenta = 0

    def etiqueta(m):
        nonlocal cuenta
        e = m.group(0)
        tam = re.search(r'<c15:layout>\s*<c:manualLayout>(.*?)</c:manualLayout>', e, re.S)
        rico = re.search(r'<c:tx>\s*<c:rich>.*?</c:rich>', e, re.S)
        if not tam or not rico or "<c:delete val=\"1\"/>" in e:
            return e
        wv, hv = re.search(r'<c:w val="([^"]+)"', tam.group(1)), re.search(r'<c:h val="([^"]+)"', tam.group(1))
        texto = html.unescape("".join(re.findall(r'<a:t>([^<]*)</a:t>', rico.group(0)))).strip()
        if not wv or not hv or not texto or "[" in texto:
            return e
        szs = re.findall(r'\bsz="(\d+)"', rico.group(0))
        sz = (int(szs[0]) if szs else 600) / 100
        cuerpo = re.search(r'<a:bodyPr\b[^>]*>', rico.group(0))
        cuerpo = cuerpo.group(0) if cuerpo else ""

        def ins(nombre, defecto):
            v = re.search(rf'\b{nombre}="(\d+)"', cuerpo)
            return (int(v.group(1)) if v else defecto) / EMU_PT
        li, ri, ti, bi = ins("lIns", 91440), ins("rIns", 91440), ins("tIns", 45720), ins("bIns", 45720)
        ancho = float(wv.group(1)) * W
        alto = float(hv.group(1)) * H
        util = ancho - li - ri
        mayor = max(medir(p, sz) for p in texto.split())
        if mayor > util:
            util = mayor + 1
            ancho = util + li + ri
        lineas = len(partir_lineas(texto, util, sz, medir))
        necesario = lineas * sz * INTERLINEA + ti + bi + 1
        if necesario <= alto and ancho == float(wv.group(1)) * W:
            return e
        cuenta += 1
        nuevo = tam.group(1).replace(wv.group(0), f'<c:w val="{ancho / W:.6f}"').replace(
            hv.group(0), f'<c:h val="{max(alto, necesario) / H:.6f}"')
        return e.replace(tam.group(1), nuevo, 1)
    return re.sub(r'<c:dLbl>.*?</c:dLbl>', etiqueta, xml, flags=re.S), cuenta


def etiquetas_datos(xml):
    """Etiquetas de datos de las series: decimales de la guía (pág. 10: los mismos que en los ejes) y, si
    llevan texto y número, separados por «: » (pág. 16). Devuelve el xml y las notas."""
    notas, sobran = [], []

    def mostrar(h, nombre):
        return valor(hijo(h, nombre)) == "1"

    # Los valores con etiqueta de todo el gráfico (el panel): las cifras de series distintas que se confundirían con
    # un decimal también cuentan (G_IA2025_3.6, panel a: 0,885 y 0,933 → 0,9 y 0,9)
    del_panel = []
    for s_ in re.findall(r'<c:ser>.*?</c:ser>', xml, re.S):
        d_ = re.search(r'<c:dLbls>.*?</c:dLbls>', s_, re.S)
        v_ = re.search(r'<c:(?:val|yVal)>.*?</c:(?:val|yVal)>', s_, re.S)
        if d_ and v_ and 'showVal val="1"' in d_.group(0):
            del_panel += numeros(v_.group(0))

    def separador(h, orden, texto_extra):
        texto = mostrar(h, "showCatName") or mostrar(h, "showSerName") or texto_extra
        numero = mostrar(h, "showVal") or mostrar(h, "showPercent")
        if texto and numero and hijo(h, "separator") != f"<c:separator>{SEPARADOR_ETIQUETAS}</c:separator>":
            poner(h, orden, "separator", f"<c:separator>{SEPARADOR_ETIQUETAS}</c:separator>")
            return True
        return False

    def serie(m):
        ser = m.group(0)
        dl = re.search(r'<c:dLbls>.*?</c:dLbls>', ser, re.S)
        if not dl:
            return ser
        nombre = nombre_serie(ser)
        h = hijos(dl.group(0))
        rango = 'showDataLabelsRange val="1"' in dl.group(0)
        cambios = []
        # El formato con el que el autor veía las etiquetas (el suyo o, enlazado, el de los datos)
        nf_autor = re.search(r'<c:numFmt formatCode="([^"]*)" sourceLinked="(\d)"/>', hijo(h, "numFmt") or "")
        if nf_autor and nf_autor.group(2) == "0":
            formato_autor = html.unescape(nf_autor.group(1))
        else:
            cache_a = re.search(r'<c:(?:val|yVal)>.*?<c:formatCode>([^<]*)</c:formatCode>', ser, re.S)
            formato_autor = html.unescape(cache_a.group(1)) if cache_a else "General"
        # Separador, en el conjunto y en las etiquetas sueltas
        if separador(h, ORDEN_DLBLS, rango):
            cambios.append(f"separador «{SEPARADOR_ETIQUETAS.strip()} »")
        for e in h:
            if e[0] == "dLbl":
                hl = hijos(e[1])
                if separador(hl, ORDEN_DLBL, rango):
                    e[1] = "<c:dLbl>" + "".join(t for _, t in hl) + "</c:dLbl>"
                    if not any(c.startswith("separador") for c in cambios):
                        cambios.append(f"separador «{SEPARADOR_ETIQUETAS.strip()} »")
        # Decimales (si muestran el valor y el formato es de números)
        val = re.search(r'<c:(?:val|yVal)>.*?</c:(?:val|yVal)>', ser, re.S)
        valores = numeros(val.group(0)) if val else []
        if (mostrar(h, "showVal") or any(e[0] == "dLbl" and 'showVal val="1"' in e[1] for e in h)) and valores:
            nf = re.search(r'<c:numFmt formatCode="([^"]*)" sourceLinked="(\d)"/>', hijo(h, "numFmt") or "")
            if nf and nf.group(2) == "0":
                actual = html.unescape(nf.group(1))
            else:
                cache = val and re.search(r'<c:formatCode>([^<]*)</c:formatCode>', val.group(0))
                actual = html.unescape(cache.group(1)) if cache else "General"
            limpio = re.sub(r'\[[^\]]*\]', '', actual.lower())
            if actual.lower() == "general" or not re.search(r'"|[dmyhs@]', limpio):
                pct = "%" in limpio
                d = max(decimales_etiquetas(valores, pct), decimales_etiquetas(del_panel, pct) if del_panel else 0)
                codigo = "#,##0" + ("." + "0" * d if d else "") + ("%" if pct else "")
                if codigo != actual or not nf or nf.group(2) != "0":
                    nuevo = f'<c:numFmt formatCode="{html.escape(codigo)}" sourceLinked="0"/>'
                    poner(h, ORDEN_DLBLS, "numFmt", nuevo)
                    for e in h:
                        if e[0] == "dLbl" and "<c:numFmt " in e[1]:
                            e[1] = re.sub(r'<c:numFmt [^>]*/>', nuevo, e[1], count=1)
                        elif e[0] == "dLbl" and 'showVal val="1"' in e[1] and '<c:delete val="1"/>' not in e[1] \
                                and "<c:tx>" not in e[1]:
                            # Etiqueta suelta con formato propio pero sin formato de número: Excel la escribía con
                            # todos sus decimales (0,933 en el 3.6)
                            hl = hijos(e[1])
                            poner(hl, ORDEN_DLBL, "numFmt", nuevo)
                            e[1] = "<c:dLbl>" + "".join(t for _, t in hl) + "</c:dLbl>"
                    if codigo != actual:
                        cambios.append(f"{codigo} (antes {actual})")
        # Decimales que salen 0 en todas las cifras de la serie («130,0», «3.817,0»): fuera, con aviso (petición del
        # usuario, 2026-11-27)
        cero = decimal_cero(xml, ser, h)
        if cero:
            codigo_sin, antes_c, ejemplo = cero
            nuevo = f'<c:numFmt formatCode="{html.escape(codigo_sin)}" sourceLinked="0"/>'
            poner(h, ORDEN_DLBLS, "numFmt", nuevo)
            for e in h:
                if e[0] == "dLbl" and "<c:numFmt " in e[1]:
                    e[1] = re.sub(r'<c:numFmt [^>]*/>', nuevo, e[1], count=1)
            # Si así queda como lo tenía el autor (la guía le había puesto el decimal), ni cambio ni aviso
            cambios = [c for c in cambios if not c.startswith(f"{antes_c} (antes ")]
            if codigo_sin != formato_autor:
                cambios.append(f"{codigo_sin} (antes {formato_autor})")
                notas.append(f"Aviso: etiquetas de «{nombre.strip()}»: el decimal salía 0 en todas sus cifras («{ejemplo}»): "
                             f"quitado ({antes_c} → {codigo_sin})")
        sobra = decimal_irrelevante(xml, ser, h, nombre)
        if sobra:
            sobran.append(sobra)
        if not cambios:
            return ser
        notas.append(f"etiquetas de «{nombre}»: " + ", ".join(cambios))
        return ser.replace(dl.group(0), "<c:dLbls>" + "".join(t for _, t in h) + "</c:dLbls>", 1)

    xml = re.sub(r'<c:ser>.*?</c:ser>', serie, xml, flags=re.S)
    if sobran:
        # Un aviso por panel con todas sus series (8.1: eran 13 avisos)
        varios = max(d for _, _, d in sobran) > 1
        notas.append("Aviso: etiquetas de " + ", ".join(f"«{n}» («{t}»)" for n, t, _ in sobran)
                     + f": todas sus cifras pasan de 100 y llevan decimal{'es' if varios else ''}, que no aporta"
                     + f"{'n' if varios else ''} nada; ¿quitarlo{'s' if varios else ''}?")
    return xml, notas


# ---------------------------------------------------------------- gráficos de tarta (guía, págs. 16 y 17)

RE_TARTA = re.compile(r'<c:(pieChart|pie3DChart|doughnutChart|ofPieChart)>')
HUECO_ANILLO = 80   # guía, pág. 17: tamaño del agujero del anillo
# Líneas de serie del subgráfico circular: blanco matiz 5 (color de los ejes), 1 pt, remate plano y ángulo
LINEA_SUBGRAFICO = ('<a:ln w="12700" cap="flat"><a:solidFill><a:srgbClr val="FFFFFF"><a:lumMod val="50000"/>'
                    '</a:srgbClr></a:solidFill><a:miter lim="800000"/></a:ln>')
CUERPO_ETIQUETA_TARTA = 6
ETIQUETA_TARTA = CUERPO_ETIQUETA_TARTA * INTERLINEA + 4   # lo que ocupan por fuera las etiquetas (pt)
AIRE_SOBRE_ETIQUETAS = 1 * MM   # de la pastilla o el título del panel a lo más alto de las etiquetas
AIRE_ANILLO_ETIQUETA = 2       # del anillo a la etiqueta (pt)
FILAS_BAJADA_TARTA = 2       # lo más que baja una tarta para que quepan sus etiquetas (filas de la retícula)
LEJOS_DE_SU_PORCION = 4      # a partir de aquí (pt) la etiqueta lleva línea guía
# Líneas guía de las etiquetas: blanco matiz 5, 0,5 pt (guía, pág. 16)
# (Nombre propio: más abajo hay otra LINEA_GUIA, sin xmlns, que la pisaba y dejaba la capa de formas sin el
# prefijo «a» declarado: XML mal formado en los pasos 2 y 3 de los anillos)
LINEA_GUIA_CAPA = ('<a:ln xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" w="6350" cap="flat"><a:solidFill>'
                   '<a:srgbClr val="FFFFFF"><a:lumMod val="50000"/></a:srgbClr></a:solidFill><a:miter lim="800000"/></a:ln>')
SEPARACION_ETIQUETAS = 1.5   # aire mínimo entre los textos de dos etiquetas (pt)
GIRO_MAXIMO_ETIQUETA = 30    # lo más que se gira una etiqueta a lo largo del anillo para no chocar (grados)


def es_tarta(xml):
    return bool(RE_TARTA.search(xml))


def sin_porcentaje(codigo):
    """El formato de las etiquetas sin el %: «#,##0%» → «#,##0», «0.0%» → «#,##0.0»."""
    d = re.search(r'\.(0+)', codigo)
    return "#,##0" + ("." + d.group(1) if d else "")


def etiquetas_con_porcentaje(xml):
    """¿Alguna serie enseña sus valores con formato de porcentaje (el de sus etiquetas o, si va enlazado, el de sus
    datos)?"""
    for ser in re.findall(r'<c:ser>.*?</c:ser>', xml, re.S):
        dl = re.search(r'<c:dLbls>.*?</c:dLbls>', ser, re.S)
        if not dl or '<c:showVal val="1"/>' not in dl.group(0):
            continue
        nf = re.search(r'<c:numFmt formatCode="([^"]*)" sourceLinked="(\d)"/>', re.sub(r'<c:dLbl>.*?</c:dLbl>', "", dl.group(0), flags=re.S))
        if nf and nf.group(2) == "0":
            codigo = html.unescape(nf.group(1))
        else:
            cache = re.search(r'<c:val>.*?<c:formatCode>([^<]*)</c:formatCode>', ser, re.S)
            codigo = html.unescape(cache.group(1)) if cache else ""
        if "%" in re.sub(r'"[^"]*"|\\%', "", codigo):
            return True
    return False


def tarta_paso1(z, xml, hojas, estilos):
    """Tartas en el paso 1: anillo al 80 %, líneas del subgráfico y etiquetas sin «%» (los datos de la hoja se
    multiplican por 100, si no son fórmulas). Devuelve xml, estilos, notas y si se ha quitado el %."""
    notas, quitado = [], False
    if "<c:doughnutChart>" in xml:
        hueco = re.search(r'<c:holeSize val="(\d+)"/>', xml)
        if not hueco or hueco.group(1) != str(HUECO_ANILLO):
            xml = (xml.replace(hueco.group(0), f'<c:holeSize val="{HUECO_ANILLO}"/>') if hueco else
                   xml.replace("</c:doughnutChart>", f'<c:holeSize val="{HUECO_ANILLO}"/></c:doughnutChart>', 1))
            notas.append(f"agujero del anillo al {HUECO_ANILLO} %")
    if "<c:ofPieChart>" in xml:
        lineas = f"<c:serLines><c:spPr>{LINEA_SUBGRAFICO}</c:spPr></c:serLines>"
        if "<c:serLines" in xml:
            xml = re.sub(r'<c:serLines\s*/>|<c:serLines>.*?</c:serLines>', lineas, xml, flags=re.S)
        else:
            xml = re.sub(r'(</c:ofPieChart>)', lineas + r'\1', xml, count=1) if "<c:extLst>" not in \
                re.search(r'<c:ofPieChart>.*?</c:ofPieChart>', xml, re.S).group(0) else xml
        notas.append("líneas del subgráfico: blanco matiz 5, 1 pt, remate plano y unión en ángulo")
    # Etiquetas con %: se quita y los datos pasan a 0-100
    grupo = RE_TARTA.search(xml)
    ser = re.search(r'<c:ser>.*?</c:ser>', xml[grupo.start():], re.S)
    if not ser:
        return xml, estilos, notas, quitado
    ser = ser.group(0)
    formatos = re.findall(r'<c:numFmt formatCode="([^"]*)" sourceLinked="0"/>', re.search(r'<c:dLbls>.*?</c:dLbls>', ser, re.S).group(0)) \
        if "<c:dLbls>" in ser else []
    if not any("%" in re.sub(r'"[^"]*"', "", html.unescape(f)) for f in formatos):
        return xml, estilos, notas, quitado
    # Etiquetas con %: en todos los gráficos circulares (decisión del usuario, 2026-11-26, G_IA2025_1.9; sustituye a
    # la de pasar los datos a 0-100): los datos del autor no se tocan, las etiquetas se quedan con su %, «%» como
    # unidad (quitado = True) y aviso para quitar el % de las cifras en Illustrator
    return xml, estilos, notas + ["Aviso: eliminar el «⟪%⟫» de las cifras en Illustrator (gráfico circular: los datos "
                                  "del autor no se tocan; «%» como unidad)"], True


# Texto del centro de una tarta, como en el TERMINADO del 2.3: la cifra en Roboto Black 24 pt (negrita) y el
# texto en Roboto Regular 7 pt, centrado; el cuadro sin relleno ni borde
CIFRA_CENTRO_TARTA = ("Roboto Black", 2400, True)
TEXTO_CENTRO_TARTA = (ROBOTO, 700, False)
# Para que lo que se ve quede en el centro: la línea de la cifra (24 pt) deja sobre los números más hueco
# (ascendente − altura de las cifras, 0,928 − 0,711 del cuerpo) que la del texto (7 pt) bajo su línea de base
# (descendente, 0,244): el cuadro sube la mitad de la diferencia (≈ 1,75 pt; medido en Excel, 5 px a 2200)
SUBIDA_CENTRO_TARTA = (24 * (0.928 - 0.711) - 7 * 0.244) / 2


A_NS = ' xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"'


def partes_centro_tarta(texto):
    """(cifra, texto) del centro de una tarta: la cifra del principio («135», «4,5», «9.140») y lo que sigue, en una
    línea («Total», «billones de euros»). Sin cifra al principio: (None, texto)."""
    t = re.sub(r'\s+', " ", html.unescape(texto)).strip()
    m = re.match(r'([\d][\d.,]*)\s*(.*)$', t)
    return (m.group(1), m.group(2).strip()) if m else (None, t)


def cuerpo_centro_tarta(texto, ns, con_ns_a=False):
    """El txBody del texto del centro de una tarta (petición del usuario, 2026-11-27, todas las publicaciones): la
    cifra en Roboto Black 24 pt y, debajo, el texto en Roboto Regular 7 pt; las dos líneas centradas; la caja sin
    márgenes ni ajuste, con el texto en su centro. `ns`: «xdr» (hoja) o «cdr» (dentro del gráfico)."""
    cifra, resto = partes_centro_tarta(texto)
    na = A_NS if con_ns_a else ""

    def parrafo(t, fuente, sz, negrita):
        return (f'<a:p{na}><a:pPr algn="ctr"/><a:r><a:rPr lang="es-ES" sz="{sz}" b="{1 if negrita else 0}">'
                f'<a:solidFill><a:srgbClr val="000000"/></a:solidFill><a:latin typeface="{fuente}"/>'
                f'<a:ea typeface="{fuente}"/></a:rPr><a:t>{html.escape(t, quote=False)}</a:t></a:r></a:p>')
    cuerpo = (parrafo(cifra, *CIFRA_CENTRO_TARTA) if cifra else "") + (parrafo(resto, *TEXTO_CENTRO_TARTA) if resto else "")
    return (f'<{ns}:txBody><a:bodyPr{na} wrap="none" lIns="0" tIns="0" rIns="0" bIns="0" anchor="ctr" anchorCtr="0" '
            f'rtlCol="0"/><a:lstStyle{na}/>{cuerpo}</{ns}:txBody>')


def medidas_centro_tarta(texto, medir):
    """Ancho y alto (pt) del texto del centro de una tarta."""
    cifra, resto = partes_centro_tarta(texto)
    ancho = max([medir(cifra, 24) if cifra and medir else 0, medir(resto, 7) if resto and medir else 0] + [10]) + 4
    alto = (24 * INTERLINEA if cifra else 0) + (7 * INTERLINEA if resto else 0)
    return ancho, alto


def texto_centro_tarta(ancla):
    def letra(rpr, fuente, sz, negrita):
        cuerpo = re.search(r'<a:rPr\b([^>]*?)(/>|>(.*?)</a:rPr>)', rpr, re.S) if rpr else None
        atributos = cuerpo.group(1) if cuerpo else ' lang="es-ES"'
        dentro = (cuerpo.group(3) or "") if cuerpo else ""
        atributos = re.sub(r'\s(sz|b)="[^"]*"', "", atributos) + f' sz="{sz}" b="{1 if negrita else 0}"'
        dentro = re.sub(r'<a:(latin|ea|cs)\b[^>]*/>', "", dentro)
        sigue = re.search(r'<a:(sym|hlinkClick|hlinkMouseOver|rtl|extLst)\b', dentro)
        pos = sigue.start() if sigue else len(dentro)
        dentro = dentro[:pos] + f'<a:latin typeface="{fuente}"/><a:ea typeface="{fuente}"/>' + dentro[pos:]
        return f"<a:rPr{atributos}>{dentro}</a:rPr>"

    def run(m):
        texto = html.unescape(m.group(3))
        if not texto.strip():
            return m.group(0)
        estilo = CIFRA_CENTRO_TARTA if re.fullmatch(r'\s*[\d.,]+\s*', texto) else TEXTO_CENTRO_TARTA
        return f"<a:r>{letra(m.group(1), *estilo)}{m.group(2)}{m.group(3)}</a:t></a:r>"
    ancla = RUN.sub(run, ancla)
    # Sin relleno ni borde (como en el TERMINADO)
    def forma(m):
        sppr = re.sub(r'<a:(solidFill|gradFill|pattFill|blipFill|grpFill)\b.*?</a:\1>|<a:noFill/>', "", m.group(0), flags=re.S)
        sppr = re.sub(r'<a:ln\b[^>]*/>|<a:ln\b.*?</a:ln>', "", sppr, flags=re.S)
        geom = re.search(r'</a:prstGeom>|<a:prstGeom\b[^>]*/>|</a:custGeom>', sppr)
        pos = geom.end() if geom else sppr.index(">") + 1
        return sppr[:pos] + '<a:noFill/><a:ln><a:noFill/></a:ln>' + sppr[pos:]
    ancla = re.sub(r'<xdr:spPr\b.*?</xdr:spPr>', forma, ancla, count=1, flags=re.S)
    # Centrado
    return re.sub(r'<a:p>(?!<a:pPr)', '<a:p><a:pPr algn="ctr"/>', re.sub(
        r'<a:pPr\b([^>]*?)(/?>)', lambda m: "<a:pPr" + re.sub(r'\salgn="\w+"', "", m.group(1)) + ' algn="ctr"' + m.group(2), ancla))


def anclas_unidad_porcentaje(caja_graf, sig):
    """Cuadro de texto «%» (unidades) arriba a la izquierda del gráfico; «Tamaño y colocación» lo pone en su
    sitio."""
    x, y = caja_graf[0] + 72000, caja_graf[1] + 36000
    cx, cy = 180000, 160000
    return (f'<xdr:absoluteAnchor><xdr:pos x="{x}" y="{y}"/><xdr:ext cx="{cx}" cy="{cy}"/>'
            f'<xdr:sp macro="" textlink=""><xdr:nvSpPr><xdr:cNvPr id="{sig}" name="Unidades %"/><xdr:cNvSpPr txBox="1"/>'
            f'</xdr:nvSpPr><xdr:spPr><a:xfrm><a:off x="{x}" y="{y}"/><a:ext cx="{cx}" cy="{cy}"/></a:xfrm>'
            '<a:prstGeom prst="rect"><a:avLst/></a:prstGeom><a:noFill/></xdr:spPr><xdr:txBody>'
            '<a:bodyPr wrap="none" lIns="0" tIns="0" rIns="0" bIns="0" anchor="t"/><a:lstStyle/><a:p><a:r>'
            f'<a:rPr lang="es-ES" sz="{CUERPO_UNIDADES * 100}" b="0"><a:solidFill><a:srgbClr val="000000"/></a:solidFill>'
            f'<a:latin typeface="{ROBOTO}"/><a:ea typeface="{ROBOTO}"/></a:rPr><a:t>%</a:t></a:r></a:p></xdr:txBody></xdr:sp>'
            '<xdr:clientData/></xdr:absoluteAnchor>')


def texto_etiqueta(v, codigo):
    pct = "%" in codigo
    d = re.search(r'\.(0+)', codigo)
    t = f"{v * (100 if pct else 1):,.{len(d.group(1)) if d else 0}f}".replace(",", " ").replace(".", ",").replace(" ", ".")
    return t + ("%" if pct else "")


def etiquetas_tarta(xml, ancho, alto, dentro, medir, limite_x=None):
    """Etiquetas de datos fuera de la tarta (guía, pág. 17). Tarta: posición «extremo externo». Anillo (Excel no
    la tiene): cada etiqueta, a mano, justo por fuera del anillo en la mitad de su porción, y las que chocan se
    apartan solas. Devuelve el xml, las notas (aviso si alguna no cabe) y las líneas guía que hacen falta (de la
    etiqueta a su porción, en pt dentro del marco del gráfico) para las que quedan lejos de su porción."""
    if re.search(r'<c:(pieChart|pie3DChart)>', xml):
        def fuera(m):
            d = re.sub(r'<c:dLbl>.*?</c:dLbl>', '', m.group(0), flags=re.S)
            d = re.sub(r'<c:dLblPos val="\w+"/>', '', d)
            return re.sub(r'(<c:showLegendKey\b)', r'<c:dLblPos val="outEnd"/>\1', d, count=1)
        return re.sub(r'<c:dLbls>.*?</c:dLbls>', fuera, xml, count=1, flags=re.S), [], []
    if "<c:doughnutChart>" not in xml:
        return xml, [], []
    grupo = re.search(r'<c:doughnutChart>.*?</c:doughnutChart>', xml, re.S).group(0)
    ser = re.search(r'<c:ser>.*?</c:ser>', grupo, re.S)
    dl = ser and re.search(r'<c:dLbls>.*?</c:dLbls>', ser.group(0), re.S)
    if not dl:
        return xml, [], []
    valores = {int(i): float(v) for i, v in re.findall(r'<c:pt idx="(\d+)"[^>]*>\s*<c:v>([^<]*)</c:v>',
                                                      re.search(r'<c:val>.*?</c:val>', ser.group(0), re.S).group(0))}
    total = sum(v for v in valores.values() if v > 0)
    if not total:
        return xml, [], []
    a0 = float((re.search(r'<c:firstSliceAng val="(\d+)"/>', grupo) or re.match("()", "")).group(1) or 0)
    hueco = float((re.search(r'<c:holeSize val="(\d+)"/>', grupo) or re.match("()", "")).group(1) or 50) / 100
    x, y, d, _ = dentro
    R, cx, cy = d / 2, x + d / 2, y + d / 2
    medio = R * (1 + hueco) / 2      # Excel pone la etiqueta en el medio del anillo
    nf = re.search(r'<c:numFmt formatCode="([^"]*)"', dl.group(0))
    codigo = html.unescape(nf.group(1)) if nf else "General"
    banderas = "".join(re.findall(r'<c:show\w+ val="\d"/>', re.sub(r'<c:dLbl>.*?</c:dLbl>', '', dl.group(0), flags=re.S)))
    # Cada etiqueta, justo por fuera del anillo a la mitad de su porción; si choca con otra, busca el sitio libre
    # más cercano girando a lo largo del anillo o separándose un poco de él, sin salir del marco ni pasar a la
    # columna de la leyenda (el anillo no se toca: sigue con sus 9 filas)
    # Porciones separadas del anillo por el autor («explosión», % del radio): salen hacia fuera y la etiqueta
    # va por fuera de ellas
    sin_puntos = re.sub(r'<c:dPt>.*?</c:dPt>', '', ser.group(0), flags=re.S)
    separada_serie = float((re.search(r'<c:explosion val="(\d+)"/>', sin_puntos) or re.match("()", "")).group(1) or 0)
    separadas = {int(i): float(e) for i, e in re.findall(r'<c:dPt><c:idx val="(\d+)"/>(?:(?!</c:dPt>).)*?'
                                                        r'<c:explosion val="(\d+)"/>', ser.group(0), re.S)}
    porciones, acum = [], 0.0
    for i in sorted(valores):
        v = valores[i]
        if v <= 0:
            continue
        ini, fin = a0 + 360 * acum / total, a0 + 360 * (acum + v) / total
        acum += v
        porciones.append((i, v, (ini + fin) / 2, (fin - ini) / 2, medir(texto_etiqueta(v, codigo), CUERPO_ETIQUETA_TARTA),
                          R * separadas.get(i, separada_serie) / 100))
    alto_txt = CUERPO_ETIQUETA_TARTA * INTERLINEA
    h = alto_txt + 3                       # márgenes internos de la etiqueta de Excel (1,5 pt arriba y abajo)
    techo = limite_x if limite_x else ancho

    # Forma real de cada porción (con su separación) para saber dónde queda libre
    formas = []
    for i, v, medio_ang, mitad, wt, fr in porciones:
        r = math.radians(medio_ang)
        formas.append((medio_ang - mitad, medio_ang + mitad, cx + fr * math.sin(r), cy - fr * math.cos(r)))
    r_dentro, r_fuera = R * hueco - AIRE_ANILLO_ETIQUETA, R + AIRE_ANILLO_ETIQUETA

    def en_anillo(x, y):
        for ini, fin, ox, oy in formas:
            dx, dy = x - ox, y - oy
            rho = math.hypot(dx, dy)
            if not r_dentro <= rho <= r_fuera:
                continue
            ang_p = math.degrees(math.atan2(dx, -dy))
            holgura = math.degrees(AIRE_ANILLO_ETIQUETA / max(rho, 1))
            if (ang_p - (ini - holgura)) % 360 <= (fin - ini) + 2 * holgura:
                return True
        return False

    def toca_anillo(c):
        x0, y0, x1, y1 = c[0] - 1.5, c[1] - 1, c[2] + 1.5, c[3] + 1
        puntos = [(x0 + (x1 - x0) * f, y) for f in (0, .2, .4, .6, .8, 1) for y in (y0, y1)]
        puntos += [(x, y0 + (y1 - y0) * f) for f in (.33, .67) for x in (x0, x1)] + [((x0 + x1) / 2, (y0 + y1) / 2)]
        return any(en_anillo(x, y) for x, y in puntos)

    def chocan(c, o):
        return (c[0] < o[2] + SEPARACION_ETIQUETAS and o[0] < c[2] + SEPARACION_ETIQUETAS and
                c[1] < o[3] + SEPARACION_ETIQUETAS and o[1] < c[3] + SEPARACION_ETIQUETAS)

    cache = {}

    def sitio(k, grados):
        """La etiqueta k, en la dirección «grados» desde el centro: el primer sitio libre por fuera del anillo
        (si llega al borde del marco, se queda pegada a él, como hace Excel)."""
        clave = (k, round(grados * 4))
        if clave in cache:
            return cache[clave]
        wt = porciones[k][4]
        w = wt + 6                         # márgenes internos (3 pt a cada lado)
        a = math.radians(grados)
        res = None
        r = R * 0.95
        while r < R * 1.9:
            px = min(max(cx + r * math.sin(a), w / 2), techo - w / 2)
            py = min(max(cy - r * math.cos(a), h / 2), alto - h / 2)
            c = (px - wt / 2, py - alto_txt / 2, px + wt / 2, py + alto_txt / 2)
            if not toca_anillo(c):
                res = (px, py, c)
                break
            r += 1
        cache[clave] = res
        return res

    # Se empujan poco a poco las que chocan (cada una hacia su lado, sin cruzarse), sin girar más de
    # GIRO_MAXIMO_ETIQUETA; si en su dirección no hay sitio, giran hacia donde lo haya
    ang = [p[2] for p in porciones]
    n_et, paso = len(porciones), 0.5

    def girar(k, d):
        nuevo = ang[k] + d
        if abs(nuevo - porciones[k][2]) > GIRO_MAXIMO_ETIQUETA:
            return False
        if n_et > 1:
            antes, despues = ang[k - 1] - (360 if k == 0 else 0), ang[(k + 1) % n_et] + (360 if k == n_et - 1 else 0)
            if not antes < nuevo < despues:
                return False
        ang[k] = nuevo
        return True

    def libre(k):
        return sitio(k, ang[k]) is not None

    for k in range(n_et):
        if not libre(k):
            for d in range(1, int(GIRO_MAXIMO_ETIQUETA / paso) + 1):
                if sitio(k, porciones[k][2] + d * paso):
                    ang[k] = porciones[k][2] + d * paso
                    break
                if sitio(k, porciones[k][2] - d * paso):
                    ang[k] = porciones[k][2] - d * paso
                    break

    for _ in range(600):
        movido = False
        for k in range(n_et if n_et > 2 else n_et - 1):
            j = (k + 1) % n_et
            sk, sj = sitio(k, ang[k]), sitio(j, ang[j])
            if sk and sj and chocan(sk[2], sj[2]):
                guarda = ang[k], ang[j]
                a1 = girar(k, -paso) and libre(k) or (ang.__setitem__(k, guarda[0]) or False)
                a2 = girar(j, paso) and libre(j) or (ang.__setitem__(j, guarda[1]) or False)
                if a1 or a2:
                    movido = True
                    if not a1 and girar(j, paso) and not libre(j):
                        ang[j] -= paso
                    if not a2 and girar(k, -paso) and not libre(k):
                        ang[k] += paso
        if not movido:
            break

    nuevos, cajas, movidas = {}, [], []
    sin_sitio = 0
    for k, (i, v, medio_ang, mitad, wt, fr) in enumerate(porciones):
        st = sitio(k, ang[k])
        if not st:
            sin_sitio += 1
            ang[k] = medio_ang
            st = sitio(k, medio_ang) or (cx + (R + fr + 8) * math.sin(math.radians(medio_ang)),
                                         cy - (R + fr + 8) * math.cos(math.radians(medio_ang)), (0, 0, 0, 0))
        px, py, c = st
        cajas.append(c)
        if abs(ang[k] - medio_ang) > 0.5:
            movidas.append(i)
        # Desplazamiento desde la posición de Excel (el medio del anillo a la mitad de la porción)
        bx, by = (cx + (medio + fr) * math.sin(math.radians(medio_ang)),
                  cy - (medio + fr) * math.cos(math.radians(medio_ang)))
        nuevos[i] = (f'<c:layout><c:manualLayout><c:x val="{(px - bx) / ancho:.6f}"/><c:y val="{(py - by) / alto:.6f}"/>'
                     '</c:manualLayout></c:layout>')
    sin_sitio += len({k for k in range(len(cajas)) for j in range(len(cajas)) if k != j and chocan(cajas[k], cajas[j])})
    bloque = dl.group(0)
    for i, lay in nuevos.items():
        actual = re.search(rf'<c:dLbl><c:idx val="{i}"/>.*?</c:dLbl>', bloque, re.S)
        if actual:
            cuerpo = re.sub(r'<c:layout>.*?</c:layout>|<c:layout/>', '', actual.group(0), count=1, flags=re.S)
            cuerpo = cuerpo.replace(f'<c:idx val="{i}"/>', f'<c:idx val="{i}"/>' + lay, 1)
            bloque = bloque.replace(actual.group(0), cuerpo, 1)
        else:
            primera = re.search(r'<c:dLbl>', bloque)
            nuevo = f'<c:dLbl><c:idx val="{i}"/>{lay}{banderas}</c:dLbl>'
            pos = primera.start() if primera else len("<c:dLbls>")
            bloque = bloque[:pos] + nuevo + bloque[pos:]
    xml = xml.replace(dl.group(0), bloque, 1)
    # Línea guía si la etiqueta queda lejos de su porción o más cerca de otra
    def distancia(c, f):
        """Lo más cerca que queda la caja c de la porción f, y ese punto de la porción."""
        ini, fin, ox, oy = formas[f]
        mejor = (1e9, None)
        for paso_a in range(13):
            r_a = math.radians(ini + (fin - ini) * paso_a / 12)
            for rr in (R * hueco, (R * hueco + R) / 2, R):
                x, y = ox + rr * math.sin(r_a), oy - rr * math.cos(r_a)
                mejor = min(mejor, (math.hypot(max(c[0] - x, 0, x - c[2]), max(c[1] - y, 0, y - c[3])), (x, y)))
        return mejor

    guias = []
    for k, (i, v, medio_ang, mitad, wt, fr) in enumerate(porciones):
        if i not in movidas:
            continue
        c = cajas[k]
        propia, (tx, ty) = distancia(c, k)
        if propia > LEJOS_DE_SU_PORCION or any(distancia(c, f)[0] < propia - 0.5 for f in range(n_et) if f != k):
            sx, sy = min(max(tx, c[0] - 1), c[2] + 1), min(max(ty, c[1] - 1), c[3] + 1)
            guias.append((sx, sy, tx, ty))
    notas = []
    if movidas:
        notas.append(f"{len(movidas)} etiqueta(s) apartada(s) para que no se solapen"
                     + (f", {len(guias)} con línea guía (blanco matiz 5, 0,5 pt; guía, pág. 16): comprueba que se entiende"
                        if guias else ""))
    if sin_sitio:
        notas.append(f"Aviso: {sin_sitio} etiqueta(s) no caben sin solaparse: hay que separarlas a mano y ponerles "
                     "líneas guía (blanco matiz 5, 0,5 pt; guía, pág. 16)")
    return xml, notas, guias


def linea_guia_grafico(x0, y0, x1, y1, ancho, alto, ident):
    """Línea guía de una etiqueta dentro del gráfico (capa de formas del gráfico: se mueve con él). Coordenadas
    en pt dentro del marco."""
    fx, tx, fy, ty = min(x0, x1) / ancho, max(x0, x1) / ancho, min(y0, y1) / alto, max(y0, y1) / alto
    giro = ' flipH="1"' if (x1 - x0) * (y1 - y0) < 0 else ""
    return ('<cdr:relSizeAnchor xmlns:cdr="http://schemas.openxmlformats.org/drawingml/2006/chartDrawing">'
            f'<cdr:from><cdr:x>{fx:.5f}</cdr:x><cdr:y>{fy:.5f}</cdr:y></cdr:from>'
            f'<cdr:to><cdr:x>{tx:.5f}</cdr:x><cdr:y>{ty:.5f}</cdr:y></cdr:to>'
            f'<cdr:cxnSp macro=""><cdr:nvCxnSpPr><cdr:cNvPr id="{ident}" name="Línea guía {ident}"/><cdr:cNvCxnSpPr/>'
            '</cdr:nvCxnSpPr><cdr:spPr><a:xfrm xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"'
            f'{giro}><a:off x="0" y="0"/><a:ext cx="{round(abs(x1 - x0) * EMU_PT)}" cy="{round(abs(y1 - y0) * EMU_PT)}"/>'
            '</a:xfrm><a:prstGeom xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" prst="line">'
            '<a:avLst/></a:prstGeom>' + LINEA_GUIA_CAPA + '</cdr:spPr></cdr:cxnSp></cdr:relSizeAnchor>')


# ---------------------------------------------------------------- línea base

# «Base 100 = III TR 2007», «100 = tipo de cambio…», «… = 100»: las unidades indican un dato de referencia
RE_BASE = re.compile(r'(?<![\d.,])(100|50)\s*=|=\s*(100|50)(?![\d.,])|\bbase\s*(100|50)\b', re.I)
# Gris como los ejes (blanco matiz 5, el del TERMINADO), 0,5 pt, remate plano y unión en ángulo
LINEA_BASE = LINEA_EJE


def columna_num(letras):
    n = 0
    for c in letras:
        n = n * 26 + ord(c) - 64
    return n


def columna_letras(n):
    letras = ""
    while n:
        n, r = divmod(n - 1, 26)
        letras = chr(65 + r) + letras
    return letras


def poner_columna(hoja, col, fila1, valores):
    """Escribe los valores (números) en la columna `col` desde la fila `fila1` de la hoja. La columna está libre
    (detrás de la última usada): cada celda va al final de su fila."""
    for k, v in enumerate(valores):
        r = fila1 + k
        celda = f'<c r="{col}{r}"><v>{cifra(v)}</v></c>'
        fila = re.search(rf'<row\b(?=[^>]*\br="{r}")[^>]*?(/>|>.*?</row>)', hoja, re.S)
        if fila:
            texto = fila.group(0)
            if texto.endswith("/>"):
                nuevo = texto[:-2] + ">" + celda + "</row>"
            else:
                nuevo = texto[:-len("</row>")] + celda + "</row>"
            # spans («1:21») es una pista para Excel: se amplía hasta la columna nueva
            nuevo = re.sub(r'\bspans="(\d+):(\d+)"', lambda m: f'spans="{m.group(1)}:{max(int(m.group(2)), columna_num(col))}"',
                           nuevo, count=1)
            hoja = hoja[:fila.start()] + nuevo + hoja[fila.end():]
        else:
            # Fila nueva, en su sitio (las filas van en orden)
            siguiente = next((m for m in re.finditer(r'<row\b[^>]*\br="(\d+)"', hoja) if int(m.group(1)) > r), None)
            pos = siguiente.start() if siguiente else hoja.index("</sheetData>")
            hoja = hoja[:pos] + f'<row r="{r}">{celda}</row>' + hoja[pos:]
    hoja = re.sub(r'<sheetData/>', '<sheetData></sheetData>', hoja)
    dim = re.search(r'<dimension ref="([A-Z]+)(\d+)(?::([A-Z]+)(\d+))?"/>', hoja)
    if dim:
        c2, r2 = dim.group(3) or dim.group(1), int(dim.group(4) or dim.group(2))
        c2 = col if columna_num(col) > columna_num(c2) else c2
        hoja = hoja.replace(dim.group(0), f'<dimension ref="{dim.group(1)}{dim.group(2)}:{c2}{max(r2, fila1 + len(valores) - 1)}"/>')
    return hoja


def ultima_columna(hoja):
    return max([columna_num(c) for c in re.findall(r'<c r="([A-Z]+)\d+"', hoja)] or [0])


def ultima_fila_con_datos(hoja, col, fila1, fila2):
    filas = [int(r) for r, c in re.findall(rf'<c r="{col}(\d+)"[^>]*?(?:/>|>(.*?)</c>)', hoja, re.S)
             if c and '<v>' in c and fila1 <= int(r) <= fila2]
    return max(filas) if filas else None


def orden_leyenda(xml):
    """Las series en el orden de la leyenda: por grupos y, dentro de cada grupo, como van escritas en el gráfico
    (no por su «order»: en el G_IA2025_1.33 panel a no coinciden y Excel sigue el orden escrito: «CLU-manufacturas»
    antes que «Bienes intermedios», order 1 y 0). El idx de <c:legendEntry> es la posición en esta lista, no el
    idx de la serie."""
    lista = []
    for g in GRUPOS.finditer(xml):
        lista += re.findall(r'<c:ser>.*?</c:ser>', g.group(0), re.S)
    return lista


def es_constante_base(ser, bases=(100, 50), xml=None):
    """¿Serie con todos sus valores iguales a 100 o 50 (una línea de referencia dibujada como serie)? Con `xml`, solo
    si ese valor cae entre los datos de las demás series (en el 2.5, «linea_100» es un auxiliar del autor fuera del eje,
    que va de -4 a 6: no se ve y no es una línea base)."""
    val = re.search(r'<c:val>.*?</c:val>', ser, re.S)
    vals = numeros(val.group(0)) if val else []
    if len(vals) < 2:
        return False
    base = next((b for b in bases if all(abs(v - b) < 1e-9 for v in vals)), None)
    if base is None:
        return False
    if xml is None:
        return True
    otros = [v for t in re.findall(r'<c:ser>.*?</c:ser>', xml, re.S) if t != ser
             for v in numeros((re.search(r'<c:(?:val|yVal)>.*?</c:(?:val|yVal)>', t, re.S) or re.match("", "")).group(0))]
    if not otros:
        return False
    lo, hi = min(otros), max(otros)
    margen = (hi - lo) * 0.1
    return lo - margen <= base <= hi + margen


def linea_base_del_autor(xml, base):
    """Una serie de líneas del autor con todos sus valores iguales a `base`: la convierte en la línea base de la app
    (nombre «Base N», gris de los ejes, sin marcadores, oculta en la leyenda). Devuelve el xml y su nombre (o None)."""
    for g in GRUPOS.finditer(xml):
        if g.group(1) not in ("lineChart", "line3DChart"):
            continue
        for ser in re.findall(r'<c:ser>.*?</c:ser>', g.group(0), re.S):
            if not es_constante_base(ser, (base,), xml):
                continue
            nombre = nombre_serie(ser)
            h = hijos(ser)
            poner(h, ORDEN_SERIE["lineChart"], "tx", f'<c:tx><c:v>Base {base}</c:v></c:tx>')
            poner(h, ORDEN_SERIE["lineChart"], "spPr", f'<c:spPr>{LINEA_BASE}</c:spPr>')
            poner(h, ORDEN_SERIE["lineChart"], "marker", '<c:marker><c:symbol val="none"/></c:marker>')
            poner(h, ORDEN_SERIE["lineChart"], "dLbls", None)
            nueva = "<c:ser>" + "".join(t for _, t in h) + "</c:ser>"
            xml = xml.replace(ser, nueva, 1)
            pos = next(k for k, t in enumerate(orden_leyenda(xml)) if t == nueva)
            if not re.search(rf'<c:legendEntry><c:idx val="{pos}"/><c:delete val="1"/>', xml):
                entrada = f'<c:legendEntry><c:idx val="{pos}"/><c:delete val="1"/></c:legendEntry>'
                if re.search(r'<c:legendPos\b[^>]*/>', xml):
                    xml = re.sub(r'(<c:legend>\s*<c:legendPos\b[^>]*/>)', lambda m: m.group(1) + entrada, xml, count=1)
                else:
                    xml = xml.replace("<c:legend>", "<c:legend>" + entrada, 1)
            return xml, nombre
    return xml, None


def anadir_linea_base(xml, base, ref, n, idx):
    """La serie de la línea base (`ref`, n puntos) en el grupo de líneas de los ejes principales (o en uno
    nuevo sobre ellos), sin marcadores y oculta en la leyenda."""
    ejes = {valor(hijo(h, "axId")): (e.group(1), h) for e in EJES.finditer(xml) for h in [hijos(e.group(0))]}
    principal = next((i for i, (t, h) in ejes.items() if t == "valAx" and valor(hijo(h, "delete")) != "1"
                      and valor(hijo(h, "axPos")) == "l"), None) \
        or next((i for i, (t, h) in ejes.items() if t == "valAx" and valor(hijo(h, "delete")) != "1"), None)
    if principal is None:
        return None
    par = {principal, valor(hijo(ejes[principal][1], "crossAx"))}
    puntos = "".join(f'<c:pt idx="{k}"><c:v>{cifra(base)}</c:v></c:pt>' for k in range(n))
    serie = (f'<c:ser><c:idx val="{idx}"/><c:order val="{idx}"/><c:tx><c:v>Base {base}</c:v></c:tx>'
             f'<c:spPr>{LINEA_BASE}</c:spPr><c:marker><c:symbol val="none"/></c:marker>'
             f'<c:val><c:numRef><c:f>{ref}</c:f><c:numCache><c:formatCode>General</c:formatCode>'
             f'<c:ptCount val="{n}"/>{puntos}</c:numCache></c:numRef></c:val><c:smooth val="0"/></c:ser>')
    grupo = next((g for g in GRUPOS.finditer(xml)
                  if set(re.findall(r'<c:axId val="(\d+)"/>', g.group(0))) == par), None)
    if grupo and grupo.group(1) == "lineChart":
        g = grupo.group(0)
        ultima = list(re.finditer(r'<c:ser>.*?</c:ser>', g, re.S))
        pos = ultima[-1].end() if ultima else re.search(r'<c:varyColors[^>]*/>', g).end()
        xml = xml.replace(g, g[:pos] + serie + g[pos:], 1)
    else:
        orden = re.findall(r'<c:axId val="(\d+)"/>', grupo.group(0)) if grupo else sorted(par)
        nuevo = ('<c:lineChart><c:grouping val="standard"/><c:varyColors val="0"/>' + serie + '<c:marker val="1"/>'
                 + "".join(f'<c:axId val="{i}"/>' for i in orden) + '</c:lineChart>')
        fin = list(GRUPOS.finditer(xml))[-1].end()
        xml = xml[:fin] + nuevo + xml[fin:]
    # Oculta en la leyenda (por su posición en la leyenda)
    pos = next(k for k, t in enumerate(orden_leyenda(xml)) if t == serie)
    entrada = f'<c:legendEntry><c:idx val="{pos}"/><c:delete val="1"/></c:legendEntry>'
    if re.search(r'<c:legendPos\b[^>]*/>', xml):
        xml = re.sub(r'(<c:legend>\s*<c:legendPos\b[^>]*/>)', lambda m: m.group(1) + entrada, xml, count=1)
    else:
        xml = xml.replace("<c:legend>", "<c:legend>" + entrada, 1)
    return xml


# Muestras anchas en la leyenda de los gráficos solo de barras (como «G_DO2608_06 TERMINADO LEYENDA»): con
# solo barras Excel dibuja muestras cuadradas pequeñas donde la trama no se ve; si en la leyenda hay una
# línea, todas las muestras salen anchas. Se añade una serie de línea blanca, sin datos, cuya entrada (al
# final) lleva el texto en blanco: no se ve, pero ensancha las muestras de las barras.
NOMBRE_MUESTRA = " "
LINEA_MUESTRA = ('<a:ln w="28575" cap="flat"><a:solidFill><a:srgbClr val="FFFFFF"/></a:solidFill></a:ln>')
TIPOS_BARRAS = ("barChart", "bar3DChart")
TIPOS_LINEA = ("lineChart", "line3DChart", "scatterChart", "radarChart")


def es_muestra(ser):
    return nombre_serie(ser) == NOMBRE_MUESTRA and "FFFFFF" in (hijo(hijos(ser), "spPr") or "")


def solo_barras_en_leyenda(xml):
    """¿En la leyenda hay barras (agrupadas o apiladas) y ninguna línea? Las series de solo marcadores (líneas
    o dispersión sin línea) también tienen muestra pequeña: no cuentan como línea («G_DO2608_01»)."""
    leyenda = re.search(r'<c:legend>.*?</c:legend>', xml, re.S)
    if not leyenda or es_tarta(xml):
        return False
    borradas = set(re.findall(r'<c:legendEntry><c:idx val="(\d+)"/><c:delete val="1"/>', leyenda.group(0)))
    tipo = {s: g.group(1) for g in GRUPOS.finditer(xml) for s in re.findall(r'<c:ser>.*?</c:ser>', g.group(0), re.S)}
    visibles = [s for k, s in enumerate(orden_leyenda(xml)) if str(k) not in borradas]
    def sin_linea(s):
        if tipo[s] not in TIPOS_LINEA:
            return False
        sppr = hijo(hijos(s), "spPr") or ""
        return bool(re.search(r'<a:ln\b[^>]*>\s*<a:noFill/>', sppr))
    return (any(tipo[s] in TIPOS_BARRAS for s in visibles)
            and all(tipo[s] in TIPOS_BARRAS or sin_linea(s) for s in visibles))


def meter_en_grupo_de_lineas(xml, serie, par):
    """La serie en el grupo de líneas de los ejes `par` (detrás de sus series, aunque solo tenga series
    filtradas), o en un grupo de líneas nuevo sobre esos ejes, al final de los grupos."""
    lineas = next((g for g in GRUPOS.finditer(xml) if g.group(1) == "lineChart"
                   and re.findall(r'<c:axId val="(\d+)"/>', g.group(0))[:2] == par[:2]), None)
    if lineas:
        g = lineas.group(0)
        series = list(re.finditer(r'<c:ser>.*?</c:ser>', g, re.S))
        pos = series[-1].end() if series else re.search(r'<c:varyColors\b[^>]*/>|<c:grouping\b[^>]*/>', g).end()
        return xml.replace(g, g[:pos] + serie + g[pos:], 1)
    grupo = ('<c:lineChart><c:grouping val="standard"/><c:varyColors val="0"/>' + serie + '<c:marker val="1"/>'
             + "".join(f'<c:axId val="{i}"/>' for i in par[:2]) + '</c:lineChart>')
    fin = list(GRUPOS.finditer(xml))[-1].end()
    return xml[:fin] + grupo + xml[fin:]


def muestra_del_autor(xml):
    """El autor (o el estudio) ya puso la serie de línea que ensancha las muestras de las barras (G_IA2025_3.6,
    «linea»: línea blanca y texto blanco en la leyenda, que se pierden al restablecer el estilo): una serie de línea
    con un dato como mucho, en un gráfico con barras, no dibuja nada. Se convierte en la de la app (sin nombre y
    línea blanca), que no cuenta para los estilos. Devuelve (xml, nombre que tenía) o (xml, None)."""
    if not any(g.group(1) in TIPOS_BARRAS for g in GRUPOS.finditer(xml)):
        return xml, None
    for g in GRUPOS.finditer(xml):
        if g.group(1) not in TIPOS_LINEA:
            continue
        for ser in re.findall(r'<c:ser>.*?</c:ser>', g.group(0), re.S):
            if es_muestra(ser):
                return xml, None
            val = re.search(r'<c:(?:val|yVal)>.*?</c:(?:val|yVal)>', ser, re.S)
            datos = re.findall(r'<c:pt idx="\d+">\s*<c:v>[^<]+</c:v>', val.group(0)) if val else []
            # Sin marcador: con uno, un solo dato sí se ve (los extremos de los intervalos del 1.28 y 1.29, rayas)
            marcador = hijo(hijos(ser), "marker")
            if not marcador or valor(hijo(hijos(marcador), "symbol")) != "none":
                continue
            # Más de un dato: solo si todos son 0 y la serie no tiene nombre (G_IA2025_3.7: celda del nombre vacía y
            # ceros; se llevaba el negro y descolocaba los colores de las barras)
            if len(datos) > 1:
                tx = re.search(r'<c:tx>.*?</c:tx>', ser, re.S)
                sin_nombre = not (tx and re.search(r'<c:v>\s*\S[^<]*</c:v>', tx.group(0)))
                if not (sin_nombre and all(abs(v) < 1e-12 for v in numeros(val.group(0)))):
                    continue
            nombre = nombre_serie(ser)
            h = hijos(ser)
            orden = ORDEN_SERIE[g.group(1)]
            poner(h, orden, "tx", f"<c:tx><c:v>{NOMBRE_MUESTRA}</c:v></c:tx>")
            poner(h, orden, "spPr", f"<c:spPr>{LINEA_MUESTRA}</c:spPr>")
            poner(h, orden, "marker", '<c:marker><c:symbol val="none"/></c:marker>')
            poner(h, orden, "dLbls", None)
            # Sin datos, como la muestra de la app: con sus ceros la línea blanca taparía el eje en 0 (1.21)
            campo = "yVal" if hijo(h, "yVal") else "val"
            poner(h, orden, campo, f'<c:{campo}><c:numLit><c:formatCode>General</c:formatCode><c:ptCount val="1"/>'
                                   f'</c:numLit></c:{campo}>')
            nueva = "<c:ser>" + "".join(t for _, t in h) + "</c:ser>"
            return xml.replace(ser, nueva, 1), nombre
    return xml, None


def muestras_anchas(xml):
    """Añade la serie de línea invisible que ensancha las muestras de la leyenda (None si no hace falta)."""
    if any(es_muestra(s) for s in re.findall(r'<c:ser>.*?</c:ser>', xml, re.S)) or not solo_barras_en_leyenda(xml):
        return None
    # Con una serie de solo marcadores en un grupo de líneas (los extremos de un intervalo, 1.28 panel b), la línea de
    # la muestra en ese grupo hace que Excel deje de dibujar los marcadores y su entrada: no se añade
    for g in GRUPOS.finditer(xml):
        if g.group(1) == "lineChart":
            for ser in re.findall(r'<c:ser>.*?</c:ser>', g.group(0), re.S):
                sppr = hijo(hijos(ser), "spPr") or ""
                marcador = hijo(hijos(ser), "marker")
                if re.search(r'<a:ln\b[^>]*>\s*<a:noFill/>', sppr) and marcador and \
                        valor(hijo(hijos(marcador), "symbol")) not in (None, "none"):
                    return None
    barras = next(g for g in GRUPOS.finditer(xml) if g.group(1) in TIPOS_BARRAS)
    horizontal = valor(hijo(hijos(barras.group(0)), "barDir")) == "bar"
    sers = re.findall(r'<c:ser>.*?</c:ser>', xml, re.S)
    idx = max([int(valor(hijo(hijos(s), "idx")) or 0) for s in sers] + [-1]) + 1
    orden = max([int(valor(hijo(hijos(s), "order")) or 0) for s in sers] + [-1]) + 1
    serie = (f'<c:ser><c:idx val="{idx}"/><c:order val="{orden}"/><c:tx><c:v>{NOMBRE_MUESTRA}</c:v></c:tx>'
             f'<c:spPr>{LINEA_MUESTRA}</c:spPr><c:marker><c:symbol val="none"/></c:marker>'
             '<c:val><c:numLit><c:formatCode>General</c:formatCode><c:ptCount val="1"/></c:numLit></c:val>'
             '<c:smooth val="0"/></c:ser>')
    antes = orden_leyenda(xml)
    # Con barras horizontales las líneas no comparten ejes: van a unos ejes secundarios borrados (los que ya
    # haya: Excel solo admite dos juegos)
    dispersion = any(g.group(1) == "scatterChart" for g in GRUPOS.finditer(xml))
    par = re.findall(r'<c:axId val="(\d+)"/>', barras.group(0))
    # Excel solo admite dos juegos de ejes: si ya hay secundarios, la línea va a ellos
    secundario = next((re.findall(r'<c:axId val="(\d+)"/>', g.group(0)) for g in GRUPOS.finditer(xml)
                       if re.findall(r'<c:axId val="(\d+)"/>', g.group(0))[:2] != par[:2]), None)
    if dispersion:
        # Excel ordena la leyenda por tipos (barras, líneas, dispersión) sean cuales sean los ejes: con una
        # dispersión, la muestra va como dispersión con línea, detrás de su última serie
        g = [g for g in GRUPOS.finditer(xml) if g.group(1) == "scatterChart"][-1].group(0)
        disp = (f'<c:ser><c:idx val="{idx}"/><c:order val="{orden}"/><c:tx><c:v>{NOMBRE_MUESTRA}</c:v></c:tx>'
                f'<c:spPr>{LINEA_MUESTRA}</c:spPr><c:marker><c:symbol val="none"/></c:marker>'
                '<c:yVal><c:numLit><c:formatCode>General</c:formatCode><c:ptCount val="1"/></c:numLit></c:yVal>'
                '<c:smooth val="0"/></c:ser>')
        series = list(re.finditer(r'<c:ser>.*?</c:ser>', g, re.S))
        fin_g = series[-1].end() if series else re.search(r'<c:varyColors\b[^>]*/>', g).end()
        xml = xml.replace(g, g[:fin_g] + disp + g[fin_g:], 1)
        serie = disp
    elif horizontal and secundario:
        xml = meter_en_grupo_de_lineas(xml, serie, secundario)
    elif horizontal:
        usados = {int(i) for i in re.findall(r'<c:axId val="(\d+)"/>', xml)}
        a, b = max(usados) + 1, max(usados) + 2
        grupo = ('<c:lineChart><c:grouping val="standard"/><c:varyColors val="0"/>' + serie + '<c:marker val="1"/>'
                 f'<c:axId val="{a}"/><c:axId val="{b}"/></c:lineChart>')
        ejes = (f'<c:catAx><c:axId val="{a}"/><c:scaling><c:orientation val="minMax"/></c:scaling><c:delete val="1"/>'
                f'<c:axPos val="b"/><c:majorTickMark val="none"/><c:minorTickMark val="none"/><c:tickLblPos val="nextTo"/>'
                f'<c:crossAx val="{b}"/><c:crosses val="autoZero"/><c:auto val="1"/><c:lblAlgn val="ctr"/>'
                f'<c:lblOffset val="100"/><c:noMultiLvlLbl val="0"/></c:catAx>'
                f'<c:valAx><c:axId val="{b}"/><c:scaling><c:orientation val="minMax"/></c:scaling><c:delete val="1"/>'
                f'<c:axPos val="r"/><c:numFmt formatCode="General" sourceLinked="1"/><c:majorTickMark val="none"/>'
                f'<c:minorTickMark val="none"/><c:tickLblPos val="nextTo"/><c:crossAx val="{a}"/>'
                f'<c:crosses val="max"/><c:crossBetween val="between"/></c:valAx>')
        fin = list(GRUPOS.finditer(xml))[-1].end()
        xml = xml[:fin] + grupo + xml[fin:]
        fin_ejes = list(EJES.finditer(xml))[-1].end()
        xml = xml[:fin_ejes] + ejes + xml[fin_ejes:]
    else:
        # En el grupo de líneas de los ejes de las barras, o en uno nuevo sobre ellos
        xml = meter_en_grupo_de_lineas(xml, serie, par)
    # Las entradas de la leyenda van por posición: las que quedan detrás de la nueva se corren una
    pos = next(k for k, t in enumerate(orden_leyenda(xml)) if t == serie)

    def correr(m):
        k = int(m.group(1))
        return f'<c:legendEntry><c:idx val="{k + 1 if k >= pos and k < len(antes) else k}"/>'
    leyenda = re.search(r'<c:legend>.*?</c:legend>', xml, re.S).group(0)
    nueva = re.sub(r'<c:legendEntry><c:idx val="(\d+)"/>', correr, leyenda)
    # Su texto, en blanco: no se ve
    texto = ('<c:legendEntry><c:idx val="{}"/><c:txPr><a:bodyPr/><a:lstStyle/><a:p><a:pPr><a:defRPr sz="700">'
             '<a:solidFill><a:srgbClr val="FFFFFF"/></a:solidFill></a:defRPr></a:pPr><a:endParaRPr lang="es-ES"/>'
             '</a:p></c:txPr></c:legendEntry>').format(pos)
    entradas = list(re.finditer(r'<c:legendEntry>.*?</c:legendEntry>', nueva, re.S))
    if entradas:
        corte = entradas[-1].end()
    else:
        corte = re.search(r'<c:legendPos\b[^>]*/>', nueva).end() if '<c:legendPos' in nueva else len("<c:legend>")
    nueva = nueva[:corte] + texto + nueva[corte:]
    return xml.replace(leyenda, nueva, 1)


# Línea divisoria (guía, pág. 14): negra, 1 pt, remate plano y unión en ángulo
LINEA_DIVISORIA = ('<a:ln w="12700" cap="flat"><a:solidFill><a:srgbClr val="000000"/></a:solidFill>'
                   '<a:miter lim="800000"/></a:ln>')


# Líneas guía de las etiquetas de datos (guía, pág. 16): blanco matiz 5 (color de los ejes), 0,5 pt, remate
# plano y unión en ángulo. Solo se ponen si las etiquetas se confunden: aquí solo se da formato a las que haya.
LINEA_GUIA = LINEA_EJE


def lineas_guia(xml):
    """Formato de las líneas guía activadas de las etiquetas de datos de las series. Dos sitios: en las tartas,
    dentro de las etiquetas (c:leaderLines); en el resto, la extensión c15 de Excel 2013. Las desactivadas no:
    Excel descarta su formato al abrir y, si luego se activan a mano, les pone el suyo (negro, 0,75 pt); para
    eso está el botón «Líneas guía» de la app, que les da formato en el Excel abierto. Devuelve el xml y
    cuántos grupos de etiquetas las llevan."""
    activas = [0]
    guia = f"<c:spPr>{LINEA_GUIA}</c:spPr>"
    tarta = es_tarta(xml)
    ext_uri = "{CE6537A1-D6FC-4f65-9D91-7224C49458BB}"

    def etiquetas(m):
        d = m.group(0)
        if tarta:
            if '<c:showLeaderLines val="1"/>' not in d:
                return d
            activas[0] += 1
            d = re.sub(r'<c:leaderLines\s*/>|<c:leaderLines>.*?</c:leaderLines>', "", d, flags=re.S)
            return d.replace('<c:showLeaderLines val="1"/>', f'<c:showLeaderLines val="1"/><c:leaderLines>{guia}</c:leaderLines>', 1)
        # Resto: extensión c15 (las etiquetas de la serie)
        ext = re.search(rf'<c:ext uri="{re.escape(ext_uri)}"[^>]*>.*?</c:ext>', d, re.S)
        if not ext or '<c15:showLeaderLines val="1"/>' not in ext.group(0):
            return d
        activas[0] += 1
        e = re.sub(r'<c15:leaderLines\s*/>|<c15:leaderLines>.*?</c15:leaderLines>', "", ext.group(0), flags=re.S)
        e = e.replace('<c15:showLeaderLines val="1"/>', f'<c15:showLeaderLines val="1"/><c15:leaderLines>{guia}</c15:leaderLines>', 1)
        return d.replace(ext.group(0), e, 1)
    # Solo las etiquetas de las series (no las del grupo, fuera de c:ser)
    xml = re.sub(r'<c:ser>.*?</c:ser>', lambda s_: re.sub(r'<c:dLbls>.*?</c:dLbls>', etiquetas, s_.group(0), count=1, flags=re.S),
                 xml, flags=re.S)
    return xml, activas[0]


def linea_flecha(ln):
    """Flecha como en el TERMINADO: negra, 0,5 pt, unión en ángulo y punta abierta en los mismos extremos."""
    puntas = ""
    for extremo in ("headEnd", "tailEnd"):
        m = re.search(rf'<a:{extremo}\b[^>]*\btype="(\w+)"', ln)
        if m and m.group(1) != "none":
            puntas += f'<a:{extremo} type="arrow"/>'
    return f'<a:ln w="6350"><a:solidFill><a:schemeClr val="tx1"/></a:solidFill><a:miter lim="800000"/>{puntas}</a:ln>'


def es_flecha(ln):
    return bool(re.search(r'<a:(headEnd|tailEnd)\b[^>]*\btype="(?!none")\w+"', ln))


def lineas_dibujadas(xml, prefijo):
    """Flechas y líneas divisorias dibujadas (conectores y formas de línea) en un dibujo de la hoja (`xdr`) o de
    un gráfico (`cdr`). Devuelve el xml y lo hecho."""
    hechos = []

    def forma(m):
        f = m.group(0)
        sppr = re.search(rf'<{prefijo}:spPr\b.*?</{prefijo}:spPr>', f, re.S)
        if not sppr or not re.search(r'prst="(line|straightConnector1|bentConnector\d|curvedConnector\d)"', sppr.group(0)):
            return f
        ln = re.search(r'<a:ln\b[^>]*/>|<a:ln\b.*?</a:ln>', sppr.group(0), re.S)
        actual = ln.group(0) if ln else ""
        if es_flecha(actual):
            nueva, que = linea_flecha(actual), "flecha"
        else:
            nueva, que = LINEA_DIVISORIA, "línea divisoria"
        # En los dibujos de los gráficos el prefijo «a» se declara en cada elemento
        if prefijo == "cdr":
            nueva = nueva.replace("<a:ln", '<a:ln xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"', 1)
        cuerpo = (sppr.group(0).replace(actual, nueva, 1) if ln
                  else sppr.group(0).replace(f"</{prefijo}:spPr>", nueva + f"</{prefijo}:spPr>"))
        hechos.append(que)
        return f.replace(sppr.group(0), cuerpo, 1)
    return re.sub(rf'<{prefijo}:(cxnSp|sp)\b.*?</{prefijo}:\1>', forma, xml, flags=re.S), hechos


def series_divisorias(xml):
    """Series de columnas que el autor usa como línea divisoria (una o pocas columnas entre muchas categorías,
    p. ej. «Elecciones EEUU»): relleno negro y contorno de la línea divisoria, que es lo que se ve."""
    hechos = []

    def grupo(g):
        def serie(m):
            ser = m.group(0)
            val = re.search(r'<c:val>.*?</c:val>', ser, re.S)
            total = re.search(r'<c:ptCount val="(\d+)"', val.group(0)) if val else None
            llenos = [v for v in re.findall(r'<c:v>([^<]*)</c:v>', val.group(0)) if v.strip() not in ("", "0")] if val else []
            if not total or int(total.group(1)) < 10 or not 1 <= len(llenos) <= 3:
                return ser
            relleno = '<c:spPr><a:solidFill><a:srgbClr val="000000"/></a:solidFill>' + LINEA_DIVISORIA + '</c:spPr>'
            h = hijos(ser)
            poner(h, ["idx", "order", "tx", "spPr", "invertIfNegative", "pictureOptions", "dPt", "dLbls", "trendline",
                      "errBars", "cat", "val", "shape", "extLst"], "spPr", relleno)
            # Los puntos con formato propio (dPt), igual
            h = [[n, re.sub(r'<c:spPr>.*?</c:spPr>', relleno, t, flags=re.S) if n == "dPt" else t] for n, t in h]
            hechos.append(f"«{nombre_serie(ser)}» (columnas como línea divisoria)")
            return "<c:ser>" + "".join(t for _, t in h) + "</c:ser>"
        return re.sub(r'<c:ser>.*?</c:ser>', serie, g.group(0), flags=re.S)
    return re.sub(r'<c:barChart>.*?</c:barChart>', grupo, xml, flags=re.S), hechos


LINEAS_INTERIORES = "Líneas interiores"


def paso4(trabajo, pid=None):
    """Líneas del interior de los gráficos. Línea base (guía de gráficos, pág. 13): si las unidades de un panel
    indican un dato de referencia («Base 100 = …», «100 = …»; 100 o 50), una columna con ese dato en la hoja de
    datos y una serie de línea con ella, oculta en la leyenda. Líneas divisorias (pág. 14): negras de 1 pt.
    Flechas: como en el TERMINADO, negras de 0,5 pt con punta abierta. Líneas guía de las etiquetas, si las hay
    (pág. 16): blanco matiz 5, 0,5 pt."""
    estado = leer_estado(trabajo)
    _, pasos = nombres(trabajo)
    base_archivo = pasos / estado["pasos"][estado["actual"]]["archivo"]
    requiere(estado, ("Ejes",), "«Línea base»")
    ret = CONFIG["reticula"]
    with zipfile.ZipFile(PROYECTO / ret["archivo"]) as zr:
        dibujo_ret = zr.read(dibujo_de_hoja(zr, ret["hoja"])).decode("utf-8")
    anclas_ret = {nombre_forma(a.group(0)): a.group(0) for a in ANCLA.finditer(dibujo_ret)}
    alto_pastilla = tamano(anclas_ret[ret["pastilla_modelo"]])[1]
    ancho_ret = tamano(anclas_ret[ret["grupo"]], escala_grupo=True)[0]
    cambios, detalle = {}, []
    with zipfile.ZipFile(base_archivo) as z:
        ruta = dibujo_de_hoja(z, HOJA_GRAFICO)
        dibujo = z.read(ruta).decode("utf-8")
        relaciones = rels(z, ruta)
        partes = list(partes_dibujo(dibujo))
        caja = medidas_hoja(z, dibujo)
        tipos = clasificar_textos(partes, caja, alto_pastilla, ancho_ret)
        graficos = sorted((caja(a)[1], i, re.search(r'<c:chart\b[^>]*\br:id="([^"]+)"', a).group(1))
                          for i, a in enumerate(partes) if ANCLA.fullmatch(a) and "<c:chart " in a)
        hojas = {}   # hoja de datos → xml, con lo que se va añadiendo
        for n, (_, ig, rid) in enumerate(graficos, 1):
            ruta_graf = relaciones[rid][1]
            xml = z.read(ruta_graf).decode("utf-8")
            # Líneas divisorias hechas con una serie de columnas
            xml, divisorias = series_divisorias(xml)
            if divisorias:
                cambios[ruta_graf] = xml.encode("utf-8")
                detalle.append(f"Panel {n}: " + ", ".join(divisorias) + ": negra, 1 pt, remate plano y unión en ángulo")
            # Líneas guía de las etiquetas que estén activadas
            xml, guias = lineas_guia(xml)
            if guias:
                cambios[ruta_graf] = xml.encode("utf-8")
                detalle.append(f"Panel {n}: líneas guía de las etiquetas en blanco matiz 5, 0,5 pt, remate plano y unión "
                               "en ángulo (guía, pág. 16)")
            # Flechas y líneas dibujadas dentro del gráfico
            ruta_dib = next((d for t, d in rels(z, ruta_graf).values() if t.endswith("/chartUserShapes")), None)
            if ruta_dib:
                formas, dibujadas = lineas_dibujadas(z.read(ruta_dib).decode("utf-8"), "cdr")
                if dibujadas:
                    cambios[ruta_dib] = formas.encode("utf-8")
                    detalle.append(f"Panel {n}: " + resumen_lineas(dibujadas))
            ruta_formas = next((d for t, d in rels(z, ruta_graf).values() if t.endswith("/chartUserShapes")), None)
            unidades = [html.unescape(texto_forma(a)).strip() for a in unidades_de(z.read(ruta_formas).decode("utf-8"), xml)] if ruta_formas else []
            unidades += [html.unescape(texto_forma(partes[i])).strip() for i, (t, g) in tipos.items() if t == "unidades" and g == ig]
            hallado = next(((u, RE_BASE.search(u)) for u in unidades if RE_BASE.search(u)), None)
            if not hallado:
                # Sin referencia en las unidades, pero con una serie del autor todo 100 o 50: es su línea base
                del_autor = None
                for b in (100, 50):
                    xml, del_autor = linea_base_del_autor(xml, b)
                    if del_autor:
                        cambios[ruta_graf] = xml.encode("utf-8")
                        detalle.append(f"Aviso: panel {n}: la serie «⟪{del_autor}⟫» del autor (todo {b}) es una línea de "
                                       "referencia: pasa a ser la línea base de la guía (gris como los ejes, 0,5 pt), "
                                       "fuera de la leyenda y de la secuencia de colores; las unidades no indican la base")
                        break
                if not del_autor:
                    detalle.append(f"Panel {n}: sin dato de referencia en las unidades, sin línea base")
                continue
            texto, m = hallado
            base = int(next(g for g in m.groups() if g))
            corto = texto.replace("\n", " ")[:60]
            if re.search(rf'<c:tx><c:v>Base {base}</c:v></c:tx>', xml):
                detalle.append(f"Panel {n}: ya tiene la línea base {base}")
                continue
            # El autor ya dibujó la línea de referencia como una serie más (todo {base}: «cien» del G_IA2025_3.2 a,
            # que salía como una línea de datos en la leyenda): pasa a ser la línea base de la guía
            xml, del_autor = linea_base_del_autor(xml, base)
            if del_autor:
                cambios[ruta_graf] = xml.encode("utf-8")
                detalle.append(f"Aviso: panel {n}: la serie «⟪{del_autor}⟫» del autor (todo {base}) es la línea de referencia "
                               f"de «{corto}»: pasa a ser la línea base de la guía (gris como los ejes, 0,5 pt), fuera de la "
                               "leyenda y de la secuencia de colores")
                continue
            # Los datos de las series: hoja, primera fila y última con datos
            refs = re.findall(r"<c:val>\s*<c:numRef>\s*<c:f>(?:'([^']+)'|([^!<]+))!\$([A-Z]+)\$(\d+):\$([A-Z]+)\$(\d+)</c:f>", xml)
            if not refs:
                detalle.append(f"Aviso: el panel {n} indica la base {base} («{corto}»), pero no encuentro sus datos "
                               "en la hoja: la línea base hay que ponerla a mano")
                continue
            nombre = refs[0][0] or refs[0][1]
            refs = [r for r in refs if (r[0] or r[1]) == nombre]
            fila1 = min(int(r[3]) for r in refs)
            ruta_hoja = hoja_de(z, nombre)
            hoja = hojas.get(ruta_hoja) or z.read(ruta_hoja).decode("utf-8")
            ultimas = [ultima_fila_con_datos(hoja, r[2], int(r[3]), int(r[5])) for r in refs]
            fila2 = max([u for u in ultimas if u] or [0])
            if fila2 < fila1:
                detalle.append(f"Aviso: el panel {n} indica la base {base} («{corto}»), pero sus series no tienen "
                               "datos: la línea base hay que ponerla a mano")
                continue
            col = columna_letras(ultima_columna(hoja) + 1)
            puntos = fila2 - fila1 + 1
            hoja = poner_columna(hoja, col, fila1, [base] * puntos)
            hojas[ruta_hoja] = hoja
            idx = max(int(i) for i in re.findall(r'<c:idx val="(\d+)"/>', xml)) + 1
            ref = f"'{nombre}'!${col}${fila1}:${col}${fila2}"
            nuevo = anadir_linea_base(xml, base, ref, puntos, idx)
            if nuevo is None:
                detalle.append(f"Aviso: el panel {n} indica la base {base}, pero no tiene eje de valores: la línea "
                               "base hay que ponerla a mano")
                continue
            cambios[ruta_graf] = nuevo.encode("utf-8")
            detalle.append(f"Panel {n}: «{corto}» → línea base {base}: serie «Base {base}» con {base} en "
                           f"{nombre}!{col}{fila1}:{col}{fila2} (la primera columna libre, hasta la última fila con "
                           "datos); gris como los ejes (matiz 5), 0,5 pt, remate plano y unión en ángulo; oculta en la leyenda")
        for ruta_hoja, hoja in hojas.items():
            cambios[ruta_hoja] = hoja.encode("utf-8")
        # Flechas y líneas dibujadas en la hoja, dentro de la retícula (la retícula no se toca)
        dibujadas = []
        for k, a in enumerate(partes):
            if ANCLA.fullmatch(a) and not es_reticula(a) and caja(a)[0] < ancho_ret:
                partes[k], hechas = lineas_dibujadas(a, "xdr")
                dibujadas += hechas
        if dibujadas:
            cambios[ruta] = "".join(partes).encode("utf-8")
            detalle.append("En la hoja: " + resumen_lineas(dibujadas))
    return nuevo_paso(trabajo, LINEAS_INTERIORES, cambios, detalle)


def resumen_lineas(hechas):
    partes = []
    if hechas.count("flecha"):
        partes.append(f"{hechas.count('flecha')} flecha{'s' if hechas.count('flecha') > 1 else ''} negra(s) de 0,5 pt, "
                      "unión en ángulo y punta abierta, como en el TERMINADO")
    if hechas.count("línea divisoria"):
        partes.append(f"{hechas.count('línea divisoria')} línea(s) divisoria(s) negra(s) de 1 pt, remate plano y unión en ángulo")
    return "; ".join(partes)

# ---------------------------------------------------------------- paso 5: tramas, colores y líneas

# Estilos de las series por paleta de la publicación («Excel. Guía líneas y tramas colores 2026»). Cada
# publicación podrá tener los suyos; de momento, los de la paleta BdE_2026 (Documentos Ocasionales).
# trama: (preset, primer plano, fondo); línea: (color, guion, marcador, tamaño del marcador)
ESTILOS_SERIES = {
    "BdE_2026": [
        {"trama": ("dkHorz", "000000", "595959"), "linea": ("000000", "solid", None, None),
         "nombre": "negro, franjas horizontales oscuras / línea sólida"},
        {"trama": ("pct90", "7DB749", "FFFFFF"), "linea": ("7DB749", "sysDash", None, None),
         "nombre": "verde, punteado 90 % / punto cuadrado"},
        {"trama": ("dkUpDiag", "FFDB93", "FFF0D2"), "linea": ("FFDB93", "sysDot", None, None),
         "nombre": "amarillo, diagonales oscuras hacia arriba / punto redondo"},
        {"trama": ("zigZag", "EF9011", "FFC000"), "linea": ("EF9011", "solid", "triangle", 6),
         "nombre": "naranja, zigzag / sólida con triángulo"},
        {"trama": ("narVert", "1D5191", "AECEF4"), "linea": ("AECEF4", "solid", "square", 5),
         "nombre": "azul, verticales estrechas / sólida con cuadrado"},
        {"trama": ("wdDnDiag", "C30FBA", "F257EB"), "linea": ("C30FBA", "solid", "circle", 5),
         "nombre": "rosa, diagonales anchas hacia abajo / sólida con círculo"},
        {"trama": ("dkVert", "7F3C2F", "C9796B"), "linea": ("C9796B", "solid", "diamond", 6),
         "nombre": "marrón, verticales oscuras / sólida con rombo"},
    ],
}
ANCHO_LINEA_SERIE = 28575    # 2,25 pt (decisión del usuario; el del TERMINADO del 2.6)
MARCADOR_SOLO = ("circle", 5)   # series que son solo marcadores: círculo sólido de 5 pt sin borde (TERMINADO 2.6)
# La forma del marcador es la del autor; si la dejó en automático, la que pone Excel según el número de la serie
# (la primera, rombo: G_IA2025_1.31, como en el .ai). Tamaño 5, sólido, sin borde y color de la secuencia
# (decisión del usuario, 2026-11-26). Círculo solo si no hay ninguna forma que respetar
MARCADORES_AUTOMATICOS = ["diamond", "square", "triangle", "x", "star", "circle", "plus"]


# Las formas de raya (sin superficie) a 5 pt casi no se ven: 7 pt, como los extremos de los intervalos de la guía
# (G_IA2025_1.35 c: rayas de 10 pt del autor)
TAMANO_RAYA = 7


def tamano_marcador(forma):
    return TAMANO_RAYA if forma in ("dash", "x", "plus", "star") else MARCADOR_SOLO[1]


def tamano_del_autor(ser):
    m = hijo(hijos(ser), "marker")
    t = valor(hijo(hijos(m), "size")) if m else None
    return int(t) if t else None


NOMBRES_MARCADOR = {"diamond": "rombo", "square": "cuadrado", "triangle": "triángulo", "circle": "círculo",
                    "x": "aspa", "star": "asterisco", "plus": "cruz", "dash": "raya", "dot": "punto"}


def forma_marcador(ser):
    """(símbolo, ¿automático?) de una serie de marcadores, como se ve en el Excel del autor."""
    h = hijos(ser)
    simbolo = valor(hijo(hijos(hijo(h, "marker")), "symbol")) if hijo(h, "marker") else None
    if simbolo and simbolo not in ("none", "auto"):
        return simbolo, False
    if simbolo == "none":
        return MARCADOR_SOLO[0], False
    idx = int(valor(hijo(h, "idx")) or 0)
    return MARCADORES_AUTOMATICOS[idx % len(MARCADORES_AUTOMATICOS)], True
MAXIMO_ESTILOS = 7
# Marcadores de las líneas con muchos puntos (petición del usuario): no se quitan, se espacian para que no se
# agolpen; como mucho uno cada ESPACIO_MARCADORES a lo ancho del trazado. Las líneas de un mismo panel se
# desfasan para que sus marcadores no caigan en la misma categoría.
ESPACIO_MARCADORES = 4 * 72 / 25.4   # 4 mm, en pt (decisión del usuario)
ORDEN_SERIE = {
    "barChart": ["idx", "order", "tx", "spPr", "invertIfNegative", "pictureOptions", "dPt", "dLbls", "trendline",
                 "errBars", "cat", "val", "shape", "extLst"],
    "bar3DChart": ["idx", "order", "tx", "spPr", "invertIfNegative", "pictureOptions", "dPt", "dLbls", "trendline",
                   "errBars", "cat", "val", "shape", "extLst"],
    "lineChart": ["idx", "order", "tx", "spPr", "marker", "dPt", "dLbls", "trendline", "errBars", "cat", "val",
                  "smooth", "extLst"],
    "areaChart": ["idx", "order", "tx", "spPr", "pictureOptions", "dPt", "dLbls", "trendline", "errBars", "cat",
                  "val", "extLst"],
    "scatterChart": ["idx", "order", "tx", "spPr", "marker", "dPt", "dLbls", "trendline", "errBars", "xVal", "yVal",
                     "smooth", "extLst"],
    "pieChart": ["idx", "order", "tx", "spPr", "explosion", "dPt", "dLbls", "cat", "val", "extLst"],
    "doughnutChart": ["idx", "order", "tx", "spPr", "explosion", "dPt", "dLbls", "cat", "val", "extLst"],
}
ORDEN_DPT = ["idx", "invertIfNegative", "marker", "bubble3D", "explosion", "spPr", "pictureOptions", "extLst"]
ORDEN_MARCADOR = ["symbol", "size", "spPr", "extLst"]
SIN_LINEA = '<a:ln><a:noFill/></a:ln>'


def sppr_trama(estilo):
    preset, frente, fondo = estilo["trama"]
    return (f'<c:spPr><a:pattFill prst="{preset}"><a:fgClr><a:srgbClr val="{frente}"/></a:fgClr><a:bgClr>'
            f'<a:srgbClr val="{fondo}"/></a:bgClr></a:pattFill>{SIN_LINEA}</c:spPr>')


def sppr_linea(estilo):
    color, guion, _, _ = estilo["linea"]
    remate = "rnd" if guion == "sysDot" else "flat"   # punto redondo: remate redondo
    return (f'<c:spPr><a:ln w="{ANCHO_LINEA_SERIE}" cap="{remate}"><a:solidFill><a:srgbClr val="{color}"/>'
            f'</a:solidFill><a:prstDash val="{guion}"/><a:round/></a:ln></c:spPr>')


def marcador(simbolo, tamano, color):
    if not simbolo:
        return '<c:marker><c:symbol val="none"/></c:marker>'
    return (f'<c:marker><c:symbol val="{simbolo}"/><c:size val="{tamano}"/><c:spPr><a:solidFill>'
            f'<a:srgbClr val="{color}"/></a:solidFill>{SIN_LINEA}</c:spPr></c:marker>')


# Recta de referencia en una dispersión (la diagonal de 45°, dos puntos): negra de 1 pt, sin marcadores, como en el
# .ai (G_IA2025_1.31, panel a; petición del usuario, 2026-11-26). Ocupa su lugar en el orden de estilos
ANCHO_RECTA_REFERENCIA = 12700


def es_recta_referencia(tipo, ser):
    if tipo != "scatterChart":
        return False
    y = re.search(r'<c:yVal>.*?</c:yVal>', ser, re.S)
    return bool(y) and len(re.findall(r'<c:pt idx="\d+">\s*<c:v>[^<]+</c:v>', y.group(0))) == 2


def nombre_serie(ser):
    # Dentro de <c:tx>: si su caché está vacía, no seguir hasta la primera categoría («2000» en el G_IA2025_3.7)
    tx = re.search(r'<c:tx>.*?</c:tx>', ser, re.S)
    m = re.search(r'<c:v>([^<]*)</c:v>', tx.group(0)) if tx else None
    return html.unescape(m.group(1)) if m else "serie sin nombre"


def es_divisoria(ser):
    """La serie de columnas que hace de línea divisoria (paso 4): no entra en el orden de colores."""
    val = re.search(r'<c:val>.*?</c:val>', ser, re.S)
    total = re.search(r'<c:ptCount val="(\d+)"', val.group(0)) if val else None
    llenos = [v for v in re.findall(r'<c:v>([^<]*)</c:v>', val.group(0)) if v.strip() not in ("", "0")] if val else []
    return bool(total and int(total.group(1)) >= 10 and 1 <= len(llenos) <= 3)


def clase_serie(tipo, ser, solo_marcadores=False):
    """«linea», «marcador», «trama» o None (no se toca: invisible, línea base…)."""
    h = hijos(ser)
    sppr = hijo(h, "spPr") or ""
    ln = re.search(r'<a:ln\b.*?</a:ln>|<a:ln\b[^>]*/>', sppr, re.S)
    sin_linea = bool(ln and "<a:noFill/>" in ln.group(0))
    relleno = re.sub(r'<a:ln\b.*?</a:ln>|<a:ln\b[^>]*/>', "", sppr, flags=re.S)
    sin_relleno = "<a:noFill/>" in relleno
    simbolo = valor(hijo(hijos(hijo(h, "marker")), "symbol")) if hijo(h, "marker") else None
    if re.fullmatch(r'Base (100|50)', nombre_serie(ser)) or es_muestra(ser):
        return None
    if tipo in ("lineChart", "scatterChart"):
        if sin_linea or (tipo == "scatterChart" and solo_marcadores and not ln):
            return None if simbolo == "none" else "marcador"
        return "linea"
    if tipo in ("barChart", "bar3DChart", "areaChart"):
        if sin_relleno:
            return None
        if tipo.startswith("bar") and es_divisoria(ser):
            return None
        return "trama"
    return None


# Intervalos (guía, pág. 16): la línea de máximos y mínimos negra de 1 pt, remate plano y unión en ángulo; los
# extremos, marcador raya negro de 7 pt (sin línea de serie)
LINEA_INTERVALO = ('<a:ln w="12700" cap="flat"><a:solidFill><a:srgbClr val="000000"/></a:solidFill>'
                   '<a:miter lim="800000"/></a:ln>')
MARCADOR_INTERVALO = ('<c:marker><c:symbol val="dash"/><c:size val="7"/><c:spPr><a:solidFill><a:srgbClr val="000000"/>'
                      '</a:solidFill><a:ln w="9525"><a:solidFill><a:srgbClr val="000000"/></a:solidFill></a:ln></c:spPr>'
                      '</c:marker>')
# Sombreados (guía, pág. 16): color de la publicación, matiz 1, sin transparencia; al 80 % si tapan datos
TRANSPARENCIA_SOMBREADO = 80


def idx_serie(ser):
    return valor(hijo(hijos(ser), "idx"))


def intervalos(xml):
    """Grupos de líneas con líneas de máximos y mínimos: formato de la línea y de los marcadores de las dos
    series de los extremos (la que más veces es la más alta y la que más veces es la más baja). Devuelve el xml,
    el detalle y los idx de las series de los extremos (no entran en el orden de colores)."""
    detalle, extremos = [], set()
    for g in list(re.finditer(r'<c:(lineChart|stockChart)>.*?</c:\1>', xml, re.S)):
        grupo = g.group(0)
        if "<c:hiLowLines" not in grupo:
            continue
        series = re.findall(r'<c:ser>.*?</c:ser>', grupo, re.S)
        valores = []
        for ser in series:
            val = re.search(r'<c:val>.*?</c:val>', ser, re.S)
            pts = dict(re.findall(r'<c:pt idx="(\d+)"[^>]*>\s*<c:v>([^<]*)</c:v>', val.group(0))) if val else {}
            valores.append({int(k): float(v) for k, v in pts.items() if re.fullmatch(r'-?[\d.]+(E-?\d+)?', v, re.I)})
        if len(series) < 2:
            continue
        altas, bajas = [0] * len(series), [0] * len(series)
        for p in set().union(*valores):
            con = [(v[p], k) for k, v in enumerate(valores) if p in v]
            if len(con) >= 2:
                altas[max(con)[1]] += 1
                bajas[min(con)[1]] += 1
        alta = max(range(len(series)), key=lambda k: altas[k])
        baja = max((k for k in range(len(series)) if k != alta), key=lambda k: bajas[k])
        nuevo = re.sub(r'<c:hiLowLines\s*/>|<c:hiLowLines>.*?</c:hiLowLines>',
                       f'<c:hiLowLines><c:spPr>{LINEA_INTERVALO}</c:spPr></c:hiLowLines>', grupo, count=1, flags=re.S)
        for k in (alta, baja):
            h = hijos(series[k])
            poner(h, ORDEN_SERIE["lineChart"], "spPr", f'<c:spPr><a:ln w="{ANCHO_LINEA_SERIE}"><a:noFill/></a:ln></c:spPr>')
            poner(h, ORDEN_SERIE["lineChart"], "marker", MARCADOR_INTERVALO)
            nuevo = nuevo.replace(series[k], "<c:ser>" + "".join(t for _, t in h) + "</c:ser>", 1)
            extremos.add(idx_serie(series[k]))
        xml = xml.replace(grupo, nuevo, 1)
        detalle.append(f"intervalo: línea de máximos y mínimos negra de 1 pt (remate plano, unión en ángulo); "
                       f"«{nombre_serie(series[alta])}» y «{nombre_serie(series[baja])}» (máximo y mínimo): "
                       "marcador raya negro de 7 pt, sin línea")
    # Intervalos hechos con barras de error (G_IA2025_1.28, panel b, 2026-11-26): una serie sin línea con barras de
    # error que unen un extremo con el otro y las series de los extremos (sin línea, con marcador). Igual que con
    # las líneas de máximos y mínimos: la barra, negra de 1 pt; los extremos, raya negra de 7 pt (pág. 16); sin los
    # remates de la barra de error, que ya marcan las rayas
    for g in list(re.finditer(r'<c:(lineChart|scatterChart)>.*?</c:\1>', xml, re.S)):
        grupo = g.group(0)
        if "<c:errBars>" not in grupo:
            continue
        series = re.findall(r'<c:ser>.*?</c:ser>', grupo, re.S)

        def sin_linea(ser):
            sppr = hijo(hijos(ser), "spPr") or ""
            return bool(re.search(r'<a:ln\b[^>]*>\s*<a:noFill/>', sppr))
        de_intervalo = [ser for ser in series if sin_linea(ser) and ("<c:errBars>" in ser or (
            hijo(hijos(ser), "marker") and valor(hijo(hijos(hijo(hijos(ser), "marker")), "symbol")) not in (None, "none")))]
        if not any("<c:errBars>" in ser for ser in de_intervalo):
            continue
        nuevo, nombres_i = grupo, []
        orden = ORDEN_SERIE[g.group(1)]
        for ser in de_intervalo:
            h = hijos(ser)
            poner(h, orden, "spPr", f'<c:spPr><a:ln w="{ANCHO_LINEA_SERIE}"><a:noFill/></a:ln></c:spPr>')
            poner(h, orden, "marker", MARCADOR_INTERVALO)
            nueva = "<c:ser>" + "".join(t for _, t in h) + "</c:ser>"

            def barra(m):
                b = hijos(m.group(0))
                poner(b, ORDEN_ERRBARS, "noEndCap", '<c:noEndCap val="1"/>')
                poner(b, ORDEN_ERRBARS, "spPr", f"<c:spPr>{LINEA_INTERVALO}</c:spPr>")
                return "<c:errBars>" + "".join(t for _, t in b) + "</c:errBars>"
            nueva = re.sub(r'<c:errBars>.*?</c:errBars>', barra, nueva, flags=re.S)
            nuevo = nuevo.replace(ser, nueva, 1)
            extremos.add(idx_serie(ser))
            nombres_i.append(nombre_serie(ser))
        xml = xml.replace(grupo, nuevo, 1)
        detalle.append("intervalo con barras de error: barra negra de 1 pt (remate plano, unión en ángulo, sin remates "
                       "propios); " + ", ".join(f"«{n}»" for n in dict.fromkeys(nombres_i))
                       + " (extremos): marcador raya negro de 7 pt, sin línea")
    return xml, detalle, extremos


ORDEN_ERRBARS = ["errDir", "errBarType", "errValType", "noEndCap", "plus", "minus", "val", "spPr", "extLst"]


def es_sombreado(tipo, grupo, ser):
    """Serie que hace de sombreado (bandas de fondo, como las recesiones): áreas o columnas sin hueco cuyos
    datos son siempre el mismo valor o vacíos, con algún vacío."""
    if tipo not in ("areaChart", "barChart"):
        return False
    if tipo == "barChart":
        hueco = re.search(r'<c:gapWidth val="(\d+)"/>', grupo)
        if '<c:barDir val="bar"/>' in grupo or not hueco or int(hueco.group(1)) > 50 or es_divisoria(ser):
            return False
    val = re.search(r'<c:val>.*?</c:val>', ser, re.S)
    total = val and re.search(r'<c:ptCount val="(\d+)"', val.group(0))
    if not total or int(total.group(1)) < 5:
        return False
    llenos = [float(v) for v in re.findall(r'<c:v>([^<]*)</c:v>', val.group(0))
              if re.fullmatch(r'-?[\d.]+(E-?\d+)?', v.strip(), re.I) and float(v) != 0]
    return 2 <= len(llenos) < int(total.group(1)) and len({round(v, 9) for v in llenos}) == 1


def sombreados(xml, color):
    """Series de sombreado con el color de la publicación (matiz 1), sin borde; sin transparencia, o al 80 %
    si quedan por encima de otras barras o áreas. Devuelve el xml, el detalle y sus idx."""
    detalle, hechos = [], set()
    if not color:
        return xml, detalle, hechos
    grupos = list(GRUPOS.finditer(xml))
    ejes = {valor(re.search(r'<c:axId\b[^>]*/>', e.group(0)).group(0)): e.group(0) for e in EJES.finditer(xml)}

    def capa(g):
        derecha = any('<c:axPos val="r"/>' in ejes.get(i, "") for i in re.findall(r'<c:axId val="(\d+)"/>', g.group(0)))
        return (1 if derecha else 0, 0 if g.group(1) == "areaChart" else 1)

    for g in grupos:
        for ser in re.findall(r'<c:ser>.*?</c:ser>', g.group(0), re.S):
            if not es_sombreado(g.group(1), g.group(0), ser):
                continue
            # ¿Tapa otras barras o áreas? (Excel pinta primero las áreas, luego las columnas, y el eje
            # secundario encima; entre grupos iguales, en el orden del archivo, y dentro de un grupo, en su orden)
            tapa = False
            for g2 in grupos:
                if g2.group(1) not in ("areaChart", "barChart"):
                    continue
                for otra in re.findall(r'<c:ser>.*?</c:ser>', g2.group(0), re.S):
                    if otra == ser or es_sombreado(g2.group(1), g2.group(0), otra):
                        continue
                    if (capa(g2) < capa(g) or (capa(g2) == capa(g) and g2.start() < g.start())
                            or (g2.start() == g.start() and g.group(0).index(otra) < g.group(0).index(ser))):
                        tapa = True
            alfa = f'<a:alpha val="{(100 - TRANSPARENCIA_SOMBREADO) * 1000}"/>' if tapa else ""
            sppr = (f'<c:spPr><a:solidFill><a:srgbClr val="{color}">{alfa}</a:srgbClr></a:solidFill>'
                    '<a:ln><a:noFill/></a:ln></c:spPr>')
            h = hijos(ser)
            poner(h, ORDEN_SERIE[g.group(1)], "spPr", sppr)
            if g.group(1) == "barChart":
                poner(h, ORDEN_SERIE["barChart"], "invertIfNegative", '<c:invertIfNegative val="0"/>')
            xml = xml.replace(ser, "<c:ser>" + "".join(t for _, t in h) + "</c:ser>", 1)
            hechos.add(idx_serie(ser))
            detalle.append(f"«{nombre_serie(ser)}» (sombreado): color de la publicación {color}, sin borde, "
                           + (f"transparencia {TRANSPARENCIA_SOMBREADO} % (queda por encima de otros datos)" if tapa
                              else "sin transparencia"))
    return xml, detalle, hechos


def sombreados_dibujados(formas, color):
    """Rectángulos rellenos y sin texto dibujados dentro del gráfico: sombreados. Van siempre por encima del
    trazado, así que con el color de la publicación al 80 % de transparencia y sin borde."""
    hechos = []
    if not color:
        return formas, hechos

    def forma(m):
        a = m.group(0)
        if "<cdr:sp " not in a and "<cdr:sp>" not in a:
            return a
        if not re.search(r'prst="rect"', a) or re.search(r'<a:t>[^<]*\S', a):
            return a
        sppr = re.search(r'<cdr:spPr\b.*?</cdr:spPr>', a, re.S)
        if not sppr or not re.search(r'<a:solidFill\b', re.sub(r'<a:ln\b.*?</a:ln>', '', sppr.group(0), flags=re.S)):
            return a
        A = 'xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"'
        nuevo = re.sub(r'<a:(solidFill|gradFill|pattFill)\b[^>]*>.*?</a:\1>(?=(?:(?!<a:ln\b).)*?(<a:ln\b|</cdr:spPr>))',
                       '', sppr.group(0), count=1, flags=re.S)
        nuevo = re.sub(r'<a:ln\b[^>]*/>|<a:ln\b.*?</a:ln>', '', nuevo, flags=re.S)
        geom = re.search(r'</a:prstGeom>', nuevo)
        relleno = (f'<a:solidFill {A}><a:srgbClr val="{color}"><a:alpha val="{(100 - TRANSPARENCIA_SOMBREADO) * 1000}"/>'
                   f'</a:srgbClr></a:solidFill><a:ln {A}><a:noFill/></a:ln>')
        nuevo = nuevo[:geom.end()] + relleno + nuevo[geom.end():] if geom else nuevo
        hechos.append(re.search(r'name="([^"]*)"', a).group(1) if 'name="' in a else "rectángulo")
        return a.replace(sppr.group(0), nuevo, 1)

    formas = re.sub(r'<cdr:(relSizeAnchor|absSizeAnchor)\b.*?</cdr:\1>', forma, formas, flags=re.S)
    return formas, hechos


def series_de_grafico(xml, excluir=()):
    """Las series en el orden de los colores (guía, pág. 7): primero las líneas, luego áreas y barras (de
    izquierda a derecha o desde el eje hacia arriba: el orden de las series) y al final los marcadores."""
    borradas = {int(i) for i in re.findall(r'<c:legendEntry><c:idx val="(\d+)"/><c:delete val="1"/>', xml)}
    ocultas = {t for k, t in enumerate(orden_leyenda(xml)) if k in borradas}
    grupos = []
    for g in GRUPOS.finditer(xml):
        tipo = g.group(1)
        for s in re.finditer(r'<c:ser>.*?</c:ser>', g.group(0), re.S):
            ser = s.group(0)
            clase = None if idx_serie(ser) in excluir else clase_serie(tipo, ser, '<c:scatterStyle val="marker"/>' in g.group(0))
            # Series sin ningún dato (el autor dejó el rango vacío, «Línea 4» del 1.12): no se ven, no cuentan
            valores = re.search(r'<c:(?:val|yVal)>.*?</c:(?:val|yVal)>', ser, re.S)
            if clase and valores and not re.search(r'<c:pt idx="\d+">\s*<c:v>[^<]+</c:v>', valores.group(0)):
                clase = None
            # El orden escrito en el gráfico, que es el que sigue Excel (G_IA2025_1.33 panel a: «order» no coincide)
            orden = len(grupos)
            # Barras apiladas con parte positiva y negativa: primero las que suben desde el eje y luego las que bajan
            # (G_IA2025_1.27, petición del usuario, 2026-11-26: como en el .ai)
            apilado = re.search(r'<c:grouping val="(?:stacked|percentStacked)"/>', g.group(0))
            vals = numeros(re.search(r'<c:val>.*?</c:val>', ser, re.S).group(0)) if "<c:val>" in ser else []
            abajo = 1 if apilado and vals and sum(v < 0 for v in vals) > sum(v > 0 for v in vals) else 0
            grupos.append({"tipo": tipo, "ser": ser, "clase": clase, "orden": orden, "oculta": ser in ocultas, "abajo": abajo,
                           "apilado": bool(apilado)})
    peso = {"linea": 0, "trama": 1, "marcador": 2}
    # Las series ocultas en la leyenda se ven en el gráfico: líneas y tramas llevan su estilo en el orden de la guía
    # (G_IA2025_1.22, panel b: «Total», oculta en la leyenda, se quedaba con el naranja de Excel y la guía la pone
    # negra). Los marcadores ocultos siguen aparte (gemelos de otro visible, intervalos)
    usadas = [s for s in grupos if s["clase"] and (not s["oculta"] or s["clase"] != "marcador")]
    usadas.sort(key=lambda s: (peso[s["clase"]], 0 if s["tipo"] == "areaChart" else 1, s["abajo"], s["orden"]))
    return usadas, [s for s in grupos if s["clase"] == "marcador" and s["oculta"]]


def luminancia(hexa):
    r, g, b = (int(hexa[i:i + 2], 16) / 255 for i in (0, 2, 4))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


TRAMAS_CON_ETIQUETA_BLANCA = {"7DB749"}   # además de las oscuras: la verde de la guía


def etiquetas_claras(ser, estilo, apilado=False):
    """Etiquetas dentro de una barra con trama oscura (la negra de la guía): en blanco, que en negro no se leen
    (G_IA2025_1.27, petición del usuario, 2026-11-26). Las de fuera de la barra («outEnd») siguen en negro. Devuelve
    (serie, ¿cambiada?)."""
    _, frente, fondo = estilo["trama"]
    # También sobre la trama verde de la guía (7DB749; petición del usuario, 2026-11-27, G_MemoriaSupervision_7.3)
    if (luminancia(frente) + luminancia(fondo)) / 2 >= 0.4 and frente.upper() not in TRAMAS_CON_ETIQUETA_BLANCA:
        return ser, False
    dl = re.search(r'<c:dLbls>.*?</c:dLbls>', ser, re.S)
    if not dl or 'showVal val="1"' not in dl.group(0):
        return ser, False
    # Dentro de la barra: centro o extremos interiores; sin posición, Excel las pone dentro solo en las apiladas (en
    # las agrupadas, encima: en blanco no se verían, 3.6 panel b)
    pos = re.search(r'<c:dLblPos val="(\w+)"/>', re.sub(r'<c:dLbl>.*?</c:dLbl>', "", dl.group(0), flags=re.S))
    if not (pos.group(1) in ("ctr", "inEnd", "inBase") if pos else apilado):
        return ser, False
    nuevo = re.sub(r'(<a:defRPr\b[^>]*>\s*<a:solidFill>)\s*<a:srgbClr val="[0-9A-Fa-f]{6}"/>',
                   r'\1<a:srgbClr val="FFFFFF"/>', dl.group(0))
    if nuevo == dl.group(0):
        return ser, False
    return ser.replace(dl.group(0), nuevo, 1), True


def con_estilo(s, estilo):
    """La serie con el estilo que le toca."""
    tipo, ser, clase = s["tipo"], s["ser"], s["clase"]
    h = hijos(ser)
    orden = ORDEN_SERIE[tipo]
    color = estilo["linea"][0]
    if clase == "trama":
        poner(h, orden, "spPr", sppr_trama(estilo))
        if tipo.startswith("bar"):
            poner(h, orden, "invertIfNegative", '<c:invertIfNegative val="0"/>')   # si no, los negativos salen en blanco
    elif clase == "linea":
        poner(h, orden, "spPr", sppr_linea(estilo))
        _, _, simbolo, tamano = estilo["linea"]
        poner(h, orden, "marker", marcador(simbolo, tamano, color))
    else:
        poner(h, orden, "spPr", f'<c:spPr><a:ln w="{ANCHO_LINEA_SERIE}"><a:noFill/></a:ln></c:spPr>')
        forma = forma_marcador(ser)[0]
        poner(h, orden, "marker", marcador(forma, tamano_marcador(forma), color))
    return "<c:ser>" + "".join(t for _, t in h) + "</c:ser>"


def puntos_tarta(ser, tipo, estilos):
    """Cada sector con la trama que le toca, en el orden de la leyenda (las categorías). Los sectores a 0 (o sin
    dato) no se ven y no gastan estilo: la secuencia sigue con el siguiente que se ve, como en el .ai
    (G_MemoriaSupervision_3.1: en el panel a «Negocio» vale 0 y «Capital» va en negro; petición del usuario,
    2026-11-27). Devuelve la serie, el número de sectores y los que valen 0."""
    h = hijos(ser)
    val = hijo(h, "val") or ""
    m = re.search(r'<c:ptCount val="(\d+)"', val)
    n = int(m.group(1)) if m else 0
    datos = {int(i): v for i, v in re.findall(r'<c:pt idx="(\d+)">\s*<c:v>([^<]*)</c:v>', val)}
    def vale_cero(k):
        try:
            return abs(float(datos.get(k, "0"))) < 1e-12
        except ValueError:
            return True
    # Sin ningún dato guardado (caché vacía: el 1.2) no se sabe cuánto vale cada sector: no se salta ninguno
    ceros = [k for k in range(n) if vale_cero(k)] if datos else []
    viejos = {valor(hijo(hijos(t), "idx")): t for nombre, t in h if nombre == "dPt"}
    h = [x for x in h if x[0] != "dPt"]
    nuevos, siguiente = [], 0
    for k in range(n):
        dpt = hijos(viejos[str(k)]) if str(k) in viejos else [["idx", f'<c:idx val="{k}"/>'], ["bubble3D", '<c:bubble3D val="0"/>']]
        poner(dpt, ORDEN_DPT, "spPr", sppr_trama(estilos[siguiente % len(estilos)]))
        if k not in ceros:
            siguiente += 1
        nuevos.append("<c:dPt>" + "".join(t for _, t in dpt) + "</c:dPt>")
    orden = ORDEN_SERIE[tipo]
    pos = next((i for i, x in enumerate(h) if x[0] in orden and orden.index(x[0]) > orden.index("dPt")), len(h))
    h[pos:pos] = [["dPt", d] for d in nuevos]
    return "<c:ser>" + "".join(t for _, t in h) + "</c:ser>", n, ceros


def puntos_serie(ser):
    val = re.search(r'<c:(?:val|yVal)>.*?</c:(?:val|yVal)>', ser, re.S)
    m = val and re.search(r'<c:ptCount val="(\d+)"', val.group(0))
    return int(m.group(1)) if m else 0


def ancho_trazado(xml, ancho_grafico):
    """Ancho del área de trazado en pt: el del gráfico por el del diseño manual del trazado, si lo tiene."""
    plot = re.search(r'<c:plotArea>.*?<c:layout>(.*?)</c:layout>', xml, re.S)
    w = plot and re.search(r'<c:w val="([^"]+)"', plot.group(1))
    return ancho_grafico * (float(w.group(1)) if w else 0.85)


def espaciar_marcadores(ser, tipo, cada, desfase):
    """El marcador queda en la serie (así sale en la leyenda) y se quita, con un dPt, en los puntos que no
    tocan: solo lo llevan los puntos desfase, desfase + cada, … Los dPt del autor se respetan."""
    h = hijos(ser)
    n = puntos_serie(ser)
    propios = {valor(hijo(hijos(t), "idx")) for nombre, t in h if nombre == "dPt"}
    nuevos = [f'<c:dPt><c:idx val="{k}"/><c:marker><c:symbol val="none"/></c:marker><c:bubble3D val="0"/></c:dPt>'
              for k in range(n) if (k - desfase) % cada and str(k) not in propios]
    orden = ORDEN_SERIE[tipo]
    pos = max((i + 1 for i, x in enumerate(h) if x[0] in orden and orden.index(x[0]) <= orden.index("dPt")), default=0)
    h[pos:pos] = [["dPt", d] for d in nuevos]
    return "<c:ser>" + "".join(t for _, t in h) + "</c:ser>", (n - desfase + cada - 1) // cada


def es_promedio(nombre):
    """Leyenda de un promedio, una media o una tendencia de otra serie («Promedio 1996-2019», «Media 2000-2019»,
    «Tendencia España», «Average»); no las medias móviles, que son datos (G_IA2025_1.35 a y 3.1 b, peticiones del
    usuario, 2026-11-26: que la app avise)."""
    n = nombre.lower()
    if re.search(r'\bmedias?\s+m[oó]vil(es)?\b|\bmoving\s+averages?\b', n):
        return False
    return bool(re.search(r'\b(promedios?|medias?|averages?|mean|tendencias?|trends?)\b', n))


def tramas_y_lineas(xml, estilos, ancho_grafico=None, color_publicacion=None, fijos=None):
    """Aplica los estilos de la guía a las series de un gráfico. Devuelve el xml y las líneas del detalle.
    `fijos`: {nombre de serie: número de estilo} de los paneles anteriores; la serie que se llame igual lleva el mismo
    estilo y las demás se reparten los libres (petición del usuario, 2026-11-26, G_IA2025_1.12). Se completa aquí."""
    detalle = []
    tarta = re.search(r'<c:(pieChart|doughnutChart)>.*?</c:\1>', xml, re.S)
    if tarta:
        tipo = tarta.group(1)
        g = tarta.group(0)
        s = re.search(r'<c:ser>.*?</c:ser>', g, re.S)
        if not s:
            return xml, ["sin series"]
        nuevo, n, ceros = puntos_tarta(s.group(0), tipo, estilos)
        xml = xml.replace(g, g.replace(s.group(0), nuevo, 1), 1)
        visibles = n - len(ceros)
        detalle.append(f"{visibles} sectores con las tramas 1 a {min(visibles, len(estilos))}, en el orden de la leyenda")
        if ceros:
            cats = etiquetas_categorias(xml)
            nombres_c = ", ".join(f"«{cats[k]}»" if k < len(cats) else f"n.º {k + 1}" for k in ceros)
            # Fuera también de la leyenda: no se ven y su muestra repetiría el color del siguiente
            leyenda = re.search(r'<c:legend>.*?</c:legend>', xml, re.S)
            if leyenda:
                ya = set(re.findall(r'<c:legendEntry><c:idx val="(\d+)"/>', leyenda.group(0)))
                entradas = "".join(f'<c:legendEntry><c:idx val="{k}"/><c:delete val="1"/></c:legendEntry>'
                                   for k in ceros if str(k) not in ya)
                nueva_l = re.sub(r'(<c:legendPos\b[^>]*/>)', lambda m: m.group(1) + entradas, leyenda.group(0), count=1)
                xml = xml.replace(leyenda.group(0), nueva_l, 1)
            detalle.append(f"Aviso: sectores a 0 ({nombres_c}): no se ven y no gastan color (la secuencia sigue con el "
                           "siguiente, como en el .ai)" + ("; fuera de la leyenda" if leyenda else ""))
        if n > MAXIMO_ESTILOS:
            detalle.append(f"Aviso: {n} sectores; la guía tiene {MAXIMO_ESTILOS} tramas (y recomienda 5): a partir "
                           f"del {MAXIMO_ESTILOS + 1}.º se repiten. Consultar con la unidad de edición y publicaciones")
        return xml, detalle
    xml, det_intervalos, extremos = intervalos(xml)
    xml, det_sombreados, sombras = sombreados(xml, color_publicacion)
    detalle += det_intervalos + det_sombreados
    usadas, ocultas = series_de_grafico(xml, extremos | sombras)
    if not usadas:
        return xml, detalle or ["sin series que formatear"]
    # Número de estilo de cada serie: primero las que ya lo tienen por otro panel (mismo nombre), después las demás
    # en el orden de la guía, con los libres
    fijos = {} if fijos is None else fijos
    # (mismo nombre y mismo tipo: en el 1.22, «Total» son marcadores en el panel a y una línea en el b)
    clave = lambda ser: (re.sub(r"\s+", " ", nombre_serie(ser)).strip().lower(),
                         next((u["clase"] for u in usadas if u["ser"] == ser), None))
    numero, ocupados = {}, set()
    for k, s in enumerate(usadas):
        if clave(s["ser"]) in fijos and fijos[clave(s["ser"])] not in ocupados:
            numero[k] = fijos[clave(s["ser"])]
            ocupados.add(numero[k])
    siguiente = 0
    for k, s in enumerate(usadas):
        if k in numero:
            continue
        while siguiente in ocupados or (
                # En un intervalo, los marcadores van sobre la línea negra: no pueden ser negros
                extremos and s["clase"] == "marcador" and estilos[siguiente % len(estilos)]["linea"][0] == "000000"):
            siguiente += 1
        numero[k] = siguiente
        ocupados.add(siguiente)
        siguiente += 1
    for k, s in enumerate(usadas):
        fijos.setdefault(clave(s["ser"]), numero[k])
    con_marcador = [k for k, s in enumerate(usadas)
                    if s["clase"] == "linea" and estilos[numero[k] % len(estilos)]["linea"][2]]
    espaciados, gemelos = [], {}
    for k, s in enumerate(usadas):
        estilo = estilos[numero[k] % len(estilos)]
        limpia, n_puntos = puntos_como_su_serie(s["ser"])
        if n_puntos:
            detalle.append(f"«{nombre_serie(s['ser'])}»: {n_puntos} punto{'s' if n_puntos > 1 else ''} con el mismo "
                           "color que su serie: sin ese formato, para que lleven la trama de la serie")
        if s["clase"] == "marcador":
            gemelos[firma_marcador(s["ser"])] = estilo
        original = s["ser"]
        s = {**s, "ser": limpia}
        nueva = con_estilo(s, estilo)
        recta = s["clase"] == "linea" and es_recta_referencia(s["tipo"], s["ser"])
        if recta:
            nueva = nueva.replace(f'<a:ln w="{ANCHO_LINEA_SERIE}"', f'<a:ln w="{ANCHO_RECTA_REFERENCIA}"', 1)
            nueva = re.sub(r'<c:marker>.*?</c:marker>', marcador(None, 0, None), nueva, count=1, flags=re.S)
        if s["clase"] == "trama":
            nueva, claras = etiquetas_claras(nueva, estilo, s.get("apilado", False))
            if claras:
                detalle.append(f"«{nombre_serie(s['ser'])}»: etiquetas en blanco, dentro de la trama (negra o verde)")
        n = puntos_serie(s["ser"])
        if k in con_marcador and ancho_grafico and n > 1:
            caben = max(2, int(ancho_trazado(xml, ancho_grafico) / ESPACIO_MARCADORES) + 1)
            if n > caben:
                cada = math.ceil((n - 1) / (caben - 1))
                desfase = round(cada * con_marcador.index(k) / len(con_marcador))
                nueva, quedan = espaciar_marcadores(nueva, s["tipo"], cada, desfase)
                espaciados.append(f"«{nombre_serie(s['ser'])}»: {quedan} marcadores, uno cada {cada} puntos")
        xml = xml.replace(original, nueva, 1)
        que = {"linea": "línea", "trama": "trama", "marcador": "marcador"}[s["clase"]]
        if s["clase"] == "marcador":
            forma, auto = forma_marcador(original)
            tam = tamano_marcador(forma)
            descripcion = (f"{NOMBRES_MARCADOR.get(forma, forma)} de {tam} pt {estilo['linea'][0]} (la forma del autor"
                           + (", la automática de Excel)" if auto else ")"))
            del_autor = tamano_del_autor(original)
            if del_autor and del_autor != tam:
                detalle.append(f"Aviso: «{nombre_serie(s['ser'])}»: marcador de ⟪{tam} pt⟫ (el autor lo tenía de "
                               f"{del_autor} pt)")
        elif recta:
            descripcion = f"recta de referencia: sólida {estilo['linea'][0]}, 1 pt, sin marcadores"
        elif s["clase"] == "linea":
            descripcion = estilo["nombre"].split(" / ")[1] + f" {estilo['linea'][0]}, 2,25 pt"
        else:
            descripcion = estilo["nombre"].split(" / ")[0]
        detalle.append(f"{k + 1}. «{nombre_serie(s['ser'])}» ({que}): {descripcion}")
        if s["clase"] == "linea" and es_promedio(nombre_serie(s["ser"])):
            detalle.append(f"Aviso: «{nombre_serie(s['ser'])}» es un ⟪promedio, una media o una tendencia⟫ de otra serie: por norma va "
                           "discontinua y del color de la serie a la que se refiere; la app le ha dado el estilo que "
                           "le toca en la secuencia: revisarla y cambiarla a mano si es el caso")
    if espaciados:
        detalle.append("Marcadores espaciados para que no se agolpen (como mucho uno cada 4 mm): " + "; ".join(espaciados))
    for s in ocultas:
        # Marcadores ocultos en la leyenda iguales a uno visible (mismo símbolo y color del autor): con su mismo
        # estilo, para que en el panel no haya dos marcadores distintos para lo mismo («G_DO2608_01», 1.b)
        estilo = gemelos.get(firma_marcador(s["ser"])) if s["clase"] == "marcador" else None
        if estilo:
            xml = xml.replace(s["ser"], con_estilo(s, estilo), 1)
            detalle.append(f"«{nombre_serie(s['ser'])}» oculta en la leyenda: el mismo marcador que la serie visible "
                           "que tenía el mismo marcador")
        else:
            detalle.append(f"«{nombre_serie(s['ser'])}» oculta en la leyenda: sin tocar")
    if len(usadas) > MAXIMO_ESTILOS:
        detalle.append(f"Aviso: {len(usadas)} series; la guía tiene {MAXIMO_ESTILOS} estilos (y recomienda 5): a partir "
                       f"de la {MAXIMO_ESTILOS + 1}.ª se repiten. Consultar con la unidad de edición y publicaciones")
    con_puntos = [nombre_serie(s["ser"]) for s in usadas
                  if any("<c:spPr>" in d or "<c:marker>" in d for d in re.findall(r'<c:dPt>.*?</c:dPt>', puntos_como_su_serie(s["ser"])[0], re.S))]
    if con_puntos:
        detalle.append("Aviso: " + ", ".join(f"«{n}»" for n in con_puntos) + " tiene puntos con formato propio del "
                       "autor: no se han tocado, revisar a mano")
    return xml, detalle


def color_solido(sppr):
    """Color del relleno sólido de un spPr (sin la línea), o None."""
    relleno = re.sub(r'<a:ln\b.*?</a:ln>|<a:ln\b[^>]*/>', "", sppr or "", flags=re.S)
    m = re.search(r'<a:solidFill>\s*<a:srgbClr val="([0-9A-Fa-f]{6})"\s*/?>', relleno)
    return m.group(1).upper() if m else None


def puntos_como_su_serie(ser):
    """Quita el formato de los puntos (dPt) que solo repiten el color de relleno de su serie (el autor los pintó
    a mano con el mismo color): así llevan la trama nueva de la serie. Devuelve (serie, puntos limpiados)."""
    propio = color_solido(hijo(hijos(ser), "spPr"))
    if not propio:
        return ser, 0
    limpiados = 0

    def limpiar(m):
        nonlocal limpiados
        d = m.group(0)
        sppr = re.search(r'<c:spPr>(.*?)</c:spPr>', d, re.S)
        if not sppr or color_solido(sppr.group(1)) != propio:
            return d
        resto = re.sub(r'<a:solidFill>.*?</a:solidFill>', "", sppr.group(1), count=1, flags=re.S)
        if re.sub(r'<a:ln\b[^>]*>\s*<a:noFill/>\s*</a:ln>|\s', "", resto):
            return d   # lleva algo más (borde…): se deja
        limpiados += 1
        return d.replace(sppr.group(0), "", 1)
    return re.sub(r'<c:dPt>.*?</c:dPt>', limpiar, ser, flags=re.S), limpiados


def firma_marcador(ser):
    """(símbolo, color) del marcador del autor: para reconocer series de marcadores que son lo mismo."""
    marcador = hijo(hijos(ser), "marker") or ""
    simbolo = re.search(r'<c:symbol val="(\w+)"', marcador)
    color = color_solido(re.search(r'<c:spPr>(.*?)</c:spPr>', marcador, re.S).group(1)) if "<c:spPr>" in marcador else None
    return (simbolo.group(1) if simbolo else None, color)


def separador_decimal_mac():
    """El separador decimal de la configuración del Mac (el que usa Excel si tiene «Usar separadores del
    sistema»), o None si no se puede leer."""
    try:
        r = subprocess.run(["osascript", "-e", 'use framework "Foundation"', "-e",
                            "return (current application's NSLocale's currentLocale()'s decimalSeparator()) as text"],
                           capture_output=True, text=True, timeout=10)
        return r.stdout.strip() or None
    except (OSError, subprocess.SubprocessError):
        return None


def aviso_separador_ingles(estado):
    """En inglés, aviso si el Mac pone coma decimal: Excel la usa en etiquetas y ejes y no se puede fijar desde
    el archivo (ningún formato de número lo cambia)."""
    if estado.get("idioma") != "en" or separador_decimal_mac() != ",":
        return []
    return ["Aviso: el gráfico es en inglés y el Mac usa la coma decimal: Excel muestra así las cifras (80,8% en "
            "vez de 80.8%). Cámbialo a mano antes de revisar o exportar: Ajustes del Sistema > General > Idioma y "
            "región > Formato de número «1,234,567.89» (y en Excel, Preferencias > Edición, «Usar separadores del "
            "sistema» activado). Vuelve a dejarlo como estaba al acabar."]


TRAMAS_COLORES_LINEAS = "Tramas, colores y líneas"


def paso5(trabajo, pid=None):
    """Tramas, colores y tipos de línea de las series («Excel. Guía líneas y tramas colores 2026», en el orden de
    la guía de gráficos, pág. 7): primero las líneas, luego las barras y áreas y al final los marcadores."""
    estado = leer_estado(trabajo)
    _, pasos = nombres(trabajo)
    base = pasos / estado["pasos"][estado["actual"]]["archivo"]
    requiere(estado, (LINEAS_INTERIORES, "Línea base"), "«Tramas, colores y líneas»")
    tema = publicacion(pid).get("tema") if pid else "BdE_2026"
    estilos = ESTILOS_SERIES.get(tema)
    if not estilos:
        raise Fallo(f"La paleta «{tema}» de la publicación todavía no tiene definidos sus tramas y estilos de línea")
    cambios, detalle = {}, []
    with zipfile.ZipFile(base) as z:
        ruta = dibujo_de_hoja(z, HOJA_GRAFICO)
        dibujo = z.read(ruta).decode("utf-8")
        relaciones = rels(z, ruta)
        partes = list(partes_dibujo(dibujo))
        caja = medidas_hoja(z, dibujo)
        graficos = sorted((caja(a)[1], re.search(r'<c:chart\b[^>]*\br:id="([^"]+)"', a).group(1), caja(a)[2] / EMU_PT)
                          for a in partes if ANCLA.fullmatch(a) and "<c:chart " in a)
        # Color de los sombreados: el de la publicación (si no llega, el de la pastilla que puso el paso 1)
        color = publicacion(pid).get("color") if pid else None
        if not color:
            pas = next((a for a in partes if re.search(r'name="Pastilla', a)), "")
            m = re.search(r'<a:solidFill><a:srgbClr val="([0-9A-Fa-f]{6})"', pas)
            color = m.group(1).upper() if m else None
        fijos = {}   # mismo nombre de serie, mismo estilo en todos los paneles
        for n, (_, rid, ancho) in enumerate(graficos, 1):
            ruta_graf = relaciones[rid][1]
            xml, lineas = tramas_y_lineas(z.read(ruta_graf).decode("utf-8"), estilos, ancho, color, fijos)
            cambios[ruta_graf] = xml.encode("utf-8")
            for t, ruta_formas in rels(z, ruta_graf).values():
                if t.endswith("/chartUserShapes"):
                    formas, hechos = sombreados_dibujados(z.read(ruta_formas).decode("utf-8"), color)
                    if hechos:
                        cambios[ruta_formas] = formas.encode("utf-8")
                        lineas.append(", ".join(f"«{h}»" for h in hechos) + f" (sombreado dibujado): color de la "
                                      f"publicación {color}, transparencia {TRANSPARENCIA_SOMBREADO} %, sin borde")
            detalle += [(l if l.startswith("Aviso") else f"Panel {n}: {l}") for l in lineas]
    detalle.append(f"Estilos de la paleta {tema} («Excel. Guía líneas y tramas colores 2026»); tramas sin borde; "
                   "líneas de 2,25 pt; orden de la guía de gráficos, pág. 7")
    detalle += aviso_separador_ingles(estado)
    return nuevo_paso(trabajo, TRAMAS_COLORES_LINEAS, cambios, detalle)

# ---------------------------------------------------------------- herramienta: sin eje vertical

SIN_EJE_VERTICAL = "Sin eje vertical, valor sobre cada barra"
AIRE_TRAZADO_SIN_EJE = 1.0   # del borde del marco al trazado sin eje vertical (pt; en el TERMINADO, casi pegado)


def quitar_eje_vertical(xml):
    """Barras verticales sin eje vertical (como «G_DO26XX_04 TERMINADO ORIGINAL»): el eje de valores se borra
    (sin líneas de división ni marcas) y cada barra lleva encima su valor, fuera al final, a 6 pt. Devuelve
    (xml, notas, hecho)."""
    notas = []
    grupos = [g for g in GRUPOS.finditer(xml) if g.group(1) in TIPOS_BARRAS and not es_horizontal(g.group(0))]
    if not grupos:
        return xml, ["no tiene barras verticales: sin tocar"], False
    apiladas = [g for g in grupos if re.search(r'<c:grouping val="(stacked|percentStacked)"/>', g.group(0))]
    if apiladas:
        return xml, ["Aviso: barras apiladas: Excel no deja poner el valor «fuera, al final» de cada tramo; "
                     "sin tocar"], False
    # Ejes de valores verticales a la vista: borrados, sin líneas de división ni marcas
    def eje(m):
        a = m.group(0)
        if not re.search(r'<c:axPos val="[lr]"/>', a) or '<c:delete val="1"/>' in a:
            return a
        a = re.sub(r'<c:(major|minor)Gridlines\b.*?</c:\1Gridlines>|<c:(major|minor)Gridlines/>', "", a, flags=re.S)
        a = re.sub(r'<c:delete val="\w+"/>', '<c:delete val="1"/>', a, count=1)
        a = re.sub(r'<c:majorTickMark val="\w+"/>', '<c:majorTickMark val="none"/>', a, count=1)
        notas.append("eje vertical borrado, sin líneas de división ni marcas")
        return a
    xml = re.sub(r'<c:valAx>.*?</c:valAx>', eje, xml, flags=re.S)
    # Cada serie de barras, con su valor encima
    etiquetas = ('<c:dLbls><c:spPr><a:noFill/><a:ln><a:noFill/></a:ln></c:spPr><c:txPr><a:bodyPr/><a:lstStyle/>'
                 f'<a:p><a:pPr><a:defRPr sz="600" b="0">{NEGRO}<a:latin typeface="{ROBOTO}"/><a:ea typeface="{ROBOTO}"/>'
                 '</a:defRPr></a:pPr><a:endParaRPr lang="es-ES"/></a:p></c:txPr><c:dLblPos val="outEnd"/>'
                 '<c:showLegendKey val="0"/><c:showVal val="1"/><c:showCatName val="0"/><c:showSerName val="0"/>'
                 '<c:showPercent val="0"/><c:showBubbleSize val="0"/></c:dLbls>')
    con = []
    for g in grupos:
        bloque = g.group(0)
        nuevo = bloque
        for ser in re.findall(r'<c:ser>.*?</c:ser>', bloque, re.S):
            if es_divisoria(ser) or es_muestra(ser) or clase_serie(g.group(1), ser) is None:
                continue
            # Los decimales de los datos del autor, con separador de miles (como en el TERMINADO: 0,33 y 29,67)
            cache = re.search(r'<c:val>.*?<c:formatCode>([^<]*)</c:formatCode>', ser, re.S)
            d = re.search(r'\.(0+)', html.unescape(cache.group(1))) if cache else None
            pct = "%" if cache and "%" in cache.group(1) else ""
            codigo = "#,##0" + ("." + d.group(1) if d else "") + pct
            h = hijos(ser)
            poner(h, ORDEN_SERIE[g.group(1)], "dLbls",
                  etiquetas.replace("<c:dLbls>", f'<c:dLbls><c:numFmt formatCode="{codigo}" sourceLinked="0"/>', 1))
            nuevo = nuevo.replace(ser, "<c:ser>" + "".join(t for _, t in h) + "</c:ser>", 1)
            con.append(nombre_serie(ser))
        xml = xml.replace(bloque, nuevo, 1)
    notas.append("valor sobre cada barra (fuera, al final; Roboto 6 pt; con los decimales de los datos): "
                 + ", ".join(f"«{c}»" for c in con))
    # Líneas o áreas a la vista (no la línea base ni la serie invisible de la leyenda)
    otras = [ser for g in GRUPOS.finditer(xml) if g.group(1) in ("lineChart", "scatterChart", "areaChart")
             for ser in re.findall(r'<c:ser>.*?</c:ser>', g.group(0), re.S)
             if clase_serie(g.group(1), ser, '<c:scatterStyle val="marker"/>' in g.group(0))]
    if otras:
        notas.append("Aviso: el gráfico tiene también líneas o áreas: sin eje vertical, comprueba que se entienden")
    return xml, notas, True


def separar_etiquetas_barras(xml, W, H, medir):
    """Barras agrupadas con el valor encima: si dos etiquetas vecinas de la misma categoría quedan a casi la
    misma altura y se tocan (las barras son más estrechas que los números), se apartan en horizontal lo justo,
    cada una hacia su lado (como en el TERMINADO). Devuelve (xml, etiquetas movidas)."""
    t = trazado_rel(xml)
    grupo = next((g for g in GRUPOS.finditer(xml) if g.group(1) in TIPOS_BARRAS and not es_horizontal(g.group(0))), None)
    if not t or not grupo or not medir:
        return xml, 0
    series = [s for s in re.findall(r'<c:ser>.*?</c:ser>', grupo.group(0), re.S) if "<c:dLbls>" in s]
    if len(series) < 2:
        return xml, 0
    hueco = float(valor(re.search(r'<c:gapWidth val="[^"]+"/>', grupo.group(0)).group(0)) if '<c:gapWidth' in grupo.group(0) else 150)
    valores = []
    for s in series:
        val = re.search(r'<c:val>.*?</c:val>', s, re.S)
        valores.append({int(i): float(v) for i, v in re.findall(r'<c:pt idx="(\d+)"[^>]*>\s*<c:v>([^<]*)</c:v>', val.group(0) if val else "")
                        if re.fullmatch(r'-?[\d.]+(E[-+]?\d+)?', v, re.I)})
    ncat = max((max(v) + 1 for v in valores if v), default=0)
    if not ncat:
        return xml, 0
    eje = next((e.group(0) for e in re.finditer(r'<c:valAx>.*?</c:valAx>', xml, re.S) if re.search(r'<c:axPos val="[lr]"/>', e.group(0))), "")
    todos = [v for d in valores for v in d.values()]
    mx = re.search(r'<c:max val="([^"]+)"/>', eje)
    mn = re.search(r'<c:min val="([^"]+)"/>', eje)
    tope = float(mx.group(1)) if mx else max(todos) * 1.1
    base = float(mn.group(1)) if mn else min(0, min(todos))
    alto_trazado, ancho_trazado = t[3] * H, t[2] * W
    barra = ancho_trazado / ncat / (len(series) + hueco / 100)
    codigos = [re.search(r'<c:dLbls>.*?<c:numFmt formatCode="([^"]*)"', s, re.S) for s in series]
    desplaza = [dict() for _ in series]
    for c in range(ncat):
        presentes = [k for k in range(len(series)) if c in valores[k]]
        if len(presentes) < 2:
            continue
        def ancho(k):
            cod = html.unescape(codigos[k].group(1)) if codigos[k] else "General"
            d = re.search(r'\.(0+)', cod)
            texto = f"{valores[k][c]:,.{len(d.group(1)) if d else 0}f}"
            return medir(texto, 6) + 1
        # Centros de cada etiqueta, de izquierda a derecha; se empuja a la derecha lo que choca con la anterior
        centros = {k: k * barra for k in presentes}
        nuevos = dict(centros)
        for a, b in zip(presentes, presentes[1:]):
            dy = abs(valores[a][c] - valores[b][c]) * alto_trazado / (tope - base)
            if dy >= 6 * INTERLINEA:
                continue
            falta = (ancho(a) + ancho(b)) / 2 + 1 - (nuevos[b] - nuevos[a])
            if falta > 0:
                for k in presentes[presentes.index(b):]:
                    nuevos[k] += falta
        # El grupo, centrado otra vez sobre sus barras
        medio = sum(nuevos[k] - centros[k] for k in presentes) / len(presentes)
        for k in presentes:
            dx = nuevos[k] - centros[k] - medio
            if abs(dx) > 0.2:
                desplaza[k][c] = dx
    movidas = 0
    bloque = grupo.group(0)
    nuevo_bloque = bloque
    for k, s in enumerate(series):
        if not desplaza[k]:
            continue
        dl = re.search(r'<c:dLbls>.*?</c:dLbls>', s, re.S).group(0)
        general = [(n_, t_) for n_, t_ in hijos(dl) if n_ in ("numFmt", "spPr", "txPr", "dLblPos", "showLegendKey", "showVal",
                                                           "showCatName", "showSerName", "showPercent", "showBubbleSize")]
        propios = "".join(
            f'<c:dLbl><c:idx val="{c}"/><c:layout><c:manualLayout><c:x val="{dx / W:.6f}"/><c:y val="0"/></c:manualLayout>'
            '</c:layout>' + "".join(t_ for _, t_ in general) + '</c:dLbl>'
            for c, dx in sorted(desplaza[k].items()))
        nuevo_dl = dl.replace("<c:dLbls>", "<c:dLbls>" + propios, 1)
        nuevo_bloque = nuevo_bloque.replace(s, s.replace(dl, nuevo_dl, 1), 1)
        movidas += len(desplaza[k])
    return xml.replace(bloque, nuevo_bloque, 1), movidas


def sin_eje_vertical(trabajo, pid=None):
    """Herramienta (botón de la app): en los paneles de barras verticales, el eje vertical se quita y cada barra
    lleva su valor encima; el trazado se alarga hasta el principio de la columna (ya no hay números) y las
    unidades van a su borde izquierdo. Deja una versión nueva."""
    estado = leer_estado(trabajo)
    _, pasos = nombres(trabajo)
    base_archivo = pasos / estado["pasos"][estado["actual"]]["archivo"]
    requiere(estado, ("Tamaño y colocación",), f"«{SIN_EJE_VERTICAL}»")
    ret = CONFIG["reticula"]
    with zipfile.ZipFile(PROYECTO / ret["archivo"]) as zr:
        dibujo_ret = zr.read(dibujo_de_hoja(zr, ret["hoja"])).decode("utf-8")
    anclas_ret = {nombre_forma(a.group(0)): a.group(0) for a in ANCLA.finditer(dibujo_ret)}
    alto_pastilla = tamano(anclas_ret[ret["pastilla_modelo"]])[1]
    ancho_ret = tamano(anclas_ret[ret["grupo"]], escala_grupo=True)[0]
    cambios, detalle, hechos = {}, [], 0
    medir = medidor()
    with zipfile.ZipFile(base_archivo) as z:
        ruta = dibujo_de_hoja(z, HOJA_GRAFICO)
        dibujo = z.read(ruta).decode("utf-8")
        relaciones = rels(z, ruta)
        partes = list(partes_dibujo(dibujo))
        caja = medidas_hoja(z, dibujo)
        tipos = clasificar_textos(partes, caja, alto_pastilla, ancho_ret)
        graficos = sorted((caja(a)[1], i, re.search(r'<c:chart\b[^>]*\br:id="([^"]+)"', a).group(1))
                          for i, a in enumerate(partes) if ANCLA.fullmatch(a) and "<c:chart " in a)
        for n, (_, ig, rid) in enumerate(graficos, 1):
            ruta_graf = relaciones[rid][1]
            xml = z.read(ruta_graf).decode("utf-8")
            xml, notas, hecho = quitar_eje_vertical(xml)
            if not hecho:
                detalle += [(f"Aviso: panel {n}: " + t.split("Aviso: ", 1)[1]) if t.startswith("Aviso") else f"Panel {n}: {t}"
                            for t in notas]
                continue
            hechos += 1
            gx, gy, gw, gh = caja(partes[ig])
            W, H = gw / EMU_PT, gh / EMU_PT
            # El trazado empieza al principio de la columna: ya no hay números a la izquierda
            t = trazado_rel(xml)
            nuevo_x = AIRE_TRAZADO_SIN_EJE / W
            if t:
                fin = t[0] + t[2]
                xml = re.sub(r'(<c:plotArea>\s*<c:layout>\s*<c:manualLayout>.*?<c:x val=")[^"]+("/>.*?<c:w val=")[^"]+(")',
                             lambda m: f"{m.group(1)}{nuevo_x:.6f}{m.group(2)}{fin - nuevo_x:.6f}{m.group(3)}", xml,
                             count=1, flags=re.S)
            xml, movidas_et = separar_etiquetas_barras(xml, W, H, medir)
            if movidas_et:
                notas.append(f"{movidas_et} etiquetas apartadas a su lado para que no se monten con la de la barra vecina")
            cambios[ruta_graf] = xml.encode("utf-8")
            # Unidades, al borde izquierdo del trazado
            movidas = []
            ruta_formas = next((d for tp, d in rels(z, ruta_graf).values() if tp.endswith("/chartUserShapes")), None)
            if ruta_formas:
                formas = z.read(ruta_formas).decode("utf-8")
                for u in unidades_de(formas, xml):
                    x0, y0, x1, y1 = caja_rel(u)
                    formas, _ = colocar_rel(formas, u, nuevo_x * W, y0 * H, (nuevo_x + x1 - x0) * W, y1 * H, W, H)
                    movidas.append(html.unescape(texto_forma(u)).strip())
                cambios[ruta_formas] = formas.encode("utf-8")
            for iu in [i for i, (tp, g) in tipos.items() if tp == "unidades" and g == ig]:
                a = partes[iu]
                l, _, _, _ = margenes(a)
                xu, yu, wu, hu = caja(a)
                partes[iu] = colocar(a, gx + round(nuevo_x * gw) - l, yu, wu, hu)
                movidas.append(html.unescape(texto_forma(a)).strip())
            if movidas:
                notas.append("unidades al borde izquierdo del trazado: " + ", ".join(f"«{m}»" for m in movidas))
            notas.append("el trazado empieza al principio de la columna (sin números a la izquierda)")
            detalle += [(f"Aviso: panel {n}: " + t.split("Aviso: ", 1)[1]) if t.startswith("Aviso") else f"Panel {n}: {t}"
                        for t in notas]
        cambios[ruta] = "".join(partes).encode("utf-8")
    if not hechos:
        raise Fallo("Ningún panel tiene barras verticales sin apilar: no hay eje vertical que quitar")
    return nuevo_paso(trabajo, SIN_EJE_VERTICAL, cambios, detalle)


SOLO_COLUMNA_1 = "Sin leyenda: gráfico solo en la columna 1"


def solo_columna_1(trabajo, pid=None):
    """Herramienta (botón de «Excepciones a los gráficos», petición del usuario, 2026-11-26, G_IA2025_1.11): en los
    paneles sin leyenda, que el paso 2 extiende a las dos columnas, el trazado vuelve a acabar al final de la
    columna 1. El marco del gráfico no cambia; los textos sueltos del gráfico se mueven con el trazado, como en el
    paso 2. Ni tartas ni barras horizontales (ya van en la columna 1). Deja una versión nueva."""
    estado = leer_estado(trabajo)
    _, pasos = nombres(trabajo)
    base_archivo = pasos / estado["pasos"][estado["actual"]]["archivo"]
    requiere(estado, ("Tamaño y colocación",), f"«{SOLO_COLUMNA_1}»")
    cambios, detalle, hechos = {}, [], 0
    medir, hojas = medidor(), {}
    with zipfile.ZipFile(base_archivo) as z:
        ruta = dibujo_de_hoja(z, HOJA_GRAFICO)
        dibujo = z.read(ruta).decode("utf-8")
        relaciones = rels(z, ruta)
        partes = list(partes_dibujo(dibujo))
        caja = medidas_hoja(z, dibujo)
        (x1, w1), _ = guias_reticula(dibujo)[0]
        graficos = sorted((caja(a)[1], i, re.search(r'<c:chart\b[^>]*\br:id="([^"]+)"', a).group(1))
                          for i, a in enumerate(partes) if ANCLA.fullmatch(a) and "<c:chart " in a)
        for n, (_, ig, rid) in enumerate(graficos, 1):
            ruta_graf = relaciones[rid][1]
            xml = z.read(ruta_graf).decode("utf-8")
            gx, gy, gw, gh = caja(partes[ig])
            W, H = gw / EMU_PT, gh / EMU_PT
            if not sin_leyenda(xml, W):
                continue
            if es_tarta(xml) or 'barDir val="bar"' in xml:
                detalle.append(f"Panel {n}: sin leyenda, pero ya va en la columna 1 (tarta o barras horizontales)")
                continue
            t = trazado_rel(xml)
            if not t:
                detalle.append(f"Aviso: panel {n}: sin leyenda, pero su trazado no tiene disposición fija: no se toca")
                continue
            fin = (x1 + w1 - gx) / gw          # final de la columna 1, en fracción del gráfico
            # Lo que sobresale a la derecha del trazado (la última categoría o la etiqueta del último punto) también
            # dentro de la columna (G_IA2025_2.3: «85,29» se salía)
            sobresale = media_ultima_categoria(xml, 7, medir, W) if medir else 0
            if t[0] + t[2] <= fin - sobresale / W + 0.002:
                detalle.append(f"Panel {n}: sin leyenda y ya acaba en la columna 1")
                continue
            nuevo_w = fin - t[0] - sobresale / W
            xml = re.sub(r'(<c:plotArea>\s*<c:layout>\s*<c:manualLayout>.*?<c:w val=")[^"]+(")',
                         lambda m: f"{m.group(1)}{nuevo_w:.6f}{m.group(2)}", xml, count=1, flags=re.S)
            # Las etiquetas del eje horizontal, otra vez con las reglas del paso 1 para el ancho nuevo: el cuerpo (7 pt,
            # 6,5 o 6 si se pierde texto) y la dirección (guía, pág. 11: en vertical si no caben ni a 6 pt)
            notas_cat = []

            def cuerpo(m):
                eje = m.group(0)
                if not re.search(r'<c:axPos val="[bt]"/>', eje) or '<c:delete val="1"/>' in eje:
                    return eje
                sz, nota = cuerpo_categorias(xml, W)
                if sz != 700:
                    notas_cat.append(f"eje de categorías a {sz / 100:g} pt".replace(".", ",") + (f" ({nota})" if nota else ""))
                return con_txpr(eje, ["crossAx"], sz, ROBOTO)
            xml = re.sub(r'<c:catAx>.*?</c:catAx>', cuerpo, xml, flags=re.S)
            xml, nota_cat = direccion_categorias(z, xml, nuevo_w * W, hojas, medir)
            if notas_cat:
                nota_cat = "; ".join(notas_cat + ([nota_cat] if nota_cat else []))
            cambios[ruta_graf] = xml.encode("utf-8")
            hechos += 1
            linea = (f"Panel {n}: sin leyenda; el trazado acaba al final de la columna 1 "
                     f"({t[2] * W / MM:.1f} → {nuevo_w * W / MM:.1f} mm de ancho)").replace(".", ",")
            ruta_formas = next((d for tp, d in rels(z, ruta_graf).values() if tp.endswith("/chartUserShapes")), None)
            if ruta_formas:
                formas = z.read(ruta_formas).decode("utf-8")
                actuales = re.findall(r'<cdr:relSizeAnchor\b.*?</cdr:relSizeAnchor>', formas, re.S)
                saltar = [a for a in actuales if girado(a) or es_unidad_grafico(a, xml)]
                dentro = (t[0] * W, t[1] * H, nuevo_w * W, t[3] * H)
                formas, movidos = recolocar_formas(formas, t, (W, H), dentro, W, H, saltar)
                if movidos:
                    linea += "; se mueven con el trazado: " + ", ".join(f"«{m}»" for m in movidos)
                cambios[ruta_formas] = formas.encode("utf-8")
            if nota_cat and not nota_cat.startswith("Aviso"):
                linea += "; " + nota_cat.split(" — Aviso")[0]
            detalle.append(linea)
            if nota_cat and "Aviso" in nota_cat:
                detalle.append(f"Aviso: panel {n}: " + nota_cat.split("Aviso: ", 1)[1])
        for ruta_hoja, hoja in hojas.items():
            cambios[ruta_hoja] = hoja.encode("utf-8")
    if not hechos:
        raise Fallo("Ningún panel sin leyenda ocupa las dos columnas: no hay nada que estrechar")
    return nuevo_paso(trabajo, SOLO_COLUMNA_1, cambios, detalle)


# ---------------------------------------------------------------- comparar con el original y terminar

FORMATOS_INTERNOS = {0: "General", 1: "0", 2: "0.00", 3: "#,##0", 4: "#,##0.00", 9: "0%", 10: "0.00%",
                     11: "0.00E+00", 14: "fecha corta", 15: "d-mmm-yy", 16: "d-mmm", 17: "mmm-yy", 22: "fecha y hora",
                     49: "@"}
MAXIMO_EJEMPLOS = 6


def hojas_libro(z):
    """[(nombre, ruta)] de las hojas del libro, en su orden."""
    wb = z.read("xl/workbook.xml").decode("utf-8")
    relaciones = rels(z, "xl/workbook.xml")
    hojas = []
    for nombre, rid in re.findall(r'<sheet\b(?=[^>]*\bname="([^"]*)")(?=[^>]*\br:id="([^"]+)")[^>]*/>', wb):
        if rid in relaciones and relaciones[rid][1] in z.namelist():
            hojas.append((html.unescape(nombre), relaciones[rid][1]))
    return hojas


def formatos_celdas(z):
    """Código de formato de número de cada estilo de celda (índice de cellXfs)."""
    if "xl/styles.xml" not in z.namelist():
        return []
    estilos = z.read("xl/styles.xml").decode("utf-8")
    propios = {int(i): html.unescape(c) for i, c in
               re.findall(r'<numFmt\b[^>]*\bnumFmtId="(\d+)"[^>]*\bformatCode="([^"]*)"', estilos)}
    xfs = re.search(r'<cellXfs\b[^>]*>(.*?)</cellXfs>', estilos, re.S)
    lista = []
    for xf in re.findall(r'<xf\b[^>]*>', xfs.group(1)) if xfs else []:
        m = re.search(r'\bnumFmtId="(\d+)"', xf)
        i = int(m.group(1)) if m else 0
        lista.append(propios.get(i) or FORMATOS_INTERNOS.get(i, f"formato interno {i}"))
    return lista


def celdas_libro(z):
    """{hoja: {ref: (valor, formato)}} de todas las celdas con valor."""
    compartidos = textos_compartidos(z)
    formatos = formatos_celdas(z)
    todo = {}
    for nombre, ruta in hojas_libro(z):
        hoja = z.read(ruta).decode("utf-8")
        celdas = {}
        for c in re.finditer(r'<c r="([A-Z]+\d+)"[^>]*?(?:/>|>.*?</c>)', hoja, re.S):
            valor_c = texto_de_celda(c, compartidos)
            if valor_c is None or valor_c == "":
                continue
            s_ = re.search(r'\bs="(\d+)"', c.group(0)[:c.group(0).find(">")])
            k = int(s_.group(1)) if s_ else 0
            celdas[c.group(1)] = (valor_c, formatos[k] if k < len(formatos) else "General")
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


def series_libro(z):
    """{gráfico: [(nombre, referencias)]} de las series, para ver si falta alguna o ha cambiado su rango."""
    todo = {}
    for n in sorted(z.namelist()):
        if re.match(r'xl/charts/chart\d+\.xml$', n):
            xml = z.read(n).decode("utf-8")
            todo[n] = [(nombre_serie(s), tuple(re.findall(r'<c:f>([^<]*)</c:f>', s)))
                       for s in re.findall(r'<c:ser>.*?</c:ser>', xml, re.S)]
    return todo


def formatos_ejes(z):
    """{(gráfico, idEje): formato} de los números o fechas de los ejes."""
    todo = {}
    for n in sorted(z.namelist()):
        if re.match(r'xl/charts/chart\d+\.xml$', n):
            for e in EJES.finditer(z.read(n).decode("utf-8")):
                h = hijos(e.group(0))
                f = re.search(r'formatCode="([^"]*)"', hijo(h, "numFmt") or "")
                if f:
                    todo[(n, valor(hijo(h, "axId")))] = html.unescape(f.group(1))
    return todo


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
        # Columnas enteras multiplicadas por 100 (tartas: el % fuera de las etiquetas)
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
    # 2. Series de los gráficos
    so, sf = series_libro(zo), series_libro(zf)
    for graf, series in so.items():
        fin = sf.get(graf, [])
        refs_fin = {f for _, f in fin}
        nombres_fin = {n for n, _ in fin}
        for nombre, f in series:
            if f in refs_fin:
                continue
            if nombre in nombres_fin:
                cambios.append(f"rango de la serie «{nombre}»: {lista_corta(f)} → "
                               f"{lista_corta(next(g for n, g in fin if n == nombre))}")
            else:
                faltan.append(f"falta la serie «{nombre}» ({lista_corta(f)})")
        for nombre, f in fin:
            if nombre not in {n for n, _ in series} and f not in {g for _, g in series}:
                info.append(f"Serie añadida: «{nombre}»")
    # 3. Formato de los números y fechas de los ejes
    fo, ff = formatos_ejes(zo), formatos_ejes(zf)
    for clave, a in fo.items():
        b = ff.get(clave)
        if b is not None and a != b:
            que = "fechas" if re.search(r'[ymd]', re.sub(r'"[^"]*"|\[[^\]]*\]', "", b), re.I) else "formato de números"
            num = re.search(r'chart(\d+)\.xml', clave[0]).group(1)
            cambios.append(f"{que} de un eje (gráfico {num} del libro): «{a}» → «{b}»")
    # 4. Textos de los cuadros y de los gráficos
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


def copia_actual(trabajo):
    """La copia de trabajo más reciente (el usuario puede haber guardado cambios en «(2)»)."""
    trabajo = Path(trabajo)
    b = trabajo.with_name(trabajo.stem + " (2).xlsx")
    return max([c for c in (trabajo, b) if c.exists()], key=lambda c: c.stat().st_mtime)


CAMBIOS_A_MANO = "Cambios a mano en Excel"


def normalizar_visto(t):
    """Para comparar con el texto del PDF de Excel: sin espacios ni saltos (Excel parte las líneas donde quiere) y
    sin mayúsculas."""
    return re.sub(r"[\s\u00a0\u202f\u2009\u200a\u00ad]+", "", html.unescape(t)).casefold()


COMPROBACION = "Comprobación en Excel"


def comprobar(trabajo, ruta_texto):
    """Comprobación final (la app, al terminar el paso 5): Excel exporta la hoja del gráfico a PDF y la app pasa
    aquí su texto. Cada entrada de las leyendas y cada categoría del eje tienen que verse enteras: Excel esconde lo que
    no le cabe sin decir nada (8.2: «Compras en TPV» pasaba a una fila de la leyenda que no se veía; 8.4 b: «…(b)»
    cortado con «…»; 3.5 a 7 pt: se saltaba una categoría de cada dos). Las líneas van al detalle de la versión
    actual (petición del usuario, 2026-11-27)."""
    trabajo, pasos = nombres(trabajo)
    estado = leer_estado(trabajo)
    version = pasos / estado["pasos"][estado["actual"]]["archivo"]
    paginas = Path(ruta_texto).read_text(encoding="utf-8").split("\f")
    esperados = []          # (panel, qué, texto)
    with zipfile.ZipFile(version) as z:
        ruta = dibujo_de_hoja(z, HOJA_GRAFICO)
        dibujo = z.read(ruta).decode("utf-8")
        # Excel exporta el libro entero (también la hoja de datos, donde salen los nombres de las series): solo
        # cuenta la página de la hoja del gráfico, la que tiene más textos de sus formas (título, paneles, FUENTES…)
        formas = [normalizar_visto(texto_forma(a.group(0))) for a in ANCLA.finditer(dibujo) if "<xdr:txBody>" in a.group(0)]
        formas = [f for f in formas if len(f) > 3]
        visto = max(paginas, key=lambda pg: sum(f in normalizar_visto(pg) for f in formas))
        plano = normalizar_visto(visto)
        relaciones = rels(z, ruta)
        caja = medidas_hoja(z, dibujo)
        anclas = [a for a in partes_dibujo(dibujo) if ANCLA.fullmatch(a)]
        graficos = sorted((caja(a)[1], k, a) for k, a in enumerate(anclas, 1) if "<c:chart " in a)
        for n, (_, _, a) in enumerate(graficos, 1):
            rid = re.search(r'<c:chart\b[^>]*\br:id="([^"]+)"', a)
            if not rid or rid.group(1) not in relaciones:
                continue
            xml = z.read(relaciones[rid.group(1)][1]).decode("utf-8")
            if re.search(r'<c:legend>', xml) and not sin_leyenda(xml, caja(a)[2] / EMU_PT):
                esperados += [(n, "leyenda", t) for t, _ in entradas_leyenda(xml) if t.strip()]
            eje = next((e.group(0) for e in re.finditer(r'<c:catAx>.*?</c:catAx>', xml, re.S)
                        if '<c:delete val="1"/>' not in e.group(0) and '<c:tickLblPos val="none"/>' not in e.group(0)), None)
            if eje and not es_tarta(xml):
                salto = re.search(r'<c:tickLblSkip val="(\d+)"/>', eje)
                cats = etiquetas_categorias(xml)[::int(salto.group(1)) if salto else 1]
                esperados += [(n, "categoría", t) for t in cats if t.strip()]
    necesarios = Counter(normalizar_visto(t) for _, _, t in esperados)
    faltan = {t for t, k in necesarios.items() if t and plano.count(t) < k}
    lineas, vistos_aviso = [], set()
    for n, que, t in esperados:
        clave = normalizar_visto(t)
        if clave in faltan and (n, clave) not in vistos_aviso:
            vistos_aviso.add((n, clave))
            otros = sorted({m for m, _, u in esperados if normalizar_visto(u) == clave and m != n})
            texto = re.sub(r"\s+", " ", t).strip()
            lineas.append(f"Aviso: panel {n}: comprobación en Excel: no se ve entera la {que} «{texto}»"
                          + (f" (está también en el panel {', '.join(map(str, otros))}: falta en alguno)"
                             if otros and plano.count(clave) else "")
                          + (": Excel la esconde porque no le cabe en el cuadro de la leyenda" if que == "leyenda"
                             else ": Excel se la salta o la corta porque no cabe"))
    textos_hoja = normalizar_visto(" ".join(t for _, _, t in esperados))
    for m in re.finditer(r"\u2026", visto):
        trozo = re.sub(r"\s+", " ", visto[max(0, m.start() - 30):m.end()]).strip()
        if "\u2026" not in textos_hoja:
            lineas.append(f"Aviso: comprobación en Excel: Excel corta un texto con «…»: «{trozo}»")
    if not lineas:
        lineas = [f"{COMPROBACION}: las leyendas y las categorías se ven enteras ({len(esperados)} textos)"]
    else:
        lineas.insert(0, f"{COMPROBACION}: {len(lineas)} problema{'s' if len(lineas) > 1 else ''} en lo que dibuja Excel")
    detalle = [l for l in estado["pasos"][estado["actual"]]["detalle"] if COMPROBACION.lower() not in l.lower()]
    estado["pasos"][estado["actual"]]["detalle"] = detalle + marcar_detalle(version, lineas)
    guardar_estado(trabajo, estado)
    return {"trabajo": str(trabajo), **estado, "comprobacion": estado["pasos"][estado["actual"]]["detalle"][len(detalle):]}


def a_mano(trabajo, pid=None):
    """Antes de un paso o una herramienta (lo llama la app, tras guardar en Excel los cambios sin guardar): si la copia
    de trabajo ya no es la versión de la que partía, es que se ha retocado a mano en Excel (posición, tamaño…); se
    guarda como versión nueva y el paso parte de ella, así no se pierde (petición del usuario, 2026-11-26). Si no ha
    cambiado nada, no hace nada. Se comparan las partes del libro salvo `xl/workbook.xml` (la app escribe ahí el sitio
    de la ventana) y `docProps`."""
    trabajo, pasos = nombres(trabajo)
    estado = leer_estado(trabajo)
    version = pasos / estado["pasos"][estado["actual"]]["archivo"]
    copia = copia_actual(trabajo)

    def partes(f):
        with zipfile.ZipFile(f) as z:
            return {n: z.read(n) for n in z.namelist() if n != "xl/workbook.xml" and not n.startswith("docProps/")}
    antes, ahora = partes(version), partes(copia)
    if antes == ahora:
        return {"trabajo": str(trabajo), **estado, "a_mano": False}
    # Qué formas de la hoja del gráfico se han movido o cambiado de tamaño (más de medio milímetro)
    detalle = []
    try:
        with zipfile.ZipFile(version) as zv, zipfile.ZipFile(copia) as zc:
            def cajas(z):
                d = z.read(dibujo_de_hoja(z, HOJA_GRAFICO)).decode("utf-8")
                caja = medidas_hoja(z, d)
                return {(k, nombre_forma(a.group(0))): caja(a.group(0)) for k, a in enumerate(ANCLA.finditer(d), 1)}
            cv, cc = cajas(zv), cajas(zc)
        movidas = [n for (k, n), c in cc.items() if (k, n) in cv and max(abs(a - b) for a, b in zip(c, cv[(k, n)])) > 0.5 * 36000]
        nuevas = [n for (k, n) in cc if (k, n) not in cv]
        if movidas:
            detalle.append("Movido o cambiado de tamaño a mano: " + ", ".join(f"«{n}»" for n in movidas[:8]))
        if nuevas:
            detalle.append("Formas nuevas o cambiadas de orden: " + ", ".join(f"«{n}»" for n in nuevas[:8]))
    except (Fallo, KeyError, zipfile.BadZipFile):
        pass
    detalle.insert(0, "Cambios hechos a mano en Excel, guardados como versión para que los pasos siguientes partan "
                      "de ellos (⌘← para quitarlos)")
    if len(detalle) == 1:
        detalle.append("Cambios dentro de los gráficos o de las celdas (sin formas movidas)")
    # Como `nuevo_paso`, pero con el libro entero de la copia
    actual = estado["actual"]
    for p in estado["pasos"][actual + 1:]:
        (pasos / p["archivo"]).unlink(missing_ok=True)
    del estado["pasos"][actual + 1:]
    n = actual + 1
    archivo = f"{n:02d} {CAMBIOS_A_MANO}.xlsx"
    shutil.copyfile(copia, pasos / archivo)
    solo_lectura(pasos / archivo)
    if copia != trabajo:
        shutil.copyfile(copia, trabajo)
        os.chmod(trabajo, 0o644)
    estado["pasos"].append({"n": n, "titulo": CAMBIOS_A_MANO, "archivo": archivo,
                            "detalle": marcar_detalle(pasos / archivo, detalle)})
    estado["actual"] = n
    guardar_estado(trabajo, estado)
    return {"trabajo": str(trabajo), **estado, "a_mano": True}


def comparar(trabajo):
    estado = leer_estado(trabajo)
    _, pasos = nombres(trabajo)
    origen = Path(estado.get("origen", ""))
    if not origen.is_file():
        origen = pasos / estado["pasos"][0]["archivo"]
    actual = copia_actual(trabajo)
    with zipfile.ZipFile(origen) as zo, zipfile.ZipFile(actual) as zf:
        lineas = comparar_libros(zo, zf, estado.get("idioma", "es"))
        lineas = marcar_comparacion(zf, lineas)
    # Solo lo que sale de comparar: los avisos de los pasos 1 a 5 ya están en «N avisos en esta maquetación» y en
    # cada versión (petición del usuario, 2026-11-27: repetirlos aquí despistaba)
    return {"trabajo": str(trabajo), **estado, "comparacion": lineas, "comparado": str(actual), "original": str(origen)}


def formas_del_libro(z):
    """[(hoja, k, nombre, texto, gráfico)] de las formas de cada hoja con dibujo (k: su número en la hoja, el de
    «shape k» en Excel). El texto de un gráfico junta el suyo (títulos, ejes, series, etiquetas) y el de su capa de
    formas; gráfico: la ruta de su chartN.xml."""
    salida = []
    for hoja, ruta_hoja in hojas_libro(z):
        dibujo = next((d for t, d in rels(z, ruta_hoja).values() if t.endswith("/drawing")), None)
        if not dibujo or dibujo not in z.namelist():
            continue
        xml = z.read(dibujo).decode("utf-8")
        relaciones = rels(z, dibujo)
        for k, a in enumerate((m.group(0) for m in ANCLA.finditer(xml)), 1):
            textos = [html.unescape(t) for t in re.findall(r'<a:t>([^<]*)</a:t>', a)]
            grafico = None
            rid = re.search(r'<c:chart\b[^>]*\br:id="([^"]+)"', a)
            if rid and rid.group(1) in relaciones:
                grafico = relaciones[rid.group(1)][1]
                if grafico in z.namelist():
                    gx = z.read(grafico).decode("utf-8")
                    textos += [html.unescape(t) for t in re.findall(r'<a:t>([^<]*)</a:t>|<c:v>([^<]*)</c:v>', gx) for t in t if t]
                    for t, f in rels(z, grafico).values():
                        if t.endswith("/chartUserShapes") and f in z.namelist():
                            textos += [html.unescape(x) for x in re.findall(r'<a:t>([^<]*)</a:t>', z.read(f).decode("utf-8"))]
            try:
                nombre = nombre_forma(a)
            except AttributeError:
                nombre = ""
            salida.append((hoja, k, nombre, re.sub(r"\s+", " ", " ".join(textos)), grafico))
    return salida


def marcar_comparacion(z, lineas):
    """Marca de cada línea de la comparación con lo que hay que enseñar en Excel (petición del usuario,
    2026-11-25): celdas de una hoja (datos que faltan o cambian: «⟦celdas:hoja|B9 B10⟧»), el gráfico de un eje o
    de una serie, o la forma donde está un texto («⟦forma:hoja|k|nombre⟧»)."""
    hojas = [h for h, _ in hojas_libro(z)]
    formas = formas_del_libro(z)
    salida = []
    for linea in lineas:
        marca_l = ""
        citas = re.findall(r'«([^«»]*)»', linea)
        hoja = next((c for c in citas if c in hojas and re.search(rf'(?:en|de) (?:la hoja )?«{re.escape(c)}»', linea)), None)
        graf = re.search(r'\(gráfico (\d+) del libro\)', linea)
        if hoja:
            # Las referencias de celda fuera de las citas
            fuera = re.sub(r'«[^«»]*»', " ", linea.split(f"«{hoja}»", 1)[1])
            refs = []
            for a, b in re.findall(r'\b([A-Z]{1,3}\d+)(?::([A-Z]{1,3}\d+))?\b', fuera):
                refs.append(f"{a}:{b}" if b else a)
            if refs:
                marca_l = f" ⟦celdas:{hoja}|{' '.join(refs[:30])}⟧"
        elif graf:
            f = next((x for x in formas if x[4] == f"xl/charts/chart{graf.group(1)}.xml"), None)
            if f:
                marca_l = f" ⟦forma:{f[0]}|{f[1]}|{f[2]}⟧"
        elif citas:
            # Texto o serie: la forma (de la hoja o gráfico) que lo contiene; primero lo de después de «→»
            candidatos = citas[::-1] if "→" in linea else citas
            # Primero los cuadros de la hoja y después los gráficos; primero el texto suelto (que «1.1» no case con
            # «1.1.a») y después dentro de otro
            orden = [x for x in formas if not x[4]] + [x for x in formas if x[4]]
            for c in candidatos:
                c = re.sub(r"\s+", " ", c).strip().rstrip("…").strip()
                if len(c) < 3:
                    continue
                suelto = re.compile(r"(?<![\w.])" + re.escape(c.lower()) + r"(?![\w.])")
                f = next((x for x in orden if suelto.search(x[3].lower())), None) \
                    or next((x for x in orden if c.lower() in x[3].lower()), None)
                if f:
                    marca_l = f" ⟦forma:{f[0]}|{f[1]}|{f[2]}⟧"
                    break
        salida.append(con_resaltes(linea + marca_l))
    return salida


def nombre_terminado(origen, carpeta):
    """«… EXCEL.xlsx» (como en Cuadros Excel BdE; antes «TERMINADO», petición del usuario, 2026-11-25): «ORIGINALES»
    u «ORIGINAL» pasan a «EXCEL»; si no, « EXCEL» al final."""
    base = origen.stem
    if re.search(r'\bORIGINALES\b', base):
        base = re.sub(r'\bORIGINALES\b', "EXCEL", base)
    elif re.search(r'\bORIGINAL\b', base):
        base = re.sub(r'\bORIGINAL\b', "EXCEL", base)
    elif not re.search(r'\bEXCEL$', base):
        base += " EXCEL"
    destino, n = carpeta / f"{base}.xlsx", 2
    while destino.exists():   # nunca se pisa un EXCEL que ya exista
        destino, n = carpeta / f"{base} ({n}).xlsx", n + 1
    return destino


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
    borrados = []
    for c in (trabajo, trabajo.with_name(trabajo.stem + " (2).xlsx")):
        if c.exists():
            c.unlink()
            borrados.append(c.name)
    if pasos.is_dir() and pasos.name.endswith(" (pasos)"):
        shutil.rmtree(pasos)
        borrados.append(pasos.name)
    return {"terminado": str(destino), "borrados": borrados, "original": str(origen) if origen.is_file() else None}


# ---------------------------------------------------------------- medir textos

CARPETAS_FUENTES = [Path.home() / "Library/Fonts", Path("/Library/Fonts"), Path("/System/Library/Fonts/Supplemental")]
HOLGURA_PT = 5.0   # lo que Excel deja libre en cada hueco: si la palabra no cabe, agranda el trazado
HOLGURA_HORIZONTAL = 3.0   # lo justo para que Excel deje las categorías en horizontal sin saltarse ninguna (3.5)
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
    cuenta = re.search(r'<c:ptCount val="(\d+)"', cat.group(0))
    # Sin caché de categorías (rango vacío o borrado, Rec_IA2025_2.2_G1) no hay etiquetas que medir
    n = int(cuenta.group(1)) if cuenta else max((max(nv, default=-1) for nv in niveles), default=-1) + 1
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


def maquetar_formas_grafico(xml, graf=None):
    """Cuadros de texto dentro del gráfico: las unidades y el título girado del eje vertical (7 pt); el resto,
    interior (6 pt)."""
    unidades, otros = [], []

    def cambiar(m):
        a = m.group(0)
        texto = texto_forma(a).strip()
        if not texto:
            return a
        if es_unidad_grafico(a, graf) or girado(a):
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
    ordenes = {"empezar": empezar, "estado": lambda t: {"trabajo": t, **leer_estado(t)}, "ir": ir, "paneles": paneles, "reiniciar": reiniciar, "paso1": paso1, "paso2": paso2, "paso3": paso3, "paso4": paso4, "paso5": paso5, "comparar": comparar, "sin_eje_vertical": sin_eje_vertical, "solo_columna_1": solo_columna_1, "a_mano": a_mano, "comprobar": comprobar, "terminar": terminar, "info": info,
               "publicaciones": lambda: {}, "guardar_publicacion": guardar_publicacion, "borrar_publicacion": borrar_publicacion, "paletas": paletas}
    if not args or args[0] not in ordenes:
        print(__doc__, file=sys.stderr)
        return 2
    try:
        res = ordenes[args[0]](*args[1:])
        res["publicaciones"] = CONFIG["publicaciones"]
        if args[0] in ("empezar", "estado", "ir", "reiniciar", "paneles") or args[0].startswith("paso"):
            res["reticula_pt"] = medidas_reticula()
        res["muestrario"] = CONFIG.get("muestrario", [])
        print(json.dumps({"ok": True, **res}, ensure_ascii=False))
        return 0
    except (Fallo, OSError, zipfile.BadZipFile, KeyError) as e:
        print(json.dumps({"ok": False, "error": str(e)}, ensure_ascii=False))
        return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
