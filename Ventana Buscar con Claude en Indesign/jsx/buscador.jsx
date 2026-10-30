// Ventana «Buscar con Claude», parecida a Buscar/Cambiar. El usuario describe qué buscar o
// cambiar y dónde (selección, artículo, documento, todos los documentos o un libro);
// buscar.py lo resuelve con Claude Code en segundo plano y aquí se revisan los resultados:
// antes y después de cada uno, Cambiar / Omitir / Cambiar todo, y los casos dudosos aparte.
// Los cambios se ven al momento y, en cada documento, todos los aceptados forman un solo paso
// de deshacer (se deshace el paso anterior y se reaplica todo junto).
// Se carga en el motor persistente "indesign_mcp" (menú Ventana o panel Scripts), que define
// INDESIGN_MCP (carpeta del proyecto).
$.evalFile(File(INDESIGN_MCP + "/jsx/comun.jsx"));

(function () {
    var B = $.global.buscadorClaude;
    if (B && B.ventana) { B.ventana.show(); B.ventana.active = true; return; }  // estaba oculta
    B = $.global.buscadorClaude = {};

    var CARPETA = Folder(Folder.temp + "/indesign_mcp");
    CARPETA.create();
    var PYTHON = INDESIGN_MCP + "/.venv/bin/python", BUSCAR = INDESIGN_MCP + "/buscar.py";
    var VISTA = "Vista previa de Claude (no rehacer)";
    var AMBITOS = {seleccion: "Selección", articulo: "Artículo", documento: "Documento", documentos: "Todos los documentos"};

    // --- Ventana ------------------------------------------------------------
    var w = B.ventana = new Window("palette", "Buscar con Claude");
    w.alignChildren = "fill";
    var pBuscar = w.add("panel", undefined, "Qué buscar o cambiar");
    pBuscar.alignChildren = "fill";
    var desc = pBuscar.add("edittext", [0, 0, 520, 46], "", {multiline: true});
    var fila = pBuscar.add("group");
    fila.add("statictext", undefined, "Buscar en:");
    var ambito = fila.add("dropdownlist", undefined, []);
    ambito.preferredSize.width = 150;
    var bBuscar = fila.add("button", undefined, "Buscar");
    var bLibro = fila.add("button", undefined, "Buscar en libro…");
    var bCancelar = fila.add("button", undefined, "Detener");
    bCancelar.helpTip = "Detiene la búsqueda en curso.";
    bCancelar.enabled = false;
    var bNueva = fila.add("button", undefined, "Nueva búsqueda");
    bNueva.helpTip = "Borra la descripción y los resultados para empezar otra búsqueda. Los cambios ya hechos se conservan.";
    var estado = pBuscar.add("statictext", undefined, "");

    var resumen = w.add("statictext", [0, 0, 540, 34], "", {multiline: true});
    var lista = w.add("listbox", [0, 0, 540, 190], [], {
        numberOfColumns: 5, showHeaders: true, columnTitles: ["", "Documento", "Pág.", "Resultado", "Cambio"],
        columnWidths: [22, 100, 36, 270, 106]
    });
    var gAD = w.add("group");
    gAD.alignChildren = "fill";
    var pAntes = gAD.add("panel", undefined, "Antes");
    var antes = pAntes.add("edittext", [0, 0, 246, 66], "", {multiline: true, readonly: true});
    var pDespues = gAD.add("panel", undefined, "Después");
    var despues = pDespues.add("edittext", [0, 0, 246, 66], "", {multiline: true, readonly: true});
    var filaB = w.add("group");
    var bCambiar = filaB.add("button", undefined, "Cambiar");
    var bOmitir = filaB.add("button", undefined, "Omitir");
    bOmitir.helpTip = "No se realizará el cambio.";
    var bTodo = filaB.add("button", undefined, "Cambiar todo");
    bTodo.helpTip = "Se realizarán todos los cambios excepto los omitidos previamente. Los casos dudosos tampoco se cambian: hazlo uno a uno con Cambiar.";
    var bDeshacer = filaB.add("button", undefined, "Cancelar");
    bDeshacer.helpTip = "No se realizará ningún cambio: se deshacen los cambios de esta revisión y el documento queda como estaba.";
    var bTerminar = filaB.add("button", undefined, "Terminar");
    bTerminar.helpTip = "Termina la revisión y conserva los cambios hechos hasta ahora.";
    var nota = w.add("statictext", undefined, "");
    var pDudosos = w.add("panel", undefined, "Casos dudosos");
    pDudosos.alignChildren = "fill";
    var dudosos = pDudosos.add("listbox", [0, 0, 520, 70], [], {numberOfColumns: 2, columnWidths: [130, 380]});

    // --- Utilidades -----------------------------------------------------------
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
    function contexto(cont, ini, fin) {
        var total = largo(cont), a = Math.max(0, ini - 50), b = Math.min(total, fin + 50);
        function trozo(x, y) { return y > x ? cont.characters.itemByRange(x, y - 1).contents : ""; }
        return ((a > 0 ? "…" : "") + trozo(a, ini) + "⟦" + trozo(ini, fin) + "⟧" + trozo(fin, b) +
                (b < total ? "…" : "")).replace(/\r/g, " ¶ ");
    }
    function textoRango(cont, ini, fin) {
        return fin > ini ? String(cont.characters.itemByRange(ini, fin - 1).contents).replace(/\r/g, " ¶ ") : "";
    }
    // Para la lista: lo encontrado con n palabras por delante y por detrás.
    function contextoPalabras(cont, ini, fin, n) {
        var total = largo(cont);
        var delante = textoRango(cont, Math.max(0, ini - 120), ini).match(new RegExp("(?:\\S+\\s+){0," + n + "}\\S*$"))[0];
        var detras = textoRango(cont, fin, Math.min(total, fin + 120)).match(new RegExp("^\\S*(?:\\s+\\S+){0," + n + "}"))[0];
        // sin pasar de un párrafo a otro
        return delante.replace(/^[\s\S]* ¶ /, "") + textoRango(cont, ini, fin) + detras.replace(/ ¶ [\s\S]*$/, "");
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
    function corto(nombre) { return String(nombre).replace(/\.indd$/i, ""); }

    // --- Ámbito ---------------------------------------------------------------
    // Opciones según lo que haya seleccionado; la primera es la propuesta por defecto.
    function contextoActual() {
        var c = {opciones: []};
        if (app.documents.length === 0 || app.layoutWindows.length === 0) return c;
        var doc = app.activeDocument, sel = app.selection, s = sel.length === 1 ? sel[0] : null, historia = null;
        c.doc = doc.name;
        if (s && esTexto(s)) {
            if (s.constructor.name !== "InsertionPoint" && s.length > 0) { c.opciones.push("seleccion"); c.selRef = s.toSpecifier(); }
            historia = s.parentStory;
        } else if (s && s instanceof TextFrame) historia = s.parentStory;
        if (historia) { c.opciones.push("articulo"); c.artRef = historia.toSpecifier(); }
        c.opciones.push("documento");
        if (documentosConVentana().length > 1) c.opciones.push("documentos");
        c.firma = c.opciones.join(",") + "|" + (c.selRef || "") + "|" + (c.artRef || "") + "|" + c.doc;
        return c;
    }
    function documentosConVentana() {
        var r = [];
        for (var i = 0; i < app.documents.length; i++) if (app.documents[i].windows.length) r.push(app.documents[i].name);
        return r;
    }
    var claves = [];
    function actualizarAmbito() {
        var c = contextoActual();
        if (c.firma === B.firma) return;
        B.firma = c.firma;
        ambito.removeAll();
        claves = c.opciones;
        for (var i = 0; i < claves.length; i++) ambito.add("item", AMBITOS[claves[i]]);
        if (claves.length) ambito.selection = 0;
    }
    w.onActivate = function () { try { actualizarAmbito(); } catch (_) {} };
    // InDesign avisa de cada cambio de selección; así el ámbito se actualiza sin tocar la ventana.
    var OYENTE_SEL = "claude_buscador_seleccion";
    function quitarOyenteSeleccion() {
        for (var i = app.eventListeners.length - 1; i >= 0; i--)
            if (app.eventListeners[i].name === OYENTE_SEL) app.eventListeners[i].remove();
    }
    quitarOyenteSeleccion();
    app.addEventListener("afterSelectionChanged", function () {
        if (w.visible) try { actualizarAmbito(); } catch (_) {}
    }).name = OYENTE_SEL;

    // --- Documentos abiertos por la búsqueda en libro -----------------------------
    // Se abren sin ventana; al empezar otra búsqueda se cierran los que el usuario no ha mirado
    // (los que tienen cambios se quedan abiertos, con ventana, para que pueda guardarlos).
    B.abiertos = [];
    function cerrarAbiertos() {
        for (var i = 0; i < B.abiertos.length; i++) {
            var d = B.abiertos[i];
            try {
                if (!d.isValid || d.windows.length) continue;
                if (d.modified) d.windows.add();
                else d.close(SaveOptions.NO);
            } catch (_) {}
        }
        B.abiertos = [];
    }

    // --- Resultados -----------------------------------------------------------
    // Cada resultado: {d: datos de Claude, estado: "" | "hecho" | "omitido" | "error", doc, cdoc,
    //   texto, cont, clave, ini, fin (posición original), delta (cambio de longitud al aplicarlo),
    //   fijo (aplicado en un paso anterior que ya no se puede rehacer), antes}
    var R = [];
    var topes = {};  // por documento: longitud del historial justo después de nuestro último paso
    B.cambio = null;
    var fAplicar = null;

    function preparar(datos) {
        R = [];
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
                e.antes = textoRango(e.cont, e.ini, e.fin);
                e.lista = contextoPalabras(e.cont, e.ini, e.fin, 3);
            } else if (o && o.isValid) {
                e.obj = o;
                e.antes = d.texto || describir(o);  // para objetos, la descripción de Claude es más clara
            } else {
                e.estado = "error";
                e.antes = "(no se encuentra en el documento)";
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
        if (n === topes[cdoc] && doc.undoName === B.cambio.descripcion) return "arriba";
        var deshecho = n === topes[cdoc] - 1 && doc.redoName === B.cambio.descripcion;
        for (i = 0; i < R.length; i++) {
            if (R[i].cdoc !== cdoc || R[i].estado !== "hecho" || R[i].fijo) continue;
            if (deshecho) R[i].estado = "";  // el usuario lo deshizo
            else R[i].fijo = true;           // ha seguido trabajando: lo aplicado se queda en su paso
        }
        delete topes[cdoc];
        return "suelto";
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
                    fAplicar(p.obj, doc);
                    e.delta = e.texto ? largo(e.cont) - antesLargo : 0;
                } catch (x) { e.estado = "error"; e.error = x.message; e.delta = 0; }
                e.pendiente = false;
            }
        }, ScriptLanguage.JAVASCRIPT, undefined, UndoModes.ENTIRE_SCRIPT, B.cambio.descripcion);
        topes[cdoc] = doc.undoHistory.length;
        if (!doc.windows.length) doc.windows.add();  // capítulo abierto sin ventana: que se vea y se pueda guardar
    }

    // Si el cambio es solo de formato el texto no cambia: se añade debajo la propuesta («→ 85 Heavy»).
    function conPropuesta(e, txt) {
        return txt === e.antes && e.d.propuesta ? txt + "\n" + e.d.propuesta : txt;
    }
    // Texto «después» de un resultado sin cambiar: se aplica a prueba y se deshace.
    function vistaPrevia(k) {
        var e = R[k], doc = e.doc;
        if (!fAplicar || !doc) return "";
        if (e.estado === "hecho") { var p0 = actual(k); return e.texto ? conPropuesta(e, textoRango(e.cont, p0.ini, p0.fin)) : describir(e.obj); }
        if (e.estado === "error") return e.error || "";
        var p = actual(k), l0 = e.texto ? largo(e.cont) : 0, pasos = doc.undoHistory.length, txt;
        try {
            app.doScript(function () { fAplicar(p.obj, doc); }, ScriptLanguage.JAVASCRIPT, undefined,
                         UndoModes.ENTIRE_SCRIPT, VISTA);
            txt = e.texto ? conPropuesta(e, textoRango(e.cont, p.ini, p.fin + largo(e.cont) - l0)) : describir(e.obj);
        } catch (x) { txt = "Error al aplicar: " + x.message; }
        if (doc.undoHistory.length > pasos) doc.undo();
        return txt;
    }

    // --- Lista ----------------------------------------------------------------
    var MARCA = {"": "", hecho: "✓", omitido: "–", error: "!"};
    function marca(e) { return e.estado === "" && e.d.dudoso ? "?" : MARCA[e.estado]; }

    function pintar() {
        lista.removeAll();
        dudosos.removeAll();
        for (var i = 0; i < R.length; i++) {
            var e = R[i], it = lista.add("item", marca(e));
            it.subItems[0].text = corto(e.d.documento || "");
            it.subItems[1].text = e.d.pagina;
            it.subItems[2].text = e.lista || e.d.texto.replace(/[\r\n]+/g, " ¶ ");
            it.subItems[3].text = e.d.propuesta || "";
            if (e.d.dudoso) {
                var du = dudosos.add("item", corto(e.d.documento || "") + " · pág. " + e.d.pagina);
                du.subItems[0].text = (e.d.motivo || "Caso dudoso") + " — " + (e.lista || e.d.texto.replace(/[\r\n]+/g, " ¶ "));
                du.indice = i;
            }
        }
        pDudosos.text = "Casos dudosos (" + dudosos.items.length + ")";
        recuento();
    }
    function refrescar(k) { lista.items[k].text = marca(R[k]); }
    function recuento() {
        var h = 0, p = 0;
        for (var i = 0; i < R.length; i++) { if (R[i].estado === "hecho") h++; if (R[i].estado === "") p++; }
        var hay = !!fAplicar && R.length > 0;
        bCambiar.enabled = bOmitir.enabled = bTodo.enabled = hay && p > 0;
        bDeshacer.enabled = hay && h > 0;
        bTerminar.enabled = hay;
        nota.text = hay ? h + " cambiados, " + p + " pendientes" : "";
    }
    function siguiente(k) {
        for (var i = k + 1; i < R.length; i++) if (R[i].estado === "") return i;
        for (i = 0; i < k; i++) if (R[i].estado === "") return i;
        return -1;
    }

    function mostrarCaso(k) {
        var e = R[k];
        antes.text = e.antes;
        despues.text = fAplicar ? vistaPrevia(k) : "";
        if (e.estado === "error" || !e.doc) return;
        try {
            if (!e.doc.windows.length) e.doc.windows.add();  // capítulo abierto sin ventana
            app.activeDocument = e.doc;
            var o = actual(k).obj;
            app.select(o);
            if (o.hasOwnProperty("showText")) o.showText();
            else if (o.parentPage) app.activeWindow.activePage = o.parentPage;
            B.firma = B.firmaPropia = contextoActual().firma;  // selección hecha por la ventana: no cambia el ámbito
        } catch (x) { estado.text = "No se puede mostrar: " + x.message; }
        w.active = true;  // al ir al texto, InDesign pone delante el documento y la ventana quedaba detrás
    }
    var ignorar = false;  // para no reaccionar a cambios de selección hechos por código
    function seleccionar(k) {
        ignorar = true;
        lista.selection = k < 0 ? null : k;
        ignorar = false;
        if (k >= 0) mostrarCaso(k);
        else { antes.text = ""; despues.text = ""; }
    }
    lista.onChange = function () { if (!ignorar && lista.selection) mostrarCaso(lista.selection.index); };
    dudosos.onChange = function () { if (dudosos.selection) seleccionar(dudosos.selection.indice); };

    function actuar(fn) {
        if (app.documents.length === 0) { estado.text = "No hay ningún documento abierto"; return; }
        try { fn(); } catch (x) { estado.text = "Error: " + x.message; }
        recuento();
    }
    bCambiar.onClick = function () {
        actuar(function () {
            var k = lista.selection ? lista.selection.index : siguiente(-1);
            if (k < 0 || R[k].estado !== "") return;
            R[k].estado = "hecho";
            aplicarHechos(R[k].doc, R[k].cdoc);
            refrescar(k);
            seleccionar(siguiente(k));
        });
    };
    bOmitir.onClick = function () {
        actuar(function () {
            var k = lista.selection ? lista.selection.index : siguiente(-1);
            if (k < 0 || R[k].estado !== "") return;
            R[k].estado = "omitido";
            refrescar(k);
            seleccionar(siguiente(k));
        });
    };
    bTodo.onClick = function () {
        actuar(function () {
            var docs = {}, n = 0, i;
            for (i = 0; i < R.length; i++)
                if (R[i].estado === "" && !R[i].d.dudoso && R[i].doc) { R[i].estado = "hecho"; docs[R[i].cdoc] = R[i].doc; n++; }
            if (!n) { estado.text = "Solo quedan casos dudosos: cámbialos uno a uno"; return; }
            for (var c in docs) if (docs.hasOwnProperty(c)) aplicarHechos(docs[c], c);
            for (i = 0; i < R.length; i++) refrescar(i);
            seleccionar(-1);
        });
    };

    // Cancelar: deshace en cada documento nuestro paso de deshacer, si sigue siendo el último.
    function deshacerTodo() {
        var docs = {}, i, c, quedan = 0;
        for (i = 0; i < R.length; i++) if (R[i].estado === "hecho" && R[i].doc) docs[R[i].cdoc] = R[i].doc;
        for (c in docs) if (docs.hasOwnProperty(c) && sincronizar(docs[c], c) === "arriba") { docs[c].undo(); delete topes[c]; }
        for (i = 0; i < R.length; i++) if (R[i].estado === "hecho" && R[i].fijo) quedan++;
        return quedan;  // cambios que no se pudieron deshacer porque el usuario siguió trabajando
    }
    function cerrarRevision(mensaje) {
        R = [];
        topes = {};
        B.cambio = null;
        fAplicar = null;
        pintar();
        antes.text = despues.text = "";
        estado.text = mensaje;
        cerrarAbiertos();
    }
    bDeshacer.onClick = function () {
        actuar(function () {
            var quedan = deshacerTodo();
            cerrarRevision(quedan ? "Cancelado. " + quedan + " cambios no se pudieron deshacer porque has seguido trabajando: usa Cmd+Z"
                                  : "Cancelado: no se ha realizado ningún cambio");
        });
    };
    bTerminar.onClick = function () {
        actuar(function () {
            var h = 0;
            for (var i = 0; i < R.length; i++) if (R[i].estado === "hecho") h++;
            cerrarRevision(h ? "Terminado: " + h + " cambios hechos (Cmd+Z para deshacerlos)" : "Terminado sin cambios");
        });
    };

    // --- Búsqueda en segundo plano -----------------------------------------
    function shell(orden) {
        app.doScript('do shell script "' + orden.replace(/\\/g, "\\\\").replace(/"/g, '\\"') + '"',
                     ScriptLanguage.APPLESCRIPT_LANGUAGE);
    }
    function q(ruta) { return "'" + ruta.replace(/'/g, "'\\''") + "'"; }
    function leer(f) {
        f.encoding = "UTF-8";
        f.open("r");
        var s = f.read();
        f.close();
        return eval("(" + s + ")");  // JSON escrito por buscar.py (solo ASCII)
    }

    function terminar() {
        if (B.tarea && B.tarea.isValid) B.tarea.remove();
        B.tarea = null;
        bBuscar.enabled = bLibro.enabled = true;
        bCancelar.enabled = false;
    }

    function mostrar(datos) {
        if (datos.error) {
            estado.text = "No se pudo buscar";
            resumen.text = datos.error;
            return;
        }
        estado.text = datos.resultados.length + " resultados · " + Math.round((new Date() - B.inicio) / 1000) + " s";
        resumen.text = datos.resumen;
        B.cambio = datos.cambio && /\S/.test(datos.cambio.aplicar) ? datos.cambio : null;
        fAplicar = null;
        if (B.cambio) {
            try { fAplicar = new Function("obj", "doc", B.cambio.aplicar); }
            catch (x) { resumen.text += "\n(El cambio propuesto tiene un error: " + x.message + ")"; B.cambio = null; }
        }
        preparar(datos);
        pintar();
        for (var i = 0; i < R.length; i++) if (R[i].estado !== "error") { seleccionar(i); break; }
    }

    function comprobar() {
        if (!B.salida) return;
        if (!B.salida.exists) {
            estado.text = B.texto_espera + " " + Math.round((new Date() - B.inicio) / 1000) + " s";
            return;
        }
        terminar();
        var datos;
        try { datos = leer(B.salida); } catch (e) { datos = {error: "Respuesta ilegible: " + e.message}; }
        B.salida.remove();
        B.salida = null;
        try { mostrar(datos); } catch (e) { estado.text = "Error al mostrar: " + e.message; }
    }

    // Lanza buscar.py con la petición y deja la ventana esperando el resultado.
    function lanzar(texto, alcance, espera) {
        var id = new Date().getTime();
        var pet = File(CARPETA + "/peticion_" + id + ".json");
        B.salida = File(CARPETA + "/resultado_" + id + ".json");
        pet.encoding = "UTF-8";
        pet.open("w");
        pet.write(json({descripcion: texto, alcance: alcance, salida: B.salida.fsName}));
        pet.close();
        shell(q(PYTHON) + " " + q(BUSCAR) + " " + q(pet.fsName) + " > /dev/null 2>&1 &");
        B.inicio = new Date();
        B.texto_espera = espera;
        estado.text = espera;
        bBuscar.enabled = bLibro.enabled = false;
        bCancelar.enabled = true;
        B.tarea = app.idleTasks.add({name: "buscador_claude", sleep: 1000});
        B.tarea.addEventListener(IdleEvent.ON_IDLE, comprobar);
    }

    function limpiar() {
        cerrarAbiertos();
        R = [];
        topes = {};
        B.cambio = null;
        fAplicar = null;
        pintar();
        resumen.text = "";
        antes.text = despues.text = "";
    }

    B.buscar = function (texto) {
        if (!/\S/.test(texto)) { estado.text = "Escribe qué quieres buscar"; return; }
        var c = contextoActual();
        if (!c.opciones.length) { estado.text = "No hay ningún documento abierto"; return; }
        var tipo = ambito.selection ? claves[ambito.selection.index] : c.opciones[0];
        var alcance = {tipo: tipo, documentos: [c.doc]};
        if (c.firma === B.firmaPropia && B.alcance && B.alcance.tipo === tipo) {
            alcance = B.alcance;  // lo seleccionado es un resultado puesto por la ventana: mismo ámbito que antes
        } else if (tipo === "seleccion" || tipo === "articulo") {
            alcance.ref = tipo === "seleccion" ? c.selRef : c.artRef;
            if (!alcance.ref) { estado.text = tipo === "seleccion" ? "Ya no hay texto seleccionado" : "El cursor ya no está en un texto"; return; }
        }
        if (tipo === "documentos" && alcance !== B.alcance) alcance.documentos = documentosConVentana();
        B.alcance = alcance;
        limpiar();
        lanzar(texto, alcance, "Buscando en " + AMBITOS[tipo].toLowerCase() + "…");
    };

    // --- Búsqueda en un libro -----------------------------------------------
    function elegirLibro() {
        var abiertos = app.books, otro = "Otro libro…";
        if (abiertos.length) {
            var d = new Window("dialog", "Buscar en libro");
            d.add("statictext", undefined, "Libro:");
            var lst = d.add("dropdownlist", undefined, []);
            for (var i = 0; i < abiertos.length; i++) lst.add("item", abiertos[i].name);
            lst.add("item", otro);
            lst.selection = 0;
            var g = d.add("group");
            g.add("button", undefined, "Cancelar", {name: "cancel"});
            g.add("button", undefined, "Buscar", {name: "ok"});
            if (d.show() !== 1) return null;
            if (lst.selection.text !== otro) return abiertos.itemByName(lst.selection.text).fullName;
        }
        return File.openDialog("Elige el libro de InDesign", function (f) { return f instanceof Folder || /\.indb$/i.test(f.name); });
    }

    B.buscarLibro = function (texto, archivo) {
        if (!/\S/.test(texto)) { estado.text = "Escribe qué quieres buscar"; return; }
        limpiar();
        estado.text = "Abriendo los capítulos…";
        var interaccion = app.scriptPreferences.userInteractionLevel, libro, nombres = [], faltan = [];
        app.scriptPreferences.userInteractionLevel = UserInteractionLevels.NEVER_INTERACT;  // sin avisos de fuentes o vínculos
        try {
            for (var b = 0; b < app.books.length && !libro; b++)  // si ya está abierto, volver a abrirlo falla
                if (app.books[b].fullName.fsName === File(archivo).fsName) libro = app.books[b];
            if (!libro) libro = app.open(File(archivo));
            for (var i = 0; i < libro.bookContents.length; i++) {
                var cap = libro.bookContents[i], f = File(cap.fullName), doc = null;
                if (!f.exists) { faltan.push(cap.name); continue; }
                for (var j = 0; j < app.documents.length; j++)
                    try { if (app.documents[j].fullName.fsName === f.fsName) doc = app.documents[j]; } catch (_) {}  // sin guardar: sin ruta
                if (!doc) { doc = app.open(f, false); B.abiertos.push(doc); }
                nombres.push(doc.name);
            }
        } catch (x) {
            estado.text = "No se pudo abrir el libro: " + x.message;
            return;
        } finally { app.scriptPreferences.userInteractionLevel = interaccion; }
        if (!nombres.length) { estado.text = "El libro no tiene capítulos que se puedan abrir"; return; }
        lanzar(texto, {tipo: "libro", libro: libro.name, documentos: nombres},
               "Buscando en " + nombres.length + " capítulos de «" + libro.name.replace(/\.indb$/i, "") + "»…");
        if (faltan.length) resumen.text = "No se encuentran estos capítulos: " + faltan.join(", ");
    };

    B.cancelar = function () {
        if (!B.salida) return;
        var pid = File(B.salida.fsName + ".pid");
        if (pid.exists) {
            pid.open("r");
            var n = parseInt(pid.read(), 10);
            pid.close();
            if (n) shell("kill " + n);
        }
        estado.text = "Cancelando…";
    };

    // Oyente que fuerza el redibujado tras Cmd+Z (ver oyente_deshacer.jsx).
    try {
        var f = File(INDESIGN_MCP + "/jsx/oyente_deshacer.jsx");
        f.encoding = "UTF-8";
        f.open("r");
        var codigo = f.read().replace(/^#.*$/mg, "");
        f.close();
        new Function("ARGS", codigo)({});
    } catch (_) {}

    B.interno = {R: function () { return R; }, actual: actual};  // solo para pruebas desde fuera
    bBuscar.onClick = function () { B.buscar(desc.text); };
    bLibro.onClick = function () {
        if (!/\S/.test(desc.text)) { estado.text = "Escribe qué quieres buscar"; return; }
        var archivo = elegirLibro();
        if (archivo) B.buscarLibro(desc.text, archivo);
    };
    bCancelar.onClick = function () { B.cancelar(); };
    bNueva.onClick = function () {
        if (B.tarea) {  // búsqueda en marcha: se detiene y su resultado se ignora
            B.cancelar();
            terminar();
            B.salida = null;
        }
        cerrarRevision("");
        desc.text = resumen.text = "";
        B.alcance = B.firma = B.firmaPropia = null;
        try { actualizarAmbito(); } catch (_) {}
        desc.active = true;
    };

    // Posición: donde la dejó el usuario; la primera vez, arriba a la derecha.
    var CLAVE_POS = "claude_buscador_posicion";
    w.onShow = function () {
        var v = app.extractLabel(CLAVE_POS).split(","), s = $.screens[0];
        w.location = v.length === 2 ? [Number(v[0]), Number(v[1])] : [s.right - w.size.width - 40, s.top + 140];
        try { actualizarAmbito(); } catch (_) {}
    };
    w.onMove = function () { app.insertLabel(CLAVE_POS, w.location[0] + "," + w.location[1]); };
    w.onClose = function () {
        if (B.destruyendo) { if (B.tarea) B.cancelar(); return true; }
        w.hide();  // cerrar solo la oculta: Ventana > Buscar con Claude la vuelve a mostrar igual
        return false;
    };
    B.destruir = function () {
        B.destruyendo = true;
        quitarOyenteSeleccion();
        w.close();
        cerrarAbiertos();
        $.global.buscadorClaude = null;
    };
    recuento();
    w.show();
})();
