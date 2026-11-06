// Marcador y prefijo de la primera sección de un documento abierto (la cornisa suele tomarlos).
// Argumentos: [0] nombre del documento, [1] "leer" | "poner", [2] marcador, [3] prefijo.
// «leer» devuelve «marcador<TAB>prefijo<TAB>incluir prefijo (true/false)»; «poner» los cambia
// sin tocar la numeración de páginas (cambiar el marcador la reinicia en 1: se restaura).

var ARGS = arguments;      // dentro de una función, «arguments» son los de la función

(function () {
    var d = app.documents.itemByName(ARGS[0]);
    if (!d.isValid) return "ERROR: «" + ARGS[0] + "» no está abierto en InDesign";
    var s = d.sections[0];
    if (ARGS[1] == "poner") {
        var seguir = s.continueNumbering, inicio = s.pageNumberStart;
        s.marker = ARGS[2];
        s.sectionPrefix = ARGS[3];
        s.continueNumbering = seguir;
        if (!seguir) s.pageNumberStart = inicio;
    }
    return s.marker + "\t" + s.sectionPrefix + "\t" + s.includeSectionPrefix;
})();
