"""Registro de los cambios y avisos que produce cada paso."""

from collections import Counter


class Informe:
    def __init__(self):
        self.cambios = Counter()
        self.avisos = []

    def contar(self, que, n=1):
        if n:
            self.cambios[que] += n

    def avisar(self, texto):
        self.avisos.append(texto)

    def texto(self):
        lineas = ["Cambios:"]
        if self.cambios:
            lineas += [f"  {n:5d}  {que}" for que, n in sorted(self.cambios.items())]
        else:
            lineas.append("  (ninguno)")
        lineas.append("Avisos:")
        lineas += [f"  - {a}" for a in self.avisos] or ["  (ninguno)"]
        return "\n".join(lineas)
