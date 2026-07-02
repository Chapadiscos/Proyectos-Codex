var templatePath = File('/Volumes/DATOS/Proyectos Codex/Extraer textos/Indices limpio.indd');
var textPath = File('/Volumes/DATOS/Proyectos Codex/Extraer textos/MS2025_indices_para_InDesign.txt');
var outputPath = File('/Volumes/DATOS/Proyectos Codex/Extraer textos/MS2025_indices_maquetado.indd');
var pdfPath = File('/Volumes/DATOS/Proyectos Codex/Extraer textos/MS2025_indices_maquetado.pdf');

app.scriptPreferences.userInteractionLevel = UserInteractionLevels.NEVER_INTERACT;
app.scriptPreferences.measurementUnit = MeasurementUnits.MILLIMETERS;

function readText(fileObj) {
  fileObj.encoding = 'UTF-8';
  fileObj.open('r');
  var text = fileObj.read();
  fileObj.close();
  return text;
}

function trimText(value) {
  return value.replace(/^\s+|\s+$/g, '');
}

function removePageTextFrames(page) {
  for (var i = page.textFrames.length - 1; i >= 0; i--) {
    page.textFrames[i].remove();
  }
}

function sectionTitle(rawTitle) {
  var t = rawTitle.toLowerCase();
  return t.replace('índice de ', 'índice de ');
}

var raw = readText(textPath);
var parts = raw.split('\f');
var sections = [];
for (var i = 0; i < parts.length; i++) {
  var lines = parts[i].replace(/\r/g, '\n').split('\n');
  var title = '';
  var body = [];
  for (var j = 0; j < lines.length; j++) {
    var line = trimText(lines[j]);
    if (!line) {
      continue;
    }
    if (!title) {
      title = line;
    } else {
      body.push(line);
    }
  }
  if (title && body.length) {
    sections.push({ title: title, body: body });
  }
}

var doc = app.open(templatePath, false);
doc.viewPreferences.rulerOrigin = RulerOrigin.PAGE_ORIGIN;
doc.documentPreferences.allowPageShuffle = true;
doc.spreads.everyItem().allowPageShuffle = true;
while (doc.pages.length > 1) {
  doc.pages[-1].remove();
}
while (doc.pages.length < sections.length) {
  doc.pages.add(LocationOptions.AT_END);
}

var titleStyle = doc.paragraphStyles.itemByName('Indice titulo cap');
var bodyStyle = doc.paragraphStyles.itemByName('Indice Varios');
if (!titleStyle.isValid) {
  throw new Error('No existe el estilo de párrafo "Indice titulo cap".');
}
if (!bodyStyle.isValid) {
  throw new Error('No existe el estilo de párrafo "Indice Varios".');
}

var titleBounds = [54.46, 19, 73, 191];
var bodyBounds = [80, 19, 276.5, 191];
var headerBounds = [38, -3, 73, 213];
var headerColor = doc.swatches.itemByName('PANTONE 7470 C 85%');
var noneColor = doc.swatches.itemByName('None');

function ensureHeaderBand(page) {
  var hasBand = false;
  for (var i = 0; i < page.rectangles.length; i++) {
    try {
      if (page.rectangles[i].fillColor.name === 'PANTONE 7470 C 85%') {
        hasBand = true;
        break;
      }
    } catch (e) {}
  }
  if (!hasBand) {
    var rect = page.rectangles.add();
    rect.geometricBounds = headerBounds;
    rect.fillColor = headerColor;
    rect.strokeColor = noneColor;
    rect.sendToBack();
  }
}

for (var p = 0; p < sections.length; p++) {
  var page = doc.pages[p];
  removePageTextFrames(page);
  ensureHeaderBand(page);

  var titleFrame = page.textFrames.add();
  titleFrame.geometricBounds = titleBounds;
  titleFrame.contents = sectionTitle(sections[p].title);
  titleFrame.parentStory.paragraphs.everyItem().appliedParagraphStyle = titleStyle;

  var bodyFrame = page.textFrames.add();
  bodyFrame.geometricBounds = bodyBounds;
  bodyFrame.textFramePreferences.textColumnCount = 2;
  bodyFrame.textFramePreferences.textColumnGutter = 15;
  bodyFrame.contents = sections[p].body.join('\r');
  bodyFrame.parentStory.paragraphs.everyItem().appliedParagraphStyle = bodyStyle;
}

doc.save(outputPath);
try {
  if (pdfPath.exists) {
    pdfPath.remove();
  }
  app.pdfExportPreferences.pageRange = PageRange.ALL_PAGES;
  doc.exportFile(ExportFormat.PDF_TYPE, pdfPath, false);
} catch (e) {
  // The INDD is the primary output; PDF export is a convenience check.
}

var report = [];
report.push('output=' + outputPath.fsName);
report.push('pdf=' + pdfPath.fsName);
report.push('pages=' + doc.pages.length);
for (var k = 0; k < sections.length; k++) {
  report.push(sections[k].title + ': ' + sections[k].body.length + ' entradas');
}
doc.close(SaveOptions.YES);
report.join('\n');
