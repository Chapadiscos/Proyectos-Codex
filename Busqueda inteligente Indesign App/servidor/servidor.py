"""Servidor MCP de la app «Búsqueda inteligente»: copia del de «Ventana Buscar con Claude en Indesign»
con solo las herramientas de lectura que usa la búsqueda (más probar_cambio), y que admite que todos
los documentos abiertos estén sin ventana (capítulos de un libro abiertos en segundo plano)."""

import json
import os
import subprocess
import tempfile
from pathlib import Path

from mcp.server.mcpserver import Image, MCPServer
from mcp.server.mcpserver.exceptions import ToolError

APP = os.environ.get("INDESIGN_APP", "Adobe InDesign 2026")
JSX = Path(__file__).parent / "jsx"

mcp = MCPServer(
    name="indesign",
    instructions=(
        "Herramientas para leer y modificar el documento de InDesign que el usuario "
        "tiene abierto. Trabajan sobre el documento activo y la selección actual."
    ),
)


class ErrorInDesign(ToolError):
    """Error previsto: su mensaje llega a Claude (otras excepciones llegan sin texto)."""


def ejecutar_jsx(codigo: str, args: dict | None = None, timeout: int = 60):
    """Ejecuta ExtendScript en InDesign y devuelve el resultado decodificado de JSON.

    El código recibe `ARGS` (objeto) y la función `json(v)`; su última expresión
    debe ser `json(...)`. Un error en el script se devuelve como ErrorInDesign.
    """
    script = "\n".join([
        (JSX / "comun.jsx").read_text(encoding="utf-8"),
        "var ARGS = " + json.dumps(args or {}, ensure_ascii=False) + ";",
        "(function () { try { return (function () {",
        codigo,
        "})(); } catch (e) { return json({__error: String(e) + ' (línea ' + e.line + ')'}); } })();",
    ])
    with tempfile.NamedTemporaryFile("w", suffix=".jsx", encoding="utf-8", delete=False) as f:
        f.write("﻿" + script)
        ruta = f.name
    applescript = f'''
on run argv
    if application "{APP}" is not running then return "__NO_ABIERTO__"
    set archivo to POSIX file (item 1 of argv)
    with timeout of {timeout} seconds
        tell application "{APP}"
            do script archivo language javascript
        end tell
    end timeout
end run'''
    try:
        r = subprocess.run(["osascript", "-e", applescript, ruta],
                           capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        raise ErrorInDesign(f"InDesign no respondió en {timeout} s (¿hay un diálogo abierto?)")
    finally:
        os.unlink(ruta)
    if r.returncode != 0:
        raise ErrorInDesign(r.stderr.strip())
    salida = r.stdout.strip()
    if salida == "__NO_ABIERTO__":
        raise ErrorInDesign(f"{APP} no está abierto")
    datos = json.loads(salida) if salida else None
    if isinstance(datos, dict) and "__error" in datos:
        raise ErrorInDesign(datos["__error"])
    return datos


@mcp.tool()
def estado() -> dict:
    """Describe el InDesign abierto: versión, documentos, documento activo
    (nombre, ruta, páginas, página visible, si tiene cambios sin guardar) y
    la selección actual (tipo de objetos y, si es texto, su contenido)."""
    return ejecutar_jsx((JSX / "estado.jsx").read_text(encoding="utf-8"))


@mcp.tool()
def ver_pagina(pagina: str = "", resolucion: int = 100) -> list:
    """Devuelve una imagen PNG de una página del documento activo, tal como se
    imprimiría (sin marcos ni guías). `pagina` es el nombre que aparece en el
    panel Páginas; vacío = la página visible. `resolucion` en ppp (36–200)."""
    resolucion = max(36, min(200, resolucion))
    with tempfile.TemporaryDirectory() as tmp:
        ruta = os.path.join(tmp, "pagina.png")
        info = ejecutar_jsx((JSX / "ver_pagina.jsx").read_text(encoding="utf-8"),
                            {"pagina": pagina, "resolucion": resolucion, "ruta": ruta})
        if not os.path.exists(ruta):
            raise ErrorInDesign("InDesign no generó la imagen")
        imagen = Image(data=Path(ruta).read_bytes(), format="png")
    return [json.dumps(info, ensure_ascii=False), imagen]


@mcp.tool()
def consultar(codigo: str, documento: str = "") -> dict:
    """Ejecuta ExtendScript de SOLO LECTURA sobre un documento y devuelve
    lo que el código devuelva con `return` (datos simples, nunca objetos de InDesign).
    Si el código modifica el documento, se deshace y se devuelve un error.

    El código recibe `doc` y estas ayudas:
    - `pagina(o)`: nombre de la página de un texto u objeto (null si está fuera).
    - `ref(o)`: referencia para volver a localizar `o` después.
    - `contexto(t)`: texto alrededor de `t`, con `t` marcado entre ⟦ ⟧.
    Si usas findGrep/findText, deja las preferencias en NothingEnum.NOTHING al acabar.
    `documento`: nombre de un documento abierto (también los abiertos sin ventana, p. ej.
    capítulos de un libro); vacío = el documento activo."""
    return ejecutar_jsx((JSX / "consultar.jsx").read_text(encoding="utf-8"),
                        {"codigo": codigo, "documento": documento}, timeout=120)


@mcp.tool()
def probar_cambio(aplicar: str, refs: list[str]) -> list:
    """Prueba un cambio sin dejarlo hecho: para cada referencia (hasta 5, de `ref(o)`
    en `consultar`) aplica `aplicar` (cuerpo de función que recibe `obj` y `doc`),
    anota el texto antes y después (con el objetivo entre ⟦ ⟧) y lo deshace en el acto.
    Úsala para comprobar un cambio antes de proponerlo."""
    return ejecutar_jsx((JSX / "probar_cambio.jsx").read_text(encoding="utf-8"),
                        {"aplicar": aplicar, "refs": refs}, timeout=120)


if __name__ == "__main__":
    mcp.run()
