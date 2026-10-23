var r = {version: app.version, documentos: []};
for (var i = 0; i < app.documents.length; i++) r.documentos.push(app.documents[i].name);
if (app.documents.length === 0) return json(r);

var doc = app.activeDocument;
r.activo = {
    nombre: doc.name,
    ruta: doc.saved ? doc.fullName.fsName : null,
    paginas: doc.pages.length,
    pagina_visible: app.activeWindow.activePage.name,
    cambios_sin_guardar: doc.modified
};

var sel = app.selection, items = [];
for (var j = 0; j < sel.length && j < 50; j++) {
    var o = sel[j], it = {tipo: o.constructor.name};
    if (o.hasOwnProperty("contents") && typeof o.contents === "string") {
        it.texto = o.contents.length > 500 ? o.contents.slice(0, 500) + "…" : o.contents;
    }
    if (o.hasOwnProperty("appliedParagraphStyle")) it.estilo_parrafo = o.appliedParagraphStyle.name;
    if (o.hasOwnProperty("geometricBounds")) it.limites = o.geometricBounds;
    items.push(it);
}
r.seleccion = {total: sel.length, elementos: items};
return json(r);
