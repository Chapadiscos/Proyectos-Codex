#!/bin/bash
# Genera el índice de Cuadros/Gráficos/Esquemas/Recuadros de un PDF del
# Banco de España, de principio a fin, en un solo paso:
#   1) extrae los datos del PDF (Python)
#   2) los vuelca en "Indices limpio.indd" generando páginas/columnas
#      automáticamente (InDesign, vía ExtendScript)
#
# Uso:
#   scripts/generar_indice.sh /ruta/al/Informe.pdf [nombre_salida.indd]
#
# Requiere InDesign 2026 abierto (se abre solo si no lo está) y Python 3
# con PyMuPDF instalado.

set -euo pipefail

if [ $# -lt 1 ]; then
    echo "Uso: $0 <archivo.pdf> [nombre_salida.indd]"
    exit 1
fi

PDF_PATH="$1"
if [ ! -f "$PDF_PATH" ]; then
    echo "ERROR: no existe el PDF: $PDF_PATH"
    exit 1
fi

CARPETA="/Volumes/DATOS/Proyectos Codex/Crear Indices Graficos desde PDF"
SCRIPTS="$CARPETA/scripts"
BASENAME="$(basename "$PDF_PATH")"
NOMBRE="${BASENAME%.*}"

SALIDA_INDD="${2:-Indice_${NOMBRE}.indd}"
JSON_PATH="$SCRIPTS/indice_${NOMBRE}.json"
JSX_PATH="$SCRIPTS/indice_${NOMBRE}.jsx"
LOG_PATH="$SCRIPTS/poblar_log.txt"
LANZADOR="$SCRIPTS/_lanzador_generado.jsx"

echo "== 1/2: extrayendo índice de \"$BASENAME\" =="
python3 "$SCRIPTS/extraer_indice.py" "$PDF_PATH" "$JSON_PATH"

echo
echo "== 2/2: generando \"$SALIDA_INDD\" en InDesign =="
cat > "$LANZADOR" <<EOF
var CARPETA = "$CARPETA/";
var TEMPLATE_PATH = CARPETA + "Indices limpio.indd";
var JSON_PATH = "$JSX_PATH";
var OUTPUT_PATH = CARPETA + "$SALIDA_INDD";
var LOG_PATH = "$LOG_PATH";
\$.evalFile(CARPETA + "scripts/poblar_indice.jsx");
EOF

osascript -e "
tell application \"Adobe InDesign 2026\"
    do script (POSIX file \"$LANZADOR\") language javascript
end tell" > /dev/null

echo
cat "$LOG_PATH"
echo
if grep -q "^ERROR" "$LOG_PATH"; then
    echo "!! Hubo un error, revisa el registro de arriba."
    exit 1
fi
echo "Listo: \"$CARPETA/$SALIDA_INDD\""
