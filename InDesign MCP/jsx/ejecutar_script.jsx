// Ejecuta ARGS.codigo sobre el documento activo como un único paso de deshacer
// llamado ARGS.descripcion. Si el código falla, se deshace lo que hubiera hecho.
if (app.documents.length === 0) throw new Error("No hay ningún documento abierto");
var doc = app.activeDocument;
if (!doc.saved) throw new Error("El documento «" + doc.name + "» no se ha guardado nunca; guárdalo antes de modificarlo");

try { var cuerpo = new Function("doc", ARGS.codigo); }
catch (e) { return json({__error: "Error de sintaxis en el código: " + e.message + "; no se cambió nada"}); }
var pasos = doc.undoHistory.length, resultado, fallo = null;
app.doScript(function () {
    try { resultado = cuerpo(doc); } catch (e) { fallo = e; }
}, ScriptLanguage.JAVASCRIPT, undefined, UndoModes.ENTIRE_SCRIPT, ARGS.descripcion);

var hubo_cambios = doc.undoHistory.length > pasos || doc.undoName === ARGS.descripcion;
if (fallo) {
    if (hubo_cambios) doc.undo();
    return json({__error: (fallo.message || String(fallo)) + " (línea " + (fallo.line - 1) + " del código)" +
                          (hubo_cambios ? "; se han deshecho los cambios parciales" : "; no se cambió nada")});
}
return json({resultado: resultado, deshacer: hubo_cambios ? doc.undoName : null});
