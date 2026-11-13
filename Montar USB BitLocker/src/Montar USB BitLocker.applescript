-- Montar USB BitLocker: monta en solo lectura un USB cifrado con BitLocker (dislocker + macFUSE)
on comoAdmin(cmd, entrada)
	set apw to text returned of (display dialog "Contraseña de administrador del Mac:" default answer "" with hidden answer buttons {"Cancelar", "Aceptar"} default button "Aceptar" with title "Montar USB BitLocker" with icon note)
	try
		return do shell script "printf '%s\\n%s\\n' " & quoted form of apw & " " & quoted form of entrada & " | sudo -k -S -p '' " & cmd
	on error e
		if e contains "incorrect password" or e contains "Sorry" then
			display dialog "La contraseña del Mac no es correcta." buttons {"OK"} default button 1 with title "Montar USB BitLocker" with icon stop
			error number -128
		end if
		error e
	end try
end comoAdmin

on run
	set R to POSIX path of (path to resource "dislocker")
	set R to text 1 thru -11 of R -- carpeta Resources/
	set montado to (do shell script "mount | grep -c 'montar-bitlocker' || true") is not "0"
	if montado then
		set b to button returned of (display dialog "El USB BitLocker está montado." buttons {"Cancelar", "Abrir", "Desmontar y expulsar"} default button "Desmontar y expulsar" with title "Montar USB BitLocker" with icon note)
		if b is "Abrir" then
			do shell script "open \"$(cat ~/Library/Caches/montar-usb-bitlocker.vol)\""
		else if b is "Desmontar y expulsar" then
			do shell script quoted form of (R & "desmontar.sh")
			display dialog "Listo. Ya puedes sacar el USB." & return & return & "Saca siempre el USB así, para que lo grabado quede guardado." buttons {"OK"} default button 1 with title "Montar USB BitLocker"
		end if
		return
	end if
	set pw to text returned of (display dialog "Conecta el USB y escribe su contraseña de BitLocker:" default answer "" with hidden answer buttons {"Cancelar", "Montar"} default button "Montar" with title "Montar USB BitLocker" with icon note)
	try
		set res to do shell script "sudo -n /usr/local/libexec/montar-usb-bitlocker-preparar"
	on error
		set res to my comoAdmin(quoted form of (R & "preparar.sh"), "")
	end try
	if res starts with "DEV:" then
		set res to do shell script "printf '%s\\n' " & quoted form of pw & " | " & quoted form of (R & "montar.sh") & " " & quoted form of R & " " & quoted form of (text 5 thru -1 of res)
	end if
	set pw to ""
	if res starts with "OK:" then
		do shell script "open " & quoted form of (text 4 thru -1 of res)
	else if res is "NOUSB" then
		display dialog "No encuentro ningún USB cifrado con BitLocker conectado." & return & return & "Detalles en ~/Library/Logs/montar-usb-bitlocker.log" buttons {"OK"} default button 1 with title "Montar USB BitLocker" with icon caution
	else if res is "PERMISO" then
		display dialog "macOS no deja a la app leer el USB (permiso denegado)." & return & return & "Ajustes del Sistema → Privacidad y seguridad → Acceso total al disco: quita «Montar USB BitLocker» con «−», vuelve a añadirla con «+» y actívala." buttons {"OK"} default button 1 with title "Montar USB BitLocker" with icon caution
	else if res is "CLAVE" then
		display dialog "La contraseña no es correcta." buttons {"OK"} default button 1 with title "Montar USB BitLocker" with icon stop
	else if res is "FUSE" then
		display dialog "macFUSE no ha podido montar." & return & return & "Ajustes del Sistema → General → Ítems de inicio y extensiones → Extensiones del sistema de archivos: activa macFUSE y reinicia. Detalles en ~/Library/Logs/montar-usb-bitlocker.log" buttons {"OK"} default button 1 with title "Montar USB BitLocker" with icon caution
	else
		display dialog "No se ha podido montar. Detalles en ~/Library/Logs/montar-usb-bitlocker.log" buttons {"OK"} default button 1 with title "Montar USB BitLocker" with icon stop
	end if
end run
