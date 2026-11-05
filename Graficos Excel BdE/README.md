# Gráficos Excel BdE

App de Mac (SwiftUI) que maqueta, paso a paso, el Excel que entrega el autor (origen del PDF que luego se
maqueta en «Graficos Illus BdE», que no se toca desde aquí).

- **Ventana general**, como la de «Crear Publicación»: publicación (alta, edición y borrado), Excel del
  autor, tarjetas «Maquetar» (los pasos) y «Adelante y atrás» (las versiones) y la actividad abajo.
- **Excel al lado**: cada paso y cada salto de versión se ven directamente en Excel. La app se pone a la
  izquierda de la pantalla y Excel a la derecha, en la hoja «Gráfico», desde A1 y con el zoom justo para ver
  la retícula entera. Excel enseña siempre la copia de trabajo `X maquetado.xlsx`, en una sola ventana: tras
  cada paso o salto de versión la copia pasa a ser esa versión y Excel la cierra sin guardar y la vuelve a
  abrir en el mismo sitio (≈ 0,9 s), como un deshacer o rehacer. Lo que se cambie a mano en esa ventana se
  pierde al cambiar de versión. «Colocar Excel» vuelve a ponerlo en su sitio y recalcula el zoom.
- **Reiniciar** (en «Adelante y atrás»): vuelve a empezar desde el Excel del autor. Pregunta antes, borra todas
  las versiones, rehace «00 Copia exacta» con el original y la copia de trabajo vuelve a ser esa (motor:
  `reiniciar`).
- Siempre el mismo archivo porque Excel (aislado) pide permiso archivo a archivo: con cada versión en su
  propio archivo, cada paso nuevo era un archivo nuevo y Excel pedía permiso con una ventana «Abrir»
  («Conceder acceso») que el Organizador visual escondía. Ahora se pide una vez por trabajo.
- La app habla con Excel dentro de sí misma (NSAppleScript); lanzar `osascript` en cada orden costaba
  segundos. No entra nunca en la carpeta de Office (`~/Library/Group Containers/UBF8T346G9.Office/`): es de
  otra app y macOS frena o pide permiso a quien entra (y como la app solo tiene firma local, la trata como
  nueva cada vez que se compila). Por eso las paletas se leen de una copia, `motor/paletas.json`, que solo
  se rehace con ↻.
- Firma: `compilar_app.sh` firma en local con un requisito fijo (el identificador de la app). Con la firma
  local normal, el requisito era la huella del ejecutable: cada compilación era «otra app» para macOS, el
  permiso de Automatización sobre Excel dejaba de valer (aunque siguiera marcado en Ajustes) y macOS volvía
  a preguntar con un aviso que el Organizador visual escondía: esperas de minutos sin rastro.
- **Nada de animaciones continuas** en la ventana (ruedecitas, iconos que laten): con el Organizador visual,
  cada fotograma dejaba a la app esperando a que macOS lo mostrara, y la app entera (también Excel y el
  motor) se quedaba parada hasta que se tocaba algo. Era la causa de las esperas de segundos y minutos. El
  contador de segundos solo corre con la ventana a la vista. Ahora: abrir el trabajo ≈ 1,3 s, cada cambio
  de versión ≈ 1 s.
- Excel se coloca donde acaba de verdad la ventana de la app (con el Organizador visual, macOS puede apartarla
  a la derecha). La app solo se recoloca si cambia su tamaño.
- Si la app arranca Excel, lo activa una vez: recién arrancado en segundo plano, Excel no enseña sus ventanas.
  Luego espera 1 s a que acabe el cambio de grupo antes de juntar las ventanas.
- Con el Organizador visual (Stage Manager) activado, Excel crea cada ventana nueva (la copia reabierta) en un
  grupo aparte, escondida en la tira de la izquierda. Tras cada cambio la app la mete en su grupo con la acción
  «AXAddToStage» de su miniatura en la tira (como arrastrarla a mano); la miniatura se busca por el número de
  ventana (atributo «AXWindowsIDs»): la más nueva de Excel que esté en la tira o a la vista (Excel tiene
  ventanas internas, como una de 500 × 500 al arrancar, que no están en ninguna). Ya están juntas si se ven
  las dos a la vez. Al juntarla, el Organizador visual la coloca a su manera: se vuelve a poner en su sitio. Necesita el permiso de **Accesibilidad** para la app (Ajustes del Sistema →
  Privacidad y seguridad → Accesibilidad); sin él, la actividad lo avisa. Los avisos de permiso (de Excel o de
  macOS) también quedan escondidos por el Organizador visual.
- **Dos copias de trabajo** que se alternan, «X maquetado.xlsx» y «X maquetado (2).xlsx», siempre con la
  versión elegida: al cambiar de versión, Excel abre la que no está abierta, la coloca y, después, cierra la
  otra; así su ventana no desaparece (Excel no abre dos veces el mismo archivo ni dos libros que se llamen
  igual). Antes de abrirla, la app escribe en el libro (workbookView de xl/workbook.xml, en veinteavos de
  punto) el sitio de la ventana, y nace ya colocada. Con el Organizador visual, Excel se pone delante antes de
  abrir solo si su ventana ya está en el grupo de la app (la nueva nace en el mismo grupo); si no, se junta
  después. Para dar por juntas la app y Excel tienen que seguir viéndose 0,6 s después (durante el cambio de
  grupo se ven un momento las dos). Probado con la app y `scratchpad/vigilar` (ventanas en pantalla cada 0,1 s):
  Excel siempre en pantalla, también arrancando con Excel cerrado. `--abrir <xlsx>` abre un trabajo al
  arrancar la app (para probar sin el diálogo).
- Se trabaja sobre una **copia**: del original `X.xlsx` sale `X maquetado.xlsx`, y cada paso deja su
  versión en `X maquetado (pasos)/` (`00 Copia exacta.xlsx`, `01 Retícula, pastilla y textos.xlsx`…). Ir adelante
  y atrás es volver a una de esas versiones. Elegir otra vez el original o la copia sigue donde se quedó.
- Excel abre siempre **sin actualizar vínculos externos**. La copia de trabajo `X maquetado.xlsx` es
  siempre igual a la versión elegida.
- Si Excel tarda más de 2,5 s (casi seguro, su ventana de permiso), la app lo trae delante y lo avisa.
- AppleScript de Excel: las rutas van con barras (POSIX); con dos puntos da «Error de parámetros (-50)».
  `repeat with … in every workbook` también da -50: hay que recorrer los libros por número.
  Y no llamar `pdf` a una variable: es palabra reservada de Excel.
- La retícula no se imprime (como en el archivo de retículas): solo es guía en pantalla.
- La hoja del gráfico es «Gráfico»; si no existe (hay autores que usan «G1» y «D1»), la primera hoja con
  gráficos.
- Idioma del gráfico por el nombre: «Ing» delante o detrás (`Ing_…`, `…_Ing`) es inglés; si no, castellano.

## Pasos

Van en orden: cada paso exige que el anterior esté en la versión de la que parte (si no, el motor avisa).
Las versiones hechas cuando retícula y textos eran dos pasos («Retícula y pastilla» y «Textos») siguen valiendo.

1. **Retícula, pastilla y textos** (`paso1`, una sola versión; el motor hace primero la retícula y la
   pastilla y, sobre eso, los textos):
   - Si el autor lo ha agrupado todo con el gráfico (pastilla, títulos, gráfico, FUENTES: «G_26XX_06
     INTERVALOS»), primero se desagrupa: cada elemento, con la escala de su grupo, queda anclado a sus celdas en
     el mismo sitio (`desagrupar`). La retícula del autor (grupo de líneas) no se desagrupa.
   - Retícula y pastilla: borra la retícula y la pastilla del autor y pone las del archivo de retículas
   (`SdE_Reticulas_Publicaciones_ImagenNueva2024_Roboto.xlsx`, hoja «Gráfico»), en A1 y al fondo, con el
   color de la publicación. La retícula va a su tamaño de diseño (16,63 × 24,78 cm).
   - Textos: todo en Roboto, sin negrita (el peso lo da la variante):
   - «Gráfico NN»: Roboto Regular 7 pt; título: Roboto Medium 8,5 pt. Los dos toman el marco de la plantilla
     (`marco_grafico` y `marco_titulo` en la configuración): posición, tamaño, márgenes y letra, con el texto
     del autor.
   - Títulos de panel 8 pt; ejes, leyendas y unidades 7 pt; interior del gráfico (etiquetas de datos, tabla
     de datos, lo que no tenga letra propia) 6 pt; FUENTES Roboto Light 7 pt. Donde los dejó el autor.
   - Cómo se reconoce cada texto de la hoja (`clasificar_textos`, el mismo en los pasos 1 y 2): «Gráfico NN»
     por su texto; el título, el que empieza dentro de la pastilla; FUENTES, el que empieza por
     «FUENTE»/«SOURCE»; título de panel, el numerado («1 a», «1.a», «2.6.a»), aunque esté encima del gráfico;
     un texto suelto en la mitad de arriba de un gráfico (o hasta 2 mm por encima), a la izquierda, son
     unidades (7 pt) y a la derecha, un texto sobre el gráfico (7 pt, se mueve con él, p. ej. «14%»); el resto,
     título de panel. Lo que queda fuera de la retícula (el «Más info») no se toca. Dentro del gráfico, los
     cuadros de texto del 20 % de arriba son unidades y el resto, interior.
   - Si «Gráfico NN» y el título van en el mismo cuadro (dos párrafos), se parte en dos cuadros.
   - La pastilla del autor se reconoce aunque esté hasta 1 mm desplazada del origen (en el 2.6, 0,3 mm).
   - Leyendas en minúscula salvo siglas (y la primera letra, la de después de un punto, los nombres propios y
     los números romanos), solo si el autor las escribió enteras en mayúsculas («FRENTE AL EURO» → «Frente al
     euro», «ELECCIONES EEUU» → «Elecciones EEUU»). Listas de siglas y nombres propios en el motor (`SIGLAS`,
     `SIGLAS_ESCRITAS` — «pymes», «euríbor», «BdE» —, `NOMBRES_PROPIOS`). Se cambia la celda de la que sale el
     nombre (como texto propio de la celda, sin tocar los textos compartidos) y, si es una fórmula
     (`=SI(…;T(F9);T(F8))`), la celda de su columna con el mismo texto, su origen.
   - Textos especiales (guía, págs. 10 y 11; interactiva: Esp_texto02-0n):
     - Fechas del eje en el formato del idioma: `[$-1540A]mmm\-yy;@` (es; el `[$-es-US,1]mmm-aa;@` de la guía)
       o `[$-10409]mmm\-yy;@` (en), si el eje (o sus datos) tienen mes y año o día.
     - Números de los ejes de valores: sin decimales si todos son ceros, uno si hay decimales, dos en las
       centésimas; separador de miles (`#,##0`, `#,##0.0`, `#,##0.00`; respeta el %). Los decimales salen del
       salto del eje: el fijo o el que pondría Excel (`escala_eje`: el menor de 1, 2, 5 × 10ⁿ con ≤ 9 tramos,
       5 % de aire, 0 como mínimo salvo datos por encima de 5/6 del máximo; comprobado con los ejes de prueba).
       Solo ejes (no etiquetas de datos). Si el eje toma el formato de los datos, se cambia en sus celdas (un
       numFmt y copias de los estilos de celda).
     - Leyendas con la escala derecha en cualquier versión → «(Escala dcha.)» / «(Right-hand scale)», en la
       celda de la que salen. Sin cursiva (decisión del usuario: no se usa la cursiva).
     - Etiquetas de datos (págs. 10 y 16, `etiquetas_datos`): los decimales de la regla de los ejes según sus
       valores (ninguno si son enteros, uno si hay decimales, dos si con uno alguna cifra quedaría en 0,0;
       separador de miles; respeta el %), escritos en las etiquetas (`sourceLinked 0`; las celdas no se tocan).
       Va después de pasar las tartas a 0-100: el G_26XX_05 queda con un decimal (62,6), no con dos como su
       TERMINADO. Si una etiqueta lleva texto (categoría, serie o valor de las celdas) y número, separador «: ».
     - Trimestres → «I TR … IV TR» (es) / «Q1 … Q4» (en), con el año detrás: en leyendas, categorías (celdas y
       caché), textos de la hoja dentro de la retícula y textos de dentro de los gráficos.
     - Eje horizontal: nunca en oblicuo. Horizontal (explícito, para que Excel no lo incline) si la palabra
       más larga cabe a 6 pt; si no, vertical de abajo arriba (`rot=-5400000`) a 7 pt (6 si no cabe una línea),
       partido en 2 o 3 líneas (saltos en las celdas) solo lo necesario para no pasar del largo de la etiqueta
       más difícil; si ni así cabe, aviso. «Tamaño y colocación» mide entonces las categorías por su línea más
       larga. Se decide con el ancho final del trazado (columna 1, o las dos si va sin leyenda).
   - Título: si acaba en una letra, «(cont.)» o «(cont'd)» entre paréntesis, ese final va en Roboto Regular.
   - Formato local del autor: se respetan cursivas, subrayados, índices y la negrita de una parte del texto
     (también en «Gráfico NN» y el título, aunque tomen el marco de la plantilla). Si todo un texto va en
     negrita, se quita: el peso lo da la variante de Roboto.
   - FUENTES, con las reglas de «Gráficos Illus BdE» (`setSourceFrameText` del generador V3):
     - rótulo FUENTE(S)/SOURCE(S)/NOTA(S) seguido de «:», «.» o espacio → en mayúsculas y con «: »; en inglés,
       FUENTE → SOURCE. FUENTE(S)/SOURCE(S) en Roboto Medium; NOTA(S) en Light. Si la primera línea no
       lleva rótulo, se le pone «FUENTE:». Singular o plural, el del autor (en Illustrator lo elige un
       diálogo).
     - notas con letra («a.» o «a» + tabulador): letra en Medium, tabulador y sangría francesa de 8,5 pt; las
       líneas siguientes sin letra ni rótulo se unen a la nota.
     - una línea en blanco tras la fuente (salvo que siga una NOTA) y tras cada NOTA; las líneas vacías del
       autor se quitan.
     - en castellano, comillas españolas («») y espacio que no parte línea entre la cifra y «%»; en inglés,
       «%» sin espacio.
   - Eje de categorías horizontal: 7 pt, salvo que se pierda texto. Se mide con la Roboto instalada la palabra
     más larga de las etiquetas contra el hueco de cada categoría (ancho del área de trazado / categorías,
     menos 1 pt); si no cabe, 6,5 pt, y si tampoco, 6 pt. Excel parte por espacios: si una palabra no cabe, la
     corta o gira las etiquetas.
2. **Tamaño y colocación** (`paso2`) (como en «Graficos Illus BdE», paneles uno debajo de otro):
   - Guías de la retícula de la copia: columna 1 (2,55–114,72 mm), columna 2 (121,25–163,62 mm), filas de
     5,03 mm.
   - Cada gráfico, de la columna 1 al final de la columna 2. Dentro, el área de trazado interior
     (`layoutTarget inner`) llena la columna 1: a la izquierda queda el sitio de los números del eje (su ancho
     + 8 pt; si no caben, Excel corre todo el trazado a la derecha).
   - Sin título del gráfico (solo «Gráfico NN», como en el G_Trim_03): la pastilla se acorta lo que va de la
     línea de base de «Gráfico NN» a la del título en la plantilla (unos 4 mm: queda en 9,2 mm; el TERMINADO,
     8,6), para acabar a la misma distancia del último texto; los paneles suben con ella.
   - Leyenda: empieza en la columna 2 (el cuadro, 3 mm antes, por el aire que deja alrededor del texto), a la
     altura del comienzo del gráfico, con el ancho justo de su línea más larga (los nombres que no caben en
     la columna 2 se parten), para que vayan una debajo de otra. Medido en Excel: Excel **centra** las
     entradas si el cuadro es más ancho (por eso el ancho justo); la muestra de una serie de líneas mide unos
     16 pt más que la de columnas; cada entrada ocupa el alto de la más alta y Excel reparte lo que sobre, y
     si no caben todas quita las últimas. No cuentan las entradas borradas de la leyenda.
   - Sin leyenda: si el autor no la tiene, ha borrado todas sus entradas o la ha encogido a menos de 10 pt de
     ancho (en el 2.6, el panel a: 6 pt), el trazado ocupa las dos columnas, como en el TERMINADO, la leyenda
     se deja como está y el detalle lo avisa (en rojo y negrita en la app): lo que representa tiene que explicarlo
     el título del panel.
   - Título de panel: va con el gráfico que empieza más cerca de él (hay autores que lo ponen sobre el marco
     del gráfico).
   - Unidades puestas en la hoja (no dentro del gráfico): igual que las del gráfico, en la línea del eje y
     con la línea de base 2 mm sobre el trazado.
   - Las filas se miden por la letra que se ve, de lo alto del número más alto del eje a lo bajo de la última
     línea de categorías (`LETRA_ARRIBA` 1,7 pt y `LETRA_ABAJO` 3,4 pt: lo que sobran las cajas de Excel; sin
     esto el panel quedaba 5,1 pt corto). Las filas de las categorías se cuentan igual: dos niveles de una
     línea caben en 2 filas.
   - Alto: 9 filas desde lo más alto del trazado hasta el final de las categorías. Si las categorías ocupan
     más de 2 filas, el trazado se queda en 7 y el panel crece. Alto de las categorías (medido en Excel): 6 pt
     hasta la primera línea, sus líneas (partidas por palabras en su hueco), 13,5 pt más por cada nivel de más y
     4 pt debajo. Los niveles se cuentan por el rango (puede ser una unión de trozos; la caché puede venir
     incompleta).
   - Cuerpo de las categorías: la regla de los textos con el hueco nuevo. Excel deja unos 5 pt libres por hueco;
     si la palabra más larga no cabe, ensancha el trazado por su cuenta.
   - Vertical: el texto del título del panel 1 empieza 3,8 mm por debajo de la pastilla (como en el TERMINADO; lo
     deducido de Illus quedaba pegado a la pastilla); sin título de panel, el panel 1 empieza donde en Illus.
     Con las medidas de Illus: el gráfico empieza 7,38 mm por debajo del final del título de panel (0,5 mm más
     arriba, y 0,7 mm más si hay unidades);
     8,5 mm entre paneles; FUENTES 5 mm bajo el último, a lo ancho de las dos columnas.
   - Unidades (cuadro de texto dentro del gráfico, en su 20 % de arriba): en la línea del eje vertical, con su
     línea de base 2 mm por encima del borde de arriba del trazado. El marco del gráfico empieza en ellas.
   - Título del gráfico de 2 o 3 líneas: su marco, la pastilla y todo lo de debajo crecen o bajan un interlineado
     del título por línea de más (el alto de línea de Roboto Medium 8,5 pt, 9,96 pt, por el interlineado del
     párrafo): la pastilla queda siempre a la misma distancia por debajo del texto. Se reescribe su anclaje (en
     uno de dos celdas, cambiar solo el tamaño de dentro no hace nada). Un título de panel de varias líneas
     baja su gráfico (7,38 mm desde el final del título) y todo lo de debajo.
   - Las posiciones se leen de las celdas de anclaje (el `a:off` de dentro puede estar desfasado) y se
     escriben con ancla absoluta (`absoluteAnchor`).
3. **Ejes** (`paso3`; se irá completando). Casos de la página 15 de la «Guía gráficos v4.pdf» (interactiva:
   el texto está en campos ocultos, G-Eje/Esp-Eje/Esq-Eje) y formato del TERMINADO. En cada panel:
   - Línea de los ejes visibles (también el derecho) 0,5 pt y de las líneas de división 0,3 pt, en
     blanco oscurecido: matiz 5 (`FFFFFF` con `lumMod` 50 %) los ejes y matiz 4 (65 %) las divisiones; remate
     plano («sin relieve») y unión angular. Solo da formato a las divisiones que ya tenga el autor.
   - Eje en cero: el eje de categorías (y los dos en dispersión) cruza el otro en 0 (`crossesAt 0`). Si cruza
     en el máximo (eje derecho o de arriba) se deja y se avisa.
   - Marcas de graduación: horizontal en Cruz si el eje que cruza tiene negativos, si no Interior; vertical
     siempre Interior (en dispersión, Cruz si hay negativos). Secundarias Ninguno. Si el eje horizontal queda
     arriba (todo negativo), principal y secundaria Exterior. Una marca por valor en el eje horizontal.
   - Etiquetas en Bajo (ejes horizontales y, en dispersión, también el vertical) y, en el eje de categorías,
     a distancia 100 (en el de valores Excel no tiene ese ajuste).
   - Eje cortado: un máximo fijo sube y un mínimo fijo baja al siguiente tramo del intervalo (55 → 60 de 10
     en 10), para cerrar con una línea de división. Si el intervalo es automático, solo avisa.
   - Los ejes ocultos no se tocan (como en el TERMINADO 2.6).
   - Dispersión: solo cuando el grupo `scatterChart` va sobre dos ejes de valores; en un gráfico combinado
     (columnas + puntos) la dispersión puede ir sobre el eje de categorías y no cuenta.
   - Comprobado con «G_DO26XX_2.6 EJES ORIGINAL/TERMINADO.xlsx»: los ejes quedan idénticos al TERMINADO.
   - El TERMINADO no sigue la guía en el panel 3: Cruz sin negativos y una marca cada 2 categorías.
4. **Líneas interiores** (`paso4`). Línea base, líneas divisorias y flechas.
   - Línea base (guía de gráficos, pág. 13, interactiva: el texto está en Esp-Base_0n). Si las
   unidades de un panel (de la hoja o de dentro del gráfico) indican un dato de referencia — «Base 100 = …»,
   «100 = …», «… = 100», o con 50 —:
   - En la hoja de datos de sus series, en la primera columna libre (detrás de la última usada, para no mover
     las referencias de las demás series), ese dato desde la primera fila de las series hasta la última con
     datos (las series suelen apuntar a más filas de las que tienen).
   - Una serie «Base 100» / «Base 50» (nombre escrito en la serie) en el grupo de líneas de los ejes
     principales, o en uno nuevo sobre ellos si el gráfico es de columnas; sin marcadores; gris como los ejes
     (blanco matiz 5, como en el TERMINADO de prueba «G_Trim_03 BASE 100TERMINADO.xlsx»), 0,5 pt, remate plano y
     unión en ángulo; oculta en la leyenda. El TERMINADO la llama «100»; el usuario prefiere «Base 100».
   - Líneas divisorias (pág. 14: negra, 1 pt, remate plano y unión en ángulo). Las que el autor hace con una
     serie de columnas (muchas categorías y como mucho 3 valores, como «Elecciones EEUU» en el G_Trim_03):
     relleno negro y contorno de 1 pt, como en el TERMINADO (que se lo pone al punto). Las dibujadas (línea
     sin puntas): igual.
   - Flechas dibujadas (dentro del gráfico o en la hoja, dentro de la retícula), como en el TERMINADO: negras
     (tx1), 0,5 pt, unión en ángulo y punta abierta («arrow») en los mismos extremos.
   - Líneas guía de las etiquetas de datos (pág. 16: blanco matiz 5, 0,5 pt, remate plano y unión en ángulo):
     solo se ponen si las etiquetas se confunden, así que no se activan; si están activadas, se les da ese
     formato. Dos sitios: en las tartas, `c:showLeaderLines` + `c:leaderLines` dentro de las etiquetas; en el
     resto (Excel 2013), `c15:showLeaderLines` + `c15:leaderLines` en su extensión. Probado en Excel con copias
     del circular y de PRUEBAS.
     Si se activan a mano en Excel, Excel les pone su formato (negro, 0,75 pt): el formato de las desactivadas
     no sirve, porque Excel lo descarta al abrir. Para eso está el botón **«Líneas guía»** de la app (tarjeta de
     versiones): en el Excel abierto, a cada serie con líneas guía le pone 0,5 pt y gris 808080 (AppleScript:
     `line format of chart format of leader lines`); hay que guardar el libro para conservarlo. Además, cada vez
     que se vuelve a la app (de Excel), lo revisa sola y corrige las que no tengan ese formato (lo anota en la
     actividad); una nota bajo los botones lo recuerda. No hay forma de que Excel las cree así por defecto: los
     gráficos de los autores no tienen hoja de estilo (`xl/charts/styleN.xml`, donde va `cs:leaderLine`).
   - Trampa: en los dibujos de dentro de los gráficos el prefijo `a:` se declara en cada elemento; un `<a:ln>`
     nuevo sin `xmlns:a` hace que Excel descarte todo el dibujo (desaparecen flechas y textos).

5. **Tramas, colores y líneas** (`paso5`). Estilos de las series según «Excel. Guía lineas y tramas colores
   2026.pdf», con la paleta de la publicación (`ESTILOS_SERIES` por tema; de momento solo BdE_2026,
   Documentos Ocasionales; las demás publicaciones tendrán los suyos).
   - Secuencia de 7 estilos, empezando por el negro (decisión del usuario: la de la guía 2026, no «el tercer
     color del tema» de la guía v4). Tramas: dkHorz 000000/595959, pct90 7DB749/FFFFFF, dkUpDiag
     FFDB93/FFF0D2 (la pág. 2 dice FFEDC9; el usuario eligió FFF0D2, como el TERMINADO), zigZag EF9011/FFC000,
     narVert 1D5191/AECEF4, wdDnDiag C30FBA/F257EB, dkVert 7F3C2F/C9796B; sin borde. Líneas de 2,25 pt: negra
     sólida, 7DB749 punto cuadrado (`sysDash`), FFDB93 punto redondo (`sysDot`, remate redondo), y sólidas con
     marcador sin borde del color de la línea: EF9011 triángulo 6, AECEF4 cuadrado 5, C30FBA círculo 5, C9796B
     rombo 6.
   - Orden (guía de gráficos, pág. 7), en cada panel: primero las líneas, luego áreas y barras (en el orden de
     las series: de izquierda a derecha o desde el eje hacia arriba) y al final los marcadores (series de
     dispersión o de línea sin línea: círculo sólido de 5 pt sin borde, del color de su estilo). Tartas: un
     estilo por sector, en el orden de la leyenda.
   - No se tocan: la línea base, las series de columnas que hacen de línea divisoria, las invisibles y las
     ocultas en la leyenda. Las barras llevan `invertIfNegative` 0 (si no, los negativos salen en blanco).
   - Aviso en rojo a partir de la 8.ª serie (la guía recomienda 5; con 8 o más la secuencia se repite) y si
     una serie tiene puntos con formato propio del autor (no se tocan).
   - Trampa: el `idx` de `<c:legendEntry>` es la posición en la leyenda (grupos en su orden y, dentro, por
     `order`), no el `idx` de la serie (`orden_leyenda`). Arreglado también en la línea base y en las medidas
     de la leyenda del paso 2.
   - Cada panel empieza de cero (decisión del usuario; el TERMINADO del 2.6 empieza el panel b en el estilo 2,
     pero no se sigue).
   - Marcadores de las líneas con muchos puntos (series diarias): no se quitan, se espacian (como mucho uno
     cada 4 mm del ancho del trazado, `ESPACIO_MARCADORES`). El marcador se queda en la serie (así sale en la
     leyenda) y se quita con un `dPt` (`symbol none`) en los puntos que no tocan; las líneas con marcador de un
     mismo panel se desfasan para no coincidir. Comprobado en Excel con el G_Trim_03 (17 triángulos, uno cada
     32 puntos; la leyenda conserva el triángulo).
   - Intervalos (guía, pág. 16; prueba: «G_26XX_06 INTERVALOS ORIGINAL/TERMINADO»): en los grupos de líneas con
     líneas de máximos y mínimos (`c:hiLowLines`), la línea negra de 1 pt, remate plano y unión en ángulo; las
     dos series de los extremos (la que más veces es la más alta y la más baja) sin línea y con marcador raya
     negro de 7 pt; no entran en el orden de colores. Los marcadores del medio no pueden ser negros (irían sobre
     la línea negra): se salta al estilo siguiente.
   - Sombreados (pág. 16): series de áreas o columnas sin hueco (≤ 50) cuyos datos son siempre el mismo valor o
     vacíos (con algún vacío; no las divisorias), y rectángulos rellenos sin texto dibujados dentro del gráfico.
     Color de la publicación (el de la pastilla; matiz 1), sin borde; sin transparencia, o al 80 % si quedan por
     encima de otras columnas o áreas (Excel pinta áreas, luego columnas, el eje secundario encima y, entre
     grupos iguales, en el orden del archivo); los dibujados, siempre al 80 %. No entran en el orden de colores.
     Probado en Excel con una banda añadida al G_Trim_03 (no hay archivo de prueba con sombreados).
   - Pendiente: datos proyectados (fondo de otro color).

### Terminar (tarjeta «Terminar», debajo de los pasos)

- **Comparar con el original** (`comparar`): compara lo guardado (la más reciente de las dos copias de
  trabajo, así que incluye lo que el usuario haya guardado a mano en Excel) con el Excel del autor. No mira la
  colocación ni el formato de letra; sí:
  - los datos de todas las hojas (celda a celda): los que faltan (aviso en rojo), los que cambian, clasificados
    en cifras, mayúsculas, trimestres, ortotipografía o texto (columnas enteras ×100 de las tartas, en una
    línea), los cambios de formato de número o fecha de las celdas y las celdas añadidas (línea base);
  - las series de los gráficos (que falte alguna o cambie su rango; las añadidas);
  - el formato de números y fechas de los ejes;
  - los textos de los cuadros (de la hoja y de dentro de los gráficos) y de los gráficos (títulos, títulos de
    ejes, etiquetas escritas): se emparejan por parecido y se comparan palabra a palabra (lo que el paso 1
    separa en otro cuadro, como «Gráfico 2.6», no cuenta como falta; si solo se quitan letras, «falta»).
  El resultado sale en la tarjeta y en la actividad: «Aviso…» en rojo, «Cambio de…» en naranja. No crea versión
  y se borra al cambiar de versión. Trampa: `difflib` con `autojunk` (por defecto) da parecidos muy bajos en
  textos de más de 200 caracteres (FUENTES con notas): siempre `autojunk=False`.
- **Guardar como TERMINADO** (`terminar`): si la copia abierta en Excel tiene cambios sin guardar, avisa y no
  sigue; pide confirmación; cierra en Excel; copia lo guardado como «… TERMINADO.xlsx» junto al original
  («ORIGINAL» del nombre pasa a «TERMINADO», o se añade al final; si ya existe no se pisa: « (2)», « (3)»…) y
  borra las dos copias de trabajo y la carpeta «(pasos)». El original del autor no se toca. Al acabar enseña el
  TERMINADO en el Finder.

### Gráficos de tarta (guía, págs. 16 y 17; prueba: «G_MemoriaSupervision_2.3 CIRCULAR»)

Tartas, anillos y subgráficos (`pieChart`, `pie3DChart`, `doughnutChart`, `ofPieChart`):
- Paso 1: anillo con agujero del 80 %; líneas del subgráfico en blanco matiz 5, 1 pt, remate plano y unión en
  ángulo; si las etiquetas llevan %, se quita (formato sin %: `#,##0`, `#,##0.0`…), los datos de la hoja se
  multiplican por 100 (no si son fórmulas: aviso) y se pone «%» como unidad arriba a la izquierda si no está.
  El texto del hueco del anillo («2,3 billones de euros»), como en el TERMINADO: la cifra en Roboto Black
  24 pt (negrita) y el resto en Roboto Regular 7 pt, centrado, y el cuadro sin relleno ni borde (probado con
  «… ORIGINAL MODIFICADO», que lo trae con otras fuentes, tamaños y fondo rojo).
- Paso 2: la tarta mide 9 filas de diámetro y va centrada en la columna 1; arriba, donde le toque por el
  título, el título de panel y las unidades (como el trazado de los demás gráficos). La leyenda (sus entradas
  son las categorías) va centrada a lo alto de la tarta, pegada a la columna 2. Etiquetas por fuera: en las
  tartas, «extremo externo»; en los anillos (Excel no lo tiene), cada una a mano, 2 pt por fuera del anillo
  en la mitad de su porción (por fuera de la porción si el autor la separó: «explosión», % del radio; Excel
  no achica el anillo por ello). Las que chocan se apartan solas: se empujan a lo largo del anillo sin
  cruzarse (30° como mucho), cada una en el primer sitio libre en su dirección (se mira la forma real de cada
  porción) y sin salir del marco ni pasar a la columna de la leyenda; el marco sube hasta la pastilla o el
  título del panel. Si así alguna queda lejos de su porción (más de 4 pt o más cerca de otra), el anillo baja
  una fila de la retícula (dos como mucho; sigue con 9 filas de diámetro y FUENTES baja con él) y se queda con
  la primera que vale (G_26XX_05: baja 1 fila y las tres pequeñas de arriba quedan junto a la suya, como en el
  TERMINADO). Si ni así, línea guía dibujada en la capa de formas del gráfico (blanco matiz 5, 0,5 pt; Excel
  no dibuja líneas guía en los anillos) y aviso si alguna no cabe. Los
  textos sobre la tarta se mueven con su centro; el del hueco se centra en la tarta (cuadro centrado, texto en
  el medio del cuadro y 1,75 pt más arriba para compensar el hueco de la línea de 24 pt sobre las cifras;
  medido en Excel: centro del anillo y del texto a 1 px).
- Unidades de la hoja: solo las que están arriba (hasta 12 mm por debajo del borde del gráfico) y a la
  izquierda; el resto es texto interior.

## Publicaciones

En `motor/publicaciones.json`:
- `publicaciones`: las que se dan de alta en la app (nombre, color de la pastilla y paleta). Solo estas salen
  en el lateral; el paso 1 necesita una elegida.
- `muestrario`: las 8 pastillas del archivo de retículas (hoja «Gráfico») con la publicación de al lado. Solo
  de consulta: no son publicaciones.

La hoja de «Nueva publicación» / «Editar publicación» enseña:
- el **muestrario de pastillas**: arriba la publicación que se edita, tal como va quedando; luego las otras
  publicaciones creadas y las pastillas del archivo de retículas. Un clic en una pastilla pone su color (y su
  nombre, si aún está vacío); avisa si el color ya lo usa otra publicación creada;
- el **panel de paletas**: las paletas (temas de color) instaladas en Excel, en
  `~/Library/Group Containers/UBF8T346G9.Office/User Content.localized/Themes.localized/Theme Colors`, con sus
  10 colores en el orden de Excel y las publicaciones que ya las usan. El tema se guarda con el nombre del
  archivo, no con el de dentro: `BdE_2026.xml` se llama por dentro «Colores 2026_2», igual que la paleta de los
  Excel del autor, pero con Texto oscuro 2 y Énfasis 1 cambiados (EF9011 ↔ FFDB93). La buena es `BdE_2026`.

## Archivos

- `motor/maquetar_excel.py`: el motor (Python 3 del sistema, sin dependencias). Toca el .xlsx por dentro y
  deja igual todo lo que el paso no cambia. Se puede usar suelto:
  `maquetar_excel.py empezar|estado|ir|reiniciar|paso1|paso2|paso3|paso4|info|publicaciones|guardar_publicacion|borrar_publicacion|paletas`.
- `app/compilar_app.sh` → `Gráficos Excel BdE.app` en esta carpeta (no va a git).
- `app/crear_icono.swift` dibuja el icono (degradado verde-azul de «Maquetar» y «Versiones» con unas barras);
  `compilar_app.sh` lo convierte en `app/icono.icns` si no existe (para rehacerlo, se borra el .icns).
