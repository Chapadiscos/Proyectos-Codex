"""Pasos del pipeline, en el orden en que se ejecutan.

Cada paso es un módulo que puede definir:
  pre(texto, cfg, ctx, informe) -> texto   sobre el HTML en bruto, antes de parsearlo
  aplicar(soup, cfg, ctx, informe)          sobre el árbol BeautifulSoup
`cfg` es la sección del paso en config.yaml; `ctx` lleva rutas y datos comunes.
"""

from . import (
    p01_estilos_capitulo,
    p02_limpieza,
    p03_correcciones_indesign,
    p04_imagenes,
    p05_reglas_helice,
    p06_inyectar,
    p07_salida,
)

PASOS = [
    ("estilos_capitulo", p01_estilos_capitulo),
    ("limpieza", p02_limpieza),
    ("correcciones_indesign", p03_correcciones_indesign),
    ("imagenes", p04_imagenes),
    ("reglas_helice", p05_reglas_helice),
    ("inyectar", p06_inyectar),
    ("salida", p07_salida),
]
