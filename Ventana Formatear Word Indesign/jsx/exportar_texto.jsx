// Exporta el texto de un documento abierto para revisarlo fuera de InDesign (bloque 2).
// Argumentos: [salida.json, nombre del documento].
// Cada párrafo: {spec, estilo, texto, cursiva: [[inicio, fin], ...]}. «spec» es el
// especificador del párrafo, para volver a él con resolve() y marcar las dudas; vale mientras
// no cambie el texto (marcar con condiciones no lo cambia).

#target indesign

var ARGS = (typeof arguments != "undefined") ? arguments : [];

function rutaEstilo(est) {
    var r = est.name, p = est.parent;
    while (p && p.constructor && p.constructor.name == "ParagraphStyleGroup") { r = p.name + "/" + r; p = p.parent; }
    return r;
}

// ExtendScript no tiene JSON.
function cadena(s) {
    return '"' + String(s).replace(/\\/g, "\\\\").replace(/"/g, '\\"').replace(/\r/g, "\\r")
        .replace(/\n/g, "\\n").replace(/\t/g, "\\t").replace(/[\u0000-\u001F\u2028\u2029]/g, function (c) {
            return "\\u" + ("000" + c.charCodeAt(0).toString(16)).slice(-4);
        }) + '"';
}

function esCursiva(r) {
    var n = "";
    try { n = r.appliedCharacterStyle.name + " " + r.fontStyle; } catch (e) {}
    return /Italic|Cursiva|Oblique/i.test(n);
}

function parrafo(p) {
    var texto = p.contents.replace(/\r$/, ""), cursiva = [], ini = 0;
    var rs = p.textStyleRanges.everyItem().getElements();
    for (var i = 0; i < rs.length; i++) {
        var n = rs[i].contents.length;
        if (esCursiva(rs[i])) cursiva.push("[" + ini + "," + Math.min(ini + n, texto.length) + "]");
        ini += n;
    }
    var est = "";
    try { est = rutaEstilo(p.appliedParagraphStyle); } catch (e) {}
    return "{\"spec\":" + cadena(p.toSpecifier()) + ",\"estilo\":" + cadena(est) + ",\"texto\":" + cadena(texto) +
        ",\"cursiva\":[" + cursiva.join(",") + "]}";
}

function principal() {
    var d = app.documents.itemByName(ARGS[1]);
    if (!d.isValid) return "ERROR: no está abierto " + ARGS[1];
    var out = [];
    for (var s = 0; s < d.stories.length; s++) {
        var st = d.stories[s], ps = st.paragraphs.everyItem().getElements();
        for (var i = 0; i < ps.length; i++) out.push(parrafo(ps[i]));
        for (var t = 0; t < st.tables.length; t++) {
            var cs = st.tables[t].cells.everyItem().getElements();
            for (var c = 0; c < cs.length; c++) {
                var pc = cs[c].paragraphs.everyItem().getElements();
                for (var k = 0; k < pc.length; k++) out.push(parrafo(pc[k]));
            }
        }
    }
    var f = File(ARGS[0]);
    f.encoding = "UTF-8";
    f.open("w");
    f.write("[\n" + out.join(",\n") + "\n]");
    f.close();
    return out.length + " párrafos";
}

var resultado;
try { resultado = principal(); }
catch (e) { resultado = "ERROR: " + e + " (línea " + e.line + ")"; }
resultado;
