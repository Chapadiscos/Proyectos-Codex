# Búsqueda inteligente

App de Mac (SwiftUI) para buscar y cambiar en InDesign describiendo en español lo que quieres
(«números de cinco cifras sin punto de millar en el texto base», «pasa a 85 Heavy los años en 45 Book»…).
Es la ventana «Buscar con Claude» de InDesign hecha app: más visual, enseña en directo lo que hace Claude
y no instala nada en InDesign, así que sigue funcionando aunque se reinstale.

- **Buscar en**: selección, artículo, documento, todos los documentos o un libro: abre los capítulos sin ventana,
  en segundo plano, y los cierra al terminar la revisión (salvo los que tengan cambios, que quedan con ventana).
  Lo que tengas seleccionado en InDesign propone el ámbito al volver a la app.
- **Documento del disco**: en «Buscar en», elige uno o varios .indd sin abrirlos antes: la app los abre en InDesign sin
  ventana, en segundo plano. Si cambias algo, el documento pasa a tener ventana para que lo guardes; si no, se cierra
  al terminar la revisión.
- **Solo las páginas**: lo que está en la mesa de trabajo (fuera de las páginas) se omite; el texto desbordado de un
  marco que está en una página sí cuenta.
- **Actividad**: cada paso de Claude (qué consulta, qué le contesta InDesign, cómo prueba el cambio) con su tiempo.
- **Revisión**: antes y después con contexto; Cambiar (⌘Y, se queda en el resultado), Buscar/Cambiar (⇧⌘Y, cambia y
  pasa al siguiente), Buscar siguiente (⌘G, pasa sin cambiar), Omitir (⌥⌘N), Cambiar todo (salvo los dudosos),
  Cancelar (deshace todo) y Terminar (conserva). En cada documento, todos los cambios son un solo Cmd+Z.
- **Recorrer en InDesign**: doble clic en un resultado (o «Ver en InDesign») pone InDesign delante con una ventanita
  flotante encima: al pulsar en ella InDesign sigue activo y va saltando a cada resultado; también Cambiar, Omitir y
  Cambiar todo. «Volver a la app» recupera la ventana grande.
- **Búsquedas guardadas**: desplegable «★ Guardadas» (arriba a la derecha): «Guardar esta búsqueda…» (o botón derecho en
  una reciente) le pone un nombre; al elegir una se rellena la descripción y el ámbito (documento, libro…) se elige cada
  vez. Cada una lleva a su derecha los botones Editar (✎) y Quitar (🗑).
- **Búsquedas recientes** en la barra lateral, para repetirlas.

Cómo está hecha:
- `app/BusquedaInteligente.swift`: la app. Compilar con `app/compilar_app.sh` → `Búsqueda inteligente.app` (no va a git).
- `jsx/revision.jsx`: la revisión dentro de InDesign (motor persistente `busqueda_inteligente`); la app lo ejecuta
  con `do script` en cada acción.
- `claude/instrucciones.md` y `claude/esquema.json`: lo que se le pide a Claude (copiado de `buscar.py`); se
  pueden editar sin recompilar.
- `servidor/`: el servidor MCP con el que busca Claude Code (el de la extensión de VS Code, sin interfaz). Es copia
  del de `../Ventana Buscar con Claude en Indesign/` (que no se toca) con solo las herramientas de la búsqueda, y
  admite que todos los documentos estén sin ventana (capítulos de un libro). Usa el `.venv` de esa carpeta.
  Otras rutas: `defaults write es.estudioencuadre.busqueda-inteligente motor "<carpeta>"` o `… claude "<ejecutable>"`.
- La primera vez macOS pide acceso al volumen DATOS y permiso para controlar InDesign (Automatización).
- Pruebas: `open -n "Búsqueda inteligente.app" --args --buscar "<descripción>"` lanza la búsqueda al abrir.
