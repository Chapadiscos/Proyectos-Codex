#!/bin/zsh
# Compila la app «Gráficos Excel BdE» (SwiftUI) y la deja en la carpeta del proyecto, junto a motor/.
dir="${0:A:h}"
app="${dir:h}/Gráficos Excel BdE.app"
rm -rf "$app"
mkdir -p "$app/Contents/MacOS" "$app/Contents/Resources"
swiftc -swift-version 5 -O -parse-as-library "$dir/GraficosExcel.swift" -o "$app/Contents/MacOS/GraficosExcel" || exit 1
cp "$dir/Info.plist" "$app/Contents/"
if [[ ! -f "$dir/icono.icns" ]]; then
    tmp=$(mktemp -d)/icono.iconset
    mkdir -p "$tmp"
    swift "$dir/crear_icono.swift" "$tmp" && iconutil -c icns "$tmp" -o "$dir/icono.icns"
fi
cp "$dir/icono.icns" "$app/Contents/Resources/"
# Firma local, para que macOS la deje abrir. El requisito fijo (el identificador) hace que el permiso de
# Automatización sobre Excel valga entre compilaciones; sin él macOS la toma por otra app y vuelve a preguntar.
codesign --force --deep -s - -r='designated => identifier "es.estudioencuadre.graficos-excel"' "$app" 2>/dev/null
touch "$app"                                       # para que el Finder refresque el icono
echo "Creada: $app"
