// Exporta un .indd a "HTML (heredado)" en su misma carpeta, con los ajustes HTML
// guardados en el propio documento (los mismos que usa Archivo > Exportar).
// Uso (AppleScript): do script (POSIX file ".../exportar_html.jsx") language javascript
//                    with arguments {"/ruta/al/capitulo.indd", "/carpeta/para/fuentes"}
// Devuelve "ok|<ruta del html>" o "error|<mensaje>".
//
// Si se indica la segunda carpeta, escribe en ella "<capítulo>.fuentes.tsv" con la
// fuente real de cada tramo de texto (texto, familia, estilo). La CSS que genera
// InDesign no sirve para el peso: exporta como "font-weight: normal" tanto Light como
// Regular o Medium; el depurador usa este archivo para poner el peso correcto.
// Con un tercer argumento "solo_fuentes" no exporta: solo escribe ese archivo.
//
// Ojo: la exportación HTML (heredado) toma el contenido del DOCUMENTO ACTIVO, no del
// documento sobre el que se llama exportFile. Por eso el capítulo se abre con ventana
// y se pone en primer plano antes de exportar (si no, con otro documento abierto se
// exporta ese otro: pasó con la portadilla de sección en el capítulo 37).
function guardarFuentes(doc, carpeta, nombre) {
    var f = File(carpeta + "/" + nombre + ".fuentes.tsv");
    f.encoding = "UTF-8";
    f.lineFeed = "Unix";  // por defecto ExtendScript escribe CR (Mac antiguo)
    if (!f.open("w")) return;
    var limpiar = function (s) { return String(s).replace(/[\t\r\n]+/g, " "); };
    for (var s = 0; s < doc.stories.length; s++) {
        var rangos = doc.stories[s].textStyleRanges.everyItem().getElements();
        for (var r = 0; r < rangos.length; r++) {
            var t = rangos[r].contents;
            if (typeof t != "string" || !/\S/.test(t)) continue;
            try {
                f.writeln(limpiar(t) + "\t" + rangos[r].appliedFont.fontFamily + "\t" + rangos[r].fontStyle);
            } catch (e) {}  // fuente que falta: se omite
        }
    }
    f.close();
}

(function (ruta, carpetaFuentes, modo) {
    if (!ruta) return "error|No se ha indicado el .indd";
    var indd = File(ruta);
    if (!indd.exists) return "error|No existe " + indd.fsName;

    var nivel = app.scriptPreferences.userInteractionLevel;
    app.scriptPreferences.userInteractionLevel = UserInteractionLevels.NEVER_INTERACT;
    var anterior = app.documents.length ? app.activeDocument : null;
    var doc = null, abiertoAntes = false;
    try {
        for (var i = 0; i < app.documents.length; i++) {
            if (app.documents[i].fullName.fsName == indd.fsName) { doc = app.documents[i]; abiertoAntes = true; }
        }
        if (modo == "solo_fuentes") {
            if (!doc) doc = app.open(indd, false);
            guardarFuentes(doc, carpetaFuentes, indd.name.replace(/\.indd$/i, ""));
            return "ok|solo_fuentes";
        }
        if (!doc) doc = app.open(indd, true);
        app.activeDocument = doc;
        if (app.activeDocument.fullName.fsName != indd.fsName) {
            return "error|No se ha podido poner en primer plano " + indd.name;
        }
        var html = File(indd.parent.fsName + "/" + indd.name.replace(/\.indd$/i, "") + ".html");
        // Sin abrir el HTML en el navegador al terminar («Ver HTML después de exportar»)
        var ver = doc.htmlExportPreferences.viewDocumentAfterExport;
        doc.htmlExportPreferences.viewDocumentAfterExport = false;
        try {
            doc.exportFile(ExportFormat.HTML, html, false);
        } finally {
            if (abiertoAntes) doc.htmlExportPreferences.viewDocumentAfterExport = ver;
        }
        if (carpetaFuentes) guardarFuentes(doc, carpetaFuentes, indd.name.replace(/\.indd$/i, ""));
        return "ok|" + html.fsName;
    } catch (e) {
        return "error|" + e;
    } finally {
        if (doc && !abiertoAntes && doc.isValid) doc.close(SaveOptions.NO);
        if (anterior && anterior.isValid) app.activeDocument = anterior;
        app.scriptPreferences.userInteractionLevel = nivel;
    }
})(arguments[0], arguments[1], arguments[2]); // el "arguments" de do script, no el de la función
