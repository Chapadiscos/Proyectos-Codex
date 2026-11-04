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
  maquetar_excel.py info    <archivo.xlsx>
  maquetar_excel.py publicaciones
  maquetar_excel.py guardar_publicacion '<json>'
  maquetar_excel.py borrar_publicacion <id>
  maquetar_excel.py paletas [actualizar]
"""
import html
import io
import json
import math
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


# Leyendas en minúscula salvo las siglas (y la primera letra, y los nombres propios). Solo se tocan los nombres
# que el autor escribió enteros en mayúsculas: en uno con minúsculas no se sabe qué palabra es sigla o propia.
SIGLAS = {"EEUU", "EE.UU.", "EE", "UU", "UEM", "UE", "EA", "PIB", "IPC", "IPCA", "IAPC", "IPRI", "BCE", "BDE", "FMI",
          "OCDE", "OPEP", "IA", "TIC", "PYME", "PYMES", "VAB", "EPA", "PMI", "CNMV", "TAE", "TIN", "ICO", "IRPF",
          "IVA", "I+D", "SA", "EBAE", "ROE", "ROA", "NPL", "BBVA", "CCAA", "AAPP", "ISFLSH", "PER", "ETF", "EURIBOR",
          "FED", "INE", "AEAT", "BIS", "BPI", "UK", "US", "USA", "USD", "EUR", "GBP", "JPY", "CNY", "ESG", "TR", "EMU",
          "GDP", "CPI", "HICP", "ECB", "IMF", "OECD", "SME", "SMES", "AI", "UN", "CET1", "LTV", "DSTI", "SMI", "OIS"}
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
    "MAY", "JUNE", "JULY", "AUGUST", "SEPTEMBER", "OCTOBER", "NOVEMBER", "DECEMBER"}
NOMBRES_PROPIOS_SOLO_EN = {"EURO", "AREA", "MAY", "MARCH", "UNITED", "STATES", "KINGDOM", "LATIN", "AMERICA"}
ROMANOS = re.compile(r'(?=[IVXLC]+$)M*(C[MD]|D?C{0,3})(X[CL]|L?X{0,3})(I[XV]|V?I{0,3})$')


def en_minuscula(texto, idioma="es"):
    """Nombre de leyenda en minúscula salvo las siglas, los nombres propios, los números romanos y la primera
    letra (y la de después de un punto). Solo si está entero en mayúsculas; si no, como lo escribió el autor."""
    letras = [c for c in texto if c.isalpha()]
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
        if limpia in siglas or limpia.replace(".", "") in siglas or any(c.isdigit() for c in limpia) or (limpia and ROMANOS.match(limpia)):
            escrita = SIGLAS_ESCRITAS.get(limpia, limpia)
            if mayuscula and escrita[:1].islower():
                escrita = escrita[0].upper() + escrita[1:]   # «pymes» al principio: «Pymes»
            nueva = parte.replace(limpia, escrita) if limpia else parte
        elif limpia in propios:
            nueva = parte.replace(limpia, limpia[0] + limpia[1:].lower())
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
    return re.sub(r'<c:ser>.*?</c:ser>', serie, xml, flags=re.S), hechos


RE_PANEL = re.compile(r'\s*\d+(?:\.\d+)*\.?\s*[a-zA-Z]\b')   # «1 a», «1.a», «2.6.a»: título de panel


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
                tipos[i] = ("unidades" if x < g[0] + g[2] / 4 else "interior", gi)
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
            detalle.append(f"Fuentes «{corto}»: Roboto Light 7 pt" + "".join(f"; {n}" for n in notas))
        elif tipo == "unidades":
            a = fijar_letra(a, 700, ROBOTO)
            detalle.append(f"Unidades en la hoja «{corto}»: Roboto Regular 7 pt")
        elif tipo == "interior":
            a = fijar_letra(a, 700, ROBOTO)
            detalle.append(f"Texto sobre el gráfico, a la derecha «{corto}»: Roboto Regular 7 pt, donde lo dejó el autor")
        else:
            a = fijar_letra(a, 800, ROBOTO)
            detalle.append(f"Título de panel «{corto}»: Roboto Regular 8 pt")
        partes[k] = a
    for falta, nombre in (("grafico", "«Gráfico NN»"), ("titulo", "título del gráfico")):
        if falta not in hechos:
            detalle.append(f"Aviso: no encuentro el {nombre}")
    cambios[ruta] = "".join(partes).encode("utf-8")

    # Textos de cada gráfico y de sus formas (unidades)
    relaciones = rels(z, ruta)
    anchos = anchos_graficos(z, dibujo)
    hojas_datos = {}
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
        cambios[ruta_graf] = graf.encode("utf-8")
        linea = f"Panel {i}: general e interior Roboto Regular 6 pt"
        if cuentas:
            linea += "; " + ", ".join(cuentas)
        for tipo, ruta_formas in rels(z, ruta_graf).values():
            if tipo.endswith("/chartUserShapes"):
                formas, unidades, otros = maquetar_formas_grafico(z.read(ruta_formas).decode("utf-8"))
                formas, hechos = textos_trimestres(formas, estado["idioma"])
                if hechos:
                    especiales.append("trimestres: " + ", ".join(hechos[:4]))
                cambios[ruta_formas] = formas.encode("utf-8")
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
    for ruta_hoja, hoja in hojas_datos.items():
        cambios[ruta_hoja] = hoja.encode("utf-8")
    if estilos != estilos_antes:
        cambios["xl/styles.xml"] = estilos.encode("utf-8")
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
    entrada más larga (una entrada por línea) y el alto de sus entradas; con `leyenda` None, no se toca."""
    x, y, w, h = dentro
    trazado = ('<c:layout><c:manualLayout><c:layoutTarget val="inner"/><c:xMode val="edge"/><c:yMode val="edge"/>'
               f'<c:x val="{x / ancho:.6f}"/><c:y val="{y / alto:.6f}"/><c:w val="{w / ancho:.6f}"/>'
               f'<c:h val="{h / alto:.6f}"/></c:manualLayout></c:layout>')
    xml = re.sub(r'(<c:plotArea>\s*)(<c:layout>.*?</c:layout>|<c:layout/>)?', lambda m: m.group(1) + trazado,
                 xml, count=1, flags=re.S)
    if leyenda is None:
        return xml
    lx, ly, lmax = leyenda
    entradas = entradas_leyenda(xml) or [("Serie", False)]
    # Muestra de color, separación y márgenes de la leyenda (pt); la de una línea mide unos 16 pt más
    clave = CLAVE_LEYENDA + (CLAVE_LINEA_DE_MAS if any(linea for _, linea in entradas) else 0)
    # Excel centra las entradas en el cuadro: con el ancho justo de la línea más larga (partiendo los nombres
    # que no caben en la columna 2), la muestra queda al principio
    partidos = [partir_lineas(n, lmax - clave - 2, 7, medir) for n, _ in entradas]
    lw = max(w for anchos in partidos for w in anchos) + clave + 2
    # Excel da a cada entrada el alto de la más alta y reparte lo que sobre: alto justo para todas
    lh = len(entradas) * (max(len(a) for a in partidos) * 7 * INTERLINEA + 1.5) + 4

    def cambiar(m):
        lay = ('<c:layout><c:manualLayout><c:xMode val="edge"/><c:yMode val="edge"/>'
               f'<c:x val="{lx / ancho:.6f}"/><c:y val="{ly / alto:.6f}"/><c:w val="{lw / ancho:.6f}"/>'
               f'<c:h val="{min(lh, alto - ly) / alto:.6f}"/></c:manualLayout></c:layout>')
        bloque = re.sub(r'<c:layout>.*?</c:layout>|<c:layout/>', "", m.group(0), count=1, flags=re.S)
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
    for g in GRUPOS.finditer(xml):
        for ser in re.findall(r'<c:ser>.*?</c:ser>', g.group(0), re.S):
            idx = re.search(r'<c:idx val="(\d+)"', ser).group(1)
            nombre = re.search(r'<c:tx>.*?<c:v>([^<]*)</c:v>.*?</c:tx>', ser, re.S)
            if idx in borradas or not nombre:
                continue
            sppr = hijo(hijos(ser), "spPr") or ""
            sin_linea = re.search(r'<a:ln\b[^>]*>\s*<a:noFill/>', sppr)
            entradas.append((html.unescape(nombre.group(1)),
                             g.group(1) in ("lineChart", "line3DChart", "scatterChart", "radarChart") and not sin_linea))
    return entradas


def sin_leyenda(xml, ancho_pt):
    """Por qué el autor ha dejado el gráfico sin leyenda (None si la lleva): no la hay, ha borrado todas sus
    entradas o la ha encogido a menos de 10 pt de ancho, donde no se ve (en el 2.6, el panel a)."""
    leyenda = re.search(r'<c:legend>.*?</c:legend>', xml, re.S)
    if not leyenda:
        return "no tiene leyenda"
    series = re.findall(r'<c:ser>.*?<c:idx val="(\d+)"', xml, re.S)
    borradas = set(re.findall(r'<c:legendEntry><c:idx val="(\d+)"/><c:delete val="1"/>', leyenda.group(0)))
    if series and set(series) <= borradas:
        return "ha borrado todas las entradas de la leyenda"
    w = re.search(r'<c:manualLayout>.*?<c:w val="([^"]+)"', leyenda.group(0), re.S)
    if w and float(w.group(1)) * ancho_pt < 10:
        return f"ha encogido la leyenda a {float(w.group(1)) * ancho_pt:.0f} pt de ancho, donde no se ve"
    return None


def es_unidad_grafico(ancla):
    """Unidades dentro del gráfico: cuadro de texto en el 20 % de arriba y el cuarto de la izquierda (donde
    empieza el eje). Lo de más a la derecha es una etiqueta, como «Elecciones EEUU» sobre una barra."""
    x = float(re.search(r'<cdr:from>.*?<cdr:x>([^<]+)</cdr:x>', ancla, re.S).group(1))
    y = float(re.search(r'<cdr:from>.*?<cdr:y>([^<]+)</cdr:y>', ancla, re.S).group(1))
    return y < 0.2 and x < 0.25


def unidades_de(formas):
    """Las anclas de las unidades en las formas del gráfico."""
    return [a for a in re.findall(r'<cdr:relSizeAnchor\b.*?</cdr:relSizeAnchor>', formas, re.S)
            if texto_forma(a).strip() and es_unidad_grafico(a)]


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
    eje = next((e.group(0) for e in re.finditer(r'<c:catAx>.*?</c:catAx>', xml, re.S)
                if re.search(r'<c:axPos val="[bt]"/>', e.group(0)) and '<c:delete val="1"/>' not in e.group(0)), "")
    if es_vertical(eje) and medir:
        # Verticales (paso 1): ocupan a lo alto lo que mide su línea más larga, con el cuerpo que ya tienen
        cuerpo = re.search(r'<c:txPr>.*?<a:defRPr\b[^>]*\bsz="(\d+)"', eje, re.S)
        sz = int(cuerpo.group(1)) if cuerpo else 700
        largo = max([medir(l, sz / 100) for e in etiquetas_categorias(xml) for l in e.split("\n")] or [0])
        alto = SEPARACION_CATEGORIAS + largo + MARGEN_CATEGORIAS
        return sz, "etiquetas en vertical", 1, max(1, math.ceil((alto - LETRA_ABAJO) / paso_pt - 1e-6)), alto
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

            # Sin leyenda (el autor la ha quitado o escondido): el trazado ocupa las dos columnas, como en el
            # TERMINADO del 2.6, y la leyenda se deja como está
            motivo = sin_leyenda(xml, caja(partes[ig])[2] / EMU_PT)
            if motivo:
                detalle.append(f"Aviso: el panel {n} va sin leyenda (el autor {motivo}): el trazado ocupa las dos "
                               "columnas. Comprueba que lo que representa se explica en el título del panel.")
            # Alto: 9 filas hasta el final de las categorías (el trazado, como mínimo 7)
            numeros = ancho_numeros_eje(xml, medir)
            trazado = (ancho_util if motivo else w1) / EMU_PT - numeros
            sz, nota, lineas_cat, filas_cat, alto_cat = filas_categorias(xml, trazado, paso_pt)
            filas = max(FILAS_PANEL, FILAS_MIN_TRAZADO + filas_cat)
            alto_panel = filas * paso_pt + LETRA_VISIBLE
            # Unidades: su línea de base, 2 mm por encima del borde de arriba del trazado
            ini_unidades = inicio + MEDIA_ETIQUETA - UNIDADES_A_GRAFICO - BASE_UNIDADES
            arriba_marco = min(ini_unidades, inicio) if unidades else inicio
            H = inicio + alto_panel - arriba_marco
            dentro = (numeros, inicio - arriba_marco + MEDIA_ETIQUETA, trazado,
                      alto_panel - MEDIA_ETIQUETA - alto_cat)
            xml = disposicion(xml, W, H, dentro, None if motivo else
                              ((x2 - x1) / EMU_PT - LEYENDA_A_LA_IZQUIERDA, inicio - arriba_marco, w2 / EMU_PT), medir)
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
            # Textos sueltos sobre el gráfico, a la derecha: se mueven con él
            antes = caja(partes[ig])[1]
            for ii in [i for i, (t, g) in tipos.items() if t == "interior" and g == ig]:
                xi, yi, wi, hi = caja(partes[ii])
                partes[ii] = colocar(partes[ii], xi, yi + round(arriba_marco * EMU_PT) - antes, wi, hi)
                linea += f" «{html.unescape(texto_forma(partes[ii])).strip()}» se mueve con el gráfico;"
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
    # Oculta en la leyenda
    entrada = f'<c:legendEntry><c:idx val="{idx}"/><c:delete val="1"/></c:legendEntry>'
    if re.search(r'<c:legendPos\b[^>]*/>', xml):
        xml = re.sub(r'(<c:legend>\s*<c:legendPos\b[^>]*/>)', lambda m: m.group(1) + entrada, xml, count=1)
    else:
        xml = xml.replace("<c:legend>", "<c:legend>" + entrada, 1)
    return xml


# Línea divisoria (guía, pág. 14): negra, 1 pt, remate plano y unión en ángulo
LINEA_DIVISORIA = ('<a:ln w="12700" cap="flat"><a:solidFill><a:srgbClr val="000000"/></a:solidFill>'
                   '<a:miter lim="800000"/></a:ln>')


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
    Flechas: como en el TERMINADO, negras de 0,5 pt con punta abierta."""
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
            # Flechas y líneas dibujadas dentro del gráfico
            ruta_dib = next((d for t, d in rels(z, ruta_graf).values() if t.endswith("/chartUserShapes")), None)
            if ruta_dib:
                formas, dibujadas = lineas_dibujadas(z.read(ruta_dib).decode("utf-8"), "cdr")
                if dibujadas:
                    cambios[ruta_dib] = formas.encode("utf-8")
                    detalle.append(f"Panel {n}: " + resumen_lineas(dibujadas))
            ruta_formas = next((d for t, d in rels(z, ruta_graf).values() if t.endswith("/chartUserShapes")), None)
            unidades = [html.unescape(texto_forma(a)).strip() for a in unidades_de(z.read(ruta_formas).decode("utf-8"))] if ruta_formas else []
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
    """Cuadros de texto dentro del gráfico: arriba a la izquierda, las unidades (7 pt); el resto, interior
    (6 pt)."""
    unidades, otros = [], []

    def cambiar(m):
        a = m.group(0)
        texto = texto_forma(a).strip()
        if not texto:
            return a
        if es_unidad_grafico(a):
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
    ordenes = {"empezar": empezar, "estado": lambda t: {"trabajo": t, **leer_estado(t)}, "ir": ir, "reiniciar": reiniciar, "paso1": paso1, "paso2": paso2, "paso3": paso3, "paso4": paso4, "info": info,
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
