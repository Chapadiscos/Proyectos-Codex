// Lo que comparten «Finalizar capítulo» (finalizar.jsx, todo de golpe) y la ventana «Revisar
// cierre» (revisar_cierre.jsx, uno a uno): qué cambios hace el cierre y cómo se aplica cada uno.
// 1. Puntuación: la que va pegada a una palabra toma su formato: el estilo de carácter (salvo los
//    de `excluir`, como el superíndice: «10⁶.» no lleva el punto volado) y, si lo hay, el formato
//    local (estilo de fuente). Como el script «Formatear puntuaciones»:
//      - detrás de la palabra: . , ; : ) ] } » ” ’ ! ? … /   (también en cadena: «»),»; «Fusarium/»)
//      - delante: ( [ { « “ ‘ ¿ ¡
//      - entre dos palabras con el mismo formato: - – —
//    «Palabra» es cualquier carácter que no sea espacio ni puntuación: también «%» («98 %.»).
// 2. URLs (http://…, https://…, www.…) y DOI («doi: 10.1016/…», enlazado a https://doi.org/…) →
//    hipervínculos, sin tocar su formato ni su estilo de carácter y sin borde visible. La
//    puntuación final («…html).») queda fuera del enlace; lo que ya es hipervínculo no se toca.
// Cada cambio: {tipo: "puntuacion" | "url" | "doi", cont (historia o celda), ini, len, texto,
// fw (puntuación: {estilo, nombre, fuente}), destino (enlaces)}.

var CIERRE = ".,;:)]}»”’!?…/";      // pegada detrás de la palabra
var APERTURA = "([{«“‘¿¡";      // pegada delante
var ENTRE = "-–—";
var PATRON_URL = "(?i)(?:https?://|www\\.)[^\\s«»\"<>]+";
var PATRON_DOI = "(?i)\\bdoi:?\\s*10\\.\\d{4,9}/[^\\s«»\"<>]+";

// Todos los textos del documento: historias y celdas de tabla.
function textosCierre(d) {
    var r = [], ss = d.stories.everyItem().getElements();
    for (var s = 0; s < ss.length; s++) {
        r.push(ss[s]);
        for (var t = 0; t < ss[s].tables.length; t++) {
            var cs = ss[s].tables[t].cells.everyItem().getElements();
            for (var c = 0; c < cs.length; c++) r.push(cs[c].texts[0]);
        }
    }
    return r;
}

function esPalabra(c) { return /\S/.test(c) && CIERRE.indexOf(c) < 0 && APERTURA.indexOf(c) < 0 && ENTRE.indexOf(c) < 0; }

function formatoCierre(c) {
    var est = c.appliedCharacterStyle;
    return { estilo: est, nombre: est.name, fuente: c.fontStyle, clave: est.name + "|" + c.fontStyle };
}

function cambiosPuntuacion(d, excluir) {
    var res = [], fuera = {};
    for (var i = 0; i < excluir.length; i++) fuera[excluir[i]] = 1;
    var ts = textosCierre(d);
    for (var k = 0; k < ts.length; k++) {
        var cont = ts[k], txt;
        try { txt = String(cont.contents); } catch (e) { continue; }
        var chars = cont.characters, total = txt.length;
        for (var i = 0; i < total; i++) {
            var ch = txt.charAt(i), j = -1;
            if (CIERRE.indexOf(ch) >= 0) {                 // la palabra, a la izquierda de la cadena
                j = i - 1;
                while (j >= 0 && CIERRE.indexOf(txt.charAt(j)) >= 0) j--;
            } else if (APERTURA.indexOf(ch) >= 0) {        // la palabra, a la derecha
                j = i + 1;
                while (j < total && APERTURA.indexOf(txt.charAt(j)) >= 0) j++;
            } else if (ENTRE.indexOf(ch) >= 0) {
                if (i > 0 && i < total - 1 && esPalabra(txt.charAt(i - 1)) && esPalabra(txt.charAt(i + 1))) {
                    var a = formatoCierre(chars[i - 1]), b = formatoCierre(chars[i + 1]);
                    if (a.clave == b.clave) j = i - 1;
                }
            }
            if (j < 0 || j >= total || !esPalabra(txt.charAt(j))) continue;
            var fp = formatoCierre(chars[i]), fw = formatoCierre(chars[j]);
            if (fp.clave == fw.clave || fuera[fw.nombre]) continue;
            // El índice dentro de su historia (en una celda, contando desde el principio de la historia)
            res.push({ tipo: "puntuacion", cont: cont, ini: i, len: 1, texto: ch, fw: fw, actual: fp });
        }
    }
    return res;
}

function aplicarPuntuacion(c) {
    var ch = c.cont.characters[c.ini];
    if (String(ch.contents) != c.texto) throw new Error("el texto ha cambiado (pulsa Actualizar)");
    if (ch.appliedCharacterStyle.id != c.fw.estilo.id) ch.appliedCharacterStyle = c.fw.estilo;
    if (ch.fontStyle != c.fw.fuente) ch.fontStyle = c.fw.fuente;     // formato local
}

function enlazados(d) {
    var r = [], fs = d.hyperlinkTextSources.everyItem().getElements();
    for (var i = 0; i < fs.length; i++) {
        try { var t = fs[i].sourceText; r.push([t.parentStory.id, t.index, t.index + t.length]); } catch (e) {}
    }
    return r;
}

// Quita la puntuación final de un enlace; «)» solo si el paréntesis no se abre dentro.
function sinPuntuacionFinal(s) {
    while (s.length) {
        var c = s.charAt(s.length - 1);
        if (".,;:]}»”’!?".indexOf(c) >= 0 || (c == ")" && s.indexOf("(") < 0)) s = s.substring(0, s.length - 1);
        else break;
    }
    return s;
}

// URLs: todo lo encontrado, sin la puntuación final.
function partesURL(texto) {
    var url = sinPuntuacionFinal(texto);
    return { ini: 0, texto: url, destino: /^https?:\/\//i.test(url) ? url : "http://" + url };
}

// DOI: solo el identificador («10.1016/j.ajo.2009.07.021»), no el «doi:» de delante.
function partesDOI(texto) {
    var ini = texto.search(/10\./), id = sinPuntuacionFinal(texto.substring(ini));
    return { ini: ini, texto: id, destino: "https://doi.org/" + id };
}

// Cada aparición de `patron` (GREP) que aún no es (ni está dentro de) un hipervínculo.
function cambiosEnlace(d, tipo) {
    var patron = tipo == "doi" ? PATRON_DOI : PATRON_URL, partes = tipo == "doi" ? partesDOI : partesURL;
    var res = [], ya = enlazados(d);
    app.findGrepPreferences = NothingEnum.NOTHING;
    app.findChangeGrepOptions.includeFootnotes = true;
    app.findChangeGrepOptions.includeMasterPages = false;
    app.findGrepPreferences.findWhat = patron;
    var h = d.findGrep();
    app.findGrepPreferences = NothingEnum.NOTHING;
    for (var i = 0; i < h.length; i++) {
        var p = partes(String(h[i].contents));
        if (!p.texto) continue;
        // resolve(): itemByRange no da un Text normal (su index no sirve para comparar).
        var t = resolve(h[i].characters.itemByRange(p.ini, p.ini + p.texto.length - 1).toSpecifier());
        var sid = t.parentStory.id, ini = t.index, ocupado = false;
        for (var k = 0; k < ya.length; k++) if (ya[k][0] == sid && ya[k][1] < ini + p.texto.length && ini < ya[k][2]) ocupado = true;
        if (ocupado) continue;
        // En una celda o una nota la posición cuenta desde su principio: el cambio va con ella
        var cont = t.parent.constructor.name == "Story" ? t.parent : t.parent.texts[0];
        res.push({ tipo: tipo, cont: cont, ini: ini, len: p.texto.length, texto: p.texto, destino: p.destino });
    }
    return res;
}

function aplicarEnlace(d, c) {
    var t = resolve(c.cont.characters.itemByRange(c.ini, c.ini + c.len - 1).toSpecifier());
    if (String(t.contents) != c.texto) throw new Error("el texto ha cambiado (pulsa Actualizar)");
    var fuente = d.hyperlinkTextSources.add(t);
    var dest = d.hyperlinkURLDestinations.add(c.destino, { hidden: true });
    var nombre = c.texto, k = 2;
    while (d.hyperlinks.itemByName(nombre).isValid) nombre = c.texto + " (" + k++ + ")";
    d.hyperlinks.add(fuente, dest, { name: nombre, visible: false });
}

// Todos los cambios del cierre de un documento, en el orden en que se aplican
function cambiosCierre(d, excluir) {
    return cambiosPuntuacion(d, excluir).concat(cambiosEnlace(d, "url"), cambiosEnlace(d, "doi"));
}

function aplicarCierre(d, c) {
    if (c.tipo == "puntuacion") aplicarPuntuacion(c);
    else aplicarEnlace(d, c);
}
