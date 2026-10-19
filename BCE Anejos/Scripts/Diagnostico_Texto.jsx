#target illustrator
// Herramienta de diagnóstico: NO modifica nada. Lista los textos del ámbito actual
// (selección, o capa activa si no hay selección) mostrando su contenido exacto,
// incluyendo caracteres no imprimibles como códigos \uXXXX, para averiguar por qué
// "Q1", "Q3" o "Mar." no coinciden con las búsquedas del script.
// También indica en qué capa/grupo está cada texto y si está bloqueado u oculto.

function main() {
    if (app.documents.length === 0) {
        alert("Abre primero el documento de Illustrator.");
        return;
    }
    var doc = app.activeDocument;

    function escapeVisible(s) {
        var out = "";
        for (var i = 0; i < s.length; i++) {
            var code = s.charCodeAt(i);
            var ch = s.charAt(i);
            if (ch === "\r") out += "\\r";
            else if (ch === "\n") out += "\\n";
            else if (ch === "\t") out += "\\t";
            else if (code === 0x00A0) out += "\\u00A0(NBSP)";
            else if (code < 0x20 || code > 0x7E) out += "\\u" + ("0000" + code.toString(16)).slice(-4);
            else out += ch;
        }
        return out;
    }

    function collectTextFrames(items, out, pathLabel) {
        for (var i = 0; i < items.length; i++) {
            var it = items[i];
            var loc = pathLabel + "/" + it.typename + "[" + i + "]";
            if (it.typename === "TextFrame") {
                out.push({ frame: it, loc: loc });
            } else if (it.typename === "GroupItem") {
                collectTextFrames(it.pageItems, out, loc);
            }
        }
    }

    var scopeItems;
    var scopeDesc;
    if (doc.selection && doc.selection.length > 0) {
        scopeItems = doc.selection;
        scopeDesc = "la selección actual (" + doc.selection.length + " objetos raíz)";
    } else {
        scopeItems = doc.activeLayer.pageItems;
        scopeDesc = "la capa activa (\"" + doc.activeLayer.name + "\")";
    }

    var found = [];
    collectTextFrames(scopeItems, found, "root");

    if (found.length === 0) {
        alert("No se encontró ningún TextFrame en " + scopeDesc + ".\n" +
              "(Si el PDF se colocó como imagen/objeto vinculado en vez de texto editable, " +
              "el script no podría tocarlo aunque Buscar y reemplazar sí funcione desde Illustrator.)");
        return;
    }

    var msg = "Encontrados " + found.length + " TextFrame(s) en " + scopeDesc + ":\n\n";
    for (var f = 0; f < found.length; f++) {
        var tf = found[f].frame;
        var raw = tf.contents;
        var hasQ13 = (raw.indexOf("Q1") !== -1) || (raw.indexOf("Q3") !== -1);
        var hasMar = raw.indexOf("Mar") !== -1;
        msg += "--- #" + (f + 1) + " " + found[f].loc +
               "  locked=" + tf.locked + " hidden=" + tf.hidden +
               " top=" + Math.round(tf.top) +
               (hasQ13 ? "  [contiene Q1/Q3]" : "") +
               (hasMar ? "  [contiene Mar]" : "") + " ---\n";
        msg += escapeVisible(raw.length > 200 ? raw.substring(0, 200) + "..." : raw) + "\n\n";
    }

    alert(msg);
}

main();
