#!/bin/zsh
# Compila la app «InDesign a HTML» a partir de su código AppleScript y le pone su icono.
dir="${0:A:h}"
app="InDesign a HTML.app"
cd "$dir" || exit 1
rm -rf "$app"
osacompile -o "$app" "InDesign a HTML.applescript" || exit 1
cp icono/icono.icns "$app/Contents/Resources/applet.icns"
codesign --force --deep -s - "$app" 2>/dev/null   # el icono cambia los recursos: volver a firmar (local)
touch "$app"                                       # para que el Finder refresque el icono
echo "Creada: $dir/$app"
