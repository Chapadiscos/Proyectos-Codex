// Coloca VS Code en la mitad izquierda de la pantalla principal e InDesign en la derecha.
// Uso: osascript -l JavaScript ventanas.js   (necesita permiso de Accesibilidad para quien lo lance)
ObjC.import("AppKit");

function run() {
    var pantalla = $.NSScreen.screens.objectAtIndex(0);   // la de la barra de menús
    var total = pantalla.frame, util = pantalla.visibleFrame;
    // Cocoa cuenta desde abajo; System Events, desde arriba.
    var x = util.origin.x, y = total.size.height - util.origin.y - util.size.height;
    var mitad = Math.floor(util.size.width / 2), alto = util.size.height;

    var se = Application("System Events"), avisos = [];
    function colocar(proceso, izq, ancho) {
        if (!se.processes[proceso].exists()) { avisos.push(proceso + " no está abierto"); return; }
        var ventanas = se.processes[proceso].windows;
        if (ventanas.length === 0) { avisos.push(proceso + " no tiene ventanas"); return; }
        ventanas[0].position = [izq, y];
        ventanas[0].size = [ancho, alto];
    }
    colocar("Code", x, mitad);
    colocar("Adobe InDesign 2026", x + mitad, util.size.width - mitad);
    return avisos.length ? avisos.join("; ") : "Ventanas colocadas";
}
