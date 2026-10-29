// Rellena un índice de Cuadros/Gráficos/Esquemas/Recuadros usando el diseño
// de columna de "Indices limpio.indd" (banda azul + título + entradas) como
// plantilla, generando tantas columnas y páginas nuevas como haga falta para
// que quepa todo el contenido, sin mezclar categorías entre sí.
//
// Variables que debe definir el script lanzador antes de #include/evalFile:
//   TEMPLATE_PATH, JSON_PATH (archivo .jsx con INDICE_DATA), OUTPUT_PATH, LOG_PATH
// y, opcional, PDF_PATH (si se define, exporta ahí un PDF para revisar).

var CATEGORIAS_ORDEN = [
    "Cuadro", "Gráfico", "Esquema", "Figura", "Recuadro",
    "Table", "Chart", "Schema", "Figure", "Box"
];
// Título completo de cada categoría (el estilo de párrafo lo pone en
// mayúsculas automáticamente, así que basta con escribirlo en minúsculas).
var TITULO_INDICE = {
    "Cuadro": "índice de cuadros",
    "Gráfico": "índice de gráficos",
    "Esquema": "índice de esquemas",
    "Figura": "índice de figuras",
    "Recuadro": "índice de recuadros",
    "Table": "index of tables",
    "Chart": "index of charts",
    "Schema": "index of schemas",
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

// Quita del título las marcas <i>…</i> de las cursivas del PDF y apunta en
// `cursivas` dónde quedan en la historia, como [inicio, fin) contando desde
// `inicio` (posición del título en la historia).
function quitarMarcasCursiva(titulo, inicio, cursivas) {
    var marca = /<\/?i>/g, m, limpio = "", ultimo = 0, desde = -1;
    while ((m = marca.exec(titulo)) !== null) {
        limpio += titulo.substring(ultimo, m.index);
        ultimo = marca.lastIndex;
        if (m[0] === "<i>") {
            desde = inicio + limpio.length;
        } else if (desde >= 0) {
            cursivas.push([desde, inicio + limpio.length]);
            desde = -1;
        }
    }
    limpio += titulo.substring(ultimo);
    if (desde >= 0) cursivas.push([desde, inicio + limpio.length]);
    return limpio;
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
    var estiloCursiva = doc.characterStyles.item("Light Italic");
    if (!estiloCursiva.isValid) log("ADVERTENCIA: no existe el estilo de carácter 'Light Italic'; las cursivas quedan en redonda");

    // Usamos la página 1 como plantilla pristina de columna (banner + L + R).
    while (doc.pages.length > 1) doc.pages[doc.pages.length - 1].remove();
    var paginaPristina = doc.pages[0];
    var cols0 = clasificarColumnas(paginaPristina);
    if (!cols0.bannerItem || !cols0.Ltitle || !cols0.Lentries || !cols0.Rtitle || !cols0.Rentries) {
        throw new Error("No se pudieron identificar las columnas de la plantilla");
    }
    log("Columnas de plantilla identificadas en página 1");

    // Columnas de entradas en orden de lectura (izquierda y derecha de cada
    // página), cada una con su marco de título encima.
    var columnas = [];

    function nuevaPaginaDeTrabajo() {
        // Se duplica el pliego y no la página: una página duplicada «después
        // de» otra se mete en su mismo pliego y acababan todas en uno solo.
        var pliego = paginaPristina.parent.duplicate(LocationOptions.AT_END);
        var nueva = pliego.pages[0];
        var cols = clasificarColumnas(nueva);
        // La plantilla trae la columna L enhebrada a la R: se rompe y se vacía
        // todo; el enhebrado se rehace abajo, columna a columna.
        if (cols.Lentries.nextTextFrame !== null) cols.Lentries.nextTextFrame = null;
        if (cols.Rentries.nextTextFrame !== null) cols.Rentries.nextTextFrame = null;
        cols.Ltitle.contents = "";
        cols.Rtitle.contents = "";
        cols.Lentries.contents = "";
        cols.Rentries.contents = "";
        columnas.push({ entradas: cols.Lentries, titulo: cols.Ltitle });
        columnas.push({ entradas: cols.Rentries, titulo: cols.Rtitle });
        log("Nueva página de trabajo creada: " + nueva.name);
    }

    function columnaDe(parrafo) {
        var marco = parrafo.parentTextFrames[0];
        for (var k = 0; k < columnas.length; k++) {
            if (columnas[k].entradas.id === marco.id) return k;
        }
        return -1;
    }

    // Todas las entradas van en una sola historia enhebrada por todas las
    // columnas; cada tipo de índice acaba en un salto de columna para que el
    // siguiente empiece en columna nueva.
    var lineas = [];
    var posicion = 0; // caracteres de la historia antes de la línea actual
    var cursivas = []; // tramos [inicio, fin) que van en «Light Italic»
    function anadirLinea(texto) {
        lineas.push(texto);
        posicion += texto.length + 1; // + el retorno
    }
    var indices = []; // tipos presentes: categoría, primer y último párrafo
    for (var c = 0; c < CATEGORIAS_ORDEN.length; c++) {
        var categoria = CATEGORIAS_ORDEN[c];
        var entradas = datos[categoria];
        if (!entradas || entradas.length === 0) {
            log(categoria + ": sin entradas, se omite");
            continue;
        }
        var indice = { categoria: categoria, primero: lineas.length, entradas: entradas.length };
        var capituloAnterior = null;
        for (var e = 0; e < entradas.length; e++) {
            var entry = entradas[e];
            var capitulo = entry.numero.split(".")[0];
            if (capituloAnterior !== null && capitulo !== capituloAnterior) {
                anadirLinea(""); // retorno de carro extra al cambiar de capítulo
            }
            capituloAnterior = capitulo;
            // Espacio largo (Em space) entre el título y el número de página.
            var antes = entry.numero + "\t";
            var tituloLimpio = quitarMarcasCursiva(entry.titulo, posicion + antes.length, cursivas);
            anadirLinea(antes + tituloLimpio + " " + entry.pagina);
        }
        indice.ultimo = lineas.length - 1;
        indices.push(indice);
    }
    if (indices.length === 0) throw new Error("No hay ninguna entrada que maquetar");

    nuevaPaginaDeTrabajo();
    columnas[0].entradas.nextTextFrame = columnas[1].entradas;
    columnas[0].entradas.contents = lineas.join("\r");
    var historia = columnas[0].entradas.parentStory;
    historia.paragraphs.everyItem().appliedParagraphStyle = estiloEntrada;
    for (var k = 0; k < indices.length - 1; k++) {
        // El retorno final del último párrafo de cada tipo pasa a ser un salto de columna
        historia.paragraphs[indices[k].ultimo].characters.lastItem().contents = SpecialCharacters.COLUMN_BREAK;
    }

    var vueltas = 0;
    while (historia.textContainers[historia.textContainers.length - 1].overflows && vueltas < 100) {
        var ultima = columnas[columnas.length - 1].entradas;
        nuevaPaginaDeTrabajo();
        ultima.nextTextFrame = columnas[columnas.length - 2].entradas;
        columnas[columnas.length - 2].entradas.nextTextFrame = columnas[columnas.length - 1].entradas;
        vueltas++;
    }
    if (vueltas >= 100) log("ADVERTENCIA: el texto sigue desbordando tras 100 páginas");
    if (estiloCursiva.isValid) {
        for (var k = 0; k < cursivas.length; k++) {
            if (cursivas[k][1] <= cursivas[k][0]) continue;
            historia.characters.itemByRange(cursivas[k][0], cursivas[k][1] - 1).appliedCharacterStyle = estiloCursiva;
        }
        if (cursivas.length) log("Cursivas: " + cursivas.length + " tramo(s) con el estilo 'Light Italic'");
    }
    historia.recompose();

    // La cabecera de cada índice se repite, igual, sobre todas sus columnas.
    for (var k = 0; k < indices.length; k++) {
        var desde = columnaDe(historia.paragraphs[indices[k].primero]);
        var hasta = columnaDe(historia.paragraphs[indices[k].ultimo]);
        if (desde < 0) throw new Error(indices[k].categoria + ": no se encuentra la columna donde empieza");
        if (hasta < desde) throw new Error(indices[k].categoria + ": no se encuentra la columna donde acaba");
        for (var col = desde; col <= hasta; col++) {
            var titulo = columnas[col].titulo;
            titulo.contents = TITULO_INDICE[indices[k].categoria];
            titulo.parentStory.paragraphs.everyItem().appliedParagraphStyle = estiloTitulo;
        }
        log(indices[k].categoria + ": " + indices[k].entradas + " entradas insertadas en " + (hasta - desde + 1) + " columna(s)");
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
