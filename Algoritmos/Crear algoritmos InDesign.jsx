var scriptFile = File($.fileName);
var folder = scriptFile.parent;

var outIndd = File(folder.fsName + "/Algoritmos convertidos.indd");
var outIdml = File(folder.fsName + "/Algoritmos convertidos.idml");
var outPdf = File(folder.fsName + "/Algoritmos convertidos.pdf");

app.scriptPreferences.userInteractionLevel = UserInteractionLevels.NEVER_INTERACT;
app.scriptPreferences.measurementUnit = MeasurementUnits.MILLIMETERS;

if (outIndd.exists) outIndd.remove();
if (outIdml.exists) outIdml.remove();
if (outPdf.exists) outPdf.remove();

var doc = app.documents.add();
doc.documentPreferences.facingPages = false;
doc.documentPreferences.pageWidth = 420;
doc.documentPreferences.pageHeight = 315;
doc.viewPreferences.horizontalMeasurementUnits = MeasurementUnits.MILLIMETERS;
doc.viewPreferences.verticalMeasurementUnits = MeasurementUnits.MILLIMETERS;
doc.marginPreferences.top = 0;
doc.marginPreferences.bottom = 0;
doc.marginPreferences.left = 0;
doc.marginPreferences.right = 0;

function colorByName(name, model, space, values) {
  var c = doc.colors.itemByName(name);
  if (!c.isValid) {
    c = doc.colors.add({
      name: name,
      model: model,
      space: space,
      colorValue: values
    });
  }
  return c;
}

var ORANGE = colorByName("Algoritmo naranja", ColorModel.PROCESS, ColorSpace.CMYK, [18, 72, 100, 6]);
var ORANGE_LIGHT = colorByName("Algoritmo naranja claro", ColorModel.PROCESS, ColorSpace.CMYK, [3, 10, 16, 0]);
var GREY = colorByName("Texto gris algoritmo", ColorModel.PROCESS, ColorSpace.CMYK, [0, 0, 0, 55]);
var LIGHT_GREY = colorByName("Fondo gris algoritmo", ColorModel.PROCESS, ColorSpace.CMYK, [0, 0, 0, 6]);
var BLACK = doc.swatches.itemByName("Black");
var NONE = doc.swatches.itemByName("None");
var PAPER = doc.swatches.itemByName("Paper");

function U(s) {
  return decodeURIComponent(s);
}

function findFont(names) {
  for (var i = 0; i < names.length; i++) {
    try {
      var f = app.fonts.itemByName(names[i]);
      if (f.isValid) return f;
    } catch (e) {}
  }
  return app.fonts[0];
}

var FONT_REG = findFont([
  "Neue Haas Grotesk Display Pro\t45 Light",
  "Avenir\tBook",
  "Helvetica\tRegular",
  "Arial\tRegular"
]);
var FONT_BOLD = findFont([
  "Neue Haas Grotesk Display Pro\t75 Bold",
  "Neue Haas Grotesk Display Pro\t65 Medium",
  "Avenir\tHeavy",
  "Helvetica\tBold",
  "Arial\tBold"
]);
var FONT_ITALIC = findFont([
  "Neue Haas Grotesk Display Pro\t46 Light Italic",
  "Avenir\tOblique",
  "Helvetica\tOblique",
  "Arial\tItalic"
]);

function applyText(tf, opts) {
  var text = tf.parentStory.texts[0];
  text.appliedFont = opts.bold ? FONT_BOLD : (opts.italic ? FONT_ITALIC : FONT_REG);
  text.pointSize = opts.size || 7;
  text.leading = opts.leading || ((opts.size || 7) * 1.15);
  text.fillColor = opts.color || BLACK;
  text.justification = opts.align === "left" ? Justification.LEFT_ALIGN : Justification.CENTER_ALIGN;
  try {
    text.hyphenation = false;
  } catch (e) {}
}

function fitText(tf, minSize) {
  var text = tf.parentStory.texts[0];
  var size = Number(text.pointSize);
  var min = minSize || 4.2;
  var guard = 0;
  while (tf.overflows && size > min && guard < 40) {
    size -= 0.25;
    text.pointSize = size;
    text.leading = size * 1.12;
    guard++;
  }
}

function box(page, x, y, w, h, text, opts) {
  opts = opts || {};
  var tf = page.textFrames.add();
  tf.geometricBounds = [y, x, y + h, x + w];
  tf.contents = text;
  tf.fillColor = opts.fill || PAPER;
  if (opts.stroke === false) {
    tf.strokeColor = PAPER;
    tf.strokeWeight = 0;
  } else {
    tf.strokeColor = opts.strokeColor || ORANGE;
    tf.strokeWeight = opts.strokeWeight === undefined ? 0.5 : opts.strokeWeight;
  }
  try {
    tf.textFramePreferences.insetSpacing = opts.inset || [1.1, 1.5, 1.1, 1.5];
    tf.textFramePreferences.verticalJustification = opts.vAlign === "top" ? VerticalJustification.TOP_ALIGN : VerticalJustification.CENTER_ALIGN;
  } catch (e) {}
  applyText(tf, opts);
  if (opts.firstBold) {
    try { tf.parentStory.paragraphs[0].appliedFont = FONT_BOLD; } catch (e2) {}
  }
  fitText(tf, opts.minSize || 4.2);
  return tf;
}

function label(page, x, y, w, h, text) {
  return box(page, x, y, w, h, text, {
    bold: true,
    size: 6.4,
    leading: 7,
    fill: PAPER,
    inset: [0.4, 1, 0.4, 1]
  });
}

function line(page, x1, y1, x2, y2, arrow, dashed) {
  var gl = page.graphicLines.add();
  gl.paths[0].entirePath = [[x1, y1], [x2, y2]];
  gl.strokeColor = ORANGE;
  gl.strokeWeight = dashed ? 0.55 : 0.75;
  if (dashed) {
    try { gl.strokeType = app.strokeStyles.itemByName("Dashed"); } catch (e) {}
    try { gl.strokeType = app.strokeStyles.itemByName("$ID/Dashed"); } catch (e2) {}
  }
  if (arrow) {
    try { gl.endArrowHead = ArrowHead.TRIANGLE_ARROW_HEAD; } catch (e3) {}
  }
  try { gl.sendToBack(); } catch (e4) {}
  return gl;
}

function poly(page, pts, arrow, dashed) {
  for (var i = 0; i < pts.length - 1; i++) {
    line(page, pts[i][0], pts[i][1], pts[i + 1][0], pts[i + 1][1], arrow && i === pts.length - 2, dashed);
  }
}

function mapFactory(srcW, srcH, left, top, width, height) {
  return {
    x: function (v) { return left + (v / srcW) * width; },
    y: function (v) { return top + (v / srcH) * height; },
    w: function (v) { return (v / srcW) * width; },
    h: function (v) { return (v / srcH) * height; }
  };
}

function mappedBox(page, m, r, text, opts) {
  return box(page, m.x(r[0]), m.y(r[1]), m.w(r[2]), m.h(r[3]), text, opts);
}

function mappedLabel(page, m, r, text) {
  return label(page, m.x(r[0]), m.y(r[1]), m.w(r[2]), m.h(r[3]), text);
}

function mappedPoly(page, m, pts, arrow, dashed) {
  var mapped = [];
  for (var i = 0; i < pts.length; i++) {
    mapped.push([m.x(pts[i][0]), m.y(pts[i][1])]);
  }
  poly(page, mapped, arrow, dashed);
}

function drawLio(page) {
  var m = mapFactory(1448, 1086, 12, 8, 396, 297);

  mappedBox(page, m, [210, 5, 1030, 42], U("Algoritmo de decisi%C3%B3n ante luxaci%C3%B3n/subluxaci%C3%B3n de LIO"), {
    stroke: false, bold: true, size: 13.2, leading: 14
  });
  mappedBox(page, m, [350, 50, 750, 26], U("Evaluaci%C3%B3n y manejo en urgencias y cirug%C3%ADa diferida"), {
    stroke: false, italic: true, color: GREY, size: 8.5, leading: 9.5
  });

  mappedBox(page, m, [433, 91, 474, 37], U("Sospecha de luxaci%C3%B3n / subluxaci%C3%B3n de LIO"), { bold: true, size: 7.2 });
  mappedBox(page, m, [489, 145, 349, 109], U("Exploraci%C3%B3n completa\r- Biomicroscop%C3%ADa\r- PIO\r- OCT segmento anterior\r- Valoraci%C3%B3n de retina y m%C3%A1cula"), {
    firstBold: true, align: "left", size: 6.2, leading: 7.1, inset: [1.4, 7, 1.4, 7], vAlign: "top"
  });
  mappedBox(page, m, [473, 272, 374, 36], U("%C2%BFExisten criterios de urgencia?"), { bold: true, size: 6.9 });

  mappedLabel(page, m, [286, 310, 68, 28], U("S%C3%AD"));
  mappedBox(page, m, [185, 365, 263, 35], U("Cirug%C3%ADa urgente"), { bold: true, size: 7 });
  mappedBox(page, m, [184, 413, 274, 103], U("- Contacto corneal\r- Bloqueo pupilar\r- S%C3%ADndrome UGH grave\r- Luxaci%C3%B3n v%C3%ADtrea con DR asociado"), {
    align: "left", size: 6.1, leading: 7.1, inset: [2.1, 3, 1.7, 3]
  });

  mappedLabel(page, m, [916, 310, 68, 28], "No");
  mappedBox(page, m, [795, 346, 291, 42], U("Control de inflamaci%C3%B3n y PIO\rEstudio anat%C3%B3mico completo"), { size: 6.5, leading: 7.2 });
  mappedBox(page, m, [772, 407, 334, 48], U("%C2%BFS%C3%ADntomas importantes o riesgo\rde progresi%C3%B3n?"), { bold: true, size: 6.5, leading: 7.1 });
  mappedLabel(page, m, [724, 468, 64, 28], "No");
  mappedBox(page, m, [636, 502, 241, 32], U("Observaci%C3%B3n y seguimiento"), { size: 6.5 });
  mappedLabel(page, m, [1093, 468, 64, 28], U("S%C3%AD"));
  mappedBox(page, m, [1016, 502, 221, 32], U("Cirug%C3%ADa diferida"), { bold: true, size: 6.5 });

  mappedBox(page, m, [482, 563, 397, 31], U("%C2%BFExiste soporte capsular suficiente?"), { bold: true, size: 6.7 });
  mappedLabel(page, m, [323, 594, 61, 29], U("S%C3%AD"));
  mappedBox(page, m, [219, 631, 259, 52], U("Reposicionar complejo\rsaco-LIO +/- fijaci%C3%B3n escleral"), { size: 6.2, leading: 7 });
  mappedLabel(page, m, [959, 594, 61, 29], "No");
  mappedBox(page, m, [850, 626, 275, 31], "Analizar tipo de LIO", { size: 6.4 });

  mappedBox(page, m, [627, 678, 156, 29], "LIO 3 piezas", { size: 5.8 });
  mappedBox(page, m, [626, 724, 156, 49], "Yamane / Canabrava /\rsuturada", { size: 5.1, leading: 6 });
  mappedBox(page, m, [800, 678, 166, 29], U("Monobloque acr%C3%ADlica"), { size: 5.5 });
  mappedBox(page, m, [800, 724, 166, 49], U("Recambio o fijaci%C3%B3n\rescleral"), { size: 5.1, leading: 6 });
  mappedBox(page, m, [980, 678, 151, 29], "Artisan / iris-claw", { size: 5.3 });
  mappedBox(page, m, [985, 724, 144, 49], U("Fijaci%C3%B3n iridiana"), { size: 5.1 });
  mappedBox(page, m, [1152, 678, 151, 29], "Apoyo angular", { size: 5.4 });
  mappedBox(page, m, [1152, 724, 151, 49], "Casos seleccionados", { size: 5.1 });

  mappedBox(page, m, [528, 794, 291, 37], U("%C2%BFLIO en cavidad v%C3%ADtrea?"), { bold: true, size: 6.4 });
  mappedLabel(page, m, [416, 824, 54, 30], U("S%C3%AD"));
  mappedBox(page, m, [318, 853, 234, 48], U("Vitrectom%C3%ADa pars plana +\rrescate o recambio de LIO"), { size: 5.8, leading: 6.6 });
  mappedLabel(page, m, [884, 824, 54, 30], "No");
  mappedBox(page, m, [790, 855, 245, 38], U("Cirug%C3%ADa anterior convencional"), { size: 5.9 });

  mappedBox(page, m, [377, 932, 617, 106], U("Seguimiento postoperatorio\r\r- PIO                                      - Retina y DR\r- Endotelio corneal                  - Descentramiento de LIO\r- Edema macular cistoide       - Refracci%C3%B3n residual"), {
    firstBold: true, align: "left", size: 6.1, leading: 7.2, inset: [2, 10, 1.5, 10]
  });
  mappedBox(page, m, [285, 1051, 890, 28], U("Figura. Algoritmo de decisi%C3%B3n ante luxaci%C3%B3n/subluxaci%C3%B3n de lente intraocular."), {
    stroke: false, italic: true, size: 7.2, leading: 8
  });

  mappedPoly(page, m, [[670, 128], [670, 145]], true);
  mappedPoly(page, m, [[670, 254], [670, 272]], true);
  mappedPoly(page, m, [[473, 290], [319, 290], [319, 310]], true);
  mappedPoly(page, m, [[320, 338], [320, 365]], true);
  mappedPoly(page, m, [[319, 400], [319, 413]], true);
  mappedPoly(page, m, [[847, 290], [951, 290], [951, 310]], true);
  mappedPoly(page, m, [[951, 338], [951, 346]], true);
  mappedPoly(page, m, [[951, 388], [951, 407]], true);
  mappedPoly(page, m, [[772, 455], [756, 455], [756, 468]], true);
  mappedPoly(page, m, [[756, 496], [756, 502]], true);
  mappedPoly(page, m, [[1106, 455], [1125, 455], [1125, 468]], true);
  mappedPoly(page, m, [[1125, 496], [1125, 502]], true);
  mappedPoly(page, m, [[319, 516], [319, 542], [682, 542], [682, 563]], true);
  mappedPoly(page, m, [[756, 534], [756, 563]], true);
  mappedPoly(page, m, [[1125, 534], [1125, 542], [682, 542], [682, 563]], true);
  mappedPoly(page, m, [[482, 579], [354, 579], [354, 594]], true);
  mappedPoly(page, m, [[354, 623], [354, 631]], true);
  mappedPoly(page, m, [[879, 579], [990, 579], [990, 594]], true);
  mappedPoly(page, m, [[990, 623], [990, 626]], true);
  mappedPoly(page, m, [[987, 657], [987, 664], [705, 664], [705, 678]], true);
  mappedPoly(page, m, [[987, 664], [883, 664], [883, 678]], true);
  mappedPoly(page, m, [[987, 664], [1055, 664], [1055, 678]], true);
  mappedPoly(page, m, [[987, 664], [1227, 664], [1227, 678]], true);
  mappedPoly(page, m, [[705, 707], [705, 724]], true);
  mappedPoly(page, m, [[883, 707], [883, 724]], true);
  mappedPoly(page, m, [[1055, 707], [1055, 724]], true);
  mappedPoly(page, m, [[1227, 707], [1227, 724]], true);
  mappedPoly(page, m, [[354, 683], [354, 775], [673, 775], [673, 794]], true);
  mappedPoly(page, m, [[705, 773], [705, 785], [673, 785], [673, 794]], true);
  mappedPoly(page, m, [[883, 773], [883, 785], [673, 785]], false);
  mappedPoly(page, m, [[1055, 773], [1055, 785], [673, 785]], false);
  mappedPoly(page, m, [[1227, 773], [1227, 785], [673, 785]], false);
  mappedPoly(page, m, [[528, 813], [443, 813], [443, 824]], true);
  mappedPoly(page, m, [[443, 854], [443, 853]], true);
  mappedPoly(page, m, [[819, 813], [911, 813], [911, 824]], true);
  mappedPoly(page, m, [[911, 854], [911, 855]], true);
  mappedPoly(page, m, [[443, 901], [443, 918], [685, 918], [685, 932]], true);
  mappedPoly(page, m, [[911, 893], [911, 918], [685, 918]], false);
}

function drawTass(page) {
  var m = mapFactory(640, 480, 12, 8, 396, 297);

  mappedBox(page, m, [204, 7, 229, 39], U("INFLAMACI%C3%93N POSTQUIR%C3%9ARGICA PRECOZ\rPaciente operado de segmento anterior"), {
    fill: LIGHT_GREY, strokeColor: ORANGE, strokeWeight: 0.7, firstBold: true, size: 6.1, leading: 7
  });
  mappedBox(page, m, [239, 64, 164, 22], U("%C2%BF12-48 h tras la cirug%C3%ADa?"), { size: 6.2 });
  mappedLabel(page, m, [144, 99, 84, 20], "NO");
  mappedLabel(page, m, [396, 99, 84, 20], U("S%C3%8D"));
  mappedBox(page, m, [62, 125, 168, 58], U("Sospecha de ENDOFTALMITIS\rIniciar protocolo de endoftalmitis:\r- Toma de muestras\r- Tratamiento antibi%C3%B3tico inmediato"), {
    firstBold: true, align: "left", size: 5.2, leading: 6.1, inset: [1.8, 2.2, 1.5, 2.2]
  });
  mappedBox(page, m, [357, 124, 149, 20], "Valorar dolor y vitritis", { size: 5.9 });
  mappedBox(page, m, [359, 162, 155, 22], U("%C2%BFDolor intenso o vitritis?"), { size: 5.8 });
  mappedLabel(page, m, [285, 198, 72, 21], U("S%C3%8D"));
  mappedBox(page, m, [210, 223, 185, 63], U("Sospecha de ENDOFTALMITIS\rIniciar protocolo de endoftalmitis:\r- Toma de muestras\r- Tratamiento antibi%C3%B3tico inmediato"), {
    firstBold: true, align: "left", size: 5.1, leading: 6, inset: [1.8, 2.2, 1.5, 2.2]
  });
  mappedLabel(page, m, [484, 198, 72, 21], "NO");
  mappedBox(page, m, [429, 223, 183, 63], U("Sospecha de TASS\r- Reacci%C3%B3n en c%C3%A1mara anterior\r- Edema corneal blanco a blanco"), {
    firstBold: true, align: "left", size: 5.1, leading: 6, inset: [1.8, 2.2, 1.5, 2.2]
  });
  mappedBox(page, m, [427, 292, 185, 52], "TRATAMIENTO INMEDIATO\r- Prednisolona acetato 1% cada 1-2 horas\r- Control estrecho de la PIO\r- Evitar prostaglandinas", {
    firstBold: true, align: "left", size: 4.9, leading: 5.8, inset: [1.8, 2.2, 1.5, 2.2]
  });
  mappedBox(page, m, [413, 354, 151, 20], U("Revisi%C3%B3n en 24-48 h"), { size: 5.8 });
  mappedBox(page, m, [432, 382, 135, 22], U("%C2%BFMejor%C3%ADa cl%C3%ADnica?"), { size: 5.8 });
  mappedLabel(page, m, [363, 413, 60, 21], U("S%C3%8D"));
  mappedBox(page, m, [306, 432, 143, 42], "Mantener pauta\ry descenso progresivo\rde corticoides", { size: 5.1, leading: 6 });
  mappedLabel(page, m, [543, 413, 60, 21], "NO");
  mappedBox(page, m, [473, 432, 128, 42], U("Revalorar diagn%C3%B3stico diferencial\rConsiderar:\r- Endoftalmitis\r- Nuevo estudio etiol%C3%B3gico"), {
    align: "left", size: 4.6, leading: 5.3, inset: [1.5, 2, 1.3, 2]
  });

  mappedBox(page, m, [44, 283, 184, 75], U("POSIBLES SECUELAS\r- Edema corneal persistente\r  -> DMEK / DSAEK\r- Glaucoma secundario\r  -> Tratamiento hipotensor\r  -> Cirug%C3%ADa filtrante si precisa"), {
    firstBold: true, align: "left", size: 4.7, leading: 5.4, inset: [1.8, 2.2, 1.5, 2.2], strokeWeight: 0.55
  });
  mappedBox(page, m, [68, 370, 135, 39], U("%C2%BFExisten otros casos\roperados en el mismo periodo?"), { size: 5.1, leading: 5.8, strokeWeight: 0.55 });
  mappedLabel(page, m, [41, 416, 58, 20], U("S%C3%8D"));
  mappedLabel(page, m, [155, 416, 58, 20], "NO");
  mappedBox(page, m, [8, 442, 135, 32], "Investigar posible brote de TASS\ry notificar", { size: 4.8, leading: 5.5 });
  mappedBox(page, m, [153, 442, 85, 32], "Seguimiento\rhabitual", { size: 4.8, leading: 5.5 });

  mappedPoly(page, m, [[318, 46], [318, 64]], true);
  mappedPoly(page, m, [[239, 75], [187, 75], [187, 99]], true);
  mappedPoly(page, m, [[187, 119], [187, 125]], true);
  mappedPoly(page, m, [[403, 75], [438, 75], [438, 99]], true);
  mappedPoly(page, m, [[438, 119], [438, 124]], true);
  mappedPoly(page, m, [[438, 144], [438, 162]], true);
  mappedPoly(page, m, [[359, 173], [322, 173], [322, 198]], true);
  mappedPoly(page, m, [[322, 219], [322, 223]], true);
  mappedPoly(page, m, [[514, 173], [520, 173], [520, 198]], true);
  mappedPoly(page, m, [[520, 219], [520, 223]], true);
  mappedPoly(page, m, [[520, 286], [520, 292]], true);
  mappedPoly(page, m, [[520, 344], [488, 344], [488, 354]], true);
  mappedPoly(page, m, [[488, 374], [488, 382]], true);
  mappedPoly(page, m, [[432, 393], [393, 393], [393, 413]], true);
  mappedPoly(page, m, [[393, 434], [393, 432]], true);
  mappedPoly(page, m, [[567, 393], [573, 393], [573, 413]], true);
  mappedPoly(page, m, [[573, 434], [573, 432]], true);
  mappedPoly(page, m, [[427, 318], [360, 318], [360, 360], [228, 360]], true, true);
  mappedPoly(page, m, [[136, 358], [136, 370]], true, true);
  mappedPoly(page, m, [[136, 409], [70, 409], [70, 416]], true, true);
  mappedPoly(page, m, [[136, 409], [184, 409], [184, 416]], true, true);
  mappedPoly(page, m, [[70, 436], [70, 442]], true);
  mappedPoly(page, m, [[184, 436], [184, 442]], true);
}

drawLio(doc.pages[0]);
var p2 = doc.pages.add(LocationOptions.AFTER, doc.pages[0]);
p2.marginPreferences.top = 0;
p2.marginPreferences.bottom = 0;
p2.marginPreferences.left = 0;
p2.marginPreferences.right = 0;
drawTass(p2);

doc.save(outIndd);
doc.exportFile(ExportFormat.INDESIGN_MARKUP, outIdml);

try {
  var preset = app.pdfExportPresets.itemByName("[High Quality Print]");
  doc.exportFile(ExportFormat.PDF_TYPE, outPdf, false, preset);
} catch (e) {
  doc.exportFile(ExportFormat.PDF_TYPE, outPdf);
}

doc.close(SaveOptions.YES);
