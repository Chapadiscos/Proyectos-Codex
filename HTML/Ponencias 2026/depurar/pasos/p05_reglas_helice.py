"""Reglas de maquetación del libro en Hélice.

1. Las imágenes no llevan texto alternativo (alt="").
4. <br> entre un párrafo y una imagen, y entre la imagen (o su pie) y el párrafo
   siguiente, salvo que sea un ladillo, que ya tiene espacio por definición.
5. El HTML empieza con un <br>.
6. La cabecera CXX enlaza a la URL de su código QR (se lee de la imagen).
7. Entre dos ladillos seguidos se anula el espacio del segundo.
8. Las imágenes IBXX (estrechas) van con max-width: 60 % y centradas.
"""

import os
import re
from urllib.parse import unquote

from bs4 import BeautifulSoup

from ..bloques import bloque_de, es_bloque_imagen, hermano, tiene_clase
from ..css import anadir_style


def aplicar(soup, cfg, ctx, informe):
    for img in soup.find_all("img"):
        img["alt"] = ""
    _enlace_cabecera(soup, cfg, ctx, informe)
    _ideas_basicas(soup, cfg, ctx, informe)
    _ladillos_seguidos(soup, cfg, informe)
    _separadores(soup, cfg, informe)
    _salto_inicial(soup, informe)


def _nombre_local(img, ctx):
    src = img.get("src", "")
    ruta = ctx.get("origen_imagenes", {}).get(src) or os.path.join(ctx["dir_entrada"], unquote(src))
    return ruta, os.path.basename(ruta)


def _imagenes(soup, patron, ctx):
    for img in soup.find_all("img"):
        ruta, nombre = _nombre_local(img, ctx)
        if re.search(patron, nombre):
            yield img, ruta, nombre


def _enlace_cabecera(soup, cfg, ctx, informe):
    import zxingcpp
    from PIL import Image

    if cfg.get("cabecera_con_qr") is False:  # libro sin QR en la cabecera (Ponencias 2025)
        return
    for img, ruta, nombre in _imagenes(soup, cfg.get("cabecera", r"^C\d+\."), ctx):
        if img.find_parent("a"):
            continue
        codigos = zxingcpp.read_barcodes(Image.open(ruta)) if os.path.exists(ruta) else []
        urls = [c.text for c in codigos if c.text.startswith("http")]
        if not urls:
            informe.avisar(f"no se ha podido leer el QR de la cabecera {nombre}")
            continue
        img.wrap(soup.new_tag("a", attrs={"href": urls[0], "target": "_blank", "rel": "noopener"}))
        informe.contar("cabecera enlazada a la URL de su QR")
        informe.informar(f"enlace de {nombre}: {urls[0]}")


def _ideas_basicas(soup, cfg, ctx, informe):
    """Imágenes estrechas (Ideas básicas): ancho máximo fijo y centradas en el visor."""
    ib = cfg.get("ideas_basicas") or {}
    for img, _, nombre in _imagenes(soup, ib.get("patron", r"^IB\d+\."), ctx):
        anadir_style(img, ib.get("estilo", {"max-width": "60%", "display": "block", "margin": "0 auto"}))
        informe.contar("imágenes Ideas básicas al 60 %")


def _ladillos_seguidos(soup, cfg, informe):
    patron = cfg.get("clase_ladillo", r"Ladillo-\d")
    for p in soup.find_all("p"):
        if tiene_clase(p, patron) and tiene_clase(hermano(p, +1), patron):
            p.insert_after(BeautifulSoup(cfg["entre_ladillos"], "html.parser"))
            informe.contar("espacio anulado entre ladillos seguidos")


def _separadores(soup, cfg, informe):
    ladillo, pie = cfg.get("clase_ladillo", r"Ladillo-\d"), cfg.get("clase_pie", "Pie-Figura")
    bloques = []
    for img in soup.find_all("img"):
        b = bloque_de(img, pie)
        if b not in bloques:
            bloques.append(b)

    def separable(nodo):
        # Solo entre bloques: con texto en línea delante un <br> no añade espacio
        return nodo is not None and getattr(nodo, "name", None) not in (None, "br") \
            and not es_bloque_imagen(nodo) and not tiene_clase(nodo, ladillo)

    for b in bloques:
        if separable(hermano(b, -1)) and not tiene_clase(hermano(b, -1), pie):
            b.insert_before(soup.new_tag("br"))
            informe.contar("<br> antes de imagen")
        fin = b
        if tiene_clase(hermano(fin, +1), pie):
            fin = hermano(fin, +1)  # pie suelto: el salto va después del pie
        if separable(hermano(fin, +1)):
            fin.insert_after(soup.new_tag("br"))
            informe.contar("<br> después de imagen o pie")


def _salto_inicial(soup, informe):
    cuerpo = soup.body or soup
    primero = next((h for h in cuerpo.children if getattr(h, "name", None) or str(h).strip()), None)
    if getattr(primero, "name", None) != "br":
        cuerpo.insert(0, soup.new_tag("br"))
        informe.contar("<br> al principio")
