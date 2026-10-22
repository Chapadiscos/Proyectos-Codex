"""Publicación en Hélice con su API (panel.helice.app/api/ws, token en el llavero de macOS).

La API no deja crear secciones de tipo Menú, ni borrar ni editar lo creado. Por eso:
- los bloques (Menú) se crean a mano en el panel y su identificador va en la
  configuración del libro (publicar.bloques[].seccion);
- ./publicar --estructura crea dentro de cada bloque sus temas (secciones de
  Información) y guarda sus identificadores en publicar.estado;
- ./publicar 06 añade al tema del capítulo un elemento «Capítulo 06» con su HTML
  depurado y comprueba que ha quedado (getContent). Un capítulo ya publicado no se
  vuelve a publicar: las correcciones, en el panel.
Los iconos se asignan en el panel.

--plan ruta.html   para la app: SI | YA | NO, y el tema o el motivo
"""

import argparse
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
        raise ErrorHelice(f"{funcion}: {respuesta.get('error') or respuesta}")
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
        seccion = self.estado["temas"].get(f"{bloque['nombre']}/{tema['nombre']}")
        if not seccion:
            return "NO", f"falta crear «{bloque['nombre']} / {tema['nombre']}» (./publicar --estructura)"
        return "SI", f"{bloque['nombre']} / {tema['nombre']}"

    def publicar(self, n, ruta_html):
        estado, detalle = self.plan(n)
        if estado != "SI":
            raise ErrorHelice(f"Capítulo {n:02d}: {detalle}")
        bloque, tema = self.tema_de(n)
        seccion = self.estado["temas"][f"{bloque['nombre']}/{tema['nombre']}"]
        titulo = self.cfg.get("titulo", "Capítulo {n:02d}").format(n=n)
        html = open(ruta_html, encoding="utf-8").read()
        antes = len(elementos(seccion))
        llamar("addListElement", section=str(seccion), header=titulo, text=html, layout=str(self.cfg.get("layout", 1)))
        despues = elementos(seccion)
        if len(despues) != antes + 1:
            raise ErrorHelice(f"Capítulo {n:02d}: Hélice dice que se ha añadido, pero la sección tiene {len(despues)} elementos (antes {antes})")
        from datetime import datetime

        self.estado["capitulos"][f"{n:02d}"] = {"seccion": seccion, "titulo": titulo, "html": os.path.basename(ruta_html),
                                               "fecha": datetime.now().strftime("%Y-%m-%d %H:%M")}
        self.guardar()
        return f"{titulo} publicado en {bloque['nombre']} / {tema['nombre']} (sección {seccion})"


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
        print(pub.publicar(n, args.html))
        return 0
    except (ErrorHelice, ValueError) as e:
        print(("NO\n" if args.plan else "ERROR: ") + str(e))
        return 0 if args.plan else 1


if __name__ == "__main__":
    sys.exit(main())
