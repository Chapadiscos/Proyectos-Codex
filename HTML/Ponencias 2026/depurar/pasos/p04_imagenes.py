"""Sustituye las rutas locales de las imágenes por sus URL en Hélice.

Las URL salen del .txt del capítulo (una por línea). Cada URL se descarga y se
empareja por contenido (md5) con la imagen local de *-web-resources: Hélice
guarda el archivo tal cual, así que no depende del orden de subida. Si el md5 no
coincide (InDesign no siempre codifica igual el mismo JPEG al reexportar), se
empareja por parecido visual: mismas dimensiones y píxeles casi iguales.
"""

import glob
import hashlib
import os
from urllib.parse import unquote

import requests


def aplicar(soup, cfg, ctx, informe):
    txts = sorted(glob.glob(os.path.join(ctx["dir_entrada"], cfg.get("lista_urls", "*.txt"))))
    if not txts:
        informe.avisar("no hay .txt con las URL de las imágenes junto al HTML")
        return
    if len(txts) > 1:
        informe.avisar(f"varios .txt; se usa {os.path.basename(txts[0])}")
    with open(txts[0], encoding="utf-8") as f:
        urls = [l.strip() for l in f if l.strip().startswith("http")]

    cache = ctx["resolver_raiz"](cfg.get("cache", ".cache/imagenes"))
    remotas = {}
    for url in urls:
        h = _md5(_descargar(url, cache))
        if h in remotas:
            informe.avisar(f"URL con la misma imagen que otra: {url}")
        remotas.setdefault(h, url)

    usadas, pendientes = set(), []
    for img in soup.find_all("img"):
        src = img.get("src", "")
        if src.startswith(("http://", "https://", "data:")):
            continue
        ruta = os.path.join(ctx["dir_entrada"], unquote(src))
        url = remotas.get(_md5(ruta)) if os.path.exists(ruta) else None
        if url:
            _asignar(img, url, ruta, usadas, ctx)
            informe.contar("imágenes con URL de Hélice")
        else:
            pendientes.append((img, ruta))

    # Si InDesign ha vuelto a codificar el JPEG (reexportación), el md5 cambia:
    # se empareja por parecido visual con las URL que aún no se han usado.
    libres = {h: u for h, u in remotas.items() if u not in usadas}
    for img, ruta in pendientes:
        url = _parecida(ruta, [(u, _ruta_cache(u, cache)) for u in libres.values() if u not in usadas], cfg)
        if url:
            _asignar(img, url, ruta, usadas, ctx)
            informe.contar("imágenes con URL de Hélice (por parecido visual)")
        else:
            informe.avisar(f"imagen sin URL en Hélice: {os.path.basename(ruta)}")

    for url in urls:
        if url not in usadas:
            informe.avisar(f"URL del .txt que no corresponde a ninguna imagen: {url}")


def _asignar(img, url, ruta, usadas, ctx):
    img["src"] = url
    usadas.add(url)
    ctx.setdefault("origen_imagenes", {})[url] = ruta


def _parecida(ruta, candidatas, cfg):
    """URL cuya imagen tiene las mismas dimensiones y casi los mismos píxeles (o None)."""
    if not os.path.exists(ruta):
        return None
    from PIL import Image, ImageChops, ImageStat

    umbral = cfg.get("diferencia_maxima", 3.0)  # media de diferencia por píxel, 0-255
    with Image.open(ruta) as a:
        a = a.convert("RGB")
        mejor = None
        for url, ruta_remota in candidatas:
            with Image.open(ruta_remota) as b:
                if b.size != a.size:
                    continue
                dif = sum(ImageStat.Stat(ImageChops.difference(a, b.convert("RGB"))).mean) / 3
            if dif <= umbral and (mejor is None or dif < mejor[1]):
                mejor = (url, dif)
    return mejor[0] if mejor else None


def _ruta_cache(url, cache):
    return os.path.join(cache, os.path.basename(url))


def _descargar(url, cache):
    ruta = _ruta_cache(url, cache)
    if not os.path.exists(ruta):
        os.makedirs(cache, exist_ok=True)
        r = requests.get(url, timeout=30)
        r.raise_for_status()
        with open(ruta, "wb") as f:
            f.write(r.content)
    return ruta


def _md5(ruta):
    with open(ruta, "rb") as f:
        return hashlib.md5(f.read()).hexdigest()
