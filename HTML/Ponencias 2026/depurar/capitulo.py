"""Procesa un capítulo del libro en su carpeta del servidor.

Uso: ./capitulo 33            (número de capítulo; con varios libros, --libro <libro>)
     ./capitulo ruta/al/33 Ponencias 2026 (APP).indd   (o el .html, o la carpeta)
El libro (config/libros/<libro>.yaml) se reconoce por la ruta.

1. Localiza el HTML exportado desde InDesign y el .txt de URL del capítulo.
2. Si el portapapeles tiene las URL copiadas con el marcador «Enlaces Hélice»,
   las añade a las que ya tenga el .txt (si las imágenes ocupan varias páginas
   en el panel de Hélice, se pulsa el marcador en cada página y se repite).
3. Genera "<html> - Helice.html" en la carpeta del capítulo (vista previa e
   informe en salida/ del proyecto). Si no hay avisos, copia el HTML al
   portapapeles; con avisos, solo si se pide con --copiar.

--resumen escribe una salida breve para la app «InDesign a HTML» (no abre la
vista previa; copia igual que en modo normal):
  línea 1: OK | AVISOS | FALTAN_URLS | FALTAN_IMAGENES | ERROR
  línea 2: HTML final    línea 3: vista previa    resto: avisos e información
"""

import argparse
import glob
import os
import re
import subprocess
import sys

from . import css_libro
from .__main__ import RAIZ, configuracion, procesar
from .informe import Informe

URL_IMAGEN = re.compile(r"https?://[^\s\"'<>)]+/uploads/[^\s\"'<>)]+\.(?:jpe?g|png|gif|webp)", re.I)


class Parada(Exception):
    def __init__(self, estado, mensaje):
        super().__init__(mensaje)
        self.estado = estado


def main(argv=None):
    ap = argparse.ArgumentParser(prog="capitulo", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("capitulo", help="número del capítulo, o ruta al .indd, al .html o a su carpeta")
    ap.add_argument("--libro", help="libro de config/libros (por defecto, según la ruta)")
    ap.add_argument("--config", help="archivo de configuración (en vez de --libro)")
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

    copiado = estado in ("OK", "AVISOS", "FALTAN_IMAGENES") and (estado == "OK" or args.copiar)
    if copiado:
        copiar(destino)
    if args.resumen:
        print(f"{estado}\n{destino}\n{vista}\n{breve}")
        return 0
    print(mensaje)
    if estado in ("OK", "AVISOS", "FALTAN_IMAGENES"):
        if copiado:
            print("\nCopiado al portapapeles: pégalo en Hélice con ⌘V.")
        elif estado == "FALTAN_IMAGENES":
            print("\n" + breve.split("\n\n")[0])
            print("No se ha copiado al portapapeles; para copiarlo igualmente: --copiar")
        else:
            print("\nNo se ha copiado al portapapeles por los avisos. Revísalos; para copiarlo igualmente: --copiar")
        if os.path.exists(vista) and not args.no_abrir:
            subprocess.run(["open", vista])
        return 0
    return 1


def _ejecutar(args):
    try:
        config, dir_config = configuracion(args.libro, args.config, None if args.capitulo.isdigit() else args.capitulo)
    except ValueError as e:
        raise Parada("ERROR", str(e))
    libro = config.get("libro", {})
    sufijo = libro.get("sufijo_salida", " - Helice")

    carpeta = _carpeta(args.capitulo, libro)
    html = _html_exportado(carpeta, sufijo)
    numero = _numero(carpeta)
    lineas = [f"Capítulo {numero:02d}: {os.path.basename(html)}" if numero is not None else os.path.basename(html)]
    lineas.append(_preparar_urls(carpeta, numero, libro))

    salida = os.path.join(RAIZ, "salida")
    # Libro nuevo: su CSS de Hélice se completa con los estilos de este capítulo (antes de
    # depurar, para que la vista previa y los pesos ya la usen)
    aviso_css = Informe()
    css_libro.actualizar(config, html, aviso_css)
    destino, informe = procesar(html, config, dir_config, carpeta, sufijo, salida)
    informe.avisos[:0] = aviso_css.avisos
    vista = os.path.join(salida, os.path.basename(destino)[: -len(".html")] + ".vista.html")
    lineas += [informe.texto(), f"\nHTML final: {destino}"]
    breve = []
    if informe.sin_url:
        breve += [
            f"Faltan por enlazar {len(informe.sin_url)} imágenes: {', '.join(informe.sin_url)}.",
            "Si en Hélice las imágenes del capítulo ocupan varias páginas, pasa a la siguiente página, "
            "pulsa el marcador «Enlaces Hélice» y vuelve a intentarlo: los enlaces se suman a los anteriores.",
            "",
        ]
    if informe.avisos:
        breve += [f"⚠️ AVISOS ({len(informe.avisos)}):"] + [f"⚠️ {a}" for a in informe.avisos]
    if informe.informacion:
        breve += ["Información:"] + [f"• {i}" for i in informe.informacion]
    estado = "FALTAN_IMAGENES" if informe.sin_url else "AVISOS" if informe.avisos else "OK"
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
    # Las de fuentes (CSS de un libro nuevo) pueden venir mezcladas: se ignoran aquí
    if not lineas or not all(URL_IMAGEN.fullmatch(l) or css_libro.URL_FUENTE.fullmatch(l) for l in lineas):
        return []
    return list(dict.fromkeys(l for l in lineas if URL_IMAGEN.fullmatch(l)))


def _preparar_urls(carpeta, numero, libro):
    """Guarda en el .txt las URL del portapapeles, o comprueba que el .txt ya las tiene."""
    txts = glob.glob(os.path.join(carpeta, "*.txt"))
    nombre = libro.get("nombre_txt", "{n:02d}Ponencias2026.txt").format(n=numero or 0)
    txt = txts[0] if txts else os.path.join(carpeta, nombre)

    actuales = URL_IMAGEN.findall(open(txt, encoding="utf-8").read()) if os.path.exists(txt) else []
    pegadas = urls_del_marcador(pegar())
    if pegadas:
        # Las del portapapeles primero: si una imagen se subió dos veces, gana la última copia.
        todas = list(dict.fromkeys(pegadas + actuales))
        with open(txt, "w", encoding="utf-8") as f:
            f.write("\n".join(todas) + "\n")
        nuevas = len(todas) - len(actuales)
        return f"URL de imágenes: {nuevas} nuevas del portapapeles, {len(todas)} en total en {os.path.basename(txt)}"

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
