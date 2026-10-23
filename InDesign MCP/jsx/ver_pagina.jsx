// Exporta una página del documento activo a PNG en ARGS.ruta.
// ARGS.pagina: nombre de la página (el que se ve en el panel Páginas); vacío = la visible.
if (app.documents.length === 0) throw new Error("No hay ningún documento abierto");
var doc = app.activeDocument;
var pag = ARGS.pagina ? doc.pages.itemByName(String(ARGS.pagina)) : app.activeWindow.activePage;
if (!pag.isValid) throw new Error("No existe la página «" + ARGS.pagina + "»");

// Las preferencias de exportación PNG son de la aplicación: se guardan y se restauran.
var pref = app.pngExportPreferences;
var claves = ["pngExportRange", "pageString", "exportResolution", "pngQuality",
              "exportingSpread", "transparentBackground", "antiAlias", "useDocumentBleeds"];
var antes = {};
for (var i = 0; i < claves.length; i++) antes[claves[i]] = pref[claves[i]];
try {
    pref.pngExportRange = PNGExportRangeEnum.EXPORT_RANGE;
    pref.pageString = "+" + (pag.documentOffset + 1);  // numeración absoluta, evita líos con secciones
    pref.exportResolution = ARGS.resolucion;
    pref.pngQuality = PNGQualityEnum.HIGH;
    pref.exportingSpread = false;
    pref.transparentBackground = false;
    pref.antiAlias = true;
    pref.useDocumentBleeds = false;
    doc.exportFile(ExportFormat.PNG_FORMAT, File(ARGS.ruta), false);
} finally {
    for (var k in antes) pref[k] = antes[k];
}

var b = pag.bounds;  // [y1, x1, y2, x2] en las unidades de la regla
return json({
    pagina: pag.name,
    posicion: pag.documentOffset + 1,
    de: doc.pages.length,
    ancho: b[3] - b[1],
    alto: b[2] - b[0],
    unidades: String(doc.viewPreferences.horizontalMeasurementUnits).replace(/^.*\./, "")
});
