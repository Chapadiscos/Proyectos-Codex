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
- Terminar («Guardar como EXCEL»): guarda «… EXCEL.xlsx» («ORIGINALES»/«ORIGINAL» → «EXCEL»; antes «TERMINADOS»)
  junto al original, lo deja abierto en Excel en lugar de la copia de trabajo y borra copias y versiones (petición
  del usuario, 2026-11-18). Lo abre como desde el Finder («open -a»), igual que las copias de trabajo, para que
  Excel no pida «Conceder acceso».
- **Reiniciar**: cierra la copia en Excel sin guardar, borra todo lo generado (las dos copias de trabajo, la carpeta
  «(pasos)» entera y los bloqueos «~$» de Excel) y empieza de nuevo desde el original, como la primera vez.

- **Avisos que se ven en Excel** (petición del usuario, 2026-11-17): los avisos del motor llevan al final una marca
  invisible «⟦A5 A6⟧» o «⟦forma:FUENTES⟧»; la app la quita al mostrarlos y, si la llevan, se pueden pulsar (icono de
  diana), en «Cambios de la versión», en «Comparar con el original» y en la actividad: Excel pasa al frente y selecciona esas celdas (separadas por «;» en el Excel en castellano; si falla, «,») o esa forma en
  la hoja del cuadro, sin tocar el archivo.
- Los avisos y cambios con varias entradas («…, revísalas: B7 «…» → «…»; A5 «…» → «…»», «Cambio de cifras en
  «C1»: B9 «96» → «84», B10 …») se enseñan con su encabezado y, debajo, una entrada por línea (`partirLista`,
  petición del usuario, 2026-11-18): se parte por «; » o por «, » antes de una celda, nunca dentro de «…», ⟪…⟫ ni
  paréntesis; sin encabezado claro o con una sola entrada, de corrido.

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
   - **«Cuadro» siempre así**, en todas las publicaciones (decisión del usuario, 2026-11-17, Memoria 3.2): «CUADRO
     3.2» o «cuadro 3.2» → «Cuadro 3.2» (en inglés, «Table»), sin aviso.
   - **FUENTE y notas escritas en celdas bajo el cuadro** (Memoria 3.2, DO): la primera celda sola en su fila que
     empieza por FUENTE/FUENTES/NOTA, por debajo de la última fila con dos o más textos, y las celdas solas que la
     siguen (hasta dos filas vacías seguidas o una fila con varios textos) pasan, un párrafo por celda, al cuadro de
     texto de FUENTES de la plantilla, que se maqueta con sus reglas; las celdas se vacían (petición del usuario,
     2026-11-17). La comparación las da por «pasadas de celdas a cuadros de texto», no por perdidas.
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
   - Todo en negro. Lo que queda fuera de la retícula no se toca.
   - **Título en mayúsculas**: aviso con la propuesta en minúsculas (primera palabra, siglas, romanos y nombres
     propios con mayúscula; las palabras de instituciones y lugares —«Banco», «Central», «Comunidad»…— solo en
     cadena: «Banco de España», «Banco Central Europeo») y botón «Aplicar» (ver más abajo).
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
     sangría se repite en cada una (saltos manuales, como el TERMINADO del 1.5); sin viñetas «- »; «Total» → «TOTAL» en la primera columna (fondo gris); en la cabecera, sobre el color de la
     publicación, «Total» en minúscula («TOTAL» → «Total», decisión del usuario, 2026-11-17, Memoria 3.1).
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
   - **Unidades en la esquina de la cabecera** (Memoria 4.1: «Datos a 31 de diciembre» en A5:A9, con filas ocultas):
     Roboto Light 6 pt, arriba a la izquierda y sin relleno (el paso 3 no la pinta), como el publicado (petición del
     usuario, 2026-11-18).
   - **Notas del autor pegadas al cuadro** (Memoria 4.1 E16 «CAMBIADOS LOS NOMBRES», 4.2 K12, 6.1 F6): una columna del
     borde derecho con un solo texto y sin cifras no es del cuadro; el paso 2 avisa de ella (textos fuera del cuadro
     «o pegados a él») para borrarla (petición del usuario, 2026-11-18).
   - **Fila TOTAL entera en Roboto Medium** (texto y cifras), en todas las publicaciones (decisión del usuario,
     2026-11-17: así todos los Memoria publicados).
   - **Toda la letra de las celdas en negro**: el color del autor no se queda (cifras grises del Memoria 3.2
     publicado, caso aislado); en los textos con formato, los trozos toman el color de la celda. Solo las cabeceras
     llevan otro color, el que les pone el paso 3 (decisión del usuario, 2026-11-17).
4. **Líneas y fondos** (`paso4`, en pruebas desde 2026-11-13; exige el paso 3):
   - Solo líneas horizontales finas: blanco matiz 2 (#D9D9D9) entre filas; la última fila, sin línea.
   - **La fila TOTAL no lleva línea oscura encima**, en ninguna publicación (decisión del usuario, 2026-11-17,
     publicado Memoria 3.1; antes iba siempre): entre la fila de encima y la TOTAL, línea blanca. La línea oscura
     solo separa conceptos importantes, a mano con «Línea oscura sobre la selección», y los estadísticos de las
     regresiones. Sin recordatorio en los avisos: por definición nunca va (decisión del usuario, 2026-11-17).
   - Primera columna: fondo blanco matiz 1 (#F2F2F2) con líneas blancas entre todas las filas, también entre
     sangrados (como el TERMINADO, decisión del usuario; la guía decía que no).
   - Títulos de bloque (concepto sin sangría y sin datos en las demás columnas): blanco matiz 2 en la primera
     columna. Subtotales («Total …»): blanco matiz 2 en toda la fila.
   - Fila «España» («Spain») en una lista de provincias o países (sin sangría y con datos): toda la fila en blanco
     matiz 2 con líneas blancas (publicados 2.7 y 2.9, Ejemplos 2.3); si es un concepto sangrado de un bloque (1.4),
     no.
   - Fila TOTAL: blanco matiz 2, o matiz 5 con el texto en blanco si el matiz 2 ya lo usan bloques o subtotales
     (Ejemplos 1.4 y A2.2); sin hueco en las columnas de separación. Columna TOTAL: **sin fondo** (decisión del
     usuario, 2026-11-17, Memoria 3.1: su cabecera va en el color de la publicación; antes, blanco matiz 2).
   - **Conceptos de nivel intermedio** (decisión del usuario, 2026-11-17, Memoria 3.1): los sangrados que tienen otros
     más sangrados debajo («A entidades de crédito españolas» → «Lideradas por…») llevan su texto (solo la primera
     columna) en Roboto Medium. Los de primer nivel (sin sangría) no: así los publicados 1.5 y Memoria 3.2 y 4.2.
   - **Filas de suma** (decisión del usuario, 2026-11-17, publicado Memoria 2.1): si las cifras de una fila son la SUMA
     de las filas de justo debajo («Entidades de crédito» = SUM(E7:E12)), toda la fila va en Roboto Medium, como un
     subtotal, sin fondo. Se avisa con diana.
   - **Ajustes por publicación** (en `publicaciones.json`, se conservan al editar la publicación en la app):
     `cabecera_letra_blanca`: niveles de cabecera con el texto en blanco (Memoria Supervisión: `[2]`, el nivel 2 sobre
     el matiz 2, publicados 3.1 y 3.4; en el Informe Anual va en negro).
     Documentos Ocasionales (color F06800, pastilla y cabecera #FFE0C9; publicados en «Cuadros Excel DO TERMINADOS»,
     2026-11-18), con sus cuadros de texto:
     - `cuadros_de_texto`: en los cuadros sin cifras en los datos, la primera columna a su medida (entre un octavo y un
       tercio del cuadro), las columnas cortas a la medida de su texto en una línea y las de descripciones, el resto;
       si todo cabe en una línea, lo que sobra va a las de datos (DO 05: 60/408 pt frente a 87/420; DO 09:
       63/69/75/261 frente a 57/109/109/231);
     - `texto_izquierda`: media de caracteres desde la que una columna de textos va a la izquierda (30; por defecto
       80): «Percepción de un solo color…» a la izquierda y «Relajación, concentración» al centro;
     - `centrado_en_altura`: también las filas de varias líneas, centradas en altura (en el Informe Anual, arriba).
     - `bloques_con_apartados`: el título de bloque (sin sangría ni datos) lleva el fondo de la primera columna
       (#F2F2F2, no el matiz 2), sin línea con su primer apartado sangrado; encima de cada bloque salvo el primero,
       línea oscura (#808080); la fila vacía que el autor dejaba antes de un bloque se oculta (publicados
       DO26XX_01, 03 y 04); el TOTAL justo bajo un título de bloque es su cabeza y lo que viene detrás va sangrado
       (DO26XX_04);
     - `datos_a_lo_justo` (decisión del usuario, 2026-11-19): en los cuadros con cifras, las columnas de datos iguales
       y del ancho de la cabecera más larga en una línea (o de la cifra más ancha), como mínimo 60 pt
       (`DATO_JUSTO_MINIMO`), y la primera columna el resto; si así la primera partiría sus textos, las de datos
       ceden hasta dejarla en una línea. DO26XX_03: 216/84 pt (publicado 256/83); 04: 279/63 (298/68);
       02: 228/60 (201/75);
     - `rotulo_y_titulo_en_color`: «Cuadro N» y el título, en el color de la publicación (DO: naranja F06800, como
       sus publicados; Informe Anual y Memoria, en negro). FUENTES y unidades siguen en negro.
     «LATAM/Economía Latinoamericana» (cuadros regionales sin país, 2026-11-20): color A32938, pastilla #F3CED3,
     estilo habitual (cabecera en matices, primera columna gris) y `rotulo_y_titulo_en_color`. `primera_como_datos` (decisión
     del usuario, 2026-11-20): si la primera columna, a su medida, sería más estrecha que las de datos, todas iguales
     y lo que sobra al redondear a 3 pt, a la primera (01: 72/66 pt; publicado 79/72, que se salía de la retícula).
     También `centrado_en_altura` (filas de varias líneas centradas, publicado 02), `bloques_sin_fondo` (títulos de
     bloque con el gris de la primera columna, no en matiz 2: publicados 02 y 05) y `esquina_una_fila` (con una sola
     fila de cabecera, la esquina vacía lleva su color: publicado 02; con dos o más, sin relleno: 01, 04, 05).
     `apartados_sin_linea_blanca` (petición del usuario, 2026-11-20, cuadro 02): en la primera columna, sin línea
     (ni blanca ni gris) encima de los conceptos sangrados, que son del mismo grupo; solo entre grupos.
     `titulos_bloque_desbordan` (publicado 05): en los cuadros de cifras, los títulos de bloque (sin sangría ni datos)
     no cuentan para el ancho de la primera columna: van en una línea, sin ajustar texto, y pasan por encima de las
     celdas vacías de su fila (05: primera columna 159 pt en vez de 210).
     `linea_entre_bloques` (petición del usuario, 2026-11-20, como el publicado 05): línea gris oscura #A6A6A6 (blanco
     −35 %) bajo la última fila de cada bloque, de lado a lado (también en la primera columna). Los cuadros con país
     (C_EconomiaLatinoamericana_<País>_NN, «Indicadores Macrofinancieros») son otra sección, solo con líneas.
   - **Varias tablas en la hoja** (Economía Latinoamericana 01: la trimestral publicada en A3 y la mensual del autor
     en A43): si hay más de un bloque con texto en 3 filas y 3 columnas al menos, el cuadro es el de arriba; el otro
     se oculta (filas ocultas, sin borrar nada; el publicado la quitó) si está debajo y tiene texto en 3 filas y 3
     columnas al menos; su alto pasa a la fila de debajo para que no se mueva lo que el autor dejó más abajo (01: una
     copia de la FUENTE en la fila 62 subía dentro de la retícula).
   - **Cabecera de grupo en una combinada encima de la tabla** (Economía Latinoamericana 01: B3:G3 «Tasas de variación
     interanual» sobre B4:G4): no se toma por unas unidades; es la primera fila de la cabecera.
   - **Economía Latinoamericana 05** (2026-11-21, «me refiero a esas»): `respetar_saltos_cabecera` (el salto del autor
     se queda, sin espacios alrededor: «Promedio⏎2007-2024»), `cabecera_abajo` (texto combinado en vertical desde la
     fila de los grupos, pasando por filas ocultas, se descombina y baja a la última fila de la cabecera: «Promedio»
     y «2025»; en el 04 «Expectativas…» ocupa dos filas visibles y se queda) y herramienta «Probar letra a 6 pt» (el
     mínimo de la guía; el 05 publicado va a 6 pt): 05 a 6 pt, primera 105 pt y datos iguales de 36 (publicado 132/36,
     se salía de la retícula), filas de 9 pt.
   - **Columnas con puntos o flechas dibujados** (Economía Latinoamericana 04, la escala DOVISH-NEUTRAL-HAWKISH: sin
     textos en el cuerpo y con formas encima): las de texto, a su medida en una línea; la primera, no más estrecha que
     ellas; la escala, el resto a partes iguales, redondeado hacia abajo (04: 81 / 102 ×3 / 75 pt; PDF 78 / 101 / 85).
     Sus filas, de 21 pt como mínimo (`ALTO_FILA_PUNTOS`, publicado 04).
   - **Cuadros que no caben en altura** (todas las publicaciones): si las filas suman más de lo que deja la retícula
     (pastilla, 4 mm, 5 mm y FUENTES estimada por su texto), bajan en proporción sin bajar de 1,5 veces la letra (05 a
     6 pt: 9 pt, como el publicado; Memoria 4.2 a 7,5: 11,5 pt por línea; a 6,5 cabe y no cambia).
   - **«LATAM/Indicadores Macrofinancieros»** (cuadros con país, C_EconomiaLatinoamericana_<País>_NN, 2026-11-20; ante
     la duda manda el Illustrator publicado, no el Excel): `solo_lineas` (cabecera sin fondo y en negro, línea A32938
     bajo cada texto —los grupos solo en su ancho— y bajo la última fila; entre filas, matiz 1 F3CED3 de lado a lado,
     también por las separaciones; primera columna sin fondo; entre grupos, A32938; los colores del autor en los datos
     se quedan), `cuerpo_celda` 6,5 pt, `datos_cada_uno_a_lo_justo` (cada columna de datos a su cabecera en una línea
     o su cifra; la primera, el resto: Arg_03 159/45/30 pt, publicado 170/41/32-35), centrado en altura.
   - **Bloque de arriba** (`bloque_arriba`, Indicadores 01: «PIB per cápita… 2026» y «Esperanza de vida… 2024», dos
     tablitas lado a lado encima de la tabla, separadas por filas vacías; en Br_01 con una sola fila vacía, dentro
     del bloque de celdas del autor): parte del cuadro; año arriba con línea A32938, conceptos a la izquierda, años y valores
     centrados, líneas F3CED3 entre filas, cada tablita en su ancho; el cuadro se coloca desde el bloque y entre
     bloque y tabla quedan 4 mm. Anchos (`datos_cada_uno_a_lo_justo`): si la primera columna cabe en una línea, a su
     medida y las de datos el resto a partes iguales (redondeo hacia abajo); las que solo llevan valores del bloque, a
     lo justo (Arg_01: 180 / 51 pt, PDF 177 / 56). Si no cabe (03), datos a lo justo y la primera el resto.
     Si la segunda tablita empieza en la primera columna de datos de la tabla (Br_01: «Esperanza de vida…» en G,
     pegada a la primera en cuanto se oculta la F), sus conceptos pasan a la siguiente columna de datos (G→I), como en
     el PDF publicado y como está el Arg_01 (decisión del usuario, 2026-11-24, tras probar un hueco visible en F: la
     tabla de abajo quedaba con la primera columna de datos 75 pt a la derecha del PDF). El hueco sigue para cuando
     entre las tablitas solo haya una columna vacía que no lleve nada en la tabla.
   - **Mapa de calor** (Indicadores 02 de los grandes, Arg_02, 2026-11-21): el texto suelto encima de la cabecera,
     separado por filas ocultas y con cabecera debajo en su columna («Respecto al resto de los emergentes» sobre
     «Último dato (b)»), es la primera fila de la cabecera (sin línea debajo en Indicadores); las columnas estrechas
     cuya cabecera no cabe en una línea se ensanchan lo justo en múltiplos de 3 («II S»: 14→15 pt; antes se partía en
     «II⏎S»); las cifras que un formato condicional esconde (letra del color del fondo) no cuentan para los anchos y
     esas columnas van a lo justo de su cabecera; las separaciones entre años se quedan (3 pt). Arg_02: 171 / 14-15 /
     21 / 51 pt (PDF ≈179 / 14 / 45). Además: si un paso quita o cambia de sitio fórmulas se quita calcChain.xml (libro dañado), la
     unidad de ancho de las formas solo con medidas positivas (columna 16384) y sumas acumuladas (no responde).
     Grupos del autor (Indicadores): las filas que el autor separó con una línea más oscura que las demás bajo la
     primera columna (Arg_02: «Diferencial soberano (cambio trimestral)», «Sobrevaloración cambiaria»…; Arg_03: «Activos
     de los bancos…») llevan línea A32938 de lado a lado. En el mapa de calor, las rosas solo bajo los conceptos (no
     sobre los colores) y la separación de 3 pt entre los conceptos y los colores (D) se queda.
     Letra: `cuerpo_mapa_calor` 7 pt (todos los 02 publicados de los grandes van a 7; los demás cuadros de Indicadores,
     6,5). Columnas estrechas: medio punto de tolerancia antes de ensancharlas (a 7 pt «II S» pide 15,1 → 15 pt).
     En el mapa de calor las separaciones de 3 pt cortan las líneas del cuerpo (huecos blancos, como el publicado) y no
     se oculta ninguna (también la de entre «2026» y «Último dato»).
   - **Aviso de cuadro que se sale de la retícula** (petición del usuario, 2026-11-21): en cada paso desde «Celdas», si
     las columnas del cuadro miden más que la retícula o si la tabla o FUENTES (medida por su texto, no por su marco)
     acaban más abajo, «Aviso: …» con los puntos que sobran y qué probar (letra más pequeña, acortar notas, quitar filas
     vacías). Hoy: Economía Latinoamericana 05 a 7,5 pt (sobran 32) y Memoria 4.2 a 7,5 (sobran 12).
   - **Herramienta «Igualar al modelo»** (orden `modelo`, petición del usuario, 2026-11-21): busca en la carpeta del
     original y en «Modelos» (junto a ella o en el proyecto) el EXCEL terminado más parecido (palabras en común sin
     países ni cifras, al menos un 50 %; si empatan, el último guardado) y copia de él, tal como esté guardado (con
     los retoques a mano): anchos por papel de columna (primera, de datos por orden, solo del bloque), altos y el
     formato de cada celda (fuente, relleno, borde y alineación, con los colores del tema pasados a RGB), emparejando
     las filas por concepto (difflib) y el bloque de arriba por tablitas. Lo que falte o sobre de ancho va a la
     primera columna (solo si el cuadro tiene las mismas columnas que el modelo: Co_01 y Cos_01 llevan el valor de
     «2026» en la primera columna de datos y Arg_01 en una aparte; entonces, los anchos de la app). Avisa de las filas sin pareja; esas filas toman el alto normal del modelo y, si debajo de una
     fila hay otra que en el modelo (Br_01: «CDS soberano», última del grupo en Arg_01, seguida aquí de «CDS Petrobras»),
     sus líneas son las que puso la app (rosa, como el PDF), no la oscura de fin de grupo del modelo. Textos y cifras, siempre los del cuadro. Probado: Arg_01 como
     modelo de Br_01 y Cos_01, también con un retoque a mano (primera columna y un fondo).
   - **Cifras a la derecha** (`cifras_a_la_derecha`, Indicadores; petición del usuario, 2026-11-24, como los PDF
     Br_01 y Arg_03): cada columna con su cifra más ancha centrada bajo la cabecera y las demás alineadas con ella por
     la derecha; el margen va en el formato de número («0.0_0_0_0_0»: ceros invisibles), igual en Mac y Windows. Se
     rehace en cada paso (`nuevo_paso`), con los anchos y la letra del momento (Igualar al modelo, «Probar letra»).
     Textos («—», «n. d.», «3 % (± 1,5 pp)»), cifras escondidas del mapa de calor y separaciones de 3 pt, sin tocar.
   - **Textos como los publicados** (Indicadores, en castellano; petición del usuario, 2026-11-24, Ch_01): espacio
     que no parte línea entre la cifra y «%» también en el bloque de arriba («3%(± 1 pp)» → «3 % (± 1 pp)», con
     espacio antes del paréntesis); `textos_es` en publicaciones.json: «PIB per cápita (USD)» → «(dólares
     constantes)», «PIB (m. USD)» → «PIB (mm de dólares)», «Average/Promedio 2000-2009» → «Promedio⏎2000-2009» (en dos
     líneas aunque quepa en una, Cos_01), «crédito - PIB» → «crédito-PIB»; `cursivas`: «ARA *metrics*», «*Tier* 1»
     (texto con formato, cada trozo en la letra de la celda). Esas celdas eran fórmulas: pasan a texto.
     En FUENTES y las notas: `textos_notas_es` («inferiores a 3 dólares» → «a tres dólares») y `cursivas_notas`
     («*assessing reserve adequacy*», «*Return on Assets*», «*Return on Equity*»). La barra solo se espacia entre
     expresiones cortas (hasta 4 palabras a cada lado): «otros ingresos/gastos de explotación» queda pegado, como el PDF.
   - **Indicadores 01 de los demás países** (2026-11-24, Mx, Pe y CARD, comparados con los PDF): título con el país del
     archivo (`paises`; el original de México decía «Colombia», el de Rep. Dominicana «La República Dominicana»);
     «Cuadro 1 (cont.)» se reconoce como rótulo, con «(cont.)» en Roboto Light; `quitar_p`: «25784 (p)» → «25.784» y la
     cabecera de su tablita «2026 (p)», «0,9 (p)» → «0,9»; `millares`: punto de millares en formatos y cifras de texto
     («4770,7» → «4.770,7»); cifras de texto a la derecha como las demás; «Tipos de interés» → «Tipo», «2,5 - 3,5» →
     «2,5-3,5»; `juntar_saltos_primera`: el salto del autor en un concepto que cabe en una línea, fuera (Gua). En CARD la
     separación entre las tablitas (E) se queda visible a 12 pt (`HUECO_TABLITAS_PT`) para que sus líneas no se toquen.
     El cuadro de un EXCEL terminado con el bloque y la tabla separados por ≤3 filas se lee entero (antes, solo el
     bloque, y no servía de modelo).
   - **Aviso de modelo** (petición del usuario, 2026-11-24): al empezar (y al terminar «Líneas y fondos») el motor
     busca si el cuadro tiene modelo (`estado["modelo"]`). La app resalta en naranja «Igualar al modelo · hay
     modelo», avisa al acabar «Líneas y fondos» y, al «Guardar como EXCEL» sin igualar, pregunta antes.
   - **Filas ocultas del autor** (Arg_03: 4-7 con «#REF!» y 9-16, un bloque entero): siguen ocultas y no cuentan para
     la cabecera, los bloques, las sangrías ni los anchos (el cuadro se localiza con ellas, para que no se parta).
   - **Textos de fórmulas con espacios** (`<v xml:space="preserve">`, Economía Latinoamericana 05 y Memoria 2.1: la
     primera columna con =IF(…;A17;B17) y conceptos sangrados): se leen. Antes salían vacíos: en el 05 la cabecera
     llegaba hasta la fila 63; en el 2.1 la primera columna medía 156 pt y cortaba «…extracomunitarias» (ahora 198).
   - **Columnas a la derecha de la retícula del autor** (Economía Latinoamericana 04: BB «actual»; 03: EO-EU, meses de
     2023), separadas del cuadro por columnas vacías: no son del cuadro (la retícula del autor se lee en el original).
   - **Columnas anchas vacías dentro del cuadro** (04: AV, 69 pt, entre la escala y «Expectativas»): columnas de
     separación de 3 pt.
   - **Puntos y flechas dibujados sobre las celdas** (04: tono de la política monetaria): al cambiar anchos y altos,
     cada extremo guarda su sitio relativo en su celda; los puntos pequeños (hasta 4 mm) se mueven por su centro sin
     cambiar de tamaño y las flechas siguen tocándolos. Solo formas sin texto y con tamaño.
   - **Subtítulo combinado a lo ancho de los datos** sin concepto en la primera columna (Economía Latinoamericana 01:
     B8:G8 «Percentiles de distribución…»): no cuenta como texto largo de su columna (ni la ensancha ni la alinea a la
     izquierda) y va al centro.
   - **Columnas ocultas del autor** (Memoria 2.1: textos de traducción en A-C que la columna D enseña con una
     fórmula; «Descuadre» en G): ni se miden para el alto de fila ni se les cambia el formato.
   - **«Cuadro N» y unidades en celdas** encima del cuadro (Memoria 2.1, 3.2, 4.2): el paso 1 los pasa a cuadros de
     texto como en el Informe Anual (rótulo con el marco de la plantilla; unidades en Roboto Light 6 pt, colocadas
     como las demás) y vacía la celda. Solo celdas solas en su fila, por encima de la primera fila con dos textos,
     y, las unidades, si empiezan como unas unidades («Datos a…», «Millones…», «%»…). Al comparar con el
     original salen como «pasados de celdas a cuadros de texto», no como datos que faltan.
   - **Avisos de la comparación con el original, concretos** (petición del usuario, 2026-11-17): solo lo que cambia va
     entre ⟪ ⟫ y la app lo pinta en rojo; los espacios, saltos de línea y espacios que no parten línea se ven (␣ ⏎
     ⍽), con algo de texto alrededor, y se explica el cambio invisible («sangría de 2 a 4 espacios», «salto de
     línea añadido», «espacio que no parte línea»…).
   - Al comparar con el original, el formato de número sin el relleno que quita el paso 2 no cuenta como cambio.
   - Líneas y fondos sueltos del autor en celdas vacías a la derecha del cuadro, quitados (1.2, columnas I-K), y
     también encima del cuadro (filas entre la pastilla y la cabecera) y en las columnas ocultas (publicado del 3.3).
   - **Regresiones** (publicado del 3.3): la fila del coeficiente y la de su error estándar (entre paréntesis, sin
     concepto) son un solo concepto: la primera columna se combina en las dos filas y entre ellas no hay línea. Antes
     de los estadísticos («Observaciones», «R2», «R²», «Pseudo R2»…), línea oscura (blanco matiz 5).
   - Columnas de separación sin líneas ni fondo en las filas de datos (las líneas se cortan entre grupos, TERMINADO
     3.4); en la fila TOTAL, sin hueco.
   - La línea que cierra cada bloque de sangrados (gris claro, como el resto) queda por revisar con más ejemplos.
   - Paso 2: si quedan la FUENTE y las notas en celdas bajo el cuadro (las que el paso 1 no reconoce), el cuadro
     acaba antes y se avisa para pasarlas al cuadro de texto de FUENTES.
**Columnas a su medida** (decisión del usuario, 2026-11-18, publicado del Memoria 4.2): las columnas de datos van
siempre iguales; solo si así no caben (9 columnas que necesitan 64 pt cada una), cada una toma el ancho de su palabra
o cifra más larga y la primera columna, el resto (si ni así cabe, aviso para bajar la letra). A 6,5 pt el 4.2 queda
como el publicado (primera 99 pt frente a 106; datos 27-57 frente a 27-61).

**Letra «Normal» del libro: Roboto Light 11** (petición del usuario, 2026-11-19, cuadros abiertos en Windows): los
anchos de columna se guardan en «caracteres» de la letra «Normal» y cada Excel los convierte a su manera (Mac: dígito
en puntos enteros; Windows: en píxeles de pantalla, según el escalado). Con Arial 12 o Calibri 11 las columnas salían
un 4-12 % más estrechas en Windows mientras la pastilla y la retícula (formas, en mm) no cambiaban. El dígito de Roboto
Light 11 mide 6 pt en Mac y 8/10/12/14/16 px (= 6 pt) en Windows al 100/125/150/175/200 %. El paso 1 cambia la letra
«Normal» y recalcula los anchos que había (en Mac no cambian); `ancho_comun` elige el ancho guardado que da los mismos
puntos en Mac y en Windows a todas esas escalas (con anchos en múltiplos de 3 pt es exacto). Los 23 cuadros miden
468 pt en Mac y en Windows.

**Cabecera hecha con cuadros de texto** (DO26XX_02, 2026-11-19): si la fila de justo encima del cuadro no tiene
textos en celdas pero sí cuadros de texto anclados en dos o más de sus columnas de datos (símbolos de ecuación 𝑡, 𝛽,
𝜌, 𝜎²), es la cabecera: entra en el cuadro y esas celdas se colorean como cabecera (paso 3, `cabecera_formas`). En el
paso 2 esos cuadros de texto se centran en su celda con los anchos y altos nuevos (si no, quedaban descentrados).

**Decimales escritos como texto** (DO26XX_02, 2026-11-19, en español): «(.0002)» → «(0,0002)». Solo los que no pueden
ser millares (punto sin cifra delante, o «0.» delante).

**Un «TOTAL» por bloque** (DO26XX_04, 2026-11-19): con varias filas «TOTAL», son totales de bloque: todas en blanco
matiz 2 y Roboto Medium, sin fila TOTAL principal en matiz 5.

**FUENTES del autor por duplicado** (DO26XX_03, 2026-11-19): se maqueta y se coloca la de más texto dentro de la
retícula; las formas por debajo de la retícula quedan sin tocar, y las otras FUENTES se avisan.

**El cuadro se busca desde la primera columna visible con texto** (DO26XX_01, 2026-11-19): un código suelto en una
columna oculta (A74) se tomaba por el cuadro.

**Columnas de nombres propios** (publicado del Memoria 6.1, 2026-11-18): una columna de datos solo de textos de una
línea, cada uno con 2 o más palabras en mayúscula inicial (salvo conectores: «Banco Bilbao Vizcaya Argentaria, SA»),
va a la izquierda (su cabecera, al centro) y, si cabe sin partir la primera columna y no pasa de un tercio del cuadro,
con cada nombre en una línea: las columnas de datos a su medida, la de nombres justa y el sobrante para bajar líneas de
cabecera (cada vez a la más alta, la que menos cuesta), y lo que quede a partes iguales. Las de conceptos
(«Relajación, concentración», DO 05) siguen al centro. Solo afecta al 6.1 de los 23 ejemplos: 99/132/66/81/90 pt
frente a 124/135/62/82/93 del publicado (que se sale de la retícula).

**Celdas de la primera columna combinadas en vertical** (DO 02, 2026-11-18: «Indicadores directos de actividad
neuronal» en A7:A9): caben en tantas líneas como filas juntan sin alargar el cuadro, así que su ancho natural es el
mínimo con el que no pasan de esas líneas. El 02 pasa de 153/63 pt a 93/75 (publicado 130/75).
**Cabeceras que se parten por poco** (DO 02, decisión del usuario, 2026-11-18): si la cabecera de una columna de
datos cabe en una línea con un múltiplo (3 pt) más, esa columna sube (todas, si eran iguales) y la primera cede el
ancho, siempre que el cuadro no crezca. El 02 queda a 78/78 pt: «Resolución temporal» en una línea y «Estimulación
cerebral» (A15, sin combinar) en dos; mismo alto.

**Líneas del autor debajo del cuadro** (DO 05 y 09, 2026-11-18): el paso 4 quita las líneas y fondos que se ven en las
celdas vacías de las 10 filas de debajo del cuadro (la línea azul que el autor ponía encima de la FUENTE se quedaba al
pasar la FUENTE al cuadro de texto). Los bordes vacíos (IA 1.3, 1.4) no cuentan.

**Cabecera combinada a todo el ancho** (DO 06, 2026-11-18: «Alteraciones del color» en A5:C5): al centro, como el
publicado; la que empieza en la primera columna y no llega al final (DO 02, «Método» en A6:B6) sigue a la izquierda.

**Cuadros de texto que caben en una línea** (DO 09, 2026-11-18): las columnas de descripciones se quedan con lo justo
para su texto en una línea y lo que sobra iguala las columnas cortas (09: 54/90/90/234 pt frente a 57/109/109/231 del
publicado); al redondear a múltiplos de 3 pt ninguna baja de lo que necesita su texto en una línea.

**Herramienta «Probar letra a 6,5 pt»** (`letra65`, petición del usuario, 2026-11-18): como la de 7 pt, a 6,5 pt
(versión «Letra 6,5 pt»).

**Herramienta «Probar letra a 7 pt»** (`letra7`, petición del usuario, 2026-11-17): rehace desde la versión del
paso 1 los pasos 2, 3 y 4 que haya hechos con la letra de las celdas a 7 pt y lo guarda como una versión nueva
(«Letra 7 pt»); las de 7,5 pt quedan detrás para volver con ⌘←. El paso 2 la propone en su aviso de muchas
columnas. En el 3.4 deja la cabecera en 60 pt, como el TERMINADO.

**Botón «Aplicar» de las propuestas** (`aplicar <trabajo> <publicación> <paso:propuesta>`, petición del usuario,
2026-11-17, Memoria 3.2): los avisos con un cambio propuesto y no hecho —título en mayúsculas (paso 1), mayúsculas de
título en la primera columna (paso 2)— llevan la marca invisible «⟦aplicar:k⟧» y la propuesta se guarda en el paso
(`propuestas` en estado.json). La app pone debajo del aviso el botón «Aplicar», que hace el cambio en una versión
nueva («Propuesta aplicada», `aplica: ["n:k"]`; ⌘← para quitarlo) y lo enseña en Excel; aplicada, el botón pasa a
«Aplicada». Solo cambia mayúsculas y minúsculas y comprueba antes que el texto sigue siendo el del aviso (si se ha
tocado a mano, no hace nada). «Probar letra a 7 pt» vuelve a aplicar las propuestas ya aplicadas.

**Herramienta «Línea oscura sobre la selección»** (`linea_oscura`, petición del usuario, 2026-11-17, publicado
del 2.9): para separar conceptos. Se selecciona en Excel una celda de cada fila que empieza un concepto nuevo (varias
con ⌘; de cada zona cuenta su primera fila) y la app pone la línea oscura (blanco matiz 5) encima de esas filas, en
todo el ancho del cuadro salvo las separaciones, en una versión nueva («Líneas oscuras»). Exige el paso 4.

5. **Terminar**: «Comparar con el original» (`comparar`, sin crear versión: datos de todas las hojas y textos de
   las formas frente al Excel del autor; avisa en rojo de lo que falte y lista los cambios —sangrías, viñetas,
   «TOTAL», puntos, comillas—) y «Guardar como EXCEL» («ORIGINALES» → «EXCEL», junto al original; lo deja abierto en Excel y borra
   copias y versiones).
