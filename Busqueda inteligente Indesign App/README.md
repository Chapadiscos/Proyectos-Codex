# Búsqueda inteligente

App de Mac (SwiftUI) para buscar y cambiar en InDesign describiendo en español lo que quieres
(«números de cinco cifras sin punto de millar en el texto base», «pasa a 85 Heavy los años en 45 Book»…).
Es la ventana «Buscar con Claude» de InDesign hecha app: más visual, enseña en directo lo que hace Claude
y no instala nada en InDesign, así que sigue funcionando aunque se reinstale.

- **Buscar en**: selección, artículo, documento, todos los documentos o un libro (abre los capítulos sin ventana).
  Lo que tengas seleccionado en InDesign propone el ámbito al volver a la app.
- **Actividad**: cada paso de Claude (qué consulta, qué le contesta InDesign, cómo prueba el cambio) con su tiempo.
- **Revisión**: antes y después con contexto; Cambiar (⌘Y), Omitir (⌥⌘N), Cambiar todo (salvo los dudosos),
  Cancelar (deshace todo) y Terminar (conserva). En cada documento, todos los cambios son un solo Cmd+Z.
- **Recorrer en InDesign**: doble clic en un resultado (o «Ver en InDesign») pone InDesign delante con una ventanita
  flotante encima: al pulsar en ella InDesign sigue activo y va saltando a cada resultado; también Cambiar, Omitir y
  Cambiar todo. «Volver a la app» recupera la ventana grande.
- **Búsquedas recientes** en la barra lateral, para repetirlas.

Cómo está hecha:
- `app/BusquedaInteligente.swift`: la app. Compilar con `app/compilar_app.sh` → `Búsqueda inteligente.app` (no va a git).
- `jsx/revision.jsx`: la revisión dentro de InDesign (motor persistente `busqueda_inteligente`); la app lo ejecuta
  con `do script` en cada acción.
- `claude/instrucciones.md` y `claude/esquema.json`: lo que se le pide a Claude (copiado de `buscar.py`); se
  pueden editar sin recompilar.
- Claude Code (el de la extensión de VS Code, sin interfaz) busca con el servidor MCP de
  `../Ventana Buscar con Claude en Indesign/` (`servidor.py` y su `.venv`), que se usa en su sitio sin modificarlo.
  Otras rutas: `defaults write es.estudioencuadre.busqueda-inteligente motor "<carpeta>"` o `… claude "<ejecutable>"`.
- La primera vez macOS pide acceso al volumen DATOS y permiso para controlar InDesign (Automatización).
- Pruebas: `open -n "Búsqueda inteligente.app" --args --buscar "<descripción>"` lanza la búsqueda al abrir.
