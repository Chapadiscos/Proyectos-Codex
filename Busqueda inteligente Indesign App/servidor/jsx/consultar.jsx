// Ejecuta ARGS.codigo sin modificar el documento: si el código cambia algo, se deshace y falla.
// `doc` es ARGS.documento o, si no se indica, el documento activo.
// El código recibe doc y estas ayudas:
//   pagina(o)   → nombre de la página donde está o (texto u objeto), o null si está fuera
//   ref(o)      → referencia para volver a encontrar o después (o.toSpecifier())
//   contexto(t) → texto alrededor de t, con t marcado entre ⟦ ⟧
if (app.documents.length === 0) throw new Error("No hay ningún documento abierto");
// ARGS.documento: nombre de un documento abierto (también los abiertos sin ventana); vacío = el activo.
// Con todos los documentos sin ventana, app.activeDocument falla: solo se pide si no se indica otro
var doc = null;
if (!ARGS.documento) {
    if (app.layoutWindows.length === 0) throw new Error("No hay documento activo (todos están sin ventana): indica documento");
    doc = app.activeDocument;
} else {
    // Los nombres que vienen del disco llevan las tildes descompuestas («i» + U+0301) y Claude las escribe
    // compuestas («í»): se ven iguales pero no lo son. Se comparan sin tildes ni mayúsculas.
    var plano = function (t) {
        var de = "áàâäãåéèêëíìîïóòôöõúùûüñçÁÀÂÄÃÅÉÈÊËÍÌÎÏÓÒÔÖÕÚÙÛÜÑÇ", a = "aaaaaaeeeeiiiiooooouuuuncaaaaaaeeeeiiiiooooouuuunc", r = "";
        t = String(t).replace(/[\u0300-\u036f]/g, "");
        for (var k = 0; k < t.length; k++) { var x = de.indexOf(t.charAt(k)); r += x < 0 ? t.charAt(k).toLowerCase() : a.charAt(x); }
        return r;
    };
    doc = null;
    var nombres = [], buscado = plano(ARGS.documento);
    for (var i = 0; i < app.documents.length; i++) {
        nombres.push(app.documents[i].name);
        if (app.documents[i].name === ARGS.documento) doc = app.documents[i];
    }
    for (i = 0; i < app.documents.length && !doc; i++) if (plano(app.documents[i].name) === buscado) doc = app.documents[i];
    if (!doc) throw new Error("No está abierto «" + ARGS.documento + "». Abiertos: " + nombres.join(", "));
}

function pagina(o) {
    try {
        if (o.hasOwnProperty("parentTextFrames")) {
            var m = o.parentTextFrames;
            return m.length && m[0].parentPage ? m[0].parentPage.name : null;
        }
        return o.parentPage ? o.parentPage.name : null;
    } catch (_) { return null; }
}
function ref(o) { return o.toSpecifier(); }
function contexto(t, n) {
    n = n || 50;
    var cont = t.parent instanceof Cell ? t.parent : t.parentStory;
    var total = cont.texts[0].length, ini = t.index, fin = t.index + t.length;
    var a = Math.max(0, ini - n), b = Math.min(total, fin + n);
    function trozo(x, y) { return y > x ? cont.characters.itemByRange(x, y - 1).contents : ""; }
    return (a > 0 ? "…" : "") + trozo(a, ini) + "⟦" + trozo(ini, fin) + "⟧" + trozo(fin, b) + (b < total ? "…" : "");
}

try { var cuerpo = new Function("doc", "pagina", "ref", "contexto", ARGS.codigo); }
catch (e) { return json({__error: "Error de sintaxis en el código: " + e.message}); }

var pasos = doc.undoHistory.length, resultado, fallo = null;
try { resultado = cuerpo(doc, pagina, ref, contexto); } catch (e) { fallo = e; }
if (doc.undoHistory.length > pasos) {
    while (doc.undoHistory.length > pasos) doc.undo();
    return json({__error: "El código modificó el documento y se ha deshecho: consultar es solo de lectura"});
}
if (fallo) return json({__error: (fallo.message || String(fallo)) + " (línea " + (fallo.line - 1) + " del código)"});
return json({resultado: resultado});
