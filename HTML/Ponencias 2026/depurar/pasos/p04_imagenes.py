"""Sustituye las rutas locales de las imágenes por sus URL en Hélice.

Las URL salen del .txt del capítulo (una por línea). Cada URL se descarga y se
empareja por contenido (md5) con la imagen local de *-web-resources: Hélice
guarda el archivo tal cual, así que no depende del orden de subida.
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

    usadas = set()
    for img in soup.find_all("img"):
        src = img.get("src", "")
        if src.startswith(("http://", "https://", "data:")):
            continue
        nombre = os.path.basename(unquote(src))
        ruta = os.path.join(ctx["dir_entrada"], unquote(src))
        url = remotas.get(_md5(ruta)) if os.path.exists(ruta) else None
        if url:
            img["src"] = url
            usadas.add(url)
            ctx.setdefault("origen_imagenes", {})[url] = ruta
            informe.contar("imágenes con URL de Hélice")
        else:
            informe.avisar(f"imagen sin URL en Hélice: {nombre}")

    for url in urls:
        if url not in usadas:
            informe.avisar(f"URL del .txt que no corresponde a ninguna imagen: {url}")


def _descargar(url, cache):
    ruta = os.path.join(cache, os.path.basename(url))
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
