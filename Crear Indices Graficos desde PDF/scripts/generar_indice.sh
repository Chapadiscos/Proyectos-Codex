#!/bin/bash
# Genera el índice de Cuadros/Gráficos/Esquemas/Recuadros de un PDF del
# Banco de España:
#   1) extrae los datos del PDF (Python) a datos/indice_<nombre>.json
#   2) los vuelca en "Indices limpio.indd" generando páginas/columnas
#      automáticamente (InDesign, vía ExtendScript) y guarda en salida/
#      el .indd y un PDF para revisarlo, que se abre al terminar.
#
# Uso:
#   scripts/generar_indice.sh [--solo-extraer | --solo-maquetar] <archivo.pdf> [salida.indd]
#
#   --solo-extraer   hace solo el paso 1, para revisar/retocar el .json
#   --solo-maquetar  hace solo el paso 2 a partir del .json ya existente
#                    (p. ej. después de corregir a mano algún título)
#
# Requiere InDesign abierto (se abre solo si no lo está) y Python 3 con
# PyMuPDF instalado. Otra versión de InDesign: INDESIGN_APP="Adobe InDesign 2027"
# Con DESDE_APP=1 (lo pone la app «Crear índices gráficos») no abre el PDF
# ni da las instrucciones de la línea de órdenes.

set -euo pipefail

# Las apps abiertas desde el Finder no heredan el PATH del Terminal: sin esto
# no se encuentra el python3 que tiene PyMuPDF.
export PATH="/Library/Frameworks/Python.framework/Versions/Current/bin:/opt/homebrew/bin:/usr/local/bin:$PATH"
export PYTHONUNBUFFERED=1
DESDE_APP="${DESDE_APP:-0}"

PASO_EXTRAER=1
PASO_MAQUETAR=1
case "${1:-}" in
    --solo-extraer) PASO_MAQUETAR=0; shift ;;
    --solo-maquetar) PASO_EXTRAER=0; shift ;;
esac

if [ $# -lt 1 ]; then
    echo "Uso: $0 [--solo-extraer | --solo-maquetar] <archivo.pdf> [salida.indd]"
    exit 1
fi

PDF_PATH="$1"
SCRIPTS="$(cd "$(dirname "$0")" && pwd)"
CARPETA="$(dirname "$SCRIPTS")"
DATOS="$CARPETA/datos"
SALIDA="$CARPETA/salida"
INDESIGN_APP="${INDESIGN_APP:-Adobe InDesign 2026}"
mkdir -p "$DATOS" "$SALIDA"

BASENAME="$(basename "$PDF_PATH")"
NOMBRE="${BASENAME%.*}"

SALIDA_INDD="${2:-Indice_${NOMBRE}.indd}"
SALIDA_INDD="$SALIDA/$(basename "$SALIDA_INDD")"
SALIDA_PDF="${SALIDA_INDD%.*}.pdf"
JSON_PATH="$DATOS/indice_${NOMBRE}.json"
JSX_PATH="$DATOS/indice_${NOMBRE}.jsx"
LOG_PATH="$DATOS/poblar_log.txt"
LANZADOR="$DATOS/_lanzador_generado.jsx"

if [ "$PASO_EXTRAER" = 1 ]; then
    if [ ! -f "$PDF_PATH" ]; then
        echo "ERROR: no existe el PDF: $PDF_PATH"
        exit 1
    fi
    echo "== Extrayendo índice de \"$BASENAME\" =="
    python3 "$SCRIPTS/extraer_indice.py" "$PDF_PATH" "$JSON_PATH"
fi

if [ "$PASO_MAQUETAR" = 0 ]; then
    [ "$DESDE_APP" = 1 ] && exit 0
    echo
    echo "Revisa y retoca si hace falta: $JSON_PATH"
    echo "Luego: $0 --solo-maquetar \"$PDF_PATH\""
    exit 0
fi

if [ ! -f "$JSON_PATH" ]; then
    echo "ERROR: no existe $JSON_PATH (lanza antes la extracción)"
    exit 1
fi
# El .jsx se rehace siempre desde el .json, por si se ha retocado a mano.
python3 "$SCRIPTS/extraer_indice.py" --a-jsx "$JSON_PATH" > /dev/null

echo
echo "== Maquetando \"$(basename "$SALIDA_INDD")\" en $INDESIGN_APP =="
cat > "$LANZADOR" <<EOF
var TEMPLATE_PATH = "$CARPETA/Indices limpio.indd";
var JSON_PATH = "$JSX_PATH";
var OUTPUT_PATH = "$SALIDA_INDD";
var PDF_PATH = "$SALIDA_PDF";
var LOG_PATH = "$LOG_PATH";
\$.evalFile("$SCRIPTS/poblar_indice.jsx");
EOF

rm -f "$LOG_PATH"
osascript -e "
with timeout of 600 seconds
    tell application \"$INDESIGN_APP\"
        do script (POSIX file \"$LANZADOR\") language javascript
    end tell
end timeout" > /dev/null

echo
if [ ! -f "$LOG_PATH" ]; then
    echo "!! InDesign no dejó registro: el script no llegó a ejecutarse."
    exit 1
fi
cat "$LOG_PATH"
echo
if grep -q "^ERROR" "$LOG_PATH"; then
    echo "!! Hubo un error, revisa el registro de arriba."
    exit 1
fi
echo "Listo: $SALIDA_INDD"
if [ -f "$SALIDA_PDF" ] && [ "$DESDE_APP" = 0 ]; then
    open "$SALIDA_PDF"
fi
