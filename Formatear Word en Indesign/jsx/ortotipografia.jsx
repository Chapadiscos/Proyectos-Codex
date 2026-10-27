// Correcciones ortotipográficas seguras con Buscar/Cambiar GREP.
// Argumentos: [reglas.json, modo ("simular" | "aplicar"), nombre del documento (opcional)].
// - simular: cuenta los cambios de cada regla y enseña ejemplos; no toca el documento.
// - aplicar: hace los cambios en un solo paso de deshacer (un Cmd+Z los revierte todos).
// Sin nombre de documento, trabaja con todos los documentos abiertos.

#target indesign
#include "reglas_comun.jsx"

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

// Texto alrededor de un hallazgo, para el informe: «…antes[hallazgo]después…»
function contexto(t) {
    try {
        var par = t.paragraphs[0], ini = t.index - par.index, txt = par.contents;
        var a = Math.max(0, ini - 25), b = Math.min(txt.length, ini + t.contents.length + 25);
        return (a > 0 ? "…" : "") + txt.substring(a, ini) + "[" + t.contents + "]" + txt.substring(ini + t.contents.length, b) + (b < txt.length ? "…" : "");
    } catch (e) { return String(t.contents); }
}

// Estilos de carácter de la maqueta (de maqueta-base.toml), para las reglas con «estilo».
var ESTILOS = { caracter: {}, por_grupo: {} };

function procesar(d, reglas, aplicar) {
    var lineas = [], total = 0, errores = [];
    for (var r = 0; r < reglas.length; r++) {
        var rg = reglas[r];
        if (rg.tipo == "ladillos_seguidos") {
            var pares = ladillosPendientes(d, rg), ej = [];
            for (var i = 0; i < pares.length; i++) {
                if (DETALLE || ej.length < 3)
                    ej.push("      " + pares[i][0].contents.replace(/\r/g, "") + "  ⟂  " + pares[i][1].contents.replace(/\r/g, ""));
                if (aplicar) { pares[i][0].spaceAfter = 0; pares[i][1].spaceBefore = 0; }
            }
            if (pares.length) { total += pares.length; lineas.push("   " + rg.nombre + ": " + pares.length + "\n" + ej.join("\n")); }
            continue;
        }
        var hs = hallazgos(d, rg, ESTILOS);
        if (!hs.length) continue;
        total += hs.length;
        var ej = [];
        for (var i = 0; i < (DETALLE ? hs.length : Math.min(3, hs.length)); i++) ej.push("      " + contexto(hs[i].t).replace(/\r/g, " "));
        lineas.push("   " + rg.nombre + ": " + hs.length + "\n" + ej.join("\n"));
        if (aplicar && rg.estilo) {
            for (var i = 0; i < hs.length; i++) {
                try { hs[i].t.appliedCharacterStyle = hs[i].ec; }
                catch (e) { errores.push(rg.nombre + ": " + e); }
            }
        } else if (aplicar) {
            // Se cambia el párrafo entero de cada hallazgo, no el fragmento: con un fragmento
            // suelto, las reglas que miran alrededor ((?<=\d), (?=…)) ya no encuentran nada.
            // De atrás adelante para que los cambios no muevan los párrafos pendientes.
            var pars = [], vistos = {};
            for (var i = 0; i < hs.length; i++) {
                // En las tablas el índice cuenta desde el principio de cada celda: la clave lleva
                // el contenedor (la historia o la celda), si no se pierden párrafos de otras celdas.
                var p = hs[i].t.paragraphs[0], cont = p.parent.toSpecifier(), clave = cont + ":" + p.index;
                if (!vistos[clave]) { vistos[clave] = 1; pars.push({ p: p, cont: cont, i: p.index }); }
            }
            pars.sort(function (a, b) { return a.cont < b.cont ? -1 : a.cont > b.cont ? 1 : b.i - a.i; });
            opcionesGrep();
            app.findGrepPreferences = NothingEnum.NOTHING;
            app.changeGrepPreferences = NothingEnum.NOTHING;
            app.findGrepPreferences.findWhat = rg.buscar;
            app.changeGrepPreferences.changeTo = rg.cambiar;
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
