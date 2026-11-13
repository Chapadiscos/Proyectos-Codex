#!/bin/bash
# Como el usuario: suelta la imagen, desmonta dislocker y expulsa el USB.
EST=/var/run/montar-usb-bitlocker.dev
for MP in "$HOME/Library/Caches/montar-bitlocker-interno" /Volumes/montar-bitlocker; do
  IMG=$(hdiutil info | awk -v f="$MP/dislocker-file" '$0 ~ "image-path" && index($0,f){m=1} m && /^\/dev\/disk[0-9]+[ \t]/{print $1; exit}')
  [ -n "$IMG" ] && hdiutil detach "$IMG" -force >/dev/null 2>&1
  mount | grep -q " on $MP " && { umount "$MP" 2>/dev/null || diskutil unmount force "$MP" >/dev/null 2>&1; }
done
sleep 1
if [ -f "$EST" ]; then
  PHY=$(sed -E 's#(/dev/disk[0-9]+).*#\1#' "$EST"); diskutil eject "$PHY" >/dev/null 2>&1
fi
rm -f "$HOME/Library/Caches/montar-usb-bitlocker.vol"
echo OK
