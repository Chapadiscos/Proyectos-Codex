// Ejecuta ARGS.codigo sin modificar el documento: si el código cambia algo, se deshace y falla.
// `doc` es ARGS.documento o, si no se indica, el documento activo.
// El código recibe doc y estas ayudas:
//   pagina(o)   → nombre de la página donde está o (texto u objeto), o null si está fuera
//   ref(o)      → referencia para volver a encontrar o después (o.toSpecifier())
//   contexto(t) → texto alrededor de t, con t marcado entre ⟦ ⟧
if (app.documents.length === 0) throw new Error("No hay ningún documento abierto");
// ARGS.documento: nombre de un documento abierto (también los abiertos sin ventana); vacío = el activo.
var doc = app.activeDocument;
if (ARGS.documento) {
    doc = null;
    var nombres = [];
    for (var i = 0; i < app.documents.length; i++) {
        nombres.push(app.documents[i].name);
        if (app.documents[i].name === ARGS.documento) doc = app.documents[i];
    }
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
