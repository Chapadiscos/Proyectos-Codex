# Búsqueda inteligente Indesign App

App SwiftUI que sustituye a la paleta «Buscar con Claude» (ver README.md). De
`../Ventana Buscar con Claude en Indesign/` no se toca nada: `servidor/` es copia de su servidor MCP (solo
estado, consultar, ver_pagina y probar_cambio) y solo se usa su `.venv`.

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
  Otras opciones de prueba: `--ambito libro|disco`, `--archivo <.indd>`.
- Cada recompilación cambia la firma local y macOS vuelve a pedir acceso al volumen DATOS: avisar al usuario.
- Con todos los documentos sin ventana (búsqueda en libro) `app.activeDocument` falla con «No hay documentos abiertos»:
  `servidor/jsx/estado.jsx` y `consultar.jsx` lo evitan (el original no, y Claude creía que no había nada abierto).
- `NSRunningApplication` dentro de la app a veces dice que InDesign no está abierto aunque lo esté: se comprueba en el
  propio AppleScript de `enInDesign` (`application id … is running`).
- Registro de las llamadas a InDesign: `~/Library/Logs/Busqueda inteligente.log`.
- Nombres de archivo con tildes: macOS los da descompuestos («i» + U+0301) y Claude los escribe compuestos («í»).
  `servidor/jsx/consultar.jsx` compara los nombres de documento sin tildes ni mayúsculas (`plano`); si no, Claude
  no encuentra un documento abierto desde el disco aunque el nombre se vea igual.
- Mesa de trabajo: las búsquedas solo cuentan lo que está en las páginas (lo pide `claude/instrucciones.md`) y
  `revision.jsx` descarta en `cargar` lo que aún llegue de la mesa (`enMesaDeTrabajo`, devuelve `omitidosMesa`).
  Para probar `revision.jsx` sin pisar la revisión del usuario: copia con otro `#targetengine`.
