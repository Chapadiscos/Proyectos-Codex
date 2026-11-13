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
import html
import io
import json
import os
import re
import shutil
import sys
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


def reiniciar(trabajo):
    """Vuelve a empezar desde el original del autor: borra todas las versiones, rehace «00 Copia exacta»
    con el original (si sigue en su sitio) y la copia de trabajo pasa a ser esa versión."""
    estado = leer_estado(trabajo)
    _, pasos = nombres(trabajo)
    origen = Path(estado.get("origen", ""))
    if not origen.is_file():
        raise Fallo(f"No encuentro el original del autor ({origen}): no puedo reiniciar")
    for p in estado["pasos"]:
        (pasos / p["archivo"]).unlink(missing_ok=True)
    v0 = pasos / "00 Copia exacta.xlsx"
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


def texto_forma(ancla):
    """Texto de una forma, un párrafo por línea."""
    return "\n".join("".join(re.findall(r'<a:t>([^<]*)</a:t>', p))
                     for p in re.findall(r'<a:p>.*?</a:p>', ancla, re.S))


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


# ---------------------------------------------------------------- pasos

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
    borrados = []
    for c in (trabajo, trabajo.with_name(trabajo.stem + " (2).xlsx")):
        if c.exists():
            c.unlink()
            borrados.append(c.name)
    if pasos.is_dir() and pasos.name.endswith(" (pasos)"):
        shutil.rmtree(pasos)
        borrados.append(pasos.name)
    return {"terminado": str(destino), "borrados": borrados}


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
           "paso1": pendiente("Retícula, pastilla y textos"), "paso2": pendiente("Celdas"),
           "paso3": pendiente("Cabeceras"), "paso4": pendiente("Líneas y fondos"),
           "comparar": pendiente("Comparar con el original"), "terminar": terminar, "info": info, "publicaciones": lambda: {},
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
