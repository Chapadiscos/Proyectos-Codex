"""Añade el sufijo del libro a las clases de los estilos de párrafo y carácter.

Así el .indd conserva los nombres de sus estilos («Texto base») y en el HTML salen las
clases de la CSS de Hélice («Texto-base-PO26»), que no pisan las de libros de otros
años. Las clases propias de InDesign (anulaciones, _idGen…, estilos de objeto) no se
tocan. El resto de pasos ya trabaja con los nombres con sufijo.
"""

import re


def renombrador(cfg):
    """Función clase de InDesign -> clase de Hélice (None si no hay sufijo configurado)."""
    sufijo = cfg.get("sufijo")
    if not sufijo:
        return None
    excluir = [re.compile(p) for p in cfg.get("excluir", [])]
    # Clases que en Hélice tienen otro nombre (p. ej. otro grupo de estilos en InDesign)
    equivalencias = [(re.compile(k), v) for k, v in (cfg.get("equivalencias") or {}).items()]

    def renombrar(clase):
        if any(p.fullmatch(clase) for p in excluir):
            return clase
        for patron, destino in equivalencias:
            if patron.fullmatch(clase):
                clase = patron.sub(destino, clase)
                break
        return clase + sufijo

    return renombrar


def aplicar(soup, cfg, ctx, informe):
    renombrar = renombrador(cfg)
    if not renombrar:
        return
    sufijo = cfg["sufijo"]
    ctx["renombrar_clase"] = renombrar  # p01 lo aplica a las reglas de la CSS local
    for tag in soup.find_all(class_=True):
        nuevas = [renombrar(c) for c in tag["class"]]
        informe.contar(f"clases con sufijo {sufijo}", sum(a != b for a, b in zip(tag["class"], nuevas)))
        tag["class"] = nuevas
