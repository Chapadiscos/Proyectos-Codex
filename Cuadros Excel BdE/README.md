# Cuadros Excel BdE

App de Mac (SwiftUI) que maqueta, paso a paso, el Excel del **cuadro** que entrega el autor. Es una réplica de
«Gráficos Excel BdE» (misma ventana, mismas versiones adelante y atrás, Excel al lado), pero para cuadros:
tablas hechas en celdas, con la pastilla, «Cuadro N», el título, las unidades y la FUENTE como formas encima.

- Normas: `Resumen cuadros.pdf` (págs. 21-22 de la guía) y `Ejemplos cuadros.pdf` (con notas en rojo).
- Ejemplos: «Cuadros Excel ORIGINALES/TERMINADOS» (IA2025, Memoria de Supervisión) y «Cuadros Excel DO
  ORIGINALES/TERMINADOS» (Documentos Ocasionales; el TERMINADO lleva todos los cuadros del DO en un libro).
- Retícula, pastillas y marcos: hojas «Cuadro» y «Cuadro_Horizontal» de
  `SdE_Reticulas_Publicaciones_ImagenNueva2024_Roboto.xlsx` (copia de la de «Gráficos Excel BdE»).
- Compilar: `app/compilar_app.sh` (firma local con el identificador `es.estudioencuadre.cuadros-excel`). Como es
  una app nueva, macOS pide otra vez los permisos de **Automatización** (Excel) y **Accesibilidad**.
- La app se usa desde **Aplicaciones**; encuentra el motor por su ajuste
  `defaults write es.estudioencuadre.cuadros-excel motor "/Volumes/DATOS/Proyectos Codex/Cuadros Excel BdE/motor"`
  (sin él, lo busca junto a la app). `compilar_app.sh` también pone al día la copia de Aplicaciones si existe.
- Motor: `motor/maquetar_cuadros.py` (JSON por la salida estándar). Publicaciones en `motor/publicaciones.json`.
- **Color de la publicación**: cada publicación guarda un solo color, el **sólido**; de él salen los matices como en
  Excel (Resumen cuadros, pág. 22): matiz 1-3 un 80/60/40 % más claros y 4-5 un 25/50 % más oscuros. La
  **pastilla es el matiz 1** (comprobado con el archivo de retículas: 004081 → B3D9FF del Informe Anual, F06800 →
  FFE0C9 de los DO, A32938 → F3CED3 de las bianuales). La paleta de Excel queda en segundo plano (opcional).
  Publicación creada: «Informe Anual», sólido 004081.

## Cómo trabaja

- Se trabaja sobre una **copia**: del original `X.xlsx` sale `X maquetado.xlsx`, y cada paso deja su versión en
  `X maquetado (pasos)/` (`00 Copia exacta.xlsx`, `01 …`). Las dos copias de trabajo que se alternan en Excel,
  el «Reiniciar», el «No actualizar» vínculos y el Organizador visual funcionan igual que en Gráficos (ver su
  README).
- **Hoja del cuadro**: la primera hoja visible con el rótulo «Cuadro N» en sus formas; si ninguna lo tiene, la
  primera visible (los autores la llaman «Cuadro datos», «Cua», «C1», «Cuadro 2»…). Excel se abre en ella.
- Idioma: inglés si el nombre lleva «Ing» (`CIng_…`, `…_Ing`) o el rótulo es «Table N»; si no, castellano.
- Terminar: guarda «… TERMINADO.xlsx» («ORIGINALES» → «TERMINADOS») junto al original y borra copias y versiones.
- **Reiniciar**: cierra la copia en Excel sin guardar, borra todo lo generado (las dos copias de trabajo, la carpeta
  «(pasos)» entera y los bloqueos «~$» de Excel) y empieza de nuevo desde el original, como la primera vez.

## Pasos (se construyen y aprueban uno a uno)

0. **App y copia exacta** (hecho, 2026-11-13).
1. **Retícula, pastilla y textos** (`paso1`, en pruebas desde 2026-11-13):
   - Borra la retícula del autor (rectángulos o grupos de rectángulos sin texto ni relleno, de página entera,
     también si está apartada o es la antigua) y su pastilla (rectángulo de color sin texto en A1); pone en A1 la
     retícula «Grupo 20» y la pastilla «Rectángulo 16» de la hoja «Cuadro», en el matiz 1 de la publicación.
   - «Cuadro N» (Roboto Regular 7 pt) y título (Roboto Medium 8,5 pt) toman el marco de la plantilla. Si van en
     el mismo cuadro, se separan. Al final de cada párrafo del título, las letras entre paréntesis («(a)»,
     «(a) (b)», «(a, b)») y «(cont.)» / «(cont'd)» van en Roboto Regular, como en Gráficos. Con un título de
     2-3 líneas, el marco del título y la pastilla crecen un interlineado (3,5 mm) por línea y las unidades bajan.
   - Unidades (texto bajo la pastilla): Roboto Light 6 pt, donde las dejó el autor.
   - FUENTES: reglas de Gráficos (Roboto Light 7 pt, rótulo en Medium, notas con letra —también «a.», «a)»,
     «(a)» y «a» + espacio + mayúscula— con sangría de 8,5 pt, línea en blanco, comillas, «%»), punto final en
     la fuente, en el ancho de la plantilla desde la columna A y anclada a su fila (sigue al cuadro).
   - Todo en negro. Lo que queda fuera de la retícula no se toca. Avisa si el rótulo o el título van en mayúsculas.
   - Probado con los 24 originales (XML válido en todos). Caso especial pendiente: el 1.6 (cuadro a la derecha
     de un gráfico, fuera de la retícula).
2. **Celdas** (`paso2`, en pruebas desde 2026-11-13; exige el paso 1):
   - El cuadro: el bloque de celdas con texto, borde o relleno unidas entre sí que empieza en la columna más a la
     izquierda dentro de la retícula; salta columnas estrechas vacías (< 3 de ancho, separaciones del autor) y se
     recortan los bordes sin texto. Lo que queda aparte (datos de un gráfico, 1.4 E:H) no se toca.
   - Las fuentes de Office (Calibri, Aptos) se miden desde Excel.app/Contents/Resources/DFonts.
   - **Anchos de columna** (petición del usuario, 2026-11-13): el cuadro llega justo al borde derecho de la
     retícula (165,4 mm). Manda la primera columna: el ancho de su texto más largo en una línea (con la sangría y
     1,5 pt de holgura). Las demás, iguales si se puede; si no caben (su cifra o su palabra más larga), la
     primera cede hasta lo que pida su palabra más larga, y si aun así no caben, aviso (la guía deja bajar la letra
     hasta 6 pt). Columnas de textos largos (1.2 G-H): si con anchos iguales sus filas salen muy altas, ganan ancho
     de las que tienen holgura. Separaciones estrechas (< 3) y columnas ocultas, sin tocar. Las cifras se miden
     como las enseña Excel (formato de número, en castellano).
   - **Separaciones de la cabecera** (columnas estrechas sin texto): 3 pt (≈ 1,06 mm; Memoria 3.4 TERMINADO, que
     Excel enseña como «0,25» de ancho en caracteres). Ancho guardado elegido para que mida 3 pt en Mac y 4 px en
     Windows (`ancho_comun`; Windows calculado, no medido).
   - **Múltiplos de 3 pt** (decisión del usuario, 2026-11-13: «visualmente ni se aprecia»): cada columna mide un
     múltiplo de 3 pt, la medida en que coinciden el Mac (puntos enteros) y Windows (píxeles de 0,75 pt). Las de
     datos se redondean hacia arriba y la primera se queda con el resto: el cuadro mide 468 pt (retícula 468,9).
     El ancho guardado de cada columna (`ancho_comun`) da esa medida exacta en el Mac y, si la fuente «Normal» lo
     permite, también en Windows.
   - **Pendiente (Windows)**: con las fuentes «Normal» de los autores (Calibri 11, Arial 12) el Excel de Windows
     mide las columnas distinto que el de Mac (−12 % / −3,6 %). Propuesta sin hacer: «Normal» = Roboto Light 11 (6 pt
     por carácter en los dos; los múltiplos de 3 pt ya están hechos). El usuario lo comprobará en Windows antes de decidir.
   - **Cabecera compensada** (petición del usuario, 1.4): si los textos de cabecera de las columnas de datos ocupan
     varias líneas, esas columnas se estrechan hasta el ancho mínimo con las mismas líneas (líneas parejas: «Incremento
     de la tasa de / ahorro entre 2017 y 2024») y la primera columna se queda con el resto. Solo si ninguna celda
     (cabecera o datos) gana líneas.
   - **Ancho de columna en el Excel de Mac** (medido en Excel, 2026-11-13): puntos = ancho guardado × el dígito
     más ancho de la fuente por defecto del libro en puntos enteros (Calibri 11 y Aptos Narrow 12 → 6, Arial 12 →
     7), redondeado. No la fórmula de Windows (píxeles a 96 ppp), que dejaba el cuadro un 14 % más ancho que la
     retícula. El redondeo a puntos lo absorbe la primera columna: el cuadro mide 469 pt (retícula 468,9).
   - **Texto en las celdas del Excel de Mac** (medido en Excel, 2026-11-13): lo dibuja un 5 % más ancho que la suma
     de avances de la Roboto Light y deja unos 5 pt de margen en la celda («Régimen de tenencia de la vivienda»,
     114,7 pt, cabe desde 125 pt de columna; «País de nacimiento», 62,4 pt, desde 70). Todas las medidas de texto
     del paso 2 llevan ese factor (`ESCALA_TEXTO_EXCEL`).
   - Cabecera: la primera fila con texto y las de debajo hasta la primera fila con cifra y concepto (así los años
     de cabecera no cuentan como datos), sin títulos de bloque, más lo que abarquen sus celdas combinadas.
   - Letra Roboto Light 7,5 pt; lo que el autor puso en negrita (o en una variante gruesa), en **Roboto Medium**
     sin la negrita de Excel, como los TERMINADOS (TOTAL de Memoria 3.4, 4.1, 3.1…). Cursiva, subrayado, índices y
     color se conservan; también en los textos enriquecidos. Cada celda se mide con su variante. Formatos nuevos en styles.xml; los del autor no se tocan.
   - Alto de fila por líneas (medidas con la Roboto Light): 14 / 28 / 40 / 50 y 10 pt más por línea a partir de
     la 5.ª (confirmado). Filas vacías del autor, sin tocar.
   - Alineación: cabecera, la primera a la izquierda y las demás al centro; primera columna a la izquierda;
     cifras al centro; textos de datos al centro, o a la izquierda en columnas de textos largos (media > 80 —umbral en pruebas—
     caracteres, como G y H del 1.2); en altura al centro, o arriba si la fila lleva textos de 2 o más líneas
     en las columnas de datos (si solo la primera columna ocupa varias líneas, al centro, como el 1.5).
   - Primera columna: sangrías (de Excel o con espacios) → 4, 8 o 12 espacios por nivel; con varias líneas, la
     sangría se repite en cada una (saltos manuales, como el TERMINADO del 1.5); sin viñetas «- »; «Total» → «TOTAL» (también en la cabecera).
3. **Cabeceras** (`paso3`, en pruebas desde 2026-11-13; exige el paso 2, que deja en el estado dónde está el
   cuadro y su cabecera: `cuadro` en estado.json):
   - Fondo con los matices del color de la publicación por nivel, contando desde la fila de abajo: cabecera 1
     matiz 1 (la pastilla), 2 matiz 2, 3 matiz 3 y 4 sólido; las dos últimas con el texto en blanco. Solo cuentan
     como niveles las filas con textos de cabecera en las columnas de datos (no una celda combinada de la primera
     columna, como las unidades de Memoria 4.1). Las celdas combinadas en vertical toman el nivel de su fila de
     abajo (F3:F4 del 1.2, matiz 1), como los TERMINADOS.
   - Líneas blancas finas a los lados de cada celda y entre niveles.
   - La celda de la primera columna, solo si lleva texto («Evento», 1.2); si no, esquina en blanco.
   - Columnas estrechas de separación (< 3), sin relleno: hueco blanco entre grupos.
   - Formatos nuevos (rellenos, bordes y fuentes con color) en styles.xml; los del autor no se tocan.
4. **Líneas y fondos** (`paso4`, en pruebas desde 2026-11-13; exige el paso 3):
   - Solo líneas horizontales finas: blanco matiz 2 (#D9D9D9) entre filas; la última fila, sin línea.
   - Línea oscura (blanco matiz 5, #808080) **siempre encima de la fila TOTAL** (decisión del usuario) y en ningún
     otro sitio: el detalle recuerda en rojo que, si hay que separar otros conceptos importantes, se añade a mano.
   - Primera columna: fondo blanco matiz 1 (#F2F2F2) con líneas blancas; sin línea entre conceptos sangrados.
   - Títulos de bloque (concepto sin sangría y sin datos en las demás columnas): blanco matiz 2 en la primera
     columna. Subtotales («Total …»): blanco matiz 2 en toda la fila.
   - Fila TOTAL: blanco matiz 2, o matiz 5 con el texto en blanco si el matiz 2 ya lo usan bloques o subtotales
     (Ejemplos 1.4 y A2.2); sin hueco en las columnas de separación. Columna TOTAL (cabecera «TOTAL»): blanco
     matiz 2 con línea blanca a la izquierda y entre filas (Ejemplos 4.2 y A4.6).
   - La línea que cierra cada bloque de sangrados (gris claro, como el resto) queda por revisar con más ejemplos.
   - Paso 2: si el autor escribió la FUENTE y las notas en celdas bajo el cuadro (DO, Memoria 3.2), el cuadro
     acaba antes y se avisa para pasarlas al cuadro de texto de FUENTES.
5. **Terminar** (comparar con el original y guardar) — guardar hecho; comparar pendiente.
