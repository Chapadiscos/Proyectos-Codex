"""Publicación en Hélice con su API (panel.helice.app/api/ws, token en el llavero de macOS).

La API no deja crear secciones de tipo Menú, ni borrar ni editar lo creado, y una
sección de Información no puede contener otras (el panel no las muestra). Por eso:
- los bloques y los temas (Menú) se crean a mano en el panel y sus identificadores van
  en la configuración del libro (publicar.bloques[].seccion y .temas[].seccion);
- ./publicar --estructura crearía los temas como Información (solo para libros sin
  capítulos como sección propia; no se usa en Ponencias);
- ./publicar 06 crea dentro del tema la sección de Información «Capítulo 06», le añade
  un elemento con el HTML depurado y comprueba que ha quedado igual (getContent). Un
  capítulo ya publicado no se vuelve a publicar: las correcciones, en el panel.
Los iconos se asignan en el panel.

Subida de archivos (la API no puede): el marcador «Subir a Hélice» (herramientas/
subir_helice.js) lo hace desde el panel con la sesión iniciada. ./publicar --manifiesto
ruta.html deja en la carpeta del capítulo «helice_subida.json» con su carpeta en Ficheros
(ficheros.capitulo) y las imágenes exportadas que hay que subir.

--plan ruta.html   para la app: SI | YA | NO, y el tema o el motivo
"""

import argparse
import glob
import json
import os
import re
import subprocess
import sys

from . import libros

API = "https://panel.helice.app/api/ws/"
LLAVERO = ("helice-api", "publicacionesseo")  # servicio y cuenta en el llavero


class ErrorHelice(Exception):
    pass


def token():
    r = subprocess.run(["security", "find-generic-password", "-s", LLAVERO[0], "-a", LLAVERO[1], "-w"],
                       capture_output=True, text=True)
    if r.returncode:
        raise ErrorHelice("No está el token de Hélice en el llavero (servicio «helice-api»)")
    return r.stdout.strip()


def llamar(funcion, metodo="POST", **datos):
    import requests

    cabeceras = {"token": token()}
    if metodo == "GET":
        r = requests.get(API + funcion, params=datos, headers=cabeceras, timeout=60)
    else:  # en el cuerpo: el HTML de un capítulo no cabe en la URL
        r = requests.post(API + funcion, data=datos, headers=cabeceras, timeout=120)
    try:
        respuesta = r.json()
    except ValueError:
        raise ErrorHelice(f"{funcion}: respuesta no válida ({r.status_code})")
    if respuesta.get("status") != 200:
        detalle = respuesta.get("msgs")  # el motivo concreto («El campo nombre es obligatorio»)
        raise ErrorHelice(f"{funcion}: {respuesta.get('error') or respuesta}" + (f" ({detalle})" if detalle else ""))
    return respuesta


class Publicacion:
    def __init__(self, libro):
        self.libro = libro
        self.cfg = libro.config.get("publicar") or {}
        carpeta = (libro.config.get("libro") or {}).get("carpeta", "")
        self.ruta_estado = self.cfg.get("estado", "{carpeta}/helice_publicacion.json").format(carpeta=carpeta)
        self.estado = json.load(open(self.ruta_estado, encoding="utf-8")) if os.path.exists(self.ruta_estado) else {}
        self.estado.setdefault("temas", {})
        self.estado.setdefault("capitulos", {})
        self.estado.setdefault("secciones_capitulo", {})  # creadas aunque falle luego el elemento

    def guardar(self):
        os.makedirs(os.path.dirname(self.ruta_estado), exist_ok=True)
        with open(self.ruta_estado, "w", encoding="utf-8") as f:
            json.dump(self.estado, f, ensure_ascii=False, indent=1)

    def tema_de(self, n):
        """(bloque, tema) del capítulo n según la configuración."""
        for bloque in self.cfg.get("bloques") or []:
            for tema in bloque.get("temas") or []:
                if n in tema.get("capitulos", []):
                    return bloque, tema
        return None, None

    def seccion_tema(self, bloque, tema):
        """El Menú del tema creado a mano (configuración) o, si no, el creado por la API."""
        return tema.get("seccion") or self.estado["temas"].get(f"{bloque['nombre']}/{tema['nombre']}")

    def crear_estructura(self, avisar=print):
        for bloque in self.cfg.get("bloques") or []:
            if not bloque.get("seccion"):
                avisar(f"{bloque['nombre']}: falta su sección (Menú creado en el panel) en publicar.bloques")
                continue
            for tema in bloque.get("temas") or []:
                clave = f"{bloque['nombre']}/{tema['nombre']}"
                if clave in self.estado["temas"]:
                    avisar(f"{clave}: ya existe ({self.estado['temas'][clave]})")
                    continue
                r = llamar("createSection", type="info", father=str(bloque["seccion"]), name=tema["nombre"])
                self.estado["temas"][clave] = r["sectionid"]
                self.guardar()
                avisar(f"{clave}: creada la sección {r['sectionid']}")

    def plan(self, n):
        clave = f"{n:02d}"
        if clave in self.estado["capitulos"]:
            return "YA", f"publicado el {self.estado['capitulos'][clave]['fecha']}"
        bloque, tema = self.tema_de(n)
        if not tema:
            return "NO", f"el capítulo {n} no está en ningún tema de publicar.bloques"
        if not self.seccion_tema(bloque, tema):
            return "NO", f"falta la sección de «{bloque['nombre']} / {tema['nombre']}» (publicar.bloques[].temas[].seccion)"
        return "SI", f"{bloque['nombre']} / {tema['nombre']}"

    def publicar(self, n, ruta_html):
        estado, detalle = self.plan(n)
        if estado != "SI":
            raise ErrorHelice(f"Capítulo {n:02d}: {detalle}")
        bloque, tema = self.tema_de(n)
        seccion_tema = self.seccion_tema(bloque, tema)
        titulo = self.cfg.get("titulo", "Capítulo {n:02d}").format(n=n)
        html = open(ruta_html, encoding="utf-8").read()
        clave = f"{n:02d}"
        # Sección de Información propia del capítulo, dentro del tema (se apunta enseguida:
        # si falla el elemento, al repetir se usa la misma y no se crea otra)
        seccion = self.estado["secciones_capitulo"].get(clave)
        if not seccion:
            seccion = llamar("createSection", type="info", father=str(seccion_tema), name=titulo)["sectionid"]
            self.estado["secciones_capitulo"][clave] = seccion
            self.guardar()
        if elementos(seccion):
            raise ErrorHelice(f"{titulo}: su sección ({seccion}) ya tiene contenido; revísala en el panel")
        # «name» es obligatorio aunque la especificación OpenAPI no lo incluya
        llamar("addListElement", section=str(seccion), name=titulo, text=html, layout=str(self.cfg.get("layout", 1)))
        despues = elementos(seccion)
        if len(despues) != 1 or despues[0].get("text") != html:
            raise ErrorHelice(f"{titulo}: Hélice dice que se ha añadido, pero el contenido de la sección {seccion} no coincide")
        from datetime import datetime

        self.estado["capitulos"][f"{n:02d}"] = {"seccion": seccion, "titulo": titulo, "html": os.path.basename(ruta_html),
                                               "fecha": datetime.now().strftime("%Y-%m-%d %H:%M")}
        self.guardar()
        return f"{titulo} publicado en {bloque['nombre']} / {tema['nombre']} / {titulo} (sección {seccion})"


def manifiesto(libro, ruta_html):
    """Escribe helice_subida.json junto al HTML; devuelve su ruta (None si el libro no lo usa)."""
    plantilla = (libro.config.get("ficheros") or {}).get("capitulo")
    if not plantilla:
        return None
    n = numero(ruta_html)
    bloque, tema = Publicacion(libro).tema_de(n)
    valores = {"n": n, "bloque": bloque["nombre"] if bloque else "", "tema": tema["nombre"] if tema else ""}
    ruta = [p.format(**valores) for p in plantilla]
    if any(not p.strip() for p in ruta):
        raise ErrorHelice(f"Capítulo {n}: no está en ningún tema de publicar.bloques, no sé su carpeta en Ficheros")
    carpeta = os.path.dirname(os.path.abspath(ruta_html))
    archivos = sorted(os.path.relpath(f, carpeta) for f in glob.glob(os.path.join(carpeta, "*-web-resources", "image", "*"))
                      if not os.path.basename(f).startswith("."))
    destino = os.path.join(carpeta, "helice_subida.json")
    with open(destino, "w", encoding="utf-8") as f:
        json.dump({"capitulo": f"{n:02d}", "ruta": ruta, "archivos": archivos}, f, ensure_ascii=False, indent=1)
    return destino


def elementos(seccion):
    try:
        return llamar("getContent", "GET", section=str(seccion)).get("elements") or []
    except ErrorHelice as e:
        if "no content" in str(e):
            return []
        raise


def numero(ruta):
    m = re.match(r"(\d+)", os.path.basename(ruta))
    return int(m.group(1)) if m else None


def main(argv=None):
    ap = argparse.ArgumentParser(prog="publicar", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("html", nargs="?", help="HTML depurado del capítulo (… - Helice.html)")
    ap.add_argument("--libro", help="libro de config/libros (por defecto, según la ruta)")
    ap.add_argument("--estructura", action="store_true", help="crea los temas de cada bloque")
    ap.add_argument("--plan", action="store_true", help="solo dice si se puede publicar (para la app)")
    ap.add_argument("--manifiesto", action="store_true", help="escribe helice_subida.json para el marcador «Subir a Hélice»")
    args = ap.parse_args(argv)
    try:
        libro = libros.elegir(args.libro, args.html)
        pub = Publicacion(libro)
        if args.estructura:
            pub.crear_estructura()
            return 0
        if not args.html:
            ap.error("indica el HTML del capítulo o --estructura")
        n = numero(args.html)
        if n is None:
            raise ErrorHelice(f"El nombre no empieza por el número de capítulo: {os.path.basename(args.html)}")
        if args.plan:
            print("\n".join(pub.plan(n)))
            return 0
        if args.manifiesto:
            ruta = manifiesto(libro, args.html)
            print(ruta or "")
            return 0
        print(pub.publicar(n, args.html))
        return 0
    except (ErrorHelice, ValueError) as e:
        if args.manifiesto:  # sin manifiesto, la app sigue con la subida a mano
            print("")
            return 0
        print(("NO\n" if args.plan else "ERROR: ") + str(e))
        return 0 if args.plan else 1


if __name__ == "__main__":
    sys.exit(main())
