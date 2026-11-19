/*  Viudas Huerfanas — afloja un paso los párrafos seleccionados (para asignarle atajo de teclado) */
#targetengine "viudasHuerfanas"
#include "lib/ajuste.jsxinc"

(function () {
    var ps = VH.parrafosSeleccion();
    if (ps.length === 0) return;
    VH.enUnPaso("Aflojar párrafo", function () { VH.paso(ps, 1, VH.colorearActivo()); });
    try { if (VH.ventana && VH.refrescar) VH.refrescar(); } catch (e) {}
})();
