"""Configuración de cada libro: config/libros/<libro>.yaml.

El libro de un .indd o un .html se reconoce por su ruta (libro.raiz). Un libro puede
heredar de otro con «base: otro.yaml» y cambiar solo lo que sea distinto: las secciones
se mezclan y las listas se sustituyen enteras; un «{}» vacío borra lo heredado. Los
archivos que empiezan por «_» (la plantilla) no son libros.
"""

import glob
import os

import yaml

DIR_LIBROS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config", "libros")


class Libro:
    def __init__(self, ruta):
        self.ruta = os.path.abspath(ruta)
        self.id = os.path.splitext(os.path.basename(ruta))[0]
        self.dir_config = os.path.dirname(self.ruta)  # las rutas relativas del yaml parten de aquí
        self.config = cargar(self.ruta)
        datos = self.config.get("libro") or {}
        self.nombre = datos.get("nombre", self.id)
        self.raiz = datos.get("raiz") or datos.get("carpeta") or ""

    def contiene(self, ruta):
        raiz = os.path.normcase(os.path.abspath(self.raiz)).rstrip(os.sep)
        return bool(self.raiz) and os.path.normcase(os.path.abspath(ruta)).startswith(raiz + os.sep)


def cargar(ruta):
    with open(ruta, encoding="utf-8") as f:
        datos = yaml.safe_load(f) or {}
    base = datos.pop("base", None)
    if not base:
        return datos
    return mezclar(cargar(os.path.join(os.path.dirname(ruta), base)), datos)


def mezclar(base, cambios):
    r = dict(base)
    for k, v in cambios.items():
        r[k] = mezclar(r[k], v) if v and isinstance(v, dict) and isinstance(r.get(k), dict) else v
    return r


def todos(directorio=None):
    rutas = sorted(glob.glob(os.path.join(directorio or DIR_LIBROS, "*.yaml")))
    return [Libro(r) for r in rutas if not os.path.basename(r).startswith("_")]


def elegir(libro=None, ruta=None, directorio=None):
    """El libro indicado por nombre, el que contiene la ruta o, si solo hay uno, ese."""
    libros = todos(directorio)
    nombres = ", ".join(l.id for l in libros) or "ninguno"
    if libro:
        for l in libros:
            if l.id == libro:
                return l
        raise ValueError(f"No hay configuración para el libro «{libro}» (hay: {nombres})")
    if ruta and os.path.exists(ruta):
        encontrados = [l for l in libros if l.contiene(ruta)]
        if len(encontrados) == 1:
            return encontrados[0]
        if len(encontrados) > 1:
            raise ValueError(f"{ruta} está en varios libros: {', '.join(l.id for l in encontrados)}")
        raise ValueError(
            f"{ruta} no está en la carpeta de ningún libro configurado ({nombres}).\n"
            f"Para un libro nuevo, copia config/libros/_plantilla.yaml con el nombre del libro y pon su carpeta en libro.raiz."
        )
    if len(libros) == 1:
        return libros[0]
    raise ValueError(f"Indica el libro con --libro ({nombres})")
