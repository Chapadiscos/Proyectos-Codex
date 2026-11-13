#!/bin/zsh
# Compila la app «Cuadros Excel BdE» (SwiftUI) y la deja en la carpeta del proyecto, junto a motor/.
dir="${0:A:h}"
app="${dir:h}/Cuadros Excel BdE.app"
rm -rf "$app"
mkdir -p "$app/Contents/MacOS" "$app/Contents/Resources"
swiftc -swift-version 5 -O -parse-as-library "$dir/CuadrosExcel.swift" -o "$app/Contents/MacOS/CuadrosExcel" || exit 1
cp "$dir/Info.plist" "$app/Contents/"
if [[ ! -f "$dir/icono.icns" ]]; then
    tmp=$(mktemp -d)/icono.iconset
    mkdir -p "$tmp"
    swift "$dir/crear_icono.swift" "$tmp" && iconutil -c icns "$tmp" -o "$dir/icono.icns"
fi
cp "$dir/icono.icns" "$app/Contents/Resources/"
# Firma local con requisito fijo (el identificador): así el permiso de Automatización sobre Excel y el de
# Accesibilidad valen entre compilaciones; sin él macOS la toma por otra app y vuelve a preguntar.
codesign --force --deep -s - -r='designated => identifier "es.estudioencuadre.cuadros-excel"' "$app" 2>/dev/null
touch "$app"                                       # para que el Finder refresque el icono
echo "Creada: $app"
# Si hay una copia en Aplicaciones, se pone al día (el motor lo encuentra por el ajuste «motor»:
# defaults write es.estudioencuadre.cuadros-excel motor "<carpeta motor>")
instalada="/Applications/${app:t}"
if [[ -d "$instalada" ]]; then
    rm -rf "$instalada" && ditto "$app" "$instalada" && echo "Actualizada: $instalada"
fi
