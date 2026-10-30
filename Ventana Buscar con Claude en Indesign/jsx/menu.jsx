// Añade «Buscar con Claude» al final del menú Ventana: abre o cierra (oculta) la ventana.
// Se ejecuta en el motor persistente "indesign_mcp" desde el script de arranque de InDesign,
// que define INDESIGN_MCP. Se puede volver a ejecutar: no duplica nada.
var NOMBRE = "Buscar con Claude";

function ventanaBuscador() {
    var B = $.global.buscadorClaude;
    return B && B.ventana ? B.ventana : null;
}

var accion = app.scriptMenuActions.itemByName(NOMBRE);
if (!accion.isValid) accion = app.scriptMenuActions.add(NOMBRE);
while (accion.eventListeners.length) accion.eventListeners[0].remove();
accion.addEventListener("onInvoke", function () {
    var w = ventanaBuscador();
    if (w && w.visible) w.hide();
    else $.evalFile(File(INDESIGN_MCP + "/jsx/buscador.jsx"));  // crea la ventana o muestra la oculta
});
accion.addEventListener("beforeDisplay", function () {
    var w = ventanaBuscador();
    accion.checked = !!(w && w.visible);
});

var menuVentana = app.menus.item("$ID/Main").submenus.item("$ID/&Window");
if (!menuVentana.menuItems.itemByName(NOMBRE).isValid) menuVentana.menuItems.add(accion, LocationOptions.AT_END);
