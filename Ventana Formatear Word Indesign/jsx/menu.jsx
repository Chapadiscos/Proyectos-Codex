// Añade «Formatear Word» al final del menú Ventana: abre o cierra (oculta) la ventana.
// Se ejecuta en el motor persistente "formatear_word" desde el script de arranque de InDesign
// (instalacion/startup scripts - Formatear Word (menú).jsx). Se puede volver a ejecutar: no
// duplica nada.

#targetengine "formatear_word"

(function () {
    var NOMBRE = "Formatear Word";
    var VENTANA = File(File($.fileName).parent.fsName + "/ventana.jsx");

    function ventana() {
        var F = $.global.formatearWord;
        return F && F.ventana ? F.ventana : null;
    }

    var accion = app.scriptMenuActions.itemByName(NOMBRE);
    if (!accion.isValid) accion = app.scriptMenuActions.add(NOMBRE);
    while (accion.eventListeners.length) accion.eventListeners[0].remove();
    accion.addEventListener("onInvoke", function () {
        var w = ventana();
        if (w && w.visible) w.hide();
        else $.evalFile(VENTANA);           // crea la ventana o muestra la oculta
    });
    accion.addEventListener("beforeDisplay", function () {
        var w = ventana();
        accion.checked = !!(w && w.visible);
    });

    var menuVentana = app.menus.item("$ID/Main").submenus.item("$ID/&Window");
    if (!menuVentana.menuItems.itemByName(NOMBRE).isValid) menuVentana.menuItems.add(accion, LocationOptions.AT_END);
})();
