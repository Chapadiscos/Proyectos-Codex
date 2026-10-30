# Búsqueda inteligente Indesign App

App SwiftUI que sustituye a la paleta «Buscar con Claude» (ver README.md). De
`../Ventana Buscar con Claude en Indesign/` no se toca nada: se usa su servidor MCP en su sitio.

## Trampas
- `jsx/revision.jsx` se lee con `do script` sin garantía de UTF-8: los caracteres no ASCII de las cadenas van con `\u`.
- `arguments` de `do script` se recoge en lo alto del archivo (`ARGV`) y se pasa a la función.
- No se recompila al cambiar `revision.jsx` ni `claude/`: se leen en cada uso. El estado de la revisión vive en
  `$.global.busquedaInteligente` mientras InDesign esté abierto.
- `firmaPropia`: la selección que pone la app al mostrar un resultado (o tras cambiar) no debe proponer el ámbito
  Selección/Artículo; se vuelve al ámbito anterior o a Documento.
- Cada acción de revisión llama antes a `sincronizarTodos()`: si el usuario ha hecho Cmd+Z en InDesign, los resultados
  vuelven a pendientes.
- Probar sin el usuario: documento propio sin guardar (`app.documents.add()`), la acción `cargar` con refs de un
  `findGrep` y el resto de acciones por osascript; Cmd+Z = `app.menuActions.itemByID(265).invoke()`. Cerrar al acabar
  solo los documentos propios y sin guardar.
- Ventanita «Recorrer» (`Recorrido`): NSPanel `.nonactivatingPanel` un nivel por encima de `.floating` (si no, los
  paneles flotantes de InDesign la tapan). Sus filas son botones: una List no cambia la selección en una ventana
  que no está activa. `--recorrer` (pruebas) la abre al terminar la búsqueda.
- Cada recompilación cambia la firma local y macOS vuelve a pedir acceso al volumen DATOS: avisar al usuario.
