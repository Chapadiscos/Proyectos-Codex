// Fase 2: monta un capítulo en una copia de la maqueta base a partir del manifiesto que
// prepara importar.py. Se llama con la ruta del manifiesto como argumento.
//
// Es una galerada: la portadilla y la maquetación fina se hacen a mano.
// - Texto: se coloca historia.icml (título y autores al principio) y se añaden páginas
//   con la maestra de interior hasta que no sobre texto.
// - Figuras, tablas e imágenes sin pie: en la mesa de trabajo, junto a la página donde se
//   citan por primera vez. Sus avisos, con la condición «Duda figura».

#target indesign

var ACCION_PIE_ESTATICO = 132651;   // Objeto > Pie de ilustración > Generar pie de ilustración estático
function accionPie() {
    var a = app.menuActions.itemByID(ACCION_PIE_ESTATICO);
    if (a.isValid) return a;
    var nombres = ["Generar pie de ilustración estático", "Generate Static Caption"];
    for (var i = 0; i < nombres.length; i++) { a = app.menuActions.itemByName(nombres[i]); if (a.isValid) return a; }
    return null;
}
var MANIFIESTO = (typeof arguments != "undefined" && arguments.length) ? arguments[0] : "";

function leerJSON(ruta) {
    var f = File(ruta);
    f.encoding = "UTF-8";
    f.open("r");
    var t = f.read();
    f.close();
    return eval("(" + t + ")");
}

// Colocar un ICML deja el artículo vinculado a InCopy y bloqueado: se desvincula para
// que sea texto normal de InDesign (editable y visible para Buscar/Cambiar).
function colocarICML(marco, ruta) {
    marco.place(File(ruta));
    var st = marco.parentStory;
    try { if (st.itemLink && st.itemLink.isValid) st.itemLink.unlink(); } catch (e) {}
    return st;
}

// Duda en una pieza de la mesa de trabajo: texto condicional y, si se pide, nota.
function marcarDuda(d, texto, motivo, nombre, conNota) {
    var c = d.conditions.itemByName(nombre);
    if (!c.isValid) c = d.conditions.add({ name: nombre, indicatorMethod: ConditionIndicatorMethod.USE_HIGHLIGHT, indicatorColor: UIColors.GREEN });
    try { texto.texts[0].appliedConditions = [c]; } catch (e) {}
    if (conNota) {
        try { texto.insertionPoints[0].notes.add().texts[0].contents = motivo; } catch (e) {}
    }
}

// Primer marco de la historia más larga de una página (el de las columnas).
function primerMarco(pagina) {
    var mejor = null;
    for (var i = 0; i < pagina.textFrames.length; i++) {
        var f = pagina.textFrames[i];
        if (!f.previousTextFrame && (f.nextTextFrame || !mejor)) mejor = f;
    }
    return mejor;
}

function importar(m) {
    app.scriptPreferences.measurementUnit = MeasurementUnits.MILLIMETERS;
    var destino = File(m.destino);
    for (var i = 0; i < app.documents.length; i++) {
        if (app.documents[i].saved && app.documents[i].fullName.fsName == destino.fsName)
            return "ERROR: " + destino.name + " está abierto en InDesign. Ciérralo y vuelve a lanzar la importación.";
    }
    if (destino.exists) destino.remove();
    if (!File(m.maqueta).copy(destino)) return "ERROR: no se pudo copiar la maqueta a " + destino.fsName;

    // Visible desde el principio: los pies de ilustración nativos se generan con una orden
    // de menú, que necesita el documento activo y el marco seleccionado.
    var d = app.open(destino, true);
    var res = [];
    try {
        d.viewPreferences.horizontalMeasurementUnits = MeasurementUnits.MILLIMETERS;
        d.viewPreferences.verticalMeasurementUnits = MeasurementUnits.MILLIMETERS;

        // ---- número de capítulo ------------------------------------------------
        // Galerada: la portadilla se monta a mano desde la Biblioteca de la publicación.
        // Solo se pone el número (marcador de sección) para que la cornisa diga «Capítulo N».
        // Las páginas no se numeran aquí: numeración automática, la pone el libro.
        if (m.capitulo.numero) d.sections[0].marker = m.capitulo.numero;
        d.sections[0].continueNumbering = true;
        var p1 = d.pages[0];

        // ---- texto -------------------------------------------------------------
        var plantilla = [];          // columnas de la página de interior, relativas a la página
        var pInt = d.pages[1], bi = pInt.bounds;
        var cols = [];
        for (var i = 0; i < pInt.textFrames.length; i++) cols.push(pInt.textFrames[i]);
        cols.sort(function (a, b) { return a.geometricBounds[1] - b.geometricBounds[1]; });
        for (var i = 0; i < cols.length; i++) {
            var g = cols[i].geometricBounds;
            plantilla.push([g[0] - bi[0], g[1] - bi[1], g[2] - bi[0], g[3] - bi[1]]);
        }
        var maestra = pInt.appliedMaster;

        var primero = primerMarco(p1);
        var historia = colocarICML(primero, m.historia);
        var ultimo = historia.textContainers[historia.textContainers.length - 1];
        var vueltas = 0;
        while (ultimo.overflows && vueltas < 300) {
            var np = d.pages.add(LocationOptions.AT_END, { appliedMaster: maestra });
            var bn = np.bounds;
            for (var c = 0; c < plantilla.length; c++) {
                var t = plantilla[c];
                var nf = np.textFrames.add({ geometricBounds: [bn[0] + t[0], bn[1] + t[1], bn[0] + t[2], bn[1] + t[3]] });
                ultimo.nextTextFrame = nf;
                ultimo = nf;
            }
            vueltas++;
        }
        // Páginas sobrantes al final (si el texto ocupa menos que la maqueta).
        for (var i = d.pages.length - 1; i > 1; i--) {
            var pg = d.pages[i], usada = false;
            for (var j = 0; j < pg.textFrames.length; j++) if (pg.textFrames[j].characters.length) usada = true;
            if (usada) break;
            pg.remove();
        }
        res.push("Páginas: " + d.pages.length + (ultimo.overflows ? " (¡sigue sobrando texto!)" : ""));

        // ---- mesa de trabajo ---------------------------------------------------
        // Las piezas van en dos columnas junto a la página: la mesa solo se ensancha lo justo
        // para ellas (o para una tabla, que ocupa las dos); su altura no se toca.
        var SEP = 10, MARGEN = 15, anchoCol = m.figura.ancho;
        var mesa = d.pasteboardPreferences.pasteboardMargins;
        d.pasteboardPreferences.pasteboardMargins = [Math.max(mesa[0], MARGEN + Math.max(2 * anchoCol + SEP, m.tabla.ancho) + 25), mesa[1]];
        var huecos = {};             // altura ya ocupada en la mesa de cada página

        function paginaDeCita(regex) {
            app.findGrepPreferences = NothingEnum.NOTHING;
            app.findGrepPreferences.findWhat = regex;
            var r = historia.findGrep();
            app.findGrepPreferences = NothingEnum.NOTHING;
            for (var i = 0; i < r.length; i++) {
                try { var pf = r[i].parentTextFrames[0]; if (pf && pf.parentPage) return pf.parentPage; } catch (e) {}
            }
            return d.pages[d.pages.length - 1];
        }
        // Las piezas van en dos columnas junto a la página donde se citan (la columna 0 es la
        // más cercana a la página); una pieza más ancha que una columna ocupa las dos. Si ya
        // no cabe en la mesa de esa página, pasa a la otra página del pliego y después a las
        // siguientes: la mesa no se alarga.
        function columnas(pagina) {
            if (!huecos[pagina.id]) huecos[pagina.id] = [pagina.bounds[0], pagina.bounds[0]];
            return huecos[pagina.id];
        }
        function sitio(pagina, ancho, alto) {
            var b = pagina.bounds, izq = pagina.side == PageSideOptions.LEFT_HAND;
            var col = columnas(pagina), doble = ancho > anchoCol, k, y;
            if (doble) { k = 0; y = Math.max(col[0], col[1]); }
            else { k = col[1] < col[0] ? 1 : 0; y = col[k]; }
            if (y + alto > b[2] + mesa[1]) return null;
            var x = izq ? b[1] - MARGEN - (doble ? ancho : anchoCol) - k * (anchoCol + SEP)
                        : b[3] + MARGEN + k * (anchoCol + SEP);
            return { y: y, x: x, pagina: pagina, cols: doble ? [0, 1] : [k] };
        }
        function candidatas(pagina) {
            var lista = [pagina], pl = pagina.parent.pages;
            for (var i = 0; i < pl.length; i++) if (pl[i].id != pagina.id) lista.push(pl[i]);
            for (var i = pagina.documentOffset + 1; i < d.pages.length; i++) if (d.pages[i].parent.id != pagina.parent.id) lista.push(d.pages[i]);
            for (var i = pagina.documentOffset - 1; i >= 0; i--) if (d.pages[i].parent.id != pagina.parent.id) lista.push(d.pages[i]);
            return lista;
        }
        // Lleva la pieza ya montada al primer sitio libre donde quepa entera.
        function acomodar(pieza, pagina, ancho) {
            var gb = pieza.geometricBounds, alto = gb[2] - gb[0], lista = candidatas(pagina), h = null;
            for (var i = 0; i < lista.length && !h; i++) h = sitio(lista[i], ancho, alto);
            if (!h) h = sitio(pagina, ancho, 0);          // no cabe en ninguna: donde se cita
            if (h.pagina.parent.id != pieza.parent.id) pieza.move(h.pagina.parent);
            pieza.move([h.x, h.y]);
            for (var i = 0; i < h.cols.length; i++) columnas(h.pagina)[h.cols[i]] = h.y + alto + 8;
        }
        // Posición provisional para montar una pieza antes de acomodarla.
        function provisional(pagina) { var b = pagina.bounds; return { x: b[3] + MARGEN, y: b[0] }; }

        // Imágenes de una figura en una fila de «ancho» mm: cada una ocupa su parte, todas a
        // la misma altura (recortadas en proporción si hace falta) y separadas por un filete
        // blanco. La altura sale de la proporción real de la imagen, sin ajustes automáticos
        // (el estilo de objeto rellena el marco y FRAME_TO_CONTENT lo hacía crecer hacia arriba).
        function colocarImagenes(pliego, x0, y, ancho, archivos, avisos) {
            var n = archivos.length, w = ancho / n, rects = [], ratios = [];
            for (var i = 0; i < n; i++) {
                var caja = [y, x0 + i * w, y + w * 0.75, x0 + (i + 1) * w];
                var r = pliego.rectangles.add({ geometricBounds: caja });
                try { r.appliedObjectStyle = d.objectStyles.itemByName(m.figura.estilo_objeto); } catch (e) {}
                try { r.frameFittingOptions.autoFit = false; } catch (e) {}
                r.geometricBounds = caja;
                var ratio = 0.75;
                try {
                    var g = r.place(File(archivos[i]))[0];
                    var gb = g.geometricBounds;
                    ratio = (gb[2] - gb[0]) / (gb[3] - gb[1]);
                } catch (e) { avisos.push("No se pudo colocar " + File(archivos[i]).name + ": " + e); }
                rects.push(r);
                ratios.push(ratio);
            }
            var h = w * Math.min.apply(null, ratios);
            for (var i = 0; i < n; i++) {
                rects[i].geometricBounds = [y, x0 + i * w, y + h, x0 + (i + 1) * w];
                try {
                    rects[i].fit(n > 1 ? FitOptions.FILL_PROPORTIONALLY : FitOptions.PROPORTIONALLY);
                    rects[i].fit(FitOptions.CENTER_CONTENT);
                } catch (e) {}
            }
            var objetos = rects.slice(0);
            for (var i = 1; i < n; i++) {
                var l = pliego.graphicLines.add({ geometricBounds: [y, x0 + i * w, y + h, x0 + i * w] });
                l.strokeWeight = m.figura.filete + "pt";
                try { l.strokeColor = d.swatches.itemByName("Paper"); } catch (e) {}
                objetos.push(l);
            }
            return { objetos: objetos, alto: h };
        }
        // Pie de ilustración nativo (Objeto > Pie de ilustración > Generar pie de ilustración
        // estático): lo coloca según la configuración de pie de ilustración de la maqueta (pegado
        // bajo la imagen, estilo Pie Figura) y lo agrupa con ella. Devuelve el marco del pie.
        function pieNativo(marco) {
            app.select(marco);
            try { accionPie().invoke(); } catch (e) {}
            app.select(NothingEnum.NOTHING);
            if (marco.parent.constructor.name == "Group" && marco.parent.textFrames.length)
                return marco.parent.textFrames[0];
            // Si InDesign no lo genera, un marco pegado bajo la imagen.
            var b = marco.geometricBounds;
            return marco.parent.textFrames.add({ geometricBounds: [b[2], b[1], b[2] + 10, b[3]] });
        }
        // Figura: imágenes + pie nativo, todo en un grupo. En las compuestas el pie se genera
        // con la primera imagen (todas tienen la misma altura) y se ensancha a toda la figura.
        function colocarFigura(pagina, archivos, pieICML, textoPie, avisos) {
            var ancho = m.figura.ancho, h = provisional(pagina), pliego = pagina.parent;
            var im = colocarImagenes(pliego, h.x, h.y, ancho, archivos, avisos);
            var tf = pieNativo(im.objetos[0]);
            var tb = tf.geometricBounds;
            if (tf.parent.constructor.name == "Group") tf.parent.ungroup();
            tf.geometricBounds = [tb[0], h.x, tb[2], h.x + ancho];
            tf.contents = "";
            if (pieICML) colocarICML(tf, pieICML);
            else tf.contents = textoPie;
            try {
                tf.textFramePreferences.autoSizingReferencePoint = AutoSizingReferenceEnum.TOP_CENTER_POINT;
                tf.textFramePreferences.autoSizingType = AutoSizingTypeEnum.HEIGHT_ONLY;
            } catch (e) {}
            if (avisos.length) marcarDuda(d, tf.parentStory, avisos.join(" · "), m.condicion_figuras, m.notas);
            tf.recompose();
            var grupo = pliego.groups.add(im.objetos.concat([tf]));
            acomodar(grupo, pagina, ancho);
        }
        // Tabla (o pie suelto): marco de texto que crece hasta que no sobre texto.
        function colocarTabla(pagina, tablaICML, avisos, anchoMarco) {
            var ancho = anchoMarco || m.tabla.ancho, h = provisional(pagina);
            var tf = pagina.parent.textFrames.add({ geometricBounds: [h.y, h.x, h.y + 20, h.x + ancho] });
            colocarICML(tf, tablaICML);
            var tablas = tf.parentStory.tables;
            for (var k = 0; k < tablas.length; k++) {
                var tbl = tablas[k];
                try { tbl.appliedTableStyle = d.tableStyles.itemByName(m.tabla.estilo); } catch (e) {}
                try { tbl.rows[0].rowType = RowTypes.HEADER_ROW; } catch (e) {}
                for (var c = 0; c < tbl.cells.length; c++) {
                    var celda = tbl.cells[c];
                    var tipo = celda.parentRow.rowType;
                    var est = tipo == RowTypes.HEADER_ROW ? m.tabla.celda_cabecera : tipo == RowTypes.FOOTER_ROW ? m.tabla.celda_pie : m.tabla.celda;
                    try { celda.appliedCellStyle = d.cellStyles.itemByName(est); } catch (e) {}
                }
            }
            var gt = tf.geometricBounds, altoT = 20;
            while (tf.overflows && altoT < 600) { altoT += 10; tf.geometricBounds = [gt[0], gt[1], gt[0] + altoT, gt[3]]; }
            if (tf.overflows) avisos.push("La tabla no cabe en el marco");
            if (avisos.length) marcarDuda(d, tf.parentStory, avisos.join(" · "), m.condicion_figuras, m.notas);
            acomodar(tf, pagina, ancho);
        }

        for (var i = 0; i < m.figuras.length; i++) {
            var fg = m.figuras[i];
            var pag = paginaDeCita("(?i)\\bfig(?:ura|s)?\\.?\\s*" + fg.buscar + "(?!\\d)");
            if (fg.archivos.length) colocarFigura(pag, fg.archivos, fg.pie, "", fg.avisos.slice(0));
            else colocarTabla(pag, fg.pie, fg.avisos.slice(0), m.figura.ancho);   // pie solo, sin imagen
        }
        for (var i = 0; i < m.tablas.length; i++) {
            var tb = m.tablas[i];
            var pag = tb.buscar ? paginaDeCita("(?i)\\btabla\\s+" + tb.buscar + "(?!\\d)") : d.pages[d.pages.length - 1];
            colocarTabla(pag, tb.icml, tb.avisos.slice(0));
        }
        for (var i = 0; i < m.sueltas.length; i++) {
            var su = m.sueltas[i], pag = d.pages[d.pages.length - 1];
            if (su.buscar_texto) {
                app.findTextPreferences = NothingEnum.NOTHING;
                app.findTextPreferences.findWhat = su.buscar_texto.substr(0, 30);
                var r = historia.findText();
                app.findTextPreferences = NothingEnum.NOTHING;
                if (r.length && r[0].parentTextFrames.length) pag = r[0].parentTextFrames[0].parentPage;
            }
            colocarFigura(pag, [su.archivos[0]], "", "Imagen sin pie", su.avisos.slice(0));
        }
        res.push("Figuras: " + m.figuras.length + " · Tablas: " + m.tablas.length + " · Imágenes sin pie: " + m.sueltas.length);

        // El ICML no admite espacios en los nombres de condición: «Duda-estilo» → «Duda estilo».
        for (var i = 0; i < d.conditions.length; i++) {
            var cr = d.conditions[i];
            if (cr.name.indexOf("Duda-") == 0) try { cr.name = cr.name.replace("Duda-", "Duda "); } catch (e) {}
        }
        var dudas = [];
        for (var i = 0; i < d.conditions.length; i++) {
            var cn = d.conditions[i];
            if (cn.name.indexOf("Duda") != 0) continue;
            app.findTextPreferences = NothingEnum.NOTHING;
            app.findTextPreferences.appliedConditions = [cn];
            var nd = d.findText().length;
            app.findTextPreferences = NothingEnum.NOTHING;
            if (nd) dudas.push(cn.name.replace("Duda ", "") + " " + nd);
        }
        res.push("Dudas marcadas: " + (dudas.length ? dudas.join(" · ") : "ninguna"));
        try { d.conditionalTextPreferences.showConditionIndicators = ConditionIndicatorMode.SHOW_INDICATORS; } catch (e) {}
        d.save(destino);
    } catch (e) {
        res.push("ERROR: " + e + " (línea " + e.line + ")");
        try { d.close(SaveOptions.NO); } catch (e2) {}
    }
    return res.join("\n");
}

app.scriptPreferences.userInteractionLevel = UserInteractionLevels.NEVER_INTERACT;
var salida;
try {
    salida = MANIFIESTO ? importar(leerJSON(MANIFIESTO)) : "ERROR: falta la ruta del manifiesto";
} finally {
    app.scriptPreferences.userInteractionLevel = UserInteractionLevels.INTERACT_WITH_ALL;
    app.scriptPreferences.measurementUnit = AutoEnum.AUTO_VALUE;
}
salida;
