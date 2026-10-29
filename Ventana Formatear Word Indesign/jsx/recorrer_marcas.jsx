// Ventana «Recorrer marcas» (Ventana > Formatear Word > Recorrer marcas…): recorre en orden todo
// el texto condicional del documento activo («Duda …», «Revisar …»…) y dice el motivo de cada
// marca, sin tener que buscarlas a mano. Las palabras resaltadas («Risk word») no se listan.
// Los motivos salen de informes/<documento>-marcas.json (lo escribe importar.py: dudas de la
// importación) y de informes/<documento>-dudas.json (dudas.py --marcar: «Revisar …»).
// - Al elegir una marca, la selecciona en el documento.
// - Quitar marca: quita su condición (o condiciones) del texto; un paso de deshacer.
// Motor persistente "formatear_word"; la ventana vive en $.global.recorrerMarcas.

#targetengine "formatear_word"

(function () {
    var RAIZ = File($.fileName).parent.parent;     // carpeta del proyecto

    if ($.global.recorrerMarcas && $.global.recorrerMarcas.ventana) {
        $.global.recorrerMarcas.cargar();
        $.global.recorrerMarcas.ventana.show();
        return;
    }
    var M = $.global.recorrerMarcas = {};

    var IGNORAR = { "Risk word": 1 };      // el resaltado de Tabla, Figura… no es una duda

    function leerJSON(f) {
        f.encoding = "UTF-8";
        if (!f.exists || !f.open("r")) return null;
        var t = f.read();
        f.close();
        try { return eval("(" + t + ")"); } catch (e) { return null; }
    }
    var BLANCOS = /[\s\u00A0\u2009\u202F\u2028]+/g;
    function normal(s) { return String(s).replace(BLANCOS, " ").replace(/^ | $/g, ""); }
    function lista(x) { return x instanceof Array ? x : [x]; }

    // ---- marcas del documento --------------------------------------------------------------
    // Todos los textos: historias, celdas de tabla y notas al pie.
    function contenedores(d) {
        var r = [], ss = d.stories.everyItem().getElements();
        for (var s = 0; s < ss.length; s++) {
            r.push(ss[s]);
            for (var t = 0; t < ss[s].tables.length; t++) {
                var cs = ss[s].tables[t].cells.everyItem().getElements();
                for (var c = 0; c < cs.length; c++) r.push(cs[c].texts[0]);
            }
            for (var f = 0; f < ss[s].footnotes.length; f++) r.push(ss[s].footnotes[f].texts[0]);
        }
        return r;
    }

    // Tramos seguidos con las mismas condiciones = una marca {cont, ini, fin, nombres, texto}.
    function buscarMarcas(d) {
        var res = [], cs = contenedores(d);
        for (var k = 0; k < cs.length; k++) {
            var r = cs[k].textStyleRanges, n;
            try { n = r.length; } catch (e) { continue; }
            if (!n) continue;
            var conds, lens, txts;
            if (n == 1) { conds = [r[0].appliedConditions]; lens = [r[0].length]; txts = [r[0].contents]; }
            else {
                var todos = r.everyItem();
                conds = todos.appliedConditions; lens = lista(todos.length); txts = lista(todos.contents);
            }
            var pos = 0, previa = null;
            for (var i = 0; i < n; i++) {
                var cc = conds[i], nombres = [];
                for (var j = 0; j < cc.length; j++) if (!IGNORAR[cc[j].name]) nombres.push(cc[j].name);
                if (nombres.length) {
                    var clave = nombres.sort().join("|"), txt = String(txts[i]);
                    if (!lens[i]) {
                        // Tramo vacío con condición (tras una tabla, en galeradas importadas antes de
                        // marcar la primera celda): la marca es todo el texto del contenedor.
                        try { txt = cs[k].tables.length ? "[tabla]" : String(cs[k].texts[0].contents); } catch (e) { txt = ""; }
                        res.push({ cont: cs[k], ini: pos, fin: pos, vacia: true, nombres: nombres, clave: clave,
                                   texto: txt, orden: res.length });
                        previa = null;
                        continue;
                    }
                    if (previa && previa.fin == pos && previa.clave == clave) { previa.fin += lens[i]; previa.texto += txt; }
                    else { previa = { cont: cs[k], ini: pos, fin: pos + lens[i], nombres: nombres, clave: clave, texto: txt, orden: res.length }; res.push(previa); }
                } else previa = null;
                pos += lens[i];
            }
        }
        // En orden de página (la mesa de trabajo, tras su pliego; el texto desbordado, al final).
        for (var i = 0; i < res.length; i++) {
            var m = res[i];
            m.pagina = "—"; m.clavePag = 1e6;
            try {
                var t = texto(m), fr = t.parentTextFrames[0], pg = fr.parentPage;
                if (pg) { m.pagina = pg.name; m.clavePag = pg.documentOffset; }
                else { var sp = fr.parent; while (sp && !(sp instanceof Spread)) sp = sp.parent;
                       m.pagina = "mesa " + sp.pages[sp.pages.length - 1].name; m.clavePag = sp.pages[sp.pages.length - 1].documentOffset + 0.5; }
            } catch (e) {}
        }
        res.sort(function (a, b) { return a.clavePag - b.clavePag || a.orden - b.orden; });
        return res;
    }

    function texto(m) {
        if (m.vacia) return m.cont.texts[0];
        return resolve(m.cont.characters.itemByRange(m.ini, m.fin - 1).toSpecifier());
    }

    // ---- motivos -----------------------------------------------------------------------------
    // Cada duda apuntada se asigna a la marca de su condición con el mismo texto (o que lo
    // contiene); las que no casan (el texto ha cambiado desde entonces), por orden a las marcas
    // de esa condición que siguen sin motivo.
    function asignar(marcas, apuntadas) {
        var sueltas = [];
        for (var i = 0; i < apuntadas.length; i++) {
            var a = apuntadas[i], ta = normal(a.texto), hecha = false;
            for (var pase = 0; pase < 2 && !hecha; pase++) {
                for (var k = 0; k < marcas.length && !hecha; k++) {
                    var m = marcas[k], tm = normal(m.texto);
                    if (!tieneCond(m, a.condicion) || m.usados[ta]) continue;
                    if (pase == 0 ? tm == ta : (ta.length > 2 && (tm.indexOf(ta) >= 0 || ta.indexOf(tm) >= 0))) {
                        m.motivos.push(a.motivo); m.usados[ta] = 1; hecha = true;
                    }
                }
            }
            if (!hecha) sueltas.push(a);
        }
        for (var i = 0; i < sueltas.length; i++) {
            for (var k = 0; k < marcas.length; k++) {
                if (tieneCond(marcas[k], sueltas[i].condicion) && !marcas[k].motivos.length) {
                    marcas[k].motivos.push(sueltas[i].motivo + " (el texto ha cambiado desde que se marcó)");
                    break;
                }
            }
        }
    }
    function tieneCond(m, nombre) {
        for (var i = 0; i < m.nombres.length; i++) if (m.nombres[i] == nombre) return true;
        return false;
    }

    function motivos(d, marcas) {
        var base = RAIZ + "/informes/" + d.name.replace(/\.indd$/, "");
        for (var i = 0; i < marcas.length; i++) { marcas[i].motivos = []; marcas[i].usados = {}; }
        var imp = leerJSON(File(base + "-marcas.json"));
        if (imp) asignar(marcas, imp.marcas);
        var dud = leerJSON(File(base + "-dudas.json"));
        if (dud) {
            var ap = [];
            for (var i = 0; i < dud.dudas.length; i++) {
                var x = dud.dudas[i], p = x.propuesta, mot = x.motivo + (x.sugerencia ? " (sugerencia: " + x.sugerencia + ")" : "");
                if (p) mot += "\nClaude: " + (p.accion == "cambiar" ? "cambiar" + (p.texto_nuevo ? " por «" + p.texto_nuevo + "»" : "") +
                                              (p.formato ? " (" + p.formato.replace("_", " ") + ")" : "") : "dejar como está") +
                              (p.motivo ? ". " + p.motivo : "");
                ap.push({ condicion: dud.condiciones[x.tipo][0], texto: x.texto, motivo: mot });
            }
            asignar(marcas, ap);
        }
        for (var i = 0; i < marcas.length; i++) {
            var m = marcas[i];
            if (!m.motivos.length) m.motivos.push("Sin motivo apuntado (" + m.nombres.join(", ") + ").");
        }
    }

    // ---- ventana ---------------------------------------------------------------------------
    var w = M.ventana = new Window("palette", "Recorrer marcas", undefined, { resizeable: true });
    w.orientation = "column";
    w.alignChildren = ["fill", "top"];
    var cab = w.add("group");
    cab.alignChildren = ["left", "center"];
    var titulo = cab.add("statictext", undefined, "", { characters: 36, truncate: "end" });
    cab.add("statictext", undefined, "Ver:");
    var filtro = cab.add("dropdownlist", undefined, []);
    filtro.preferredSize.width = 220;
    var bActualizar = cab.add("button", undefined, "Actualizar");
    bActualizar.helpTip = "Vuelve a leer las marcas del documento activo (también tras un Cmd+Z)";

    var lb = w.add("listbox", [0, 0, 720, 260], undefined, {
        numberOfColumns: 4, showHeaders: true,
        columnTitles: ["Nº", "Marca", "Pág.", "Texto"], columnWidths: [40, 120, 50, 490] });
    lb.alignment = ["fill", "fill"];

    var pMot = w.add("panel", undefined, "Motivo");
    pMot.alignChildren = ["fill", "top"];
    var motivo = pMot.add("statictext", [0, 0, 700, 64], "", { multiline: true });

    var gBot = w.add("group");
    gBot.alignment = ["fill", "top"];
    var bAnt = gBot.add("button", undefined, "◀ Anterior");
    var bSig = gBot.add("button", undefined, "Siguiente ▶");
    var hueco = gBot.add("group"); hueco.alignment = ["fill", "center"];
    var bQuitar = gBot.add("button", undefined, "Quitar marca");
    bQuitar.helpTip = "Da la marca por revisada: le quita la condición al texto (un Cmd+Z lo deshace)";
    var bTerminar = gBot.add("button", undefined, "Terminar");
    bTerminar.helpTip = "Deja de recorrer las marcas: cierra la ventana y quita la selección (las marcas que queden siguen en el documento)";

    function visibles() {
        var f = filtro.selection ? filtro.selection.text.replace(/ \(\d+\)$/, "") : "";
        if (!f || filtro.selection.index == 0) return M.marcas;
        var r = [];
        for (var i = 0; i < M.marcas.length; i++) if (tieneCond(M.marcas[i], f)) r.push(M.marcas[i]);
        return r;
    }

    function rellenar(sel) {
        lb.removeAll();
        M.vistas = visibles();
        for (var i = 0; i < M.vistas.length; i++) {
            var m = M.vistas[i], it = lb.add("item", String(i + 1));
            it.subItems[0].text = m.nombres.join(", ");
            it.subItems[1].text = m.pagina;
            var t = normal(m.texto.replace(/\u0016/g, "[tabla]"));
            it.subItems[2].text = t.length > 90 ? t.substring(0, 90) + "…" : t;
        }
        if (M.vistas.length) lb.selection = Math.min(sel || 0, M.vistas.length - 1);
        else mostrar();
    }

    function mostrar() {
        var it = lb.selection;
        bQuitar.enabled = bAnt.enabled = bSig.enabled = !!it;
        if (!it) { motivo.text = ""; return; }
        var m = M.vistas[it.index];
        bAnt.enabled = it.index > 0;
        bSig.enabled = it.index < M.vistas.length - 1;
        motivo.text = m.motivos.join("\n");
        try { var t = texto(m); app.select(t); t.showText(); } catch (e) {}
    }

    M.cargar = function (sel) {
        var anterior = filtro.selection ? filtro.selection.text.replace(/ \(\d+\)$/, "") : "";
        filtro.removeAll();
        M.marcas = []; M.vistas = [];
        if (!app.documents.length) {
            M.doc = null; titulo.text = "No hay ningún documento abierto"; lb.removeAll(); mostrar(); return;
        }
        M.doc = app.activeDocument;
        M.marcas = buscarMarcas(M.doc);
        motivos(M.doc, M.marcas);
        titulo.text = M.doc.name + ": " + M.marcas.length + " marcas";
        var cuenta = {}, nombres = [];
        for (var i = 0; i < M.marcas.length; i++)
            for (var j = 0; j < M.marcas[i].nombres.length; j++) {
                var n = M.marcas[i].nombres[j];
                if (!cuenta[n]) { cuenta[n] = 0; nombres.push(n); }
                cuenta[n]++;
            }
        nombres.sort();
        filtro.add("item", "Todas (" + M.marcas.length + ")");
        var elegido = 0;
        for (var i = 0; i < nombres.length; i++) {
            filtro.add("item", nombres[i] + " (" + cuenta[nombres[i]] + ")");
            if (nombres[i] == anterior) elegido = i + 1;
        }
        M.cargando = true;
        filtro.selection = elegido;
        M.cargando = false;
        rellenar(sel);
    };

    filtro.onChange = function () { if (!M.cargando) rellenar(0); };
    lb.onChange = mostrar;
    bActualizar.onClick = function () { M.cargar(lb.selection ? lb.selection.index : 0); };
    bAnt.onClick = function () { if (lb.selection && lb.selection.index > 0) lb.selection = lb.selection.index - 1; };
    bSig.onClick = function () { if (lb.selection && lb.selection.index < M.vistas.length - 1) lb.selection = lb.selection.index + 1; };

    // Quita las condiciones de la marca (con un filtro elegido, solo esa) y, si una «Duda …» o
    // «Revisar …» se queda sin texto, la condición del panel.
    bQuitar.onClick = function () {
        if (!lb.selection || !M.doc || !M.doc.isValid) return;
        var i = lb.selection.index, m = M.vistas[i];
        var f = filtro.selection.index ? filtro.selection.text.replace(/ \(\d+\)$/, "") : "";
        try {
            app.doScript(function () {
                var t = texto(m), cs = t.appliedConditions, quedan = [];
                for (var k = 0; k < cs.length; k++) if (f ? cs[k].name != f : IGNORAR[cs[k].name]) quedan.push(cs[k]);
                t.applyConditions(quedan, true);
                for (var k = 0; k < m.nombres.length; k++) {
                    if (f && m.nombres[k] != f) continue;
                    if (!/^(Revisar|Duda) /.test(m.nombres[k])) continue;
                    var otra = false;
                    for (var j = 0; j < M.marcas.length && !otra; j++) if (M.marcas[j] !== m && tieneCond(M.marcas[j], m.nombres[k])) otra = true;
                    var c = M.doc.conditions.itemByName(m.nombres[k]);
                    if (!otra && c.isValid) c.remove();
                }
            }, ScriptLanguage.JAVASCRIPT, undefined, UndoModes.ENTIRE_SCRIPT, "Recorrer marcas: quitar marca");
        } catch (e) { alert("No se pudo quitar la marca: " + e); }
        M.cargar(i);
    };

    // Terminar: se cierra sin tocar nada; al volver a abrirla se leen de nuevo las marcas que queden.
    bTerminar.onClick = function () {
        try { if (M.doc && M.doc.isValid) M.doc.select(NothingEnum.NOTHING); } catch (e) {}
        M.destruir();
    };

    w.onActivate = function () {
        if (app.documents.length && (!M.doc || !M.doc.isValid || M.doc.id != app.activeDocument.id)) M.cargar();
    };
    w.onResizing = w.onResize = function () { this.layout.resize(); };
    // Cerrada con la X tampoco se guarda: al volver a abrirla se crea de nuevo (con el código al día).
    w.onClose = function () { $.global.recorrerMarcas = null; };

    // Para probar desde fuera (#targetengine "formatear_word").
    M.lista = lb;
    M.campos = { filtro: filtro, motivo: motivo, titulo: titulo };
    M.botones = { anterior: bAnt, siguiente: bSig, quitar: bQuitar, terminar: bTerminar, actualizar: bActualizar };
    M.destruir = function () { try { w.close(); } catch (e) {} $.global.recorrerMarcas = null; };
    M.cargar();
    w.show();
})();
