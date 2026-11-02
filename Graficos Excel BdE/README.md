# Gráficos Excel BdE

App de Mac (SwiftUI) que maqueta, paso a paso, el Excel que entrega el autor (origen del PDF que luego se
maqueta en «Graficos Illus BdE», que no se toca desde aquí).

- **Ventana general**, como la de «Crear Publicación»: publicación (alta, edición y borrado), Excel del
  autor, tarjetas «Maquetar» (los pasos) y «Adelante y atrás» (las versiones) y la actividad abajo.
- **Ventana flotante** «Vista previa», siempre encima: el gráfico de la versión elegida tal como lo dibuja
  Excel (PDF de la hoja «Gráfico»), con o sin la retícula. Cada versión guarda su PDF en la carpeta de pasos.

- Se trabaja sobre una **copia**: del original `X.xlsx` sale `X maquetado.xlsx`, y cada paso deja su
  versión en `X maquetado (pasos)/` (`00 Copia exacta.xlsx`, `01 Retícula y pastilla.xlsx`…). Ir adelante
  y atrás es volver a una de esas versiones. Elegir otra vez el original o la copia sigue donde se quedó.
- Tras cada paso la app cierra la copia en Excel **sin guardar** y la vuelve a abrir **sin actualizar
  vínculos externos**. Lo que se toque a mano en esa copia se pierde: los cambios los hace la app.
- Excel está aislado (sandbox): la vista previa se exporta desde
  `~/Library/Group Containers/UBF8T346G9.Office/Graficos Excel BdE/`, donde no pide permiso. Para abrir la
  copia de trabajo puede pedirlo una vez con una ventana «Abrir»: se elige la carpeta y «Conceder acceso».
- AppleScript de Excel: las rutas van con barras (POSIX); con dos puntos da «Error de parámetros (-50)».
  Y no llamar `pdf` a una variable: es palabra reservada de Excel.
- Idioma del gráfico por el nombre: «Ing» delante o detrás (`Ing_…`, `…_Ing`) es inglés; si no, castellano.

## Pasos

1. **Retícula y pastilla**: borra la retícula y la pastilla del autor y pone las del archivo de retículas
   (`SdE_Reticulas_Publicaciones_ImagenNueva2024_Roboto.xlsx`, hoja «Gráfico»), en A1 y al fondo, con el
   color de la publicación. La retícula va a su tamaño de diseño (16,63 × 24,78 cm).
2. **Textos**: todo en Roboto, sin negrita (el peso lo da la variante):
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
  `maquetar_excel.py empezar|estado|ir|paso1|vista|info|publicaciones|guardar_publicacion|borrar_publicacion|paletas`.
- `app/compilar_app.sh` → `Gráficos Excel BdE.app` en esta carpeta (no va a git).
