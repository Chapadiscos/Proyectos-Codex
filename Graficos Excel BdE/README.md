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
- Idioma del gráfico por el nombre: «Ing» delante o detrás (`Ing_…`, `…_Ing`) es inglés; si no, castellano.

## Pasos

Van en orden: cada paso exige que el anterior esté en la versión de la que parte (si no, el motor avisa).
Las versiones hechas cuando retícula y textos eran dos pasos («Retícula y pastilla» y «Textos») siguen valiendo.

1. **Retícula, pastilla y textos** (`paso1`, una sola versión; el motor hace primero la retícula y la
   pastilla y, sobre eso, los textos):
   - Retícula y pastilla: borra la retícula y la pastilla del autor y pone las del archivo de retículas
   (`SdE_Reticulas_Publicaciones_ImagenNueva2024_Roboto.xlsx`, hoja «Gráfico»), en A1 y al fondo, con el
   color de la publicación. La retícula va a su tamaño de diseño (16,63 × 24,78 cm).
   - Textos: todo en Roboto, sin negrita (el peso lo da la variante):
   - «Gráfico NN»: Roboto Regular 7 pt; título: Roboto Medium 8,5 pt. Los dos toman el marco de la plantilla
     (`marco_grafico` y `marco_titulo` en la configuración): posición, tamaño, márgenes y letra, con el texto
     del autor.
   - Títulos de panel 8 pt; ejes, leyendas y unidades 7 pt; interior del gráfico (etiquetas de datos, tabla
     de datos, lo que no tenga letra propia) 6 pt; FUENTES Roboto Light 7 pt. Donde los dejó el autor.
   - Cómo se reconoce cada texto: «Gráfico NN» por su texto; el título, el que empieza dentro de la pastilla;
     FUENTES, el que empieza por «FUENTE»/«SOURCE»; el resto de cuadros de la hoja, títulos de panel. Dentro
     del gráfico, los cuadros de texto del 20 % de arriba son unidades y el resto, interior. Lo que queda
     fuera de la retícula (el «Más info») no se toca.
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
   - Leyenda: empieza en la columna 2 (el cuadro, 3 mm antes, por el aire que deja alrededor del texto), a la
     altura del comienzo del gráfico, con el ancho justo de su entrada más larga, para que vayan una debajo de
     otra.
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
  `maquetar_excel.py empezar|estado|ir|reiniciar|paso1|paso2|info|publicaciones|guardar_publicacion|borrar_publicacion|paletas`.
- `app/compilar_app.sh` → `Gráficos Excel BdE.app` en esta carpeta (no va a git).
- `app/crear_icono.swift` dibuja el icono (degradado verde-azul de «Maquetar» y «Versiones» con unas barras);
  `compilar_app.sh` lo convierte en `app/icono.icns` si no existe (para rehacerlo, se borra el .icns).
