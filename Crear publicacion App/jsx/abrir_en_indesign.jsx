// Abre una ventana del motor «Formatear Word» (Revisar correcciones, Revisar dudas, Recorrer
// marcas) a petición de la app Crear Publicación, en el mismo motor persistente que usa la
// ventana de InDesign, para que las dos compartan las ventanas abiertas.
// Argumentos: [0] el .jsx del motor, [1] el documento que se activa antes (vacío = el activo),
// [2] el .toml de la publicación (lo lee «Revisar correcciones»).

#targetengine "formatear_word"

(function () {
    var jsx = File(arguments[0]), nombre = arguments[1], publicacion = arguments[2];
    if (!jsx.exists) return "No encuentro " + jsx.fsName;
    if (nombre) {
        var d = app.documents.itemByName(nombre);
        if (!d.isValid) return "«" + nombre + "» ya no está abierto en InDesign";
        app.activeDocument = d;
    }
    if (publicacion) $.global.formatearWordPublicacion = publicacion;
    $.evalFile(jsx);
    return "ok";
})();
