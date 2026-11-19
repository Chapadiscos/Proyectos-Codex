#!/bin/zsh
# Copia los scripts al panel Scripts de InDesign 2027 (carpeta «Viudas Huerfanas»).
set -e
ORIGEN="$(cd "$(dirname "$0")" && pwd)/scripts"
DESTINO="$HOME/Library/Preferences/Adobe InDesign/Version 22.0/es_ES/Scripts/Scripts Panel/Viudas Huerfanas"
mkdir -p "$DESTINO/lib"
cp "$ORIGEN"/*.jsx "$DESTINO/"
cp "$ORIGEN"/lib/*.jsxinc "$DESTINO/lib/"
echo "Instalado en: $DESTINO"
