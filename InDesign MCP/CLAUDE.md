# InDesign MCP

Servidor MCP (Python, SDK `mcp` 2.x → `MCPServer`, no `FastMCP`) que deja a Claude leer y modificar en vivo el documento abierto en InDesign 2026, vía `osascript` + `do script` (ExtendScript).

- `servidor.py`: herramientas MCP; `ejecutar_jsx()` es el puente común.
- `jsx/`: scripts ExtendScript. `comun.jsx` se antepone a todos (da `json()`); cada script recibe `ARGS` y termina en `return json(...)`.
- Ventana «Buscar con Claude» (paleta ScriptUI): `jsx/buscador.jsx`. Se abre y cierra desde Ventana > Buscar con Claude (`jsx/menu.jsx`, instalado por el script de arranque `~/Library/Preferences/Adobe InDesign/Version 21.0/es_ES/Scripts/startup scripts/Buscar con Claude (menú).jsx`); cerrar solo la oculta y conserva los resultados. También se lanza desde el panel Scripts por `~/Library/Preferences/Adobe InDesign/Version 21.0/es_ES/Scripts/Scripts Panel/Buscar con Claude.jsx` (motor persistente `indesign_mcp`, define `INDESIGN_MCP`). Al buscar lanza `buscar.py` en segundo plano, que ejecuta el `claude` de la extensión de VS Code sin interfaz (`-p`, `--json-schema`, solo herramientas de lectura: `estado`, `consultar`, `ver_pagina`) y escribe el resultado en un JSON que la paleta recoge con una `idleTask`. Si el usuario pide un cambio, Claude lo prueba con `probar_cambio` (aplica y deshace) y lo devuelve como `cambio.aplicar`; el botón «Revisar cambios…» de la paleta ejecuta `revisar_cambios.jsx` sobre los resultados.
- `instalacion/`: copias de los dos scripts que van en las preferencias de InDesign (`~/Library/Preferences/Adobe InDesign/Version 21.0/es_ES/Scripts/`): el lanzador del panel Scripts y el script de arranque que crea Ventana > Buscar con Claude. Para reinstalar, copiarlos a «Scripts Panel» y «startup scripts» quitando el prefijo del nombre.
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
- Ver la pantalla: `screencapture -x` (InDesign ya no ocupa una posición fija).
- Las `idleTasks` de InDesign solo se disparan con InDesign en primer plano: la paleta no se actualiza hasta que el usuario vuelve a InDesign.
- `resolve(especificador)` recupera un objeto desde `o.toSpecifier()`; los especificadores de texto son por posición, valen mientras el texto no cambie.
- Para tocar la paleta abierta desde fuera: un script con `#targetengine "indesign_mcp"` accede a `$.global.buscadorClaude` (`buscar(texto)`, `ventana`, `interno`). Tras cambiar `buscador.jsx` hay que llamar a `buscadorClaude.destruir()` (cerrar solo la oculta) y volver a abrirla.
- La búsqueda usa siempre el modelo por defecto (Opus): el usuario prefirió precisión a velocidad (Sonnet con esfuerzo bajo era un 30-40 % más rápido).
- `story.characters.itemByRange(a, b)` (y su `.texts[0]`) da `contents` como objeto, no como cadena: `obj.contents.replace` falla. Pasarlo por `resolve(x.toSpecifier())` devuelve un `Text` normal, como el de `resolve(ref)`.
- Ámbitos de búsqueda: la paleta propone Selección / Artículo / Documento / Todos los documentos según `app.selection` (se recalcula en `onActivate`) y pasa a `buscar.py` el `alcance` con `ref` de la selección o de la historia; `consultar(documento=…)` trabaja sobre cualquier documento abierto.
- Búsqueda en libro: la paleta abre los capítulos que no estén abiertos con `app.open(f, false)` (sin ventana, `NEVER_INTERACT`), los lista en `buscadorClaude.abiertos` y los cierra al empezar otra búsqueda si siguen sin ventana y sin cambios. Al hacer clic en un resultado de un capítulo sin ventana, `doc.windows.add()` lo muestra. Un libro ya abierto no se puede volver a abrir con `app.open` (da «El usuario ha cancelado»): buscarlo en `app.books`.
- Deshacer con varios documentos: cada documento tiene su propio historial, así que hay un paso de deshacer por documento.
- Una paleta ScriptUI creada desde fuera (osascript `do script`, aunque sea invocando el menú) queda detrás de la ventana de InDesign al hacer clic en el documento; creada por el usuario desde el menú o el atajo, siempre queda delante. Si en una prueba hay que abrir la ventana desde fuera, al terminar llamar a `buscadorClaude.destruir()` y dejar que el usuario la abra.
- Un `TextFrame` también tiene `parentStory` e `index`: para saber si algo es texto, comprobar además `length` y que no sea `TextFrame` (`esTexto()` en buscador.jsx y probar_cambio.jsx).
