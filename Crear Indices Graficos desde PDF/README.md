# Crear índices gráficos desde PDF

Genera en InDesign los índices de Cuadros, Gráficos, Esquemas y Recuadros
(o Tables, Charts, Figures y Boxes) de un informe del Banco de España a partir
de su PDF final.

## Carpetas

| Carpeta / archivo | Qué hay |
|---|---|
| `entrada/` | PDF de los informes |
| `datos/` | Lo que se extrae de cada PDF (`indice_<nombre>.json`) y el registro de InDesign. No se versiona |
| `salida/` | El `.indd` generado y un PDF para revisarlo |
| `Indices limpio.indd` | Plantilla: banda azul + título + dos columnas. No se modifica nunca |
| `Indice ejemplo final.pdf` | Referencia del resultado esperado |
| `scripts/` | El código |

## Uso

Requiere Python 3 con PyMuPDF (`pip install pymupdf`) e InDesign 2026.

```bash
cd "/Volumes/DATOS/Proyectos Codex/Crear Indices Graficos desde PDF"

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

- **Detección en el PDF**: `scripts/extraer_indice.py`.
  - `LABEL_RE`: etiquetas en un bloque propio, con el título en el bloque siguiente (Cuadro, Gráfico, Esquema…).
  - `RECUADRO_RE`: etiqueta y título en el mismo bloque (Recuadro / Box).
  - `NO_TITULO_RE`: pies y fuentes que nunca son título.
  - `numero_pagina_impreso()`: lee el número de página del pie.
- **Maquetación**: `scripts/poblar_indice.jsx`.
  - `CATEGORIAS_ORDEN`: orden de los índices.
  - `TITULO_INDICE`: textos de cabecera.
  - Estilos de párrafo `Indice Varios` (entradas) e `Indice titulo cap` (cabecera), que salen de la plantilla.
  - Línea en blanco entre capítulos y espacio eme antes del número de página.
- **Columnas de la plantilla**: `clasificarColumnas()` las reconoce por posición. Columna izquierda en x≈19 mm; banda si el ancho es mayor de 150; título si el alto es menor de 30. Si se mueve algo en la plantilla, hay que ajustar estos valores.
- **Otra versión de InDesign**: `INDESIGN_APP="Adobe InDesign 2027" scripts/generar_indice.sh …`
