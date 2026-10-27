// Cierre de un capítulo ya corregido (Ventana > Formatear Word > Finalizar capítulo):
// 1. Puntuación: la que va pegada a una palabra toma su formato («(Fusarium)», «Epiescleritis.»,
//    «»),», «Fusarium/Aspergillus»). Sustituye al script «Formatear puntuaciones».
// 2. URLs (http://…, https://…, www.…) y DOI («doi: 10.1016/…», enlazado a https://doi.org/…)
//    → hipervínculos, sin tocar su formato ni su estilo de carácter y sin borde visible. La
//    puntuación final («…html).») queda fuera del enlace; lo que ya es hipervínculo no se toca.
// Argumentos: [datos.json, "simular" | "aplicar", nombre del documento (opcional: todos los
// «Capitulo…» abiertos), "detalle" (opcional)]. datos.json: {excluir: [estilos de carácter que
// no pasan a la puntuación: superíndice, símbolos]}. Al aplicar, un paso de deshacer por documento.

#target indesign

var ARGS = (typeof arguments != "undefined") ? arguments : [];
var DETALLE = ARGS.length > 3 && ARGS[3] == "detalle";

var CIERRE = ".,;:)]}»”’!?…/";      // pegada detrás de la palabra
var APERTURA = "([{«“‘¿¡";          // pegada delante

function leerJSON(ruta) {
    var f = File(ruta);
    f.encoding = "UTF-8";
    f.open("r");
    var t = f.read();
    f.close();
    return eval("(" + t + ")");
}

// Todos los textos del documento: historias y celdas de tabla.
function textos(d) {
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

// ---- 1. puntuación ---------------------------------------------------------------------
// La puntuación pegada a una palabra toma su formato: el estilo de carácter (cualquiera salvo
// los de `excluir`, como el superíndice: «10⁶.» no lleva el punto volado) y, si lo hay, el
// formato local (estilo de fuente). Como el script «Formatear puntuaciones»:
//   - detrás de la palabra: . , ; : ) ] } » ” ’ ! ? … /   (también en cadena: «»),»; «Fusarium/»)
//   - delante: ( [ { « “ ‘ ¿ ¡
//   - entre dos palabras con el mismo formato: - – —
// «Palabra» es cualquier carácter que no sea espacio ni puntuación: también «%» («98 %.»).
var ENTRE = "-\u2013\u2014";
function esPalabra(c) { return /\S/.test(c) && CIERRE.indexOf(c) < 0 && APERTURA.indexOf(c) < 0 && ENTRE.indexOf(c) < 0; }

function formato(c) {
    var est = c.appliedCharacterStyle;
    return { estilo: est, nombre: est.name, fuente: c.fontStyle, clave: est.name + "|" + c.fontStyle };
}

function puntuacion(d, excluir, aplicar, ejemplos) {
    var n = 0, fuera = {};
    for (var i = 0; i < excluir.length; i++) fuera[excluir[i]] = 1;
    var ts = textos(d);
    for (var k = 0; k < ts.length; k++) {
        var cont = ts[k], txt;
        try { txt = String(cont.contents); } catch (e) { continue; }
        var chars = cont.characters, total = txt.length, cambios = [];
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
                    var a = formato(chars[i - 1]), b = formato(chars[i + 1]);
                    if (a.clave == b.clave) j = i - 1;
                }
            }
            if (j < 0 || j >= total || !esPalabra(txt.charAt(j))) continue;
            var fp = formato(chars[i]), fw = formato(chars[j]);
            if (fp.clave == fw.clave || fuera[fw.nombre]) continue;
            cambios.push([i, fw]);
        }
        for (var i = 0; i < cambios.length; i++) {
            var c = chars[cambios[i][0]], fw = cambios[i][1];
            if (ejemplos.length < (DETALLE ? 1000 : 4)) {
                var a = Math.max(0, cambios[i][0] - 20), b = Math.min(total, cambios[i][0] + 4);
                ejemplos.push("      …" + txt.substring(a, cambios[i][0]).replace(/\r/g, " ") + "[" + txt.charAt(cambios[i][0]) + "]" +
                              txt.substring(cambios[i][0] + 1, b).replace(/\r/g, " ") + "… → " + fw.nombre +
                              (fw.fuente != c.fontStyle && fw.nombre == "[Ninguno]" ? " (" + fw.fuente + ")" : ""));
            }
            if (aplicar) {
                if (c.appliedCharacterStyle.id != fw.estilo.id) c.appliedCharacterStyle = fw.estilo;
                if (c.fontStyle != fw.fuente) c.fontStyle = fw.fuente;     // formato local
            }
            n++;
        }
    }
    return n;
}

// ---- 2. URLs y DOI ---------------------------------------------------------------------------
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

// Convierte en hipervínculo cada aparición de `patron` (GREP), sin tocar su formato ni su
// estilo de carácter y sin borde visible. Se salta lo que ya es (o está dentro de) un enlace.
function enlazar(d, patron, partes, aplicar, ejemplos) {
    var n = 0, ya = enlazados(d);
    app.findGrepPreferences = NothingEnum.NOTHING;
    app.findChangeGrepOptions.includeFootnotes = true;
    app.findChangeGrepOptions.includeMasterPages = false;
    app.findGrepPreferences.findWhat = patron;
    var h = d.findGrep();
    app.findGrepPreferences = NothingEnum.NOTHING;
    for (var i = h.length - 1; i >= 0; i--) {
        var p = partes(h[i].contents);
        if (!p.texto) continue;
        // resolve(): itemByRange no da un Text normal (su index no sirve para comparar).
        var t = resolve(h[i].characters.itemByRange(p.ini, p.ini + p.texto.length - 1).toSpecifier());
        var sid = t.parentStory.id, ini = t.index, ocupado = false;
        for (var k = 0; k < ya.length; k++) if (ya[k][0] == sid && ya[k][1] < ini + p.texto.length && ini < ya[k][2]) ocupado = true;
        if (ocupado) continue;
        if (ejemplos.length < (DETALLE ? 1000 : 4)) ejemplos.push("      " + p.texto + (p.destino != p.texto ? " → " + p.destino : ""));
        if (aplicar) {
            try {
                var fuente = d.hyperlinkTextSources.add(t);
                var dest = d.hyperlinkURLDestinations.add(p.destino, { hidden: true });
                var nombre = p.texto, k = 2;
                while (d.hyperlinks.itemByName(nombre).isValid) nombre = p.texto + " (" + k++ + ")";
                d.hyperlinks.add(fuente, dest, { name: nombre, visible: false });
            } catch (e) { ejemplos.push("      NO SE PUDO: " + p.texto + ": " + e); continue; }
        }
        n++;
    }
    return n;
}

function procesar(d, datos, aplicar) {
    var ejP = [], ejU = [], ejD = [];
    var nP = puntuacion(d, datos.excluir, aplicar, ejP);
    var nU = enlazar(d, "(?i)(?:https?://|www\\.)[^\\s«»\"<>]+", partesURL, aplicar, ejU);
    var nD = enlazar(d, "(?i)\\bdoi:?\\s*10\\.\\d{4,9}/[^\\s«»\"<>]+", partesDOI, aplicar, ejD);
    var verbo = aplicar ? "" : " posibles";
    function linea(t, n, ej) { return "\n   " + t + ": " + n + verbo + (ej.length ? "\n" + ej.join("\n") : ""); }
    return "== " + d.name + linea("Puntuación con el estilo de su palabra", nP, ejP) +
        linea("URLs → hipervínculos", nU, ejU) + linea("DOI → hipervínculos", nD, ejD);
}

function principal() {
    var datos = leerJSON(ARGS[0]), aplicar = ARGS[1] == "aplicar", nombre = ARGS[2] || "";
    var docs = [];
    for (var i = 0; i < app.documents.length; i++) {
        var n = app.documents[i].name;
        if (nombre ? n == nombre : n.indexOf("Capitulo") == 0) docs.push(n);
    }
    if (!docs.length) return "ERROR: no hay documentos abiertos" + (nombre ? " con el nombre " + nombre : " «Capitulo…»");
    var res = [];
    for (var i = 0; i < docs.length; i++) {
        var d = app.documents.itemByName(docs[i]);
        if (aplicar) {
            var s;
            app.doScript(function () { s = procesar(d, datos, true); }, ScriptLanguage.JAVASCRIPT, undefined,
                         UndoModes.ENTIRE_SCRIPT, "Finalizar capítulo");
            res.push(s);
        } else res.push(procesar(d, datos, false));
    }
    return res.join("\n\n");
}

app.scriptPreferences.userInteractionLevel = UserInteractionLevels.NEVER_INTERACT;
var resultado;
try { resultado = principal(); }
catch (e) { resultado = "ERROR: " + e + " (línea " + e.line + ")"; }
finally { app.scriptPreferences.userInteractionLevel = UserInteractionLevels.INTERACT_WITH_ALL; }
resultado;
