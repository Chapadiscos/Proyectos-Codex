// Correcciones ortotipográficas seguras con Buscar/Cambiar GREP.
// Argumentos: [reglas.json, modo ("simular" | "aplicar"), nombre del documento (opcional)].
// - simular: cuenta los cambios de cada regla y enseña ejemplos; no toca el documento.
// - aplicar: hace los cambios en un solo paso de deshacer (un Cmd+Z los revierte todos).
// Sin nombre de documento, trabaja con todos los documentos abiertos.

#target indesign

var ARGS = (typeof arguments != "undefined") ? arguments : [];
var DETALLE = ARGS.length > 3 && ARGS[3] == "detalle";     // todos los ejemplos, no solo 3

function leerJSON(ruta) {
    var f = File(ruta);
    f.encoding = "UTF-8";
    f.open("r");
    var t = f.read();
    f.close();
    return eval("(" + t + ")");
}

function rutaEstilo(est) {
    var r = est.name, p = est.parent;
    while (p && p.constructor && p.constructor.name == "ParagraphStyleGroup") { r = p.name + "/" + r; p = p.parent; }
    return r;
}

// Texto alrededor de un hallazgo, para el informe: «…antes[hallazgo]después…»
function contexto(t) {
    try {
        var par = t.paragraphs[0], ini = t.index - par.index, txt = par.contents;
        var a = Math.max(0, ini - 25), b = Math.min(txt.length, ini + t.contents.length + 25);
        return (a > 0 ? "…" : "") + txt.substring(a, ini) + "[" + t.contents + "]" + txt.substring(ini + t.contents.length, b) + (b < txt.length ? "…" : "");
    } catch (e) { return String(t.contents); }
}

// ¿El estilo está en la lista? Vale el nombre completo («Tabla/Pie tabla»), el nombre solo
// («Pie tabla») o un grupo entero («Tabla» abarca todos los estilos del grupo Tabla).
function enLista(est, lista) {
    for (var k = 0; k < lista.length; k++)
        if (est == lista[k] || est.split("/").pop() == lista[k] || est.indexOf(lista[k] + "/") == 0) return true;
    return false;
}

// Dos ladillos seguidos van sin separación: sin espacio después el de arriba y sin espacio
// antes el de abajo. Solo cuenta los que aún tienen espacio, para poder repetirla.
function ladillosSeguidos(d, rg, aplicar) {
    var n = 0, ej = [], grupo = rg.solo || ["Ladillos"];
    for (var s = 0; s < d.stories.length; s++) {
        var ps = d.stories[s].paragraphs.everyItem().getElements(), anterior = null;
        for (var i = 0; i < ps.length; i++) {
            var est = "";
            try { est = rutaEstilo(ps[i].appliedParagraphStyle); } catch (e) {}
            var es = enLista(est, grupo);
            if (es && anterior && (anterior.spaceAfter != 0 || ps[i].spaceBefore != 0)) {
                n++;
                if (DETALLE || ej.length < 3)
                    ej.push("      " + anterior.contents.replace(/\r/g, "") + "  ⟂  " + ps[i].contents.replace(/\r/g, ""));
                if (aplicar) { anterior.spaceAfter = 0; ps[i].spaceBefore = 0; }
            }
            anterior = es ? ps[i] : null;
        }
    }
    return { n: n, ej: ej };
}

// Estilos de carácter de la maqueta (de maqueta-base.toml): {cursiva: "46 Light Italic", ...}
// y, por grupo de estilos de párrafo, los suyos propios ("" = no aplicar).
var ESTILOS = { caracter: {}, por_grupo: {} };

function estiloCaracter(d, estPar, clave) {
    var nombre = ESTILOS.caracter[clave], grupo = estPar.indexOf("/") >= 0 ? estPar.split("/")[0] : estPar;
    var pg = ESTILOS.por_grupo[grupo];
    if (pg && pg[clave] !== undefined) nombre = pg[clave];
    if (!nombre) return null;
    var todos = d.allCharacterStyles;
    for (var i = 0; i < todos.length; i++) if (todos[i].name == nombre) return todos[i];
    return null;
}

function procesar(d, reglas, aplicar) {
    var lineas = [], total = 0, errores = [];
    var op = app.findChangeGrepOptions;
    op.includeFootnotes = true; op.includeHiddenLayers = false; op.includeLockedLayersForFind = false;
    op.includeLockedStoriesForFind = false; op.includeMasterPages = false;
    for (var r = 0; r < reglas.length; r++) {
        var rg = reglas[r], excl = rg.excluir || [], solo = rg.solo || [];
        // Lista de patrones, no uno con «|»: en ExtendScript, «A$|^B$|C$» encaja con cualquier texto.
        var excl_texto = [], et = rg.excluir_texto || [];
        if (typeof et == "string") et = [et];
        for (var k = 0; k < et.length; k++) excl_texto.push(new RegExp(et[k]));
        if (rg.tipo == "ladillos_seguidos") {
            var res = ladillosSeguidos(d, rg, aplicar);
            if (res.n) { total += res.n; lineas.push("   " + rg.nombre + ": " + res.n + "\n" + res.ej.join("\n")); }
            continue;
        }
        app.findGrepPreferences = NothingEnum.NOTHING;
        app.changeGrepPreferences = NothingEnum.NOTHING;
        app.findGrepPreferences.findWhat = rg.buscar;
        if (rg.cambiar !== undefined) app.changeGrepPreferences.changeTo = rg.cambiar;
        var hallados = d.findGrep(), validos = [], estilos_destino = [];
        for (var i = 0; i < hallados.length; i++) {
            var est = "";
            try { est = rutaEstilo(hallados[i].paragraphs[0].appliedParagraphStyle); } catch (e) {}
            var fuera = enLista(est, excl) || (solo.length && !enLista(est, solo));
            if (!fuera && excl_texto.length) {
                var txt = "";
                try { txt = hallados[i].paragraphs[0].contents.replace(/\r$/, ""); } catch (e) {}
                for (var k = 0; k < excl_texto.length; k++) if (excl_texto[k].test(txt)) fuera = true;
            }
            if (!fuera && rg.estilo) {
                // Regla de estilo de carácter: solo cuenta lo que aún no lo tiene.
                var ec = estiloCaracter(d, est, rg.estilo);
                if (!ec || hallados[i].appliedCharacterStyle.id == ec.id) fuera = true;
                else estilos_destino.push(ec);
            }
            if (!fuera) validos.push(hallados[i]);
        }
        if (!validos.length) continue;
        total += validos.length;
        var ej = [];
        for (var i = 0; i < (DETALLE ? validos.length : Math.min(3, validos.length)); i++) ej.push("      " + contexto(validos[i]).replace(/\r/g, " "));
        lineas.push("   " + rg.nombre + ": " + validos.length + "\n" + ej.join("\n"));
        if (aplicar && rg.estilo) {
            for (var i = 0; i < validos.length; i++) {
                try { validos[i].appliedCharacterStyle = estilos_destino[i]; }
                catch (e) { errores.push(rg.nombre + ": " + e); }
            }
        } else if (aplicar) {
            // Se cambia el párrafo entero de cada hallazgo, no el fragmento: con un fragmento
            // suelto, las reglas que miran alrededor ((?<=\d), (?=…)) ya no encuentran nada.
            // De atrás adelante para que los cambios no muevan los párrafos pendientes.
            var pars = [], vistos = {};
            for (var i = 0; i < validos.length; i++) {
                // En las tablas el índice cuenta desde el principio de cada celda: la clave lleva
                // el contenedor (la historia o la celda), si no se pierden párrafos de otras celdas.
                var p = validos[i].paragraphs[0], cont = p.parent.toSpecifier(), clave = cont + ":" + p.index;
                if (!vistos[clave]) { vistos[clave] = 1; pars.push({ p: p, cont: cont, i: p.index }); }
            }
            pars.sort(function (a, b) { return a.cont < b.cont ? -1 : a.cont > b.cont ? 1 : b.i - a.i; });
            for (var i = 0; i < pars.length; i++) {
                try { pars[i].p.changeGrep(); }
                catch (e) { errores.push(rg.nombre + ": " + e); }
            }
        }
    }
    app.findGrepPreferences = NothingEnum.NOTHING;
    app.changeGrepPreferences = NothingEnum.NOTHING;
    return "== " + d.name + ": " + total + (aplicar ? " cambios hechos" : " cambios posibles") + "\n" + lineas.join("\n") +
        (errores.length ? "\n   ERRORES (" + errores.length + "): " + errores.slice(0, 3).join(" · ") : "");
}

function principal() {
    if (!ARGS.length) return "ERROR: falta el archivo de reglas";
    ESTILOS = leerJSON(ARGS[0]).estilos || ESTILOS;
    var datos = leerJSON(ARGS[0]), reglas = datos.reglas, aplicar = ARGS[1] == "aplicar", nombre = ARGS[2] || "";
    // Por nombre: la posición de cada documento en app.documents cambia mientras se trabaja.
    var nombres = [], docs = [];
    for (var i = 0; i < app.documents.length; i++) if (!nombre || app.documents[i].name == nombre) nombres.push(app.documents[i].name);
    for (var i = 0; i < nombres.length; i++) docs.push(app.documents.itemByName(nombres[i]));
    if (!docs.length) return "ERROR: no hay documentos abiertos" + (nombre ? " con el nombre " + nombre : "");
    var res = [];
    for (var i = 0; i < docs.length; i++) {
        if (aplicar) {
            var salida;
            app.doScript(function () { salida = procesar(docs[i], reglas, true); }, ScriptLanguage.JAVASCRIPT,
                         undefined, UndoModes.ENTIRE_SCRIPT, "Correcciones ortotipográficas");
            res.push(salida);
        } else {
            res.push(procesar(docs[i], reglas, false));
        }
    }
    return res.join("\n\n");
}

app.scriptPreferences.userInteractionLevel = UserInteractionLevels.NEVER_INTERACT;
var resultado;
try { resultado = principal(); }
catch (e) { resultado = "ERROR: " + e + " (línea " + e.line + ")"; }
finally { app.scriptPreferences.userInteractionLevel = UserInteractionLevels.INTERACT_WITH_ALL; }
resultado;
