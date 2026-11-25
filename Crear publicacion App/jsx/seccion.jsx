// Marcador y prefijo de la primera sección de un documento abierto (la cornisa suele tomarlos)
// y, si la publicación tiene partes, la variable de texto con el título de la parte.
// Argumentos: [0] nombre del documento, [1] "leer" | "poner".
//   leer:  [2] nombre de la variable (opcional)
//   poner: [2] marcador, [3] prefijo, [4] nombre de la variable (opcional), [5] su texto
// Devuelve «|marcador<TAB>prefijo<TAB>incluir prefijo (true/false)<TAB>texto de la variable<TAB>
// estado de la variable» (estado: «ok», «falta» si no existe, «otra» si no es de texto
// personalizado, vacío si no se pidió), entre «|». «poner» no toca la numeración de páginas (cambiar el
// marcador la reinicia en 1: se restaura) y deja todo en un solo paso de deshacer.

var ARGS = arguments;      // dentro de una función, «arguments» son los de la función

function variable(d, nombre) {
    if (!nombre) return null;
    var v = d.textVariables.itemByName(nombre);
    return v.isValid ? v : false;
}

function estadoVariable(v) {
    if (v === null) return ["", ""];
    if (v === false) return ["", "falta"];
    if (v.variableType != VariableTypes.CUSTOM_TEXT_TYPE) return ["", "otra"];
    return [v.variableOptions.contents, "ok"];
}

(function () {
    var d = app.documents.itemByName(ARGS[0]);
    if (!d.isValid) return "ERROR: «" + ARGS[0] + "» no está abierto en InDesign";
    var s = d.sections[0], v;
    if (ARGS[1] == "poner") {
        v = variable(d, ARGS[4]);
        if (v === false) return "ERROR: «" + ARGS[0] + "» no tiene la variable de texto «" + ARGS[4] + "»";
        app.doScript(function () {
            var seguir = s.continueNumbering, inicio = s.pageNumberStart;
            if (s.marker != ARGS[2]) s.marker = ARGS[2];
            if (s.sectionPrefix != ARGS[3]) s.sectionPrefix = ARGS[3];
            s.continueNumbering = seguir;
            if (!seguir) s.pageNumberStart = inicio;
            if (v && v.variableType == VariableTypes.CUSTOM_TEXT_TYPE && v.variableOptions.contents != ARGS[5])
                v.variableOptions.contents = ARGS[5];
        }, ScriptLanguage.JAVASCRIPT, [], UndoModes.ENTIRE_SCRIPT, "Sección del capítulo");
    } else {
        v = variable(d, ARGS[2]);
    }
    // Entre «|» para que los tabuladores de los extremos (campos vacíos) no se pierdan al leerlo
    return "|" + [s.marker, s.sectionPrefix, s.includeSectionPrefix].concat(estadoVariable(v)).join("\t") + "|";
})();
