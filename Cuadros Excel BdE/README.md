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
  Publicaciones creadas: «Informe Anual» y «Memoria Supervisión» (2026-11-17), las dos con sólido 004081 (los publicados
  de la Memoria usan la misma pastilla B3D9FF); separadas por si más adelante hay diferencias.

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

- **Avisos que se ven en Excel** (petición del usuario, 2026-11-17): los avisos del motor llevan al final una marca
  invisible «⟦A5 A6⟧» o «⟦forma:FUENTES⟧»; la app la quita al mostrarlos y, si la llevan, se pueden pulsar (icono de
  diana), en «Cambios de la versión», en «Comparar con el original» y en la actividad: Excel pasa al frente y selecciona esas celdas (separadas por «;» en el Excel en castellano; si falla, «,») o esa forma en
  la hoja del cuadro, sin tocar el archivo.

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
   - Sin FUENTE del autor (1.2): se añade el marco de FUENTE de la plantilla («FUENTE: Xxxxxxxxxx.») con aviso para
     escribirla; el paso 2 lo coloca 5 mm bajo el cuadro.
   - Unidades (texto bajo la pastilla): Roboto Light 6 pt, donde las dejó el autor.
   - **FUENTE / FUENTES** según las entidades citadas (decisión del usuario, 2026-11-17): «INE y Banco de España»,
     «Encuesta…, Encuesta… y Banco de España» → FUENTES; «Banco de España, con datos del INE…» o «elaboración propia
     a partir de…» → FUENTE (lo que va tras «con datos de», «a partir de»… no cuenta; los paréntesis tampoco).
     La fuente y las notas acaban siempre en punto.
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
   - **Primera columna, como mínimo un tercio del cuadro** (decisión del usuario, 2026-11-17; los publicados 1.3,
     1.4, 1.5, 2.7 y 2.9 le dan el 31-34 %), en cuadros de cifras o de hasta 3 columnas de datos, si las demás siguen
     cabiendo. En cuadros de texto con muchas columnas (1.2) no. Se mantiene aunque el publicado del 3.3 (4 columnas
     de cifras) le diera solo el 22 % (decisión del usuario). El orden de las entidades en FUENTES no se toca.
   - **Separación pegada a la primera columna**: la columna estrecha vacía justo detrás de la primera no separa
     grupos y se oculta (ancho 0), como en el publicado del 1.5 (que la borró).
   - **Separaciones solo entre grupos** (decisión del usuario, 2026-11-17, publicado del 3.1): una columna de
     separación se queda solo si separa grupos (una cabecera combinada sobre varias columnas acaba justo antes o
     empieza justo después). Entre columnas sueltas sobra y se oculta (ancho 0), como la de la primera columna.
   - **Múltiplos de 3 pt** (decisión del usuario, 2026-11-13: «visualmente ni se aprecia»): cada columna mide un
     múltiplo de 3 pt, la medida en que coinciden el Mac (puntos enteros) y Windows (píxeles de 0,75 pt). Las de
     datos se redondean hacia arriba y la primera se queda con el resto: el cuadro mide 468 pt (retícula 468,9).
     El ancho guardado de cada columna (`ancho_comun`) da esa medida exacta en el Mac y, si la fuente «Normal» lo
     permite, también en Windows.
   - **Cabecera de datos muy alta** (> 3 líneas; decisión del usuario, 2026-11-17): la primera columna puede ceder
     ancho (sus textos, hasta 2 líneas, o una más si ya ocupaban 2) y se queda el reparto con el cuadro más bajo;
     se busca primero la cabecera más baja y, a igualdad, el cuadro más bajo (como el TERMINADO del 3.4).
   - **Aviso de muchas columnas** (10 o más de datos, o de menos de 30 pt): valorar bajar la letra a 7 pt.
   - **Aviso de textos en celdas fuera del cuadro** dentro de la retícula (3.4: A28, restos del autor).
   - **Pendiente (Windows)**: con las fuentes «Normal» de los autores (Calibri 11, Arial 12) el Excel de Windows
     mide las columnas distinto que el de Mac (−12 % / −3,6 %). Propuesta sin hacer: «Normal» = Roboto Light 11 (6 pt
     por carácter en los dos; los múltiplos de 3 pt ya están hechos). El usuario lo comprobará en Windows antes de decidir.
   - **Cabecera de 2 líneas** (decisión del usuario, 2026-11-17, como los publicados 1.3 y 1.4; sustituye a la
     «cabecera compensada», que estrechaba las columnas de datos): las columnas de datos se quedan con todo el ancho
     y la app pone el salto de línea antes de un nexo («en», «entre», «y», «para»…, o tras «:»), si no antes de «de»,
     y entre los posibles el que deja las líneas más parejas («Cuota de Oriente Medio / en las importaciones de la
     UE (%)»). Con 3 líneas o más, Excel parte solo. Al redondear a 3 pt, la primera columna no pierde sitio.
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
   - **Formato de número sin relleno** (2026-11-17, publicado del 3.1): el relleno de los lados del formato del autor
     («0.00_m_m_m», «#,##0\ _€», «@_m_m_n») descentra las cifras; se quita («0.00», «#,##0», «@»). Los formatos de
     contabilidad («_-* …») se dejan.
   - **Salto de línea del autor en la cabecera** (publicado del 3.1): si el texto cabe en una línea, se quita
     («Peso VAB⏎2023» → «Peso VAB 2023») y se avisa; el de antes de un paréntesis se queda (publicado del 1.5).
   - **Sitio del cuadro** (decisión del usuario, 2026-11-17): las unidades, justo bajo la pastilla (0,3 mm); la
     cabecera, 4 mm bajo un cuadro de unidades de 5 mm (2,5 mm más por línea de más) o, sin unidades, 4 mm bajo
     la pastilla (1.4: fila 2 = 51,25 pt; TERMINADO 51). Lo da la fila de encima del cuadro; si las de arriba ya
     ocupan más, se encogen. Todo lo de encima del cuadro se vuelve a anclar en su sitio (no se mueve).
   - **FUENTES, 5 mm bajo el final del cuadro**, anclada a su fila.
   - «<34» → «< 34»: espacio tras «<», «>», «≤», «≥» pegados a cifra o letra (TERMINADO 1.4), y también antes
     («ROA< 0» → «ROA < 0», publicado del 3.2).
   - Barra entre expresiones de varias palabras, con espacios: «Deuda total/Activo total» → «Deuda total / Activo
     total» (publicado del 3.2, corrección ortotipográfica con aviso). Entre palabras sueltas, pegada («Deuda/PIB»,
     «mb/d», «2023/2024»).
   - Asteriscos de significatividad pegados a la cifra: «0,237 ***» → «0,237***» (publicado del 3.3).
   - Un símbolo griego al principio («Δ Acum. intangibles») no cuenta como primera palabra para las minúsculas.
   - Celdas con formato en el texto (superíndices como el de «R²», cursivas): no se reescriben para no perder el
     formato; si solo cambian los espacios de los lados, se dejan; la sangría se añade al primer trozo; otras
     correcciones se avisan para hacerlas a mano (fallo visto en el 3.3: «R²» quedaba «R2»).
   - **Primera columna con mayúsculas de título** («Industria Manufacturera»): no se cambia (puede haber nombres de
     entidades); aviso con la propuesta («Industria manufacturera») para revisarla (decisión del usuario, 2026-11-17).
     La lista de nombres propios incluye provincias, comunidades e instituciones (Banco, Central, Europeo…); tras un
     punto que cierra frase se respeta la mayúscula, tras una abreviatura («Act.») no.
   - «7%» → «7 %» en las celdas (espacio que no parte línea; TERMINADO 1.2), como en FUENTES.
   - **Correcciones ortotipográficas** (decisión del usuario, 2026-11-17), en celdas, título, unidades y FUENTES,
     con aviso en rojo para revisarlas: trimestres como en Gráficos (es «I TR 2024», en «Q1 2024»), «EE.UU.» →
     «EEUU», «Mb/d» → «mb/d», años abreviados «1973–74» → «1973–1974» y, en la cabecera, minúscula en las palabras
     con mayúscula de título; nombres oficiales de provincias (Vizcaya → Bizkaia, Guipúzcoa → Gipuzkoa, Álava →
     Araba/Álava, Orense → Ourense, Gerona → Girona, Lérida → Lleida, La Coruña → A Coruña, Baleares → Illes
     Balears) solo en celdas que son la provincia sola (no en «Banco Bilbao Vizcaya Argentaria») y, en la cabecera,
     minúscula en las palabras
     con mayúscula de título (salvo la primera, siglas, nombres propios y lo que va pegado a ellos: «Oriente Medio»,
     «ICO Crecimiento»).
   - Hijos de un título de bloque, sangrados aunque el autor no los sangrara (si hay otros hijos sangrados).
   - Textos de la cabecera repetidos en filas de datos (1.3), borrados con aviso.
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
   - Primera columna: fondo blanco matiz 1 (#F2F2F2) con líneas blancas entre todas las filas, también entre
     sangrados (como el TERMINADO, decisión del usuario; la guía decía que no).
   - Títulos de bloque (concepto sin sangría y sin datos en las demás columnas): blanco matiz 2 en la primera
     columna. Subtotales («Total …»): blanco matiz 2 en toda la fila.
   - Fila «España» («Spain») en una lista de provincias o países (sin sangría y con datos): toda la fila en blanco
     matiz 2 con líneas blancas (publicados 2.7 y 2.9, Ejemplos 2.3); si es un concepto sangrado de un bloque (1.4),
     no.
   - Fila TOTAL: blanco matiz 2, o matiz 5 con el texto en blanco si el matiz 2 ya lo usan bloques o subtotales
     (Ejemplos 1.4 y A2.2); sin hueco en las columnas de separación. Columna TOTAL (cabecera «TOTAL»): blanco
     matiz 2 con línea blanca a la izquierda y entre filas (Ejemplos 4.2 y A4.6).
   - **Filas de suma** (decisión del usuario, 2026-11-17, publicado Memoria 2.1): si las cifras de una fila son la SUMA
     de las filas de justo debajo («Entidades de crédito» = SUM(E7:E12)), toda la fila va en Roboto Medium, como un
     subtotal, sin fondo. Se avisa con diana.
   - **Columnas ocultas del autor** (Memoria 2.1: textos de traducción en A-C que la columna D enseña con una
     fórmula; «Descuadre» en G): ni se miden para el alto de fila ni se les cambia el formato.
   - **«Cuadro N» y unidades en celdas** encima del cuadro (Memoria 2.1, 3.2, 4.2): el paso 1 los pasa a cuadros de
     texto como en el Informe Anual (rótulo con el marco de la plantilla; unidades en Roboto Light 6 pt, colocadas
     como las demás) y vacía la celda. Solo celdas solas en su fila, por encima de la primera fila con dos textos,
     y, las unidades, si empiezan como unas unidades («Datos a…», «Millones…», «%»…). Al comparar con el
     original salen como «pasados de celdas a cuadros de texto», no como datos que faltan.
   - Al comparar con el original, el formato de número sin el relleno que quita el paso 2 no cuenta como cambio.
   - Líneas y fondos sueltos del autor en celdas vacías a la derecha del cuadro, quitados (1.2, columnas I-K), y
     también encima del cuadro (filas entre la pastilla y la cabecera) y en las columnas ocultas (publicado del 3.3).
   - **Regresiones** (publicado del 3.3): la fila del coeficiente y la de su error estándar (entre paréntesis, sin
     concepto) son un solo concepto: la primera columna se combina en las dos filas y entre ellas no hay línea. Antes
     de los estadísticos («Observaciones», «R2», «R²», «Pseudo R2»…), línea oscura (blanco matiz 5).
   - Columnas de separación sin líneas ni fondo en las filas de datos (las líneas se cortan entre grupos, TERMINADO
     3.4); en la fila TOTAL, sin hueco.
   - La línea que cierra cada bloque de sangrados (gris claro, como el resto) queda por revisar con más ejemplos.
   - Paso 2: si el autor escribió la FUENTE y las notas en celdas bajo el cuadro (DO, Memoria 3.2), el cuadro
     acaba antes y se avisa para pasarlas al cuadro de texto de FUENTES.
**Herramienta «Probar letra a 7 pt»** (`letra7`, petición del usuario, 2026-11-17): rehace desde la versión del
paso 1 los pasos 2, 3 y 4 que haya hechos con la letra de las celdas a 7 pt y lo guarda como una versión nueva
(«Letra 7 pt»); las de 7,5 pt quedan detrás para volver con ⌘←. El paso 2 la propone en su aviso de muchas
columnas. En el 3.4 deja la cabecera en 60 pt, como el TERMINADO.

**Herramienta «Línea oscura sobre la selección»** (`linea_oscura`, petición del usuario, 2026-11-17, publicado
del 2.9): para separar conceptos. Se selecciona en Excel una celda de cada fila que empieza un concepto nuevo (varias
con ⌘; de cada zona cuenta su primera fila) y la app pone la línea oscura (blanco matiz 5) encima de esas filas, en
todo el ancho del cuadro salvo las separaciones, en una versión nueva («Líneas oscuras»). Exige el paso 4.

5. **Terminar**: «Comparar con el original» (`comparar`, sin crear versión: datos de todas las hojas y textos de
   las formas frente al Excel del autor; avisa en rojo de lo que falte y lista los cambios —sangrías, viñetas,
   «TOTAL», puntos, comillas—) y «Guardar como TERMINADO» («ORIGINALES» → «TERMINADOS», junto al original; borra
   copias y versiones).
