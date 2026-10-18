#!/bin/zsh
# Compila la app «InDesign a HTML» a partir de su código AppleScript.
cd "${0:A:h}" || exit 1
rm -rf "InDesign a HTML.app"
osacompile -o "InDesign a HTML.app" "InDesign a HTML.applescript" && echo "Creada: ${0:A:h}/InDesign a HTML.app"
