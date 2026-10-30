"""Registro de los cambios, avisos e información que produce cada paso.

Los avisos son lo que hay que revisar (impiden la copia automática al
portapapeles); la información es solo para consultar.
"""

from collections import Counter


class Informe:
    def __init__(self):
        self.cambios = Counter()
        self.avisos = []
        self.informacion = []
        self.sin_url = []  # imágenes del capítulo sin URL de Hélice (faltan enlaces)

    def contar(self, que, n=1):
        if n:
            self.cambios[que] += n

    def avisar(self, texto):
        self.avisos.append(texto)

    def informar(self, texto):
        self.informacion.append(texto)

    def texto(self):
        lineas = ["Cambios:"]
        if self.cambios:
            lineas += [f"  {n:5d}  {que}" for que, n in sorted(self.cambios.items())]
        else:
            lineas.append("  (ninguno)")
        if self.informacion:
            lineas.append("Información:")
            lineas += [f"  - {i}" for i in self.informacion]
        lineas.append("Avisos:")
        lineas += [f"  - {a}" for a in self.avisos] or ["  (ninguno)"]
        return "\n".join(lineas)
