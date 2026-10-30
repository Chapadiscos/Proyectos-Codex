#!/bin/zsh
# Compila la app «InDesign a HTML» (SwiftUI) y la deja en herramientas/.
dir="${0:A:h}"
app="${dir:h}/InDesign a HTML.app"
rm -rf "$app"
mkdir -p "$app/Contents/MacOS" "$app/Contents/Resources"
swiftc -swift-version 5 -O -parse-as-library "$dir/InDesignAHTML.swift" -o "$app/Contents/MacOS/InDesignAHTML" || exit 1
cp "$dir/Info.plist" "$app/Contents/"
cp "${dir:h}/icono/icono.icns" "$app/Contents/Resources/"
codesign --force --deep -s - "$app" 2>/dev/null   # firma local, para que macOS la deje abrir
touch "$app"                                       # para que el Finder refresque el icono
/System/Library/Frameworks/CoreServices.framework/Frameworks/LaunchServices.framework/Support/lsregister -f "$app"   # que macOS sepa que abre .indd
echo "Creada: $app"
