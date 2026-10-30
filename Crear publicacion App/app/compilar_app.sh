#!/bin/zsh
# Compila la app «Crear Publicación» (SwiftUI) y la deja en la carpeta del proyecto.
dir="${0:A:h}"
app="${dir:h}/Crear Publicación.app"
rm -rf "$app"
mkdir -p "$app/Contents/MacOS" "$app/Contents/Resources"
swiftc -swift-version 5 -O -parse-as-library "$dir/CrearPublicacion.swift" -o "$app/Contents/MacOS/CrearPublicacion" || exit 1
cp "$dir/Info.plist" "$app/Contents/"
if [[ ! -f "$dir/icono.icns" ]]; then
    tmp=$(mktemp -d)/icono.iconset
    mkdir -p "$tmp"
    swift "$dir/crear_icono.swift" "$tmp" && iconutil -c icns "$tmp" -o "$dir/icono.icns"
fi
cp "$dir/icono.icns" "$app/Contents/Resources/"
codesign --force --deep -s - "$app" 2>/dev/null   # firma local, para que macOS la deje abrir
touch "$app"                                       # para que el Finder refresque el icono
echo "Creada: $app"
