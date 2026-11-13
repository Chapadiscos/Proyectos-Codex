#!/bin/bash
# Se instala como /usr/local/libexec/montar-usb-bitlocker-preparar (root:wheel 755) y se ejecuta con sudo sin contraseña.
# No admite argumentos: localiza la partición BitLocker de un disco externo y se la cede al usuario que llama.
set -u; PATH=/usr/bin:/bin:/usr/sbin:/sbin; umask 022
U="${SUDO_USER:-}"; [ -z "$U" ] && U=$(stat -f %Su /dev/console)
id "$U" >/dev/null 2>&1 || exit 1
MP=/Volumes/montar-bitlocker; EST=/var/run/montar-usb-bitlocker.dev; LOG=/var/log/montar-usb-bitlocker.log
{ echo "== $(date)  preparar para $U"; diskutil list external physical; } > "$LOG" 2>&1
DEV=""; PERM=""; ERR=$(mktemp)
for d in $(diskutil list external physical | grep -oE 'disk[0-9]+(s[0-9]+)?[[:space:]]*$' | tr -d '[:space:]\n' | sed 's/disk/ disk/g'); do
  [[ $d =~ ^disk[0-9]+(s[0-9]+)?$ ]] || continue
  sig=$(dd if=/dev/r$d bs=512 count=1 2>"$ERR" | dd bs=1 skip=3 count=8 2>/dev/null | LC_ALL=C tr -cd 'A-Z-')
  grep -qi "not permitted" "$ERR" && PERM=1
  echo "$d: firma='$sig'" >> "$LOG"
  [ "$sig" = "-FVE-FS-" ] && { DEV=$d; break; }
done
rm -f "$ERR"
[ -z "$DEV" ] && [ -n "$PERM" ] && { echo "PERMISO"; exit 0; }
[ -z "$DEV" ] && { echo "NOUSB"; exit 0; }
chown "$U" /dev/$DEV /dev/r$DEV
[ -L "$MP" ] && rm -f "$MP"; mkdir -p "$MP"; chown "$U" "$MP"
echo "/dev/$DEV" > "$EST"
echo "DEV:/dev/$DEV"
