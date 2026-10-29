# Crear índices gráficos desde PDF

Genera en InDesign los índices de Cuadros, Gráficos, Esquemas, Figuras y
Recuadros (o Tables, Charts, Figures y Boxes) de un informe del Banco de España a partir
de su PDF final.

## La app

Abre **Crear índices gráficos.app**, en esta carpeta. Se puede dejar en el
Dock. Al abrirla pide el PDF del informe; también puedes soltar el PDF
sobre su icono. A partir de ahí hace todo el proceso:

1. **Extrae** los datos del PDF.
2. Si hay **avisos**, se para. «Corregir datos…» abre el `.json` en TextEdit;
   lo guardas y pulsas «Maquetar». Si no hay avisos, sigue sola.
3. **Maqueta** en InDesign y muestra el índice a la derecha de la ventana.
   Desde ahí puedes abrirlo en InDesign, verlo en Vista Previa o el Finder,
   corregir datos y volver a maquetar, o empezar con otro PDF.

A la izquierda de la ventana se ve en directo el registro del proceso: los
pasos en azul, los avisos en naranja, los errores en rojo y el final en verde.
Si algo falla, «Reintentar» repite el último paso.

La app se compila con `app/compilar_app.sh`, que la deja en esta carpeta.
Hay que volver a compilarla si se cambia `app/CrearIndices.swift`; si solo se
cambian los scripts, no. El icono se genera con `app/icono/generar_icono.sh`.

## Carpetas

| Carpeta / archivo | Qué hay |
|---|---|
| `entrada/` | PDF de los informes |
| `datos/` | Lo que se extrae de cada PDF (`indice_<nombre>.json`) y el registro de InDesign. No se versiona |
| `salida/` | El `.indd` generado y un PDF para revisarlo |
| `Indices limpio.indd` | Plantilla: banda azul + título + dos columnas. No se modifica nunca |
| `Indice ejemplo final.pdf` | Referencia del resultado esperado |
| `scripts/` | El proceso: extracción (Python) y maquetación (InDesign) |
| `app/` | El código de la app y su icono |

## Uso desde el Terminal

Hace lo mismo que la app. Requiere Python 3 con PyMuPDF (`pip install pymupdf`) e InDesign 2026.

```bash
cd "/Volumes/DATOS/Proyectos Codex/Extraer indices PDF Publicacion del BdE"

# Todo de una vez: extrae, maqueta y abre el PDF de revisión
scripts/generar_indice.sh entrada/MiInforme.pdf

# Por pasos, para revisar o corregir los datos antes de maquetar
scripts/generar_indice.sh --solo-extraer entrada/MiInforme.pdf
#   ... revisar / retocar datos/indice_MiInforme.json ...
scripts/generar_indice.sh --solo-maquetar entrada/MiInforme.pdf
```

El resultado va a `salida/Indice_MiInforme.indd` (y `.pdf`). Si ya existe, se
sobrescribe. Se le puede dar otro nombre como segundo argumento.

La extracción termina con **avisos para revisar**: títulos vacíos o raros,
huecos en la numeración (falta el 1.4, por ejemplo), páginas que retroceden o
páginas sin número impreso en el pie. Si no hay avisos, no aparece la sección.

La plantilla no puede estar abierta en InDesign mientras se maqueta: el
script se para y lo avisa. Los demás documentos abiertos no se tocan.

## Dónde tocar

- **Detección en el PDF**: `scripts/extraer_indice.py`. Trabaja línea a línea y en el sentido de lectura de cada una, así que sirve también para las páginas apaisadas con el texto girado.
  - `ETIQUETA_RE`: la línea con la etiqueta sola («Cuadro 1.1», «Recuadro 3.2», «Table A1.2»…).
  - `titulo_junto_a()`: el título es la línea alineada justo después de la etiqueta, más las que la siguen con la misma fuente. Si no la hay, se busca justo antes.
  - `NO_TITULO_RE`: pies y fuentes que nunca son título.
  - `LIGADURAS`: «ﬁ», «ﬂ»… que algunos PDF dan como un solo carácter (también en «Gráﬁco»).
  - `numero_pagina_impreso()`: lee el número de página del pie.
- **Maquetación**: `scripts/poblar_indice.jsx`.
  - `CATEGORIAS_ORDEN`: orden de los índices.
  - `TITULO_INDICE`: textos de cabecera.
  - Estilos de párrafo `Indice Varios` (entradas) e `Indice titulo cap` (cabecera), que salen de la plantilla.
  - Línea en blanco entre capítulos y espacio eme antes del número de página.
  - Cada página va en su propio pliego. Todas las columnas de entradas forman una sola historia enhebrada; los marcos de título van aparte. Cada tipo de índice termina con un salto de columna y lleva su cabecera solo sobre la columna donde empieza.
- **Cursivas**: el extractor marca en el título los tramos que en el PDF van en cursiva, así: `<i>Boletín Económico</i>`. Se pueden añadir o quitar a mano en el `.json`. Al maquetar, `poblar_indice.jsx` quita las marcas y aplica el estilo de carácter `Light Italic` de la plantilla.
- **Espacios de no separación**: `PALABRAS_UNIDAS` en `scripts/extraer_indice.py`. Lista las palabras cortas (la, de, un, y…; en inglés the, of, and…) que no deben quedarse a final de línea. El espacio que las sigue se cambia por uno de no separación al pasar los datos a InDesign; el `.json` conserva los espacios normales.
- **Columnas de la plantilla**: `clasificarColumnas()` las reconoce por posición. Columna izquierda en x≈19 mm; banda si el ancho es mayor de 150; título si el alto es menor de 30. Si se mueve algo en la plantilla, hay que ajustar estos valores.
- **Otra versión de InDesign**: `INDESIGN_APP="Adobe InDesign 2027" scripts/generar_indice.sh …`
