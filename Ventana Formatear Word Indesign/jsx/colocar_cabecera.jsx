// Cabecera de la portadilla desde la Biblioteca de la publicación ([portadilla] de su .toml):
// coloca el elemento en la primera página, en el margen izquierdo y a la altura indicada, y le
// pasa el título y los autores del capítulo, que la importación deja al principio del texto
// (se mueven con su formato, ya no quedan en el texto); el resto de la cabecera (el capítulo)
// queda como en la Biblioteca. Los marcos de texto de esa página empiezan en la guía.
// Argumentos: [0] nombre del documento abierto, [1] JSON con {biblioteca, elemento, y,
// texto_desde, estilos: {titulo, autores}}.

#target indesign

var ARGS = arguments;      // dentro de una función, «arguments» son los de la función

function leerJSON(ruta) {
    var f = File(ruta);
    f.encoding = "UTF-8";
    f.open("r");
    var t = f.read();
    f.close();
    return eval("(" + t + ")");
}

// «Grupo/Estilo» o «Estilo» → el nombre del estilo (sin grupo), para comparar
function hoja(ruta) { var p = String(ruta || "").split("/"); return p[p.length - 1]; }

// Ruta del documento al que pertenece un objeto
function documentoDe(o) {
    while (o && o.constructor.name != "Document") o = o.parent;
    try { return o.fullName.fsName; } catch (e) { return ""; }
}

// Texto sin el retorno final de un párrafo
function sinRetorno(p) {
    var n = p.characters.length;
    if (n && p.characters[n - 1].contents == "\r") n--;
    return n ? p.characters.itemByRange(0, n - 1) : null;
}

function colocar(d, c) {
    var r = [];
    d.viewPreferences.horizontalMeasurementUnits = MeasurementUnits.MILLIMETERS;
    d.viewPreferences.verticalMeasurementUnits = MeasurementUnits.MILLIMETERS;
    var origen = d.viewPreferences.rulerOrigin;
    d.viewPreferences.rulerOrigin = RulerOrigin.PAGE_ORIGIN;

    // La biblioteca: la abierta o se abre (y se cierra al acabar)
    var lib = null, abierta = true;
    for (var i = 0; i < app.libraries.length; i++)
        if (app.libraries[i].fullName.fsName == File(c.biblioteca).fsName) lib = app.libraries[i];
    if (!lib) {
        if (!File(c.biblioteca).exists) throw new Error("No encuentro la biblioteca " + c.biblioteca);
        lib = app.open(File(c.biblioteca));
        abierta = false;
    }
    try {
        var a = lib.assets.itemByName(c.elemento);
        if (!a.isValid) throw new Error("La biblioteca no tiene el elemento «" + c.elemento + "»");
        // placeAsset coloca en el documento ACTIVO aunque se le pase otro: se activa el nuevo
        // (la importación lo deja visible) y, si aun así cae en otro, se pasa al nuevo y se quita
        if (d.visible) app.activeDocument = d;
        var cab = a.placeAsset(d)[0];
        if (documentoDe(cab) !== d.fullName.fsName) {
            var copia = cab.duplicate(d.pages[0]);
            cab.remove();
            cab = copia;
        }
    } finally { if (!abierta) lib.close(); }

    // En la primera página, en el margen izquierdo y a la altura de la configuración
    var pag = d.pages[0];
    cab.move(pag);
    cab.move([pag.marginPreferences.left, c.y]);
    r.push("cabecera en la página " + pag.name + " a " + c.y + " mm");

    // Título y autores: los primeros párrafos del texto con esos estilos pasan a la cabecera
    var principal = null;
    for (i = 0; i < d.stories.length; i++)
        if (!principal || d.stories[i].characters.length > principal.characters.length) principal = d.stories[i];
    function destino(estilo) {
        var ps = cab.parentStory.paragraphs;
        for (var k = 0; k < ps.length; k++) if (ps[k].appliedParagraphStyle.name == hoja(estilo)) return ps[k];
        return null;
    }
    function pasar(estilo, nombre, caracter) {
        var hacia = destino(estilo);
        if (!hacia) { r.push("⚠ la cabecera no tiene párrafo " + hoja(estilo)); return; }
        var desde = null, ps = principal.paragraphs;
        for (var k = 0; k < Math.min(ps.length, 6); k++) if (ps[k].appliedParagraphStyle.name == hoja(estilo)) { desde = ps[k]; break; }
        if (!desde) { r.push("sin " + nombre + " en el Word: se deja el de la muestra"); return; }
        var muestra = sinRetorno(hacia);
        var punto = muestra ? muestra.insertionPoints[0] : hacia.insertionPoints[0];
        var texto = sinRetorno(desde), largo = texto ? texto.characters.length : 0;
        if (texto) texto.move(LocationOptions.BEFORE, punto);      // con su formato
        muestra = sinRetorno(destino(estilo));                       // el texto movido + «Xx»
        if (muestra && largo && muestra.characters.length > largo)
            muestra.characters.itemByRange(largo, muestra.characters.length - 1).remove();
        // Estilo de carácter para el texto pasado (el del título lo toman las cornisas)
        if (caracter && largo) {
            var ec = null, todos = d.allCharacterStyles;
            for (var k = 0; k < todos.length; k++) if (todos[k].name == caracter) ec = todos[k];
            if (ec) sinRetorno(destino(estilo)).appliedCharacterStyle = ec;
            else r.push("⚠ no está el estilo de carácter " + caracter);
        }
        // El párrafo del texto, ya vacío, se borra
        for (var k = 0; k < Math.min(principal.paragraphs.length, 6); k++) {
            var p = principal.paragraphs[k];
            if (p.appliedParagraphStyle.name == hoja(estilo) && p.contents.replace(/\r$/, "") == "") { p.remove(); break; }
        }
        r.push(nombre + " pasado a la cabecera");
    }
    pasar(c.estilos.titulo, "título", c.estilos.caracter_titulo);
    pasar(c.estilos.autores, "autores");

    // Crece hacia abajo si el título necesita más líneas
    cab.textFramePreferences.properties = { autoSizingReferencePoint: AutoSizingReferenceEnum.TOP_CENTER_POINT,
        autoSizingType: AutoSizingTypeEnum.HEIGHT_ONLY, useMinimumHeightForAutoSizing: true,
        minimumHeightForAutoSizing: cab.geometricBounds[2] - cab.geometricBounds[0] };
    // El texto de la portadilla empieza en la guía («texto_desde» mm), no detrás de la cabecera
    if (c.texto_desde) {
        var marcos = pag.textFrames.everyItem().getElements(), n = 0;
        for (i = 0; i < marcos.length; i++) {
            var b = marcos[i].geometricBounds;
            if (marcos[i].id == cab.id || marcos[i].parentStory.id != principal.id || b[0] >= c.texto_desde) continue;
            marcos[i].geometricBounds = [c.texto_desde, b[1], b[2], b[3]];
            n++;
        }
        r.push("texto de la portadilla desde " + c.texto_desde + " mm (" + n + " marcos)");
        // En la portadilla cabe menos: si sobra texto, más páginas como la segunda (lo mismo
        // que hace importar.jsx)
        var ultimo = principal.textContainers[principal.textContainers.length - 1], nuevas = 0;
        // Con el origen en la página, los marcos de una página impar nueva caen fuera de ella:
        // las páginas se añaden con el origen del pliego (como importar.jsx)
        d.viewPreferences.rulerOrigin = RulerOrigin.SPREAD_ORIGIN;
        if (ultimo.overflows && d.pages.length > 1) {
            var pInt = d.pages[1], bi = pInt.bounds, plantilla = [], cols = pInt.textFrames.everyItem().getElements();
            cols.sort(function (x, y) { return x.geometricBounds[1] - y.geometricBounds[1]; });
            for (i = 0; i < cols.length; i++) {
                var g = cols[i].geometricBounds;
                plantilla.push([g[0] - bi[0], g[1] - bi[1], g[2] - bi[0], g[3] - bi[1]]);
            }
            while (ultimo.overflows && nuevas < 50 && plantilla.length) {
                var np = d.pages.add(LocationOptions.AT_END, { appliedMaster: pInt.appliedMaster }), bn = np.bounds;
                for (var k = 0; k < plantilla.length; k++) {
                    var t = plantilla[k];
                    var nf = np.textFrames.add({ geometricBounds: [bn[0] + t[0], bn[1] + t[1], bn[0] + t[2], bn[1] + t[3]] });
                    ultimo.nextTextFrame = nf;
                    ultimo = nf;
                }
                nuevas++;
            }
            r.push(nuevas + " página(s) más" + (ultimo.overflows ? " (¡sigue sobrando texto!)" : ""));
        }
    }
    d.viewPreferences.rulerOrigin = origen;
    return r;
}

(function () {
    var d = app.documents.itemByName(ARGS[0]);
    if (!d.isValid) return "Cabecera: «" + ARGS[0] + "» no está abierto";
    try { return "Cabecera: " + colocar(d, leerJSON(ARGS[1])).join("; "); }
    catch (e) { return "⚠ Cabecera: " + e.message + " (línea " + e.line + ")"; }
})();
