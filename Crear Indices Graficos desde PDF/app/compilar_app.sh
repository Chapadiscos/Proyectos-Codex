#!/bin/zsh
# Compila la app «Crear índices gráficos» (SwiftUI) y la deja en la carpeta del proyecto.
dir="${0:A:h}"
app="${dir:h}/Crear índices gráficos.app"
rm -rf "$app"
mkdir -p "$app/Contents/MacOS" "$app/Contents/Resources"
swiftc -swift-version 5 -O -parse-as-library "$dir/CrearIndices.swift" -o "$app/Contents/MacOS/CrearIndices" || exit 1
cp "$dir/Info.plist" "$app/Contents/"
[ -f "$dir/icono/icono.icns" ] && cp "$dir/icono/icono.icns" "$app/Contents/Resources/"
codesign --force --deep -s - "$app" 2>/dev/null   # firma local, para que macOS la deje abrir
touch "$app"                                       # para que el Finder refresque el icono
/System/Library/Frameworks/CoreServices.framework/Frameworks/LaunchServices.framework/Support/lsregister -f "$app"   # que macOS sepa que abre PDF
echo "Creada: $app"
