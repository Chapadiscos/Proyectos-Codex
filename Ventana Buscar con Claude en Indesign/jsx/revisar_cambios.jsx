// Revisión de cambios uno a uno, como Buscar/Cambiar.
// ARGS.buscar: cuerpo de función (doc) que devuelve un array de objetivos: objetos de
//   InDesign (texto, marcos…) o {objeto: ..., nota: "..."}.
// ARGS.aplicar: cuerpo de función (obj, doc) que hace el cambio en un objetivo.
// Cada cambio se aplica a prueba para verlo; al terminar se deshacen las pruebas y los
// aceptados se vuelven a aplicar juntos en un solo paso de deshacer (ARGS.descripcion).
if (app.documents.length === 0) throw new Error("No hay ningún documento abierto");
var doc = app.activeDocument;
if (!doc.saved) throw new Error("El documento «" + doc.name + "» no se ha guardado nunca; guárdalo antes de modificarlo");

try {
    var fBuscar = new Function("doc", ARGS.buscar);
    var fAplicar = new Function("obj", "doc", ARGS.aplicar);
} catch (e) { return json({__error: "Error de sintaxis en el código: " + e.message + "; no se cambió nada"}); }

var hallados = fBuscar(doc);
if (!(hallados instanceof Array)) throw new Error("`buscar` debe devolver un array");
if (hallados.length === 0) return json({total: 0, aceptados: 0, rechazados: 0, sin_aplicar: 0, cancelado: false, deshacer: null});

// --- Objetivos -----------------------------------------------------------
// El texto se guarda como (contenedor, inicio, fin) y se desplaza cuando un cambio
// anterior en el mismo contenedor alarga o acorta el texto.
function esTexto(o) {
    return o.hasOwnProperty("parentStory") && o.hasOwnProperty("index") && o.hasOwnProperty("length");
}
function entrada(h) {
    var nota = "", o = h;
    if (h && h.constructor && h.constructor.name === "Object" && h.objeto) { o = h.objeto; nota = h.nota || ""; }
    if (!o || !o.isValid) throw new Error("`buscar` devolvió un objetivo no válido");
    if (esTexto(o)) {
        var cont = o.parent instanceof Cell ? o.parent : o.parentStory;
        return {texto: true, cont: cont, clave: cont.toSpecifier(), ini: o.index, fin: o.index + o.length, nota: nota};
    }
    return {texto: false, obj: o, nota: nota};
}
var objetivos = [];
for (var i = 0; i < hallados.length; i++) objetivos.push(entrada(hallados[i]));
var originales = [];
for (i = 0; i < objetivos.length; i++) originales.push({ini: objetivos[i].ini, fin: objetivos[i].fin});

function longitud(cont) { return cont.texts[0].length; }
function resolver(e) {
    if (!e.texto) return e.obj;
    return e.fin > e.ini ? e.cont.characters.itemByRange(e.ini, e.fin - 1) : e.cont.insertionPoints[e.ini];
}
function desplazar(desde, e, delta) {  // tras cambiar e, mueve los objetivos posteriores del mismo texto
    if (!e.texto || delta === 0) return;
    for (var k = desde; k < objetivos.length; k++) {
        var o = objetivos[k];
        if (o.texto && o.clave === e.clave && o.ini >= e.fin - delta) { o.ini += delta; o.fin += delta; }
    }
}
function aplicar(e) {  // aplica el cambio y ajusta el final del objetivo; devuelve el delta
    var antes = e.texto ? longitud(e.cont) : 0;
    fAplicar(resolver(e), doc);
    var delta = e.texto ? longitud(e.cont) - antes : 0;
    e.fin += delta;
    return delta;
}

// --- Presentación --------------------------------------------------------
function pagina(o) {
    try {
        if (esTexto(o)) { var m = o.parentTextFrames; return m.length ? m[0].parentPage : null; }
        return o.parentPage;
    } catch (_) { return null; }
}
function contexto(e) {
    if (!e.texto) {
        var o = e.obj, t = o.constructor.name;
        if (o.hasOwnProperty("contents") && typeof o.contents === "string") t += ": " + o.contents.slice(0, 120);
        return t;
    }
    var n = longitud(e.cont), a = Math.max(0, e.ini - 50), b = Math.min(n, e.fin + 50);
    function trozo(x, y) { return y > x ? e.cont.characters.itemByRange(x, y - 1).contents : ""; }
    return (a > 0 ? "…" : "") + trozo(a, e.ini) + "⟦" + trozo(e.ini, e.fin) + "⟧" + trozo(e.fin, b) + (b < n ? "…" : "");
}
function mostrar(e) {
    var o = resolver(e), p = pagina(o);
    if (p && p.isValid) app.activeWindow.activePage = p;
    try { app.select(o); } catch (_) {}
    if (e.texto) try { o.showText(); } catch (_) {}  // desplaza la vista hasta el texto
}
// Posición del diálogo: la última en que el usuario lo dejó (se guarda en la aplicación).
var CLAVE_POS = "claude_revisar_cambios_posicion";
function posicionGuardada() {
    var v = app.extractLabel(CLAVE_POS).split(",");
    return v.length === 2 ? [Number(v[0]), Number(v[1])] : null;
}
// Botones del diálogo → decisión
function preguntar(n, e, antes, despues) {
    var w = new Window("dialog", "Revisar cambios — " + ARGS.descripcion);
    w.alignChildren = "fill";
    var p = pagina(resolver(e));
    w.add("statictext", undefined, "Cambio " + (n + 1) + " de " + objetivos.length + (p ? "  ·  página " + p.name : ""));
    if (e.nota) w.add("statictext", undefined, e.nota, {multiline: true});
    w.add("statictext", undefined, "Antes:");
    w.add("edittext", [0, 0, 520, 60], antes, {multiline: true, readonly: true});
    w.add("statictext", undefined, "Después:");
    w.add("edittext", [0, 0, 520, 60], despues, {multiline: true, readonly: true});
    var fila = w.add("group"), decision = "terminar";
    function boton(texto, valor) {
        var b = fila.add("button", undefined, texto);
        b.onClick = function () {
            decision = valor;
            app.insertLabel(CLAVE_POS, w.location[0] + "," + w.location[1]);
            w.close();
        };
        return b;
    }
    w.defaultElement = boton("Aceptar", "aceptar");
    boton("Rechazar", "rechazar");
    boton("Aceptar todos", "todos");
    w.cancelElement = boton("Terminar", "terminar");
    boton("Cancelar todo", "cancelar");
    w.onShow = function () {  // donde lo dejó el usuario; la primera vez, abajo a la derecha
        var s = $.screens[0];
        w.location = posicionGuardada() || [s.right - w.size.width - 30, s.bottom - w.size.height - 60];
    };
    if (ARGS.auto) {  // solo para pruebas: el diálogo se abre, se cierra solo y decide ARGS.auto (o ARGS.auto[n])
        w.onShow = function () { w.close(); };
        w.show();
        return ARGS.auto instanceof Array ? ARGS.auto[n] : ARGS.auto;
    }
    w.show();
    return decision;
}

// --- Revisión ------------------------------------------------------------
var interaccion = app.scriptPreferences.userInteractionLevel;
app.scriptPreferences.userInteractionLevel = UserInteractionLevels.INTERACT_WITH_ALL;
app.activate();

var aceptado = [], pruebas = 0, decision = null, fallo = null, n, rechazados = 0;
try {
    for (n = 0; n < objetivos.length; n++) {
        var e = objetivos[n];
        mostrar(e);
        var antes = contexto(e), pasos = doc.undoHistory.length, delta = 0;
        try {
            app.doScript(function () { delta = aplicar(e); }, ScriptLanguage.JAVASCRIPT, undefined,
                         UndoModes.ENTIRE_SCRIPT, "Prueba: " + ARGS.descripcion);
        } catch (err) { fallo = err; }
        var hubo = doc.undoHistory.length > pasos;
        if (hubo) pruebas++;
        if (fallo) break;
        mostrar(e);
        decision = preguntar(n, e, antes, contexto(e));
        if (decision === "aceptar" || decision === "todos") {
            aceptado[n] = true;
            desplazar(n + 1, e, delta);
            if (decision === "todos") {
                for (var k = n + 1; k < objetivos.length; k++) aceptado[k] = true;
                n = objetivos.length;
                break;
            }
        } else {
            if (hubo) { doc.undo(); pruebas--; }
            if (decision !== "rechazar") break;
            rechazados++;
        }
    }
} finally {
    app.scriptPreferences.userInteractionLevel = interaccion;
    // Se deshacen todas las pruebas que quedaron…
    for (; pruebas > 0; pruebas--) doc.undo();
    try { app.select(NothingEnum.NOTHING); } catch (_) {}
}
if (fallo) return json({__error: "Error al aplicar el cambio " + (n + 1) + ": " + (fallo.message || String(fallo)) +
                              " (línea " + (fallo.line - 1) + " de `aplicar`); no se cambió nada"});

// …y los aceptados se aplican de nuevo, juntos, en un solo paso.
var cuantos = 0;
for (i = 0; i < objetivos.length; i++) { objetivos[i].ini = originales[i].ini; objetivos[i].fin = originales[i].fin; if (aceptado[i]) cuantos++; }
if (decision === "cancelar") cuantos = 0;
var deshacer = null;
if (cuantos > 0) {
    var pasos0 = doc.undoHistory.length;
    app.doScript(function () {
        for (var j = 0; j < objetivos.length; j++) {
            if (!aceptado[j]) continue;
            desplazar(j + 1, objetivos[j], aplicar(objetivos[j]));
        }
    }, ScriptLanguage.JAVASCRIPT, undefined, UndoModes.ENTIRE_SCRIPT, ARGS.descripcion);
    if (doc.undoHistory.length > pasos0 || doc.undoName === ARGS.descripcion) deshacer = doc.undoName;
}
return json({
    total: objetivos.length,
    aceptados: cuantos,
    rechazados: rechazados,
    sin_aplicar: objetivos.length - cuantos - rechazados,
    cancelado: decision === "cancelar",
    deshacer: deshacer
});
