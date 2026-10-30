"""Prepara el formato final: página completa o solo fragmento para pegar en Hélice.

Si se indica `vista_previa_css`, genera además <nombre>.vista.html con esa CSS
incrustada, para revisar en el navegador cómo quedará con los estilos de Hélice.
También avisa de las clases que no tienen regla en esa CSS y de las que no
deberían usarse en InDesign (`estilos_no_permitidos`).
"""

from ..css import leer_reglas
from ..pasos.p01_estilos_capitulo import SELECTOR_CLASE


def aplicar(soup, cfg, ctx, informe):
    _comprobar_estilos(soup, cfg, ctx, informe)
    css = cfg.get("vista_previa_css")
    if css:
        with open(ctx["resolver"](css), encoding="utf-8") as f:
            contenido = f.read()
        ctx["vista_previa"] = str(soup).replace("</head>", f"<style>\n{contenido}\n</style>\n</head>", 1)

    if cfg.get("modo", "pagina") != "fragmento":
        ctx["resultado"] = str(soup)
        return
    # Fragmento: los <style>/<link> del head pasan delante del contenido del body.
    partes = []
    if soup.head:
        partes += [str(t) for t in soup.head.find_all(["style", "link"])]
    cuerpo = soup.body or soup
    partes += [str(c) for c in cuerpo.contents]
    ctx["resultado"] = "".join(partes).strip() + "\n"
    informe.contar("salida en modo fragmento")


def _comprobar_estilos(soup, cfg, ctx, informe):
    usadas = {}
    for tag in soup.find_all(class_=True):
        for clase in tag["class"]:
            usadas[clase] = usadas.get(clase, 0) + 1

    for clase in cfg.get("estilos_no_permitidos", []):
        if clase in usadas:
            informe.avisar(f"estilo que no debe usarse en InDesign: {clase} ({usadas[clase]} elementos)")

    css = cfg.get("vista_previa_css")
    if not css:
        return
    with open(ctx["resolver"](css), encoding="utf-8") as f:
        definidas = {
            m.group(2)
            for selectores, _ in leer_reglas(f.read())
            for s in selectores
            if (m := SELECTOR_CLASE.fullmatch(s.split("::")[0]))
        }
    for clase, n in sorted(usadas.items()):
        if clase not in definidas:
            informe.avisar(f"clase sin regla en la CSS de Hélice: {clase} ({n} elementos)")
