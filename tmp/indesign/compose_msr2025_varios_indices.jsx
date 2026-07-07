var templatePath = File('/Volumes/DATOS/Proyectos Codex/Indices varios/Indices limpio.indd');
var textPath = File('/Volumes/DATOS/Proyectos Codex/Indices varios/MSR2025 Varios_indices_para_InDesign.txt');
var outputPath = File('/Volumes/DATOS/Proyectos Codex/Indices varios/MSR2025 Varios_indices_maquetado.indd');
var pdfPath = File('/Volumes/DATOS/Proyectos Codex/Indices varios/MSR2025 Varios_indices_maquetado.pdf');

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
  return rawTitle.toLowerCase();
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

function preparePage(page, rawTitle) {
  removePageTextFrames(page);
  ensureHeaderBand(page);

  var titleFrame = page.textFrames.add();
  titleFrame.geometricBounds = titleBounds;
  titleFrame.contents = sectionTitle(rawTitle);
  titleFrame.parentStory.paragraphs.everyItem().appliedParagraphStyle = titleStyle;

  var bodyFrame = page.textFrames.add();
  bodyFrame.geometricBounds = bodyBounds;
  bodyFrame.textFramePreferences.textColumnCount = 2;
  bodyFrame.textFramePreferences.textColumnGutter = 15;
  bodyFrame.parentStory.paragraphs.everyItem().appliedParagraphStyle = bodyStyle;
  return bodyFrame;
}

var sectionReports = [];
for (var s = 0; s < sections.length; s++) {
  var page = s === 0 ? doc.pages[0] : doc.pages.add(LocationOptions.AT_END);
  var bodyFrame = preparePage(page, sections[s].title);
  bodyFrame.contents = sections[s].body.join('\r');
  bodyFrame.parentStory.paragraphs.everyItem().appliedParagraphStyle = bodyStyle;

  var pagesForSection = 1;
  var lastFrame = bodyFrame;
  while (lastFrame.overflows) {
    var nextFrame = preparePage(doc.pages.add(LocationOptions.AT_END), sections[s].title);
    lastFrame.nextTextFrame = nextFrame;
    lastFrame = nextFrame;
    lastFrame.parentStory.paragraphs.everyItem().appliedParagraphStyle = bodyStyle;
    pagesForSection++;
    if (pagesForSection > 20) {
      throw new Error('Demasiadas páginas de continuidad para ' + sections[s].title);
    }
  }
  sectionReports.push(sections[s].title + ': ' + sections[s].body.length + ' entradas, ' + pagesForSection + ' páginas');
}

doc.save(outputPath);
try {
  if (pdfPath.exists) {
    pdfPath.remove();
  }
  app.pdfExportPreferences.pageRange = PageRange.ALL_PAGES;
  doc.exportFile(ExportFormat.PDF_TYPE, pdfPath, false);
} catch (e) {
}

var report = [];
report.push('output=' + outputPath.fsName);
report.push('pdf=' + pdfPath.fsName);
report.push('pages=' + doc.pages.length);
for (var r = 0; r < sectionReports.length; r++) {
  report.push(sectionReports[r]);
}
doc.close(SaveOptions.YES);
report.join('\n');
