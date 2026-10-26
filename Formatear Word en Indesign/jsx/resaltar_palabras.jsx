// Resalta con texto condicional las palabras de una lista (Tabla, Figura, Algoritmo…), para ver
// dónde se cita cada elemento al colocarlo. Sustituye al script «Resaltar palabras (lista).jsx»
// y a su archivo risk-words.txt: la lista está en [resaltar] de la configuración de la publicación.
// Argumentos: [palabras separadas por «|», nombre del documento, nombre de la condición,
// color de UIColors].
// La condición se borra y se vuelve a crear con sus mismas propiedades: así una palabra quitada
// de la lista deja de estar resaltada. Las demás condiciones del texto («Duda …», «Revisar …»)
// se conservan. Todo en un paso de deshacer.

#target indesign

var ARGS = (typeof arguments != "undefined") ? arguments : [];

function condicion(d, nombre, color) {
    var c = d.conditions.itemByName(nombre), props;
    if (c.isValid) {
        props = c.properties;
        c.remove();             // quita el resaltado de todo el texto de una vez
        delete props.id; delete props.index; delete props.parent;
    } else {
        props = { name: nombre, indicatorMethod: ConditionIndicatorMethod.USE_HIGHLIGHT, indicatorColor: UIColors[color] };
    }
    d.conditionalTextPreferences.showConditionIndicators = ConditionIndicatorMode.SHOW_INDICATORS;
    return d.conditions.add(props);
}

function resaltar(d, palabras, c) {
    var n = 0;
    app.findTextPreferences = NothingEnum.NOTHING;
    app.findChangeTextOptions = NothingEnum.NOTHING;
    app.findChangeTextOptions.caseSensitive = false;
    app.findChangeTextOptions.wholeWord = true;
    app.findChangeTextOptions.includeFootnotes = true;
    app.findChangeTextOptions.includeMasterPages = false;
    app.findChangeTextOptions.includeLockedStoriesForFind = false;
    for (var i = 0; i < palabras.length; i++) {
        app.findTextPreferences.findWhat = palabras[i].replace(/\^/g, "^^");
        var h = d.findText();
        // false: se añade a las condiciones que ya tenga el texto, no las sustituye.
        for (var k = h.length - 1; k >= 0; k--) { h[k].applyConditions([c], false); n++; }
    }
    app.findTextPreferences = NothingEnum.NOTHING;
    app.findChangeTextOptions = NothingEnum.NOTHING;
    return n;
}

function principal() {
    var palabras = ARGS[0].split("|");
    if (!ARGS[0]) return "ERROR: no hay palabras que resaltar";
    var d = app.documents.itemByName(ARGS[1]);
    if (!d.isValid) return "ERROR: no está abierto " + ARGS[1];
    var n;
    app.doScript(function () { n = resaltar(d, palabras, condicion(d, ARGS[2], ARGS[3])); },
                 ScriptLanguage.JAVASCRIPT, undefined, UndoModes.ENTIRE_SCRIPT, "Resaltar palabras de la lista");
    return d.name + ": " + n + " palabras resaltadas con «" + ARGS[2] + "»";
}

app.scriptPreferences.userInteractionLevel = UserInteractionLevels.NEVER_INTERACT;
var resultado;
try { resultado = principal(); }
catch (e) { resultado = "ERROR: " + e + " (línea " + e.line + ")"; }
finally { app.scriptPreferences.userInteractionLevel = UserInteractionLevels.INTERACT_WITH_ALL; }
resultado;
