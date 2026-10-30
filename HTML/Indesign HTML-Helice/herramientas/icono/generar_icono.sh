#!/bin/zsh
# Genera icono.icns a partir de icono.svg (necesita Google Chrome para pasar el SVG a PNG).
# Solo hace falta si se cambia el diseño; compilar_app.sh usa el icono.icns ya generado.
dir="${0:A:h}"
tmp=$(mktemp -d) || exit 1
chrome="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"

print -r -- "<html><body style='margin:0;background:transparent'><img src='file://$dir/icono.svg' width='1024' height='1024' style='display:block'></body></html>" > "$tmp/icono.html"
"$chrome" --headless=new --disable-gpu --hide-scrollbars --allow-file-access-from-files \
  --default-background-color=00000000 --window-size=1024,1024 --force-device-scale-factor=1 \
  --screenshot="$tmp/1024.png" "file://$tmp/icono.html" 2>/dev/null || exit 1

set="$tmp/icono.iconset"
mkdir "$set"
for s in 16 32 128 256 512; do
  sips -z $s $s "$tmp/1024.png" --out "$set/icon_${s}x${s}.png" >/dev/null
  sips -z $((s * 2)) $((s * 2)) "$tmp/1024.png" --out "$set/icon_${s}x${s}@2x.png" >/dev/null
done
iconutil -c icns "$set" -o "$dir/icono.icns" && echo "Creado: $dir/icono.icns"
rm -r "$tmp"
