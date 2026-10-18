// Exporta un .indd a "HTML (heredado)" en su misma carpeta, con los ajustes HTML
// guardados en el propio documento (los mismos que usa Archivo > Exportar).
// Uso (AppleScript): do script (POSIX file ".../exportar_html.jsx") language javascript with arguments {"/ruta/al/capitulo.indd"}
// Devuelve "ok|<ruta del html>" o "error|<mensaje>".
(function (ruta) {
    if (!ruta) return "error|No se ha indicado el .indd";
    var indd = File(ruta);
    if (!indd.exists) return "error|No existe " + indd.fsName;

    var nivel = app.scriptPreferences.userInteractionLevel;
    app.scriptPreferences.userInteractionLevel = UserInteractionLevels.NEVER_INTERACT;
    var doc = null, abiertoAntes = false;
    try {
        for (var i = 0; i < app.documents.length; i++) {
            if (app.documents[i].fullName.fsName == indd.fsName) { doc = app.documents[i]; abiertoAntes = true; }
        }
        if (!doc) doc = app.open(indd, false);
        var html = File(indd.parent.fsName + "/" + indd.name.replace(/\.indd$/i, "") + ".html");
        doc.exportFile(ExportFormat.HTML, html, false);
        return "ok|" + html.fsName;
    } catch (e) {
        return "error|" + e;
    } finally {
        if (doc && !abiertoAntes) doc.close(SaveOptions.NO);
        app.scriptPreferences.userInteractionLevel = nivel;
    }
})(arguments[0]); // el "arguments" de do script, no el de la función
