# InDesign MCP

Servidor MCP (Python, SDK `mcp` 2.x → `MCPServer`, no `FastMCP`) que deja a Claude leer y modificar en vivo el documento abierto en InDesign 2026, vía `osascript` + `do script` (ExtendScript).

- `servidor.py`: herramientas MCP; `ejecutar_jsx()` es el puente común.
- `jsx/`: scripts ExtendScript. `comun.jsx` se antepone a todos (da `json()`); cada script recibe `ARGS` y termina en `return json(...)`.
- `ventanas.js` (JXA): VS Code a la mitad izquierda e InDesign a la derecha; pensado para un hook `SessionStart`.
- Entorno: `.venv` (`python3 -m venv .venv && .venv/bin/pip install -r requirements.txt`). Registrado en `.mcp.json`; tras cambiar herramientas hay que reiniciar la sesión de Claude.

## Forma de trabajo
- Se avanza paso a paso: cada herramienta nueva se prueba con un documento real y el usuario la da por buena antes de seguir.
- Se trabaja sobre el documento original abierto: pedir que esté guardado antes de modificar.
- Todo cambio debe poder deshacerse con un solo Cmd+Z (`UndoModes.ENTIRE_SCRIPT`).
- Cambios en varios sitios: `revisar_cambios` (el usuario los aprueba uno a uno en un diálogo de InDesign, como Buscar/Cambiar); cambios puntuales: `ejecutar_script`.
- No cerrar documentos ni lanzar scripts largos si InDesign parece colgado: preguntar antes.

## Trampas conocidas
- AppleScript: `POSIX file` dentro de `tell application "InDesign"` falla (-1708); convertir la ruta fuera del `tell`.
- ExtendScript no tiene `JSON` y no tolera `\u0000` en expresiones regulares.
- SDK `mcp`: solo los mensajes de `ToolError` llegan a Claude; cualquier otra excepción se queda en «Error executing tool». Por eso `ErrorInDesign` hereda de `ToolError`.
- Tras deshacer por script (`doc.undo()`) y reaplicar, el Cmd+Z posterior del usuario puede no redibujarse. `doc.recompose()` no basta. `oyente_deshacer.jsx` (motor persistente `indesign_mcp`) engancha Deshacer/Rehacer y fuerza el redibujado; `revisar_cambios` lo instala. Ojo: deshacer desde un script siempre redibuja al acabar el script, así que esas pruebas no reproducen el fallo.

## Probar sin el usuario
- `revisar_cambios.jsx` acepta `ARGS.auto` ("aceptar", "rechazar"…): el diálogo se abre y se cierra solo con esa decisión. Solo para pruebas; la herramienta MCP no lo expone.
- Cmd+Z equivalente: `app.menuActions.itemByID(265).invoke()` (Edición > Deshacer). No enviar pulsaciones de teclado: si el diálogo no está abierto, van a otra aplicación.
- Ver la pantalla: `screencapture -x -R1280,31,1280,1409` (InDesign en la mitad derecha).
