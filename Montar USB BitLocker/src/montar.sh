#!/bin/bash
# Como el usuario: montar.sh <dir_recursos> <dispositivo>   — contraseña de BitLocker por la entrada estándar
IFS= read -r BLPW
R="$1"; DEV="$2"; DL="$R/dislocker/MacOS/dislocker-fuse"
LOG="$HOME/Library/Logs/montar-usb-bitlocker.log"
# 1º carpeta oculta en el usuario (no sale en el Finder); si macFUSE no la acepta, /Volumes (la crea preparar.sh)
OCULTO="$HOME/Library/Caches/montar-bitlocker-interno"; VISIBLE=/Volumes/montar-bitlocker
: > "$LOG"; echo "== montar como $(id -un) $DEV" >> "$LOG"
for MP in "$OCULTO" "$VISIBLE"; do
  mkdir -p "$MP" 2>/dev/null
  echo "-- probando $MP" >> "$LOG"
  "$DL" -V "$DEV" -u"$BLPW" -- -o backend=fskit,nobrowse,volname=BitLocker-interno "$MP" >> "$LOG" 2>&1
  for i in 1 2 3 4 5; do [ -e "$MP/dislocker-file" ] && break; sleep 1; done
  [ -e "$MP/dislocker-file" ] && break
  umount "$MP" 2>/dev/null
  grep -q "VMK or FVEK" "$LOG" && break   # contraseña mala: no insistir
done
if [ ! -e "$MP/dislocker-file" ]; then
  if grep -q "VMK or FVEK" "$LOG"; then echo "CLAVE"
  elif grep -qiE "extension not found|not available|macfuse" "$LOG"; then echo "FUSE"
  else echo "ERROR"; fi
  exit 0
fi
echo "montado dislocker en $MP" >> "$LOG"
VOL=$(hdiutil attach -imagekey diskimage-class=CRawDiskImage "$MP/dislocker-file" 2>>"$LOG" | grep -oE '/Volumes/.*$' | head -1)
[ -z "$VOL" ] && { echo "ERROR"; exit 0; }
echo "$VOL" > "$HOME/Library/Caches/montar-usb-bitlocker.vol"; echo "OK:$VOL"
