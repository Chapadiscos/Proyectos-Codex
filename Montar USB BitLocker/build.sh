#!/bin/bash
# Recompila la app en la carpeta del proyecto y la instala en /Applications.
set -e; cd "$(dirname "$0")"; A="Montar USB BitLocker.app"
rm -rf "$A"; osacompile -o "$A" "src/Montar USB BitLocker.applescript"
cp -pR vendor/dislocker "$A/Contents/Resources/dislocker"
cp src/preparar.sh src/montar.sh src/desmontar.sh "$A/Contents/Resources/"; chmod +x "$A/Contents/Resources/"*.sh
/usr/libexec/PlistBuddy -c "Add :CFBundleIdentifier string local.montar-usb-bitlocker" "$A/Contents/Info.plist"
/usr/libexec/PlistBuddy -c "Delete :CFBundleIconName" "$A/Contents/Info.plist" 2>/dev/null || true
rm -f "$A/Contents/Resources/Assets.car"; cp src/Icono.icns "$A/Contents/Resources/applet.icns"
codesign -f -s - "$A"
rm -rf "/Applications/$A"; cp -pR "$A" /Applications/
touch "/Applications/$A"
echo "Instalada. Hay que volver a dar Acceso total al disco (quitar con − y añadir con +)."
