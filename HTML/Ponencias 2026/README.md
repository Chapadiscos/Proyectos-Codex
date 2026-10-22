# De InDesign a Hélice (Ponencias 2026 y otros libros)

Del capítulo maquetado para imprenta al HTML publicado en Hélice: preparar el .indd, exportarlo a HTML (heredado) y depurarlo.

## Libros
Cada libro tiene su configuración en `config/libros/<libro>.yaml` y se reconoce por la carpeta del archivo (`libro.raiz`).

Hoy hay dos: `ponencias2026.yaml` y `ponencias2025.yaml` (prueba del proceso completo con el sufijo `-PRUEBAS`).

**Libro nuevo:** copia `config/libros/_plantilla.yaml` como `config/libros/<libro>.yaml` y cambia lo que sea distinto: carpetas, destino de las copias, sufijo de las clases (`-XX27`), CSS de Hélice, kit de Typekit, si hay cabecera o ideas básicas, estilos de pie y de cuadros… Con `base: ponencias2026.yaml` hereda el resto: las secciones se mezclan y las listas se sustituyen enteras.

Depura el HTML de **Archivo > Exportar > HTML (heredado)** de InDesign para publicarlo en https://avpm.helice.app/.

## Instalación (una vez)
```sh
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

### CSS de Hélice de un libro nuevo (`css_libro`)
Con `css_libro.generar: true`, cada capítulo que se depura completa la CSS del libro (`css_libro.archivo`) con los estilos que aún no tenía, tomados de la CSS que exporta InDesign: con el sufijo del libro y la familia web de cada fuente. Lo que ya está no se toca (se puede retocar a mano). Cuando cambia, el resultado sale con el aviso «súbela a Hélice antes de pegar el HTML».

**Fuentes propias** (no de Adobe Fonts), en `css_libro.fuentes_web`: se convierten a `.woff2` en su carpeta y la CSS lleva un `@font-face` por archivo.
1. Sube los `.woff2` a una carpeta de Hélice, ábrela y pulsa el marcador «Enlaces Hélice» (recoge imágenes y fuentes; si lo instalaste antes del 2026-10-22, vuelve a arrastrarlo desde `herramientas/instalar_marcador.html`).
2. `./css_libro --fuentes`: empareja las URL con los archivos por contenido (Hélice les cambia el nombre) y rehace la CSS.
3. Sube la CSS a Hélice.
Mientras no estén las URL, el `@font-face` apunta a los archivos locales y la vista previa los usa.

### Publicar en Hélice por la API (`./publicar`)
La API de Hélice (OpenAPI en `panel.helice.app/docs/openapi.webservices.viewer.html`; token en el llavero de macOS, servicio `helice-api`) permite crear secciones de tipo Información (`info`), lista, agenda, galería o PDF y añadirles elementos con HTML. **No** permite crear Menús, subir archivos (imágenes, fuentes, CSS), editar ni borrar, ni poner iconos de sección. Por eso:
1. En el panel: crea el Menú de cada bloque y pon su identificador en `publicar.bloques[].seccion`.
2. `./publicar --estructura`: crea los temas (Información) de cada bloque y guarda sus identificadores en `publicar.estado`.
3. Cada capítulo, al terminar la app (o `./publicar "…/06 … - Helice.html"`): se añade a su tema un elemento «Capítulo 06» con el HTML y se comprueba con `getContent`. Un capítulo ya publicado no se repite; las correcciones y los iconos, en el panel.

## Paso previo: preparar el .indd de imprenta
```sh
./preparar "Libro x Secciones/Seccion II (4-17) Ponencias 2026.indd" --capitulo 5   # o 5 6 7, o todos
./preparar "Maquetas/Carpeta 1 Ponencias 2026/1 Ponencias 2026.indd"                  # un solo capítulo
```
(`--forzar` rehace una copia que ya existe; la anterior queda como `… (anterior).indd`.) Normalmente lo hace la app (abajo).

Hace una **copia** en el destino del libro (`preparar.destino`: en Ponencias, `05 PONENCIAS 2026 (APP)/05 Ponencias 2026 (APP).indd`; si la carpeta ya tiene su .indd con otro nombre, ese) sin tocar el original. En un **archivo de sección** (cada capítulo es una sección de InDesign con su número como marcador) la copia se queda solo con las páginas del capítulo. Con `herramientas/preparar_html.jsx` la deja lista para exportar:

| Qué | Cómo |
|---|---|
| Cabecera, tablas, cuadros (algoritmo, ideas básicas) y figuras compuestas (varias imágenes con letras) | Se exportan a JPG como «Exportar > JPEG» de la selección (150 ppp, calidad máxima, RGB con perfil) con los nombres `C5`, `T5.1`, `algoritmo 5`, `IB5`, `F5.5`, junto a la copia, y se colocan en su lugar |
| Figuras y tablas | Cada una (imagen + pie, agrupados) se ancla en un párrafo propio tras el párrafo que la cita («(Figura 1)», «Tabla 1»); si no se cita, tras el párrafo que tiene encima (aviso) |
| Cabecera / cuadros | Al principio del texto / al final, antes de la bibliografía. Si un cuadro dibujado lleva un pie «Tabla N.» o «Figura N.» pegado, es esa tabla o figura (`T4.3`) y se ancla donde se cita |
| Recuadros dentro del texto | Marcos de texto anclados (no tablas ni figuras): JPG en el mismo sitio, `CUADRO 4.1`… |
| Vídeos y otros tipos (`otras_figuras`) | Como las figuras, con su pie («Video 1:»), su numeración y su nombre (`V6.1`); siempre a JPG (QR y formas) |
| Grupos sin pie | A JPG (`IMAGEN 6.1`), donde están, con aviso |
| Tablas sin «Tabla N» | `TABLA 4.1`…, tras el párrafo que tienen encima (con aviso para revisarlo) |
| Viñetas | Si es la única figura o tabla citada en la lista, va al final de la lista; si hay varias, cada una tras su viñeta y las subviñetas de esta |
| Maestras y mesa de trabajo | Se vacían (cornisas, folios, restos) |
| Texto | Variables y marcadores a texto; fuera guiones discrecionales, retornos forzados («especia-⏎lizado» → «especializado») y saltos de columna |
| Estilos y muestras | Se borran los que no se usan. **No se renombran**: el sufijo `-PO26` lo pone el depurador (`renombrar_clases`) |
| Exportación HTML | Fija en la copia los ajustes de `html_export` (conservar aspecto, JPEG, calidad media) |

El informe sale en pantalla y en `salida/<copia>.preparar.txt`; los avisos son lo que hay que revisar a mano en la copia. Todo lo propio del libro (estilos de pie, de cuadros, nombres de los JPG, si hay cabecera…) está en la sección `preparar` del libro.

El texto alternativo no hace falta quitarlo en InDesign: el depurador pone `alt=""` a todas las imágenes.

## Uso: app «InDesign a HTML»
La app está en `herramientas/InDesign a HTML.app`; arrástrala al Dock. Si cambias su código (`herramientas/InDesign a HTML.applescript`), vuelve a crearla con `herramientas/compilar_app.sh`. El icono está en `herramientas/icono/` (`icono.svg`; si cambias el diseño, `generar_icono.sh` vuelve a crear `icono.icns`).

1. **Abre la app** y elige el `.indd`: el de imprenta, el archivo de sección (te pregunta qué capítulo) o la versión ya preparada.
   - Si no está preparado, la app lo prepara (paso previo de arriba) y muestra el informe: **Exportar a HTML** sigue; **Abrir en InDesign** abre la copia para revisar los avisos (luego vuelve a abrir la app y elige la copia).
   - Si el capítulo ya tiene versión preparada, pregunta si usarla o prepararla de nuevo.
2. **InDesign lo exporta** a HTML (heredado) en su misma carpeta, con los ajustes HTML del propio documento (`herramientas/exportar_html.jsx`), sin abrirlo en el navegador. El capítulo se pone en primer plano para exportar, porque InDesign exporta el documento activo.
3. **Pausa:** la app indica la carpeta `…-web-resources/image` con las imágenes que hay que subir.
   - Sube esas imágenes a la carpeta del capítulo en Hélice (no los .jpg sueltos de la carpeta del capítulo).
   - Abre esa carpeta en Hélice y pulsa el marcador **«Enlaces Hélice»**: copia las URL al portapapeles y las muestra en un recuadro que se cierra solo. Para instalarlo, abre `herramientas/instalar_marcador.html` y arrastra el botón a la barra de marcadores (el código está en `herramientas/enlaces_helice.js`).
   - Vuelve a la app y pulsa **Continuar**.
   - **Si las imágenes ocupan varias páginas en Hélice**, la app dice cuáles faltan: pasa a la siguiente página, pulsa otra vez el marcador y **Continuar**. Los enlaces se van sumando en el `.txt` del capítulo. «Seguir sin ellas» genera el HTML con las que haya.
4. **Depuración:** se genera `… - Helice.html` en la carpeta del capítulo. La vista previa y el informe van a `salida/` del proyecto.
   - **Sin avisos:** el HTML queda copiado en el portapapeles. Pégalo en Hélice con ⌘V.
   - **Con avisos:** se muestran y puedes ver la vista previa o copiarlo igualmente.
   - El enlace leído del QR de la cabecera se muestra como información, no como aviso.

La primera vez, macOS pedirá permiso para que la app controle InDesign y el Finder.

### Desde el Terminal
```sh
./capitulo 33                      # o la ruta al .indd, al .html o a la carpeta del capítulo
./capitulo 33 --copiar             # copia al portapapeles aunque haya avisos
./capitulo 33 --libro otro         # con un número y varios libros, cuál
```
Si el portapapeles solo contiene URL (las del marcador), se añaden a las del `.txt` del capítulo; si no, se usan las que ya tenga. Las URL de más (otras páginas, subidas repetidas o borradas) se informan pero no bloquean.

Para un HTML suelto: `.venv/bin/python -m depurar ruta/al/archivo.html [--libro ponencias2026]` (sale en `salida/`).

## Pasos (`depurar/pasos/`)
| Paso | Qué hace |
|---|---|
| `p00_renombrar_clases` | Añade el sufijo del libro (`-PO26`) a las clases de estilo, con equivalencias para las que en Hélice se llaman distinto (`Viñetas_…` → `Ladillos_Viñetas_…`); las que ya lo llevan no se tocan |
| `p01_estilos_capitulo` | Pasa a `style=""` lo que solo está en la CSS del capítulo: anulaciones de carácter (`CharOverride-N`), `noPartir`, e imágenes a tamaño natural, centradas y sin pasar del ancho del visor (el % de ancho se pone a mano si hace falta) |
| `p02_limpieza` | Quita clases e ids autogenerados, el `<link>` a la CSS local, los `span` y `div` sobrantes, y une los `span` partidos iguales |
| `p03_correcciones_indesign` | Errores de la exportación: caracteres invisibles, `<br>` finales, **pie de figura debajo de la imagen** y **jerarquía de viñetas** cuando una imagen parte la lista |
| `p04_imagenes` | Descarga las URL del `.txt` y las empareja **por contenido** con las imágenes locales; si InDesign ha recodificado un JPEG al reexportar, **por parecido visual** |
| `p05_reglas_helice` | Reglas del libro en Hélice (abajo) |
| `p06_inyectar` | Añade al `<head>` el `<link>` de Adobe Fonts (Typekit) |
| `p07_salida` | Página completa o fragmento, vista previa y aviso de clases sin regla en la CSS de Hélice o no permitidas (`P-rrafo-b-sico`) |

## Reglas del HTML en Hélice
1. Las imágenes no llevan texto alternativo (`alt=""`).
2. Los pies de figura van siempre debajo de la imagen.
3. Se respeta la jerarquía de las viñetas aunque haya imágenes entre ellas.
4. `<br>` entre un párrafo y una imagen, y entre la imagen o su pie y el párrafo siguiente, salvo si es un ladillo.
5. El HTML empieza con un `<br>`.
6. La cabecera `CXX` enlaza (en pestaña nueva) a la URL de su QR, que se lee automáticamente de la imagen.
7. Entre dos ladillos seguidos: `<p style="margin-top: -1.3em; margin-bottom: 0.3em;"></p>`.
8. Las imágenes `IBXX` (estrechas): `max-width: 60%; display: block; margin: 0 auto;`.

Todo se configura en `config/libros/ponencias2026.yaml`. `config/libros/helice_ponencias2026.css` es una copia de la CSS subida a Hélice, solo para la vista previa.

### Pesos tipográficos
La CSS que genera InDesign exporta como `font-weight: normal` todo lo que no es Bold (Light, Regular, Medium…). Por eso la app, al exportar, guarda en `salida/<capítulo>.fuentes.tsv` la fuente real de cada tramo de texto, y el depurador pone el peso a partir de ella (`pesos_indesign` en la configuración del libro). Para un capítulo exportado a mano se puede generar sin reexportar:
```sh
osascript -e 'tell application "Adobe InDesign 2026" to do script (POSIX file "'"$PWD"'/herramientas/exportar_html.jsx") language javascript with arguments {"/ruta/al/capitulo.indd", "'"$PWD"'/salida", "solo_fuentes"}'
```
Sin ese archivo se aplica una regla de respaldo: manda el estilo de carácter propio; si el texto hereda negrita (ladillo), «normal» se toma como Light.

## Por qué así
- Hélice solo tiene la CSS de los **estilos del libro**. Las clases `ParaOverride-N`, `CharOverride-N` e `#_idContainerNNN` se numeran por capítulo y no existen allí.
- Al emparejar las imágenes por orden (el antiguo `codigo.py`), en los capítulos 04, 09, 11, 17, 19 y 32 quedaron imágenes cruzadas. Por contenido no puede pasar.

## Tests
```sh
.venv/bin/python -m pytest
```
