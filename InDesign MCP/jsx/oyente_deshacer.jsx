#targetengine "indesign_mcp"
// Tras los cambios de revisar_cambios, el Cmd+Z del usuario a veces no se redibuja.
// Un oyente en Edición > Deshacer/Rehacer ejecuta un script mínimo después de cada uno,
// y al acabar un script InDesign redibuja la pantalla. Vive mientras InDesign esté abierto.
var NOMBRE = "claude_redibujar", instalados = 0;
var ids = [265, 266];  // Deshacer, Rehacer
for (var i = 0; i < ids.length; i++) {
    var m = app.menuActions.itemByID(ids[i]);
    if (!m.isValid) continue;
    var ya = false;
    for (var j = 0; j < m.eventListeners.length; j++) if (m.eventListeners[j].name === NOMBRE) ya = true;
    if (ya) continue;
    m.addEventListener("afterInvoke", function () {
        try { var w = app.activeWindow; w.zoomPercentage = w.zoomPercentage; } catch (_) {}
    }).name = NOMBRE;
    instalados++;
}
return json({motor: $.engineName, instalados: instalados});
