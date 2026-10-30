#!/usr/bin/env python3
"""
Pone todas las conversaciones en el historial de Claude Code de "Proyectos Codex".

Uso:
    python3 importar_a_claude.py

1) Mueve a la carpeta del proyecto principal las sesiones de Claude que se
   abrieron desde una subcarpeta (InDesign MCP, Formatear Word en Indesign...).
2) Titula cada conversación de Claude como "Carpeta/tema" (TITULOS_CLAUDE).
3) Convierte las conversaciones de Codex en sesiones de Claude, con el texto
   de cada mensaje (sin los resultados de las herramientas), para poder
   abrirlas desde el historial y seguir hablando con todo ese contexto.

Se puede volver a ejecutar: las conversaciones de Codex ya importadas se
regeneran con el mismo identificador en lugar de duplicarse.
"""

import json
import re
import shutil
import uuid
from datetime import datetime
from pathlib import Path

from exportar_conversaciones import CLAUDE_PROYECTOS, CODEX, TITULOS_CODEX, leer_codex, limpiar

PROYECTO = "/Volumes/DATOS/Proyectos Codex"
DESTINO = CLAUDE_PROYECTOS / re.sub(r"[^A-Za-z0-9]", "-", PROYECTO)
VERSION = "2.1.312"

# Título de cada sesión de Claude (primeros 8 caracteres del id → título).
TITULOS_CLAUDE = {
    "e94a680d": "BCE Anejos",
    "6824eae3": "Scripts InDesign/Eliminar texto alternativo",
    "d8641b7a": "HTML/HTML - Preparar HTML exportado desde InDesign para Helice",
    "3135837e": "HTML/HTML - Preparación de InDesign para HTML",
    "df7edc27": "Ventana Buscar con Claude en Indesign",
    "bdcc7f46": "Ventana Formatear Word Indesign",
}

# Carpeta de "Proyectos Codex" de la que trata cada conversación de Codex.
# Las que no están aquí toman el nombre de la carpeta en la que se abrieron.
CARPETAS_CODEX = {
    "019e4ed7": "Scripts InDesign",
    "019e4f53": "Scripts InDesign",
    "019f18cb": "Scripts Illustrator",
    "019f1934": "Scripts Illustrator",
    "019f1e90": "Scripts InDesign",
}

AVISO_CODEX = ("*(Conversación importada desde Codex, del {fecha}, abierta en «{cwd}». "
               "Las respuestas son de Codex; los resultados de sus herramientas no se conservan.)*\n\n")


def mover_sesiones_de_subcarpetas():
    for carpeta in CLAUDE_PROYECTOS.glob(DESTINO.name + "-*"):
        for item in list(carpeta.iterdir()):
            if (DESTINO / item.name).exists():
                print(f"  ! Ya existe {item.name} en el proyecto principal; se deja donde está")
                continue
            shutil.move(str(item), str(DESTINO / item.name))
            print(f"  Movido {carpeta.name}/{item.name}")
        if not any(carpeta.iterdir()):
            carpeta.rmdir()


def titular(archivo, titulo, sesion):
    """Añade el título si no es ya el último título personalizado de la sesión."""
    actual = None
    with archivo.open(encoding="utf-8", errors="replace") as f:
        for linea in f:
            if '"custom-title"' in linea:
                actual = json.loads(linea).get("customTitle")
    if actual != titulo:
        with archivo.open("a", encoding="utf-8") as f:
            f.write(json.dumps({"type": "custom-title", "customTitle": titulo, "sessionId": sesion},
                               ensure_ascii=False) + "\n")


def titular_sesiones_claude():
    for prefijo, titulo in TITULOS_CLAUDE.items():
        for archivo in DESTINO.glob(f"{prefijo}*.jsonl"):
            titular(archivo, titulo, archivo.stem)


def leer_conversacion_codex(archivo):
    """Devuelve (meta, modelo, turnos) con turnos = [[rol, timestamp, texto], ...]."""
    meta, modelo, turnos = {}, None, []
    for linea in leer_codex(archivo):
        try:
            o = json.loads(linea)
        except ValueError:
            continue
        p = o.get("payload") or {}
        ts = o.get("timestamp")
        if o.get("type") == "session_meta":
            meta = p
        elif o.get("type") == "turn_context":
            modelo = p.get("model") or modelo
        elif o.get("type") == "response_item":
            if p.get("type") == "message" and p.get("role") in ("user", "assistant"):
                texto = "\n\n".join(c.get("text", "") for c in p.get("content", []) if isinstance(c, dict))
                if p["role"] == "user":
                    if texto.lstrip().startswith(("<environment_context", "<user_instructions", "# AGENTS.md")):
                        continue
                    rol, texto = "user", limpiar(texto)
                else:
                    rol, texto = "assistant", texto.strip()
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
                rol, texto = "assistant", f"> 🔧 {p.get('name') or p.get('type')}: {' '.join(str(args).split())[:160]}"
            else:
                continue
            if not texto:
                continue
            if turnos and turnos[-1][0] == rol:
                turnos[-1][2] += "\n\n" + texto
            else:
                turnos.append([rol, ts, texto])
    return meta, modelo, turnos


def importar_codex():
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
        meta, modelo, turnos = leer_conversacion_codex(archivo)
        if meta.get("thread_source") == "subagent" or not any(r == "user" for r, _, _ in turnos):
            continue
        ids = re.findall(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", archivo.name)
        ident = ids[-1] if ids else archivo.stem
        sesion = str(uuid.uuid5(uuid.NAMESPACE_URL, "codex:" + ident))  # estable entre ejecuciones

        cwd = meta.get("cwd") or PROYECTO
        carpeta = CARPETAS_CODEX.get(ident[:8]) or Path(cwd).name
        tema = (TITULOS_CODEX.get(ident[:8]) or titulos.get(meta.get("id"))
                or next(t for r, _, t in turnos if r == "user").split("\n")[0][:60])
        if len(ids) > 1:
            tema += " (continuación)"
        titulo = f"{carpeta}/{tema} (Codex)"

        if turnos[0][0] != "user":
            turnos.insert(0, ["user", turnos[0][1], ""])
        fecha = datetime.fromisoformat(turnos[0][1].replace("Z", "+00:00")).astimezone()
        turnos[0][2] = AVISO_CODEX.format(fecha=f"{fecha:%d/%m/%Y}", cwd=cwd) + turnos[0][2]

        lineas, padre = [], None
        for rol, ts, texto in turnos:
            u = str(uuid.uuid5(uuid.NAMESPACE_URL, f"codex:{ident}:{len(lineas)}"))
            comun = {"parentUuid": padre, "isSidechain": False, "uuid": u, "timestamp": ts,
                     "userType": "external", "entrypoint": "claude-vscode", "cwd": PROYECTO,
                     "sessionId": sesion, "version": VERSION, "importadoDe": "codex"}
            if rol == "user":
                lineas.append({**comun, "type": "user",
                               "message": {"role": "user", "content": [{"type": "text", "text": texto}]}})
            else:
                lineas.append({**comun, "type": "assistant",
                               "message": {"model": modelo or "codex", "id": "msg_codex_" + u.replace("-", ""),
                                           "type": "message", "role": "assistant",
                                           "content": [{"type": "text", "text": texto}],
                                           "stop_reason": "end_turn", "stop_sequence": None,
                                           "usage": {"input_tokens": 0, "output_tokens": 0}}})
            padre = u
        lineas.append({"type": "custom-title", "customTitle": titulo, "sessionId": sesion})

        # Si la conversación ya siguió en Claude, regenerarla borraría lo nuevo.
        destino = DESTINO / f"{sesion}.jsonl"
        if destino.exists() and any(
            '"importadoDe"' not in l and ('"type": "assistant"' in l or '"type":"assistant"' in l)
            for l in destino.open(encoding="utf-8")
        ):
            print(f"  = {titulo}: ya continuó en Claude, no se regenera")
            continue

        with destino.open("w", encoding="utf-8") as f:
            for o in lineas:
                f.write(json.dumps(o, ensure_ascii=False) + "\n")
        n += 1
    return n


if __name__ == "__main__":
    print("1) Sesiones de subcarpetas:")
    mover_sesiones_de_subcarpetas()
    print("2) Títulos de las conversaciones de Claude")
    titular_sesiones_claude()
    print(f"3) Codex: {importar_codex()} conversaciones importadas")
