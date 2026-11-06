// Abre una ventana del motor «Formatear Word» (Revisar correcciones, Revisar dudas, Recorrer
// marcas) a petición de la app Crear Publicación, en el mismo motor persistente que usa la
// ventana de InDesign, para que las dos compartan las ventanas abiertas.
// Devuelve «ok» o, si la ventana lo apunta (Recorrer marcas), «ok N» con lo que ha encontrado.
// Argumentos: [0] el .jsx del motor, [1] el documento que se activa antes (vacío = el activo),
// [2] el .toml de la publicación (lo lee «Revisar correcciones»).

#targetengine "formatear_word"

var ARGS = arguments;      // dentro de una función, «arguments» son los de la función

(function () {
    var jsx = File(ARGS[0]), nombre = ARGS[1], publicacion = ARGS[2];
    if (!jsx.exists) return "No encuentro " + jsx.fsName;
    if (nombre) {
        var d = app.documents.itemByName(nombre);
        if (!d.isValid) return "«" + nombre + "» ya no está abierto en InDesign";
        app.activeDocument = d;
    }
    if (publicacion) $.global.formatearWordPublicacion = publicacion;
    $.global.formatearWordCuenta = undefined;
    $.evalFile(jsx);
    // «Recorrer marcas» deja cuántas ha encontrado: con 0 la app da el paso por hecho
    var n = $.global.formatearWordCuenta;
    return n === undefined ? "ok" : "ok " + n;
})();
