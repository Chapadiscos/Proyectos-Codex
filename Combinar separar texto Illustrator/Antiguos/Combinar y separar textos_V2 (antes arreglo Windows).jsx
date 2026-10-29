#target illustrator
#targetengine "combinar_separar_textos"

/*
  Ventana flotante standalone para combinar o separar textos seleccionados.
  Todo el codigo necesario vive en este archivo; no depende de otros scripts.
*/

(function () {
  var WINDOW_ID = "combinarSepararTextosWindow";

  if ($.global[WINDOW_ID] && $.global[WINDOW_ID] instanceof Window) {
    try {
      $.global[WINDOW_ID].close();
    } catch (err) {
      // Si Illustrator ya destruyo la ventana, seguimos y creamos una nueva.
    }

    $.global[WINDOW_ID] = null;
  }

  var win = new Window("palette", "Combinar / separar textos");
  $.global[WINDOW_ID] = win;

  win.orientation = "column";
  win.alignChildren = ["fill", "top"];
  win.margins = 16;
  win.spacing = 10;

  var combineButton = win.add("button", undefined, "Combinar textos");
  var splitButton = win.add("button", undefined, "Separar textos");
  var closeButton = win.add("button", undefined, "Cerrar");

  combineButton.preferredSize.width = 190;
  splitButton.preferredSize.width = 190;
  closeButton.preferredSize.width = 190;

  combineButton.onClick = function () {
    runAction(runCombineTexts, "combinar");
  };

  splitButton.onClick = function () {
    runAction(runSplitTexts, "separar");
  };

  closeButton.onClick = function () {
    win.close();
  };

  win.onClose = function () {
    $.global[WINDOW_ID] = null;
  };

  win.center();
  win.show();

  function runAction(actionFunction, actionName) {
    if (app.documents.length === 0) {
      alert("Abre un documento antes de ejecutar esta accion.");
      return;
    }

    var tempFile = File(Folder.temp.fsName + "/combinar_separar_textos_" + actionName + "_" + new Date().getTime() + ".jsx");
    var source = "(" + actionFunction.toString() + ")();";

    if (!tempFile.open("w")) {
      alert("No se pudo crear el script temporal.");
      return;
    }

    tempFile.write(source);
    tempFile.close();

    var message = new BridgeTalk();
    message.target = "illustrator";
    message.body = "var f = File(" + quoteForJavaScript(tempFile.fsName) + "); try { $.evalFile(f); } finally { try { f.remove(); } catch (err) {} }";
    message.onError = function (response) {
      alert("No se pudo ejecutar la accion:\r" + response.body);
    };
    message.send();
  }

  function quoteForJavaScript(value) {
    return "\"" + String(value).replace(/\\/g, "\\\\").replace(/"/g, "\\\"") + "\"";
  }

  function runCombineTexts() {
  // Combina TextFrames seleccionados en un unico TextFrame siguiendo el orden visual.
  // Version mejorada a partir del script original "Combiner" de vd.
  
  (function () {
    var REMOVE_ORIGINALS = true;
    var ALIGN_FIRST_CHARACTER = true;
    var MATCH_LAST_LINE_BASELINE = true;
    var DETECT_PARAGRAPH_ALIGNMENT = true;
    var LINE_TOLERANCE_FACTOR = 0.45;
    var MIN_LINE_TOLERANCE = 2;
  
    if (app.documents.length === 0) {
      alert("Abre un documento y selecciona los textos que quieres combinar.");
      return;
    }
  
    var doc = app.activeDocument;
    var frames = [];
    collectTextFrames(app.selection, frames);
  
    if (frames.length === 0) {
      alert("Selecciona al menos un marco de texto.");
      return;
    }
  
    if (isRotated90Selection(frames)) {
      var rotatedTolerance = getAverageRotatedLineThickness(frames) * LINE_TOLERANCE_FACTOR;
      if (rotatedTolerance < MIN_LINE_TOLERANCE) {
        rotatedTolerance = MIN_LINE_TOLERANCE;
      }
  
      combineRotated90Frames(doc, frames, rotatedTolerance, REMOVE_ORIGINALS, ALIGN_FIRST_CHARACTER, MATCH_LAST_LINE_BASELINE);
      return;
    }
  
    frames.sort(sortTopToBottom);
  
    var lineTolerance = getAverageHeight(frames) * LINE_TOLERANCE_FACTOR;
    if (lineTolerance < MIN_LINE_TOLERANCE) {
      lineTolerance = MIN_LINE_TOLERANCE;
    }
  
    var lines = groupFramesByLine(frames, lineTolerance);
    lines[0].frames.sort(sortLeftToRight);
    lines[lines.length - 1].frames.sort(sortLeftToRight);
    var firstFrame = lines[0].frames[0];
    var lastFrame = lines[lines.length - 1].frames[0];
    var paragraphAlignment = DETECT_PARAGRAPH_ALIGNMENT ? getParagraphAlignment(lines) : "left";
    var alignmentReference = getAlignmentReference(lines, paragraphAlignment);
    var targetLeading = getTargetLeading(lines, firstFrame, lastFrame);
    var newFrame = doc.textFrames.add();
    newFrame.position = [firstFrame.position[0], firstFrame.position[1]];
    newFrame.contents = "";
  
    for (var lineIndex = 0; lineIndex < lines.length; lineIndex++) {
      var lineFrames = lines[lineIndex].frames;
      lineFrames.sort(sortLeftToRight);
  
      if (lineIndex > 0) {
        appendSeparator(doc, newFrame, "\r", lineFrames[0]);
      }
  
      if (isCharacterLine(lineFrames)) {
        appendCharacterLine(newFrame, lineFrames);
      } else {
        appendWordLine(doc, newFrame, lineFrames);
      }
    }
  
    cleanCombinedText(newFrame);
  
    if (MATCH_LAST_LINE_BASELINE && targetLeading > 0) {
      applyLeading(newFrame, targetLeading);
    }
  
    applyParagraphJustification(newFrame, paragraphAlignment);
  
    if (ALIGN_FIRST_CHARACTER) {
      alignToReference(newFrame, alignmentReference, paragraphAlignment);
    }
  
    if (REMOVE_ORIGINALS) {
      for (var i = 0; i < frames.length; i++) {
        frames[i].remove();
      }
    }
  
    newFrame.selected = true;
  })();
  
  function combineRotated90Frames(doc, frames, tolerance, removeOriginals, alignFirstCharacter, matchLastLineBaseline) {
    frames.sort(sortRotatedTextOrder);
  
    var lines = groupFramesByRotatedLine(frames, tolerance);
    sortRotatedLines(lines, frames[0]);
  
    for (var i = 0; i < lines.length; i++) {
      sortRotatedLineFrames(lines[i].frames);
    }
  
    var firstFrame = lines[0].frames[0];
    var targetLeading = getRotatedTargetLeading(lines);
    var alignmentReference = getRotatedAlignmentReference(lines);
    var newFrame = firstFrame.duplicate();
    newFrame.contents = "";
  
    for (var lineIndex = 0; lineIndex < lines.length; lineIndex++) {
      var lineFrames = lines[lineIndex].frames;
  
      if (lineIndex > 0) {
        appendSeparator(doc, newFrame, "\r", lineFrames[0]);
      }
  
      if (isCharacterLine(lineFrames)) {
        appendCharacterLine(newFrame, lineFrames);
      } else {
        appendWordLine(doc, newFrame, lineFrames);
      }
    }
  
    cleanCombinedText(newFrame);
  
    if (matchLastLineBaseline && targetLeading > 0) {
      applyLeading(newFrame, targetLeading);
    }
  
    applyParagraphJustification(newFrame, "right");
  
    if (alignFirstCharacter) {
      alignRotatedToReference(newFrame, alignmentReference);
    }
  
    if (removeOriginals) {
      for (var i = 0; i < frames.length; i++) {
        frames[i].remove();
      }
    }
  
    newFrame.selected = true;
  }
  
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
  
  function isRotated90Selection(frames) {
    if (frames.length < 2) {
      return false;
    }
  
    var rotatedCount = 0;
  
    for (var i = 0; i < frames.length; i++) {
      if (isRotated90Frame(frames[i])) {
        rotatedCount++;
      }
    }
  
    return rotatedCount / frames.length >= 0.75;
  }
  
  function isRotated90Frame(frame) {
    var matrix = getMatrix(frame);
    if (!matrix) {
      return false;
    }
  
    var angle = Math.atan2(matrix.mValueB, matrix.mValueA) * 180 / Math.PI;
    angle = normalizeAngle(angle);
  
    return Math.abs(Math.abs(angle) - 90) <= 8;
  }
  
  function normalizeAngle(angle) {
    while (angle > 180) {
      angle -= 360;
    }
  
    while (angle < -180) {
      angle += 360;
    }
  
    return angle;
  }
  
  function getMatrix(frame) {
    try {
      return frame.matrix;
    } catch (err) {
      return null;
    }
  }
  
  function groupFramesByRotatedLine(frames, tolerance) {
    var lines = [];
  
    for (var i = 0; i < frames.length; i++) {
      var frame = frames[i];
      var line = getMatchingRotatedLine(lines, frame, tolerance);
  
      if (!line) {
        line = {
          centerX: getRotatedLineX(frame),
          frames: []
        };
        lines.push(line);
      }
  
      line.frames.push(frame);
      line.centerX = getAverageRotatedLineX(line.frames);
    }
  
    return lines;
  }
  
  function getMatchingRotatedLine(lines, frame, tolerance) {
    var centerX = getRotatedLineX(frame);
  
    for (var i = 0; i < lines.length; i++) {
      if (Math.abs(lines[i].centerX - centerX) <= tolerance) {
        return lines[i];
      }
    }
  
    return null;
  }
  
  function sortRotatedLines(lines, sampleFrame) {
    var direction = getLineBreakXDirection(sampleFrame);
  
    lines.sort(function (a, b) {
      if (direction >= 0) {
        return a.centerX - b.centerX;
      }
  
      return b.centerX - a.centerX;
    });
  }
  
  function sortRotatedLineFrames(lineFrames) {
    lineFrames.sort(function (a, b) {
      var aCenterY = getCenterY(a);
      var bCenterY = getCenterY(b);
  
      if (Math.abs(aCenterY - bCenterY) < 0.01) {
        return a.left - b.left;
      }
  
      return bCenterY - aCenterY;
    });
  }
  
  function sortRotatedTextOrder(a, b) {
    var centerDiff = getRotatedLineX(a) - getRotatedLineX(b);
    if (Math.abs(centerDiff) > 0.01) {
      return centerDiff;
    }
  
    return getCenterY(b) - getCenterY(a);
  }
  
  function getLineBreakXDirection(frame) {
    var matrix = getMatrix(frame);
    if (!matrix) {
      return 1;
    }
  
    return -matrix.mValueC;
  }
  
  function getAverageRotatedLineThickness(frames) {
    var total = 0;
  
    for (var i = 0; i < frames.length; i++) {
      var bounds = getBounds(frames[i]);
      total += Math.abs(bounds[2] - bounds[0]);
    }
  
    return total / frames.length;
  }
  
  function getAverageRotatedLineX(frames) {
    var total = 0;
  
    for (var i = 0; i < frames.length; i++) {
      total += getRotatedLineX(frames[i]);
    }
  
    return total / frames.length;
  }
  
  function getRotatedLineX(frame) {
    return getCenterX(frame);
  }
  
  function getCenterX(frame) {
    var bounds = getBounds(frame);
    return bounds[0] + (bounds[2] - bounds[0]) / 2;
  }
  
  function getCenterY(frame) {
    var bounds = getBounds(frame);
    return bounds[3] + (bounds[1] - bounds[3]) / 2;
  }
  
  function getRotatedTargetLeading(lines) {
    if (lines.length < 2) {
      return 0;
    }
  
    var firstX = lines[0].centerX;
    var lastX = lines[lines.length - 1].centerX;
    var distance = Math.abs(firstX - lastX);
  
    if (distance <= 0) {
      return 0;
    }
  
    return distance / (lines.length - 1);
  }
  
  function getRotatedAlignmentReference(lines) {
    var bounds = getRotatedLinesBounds(lines);
  
    return {
      right: bounds.right,
      top: bounds.top
    };
  }
  
  function getRotatedLinesBounds(lines) {
    var left = null;
    var top = null;
    var right = null;
    var bottom = null;
  
    for (var i = 0; i < lines.length; i++) {
      var lineBounds = getLineBounds(lines[i].frames);
  
      if (left === null || lineBounds.left < left) {
        left = lineBounds.left;
      }
  
      if (top === null || lineBounds.top > top) {
        top = lineBounds.top;
      }
  
      if (right === null || lineBounds.right > right) {
        right = lineBounds.right;
      }
  
      if (bottom === null || lineBounds.bottom < bottom) {
        bottom = lineBounds.bottom;
      }
    }
  
    return {
      left: left,
      top: top,
      right: right,
      bottom: bottom
    };
  }
  
  function alignRotatedToReference(item, reference) {
    var bounds = getBounds(item);
    item.translate(reference.right - bounds[2], reference.top - bounds[1]);
  }
  
  function groupFramesByLine(frames, tolerance) {
    var lines = [];
  
    for (var i = 0; i < frames.length; i++) {
      var frame = frames[i];
      var line = getMatchingLine(lines, frame, tolerance);
  
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
  
  function getMatchingLine(lines, frame, tolerance) {
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
  
  function getParagraphAlignment(lines) {
    if (lines.length < 2) {
      return "left";
    }
  
    var metrics = [];
    for (var i = 0; i < lines.length; i++) {
      metrics.push(getLineBounds(lines[i].frames));
    }
  
    var leftSpread = getValueSpread(metrics, "left");
    var centerSpread = getValueSpread(metrics, "center");
    var rightSpread = getValueSpread(metrics, "right");
  
    if (centerSpread < leftSpread * 0.5 && centerSpread < rightSpread * 0.5) {
      return "center";
    }
  
    if (rightSpread < leftSpread * 0.5 && rightSpread < centerSpread * 0.5) {
      return "right";
    }
  
    return "left";
  }
  
  function getAlignmentReference(lines, alignment) {
    var topLineBounds = getLineBounds(lines[0].frames);
  
    if (alignment === "center") {
      return {
        x: getAverageLineValue(lines, "center"),
        y: topLineBounds.top
      };
    }
  
    if (alignment === "right") {
      return {
        x: getAverageLineValue(lines, "right"),
        y: topLineBounds.top
      };
    }
  
    return {
      x: topLineBounds.left,
      y: topLineBounds.top
    };
  }
  
  function getLineBounds(frames) {
    var left = null;
    var top = null;
    var right = null;
    var bottom = null;
    var foundVisibleFrame = false;
  
    for (var i = 0; i < frames.length; i++) {
      if (!hasVisibleText(frames[i].contents)) {
        continue;
      }
  
      foundVisibleFrame = true;
      var bounds = getBounds(frames[i]);
  
      if (left === null || bounds[0] < left) {
        left = bounds[0];
      }
  
      if (top === null || bounds[1] > top) {
        top = bounds[1];
      }
  
      if (right === null || bounds[2] > right) {
        right = bounds[2];
      }
  
      if (bottom === null || bounds[3] < bottom) {
        bottom = bounds[3];
      }
    }
  
    if (!foundVisibleFrame) {
      return getLineBoundsIncludingWhitespace(frames);
    }
  
    return {
      left: left,
      top: top,
      right: right,
      bottom: bottom,
      center: left + (right - left) / 2
    };
  }
  
  function getLineBoundsIncludingWhitespace(frames) {
    var left = null;
    var top = null;
    var right = null;
    var bottom = null;
  
    for (var i = 0; i < frames.length; i++) {
      var bounds = getBounds(frames[i]);
  
      if (left === null || bounds[0] < left) {
        left = bounds[0];
      }
  
      if (top === null || bounds[1] > top) {
        top = bounds[1];
      }
  
      if (right === null || bounds[2] > right) {
        right = bounds[2];
      }
  
      if (bottom === null || bounds[3] < bottom) {
        bottom = bounds[3];
      }
    }
  
    return {
      left: left,
      top: top,
      right: right,
      bottom: bottom,
      center: left + (right - left) / 2
    };
  }
  
  function getBounds(item) {
    try {
      return item.geometricBounds;
    } catch (err) {
      return [item.left, item.top, item.left + item.width, item.top - item.height];
    }
  }
  
  function getValueSpread(metrics, key) {
    var min = metrics[0][key];
    var max = metrics[0][key];
  
    for (var i = 1; i < metrics.length; i++) {
      if (metrics[i][key] < min) {
        min = metrics[i][key];
      }
  
      if (metrics[i][key] > max) {
        max = metrics[i][key];
      }
    }
  
    return Math.abs(max - min);
  }
  
  function getAverageLineValue(lines, key) {
    var total = 0;
  
    for (var i = 0; i < lines.length; i++) {
      total += getLineBounds(lines[i].frames)[key];
    }
  
    return total / lines.length;
  }
  
  function getTargetLeading(lines, firstFrame, lastFrame) {
    if (lines.length < 2) {
      return 0;
    }
  
    var firstY = getLineY(firstFrame);
    var lastY = getLineY(lastFrame);
    var distance = Math.abs(firstY - lastY);
  
    if (distance <= 0) {
      return 0;
    }
  
    return distance / (lines.length - 1);
  }
  
  function getLineY(frame) {
    try {
      return frame.position[1];
    } catch (err) {
      return frame.top;
    }
  }
  
  function applyLeading(textFrame, leading) {
    try {
      textFrame.textRange.characterAttributes.autoLeading = false;
    } catch (err) {}
  
    try {
      textFrame.textRange.characterAttributes.leading = leading;
    } catch (err) {}
  
    try {
      for (var i = 0; i < textFrame.textRanges.length; i++) {
        textFrame.textRanges[i].characterAttributes.autoLeading = false;
        textFrame.textRanges[i].characterAttributes.leading = leading;
      }
    } catch (err) {}
  
    try {
      for (var j = 0; j < textFrame.characters.length; j++) {
        textFrame.characters[j].characterAttributes.autoLeading = false;
        textFrame.characters[j].characterAttributes.leading = leading;
      }
    } catch (err) {}
  }
  
  function applyParagraphJustification(textFrame, alignment) {
    var justification = Justification.LEFT;
  
    if (alignment === "center") {
      justification = Justification.CENTER;
    } else if (alignment === "right") {
      justification = Justification.RIGHT;
    }
  
    try {
      textFrame.textRange.paragraphAttributes.justification = justification;
    } catch (err) {}
  
    try {
      for (var i = 0; i < textFrame.paragraphs.length; i++) {
        textFrame.paragraphs[i].paragraphAttributes.justification = justification;
      }
    } catch (err2) {}
  }
  
  function alignToReference(item, reference, alignment) {
    var bounds = getBounds(item);
    var itemX = bounds[0];
  
    if (alignment === "center") {
      itemX = bounds[0] + (bounds[2] - bounds[0]) / 2;
    } else if (alignment === "right") {
      itemX = bounds[2];
    }
  
    item.translate(reference.x - itemX, reference.y - bounds[1]);
  }
  
  function isCharacterLine(lineFrames) {
    var visibleCount = 0;
    var shortCount = 0;
  
    for (var i = 0; i < lineFrames.length; i++) {
      var contents = lineFrames[i].contents;
      if (!hasVisibleText(contents)) {
        continue;
      }
  
      visibleCount++;
      if (contents.length <= 2 && lineFrames[i].words.length <= 1) {
        shortCount++;
      }
    }
  
    return visibleCount >= 3 && shortCount / visibleCount > 0.75;
  }
  
  function appendCharacterLine(targetFrame, lineFrames) {
    for (var i = 0; i < lineFrames.length; i++) {
      lineFrames[i].textRange.duplicate(targetFrame);
    }
  }
  
  function appendWordLine(doc, targetFrame, lineFrames) {
    var appendedInLine = 0;
    var lastAppendedFrame = null;
  
    for (var i = 0; i < lineFrames.length; i++) {
      if (!hasVisibleText(lineFrames[i].contents)) {
        continue;
      }
  
      if (appendedInLine > 0 && shouldInsertWordSeparator(doc, lastAppendedFrame, lineFrames[i])) {
        appendSeparator(doc, targetFrame, " ", lastAppendedFrame);
      }
  
      lineFrames[i].textRange.duplicate(targetFrame);
      appendedInLine++;
      lastAppendedFrame = lineFrames[i];
    }
  }

  function shouldInsertWordSeparator(doc, previousFrame, currentFrame) {
    var gap = getFrameGap(previousFrame, currentFrame);

    if (gap <= 0) {
      return false;
    }

    var previousIsNumeric = isNumericLikeText(previousFrame.contents);
    var currentIsNumeric = isNumericLikeText(currentFrame.contents);
    var fontSize = getFrameFontSize(previousFrame);
    var thresholdFactor = previousIsNumeric && currentIsNumeric ? 0.22 : 0.35;
    var minimumThreshold = previousIsNumeric && currentIsNumeric ? 1.5 : 0.5;
    var threshold = minimumThreshold;

    if (fontSize && fontSize > 0) {
      threshold = Math.max(fontSize * thresholdFactor, minimumThreshold);
    }

    return gap > threshold;
  }

  function getFrameGap(previousFrame, currentFrame) {
    var previousBounds = getBounds(previousFrame);
    var currentBounds = getBounds(currentFrame);
    return currentBounds[0] - previousBounds[2];
  }

  function isNumericLikeText(value) {
    if (!value) {
      return false;
    }

    var cleanValue = value.replace(/\s+/g, "");
    return /[0-9]/.test(cleanValue) && !/[A-Za-z]/.test(cleanValue);
  }

  function getFrameFontSize(frame) {
    try {
      return frame.textRange.characterAttributes.size;
    } catch (err) {}

    try {
      return frame.characters[0].characterAttributes.size;
    } catch (err2) {}

    try {
      var bounds = getBounds(frame);
      return Math.abs(bounds[1] - bounds[3]);
    } catch (err3) {}

    return 0;
  }

  function cleanCombinedText(textFrame) {
    var removeIndexes = getWhitespaceIndexesToRemove(textFrame.contents);
  
    for (var i = removeIndexes.length - 1; i >= 0; i--) {
      removeCharacterAt(textFrame, removeIndexes[i]);
    }
  }
  
  function getWhitespaceIndexesToRemove(contents) {
    var removeIndexes = [];
    var pendingSpaces = [];
    var atLineStart = true;
  
    for (var i = 0; i < contents.length; i++) {
      var character = contents.charAt(i);
  
      if (isLineBreak(character)) {
        addPendingSpaces(removeIndexes, pendingSpaces);
        pendingSpaces = [];
        atLineStart = true;
        continue;
      }
  
      if (isInlineWhitespace(character)) {
        if (atLineStart || pendingSpaces.length > 0) {
          removeIndexes.push(i);
        } else {
          pendingSpaces.push(i);
        }
        continue;
      }
  
      pendingSpaces = [];
      atLineStart = false;
    }
  
    addPendingSpaces(removeIndexes, pendingSpaces);
    return removeIndexes;
  }
  
  function addPendingSpaces(removeIndexes, pendingSpaces) {
    for (var i = 0; i < pendingSpaces.length; i++) {
      removeIndexes.push(pendingSpaces[i]);
    }
  }
  
  function isLineBreak(character) {
    return character === "\r" || character === "\n";
  }
  
  function isInlineWhitespace(character) {
    return /\s/.test(character) && !isLineBreak(character);
  }
  
  function removeCharacterAt(textFrame, index) {
    try {
      textFrame.characters[index].remove();
    } catch (err) {}
  }
  
  function hasVisibleText(contents) {
    return contents && contents.replace(/\s/g, "").length > 0;
  }
  
  function appendSeparator(doc, targetFrame, separator, styleSourceFrame) {
    var tempFrame = styleSourceFrame.duplicate();
    tempFrame.contents = separator;
  
    try {
      tempFrame.textRange.duplicate(targetFrame);
    } catch (err) {
      targetFrame.contents = targetFrame.contents + separator;
    }
  
    tempFrame.remove();
  }
  }

  function runSplitTexts() {
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
      item.move(sourceFrame, ElementPlacement.PLACEBEFORE);
    } catch (err) {
      // Si Illustrator no permite moverlo junto al texto original, se queda en la capa activa.
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
  }
})();
