"""Sube las imágenes de un capítulo a Ficheros de Hélice sin pasar por el marcador.

La app no puede iniciar sesión en el panel (el acceso es por código al correo), así que
usa la pestaña del panel ya abierta en Safari o Chrome: le pasa las imágenes en base64 y
ejecuta allí herramientas/subir_helice.js (lo mismo que el marcador «Subir a Hélice»).
Los enlaces se guardan en el .txt del capítulo, como los del marcador «Enlaces Hélice».

Hace falta, una vez, permitir que el navegador ejecute JavaScript de otras apps:
- Safari: Ajustes › Avanzado › «Mostrar funciones para desarrolladores web», y en el
  menú Desarrollo › «Permitir JavaScript desde eventos de Apple».
- Chrome: Ver › Desarrollador › «Permitir JavaScript desde eventos de Apple».

Uso: ./subir "ruta/al/06 … .html"     (salida para la app: OK | ERROR y el detalle)
     ./subir --fuentes --libro ponencias2025   las fuentes propias del libro, a la carpeta
         ficheros.fuentes de Hélice; sus enlaces se guardan y la CSS del libro se rehace
"""

import base64
import glob
import json
import os
import subprocess
import sys
import tempfile
import time

from . import libros
from .__main__ import RAIZ
from .capitulo import URL_IMAGEN

JS = os.path.join(RAIZ, "herramientas", "subir_helice.js")
TROZO = 400_000  # caracteres de base64 por llamada al navegador

SCRIPT_BUSCAR = '''
if application "Safari" is running then
	tell application "Safari"
		repeat with w in windows
			repeat with t in tabs of w
				if URL of t contains "helice.app/panel/" then return "safari|" & (id of w) & "|" & (index of t)
			end repeat
		end repeat
	end tell
end if
if application "Google Chrome" is running then
	tell application "Google Chrome"
		repeat with w in windows
			repeat with t in tabs of w
				if URL of t contains "helice.app/panel/" then return "chrome|" & (id of w) & "|" & (id of t)
			end repeat
		end repeat
	end tell
end if
return ""
'''

SCRIPT_EJECUTAR = '''
on run argv
	set navegador to item 1 of argv
	set w to (item 2 of argv) as integer
	set t to (item 3 of argv) as integer
	set js to read (POSIX file (item 4 of argv)) as «class utf8»
	if navegador is "safari" then
		tell application "Safari" to set r to do JavaScript js in tab t of window id w
	else
		tell application "Google Chrome" to set r to execute (tab id t of window id w) javascript js
	end if
	if r is missing value then return ""
	return r as text
end run
'''


class ErrorSubida(Exception):
    pass


def _osascript(script, *args):
    r = subprocess.run(["osascript", "-e", script, *args], capture_output=True, text=True)
    if r.returncode:
        mensaje = r.stderr.strip()
        if "JavaScript" in mensaje or "Apple Events" in mensaje or "eventos de Apple" in mensaje:
            raise ErrorSubida("El navegador no permite que la app ejecute JavaScript. Actívalo una vez:\n"
                              "· Safari: menú Desarrollo › «Permitir JavaScript desde eventos de Apple»\n"
                              "· Chrome: Ver › Desarrollador › «Permitir JavaScript desde eventos de Apple»")
        if "-1712" in mensaje or "-1743" in mensaje:  # tiempo agotado o sin permiso
            raise ErrorSubida("macOS no ha dejado que la app controle el navegador. Acepta el aviso de permiso "
                              "(o actívalo en Ajustes del Sistema › Privacidad y seguridad › Automatización) "
                              "y vuelve a intentarlo")
        raise ErrorSubida(mensaje)
    return r.stdout.strip()


class Pestana:
    def __init__(self):
        r = _osascript(SCRIPT_BUSCAR)
        if not r:
            raise ErrorSubida("No hay ninguna pestaña del panel de Hélice abierta en Safari ni en Chrome: "
                              "ábrela (con la sesión iniciada) y vuelve a intentarlo")
        self.navegador, self.ventana, self.pestana = r.split("|")

    def ejecutar(self, js):
        with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as f:
            f.write(js)
        try:
            return _osascript(SCRIPT_EJECUTAR, self.navegador, self.ventana, self.pestana, f.name)
        finally:
            os.unlink(f.name)


def subir(ruta_html, espera=900, avisar=lambda t: None):
    """Sube lo que pide helice_subida.json; devuelve las URL (también las guarda en el .txt)."""
    carpeta = os.path.dirname(os.path.abspath(ruta_html))
    manifiesto = os.path.join(carpeta, "helice_subida.json")
    if not os.path.exists(manifiesto):
        raise ErrorSubida(f"No hay helice_subida.json en {carpeta}")
    datos = json.load(open(manifiesto, encoding="utf-8"))
    urls = subir_archivos(datos["ruta"], datos["archivos"], carpeta, espera, avisar)
    guardar_urls(carpeta, urls)
    return urls


def subir_archivos(ruta, archivos, carpeta="", espera=900, avisar=lambda t: None):
    """Sube los archivos (relativos a carpeta, o absolutos) a la ruta de Ficheros; devuelve sus URL."""
    pestana = Pestana()
    avisar(f"Pestaña del panel en {pestana.navegador}")

    pestana.ejecutar("window.__subidaArchivos = {}; 'ok'")
    for rel in archivos:
        b64 = base64.b64encode(open(os.path.join(carpeta, rel), "rb").read()).decode()
        clave = json.dumps(rel)
        for i in range(0, len(b64), TROZO):
            pestana.ejecutar(f"window.__subidaArchivos[{clave}] = (window.__subidaArchivos[{clave}] || '') + "
                             f"{json.dumps(b64[i:i + TROZO])}; 'ok'")
    codigo = open(JS, encoding="utf-8").read()
    pestana.ejecutar(f"{codigo}\nsubirHelice({json.dumps({'ruta': ruta, 'archivos': archivos})}); 'iniciado'")

    limite = time.time() + espera
    while time.time() < limite:
        time.sleep(2)
        r = pestana.ejecutar("JSON.stringify(window.__subidaHelice || null)")
        estado = json.loads(r) if r else None
        if estado and estado["estado"] == "ok":
            return estado["urls"]
        if estado and estado["estado"] == "error":
            raise ErrorSubida("Hélice: " + estado["error"])
    raise ErrorSubida("La subida no ha terminado en el tiempo previsto; mira el recuadro en la pestaña del panel")


def guardar_urls(carpeta, urls):
    """Añade las URL al .txt del capítulo (el que lee ./capitulo)."""
    txts = glob.glob(os.path.join(carpeta, "*.txt"))
    if txts:
        txt = txts[0]
    else:
        n = int(os.path.basename(carpeta)[:2]) if os.path.basename(carpeta)[:2].isdigit() else 0
        libro = libros.elegir(ruta=carpeta)
        txt = os.path.join(carpeta, (libro.config.get("libro") or {}).get("nombre_txt", "{n:02d}.txt").format(n=n))
    previas = URL_IMAGEN.findall(open(txt, encoding="utf-8").read()) if os.path.exists(txt) else []
    with open(txt, "w", encoding="utf-8") as f:
        f.write("\n".join(dict.fromkeys(urls + previas)) + "\n")


def subir_fuentes(libro_id, avisar=print):
    """Sube las fuentes propias del libro a Hélice, guarda sus enlaces y rehace la CSS del libro."""
    from . import css_libro
    from .informe import Informe
    from .libro import carpeta_fuentes

    libro = libros.elegir(libro_id)
    fuentes = ((libro.config.get("css_libro") or {}).get("fuentes_web") or {}).get("archivos") or []
    if not fuentes:
        raise ErrorSubida(f"El libro «{libro.nombre}» no tiene fuentes propias (css_libro.fuentes_web.archivos)")
    ruta = carpeta_fuentes(libro.config)
    if not ruta:
        raise ErrorSubida("Falta la carpeta de Ficheros del libro (ficheros.capitulo o ficheros.fuentes)")
    originales = [f[3] for f in fuentes]
    faltan = [o for o in originales if not os.path.exists(o)]
    if faltan:
        raise ErrorSubida("No encuentro estas fuentes en el Mac: " + ", ".join(faltan))
    urls = subir_archivos(ruta, originales, avisar=avisar)
    archivo, _, txt_urls = css_libro.rutas(libro.config)
    previas = open(txt_urls, encoding="utf-8").read().split() if os.path.exists(txt_urls) else []
    os.makedirs(os.path.dirname(txt_urls), exist_ok=True)
    with open(txt_urls, "w", encoding="utf-8") as f:
        f.write("\n".join(dict.fromkeys(urls + previas)) + "\n")
    informe = Informe()
    css_libro.actualizar(libro.config, os.path.join(os.path.dirname(archivo), "-"), informe)
    return urls, informe.avisos


def main(argv=None):
    args = (argv if argv is not None else sys.argv[1:])
    if args[:1] == ["--fuentes"]:
        try:
            if len(args) != 3 or args[1] != "--libro":
                raise ErrorSubida("Uso: ./subir --fuentes --libro <libro>")
            urls, avisos = subir_fuentes(args[2])
            print(f"OK\n{len(urls)} fuentes en Hélice " + " / ".join(carpeta_de(args[2])) + "; CSS del libro rehecha")
            for a in avisos:
                print("⚠️ " + a)
        except (ErrorSubida, ValueError, OSError) as e:
            print(f"ERROR\n{e}")
        return 0
    if len(args) != 1:
        print(__doc__)
        return 1
    try:
        urls = subir(args[0])
        print(f"OK\n{len(urls)} imágenes en Hélice; enlaces guardados en el .txt del capítulo")
    except (ErrorSubida, ValueError, OSError) as e:
        print(f"ERROR\n{e}")
    return 0


def carpeta_de(libro_id):
    from .libro import carpeta_fuentes

    return carpeta_fuentes(libros.elegir(libro_id).config)


if __name__ == "__main__":
    sys.exit(main())
