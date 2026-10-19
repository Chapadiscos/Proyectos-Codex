# Correcciones ortotipográficas

Herramienta para revisar PDFs de forma editorial antes de corregirlos en InDesign.

## Uso

1. Deja el/los PDF a revisar directamente en esta carpeta (o en `entrada/`, si prefieres mantenerlo ordenado).
2. Ejecuta, sin argumentos, para procesar todos los PDF encontrados:

   ```
   python3 revisar.py
   ```

   O indica uno o varios archivos concretos:

   ```
   python3 revisar.py "mi_libro.pdf"
   ```

3. En `salida/` se generan dos archivos por PDF:
   - `<nombre>_comentarios.pdf`: copia del original con resaltados y comentarios
     (uno por incidencia). Ábrelo en Adobe Acrobat y usa **Archivo > Importar
     datos > Comentarios de un archivo PDF** en InDesign, o revisa los
     comentarios directamente en Acrobat.
   - `<nombre>_informe.csv`: listado de todas las incidencias (página,
     categoría, texto, comentario) para revisión rápida en una hoja de cálculo.

Usa `--sin-gramatica` para omitir la revisión ortográfica/gramatical (más rápido,
útil para pruebas).

## Qué revisa

- **Unificación de criterios**: alterna "Fig./Figura", "Tab./Tabla", "Gráf./Gráfico"
  y marca las apariciones minoritarias respecto a la forma dominante en el documento.
- **Celdas de tabla**: detecta tablas (por estructura visual) y marca las celdas
  que terminan en punto.
- **Ladillos**: heurística sobre líneas cortas y aisladas en negrita que terminan
  en punto (revisar siempre visualmente, es una heurística aproximada).
- **Mayúsculas en títulos**: agrupa títulos/encabezados por tamaño y estilo de
  fuente y marca los que no siguen el patrón de caja (mayúsculas/versalitas/
  minúsculas) dominante de su mismo nivel.
- **Formato numérico**: detecta mezcla de separador de miles (punto vs. coma) y
  de separador decimal (punto vs. coma) dentro del mismo documento.
- **Fechas**: detecta mezcla de formatos (dd/mm/aaaa, dd-mm-aaaa, "dd de mes de aaaa").
- **Ortografía y gramática**: usa LanguageTool en español (motor local, sin enviar
  el texto a internet) para detectar errores ortográficos y gramaticales.

## Notas técnicas

- `tools/jre/`: contiene un JRE portable (Eclipse Temurin 17) para poder ejecutar
  LanguageTool sin depender de una instalación de Java en el sistema. No requiere
  configuración adicional; el script lo detecta automáticamente.
- La primera vez que se ejecuta con revisión gramatical, `language_tool_python`
  descarga el motor de LanguageTool (~260 MB) y lo cachea en
  `~/.cache/language_tool_python/` para usos posteriores.
- Las heurísticas de ladillos y de detección de tablas están pensadas para
  maquetaciones editoriales típicas, pero conviene revisar visualmente los
  falsos positivos/negativos con los primeros PDFs reales y ajustar el script
  (`revisar.py`) según el estilo concreto del libro.
