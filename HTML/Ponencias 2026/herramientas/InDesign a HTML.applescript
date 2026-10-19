-- InDesign a HTML: de un capítulo de InDesign al HTML depurado en el portapapeles.
-- 1. Eliges el .indd.  2. InDesign lo exporta a HTML (heredado) en su carpeta.
-- 3. Pausa para subir las imágenes a Hélice y copiar sus enlaces con el marcador.
-- 4. Se depura el HTML; si no hay avisos, queda copiado en el portapapeles.
-- Compilar: herramientas/compilar_app.sh

property proyecto : "/Volumes/DATOS/Proyectos Codex/HTML/Ponencias 2026"
property libro : "/Volumes/MACLINE SERVER/LIBROS/PONENCIA SEO 2026/Ponencias 2026 (APP)"
property titulo : "InDesign a HTML"

on run
	-- 1. Elegir el capítulo
	try
		set inicio to (POSIX file libro) as alias
	on error
		set inicio to path to desktop
	end try
	set indd to choose file with prompt "Elige el capítulo de InDesign que quieres pasar a Hélice:" of type {"com.adobe.indesign-document", "indd"} default location inicio
	set rutaIndd to POSIX path of indd

	-- 2. Exportar a HTML (heredado) en la misma carpeta
	set jsx to POSIX file (proyecto & "/herramientas/exportar_html.jsx")
	try
		with timeout of 900 seconds
			tell application "Adobe InDesign 2026"
				set res to do script jsx language javascript with arguments {rutaIndd, proyecto & "/salida"}
			end tell
		end timeout
	on error msg
		set res to "error|" & msg
	end try
	activate
	if res does not start with "ok|" then
		display dialog "InDesign no ha podido exportar el HTML:" & return & return & (text 7 thru -1 of res) buttons {"Aceptar"} default button 1 with title titulo with icon stop
		return
	end if
	set rutaHtml to text 4 thru -1 of res

	-- 3. Pausa: subir las imágenes y copiar sus enlaces con el marcador
	set carpetaImagenes to do shell script "ls -d " & quoted form of (my carpetaDe(rutaHtml)) & "/*-web-resources/image 2>/dev/null | head -1"
	if carpetaImagenes is "" then
		-- Todos los capítulos llevan al menos la cabecera: sin imágenes, la exportación ha salido mal
		set tamano to do shell script "stat -f %z " & quoted form of rutaHtml
		display dialog "El HTML exportado no tiene imágenes (" & tamano & " bytes), así que parece que InDesign no ha exportado el capítulo completo." & return & return & ¬
			"Revisa el documento en InDesign y vuelve a intentarlo." buttons {"Aceptar"} default button 1 with title titulo with icon stop
		return
	end if
	set numImagenes to do shell script "ls " & quoted form of carpetaImagenes & " | grep -v '^\\.' | wc -l | tr -d ' '"
	set aviso to "HTML exportado." & return & return & ¬
		"1. Sube a Hélice, en la carpeta del capítulo, las " & numImagenes & " imágenes de:" & return & carpetaImagenes & return & ¬
		"2. Abre esa carpeta en Hélice y pulsa el marcador «Enlaces Hélice»." & return & ¬
		"3. Vuelve aquí y pulsa Continuar."
	set botones to {"Cancelar", "Continuar"}
	repeat
		set boton to button returned of (display dialog aviso buttons botones default button "Continuar" cancel button "Cancelar" with title titulo)
		if boton is "Seguir sin ellas" then
			-- El HTML ya está generado; se trata como un resultado con avisos
			set estado to "AVISOS"
			exit repeat
		end if
		set salida to do shell script quoted form of (proyecto & "/capitulo") & " " & quoted form of rutaHtml & " --resumen"
		set estado to paragraph 1 of salida
		if estado is "FALTAN_URLS" then
			set aviso to "No hay enlaces de Hélice en el portapapeles." & return & return & ¬
				"Abre en Hélice la carpeta con las imágenes del capítulo, pulsa el marcador «Enlaces Hélice» y vuelve a pulsar Continuar."
			set botones to {"Cancelar", "Continuar"}
		else if estado is "FALTAN_IMAGENES" then
			-- Imágenes repartidas en varias páginas del panel: se van sumando los enlaces
			set aviso to my desde(salida, 4)
			set botones to {"Cancelar", "Seguir sin ellas", "Continuar"}
		else
			exit repeat
		end if
	end repeat

	-- 4. Resultado
	set rutaFinal to paragraph 2 of salida
	set rutaVista to paragraph 3 of salida
	set detalle to my desde(salida, 4)
	if estado is "OK" then
		set texto to "HTML depurado copiado al portapapeles." & return & "Pégalo en Hélice con ⌘V." & return & return & detalle
		repeat
			set boton to button returned of (display dialog texto buttons {"Ver vista previa", "Aceptar"} default button "Aceptar" with title titulo)
			if boton is "Aceptar" then exit repeat
			do shell script "open " & quoted form of rutaVista
			activate
		end repeat
	else if estado is "AVISOS" then
		set texto to "El HTML depurado tiene avisos y NO se ha copiado al portapapeles." & return & return & detalle
		repeat
			set boton to button returned of (display dialog texto buttons {"Ver vista previa", "Copiar igualmente", "Cancelar"} default button "Ver vista previa" with title titulo with icon caution)
			if boton is "Cancelar" then exit repeat
			if boton is "Ver vista previa" then
				do shell script "open " & quoted form of rutaVista
				activate
			else
				do shell script "LANG=es_ES.UTF-8 pbcopy < " & quoted form of rutaFinal
				display dialog "HTML depurado copiado al portapapeles." & return & "Pégalo en Hélice con ⌘V." buttons {"Aceptar"} default button 1 with title titulo
				exit repeat
			end if
		end repeat
	else
		display dialog "No se ha podido depurar el HTML:" & return & return & detalle buttons {"Aceptar"} default button 1 with title titulo with icon stop
	end if
end run

on carpetaDe(ruta)
	return do shell script "dirname " & quoted form of ruta
end carpetaDe

on desde(texto, n)
	set lineas to paragraphs of texto
	if (count of lineas) < n then return ""
	set AppleScript's text item delimiters to return
	set resultado to (items n thru -1 of lineas) as text
	set AppleScript's text item delimiters to ""
	return resultado
end desde
