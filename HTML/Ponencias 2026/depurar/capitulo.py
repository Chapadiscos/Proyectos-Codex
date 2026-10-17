"""Procesa un capítulo del libro directamente en su carpeta del servidor.

Uso: ./capitulo 33

1. Busca la carpeta "33 …" del libro, el HTML exportado desde InDesign y su .txt.
2. Si el .txt no tiene URL, las toma del portapapeles (marcador «Enlaces Hélice»)
   y las guarda en él.
3. Genera "<html> - Helice.html" en la misma carpeta (la vista previa y el
   informe, en salida/ del proyecto), copia el HTML al portapapeles y abre la vista previa.
"""

import argparse
import glob
import os
import re
import subprocess
import sys

import yaml

from .__main__ import RAIZ, procesar

URL_IMAGEN = re.compile(r"https?://[^\s\"'<>)]+/uploads/[^\s\"'<>)]+\.(?:jpe?g|png|gif|webp)", re.I)


def main(argv=None):
    ap = argparse.ArgumentParser(prog="capitulo", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("numero", type=int, help="número del capítulo")
    ap.add_argument("--config", default=os.path.join(RAIZ, "config", "config.yaml"))
    ap.add_argument("--no-abrir", action="store_true", help="no abrir la vista previa")
    args = ap.parse_args(argv)

    with open(args.config, encoding="utf-8") as f:
        config = yaml.safe_load(f) or {}
    libro = config.get("libro", {})
    sufijo = libro.get("sufijo_salida", " - Helice")

    carpeta = _carpeta_capitulo(libro["carpeta"], args.numero)
    html = _html_exportado(carpeta, sufijo)
    print(f"Capítulo {args.numero}: {os.path.basename(html)}")

    if not _preparar_urls(carpeta, args.numero, libro):
        return 1

    salida = os.path.join(RAIZ, "salida")
    destino, informe = procesar(html, config, os.path.dirname(os.path.abspath(args.config)), carpeta, sufijo, salida)
    with open(destino, encoding="utf-8") as f:
        subprocess.run(["pbcopy"], input=f.read(), text=True, check=True)
    print(informe.texto())
    print(f"\nHTML final: {destino}")
    print("Copiado al portapapeles: pégalo en Hélice con ⌘V.")
    vista = os.path.join(salida, os.path.basename(destino)[: -len(".html")] + ".vista.html")
    if os.path.exists(vista) and not args.no_abrir:
        subprocess.run(["open", vista])
    return 0


def _carpeta_capitulo(raiz, numero):
    candidatas = [d for d in glob.glob(os.path.join(raiz, f"{numero:02d} *")) if os.path.isdir(d)]
    if len(candidatas) != 1:
        sys.exit(f"No encuentro una única carpeta del capítulo {numero:02d} en {raiz} ({len(candidatas)} encontradas)")
    return candidatas[0]


def _html_exportado(carpeta, sufijo):
    """El HTML de InDesign: tiene su carpeta -web-resources y no es una salida nuestra ni un _nuevo."""
    propios = (f"{sufijo}.html", f"{sufijo}.vista.html", "_nuevo.html")
    htmls = [h for h in glob.glob(os.path.join(carpeta, "*.html")) if not h.endswith(propios)]
    if not htmls:
        sys.exit(f"No hay HTML exportado en {carpeta}. Exporta desde InDesign: Archivo > Exportar > HTML (heredado).")
    if len(htmls) > 1:
        sys.exit("Hay varios HTML exportados; deja solo uno:\n  " + "\n  ".join(map(os.path.basename, htmls)))
    if not glob.glob(os.path.join(carpeta, "*-web-resources")):
        sys.exit(f"Falta la carpeta -web-resources junto a {os.path.basename(htmls[0])}")
    return htmls[0]


def _preparar_urls(carpeta, numero, libro):
    """Asegura que el .txt del capítulo tiene las URL; si no, las toma del portapapeles."""
    txts = glob.glob(os.path.join(carpeta, "*.txt"))
    txt = txts[0] if txts else os.path.join(carpeta, libro.get("nombre_txt", "{n:02d}Ponencias2026.txt").format(n=numero))
    actuales = URL_IMAGEN.findall(open(txt, encoding="utf-8").read()) if os.path.exists(txt) else []
    if actuales:
        print(f"URL de imágenes: {len(actuales)} en {os.path.basename(txt)}")
        return True

    pegadas = list(dict.fromkeys(URL_IMAGEN.findall(subprocess.run(["pbpaste"], capture_output=True, text=True).stdout)))
    if not pegadas:
        imagenes = glob.glob(os.path.join(carpeta, "*-web-resources", "image", "*"))
        print(
            "\nFaltan las URL de las imágenes en Hélice.\n"
            f"1. Sube a la carpeta del capítulo en Hélice estas {len(imagenes)} imágenes de "
            f"{os.path.dirname(imagenes[0]) if imagenes else '-web-resources/image'}:\n   "
            + ", ".join(sorted(os.path.basename(i) for i in imagenes))
            + "\n2. Abre esa carpeta en Hélice y pulsa el marcador «Enlaces Hélice»."
            f"\n3. Vuelve a ejecutar: ./capitulo {numero}"
        )
        return False
    with open(txt, "w", encoding="utf-8") as f:
        f.write("\n".join(pegadas) + "\n")
    print(f"URL de imágenes: {len(pegadas)} tomadas del portapapeles y guardadas en {os.path.basename(txt)}")
    return True


if __name__ == "__main__":
    sys.exit(main())
