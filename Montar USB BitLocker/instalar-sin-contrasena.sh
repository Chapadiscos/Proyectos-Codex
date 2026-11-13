#!/bin/bash
# Ejecutar como root (sudo ./instalar-sin-contrasena.sh <usuario>): instala el script de preparación
# y la regla de sudo que permite ejecutar SOLO ese script sin contraseña.
set -e; U="$1"; [ -n "$U" ] || { echo "falta el usuario"; exit 1; }
D="$(cd "$(dirname "$0")" && pwd)"
install -d -o root -g wheel -m 755 /usr/local/libexec
install -o root -g wheel -m 755 "$D/src/preparar.sh" /usr/local/libexec/montar-usb-bitlocker-preparar
T=$(mktemp); echo "$U ALL=(root) NOPASSWD: /usr/local/libexec/montar-usb-bitlocker-preparar" > "$T"
visudo -cf "$T" >/dev/null && install -o root -g wheel -m 440 "$T" /etc/sudoers.d/montar-usb-bitlocker; rm -f "$T"
echo instalado
