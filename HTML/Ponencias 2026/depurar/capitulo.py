"""Procesa un capítulo del libro en su carpeta del servidor.

Uso: ./capitulo 33            (número de capítulo)
     ./capitulo ruta/al/33 Ponencias 2026 (APP).indd   (o el .html, o la carpeta)

1. Localiza el HTML exportado desde InDesign y el .txt de URL del capítulo.
2. Si el portapapeles tiene las URL copiadas con el marcador «Enlaces Hélice»,
   las guarda en el .txt; si no, usa las que ya tenga el .txt.
3. Genera "<html> - Helice.html" en la carpeta del capítulo (vista previa e
   informe en salida/ del proyecto). Si no hay avisos, copia el HTML al
   portapapeles; con avisos, solo si se pide con --copiar.

--resumen escribe una salida breve para la app «InDesign a HTML» (no abre la
vista previa; copia igual que en modo normal):
  línea 1: OK | AVISOS | FALTAN_URLS | ERROR
  línea 2: HTML final    línea 3: vista previa    resto: avisos e información
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


class Parada(Exception):
    def __init__(self, estado, mensaje):
        super().__init__(mensaje)
        self.estado = estado


def main(argv=None):
    ap = argparse.ArgumentParser(prog="capitulo", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("capitulo", help="número del capítulo, o ruta al .indd, al .html o a su carpeta")
    ap.add_argument("--config", default=os.path.join(RAIZ, "config", "config.yaml"))
    ap.add_argument("--no-abrir", action="store_true", help="no abrir la vista previa")
    ap.add_argument("--copiar", action="store_true", help="copiar el HTML al portapapeles aunque haya avisos")
    ap.add_argument("--resumen", action="store_true", help="salida para la app (no copia ni abre nada)")
    args = ap.parse_args(argv)

    try:
        estado, destino, vista, mensaje, breve = _ejecutar(args)
    except Parada as p:
        estado, destino, vista, mensaje, breve = p.estado, "", "", str(p), str(p)
    except Exception as e:  # la app tiene que poder mostrar cualquier fallo
        if not args.resumen:
            raise
        estado, destino, vista, mensaje, breve = "ERROR", "", "", "", f"{type(e).__name__}: {e}"

    copiado = estado in ("OK", "AVISOS") and (estado == "OK" or args.copiar)
    if copiado:
        copiar(destino)
    if args.resumen:
        print(f"{estado}\n{destino}\n{vista}\n{breve}")
        return 0
    print(mensaje)
    if estado in ("OK", "AVISOS"):
        if copiado:
            print("\nCopiado al portapapeles: pégalo en Hélice con ⌘V.")
        else:
            print("\nNo se ha copiado al portapapeles por los avisos. Revísalos; para copiarlo igualmente: --copiar")
        if os.path.exists(vista) and not args.no_abrir:
            subprocess.run(["open", vista])
        return 0
    return 1


def _ejecutar(args):
    with open(args.config, encoding="utf-8") as f:
        config = yaml.safe_load(f) or {}
    libro = config.get("libro", {})
    sufijo = libro.get("sufijo_salida", " - Helice")

    carpeta = _carpeta(args.capitulo, libro)
    html = _html_exportado(carpeta, sufijo)
    numero = _numero(carpeta)
    lineas = [f"Capítulo {numero:02d}: {os.path.basename(html)}" if numero is not None else os.path.basename(html)]
    lineas.append(_preparar_urls(carpeta, numero, libro))

    salida = os.path.join(RAIZ, "salida")
    destino, informe = procesar(html, config, os.path.dirname(os.path.abspath(args.config)), carpeta, sufijo, salida)
    vista = os.path.join(salida, os.path.basename(destino)[: -len(".html")] + ".vista.html")
    lineas += [informe.texto(), f"\nHTML final: {destino}"]
    breve = []
    if informe.avisos:
        breve += ["Avisos:"] + [f"• {a}" for a in informe.avisos]
    if informe.informacion:
        breve += ["Información:"] + [f"• {i}" for i in informe.informacion]
    estado = "AVISOS" if informe.avisos else "OK"
    return estado, destino, vista, "\n".join(lineas), "\n".join(breve)


# pbcopy/pbpaste usan LANG para la codificación; lanzados desde una app no la tienen.
ENTORNO_UTF8 = {**os.environ, "LANG": "es_ES.UTF-8", "LC_ALL": "es_ES.UTF-8"}


def copiar(ruta):
    with open(ruta, encoding="utf-8") as f:
        subprocess.run(["pbcopy"], input=f.read().encode("utf-8"), env=ENTORNO_UTF8, check=True)


def pegar():
    return subprocess.run(["pbpaste"], capture_output=True, env=ENTORNO_UTF8).stdout.decode("utf-8", "replace")


def _carpeta(capitulo, libro):
    if capitulo.isdigit():
        raiz = libro["carpeta"]
        candidatas = [d for d in glob.glob(os.path.join(raiz, f"{int(capitulo):02d} *")) if os.path.isdir(d)]
        if len(candidatas) != 1:
            raise Parada("ERROR", f"No encuentro una única carpeta del capítulo {capitulo} en {raiz} ({len(candidatas)} encontradas)")
        return candidatas[0]
    ruta = os.path.abspath(capitulo)
    if not os.path.exists(ruta):
        raise Parada("ERROR", f"No existe {ruta}")
    return ruta if os.path.isdir(ruta) else os.path.dirname(ruta)


def _numero(carpeta):
    m = re.match(r"(\d+)", os.path.basename(carpeta))
    return int(m.group(1)) if m else None


def _html_exportado(carpeta, sufijo):
    """El HTML de InDesign: tiene su carpeta -web-resources y no es una salida nuestra ni un _nuevo."""
    propios = (f"{sufijo}.html", f"{sufijo}.vista.html", "_nuevo.html")
    htmls = [h for h in glob.glob(os.path.join(carpeta, "*.html")) if not h.endswith(propios)]
    if not htmls:
        raise Parada("ERROR", f"No hay HTML exportado en {carpeta}. Exporta desde InDesign: Archivo > Exportar > HTML (heredado).")
    if len(htmls) > 1:
        raise Parada("ERROR", "Hay varios HTML exportados; deja solo uno:\n  " + "\n  ".join(map(os.path.basename, htmls)))
    if not glob.glob(os.path.join(carpeta, "*-web-resources")):
        raise Parada("ERROR", f"Falta la carpeta -web-resources junto a {os.path.basename(htmls[0])}")
    return htmls[0]


def urls_del_marcador(texto):
    """URL copiadas con el marcador: el texto es solo una lista de URL (no un HTML que las contenga)."""
    lineas = [l.strip() for l in texto.splitlines() if l.strip()]
    if not lineas or not all(URL_IMAGEN.fullmatch(l) for l in lineas):
        return []
    return list(dict.fromkeys(lineas))


def _preparar_urls(carpeta, numero, libro):
    """Guarda en el .txt las URL del portapapeles, o comprueba que el .txt ya las tiene."""
    txts = glob.glob(os.path.join(carpeta, "*.txt"))
    nombre = libro.get("nombre_txt", "{n:02d}Ponencias2026.txt").format(n=numero or 0)
    txt = txts[0] if txts else os.path.join(carpeta, nombre)

    pegadas = urls_del_marcador(pegar())
    if pegadas:
        with open(txt, "w", encoding="utf-8") as f:
            f.write("\n".join(pegadas) + "\n")
        return f"URL de imágenes: {len(pegadas)} tomadas del portapapeles y guardadas en {os.path.basename(txt)}"

    actuales = URL_IMAGEN.findall(open(txt, encoding="utf-8").read()) if os.path.exists(txt) else []
    if actuales:
        return f"URL de imágenes: {len(actuales)} en {os.path.basename(txt)}"

    imagenes = sorted(os.path.basename(i) for i in glob.glob(os.path.join(carpeta, "*-web-resources", "image", "*")))
    raise Parada(
        "FALTAN_URLS",
        "Faltan las URL de las imágenes en Hélice.\n"
        f"1. Sube a la carpeta del capítulo en Hélice estas {len(imagenes)} imágenes (carpeta -web-resources/image):\n   "
        + ", ".join(imagenes)
        + "\n2. Abre esa carpeta en Hélice y pulsa el marcador «Enlaces Hélice».\n3. Vuelve a intentarlo.",
    )


if __name__ == "__main__":
    sys.exit(main())
