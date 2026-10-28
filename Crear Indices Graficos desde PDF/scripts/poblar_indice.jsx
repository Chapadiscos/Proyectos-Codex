// Rellena un índice de Cuadros/Gráficos/Esquemas/Recuadros usando el diseño
// de columna de "Indices limpio.indd" (banda azul + título + entradas) como
// plantilla, generando tantas columnas y páginas nuevas como haga falta para
// que quepa todo el contenido, sin mezclar categorías entre sí.
//
// Variables que debe definir el script lanzador antes de #include/evalFile:
//   TEMPLATE_PATH, JSON_PATH (archivo .jsx con INDICE_DATA), OUTPUT_PATH, LOG_PATH
// y, opcional, PDF_PATH (si se define, exporta ahí un PDF para revisar).

var CATEGORIAS_ORDEN = [
    "Cuadro", "Gráfico", "Esquema", "Recuadro",
    "Table", "Chart", "Figure", "Box"
];
// Título completo de cada categoría (el estilo de párrafo lo pone en
// mayúsculas automáticamente, así que basta con escribirlo en minúsculas).
var TITULO_INDICE = {
    "Cuadro": "índice de cuadros",
    "Gráfico": "índice de gráficos",
    "Esquema": "índice de esquemas",
    "Recuadro": "índice de recuadros",
    "Table": "index of tables",
    "Chart": "index of charts",
    "Figure": "index of figures",
    "Box": "index of boxes"
};

var _log = [];
function log(msg) { _log.push(msg); }
function flushLog() {
    var f = new File(LOG_PATH);
    f.encoding = "UTF8";
    f.lineFeed = "Unix"; // en Mac ExtendScript escribe \r por defecto
    f.open("w");
    f.write(_log.join("\n"));
    f.close();
}

function esColumnaIzquierda(bounds) {
    return Math.abs(bounds[1] - 19) < 2;
}

// Clasifica los pageItems de una página en banner / título-L / entradas-L /
// título-R / entradas-R, a partir de su geometría (izquierda/derecha, alto).
function clasificarColumnas(page) {
    var res = { bannerItem: null, Ltitle: null, Lentries: null, Rtitle: null, Rentries: null };
    for (var i = 0; i < page.pageItems.length; i++) {
        var item = page.pageItems[i];
        var b = item.geometricBounds; // [y1,x1,y2,x2]
        var alto = b[2] - b[0];
        var ancho = b[3] - b[1];
        if (ancho > 150) { res.bannerItem = item; continue; }
        var esL = esColumnaIzquierda(b);
        var esTitulo = alto < 30;
        if (esL && esTitulo) res.Ltitle = item;
        else if (esL && !esTitulo) res.Lentries = item;
        else if (!esL && esTitulo) res.Rtitle = item;
        else if (!esL && !esTitulo) res.Rentries = item;
    }
    return res;
}

// Si la plantilla ya está abierta, app.open() devolvería ese mismo documento
// y el script lo vaciaría y lo cerraría; mejor parar y avisar.
function comprobarNoAbierto(ruta) {
    var buscado = new File(ruta).fsName;
    for (var i = 0; i < app.documents.length; i++) {
        var d = app.documents[i];
        if (d.saved && d.fullName.fsName === buscado) {
            throw new Error("Cierra en InDesign el documento " + d.name + " y vuelve a lanzarlo");
        }
    }
}

function exportarPDF(doc, ruta) {
    var prefs = app.pdfExportPreferences;
    var rangoAnterior = prefs.pageRange;
    prefs.pageRange = PageRange.ALL_PAGES;
    try {
        doc.exportFile(ExportFormat.PDF_TYPE, new File(ruta), false);
    } finally {
        prefs.pageRange = rangoAnterior;
    }
}

function main() {
    $.evalFile(JSON_PATH);
    var datos = INDICE_DATA;

    var plantilla = new File(TEMPLATE_PATH);
    if (!plantilla.exists) throw new Error("No existe la plantilla: " + TEMPLATE_PATH);
    comprobarNoAbierto(TEMPLATE_PATH);
    comprobarNoAbierto(OUTPUT_PATH);
    var doc = app.open(plantilla, false);
    _docPlantilla = doc;
    log("Plantilla abierta: " + TEMPLATE_PATH);

    var estiloEntrada = doc.paragraphStyles.item("Indice Varios");
    var estiloTitulo = doc.paragraphStyles.item("Indice titulo cap");
    if (!estiloEntrada.isValid) throw new Error("No existe el estilo 'Indice Varios'");
    if (!estiloTitulo.isValid) throw new Error("No existe el estilo 'Indice titulo cap'");

    // Usamos la página 1 como plantilla pristina de columna (banner + L + R).
    while (doc.pages.length > 1) doc.pages[doc.pages.length - 1].remove();
    var paginaPristina = doc.pages[0];
    var cols0 = clasificarColumnas(paginaPristina);
    if (!cols0.bannerItem || !cols0.Ltitle || !cols0.Lentries || !cols0.Rtitle || !cols0.Rentries) {
        throw new Error("No se pudieron identificar las columnas de la plantilla");
    }
    log("Columnas de plantilla identificadas en página 1");

    var paginasTrabajo = [];

    function nuevaPaginaDeTrabajo() {
        var nueva = paginaPristina.duplicate(LocationOptions.AFTER, doc.pages.lastItem());
        var cols = clasificarColumnas(nueva);
        // Rompe cualquier enhebrado heredado de la plantilla (la propia
        // "Indices limpio.indd" trae la columna L enhebrada a la R) para que
        // cada columna nueva empiece como una story independiente; si no se
        // rompe, el desbordamiento de una categoría se cuela silenciosamente
        // en la columna de al lado sin que este script lo detecte.
        if (cols.Lentries.nextTextFrame !== null) cols.Lentries.nextTextFrame = null;
        if (cols.Rentries.nextTextFrame !== null) cols.Rentries.nextTextFrame = null;
        cols.Ltitle.contents = "";
        cols.Rtitle.contents = "";
        cols.Lentries.contents = "";
        cols.Rentries.contents = "";
        paginasTrabajo.push(nueva);
        log("Nueva página de trabajo creada: " + nueva.name);
        return { page: nueva, cols: cols };
    }

    var actual = nuevaPaginaDeTrabajo();
    var ladoActual = "L"; // columna donde toca escribir a continuación
    var columnaUsada = false; // si la columna actual ya tiene contenido

    function siguienteColumnaLibre() {
        if (!columnaUsada) return; // la columna actual sigue libre
        if (ladoActual === "L") {
            ladoActual = "R";
        } else {
            actual = nuevaPaginaDeTrabajo();
            ladoActual = "L";
        }
        columnaUsada = false;
    }

    function frameTitulo() { return ladoActual === "L" ? actual.cols.Ltitle : actual.cols.Rtitle; }
    function frameEntradas() { return ladoActual === "L" ? actual.cols.Lentries : actual.cols.Rentries; }

    function agregarColumnaContinuacion() {
        // Crea/usa la siguiente columna disponible y la enhebra a continuación
        // de la última (salto de columna). No repite el título: cada índice
        // lleva una única cabecera, en su primera columna.
        var frameAnterior = frameEntradas();
        siguienteColumnaLibre();
        columnaUsada = true;
        frameAnterior.nextTextFrame = frameEntradas();
        return frameEntradas();
    }

    for (var c = 0; c < CATEGORIAS_ORDEN.length; c++) {
        var categoria = CATEGORIAS_ORDEN[c];
        var entradas = datos[categoria];
        if (!entradas || entradas.length === 0) {
            log(categoria + ": sin entradas, se omite");
            continue;
        }

        siguienteColumnaLibre();
        columnaUsada = true;

        frameTitulo().contents = TITULO_INDICE[categoria];
        frameTitulo().parentStory.paragraphs.everyItem().appliedParagraphStyle = estiloTitulo;

        var lineas = [];
        var capituloAnterior = null;
        for (var e = 0; e < entradas.length; e++) {
            var entry = entradas[e];
            var capitulo = entry.numero.split(".")[0];
            if (capituloAnterior !== null && capitulo !== capituloAnterior) {
                lineas.push(""); // retorno de carro extra al cambiar de capítulo
            }
            capituloAnterior = capitulo;
            // Espacio largo (Em space) entre el título y el número de página.
            lineas.push(entry.numero + "\t" + entry.titulo + " " + entry.pagina);
        }

        var frameActualEntradas = frameEntradas();
        frameActualEntradas.contents = lineas.join("\r");
        frameActualEntradas.parentStory.paragraphs.everyItem().appliedParagraphStyle = estiloEntrada;

        var vueltas = 0;
        while (frameActualEntradas.overflows && vueltas < 200) {
            frameActualEntradas = agregarColumnaContinuacion();
            frameActualEntradas.parentStory.paragraphs.everyItem().appliedParagraphStyle = estiloEntrada;
            vueltas++;
        }
        if (vueltas >= 200) log(categoria + ": ADVERTENCIA posible bucle infinito de desbordamiento");

        log(categoria + ": " + entradas.length + " entradas insertadas en " + (vueltas + 1) + " columna(s)");
    }

    paginaPristina.remove();

    var outFile = new File(OUTPUT_PATH);
    doc.saveACopy(outFile);
    log("Copia guardada en: " + OUTPUT_PATH);

    if (typeof PDF_PATH !== "undefined" && PDF_PATH) {
        exportarPDF(doc, PDF_PATH);
        log("PDF de revisión exportado en: " + PDF_PATH);
    }

    doc.close(SaveOptions.NO);
    _docPlantilla = null;
    log("Documento cerrado sin guardar cambios en la plantilla original");
}

// Copia de la plantilla abierta (sin ventana) por este script; si algo falla
// a medias se cierra sin guardar para no dejarla abierta e invisible.
var _docPlantilla = null;
var _interaccionAnterior = app.scriptPreferences.userInteractionLevel;
app.scriptPreferences.userInteractionLevel = UserInteractionLevels.NEVER_INTERACT;
try {
    main();
} catch (e) {
    log("ERROR: " + e.toString() + " (line " + e.line + ")");
    if (_docPlantilla !== null && _docPlantilla.isValid) _docPlantilla.close(SaveOptions.NO);
}
app.scriptPreferences.userInteractionLevel = _interaccionAnterior;
flushLog();
