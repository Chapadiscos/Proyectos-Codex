#targetengine "busqueda_inteligente"
// Motor de la app «Búsqueda inteligente» dentro de InDesign: la revisión de la paleta «Buscar con
// Claude» (buscador.jsx) sin la ventana. La app lo ejecuta con
//   do script <este archivo> language javascript with arguments {acción, archivo .json con los datos}
// y recibe un JSON. La revisión en curso vive en $.global.busquedaInteligente (motor persistente)
// mientras InDesign esté abierto. En cada documento, todos los cambios aceptados forman un solo
// paso de deshacer: se deshace el paso anterior y se reaplica todo junto.
// Las cadenas con caracteres no ASCII van con \u: el archivo puede leerse sin saber que es UTF-8.
var ARGV = typeof arguments !== "undefined" ? arguments : [];

(function (accion, rutaDatos) {
    var S = $.global.busquedaInteligente;
    if (!S) S = $.global.busquedaInteligente = {R: [], topes: {}, abiertos: [], cambio: null, fAplicar: null};
    var R = S.R, topes = S.topes;
    var VISTA = "Vista previa de Búsqueda inteligente (no rehacer)";
    var PARRAFO = " ¶ ";

    // ExtendScript no trae JSON: json(v) serializa objetos, arrays, cadenas, números y booleanos.
    function json(v) {
        if (v === null || v === undefined) return "null";
        var t = typeof v;
        if (t === "number") return isFinite(v) ? String(v) : "null";
        if (t === "boolean") return String(v);
        if (t === "string") {
            var s = "";
            for (var n = 0; n < v.length; n++) {
                var c = v.charAt(n), cc = v.charCodeAt(n);
                if (c === '"' || c === "\\") s += "\\" + c;
                else if (cc < 32 || cc === 0x2028 || cc === 0x2029) s += "\\u" + ("0000" + cc.toString(16)).slice(-4);
                else s += c;
            }
            return '"' + s + '"';
        }
        if (v instanceof Array) {
            var a = [];
            for (var i = 0; i < v.length; i++) a.push(json(v[i]));
            return "[" + a.join(",") + "]";
        }
        var p = [];
        for (var k in v) if (v.hasOwnProperty(k)) p.push(json(String(k)) + ":" + json(v[k]));
        return "{" + p.join(",") + "}";
    }
    function leerDatos() {
        if (!rutaDatos) return {};
        var f = File(rutaDatos);
        f.encoding = "UTF-8";
        f.open("r");
        var s = f.read();
        f.close();
        return eval("(" + s + ")");  // JSON escrito por la app
    }

    // --- Utilidades (como en buscador.jsx) ---------------------------------------
    function esTexto(o) {  // texto (no un marco: TextFrame también tiene parentStory e index)
        return o.hasOwnProperty("parentStory") && o.hasOwnProperty("index") && o.hasOwnProperty("length") && !(o instanceof TextFrame);
    }
    function contenedor(t) { return t.parent instanceof Cell ? t.parent : t.parentStory; }
    function largo(cont) { return cont.texts[0].length; }
    function rango(cont, ini, fin) {
        // Pasado por resolve() para obtener un Text con contents de tipo cadena, igual que el que
        // recibe Claude al probar el cambio (itemByRange y .texts[0] lo dan como objeto).
        return fin > ini ? resolve(cont.characters.itemByRange(ini, fin - 1).toSpecifier()) : cont.insertionPoints[ini];
    }
    function textoRango(cont, ini, fin) {
        return fin > ini ? String(cont.characters.itemByRange(ini, fin - 1).contents).replace(/\r/g, PARRAFO) : "";
    }
    // Lo encontrado con n palabras por delante y por detrás, sin pasar de un párrafo a otro.
    function partes(cont, ini, fin, n) {
        var total = largo(cont);
        var delante = textoRango(cont, Math.max(0, ini - 160), ini).match(new RegExp("(?:\\S+\\s+){0," + n + "}\\S*$"))[0];
        var detras = textoRango(cont, fin, Math.min(total, fin + 160)).match(new RegExp("^\\S*(?:\\s+\\S+){0," + n + "}"))[0];
        return {pre: delante.replace(/^[\s\S]* ¶ /, ""), enc: textoRango(cont, ini, fin), post: detras.replace(/ ¶ [\s\S]*$/, "")};
    }
    var TIPOS = {TextFrame: "Marco de texto", Rectangle: "Rectángulo", Oval: "Elipse", Polygon: "Polígono",
                 GraphicLine: "Línea", Group: "Grupo", Image: "Imagen", PDF: "PDF", EPS: "EPS", Button: "Botón"};
    function describir(o) {
        var t = TIPOS[o.constructor.name] || o.constructor.name;
        try { if (o.allGraphics && o.allGraphics.length && o.allGraphics[0].itemLink) t += " con imagen «" + o.allGraphics[0].itemLink.name + "»"; } catch (_) {}
        if (o.hasOwnProperty("contents") && typeof o.contents === "string" && o.contents) t += ": «" + o.contents.slice(0, 120) + "»";
        return t;
    }
    function docDe(o) {
        while (o && o.constructor.name !== "Document" && o.constructor.name !== "Application") o = o.parent;
        return o && o.constructor.name === "Document" ? o : null;
    }
    function caso(k) {
        if (!R[k]) throw new Error("La revisión ya no está en InDesign (¿se ha reiniciado?): vuelve a buscar");
        return R[k];
    }

    // --- Ámbito ---------------------------------------------------------------
    // Opciones según lo que haya seleccionado; la primera es la propuesta por defecto.
    function contextoActual() {
        var c = {opciones: []};
        if (app.documents.length === 0 || app.layoutWindows.length === 0) return c;
        var doc = app.activeDocument, sel = app.selection, s = sel.length === 1 ? sel[0] : null, historia = null;
        c.activo = doc.name;
        if (s && esTexto(s)) {
            if (s.constructor.name !== "InsertionPoint" && s.length > 0) {
                c.opciones.push("seleccion");
                c.selRef = s.toSpecifier();
                var t = String(s.contents).replace(/\r/g, PARRAFO);
                c.seleccion = "«" + (t.length > 60 ? t.slice(0, 60) + "…" : t) + "»";
            } else c.seleccion = "Cursor en un texto";
            historia = s.parentStory;
        } else if (s && s instanceof TextFrame) {
            historia = s.parentStory;
            c.seleccion = "Marco de texto";
        } else if (sel.length) c.seleccion = sel.length === 1 ? (TIPOS[s.constructor.name] || s.constructor.name) : sel.length + " objetos";
        if (historia) { c.opciones.push("articulo"); c.artRef = historia.toSpecifier(); }
        c.opciones.push("documento");
        var conVentana = 0;
        for (var i = 0; i < app.documents.length; i++) if (app.documents[i].windows.length) conVentana++;
        if (conVentana > 1) c.opciones.push("documentos");
        c.firma = c.opciones.join(",") + "|" + (c.selRef || "") + "|" + (c.artRef || "") + "|" + c.activo;
        return c;
    }

    // --- Documentos abiertos por la búsqueda en libro -----------------------------
    // Se abren sin ventana; al cerrar la revisión se cierran los que el usuario no ha mirado
    // (los que tienen cambios se quedan abiertos, con ventana, para que pueda guardarlos).
    function cerrarAbiertos() {
        for (var i = 0; i < S.abiertos.length; i++) {
            var d = S.abiertos[i];
            try {
                if (!d.isValid || d.windows.length) continue;
                if (d.modified) d.windows.add();
                else d.close(SaveOptions.NO);
            } catch (_) {}
        }
        S.abiertos = [];
    }

    // --- Resultados -----------------------------------------------------------
    // Cada resultado: {d: datos de Claude, estado: "" | "hecho" | "omitido" | "error", doc, cdoc,
    //   texto, cont, clave, ini, fin (posición original), delta (cambio de longitud al aplicarlo),
    //   fijo (aplicado en un paso anterior que ya no se puede rehacer), antes}
    function preparar(datos) {
        for (var i = 0; i < datos.resultados.length; i++) {
            var d = datos.resultados[i], o = null, e = {d: d, estado: "", delta: 0};
            try { o = resolve(d.ref); } catch (_) {}
            if (o && o.isValid) {
                e.doc = docDe(o);
                e.cdoc = e.doc ? e.doc.toSpecifier() : "";
            }
            if (o && o.isValid && esTexto(o)) {
                e.texto = true;
                e.cont = contenedor(o);
                e.clave = e.cont.toSpecifier();
                e.ini = o.index;
                e.fin = o.index + o.length;
                e.partes = partes(e.cont, e.ini, e.fin, 4);
            } else if (o && o.isValid) {
                e.obj = o;
                e.antes = d.texto || describir(o);  // para objetos, la descripción de Claude es más clara
            } else {
                e.estado = "error";
                e.error = "No se encuentra en el documento";
            }
            R.push(e);
        }
    }

    // Desplazamiento de un resultado por los cambios ya aplicados antes que él en el mismo texto.
    function desplazamiento(k) {
        var e = R[k], d = 0;
        if (!e.texto) return 0;
        for (var j = 0; j < R.length; j++) {
            var x = R[j];
            if (j !== k && x.estado === "hecho" && !x.pendiente && x.texto && x.clave === e.clave && x.fin <= e.ini) d += x.delta;
        }
        return d;
    }
    function actual(k) {  // {ini, fin, obj} en el documento tal como está ahora
        var e = R[k];
        if (!e.texto) return {obj: e.obj};
        var d = desplazamiento(k), ini = e.ini + d, fin = e.fin + d + (e.estado === "hecho" && !e.pendiente ? e.delta : 0);
        return {ini: ini, fin: fin, obj: rango(e.cont, ini, fin)};
    }

    // Comprueba qué ha pasado con nuestro paso de deshacer en un documento desde la última vez.
    function sincronizar(doc, cdoc) {
        if (topes[cdoc] === undefined) return "nada";
        var n = doc.undoHistory.length, i;
        if (n === topes[cdoc] && doc.undoName === S.cambio.descripcion) return "arriba";
        var deshecho = n === topes[cdoc] - 1 && doc.redoName === S.cambio.descripcion;
        for (i = 0; i < R.length; i++) {
            if (R[i].cdoc !== cdoc || R[i].estado !== "hecho" || R[i].fijo) continue;
            if (deshecho) R[i].estado = "";  // el usuario lo deshizo
            else R[i].fijo = true;           // ha seguido trabajando: lo aplicado se queda en su paso
        }
        delete topes[cdoc];
        return "suelto";
    }

    // Antes de cada acción: si el usuario ha deshecho nuestro paso (Cmd+Z) los resultados vuelven a
    // pendientes; si ha seguido trabajando, lo cambiado se queda fijo en su paso.
    function sincronizarTodos() {
        if (!S.cambio) return;
        var vistos = {};
        for (var i = 0; i < R.length; i++) {
            var e = R[i];
            if (!e.doc || vistos[e.cdoc] || topes[e.cdoc] === undefined) continue;
            vistos[e.cdoc] = true;
            try { if (e.doc.isValid) sincronizar(e.doc, e.cdoc); } catch (_) {}
        }
    }

    // Aplica en un documento todos sus aceptados en un solo paso, sustituyendo el anterior si sigue arriba.
    function aplicarHechos(doc, cdoc) {
        var i;
        if (sincronizar(doc, cdoc) === "arriba") doc.undo();
        var orden = [];
        for (i = 0; i < R.length; i++)
            if (R[i].cdoc === cdoc && R[i].estado === "hecho" && !R[i].fijo) { R[i].pendiente = true; orden.push(i); }
        orden.sort(function (a, b) { return R[a].texto && R[b].texto && R[a].clave === R[b].clave ? R[a].ini - R[b].ini : a - b; });
        if (!orden.length) return;
        app.doScript(function () {
            for (var j = 0; j < orden.length; j++) {
                var e = R[orden[j]], p = actual(orden[j]), antesLargo = e.texto ? largo(e.cont) : 0;
                try {
                    S.fAplicar(p.obj, doc);
                    e.delta = e.texto ? largo(e.cont) - antesLargo : 0;
                } catch (x) { e.estado = "error"; e.error = x.message; e.delta = 0; }
                e.pendiente = false;
            }
        }, ScriptLanguage.JAVASCRIPT, undefined, UndoModes.ENTIRE_SCRIPT, S.cambio.descripcion);
        topes[cdoc] = doc.undoHistory.length;
        if (!doc.windows.length) doc.windows.add();  // capítulo abierto sin ventana: que se vea y se pueda guardar
    }

    // Texto «después» de un resultado sin cambiar: se aplica a prueba y se deshace.
    function vistaPrevia(k, p) {
        var e = R[k], doc = e.doc;
        if (!S.fAplicar || !doc) return "";
        if (e.estado === "hecho") return e.texto ? textoRango(e.cont, p.ini, p.fin) : describir(e.obj);
        if (e.estado === "error") return "";
        var l0 = e.texto ? largo(e.cont) : 0, pasos = doc.undoHistory.length, txt;
        try {
            app.doScript(function () { S.fAplicar(p.obj, doc); }, ScriptLanguage.JAVASCRIPT, undefined,
                         UndoModes.ENTIRE_SCRIPT, VISTA);
            txt = e.texto ? textoRango(e.cont, p.ini, p.fin + largo(e.cont) - l0) : describir(e.obj);
        } catch (x) { txt = "Error al aplicar: " + x.message; }
        if (doc.undoHistory.length > pasos) doc.undo();
        return txt;
    }

    function estados(extra) {
        var r = extra || {}, l = [];
        for (var i = 0; i < R.length; i++) l.push({estado: R[i].estado, error: R[i].error || ""});
        r.estados = l;
        return r;
    }

    // Tras deshacer por script y reaplicar, el Cmd+Z del usuario a veces no se redibuja: un oyente
    // en Edición > Deshacer/Rehacer fuerza el redibujado (como oyente_deshacer.jsx; mismo nombre,
    // para no duplicarlo si también está la paleta).
    function instalarOyenteDeshacer() {
        var NOMBRE = "claude_redibujar", ids = [265, 266];  // Deshacer, Rehacer
        for (var i = 0; i < ids.length; i++) {
            var m = app.menuActions.itemByID(ids[i]);
            if (!m.isValid) continue;
            var ya = false;
            for (var j = 0; j < m.eventListeners.length; j++) if (m.eventListeners[j].name === NOMBRE) ya = true;
            if (ya) continue;
            m.addEventListener("afterInvoke", function () {
                try { var w = app.activeWindow; w.zoomPercentage = w.zoomPercentage; } catch (_) {}
            }).name = NOMBRE;
        }
    }

    // Cancelar: deshace en cada documento nuestro paso de deshacer, si sigue siendo el último.
    function deshacerTodo() {
        var docs = {}, i, c, quedan = 0;
        for (i = 0; i < R.length; i++) if (R[i].estado === "hecho" && R[i].doc) docs[R[i].cdoc] = R[i].doc;
        for (c in docs) if (docs.hasOwnProperty(c) && sincronizar(docs[c], c) === "arriba") { docs[c].undo(); delete topes[c]; }
        for (i = 0; i < R.length; i++) if (R[i].estado === "hecho" && R[i].fijo) quedan++;
        return quedan;  // cambios que no se pudieron deshacer porque el usuario siguió trabajando
    }
    // La selección que deja la app tras cambiar (el texto ha cambiado de longitud) tampoco es del usuario
    function anotarSeleccion() {
        try { S.firmaPropia = contextoActual().firma; } catch (_) {}
    }
    function cerrar() {
        cerrarAbiertos();
        S.R = R = [];
        S.topes = topes = {};
        S.cambio = null;
        S.fAplicar = null;
    }

    // --- Acciones ---------------------------------------------------------------
    var A = {};

    // Qué hay abierto en InDesign y qué ámbitos tienen sentido con la selección actual.
    A.contexto = function () {
        var r = contextoActual(), i;
        r.version = app.version;
        r.documentos = [];
        for (i = 0; i < app.documents.length; i++) {
            var d = app.documents[i];
            r.documentos.push({nombre: d.name, ventana: d.windows.length > 0, modificado: d.modified});
        }
        r.libros = [];
        for (i = 0; i < app.books.length; i++) r.libros.push({nombre: app.books[i].name, ruta: app.books[i].fullName.fsName});
        r.propia = !!r.firma && r.firma === S.firmaPropia;  // lo seleccionado lo puso la app al mostrar un resultado
        return r;
    };

    // Abre los capítulos de un libro que no estén abiertos, sin ventana.
    A.abrirLibro = function (d) {
        var interaccion = app.scriptPreferences.userInteractionLevel, libro, nombres = [], faltan = [];
        app.scriptPreferences.userInteractionLevel = UserInteractionLevels.NEVER_INTERACT;  // sin avisos de fuentes o vínculos
        try {
            for (var b = 0; b < app.books.length && !libro; b++)  // si ya está abierto, volver a abrirlo falla
                if (app.books[b].fullName.fsName === File(d.ruta).fsName) libro = app.books[b];
            if (!libro) libro = app.open(File(d.ruta));
            for (var i = 0; i < libro.bookContents.length; i++) {
                var cap = libro.bookContents[i], f = File(cap.fullName), doc = null;
                if (!f.exists) { faltan.push(cap.name); continue; }
                for (var j = 0; j < app.documents.length; j++)
                    try { if (app.documents[j].fullName.fsName === f.fsName) doc = app.documents[j]; } catch (_) {}  // sin guardar: sin ruta
                if (!doc) { doc = app.open(f, false); S.abiertos.push(doc); }
                nombres.push(doc.name);
            }
        } finally { app.scriptPreferences.userInteractionLevel = interaccion; }
        return {libro: libro.name, documentos: nombres, faltan: faltan};
    };

    // Recibe {resultados, cambio} de Claude y prepara la revisión.
    A.cargar = function (d) {
        S.R = R = [];
        S.topes = topes = {};
        S.cambio = d.cambio && /\S/.test(d.cambio.aplicar || "") ? d.cambio : null;
        S.fAplicar = null;
        var aviso = "";
        if (S.cambio) {
            try { S.fAplicar = new Function("obj", "doc", S.cambio.aplicar); }
            catch (x) { aviso = "El cambio propuesto tiene un error: " + x.message; S.cambio = null; }
        }
        preparar(d);
        if (S.cambio) instalarOyenteDeshacer();
        var items = [];
        for (var i = 0; i < R.length; i++) {
            var e = R[i], p = e.partes || {};
            items.push({documento: e.d.documento || "", pagina: e.d.pagina || "", pre: p.pre || "", enc: p.enc || "",
                        post: p.post || "", desc: e.texto ? "" : (e.antes || e.d.texto || ""), propuesta: e.d.propuesta || "",
                        dudoso: !!e.d.dudoso, motivo: e.d.motivo || ""});
        }
        return estados({items: items, hayCambio: !!S.cambio, aviso: aviso});
    };

    // Selecciona un resultado en InDesign y devuelve su antes y después.
    A.mostrar = function (d) {
        sincronizarTodos();
        var e = caso(d.k), r = {};
        if (e.estado === "error" || !e.doc || !e.doc.isValid) return estados({error: e.error || "No se encuentra en el documento"});
        var p = actual(d.k);
        if (e.texto) {
            var pp = partes(e.cont, p.ini, p.fin, 8);
            r.pre = pp.pre;
            r.post = pp.post;
            r.antes = e.estado === "hecho" ? e.partes.enc : pp.enc;  // ya cambiado: el texto original
        } else r.antes = e.antes;
        r.despues = vistaPrevia(d.k, p);
        try {
            if (!e.doc.windows.length) e.doc.windows.add();  // capítulo abierto sin ventana
            app.activeDocument = e.doc;
            app.select(p.obj);
            if (p.obj.hasOwnProperty("showText")) p.obj.showText();
            else if (p.obj.parentPage) app.activeWindow.activePage = p.obj.parentPage;
            S.firmaPropia = contextoActual().firma;  // selección hecha por la app: no cambia el ámbito
        } catch (x) { r.aviso = "No se puede mostrar: " + x.message; }
        return estados(r);
    };

    A.cambiar = function (d) {
        sincronizarTodos();
        var e = caso(d.k);
        if (e.estado !== "") return estados();
        e.estado = "hecho";
        aplicarHechos(e.doc, e.cdoc);
        anotarSeleccion();
        return estados();
    };

    A.omitir = function (d) {
        sincronizarTodos();
        var e = caso(d.k);
        if (e.estado === "") e.estado = "omitido";
        return estados();
    };

    A.cambiarTodo = function () {
        sincronizarTodos();
        var docs = {}, n = 0, i;
        for (i = 0; i < R.length; i++)
            if (R[i].estado === "" && !R[i].d.dudoso && R[i].doc) { R[i].estado = "hecho"; docs[R[i].cdoc] = R[i].doc; n++; }
        if (!n) return estados({mensaje: "Solo quedan casos dudosos: cámbialos uno a uno"});
        for (var c in docs) if (docs.hasOwnProperty(c)) aplicarHechos(docs[c], c);
        anotarSeleccion();
        return estados({mensaje: n + " cambios hechos"});
    };

    A.cancelar = function () {
        var quedan = deshacerTodo();
        cerrar();
        anotarSeleccion();
        return {mensaje: quedan ? "Cancelado. " + quedan + " cambios no se pudieron deshacer porque has seguido trabajando: usa Cmd+Z"
                                : "Cancelado: no se ha realizado ningún cambio"};
    };

    // Termina la revisión: los cambios hechos se quedan (Cmd+Z en InDesign para deshacerlos).
    A.cerrar = function () {
        var h = 0;
        for (var i = 0; i < R.length; i++) if (R[i].estado === "hecho") h++;
        cerrar();
        return {hechos: h, mensaje: h ? "Terminado: " + h + " cambios hechos (Cmd+Z en InDesign para deshacerlos)" : "Terminado sin cambios"};
    };

    if (!A[accion]) return json({error: "Acción desconocida: " + accion});
    if (accion !== "contexto" && accion !== "cerrar" && app.documents.length === 0 && accion !== "abrirLibro")
        return json({error: "No hay ningún documento abierto en InDesign"});
    try { return json(A[accion](leerDatos())); }
    catch (e) { return json({error: (e.message || String(e)) + (e.line ? " (línea " + e.line + ")" : "")}); }
})(ARGV[0], ARGV[1]);
