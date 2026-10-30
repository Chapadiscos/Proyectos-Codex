"""Búsqueda en segundo plano para la ventana «Buscar con Claude» de InDesign.

Uso: buscar.py <peticion.json>
La petición trae {descripcion, alcance, salida}; alcance = {tipo, documentos, ref, libro}
(tipo: seleccion, articulo, documento, documentos o libro). Lanza Claude Code sin interfaz con
el servidor MCP de este proyecto (solo herramientas de lectura) y escribe en `salida`
el resultado {resumen, resultados, cambio} o {error}. Mientras trabaja, deja su PID en
`salida + ".pid"` para que la ventana pueda cancelarlo.
"""

import json
import os
import signal
import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).parent
HERRAMIENTAS = "mcp__indesign__estado,mcp__indesign__consultar,mcp__indesign__ver_pagina,mcp__indesign__probar_cambio"

ESQUEMA = {
    "type": "object",
    "required": ["resumen", "resultados", "cambio"],
    "properties": {
        "resumen": {"type": "string"},
        "cambio": {
            "type": "object",
            "required": ["descripcion", "aplicar"],
            "properties": {"descripcion": {"type": "string"}, "aplicar": {"type": "string"}},
        },
        "resultados": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["documento", "pagina", "texto", "ref", "dudoso"],
                "properties": {
                    "documento": {"type": "string"},
                    "pagina": {"type": "string"},
                    "texto": {"type": "string"},
                    "ref": {"type": "string"},
                    "propuesta": {"type": "string"},
                    "dudoso": {"type": "boolean"},
                    "motivo": {"type": "string"},
                },
            },
        },
    },
}

SISTEMA = """Eres el buscador de una ventana de InDesign parecida a Buscar/Cambiar.
El usuario describe en español lo que quiere encontrar o cambiar, y en qué ámbito
(selección, artículo, documento, varios documentos o los capítulos de un libro).
Busca con la herramienta `consultar` (solo lectura; usa findGrep/findText, estilos,
propiedades del texto y de los objetos), pasándole `documento` con el nombre de cada
documento. Respeta el ámbito: si es una selección o un artículo, busca solo dentro de
resolve(ref) (findGrep/findText funcionan sobre ese texto). No modifiques nada.

Responde con:
- resumen: una o dos frases con lo encontrado (p. ej. «15 años en 45 Book en el texto
  base»). Si has dejado partes fuera (otros estilos, tablas, texto desbordado…), dilo aquí.
- resultados: cada aparición, en orden de lectura (documento a documento).
  `documento` = nombre del documento, `pagina` = pagina(o) (o "fuera"),
  `texto` = contexto(t) para texto o una descripción corta para objetos, `ref` = ref(o)
  exactamente como lo devuelve. Como máximo 300; si hay más, dilo en el resumen.
  `ref` debe abarcar justo lo que se cambiará (p. ej. el número, no la frase entera).
- dudoso: true si el caso encaja con la búsqueda pero probablemente NO deba cambiarse
  o hay que mirarlo (p. ej. «versión 2.2» al pasar números a formato inglés, una cita
  literal, un nombre propio, una referencia bibliográfica); `motivo` = la duda en pocas
  palabras. Los dudosos no se cambian salvo que el usuario lo decida uno a uno.
  No incluyas casos que claramente no son de la búsqueda.
- cambio: si el usuario pide cambiar algo («pon», «quita», «corrige», «pasa a»…), o la
  corrección es evidente y segura, propón un cambio que se aplicará a cada resultado:
  `descripcion` = nombre corto en español para Edición > Deshacer; `aplicar` = cuerpo de
  una función que recibe `obj` (el objeto de `ref`) y `doc`, y cambia SOLO ese resultado,
  sin depender de los demás (p. ej. `obj.fontStyle = "85 Heavy";` o
  `obj.contents = obj.contents.replace(/\\./g, ",");`).
  Si solo quiere buscar, deja `descripcion` y `aplicar` vacíos.
  Antes de responder, prueba `aplicar` con `probar_cambio` en 2 o 3 resultados y comprueba
  que el después es el esperado; si no, corrígelo.
- propuesta: en cada resultado con cambio, el resultado del cambio, muy breve
  («1,234.5», «→ 85 Heavy», «dos espacios → uno»).
Escribe resumen y motivos para un maquetador: claros y breves, sin identificadores
internos (story, id, specifier) ni nombres de funciones.
Sé rápido: pocas llamadas, y devuelve todos los datos de una vez desde `consultar`."""


def claude_ejecutable() -> str:
    candidatos = sorted(Path.home().glob(".vscode/extensions/anthropic.claude-code-*/resources/native-binary/claude"),
                        key=lambda p: [int(x) if x.isdigit() else x for x in p.parts[-4].replace("-", ".").split(".")])
    if not candidatos:
        raise RuntimeError("No encuentro Claude Code (extensión de VS Code)")
    return str(candidatos[-1])


def describir_alcance(a: dict) -> str:
    docs = ", ".join(f"«{d}»" for d in a.get("documentos", []))
    if a["tipo"] == "seleccion":
        return f"Ámbito: solo el texto seleccionado en {docs}: resolve(\"{a['ref']}\")."
    if a["tipo"] == "articulo":
        return f"Ámbito: solo el artículo (historia) donde está el cursor en {docs}: resolve(\"{a['ref']}\")."
    if a["tipo"] == "libro":
        return f"Ámbito: todos los capítulos del libro «{a['libro']}»: {docs} (abiertos, algunos sin ventana)."
    if a["tipo"] == "documentos":
        return f"Ámbito: todos estos documentos abiertos: {docs}."
    return f"Ámbito: todo el documento {docs}."


def main():
    peticion = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    Path(sys.argv[1]).unlink()
    salida = Path(peticion["salida"])
    pid = Path(str(salida) + ".pid")

    def escribir(datos):
        tmp = salida.with_suffix(".tmp")
        tmp.write_text(json.dumps(datos, ensure_ascii=True), encoding="utf-8")
        os.replace(tmp, salida)
        pid.unlink(missing_ok=True)

    proceso = None

    def cancelar(*_):
        if proceso:
            proceso.terminate()
        escribir({"error": "Búsqueda cancelada"})
        sys.exit(0)

    signal.signal(signal.SIGTERM, cancelar)
    pid.write_text(str(os.getpid()))
    try:
        orden = [claude_ejecutable(), "-p",
                 f"{describir_alcance(peticion['alcance'])}\nBúsqueda: {peticion['descripcion']}",
                 "--append-system-prompt", SISTEMA,
                 "--mcp-config", str(RAIZ / ".mcp.json"), "--strict-mcp-config",
                 "--tools", "", "--allowedTools", HERRAMIENTAS,
                 "--setting-sources", "", "--no-session-persistence",
                 "--output-format", "json", "--json-schema", json.dumps(ESQUEMA)]
        proceso = subprocess.Popen(orden, cwd=RAIZ, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        out, err = proceso.communicate(timeout=600)
        datos = json.loads(out) if out.strip() else {}
        if datos.get("is_error") or "structured_output" not in datos:
            escribir({"error": (datos.get("result") or err or "Claude no devolvió resultado").strip()[:500]})
        else:
            escribir(datos["structured_output"])
    except subprocess.TimeoutExpired:
        proceso.kill()
        escribir({"error": "La búsqueda tardó más de 10 minutos"})
    except Exception as e:
        escribir({"error": f"{type(e).__name__}: {e}"})


if __name__ == "__main__":
    main()
