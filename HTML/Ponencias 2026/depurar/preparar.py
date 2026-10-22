"""Prepara el .indd de imprenta de un capítulo para exportarlo a HTML.

Uso: ./preparar "Libro x Secciones/Seccion II (4-17) Ponencias 2026.indd" --capitulo 5
     ./preparar "Maquetas/Carpeta 1 Ponencias 2026/1 Ponencias 2026.indd"
     (--capitulo 5 6 7, o --capitulo todos; --forzar rehace las copias que ya existan)

1. Reconoce el libro por la ruta (config/libros/<libro>.yaml) y copia el .indd al
   destino del libro (preparar.destino; la carpeta del capítulo en la versión APP).
   El original no se toca. Con --forzar, la copia anterior pasa a «… (anterior).indd».
   En un archivo de sección (varios capítulos: secciones de InDesign con el número de
   capítulo como marcador), la copia se queda solo con las páginas del capítulo.
2. InDesign ejecuta herramientas/preparar_html.jsx sobre la copia: convierte en JPG la
   cabecera, tablas, cuadros y figuras compuestas (junto a la copia), vacía maestras,
   limpia el texto, ancla las imágenes y borra estilos y muestras sin uso.
3. Escribe el informe en salida/<copia>.preparar.txt y lo muestra.

--plan    no prepara nada; para la app, línea 1: ORIGINAL | SECCION | PREPARADO | ERROR,
          línea 2: libro; después «número|copia|EXISTE o NUEVA» por capítulo
--resumen salida para la app (un capítulo): OK | AVISOS | ERROR, copia y el informe
"""

import argparse
import json
import os
import re
import shutil
import subprocess
import sys

from . import libros
from .__main__ import RAIZ

JSX = os.path.join(RAIZ, "herramientas", "preparar_html.jsx")
INDESIGN = "Adobe InDesign 2026"


def main(argv=None):
    ap = argparse.ArgumentParser(prog="preparar", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("indd", help="capítulo de InDesign de imprenta")
    ap.add_argument("--libro", help="libro de config/libros (por defecto, según la ruta)")
    ap.add_argument("--capitulo", nargs="+", help="capítulos que preparar de un archivo de sección (o «todos»)")
    ap.add_argument("--destino", help="carpeta para la copia y sus JPG (en vez de la del libro)")
    ap.add_argument("--forzar", action="store_true", help="rehace la copia si ya existe")
    ap.add_argument("--plan", action="store_true", help="solo dice qué haría (para la app)")
    ap.add_argument("--resumen", action="store_true", help="salida breve para la app")
    args = ap.parse_args(argv)

    try:
        original = os.path.abspath(args.indd)
        if not os.path.isfile(original):
            raise ValueError(f"No existe {original}")
        libro = libros.elegir(args.libro, original)
        cfg = libro.config.get("preparar") or {}
        n = numero(original)
        if n is not None and _misma(destino(original, n, libro.config, args.destino), original):
            estado, caps = "PREPARADO", [n]
        else:
            estado, caps, aviso = capitulos(original, n)
            if estado == "SECCION" and not args.plan:
                caps = _elegidos(args.capitulo, caps)
    except ValueError as e:
        if args.plan or args.resumen:  # la app lee el error de la salida
            print(f"ERROR\n\n{e}")
            return 0
        print(f"ERROR: {e}")
        return 1

    copias = [(cap, destino(original, cap, libro.config, args.destino)) for cap in caps]
    if args.plan:
        print(f"{estado}\n{libro.nombre}")
        for cap, copia in copias:
            print(f"{cap}|{copia}|{'EXISTE' if os.path.exists(copia) else 'NUEVA'}")
        return 0

    codigo = 0
    for cap, copia in copias:
        lineas = preparar(original, copia, cap, cfg, args.forzar)
        if aviso and lineas[0] == "ok":
            lineas.append("AVISO|" + aviso)
        texto = _informe(copia, lineas)
        nombre = os.path.splitext(os.path.basename(copia))[0]
        os.makedirs(os.path.join(RAIZ, "salida"), exist_ok=True)
        with open(os.path.join(RAIZ, "salida", nombre + ".preparar.txt"), "w", encoding="utf-8") as f:
            f.write(texto + "\n")
        if args.resumen:
            error = lineas[0] != "ok"
            estado = "ERROR" if error else "AVISOS" if any(l.startswith("AVISO|") for l in lineas) else "OK"
            print(f"{estado}\n{copia}\n{texto}")
            return 0
        print(texto + "\n")
        codigo = codigo or (0 if lineas[0] == "ok" else 1)
    return codigo


def numero(ruta):
    m = re.match(r"\d+", os.path.basename(ruta))
    return int(m.group()) if m else None


def capitulos(original, n):
    """("SECCION" | "ORIGINAL", capítulos, aviso) según las secciones de InDesign del archivo."""
    res = _osascript(
        f'with timeout of 900 seconds\n tell application "{INDESIGN}" to do script '
        f'(POSIX file "{JSX}") language javascript with arguments {{"{original}", "capitulos"}}\nend timeout'
    ).splitlines() or ["error|InDesign no ha devuelto nada"]
    if not res[0].startswith("ok"):
        raise ValueError("InDesign no ha podido abrir el archivo: " + res[0].partition("|")[2])
    aviso = ("El original está abierto en InDesign con cambios sin guardar: "
             "se ha preparado la versión guardada") if res[0] == "ok|modificado" else ""
    caps = [int(l.split("|")[0]) for l in res[1:]]
    if len(caps) > 1:
        return "SECCION", caps, aviso
    if n is None and not caps:
        raise ValueError(f"No sé qué capítulo es: el nombre no empieza por su número ni tiene una sección con él ({os.path.basename(original)})")
    return "ORIGINAL", [n if n is not None else caps[0]], aviso


def _elegidos(pedidos, caps):
    if not pedidos:
        raise ValueError("Es un archivo de sección con los capítulos " + ", ".join(map(str, caps)) + ": indica cuáles con --capitulo")
    if pedidos == ["todos"]:
        return caps
    elegidos = [int(c) for c in pedidos]
    faltan = [c for c in elegidos if c not in caps]
    if faltan:
        raise ValueError(f"El capítulo {', '.join(map(str, faltan))} no está en este archivo (tiene: {', '.join(map(str, caps))})")
    return elegidos


def _misma(a, b):
    return os.path.normcase(os.path.abspath(a)) == os.path.normcase(os.path.abspath(b))


def destino(original, cap, config, carpeta=None):
    """Ruta de la copia preparada: la plantilla del libro o, si no hay, junto al original."""
    base = os.path.splitext(os.path.basename(original))[0] + " (HTML).indd"
    plantilla = (config.get("preparar") or {}).get("destino")
    ruta = plantilla.format(carpeta=(config.get("libro") or {}).get("carpeta", ""), n=cap) if plantilla else None
    if carpeta:  # otra carpeta (pruebas): mismo nombre que tendría en el libro
        return os.path.join(os.path.abspath(carpeta), os.path.basename(ruta) if ruta else base)
    if not ruta:
        return os.path.join(os.path.dirname(original), base)
    # Si la carpeta del capítulo ya tiene su .indd con otro nombre («02 Ponencia 2026 (APP)»), ese
    carpeta_cap = os.path.dirname(ruta)
    if not os.path.exists(ruta) and os.path.isdir(carpeta_cap):
        indds = [f for f in os.listdir(carpeta_cap) if f.endswith(".indd") and "(anterior)" not in f]
        if len(indds) == 1:
            return os.path.join(carpeta_cap, indds[0])
    return ruta


def preparar(original, copia, cap, cfg, forzar):
    """Copia y ejecuta el jsx; devuelve las líneas de su respuesta ("ok"/"error|…", "OK|…", "AVISO|…")."""
    if _misma(copia, original):
        return ["error|Este .indd ya es la versión preparada para HTML; elige el original de imprenta"]
    if copia in documentos_abiertos():
        return ["error|La versión preparada está abierta en InDesign; ciérrala y vuelve a intentarlo:\n" + copia]
    if os.path.exists(copia):
        if not forzar:
            return [f"error|Ya existe la versión preparada (para rehacerla: --forzar):\n{copia}"]
        anterior = os.path.splitext(copia)[0] + " (anterior).indd"
        os.replace(copia, anterior)
    os.makedirs(os.path.dirname(copia), exist_ok=True)
    shutil.copy2(original, copia)

    ruta_cfg = os.path.join(RAIZ, "salida", "preparar.config.json")
    os.makedirs(os.path.dirname(ruta_cfg), exist_ok=True)
    with open(ruta_cfg, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False)
    return _osascript(
        f'with timeout of 900 seconds\n tell application "{INDESIGN}" to do script '
        f'(POSIX file "{JSX}") language javascript with arguments '
        f'{{"{copia}", "{ruta_cfg}", "{cap}"}}\nend timeout'
    ).splitlines() or ["error|InDesign no ha devuelto nada"]


def documentos_abiertos():
    res = _osascript(
        f'tell application "{INDESIGN}" to do script "var r=[];for(var i=0;i<app.documents.length;i++)'
        f'try{{r.push(app.documents[i].fullName.fsName)}}catch(e){{}};r.join(\'\\\\n\')" language javascript'
    )
    return set(res.splitlines()) if not res.startswith("error|") else set()


def _osascript(script):
    r = subprocess.run(["osascript", "-e", script], capture_output=True, text=True)
    return r.stdout.strip() if r.returncode == 0 else "error|" + r.stderr.strip()


def _informe(copia, lineas):
    estado = "Preparado" if lineas[0] == "ok" else "ERROR: " + lineas[0].partition("|")[2]
    oks = [l[3:] for l in lineas[1:] if l.startswith("OK|")]
    avisos = [l[6:] for l in lineas[1:] if l.startswith("AVISO|")]
    partes = [f"{estado}: {copia}"]
    partes += ["  · " + l for l in oks]
    if avisos:
        partes.append(f"Avisos ({len(avisos)}):")
        partes += ["  ! " + l for l in avisos]
    return "\n".join(partes)


if __name__ == "__main__":
    sys.exit(main())
