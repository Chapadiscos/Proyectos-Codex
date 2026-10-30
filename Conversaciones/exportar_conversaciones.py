#!/usr/bin/env python3
"""
Exporta a Markdown todas las conversaciones de Claude Code y de Codex.

Uso:
    python3 exportar_conversaciones.py

Crea (o actualiza) un .md por conversación en las subcarpetas Claude/ y Codex/
junto a este script. Volver a ejecutarlo actualiza las conversaciones que hayan
crecido y añade las nuevas; nunca borra un .md ya exportado, aunque la
conversación original haya desaparecido.

Se guardan los mensajes del usuario y las respuestas, y cada herramienta usada
queda como una línea breve. Los resultados de las herramientas (salidas de
comandos, archivos leídos...) no se copian.
"""

import glob
import json
import re
import sys
from datetime import datetime
from pathlib import Path

import compression.zstd as zstd  # Python 3.14+

DESTINO = Path(__file__).resolve().parent
CLAUDE_PROYECTOS = Path.home() / ".claude" / "projects"
CODEX = Path.home() / ".codex"

# Título propio de una conversación de Codex (primeros 8 caracteres del id →
# título), por encima del que tenga en Codex.
TITULOS_CODEX = {
    "019f1e90": "Hipervinculos Indice PDF BdE",
}

# Bloques que el programa añade al mensaje del usuario y que no escribió él.
RUIDO_RE = re.compile(
    r"<(system-reminder|ide_selection|ide_opened_file|environment_context|"
    r"user_instructions|local-command-stdout|local-command-caveat|app-context|"
    r"permissions instructions|collaboration_mode|skills_instructions)[^>]*>.*?</\1>",
    re.DOTALL,
)
PEGADO_RE = re.compile(r"</?pasted_content[^>]*>")
COMANDO_RE = re.compile(r"<command-name>(.*?)</command-name>.*?(?:<command-args>(.*?)</command-args>)?", re.DOTALL)


def limpiar(texto):
    texto = RUIDO_RE.sub("", texto)
    m = COMANDO_RE.search(texto)
    if m:
        texto = f"`{m.group(1)} {m.group(2) or ''}`".replace(" `", "`")
    texto = PEGADO_RE.sub("", texto)
    return texto.strip()


def nombre_archivo(fecha, titulo, ident):
    titulo = re.sub(r'[\\/:*?"<>|\n\r\t]+', " ", titulo or "Sin título").strip()[:80]
    return f"{fecha:%Y-%m-%d %H%M} {titulo} [{ident[:13]}].md"


def guardar(carpeta, fecha, titulo, ident, cabecera, turnos):
    carpeta.mkdir(parents=True, exist_ok=True)
    # Si la conversación cambió de título, sustituye su exportación anterior.
    for viejo in carpeta.glob(f"* {glob.escape(f'[{ident[:13]}]')}.md"):
        viejo.unlink()
    lineas = [f"# {titulo}", ""] + [f"- **{k}:** {v}" for k, v in cabecera.items() if v]
    for rol, hora, texto in turnos:
        lineas += ["", "---", "", f"### {rol} · {hora}", "", texto]
    (carpeta / nombre_archivo(fecha, titulo, ident)).write_text("\n".join(lineas) + "\n", encoding="utf-8")


def hora(ts):
    return datetime.fromisoformat(ts.replace("Z", "+00:00")).astimezone().strftime("%Y-%m-%d %H:%M")


def anadir(turnos, rol, ts, texto):
    """Junta en un solo turno los bloques seguidos del mismo autor."""
    if not texto:
        return
    if turnos and turnos[-1][0] == rol:
        turnos[-1][2] += "\n\n" + texto
    else:
        turnos.append([rol, hora(ts), texto])


# ---------------------------------------------------------------- Claude Code

def exportar_claude():
    n = 0
    for archivo in sorted(CLAUDE_PROYECTOS.glob("*/*.jsonl")):
        turnos, titulo, propio, cwd, primera = [], None, None, None, None
        for linea in archivo.open(encoding="utf-8", errors="replace"):
            try:
                o = json.loads(linea)
            except ValueError:
                continue
            tipo = o.get("type")
            if tipo == "custom-title":
                propio = o.get("customTitle") or propio
                continue
            if tipo in ("ai-title", "summary"):
                titulo = o.get("aiTitle") or o.get("summary") or titulo
                continue
            # Los mensajes importados desde Codex ya se exportan en Codex/;
            # aquí solo cuenta lo que se haya hablado con Claude después.
            if tipo not in ("user", "assistant") or o.get("isSidechain") or o.get("isMeta") or o.get("importadoDe"):
                continue
            ts = o.get("timestamp")
            primera = primera or ts
            cwd = cwd or o.get("cwd")
            contenido = o.get("message", {}).get("content")
            if isinstance(contenido, str):
                contenido = [{"type": "text", "text": contenido}]
            for b in contenido or []:
                if not isinstance(b, dict):
                    continue
                if tipo == "user" and b.get("type") == "text":
                    texto = limpiar(b.get("text", ""))
                    if o.get("isCompactSummary"):
                        texto = "*(Resumen automático de la conversación anterior)*\n\n" + texto
                    anadir(turnos, "Usuario", ts, texto)
                elif tipo == "assistant" and b.get("type") == "text":
                    anadir(turnos, "Claude", ts, b.get("text", "").strip())
                elif tipo == "assistant" and b.get("type") == "tool_use":
                    entrada = b.get("input") or {}
                    detalle = (entrada.get("description") or entrada.get("file_path")
                               or entrada.get("command") or entrada.get("prompt") or "")
                    detalle = " ".join(str(detalle).split())[:160]
                    anadir(turnos, "Claude", ts, f"> 🔧 {b.get('name')}: {detalle}")
        if not primera or not any(r == "Usuario" for r, _, _ in turnos):
            continue
        fecha = datetime.fromisoformat(primera.replace("Z", "+00:00")).astimezone()
        guardar(DESTINO / "Claude", fecha, propio or titulo or "Sin título", archivo.stem,
                {"Carpeta": cwd, "Sesión": archivo.stem, "Archivo original": archivo}, turnos)
        n += 1
    return n


# ---------------------------------------------------------------------- Codex

def leer_codex(archivo):
    datos = archivo.read_bytes()
    if archivo.suffix == ".zst":
        datos = zstd.decompress(datos)
    return datos.decode("utf-8", errors="replace").splitlines()


def exportar_codex():
    titulos = {}
    indice = CODEX / "session_index.jsonl"
    if indice.exists():
        for linea in indice.open(encoding="utf-8"):
            try:
                o = json.loads(linea)
                titulos[o["id"]] = o.get("thread_name")
            except (ValueError, KeyError):
                pass

    archivos = sorted(CODEX.glob("sessions/**/rollout-*.jsonl*")) + sorted(CODEX.glob("archived_sessions/rollout-*.jsonl*"))
    n = 0
    for archivo in archivos:
        try:
            lineas = leer_codex(archivo)
        except Exception as e:
            print(f"  ! No se pudo leer {archivo.name}: {e}")
            continue
        turnos, meta = [], {}
        for linea in lineas:
            try:
                o = json.loads(linea)
            except ValueError:
                continue
            p = o.get("payload") or {}
            ts = o.get("timestamp")
            if o.get("type") == "session_meta":
                meta = p
                continue
            if o.get("type") != "response_item":
                continue
            if p.get("type") == "message" and p.get("role") in ("user", "assistant"):
                texto = "\n\n".join(c.get("text", "") for c in p.get("content", []) if isinstance(c, dict))
                if p["role"] == "user":
                    if texto.lstrip().startswith(("<environment_context", "<user_instructions", "# AGENTS.md")):
                        continue
                    anadir(turnos, "Usuario", ts, limpiar(texto))
                else:
                    anadir(turnos, "Codex", ts, texto.strip())
            elif p.get("type") in ("function_call", "custom_tool_call", "local_shell_call"):
                args = p.get("arguments") or p.get("input") or ""
                try:
                    a = json.loads(args) if isinstance(args, str) else args
                    if isinstance(a, dict):
                        args = a.get("command") or a.get("cmd") or a.get("path") or args
                except ValueError:
                    pass
                if isinstance(args, list):
                    args = " ".join(map(str, args))
                args = " ".join(str(args).split())[:160]
                anadir(turnos, "Codex", ts, f"> 🔧 {p.get('name') or p.get('type')}: {args}")
        if not any(r == "Usuario" for r, _, _ in turnos):
            continue
        if meta.get("thread_source") == "subagent":
            continue  # revisiones automáticas internas de Codex, no conversaciones
        # Una misma conversación puede continuar en otro archivo
        # ("rollout-...-<id>_<id2>.jsonl"); se exporta aparte como continuación.
        ids = re.findall(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", archivo.name)
        ident = ids[-1] if ids else archivo.stem
        inicio = meta.get("timestamp") or turnos[0][1]
        fecha = datetime.fromisoformat(inicio.replace("Z", "+00:00")).astimezone()
        titulo = (TITULOS_CODEX.get(ident[:8]) or titulos.get(meta.get("id"))
                  or next(t for r, _, t in turnos if r == "Usuario").split("\n")[0][:60])
        if len(ids) > 1:
            titulo += " (continuación)"
        guardar(DESTINO / "Codex", fecha, titulo, ident,
                {"Carpeta": meta.get("cwd"), "Sesión": ident, "Archivo original": archivo}, turnos)
        n += 1
    return n


if __name__ == "__main__":
    if sys.version_info < (3, 14):
        sys.exit("Hace falta Python 3.14 o posterior (para leer los archivos .zst de Codex).")
    print(f"Claude: {exportar_claude()} conversaciones exportadas")
    print(f"Codex:  {exportar_codex()} conversaciones exportadas")
    print(f"Guardadas en {DESTINO}")
