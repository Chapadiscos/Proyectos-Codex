// Cierre de un capítulo ya corregido (Ventana > Formatear Word > Finalizar capítulo):
// 1. Puntuación: la que va pegada a una palabra toma su formato («(Fusarium)», «Epiescleritis.»,
//    «»),», «Fusarium/Aspergillus»). Sustituye al script «Formatear puntuaciones».
// 2. URLs (http://…, https://…, www.…) y DOI («doi: 10.1016/…», enlazado a https://doi.org/…)
//    → hipervínculos, sin tocar su formato ni su estilo de carácter y sin borde visible. La
//    puntuación final («…html).») queda fuera del enlace; lo que ya es hipervínculo no se toca.
// Qué cambia y cómo, en cierre_comun.jsx (lo comparte con la ventana «Revisar cierre»).
// Argumentos: [datos.json, "simular" | "aplicar", nombre del documento (opcional: todos los
// «Capitulo…» abiertos), "detalle" (opcional)]. datos.json: {excluir: [estilos de carácter que
// no pasan a la puntuación: superíndice, símbolos]}. Al aplicar, un paso de deshacer por documento.

#target indesign

var ARGS = (typeof arguments != "undefined") ? arguments : [];
var DETALLE = ARGS.length > 3 && ARGS[3] == "detalle";

#include "cierre_comun.jsx"

function leerJSON(ruta) {
    var f = File(ruta);
    f.encoding = "UTF-8";
    f.open("r");
    var t = f.read();
    f.close();
    return eval("(" + t + ")");
}

// Ejemplos para el resumen: la puntuación con su contexto y su formato nuevo; los enlaces con
// su destino.
function ejemplo(c) {
    if (c.tipo != "puntuacion") return "      " + c.texto + (c.destino != c.texto ? " \u2192 " + c.destino : "");
    var txt = String(c.cont.contents), a = Math.max(0, c.ini - 20), b = Math.min(txt.length, c.ini + 4);
    return "      \u2026" + txt.substring(a, c.ini).replace(/\r/g, " ") + "[" + c.texto + "]" +
           txt.substring(c.ini + 1, b).replace(/\r/g, " ") + "\u2026 \u2192 " + c.fw.nombre +
           (c.fw.fuente != c.actual.fuente && c.fw.nombre == "[Ninguno]" ? " (" + c.fw.fuente + ")" : "");
}

// Cada grupo se busca justo antes de aplicarlo (como siempre): un enlace de URL ya hecho no se
// vuelve a enlazar como DOI.
function grupo(d, cambios, aplicar, ejemplos) {
    var n = 0;
    for (var i = 0; i < cambios.length; i++) {
        var c = cambios[i];
        if (ejemplos.length < (DETALLE ? 1000 : 4)) ejemplos.push(ejemplo(c));
        if (aplicar) {
            try { aplicarCierre(d, c); }
            catch (e) { ejemplos.push("      NO SE PUDO: " + c.texto + ": " + e); continue; }
        }
        n++;
    }
    return n;
}

function procesar(d, datos, aplicar) {
    var ejP = [], ejU = [], ejD = [];
    var nP = grupo(d, cambiosPuntuacion(d, datos.excluir), aplicar, ejP);
    var nU = grupo(d, cambiosEnlace(d, "url"), aplicar, ejU);
    var nD = grupo(d, cambiosEnlace(d, "doi"), aplicar, ejD);
    var verbo = aplicar ? "" : " posibles";
    function linea(t, n, ej) { return "\n   " + t + ": " + n + verbo + (ej.length ? "\n" + ej.join("\n") : ""); }
    return "== " + d.name + linea("Puntuaci\u00f3n con el estilo de su palabra", nP, ejP) +
        linea("URLs \u2192 hiperv\u00ednculos", nU, ejU) + linea("DOI \u2192 hiperv\u00ednculos", nD, ejD);
}

function principal() {
    var datos = leerJSON(ARGS[0]), aplicar = ARGS[1] == "aplicar", nombre = ARGS[2] || "";
    var docs = [];
    for (var i = 0; i < app.documents.length; i++) {
        var n = app.documents[i].name;
        if (nombre ? n == nombre : n.indexOf("Capitulo") == 0) docs.push(n);
    }
    if (!docs.length) return "ERROR: no hay documentos abiertos" + (nombre ? " con el nombre " + nombre : " «Capitulo…»");
    var res = [];
    for (var i = 0; i < docs.length; i++) {
        var d = app.documents.itemByName(docs[i]);
        if (aplicar) {
            var s;
            app.doScript(function () { s = procesar(d, datos, true); }, ScriptLanguage.JAVASCRIPT, undefined,
                         UndoModes.ENTIRE_SCRIPT, "Finalizar capítulo");
            res.push(s);
        } else res.push(procesar(d, datos, false));
    }
    return res.join("\n\n");
}

app.scriptPreferences.userInteractionLevel = UserInteractionLevels.NEVER_INTERACT;
var resultado;
try { resultado = principal(); }
catch (e) { resultado = "ERROR: " + e + " (línea " + e.line + ")"; }
finally { app.scriptPreferences.userInteractionLevel = UserInteractionLevels.INTERACT_WITH_ALL; }
resultado;
