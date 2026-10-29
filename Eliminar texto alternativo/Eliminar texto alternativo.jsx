// Eliminar texto alternativo.jsx
// Adobe InDesign — elimina el texto alternativo de todas las imágenes del documento activo.
//
// - Recorre todas las imágenes (incluidas las anclas en texto, en páginas maestras y en la mesa de trabajo).
// - Para el marco de cada imagen (donde InDesign guarda el texto alternativo):
//     · fija el origen del texto alternativo en "Personalizado" (así no se recupera
//       desde los metadatos XMP del vínculo: título, descripción, titular...)
//     · deja el texto alternativo personalizado vacío.
// - Toda la operación se deshace con un solo Cmd/Ctrl+Z.

#target indesign

(function () {
    if (app.documents.length === 0) {
        alert("No hay ningún documento abierto.");
        return;
    }

    var doc = app.activeDocument;
    var resultado = { objetos: 0, cambiados: 0, errores: 0 };

    app.doScript(
        function () { procesar(doc, resultado); },
        ScriptLanguage.JAVASCRIPT,
        undefined,
        UndoModes.ENTIRE_SCRIPT,
        "Eliminar texto alternativo"
    );

    var msg = "Texto alternativo eliminado.\n\n" +
              "Imágenes encontradas: " + resultado.objetos + "\n" +
              "Objetos modificados: " + resultado.cambiados;
    if (resultado.errores > 0) {
        msg += "\nObjetos que no se pudieron modificar (p. ej. capas bloqueadas): " + resultado.errores;
    }
    alert(msg);

    // ------------------------------------------------------------------

    function procesar(doc, res) {
        var graficos = doc.allGraphics;
        res.objetos = graficos.length;

        // El texto alternativo vive en el marco (rectángulo, elipse, polígono),
        // no en la imagen colocada.
        for (var i = 0; i < graficos.length; i++) {
            try { limpiar(graficos[i].parent, res); }
            catch (e) {}
        }
    }

    function limpiar(obj, res) {
        var opts;
        try {
            opts = obj.objectExportOptions;
            if (!opts || !opts.isValid) return;
        } catch (e) {
            return; // el objeto no admite opciones de exportación
        }

        try {
            var yaVacio = opts.altTextSourceType == SourceType.SOURCE_CUSTOM &&
                          opts.customAltText === "";
            if (yaVacio) return;

            opts.altTextSourceType = SourceType.SOURCE_CUSTOM;
            opts.customAltText = "";
            res.cambiados++;
        } catch (e) {
            res.errores++;
        }
    }
})();
