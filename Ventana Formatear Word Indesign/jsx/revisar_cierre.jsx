// Ventana «Revisar cierre»: recorre uno a uno los cambios del cierre del capítulo del documento
// activo (los mismos que «Finalizar capítulo», cierre_comun.jsx), con el antes y el después de
// cada uno, para aplicarlos u omitirlos.
// - Aplicar: hace ese cambio (un paso de deshacer).
// - Omitir: lo deja como está; no vuelve a salir mientras la ventana siga abierta.
// - Aplicar todos: los de la lista (todos o los del tipo elegido), en un paso de deshacer.
// Motor persistente "formatear_word"; la ventana vive en $.global.revisarCierre.

#targetengine "formatear_word"

(function () {
    var RAIZ = File($.fileName).parent.parent;     // carpeta del proyecto
    var PYTHON = "/Library/Frameworks/Python.framework/Versions/3.14/bin/python3";
    $.evalFile(File(RAIZ.fsName + "/jsx/cierre_comun.jsx"));

    if ($.global.revisarCierre && $.global.revisarCierre.ventana) {
        $.global.revisarCierre.cargar();
        $.global.revisarCierre.ventana.show();
        return;
    }
    var C = $.global.revisarCierre = {};
    C.omitidas = {};

    var TIPOS = { puntuacion: "Puntuación con el formato de su palabra", url: "URL → hipervínculo", doi: "DOI → hipervínculo" };
    var NBSP = String.fromCharCode(0xA0);
    function visible(s) { return String(s).split(NBSP).join("·").replace(/\r/g, "¶").replace(/\t/g, "→"); }

    function q(s) { return "'" + String(s).replace(/'/g, "'\\''") + "'"; }
    function leerJSON(f) {
        f.encoding = "UTF-8";
        if (!f.exists || !f.open("r")) return null;
        var t = f.read();
        f.close();
        return eval("(" + t + ")");
    }

    // Estilos que no pasan a la puntuación (superíndice, símbolos), de la publicación elegida
    function leerDatos() {
        var f = File(Folder.temp.fsName + "/formatear_word_cierre.json");
        var orden = "cd " + q(RAIZ.fsName) + " && " + q(PYTHON) + " -I finalizar.py --exportar " + q(f.fsName) +
            ($.global.formatearWordPublicacion ? " --publicacion " + q($.global.formatearWordPublicacion) : "") + " 2>&1";
        app.doScript('do shell script "' + orden.replace(/\\/g, "\\\\").replace(/"/g, '\\"') + '"', ScriptLanguage.APPLESCRIPT_LANGUAGE);
        return leerJSON(f);
    }

    function rango(c) { return resolve(c.cont.characters.itemByRange(c.ini, c.ini + c.len - 1).toSpecifier()); }

    function huella(c) {
        try {
            var t = rango(c), p = t.paragraphs[0], pc = p.contents, o = t.index - p.index;
            return c.tipo + "|" + pc.substring(Math.max(0, o - 20), o) + "[" + c.texto + "]" + pc.substr(o + c.len, 20);
        } catch (e) { return c.tipo + "|" + c.texto; }
    }

    function buscar(d) {
        var res = cambiosCierre(d, C.datos.excluir);
        for (var i = 0; i < res.length; i++) {
            var c = res[i];
            c.orden = i;
            c.pagina = "—"; c.clavePag = 1e6;
            try {
                var fr = rango(c).parentTextFrames[0], pg = fr.parentPage;
                if (pg) { c.pagina = pg.name; c.clavePag = pg.documentOffset; }
                else { var sp = fr.parent; while (sp && !(sp instanceof Spread)) sp = sp.parent;
                       c.pagina = "mesa " + sp.pages[sp.pages.length - 1].name; c.clavePag = sp.pages[sp.pages.length - 1].documentOffset + 0.5; }
            } catch (e) {}
            c.huella = huella(c);
        }
        res.sort(function (a, b) { return a.clavePag - b.clavePag || a.orden - b.orden; });
        var quedan = [];
        for (var i = 0; i < res.length; i++) if (!C.omitidas[res[i].huella]) quedan.push(res[i]);
        return quedan;
    }

    function enUnPaso(nombre, fn) {
        if (!C.doc || !C.doc.isValid) { C.cargar(); throw new Error("El documento ya no está abierto"); }
        app.doScript(fn, ScriptLanguage.JAVASCRIPT, undefined, UndoModes.ENTIRE_SCRIPT, nombre);
    }

    // ---- ventana ---------------------------------------------------------------------------
    var w = C.ventana = new Window("palette", "Revisar cierre", undefined, { resizeable: true });
    w.orientation = "column";
    w.alignChildren = ["fill", "top"];
    var cab = w.add("group");
    cab.alignChildren = ["left", "center"];
    var titulo = cab.add("statictext", undefined, "", { characters: 34, truncate: "end" });
    cab.add("statictext", undefined, "Ver:");
    var filtro = cab.add("dropdownlist", undefined, []);
    filtro.preferredSize.width = 300;
    var bActualizar = cab.add("button", undefined, "Actualizar");
    bActualizar.helpTip = "Vuelve a buscar los cambios del documento activo (también tras un Cmd+Z)";

    var lb = w.add("listbox", [0, 0, 760, 240], undefined, {
        numberOfColumns: 4, showHeaders: true,
        columnTitles: ["Nº", "Cambio", "Pág.", "Texto"], columnWidths: [40, 250, 50, 400] });
    lb.alignment = ["fill", "fill"];

    var pCmp = w.add("panel", undefined, "Cambio");
    pCmp.alignChildren = ["fill", "top"];
    var gCmp = pCmp.add("group"); gCmp.alignment = ["fill", "top"]; gCmp.alignChildren = ["fill", "top"];
    var pA = gCmp.add("panel", undefined, "Antes"); pA.alignChildren = ["fill", "top"];
    var antes = pA.add("statictext", [0, 0, 350, 48], "", { multiline: true });
    var pD = gCmp.add("panel", undefined, "Después"); pD.alignChildren = ["fill", "top"];
    var despues = pD.add("statictext", [0, 0, 350, 48], "", { multiline: true });
    var explica = pCmp.add("statictext", [0, 0, 740, 32], "", { multiline: true });

    var gBot = w.add("group");
    gBot.alignment = ["fill", "top"];
    var bAnt = gBot.add("button", undefined, "◀ Anterior");
    var bSig = gBot.add("button", undefined, "Siguiente ▶");
    var hueco = gBot.add("group"); hueco.alignment = ["fill", "center"];
    var bAplicar = gBot.add("button", undefined, "Aplicar");
    bAplicar.helpTip = "Hace este cambio (un Cmd+Z lo deshace) y pasa al siguiente";
    var bOmitir = gBot.add("button", undefined, "Omitir");
    bOmitir.helpTip = "Lo deja como está y pasa al siguiente";
    var bTodos = gBot.add("button", undefined, "Aplicar todos");
    bTodos.helpTip = "Hace todos los de la lista (si has elegido un tipo en «Ver», solo los de ese tipo); un Cmd+Z los deshace";
    var bTerminar = gBot.add("button", undefined, "Terminar");
    bTerminar.helpTip = "Deja de revisar: cierra la ventana (lo que no hayas aplicado queda sin cambiar)";

    function tipoElegido() {
        if (!filtro.selection || filtro.selection.index == 0) return "";
        return C.tiposFiltro[filtro.selection.index - 1];
    }
    function visibles() {
        var f = tipoElegido(), r = [];
        for (var i = 0; i < C.todas.length; i++) if (!f || C.todas[i].tipo == f) r.push(C.todas[i]);
        return r;
    }

    // El cambio con dos palabras delante y tres detrás: «…palabra palabra[texto]palabra…».
    function contexto(c) {
        try {
            var t = rango(c), p = t.paragraphs[0], pc = String(p.contents).replace(/\r$/, ""), o = t.index - p.index;
            var delante = pc.substring(0, o), detras = pc.substring(o + c.len);
            var a = delante.match(/(?:\S+\s+){0,2}\S*$/)[0], b = detras.match(/^\S*(?:\s+\S+){0,3}/)[0];
            return visible((a.length < delante.length ? "…" : "") + a) + "[" + visible(c.texto) + "]" +
                   visible(b + (b.length < detras.length ? "…" : ""));
        } catch (e) { return "[" + visible(c.texto) + "]"; }
    }

    function formatoTexto(f) { return f.nombre == "[Ninguno]" ? "sin estilo" + (f.fuente ? " (" + f.fuente + ")" : "") : "«" + f.nombre + "»"; }

    function rellenar(sel) {
        lb.removeAll();
        C.vistas = visibles();
        for (var i = 0; i < C.vistas.length; i++) {
            var c = C.vistas[i], it = lb.add("item", String(i + 1));
            it.subItems[0].text = TIPOS[c.tipo];
            it.subItems[1].text = c.pagina;
            var t = contexto(c);
            it.subItems[2].text = t.length > 80 ? t.substring(0, 80) + "…" : t;
        }
        titulo.text = (C.doc ? C.doc.name + ": " : "") + C.todas.length + " cambios pendientes";
        if (C.vistas.length) lb.selection = Math.min(sel || 0, C.vistas.length - 1);
        else mostrar();
    }

    function mostrar() {
        var it = lb.selection;
        bAplicar.enabled = bOmitir.enabled = bAnt.enabled = bSig.enabled = !!it;
        bTodos.enabled = C.vistas && C.vistas.length > 0;
        if (!it) { antes.text = despues.text = explica.text = ""; return; }
        var c = C.vistas[it.index];
        bAnt.enabled = it.index > 0;
        bSig.enabled = it.index < C.vistas.length - 1;
        antes.text = contexto(c);
        if (c.tipo == "puntuacion") {
            antes.text += "\n«" + visible(c.texto) + "» " + formatoTexto(c.actual);
            despues.text = contexto(c) + "\n«" + visible(c.texto) + "» " + formatoTexto(c.fw) + ", como su palabra";
            explica.text = "La puntuación pegada a una palabra toma su formato (estilo de carácter y formato local).";
        } else {
            antes.text += "\ntexto sin enlace";
            despues.text = contexto(c) + "\nhipervínculo a " + c.destino;
            explica.text = c.tipo == "doi" ? "El DOI se enlaza a doi.org (solo el identificador), sin cambiar su formato y sin borde visible."
                                          : "La URL pasa a hipervínculo sin cambiar su formato y sin borde visible; la puntuación final queda fuera.";
        }
        try { var t = rango(c); app.select(t); t.showText(); } catch (e) {}
    }

    function rehacerFiltro(anterior) {
        var cuenta = {}, orden = ["puntuacion", "url", "doi"];
        for (var i = 0; i < C.todas.length; i++) cuenta[C.todas[i].tipo] = (cuenta[C.todas[i].tipo] || 0) + 1;
        C.rellenando = true;
        filtro.removeAll();
        filtro.add("item", "Todos los cambios (" + C.todas.length + ")");
        C.tiposFiltro = [];
        var elegido = 0;
        for (var i = 0; i < orden.length; i++) {
            if (!cuenta[orden[i]]) continue;
            C.tiposFiltro.push(orden[i]);
            filtro.add("item", TIPOS[orden[i]] + " (" + cuenta[orden[i]] + ")");
            if (orden[i] == anterior) elegido = C.tiposFiltro.length;
        }
        filtro.selection = elegido;
        C.rellenando = false;
    }

    C.cargar = function (sel) {
        var anterior = tipoElegido();
        C.todas = []; C.vistas = [];
        if (!app.documents.length || !app.layoutWindows.length) {
            C.doc = null; titulo.text = "No hay ningún documento abierto"; filtro.removeAll(); lb.removeAll(); mostrar(); return;
        }
        if (C.doc && (!C.doc.isValid || C.doc.id != app.activeDocument.id)) C.omitidas = {};
        C.doc = app.activeDocument;
        C.datos = leerDatos();
        if (!C.datos) { titulo.text = "No se han podido leer los datos de la publicación"; lb.removeAll(); mostrar(); return; }
        C.todas = buscar(C.doc);
        rehacerFiltro(anterior);
        rellenar(sel);
    };

    filtro.onChange = function () { if (!C.rellenando) rellenar(0); };
    lb.onChange = mostrar;
    bActualizar.onClick = function () { C.cargar(lb.selection ? lb.selection.index : 0); };
    bAnt.onClick = function () { if (lb.selection && lb.selection.index > 0) lb.selection = lb.selection.index - 1; };
    bSig.onClick = function () { if (lb.selection && lb.selection.index < C.vistas.length - 1) lb.selection = lb.selection.index + 1; };

    bAplicar.onClick = function () {
        if (!lb.selection) return;
        var i = lb.selection.index, c = C.vistas[i];
        try { enUnPaso("Cierre: " + TIPOS[c.tipo], function () { aplicarCierre(C.doc, c); }); }
        catch (e) { alert("No se pudo hacer el cambio: " + e); return; }
        // Se vuelve a buscar todo (al enlazar una URL, el DOI que contuviera ya no sale)
        C.cargar(i);
    };
    bOmitir.onClick = function () {
        if (!lb.selection) return;
        var i = lb.selection.index, c = C.vistas[i], quedan = [];
        C.omitidas[c.huella] = 1;
        for (var k = 0; k < C.todas.length; k++) if (C.todas[k] !== c) quedan.push(C.todas[k]);
        C.todas = quedan;
        rehacerFiltro(tipoElegido());
        rellenar(i);
    };
    bTodos.onClick = function () {
        if (!C.vistas.length) return;
        var errores = [], lista = C.vistas.slice(0);
        try {
            enUnPaso("Cierre: " + (tipoElegido() ? TIPOS[tipoElegido()] : "todos"), function () {
                for (var i = 0; i < lista.length; i++) {
                    try { aplicarCierre(C.doc, lista[i]); }
                    catch (e) { errores.push(TIPOS[lista[i].tipo] + " «" + visible(lista[i].texto) + "»: " + e.message); }
                }
            });
        } catch (e) { alert("No se pudo: " + e); return; }
        C.cargar(0);
        if (errores.length) alert("No se pudieron hacer " + errores.length + ":\n" + errores.slice(0, 8).join("\n"));
    };
    bTerminar.onClick = function () {
        try { if (C.doc && C.doc.isValid) C.doc.select(NothingEnum.NOTHING); } catch (e) {}
        C.destruir();
    };

    w.onActivate = function () {
        if (app.documents.length && C.doc !== undefined && (!C.doc || !C.doc.isValid || C.doc.id != app.activeDocument.id)) C.cargar();
    };
    w.onResizing = w.onResize = function () { this.layout.resize(); };
    w.onClose = function () { $.global.revisarCierre = null; };

    // Para probar desde fuera (#targetengine "formatear_word").
    C.lista = lb;
    C.botones = { aplicar: bAplicar, omitir: bOmitir, todos: bTodos, terminar: bTerminar, actualizar: bActualizar };
    C.destruir = function () { try { w.close(); } catch (e) {} $.global.revisarCierre = null; };
    C.cargar();
    w.show();
})();
