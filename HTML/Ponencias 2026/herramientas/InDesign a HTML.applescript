-- InDesign a HTML: de un capítulo de InDesign al HTML depurado en el portapapeles.
-- 1. Eliges el .indd. Si es el de imprenta (o un archivo de sección con varios
--    capítulos), se prepara antes una copia para HTML (./preparar) en la carpeta del
--    capítulo de la versión APP; si ya es esa copia, se usa tal cual.
-- 2. InDesign lo exporta a HTML (heredado) en su carpeta.
-- 3. Pausa para subir las imágenes a Hélice y copiar sus enlaces con el marcador.
-- 4. Se depura el HTML; si no hay avisos, queda copiado en el portapapeles.
-- Cada libro tiene su configuración en config/libros/; se reconoce por la carpeta del .indd.
-- Compilar: herramientas/compilar_app.sh

property proyecto : "/Volumes/DATOS/Proyectos Codex/HTML/Ponencias 2026"
property libros : "/Volumes/MACLINE SERVER/LIBROS"
property titulo : "InDesign a HTML"

on run
	-- 1. Elegir el capítulo (por defecto, en la carpeta del último elegido)
	try
		set inicio to (POSIX file (do shell script "cat " & quoted form of (proyecto & "/salida/.ultima_carpeta") & " 2>/dev/null || echo " & quoted form of libros)) as alias
	on error
		set inicio to path to desktop
	end try
	set indd to choose file with prompt "Elige el capítulo de InDesign (el de imprenta, un archivo de sección o la versión ya preparada):" of type {"com.adobe.indesign-document", "indd"} default location inicio
	set rutaIndd to POSIX path of indd
	do shell script "mkdir -p " & quoted form of (proyecto & "/salida") & "; dirname " & quoted form of rutaIndd & " > " & quoted form of (proyecto & "/salida/.ultima_carpeta")

	-- ¿De qué libro es y hay que prepararlo?
	set progress description to "Leyendo el capítulo en InDesign…"
	set plan to do shell script quoted form of (proyecto & "/preparar") & " --plan " & quoted form of rutaIndd
	set tipoIndd to paragraph 1 of plan
	if tipoIndd is "ERROR" then
		display dialog my desde(plan, 3) buttons {"Aceptar"} default button 1 with title titulo with icon stop
		return
	end if
	set nombreLibro to paragraph 2 of plan
	if tipoIndd is not "PREPARADO" then
		set capitulos to items 3 thru -1 of paragraphs of plan
		if tipoIndd is "SECCION" then
			set opciones to {}
			repeat with c in capitulos
				set partes to my trozos(c)
				set texto to "Capítulo " & item 1 of partes
				if item 3 of partes is "EXISTE" then set texto to texto & "   (ya preparado)"
				set end of opciones to texto
			end repeat
			set elegido to choose from list opciones with prompt "«" & nombreLibro & "»: este archivo tiene varios capítulos. ¿Cuál pasas a Hélice?" with title titulo
			if elegido is false then return
			set linea to item (my posicion(item 1 of elegido, opciones)) of capitulos
		else
			set linea to item 1 of capitulos
		end if
		set partes to my trozos(linea)
		set numCap to item 1 of partes
		set copia to item 2 of partes
		set opcionForzar to ""
		if item 3 of partes is "EXISTE" then
			set boton to button returned of (display dialog "El capítulo " & numCap & " ya tiene su versión preparada para HTML:" & return & copia & return & return & ¬
				"¿La usas tal cual o la preparas de nuevo desde este original? (La actual se guarda como «(anterior)».)" buttons {"Cancelar", "Preparar de nuevo", "Usar la preparada"} default button "Usar la preparada" cancel button "Cancelar" with title titulo)
			if boton is "Preparar de nuevo" then set opcionForzar to " --forzar"
		else
			set boton to "Preparar"  -- sin versión preparada: se prepara sin preguntar (el informe dice dónde)
		end if
		if boton is not "Usar la preparada" then
			set progress description to "Preparando el capítulo " & numCap & " en InDesign…"
			with timeout of 1800 seconds
				set res to do shell script quoted form of (proyecto & "/preparar") & " " & quoted form of rutaIndd & " --resumen" & opcionForzar & " --capitulo " & numCap
			end timeout
			set estadoPrep to paragraph 1 of res
			set informePrep to my desde(res, 3)
			if estadoPrep is "ERROR" then
				display dialog "No se ha podido preparar el capítulo:" & return & return & informePrep buttons {"Aceptar"} default button 1 with title titulo with icon stop
				return
			end if
			if estadoPrep is "AVISOS" then
				set texto to "Capítulo preparado, con avisos: revísalos en la copia antes de exportar." & return & return & informePrep
				set icono to caution
			else
				set texto to "Capítulo preparado." & return & return & informePrep
				set icono to note
			end if
			set boton to button returned of (display dialog texto buttons {"Cancelar", "Abrir en InDesign", "Exportar a HTML"} default button "Exportar a HTML" cancel button "Cancelar" with title titulo with icon icono)
			if boton is "Abrir en InDesign" then
				-- Como el Finder (open -a): «open (POSIX file …)» dentro de un tell a InDesign
				-- hacía que InDesign resolviera la ruta, fallaba y la app se cerraba sin avisar
				try
					do shell script "open -a " & quoted form of "Adobe InDesign 2026" & " " & quoted form of copia
				on error msg
					display dialog "No se ha podido abrir en InDesign:" & return & return & msg & return & return & copia buttons {"Aceptar"} default button 1 with title titulo with icon stop
					return
				end try
				display dialog "Cuando lo hayas revisado y guardado, ciérralo, vuelve a abrir esta app y elige:" & return & copia buttons {"Aceptar"} default button 1 with title titulo
				return
			end if
		end if
		set rutaIndd to copia
	end if

	-- 2. Exportar a HTML (heredado) en la misma carpeta
	set progress description to "Exportando a HTML…"
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
	-- Con «ficheros» en el libro, las imágenes se suben a su carpeta de Ficheros de Hélice
	set subida to do shell script quoted form of (proyecto & "/publicar") & " --manifiesto " & quoted form of rutaHtml
	if subida is not "" then
		set aviso to "HTML exportado." & return & return & ¬
			"1. En el panel de Hélice pulsa el marcador «Subir a Hélice» y elige la carpeta del capítulo:" & return & my carpetaDe(rutaHtml) & return & ¬
			"   Sube las " & numImagenes & " imágenes a su carpeta de Ficheros y copia sus enlaces." & return & ¬
			"2. Vuelve aquí y pulsa Continuar."
	else
		set aviso to "HTML exportado." & return & return & ¬
			"1. Sube a Hélice, en la carpeta del capítulo, las " & numImagenes & " imágenes de:" & return & carpetaImagenes & return & ¬
			"2. Abre esa carpeta en Hélice y pulsa el marcador «Enlaces Hélice»." & return & ¬
			"3. Vuelve aquí y pulsa Continuar."
	end if
	-- Si se puede, la app sube las imágenes ella sola desde la pestaña del panel abierta en
	-- Safari o Chrome (./subir) y se salta la pausa; si no, se sigue con el marcador
	set saltarPausa to false
	if subida is not "" then
		set progress description to "Subiendo a Hélice las " & numImagenes & " imágenes…"
		with timeout of 1800 seconds
			set resSubida to do shell script quoted form of (proyecto & "/subir") & " " & quoted form of rutaHtml & " 2>&1; true"
		end timeout
		if paragraph 1 of resSubida is "OK" then
			set saltarPausa to true
		else
			display dialog "No se han podido subir las imágenes automáticamente:" & return & return & my desde(resSubida, 2) & return & return & ¬
				"Puedes subirlas con el marcador «Subir a Hélice»." buttons {"Cancelar", "Usar el marcador"} default button "Usar el marcador" cancel button "Cancelar" with title titulo with icon caution
		end if
	end if
	set botones to {"Cancelar", "Continuar"}
	repeat
		if saltarPausa then
			set saltarPausa to false
			set boton to "Continuar"
		else
			set boton to button returned of (display dialog aviso buttons botones default button "Continuar" cancel button "Cancelar" with title titulo)
		end if
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
	-- La CSS del libro ha cambiado (libro nuevo): se ofrece copiarla para pegarla en Hélice
	if detalle contains "la CSS del libro ha cambiado" then
		set boton to button returned of (display dialog "Este capítulo trae CSS nueva (estilos o fuentes que no tenían los anteriores)." & return & return & ¬
			"Cópiala y añádela al final de la CSS del libro en Hélice antes de pegar o publicar el HTML. Solo se copia lo nuevo." buttons {"Más tarde", "Copiar la CSS nueva"} default button "Copiar la CSS nueva" with title titulo)
		if boton is "Copiar la CSS nueva" then
			set resCss to do shell script quoted form of (proyecto & "/css_libro") & " --copiar " & quoted form of rutaFinal
			display dialog resCss & return & return & "Después pulsa Continuar." buttons {"Continuar"} default button 1 with title titulo
		end if
	end if

	-- ¿Se publica por la API? Entonces no se habla del portapapeles (se publica en su sitio)
	set planPub to ""
	if estado is "OK" or estado is "AVISOS" then
		set planPub to do shell script quoted form of (proyecto & "/publicar") & " --plan " & quoted form of rutaFinal
	end if
	set publicable to (planPub starts with "SI")

	set listo to false
	if estado is "OK" then
		set listo to true
		if publicable then
			set texto to detalle
			if texto is "" then set texto to "HTML depurado sin avisos."
		else
			set texto to "HTML depurado copiado al portapapeles." & return & "Pégalo en Hélice con ⌘V." & return & return & detalle
		end if
		repeat
			set boton to button returned of (display dialog texto buttons {"Ver vista previa", "Aceptar"} default button "Aceptar" with title titulo)
			if boton is "Aceptar" then exit repeat
			do shell script "open " & quoted form of rutaVista
			activate
		end repeat
	else if estado is "AVISOS" then
		if publicable then
			set texto to "El HTML depurado tiene avisos: revísalos antes de publicarlo." & return & return & detalle
			set seguir to "Continuar igualmente"
		else
			set texto to "El HTML depurado tiene avisos y NO se ha copiado al portapapeles." & return & return & detalle
			set seguir to "Copiar igualmente"
		end if
		repeat
			set boton to button returned of (display dialog texto buttons {"Ver vista previa", seguir, "Cancelar"} default button "Ver vista previa" with title titulo with icon caution)
			if boton is "Cancelar" then exit repeat
			if boton is "Ver vista previa" then
				do shell script "open " & quoted form of rutaVista
				activate
			else if publicable then
				set listo to true
				exit repeat
			else
				do shell script "LANG=es_ES.UTF-8 pbcopy < " & quoted form of rutaFinal
				display dialog "HTML depurado copiado al portapapeles." & return & "Pégalo en Hélice con ⌘V." buttons {"Aceptar"} default button 1 with title titulo
				set listo to true
				exit repeat
			end if
		end repeat
	else
		display dialog "No se ha podido depurar el HTML:" & return & return & detalle buttons {"Aceptar"} default button 1 with title titulo with icon stop
	end if

	-- 5. Publicar en Hélice por la API (libros con «publicar» configurado; solo capítulos nuevos)
	if listo and publicable then
		set boton to button returned of (display dialog "¿Publicar el capítulo en Hélice, en «" & paragraph 2 of planPub & "»?" & return & return & ¬
			"Antes, sube a Hélice la CSS del libro si te lo ha pedido. Solo se publica una vez: las correcciones, en el panel." buttons {"No", "Publicar"} default button "Publicar" with title titulo)
		if boton is "Publicar" then
			set progress description to "Publicando en Hélice…"
			set res to do shell script quoted form of (proyecto & "/publicar") & " " & quoted form of rutaFinal & " 2>&1; true"
			display dialog res buttons {"Aceptar"} default button 1 with title titulo
		end if
	end if
end run

on trozos(linea)
	set AppleScript's text item delimiters to "|"
	set r to text items of linea
	set AppleScript's text item delimiters to ""
	return r
end trozos

on posicion(x, lista)
	repeat with i from 1 to count of lista
		if item i of lista is x then return i
	end repeat
	return 0
end posicion

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
