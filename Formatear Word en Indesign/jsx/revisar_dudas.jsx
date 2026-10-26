// Ventana «Revisar dudas» (fase 3, bloque 3): recorre las dudas ortotipográficas marcadas con
// las condiciones «Revisar …» del documento activo, con la propuesta de Claude de cada una.
// Lee informes/<documento>-dudas.json (lo escribe `python3 dudas.py --marcar --claude`).
//
// - Al elegir una duda, la selecciona en el documento.
// - Cambiar: pone el texto de «Cambiar por» y el formato elegido, y quita la marca.
// - Omitir: deja el texto y quita la marca. «… y al diccionario» además añade la palabra a
//   publicaciones/diccionario.txt y omite las demás dudas iguales del documento.
// - Aceptar todas las propuestas: hace lo que propone Claude en todas las pendientes.
// Cada acción es un paso de deshacer. Las dudas se localizan en vivo por su condición y su
// texto (no por posición), así que se pueden cambiar en cualquier orden.

#targetengine "formatear_word"

(function () {
    var RAIZ = File($.fileName).parent.parent;     // carpeta del proyecto

    if ($.global.revisorDudas && $.global.revisorDudas.ventana) {
        $.global.revisorDudas.cargar();
        $.global.revisorDudas.ventana.show();
        return;
    }

    var R = $.global.revisorDudas = {};
    var TIPOS = { tilde: "Tilde", ortografia: "Ortografía", desconocida: "Desconocida",
                  extranjerismo: "Extranjerismo", cursiva: "Cursiva", criterio: "Criterio",
                  compuesto: "Compuesta" };

    // ---- datos -------------------------------------------------------------------------
    function leerJSON(f) {
        f.encoding = "UTF-8";
        if (!f.open("r")) return null;
        var t = f.read();
        f.close();
        return eval("(" + t + ")");
    }

    function textoNormal(t) {      // los Text de findText vienen bien; por si acaso
        return resolve(t.toSpecifier());
    }

    function buscar(doc, cond, texto) {
        app.findTextPreferences = NothingEnum.NOTHING;
        app.findChangeTextOptions.caseSensitive = true;
        app.findChangeTextOptions.wholeWord = false;
        app.findChangeTextOptions.includeFootnotes = true;
        app.findChangeTextOptions.includeMasterPages = false;
        app.findTextPreferences.findWhat = texto.replace(/\^/g, "^^");
        // No con appliedConditions: exige el conjunto exacto de condiciones y se salta el texto
        // que además lleva otra («Duda figura» en un pie, por ejemplo).
        var h = doc.findText(), res = [];
        app.findTextPreferences = NothingEnum.NOTHING;
        for (var i = 0; i < h.length; i++) {
            if (!palabraEntera(h[i])) continue;     // «reforzado» dentro de «reforzados»
            var cs = h[i].appliedConditions;
            for (var k = 0; k < cs.length; k++) if (cs[k].id == cond.id) { res.push(h[i]); break; }
        }
        return res;
    }

    function esLetra(c) { return /[A-Za-z\u00C0-\u024F]/.test(c); }
    function palabraEntera(t) {
        try {
            var c = t.contents, p = t.paragraphs[0], pc = p.contents, ini = t.index - p.index;
            if (esLetra(c.charAt(0)) && esLetra(pc.charAt(ini - 1))) return false;
            if (esLetra(c.charAt(c.length - 1)) && esLetra(pc.charAt(ini + c.length))) return false;
        } catch (e) {}
        return true;
    }

    // «20 caracteres antes + texto + 20 después», para emparejar cada marca con su duda.
    function huella(antes, texto, despues) {
        return antes.slice(-20) + "[" + texto + "]" + despues.slice(0, 20);
    }
    function huellaDuda(d) {
        var c = d.contexto, a = c.indexOf("["), b = c.lastIndexOf("]");
        return huella(c.substring(0, a).replace(/^…/, ""), d.texto, c.substring(b + 1).replace(/…$/, ""));
    }
    function huellaTexto(t) {
        try {
            var p = t.paragraphs[0], ini = t.index - p.index, pc = p.contents;
            return huella(pc.substring(0, ini), t.contents, pc.substring(ini + t.contents.length).replace(/\r$/, ""));
        } catch (e) { return ""; }
    }

    // Pendientes: dudas cuya marca sigue en el documento, cada una con su Text en vivo.
    function localizar() {
        var doc = R.doc, pend = [], grupos = {};
        for (var i = 0; i < R.datos.dudas.length; i++) {
            var d = R.datos.dudas[i], k = d.tipo + "\u0001" + d.texto;
            (grupos[k] = grupos[k] || []).push(d);
        }
        for (var k in grupos) {
            var g = grupos[k], cond = doc.conditions.itemByName(R.datos.condiciones[g[0].tipo][0]);
            if (!cond.isValid) continue;
            var hs = buscar(doc, cond, g[0].texto), usadas = {};
            for (var j = 0; j < hs.length; j++) {
                var hu = huellaTexto(hs[j]), elegida = -1;
                for (var m = 0; m < g.length && elegida < 0; m++) if (!usadas[m] && huellaDuda(g[m]) == hu) elegida = m;
                for (var m = 0; m < g.length && elegida < 0; m++) if (!usadas[m]) elegida = m;
                if (elegida < 0) continue;
                usadas[elegida] = 1;
                pend.push({ duda: g[elegida], texto: hs[j] });
            }
        }
        pend.sort(function (a, b) { return a.duda.id - b.duda.id; });
        return pend;
    }

    // ---- acciones ------------------------------------------------------------------------
    function quitarMarca(t, tipo) {
        var cond = R.doc.conditions.itemByName(R.datos.condiciones[tipo][0]), quedan = [];
        var actuales = t.appliedConditions;
        for (var i = 0; i < actuales.length; i++) if (actuales[i].id != cond.id) quedan.push(actuales[i]);
        t.applyConditions(quedan, true);
    }

    function estiloCaracter(nombre) {
        var todos = R.doc.allCharacterStyles;
        for (var i = 0; i < todos.length; i++) if (todos[i].name == nombre) return todos[i];
        return null;
    }

    // Cambia una duda: texto nuevo (o "" = el mismo) y formato ("", "cursiva", "redonda").
    function cambiar(p, nuevo, formato) {
        var t = textoNormal(p.texto), d = p.duda;
        quitarMarca(t, d.tipo);
        if (nuevo !== "" && nuevo != d.texto) {
            var cont = t.parent, ini = t.index;     // en celdas, parent es la celda y el índice cuenta desde ella
            t.contents = nuevo;
            t = resolve(cont.characters.itemByRange(ini, ini + nuevo.length - 1).toSpecifier());
        }
        if (formato == "cursiva" || formato == "negrita_cursiva") {
            var nombre = d["estilo_" + formato], ec = nombre ? estiloCaracter(nombre) : null;
            if (ec) t.appliedCharacterStyle = ec;
            // Sin estilo propio de negrita cursiva (en tablas y pies la maqueta solo tiene «Bold»):
            // el de negrita y la variante «Bold Italic» de la fuente a mano.
            if (!ec || (formato == "negrita_cursiva" && nombre == d.estilo_negrita)) {
                try { t.fontStyle = formato == "cursiva" ? "Italic" : "Bold Italic"; } catch (e) {}
            }
        } else if (formato == "no_partir") {
            // Con el estilo «noPartir» si el texto no lleva otro; si lleva uno (cursiva…), «No
            // separar» a mano para no perderlo.
            var np = d.estilo_no_partir ? estiloCaracter(d.estilo_no_partir) : null, sinEstilo = false;
            try { sinEstilo = t.appliedCharacterStyle.id == R.doc.characterStyles.item(0).id; } catch (e) {}
            if (np && sinEstilo) t.appliedCharacterStyle = np;
            else t.noBreak = true;
        } else if (formato == "redonda") {
            t.appliedCharacterStyle = R.doc.characterStyles.item(0);    // [Ninguno]
        }
    }

    function alDiccionario(palabra) {
        palabra = palabra.toLowerCase();
        var f = File(R.datos.diccionario), ya = "";
        f.encoding = "UTF-8";
        if (f.exists && f.open("r")) { ya = f.read(); f.close(); }
        var lineas = ya.split(/\r\n|\r|\n/);
        for (var i = 0; i < lineas.length; i++) if (lineas[i].split("#")[0].replace(/^\s+|\s+$/g, "").toLowerCase() == palabra) return;
        f.lineFeed = "Unix";        // en Mac, ExtendScript escribe \r por defecto
        f.open("a");
        f.write((ya && !/\n$/.test(ya) ? "\n" : "") + palabra + "\n");
        f.close();
    }

    // Condiciones «Revisar …» y «Duda …» que ya no lleva ningún texto: fuera del panel.
    function limpiarCondiciones() {
        var doc = R.doc, usadas = {};
        function anotar(textos) {
            try {
                var cs = textos.textStyleRanges.everyItem().appliedConditions;
                for (var i = 0; i < cs.length; i++) for (var k = 0; k < cs[i].length; k++) usadas[cs[i][k].id] = 1;
            } catch (e) {}
        }
        var ss = doc.stories.everyItem().getElements();
        for (var s = 0; s < ss.length; s++) {
            anotar(ss[s]);
            for (var t = 0; t < ss[s].tables.length; t++) {
                var cel = ss[s].tables[t].cells.everyItem().getElements();
                for (var c = 0; c < cel.length; c++) anotar(cel[c].texts[0]);
            }
        }
        for (var i = doc.conditions.length - 1; i >= 0; i--) {
            var cn = doc.conditions[i];
            if (/^(Revisar|Duda) /.test(cn.name) && !usadas[cn.id]) cn.remove();
        }
    }

    // Cada acción, con la limpieza de condiciones, en un paso de deshacer.
    function enUnPaso(nombre, fn) {
        if (!R.doc || !R.doc.isValid) { R.cargar(); throw new Error("El documento ya no está abierto"); }
        app.doScript(function () { fn(); limpiarCondiciones(); }, ScriptLanguage.JAVASCRIPT, undefined,
                     UndoModes.ENTIRE_SCRIPT, nombre);
    }

    // ---- ventana ---------------------------------------------------------------------------
    var w = R.ventana = new Window("palette", "Revisar dudas", undefined, { resizeable: true });
    w.orientation = "column";
    w.alignChildren = ["fill", "top"];
    var cab = w.add("group");
    cab.alignChildren = ["left", "center"];
    var titulo = cab.add("statictext", undefined, "", { characters: 50 });
    var actualizar = cab.add("button", undefined, "Actualizar");
    actualizar.helpTip = "Vuelve a leer las dudas del documento activo (también tras un Cmd+Z)";

    var lista = w.add("listbox", [0, 0, 760, 260], undefined, {
        numberOfColumns: 4, showHeaders: true,
        columnTitles: ["Tipo", "Texto", "Claude", "Propuesta"], columnWidths: [100, 190, 70, 380] });

    var pCtx = w.add("panel", undefined, "Contexto");
    pCtx.alignChildren = ["fill", "top"];
    var ctx = pCtx.add("statictext", [0, 0, 740, 44], "", { multiline: true });
    var aviso = pCtx.add("statictext", [0, 0, 740, 18], "");
    var pCl = w.add("panel", undefined, "Claude");
    pCl.alignChildren = ["fill", "top"];
    var motivo = pCl.add("statictext", [0, 0, 740, 36], "", { multiline: true });

    var gCam = w.add("group");
    gCam.alignment = ["fill", "top"];
    gCam.add("statictext", undefined, "Cambiar por:");
    var nuevoTxt = gCam.add("edittext", undefined, "");
    nuevoTxt.alignment = ["fill", "center"];
    nuevoTxt.preferredSize.width = 420;
    gCam.add("statictext", undefined, "Formato:");
    var formato = gCam.add("dropdownlist", undefined, ["Sin cambio", "Cursiva", "Negrita cursiva", "Redonda", "Sin partir"]);
    formato.selection = 0;

    var gBot = w.add("group");
    gBot.alignment = ["fill", "top"];
    var bCambiar = gBot.add("button", undefined, "Cambiar");
    var bOmitir = gBot.add("button", undefined, "Omitir");
    var bDic = gBot.add("button", undefined, "Omitir y al diccionario");
    bDic.helpTip = "Deja la palabra como está, la añade al diccionario de la publicación y omite las demás iguales";
    var hueco = gBot.add("group"); hueco.alignment = ["fill", "center"];
    var bTodas = gBot.add("button", undefined, "Aceptar todas las propuestas");
    bTodas.helpTip = "Hace lo que propone Claude en todas las dudas pendientes (un solo Cmd+Z)";

    var FORMATOS = ["", "cursiva", "negrita_cursiva", "redonda", "no_partir"];

    function propuestaTexto(d) {
        var p = d.propuesta;
        if (!p) return "(sin propuesta)";
        if (p.accion == "omitir") return "dejar como está" + (p.diccionario ? " · al diccionario" : "");
        var r = [];
        if (p.texto_nuevo) r.push("→ " + p.texto_nuevo);
        if (p.formato) r.push(p.formato == "no_partir" ? "sin partir" : p.formato.replace("_", " "));
        return r.join(" · ");
    }

    // El formato que propone Claude; cursiva en un texto que ya va en negrita → negrita cursiva.
    function formatoPropuesto(p) {
        var d = p.duda, fm = d.propuesta && d.propuesta.formato ? d.propuesta.formato : "";
        try {
            if (fm == "cursiva" && d.estilo_negrita && textoNormal(p.texto).appliedCharacterStyle.name == d.estilo_negrita)
                fm = "negrita_cursiva";
        } catch (e) {}
        return fm;
    }

    function mostrar() {
        var it = lista.selection;
        if (!it) { ctx.text = aviso.text = motivo.text = ""; nuevoTxt.text = ""; return; }
        var p = R.pendientes[it.index], d = p.duda, pr = d.propuesta;
        ctx.text = d.contexto;
        aviso.text = "Aviso: " + d.motivo + (d.sugerencia ? " (sugerencia: " + d.sugerencia + ")" : "");
        motivo.text = pr ? (pr.accion == "cambiar" ? "Cambiar. " : "Dejar como está. ") + pr.motivo : "Claude no ha revisado esta duda.";
        nuevoTxt.text = pr && pr.texto_nuevo ? pr.texto_nuevo : d.texto;
        var fm = formatoPropuesto(p);
        for (var i = 0; i < FORMATOS.length; i++) if (FORMATOS[i] == fm) formato.selection = i;
        try {
            var t = textoNormal(p.texto);
            app.select(t);
            t.showText();
        } catch (e) {}
    }

    R.cargar = function (seleccion) {
        if (!app.documents.length) {
            titulo.text = "No hay ningún documento abierto";
            lista.removeAll(); R.pendientes = []; R.doc = null; mostrar();
            return;
        }
        R.doc = app.activeDocument;
        var f = File(RAIZ + "/informes/" + R.doc.name.replace(/\.indd$/, "") + "-dudas.json");
        R.datos = f.exists ? leerJSON(f) : null;
        lista.removeAll();
        if (!R.datos) { titulo.text = R.doc.name + ": no hay dudas (python3 dudas.py --marcar --claude)"; R.pendientes = []; return; }
        R.pendientes = localizar();
        titulo.text = R.doc.name + ": " + R.pendientes.length + " de " + R.datos.dudas.length + " dudas pendientes";
        for (var i = 0; i < R.pendientes.length; i++) {
            var d = R.pendientes[i].duda, it = lista.add("item", TIPOS[d.tipo] || d.tipo);
            it.subItems[0].text = d.texto;
            it.subItems[1].text = d.propuesta ? (d.propuesta.accion == "cambiar" ? "Cambiar" : "Omitir") : "—";
            it.subItems[2].text = propuestaTexto(d);
        }
        if (R.pendientes.length) lista.selection = Math.min(seleccion || 0, R.pendientes.length - 1);
        else mostrar();
    };

    function trasAccion() {
        var i = lista.selection ? lista.selection.index : 0;
        R.cargar(i);
    }

    lista.onChange = mostrar;
    actualizar.onClick = function () { R.cargar(lista.selection ? lista.selection.index : 0); };

    bCambiar.onClick = function () {
        if (!lista.selection) return;
        var p = R.pendientes[lista.selection.index], nuevo = nuevoTxt.text, fm = FORMATOS[formato.selection.index];
        try {
            enUnPaso("Revisar dudas: «" + p.duda.texto + "» → «" + nuevo + "»", function () { cambiar(p, nuevo, fm); });
        } catch (e) { alert("No se pudo cambiar: " + e); }
        trasAccion();
    };

    bOmitir.onClick = function () {
        if (!lista.selection) return;
        var p = R.pendientes[lista.selection.index];
        try {
            enUnPaso("Revisar dudas: omitir «" + p.duda.texto + "»", function () { quitarMarca(textoNormal(p.texto), p.duda.tipo); });
        } catch (e) { alert("No se pudo omitir: " + e); }
        trasAccion();
    };

    bDic.onClick = function () {
        if (!lista.selection) return;
        var p = R.pendientes[lista.selection.index], palabra = p.duda.texto.replace(/^\s+|\s+$/g, "");
        try {
            enUnPaso("Revisar dudas: «" + palabra + "» al diccionario", function () {
                for (var i = R.pendientes.length - 1; i >= 0; i--) {
                    var q = R.pendientes[i];
                    if (q.duda.texto.toLowerCase() == p.duda.texto.toLowerCase()) quitarMarca(textoNormal(q.texto), q.duda.tipo);
                }
            });
            alDiccionario(palabra);
        } catch (e) { alert("No se pudo omitir: " + e); }
        trasAccion();
    };

    bTodas.onClick = function () {
        var n = 0;
        for (var i = 0; i < R.pendientes.length; i++) if (R.pendientes[i].duda.propuesta) n++;
        if (!n || (!R.sinPreguntar && !confirm("¿Aceptar las " + n + " propuestas de Claude de " + R.doc.name + "?"))) return;
        var errores = [], dic = {};
        try { enUnPaso("Revisar dudas: aceptar las propuestas de Claude", function () {
            // De la última a la primera: los cambios no mueven las que quedan por hacer.
            for (var i = R.pendientes.length - 1; i >= 0; i--) {
                var p = R.pendientes[i], pr = p.duda.propuesta;
                if (!pr) continue;
                try {
                    if (pr.accion == "cambiar") cambiar(p, pr.texto_nuevo, formatoPropuesto(p));
                    else quitarMarca(textoNormal(p.texto), p.duda.tipo);
                    if (pr.diccionario) dic[p.duda.texto.replace(/^\s+|\s+$/g, "").toLowerCase()] = 1;
                } catch (e) { errores.push("«" + p.duda.texto + "»: " + e); }
            }
        }); } catch (e) { alert("No se pudo: " + e); return; }
        for (var palabra in dic) alDiccionario(palabra);
        R.errores = errores;
        trasAccion();
        if (errores.length) alert("No se pudieron hacer " + errores.length + ":\n" + errores.slice(0, 8).join("\n"));
    };

    w.onActivate = function () {
        if (app.documents.length && (!R.doc || !R.doc.isValid || R.doc.id != app.activeDocument.id)) R.cargar();
    };
    w.onResizing = w.onResize = function () { this.layout.resize(); };

    // Para probar desde fuera (#targetengine "formatear_word"): R.lista, R.botones, R.sinPreguntar.
    R.lista = lista;
    R.botones = { cambiar: bCambiar, omitir: bOmitir, diccionario: bDic, todas: bTodas };
    R.campos = { nuevo: nuevoTxt, formato: formato };
    R.destruir = function () { try { w.close(); } catch (e) {} $.global.revisorDudas = null; };
    R.cargar();
    w.show();
})();
