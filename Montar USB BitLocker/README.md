# Montar USB BitLocker

App de AppleScript que monta un USB cifrado con BitLocker (lectura y escritura).

- Doble clic → contraseña de BitLocker → abre el USB en el Finder.
- Con el USB montado, doble clic → «Desmontar y expulsar» (sacarlo siempre así).

## Cómo funciona
1. `preparar.sh` (root, sin argumentos), instalado como `/usr/local/libexec/montar-usb-bitlocker-preparar`
   con regla `/etc/sudoers.d/montar-usb-bitlocker` (NOPASSWD solo para ese script): busca la firma `-FVE-FS-`
   en los discos externos y hace `chown` del /dev al usuario. Si no está instalado, la app usa la copia
   de Resources pidiendo la contraseña del Mac (sudo -S).
2. `montar.sh` (usuario): `dislocker-fuse -o backend=fskit,nobrowse` (oculto en el Finder) primero en ~/Library/Caches/montar-bitlocker-interno (nobrowse no se respeta con FSKit; fuera de /Volumes no debería salir en el Finder) y si falla en /Volumes/montar-bitlocker; luego `hdiutil attach` del
   archivo descifrado (el USB de prueba es exFAT, que macOS escribe sin más).
3. `desmontar.sh` (usuario): suelta la imagen, desmonta dislocker y expulsa.

## Trampas
- La extensión FSKit de macFUSE está registrada por usuario: montar como root da «File system extension not found».
- «with administrator privileges» pierde el Acceso total al disco de la app (dd: Operation not permitted); sudo lo conserva.
- macFUSE 5.x: el kext no carga en Apple Silicon sin rebajar seguridad; no hace falta, se usa FSKit.
- dislocker-fuse 0.7.3 (GPL, sacado de BitLockerGeeker) está firmado ad hoc y con rpath a /usr/local/lib para usar
  la libfuse del macFUSE instalado (la de BitLockerGeeker con su MFMount falla fuera de esa app).
- Sin CFBundleIdentifier macOS no deja la app en Acceso total al disco. Cada `./build.sh` cambia la firma:
  hay que quitarla con − y volver a añadirla con +.

## Archivos
- `build.sh`: recompila (osacompile + dislocker + scripts + icono + firma) e instala en /Applications.
- `instalar-sin-contrasena.sh <usuario>`: como root; si root no puede leer DATOS, copiarlo antes a /private/tmp.
- `src/icono.swift` → `src/Icono.icns`. Registros: /var/log/montar-usb-bitlocker.log y ~/Library/Logs/montar-usb-bitlocker.log.
- `vendor/dislocker/`: dislocker-fuse 0.7.3 y libdislocker (GPL-3, © Romain Coltel, https://github.com/Aorimn/dislocker),
  ya firmados ad hoc y con rpath a /usr/local/lib. La app compilada no se guarda en git: se rehace con `./build.sh`.
