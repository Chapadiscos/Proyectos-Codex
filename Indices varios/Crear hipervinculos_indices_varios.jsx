/*
  Crea hipervínculos automáticos en el/los artículo(s) de texto del índice.
  Cada párrafo que termine con un número de página se vincula a esa página
  dentro de un Libro de InDesign (.indb), que el script te pide elegir al
  arrancar. Pensado para reutilizarse tal cual con distintos índices, cada
  uno con su propio libro.

  Libro:
  - Si ya hay libros abiertos en InDesign, se pregunta cuál usar (o se
    ofrece buscar otro .indb en disco).
  - Si no hay ninguno abierto, se abre directamente el selector de archivos
    para elegir el .indb.

  Ámbito:
  - Si hay una selección (marco de texto, texto o cursor), solo se procesa
    ese artículo.
  - Si no hay selección (p.ej. al lanzar el script por automatización), se
    procesan automáticamente TODOS los artículos de texto en página del
    documento activo.

  Uso recomendado:
  1. Abre el INDD que contiene los índices.
  2. (Opcional) Selecciona un marco de texto, texto o cursor dentro del
     índice que quieras vincular; si no seleccionas nada se procesa todo
     el documento.
  3. Ejecuta este script y elige el Libro (.indb) cuando se te pida.
  4. Exporta como Adobe PDF interactivo con "Hipervínculos" activado.
*/

var CONFIG = {
  mode: 'book',
  usePageNameFirst: true,
  pageIndexOffset: 0,
  removePreviousAutoLinks: true,
  hyperlinkFullParagraph: true,
  linkLabelKey: 'codexIndiceVariosAutoLink',
  linkLabelValue: '1',
  namePrefix: 'IndiceVarios_p'
};

app.scriptPreferences.userInteractionLevel = UserInteractionLevels.INTERACT_WITH_ALL;

if (app.documents.length === 0) {
  alert('Abre primero el documento de InDesign que contiene los índices.');
  exit();
}

var sourceDoc = app.activeDocument;

function browseForBook() {
  var file = File.openDialog('Selecciona el Libro de InDesign (.indb) con el documento final', '*.indb', false);
  if (!file) {
    return null;
  }
  try {
    return app.open(file);
  } catch (e) {
    alert('No se pudo abrir el Libro seleccionado: ' + e);
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

  var pickedBook = null;
  var browseInstead = false;
  okBtn.onClick = function () { w.close(1); };
  cancelBtn.onClick = function () { w.close(0); };
  browseBtn.onClick = function () { browseInstead = true; w.close(0); };

  var result = w.show();
  if (browseInstead) {
    return browseForBook();
  }
  if (result === 1 && list.selection) {
    pickedBook = app.books[list.selection.index];
  }
  return pickedBook;
}

var selectedBook = pickBook();
if (!selectedBook) {
  alert('No se ha seleccionado ningún Libro. El script no puede continuar sin un .indb.');
  exit();
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
    if (item.constructor && item.constructor.name === 'TextFrame' && item.parentStory && item.parentStory.isValid) {
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

// Con selección: solo esa historia (comportamiento manual de siempre).
// Sin selección (p.ej. al lanzar el script desde automatización): todas
// las historias del documento que tengan algún marco de texto en página.
var targetStories = [];
var singleStory = selectedStory();
if (singleStory) {
  targetStories.push(singleStory);
} else {
  for (var st = 0; st < sourceDoc.stories.length; st++) {
    var story = sourceDoc.stories[st];
    if (story.textContainers.length === 0) continue;
    var onPage = false;
    for (var tc = 0; tc < story.textContainers.length; tc++) {
      try {
        if (story.textContainers[tc].parentPage) { onPage = true; break; }
      } catch (e) {}
    }
    if (onPage) targetStories.push(story);
  }
  if (targetStories.length === 0) {
    alert('No se ha encontrado ningún artículo de texto en página. Selecciona un marco de texto o coloca el cursor dentro del índice.');
    exit();
  }
}

function normPath(fileObj) {
  try {
    return File(fileObj).fsName;
  } catch (e) {
    return String(fileObj);
  }
}

function sameFile(a, b) {
  return normPath(a).toLowerCase() === normPath(b).toLowerCase();
}

function trimText(value) {
  return String(value).replace(/^\s+|\s+$/g, '');
}

function cleanName(value) {
  return String(value).replace(/[\\\/:*?"<>|]/g, '_');
}

function isTargetStory(story) {
  for (var i = 0; i < targetStories.length; i++) {
    if (targetStories[i] === story) return true;
  }
  return false;
}

function sourceBelongsToStory(hyperlink) {
  try {
    var source = hyperlink.source;
    if (source.constructor.name === 'HyperlinkTextSource') {
      return isTargetStory(source.sourceText.parentStory);
    }
  } catch (e) {}
  return false;
}

function removePreviousAutoLinksInTargetStories(doc) {
  var i;
  for (i = doc.hyperlinks.length - 1; i >= 0; i--) {
    try {
      if (
        doc.hyperlinks[i].extractLabel(CONFIG.linkLabelKey) === CONFIG.linkLabelValue &&
        sourceBelongsToStory(doc.hyperlinks[i])
      ) {
        doc.hyperlinks[i].remove();
      }
    } catch (e) {}
  }
  for (i = doc.hyperlinkTextSources.length - 1; i >= 0; i--) {
    try {
      if (
        doc.hyperlinkTextSources[i].extractLabel(CONFIG.linkLabelKey) === CONFIG.linkLabelValue &&
        isTargetStory(doc.hyperlinkTextSources[i].sourceText.parentStory)
      ) {
        doc.hyperlinkTextSources[i].remove();
      }
    } catch (e) {}
  }
}

function paragraphPageNumber(paragraph) {
  var contents = trimText(paragraph.contents).replace(/\r$/, '');
  var match = contents.match(/(?:\u2003|\s)(\d+)\s*$/);
  return match ? parseInt(match[1], 10) : null;
}

function paragraphSourceText(paragraph) {
  var lastIndex = paragraph.characters.length - 1;
  while (lastIndex > 0 && paragraph.characters[lastIndex].contents === '\r') {
    lastIndex--;
  }
  return paragraph.characters.itemByRange(paragraph.characters[0], paragraph.characters[lastIndex]);
}

function findPageByVisibleName(doc, pageNumber) {
  var wanted = String(pageNumber);
  for (var i = 0; i < doc.pages.length; i++) {
    if (String(doc.pages[i].name) === wanted) {
      return doc.pages[i];
    }
  }
  return null;
}

function findPageInDocument(doc, pageNumber) {
  var page = null;
  if (CONFIG.usePageNameFirst) {
    page = findPageByVisibleName(doc, pageNumber);
  }
  if (page && page.isValid) {
    return page;
  }
  var absoluteIndex = pageNumber - 1 + CONFIG.pageIndexOffset;
  if (absoluteIndex >= 0 && absoluteIndex < doc.pages.length) {
    return doc.pages[absoluteIndex];
  }
  return null;
}

function getOrCreatePageDestination(doc, page) {
  var destinationName = CONFIG.namePrefix + cleanName(page.name);
  var destination = doc.hyperlinkPageDestinations.itemByName(destinationName);
  if (destination.isValid) {
    return destination;
  }
  destination = doc.hyperlinkPageDestinations.add(page, { name: destinationName });
  try {
    destination.viewSetting = HyperlinkDestinationPageSetting.FIT_WINDOW;
  } catch (e) {}
  try {
    destination.insertLabel(CONFIG.linkLabelKey, CONFIG.linkLabelValue);
  } catch (e) {}
  return destination;
}

function parseBookPageRange(rangeText) {
  var ranges = [];
  var parts = String(rangeText).replace(/\s+/g, '').split(',');
  for (var i = 0; i < parts.length; i++) {
    var part = parts[i];
    var match = part.match(/^(\d+)(?:-(\d+))?$/);
    if (match) {
      var start = parseInt(match[1], 10);
      var end = match[2] ? parseInt(match[2], 10) : start;
      ranges.push({ start: start, end: end });
    }
  }
  return ranges;
}

function buildBookMap() {
  var book = selectedBook;
  var map = [];
  for (var i = 0; i < book.bookContents.length; i++) {
    var content = book.bookContents[i];
    var ranges = parseBookPageRange(content.documentPageRange);
    for (var r = 0; r < ranges.length; r++) {
      map.push({
        file: content.fullName,
        start: ranges[r].start,
        end: ranges[r].end
      });
    }
  }
  return map;
}

function findBookTarget(bookMap, pageNumber) {
  if (!bookMap) {
    return null;
  }
  for (var i = 0; i < bookMap.length; i++) {
    var item = bookMap[i];
    if (pageNumber >= item.start && pageNumber <= item.end) {
      return {
        file: item.file,
        localPageIndexOneBased: pageNumber - item.start + 1
      };
    }
  }
  return null;
}

function createExternalPageDestination(doc, bookTarget, pageNumber) {
  var destination = doc.hyperlinkExternalPageDestinations.add();
  destination.documentPath = File(bookTarget.file);
  destination.destinationPageIndex = bookTarget.localPageIndexOneBased;
  try {
    destination.viewSetting = HyperlinkDestinationPageSetting.FIT_WINDOW;
  } catch (e) {}
  try {
    destination.insertLabel(CONFIG.linkLabelKey, CONFIG.linkLabelValue);
  } catch (e) {}
  return destination;
}

function createHyperlinkForParagraph(paragraph, pageNumber, destination, report) {
  try {
    var sourceText = paragraphSourceText(paragraph);
    var source = sourceDoc.hyperlinkTextSources.add(sourceText);
    try {
      source.appliedCharacterStyle = sourceDoc.characterStyles.itemByName('[None]');
    } catch (e) {}
    try {
      source.insertLabel(CONFIG.linkLabelKey, CONFIG.linkLabelValue);
    } catch (e) {}

    var hyperlinkName = CONFIG.namePrefix + pageNumber + '_' + report.created;
    var hyperlink = sourceDoc.hyperlinks.add(source, destination, { name: hyperlinkName });
    try {
      hyperlink.visible = false;
    } catch (e) {}
    try {
      hyperlink.insertLabel(CONFIG.linkLabelKey, CONFIG.linkLabelValue);
    } catch (e) {}
    report.created++;
  } catch (e) {
    report.errors.push('No se pudo crear el vínculo a la página ' + pageNumber + ': ' + e);
  }
}

if (CONFIG.removePreviousAutoLinks) {
  removePreviousAutoLinksInTargetStories(sourceDoc);
}

var bookMap = buildBookMap();
if (!bookMap || bookMap.length === 0) {
  alert('No se ha podido leer el rango de páginas del Libro seleccionado. Comprueba que el .indb está actualizado.');
  exit();
}
var report = {
  scanned: 0,
  created: 0,
  missingPages: [],
  ignored: 0,
  errors: []
};

for (var s = 0; s < targetStories.length; s++) {
  var targetStory = targetStories[s];
  for (var p = 0; p < targetStory.paragraphs.length; p++) {
    var paragraph = targetStory.paragraphs[p];
    report.scanned++;
    var pageNumber = paragraphPageNumber(paragraph);
    if (!pageNumber) {
      report.ignored++;
      continue;
    }

    var destination = null;
    var bookTarget = findBookTarget(bookMap, pageNumber);
    if (bookTarget && !sameFile(bookTarget.file, sourceDoc.fullName)) {
      destination = createExternalPageDestination(sourceDoc, bookTarget, pageNumber);
    } else if (bookTarget) {
      var currentDocPage = findPageInDocument(sourceDoc, pageNumber);
      if (currentDocPage) {
        destination = getOrCreatePageDestination(sourceDoc, currentDocPage);
      }
    }

    if (!destination) {
      report.missingPages.push(pageNumber);
      continue;
    }
    createHyperlinkForParagraph(paragraph, pageNumber, destination, report);
  }
}

sourceDoc.save();

var message = [
  'Hipervínculos de índices creados.',
  'Libro: ' + selectedBook.name,
  'Ámbito: ' + (singleStory ? 'artículo seleccionado' : 'todo el documento (' + targetStories.length + ' artículo(s))'),
  'Párrafos revisados: ' + report.scanned,
  'Hipervínculos creados: ' + report.created,
  'Párrafos ignorados sin página final: ' + report.ignored,
  'Páginas no encontradas: ' + report.missingPages.length
];

if (report.missingPages.length) {
  message.push('Listado de páginas no encontradas: ' + report.missingPages.join(', '));
}
if (report.errors.length) {
  message.push('Errores:');
  message.push(report.errors.join('\r'));
}

alert(message.join('\r'));
