//@target illustrator
// Separa los TextFrame seleccionados en TextFrames independientes por palabra.
// Version mejorada a partir del script original de a.gontis.

var TRACKING_COLUMN_THRESHOLD = 400;

(function () {
  var REMOVE_ORIGINAL = true;
  var CREATE_LAYER_PER_WORD = false;

  if (app.documents.length === 0) {
    alert("Abre un documento y selecciona uno o varios textos.");
    return;
  }

  var doc = app.activeDocument;
  var textFrames = [];
  collectTextFrames(app.selection, textFrames);

  if (textFrames.length === 0) {
    alert("Selecciona al menos un marco de texto.");
    return;
  }

  var outputLayer = null;

  if (shouldBuildWordsFromFragments(textFrames)) {
    buildWordsFromFragments(doc, textFrames, outputLayer, REMOVE_ORIGINAL, CREATE_LAYER_PER_WORD);
  } else {
    for (var i = 0; i < textFrames.length; i++) {
      if (isDenseTableRow(textFrames[i])) {
        splitDenseTableRow(doc, textFrames[i], outputLayer, REMOVE_ORIGINAL, CREATE_LAYER_PER_WORD);
      } else {
        splitTextFrame(doc, textFrames[i], outputLayer, REMOVE_ORIGINAL, CREATE_LAYER_PER_WORD);
      }
    }
  }
})();

function collectTextFrames(items, result) {
  if (!items) {
    return;
  }

  for (var i = 0; i < items.length; i++) {
    var item = items[i];

    if (!item) {
      continue;
    }

    if (item.typename === "TextFrame") {
      result.push(item);
    } else if (item.typename === "GroupItem") {
      collectTextFrames(item.pageItems, result);
    }
  }
}

function splitTextFrame(doc, sourceFrame, outputLayer, removeOriginal, createLayerPerWord) {
  var lines = sourceFrame.lines;
  var lineCount = lines.length;

  if (lineCount === 0) {
    return;
  }

  var spaceWidth = measureTextWidth(doc, sourceFrame, " ");
  var fallbackLineHeight = sourceFrame.height / lineCount;
  var yOffset = 0;

  for (var lineIndex = 0; lineIndex < lineCount; lineIndex++) {
    var line = lines[lineIndex];
    var words = line.words;
    var xOffset = 0;

    for (var wordIndex = 0; wordIndex < words.length; wordIndex++) {
      var word = words[wordIndex];
      var wordText = word.contents;

      if (!wordText || !hasVisibleText(wordText)) {
        continue;
      }

      var wordFrame = duplicateWordAsFrame(doc, sourceFrame, word);
      wordFrame.position = [sourceFrame.position[0] + xOffset, sourceFrame.position[1] - yOffset];

      if (createLayerPerWord) {
        moveToNewLayer(doc, wordFrame, cleanLayerName(wordText));
      } else {
        moveToSourceLayer(wordFrame, sourceFrame);
      }

      xOffset += wordFrame.width + spaceWidth;
    }

    yOffset += getLineHeight(line, fallbackLineHeight);
  }

  if (removeOriginal) {
    sourceFrame.remove();
  }
}

function shouldBuildWordsFromFragments(textFrames) {
  if (textFrames.length < 3) {
    return false;
  }

  var visibleCount = 0;
  var shortCount = 0;

  for (var i = 0; i < textFrames.length; i++) {
    var contents = textFrames[i].contents;
    if (!contents || !hasVisibleText(contents)) {
      continue;
    }

    visibleCount++;
    if (contents.length <= 2 && textFrames[i].words.length <= 1) {
      shortCount++;
    }
  }

  return visibleCount > 0 && shortCount / visibleCount > 0.75;
}

function buildWordsFromFragments(doc, textFrames, outputLayer, removeOriginal, createLayerPerWord) {
  var lines = groupFramesByLine(textFrames);

  for (var lineIndex = 0; lineIndex < lines.length; lineIndex++) {
    var lineFrames = lines[lineIndex].frames;
    lineFrames.sort(sortLeftToRight);
    buildLineWords(doc, lineFrames, outputLayer, createLayerPerWord);
  }

  if (removeOriginal) {
    for (var i = 0; i < textFrames.length; i++) {
      textFrames[i].remove();
    }
  }
}

function buildLineWords(doc, lineFrames, outputLayer, createLayerPerWord) {
  var currentText = "";
  var currentFrames = [];
  var firstFrame = null;
  var lastFrame = null;
  var gapThreshold = getGapThreshold(lineFrames);

  for (var i = 0; i < lineFrames.length; i++) {
    var frame = lineFrames[i];
    var contents = frame.contents;

    if (!contents || !hasVisibleText(contents)) {
      flushBuiltWord(doc, currentText, currentFrames, firstFrame, outputLayer, createLayerPerWord);
      currentText = "";
      currentFrames = [];
      firstFrame = null;
      lastFrame = null;
      continue;
    }

    if (lastFrame && frame.left - (lastFrame.left + lastFrame.width) > gapThreshold) {
      flushBuiltWord(doc, currentText, currentFrames, firstFrame, outputLayer, createLayerPerWord);
      currentText = "";
      currentFrames = [];
      firstFrame = null;
    }

    if (!firstFrame) {
      firstFrame = frame;
    }

    currentText += contents;
    currentFrames.push(frame);
    lastFrame = frame;
  }

  flushBuiltWord(doc, currentText, currentFrames, firstFrame, outputLayer, createLayerPerWord);
}

function flushBuiltWord(doc, contents, sourceFrames, sourceFrame, outputLayer, createLayerPerWord) {
  if (!contents || !sourceFrame) {
    return;
  }

  var wordFrame = doc.textFrames.add();
  wordFrame.contents = "";
  appendSourceFrames(wordFrame, sourceFrames);

  if (!wordFrame.contents) {
    wordFrame.contents = contents;
    copyBasicCharacterAttributes(sourceFrame.textRange, wordFrame.textRange);
  }

  wordFrame.position = [sourceFrame.left, sourceFrame.top];

  if (createLayerPerWord) {
    moveToNewLayer(doc, wordFrame, cleanLayerName(contents));
  } else {
    moveToSourceLayer(wordFrame, sourceFrame);
  }
}

function isDenseTableRow(sourceFrame) {
  var parts = parseTrackingColumns(sourceFrame);
  return parts && parts.length >= 3;
}

function splitDenseTableRow(doc, sourceFrame, outputLayer, removeOriginal, createLayerPerWord) {
  var parts = parseTrackingColumns(sourceFrame);

  if (!parts) {
    splitTextFrame(doc, sourceFrame, outputLayer, removeOriginal, createLayerPerWord);
    return;
  }

  for (var i = 0; i < parts.length; i++) {
    var item = parts[i];
    var frame = doc.textFrames.add();
    frame.contents = item.contents;
    copyBasicCharacterAttributes(sourceFrame.textRange, frame.textRange);
    frame.position = [item.x, sourceFrame.top];

    if (createLayerPerWord) {
      moveToNewLayer(doc, frame, cleanLayerName(item.contents));
    } else {
      moveToSourceLayer(frame, sourceFrame);
    }
  }

  if (removeOriginal) {
    sourceFrame.remove();
  }
}

function parseTrackingColumns(sourceFrame) {
  var contents = sourceFrame.contents;
  if (!contents || sourceFrame.characters.length < 2) {
    return null;
  }

  var breakIndexes = [];
  for (var i = 0; i < sourceFrame.characters.length; i++) {
    if (getCharacterTracking(sourceFrame, i) >= TRACKING_COLUMN_THRESHOLD) {
      breakIndexes.push(i + 1);
    }
  }

  if (breakIndexes.length < 2) {
    return null;
  }

  var parts = [];
  var startIndex = 0;
  var currentX = sourceFrame.left;
  for (var breakIndex = 0; breakIndex < breakIndexes.length; breakIndex++) {
    currentX = addTrackingColumnPart(sourceFrame, contents, parts, startIndex, breakIndexes[breakIndex], currentX, true);
    startIndex = breakIndexes[breakIndex];
  }
  addTrackingColumnPart(sourceFrame, contents, parts, startIndex, contents.length, currentX, false);

  return parts.length >= 3 ? parts : null;
}

function addTrackingColumnPart(sourceFrame, contents, parts, startIndex, endIndex, currentX, hasTrailingColumnGap) {
  var rawText = contents.substring(startIndex, endIndex);
  var cleanText = rawText.replace(/^\s+|\s+$/g, "");

  if (cleanText.length === 0) {
    return currentX;
  }

  var leadingWhitespace = rawText.length - rawText.replace(/^\s+/, "").length;
  var adjustedStartIndex = startIndex + leadingWhitespace;
  var cleanX = currentX + measureSourceSegmentWidth(sourceFrame, rawText.substring(0, leadingWhitespace));

  parts.push({
    contents: cleanText,
    startIndex: adjustedStartIndex,
    endIndex: endIndex - getTrailingWhitespaceLength(rawText),
    x: cleanX
  });

  currentX += measureSourceSegmentWidth(sourceFrame, rawText);

  if (hasTrailingColumnGap) {
    currentX += getTrackingGap(sourceFrame, endIndex - 1);
  }

  return currentX;
}

function appendSourceFrames(targetFrame, sourceFrames) {
  if (!sourceFrames) {
    return;
  }

  for (var i = 0; i < sourceFrames.length; i++) {
    try {
      sourceFrames[i].textRange.duplicate(targetFrame);
    } catch (err) {
      targetFrame.contents = targetFrame.contents + sourceFrames[i].contents;
    }
  }
}

function getTrailingWhitespaceLength(value) {
  return value.length - value.replace(/\s+$/, "").length;
}

function getCharacterTracking(sourceFrame, characterIndex) {
  try {
    return sourceFrame.characters[characterIndex].characterAttributes.tracking;
  } catch (err) {
    return 0;
  }
}

function getTrackingGap(sourceFrame, characterIndex) {
  var tracking = getCharacterTracking(sourceFrame, characterIndex);
  var size = 0;

  try {
    size = sourceFrame.characters[characterIndex].characterAttributes.size;
  } catch (err) {}

  if (!size || size <= 0) {
    try {
      size = sourceFrame.textRange.characterAttributes.size;
    } catch (err2) {}
  }

  if (!size || size <= 0) {
    return 0;
  }

  return tracking * size / 1000;
}

function measureSourceSegmentWidth(sourceFrame, segmentText) {
  if (!segmentText || segmentText.length === 0) {
    return 0;
  }

  var tempFrame = sourceFrame.duplicate();
  tempFrame.contents = segmentText;
  var width = tempFrame.width;
  tempFrame.remove();

  return width;
}

function duplicateWordAsFrame(doc, sourceFrame, wordRange) {
  var wordFrame = doc.textFrames.add();
  wordFrame.contents = "";

  try {
    wordRange.duplicate(wordFrame);
  } catch (err) {
    wordFrame.contents = wordRange.contents;
    copyBasicCharacterAttributes(wordRange, wordFrame.textRange);
  }

  if (!wordFrame.contents) {
    wordFrame.contents = wordRange.contents;
  }

  return wordFrame;
}

function copyBasicCharacterAttributes(sourceRange, targetRange) {
  try {
    var source = sourceRange.characterAttributes;
    var target = targetRange.characterAttributes;
    target.textFont = source.textFont;
    target.size = source.size;
    target.fillColor = source.fillColor;
    target.strokeColor = source.strokeColor;
    target.tracking = source.tracking;
  } catch (err) {
    // Si Illustrator no permite copiar algun atributo, conserva el texto igualmente.
  }
}

function getLineHeight(line, fallbackLineHeight) {
  try {
    var leading = line.characterAttributes.leading;
    if (leading && leading > 0) {
      return leading;
    }
  } catch (err) {}

  return fallbackLineHeight;
}

function measureTextWidth(doc, sourceFrame, contents) {
  var tempFrame = doc.textFrames.add();
  tempFrame.contents = contents;
  copyBasicCharacterAttributes(sourceFrame.textRange, tempFrame.textRange);
  var width = tempFrame.width;
  tempFrame.remove();

  if (!width || width < 0.1) {
    width = sourceFrame.textRange.characterAttributes.size * 0.33;
  }

  return width;
}

function getOrCreateLayer(doc, name) {
  for (var i = 0; i < doc.layers.length; i++) {
    if (doc.layers[i].name === name) {
      return doc.layers[i];
    }
  }

  var layer = doc.layers.add();
  layer.name = name;
  return layer;
}

function moveToSourceLayer(item, sourceFrame) {
  try {
    item.move(sourceFrame.layer, ElementPlacement.PLACEATEND);
  } catch (err) {
    // Si Illustrator no permite moverlo, se queda en la capa activa sin crear capas nuevas.
  }
}

function groupFramesByLine(frames) {
  var sortedFrames = frames.slice(0);
  sortedFrames.sort(sortTopToBottom);

  var tolerance = getAverageHeight(sortedFrames) * 0.45;
  if (tolerance < 2) {
    tolerance = 2;
  }

  var lines = [];
  for (var i = 0; i < sortedFrames.length; i++) {
    var frame = sortedFrames[i];
    var line = findMatchingLine(lines, frame, tolerance);

    if (!line) {
      line = {
        top: frame.top,
        frames: []
      };
      lines.push(line);
    }

    line.frames.push(frame);
    line.top = getAverageTop(line.frames);
  }

  lines.sort(function (a, b) {
    return b.top - a.top;
  });

  return lines;
}

function findMatchingLine(lines, frame, tolerance) {
  for (var i = 0; i < lines.length; i++) {
    if (Math.abs(lines[i].top - frame.top) <= tolerance) {
      return lines[i];
    }
  }

  return null;
}

function sortTopToBottom(a, b) {
  if (Math.abs(a.top - b.top) < 0.01) {
    return a.left - b.left;
  }

  return b.top - a.top;
}

function sortLeftToRight(a, b) {
  return a.left - b.left;
}

function getAverageTop(frames) {
  var total = 0;

  for (var i = 0; i < frames.length; i++) {
    total += frames[i].top;
  }

  return total / frames.length;
}

function getAverageHeight(frames) {
  var total = 0;

  for (var i = 0; i < frames.length; i++) {
    total += Math.abs(frames[i].height);
  }

  return total / frames.length;
}

function getGapThreshold(frames) {
  var total = 0;
  var count = 0;

  for (var i = 0; i < frames.length; i++) {
    if (frames[i].contents && hasVisibleText(frames[i].contents)) {
      total += Math.abs(frames[i].width);
      count++;
    }
  }

  if (count === 0) {
    return 2;
  }

  var averageWidth = total / count;
  return Math.max(averageWidth * 0.65, 1.5);
}

function moveToNewLayer(doc, item, name) {
  var layer = doc.layers.add(ElementPlacement.PLACEATEND);
  layer.name = name;
  item.move(layer, ElementPlacement.PLACEATEND);
}

function cleanLayerName(name) {
  var cleanName = name.replace(/^\s+|\s+$/g, "");
  if (cleanName.length === 0) {
    cleanName = "Palabra";
  }
  return cleanName.substring(0, 80);
}

function hasVisibleText(value) {
  return value.replace(/\s/g, "").length > 0;
}
