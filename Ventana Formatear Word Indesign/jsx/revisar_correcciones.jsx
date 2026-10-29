// Ventana «Revisar correcciones» (Formatear Word > Simular correcciones): recorre una a una las
// correcciones ortotipográficas seguras (publicaciones/ortotipografia.toml) del documento activo,
// con el antes y el después de cada una, para aceptarlas u omitirlas.
// - Aceptar: hace esa corrección (un paso de deshacer). Solo se cambian los caracteres que
//   cambian, así el resto conserva su formato (la cursiva dentro de unas comillas, por ejemplo).
// - Omitir: la deja como está; no vuelve a salir mientras la ventana siga abierta.
// - Aceptar todas: las de la lista (todas o las de la regla elegida), en un paso de deshacer.
// El «después» se calcula con la misma búsqueda GREP en un documento oculto: es exactamente lo
// que haría «Aplicar correcciones».
// Motor persistente "formatear_word"; la ventana vive en $.global.revisarCorrecciones.

#targetengine "formatear_word"

(function () {
    var RAIZ = File($.fileName).parent.parent;     // carpeta del proyecto
    var PYTHON = "/Library/Frameworks/Python.framework/Versions/3.14/bin/python3";
    $.evalFile(File(RAIZ.fsName + "/jsx/reglas_comun.jsx"));

    if ($.global.revisarCorrecciones && $.global.revisarCorrecciones.ventana) {
        $.global.revisarCorrecciones.cargar();
        $.global.revisarCorrecciones.ventana.show();
        return;
    }
    var C = $.global.revisarCorrecciones = {};
    C.omitidas = {};

    // Espacios especiales, visibles en la ventana (con códigos: un literal se lo puede comer el editor).
    var NBSP = String.fromCharCode(0xA0), FINO = String.fromCharCode(0x2009), FINO_NS = String.fromCharCode(0x202F);
    function visible(s) {
        return String(s).split(NBSP).join("·").split(FINO_NS).join("ˑ").split(FINO).join("ˑ")
                        .replace(/\r/g, "¶").replace(/\t/g, "→");
    }

    function q(s) { return "'" + String(s).replace(/'/g, "'\\''") + "'"; }
    function leerJSON(f) {
        f.encoding = "UTF-8";
        if (!f.exists || !f.open("r")) return null;
        var t = f.read();
        f.close();
        return eval("(" + t + ")");
    }

    // Reglas al día desde el .toml (por si han cambiado desde la última vez).
    function leerReglas() {
        var f = File(Folder.temp.fsName + "/formatear_word_reglas.json");
        var orden = "cd " + q(RAIZ.fsName) + " && " + q(PYTHON) + " -I ortotipografia.py --exportar " + q(f.fsName) +
            ($.global.formatearWordPublicacion ? " --maqueta " + q($.global.formatearWordPublicacion) : "") + " 2>&1";
        app.doScript('do shell script "' + orden.replace(/\\/g, "\\\\").replace(/"/g, '\\"') + '"', ScriptLanguage.APPLESCRIPT_LANGUAGE);
        return leerJSON(f);
    }

    // ---- candidatos ----------------------------------------------------------------------------
    // {regla, tipo: "cambiar" | "estilo" | "ladillos", cont (historia, celda o nota), ini, len,
    //  texto, ec (estilo de carácter), ini2 (ladillos: el párrafo de abajo)}
    function clave(cont) { try { return cont.toSpecifier(); } catch (e) { return ""; } }

    function rango(c) {
        return resolve(c.cont.characters.itemByRange(c.ini, c.ini + c.len - 1).toSpecifier());
    }

    function huella(c) {
        try {
            var t = rango(c), p = t.paragraphs[0], pc = p.contents, o = c.ini - p.index;
            return c.regla.nombre + "|" + pc.substring(Math.max(0, o - 20), o) + "[" + c.texto + "]" + pc.substr(o + c.len, 20);
        } catch (e) { return c.regla.nombre + "|" + c.texto; }
    }

    function buscar(d, reglas) {
        var res = [];
        for (var r = 0; r < reglas.length; r++) {
            var rg = reglas[r];
            if (rg.tipo == "ladillos_seguidos") {
                var pares = ladillosPendientes(d, rg);
                for (var i = 0; i < pares.length; i++) {
                    var a = pares[i][0], b = pares[i][1];
                    res.push({ regla: rg, tipo: "ladillos", cont: a.parent, ini: a.index, len: a.length, ini2: b.index,
                               texto: a.contents.replace(/\r$/, "") + "  ⟂  " + b.contents.replace(/\r$/, "") });
                }
                continue;
            }
            var hs = hallazgos(d, rg, C.estilos);
            for (var i = 0; i < hs.length; i++) {
                var t = hs[i].t;
                res.push({ regla: rg, tipo: rg.estilo ? "estilo" : "cambiar", cont: t.parent, ini: t.index,
                           len: t.length, texto: String(t.contents), ec: hs[i].ec });
            }
        }
        for (var i = 0; i < res.length; i++) {
            var c = res[i];
            c.clave = clave(c.cont);
            c.orden = i;
            c.pagina = "—"; c.clavePag = 1e6;
            try {
                var fr = c.cont.characters[c.ini].parentTextFrames[0], pg = fr.parentPage;
                if (pg) { c.pagina = pg.name; c.clavePag = pg.documentOffset; }
                else { var sp = fr.parent; while (sp && !(sp instanceof Spread)) sp = sp.parent;
                       c.pagina = "mesa " + sp.pages[sp.pages.length - 1].name; c.clavePag = sp.pages[sp.pages.length - 1].documentOffset + 0.5; }
            } catch (e) {}
            c.huella = huella(c);
        }
        // Por página; dentro de la misma historia o celda, por posición.
        res.sort(function (a, b) {
            return a.clavePag - b.clavePag || (a.clave == b.clave ? a.ini - b.ini : a.orden - b.orden);
        });
        var quedan = [];
        for (var i = 0; i < res.length; i++) if (!C.omitidas[res[i].huella]) quedan.push(res[i]);
        return quedan;
    }

    // ---- el «después» --------------------------------------------------------------------------
    // Documento oculto para probar la regla sobre una copia del párrafo.
    function borrador() {
        if (!C.borrador || !C.borrador.isValid) {
            C.borrador = app.documents.add(false);
            // Sin comillas tipográficas: al escribir el párrafo, «'» pasaría a «’».
            try { C.borrador.textPreferences.typographersQuotes = false; } catch (e) {}
            C.marco = C.borrador.pages[0].textFrames.add({ geometricBounds: [0, 0, 500, 500] });
        }
        return C.marco.parentStory;
    }
    function cerrarBorrador() {
        try { if (C.borrador && C.borrador.isValid) C.borrador.close(SaveOptions.NO); } catch (e) {}
        C.borrador = null;
    }

    // Texto nuevo de un hallazgo «cambiar»: la regla se aplica al párrafo entero en el borrador
    // (las reglas miran alrededor) y se saca lo que ha quedado en lugar de este hallazgo.
    function calcular(c) {
        if (c.nuevo !== undefined) return c.nuevo;
        var t = rango(c), p = t.paragraphs[0], P = String(p.contents).replace(/\r$/, ""), o = c.ini - p.index;
        var st = borrador();
        st.contents = P;
        P = String(st.contents);        // por si InDesign ha cambiado algún carácter al escribirlo
        opcionesGrep();
        app.findGrepPreferences = NothingEnum.NOTHING;
        app.changeGrepPreferences = NothingEnum.NOTHING;
        app.findGrepPreferences.findWhat = c.regla.buscar;
        var hs = st.findGrep(), pos = [];
        for (var i = 0; i < hs.length; i++) pos.push([hs[i].index, hs[i].index + hs[i].length]);
        app.changeGrepPreferences.changeTo = c.regla.cambiar;
        st.changeGrep();
        app.findGrepPreferences = NothingEnum.NOTHING;
        app.changeGrepPreferences = NothingEnum.NOTHING;
        var A = String(st.contents), rs = repartir(P, pos, A), k = -1;
        for (var i = 0; i < pos.length; i++) if (pos[i][0] == o && pos[i][1] == o + c.len) k = i;
        c.nuevo = rs && k >= 0 ? rs[k] : null;
        return c.nuevo;
    }

    // P = U0 h0 U1 h1 … Un (h = hallazgos) y A = U0 r0 U1 r1 … Un: los r de cada hallazgo.
    function repartir(P, pos, A) {
        var U = [], ant = 0;
        for (var i = 0; i < pos.length; i++) { U.push(P.substring(ant, pos[i][0])); ant = pos[i][1]; }
        U.push(P.substring(ant));
        if (A.substring(0, U[0].length) != U[0]) return null;
        function paso(k, at) {
            if (k == pos.length) return at == A.length ? [] : null;     // el último U ya está comprobado
            var max = A.length - at - U[k + 1].length;
            for (var n = 0; n <= max; n++) {
                if (A.substr(at + n, U[k + 1].length) != U[k + 1]) continue;
                var resto = paso(k + 1, at + n + U[k + 1].length);
                if (resto) return [A.substr(at, n)].concat(resto);
            }
            return null;
        }
        return paso(0, U[0].length);
    }

    // Cambios mínimos para pasar de a a b: [{ini, fin, s}] sobre a (los caracteres que no cambian
    // se quedan, con su formato).
    function ediciones(a, b) {
        var n = a.length, m = b.length, L = [];
        if (n * m > 250000) return [{ ini: 0, fin: n, s: b }];
        for (var i = 0; i <= n; i++) { L.push([]); for (var j = 0; j <= m; j++) L[i].push(0); }
        for (var i = n - 1; i >= 0; i--)
            for (var j = m - 1; j >= 0; j--)
                L[i][j] = a.charAt(i) == b.charAt(j) ? L[i + 1][j + 1] + 1 : Math.max(L[i + 1][j], L[i][j + 1]);
        var res = [], i = 0, j = 0, act = null;
        while (i < n || j < m) {
            if (i < n && j < m && a.charAt(i) == b.charAt(j)) { act = null; i++; j++; }
            else {
                if (!act) { act = { ini: i, fin: i, s: "" }; res.push(act); }
                if (j < m && (i == n || L[i][j + 1] >= L[i + 1][j])) { act.s += b.charAt(j); j++; }
                else { i++; act.fin = i; }
            }
        }
        return res;
    }

    // ---- aplicar -------------------------------------------------------------------------------
    // Hace una corrección y corrige la posición de las demás de la misma historia o celda.
    function aplicar(c) {
        var t = rango(c);
        if (c.tipo != "ladillos" && String(t.contents) != c.texto) throw new Error("el texto ha cambiado (pulsa Actualizar)");
        var delta = 0;
        if (c.tipo == "estilo") t.appliedCharacterStyle = c.ec;
        else if (c.tipo == "ladillos") {
            c.cont.characters[c.ini].paragraphs[0].spaceAfter = 0;
            c.cont.characters[c.ini2].paragraphs[0].spaceBefore = 0;
        } else {
            var nuevo = calcular(c);
            if (nuevo === null) throw new Error("no se ha podido calcular el cambio");
            var eds = ediciones(c.texto, nuevo);
            for (var k = eds.length - 1; k >= 0; k--) {
                var e = eds[k];
                if (e.fin > e.ini) {
                    var r = resolve(c.cont.characters.itemByRange(c.ini + e.ini, c.ini + e.fin - 1).toSpecifier());
                    if (e.s) r.contents = e.s; else r.remove();
                } else c.cont.insertionPoints[c.ini + e.ini].contents = e.s;
            }
            delta = nuevo.length - c.len;
        }
        // Las demás: las de detrás se mueven; las que pisan esta se quitan (con Actualizar vuelven
        // si aún hacen falta); a las del mismo párrafo se les recalcula el «después».
        var fin = c.ini + c.len, quedan = [];
        for (var i = 0; i < C.todas.length; i++) {
            var x = C.todas[i];
            if (x === c) continue;
            if (x.clave == c.clave && x.tipo != "ladillos" && c.tipo != "ladillos") {
                if (x.ini < fin && c.ini < x.ini + x.len && (c.tipo == "cambiar" || x.tipo == "cambiar")) continue;
                if (x.ini >= fin) { x.ini += delta; }
                x.nuevo = undefined;
            } else if (x.clave == c.clave && delta) {
                if (x.ini >= fin) x.ini += delta;
                if (x.ini2 !== undefined && x.ini2 >= fin) x.ini2 += delta;
            }
            quedan.push(x);
        }
        C.todas = quedan;
    }

    function enUnPaso(nombre, fn) {
        if (!C.doc || !C.doc.isValid) { C.cargar(); throw new Error("El documento ya no está abierto"); }
        app.doScript(fn, ScriptLanguage.JAVASCRIPT, undefined, UndoModes.ENTIRE_SCRIPT, nombre);
    }

    // ---- ventana ---------------------------------------------------------------------------
    var w = C.ventana = new Window("palette", "Revisar correcciones", undefined, { resizeable: true });
    w.orientation = "column";
    w.alignChildren = ["fill", "top"];
    var cab = w.add("group");
    cab.alignChildren = ["left", "center"];
    var titulo = cab.add("statictext", undefined, "", { characters: 34, truncate: "end" });
    cab.add("statictext", undefined, "Ver:");
    var filtro = cab.add("dropdownlist", undefined, []);
    filtro.preferredSize.width = 260;
    var bActualizar = cab.add("button", undefined, "Actualizar");
    bActualizar.helpTip = "Vuelve a buscar las correcciones del documento activo (también tras un Cmd+Z o tras cambiar las reglas)";

    var lb = w.add("listbox", [0, 0, 760, 240], undefined, {
        numberOfColumns: 4, showHeaders: true,
        columnTitles: ["Nº", "Regla", "Pág.", "Texto"], columnWidths: [40, 230, 50, 420] });
    lb.alignment = ["fill", "fill"];

    var pCmp = w.add("panel", undefined, "Corrección");
    pCmp.alignChildren = ["fill", "top"];
    // Antes a la izquierda y después a la derecha.
    var gCmp = pCmp.add("group"); gCmp.alignment = ["fill", "top"]; gCmp.alignChildren = ["fill", "top"];
    var pA = gCmp.add("panel", undefined, "Antes"); pA.alignChildren = ["fill", "top"];
    var antes = pA.add("statictext", [0, 0, 350, 48], "", { multiline: true });
    var pD = gCmp.add("panel", undefined, "Después"); pD.alignChildren = ["fill", "top"];
    var despues = pD.add("statictext", [0, 0, 350, 48], "", { multiline: true });
    var regla = pCmp.add("statictext", [0, 0, 740, 32], "", { multiline: true });
    var leyenda = pCmp.add("statictext", undefined, "· espacio de no separación   ˑ espacio fino   ¶ fin de párrafo");
    leyenda.graphics.foregroundColor = leyenda.graphics.newPen(leyenda.graphics.PenType.SOLID_COLOR, [0.5, 0.5, 0.5], 1);

    var gBot = w.add("group");
    gBot.alignment = ["fill", "top"];
    var bAnt = gBot.add("button", undefined, "◀ Anterior");
    var bSig = gBot.add("button", undefined, "Siguiente ▶");
    var hueco = gBot.add("group"); hueco.alignment = ["fill", "center"];
    var bAceptar = gBot.add("button", undefined, "Aceptar");
    bAceptar.helpTip = "Hace esta corrección (un Cmd+Z la deshace) y pasa a la siguiente";
    var bOmitir = gBot.add("button", undefined, "Omitir");
    bOmitir.helpTip = "La deja como está y pasa a la siguiente";
    var bTodas = gBot.add("button", undefined, "Aceptar todas");
    bTodas.helpTip = "Hace todas las de la lista (si has elegido una regla en «Ver», solo las de esa regla); un Cmd+Z las deshace";
    var bTerminar = gBot.add("button", undefined, "Terminar");
    bTerminar.helpTip = "Deja de revisar: cierra la ventana (lo que no hayas aceptado queda sin cambiar)";

    function reglaElegida() {
        return filtro.selection && filtro.selection.index > 0 ? filtro.selection.text.replace(/ \(\d+\)$/, "") : "";
    }
    function visibles() {
        var f = reglaElegida();
        if (!f) return C.todas.slice(0);
        var r = [];
        for (var i = 0; i < C.todas.length; i++) if (C.todas[i].regla.nombre == f) r.push(C.todas[i]);
        return r;
    }

    // La corrección con dos palabras delante y tres detrás: «…palabra palabra[texto]palabra…».
    function contexto(c, medio) {
        try {
            var t = rango(c), p = t.paragraphs[0], pc = String(p.contents).replace(/\r$/, ""), o = c.ini - p.index;
            var delante = pc.substring(0, o), detras = pc.substring(o + c.len);
            var a = delante.match(/(?:\S+\s+){0,2}\S*$/)[0], b = detras.match(/^\S*(?:\s+\S+){0,3}/)[0];
            return visible((a.length < delante.length ? "…" : "") + a) + "[" + visible(medio) + "]" +
                   visible(b + (b.length < detras.length ? "…" : ""));
        } catch (e) { return "[" + visible(medio) + "]"; }
    }

    function rellenar(sel) {
        lb.removeAll();
        C.vistas = visibles();
        for (var i = 0; i < C.vistas.length; i++) {
            var c = C.vistas[i], it = lb.add("item", String(i + 1));
            it.subItems[0].text = c.regla.nombre;
            it.subItems[1].text = c.pagina;
            var t = c.tipo == "ladillos" ? visible(c.texto) : contexto(c, c.texto);
            it.subItems[2].text = t.length > 80 ? t.substring(0, 80) + "…" : t;
        }
        titulo.text = (C.doc ? C.doc.name + ": " : "") + C.todas.length + " correcciones pendientes";
        if (C.vistas.length) lb.selection = Math.min(sel || 0, C.vistas.length - 1);
        else mostrar();
    }

    function mostrar() {
        var it = lb.selection;
        bAceptar.enabled = bOmitir.enabled = bAnt.enabled = bSig.enabled = !!it;
        bTodas.enabled = C.vistas && C.vistas.length > 0;
        if (!it) { antes.text = despues.text = regla.text = ""; return; }
        var c = C.vistas[it.index];
        bAnt.enabled = it.index > 0;
        bSig.enabled = it.index < C.vistas.length - 1;
        regla.text = c.regla.nombre + ": " + (c.regla.descripcion || "");
        if (c.tipo == "ladillos") {
            antes.text = visible(c.texto) + "\n(con espacio entre los dos)";
            despues.text = visible(c.texto) + "\n(sin espacio entre los dos)";
        } else if (c.tipo == "estilo") {
            antes.text = contexto(c, c.texto);
            despues.text = contexto(c, c.texto) + "\n→ «" + visible(c.texto) + "» con el estilo «" + c.ec.name + "»";
        } else {
            antes.text = contexto(c, c.texto);
            var nuevo = null, error = "";
            try { nuevo = calcular(c); } catch (e) { error = ": " + e; }
            despues.text = nuevo === null ? "(no se ha podido calcular" + error + "; pulsa Actualizar)" : contexto(c, nuevo);
            bAceptar.enabled = nuevo !== null;
        }
        try {
            var t = c.tipo == "ladillos" ? c.cont.characters[c.ini2].paragraphs[0] : rango(c);
            app.select(t);
            t.showText();
        } catch (e) {}
    }

    C.cargar = function (sel) {
        var anterior = reglaElegida();
        filtro.removeAll();
        C.todas = []; C.vistas = [];
        if (!app.documents.length || !app.layoutWindows.length) {
            C.doc = null; titulo.text = "No hay ningún documento abierto"; lb.removeAll(); mostrar(); return;
        }
        if (C.doc && (!C.doc.isValid || C.doc.id != app.activeDocument.id)) C.omitidas = {};
        C.doc = app.activeDocument;
        var datos = leerReglas();
        if (!datos) { titulo.text = "No se han podido leer las reglas (ortotipografia.toml)"; lb.removeAll(); mostrar(); return; }
        C.estilos = datos.estilos;
        C.reglas = datos.reglas;
        C.todas = buscar(C.doc, C.reglas);
        rehacerFiltro(anterior);
        rellenar(sel);
    };

    function rehacerFiltro(anterior) {
        var cuenta = {}, nombres = [];
        for (var i = 0; i < C.todas.length; i++) {
            var n = C.todas[i].regla.nombre;
            if (!cuenta[n]) { cuenta[n] = 0; nombres.push(n); }
            cuenta[n]++;
        }
        C.rellenando = true;
        filtro.removeAll();
        filtro.add("item", "Todas las reglas (" + C.todas.length + ")");
        var elegido = 0;
        for (var i = 0; i < nombres.length; i++) {
            filtro.add("item", nombres[i] + " (" + cuenta[nombres[i]] + ")");
            if (nombres[i] == anterior) elegido = i + 1;
        }
        filtro.selection = elegido;
        C.rellenando = false;
    }

    // Tras aceptar u omitir: la lista sin esa corrección, en el mismo sitio.
    function seguir(i) {
        rehacerFiltro(reglaElegida());
        rellenar(i);
    }

    filtro.onChange = function () { if (!C.rellenando) rellenar(0); };
    lb.onChange = mostrar;
    bActualizar.onClick = function () { C.cargar(lb.selection ? lb.selection.index : 0); };
    bAnt.onClick = function () { if (lb.selection && lb.selection.index > 0) lb.selection = lb.selection.index - 1; };
    bSig.onClick = function () { if (lb.selection && lb.selection.index < C.vistas.length - 1) lb.selection = lb.selection.index + 1; };

    bAceptar.onClick = function () {
        if (!lb.selection) return;
        var i = lb.selection.index, c = C.vistas[i];
        try { enUnPaso("Corrección: " + c.regla.nombre, function () { aplicar(c); }); }
        catch (e) { alert("No se pudo hacer la corrección: " + e); return; }
        // Se vuelve a buscar todo: una corrección puede crear otra o cambiar la de al lado
        // («<25%» → «<25 %» y luego el punto final).
        C.cargar(i);
    };
    bOmitir.onClick = function () {
        if (!lb.selection) return;
        var i = lb.selection.index, c = C.vistas[i], quedan = [];
        C.omitidas[c.huella] = 1;
        for (var k = 0; k < C.todas.length; k++) if (C.todas[k] !== c) quedan.push(C.todas[k]);
        C.todas = quedan;
        seguir(i);
    };
    bTodas.onClick = function () {
        var errores = [];
        if (!C.vistas.length) return;
        try {
            enUnPaso("Correcciones: " + (reglaElegida() || "todas"), function () {
                // Varias pasadas: las que pisa otra (o las que aparecen al corregir) van en la siguiente.
                for (var pasada = 0; pasada < 5 && C.vistas.length; pasada++) {
                    var lista = C.vistas.slice(0);
                    // De la última a la primera: así casi ninguna mueve a las que faltan.
                    for (var i = lista.length - 1; i >= 0; i--) {
                        var c = lista[i], sigue = false;
                        for (var k = 0; k < C.todas.length && !sigue; k++) if (C.todas[k] === c) sigue = true;
                        if (!sigue) continue;       // la ha pisado otra
                        try { aplicar(c); } catch (e) { errores.push(c.regla.nombre + " «" + visible(c.texto) + "»: " + e.message); }
                    }
                    C.todas = buscar(C.doc, C.reglas);
                    C.vistas = visibles();
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
    // Cerrada (con la X o con Terminar) no se guarda: al volver a abrirla se crea de nuevo.
    w.onClose = function () { cerrarBorrador(); $.global.revisarCorrecciones = null; };

    // Para probar desde fuera (#targetengine "formatear_word").
    C.lista = lb;
    C.calcular = calcular; C.repartir = repartir;
    C.campos = { filtro: filtro, antes: antes, despues: despues, regla: regla, titulo: titulo };
    C.botones = { anterior: bAnt, siguiente: bSig, aceptar: bAceptar, omitir: bOmitir, todas: bTodas,
                  terminar: bTerminar, actualizar: bActualizar };
    C.destruir = function () { try { w.close(); } catch (e) {} cerrarBorrador(); $.global.revisarCorrecciones = null; };
    C.cargar();
    w.show();
})();
