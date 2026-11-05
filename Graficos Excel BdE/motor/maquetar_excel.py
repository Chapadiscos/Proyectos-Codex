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
    cambios0, detalle0 = {}, []
    if deshechos:
        cambios0[ruta] = dibujo.encode("utf-8")
        detalle0.append("Desagrupado lo que el autor había agrupado con el gráfico: " +
                        ", ".join(f"«{n}»" for n in deshechos) + " (cada elemento en su sitio)")
        previo = io.BytesIO()
        reescribir_zip(base, previo, cambios0)
    else:
        previo = base
    with zipfile.ZipFile(previo) as z:
        cambios, detalle = reticula_y_pastilla(z, pid)
    intermedio = io.BytesIO()
    reescribir_zip(previo, intermedio, cambios)
    with zipfile.ZipFile(intermedio) as z:
        cambios_textos, detalle_textos = textos(z, estado)
    return nuevo_paso(trabajo, RETICULA_Y_TEXTOS, {**cambios0, **cambios, **cambios_textos},
                      aviso_separador_ingles(estado) + detalle0 + detalle + detalle_textos)


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


# Leyendas en minúscula salvo las siglas (y la primera letra, y los nombres propios). Solo se tocan los nombres
# que el autor escribió enteros en mayúsculas: en uno con minúsculas no se sabe qué palabra es sigla o propia.
SIGLAS = {"EEUU", "EE.UU.", "EE", "UU", "UEM", "UE", "EA", "PIB", "IPC", "IPCA", "IAPC", "IPRI", "BCE", "BDE", "FMI",
          "OCDE", "OPEP", "IA", "TIC", "PYME", "PYMES", "VAB", "EPA", "PMI", "CNMV", "TAE", "TIN", "ICO", "IRPF",
          "IVA", "I+D", "SA", "EBAE", "ROE", "ROA", "NPL", "BBVA", "CCAA", "AAPP", "ISFLSH", "PER", "ETF", "EURIBOR",
          "FED", "INE", "AEAT", "BIS", "BPI", "UK", "US", "USA", "USD", "EUR", "GBP", "JPY", "CNY", "ESG", "TR", "EMU",
          "GDP", "CPI", "HICP", "ECB", "IMF", "OECD", "SME", "SMES", "AI", "UN", "CET1", "LTV", "LTI", "DTI", "DSTI", "SMI", "OIS"}
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


def en_minuscula(texto, idioma="es"):
    """Nombre de leyenda en minúscula salvo las siglas, los nombres propios, los números romanos y la primera
    letra (y la de después de un punto). Solo si está entero en mayúsculas; si no, como lo escribió el autor."""
    # Las llamadas a nota («(b)», en minúscula por norma) no cuentan para saber si está en mayúsculas
    letras = [c for c in re.sub(r'\(\w\)', "", texto) if c.isalpha()]
    if not letras or any(c.islower() for c in letras):
        return texto
    siglas = SIGLAS - (set() if idioma == "en" else SIGLAS_SOLO_EN)
    propios = NOMBRES_PROPIOS - (set() if idioma == "en" else NOMBRES_PROPIOS_SOLO_EN)
    partes = re.split(r'(\s+)', texto)
    salida, mayuscula = [], True
    for parte in partes:
        if not parte or parte.isspace():
            salida.append(parte)
            continue
        limpia = parte.strip("()[]¿?¡!«»\"',;:.")
        # Letra suelta entre paréntesis («(O)», «(D)»): abreviatura, se deja
        if len(limpia) == 1 and parte.startswith("(") and limpia.isalpha():
            nueva = parte
        elif limpia in siglas or limpia.replace(".", "") in siglas or any(c.isdigit() for c in limpia) or (limpia and ROMANOS.match(limpia)):
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
        if parte.rstrip("»\"')").endswith((".", ":", "?", "!")):
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
    return xml, hechos


RE_PANEL = re.compile(r'\s*\d+(?:\.\d+)*\.?\s*[a-zA-Z]\b')   # «1 a», «1.a», «2.6.a»: título de panel


# Título de panel (todas las publicaciones): el número siempre como «N.x», letra en minúscula («1 a», «6.A.», «6.a)» → «1.a», «6.a»;
# «2.6.a» se queda), 2 espacios entre él y el título y, dentro del título, sin espacios dobles
RE_NUMERO_PANEL = re.compile(r'\s*(\d+(?:\.\d+)*)\.?\s*([a-zA-Z])(?![^\W\d_])[.)]?([ \t\u00a0]*)(?=\S)')
HUECO_PANEL = "  "


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
        limpias, quitados = letras[:fin_cabeza], 0
        for c, k in letras[fin_cabeza:]:
            if c == " " and limpias[len(limpias) - 1:] and limpias[-1][0] == " " and len(limpias) > fin_cabeza:
                quitados += 1
                continue
            limpias.append((c, k))
        if quitados:
            hechos.append("espacios dobles del título en uno")
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
        elif RE_PANEL.match(texto):
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
                gi, g = min(encima, key=lambda t: abs(t[1][1] - y))
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
            detalle.append(f"Texto en el centro de la tarta «{corto}»: la cifra en Roboto Black 24 pt y el texto en "
                           "Roboto Regular 7 pt, centrado")
        elif tipo == "interior":
            a = fijar_letra(a, 700, ROBOTO)
            detalle.append(f"Texto sobre el gráfico, a la derecha «{corto}»: Roboto Regular 7 pt, donde lo dejó el autor")
        else:
            a = fijar_letra(a, 800, ROBOTO)
            a, cambios_panel = dos_espacios_panel(a, estado["idioma"])
            detalle.append(f"Título de panel «{corto}»: Roboto Regular 8 pt" + "".join(f"; {c}" for c in cambios_panel))
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
    for i, rid in enumerate(re.findall(r'<c:chart\b[^>]*\br:id="([^"]+)"', dibujo), 1):
        ruta_graf = relaciones[rid][1]
        graf, cuentas = maquetar_grafico(z.read(ruta_graf).decode("utf-8"), anchos.get(rid))
        graf, minusculas = leyendas_en_minuscula(z, ruta_graf, graf, estado["idioma"], hojas_datos)
        # Textos especiales (guía, págs. 10 y 11), con el ancho que tendrá el trazado en «Tamaño y colocación»
        ancho_final = (x2 + w2 - x1 if anchos.get(rid) and sin_leyenda(graf, anchos[rid]) else w1) / EMU_PT
        trazado = ancho_final - (ancho_numeros_eje(graf, medir) if medir else 0)
        graf, estilos, especiales = textos_especiales(z, graf, estado["idioma"], hojas_datos, estilos, trazado, medir)
        if es_tarta(graf):
            graf, estilos, notas_tarta, quitado = tarta_paso1(z, graf, hojas_datos, estilos)
            especiales += notas_tarta
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
NOTA_LETRA = re.compile(r'\s*([a-z])(?:\.|\t)[\t ]*')
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
    clave = CLAVE_LEYENDA + (CLAVE_LINEA_DE_MAS if any(linea for _, linea in entradas) else 0)
    # Excel centra las entradas en el cuadro: con el ancho justo de la línea más larga (partiendo los nombres
    # que no caben en la columna 2), la muestra queda al principio
    partidos = [partir_lineas(n, lmax - clave - 2, 7, medir) for n, _ in entradas]
    lw = max(w for anchos in partidos for w in anchos) + clave + 2
    # Excel da a cada entrada el alto de la más alta y reparte lo que sobre: alto justo para todas
    lh = len(entradas) * (max(len(a) for a in partidos) * 7 * INTERLINEA + 1.5) + 4
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
        return y >= (t[1] + t[3] - 0.02 if t else 0.75)
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


def recolocar_formas(formas, viejo_trazado, viejo_tam, dentro, ancho, alto, saltar=()):
    """Los textos sueltos dentro del gráfico se mueven con el trazado: su esquina conserva su sitio respecto al
    trazado (lo que señalan) y su tamaño en pt."""
    fx, fy, fw, fh = viejo_trazado
    w0, h0 = viejo_tam
    movidos = []
    for a in re.findall(r'<cdr:relSizeAnchor\b.*?</cdr:relSizeAnchor>', formas, re.S):
        if a in saltar or not texto_forma(a).strip():
            continue
        x0, y0, x1, y1 = caja_rel(a)
        u, v = (x0 - fx) / fw, (y0 - fy) / fh
        nx, ny = dentro[0] + u * dentro[2], dentro[1] + v * dentro[3]
        formas, _ = colocar_rel(formas, a, nx, ny, nx + (x1 - x0) * w0, ny + (y1 - y0) * h0, ancho, alto)
        movidos.append(html.unescape(texto_forma(a)).strip()[:30])
    return formas, movidos


def filas_categorias(xml, trazado, paso_pt):
    """Cuerpo de las categorías (regla del paso 2, con el ancho nuevo del trazado, en pt) y filas de la
    retícula que ocupan debajo del eje: la palabra más larga tiene que caber en su hueco; cada etiqueta se
    parte por palabras."""
    medir = medidor()
    eje = next((e.group(0) for e in re.finditer(r'<c:catAx>.*?</c:catAx>', xml, re.S)
                if re.search(r'<c:axPos val="[bt]"/>', e.group(0)) and '<c:delete val="1"/>' not in e.group(0)), "")
    if es_vertical(eje) and medir:
        # Verticales (paso 1): ocupan a lo alto lo que mide su línea más larga, con el cuerpo que ya tienen
        cuerpo = re.search(r'<c:txPr>.*?<a:defRPr\b[^>]*\bsz="(\d+)"', eje, re.S)
        sz = int(cuerpo.group(1)) if cuerpo else 700
        largo = max([medir(l, sz / 100) for e in etiquetas_categorias(xml) for l in e.split("\n")] or [0])
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
        graficos.sort()
        if len(graficos) > 3:
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
        for y, i in sorted(titulos_panel):
            libres = [(abs(yg - y), ig) for yg, ig, _ in graficos if ig not in de_panel]
            if libres:
                de_panel[min(libres)[1]] = i

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
                if n == 1:
                    arriba = fondo_pastilla + crece + PASTILLA_A_TITULO_PANEL
                else:
                    arriba = fondo + ENTRE_PANELES
                final_tp = arriba + lineas_tp * INTERLINEA_TITULO_PANEL
                alto_tp = t + b + round(lineas_tp * INTERLINEA_TITULO_PANEL * EMU_PT)
                partes[it] = colocar(a, x1 - l, round(arriba * EMU_PT) - t, ancho_util + l + r, alto_tp)
                inicio = final_tp + TITULO_PANEL_A_GRAFICO - subida
                techo_panel = final_tp
                linea += f" título a {arriba / MM:.1f} mm ({lineas_tp} línea{'s' if lineas_tp > 1 else ''});".replace(".", ",")
            else:
                inicio = (INICIO_SIN_TITULO_PANEL + crece if n == 1 else fondo + ENTRE_PANELES) - subida
                techo_panel = fondo_pastilla + crece if n == 1 else fondo + ENTRE_PANELES / 2

            # Sin leyenda (el autor la ha quitado o escondido): el trazado ocupa las dos columnas, como en el
            # TERMINADO del 2.6, y la leyenda se deja como está
            motivo = sin_leyenda(xml, caja(partes[ig])[2] / EMU_PT)
            if motivo and horizontal:
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
                filas = FILAS_PANEL
                diametro = filas * paso_pt
                alto_panel = MEDIA_ETIQUETA + diametro + ETIQUETA_TARTA
                trazado = diametro
            else:
                # Alto: 9 filas hasta el final de las categorías (el trazado, como mínimo 7)
                numeros = ancho_categorias_izquierda(xml, medir) if horizontal else ancho_numeros_eje(xml, medir)
                trazado = (ancho_util if motivo and not horizontal else w1) / EMU_PT - numeros
                sz, nota, lineas_cat, filas_cat, alto_cat = filas_categorias(xml, trazado, paso_pt)
                if horizontal:
                    # El gráfico acaba al final de la última cifra del eje (que sobresale medio ancho del trazado)
                    sobresale = media_ultima_cifra(xml, medir)
                    trazado -= sobresale
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
                alto_panel = filas * paso_pt + LETRA_VISIBLE
            # Tarta: si sus etiquetas no caben por arriba sin líneas guía, el anillo (con sus 9 filas) baja una
            # fila de la retícula, como mucho FILAS_BAJADA_TARTA, y se queda con la primera que vale
            inicio0, pruebas = inicio, []
            for bajada in range(FILAS_BAJADA_TARTA + 1 if tarta else 1):
                inicio = inicio0 + bajada * paso_pt
                # Unidades: su línea de base, 2 mm por encima del borde de arriba del trazado
                ini_unidades = inicio + MEDIA_ETIQUETA - UNIDADES_A_GRAFICO - BASE_UNIDADES
                arriba_marco = min(ini_unidades, inicio) if unidades_arriba else inicio
                if tarta:
                    # Las etiquetas de arriba necesitan sitio por encima del anillo: el marco sube hasta la
                    # pastilla o el título del panel (el anillo no se mueve)
                    arriba_marco = min(arriba_marco, techo_panel + AIRE_SOBRE_ETIQUETAS)
                H = inicio + alto_panel - arriba_marco
                if not tarta:
                    break
                dentro = ((w1 / EMU_PT - diametro) / 2, inicio - arriba_marco + MEDIA_ETIQUETA, diametro, diametro)
                centro = dentro[1] + diametro / 2
                xml_t = disposicion(xml, W, H, dentro, None if motivo else
                                    ((x2 - x1) / EMU_PT - LEYENDA_A_LA_IZQUIERDA, centro, w2 / EMU_PT, True), medir)
                xml_t, notas_et, guias = etiquetas_tarta(xml_t, W, H, dentro, medir, None if motivo else
                                                         (x2 - x1) / EMU_PT - LEYENDA_A_LA_IZQUIERDA)
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
                # Solo barras: la serie invisible que da muestras anchas en la leyenda (antes de medirla)
                anchas = None if motivo else muestras_anchas(xml)
                if anchas:
                    xml = anchas
                    detalle.append(f"Panel {n}: muestras de la leyenda anchas, como las de las líneas, para que se "
                                   "vean las tramas de las barras (serie de línea blanca sin datos al final de la leyenda)")
                dentro = (numeros, inicio - arriba_marco + MEDIA_ETIQUETA, trazado,
                          alto_panel - MEDIA_ETIQUETA - alto_cat)
                xml = disposicion(xml, W, H, dentro, None if motivo else
                                  ((x2 - x1) / EMU_PT - LEYENDA_A_LA_IZQUIERDA, inicio - arriba_marco, w2 / EMU_PT), medir)
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
            cambios[ruta_graf] = xml.encode("utf-8")
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
            partes[ig] = colocar(partes[ig], x1, round(arriba_marco * EMU_PT), ancho_graf, round(H * EMU_PT))
            fondo = inicio + alto_panel
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
    return datos


def formato_ejes(xml):
    """Ejes según la guía (página 15) y el TERMINADO: línea de cada eje y de sus líneas de división; eje en
    cero; marcas de graduación; etiquetas en Bajo y a distancia 100; el máximo y el mínimo fijos, en un tramo
    del eje (el gráfico se cierra con una línea de división). Devuelve el xml y lo hecho, para el detalle."""
    cuentas = []
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
            "orientacion": valor(hijo(escala, "orientation")) or "minMax", "log": hijo(escala, "logBase") is not None}

    def eje(m):
        a, tipo = m.group(0), m.group(1)
        orden = ORDEN_EJE[tipo]
        h = hijos(a)
        nombre = ("eje de categorías" if tipo in ("catAx", "dateAx") else "eje de valores" if tipo == "valAx"
                  else "eje de series")
        hecho = []
        if valor(hijo(h, "delete")) == "1":
            # Oculto: no se toca (en el TERMINADO quedan como los dejó el autor)
            cuentas.append(nombre + " (oculto): sin tocar")
            return a
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
        if tipo == "catAx" and horizontal and valor(hijo(h, "tickMarkSkip")) not in (None, "1"):
            hecho.append(f"una marca por valor (antes cada {valor(hijo(h, 'tickMarkSkip'))})")
            poner(h, orden, "tickMarkSkip", '<c:tickMarkSkip val="1"/>')

        # Etiquetas: en Bajo (las de los ejes horizontales y, en dispersión, también las del vertical) y a
        # distancia 100 del eje
        if horizontal or dispersion:
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
            detalle.append(f"Panel {i}: " + ("; ".join(cuentas) if cuentas else "sin ejes"))
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
        if unidad or (amax - amin) / u <= 9 + 1e-9:
            return amin, amax, u
    return None


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


def direccion_categorias(z, xml, trazado, hojas, medir):
    """Etiquetas del eje horizontal (guía, pág. 11): horizontales si caben (nunca en oblicuo); si no caben ni a
    6 pt, verticales de abajo arriba y, si el hueco deja, en 2 o 3 líneas (saltos en las celdas). Devuelve el
    xml y una nota (o un aviso si no se puede sin cortar texto)."""
    eje = next((e for e in re.finditer(r'<c:catAx>.*?</c:catAx>', xml, re.S)
                if re.search(r'<c:axPos val="[bt]"/>', e.group(0)) and '<c:delete val="1"/>' not in e.group(0)), None)
    if not eje:
        return xml, None
    etiquetas = etiquetas_categorias(xml)
    rot = re.search(r'<a:bodyPr\b[^>]*\brot="(-?\d+)"', eje.group(0))
    if not etiquetas or not medir:
        # Numéricas o fechas: Excel salta etiquetas si no caben; solo se quita la inclinación
        if rot and rot.group(1) not in ("0", ROT_VERTICAL):
            return xml.replace(eje.group(0), poner_rotacion(eje.group(0), "0"), 1), "etiquetas del eje horizontal sin inclinar"
        return xml, None
    hueco = trazado / len(etiquetas)
    palabras = [p for e in etiquetas for p in e.split()]
    larga = max(palabras, key=lambda p: medir(p, 6)) if palabras else ""
    if medir(larga, 6) <= hueco - HOLGURA_PT:
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

    # Trimestres en las categorías y en los títulos del gráfico
    xml, cambios, _ = cambiar_categorias(z, xml, hojas, lambda t: trimestres(t, idioma))
    if cambios:
        notas.append("trimestres en las categorías: " + ", ".join(cambios[:4]) + (" …" if len(cambios) > 4 else ""))
    xml, hechos = textos_trimestres(xml, idioma)
    if hechos:
        notas.append("trimestres: " + ", ".join(hechos[:4]))
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


def decimales_etiquetas(valores, pct=False):
    """Decimales de las etiquetas según la guía (pág. 10): ninguno si todos son ceros, uno si los hay y dos
    si son centésimas (si con uno alguna cifra que no es cero se quedaría en 0,0)."""
    f = 100 if pct else 1
    vs = [v * f for v in valores]
    if all(abs(v - round(v)) < 1e-9 for v in vs):
        return 0
    if any(v and round(v, 1) == 0 for v in vs):
        return 2
    return 1


def etiquetas_datos(xml):
    """Etiquetas de datos de las series: decimales de la guía (pág. 10: los mismos que en los ejes) y, si
    llevan texto y número, separados por «: » (pág. 16). Devuelve el xml y las notas."""
    notas = []

    def mostrar(h, nombre):
        return valor(hijo(h, nombre)) == "1"

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
                d = decimales_etiquetas(valores, pct)
                codigo = "#,##0" + ("." + "0" * d if d else "") + ("%" if pct else "")
                if codigo != actual or not nf or nf.group(2) != "0":
                    nuevo = f'<c:numFmt formatCode="{html.escape(codigo)}" sourceLinked="0"/>'
                    poner(h, ORDEN_DLBLS, "numFmt", nuevo)
                    for e in h:
                        if e[0] == "dLbl" and "<c:numFmt " in e[1]:
                            e[1] = re.sub(r'<c:numFmt [^>]*/>', nuevo, e[1], count=1)
                    if codigo != actual:
                        cambios.append(f"{codigo} (antes {actual})")
        if not cambios:
            return ser
        notas.append(f"etiquetas de «{nombre}»: " + ", ".join(cambios))
        return ser.replace(dl.group(0), "<c:dLbls>" + "".join(t for _, t in h) + "</c:dLbls>", 1)

    xml = re.sub(r'<c:ser>.*?</c:ser>', serie, xml, flags=re.S)
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
    f = re.search(r'<c:val>\s*<c:numRef>\s*<c:f>([^<]*)</c:f>', ser)
    if not f:
        return xml, estilos, notas + ["Aviso: las etiquetas llevan % pero sus datos no están en la hoja: se deja el %"], quitado
    refs = celdas_de_rango(html.unescape(f.group(1)))
    nombre = refs[0][0]
    ruta_hoja = hoja_de(z, nombre)
    hoja = hojas.get(ruta_hoja) or z.read(ruta_hoja).decode("utf-8")
    celdas_ = [celda(hoja, r) for _, r in refs]
    if any(c is None or "<f" in c.group(0) for c in celdas_):
        return xml, estilos, notas + ["Aviso: las etiquetas llevan % pero sus datos salen de fórmulas: se deja el %"], quitado
    for _, ref in refs:
        c = celda(hoja, ref)
        v = re.search(r'<v>([^<]*)</v>', c.group(0))
        if v:
            hoja = hoja[:c.start()] + c.group(0).replace(v.group(0), f"<v>{cifra(float(v.group(1)) * 100)}</v>", 1) + hoja[c.end():]
    estilos, hoja = poner_formato_celdas(estilos, hoja, [r for _, r in refs], "#,##0.00")
    hojas[ruta_hoja] = hoja
    nueva = re.sub(r'(<c:val>.*?</c:val>)', lambda m: re.sub(
        r'<c:v>([^<]*)</c:v>', lambda v: f"<c:v>{cifra(float(v.group(1)) * 100)}</c:v>",
        re.sub(r'<c:formatCode>[^<]*</c:formatCode>', '<c:formatCode>General</c:formatCode>', m.group(1))), ser, count=1, flags=re.S)
    nueva = re.sub(r'<c:numFmt formatCode="([^"]*)" sourceLinked="0"/>',
                   lambda m: f'<c:numFmt formatCode="{html.escape(sin_porcentaje(html.unescape(m.group(1))))}" sourceLinked="0"/>'
                   if "%" in html.unescape(m.group(1)) else m.group(0), nueva)
    xml = xml.replace(ser, nueva, 1)
    notas.append(f"etiquetas sin «%» ({sin_porcentaje(html.unescape(formatos[0]))}): datos de {nombre} × 100; «%» como unidad")
    return xml, estilos, notas, True


# Texto del centro de una tarta, como en el TERMINADO del 2.3: la cifra en Roboto Black 24 pt (negrita) y el
# texto en Roboto Regular 7 pt, centrado; el cuadro sin relleno ni borde
CIFRA_CENTRO_TARTA = ("Roboto Black", 2400, True)
TEXTO_CENTRO_TARTA = (ROBOTO, 700, False)
# Para que lo que se ve quede en el centro: la línea de la cifra (24 pt) deja sobre los números más hueco
# (ascendente − altura de las cifras, 0,928 − 0,711 del cuerpo) que la del texto (7 pt) bajo su línea de base
# (descendente, 0,244): el cuadro sube la mitad de la diferencia (≈ 1,75 pt; medido en Excel, 5 px a 2200)
SUBIDA_CENTRO_TARTA = (24 * (0.928 - 0.711) - 7 * 0.244) / 2


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
    """Las series en el orden de la leyenda: por grupos, como van en el gráfico, y dentro de cada grupo por su
    «order». El idx de <c:legendEntry> es la posición en esta lista, no el idx de la serie."""
    lista = []
    for g in GRUPOS.finditer(xml):
        sers = re.findall(r'<c:ser>.*?</c:ser>', g.group(0), re.S)
        lista += sorted(sers, key=lambda t: int(valor(hijo(hijos(t), "order")) or 0))
    return lista


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


def muestras_anchas(xml):
    """Añade la serie de línea invisible que ensancha las muestras de la leyenda (None si no hace falta)."""
    if any(es_muestra(s) for s in re.findall(r'<c:ser>.*?</c:ser>', xml, re.S)) or not solo_barras_en_leyenda(xml):
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
            nombre = re.search(r'<c:tx>.*?<c:v>([^<]*)</c:v>', ser, re.S)
            hechos.append(f"«{html.unescape(nombre.group(1)) if nombre else 'serie'}» (columnas como línea divisoria)")
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
                detalle.append(f"Panel {n}: sin dato de referencia en las unidades, sin línea base")
                continue
            texto, m = hallado
            base = int(next(g for g in m.groups() if g))
            corto = texto.replace("\n", " ")[:60]
            if re.search(rf'<c:tx><c:v>Base {base}</c:v></c:tx>', xml):
                detalle.append(f"Panel {n}: ya tiene la línea base {base}")
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


def nombre_serie(ser):
    m = re.search(r'<c:tx>.*?<c:v>([^<]*)</c:v>', ser, re.S)
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
    return xml, detalle, extremos


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
            orden = int(valor(hijo(hijos(ser), "order")) or 0)
            grupos.append({"tipo": tipo, "ser": ser, "clase": clase, "orden": orden, "oculta": ser in ocultas})
    peso = {"linea": 0, "trama": 1, "marcador": 2}
    usadas = [s for s in grupos if s["clase"] and not s["oculta"]]
    usadas.sort(key=lambda s: (peso[s["clase"]], 0 if s["tipo"] == "areaChart" else 1, s["orden"]))
    return usadas, [s for s in grupos if s["clase"] and s["oculta"]]


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
        poner(h, orden, "marker", marcador(*MARCADOR_SOLO, color))
    return "<c:ser>" + "".join(t for _, t in h) + "</c:ser>"


def puntos_tarta(ser, tipo, estilos):
    """Cada sector con la trama que le toca, en el orden de la leyenda (las categorías)."""
    h = hijos(ser)
    val = hijo(h, "val") or ""
    m = re.search(r'<c:ptCount val="(\d+)"', val)
    n = int(m.group(1)) if m else 0
    viejos = {valor(hijo(hijos(t), "idx")): t for nombre, t in h if nombre == "dPt"}
    h = [x for x in h if x[0] != "dPt"]
    nuevos = []
    for k in range(n):
        dpt = hijos(viejos[str(k)]) if str(k) in viejos else [["idx", f'<c:idx val="{k}"/>'], ["bubble3D", '<c:bubble3D val="0"/>']]
        poner(dpt, ORDEN_DPT, "spPr", sppr_trama(estilos[k % len(estilos)]))
        nuevos.append("<c:dPt>" + "".join(t for _, t in dpt) + "</c:dPt>")
    orden = ORDEN_SERIE[tipo]
    pos = next((i for i, x in enumerate(h) if x[0] in orden and orden.index(x[0]) > orden.index("dPt")), len(h))
    h[pos:pos] = [["dPt", d] for d in nuevos]
    return "<c:ser>" + "".join(t for _, t in h) + "</c:ser>", n


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


def tramas_y_lineas(xml, estilos, ancho_grafico=None, color_publicacion=None):
    """Aplica los estilos de la guía a las series de un gráfico. Devuelve el xml y las líneas del detalle."""
    detalle = []
    tarta = re.search(r'<c:(pieChart|doughnutChart)>.*?</c:\1>', xml, re.S)
    if tarta:
        tipo = tarta.group(1)
        g = tarta.group(0)
        s = re.search(r'<c:ser>.*?</c:ser>', g, re.S)
        if not s:
            return xml, ["sin series"]
        nuevo, n = puntos_tarta(s.group(0), tipo, estilos)
        xml = xml.replace(g, g.replace(s.group(0), nuevo, 1), 1)
        detalle.append(f"{n} sectores con las tramas 1 a {min(n, len(estilos))}, en el orden de la leyenda")
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
    con_marcador = [k for k, s in enumerate(usadas)
                    if s["clase"] == "linea" and estilos[k % len(estilos)]["linea"][2]]
    espaciados, salto, gemelos = [], 0, {}
    for k, s in enumerate(usadas):
        # En un intervalo, los marcadores van sobre la línea negra: no pueden ser negros
        if extremos and s["clase"] == "marcador" and estilos[(k + salto) % len(estilos)]["linea"][0] == "000000":
            salto += 1
        estilo = estilos[(k + salto) % len(estilos)]
        limpia, n_puntos = puntos_como_su_serie(s["ser"])
        if n_puntos:
            detalle.append(f"«{nombre_serie(s['ser'])}»: {n_puntos} punto{'s' if n_puntos > 1 else ''} con el mismo "
                           "color que su serie: sin ese formato, para que lleven la trama de la serie")
        if s["clase"] == "marcador":
            gemelos[firma_marcador(s["ser"])] = estilo
        original = s["ser"]
        s = {**s, "ser": limpia}
        nueva = con_estilo(s, estilo)
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
            descripcion = f"círculo de 5 pt {estilo['linea'][0]}"
        elif s["clase"] == "linea":
            descripcion = estilo["nombre"].split(" / ")[1] + f" {estilo['linea'][0]}, 2,25 pt"
        else:
            descripcion = estilo["nombre"].split(" / ")[0]
        detalle.append(f"{k + 1}. «{nombre_serie(s['ser'])}» ({que}): {descripcion}")
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
        for n, (_, rid, ancho) in enumerate(graficos, 1):
            ruta_graf = relaciones[rid][1]
            xml, lineas = tramas_y_lineas(z.read(ruta_graf).decode("utf-8"), estilos, ancho, color)
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


def comparar(trabajo):
    estado = leer_estado(trabajo)
    _, pasos = nombres(trabajo)
    origen = Path(estado.get("origen", ""))
    if not origen.is_file():
        origen = pasos / estado["pasos"][0]["archivo"]
    actual = copia_actual(trabajo)
    with zipfile.ZipFile(origen) as zo, zipfile.ZipFile(actual) as zf:
        lineas = comparar_libros(zo, zf, estado.get("idioma", "es"))
    return {"trabajo": str(trabajo), **estado, "comparacion": lineas, "comparado": str(actual), "original": str(origen)}


def nombre_terminado(origen, carpeta):
    base = re.sub(r'\bORIGINAL\b', "TERMINADO", origen.stem) if re.search(r'\bORIGINAL\b', origen.stem) \
        else origen.stem + " TERMINADO"
    destino, n = carpeta / f"{base}.xlsx", 2
    while destino.exists():   # nunca se pisa un TERMINADO que ya exista
        destino, n = carpeta / f"{base} ({n}).xlsx", n + 1
    return destino


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
    borrados = []
    for c in (trabajo, trabajo.with_name(trabajo.stem + " (2).xlsx")):
        if c.exists():
            c.unlink()
            borrados.append(c.name)
    if pasos.is_dir() and pasos.name.endswith(" (pasos)"):
        shutil.rmtree(pasos)
        borrados.append(pasos.name)
    return {"terminado": str(destino), "borrados": borrados}


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
    ordenes = {"empezar": empezar, "estado": lambda t: {"trabajo": t, **leer_estado(t)}, "ir": ir, "reiniciar": reiniciar, "paso1": paso1, "paso2": paso2, "paso3": paso3, "paso4": paso4, "paso5": paso5, "comparar": comparar, "sin_eje_vertical": sin_eje_vertical, "terminar": terminar, "info": info,
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
