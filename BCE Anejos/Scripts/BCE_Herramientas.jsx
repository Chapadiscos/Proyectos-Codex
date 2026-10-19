#target illustrator
#targetengine "bce_herramientas"

// Panel flotante con las herramientas de BCE Anejos. Se abre UNA vez (Archivo >
// Scripts > Otro script...) y se queda visible mientras trabajas: puedes ir
// cambiando de archivo .ai activo en Illustrator y pulsar los botones tantas
// veces como haga falta, sin volver a abrir el script cada vez.
//
// - "Traducir fechas y frases": traduce las celdas de fecha (trimestres/meses)
//   del PDF importado y avisa (seleccionando los cuadros) si aparece alguna
//   frase variable como "% of total in".
// - "Seleccionar azules + borde + Subcabeceras": selecciona (sin borrar) las
//   cabeceras/líneas azules y el borde de página del PDF importado, para
//   revisarlas visualmente y borrarlas tú con Supr si están bien.
//
// Ámbito de ambas: si hay algo seleccionado en el documento activo, trabajan
// solo sobre esa selección (recomendado: selecciona el grupo del PDF
// importado antes de pulsar el botón); si no hay selección, sobre toda la
// capa activa.
//
// El panel vive en un motor de ExtendScript persistente con nombre
// (#targetengine): sin nombre, el motor "por defecto" puede perder la
// referencia correcta al documento activo y dar "there is no document" al
// pulsar un botón. Cada clic, en vez de ejecutar la acción directamente en
// ese motor ya cargado, pide a Illustrator (vía BridgeTalk) que reevalúe este
// mismo archivo desde cero -así la acción corre siempre con una referencia
// fresca y correcta al documento activo.

(function () {
    var WINDOW_ID = "bceHerramientasWindow";
    var ACTION_ID = "bceHerramientasAccion";
    var SCRIPT_FILE = File($.fileName);

    // Constantes compartidas por "Colocación tabla" y "Alineación columnas".
    var SPLIT_GAP = 40;    // pt: salto vertical entre filas que separa dos bloques
    var LABEL_MARGIN = 4;  // pt: margen vertical para asignar rótulos a un bloque
    var NUMERIC_RE = /^(-?[\d.]+(,\d+)?|[.\-])$/;

    // Cuando el panel vuelve a ejecutar este mismo archivo via BridgeTalk, se
    // lanza directamente la acción pedida en lugar de abrir otro panel.
    var pendingAction = $.global[ACTION_ID];
    if (pendingAction) {
        $.global[ACTION_ID] = null;
        try {
            if (pendingAction === "importar") importarPdf();
            else if (pendingAction === "fechas") traducirFechasYFrases();
            else if (pendingAction === "azules") seleccionarAzules();
            else if (pendingAction === "borrar") borrarSeleccion();
            else if (pendingAction === "colocar") colocacionTabla();
            else if (pendingAction === "alinear") alineacionColumnas();
        } catch (e) {
            alert("Error en línea " + e.line + ": " + e.message);
        }
        return;
    }

    if ($.global[WINDOW_ID] && $.global[WINDOW_ID] instanceof Window) {
        try { $.global[WINDOW_ID].close(); } catch (err) {}
        $.global[WINDOW_ID] = null;
    }

    var win = new Window("palette", "BCE Anejos", undefined, { closeButton: true });
    $.global[WINDOW_ID] = win;

    win.orientation = "column";
    win.alignChildren = "fill";
    win.margins = 16;
    win.spacing = 8;

    var label = win.add("statictext", undefined, "Selecciona el archivo PDF a modificar", { multiline: true });
    label.preferredSize.width = 260;

    var btnImportar = win.add("button", undefined, "Importar PDF");
    var btnFechas = win.add("button", undefined, "Traducir fechas y frases");
    var btnAzules = win.add("button", undefined, "Seleccionar azules + borde + Subcabeceras");
    var btnBorrar = win.add("button", undefined, "Borrar selección + borde");
    var btnColocar = win.add("button", undefined, "Colocación tabla");
    var btnAlinear = win.add("button", undefined, "Alineación columnas");

    btnImportar.onClick = function () { runAction("importar"); };
    btnFechas.onClick = function () { runAction("fechas"); };
    btnAzules.onClick = function () { runAction("azules"); };
    btnBorrar.onClick = function () { runAction("borrar"); };
    btnColocar.onClick = function () { runAction("colocar"); };
    btnAlinear.onClick = function () { runAction("alinear"); };

    win.onClose = function () { $.global[WINDOW_ID] = null; };

    win.center();
    win.show();

    function quoteForJavaScript(value) {
        return "\"" + String(value).replace(/\\/g, "\\\\").replace(/"/g, "\\\"") + "\"";
    }

    function runAction(actionName) {
        if (app.documents.length === 0) {
            alert("Abre primero el documento de Illustrator.");
            return;
        }
        if (!SCRIPT_FILE.exists) {
            alert("No se encuentra el script:\r" + SCRIPT_FILE.fsName + "\rVuelve a abrir el panel desde el archivo actual.");
            return;
        }

        var actionKey = quoteForJavaScript(ACTION_ID);
        var message = new BridgeTalk();
        message.target = "illustrator";
        message.body = "$.global[" + actionKey + "] = " + quoteForJavaScript(actionName) + ";" +
            " try { $.evalFile(File(" + quoteForJavaScript(SCRIPT_FILE.fsName) + ")); }" +
            " finally { $.global[" + actionKey + "] = null; }";
        message.onError = function (response) {
            alert("No se pudo ejecutar la acción:\r" + response.body);
        };
        message.send();
    }

    function traducirFechasYFrases() {
        var doc = app.activeDocument;

        var MONTHS = {
            "jan": "Ene", "feb": "Feb", "mar": "Mar", "apr": "Abr", "may": "May",
            "jun": "Jun", "june": "Jun", "jul": "Jul", "july": "Jul", "aug": "Ago",
            "sep": "Sep", "sept": "Sep", "oct": "Oct", "nov": "Nov", "dec": "Dic"
        };
        var QUARTERS = {"Q1": "I", "Q2": "II", "Q3": "III", "Q4": "IV"};

        // Frases que solo se avisan (no se tocan). Añadir aquí futuras frases
        // problemáticas: {texto a buscar, traducción sugerida para el aviso}.
        var PHRASES_AVISO = [
            { from: "% of total in", to: "% del total en" }
        ];

        // Devuelve {text, splitIndex}: splitIndex es la posición donde termina
        // el año y empieza el periodo (misma posición en el texto original y
        // en el traducido, porque el año siempre mide 4 caracteres), o -1 si
        // la celda no lleva año delante. Devuelve null si no es una etiqueta
        // de fecha en inglés.
        function translateCell(text) {
            var m = text.match(/^(\d{4})(Q[1-4])$/);
            if (m) return { text: m[1] + QUARTERS[m[2]] + " TR", splitIndex: m[1].length };

            m = text.match(/^(Q[1-4])$/);
            if (m) return { text: QUARTERS[m[1]] + " TR", splitIndex: -1 };

            m = text.match(/^(\d{4})([A-Za-z]+)\.?$/);
            if (m) {
                var key1 = m[2].toLowerCase();
                if (MONTHS[key1]) return { text: m[1] + MONTHS[key1], splitIndex: m[1].length };
            }

            m = text.match(/^([A-Za-z]+)\.?$/);
            if (m) {
                var key2 = m[1].toLowerCase();
                if (MONTHS[key2]) return { text: MONTHS[key2], splitIndex: -1 };
            }

            return null; // sin cambios
        }

        function collectTextFrames(items, out) {
            for (var i = 0; i < items.length; i++) {
                var it = items[i];
                if (it.typename === "TextFrame") {
                    out.push(it);
                } else if (it.typename === "GroupItem") {
                    collectTextFrames(it.pageItems, out);
                }
            }
        }

        var scopeItems;
        var scopeDesc;
        if (doc.selection && doc.selection.length > 0) {
            scopeItems = doc.selection;
            scopeDesc = "la selección actual";
        } else {
            scopeItems = doc.activeLayer.pageItems;
            scopeDesc = "la capa activa (\"" + doc.activeLayer.name + "\")";
        }

        var frames = [];
        collectTextFrames(scopeItems, frames);

        var changes = [];
        for (var f = 0; f < frames.length; f++) {
            var frame = frames[f];
            var original = frame.contents;
            var trimmed = original.replace(/^\s+|\s+$/g, "");
            var result = translateCell(trimmed);
            if (result !== null && result.text !== trimmed) {
                var translated = result.text;
                var idx = result.splitIndex;

                var trackBefore = null, trackAt = null;
                if (idx > 0) {
                    try { trackBefore = frame.characters[idx - 1].characterAttributes.tracking; } catch (e1) {}
                    try { trackAt = frame.characters[idx].characterAttributes.tracking; } catch (e2) {}
                }

                frame.contents = translated;

                if (idx > 0) {
                    try { if (trackBefore !== null) frame.characters[idx - 1].characterAttributes.tracking = trackBefore; } catch (e3) {}
                    try { if (trackAt !== null) frame.characters[idx].characterAttributes.tracking = trackAt; } catch (e4) {}
                }

                changes.push(trimmed + "  ->  " + translated);
            }
        }

        // --- Aviso de frases sueltas (no se modifican, solo se avisa) ---

        function isBlank(ch) {
            return ch === " " || ch === "\t" || ch === "\r" || ch === "\n" || ch.charCodeAt(0) === 160;
        }

        function normalize(s) {
            var out = "";
            for (var i = 0; i < s.length; i++) {
                if (!isBlank(s.charAt(i))) out += s.charAt(i).toLowerCase();
            }
            return out;
        }

        // Un simple orden global por altura no sirve: en una tabla, celdas de
        // OTRA fila pueden tener un "top" que cae justo entre las dos líneas
        // de un mismo pie de texto (misma columna), colándose en medio y
        // rompiendo la frase. Así que cada cuadro se encadena solo con el más
        // cercano que esté justo debajo Y en la misma columna (misma
        // coordenada izquierda).
        var MAX_GAP = 20;  // separación vertical máxima entre línea y línea (pt)
        var LEFT_TOL = 3;  // tolerancia horizontal para considerar "misma columna" (pt)

        var successor = []; // successor[i] = índice en frames[] del cuadro que continúa a frames[i], o -1
        var hasPredecessor = [];
        for (var i1 = 0; i1 < frames.length; i1++) { successor.push(-1); hasPredecessor.push(false); }

        for (var i2 = 0; i2 < frames.length; i2++) {
            var best = -1, bestGap = MAX_GAP + 1;
            for (var j2 = 0; j2 < frames.length; j2++) {
                if (i2 === j2) continue;
                if (Math.abs(frames[i2].left - frames[j2].left) > LEFT_TOL) continue;
                var gap = frames[i2].top - frames[j2].top; // positivo si j2 está debajo de i2
                if (gap > 0 && gap <= MAX_GAP && gap < bestGap) {
                    best = j2;
                    bestGap = gap;
                }
            }
            if (best !== -1) {
                successor[i2] = best;
                hasPredecessor[best] = true;
            }
        }

        // Cada cuadro sin predecesor es el inicio de una cadena (columna de líneas).
        var chains = [];
        for (var i3 = 0; i3 < frames.length; i3++) {
            if (hasPredecessor[i3]) continue;
            var chain = [i3];
            var next = successor[i3];
            while (next !== -1 && chain.length < 20) {
                chain.push(next);
                next = successor[next];
            }
            chains.push(chain);
        }

        var warnings = [];
        var framesToSelect = [];

        for (var ph = 0; ph < PHRASES_AVISO.length; ph++) {
            var target = normalize(PHRASES_AVISO[ph].from);

            for (var ch2 = 0; ch2 < chains.length; ch2++) {
                var offsets = []; // {frame, start, end} posiciones en el string concatenado de esta cadena
                var concat = "";
                for (var c2 = 0; c2 < chains[ch2].length; c2++) {
                    var fr = frames[chains[ch2][c2]];
                    var norm = normalize(fr.contents);
                    offsets.push({ frame: fr, start: concat.length, end: concat.length + norm.length });
                    concat += norm;
                }

                var pos = concat.indexOf(target);
                while (pos !== -1) {
                    var matchStart = pos;
                    var matchEnd = pos + target.length;
                    var involved = [];
                    for (var o = 0; o < offsets.length; o++) {
                        if (offsets[o].end > matchStart && offsets[o].start < matchEnd) involved.push(offsets[o].frame);
                    }
                    if (involved.length > 0) {
                        var preview = [];
                        for (var p2 = 0; p2 < involved.length; p2++) preview.push(involved[p2].contents);
                        warnings.push("\"" + PHRASES_AVISO[ph].from + "\"  ->  traducir a  \"" + PHRASES_AVISO[ph].to +
                            "\"\n   encontrada en: " + preview.join(" | "));
                        for (var s2 = 0; s2 < involved.length; s2++) framesToSelect.push(involved[s2]);
                    }
                    pos = concat.indexOf(target, pos + 1);
                }
            }
        }

        if (framesToSelect.length > 0) {
            doc.selection = null;
            doc.selection = framesToSelect;
        }

        // Solo se avisa si aparece una frase que hay que traducir a mano.
        if (warnings.length === 0) return;

        var msg = "TRADUCIR A MANO (cuadros ya seleccionados en el documento):\n\n";
        for (var w = 0; w < warnings.length; w++) {
            msg += warnings[w] + "\n\n";
        }
        alert(msg);
    }

    // Borra por script lo que haya seleccionado (sin depender de la herramienta
    // activa ni del foco de teclado) y, además, la máscara de recorte del PDF
    // importado (el "borde de página"): es un trazado de recorte del tamaño de
    // la página que Illustrator no deja seleccionar por script junto al resto.
    function borrarSeleccion() {
        var doc = app.activeDocument;
        var sel = doc.selection;
        var n = 0;
        if (sel && sel.length > 0) {
            n = sel.length;
            for (var i = sel.length - 1; i >= 0; i--) {
                try { sel[i].remove(); } catch (e) {}
            }
        }

        var PAGE_W = 595.28, PAGE_H = 841.89, TOL = 3;
        var clips = [];
        function findClips(items) {
            for (var j = 0; j < items.length; j++) {
                var it = items[j];
                if (it.typename === "GroupItem") {
                    findClips(it.pageItems);
                } else if (it.typename === "PathItem" && it.clipping) {
                    var b = it.geometricBounds;
                    if (Math.abs((b[2] - b[0]) - PAGE_W) <= TOL && Math.abs((b[1] - b[3]) - PAGE_H) <= TOL) clips.push(it);
                }
            }
        }
        findClips(doc.pageItems);
        var nClips = 0;
        for (var k = 0; k < clips.length; k++) {
            try { clips[k].remove(); nClips++; } catch (e2) {}
        }
    }

    // Recoge TextFrames sin duplicados (pageItems puede incluir los anidados).
    function collectFrames(items, out, seen) {
        for (var i = 0; i < items.length; i++) {
            var it = items[i];
            if (it.typename === "TextFrame") {
                var g = it.geometricBounds;
                var key = it.contents + "|" + Math.round(g[0] * 10) + "|" + Math.round(g[1] * 10);
                if (!seen[key]) { seen[key] = true; out.push(it); }
            } else if (it.typename === "GroupItem") {
                collectFrames(it.pageItems, out, seen);
            }
        }
    }

    function trim(t) { return t.replace(/^\s+|\s+$/g, ""); }

    // Filas de números de columna ("1 2 3 ..." o "7 6 5 ..."): enteros de 1-2
    // cifras consecutivos de una misma fila. Son las cabeceras numeradas del PDF y
    // no forman parte de los datos (en el original están en la capa "cabeceras").
    function isColumnNumberRow(row) {
        if (row.length < 2) return false;
        var sorted = row.slice().sort(function (x, y) { return x.left - y.left; });
        var vals = [];
        for (var i = 0; i < sorted.length; i++) {
            var t = trim(sorted[i].frame.contents);
            if (!/^\d{1,2}$/.test(t)) return false;
            vals.push(parseInt(t, 10));
        }
        var step = vals[1] - vals[0];
        if (step !== 1 && step !== -1) return false;
        for (var j = 1; j < vals.length; j++) if (vals[j] - vals[j - 1] !== step) return false;
        return true;
    }

    function toCells(frames) {
        var cells = [], labels = [];
        for (var i = 0; i < frames.length; i++) {
            var g = frames[i].geometricBounds; // [left, top, right, bottom]
            var cell = { frame: frames[i], left: g[0], right: g[2], top: g[1], bottom: g[3] };
            if (NUMERIC_RE.test(trim(frames[i].contents))) cells.push(cell); else labels.push(cell);
        }
        // Se descartan las filas de números de columna.
        var byTop = cells.slice().sort(function (x, y) { return y.top - x.top; });
        var rows = [];
        for (var r = 0; r < byTop.length; r++) {
            var lastRow = rows.length ? rows[rows.length - 1] : null;
            if (lastRow && Math.abs(lastRow[0].top - byTop[r].top) <= 2) lastRow.push(byTop[r]);
            else rows.push([byTop[r]]);
        }
        var data = [];
        for (var q = 0; q < rows.length; q++) {
            if (!isColumnNumberRow(rows[q])) for (var z = 0; z < rows[q].length; z++) data.push(rows[q][z]);
        }
        return { cells: data, labels: labels };
    }

    // Separa las celdas en bloques por saltos verticales grandes (arriba->abajo).
    function splitBlocks(cells) {
        var sorted = cells.slice().sort(function (x, y) { return y.top - x.top; });
        var blocks = [];
        var prevTop = null;
        for (var i = 0; i < sorted.length; i++) {
            if (prevTop === null || prevTop - sorted[i].top > SPLIT_GAP) blocks.push([]);
            blocks[blocks.length - 1].push(sorted[i]);
            prevTop = sorted[i].top;
        }
        return blocks;
    }

    function maxOf(arr, prop) {
        var m = arr[0][prop];
        for (var i = 1; i < arr.length; i++) if (arr[i][prop] > m) m = arr[i][prop];
        return m;
    }
    function minOf(arr, prop) {
        var m = arr[0][prop];
        for (var i = 1; i < arr.length; i++) if (arr[i][prop] < m) m = arr[i][prop];
        return m;
    }


    // Rótulos (años, periodos...) que caen en el rango vertical de un bloque.
    function labelsOfBlock(block, labels) {
        var top = maxOf(block, "top"), bottom = minOf(block, "bottom");
        var out = [];
        for (var i = 0; i < labels.length; i++) {
            var cy = (labels[i].top + labels[i].bottom) / 2;
            if (cy <= top + LABEL_MARGIN && cy >= bottom - LABEL_MARGIN) out.push(labels[i]);
        }
        return out;
    }

    // Esquina superior izquierda de un bloque (celdas + sus rótulos).
    function blockCorner(members) {
        var left = null, top = null;
        for (var i = 0; i < members.length; i++) {
            var g = members[i].frame.geometricBounds; // [left, top, right, bottom]
            if (left === null || g[0] < left) left = g[0];
            if (top === null || g[1] > top) top = g[1];
        }
        return { left: left, top: top };
    }

    // Coloca el PDF importado (ya traducido y limpio, seleccionado; está en la
    // misma "Capa 3" pero fuera de la mesa de trabajo) donde estaba el contenido
    // de "Capa 3" que hay dentro de la mesa, y desplaza ese contenido original
    // 210 mm a la derecha para poder comparar ambos lado a lado.
    // Si la tabla tiene varios bloques (cada uno con su cabecera), se coloca
    // bloque a bloque: el bloque 1 en la esquina del bloque 1 original, el 2 en
    // la del 2 original, etc. Si no se pueden emparejar los bloques, se coloca
    // todo el conjunto por su esquina superior izquierda.
    function colocacionTabla() {
        var LAYER_NAME = "Capa 3";
        var SHIFT_PT = 210 * 72 / 25.4; // 210 mm en puntos
        var doc = app.activeDocument;

        var layer;
        try {
            layer = doc.layers.getByName(LAYER_NAME);
        } catch (e) {
            alert("No se encuentra la capa \"" + LAYER_NAME + "\" en este documento.");
            return;
        }

        // Si no hay nada seleccionado, se toma como tabla traducida lo que hay en
        // la capa fuera de la mesa de trabajo (el PDF importado, limpio y listo
        // para colocar).
        var sel = doc.selection;
        if (!sel || sel.length === 0) {
            var abSel = doc.artboards[doc.artboards.getActiveArtboardIndex()].artboardRect; // [left, top, right, bottom]
            var outside = [];
            for (var oi = 0; oi < layer.pageItems.length; oi++) {
                var oit = layer.pageItems[oi];
                if (!oit.parent || oit.parent.typename !== "Layer") continue;
                var og = oit.geometricBounds;
                var inside = og[0] < abSel[2] && og[2] > abSel[0] && og[1] > abSel[3] && og[3] < abSel[1];
                if (!inside) outside.push(oit);
            }
            if (outside.length === 0) {
                alert("Selecciona primero la Tabla traducida.");
                return;
            }
            doc.selection = outside;
            sel = doc.selection;
        }

        function unionBounds(items) {
            var u = null;
            for (var i = 0; i < items.length; i++) {
                var g = items[i].geometricBounds; // [left, top, right, bottom]
                if (!u) u = [g[0], g[1], g[2], g[3]];
                else {
                    u[0] = Math.min(u[0], g[0]);
                    u[1] = Math.max(u[1], g[1]);
                    u[2] = Math.max(u[2], g[2]);
                    u[3] = Math.min(u[3], g[3]);
                }
            }
            return u;
        }

        // Originales: objetos de primer nivel de la capa que caen dentro de la mesa
        // de trabajo activa (el PDF importado está fuera de ella, en la misma
        // capa, y no debe moverse). Mover también los anidados los desplazaría
        // dos veces.
        var ab = doc.artboards[doc.artboards.getActiveArtboardIndex()].artboardRect; // [left, top, right, bottom]
        var originals = [];
        for (var k = 0; k < layer.pageItems.length; k++) {
            var it = layer.pageItems[k];
            if (!it.parent || it.parent.typename !== "Layer") continue;
            var g = it.geometricBounds;
            var intersects = g[0] < ab[2] && g[2] > ab[0] && g[1] > ab[3] && g[3] < ab[1];
            if (intersects) originals.push(it);
        }
        if (originals.length === 0) {
            alert("No hay contenido de \"" + LAYER_NAME + "\" dentro de la mesa de trabajo.");
            return;
        }

        // Bloques de la tabla nueva y del original.
        var newFrames = [], origFrames = [];
        collectFrames(sel, newFrames, {});
        collectFrames(originals, origFrames, {});
        var newParts = toCells(newFrames), origParts = toCells(origFrames);

        var perBlock = null; // [{members, dx, dy}] si se pueden emparejar los bloques
        if (newParts.cells.length > 0 && origParts.cells.length > 0) {
            var nb = splitBlocks(newParts.cells), ob = splitBlocks(origParts.cells);
            if (nb.length === ob.length) {
                perBlock = [];
                for (var b = 0; b < nb.length; b++) {
                    var newMembers = nb[b].concat(labelsOfBlock(nb[b], newParts.labels));
                    var origMembers = ob[b].concat(labelsOfBlock(ob[b], origParts.labels));
                    var cn = blockCorner(newMembers), co = blockCorner(origMembers);
                    perBlock.push({ members: newMembers, dx: co.left - cn.left, dy: co.top - cn.top });
                }
            } else {
                alert("La tabla nueva tiene " + nb.length + " bloque(s) y el original " + ob.length + ": no se pueden emparejar. Se coloca todo el conjunto por su esquina superior izquierda.");
            }
        }

        // Todos los cálculos se hacen antes de mover nada.
        var dxAll, dyAll;
        if (perBlock) {
            dxAll = perBlock[0].dx;
            dyAll = perBlock[0].dy;
        } else {
            var target = unionBounds(originals);
            var pdfBounds = unionBounds(sel);
            dxAll = target[0] - pdfBounds[0];
            dyAll = target[1] - pdfBounds[1];
        }

        var layerWasLocked = layer.locked;
        layer.locked = false;
        for (var m = 0; m < originals.length; m++) {
            var wasLocked = originals[m].locked;
            originals[m].locked = false;
            originals[m].translate(SHIFT_PT, 0);
            originals[m].locked = wasLocked;
        }
        layer.locked = layerWasLocked;

        // Todo lo seleccionado se mueve como el bloque 1; los demás bloques
        // reciben además el ajuste que les falta respecto al bloque 1.
        for (var n = 0; n < sel.length; n++) {
            sel[n].translate(dxAll, dyAll);
        }
        if (perBlock) {
            for (var pb = 1; pb < perBlock.length; pb++) {
                var extraDx = perBlock[pb].dx - perBlock[0].dx;
                var extraDy = perBlock[pb].dy - perBlock[0].dy;
                for (var mm = 0; mm < perBlock[pb].members.length; mm++) {
                    perBlock[pb].members[mm].frame.translate(extraDx, extraDy);
                }
            }
        }
    }

    // Alinea la tabla seleccionada con las cabeceras y el contenido original.
    // Una página puede tener varios bloques (cada uno con su fila de números de
    // cabecera en la capa "cabeceras", que puede estar bloqueada: solo se lee):
    //  - Los bloques de la tabla nueva se separan por los saltos verticales
    //    grandes entre filas y se emparejan, de arriba a abajo, con las filas de
    //    cabeceras.
    //  - Horizontal: cada columna numérica de un bloque se alinea a la derecha con
    //    su número de cabecera, desplazando la columna entera (mediana de los
    //    bordes derechos) para no alterar la alineación interna de las cifras.
    //  - Vertical: cada bloque se coloca a la misma altura que el bloque
    //    correspondiente del contenido original de "Capa 3", que "Colocación
    //    tabla" dejó desplazado 210 mm a la derecha.
    function alineacionColumnas() {
        var HEADER_LAYER = "cabeceras";
        var ORIG_LAYER = "Capa 3";
        var SHIFT_PT = 210 * 72 / 25.4; // el original está 210 mm a la derecha
        var CLUSTER_TOL = 3;   // pt: bordes derechos a menos de esto son la misma columna
        var ROW_TOL = 2;       // pt: cabeceras a la misma altura son la misma fila
        var doc = app.activeDocument;

        var sel = doc.selection;
        if (!sel || sel.length === 0) {
            alert("Selecciona primero la Tabla traducida.");
            return;
        }

        var headerLayer = null;
        for (var l = 0; l < doc.layers.length; l++) {
            if (doc.layers[l].name.toLowerCase() === HEADER_LAYER) { headerLayer = doc.layers[l]; break; }
        }
        if (!headerLayer) {
            alert("No se encuentra la capa \"" + HEADER_LAYER + "\" en este documento.");
            return;
        }
        var origLayer = null;
        try { origLayer = doc.layers.getByName(ORIG_LAYER); } catch (eL) {}

        // --- Cabeceras: filas de números enteros de 1-2 cifras, de arriba a abajo ---
        // Los números de cabecera pueden venir como cuadros sueltos ("1", "2") o
        // todos juntos en un solo cuadro separados por tracking ("3456789101112").
        // En ese caso se localiza cada número por la posición de sus cifras: se
        // obtienen los contornos de cada carácter de una copia temporal, se agrupan
        // las cifras pegadas ("1","0" -> 10) y se calcula el borde derecho de cada
        // número a partir del centro de su última cifra y el ancho de una cifra.
        var headerFrames = [];
        collectFrames(headerLayer.pageItems, headerFrames, {});
        // Se ignoran los cuadros ocultos, o dentro de un grupo oculto (restos de
        // versiones anteriores de la cabecera que no se ven pero siguen ahí).
        function isHiddenDeep(item) {
            var cur = item;
            while (cur && cur.typename !== "Layer" && cur.typename !== "Document") {
                if (cur.hidden) return true;
                cur = cur.parent;
            }
            return false;
        }
        var visibleHeaderFrames = [];
        for (var vh = 0; vh < headerFrames.length; vh++) {
            if (!isHiddenDeep(headerFrames[vh])) visibleHeaderFrames.push(headerFrames[vh]);
        }
        headerFrames = visibleHeaderFrames;

        var digitAdvance = null; // ancho de una cifra, medido en un cuadro de una sola cifra
        for (var da = 0; da < headerFrames.length && digitAdvance === null; da++) {
            if (/^\d$/.test(trim(headerFrames[da].contents))) {
                var dg = headerFrames[da].geometricBounds;
                digitAdvance = dg[2] - dg[0];
            }
        }

        function glyphBoxes(item, out) {
            if (item.typename === "GroupItem") {
                for (var gi = 0; gi < item.pageItems.length; gi++) glyphBoxes(item.pageItems[gi], out);
            } else {
                var b = item.geometricBounds;
                out.push({ left: b[0], right: b[2] });
            }
        }

        function splitDigitFrame(frame, adv) {
            var res = [];
            // Para duplicar el cuadro hay que desbloquearlo a él y a los grupos que
            // lo contienen (pueden estar bloqueados aunque la capa ya no lo esté);
            // se restauran al terminar.
            var locks = [];
            var anc = frame;
            while (anc && (anc.typename === "TextFrame" || anc.typename === "GroupItem")) {
                if (anc.locked) { locks.push(anc); anc.locked = false; }
                anc = anc.parent;
            }
            var boxes = [];
            try {
                var copy = frame.duplicate();
                var outlined = copy.createOutline();
                glyphBoxes(outlined, boxes);
                outlined.remove();
            } finally {
                for (var lk = locks.length - 1; lk >= 0; lk--) locks[lk].locked = true;
            }
            boxes.sort(function (x, y) { return x.left - y.left; });
            var size = frame.textRange.characterAttributes.size;
            var w = adv !== null ? adv : size * 0.556;
            // Cifras del mismo número: el hueco entre sus trazos es menor que una
            // cifra; entre números distintos (separados por tracking) es mucho mayor.
            var cluster = [];
            for (var bx = 0; bx < boxes.length; bx++) {
                if (cluster.length && boxes[bx].left - cluster[cluster.length - 1].right > w * 1.6) {
                    res.push(cluster); cluster = [];
                }
                cluster.push(boxes[bx]);
            }
            if (cluster.length) res.push(cluster);
            var top = frame.geometricBounds[1];
            var nums2 = [];
            for (var rc = 0; rc < res.length; rc++) {
                var lastGlyph = res[rc][res[rc].length - 1];
                nums2.push({ right: (lastGlyph.left + lastGlyph.right) / 2 + w / 2, top: top });
            }
            return nums2;
        }

        var nums = [];
        var wasLocked = headerLayer.locked;
        headerLayer.locked = false; // hace falta para duplicar/contornear; se restaura después
        try {
        for (var h = 0; h < headerFrames.length; h++) {
            var ht = trim(headerFrames[h].contents);
            if (/^\d$/.test(ht)) {
                var hg = headerFrames[h].geometricBounds;
                nums.push({ left: hg[0], right: hg[2], top: hg[1], raw: true });
            } else if (/^\d{2,}$/.test(ht.replace(/\s+/g, ""))) {
                // Dos o más cifras: puede ser un solo número ("13") o varios juntos con
                // tracking entre ellos ("78" = 7 y 8); se decide por el hueco entre cifras.
                var split = splitDigitFrame(headerFrames[h], digitAdvance);
                for (var sp = 0; sp < split.length; sp++) nums.push(split[sp]);
            }
        }
        } finally {
            headerLayer.locked = wasLocked;
        }
        // Un número de dos cifras puede venir partido en un cuadro por cifra (el 10
        // como "1" y "0" pegados): se unen los cuadros de la misma fila que se tocan.
        nums.sort(function (x, y) { return (Math.abs(x.top - y.top) <= ROW_TOL) ? (x.left - y.left) : (y.top - x.top); });
        var mergedNums = [];
        for (var mn = 0; mn < nums.length; mn++) {
            var prevN = mergedNums.length ? mergedNums[mergedNums.length - 1] : null;
            if (prevN && prevN.raw && nums[mn].raw && prevN.digits < 3 &&
                Math.abs(prevN.top - nums[mn].top) <= ROW_TOL && nums[mn].left - prevN.right <= 1) {
                prevN.right = nums[mn].right;
                prevN.digits++;
            } else {
                nums[mn].digits = 1;
                mergedNums.push(nums[mn]);
            }
        }
        nums = mergedNums;
        nums.sort(function (x, y) { return y.top - x.top; });
        var headerRows = [];
        for (var n = 0; n < nums.length; n++) {
            var lastRow = headerRows.length ? headerRows[headerRows.length - 1] : null;
            if (lastRow && Math.abs(lastRow[0].top - nums[n].top) <= ROW_TOL) lastRow.push(nums[n]);
            else headerRows.push([nums[n]]);
        }
        // Se descartan filas sueltas de un solo número (no son cabeceras de tabla),
        // salvo que no haya ninguna con más de uno.
        var multi = [];
        for (var hr = 0; hr < headerRows.length; hr++) if (headerRows[hr].length >= 2) multi.push(headerRows[hr]);
        if (multi.length > 0) headerRows = multi;
        if (headerRows.length === 0) {
            alert("No se encontraron números de cabecera en la capa \"" + HEADER_LAYER + "\".");
            return;
        }
        var headerRights = []; // headerRights[fila] = bordes derechos de izquierda a derecha
        for (var r = 0; r < headerRows.length; r++) {
            headerRows[r].sort(function (x, y) { return x.right - y.right; });
            var rights = [];
            for (var q = 0; q < headerRows[r].length; q++) rights.push(headerRows[r][q].right);
            headerRights.push(rights);
        }

        // --- Tabla nueva: bloques ---
        var frames = [];
        collectFrames(sel, frames, {});
        var parts = toCells(frames);
        if (parts.cells.length === 0) {
            alert("No se encontraron celdas numéricas en la selección.");
            return;
        }
        var blocks = splitBlocks(parts.cells);
        // Una sola fila de cabecera y varios bloques: todos los bloques se alinean
        // con esa única fila.
        var singleHeader = headerRights.length === 1;
        if (!singleHeader && blocks.length !== headerRights.length) {
            alert("La tabla tiene " + blocks.length + " bloque(s) y la capa \"" + HEADER_LAYER + "\" " + headerRights.length + " fila(s) de cabeceras; no se puede alinear.");
            return;
        }

        // --- Horizontal: columnas alineadas con su cabecera ---
        // Agrupa las celdas por borde derecho. Los grupos con muy pocas celdas
        // (años, o celdas sueltas con el borde algo distinto, como guiones o
        // puntos) se descartan como columna de datos para que no desplacen el
        // reparto de columnas a cabeceras; esas celdas sueltas se asignan luego a
        // la columna de datos más cercana.
        function planColumns(cells, rowRights, label) {
            var need = rowRights.length;
            var byRight = cells.slice().sort(function (x, y) { return x.right - y.right; });
            var all = [];
            for (var k = 0; k < byRight.length; k++) {
                var lastCol = all.length ? all[all.length - 1] : null;
                if (lastCol && byRight[k].right - lastCol[lastCol.length - 1].right <= CLUSTER_TOL) lastCol.push(byRight[k]);
                else all.push([byRight[k]]);
            }
            var biggest = 0;
            for (var c0 = 0; c0 < all.length; c0++) if (all[c0].length > biggest) biggest = all[c0].length;
            var kept = [];
            for (var c1 = 0; c1 < all.length; c1++) if (all[c1].length >= Math.max(3, biggest / 2)) kept.push(all[c1]);
            if (kept.length < need) kept = all; // pocas celdas: no se filtra
            if (kept.length < need) return { error: label + " tiene " + kept.length + " columnas numéricas y su cabecera " + need + "." };
            kept = kept.slice(kept.length - need); // las de datos son las últimas (derecha)

            var medians = [];
            for (var c2 = 0; c2 < kept.length; c2++) {
                var rs = [];
                for (var g2 = 0; g2 < kept[c2].length; g2++) rs.push(kept[c2][g2].right);
                rs.sort(function (x, y) { return x - y; });
                medians.push(rs[Math.floor(rs.length / 2)]);
            }
            var inKept = [];
            var moves = [];
            for (var c3 = 0; c3 < kept.length; c3++) {
                for (var g3 = 0; g3 < kept[c3].length; g3++) {
                    moves.push({ cell: kept[c3][g3], dx: rowRights[c3] - medians[c3], col: c3 });
                    inKept.push(kept[c3][g3]);
                }
            }
            // Celdas fuera de las columnas elegidas: las que están a la derecha de la
            // primera columna de datos siguen a la columna más cercana; las de la
            // izquierda son etiquetas (años).
            var firstRight = medians[0];
            var labelCells = [];
            for (var c4 = 0; c4 < cells.length; c4++) {
                var found = false;
                for (var c5 = 0; c5 < inKept.length; c5++) if (inKept[c5] === cells[c4]) { found = true; break; }
                if (found) continue;
                if (cells[c4].right < firstRight - CLUSTER_TOL) { labelCells.push(cells[c4]); continue; }
                var bestI = 0, bestD = 1e9;
                for (var c6 = 0; c6 < medians.length; c6++) {
                    var dd = Math.abs(cells[c4].right - medians[c6]);
                    if (dd < bestD) { bestD = dd; bestI = c6; }
                }
                moves.push({ cell: cells[c4], dx: rowRights[bestI] - medians[bestI], col: bestI });
            }
            return { moves: moves, labelCells: labelCells };
        }

        // Plan por proximidad: cada celda va a la cabecera de borde derecho más
        // cercano (sin depender de cuántos grupos de celdas haya ni de su orden).
        // Las de la izquierda de la primera cabecera son etiquetas (años).
        function planNearest(cells, rowRights) {
            var groups = [];
            for (var i = 0; i < rowRights.length; i++) groups.push([]);
            var labelCells = [];
            for (var c = 0; c < cells.length; c++) {
                if (cells[c].right < rowRights[0] - 20) { labelCells.push(cells[c]); continue; }
                var bestI = 0, bestD = 1e9;
                for (var j = 0; j < rowRights.length; j++) {
                    var dd = Math.abs(cells[c].right - rowRights[j]);
                    if (dd < bestD) { bestD = dd; bestI = j; }
                }
                groups[bestI].push(cells[c]);
            }
            var moves = [];
            for (var g = 0; g < groups.length; g++) {
                if (groups[g].length === 0) continue;
                var rs = [];
                for (var k = 0; k < groups[g].length; k++) rs.push(groups[g][k].right);
                rs.sort(function (x, y) { return x - y; });
                var med = rs[Math.floor(rs.length / 2)];
                for (var m = 0; m < groups[g].length; m++) moves.push({ cell: groups[g][m], dx: rowRights[g] - med, col: g });
            }
            return { moves: moves, labelCells: labelCells };
        }

        // Celdas de etiqueta (años) de cada bloque, a partir de las de todo el plan.
        function yearCellsByBlock(plansList) {
            var res = [];
            for (var yb = 0; yb < blocks.length; yb++) {
                var ycs = [];
                for (var pl = 0; pl < plansList.length; pl++) {
                    for (var yc = 0; yc < plansList[pl].labelCells.length; yc++) {
                        for (var yk = 0; yk < blocks[yb].length; yk++) {
                            if (blocks[yb][yk] === plansList[pl].labelCells[yc]) { ycs.push(plansList[pl].labelCells[yc]); break; }
                        }
                    }
                }
                res.push(ycs);
            }
            return res;
        }

        // Posiciones finales previstas: si dos celdas de una misma fila se
        // pisarían, devuelve la lista de choques (vacía si todo está bien).
        function findOverlaps(plansList) {
            var predicted = [];
            var moved = {};
            for (var pi = 0; pi < plansList.length; pi++) {
                for (var pm = 0; pm < plansList[pi].moves.length; pm++) {
                    var mv = plansList[pi].moves[pm];
                    predicted.push({ left: mv.cell.left + mv.dx, right: mv.cell.right + mv.dx, top: mv.cell.top, text: trim(mv.cell.frame.contents), dx: mv.dx });
                    moved[mv.cell.top + "|" + mv.cell.left] = true;
                }
            }
            for (var pc = 0; pc < parts.cells.length; pc++) {
                var pcell = parts.cells[pc];
                if (!moved[pcell.top + "|" + pcell.left]) predicted.push({ left: pcell.left, right: pcell.right, top: pcell.top, text: trim(pcell.frame.contents), dx: 0 });
            }
            predicted.sort(function (x, y) { return y.top - x.top; });
            var predRows = [];
            for (var pr = 0; pr < predicted.length; pr++) {
                var lastPR = predRows.length ? predRows[predRows.length - 1] : null;
                if (lastPR && Math.abs(lastPR[0].top - predicted[pr].top) <= ROW_TOL) lastPR.push(predicted[pr]);
                else predRows.push([predicted[pr]]);
            }
            var out = [];
            for (var prw = 0; prw < predRows.length; prw++) {
                var rowCells = predRows[prw].sort(function (x, y) { return x.left - y.left; });
                for (var po = 1; po < rowCells.length; po++) {
                    if (rowCells[po].left < rowCells[po - 1].right - 0.5) {
                        out.push("\"" + rowCells[po - 1].text + "\" (dx " + Math.round(rowCells[po - 1].dx) + ") y \"" + rowCells[po].text + "\" (dx " + Math.round(rowCells[po].dx) +
                            ") a " + Math.round(rowCells[po].top) + " pt");
                    }
                }
            }
            return out;
        }

        // Se prueban, por orden, tres formas de agrupar las celdas en columnas y se
        // usa la primera que no provoque solapes:
        //  1) columnas por borde derecho, con las celdas de todos los bloques juntas
        //     (solo con una única fila de cabecera);
        //  2) columnas por borde derecho calculadas bloque a bloque;
        //  3) cada celda a la cabecera más cercana.
        var candidates = [];
        var lastError = null;
        function tryCandidate(builder) {
            var built = builder();
            if (built && built.plans) candidates.push(built);
        }
        function perBlockPlans() {
            var plansB = [];
            for (var bi = 0; bi < blocks.length; bi++) {
                var planB = planColumns(blocks[bi], headerRights[singleHeader ? 0 : bi], "El bloque " + (bi + 1));
                if (planB.error) { lastError = planB.error; return null; }
                plansB.push(planB);
            }
            return { plans: plansB };
        }
        if (singleHeader) {
            tryCandidate(function () {
                var planAll = planColumns(parts.cells, headerRights[0], "La tabla");
                if (planAll.error) { lastError = planAll.error; return null; }
                return { plans: [planAll] };
            });
        }
        tryCandidate(perBlockPlans);
        tryCandidate(function () {
            var plansN = [];
            if (singleHeader) plansN.push(planNearest(parts.cells, headerRights[0]));
            else for (var bn = 0; bn < blocks.length; bn++) plansN.push(planNearest(blocks[bn], headerRights[bn]));
            return { plans: plansN };
        });

        var plans = null, firstOverlaps = null;
        for (var ci = 0; ci < candidates.length; ci++) {
            var ov = findOverlaps(candidates[ci].plans);
            if (ov.length === 0) { plans = candidates[ci].plans; break; }
            if (firstOverlaps === null) firstOverlaps = ov;
        }
        if (!plans) {
            if (firstOverlaps === null) { alert(lastError || "No se pudo agrupar las columnas."); return; }
            alert("No se ha movido nada: con ninguna forma de agrupar las columnas se evitan solapes (" + firstOverlaps.length + " en la primera prueba), p.ej.:\n" + firstOverlaps.slice(0, 5).join("\n"));
            return;
        }
        var yearCells = yearCellsByBlock(plans);

        // Se mueve columna por columna (de izquierda a derecha), seleccionando la
        // columna, moviéndola y refrescando la pantalla con una pausa, para poder
        // comprobar a simple vista que cada una queda bajo su cabecera.
        var COLUMN_PAUSE_MS = 500;
        var allMoves = [];
        for (var ap = 0; ap < plans.length; ap++) {
            for (var am = 0; am < plans[ap].moves.length; am++) allMoves.push(plans[ap].moves[am]);
        }
        allMoves.sort(function (x, y) { return x.col - y.col; });
        var mi = 0;
        while (mi < allMoves.length) {
            var colNow = allMoves[mi].col;
            var batch = [], batchFrames = [];
            while (mi < allMoves.length && allMoves[mi].col === colNow) {
                batch.push(allMoves[mi]);
                batchFrames.push(allMoves[mi].cell.frame);
                mi++;
            }
            try { doc.selection = batchFrames; } catch (eSel) {}
            for (var bm = 0; bm < batch.length; bm++) batch[bm].cell.frame.translate(batch[bm].dx, 0);
            app.redraw();
            $.sleep(COLUMN_PAUSE_MS);
        }
        try { doc.selection = sel; } catch (eSel2) {}

        // --- Origen horizontal común: con varios bloques, la primera columna de
        // etiquetas (años, trimestres...) de cada uno se alinea a la izquierda con
        // la del primer bloque. Se desplazan todas las etiquetas del bloque juntas
        // para conservar las sangrías entre niveles (p.ej. año y trimestre).
        if (blocks.length >= 2) {
            var labelGroups = [];
            for (var lg = 0; lg < blocks.length; lg++) {
                var bTop = maxOf(blocks[lg], "top"), bBottom = minOf(blocks[lg], "bottom");
                var members = yearCells[lg].slice();
                for (var lb0 = 0; lb0 < parts.labels.length; lb0++) {
                    var cy0 = (parts.labels[lb0].top + parts.labels[lb0].bottom) / 2;
                    if (cy0 <= bTop + LABEL_MARGIN && cy0 >= bBottom - LABEL_MARGIN) members.push(parts.labels[lb0]);
                }
                var minLeft = null;
                for (var mm = 0; mm < members.length; mm++) {
                    var left = members[mm].frame.geometricBounds[0];
                    if (minLeft === null || left < minLeft) minLeft = left;
                }
                labelGroups.push({ members: members, left: minLeft });
            }
            var refLeft = labelGroups[0].left;
            for (var lg2 = 1; lg2 < labelGroups.length; lg2++) {
                if (labelGroups[lg2].left === null || refLeft === null) continue;
                var dxl = refLeft - labelGroups[lg2].left;
                for (var mm2 = 0; mm2 < labelGroups[lg2].members.length; mm2++) labelGroups[lg2].members[mm2].frame.translate(dxl, 0);
            }
        }

        // --- Vertical: cada bloque a la altura del bloque original correspondiente ---
        var ab = doc.artboards[doc.artboards.getActiveArtboardIndex()].artboardRect; // [left, top, right, bottom]
        var origBlocks = [];
        if (origLayer) {
            var origFrames = [];
            collectFrames(origLayer.pageItems, origFrames, {});
            var inRegion = [];
            for (var o = 0; o < origFrames.length; o++) {
                var og = origFrames[o].geometricBounds;
                if (og[0] < ab[2] + SHIFT_PT && og[2] > ab[0] + SHIFT_PT && og[1] > ab[3] && og[3] < ab[1]) inRegion.push(origFrames[o]);
            }
            var origCells = toCells(inRegion).cells;
            if (origCells.length > 0) origBlocks = splitBlocks(origCells);
        }

        if (origBlocks.length !== blocks.length) {
            alert("No se pudo alinear en vertical: se esperaban " + blocks.length + " bloque(s) del contenido original de \"" + ORIG_LAYER + "\" desplazado 210 mm a la derecha y se encontraron " + origBlocks.length + ". Las columnas sí se han alineado.");
            return;
        }

        var dys = [], tops = [], bottoms = [];
        for (var v = 0; v < blocks.length; v++) {
            tops.push(maxOf(blocks[v], "top"));
            bottoms.push(minOf(blocks[v], "bottom"));
            dys.push(maxOf(origBlocks[v], "top") - tops[v]);
        }
        for (var v2 = 0; v2 < blocks.length; v2++) {
            for (var c = 0; c < blocks[v2].length; c++) blocks[v2][c].frame.translate(0, dys[v2]);
        }
        // Rótulos (años, periodos...) se mueven con el bloque cuyo rango vertical ocupan.
        for (var lb = 0; lb < parts.labels.length; lb++) {
            var lab = parts.labels[lb];
            var cy = (lab.top + lab.bottom) / 2;
            for (var v3 = 0; v3 < blocks.length; v3++) {
                if (cy <= tops[v3] + LABEL_MARGIN && cy >= bottoms[v3] - LABEL_MARGIN) {
                    lab.frame.translate(0, dys[v3]);
                    break;
                }
            }
        }
    }

    // Importa una página de un PDF a la izquierda de la mesa de trabajo, en "Capa 3".
    // La página es la que indica el nombre del archivo de Illustrator (Pag05.ai ->
    // página 5 del PDF). El PDF (A4) se abre como documento con esa página, se copia
    // como objetos editables y se sustituyen sus fuentes por la Arial del documento:
    // las normales por Arial y las cursivas por Arial Italic (negritas por Arial
    // Bold si existe). Se importa sin diálogos (el de "fuentes que faltan" se evita).
    function importarPdf() {
        var LAYER_NAME = "Capa 3";
        var GAP_PT = 30; // separación entre la mesa de trabajo y la página importada
        var doc = app.activeDocument;

        var m = doc.name.match(/(\d+)(?!.*\d)/);
        if (!m) {
            alert("No se encuentra el número de página en el nombre del archivo (\"" + doc.name + "\").");
            return;
        }
        var pageNumber = parseInt(m[1], 10);

        var layer;
        try {
            layer = doc.layers.getByName(LAYER_NAME);
        } catch (e) {
            alert("No se encuentra la capa \"" + LAYER_NAME + "\" en este documento.");
            return;
        }

        var pdf = File.openDialog("Elige el PDF a importar (página " + pageNumber + ")", function (f) {
            return f instanceof Folder || /\.pdf$/i.test(f.name);
        });
        if (!pdf) return;

        function fontByName(names) {
            for (var i = 0; i < names.length; i++) {
                try { return app.textFonts.getByName(names[i]); } catch (e) {}
            }
            return null;
        }
        var fRegular = fontByName(["ArialMT", "Arial"]);
        var fItalic = fontByName(["Arial-ItalicMT", "Arial-Italic"]);
        var fBold = fontByName(["Arial-BoldMT", "Arial-Bold"]);
        var fBoldItalic = fontByName(["Arial-BoldItalicMT", "Arial-BoldItalic"]);
        if (!fRegular || !fItalic) {
            alert("No se encuentran las fuentes Arial y Arial Italic en este equipo.");
            return;
        }

        var prevLevel = app.userInteractionLevel;
        app.userInteractionLevel = UserInteractionLevel.DONTDISPLAYALERTS;
        var src = null;
        var group = null;
        var pageRect = null;
        try {
            var opts = app.preferences.PDFFileOptions;
            opts.pageToOpen = pageNumber;
            opts.pdfCropToBox = PDFBoxType.PDFMEDIABOX;
            src = app.open(pdf, DocumentColorSpace.RGB);

            // Se copian todos los objetos de la página al documento (duplicar entre
            // documentos no funciona) y se agrupan en "Capa 3".
            pageRect = src.artboards[0].artboardRect; // [left, top, right, bottom] de la página A4
            src.activate();
            src.selectObjectsOnActiveArtboard();
            app.copy();
            doc.activate();
            doc.activeLayer = layer;
            app.executeMenuCommand("pasteInPlace"); // conserva las coordenadas de la página
            var pasted = doc.selection;
            if (pasted && pasted.length > 0) {
                group = layer.groupItems.add();
                for (var pi = pasted.length - 1; pi >= 0; pi--) pasted[pi].move(group, ElementPlacement.PLACEATBEGINNING);
            }
        } finally {
            if (src) { try { src.close(SaveOptions.DONOTSAVECHANGES); } catch (eClose) {} }
            app.userInteractionLevel = prevLevel;
        }
        if (!group) {
            alert("No se pudo importar la página " + pageNumber + " del PDF.");
            return;
        }

        // Fuentes: por el estilo del nombre original de cada cuadro de texto.
        function replaceFonts(items) {
            for (var i = 0; i < items.length; i++) {
                var it = items[i];
                if (it.typename === "GroupItem") {
                    replaceFonts(it.pageItems);
                } else if (it.typename === "TextFrame") {
                    var name = "";
                    try { name = it.textRange.characterAttributes.textFont.name; } catch (e) {}
                    var italic = /ital|obli|cursiva/i.test(name);
                    var bold = /bold|black|heavy|semibold|-bd/i.test(name);
                    var font = fRegular;
                    if (bold && italic && fBoldItalic) font = fBoldItalic;
                    else if (bold && fBold) font = fBold;
                    else if (italic) font = fItalic;
                    try { it.textRange.characterAttributes.textFont = font; } catch (e2) {}
                }
            }
        }
        replaceFonts([group]);

        // A la izquierda de la mesa de trabajo, sin solaparse con ella (se cuenta la
        // página A4 completa, no solo su contenido) y con el borde superior alineado.
        var ab = doc.artboards[doc.artboards.getActiveArtboardIndex()].artboardRect; // [left, top, right, bottom]
        group.translate(ab[0] - GAP_PT - pageRect[2], ab[1] - pageRect[1]);

        doc.selection = null;
        doc.selection = [group];
    }

    function seleccionarAzules() {
        var doc = app.activeDocument;

        var SELECCIONAR_SOLO = true; // true = solo selecciona; false = borra directamente
        var RGB_DIFF_MIN = 35;       // cuánto debe dominar el azul sobre rojo/verde (0-255)
        var CMYK_CYAN_MIN = 35;      // % mínimo de cian
        var CMYK_YELLOW_MAX = 25;    // % máximo de amarillo (el azul tiene poco amarillo)
        var BORDER_TOLERANCE = 2;    // pt de margen para considerar que un trazado es el borde de página

        function isBlueColor(color) {
            if (!color) return false;
            try {
                if (color.typename === "RGBColor") {
                    return (color.blue - color.red >= RGB_DIFF_MIN) &&
                           (color.blue - color.green >= RGB_DIFF_MIN);
                } else if (color.typename === "CMYKColor") {
                    return (color.cyan >= CMYK_CYAN_MIN) && (color.yellow <= CMYK_YELLOW_MAX);
                }
            } catch (e) {}
            return false;
        }

        // Subcabeceras: textos en cursiva centrados (más o menos) respecto al
        // conjunto seleccionado y que no ocupan casi todo su ancho. Ya están
        // traducidas en la capa "cabeceras", así que se seleccionan con los
        // azules. Una nota en cursiva alineada a la izquierda o muy ancha no cuenta.
        var SUBHEADER_CENTER_TOL = 0.10; // fracción del ancho del conjunto
        var SUBHEADER_MAX_WIDTH = 0.60;  // fracción del ancho del conjunto
        function isSubheader(frame, bounds) {
            try {
                var font = frame.textRange.characterAttributes.textFont;
                if (!/italic|oblique|cursiva/i.test(font.name + " " + font.style)) return false;
                var g = frame.geometricBounds;
                var totalW = bounds[2] - bounds[0];
                var center = (g[0] + g[2]) / 2;
                var overallCenter = (bounds[0] + bounds[2]) / 2;
                return Math.abs(center - overallCenter) <= totalW * SUBHEADER_CENTER_TOL &&
                       (g[2] - g[0]) <= totalW * SUBHEADER_MAX_WIDTH;
            } catch (e) {}
            return false;
        }

        function itemIsBlue(it, bounds) {
            try {
                if (it.typename === "PathItem") {
                    if (it.filled && isBlueColor(it.fillColor)) return true;
                    if (it.stroked && isBlueColor(it.strokeColor)) return true;
                } else if (it.typename === "CompoundPathItem") {
                    if (it.pathItems.length > 0) {
                        var p = it.pathItems[0];
                        if (p.filled && isBlueColor(p.fillColor)) return true;
                        if (p.stroked && isBlueColor(p.strokeColor)) return true;
                    }
                } else if (it.typename === "TextFrame") {
                    var attr = it.textRange.characterAttributes;
                    if (isBlueColor(attr.fillColor)) return true;
                    if (isSubheader(it, bounds)) return true;
                }
            } catch (e) {}
            return false;
        }

        function isBorderRect(it, bounds) {
            if (it.typename !== "PathItem" && it.typename !== "CompoundPathItem") return false;
            try {
                var b = it.geometricBounds; // [left, top, right, bottom]
                return Math.abs(b[0] - bounds[0]) <= BORDER_TOLERANCE &&
                       Math.abs(b[1] - bounds[1]) <= BORDER_TOLERANCE &&
                       Math.abs(b[2] - bounds[2]) <= BORDER_TOLERANCE &&
                       Math.abs(b[3] - bounds[3]) <= BORDER_TOLERANCE;
            } catch (e) {
                return false;
            }
        }

        function walk(items, out, bounds) {
            for (var i = 0; i < items.length; i++) {
                var it = items[i];
                if (it.typename === "GroupItem") {
                    walk(it.pageItems, out, bounds);
                } else {
                    if (itemIsBlue(it, bounds) || isBorderRect(it, bounds)) out.push(it);
                }
            }
        }

        var scopeItems;
        var scopeDesc;
        if (doc.selection && doc.selection.length > 0) {
            scopeItems = doc.selection;
            scopeDesc = "la selección actual";
        } else {
            scopeItems = doc.activeLayer.pageItems;
            scopeDesc = "la capa activa (\"" + doc.activeLayer.name + "\")";
        }

        // Los límites de referencia (borde de página y centro de las subcabeceras)
        // se toman de cada objeto de primer nivel de la selección por separado
        // (el grupo del PDF importado), no de todo el conjunto: si hubiera
        // seleccionado además otra cosa (la tabla original, por ejemplo), el
        // centro se desplazaría y dejaría de reconocer las subcabeceras.
        var found = [];
        for (var s = 0; s < scopeItems.length; s++) {
            var gb = scopeItems[s].geometricBounds;
            walk([scopeItems[s]], found, [gb[0], gb[1], gb[2], gb[3]]);
        }

        if (found.length === 0) {
            alert("No se encontraron elementos azules ni el borde de página en " + scopeDesc + ".\nAjusta los umbrales al principio de la función seleccionarAzules() si es necesario.");
            return;
        }

        if (SELECCIONAR_SOLO) {
            doc.selection = null;
            doc.selection = found;
            // Tras pulsar el botón del panel, el foco de teclado se queda en
            // el panel flotante en vez de en la ventana del documento, así que
            // Supr no borraría nada aunque la selección se vea bien. Activar
            // el documento devuelve el foco a su ventana.
            // Los elementos están dentro de grupos: con la herramienta
            // Selección normal Illustrator no deja borrarlos sueltos, con
            // Selección directa sí.
            try { app.selectTool("Adobe Direct Select Tool"); } catch (eTool) {}
            try { doc.activate(); } catch (eAct) {}
        } else {
            for (var k = 0; k < found.length; k++) {
                found[k].remove();
            }
            alert("Borrados " + found.length + " elementos (azules + borde de página) en " + scopeDesc + ".");
        }
    }
})();
