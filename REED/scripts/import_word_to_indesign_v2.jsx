/* Import a Word file into an existing InDesign document and apply template styles. */
(function () {
  var inddPath = "/Users/jose/Desktop/Pruebas/Maqueta REED.indd";
  var wordPath = "/Users/jose/Desktop/Pruebas/11191 esp.docx";
  var reportPath = "/Users/jose/Desktop/Pruebas/import_word_to_indesign_report.txt";
  var paragraphStyleName = "Texto base (ESPAÑOL)";
  var tableStyleName = "Tabla REED";

  function writeReport(lines) {
    var report = File(reportPath);
    report.encoding = "UTF-8";
    report.open("w");
    report.write(lines.join("\n"));
    report.close();
  }

  function fail(message) {
    writeReport(["ERROR", message]);
    throw new Error(message);
  }

  function getStyleByName(styles, allStyles, name) {
    var style = styles.itemByName(name);
    if (style.isValid) {
      return style;
    }

    if (allStyles) {
      for (var i = 0; i < allStyles.length; i += 1) {
        if (allStyles[i].name === name) {
          return allStyles[i];
        }
      }
    }

    return null;
  }

  function trySet(object, property, value) {
    try {
      object[property] = value;
    } catch (_) {}
  }

  function areaOf(frame) {
    var b = frame.geometricBounds;
    return Math.abs((b[2] - b[0]) * (b[3] - b[1]));
  }

  function findTargetFrame(doc) {
    var page, frames, i, frame;

    if (doc.pages.length > 0) {
      page = doc.pages[0];
      frames = page.textFrames;
      if (frames.length > 0) {
        var best = frames[0];
        var bestArea = areaOf(best);
        for (i = 1; i < frames.length; i += 1) {
          frame = frames[i];
          if (areaOf(frame) > bestArea) {
            best = frame;
            bestArea = areaOf(frame);
          }
        }
        return best;
      }
    }

    if (doc.textFrames.length > 0) {
      return doc.textFrames[0];
    }

    return null;
  }

  app.scriptPreferences.userInteractionLevel = UserInteractionLevels.NEVER_INTERACT;

  var inddFile = File(inddPath);
  var wordFile = File(wordPath);
  if (!inddFile.exists) fail("No se encuentra el archivo InDesign: " + inddPath);
  if (!wordFile.exists) fail("No se encuentra el archivo Word: " + wordPath);

  var doc = null;
  for (var d = 0; d < app.documents.length; d += 1) {
    try {
      if (app.documents[d].fullName.fsName === inddFile.fsName) {
        doc = app.documents[d];
        break;
      }
    } catch (_) {}
  }
  if (doc === null) {
    doc = app.open(inddFile);
  }

  var paragraphStyle = getStyleByName(doc.paragraphStyles, doc.allParagraphStyles, paragraphStyleName);
  if (paragraphStyle === null) fail("No existe el estilo de parrafo '" + paragraphStyleName + "' en la maqueta.");

  var tableStyle = getStyleByName(doc.tableStyles, doc.allTableStyles, tableStyleName);
  if (tableStyle === null) fail("No existe el estilo de tabla '" + tableStyleName + "' en la maqueta.");

  trySet(app.wordRTFImportPreferences, "importEndnotes", true);
  trySet(app.wordRTFImportPreferences, "importFootnotes", true);
  trySet(app.wordRTFImportPreferences, "importIndex", true);
  trySet(app.wordRTFImportPreferences, "importTOC", true);
  trySet(app.wordRTFImportPreferences, "preserveGraphics", true);
  trySet(app.wordRTFImportPreferences, "preserveLocalOverrides", true);
  trySet(app.wordRTFImportPreferences, "preserveTrackChanges", false);
  trySet(app.wordRTFImportPreferences, "removeFormatting", false);
  trySet(app.wordRTFImportPreferences, "resolveCharacterStyleClash", ResolveStyleClash.RESOLVE_CLASH_USE_EXISTING);
  trySet(app.wordRTFImportPreferences, "resolveParagraphStyleClash", ResolveStyleClash.RESOLVE_CLASH_USE_EXISTING);
  trySet(app.wordRTFImportPreferences, "useTypographersQuotes", true);
  trySet(doc.textPreferences, "smartTextReflow", true);
  trySet(doc.textPreferences, "addPages", AddPageOptions.END_OF_STORY);

  var targetFrame = findTargetFrame(doc);
  if (targetFrame === null) fail("La maqueta no tiene cajas de texto donde colocar el Word.");

  var story = targetFrame.parentStory;
  story.contents = "";
  targetFrame.insertionPoints[0].place(wordFile);

  story = targetFrame.parentStory;

  var paragraphCount = 0;
  for (var p = 0; p < story.paragraphs.length; p += 1) {
    story.paragraphs[p].applyParagraphStyle(paragraphStyle, false);
    paragraphCount += 1;
  }

  var tableCount = 0;
  for (var t = 0; t < story.tables.length; t += 1) {
    story.tables[t].appliedTableStyle = tableStyle;
    tableCount += 1;
  }

  var overset = story.overflows;
  doc.save();

  writeReport([
    "OK",
    "InDesign: " + inddPath,
    "Word: " + wordPath,
    "Estilo de parrafo aplicado: " + paragraphStyleName,
    "Estilo de tabla aplicado: " + tableStyleName,
    "Parrafos procesados: " + paragraphCount,
    "Tablas procesadas: " + tableCount,
    "Texto desbordado: " + (overset ? "SI" : "NO")
  ]);
}());
