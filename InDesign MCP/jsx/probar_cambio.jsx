// Prueba ARGS.aplicar (cuerpo de función (obj, doc)) sobre los objetos de ARGS.refs:
// aplica el cambio, anota el antes y el después, y lo deshace en el acto.
if (app.documents.length === 0) throw new Error("No hay ningún documento abierto");
function docDe(o) {  // documento al que pertenece o (puede no ser el activo)
    while (o && o.constructor.name !== "Document" && o.constructor.name !== "Application") o = o.parent;
    return o && o.constructor.name === "Document" ? o : app.activeDocument;
}
try { var fAplicar = new Function("obj", "doc", ARGS.aplicar); }
catch (e) { return json({__error: "Error de sintaxis en `aplicar`: " + e.message}); }

function esTexto(o) {  // texto (no un marco: TextFrame también tiene parentStory e index)
    return o.hasOwnProperty("parentStory") && o.hasOwnProperty("index") && o.hasOwnProperty("length") && !(o instanceof TextFrame);
}
function contenedor(t) { return t.parent instanceof Cell ? t.parent : t.parentStory; }
function contexto(cont, ini, fin) {
    var total = cont.texts[0].length, a = Math.max(0, ini - 40), b = Math.min(total, fin + 40);
    function trozo(x, y) { return y > x ? cont.characters.itemByRange(x, y - 1).contents : ""; }
    return (a > 0 ? "…" : "") + trozo(a, ini) + "⟦" + trozo(ini, fin) + "⟧" + trozo(fin, b) + (b < total ? "…" : "");
}
function describir(o) {
    var t = o.constructor.name;
    try { t += " " + o.fillColor.name + ", " + (o.hasOwnProperty("contents") ? String(o.contents).slice(0, 80) : ""); } catch (_) {}
    return t;
}

var salida = [];
for (var i = 0; i < ARGS.refs.length && i < 5; i++) {
    var o, r = {ref: ARGS.refs[i]};
    try { o = resolve(ARGS.refs[i]); } catch (_) {}
    if (!o || !o.isValid) { r.error = "No existe"; salida.push(r); continue; }
    var texto = esTexto(o), cont = texto ? contenedor(o) : null;
    var ini = texto ? o.index : 0, fin = texto ? o.index + o.length : 0, largo = texto ? cont.texts[0].length : 0;
    r.antes = texto ? contexto(cont, ini, fin) : describir(o);
    var doc = docDe(o), pasos = doc.undoHistory.length, fallo = null;
    app.doScript(function () {
        try { fAplicar(o, doc); } catch (e) { fallo = e; }
    }, ScriptLanguage.JAVASCRIPT, undefined, UndoModes.ENTIRE_SCRIPT, "Prueba de Claude (no rehacer)");
    if (!fallo) {
        try { r.despues = texto ? contexto(cont, ini, fin + cont.texts[0].length - largo) : describir(o); }
        catch (e) { r.despues = "(no se puede describir: " + e.message + ")"; }
        if (texto) try { r.estilo_despues = o.isValid ? o.appliedFont.name + " / " + o.fontStyle : null; } catch (_) {}
    } else r.error = (fallo.message || String(fallo)) + " (línea " + (fallo.line - 1) + " de `aplicar`)";
    if (doc.undoHistory.length > pasos) doc.undo();
    else if (!fallo) r.aviso = "El cambio no modificó nada";
    salida.push(r);
}
return json(salida);
