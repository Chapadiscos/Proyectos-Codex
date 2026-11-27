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
- **Retoques a mano en Excel** (2026-11-26, petición del usuario): antes de cada paso o herramienta, la app guarda en
  Excel lo que esté sin guardar y el motor (`a_mano`) compara la copia de trabajo con la versión de la que partía
  (todas las partes salvo `xl/workbook.xml`, donde la app escribe el sitio de la ventana, y `docProps`). Si son
  distintas, la guarda como versión «Cambios a mano en Excel», con las formas que se han movido o cambiado de
  tamaño, y el paso parte de ella; ⌘← los quita. Si no se ha tocado nada, no hay versión nueva. Ojo: el paso 2
  («Tamaño y colocación») vuelve a colocarlo todo, así que lo retocado antes de él se recoloca; los pasos 3 a 5 y
  las herramientas lo respetan.
- **Cerrar y empezar de nuevo** (botón ⓧ junto a «Abrir en Excel», en el lateral; 2026-11-26): si se ha abierto el
  Excel que no era. Pregunta, cierra la copia en Excel sin guardar, borra lo que ha generado la app para ese Excel
  (las dos copias de trabajo y la carpeta «(pasos)») y vuelve a «Elegir Excel…», sin salir de la app. El Excel del
  autor no se toca (`descartar`).
- **Reiniciar** (en «Adelante y atrás»): vuelve a empezar desde el Excel del autor. Pregunta antes, borra todas
  las versiones, rehace «00 Copia exacta» con el original y la copia de trabajo vuelve a ser esa (motor:
  `reiniciar`).
- Siempre el mismo archivo porque Excel (aislado) pide permiso archivo a archivo: con cada versión en su
  propio archivo, cada paso nuevo era un archivo nuevo y Excel pedía permiso con una ventana «Abrir»
  («Conceder acceso») que el Organizador visual escondía. Ahora se pide una vez por trabajo.
- Sin «Conceder acceso» (2026-11-05): con el permiso de **Accesibilidad**, la app abre los libros como desde
  el Finder (`open -a`), y así macOS da a Excel permiso para ese archivo sin preguntar. Abierto así, Excel
  pregunta por los vínculos externos («No actualizar / Actualizar»): la app pulsa sola «No actualizar»
  mientras abre (`noActualizarVinculos`, por Accesibilidad), porque los vínculos externos no se actualizan
  nunca. Sin Accesibilidad, se abre como antes (`open workbook … do not update links`, que sí pide acceso).
  Excel guarda sus permisos archivo a archivo (`com.microsoft.Excel.securebookmarks.plist`, en su contenedor),
  nunca por carpetas: por eso cada trabajo nuevo lo pedía.
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
- Rutas con acentos (2026-11-26): Excel da el «full name» de un libro escrito como está en el disco (en DATOS, con
  los acentos descompuestos: «n» + tilde), y la app tenía la «ñ» de «Español» en una sola letra: las comparaciones
  no casaban y no encontraba el libro (el botón ⓧ no lo cerraba; tampoco iban la diana, las líneas guía ni el
  guardado de cambios en esas carpetas). Ahora toda ruta que se pasa a Excel se escribe como en el disco
  (`rutaComoEnDisco`, en `osascript`).
- AppleScript de Excel: las rutas van con barras (POSIX); con dos puntos da «Error de parámetros (-50)».
  `repeat with … in every workbook` también da -50: hay que recorrer los libros por número.
  Y no llamar `pdf` a una variable: es palabra reservada de Excel.
- La retícula no se imprime (como en el archivo de retículas): solo es guía en pantalla.
- La hoja del gráfico es «Gráfico»; si no existe (hay autores que usan «G1» y «D1»), la primera hoja con
  gráficos.
- Idioma del gráfico por el nombre: «Ing» delante o detrás (`Ing_…`, `…_Ing`), también pegado a la letra del
  tipo de figura (`GIng_…`, `CIng_…`), es inglés. Si el nombre no lo dice, también es inglés si el rótulo del
  gráfico es «Chart N» (`rotulo_en_ingles`). Si no, castellano. La app dice por qué lo ha decidido.
- Punto decimal en inglés: Excel pone el separador decimal según la configuración del Mac (en español, coma) y
  ningún formato de número del archivo lo cambia. **No se escriben las etiquetas como texto** (decisión del
  usuario): en inglés, si el Mac usa la coma decimal, los pasos 1 y 5 avisan en rojo de que hay que cambiarlo a
  mano (Ajustes del Sistema > General > Idioma y región > Formato de número; en Excel, «Usar separadores del
  sistema»). El separador se lee del Mac con `NSLocale` (`separador_decimal_mac`).

- **Ancho en Windows** (comprobado en Mac, 2026-11-26): lo que está dentro de la retícula queda con anclaje
  absoluto (gráficos, pastilla, títulos, FUENTES: `absoluteAnchor`; retícula y algún cuadro: `oneCellAnchor` en A1),
  así que su ancho no sale de las columnas y debería ser el mismo en Windows. Proporción trazado/pastilla igual que
  en los .ai (hechos en Windows; diferencia < 1 % en 1.1, 1.4 y 1.11); el .ai es un 3,7 % mayor en todo (escala de
  Illustrator). **Pendiente**: abrir un EXCEL de la app en Windows y comprobarlo.

## Pasos

Van en orden: cada paso exige que el anterior esté en la versión de la que parte (si no, el motor avisa).
Las versiones hechas cuando retícula y textos eran dos pasos («Retícula y pastilla» y «Textos») siguen valiendo.

1. **Retícula, pastilla y textos** (`paso1`, una sola versión; el motor hace primero la retícula y la
   pastilla y, sobre eso, los textos):
   - Si el autor lo ha agrupado todo con el gráfico (pastilla, títulos, gráfico, FUENTES: «G_26XX_06
     INTERVALOS»), primero se desagrupa: cada elemento, con la escala de su grupo, queda anclado a sus celdas en
     el mismo sitio (`desagrupar`). La retícula del autor (grupo de líneas) no se desagrupa.
   - Un título de panel numerado que el autor dejó dentro de un gráfico, como texto del gráfico (1.28, «2.28.b»),
     pasa a la hoja en el mismo sitio, con aviso (`sacar_titulos_de_graficos`).
   - **Formas vacías e invisibles dentro de los gráficos** (sin texto, relleno ni borde; restos de la plantilla del
     autor, casi siempre vinculadas a «#REF!» o a una celda vacía): se quitan, con un aviso por gráfico. Tapaban el
     gráfico y no dejaban seleccionar ni mover lo que había debajo (G_IA2025_2.5: «Rectangle 1» sobre toda la parte
     de arriba; petición del usuario, 2026-11-26; `forma_invisible`). Están en 93 de los 100 de Informe Anual.
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
   - Títulos de panel, en todos los gráficos y publicaciones (`dos_espacios_panel`): el número con letra
     siempre como **«N.x»**, con la letra en minúscula («1 a», «6.A.», «6.a)» → «1.a», «6.a»; «2.6.a» se queda), **2 espacios** entre
     él y el título (un espacio, tres, un tabulador o un espacio duro pasan a 2) y **sin espacios dobles**
     dentro del título. Funciona aunque el texto vaya repartido entre varias carreras de texto: cada letra se
     queda con su formato. Si el título viene en mayúsculas, pasa a minúscula con las reglas de las leyendas
     (salvo nombres propios, siglas y la primera letra): «2.a EVOLUCIÓN DEL CONSUMO PRIMARIO (b)» →
     «2.a  Evolución del consumo primario (b)». Las llamadas a nota («(b)»), que van en minúscula, no impiden
     reconocer un texto en mayúsculas (también en las leyendas).
   - **Sangría francesa** en los títulos de panel (todas las publicaciones; 2026-11-27, 8.2 b; `sangria_panel`): las
     líneas que siguen a la primera empiezan donde empieza el título, después de «8.2.b  », como en el .ai
     (`marL` = ancho del número y sus 2 espacios a 8 pt; `indent` negativo en el primer párrafo). Los saltos de línea
     manuales de un título con número de panel pasan a espacio, con aviso: en un título enlazado a una celda, Excel
     hace de cada línea un párrafo nuevo sin la sangría y la segunda línea volvía al borde (probado en Excel);
     partida por Excel, la sangría la alinea. «Gráfico 1⏎Título» de los recuadros (sin número de panel) no se toca.
   - Textos vinculados a una celda (`textlink`, casi todos los títulos de panel): al abrir, Excel **repone el
     texto de la celda** (comprobado). Si la app cambia el texto de un cuadro vinculado (de la hoja o de dentro
     de un gráfico), escribe el texto nuevo también en su celda (`escribir_vinculos`); solo los que ha cambiado
     ella. Si la celda es una fórmula, solo se cambia su valor guardado y hay aviso.
   - Si «Gráfico NN» y el título van en el mismo cuadro (dos párrafos), se parte en dos cuadros.
   - Número del gráfico (todas las publicaciones): el del **nombre del archivo**, que es el del .ai
     (`G_IA2025_1.1` → «Gráfico 1.1» / «Chart 1.1», aunque el autor escriba su «Gráfico 2.1»), y los títulos de
     panel de la hoja del gráfico con ese número («2.1.a» → «1.1.a»; también los que traen el número de otro
     gráfico por errata, «4.3.c» en el 3.3). Solo si el nombre lleva un número con punto (`G_DO26XX_01` no
     cambia); los recuadros (`Rec_…`) todavía no. Si el panel va vinculado a una celda, se cambia también en ella.
   - La pastilla del autor se reconoce aunque esté hasta 1 mm desplazada del origen (en el 2.6, 0,3 mm).
   - Leyendas en minúscula salvo siglas (y la primera letra, la de después de un punto, los nombres propios y
     los números romanos), solo si el autor las escribió enteras en mayúsculas («FRENTE AL EURO» → «Frente al
     euro», «ELECCIONES EEUU» → «Elecciones EEUU»). Las conjunciones y preposiciones cortas que el autor ya dejó en
     minúscula no cuentan («… 2002-2007 y 2022-2025»), ni las llamadas dobles («(a, b)», 1.33 b); el guion entre
     letras separa palabras («CLU-MANUFACTURAS» → «CLU-manufacturas»; «COVID-19» se queda), y son siglas también las
     palabras que el autor escribe en mayúsculas dentro de otra leyenda del mismo gráfico que no va entera en
     mayúsculas («PFEMP + margen…» → «PFEMP» se queda, 1.35 c; `SIGLAS_DEL_GRAFICO`), y en castellano tras dos puntos sigue minúscula («IAPC de
     servicios: evolución…», título del 1.31 a, como en el .ai). Una palabra en mayúsculas sin vocales (ni «y») es
     sigla aunque no esté en la lista («PTF», «FBCF», «MRR»; 3.1, `sin_vocales`). En las tartas y anillos la leyenda son las categorías: se les
     aplica lo mismo, en la caché y en sus celdas («ESTADOS UNIDOS» → «Estados Unidos», «MEXICO» → «México»:
     en español, los nombres propios que vienen sin tilde por ir en mayúsculas la recuperan, `CON_TILDE`; prueba
     «G_DO2608_06», paneles b y c). Una letra suelta entre paréntesis se deja («LTI (D)»: abreviatura). Listas de siglas y nombres propios en el motor (`SIGLAS`,
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
       Y dos decimales también si con uno se escribirían igual cifras distintas (0,84 y 0,80 → 0,8): el autor las
       quería distinguir (G_IA2025_1.17, 2026-11-26). Se mira en todo el panel, no serie a serie (3.6, panel a: 0,885
       de una serie y 0,933 de otra). Las etiquetas sueltas con formato propio pero sin formato de número reciben el
       del conjunto (si no, Excel las escribía con todos sus decimales: 0,933).
     - Etiquetas de datos **sin borde ni fondo**, en todas las publicaciones (`etiquetas_sin_marco`; petición del
       usuario, 2026-11-25: en el G_IA2025_1.1 el autor las puso en recuadros blancos con borde gris y en el .ai van
       sin nada). Solo la forma de las etiquetas; sus líneas guía no se tocan. Si una etiqueta no tiene forma
       propia, se le escribe una sin relleno ni borde.
     - Texto de las etiquetas (escrito o «Valor de las celdas», en la caché y en las celdas; `texto_de_etiqueta`):
       en minúscula si viene entero en mayúsculas, con las reglas de las leyendas («EDUCACIÓN (3.6%)» →
       «Educación (3,6 %)», G_IA2025_1.31), coma decimal en castellano (no la de millares) y las reglas de FUENTES.
     - Área del gráfico y área de trazado **sin fondo ni borde**, escrito siempre (`areas_sin_fondo`). Con el estilo
       del gráfico restablecido en Excel («Restablecer para hacer coincidir el estilo») desaparece el formato
       propio y Excel pone el del estilo: fondo blanco y borde gris en el área del gráfico y en las etiquetas
       (G_IA2025_1.1 MODIFICADO, 2026-11-26).
     - FUENTES: la diéresis «¨» usada como comilla de apertura también pasa a «« »» (G_IA2025_1.1). Las notas con
       letra se reconocen escritas «a.», «a:» (G_IA2025_1.17) o «a» + tabulador.
     - Texto de las etiquetas de datos con las reglas de FUENTES (`orto_texto`, `etiquetas_ortotipografia`;
       petición del usuario, 2026-11-25): en castellano comillas angulares y espacio de no separación entre cifra y
       % («10 %»); en inglés sin espacio; sin espacios dobles. El escrito en la etiqueta y el que sale de celdas
       («Valor de las celdas»: en la caché y en sus celdas, que Excel repone al abrir).
     - Etiquetas de tamaño fijo en las que ya no cabe el texto a 6 pt (Excel lo corta con «…»): en el paso 2,
       con el tamaño final del gráfico, crecen a lo alto (y a lo ancho si no cabe la palabra más larga):
       `etiquetas_que_caben` («no puede desaparecer texto», G_IA2025_1.1 «Aranceles a China, Canadá y México»).
     - Fechas: el código es el de la guía; Excel para Mac escribe el mes con el idioma del Mac y con es-US da
       «sept» (con es-ES, «sep.»), sea cual sea el código (probado: [$-1540A], [$-es-US,1], [$-540A], [$-2C0A]).
     - Trimestres → «I TR … IV TR» (es) / «Q1 … Q4» (en), con el año detrás: en leyendas, categorías (celdas y
       caché), textos de la hoja dentro de la retícula y textos de dentro de los gráficos. «IT» a secas, sin año,
       es Italia y no se toca (3.2 c: salía «I TR»).
     - Categorías con saltos de línea o espacios sobrantes al principio o al final («Jefatura⏎ »): se quitan, en la
       caché y en sus celdas, con aviso; Excel las contaba como otra línea y las cortaba («Jefatura…»,
       G_MemoriaSupervision_1.1).
     - Etiquetas de datos con formato de porcentaje en barras y líneas (el autor guarda fracciones): como en las
       tartas, los datos no se tocan, «%» como unidad (si no la hay) y aviso «eliminar el % de las cifras en
       Illustrator» (decisión del usuario, 2026-11-26; `etiquetas_con_porcentaje`).
     - Trimestres con el año solo en el primero («I TR 2022», «II TR», «III TR», «IV TR», «I TR 2023»…, en una
       columna; `trimestres_en_dos_niveles`, G_IA2025_1.33 c): en **dos niveles**, como en el .ai. Los trimestres
       quedan en la columna del autor, los años pasan a la columna de su izquierda (solo si está vacía; si no,
       aviso) y el eje los pone debajo, centrados bajo sus trimestres. Va como aviso: cambia las celdas del autor.
     - Eje horizontal: nunca en oblicuo. Horizontal (explícito, para que Excel no lo incline) si la palabra
       más larga cabe a 6 pt con 3 pt libres en su hueco (`HOLGURA_HORIZONTAL`: lo que Excel necesita para no
       saltarse etiquetas; con 5 pt, el 3.5 de Memoria, que venía en oblicuo, salía girado y en el .ai va en
       horizontal); si no, vertical de abajo arriba (`rot=-5400000`) a 7 pt (6 si no cabe una línea),
       partido en 2 o 3 líneas (saltos en las celdas) solo lo necesario para no pasar del largo de la etiqueta
       más difícil; si ni así cabe, aviso. «Tamaño y colocación» mide entonces las categorías por su línea más
       larga, más los niveles de debajo si las categorías tienen varios («1990-2018» en «G_DO2608_01»: si no
       se cuentan, Excel sube el trazado para que quepan y las unidades quedan dentro del gráfico). Se decide
       con el ancho final del trazado (columna 1, o las dos si va sin leyenda).
       Fechas y números (`direccion_fechas`; G_IA2025_1.31, que salía en oblicuo): se miden como los escribe el
       formato del eje («#,##0» → «-43») y con la distancia real entre etiquetas (en un eje de fechas, el salto va
       en meses o años). Si caben, horizontales; si no, verticales y, si el autor no fijó el salto, una cada 3, 6
       o 12 meses (o 2, 5, 10 años), la menor que deja aire. Datos diarios sin salto, o salto sin unidad: en
       horizontal y Excel elige qué fechas pone (1.1, 1.12, como en el .ai).
   - Título: si acaba en una letra, «(cont.)» o «(cont'd)» entre paréntesis, ese final va en Roboto Regular.
   - Formato local del autor: se respetan cursivas, subrayados, índices y la negrita de una parte del texto
     (también en «Gráfico NN» y el título, aunque tomen el marco de la plantilla). Si todo un texto va en
     negrita, se quita: el peso lo da la variante de Roboto.
   - **Todos los textos del gráfico, en negro** (norma general del usuario, 2026-11-05; sustituye a la de no
     tocar los colores del autor): los de la hoja dentro de la retícula (títulos, títulos de panel, unidades,
     FUENTES, textos sueltos) y los de dentro de los gráficos (ejes, leyenda, etiquetas de datos, títulos,
     textos de sus formas), en el paso 1 (`textos_en_negro`). El detalle dice qué colores había para revisar
     que ninguno estuviera así a propósito. No cuentan como cambio los negros escritos de otra forma (`tx1`,
     `dk1`, `black`, `windowText`); un `tx1` aclarado (gris) sí pasa a negro. La entrada invisible de la
     leyenda que pone el paso 2 (muestras anchas) sigue en blanco.
   - FUENTES con fórmulas de Office (ecuaciones, como en «G_DO26XX_04»): el cuadro va dos veces dentro de
     `<mc:AlternateContent>` (con la fórmula y en texto de reserva). Rehacer sus párrafos rompía el XML y Excel
     daba el libro por dañado en todos los pasos; ahora solo se cambia la letra (Roboto Light 7 pt; el rótulo
     en Medium, en las dos copias; las fórmulas, intactas) y se avisa para revisar a mano notas, líneas en
     blanco y comillas (`fuentes_con_formulas`).
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
   - **Leyenda que no cabe** (2026-11-26, G_IA2025_1.22): Excel dibuja el texto un 6 % más ancho que la suma de las
     letras (`TEXTO_EXCEL_MAS_ANCHO`) y, con el ancho justo, partía entradas en dos líneas y el alto ya no llegaba
     (desaparecían entradas). Excel reparte el cuadro a partes iguales entre las entradas y centra cada una: con
     entradas de varias líneas, 9 pt de aire entre ellas (`alto_entradas`). Si la leyenda no cabe en las 9 filas,
     el panel crece las que falten (en el 1.22, panel a: 11 filas) y se anota.
   - Leyenda: la muestra empieza **medio milímetro después de la línea de la columna 2** (petición del usuario,
     2026-11-25, G_IA2025_1.1: las muestras se metían en la línea). Medido en el PDF de Excel, con el cuadro 3 mm
     antes de la columna las muestras de una leyenda solo de líneas (anchas) empezaban 1,3 mm antes de la línea
     y las de una leyenda con barras (más estrechas, también con la muestra ancha « ») 0,2 mm antes; el cuadro
     se corre lo que toque (`MUESTRA_LINEA_ANTES`, `MUESTRA_BARRA_ANTES`) y el texto sigue sin pasar del final
     de la columna 2. Las de las tartas, como estaban. A la
     altura del comienzo del gráfico, con el ancho justo de su línea más larga (los nombres que no caben en
     la columna 2 se parten), para que vayan una debajo de otra. Medido en Excel: Excel **centra** las
     entradas si el cuadro es más ancho (por eso el ancho justo); la muestra de una serie de líneas mide unos
     16 pt más que la de columnas; cada entrada ocupa el alto de la más alta y Excel reparte lo que sobre, y
     si no caben todas quita las últimas. No cuentan las entradas borradas de la leyenda. El cuadro puede llegar
     hasta el **final de la columna 2** (`ANCHO_LEYENDA`; antes acababa 3 mm antes y partía en dos líneas entradas
     que caben en una, y Excel abría las entradas a todo el alto: G_IA2025_2.1, 1.33, 1.35, 2026-11-26).
     Si una entrada se parte se decide con lo que mide Excel de verdad (medido en sus PDF): el texto, como nuestra
     medida; del borde del cuadro al texto, 13 pt (y 16 más con muestra de línea); 3 pt a la derecha
     (`TEXTO_DESDE_BORDE`, `HUECO_DERECHA_LEYENDA`). El ancho del cuadro sigue con el margen del 6 % (1.22).
     Antes (margen del 6 % y 17 pt) partía entradas que caben y la leyenda se abría a todo el alto
     (G_MemoriaSupervision_4.5, 2026-11-27).
   - Muestras anchas en los gráficos solo de barras (agrupadas o apiladas; como «G_DO2608_06 TERMINADO
     LEYENDA», panel a): con solo barras Excel dibuja muestras cuadradas pequeñas donde la trama no se ve; si
     en la leyenda hay una línea, todas salen anchas. Se añade al final una serie de línea blanca de 2,25 pt,
     sin datos y llamada « », cuya entrada lleva el texto en blanco (`muestras_anchas`), antes de medir la
     leyenda. Si conviven barras y líneas visibles no se toca; las series de solo marcadores (línea o
     **Si el autor ya puso esa línea** (G_IA2025_3.6, «linea»: un dato, línea blanca y texto blanco en la leyenda,
     que se pierden al restablecer el estilo y la volvían una línea negra con su nombre en la leyenda): una serie de
     línea con un dato como mucho **y sin marcador** en un gráfico con barras no dibuja nada (con marcador sí: los
     extremos de los intervalos del 1.28 y 1.29), y se convierte en la de la app (sin
     nombre, línea blanca, sin estilo propio y sin datos; `muestra_del_autor`). También si tiene más datos pero
     todos son 0 y no tiene nombre (G_IA2025_3.7: se llevaba el negro y descolocaba los colores de las barras;
     1.21: con sus ceros, la línea blanca habría tapado el eje en 0). El nombre de una serie se busca solo en su
     `<c:tx>`: si su caché está vacía, antes se cogía la primera categoría («2000»).
     dispersión sin línea) no cuentan como línea, porque su muestra también es pequeña («G_DO2608_01»).
     Excel ordena la leyenda por tipos (barras, líneas, dispersión) sean cuales sean los ejes: si hay una
     dispersión, la muestra va como serie de dispersión con línea, detrás de su última serie (si no, queda
     un hueco antes de los marcadores, como en el 2.6 b). Con barras horizontales la línea va a unos ejes
     secundarios borrados (con los mismos ejes Excel rompe las categorías), y si ya hay ejes secundarios, a
     esos (Excel solo admite dos juegos: con un tercero da el libro por dañado); probado bien en un panel
     normal, pero no en uno de categorías a dos niveles girado a mano. El paso 5 no la colorea (`es_muestra`).
     El `<c:layout>` de la leyenda va detrás de los `<c:legendEntry>` (lo pide el esquema).
   - Barras horizontales («GIng_DO2626_05 HORIZONTAL»; `es_horizontal`):
     - El trazado se queda en la columna 1 aunque no haya leyenda, y el gráfico acaba al final de la última
       cifra del eje horizontal: como va centrada en el borde del trazado, el trazado acaba media cifra antes
       del final de la columna 1 (`media_ultima_cifra`, con el máximo fijo del eje o el estimado).
     - A la izquierda, las categorías (`ancho_categorias_izquierda`) y, si lo hay, el título girado del eje
       vertical: 2 mm antes de las categorías, a lo alto del trazado, a 7 pt.
     - Unidades: siempre texto horizontal, nunca un texto girado ni un número suelto como «(2)»
       (`es_unidad_grafico`). En barras horizontales son las del eje de valores: el texto de debajo del
       trazado o, si el autor las dejó arriba a la izquierda como en un gráfico vertical, ese texto (salvo un
       título «Gráfico N…» o «N.a …»; G_MemoriaSupervision_2.7 b: se quedaban arriba, cortadas). Van debajo de sus números (2 mm), en una línea, alineadas a la derecha al final del eje
       horizontal (no de la última cifra, que sobresale media cifra).
     - Números sueltos que el autor puso a mano junto a cada barra («(2)», «(4)»): pasan a ser la etiqueta de
       datos de su barra, con su mismo texto, «fuera, al final» y a 6 pt (`etiquetas_de_barras`): Excel la
       pone siempre a la derecha de la barra aunque cambie el tamaño. La barra se busca por la altura del
       número en la disposición del autor (si no la fijó, o con barras apiladas, aviso y se dejan).
     - Los demás textos sueltos del gráfico («Oracle, Amazon and Alibaba») se mueven con el trazado: su
       esquina conserva su sitio respecto al trazado y su tamaño en pt (`recolocar_formas`).
   - En los demás gráficos (no tartas), los textos y las líneas que el autor dibujó dentro del gráfico también
     se mueven con el trazado nuevo: los textos por su centro, con su tamaño en pt; las líneas se estiran de
     extremo a extremo (G_IA2025_3.2 c: los promedios y sus líneas se quedaban sobre otras barras; 1.8: las
     flechas siguen señalando su barra). No se mueven las unidades ni los títulos girados.
   - **Sin eje vertical visible** (borrado o sin cifras; G_IA2025_3.6, cifras sobre las barras, 2026-11-26): no se
     reserva sitio para sus números y el trazado empieza al principio de la columna 1 (`ancho_numeros_eje`).
   - **Escala del eje de valores: el gráfico puede aumentar de tamaño** (`avisos_escala`, paso 1; petición del
     usuario, 2026-11-27, G_MemoriaSupervision_2.6). Avisan (a veces el autor iguala la escala de varios paneles),
     salvo el primer caso, que la app corrige. Los datos son los del eje y los de los ejes de valores ocultos; en las apiladas, la suma de
     cada categoría (positivas y negativas aparte; también para `escala_eje`):
     - Solo un extremo fijado y el salto automático, con el otro extremo lejos de 0: Excel elige el otro extremo y
       los saltos según el alto y puede dejar tramos vacíos (2.6 b: mínimo −60; Excel, saltos de 50 hasta 90;
       el .ai, de −60 a 60 con saltos de 20): **la app fija la escala justa** (mínimo, máximo y salto), con aviso
       (decisión del usuario, 2026-11-27: mejor que solo avisar).
     - Mínimo o máximo fijado con al menos un tramo entero sin datos (con el salto que pondría Excel): cuántos y
       qué valor podría tener (`tramos_vacios`; 3.6: 800 con el dato más alto en 662).
     - El eje que se ve no tiene datos y las series van en un eje oculto con otra escala: los números no
       corresponden a los datos (2.6 a: visible de −10 a 15, oculto de −15 a 15).
   - **Eje vertical a la derecha** (2026-11-26, G_IA2025_2.1): si es copia exacta del izquierdo (mismo mínimo, máximo
     y formato; el salto igual o automático), se **quita** con aviso, porque repite la información y en el .ai no
     está; queda borrado con la escala del izquierdo fijada, para que sus series no se muevan
     (`quitar_eje_derecho_duplicado`). Si tiene otra escala, se queda y el trazado se estrecha lo que ocupan sus
     números, para que todo quepa en la columna 1 (`ancho_numeros_derecha`).
   - **Última categoría dentro de la columna** (`media_ultima_categoria`, 2026-11-26, G_IA2025_2.6): en líneas y áreas
     con las categorías sobre las marcas (`crossBetween midCat`), la última categoría («2025») y la etiqueta de su
     punto («22,4») van centradas en el borde derecho del trazado y sobresalían la mitad de la línea de la columna:
     el trazado se acorta esa mitad (la mayor de las dos), como en el .ai. Fechas: con el ancho de «sept-25».
     La etiqueta del último punto se mide con su formato («85,29», no «85,3») y su posición: en líneas y
     dispersiones Excel la pone por defecto a la derecha del punto, entera fuera; si el autor la movió a mano,
     cuenta su desplazamiento (`sobresale_etiqueta`, G_IA2025_2.3, 2026-11-26).
   - Fechas en vertical: el alto de debajo del eje se calcula con lo que mide la fecha más larga en vertical
     (antes solo para categorías de texto; en el 2.3 Excel las cortaba, «m…», o las partía, «mar / -71»).
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
     deducido de Illus quedaba pegado a la pastilla); sin título de panel, el panel 1 empieza donde en Illus. Si es el
     único gráfico y no tiene título de panel, todo (unidades, gráfico, leyenda, textos interiores, FUENTES y notas)
     va **3 mm más abajo** (`BAJADA_SOLO_SIN_TITULO`; petición del usuario, 2026-11-27, Memoria de Supervisión).
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
   - Ejes ocultos: no se tocan, salvo sus líneas de división, que se quitan (sin eje no van; aviso;
     G_MemoriaSupervision_3.2, como en el .ai; decisión del usuario, 2026-11-27).
   - Marcas de graduación: horizontal en Cruz si el eje que cruza tiene negativos, si no Interior; vertical
     siempre Interior (en dispersión, Cruz si hay negativos). Secundarias Ninguno. Si el eje horizontal queda
     arriba (todo negativo), principal y secundaria Exterior. Una marca por valor en el eje horizontal; si las
     etiquetas van saltadas («una cada 4»), las marcas con ellas (G_IA2025_3.1 b: 104 trimestres, una marca por
     año como en el .ai; antes llenaban el eje).
   - Líneas de división: van con el eje de valores. Si el autor las puso en el eje de categorías y el de valores
     no las tiene, pasan a este, con aviso (`divisiones_al_eje_de_valores`; G_MemoriaSupervision_3.4, barras
     horizontales: eran horizontales entre categorías y en el .ai y el TERMINADO son verticales).
   - Etiquetas en Bajo (ejes horizontales y, en dispersión, también el vertical; si el eje que cruza va invertido,
     «maxMin», en Alto, que es lo que queda abajo: 3.4, categorías de arriba abajo) y, en el eje de categorías,
     a distancia 100 (en el de valores Excel no tiene ese ajuste).
   - Eje cortado: un máximo fijo sube y un mínimo fijo baja al siguiente tramo del intervalo (55 → 60 de 10
     en 10), para cerrar con una línea de división. Si el intervalo es automático, solo avisa.
   - El eje de valores cuenta como «con negativos» también si baja de 0 sin datos negativos: con el máximo fijo y el
     mínimo automático, Excel baja el mínimo para que los saltos acaben en el máximo (130 con saltos de 20: de −10
     a 130, G_IA2025_1.1; `escala_eje` lo calcula así). Entonces el horizontal cruza en 0 con marcas en Cruz
     (petición del usuario, 2026-11-25).
   - Los ejes ocultos no se tocan (como en el TERMINADO 2.6).
   - **Eje sin cifras** (`tickLblPos none`, 2026-11-26, G_IA2025_1.14 panel a): sin línea ni marcas. El autor los
     tiene para apoyar series vacías u otra escala y los escondía con una línea invisible, que se pierde al
     restablecer el estilo: salían grises y con marcas a la derecha del gráfico.
   - Dispersión: solo cuando el grupo `scatterChart` va sobre dos ejes de valores; en un gráfico combinado
     (columnas + puntos) la dispersión puede ir sobre el eje de categorías y no cuenta.
   - Comprobado con «G_DO26XX_2.6 EJES ORIGINAL/TERMINADO.xlsx»: los ejes quedan idénticos al TERMINADO.
   - El TERMINADO no sigue la guía en el panel 3: Cruz sin negativos y una marca cada 2 categorías.
4. **Líneas interiores** (`paso4`). Línea base, líneas divisorias y flechas.
   - Línea base (guía de gráficos, pág. 13, interactiva: el texto está en Esp-Base_0n). Si las
   unidades de un panel (de la hoja o de dentro del gráfico) indican un dato de referencia — «Base 100 = …»,
   «100 = …», «… = 100», o con 50 —:
   - Si el autor ya dibujó esa línea como una serie más (todos sus valores 100 o 50, dentro del rango de los datos:
     «cien» del G_IA2025_3.2 a), esa serie pasa a ser la línea base (nombre «Base 100», gris, oculta en la leyenda,
     fuera de los colores), con aviso, y no se añade otra; también sin referencia en las unidades
     (`linea_base_del_autor`). Fuera del rango de los datos es un auxiliar del autor y no se toca («linea_100» del
     2.5 y el 1.36). La leyenda ya no le reserva sitio en el paso 2.
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
     rombo 6. Recta de referencia de una dispersión (dos puntos, la diagonal del 1.31 a): ocupa su lugar en el
     orden pero va de **1 pt**, sin marcadores (como en el .ai; `es_recta_referencia`).
   - Orden (guía de gráficos, pág. 7), en cada panel: primero las líneas, luego áreas y barras (en el orden de
     las series: de izquierda a derecha o desde el eje hacia arriba) y al final los marcadores (series de
     dispersión o de línea sin línea: sólido de 5 pt sin borde, del color de su estilo, con la **forma del autor**; si
     la dejó en automático, la que pone Excel por el número de la serie —la primera, rombo— y círculo solo si no hay
     forma que respetar: decisión del usuario, 2026-11-26, G_IA2025_1.31; `forma_marcador`). Las formas de raya
     (raya, aspa, cruz, asterisco) van de 7 pt, que a 5 casi no se ven (1.35 c). Si el tamaño cambia respecto al del
     autor, aviso.
   - **Promedios, medias y tendencias** («Promedio 1996-2019», «Media…», «Tendencia España», «Average»; no las medias móviles): por norma van
     discontinuos y del color de la serie a la que se refieren. La app no sabe a cuál, así que les da el estilo de
     la secuencia y **avisa** para revisarlos a mano (`es_promedio`; petición del usuario, 2026-11-26, 1.35 a). Tartas: un
     estilo por sector, en el orden de la leyenda.
   - No se tocan: la línea base, las series de columnas que hacen de línea divisoria, las invisibles y las
     ocultas en la leyenda. Las barras llevan `invertIfNegative` 0 (si no, los negativos salen en blanco).
   - Puntos (`dPt`) que el autor pintó con el mismo color que su serie (en «G_DO2608_01», las primeras barras
     de la OCDE y Alemania): se les quita ese relleno para que lleven la trama de la serie, como en el
     TERMINADO (`puntos_como_su_serie`). Los que tienen otro color o algo más (borde) no se tocan.
   - Marcadores ocultos en la leyenda que el autor hizo iguales (mismo símbolo y color) a una serie de
     marcadores visible (los «…_rombo» del 1.b de «G_DO2608_01»): llevan el mismo estilo que ella, para que
     en el panel no haya dos marcadores distintos (`firma_marcador`).
   - Aviso en rojo a partir de la 8.ª serie (la guía recomienda 5; con 8 o más la secuencia se repite) y si
     una serie tiene puntos con formato propio del autor que no repiten su color (no se tocan).
   - Trampa: el `idx` de `<c:legendEntry>` es la posición en la leyenda (grupos en su orden y, dentro, como van
     escritas las series en el gráfico, no por `order`: en el G_IA2025_1.33 a no coinciden y Excel sigue el orden
     escrito; el orden de los estilos también), no el `idx` de la serie (`orden_leyenda`). Arreglado también en la línea base y en las medidas
     de la leyenda del paso 2.
   - **Misma serie, mismo estilo en todos los paneles** (petición del usuario, 2026-11-26, G_IA2025_1.12): una serie
     que se llama igual que otra de un panel anterior lleva su mismo estilo, aunque el autor la ponga en otro orden;
     las demás se reparten los estilos libres en el orden de la guía (`fijos` en `tramas_y_lineas`).
   - **Barras apiladas con parte positiva y negativa** (2026-11-26, G_IA2025_1.27): el orden de los colores es primero
     el de las series que suben desde el eje (en su orden) y después el de las que bajan; luego el resto.
   - **Etiquetas dentro de una trama oscura** (la negra de la guía; luminancia media de sus dos colores < 0,4): en
     blanco (`etiquetas_claras`); también dentro de la trama verde de la guía (7DB749; petición del usuario,
     2026-11-27, G_MemoriaSupervision_7.3). Las de fuera de la barra (`outEnd`) siguen en negro.
   - Marcadores: siguen la secuencia de colores de la guía (decisión del usuario, 2026-11-26), aunque en algún .ai
     el editor los pusiera en negro (1.22, panel a: rombos negros; la app, rombo del color que toque).
   - **Series ocultas en la leyenda** (2026-11-26, G_IA2025_1.22 panel b, «Total»): se ven en el gráfico y llevan su
     estilo en el orden de la guía (antes se quedaban con el color de Excel). Los marcadores ocultos, aparte.
   - «Mismo nombre, mismo estilo» solo entre series del mismo tipo (en el 1.22, «Total» son marcadores en el panel a
     y una línea en el b).
   - Series sin ningún dato (rango vacío, «Línea 4» y «Línea 5» del 1.12): no se ven y no cuentan para el orden
     ni para el alto de la leyenda (Excel no las enseña; en el 1.14 separaban las entradas del panel a).
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

### Paneles lado a lado (Memoria de Supervisión: 2.1, 2.9, 3.1, 3.2, 3.3, 3.5, 8.1, 8.2, 8.3, 8.4; 2026-11-27)

En todas las publicaciones (los recuadros «Rec_…», no: se dejan para el final). Control «Paneles», al principio de
la tarjeta de los pasos, para elegirlo antes del paso 1 al ver el gráfico (`filas_segun_modo`, orden `paneles`;
peticiones del usuario, 2026-11-27): «Automático» (lo detectado),
«Lado a lado» (también los que el autor apiló, en filas de dos en su orden de arriba abajo: para los que no caben
al publicar; un panel solo en su fila, con número impar de paneles, va a todo el ancho de la retícula) o
«Apilados» (uno debajo de otro, como siempre). Se guarda en el estado del trabajo; al cambiarlo, la app vuelve
a la copia exacta y rehace los pasos de maquetación que estaban hechos (la retícula es del paso 1); se pierden
las versiones de las herramientas y los cambios a mano (lo pregunta antes).
Cuando en la hoja hay dos o más gráficos a la misma altura en mitades distintas (`filas_de_paneles`; los que miden
menos de 25 mm de alto o cuya leyenda lo ocupa todo son «solo leyenda»; no cuentan los de fuera de la página):

- Paso 1: la retícula es la de los recuadros («Recuadros_Gráficos_Titulo 1», dos columnas iguales de 76,86 mm separadas
  5,04 mm y sus filas; `hoja_lado_a_lado` y `grupo_lado_a_lado` en publicaciones.json). La pastilla, «Gráfico NN», el
  título y FUENTES, como siempre (decisión del usuario). Se sacan a la hoja el título propio de un gráfico
  (`<c:title>`) numerado como título de panel (3.2) y los subtítulos numerados («1  Número…», 8.1, `RE_SUBPANEL`).
  Un título de panel con solo la letra («a  Número de operaciones», 8.3) lleva el número del gráfico («8.3.a  …»).
  Los textos sueltos (unidades, centro de una tarta) van con el gráfico en cuya caja caen, no solo con el más
  cercano a lo alto.
- Paso 2, por filas: cada panel en su columna (como si fuera la columna 1), los de una fila a la misma altura y
  debajo del título más largo de la fila (los ejes quedan alineados, 8.2). Los paneles de una fila, del mismo
  alto: las filas y el sitio de las categorías, los del que más necesite; el final del trazado queda a la misma
  altura y las leyendas de debajo empiezan en la misma línea (3.2, como en el .ai; petición del usuario). Con título de fila («8.1.a …») y
  subtítulos por panel, el título va a lo ancho y los subtítulos encima de su panel. FUENTES, debajo de la última
  fila, a lo ancho.
- Leyendas (decisiones del usuario), por fila (`plan_leyendas_fila`):
  - Si la leyenda va en gráficos aparte (2.1, 3.5, 8.1, 8.3): debajo de la fila, juntos y centrados, con su
    trazado invisible (`sin_trazado`); las leyendas de los paneles, fuera.
  - Para compartir leyenda tienen que coincidir el texto y los colores (petición del usuario, 2026-11-27): las
    entradas, con su nombre y su tipo (línea, trama o marcador) y en el mismo orden (`firma_leyenda`); el paso 5
    da el mismo estilo a la serie del mismo nombre y tipo, así que los colores coinciden. En las tartas, las
    categorías y su orden. Un panel sin leyenda la comparte solo si sus series son del mismo tipo y en el mismo
    orden (sus colores van por orden: 8.2 b); si no, cada panel se queda con lo suyo y aviso.
  - «Mostrar unidades» del eje de valores (miles…, 8.2 b): los números del eje y las etiquetas de datos se miden como
    los escribe Excel, en esas unidades («320», «285,1»); si no, el trazado empezaba tarde y acababa antes.
  - La leyenda común centrada lleva 12 pt de holgura: sin ellos Excel pasaba «Compras en TPV» (8.2) a una segunda
    fila que no se ve, y la app no puede saberlo para avisar.
  - Mismas series en los paneles (o solo uno la tiene; 8.2): una leyenda común debajo de los paneles, entradas en
    horizontal y la fila centrada en el ancho de la retícula; el gráfico del primer panel se ensancha a las dos
    columnas para llevarla; las de los demás, fuera (aviso).
  - Series distintas (8.4, 3.2): cada panel su leyenda debajo, alineada a la izquierda desde su eje vertical, con
    las entradas de izquierda a derecha y después hacia abajo (el orden natural; petición del usuario,
    2026-11-27); a la misma altura en los paneles de la fila (miden lo mismo). Excel centra las entradas en el
    cuadro de la leyenda y no deja la primera muestra pegada a su borde: el cuadro se hace del ancho justo de las
    entradas (medidas en el PDF de Excel; más justo, la serie invisible de las muestras anchas salta de fila, y con
    una entrada por fila Excel parte el texto si no lleva 8 pt de más) y se coloca de modo que la primera muestra
    caiga en el eje (a qué distancia del borde la dibuja Excel, medido según las entradas: PRIMERA_MUESTRA…). Sin
    eje con cifras, el trazado empieza a esa distancia del borde del marco en vez de pegado, para que cuadren.
  - Tartas con categorías distintas (2.9, 3.3): anillo de 8 filas a la izquierda de su media página y la leyenda a
    la derecha, centrada a su altura.

### Comprobación en Excel al terminar el paso 5 (`comprobar`, 2026-11-27)

Excel esconde sin avisar lo que no le cabe: una entrada de la leyenda que pasa a una fila que no se ve (8.2,
«Compras en TPV»), un texto cortado con «…» (8.4 b), categorías que se salta (3.5 a 7 pt). Comparando los
archivos no se nota (el XML sigue teniéndolo todo), así que al terminar el paso 5 la app pide a Excel que exporte
el libro abierto a PDF (en la carpeta de Office, donde Excel escribe sin pedir permiso; el libro no cambia), lee el
texto de cada página con PDFKit y se lo pasa al motor (`comprobar <trabajo> <texto>`, páginas separadas con \f). El
motor elige la página de la hoja «Gráfico» (la que tiene más textos de sus formas: Excel exporta el libro entero, y
en la hoja de datos salen los nombres de las series) y mira que estén enteras, sin espacios ni saltos, todas las
entradas visibles de las leyendas y las categorías de texto de los ejes (respetando `tickLblSkip`), contando
repeticiones entre paneles; y cualquier «…» que no sea del autor. Lo que falte, «Aviso:» en el detalle de la
versión (se rehace si se repite). La primera vez macOS puede preguntar si la app puede acceder a datos de otras
apps (la carpeta de Office): hay que permitirlo.

### Decimal que no aporta (paso 1, 2026-11-27)

Si las etiquetas de datos de una serie llevan decimales y todas sus cifras (como las escribe Excel, con las
unidades del eje: «285,1» en el 8.2 b) pasan de 100, aviso por panel: el decimal no aporta, ¿quitarlo? Solo avisa:
los decimales los sigue decidiendo la guía.

Si el decimal sale 0 en todas las cifras con etiqueta de la serie («130,0», «3.817,0», con las unidades del eje), se
quita directamente (`decimal_cero`, 2026-11-27), con aviso. Si así quedan como las tenía el autor (la regla de la
guía les había puesto el decimal: cuenta los decimales de los datos en bruto, sin las unidades del eje), ni cambio
ni aviso.

### Herramienta «Sin leyenda: gráfico solo en la columna 1» (`solo_columna_1`, 2026-11-26)

Botón de «Excepciones a los gráficos». Cuando el paso 2 avisa de que un panel va sin leyenda (o la tiene oculta)
y su gráfico ocupa las dos columnas (G_IA2025_1.11): el trazado vuelve a acabar al final de la columna 1 (el marco
del gráfico no cambia), los textos sueltos del gráfico se mueven con él (`recolocar_formas`) y las etiquetas del
eje horizontal se recalculan para el ancho nuevo con las reglas del paso 1 (`cuerpo_categorias`: 7, 6,5 o 6 pt;
`direccion_categorias`: en vertical solo si no caben ni a 6 pt). Ni tartas ni barras horizontales (ya van en la
columna 1). El trazado acaba antes si a la derecha sobresale la última categoría o la etiqueta del último punto,
para que también quepan en la columna 1 (2.3, «85,29»). Deja una versión nueva (⌘← para quitarla). En el 1.11: de 155,5 a 106,6 mm y categorías a 6 pt (con
el trazado más estrecho Excel se saltaba tres).

### Sin eje vertical, valor sobre cada barra (apartado «Excepciones a los gráficos», en la tarjeta de los pasos)

Para los gráficos de barras verticales que lo pidan (modelo: «G_DO26XX_04 TERMINADO ORIGINAL»). Motor:
`sin_eje_vertical`; deja una versión nueva sobre la elegida (después de «Tamaño y colocación»; mejor al final).

- El eje de valores vertical se borra, sin líneas de división ni marcas (`quitar_eje_vertical`).
- Cada serie de barras lleva su valor encima («fuera, al final»), en Roboto 6 pt negra, con los decimales de
  los datos del autor y separador de miles (como el TERMINADO: 0,33 y 29,67).
- Si dos etiquetas vecinas quedan casi a la misma altura y se tocan (las barras son más estrechas que los
  números), se apartan en horizontal lo justo, cada una hacia su lado (`separar_etiquetas_barras`).
- El trazado empieza al principio de la columna (ya no hay números a la izquierda) y las unidades van a su
  borde izquierdo (las de dentro del gráfico y las de la hoja).
- Barras apiladas: aviso y sin tocar (Excel no admite «fuera, al final» en cada tramo). Si el gráfico tiene
  además líneas o áreas a la vista, aviso. Sin ningún panel de barras verticales sin apilar, error.

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
  y se borra al cambiar de versión. Solo lo que sale de comparar: los avisos de los pasos 1 a 5 ya no se repiten
  aquí (están en «N avisos en esta maquetación» y en cada versión; 2026-11-27). Se hace sola al terminar el paso 5
  (tras la comprobación en Excel) y, con o sin el botón, pone en Excel la copia de trabajo (la que esté abierta, la
  normal o la « (2)») encima del original del autor, en el sitio de la copia, en la hoja del gráfico desde A1 y con
  el mismo zoom (el que encuadra la retícula): para pasar de uno a otro (`abrirParaComparar`, como desde el Finder). Trampa: `difflib` con `autojunk` (por defecto) da parecidos muy bajos en
  textos de más de 200 caracteres (FUENTES con notas): siempre `autojunk=False`.
- **Guardar como EXCEL** (`terminar`; antes «Guardar como TERMINADO», cambiado a petición del usuario el
  2026-11-25, como en Cuadros Excel BdE): si la copia abierta en Excel tiene cambios sin guardar, los guarda
  sola (AppleScript `save workbook`, sin ⌘S; 2026-11-26) y lo anota en la actividad; pide confirmación; cierra en Excel; copia lo guardado como «… EXCEL.xlsx» junto al original
  («ORIGINALES»/«ORIGINAL» del nombre pasan a «EXCEL», o se añade « EXCEL» al final; si ya existe no se pisa:
  « (2)», « (3)»…) y borra las dos copias de trabajo y la carpeta «(pasos)». El original del autor no se toca.
  Si en la versión elegida no se han dado todos los pasos (p. ej., guardado en «Ejes»: las series quedan sin su
  formato y Excel las pinta con su estilo, con remate redondo, G_IA2025_1.4), avisa antes de qué pasos faltan y
  pide confirmación («Guardar igualmente»; `pasosQueFaltan`, 2026-11-26).
  Ya no abre nada en Excel al acabar (2026-11-27): los dos libros se superponen al comparar. Cierra también en
  Excel el original del autor que abrió la comparación, sin guardar (`cerrarOriginal`).

### App actualizada (2026-11-25, como en Cuadros Excel BdE)

Cada 10 s la app mira si su ejecutable es más nuevo que su arranque (se ha compilado o instalado después de
abrirla) y, si lo es, enseña en la cabecera una cápsula naranja: «Hay una versión nueva de la app: ciérrala (⌘Q) y
vuelve a abrirla».

### Avisos y cambios en un solo sitio (2026-11-26, petición del usuario)

- **«Cambios de la versión»** (en «Adelante y atrás») es el único sitio con el detalle: los avisos arriba, siempre a
  la vista (o «Sin avisos» en verde), y los cambios plegados bajo «Ver los N cambios».
- **La actividad** ya no repite el detalle: una línea por tarea («⚠ 12 cambios · 1 aviso → ver «Cambios de la
  versión 3»»), que al pulsarla va a esa versión (marca `⟦version:N⟧`). La comparación, igual («⚠ 2 avisos → ver
  «Comparación con el original»»). Los errores se siguen escribiendo enteros.
- **Globo rojo «⚠ N»** en el botón de cada paso (y de cada herramienta) con avisos: al pulsarlo, la app va a la
  versión de ese paso.
- **Cabecera**: «N avisos en esta maquetación» (los de todas las versiones hasta la elegida); al pulsarlo, una
  ventanita con todos, su paso y sus dianas.

### Resaltes en rojo (2026-11-26, como en Cuadros Excel BdE)

El motor marca entre ⟪ ⟫ lo que hay que señalar (`con_resaltes`, en `marcar_detalle` y `marcar_comparacion`) y la
app lo pinta en rojo y negrita sobre fondo rosado (`conResaltes`), en «Cambios de la versión», en la comparación y
en la actividad: en los cambios «antes» → «después», solo lo que cambia (`resaltar`, letra a letra, con los
espacios a la vista: ␣ espacio, ⍽ espacio que no parte, ⏎ salto de línea); en los avisos, el texto al que se
refieren (lo que va entre «») y, en el de septiembre, «sept».

«Comparar con el original» empieza con los **avisos de todos los pasos** hasta la versión elegida («Aviso (paso 1,
«Retícula, pastilla y textos»): …», con su diana): la app solo enseña los de la versión en la que se está y al
llegar al final no se veían (el «sept» del paso 1 del G_IA2025_1.6).

### Avisos que se ven en Excel (2026-11-25, como en Cuadros Excel BdE)

Las líneas del detalle que hablan de un panel («Panel 2: …», «Aviso: panel 2: …», «Aviso: el panel 2 …») y los
avisos de FUENTES llevan al final una marca invisible «⟦forma:hoja|k|nombre⟧» (`marcar_detalle`, al guardar cada
versión). La app la quita al mostrarlas y pone una diana: al pulsar la línea (en «Cambios de la versión» o en la
actividad), Excel pasa delante y selecciona esa forma en la hoja del gráfico, sin tocar el archivo. La forma va por
su número en la hoja (el orden del dibujo, el mismo que «shape k» en Excel; comprobado con el 1.13) porque los
autores repiten nombres (los cuatro gráficos del 1.13 se llaman «Chart 1»); si no casa, por su nombre. Los paneles
se cuentan como en cada paso: en el 1, en el orden del dibujo; en los demás, de arriba abajo.

También en «Comparar con el original» (`marcar_comparacion`): los datos que faltan o cambian llevan
«⟦celdas:hoja|B9 B10⟧» (Excel selecciona esas celdas en su hoja; «;» o «,» según el idioma de Excel), los cambios
de formato de un eje y las series, el gráfico, y los textos, el cuadro o gráfico donde están (primero los cuadros
de la hoja y el texto suelto: «1.1» va a «Gráfico 1.1», no a «1.1.a»).

Septiembre: con el código de la guía, Excel para Mac escribe «sept» (comprobado: los otros once meses salen con 3
letras, y en inglés todos). Si un eje de fechas en castellano tiene septiembre, el paso 1 avisa («Aviso: panel N:
…»).

### Gráficos de tarta (guía, págs. 16 y 17; prueba: «G_MemoriaSupervision_2.3 CIRCULAR»)

Tartas, anillos y subgráficos (`pieChart`, `pie3DChart`, `doughnutChart`, `ofPieChart`):
- Paso 1: anillo con agujero del 80 %; líneas del subgráfico en blanco matiz 5, 1 pt, remate plano y unión en
  ángulo. Si las etiquetas llevan %, **en todos los gráficos circulares** (decisión del usuario, 2026-11-26,
  G_IA2025_1.9; sustituye a la de pasar los datos a 0-100 y quitar el % del formato, que con etiquetas de
  «Porcentaje» dejaba 0,2 en vez de 23,1): los datos del autor no se tocan, las etiquetas se quedan con su %, se
  pone «%» como unidad arriba a la izquierda si no está y aviso en rojo «eliminar el % de las cifras en
  Illustrator».
  Sectores a 0: no se ven y no gastan color; la secuencia sigue con el siguiente que se ve, como en el .ai
  (G_MemoriaSupervision_3.1: en el panel a «Negocio» vale 0 y «Capital» va en negro), y salen de la leyenda;
  aviso. Sin ningún dato guardado en el gráfico, no se salta ninguno (`puntos_tarta`).
  El texto del hueco del anillo («2,3 billones de euros»), como en el TERMINADO: la cifra en Roboto Black
  24 pt (negrita) y el resto en Roboto Regular 7 pt, centrado, y el cuadro sin relleno ni borde (probado con
  «… ORIGINAL MODIFICADO», que lo trae con otras fuentes, tamaños y fondo rojo).
  **Centro de los gráficos circulares, en todas las publicaciones** (petición del usuario, 2026-11-27): si en el
  centro hay una cifra con un texto, en la misma caja (también en la misma línea: «944 personas», «135 Total») o en
  cajas separadas, en la hoja o dentro del gráfico, el paso 2 los junta en una sola caja: la cifra en una línea,
  Roboto Black 24 pt, y el texto debajo, Roboto Regular 7 pt, centrados entre sí y en el centro del círculo
  (`cuerpo_centro_tarta`, `medidas_centro_tarta`). Una cifra sola, igual (24 pt).
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

## Macros personales de Excel (Mac)

`PERSONAL.XLSB` (Windows) adaptado a Mac en `macros/MacrosBdE.bas` (2026-11-05): 18 macros (tramas y colores
de serie, líneas y marcadores, Roboto Light/Medium/Regular, «PlanosIngles») con sus atajos. Cambios para Mac:
- El tema de colores BdE_2026 se carga en Mac desde la carpeta de temas de Office (`…/User Content.localized/
  Themes.localized/Theme Colors/BdE_2026.xml`, sacada de `Application.StartupPath`); en Windows, de `Y:\` como
  antes (`#If Mac`). Si no está, la macro sigue (`CargarTemaBdE`).
- «PlanosIngles» ya no usa `VBScript.RegExp` (solo Windows): «Q3 2024» → «2024 Q3» con `TrimestreDetras`.
- Textos con tilde en `ChrW(…)` (el editor de VBA de Mac no lee bien la codificación de un .bas).

Instalado como libro personal de macros: «Personal Macro Workbook» (binario, oculto) en
`~/Library/Group Containers/UBF8T346G9.Office/User Content.localized/Startup.localized/Excel/`; Excel lo abre
al arrancar. Para cambiarlo: editor de VBA → «VBAProject (Personal Macro Workbook)» → quitar el módulo e
importar el .bas de nuevo → ⌘S. Atajos: en Windows Ctrl+Mayús+letra; en Mac los muestra Herramientas › Macro ›
Macros › Opciones. No mandar pulsaciones de teclado por System Events con el usuario delante: van a la ventana
que tenga en primer plano.

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
- `app/compilar_app.sh` → `Gráficos Excel BdE.app` en esta carpeta (no va a git) y, si está instalada en
  Aplicaciones, también la de `/Applications` (2026-11-25). Allí no tiene el motor al lado: lo busca con
  `defaults write es.estudioencuadre.graficos-excel motor "/Volumes/DATOS/Proyectos Codex/Graficos Excel BdE/motor"`
  (ya puesto). El motor se usa siempre desde esta carpeta: sus cambios no piden recompilar.
- `app/crear_icono.swift` dibuja el icono (degradado verde-azul de «Maquetar» y «Versiones» con unas barras);
  `compilar_app.sh` lo convierte en `app/icono.icns` si no existe (para rehacerlo, se borra el .icns).
