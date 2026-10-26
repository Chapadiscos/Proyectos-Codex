// Marca con texto condicional las dudas ortotipográficas del bloque 2.
// Argumentos: [dudas.json, nombre del documento].
// dudas.json: {condiciones: {tipo: [nombre, color de UIColors]}, dudas: [{spec, inicio, fin, tipo}]}
// Antes de marcar se borran las condiciones de una pasada anterior (el texto se queda), así
// se puede repetir. Todo en un paso de deshacer.

#target indesign

var ARGS = (typeof arguments != "undefined") ? arguments : [];

function leerJSON(ruta) {
    var f = File(ruta);
    f.encoding = "UTF-8";
    f.open("r");
    var t = f.read();
    f.close();
    return eval("(" + t + ")");
}

function marcar(d, datos) {
    var conds = {}, n = {}, errores = [];
    // Se borran las de una pasada anterior y se crean solo las de los tipos que tienen dudas.
    var hay = {};
    for (var i = 0; i < datos.dudas.length; i++) hay[datos.dudas[i].tipo] = 1;
    for (var tipo in datos.condiciones) {
        var nombre = datos.condiciones[tipo][0], c = d.conditions.itemByName(nombre);
        if (c.isValid) c.remove();
        n[tipo] = 0;
        if (hay[tipo]) conds[tipo] = d.conditions.add({ name: nombre, indicatorMethod: ConditionIndicatorMethod.USE_HIGHLIGHT,
                                                        indicatorColor: UIColors[datos.condiciones[tipo][1]] });
    }
    for (var i = 0; i < datos.dudas.length; i++) {
        var du = datos.dudas[i];
        try {
            var p = resolve(du.spec);
            p.characters.itemByRange(du.inicio, du.fin - 1).applyConditions([conds[du.tipo]], false);
            n[du.tipo]++;
        } catch (e) { errores.push(du.tipo + " «" + du.texto + "»: " + e); }
    }
    try { d.conditionalTextPreferences.showConditionIndicators = ConditionIndicatorMode.SHOW_INDICATORS; } catch (e) {}
    var r = [];
    for (var tipo in n) if (n[tipo]) r.push(datos.condiciones[tipo][0] + " " + n[tipo]);
    return d.name + ": " + (r.length ? r.join(" · ") : "ninguna duda") +
        (errores.length ? "\n   ERRORES (" + errores.length + "): " + errores.slice(0, 3).join(" · ") : "");
}

function principal() {
    var datos = leerJSON(ARGS[0]), d = app.documents.itemByName(ARGS[1]);
    if (!d.isValid) return "ERROR: no está abierto " + ARGS[1];
    var res;
    app.doScript(function () { res = marcar(d, datos); }, ScriptLanguage.JAVASCRIPT, undefined,
                 UndoModes.ENTIRE_SCRIPT, "Marcar dudas ortotipográficas");
    return res;
}

app.scriptPreferences.userInteractionLevel = UserInteractionLevels.NEVER_INTERACT;
var resultado;
try { resultado = principal(); }
catch (e) { resultado = "ERROR: " + e + " (línea " + e.line + ")"; }
finally { app.scriptPreferences.userInteractionLevel = UserInteractionLevels.INTERACT_WITH_ALL; }
resultado;
