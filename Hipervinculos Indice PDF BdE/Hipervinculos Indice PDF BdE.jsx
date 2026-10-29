/*
  Hipervinculos Indice PDF BdE

  Crea hipervínculos automáticos en el artículo de texto seleccionado de un
  índice (cuadros, gráficos, esquemas, recuadros...), como haría una Tabla de
  Contenido de InDesign. Cada entrada con el formato

      número<TAB>título<ESPACIO LARGO>página

  se vincula a esa página dentro de un Libro de InDesign (.indb), que el
  script te pide elegir al arrancar.

  Libro:
  - Si ya hay libros abiertos en InDesign, se pregunta cuál usar (o se
    ofrece buscar otro .indb en disco).
  - Si no hay ninguno abierto, se abre directamente el selector de archivos.

  Ámbito:
  - Solo se procesa el artículo (texto enlazado) de la selección: un marco
    de texto, texto seleccionado o el cursor dentro del índice.
  - Solo se vinculan los párrafos cuya página va precedida de un espacio
    largo (o tabulador); encabezados y demás párrafos se ignoran.

  Si vuelves a ejecutarlo sobre el mismo artículo, primero borra los vínculos
  que creó la vez anterior en ese artículo (y sus destinos), y los rehace.
  Todo el proceso se deshace de una vez con Edición > Deshacer.

  Uso:
  1. Abre el INDD que contiene los índices.
  2. Coloca el cursor (o selecciona el marco) en el índice que quieras vincular.
  3. Ejecuta este script y elige el Libro (.indb) cuando se te pida.
  4. Exporta el Libro como Adobe PDF interactivo con "Hipervínculos" activado.
*/

var CONFIG = {
  usePageNameFirst: true,
  pageIndexOffset: 0,
  linkLabelKey: 'codexIndiceVariosAutoLink',
  linkLabelValue: '1',
  namePrefix: 'IndiceVarios_p'
};

// Ejecución sin diálogos (solo para pruebas automatizadas): definir antes
// $.global.INDICES_VARIOS_AUTO = { document: Document, story: Story, bookFile: File }
var AUTO = (typeof $.global.INDICES_VARIOS_AUTO !== 'undefined') ? $.global.INDICES_VARIOS_AUTO : null;

function trimText(value) {
  return String(value).replace(/^\s+|\s+$/g, '');
}

function cleanName(value) {
  return String(value).replace(/[\\\/:*?"<>|]/g, '_');
}

// En macOS /private/tmp y /tmp (o /private/var y /var) son la misma carpeta.
function normPath(fileObj) {
  var path;
  try {
    path = File(fileObj).fsName;
  } catch (e) {
    path = String(fileObj);
  }
  return path.replace(/^\/private(\/(?:tmp|var|etc)\/)/, '$1');
}

function sameFile(a, b) {
  return normPath(a).toLowerCase() === normPath(b).toLowerCase();
}

// Reutiliza el Libro si ya está abierto: abrirlo otra vez da error.
function openBook(file) {
  for (var i = 0; i < app.books.length; i++) {
    if (sameFile(app.books[i].fullName, file)) {
      return app.books[i];
    }
  }
  return app.open(file);
}

function browseForBook() {
  // En Windows el filtro va como «Descripción:*.ext»; en Mac se ignora.
  var filtro = File.fs === 'Windows' ? 'Libro de InDesign:*.indb' : null;
  var file = File.openDialog('Selecciona el Libro de InDesign (.indb) con el documento final', filtro, false);
  if (!file) {
    return null;
  }
  try {
    return openBook(file);
  } catch (e) {
    avisar('No se pudo abrir el Libro seleccionado: ' + e);
    return null;
  }
}

function pickBook() {
  if (app.books.length === 0) {
    return browseForBook();
  }
  if (app.books.length === 1) {
    var onlyBook = app.books[0];
    var useIt = confirm('Se usará el Libro ya abierto:\n' + onlyBook.name + '\n\n¿Es correcto? (Cancelar para buscar otro .indb)');
    return useIt ? onlyBook : browseForBook();
  }

  var w = new Window('dialog', 'Selecciona el Libro de InDesign');
  w.orientation = 'column';
  w.alignChildren = 'fill';
  w.add('statictext', undefined, 'Hay varios Libros abiertos. Elige el que quieras usar para crear los hipervínculos:');
  var list = w.add('listbox', undefined, [], { multiselect: false });
  for (var i = 0; i < app.books.length; i++) {
    list.add('item', app.books[i].name);
  }
  list.selection = 0;

  var buttons = w.add('group');
  buttons.alignment = 'right';
  var browseBtn = buttons.add('button', undefined, 'Buscar otro…');
  var cancelBtn = buttons.add('button', undefined, 'Cancelar', { name: 'cancel' });
  var okBtn = buttons.add('button', undefined, 'Aceptar', { name: 'ok' });

  var browseInstead = false;
  okBtn.onClick = function () { w.close(1); };
  cancelBtn.onClick = function () { w.close(0); };
  browseBtn.onClick = function () { browseInstead = true; w.close(0); };

  var result = w.show();
  if (browseInstead) {
    return browseForBook();
  }
  if (result === 1 && list.selection) {
    return app.books[list.selection.index];
  }
  return null;
}

function selectedStory() {
  if (app.selection.length === 0) {
    return null;
  }
  var item = app.selection[0];
  try {
    if (item.hasOwnProperty('parentStory') && item.parentStory && item.parentStory.isValid) {
      return item.parentStory;
    }
  } catch (e) {}
  try {
    if (item.parent && item.parent.hasOwnProperty('parentStory') && item.parent.parentStory && item.parent.parentStory.isValid) {
      return item.parent.parentStory;
    }
  } catch (e) {}
  return null;
}

function hasAutoLabel(obj) {
  try {
    return obj.extractLabel(CONFIG.linkLabelKey) === CONFIG.linkLabelValue;
  } catch (e) {
    return false;
  }
}

function sourceInStory(source, story) {
  try {
    return source.sourceText.parentStory === story;
  } catch (e) {
    return false;
  }
}

// Borra los vínculos automáticos que el script creó antes en este artículo y,
// después, los destinos automáticos que hayan quedado sin ningún vínculo.
function removePreviousAutoLinks(doc, story) {
  var i;
  for (i = doc.hyperlinks.length - 1; i >= 0; i--) {
    var link = doc.hyperlinks[i];
    if (hasAutoLabel(link) && sourceInStory(link.source, story)) {
      link.remove();
    }
  }
  for (i = doc.hyperlinkTextSources.length - 1; i >= 0; i--) {
    var source = doc.hyperlinkTextSources[i];
    if (hasAutoLabel(source) && sourceInStory(source, story)) {
      source.remove();
    }
  }

  var used = {};
  for (i = 0; i < doc.hyperlinks.length; i++) {
    try {
      used[doc.hyperlinks[i].destination.id] = true;
    } catch (e) {}
  }
  var collections = [doc.hyperlinkExternalPageDestinations, doc.hyperlinkPageDestinations];
  for (var c = 0; c < collections.length; c++) {
    for (i = collections[c].length - 1; i >= 0; i--) {
      var dest = collections[c][i];
      if (hasAutoLabel(dest) && !used[dest.id]) {
        dest.remove();
      }
    }
  }
}

// Página final de la entrada: solo si va tras un espacio largo o tabulador.
function paragraphPageNumber(paragraph) {
  var contents = trimText(paragraph.contents);
  var match = contents.match(/[ \t]\s*(\d+)$/);
  return match ? parseInt(match[1], 10) : null;
}

function paragraphSourceText(paragraph) {
  var lastIndex = paragraph.characters.length - 1;
  while (lastIndex > 0 && paragraph.characters[lastIndex].contents === '\r') {
    lastIndex--;
  }
  return paragraph.characters.itemByRange(paragraph.characters[0], paragraph.characters[lastIndex]);
}

function findPageInDocument(doc, pageNumber) {
  if (CONFIG.usePageNameFirst) {
    var wanted = String(pageNumber);
    for (var i = 0; i < doc.pages.length; i++) {
      if (String(doc.pages[i].name) === wanted) {
        return doc.pages[i];
      }
    }
  }
  var absoluteIndex = pageNumber - 1 + CONFIG.pageIndexOffset;
  if (absoluteIndex >= 0 && absoluteIndex < doc.pages.length) {
    return doc.pages[absoluteIndex];
  }
  return null;
}

function parseBookPageRange(rangeText) {
  var ranges = [];
  var parts = String(rangeText).replace(/\s+/g, '').split(',');
  for (var i = 0; i < parts.length; i++) {
    var match = parts[i].match(/^(\d+)(?:-(\d+))?$/);
    if (match) {
      var start = parseInt(match[1], 10);
      var end = match[2] ? parseInt(match[2], 10) : start;
      ranges.push({ start: start, end: end });
    }
  }
  return ranges;
}

function buildBookMap(book) {
  var map = [];
  for (var i = 0; i < book.bookContents.length; i++) {
    var content = book.bookContents[i];
    var ranges = parseBookPageRange(content.documentPageRange);
    for (var r = 0; r < ranges.length; r++) {
      map.push({ file: content.fullName, start: ranges[r].start, end: ranges[r].end });
    }
  }
  return map;
}

function findBookTarget(bookMap, pageNumber) {
  for (var i = 0; i < bookMap.length; i++) {
    var item = bookMap[i];
    if (pageNumber >= item.start && pageNumber <= item.end) {
      return { file: item.file, localPageIndexOneBased: pageNumber - item.start + 1 };
    }
  }
  return null;
}

function labelDestination(destination) {
  try {
    destination.viewSetting = HyperlinkDestinationPageSetting.FIT_WINDOW;
  } catch (e) {}
  try {
    destination.insertLabel(CONFIG.linkLabelKey, CONFIG.linkLabelValue);
  } catch (e) {}
  return destination;
}

function getOrCreatePageDestination(doc, page) {
  var destination = doc.hyperlinkPageDestinations.itemByName(CONFIG.namePrefix + cleanName(page.name));
  if (destination.isValid) {
    return destination;
  }
  return labelDestination(doc.hyperlinkPageDestinations.add(page, { name: CONFIG.namePrefix + cleanName(page.name) }));
}

// Los destinos externos son ocultos y InDesign no deja compartirlos entre
// vínculos: se crea uno por entrada (los huérfanos se borran al repetir).
function createExternalPageDestination(doc, bookTarget) {
  var destination = doc.hyperlinkExternalPageDestinations.add();
  destination.documentPath = File(bookTarget.file);
  destination.destinationPageIndex = bookTarget.localPageIndexOneBased;
  return labelDestination(destination);
}

function uniqueHyperlinkName(doc, pageNumber) {
  var base = CONFIG.namePrefix + pageNumber;
  var name = base;
  var n = 2;
  while (doc.hyperlinks.itemByName(name).isValid) {
    name = base + '_' + n;
    n++;
  }
  return name;
}

function createHyperlinkForParagraph(doc, paragraph, pageNumber, destination, report) {
  var source = null;
  try {
    source = doc.hyperlinkTextSources.add(paragraphSourceText(paragraph));
    try {
      source.insertLabel(CONFIG.linkLabelKey, CONFIG.linkLabelValue);
    } catch (e) {}

    var hyperlink = doc.hyperlinks.add(source, destination, { name: uniqueHyperlinkName(doc, pageNumber) });
    try {
      hyperlink.visible = false;
    } catch (e) {}
    try {
      hyperlink.insertLabel(CONFIG.linkLabelKey, CONFIG.linkLabelValue);
    } catch (e) {}
    report.created++;
  } catch (e) {
    try {
      if (source && source.isValid) source.remove();
    } catch (e2) {}
    report.errors.push('Página ' + pageNumber + ': ' + e);
  }
}

function linkStory(doc, story, bookMap, report) {
  removePreviousAutoLinks(doc, story);
  var paragraphs = story.paragraphs.everyItem().getElements();
  for (var p = 0; p < paragraphs.length; p++) {
    var paragraph = paragraphs[p];
    report.scanned++;
    var pageNumber = paragraphPageNumber(paragraph);
    if (!pageNumber) {
      report.ignored++;
      continue;
    }

    var destination = null;
    var bookTarget = findBookTarget(bookMap, pageNumber);
    if (bookTarget && !sameFile(bookTarget.file, doc.fullName)) {
      destination = createExternalPageDestination(doc, bookTarget);
    } else if (bookTarget) {
      var page = findPageInDocument(doc, pageNumber);
      if (page) {
        destination = getOrCreatePageDestination(doc, page);
      }
    }

    if (!destination) {
      report.missingPages.push(pageNumber);
      continue;
    }
    createHyperlinkForParagraph(doc, paragraph, pageNumber, destination, report);
  }
}

function avisar(msg) {
  if (AUTO) {
    AUTO.messages = (AUTO.messages || []).concat([String(msg)]);
  } else {
    alert(msg);
  }
}

function main() {
  var doc, story, book;

  if (AUTO) {
    doc = AUTO.document;
    story = AUTO.story;
    book = openBook(File(AUTO.bookFile));
  } else {
    if (app.documents.length === 0) {
      avisar('Abre primero el documento de InDesign que contiene los índices.');
      return;
    }
    doc = app.activeDocument;
    story = selectedStory();
    if (!story) {
      avisar('Coloca el cursor o selecciona el marco de texto del índice que quieres vincular y vuelve a ejecutar el script.');
      return;
    }
    book = pickBook();
    if (!book) {
      avisar('No se ha seleccionado ningún Libro. El script no puede continuar sin un .indb.');
      return;
    }
  }

  var bookMap = buildBookMap(book);
  if (bookMap.length === 0) {
    avisar('No se ha podido leer el rango de páginas del Libro seleccionado. Comprueba que el .indb está actualizado.');
    return;
  }

  var report = { scanned: 0, created: 0, missingPages: [], ignored: 0, errors: [] };
  var failure = null;
  app.doScript(function () {
    try {
      linkStory(doc, story, bookMap, report);
    } catch (e) {
      failure = e;
    }
  }, ScriptLanguage.JAVASCRIPT, undefined, UndoModes.ENTIRE_SCRIPT, 'Crear hipervínculos del índice');
  if (failure) {
    avisar('Error al crear los hipervínculos (línea ' + failure.line + '):\r' + failure);
    return;
  }

  if (doc.saved) {
    doc.save();
  }

  var message = [
    'Hipervínculos del índice creados.',
    'Libro: ' + book.name,
    'Párrafos revisados: ' + report.scanned,
    'Hipervínculos creados: ' + report.created,
    'Párrafos ignorados (sin página): ' + report.ignored,
    'Páginas no encontradas en el Libro: ' + report.missingPages.length
  ];
  if (report.missingPages.length) {
    message.push('Listado: ' + report.missingPages.join(', '));
  }
  if (report.errors.length) {
    message.push('Errores:');
    message.push(report.errors.join('\r'));
  }

  if (AUTO) {
    AUTO.report = report;
  } else {
    avisar(message.join('\r'));
  }
}

main();
