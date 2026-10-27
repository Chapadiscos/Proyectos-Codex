// Maqueta de una publicación a partir de su último InDesign maquetado (nueva_publicacion.py).
// Argumentos: [maquetado.indd, maqueta.indd de destino, estilos.json de salida].
// Sin destino solo lee la maqueta (para compararla con una nueva al actualizar la publicación):
// no la cambia y, si está abierta, no la cierra.
// La copia se queda con dos páginas vacías: la primera (maestra de inicio de capítulo o
// artículo) y una de interior, con un marco de texto por columna dentro de los márgenes y
// todos enlazados; importar.jsx coloca ahí el texto y repite la de interior lo que haga falta.
// Estilos, muestras, maestras y variables se quedan como en el maquetado. En estilos.json
// van los nombres de los estilos y las medidas de la página, para proponer la configuración.

#target indesign

var ARGS = (typeof arguments != "undefined") ? arguments : [];

// «Grupo/Subgrupo/Estilo», como en la configuración: la barra del propio nombre va con «\».
function ruta(e) {
    function n(x) { return x.name.replace(/\//g, "\\/"); }
    var r = n(e), p = e.parent;
    while (p && p.constructor && /Group$/.test(p.constructor.name)) { r = n(p) + "/" + r; p = p.parent; }
    return r;
}

function json(v) {
    if (v === null || v === undefined) return "null";
    if (typeof v == "number" || typeof v == "boolean") return String(v);
    if (typeof v == "string") {
        var s = "";
        for (var i = 0; i < v.length; i++) {
            var c = v.charAt(i), n = v.charCodeAt(i);
            if (c == '"' || c == "\\") s += "\\" + c;
            else if (n < 32) s += "\\u" + ("000" + n.toString(16)).slice(-4);
            else s += c;
        }
        return '"' + s + '"';
    }
    var a = [];
    if (v instanceof Array) {
        for (var i = 0; i < v.length; i++) a.push(json(v[i]));
        return "[" + a.join(",") + "]";
    }
    for (var k in v) if (v.hasOwnProperty(k)) a.push(json(k) + ":" + json(v[k]));
    return "{" + a.join(",") + "}";
}

function nombres(col) {
    var a = [];
    for (var i = 0; i < col.length; i++) a.push(ruta(col[i]));
    return a;
}

// Medidas de la página: la caja de texto y sus columnas.
function medidas(pg) {
    var b = pg.bounds, mp = pg.marginPreferences, n = Math.max(1, mp.columnCount);
    var texto = b[3] - b[1] - mp.left - mp.right;
    return { ancho: b[3] - b[1], alto: b[2] - b[0], columnas: mp.columnCount, medianil: mp.columnGutter,
             ancho_columna: (texto - (n - 1) * mp.columnGutter) / n, ancho_texto: texto };
}

function estilos(d, info) {
    info.parrafo = nombres(d.allParagraphStyles);
    info.caracter = nombres(d.allCharacterStyles);
    info.objeto = nombres(d.allObjectStyles);
    info.tabla = nombres(d.allTableStyles);
    info.celda = nombres(d.allCellStyles);
    info.condiciones = nombres(d.conditions);
}

// Marcos de las columnas de la página, dentro de los márgenes (en páginas enfrentadas, el
// margen «left» es el interior: en una página par va a la derecha).
function marcosColumnas(pg) {
    var b = pg.bounds, mp = pg.marginPreferences;
    var izq = mp.left, der = mp.right;
    if (pg.side == PageSideOptions.LEFT_HAND) { izq = mp.right; der = mp.left; }
    var x0 = b[1] + izq, x1 = b[3] - der, y0 = b[0] + mp.top, y1 = b[2] - mp.bottom;
    var n = Math.max(1, mp.columnCount), g = mp.columnGutter, w = (x1 - x0 - (n - 1) * g) / n, res = [];
    for (var c = 0; c < n; c++) {
        var x = x0 + c * (w + g);
        res.push(pg.textFrames.add({ geometricBounds: [y0, x, y1, x + w] }));
    }
    return res;
}

function crear(origen, destino) {
    if (!origen.exists) return "ERROR: no existe " + origen.fsName;
    if (destino.exists) destino.remove();
    if (!origen.copy(destino)) return "ERROR: no se pudo copiar a " + destino.fsName;
    app.scriptPreferences.userInteractionLevel = UserInteractionLevels.NEVER_INTERACT;
    var d;
    try { d = app.open(destino, false); }
    finally { app.scriptPreferences.userInteractionLevel = UserInteractionLevels.INTERACT_WITH_ALL; }
    var info = {};
    try {
        d.viewPreferences.horizontalMeasurementUnits = MeasurementUnits.MILLIMETERS;
        d.viewPreferences.verticalMeasurementUnits = MeasurementUnits.MILLIMETERS;
        app.scriptPreferences.measurementUnit = MeasurementUnits.MILLIMETERS;

        // La primera página es la de inicio; la de interior, la primera con otra maestra.
        var p0 = d.pages[0], pi = d.pages.length > 1 ? d.pages[1] : null;
        for (var i = 1; i < d.pages.length; i++)
            if (d.pages[i].appliedMaster != p0.appliedMaster) { pi = d.pages[i]; break; }
        var mInicio = p0.appliedMaster, mInterior = pi ? pi.appliedMaster : p0.appliedMaster;
        info.paginas_maquetado = d.pages.length;
        info.maestra_inicio = mInicio ? mInicio.name : "";
        info.maestra_interior = mInterior ? mInterior.name : "";

        // Todo fuera: contenido de las páginas y de la mesa de trabajo, y las páginas sobrantes.
        for (var s = 0; s < d.spreads.length; s++) {
            var its = d.spreads[s].pageItems.everyItem().getElements();
            for (var k = 0; k < its.length; k++) { try { its[k].locked = false; its[k].remove(); } catch (e) {} }
        }
        while (d.pages.length > 2) d.pages[d.pages.length - 1].remove();
        if (d.pages.length < 2) d.pages.add(LocationOptions.AT_END);
        d.pages[0].appliedMaster = mInicio;
        d.pages[1].appliedMaster = mInterior;
        for (var s = d.sections.length - 1; s > 0; s--) { try { d.sections[s].remove(); } catch (e) {} }

        var marcos = marcosColumnas(d.pages[0]).concat(marcosColumnas(d.pages[1]));
        for (var k = 1; k < marcos.length; k++) marcos[k - 1].nextTextFrame = marcos[k];

        info.pagina = medidas(d.pages[1]);
        estilos(d, info);
        d.save(destino);
    } catch (e) {
        d.close(SaveOptions.NO);
        return "ERROR: " + e + " (línea " + e.line + ")";
    }
    d.close(SaveOptions.NO);
    return info;
}

// La maqueta actual, tal cual: maestras de sus dos primeras páginas, medidas y estilos.
function leerMaqueta(f) {
    if (!f.exists) return "ERROR: no existe " + f.fsName;
    var d = null;
    for (var i = 0; i < app.documents.length; i++)
        try { if (app.documents[i].fullName.fsName == f.fsName) d = app.documents[i]; } catch (e) {}
    var cerrar = !d;
    if (cerrar) {
        app.scriptPreferences.userInteractionLevel = UserInteractionLevels.NEVER_INTERACT;
        try { d = app.open(f, false); }
        finally { app.scriptPreferences.userInteractionLevel = UserInteractionLevels.INTERACT_WITH_ALL; }
    }
    var info = {};
    try {
        app.scriptPreferences.measurementUnit = MeasurementUnits.MILLIMETERS;
        var p0 = d.pages[0], pi = d.pages.length > 1 ? d.pages[1] : p0;
        info.paginas_maquetado = d.pages.length;
        info.maestra_inicio = p0.appliedMaster ? p0.appliedMaster.name : "";
        info.maestra_interior = pi.appliedMaster ? pi.appliedMaster.name : "";
        info.pagina = medidas(pi);
        estilos(d, info);
    } catch (e) {
        info = "ERROR: " + e + " (línea " + e.line + ")";
    }
    app.scriptPreferences.measurementUnit = AutoEnum.AUTO_VALUE;
    if (cerrar) d.close(SaveOptions.NO);
    return info;
}

var res = ARGS[1] ? crear(File(ARGS[0]), File(ARGS[1])) : leerMaqueta(File(ARGS[0]));
if (typeof res == "string") res;
else {
    var f = File(ARGS[2]);
    f.encoding = "UTF-8";
    f.open("w");
    f.write(json(res));
    f.close();
    "OK";
}
