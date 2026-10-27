// Piezas comunes de las reglas ortotipográficas (publicaciones/ortotipografia.toml): las usan
// ortotipografia.jsx (simular / aplicar todo) y revisar_correcciones.jsx (una a una).

function rutaEstilo(est) {
    var r = est.name, p = est.parent;
    while (p && p.constructor && p.constructor.name == "ParagraphStyleGroup") { r = p.name + "/" + r; p = p.parent; }
    return r;
}

// ¿El estilo está en la lista? Vale el nombre completo («Tabla/Pie tabla»), el nombre solo
// («Pie tabla») o un grupo entero («Tabla» abarca todos los estilos del grupo Tabla).
function enLista(est, lista) {
    for (var k = 0; k < lista.length; k++)
        if (est == lista[k] || est.split("/").pop() == lista[k] || est.indexOf(lista[k] + "/") == 0) return true;
    return false;
}

// Estilo de carácter de la maqueta para un párrafo de ese estilo. `estilos` sale de
// maqueta-base.toml: {caracter: {cursiva: "46 Light Italic", ...}, por_grupo: {Grupo: {...}}}
// ("" en un grupo = no aplicar).
function estiloCaracter(d, estilos, estPar, clave) {
    var nombre = estilos.caracter[clave], grupo = estPar.indexOf("/") >= 0 ? estPar.split("/")[0] : estPar;
    var pg = estilos.por_grupo[grupo];
    if (pg && pg[clave] !== undefined) nombre = pg[clave];
    if (!nombre) return null;
    var todos = d.allCharacterStyles;
    for (var i = 0; i < todos.length; i++) if (todos[i].name == nombre) return todos[i];
    return null;
}

function opcionesGrep() {
    var op = app.findChangeGrepOptions;
    op.includeFootnotes = true; op.includeHiddenLayers = false; op.includeLockedLayersForFind = false;
    op.includeLockedStoriesForFind = false; op.includeMasterPages = false;
}

// Lo que encuentra una regla GREP y le toca cambiar: [{t: Text, ec: estilo de carácter (reglas
// con «estilo»)}], con los filtros solo / excluir / excluir_texto aplicados.
function hallazgos(d, rg, estilos) {
    var excl = rg.excluir || [], solo = rg.solo || [];
    // Lista de patrones, no uno con «|»: en ExtendScript, «A$|^B$|C$» encaja con cualquier texto.
    var excl_texto = [], et = rg.excluir_texto || [];
    if (typeof et == "string") et = [et];
    for (var k = 0; k < et.length; k++) excl_texto.push(new RegExp(et[k]));
    opcionesGrep();
    app.findGrepPreferences = NothingEnum.NOTHING;
    app.findGrepPreferences.findWhat = rg.buscar;
    var hallados = d.findGrep(), res = [];
    app.findGrepPreferences = NothingEnum.NOTHING;
    for (var i = 0; i < hallados.length; i++) {
        var est = "", ec = null;
        try { est = rutaEstilo(hallados[i].paragraphs[0].appliedParagraphStyle); } catch (e) {}
        var fuera = enLista(est, excl) || (solo.length && !enLista(est, solo));
        if (!fuera && excl_texto.length) {
            var txt = "";
            try { txt = hallados[i].paragraphs[0].contents.replace(/\r$/, ""); } catch (e) {}
            for (var k = 0; k < excl_texto.length; k++) if (excl_texto[k].test(txt)) fuera = true;
        }
        if (!fuera && rg.estilo) {
            // Regla de estilo de carácter: solo cuenta lo que aún no lo tiene.
            ec = estiloCaracter(d, estilos, est, rg.estilo);
            if (!ec || hallados[i].appliedCharacterStyle.id == ec.id) fuera = true;
        }
        if (!fuera) res.push({ t: hallados[i], ec: ec });
    }
    return res;
}

// Dos ladillos seguidos van sin separación: sin espacio después el de arriba y sin espacio
// antes el de abajo. Devuelve las parejas que aún tienen espacio: [[arriba, abajo], ...].
function ladillosPendientes(d, rg) {
    var res = [], grupo = rg.solo || ["Ladillos"];
    for (var s = 0; s < d.stories.length; s++) {
        var ps = d.stories[s].paragraphs.everyItem().getElements(), anterior = null;
        for (var i = 0; i < ps.length; i++) {
            var est = "";
            try { est = rutaEstilo(ps[i].appliedParagraphStyle); } catch (e) {}
            var es = enLista(est, grupo);
            if (es && anterior && (anterior.spaceAfter != 0 || ps[i].spaceBefore != 0)) res.push([anterior, ps[i]]);
            anterior = es ? ps[i] : null;
        }
    }
    return res;
}
