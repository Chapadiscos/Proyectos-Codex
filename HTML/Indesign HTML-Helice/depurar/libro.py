"""Datos de los libros para la app «InDesign a HTML» (salida en JSON).

    ./libro listar                    libros configurados
    ./libro estado <libro>            capítulos y en qué paso está cada uno
    ./libro datos <libro>             lo que se puede editar desde la app
    ./libro nuevo < datos.json        crea config/libros/<id>.yaml
    ./libro estructura <libro> < datos.json   rehace «ficheros» y «publicar» (bloques y temas)
    ./libro fuentes archivo.otf …     familia, peso y estilo de cada fuente
    ./libro exportar ruta.indd        InDesign exporta el HTML (OK | ERROR, html, imágenes)

Un libro nuevo se crea con la misma estructura que Ponencias 2025 (la prueba completa
del proceso): hereda de ponencias2026.yaml y cambia carpetas, sufijo de las clases,
fuentes, carpeta de Ficheros y bloques y temas de Hélice. Lo que cambie la maquetación
(pies, cuadros, cabecera…) se ajusta después en su .yaml.
"""

import glob
import json
import os
import re
import subprocess
import sys

from . import libros
from .__main__ import RAIZ

INDESIGN = "Adobe InDesign 2026"
EXPORTAR = os.path.join(RAIZ, "herramientas", "exportar_html.jsx")
URL_IMAGEN = re.compile(r"https?://[^\s\"'<>)]+/uploads/[^\s\"'<>)]+\.(?:jpe?g|png|gif|webp)", re.I)


def _salir(datos):
    print(json.dumps(datos, ensure_ascii=False, indent=1))
    return 0


# ---------- Lectura ----------

def listar():
    return [{"id": l.id, "nombre": l.nombre, "raiz": l.raiz, "existe": bool(l.raiz) and os.path.isdir(l.raiz)}
            for l in libros.todos()]


def numeros(texto):
    """«1-3, 5» → [1, 2, 3, 5]"""
    r = []
    for parte in re.split(r"[,\s]+", str(texto).strip()):
        if not parte:
            continue
        a, _, b = parte.partition("-")
        r += list(range(int(a), int(b) + 1)) if b else [int(a)]
    return r


def rango(ns):
    """[1, 2, 3, 5] → «1-3, 5»"""
    partes, ns = [], sorted(ns)
    i = 0
    while i < len(ns):
        j = i
        while j + 1 < len(ns) and ns[j + 1] == ns[j] + 1:
            j += 1
        partes.append(str(ns[i]) if i == j else f"{ns[i]}-{ns[j]}")
        i = j + 1
    return ", ".join(partes)


def estado(libro_id):
    from .css_libro import pendiente, rutas
    from .helice import Publicacion
    from .preparar import destino

    libro = libros.elegir(libro_id)
    cfg = libro.config
    datos = cfg.get("libro") or {}
    carpeta = datos.get("carpeta", "")
    sufijo = datos.get("sufijo_salida", " - Helice")
    pub = Publicacion(libro)

    # Capítulos: los de la estructura de Hélice y los que ya tienen carpeta
    ns = {n for b in (cfg.get("publicar") or {}).get("bloques") or [] for t in b.get("temas") or []
          for n in t.get("capitulos", [])}
    if os.path.isdir(carpeta):
        for d in os.listdir(carpeta):
            m = re.match(r"(\d+) ", d)
            if m and os.path.isdir(os.path.join(carpeta, d)):
                ns.add(int(m.group(1)))

    capitulos = []
    for n in sorted(ns):
        copia = destino(os.path.join(carpeta, "x.indd"), n, cfg)
        dir_cap = os.path.dirname(copia)
        htmls = [h for h in glob.glob(os.path.join(dir_cap, "*.html")) if not h.endswith(sufijo + ".html")]
        depurados = glob.glob(os.path.join(dir_cap, f"*{sufijo}.html"))
        urls = 0
        for txt in glob.glob(os.path.join(dir_cap, "*.txt")):
            urls += len(URL_IMAGEN.findall(open(txt, encoding="utf-8", errors="replace").read()))
        bloque, tema = pub.tema_de(n)
        publicado = pub.estado["capitulos"].get(f"{n:02d}")
        capitulos.append({
            "n": n,
            "carpeta": dir_cap if os.path.isdir(dir_cap) else "",
            "preparado": copia if os.path.exists(copia) else "",
            "html": htmls[0] if htmls else "",
            "imagenes": urls,
            "depurado": depurados[0] if depurados else "",
            "tema": f"{bloque['nombre']} / {tema['nombre']}" if tema else "",
            "con_seccion": bool(tema and pub.seccion_tema(bloque, tema)),
            "publicado": publicado["fecha"] if publicado else "",
        })

    css = (cfg.get("css_libro") or {})
    archivo_css, dir_fuentes, txt_urls = rutas(cfg)
    fuentes = (css.get("fuentes_web") or {}).get("archivos") or []
    return {
        "id": libro.id, "nombre": libro.nombre, "raiz": libro.raiz, "carpeta": carpeta,
        "existe": os.path.isdir(libro.raiz or "/nada"),
        "config": libro.ruta,
        "css": archivo_css if css.get("generar") else "",
        "css_pendiente": bool(css.get("generar")) and os.path.exists(pendiente(archivo_css))
        and bool(open(pendiente(archivo_css), encoding="utf-8").read().strip()),
        "fuentes_propias": len(fuentes),
        "fuentes_en_helice": _fuentes_en_helice(archivo_css) if fuentes else 0,
        "puede_subir_fuentes": bool(fuentes) and bool(carpeta_fuentes(cfg)),
        "publicar": bool((cfg.get("publicar") or {}).get("bloques")),
        "capitulos": capitulos,
    }


def _fuentes_en_helice(archivo_css):
    if not os.path.exists(archivo_css):
        return 0
    return len(re.findall(r'src: url\("https?://', open(archivo_css, encoding="utf-8").read()))


def carpeta_fuentes(cfg):
    """Ruta en Ficheros de Hélice de las fuentes del libro: ficheros.fuentes o «<raíz>/Fuentes»."""
    f = cfg.get("ficheros") or {}
    if f.get("fuentes"):
        return list(f["fuentes"])
    if f.get("capitulo"):
        return [f["capitulo"][0], "Fuentes"]
    return []


def datos(libro_id):
    """Lo que la app deja editar de un libro (estructura de Hélice y carpeta de Ficheros)."""
    libro = libros.elegir(libro_id)
    cfg = libro.config
    bloques = []
    for b in (cfg.get("publicar") or {}).get("bloques") or []:
        bloques.append({"nombre": b.get("nombre", ""), "seccion": str(b.get("seccion") or ""),
                        "temas": [{"nombre": t.get("nombre", ""), "capitulos": rango(t.get("capitulos", [])),
                                   "seccion": str(t.get("seccion") or "")} for t in b.get("temas") or []]})
    ficheros = (cfg.get("ficheros") or {}).get("capitulo") or [""]
    return {"id": libro.id, "nombre": libro.nombre, "carpeta_ficheros": ficheros[0], "bloques": bloques}


# ---------- Fuentes ----------

def unificar(infos):
    """Una familia para todas: los nombres internos no siempre coinciden (en Adobe Clean UX
    las Light dicen «Adobe Clean»); las que son el principio de otra pasan a la más usada."""
    from collections import Counter

    cuenta = Counter(i["familia"] for i in infos)
    for i in infos:
        mayores = [f for f, _ in cuenta.most_common() if f != i["familia"] and f.startswith(i["familia"])]
        if mayores:
            i["familia"] = mayores[0]
    return infos


def info_fuente(ruta):
    from fontTools.ttLib import TTFont

    f = TTFont(ruta, lazy=True)
    nombres = f["name"]
    familia = str(nombres.getDebugName(16) or nombres.getDebugName(1) or "")
    estilo_id = str(nombres.getDebugName(17) or nombres.getDebugName(2) or "Regular")
    os2 = f["OS/2"]
    cursiva = bool(os2.fsSelection & 1) or bool(re.search(r"Italic|Oblique|\bIt\b", estilo_id))
    # Nombre del estilo en InDesign sin la cursiva: «Light Italic» → «Light»
    base = re.sub(r"\s*(Italic|Oblique|It)\b", "", estilo_id).strip() or "Regular"
    return {"archivo": ruta, "familia": familia, "estilo_indesign": estilo_id, "base": base,
            "peso": int(os2.usWeightClass), "estilo": "italic" if cursiva else "normal"}


# ---------- Alta y edición ----------

def _q(s):
    """Cadena YAML entre comillas dobles (JSON es YAML válido)."""
    return json.dumps(str(s), ensure_ascii=False)


def seccion_de(enlace):
    """Identificador de sección de Hélice a partir de su enlace del panel (o el número tal cual)."""
    enlace = str(enlace or "").strip()
    if enlace.isdigit():
        return int(enlace)
    ids = re.findall(r"/(\d{4,})(?=/|$|\?|#)", enlace)
    return int(ids[-1]) if ids else None


def bloque_publicar(bloques):
    lineas = [
        "# Publicación en Hélice por la API (./publicar). Bloques y temas son Menús creados a mano",
        "# en el panel (la API no puede); cada capítulo es una sección de Información «Capítulo NN»",
        "# con su HTML. Iconos, en el panel.",
        "publicar:",
        '  estado: "{carpeta}/helice_publicacion.json"     # identificadores creados y capítulos publicados',
        '  titulo: "Capítulo {n:02d}"',
        "  layout: 1",
        "  bloques:",
    ]
    for b in bloques:
        lineas.append(f"    - nombre: {_q(b['nombre'])}")
        s = seccion_de(b.get("seccion"))
        if s:
            lineas.append(f"      seccion: {s}")
        lineas.append("      temas:")
        for t in b.get("temas") or []:
            caps = numeros(t.get("capitulos", ""))
            s = seccion_de(t.get("seccion"))
            lineas.append(f"        - {{nombre: {_q(t['nombre'])}, capitulos: {json.dumps(caps)}"
                          + (f", seccion: {s}" if s else "") + "}")
    if not bloques:
        lineas[-1] = "  bloques: []"
    return "\n".join(lineas) + "\n"


def bloque_ficheros(raiz_ficheros):
    return (
        "# Carpetas en Ficheros de Hélice: imágenes de cada capítulo y fuentes del libro\n"
        "# (la app crea las que falten)\n"
        "ficheros:\n"
        f'  capitulo: [{_q(raiz_ficheros)}, "{{bloque}}", "{{tema}}", "Capítulo {{n:02d}}"]\n'
        f"  fuentes: [{_q(raiz_ficheros)}, \"Fuentes\"]\n"
    )


def _reemplazar_seccion(texto, clave, nuevo):
    """Sustituye la sección de primer nivel «clave:» (con sus comentarios de encima) o la añade."""
    lineas = texto.splitlines(keepends=True)
    inicio = next((i for i, l in enumerate(lineas) if l.startswith(clave + ":")), None)
    if inicio is None:
        return texto.rstrip("\n") + "\n\n" + nuevo
    while inicio > 0 and lineas[inicio - 1].startswith("#"):
        inicio -= 1
    fin = next((i for i in range(inicio + 1, len(lineas)) if re.match(r"[A-Za-z_]", lineas[i])
                and not lineas[i].startswith(clave + ":")), len(lineas))
    while fin > inicio and lineas[fin - 1].startswith("#"):  # comentarios de la sección siguiente
        fin -= 1
    while fin > inicio and not lineas[fin - 1].strip():
        fin -= 1
    resto = "".join(lineas[fin:]).lstrip("\n")
    return "".join(lineas[:inicio]) + nuevo + ("\n" + resto if resto else "")


def estructura(libro_id, d):
    libro = libros.elegir(libro_id)
    texto = open(libro.ruta, encoding="utf-8").read()
    if d.get("carpeta_ficheros"):
        texto = _reemplazar_seccion(texto, "ficheros", bloque_ficheros(d["carpeta_ficheros"]))
    texto = _reemplazar_seccion(texto, "publicar", bloque_publicar(d.get("bloques") or []))
    _validar(texto, libro.ruta)
    with open(libro.ruta, "w", encoding="utf-8") as f:
        f.write(texto)
    return {"ok": True, "config": libro.ruta}


def _validar(texto, ruta):
    import yaml

    yaml.safe_load(texto)  # que no quede un .yaml roto
    datos = yaml.safe_load(texto) or {}
    for b in (datos.get("publicar") or {}).get("bloques") or []:
        for t in b.get("temas") or []:
            if not t.get("capitulos"):
                raise ValueError(f"«{b['nombre']} / {t['nombre']}»: faltan sus capítulos")


def ident(nombre):
    s = nombre.lower()
    for a, b in zip("áéíóúüñ", "aeiouun"):
        s = s.replace(a, b)
    return re.sub(r"[^a-z0-9]+", "", s) or "libro"


def nuevo(d):
    """Crea config/libros/<id>.yaml a partir de los datos del formulario de la app."""
    nombre = d["nombre"].strip()
    lid = ident(d.get("id") or nombre)
    ruta = os.path.join(libros.DIR_LIBROS, lid + ".yaml")
    if os.path.exists(ruta):
        raise ValueError(f"Ya hay un libro «{lid}» ({ruta})")
    raiz = d["raiz"].rstrip("/")
    carpeta = (d.get("carpeta") or "").rstrip("/") or os.path.join(raiz, f"{d['nombre_archivos']} (APP)")
    archivos = d.get("nombre_archivos") or os.path.basename(carpeta).replace(" (APP)", "")
    sufijo = "-" + d["sufijo"].strip().lstrip("-")
    s_re = re.escape(sufijo).replace("\\-", "-")
    fuentes = d.get("fuentes") or {}

    # Fuentes: propias (.otf/.ttf que se suben a Hélice) o de Adobe Fonts (kit)
    if fuentes.get("tipo") == "propias":
        infos = fuentes.get("detalle") or unificar([info_fuente(a) for a in fuentes.get("archivos") or []])
        familias = sorted({i["familia"] for i in infos})
        bloque_fuentes = "  fuentes_web:\n" \
            '    carpeta: "{carpeta}/CSS Helice/Fuentes"       # aquí se dejan en .woff2\n' \
            "    archivos:                                     # familia, peso, estilo, original\n" + "".join(
                f"      - [{_q(i['familia'])}, {i['peso']}, {i['estilo']}, {_q(i['archivo'])}]\n" for i in infos)
        pesos = "".join(
            f"    {_q(f)}: {{" + ", ".join(sorted({f'{_q(i["base"])}: {i["peso"]}' for i in infos if i["familia"] == f}))
            + "}\n" for f in familias)
        mapa = "".join(f"    {_q(f)}: {_q(f)}\n" for f in familias)
        inyectar = "inyectar:\n  head: []                                        # las fuentes van en la CSS del libro\n"
    else:
        bloque_fuentes = ""
        pesos = ""
        mapa = "".join(f"    {_q(a)}: {_q(b)}\n" for a, b in (fuentes.get("familias") or {}).items())
        kit = fuentes.get("kit", "").strip()
        inyectar = ("inyectar:\n  head:\n    - html: |\n        <!-- Adobe Fonts -->\n"
                    f'        <link rel="stylesheet" href="{kit}">\n') if kit else "inyectar:\n  head: []\n"

    css = f"{{carpeta}}/CSS Helice/helice_{lid}.css"
    css_abs = css.format(carpeta=carpeta)
    texto = f"""# {nombre} → Hélice. Creado con la app «InDesign a HTML».
# Hereda de Ponencias 2026; aquí solo lo que cambia (como Ponencias 2025, la prueba
# completa del proceso). Pies, cuadros, cabecera…: se ajustan aquí si el libro es distinto.
base: ponencias2026.yaml

libro:
  nombre: {_q(nombre)}
  raiz: {_q(raiz)}
  carpeta: {_q(carpeta)}
  nombre_txt: {_q("{n:02d}" + archivos.replace(" ", "") + ".txt")}

preparar:
  destino: {_q("{carpeta}/{n:02d} " + archivos + " (APP)/{n:02d} " + archivos + " (APP).indd")}
  figuras:
    estilos_pie: ["Pie Figura"]
    titulo: "^Figura\\\\.?[\\\\s\\\\u00A0]+(\\\\d+)"      # «Figura 1:» y también «Figura. 6:»
    cita: "Figuras?"
    compuesta: "F{{cap}}.{{n}}"
  # Vídeos: QR con su pie «Video N:» al lado; siempre a JPG
  otras_figuras:
    - {{clave: video, etiqueta: "Vídeo", titulo: "^V[ÍíIi]deo\\\\.?[\\\\s\\\\u00A0]+(\\\\d+)", cita: "V[íi]deos?", nombre: "V{{cap}}.{{n}}", siempre_jpg: true}}
  cuadros: []
  no_partir_vinetas:
    final_si_unica: true
    nivel: "Viñeta (\\\\d+)"
    continuacion: []

# Sufijo del libro en las clases del HTML (que no pise los estilos de otros libros en Hélice)
renombrar_clases:
  sufijo: {_q(sufijo)}
  excluir: ["_idGen.*", "CharOverride-\\\\d+", "ParaOverride-\\\\d+", "Marco-.*", "Basic-.*", "P-rrafo-b-sico",
            "No-paragraph-style", "_id.*", "_listStyle.*", "HorizontalRule-\\\\d+", {_q(".*" + s_re)}]
  equivalencias: {{}}

# CSS de Hélice del libro: la genera la app a partir de la CSS que exporta InDesign y se
# completa con cada capítulo (lo nuevo se copia para añadirlo al final de la de Hélice)
css_libro:
  generar: true
  archivo: {_q(css)}
{bloque_fuentes}
estilos_capitulo:
  css_helice: {_q(css_abs)}
  fuentes:
{mapa or "    {}" + chr(10)}  pesos_indesign:
{pesos or "    {}" + chr(10)}  peso_normal_por_familia: {{}}
  parrafos_sangrados: {{clases: {{}}}}
  fuentes_a_clase: {{}}
  clases_a_estilo:
    {_q("noPartir" + sufijo)}: {{white-space: nowrap}}

limpieza:
  clases_eliminar: ["_idGen.*", "CharOverride-\\\\d+", "ParaOverride-\\\\d+", {_q("noPartir" + sufijo)}, "Marco-.*"]

correcciones_indesign:
  clase_texto_vineta: {_q("Texto-base---Viñeta" + sufijo)}
  clase_numerada: {_q("Viñetas_Viñeta-1--Numero-" + sufijo)}
  clase_madre_vacia: {_q("Viñetas_Viñeta-1--•-" + sufijo)}
  clases_con_marca_propia: {{}}

reglas_helice:
  cabecera_con_qr: false
  ideas_basicas: {{patron: "^IB\\\\d+\\\\.", estilo: {{max-width: 60%, display: block, margin: 0 auto}}}}

{inyectar}
salida:
  vista_previa_css: {_q(css_abs)}

{bloque_ficheros(d.get("carpeta_ficheros") or nombre)}
{bloque_publicar(d.get("bloques") or [])}"""
    texto = texto.replace("pesos_indesign:\n    {}\n", "pesos_indesign: {}\n").replace("fuentes:\n    {}\n", "fuentes: {}\n")
    _validar(texto, ruta)
    with open(ruta, "w", encoding="utf-8") as f:
        f.write(texto)
    # Comprobar que se carga bien
    libro = libros.Libro(ruta)
    return {"ok": True, "id": libro.id, "config": ruta}


# ---------- Exportar ----------

def exportar(indd):
    """InDesign exporta el HTML del .indd en su carpeta."""
    script = (f'with timeout of 900 seconds\n tell application "{INDESIGN}" to do script '
              f'(POSIX file {_q(EXPORTAR)}) language javascript with arguments '
              f'{{{_q(os.path.abspath(indd))}, {_q(os.path.join(RAIZ, "salida"))}}}\nend timeout')
    os.makedirs(os.path.join(RAIZ, "salida"), exist_ok=True)
    r = subprocess.run(["osascript", "-e", script], capture_output=True, text=True)
    res = r.stdout.strip() if r.returncode == 0 else "error|" + r.stderr.strip()
    if not res.startswith("ok|"):
        return f"ERROR\n\nInDesign no ha podido exportar el HTML: {res.partition('|')[2]}"
    html = res[3:]
    imagenes = [f for f in glob.glob(os.path.join(os.path.dirname(html), "*-web-resources", "image", "*"))
                if not os.path.basename(f).startswith(".")]
    if not imagenes:  # todos los capítulos llevan al menos la cabecera
        return (f"ERROR\n{html}\nEl HTML exportado no tiene imágenes ({os.path.getsize(html)} bytes): parece que "
                "InDesign no ha exportado el capítulo completo. Revisa el documento y vuelve a intentarlo.")
    return f"OK\n{html}\n{len(imagenes)}"


def main(argv=None):
    args = list(argv if argv is not None else sys.argv[1:])
    if not args:
        print(__doc__)
        return 1
    orden, resto = args[0], args[1:]
    try:
        if orden == "listar":
            return _salir(listar())
        if orden == "estado":
            return _salir(estado(resto[0]))
        if orden == "datos":
            return _salir(datos(resto[0]))
        if orden == "fuentes":
            return _salir(unificar([info_fuente(a) for a in resto]))
        if orden == "nuevo":
            return _salir(nuevo(json.load(sys.stdin)))
        if orden == "estructura":
            return _salir(estructura(resto[0], json.load(sys.stdin)))
        if orden == "exportar":
            print(exportar(resto[0]))
            return 0
    except Exception as e:  # la app enseña el motivo
        return _salir({"error": f"{e}"})
    print(__doc__)
    return 1


if __name__ == "__main__":
    sys.exit(main())
