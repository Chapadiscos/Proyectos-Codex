/*  Viudas Huerfanas — panel para ajustar a mano el espaciado de los párrafos
    y buscar viudas, huérfanas, líneas cortas y texto desbordado.
*/
#targetengine "viudasHuerfanas"
#include "lib/ajuste.jsxinc"

(function () {
    if (VH.ventana) {
        try { VH.ventana.show(); VH.refrescar(); return; } catch (e) { VH.ventana = null; }
    }

    var w = new Window("palette", "Viudas y huérfanas", undefined, { resizeable: true });
    w.orientation = "column";
    w.alignChildren = ["fill", "top"];
    w.spacing = 8;
    w.margins = 12;

    // ------------------------------------------------ ajuste del párrafo
    var gA = w.add("panel", undefined, "Ajuste del párrafo");
    gA.alignChildren = ["fill", "top"];
    gA.spacing = 6;
    gA.margins = [10, 14, 10, 10];

    var tParrafo = gA.add("statictext", undefined, "", { truncate: "end" });
    tParrafo.preferredSize.width = 300;

    var gS = gA.add("group");
    gS.alignChildren = ["center", "center"];
    gS.add("statictext", undefined, "Apretar");
    var deslizador = gS.add("slider", undefined, 0, -VH.MAX, VH.MAX);
    deslizador.preferredSize.width = 190;
    gS.add("statictext", undefined, "Aflojar");

    var gN = gA.add("group");
    var tNivel = gN.add("statictext", undefined, "");
    tNivel.preferredSize.width = 110;
    var tLineas = gN.add("statictext", undefined, "");
    tLineas.preferredSize.width = 180;

    var tValores = gA.add("statictext", undefined, "", { truncate: "end" });
    tValores.graphics.font = ScriptUI.newFont(tValores.graphics.font.name, "REGULAR", 10);

    var gB = gA.add("group");
    gB.alignChildren = ["fill", "center"];
    var bMenos = gB.add("button", undefined, "−1 línea");
    bMenos.helpTip = "Aprieta lo justo para que el párrafo pierda una línea";
    var bMas = gB.add("button", undefined, "+1 línea");
    bMas.helpTip = "Afloja lo justo para que el párrafo gane una línea";
    var bRestablecer = gB.add("button", undefined, "Restablecer");
    bRestablecer.helpTip = "Vuelve a los valores del estilo de párrafo";

    var gC = gA.add("group");
    var cColorear = gC.add("checkbox", undefined, "Colorear ajustes");
    cColorear.helpTip = "Marca los párrafos ajustados con texto condicional (no se imprime)";
    cColorear.value = VH.colorearActivo();
    var bQuitarColores = gC.add("button", undefined, "Quitar colores");
    bQuitarColores.helpTip = "Quita las marcas de color de todo el documento (los ajustes se quedan)";

    // ------------------------------------------------ buscar problemas
    var gP = w.add("panel", undefined, "Buscar problemas");
    gP.alignChildren = ["fill", "top"];
    gP.spacing = 6;
    gP.margins = [10, 14, 10, 10];

    var gT = gP.add("group");
    var cViuda = gT.add("checkbox", undefined, "Viudas");
    var cHuerfana = gT.add("checkbox", undefined, "Huérfanas");
    var cDesbordado = gT.add("checkbox", undefined, "Desbordado");
    cViuda.helpTip = "Última línea de un párrafo sola al principio de columna o página";
    cHuerfana.helpTip = "Primera línea de un párrafo sola al final de columna o página";
    var gT2 = gP.add("group");
    var cCorta = gT2.add("checkbox", undefined, "Líneas cortas: menos del");
    var eCorta = gT2.add("edittext", undefined, VH.pref("cortaPorc", "20"));
    eCorta.characters = 3;
    gT2.add("statictext", undefined, "% del ancho");
    cCorta.helpTip = "Última línea de un párrafo más estrecha que ese porcentaje de sus otras líneas";
    cViuda.value = VH.pref("viuda", "1") === "1";
    cHuerfana.value = VH.pref("huerfana", "1") === "1";
    cDesbordado.value = VH.pref("desbordado", "1") === "1";
    cCorta.value = VH.pref("corta", "1") === "1";

    var gE = gP.add("group");
    gE.add("statictext", undefined, "En:");
    var dAmbito = gE.add("dropdownlist", undefined, ["Documento", "Artículo"]);
    dAmbito.selection = 0;
    var bBuscar = gE.add("button", undefined, "Buscar");

    var lista = gP.add("listbox", undefined, [], {
        numberOfColumns: 3, showHeaders: true, columnTitles: ["Pág.", "Tipo", "Texto"],
        columnWidths: [40, 80, 180]
    });
    lista.preferredSize = [300, 200];
    var tEstado = gP.add("statictext", undefined, "", { truncate: "end" });

    VH.resultados = [];
    VH.lineasIniciales = {};

    // ------------------------------------------------ lógica

    function clave(p) {
        try { return p.parentStory.id + ":" + p.insertionPoints[0].index; } catch (e) { return ""; }
    }

    function textoNivel(n) {
        if (n === null) return "Ajuste: a mano";
        if (n === 0) return "Ajuste: estilo";
        return "Ajuste: " + (n < 0 ? "−" + (-n) : "+" + n);
    }

    function signo(v) { return (v > 0 ? "+" : (v < 0 ? "−" : "")) + Math.abs(Math.round(v * 10) / 10); }

    var nivelMostrado = 0, arrastrando = false;

    // dejarDeslizador: durante el arrastre no se mueve el deslizador (lo lleva el usuario)
    VH.refrescar = function (dejarDeslizador) {
        var ps = VH.parrafosSeleccion();
        var activo = ps.length > 0;
        deslizador.enabled = bMenos.enabled = bMas.enabled = bRestablecer.enabled = activo;
        bQuitarColores.enabled = bBuscar.enabled = app.documents.length > 0;
        if (!activo) {
            tParrafo.text = "Pon el cursor en un párrafo";
            tNivel.text = tLineas.text = tValores.text = "";
            deslizador.value = 0;
            nivelMostrado = 0;
            return;
        }
        var p = ps[0];
        var t = String(p.contents).replace(/[\r\n\t]+/g, " ");
        tParrafo.text = (ps.length > 1 ? ps.length + " párrafos · " : "") + p.appliedParagraphStyle.name + " · «" + t.substr(0, 60) + "»";
        var n = VH.detectarNivel(p);
        nivelMostrado = (n === null) ? 0 : n;
        if (!dejarDeslizador) deslizador.value = nivelMostrado;
        tNivel.text = textoNivel(n);

        var k = clave(p), l = p.lines.length;
        if (!(k in VH.lineasIniciales)) VH.lineasIniciales[k] = l;
        var l0 = VH.lineasIniciales[k];
        tLineas.text = (l0 === l) ? l + " líneas" : l0 + " → " + l + " líneas";

        var b = VH.base(p), a = VH.actuales(p), dt = 0;
        try { dt = p.characters[0].tracking - b.tracking; } catch (e) {}
        tValores.text = "Palabras " + Math.round(a.pMin) + "/" + Math.round(a.pDes) + "/" + Math.round(a.pMax) + " %" +
            " · Letras " + signo(a.lDes) + " %" + " · Glifos " + Math.round(a.gDes * 10) / 10 + " %" +
            " · Tracking " + signo(dt);
    };

    function conParrafos(nombre, fn, sumarAlAnterior, dejarDeslizador) {
        var ps = VH.parrafosSeleccion();
        if (ps.length === 0) return;
        try { VH.enUnPaso(nombre, function () { fn(ps); }, sumarAlAnterior); }
        catch (e) { tEstado.text = "Error: " + e.message; }
        VH.refrescar(dejarDeslizador);
    }

    // Aplica en tiempo real cada vez que el deslizador pasa a otro nivel.
    // El primer cambio de un arrastre abre un paso de deshacer; los siguientes se suman a él.
    function aplicarNivel(n, durante) {
        if (n === nivelMostrado) return;
        var sumar = arrastrando;
        arrastrando = durante;
        conParrafos("Ajuste de párrafo", function (ps) {
            for (var i = 0; i < ps.length; i++) VH.aplicar(ps[i], n, cColorear.value);
        }, sumar, durante);
    }
    deslizador.onChanging = function () {
        aplicarNivel(Math.round(deslizador.value), true);
    };
    deslizador.onChange = function () {
        var n = Math.round(deslizador.value);
        deslizador.value = n;
        aplicarNivel(n, false);
        arrastrando = false;
    };

    function cambiarLinea(d) {
        var fallos = 0;
        conParrafos(d < 0 ? "Quitar una línea" : "Añadir una línea", function (ps) {
            fallos = VH.cambiarLinea(ps, d, cColorear.value);
        });
        if (fallos) tEstado.text = (fallos === 1 ? "El párrafo no " : fallos + " párrafos no ") +
            (d < 0 ? "pierde" : "gana") + (fallos === 1 ? "" : "n") + " una línea ni al máximo; se queda como estaba.";
        else tEstado.text = "";
    }
    bMenos.onClick = function () { cambiarLinea(-1); };
    bMas.onClick = function () { cambiarLinea(1); };
    bRestablecer.onClick = function () {
        conParrafos("Restablecer párrafo", function (ps) { VH.restablecer(ps); });
    };

    cColorear.onClick = function () { VH.guardarPref("colorear", cColorear.value ? "1" : "0"); };
    bQuitarColores.onClick = function () {
        if (app.documents.length === 0) return;
        var n = 0, doc = app.activeDocument;
        try { VH.enUnPaso("Quitar colores de ajuste", function () { n = VH.quitarColoresDocumento(doc); }); }
        catch (e) { tEstado.text = "Error: " + e.message; return; }
        tEstado.text = n ? "Colores quitados." : "No había colores de ajuste.";
    };

    function guardarOpciones() {
        VH.guardarPref("viuda", cViuda.value ? "1" : "0");
        VH.guardarPref("huerfana", cHuerfana.value ? "1" : "0");
        VH.guardarPref("desbordado", cDesbordado.value ? "1" : "0");
        VH.guardarPref("corta", cCorta.value ? "1" : "0");
        VH.guardarPref("cortaPorc", eCorta.text);
    }

    bBuscar.onClick = function () {
        if (app.documents.length === 0) return;
        guardarOpciones();
        var doc = app.activeDocument, stories;
        if (dAmbito.selection.index === 1) {
            var s = app.selection.length ? app.selection[0] : null;
            try { stories = [s.parentStory]; } catch (e) { tEstado.text = "Pon el cursor en el artículo."; return; }
        } else {
            stories = doc.stories.everyItem().getElements();
        }
        var porc = parseFloat(eCorta.text);
        if (isNaN(porc) || porc <= 0) porc = 20;
        lista.removeAll();
        tEstado.text = "Buscando…";
        w.update();
        var inicio = new Date();
        try {
            VH.resultados = VH.buscar(stories, {
                viuda: cViuda.value, huerfana: cHuerfana.value, desbordado: cDesbordado.value,
                corta: cCorta.value, cortaPorc: porc
            });
        } catch (e) { tEstado.text = "Error: " + e.message; return; }
        for (var i = 0; i < VH.resultados.length; i++) {
            var r = VH.resultados[i];
            var it = lista.add("item", r.pagina);
            it.subItems[0].text = r.tipo;
            it.subItems[1].text = VH.resumen(r);
        }
        var seg = Math.round((new Date() - inicio) / 100) / 10;
        tEstado.text = VH.resultados.length === 0 ? "Sin problemas (" + seg + " s)." :
            VH.resultados.length + " resultado" + (VH.resultados.length === 1 ? "" : "s") + " (" + seg + " s). Tras ajustar, vuelve a buscar.";
    };

    lista.onChange = function () {
        if (!lista.selection) return;
        var r = VH.resultados[lista.selection.index];
        try { VH.mostrar(r); } catch (e) { tEstado.text = "Ya no está (busca de nuevo)."; }
        VH.refrescar();
    };

    // ------------------------------------------------ eventos

    function quitarOyente() {
        try { if (VH.oyente && VH.oyente.isValid) VH.oyente.remove(); } catch (e) {}
        VH.oyente = null;
    }
    quitarOyente();
    VH.alCambiarSeleccion = function () { try { if (VH.ventana && VH.ventana.visible) VH.refrescar(); } catch (e) {} };
    VH.oyente = app.addEventListener("afterSelectionChanged", VH.alCambiarSeleccion);

    w.onActivate = function () { try { VH.refrescar(); } catch (e) {} };
    w.onResizing = w.onResize = function () { w.layout.resize(); };
    w.onClose = function () { quitarOyente(); VH.ventana = null; };

    VH.ventana = w;
    VH.refrescar();
    w.show();
})();
