var folder = Folder("~/Desktop");
var scriptFile = File($.fileName);
if (scriptFile && scriptFile.exists) {
  folder = scriptFile.parent;
}

var modelFile = File(folder.fsName + "/Algoritmo ejemplo.indd");
var outFile = File(folder.fsName + "/Algoritmo ejemplo - inventario.txt");

function line(s) {
  outFile.writeln(String(s));
}

app.scriptPreferences.userInteractionLevel = UserInteractionLevels.NEVER_INTERACT;
var doc = app.open(modelFile, false);

outFile.encoding = "UTF-8";
outFile.open("w");

line("DOCUMENTO");
line("Nombre: " + doc.name);
line("Paginas: " + doc.pages.length);
line("Intent: " + doc.documentPreferences.intent);
line("Page width: " + doc.documentPreferences.pageWidth);
line("Page height: " + doc.documentPreferences.pageHeight);
line("Facing pages: " + doc.documentPreferences.facingPages);
line("Bleed top: " + doc.documentPreferences.documentBleedTopOffset);
line("");

line("COLORES");
for (var i = 0; i < doc.colors.length; i++) {
  var c = doc.colors[i];
  try {
    line(c.name + " | " + c.model + " | " + c.space + " | " + c.colorValue);
  } catch (e) {
    line(c.name);
  }
}
line("");

line("ESTILOS PARRAFO");
for (var p = 0; p < doc.paragraphStyles.length; p++) {
  var ps = doc.paragraphStyles[p];
  try {
    line(ps.name + " | font=" + ps.appliedFont.name + " | style=" + ps.fontStyle + " | size=" + ps.pointSize + " | leading=" + ps.leading + " | align=" + ps.justification);
  } catch (e2) {
    line(ps.name);
  }
}
line("");

line("ESTILOS OBJETO");
for (var o = 0; o < doc.objectStyles.length; o++) {
  line(doc.objectStyles[o].name);
}
line("");

line("ELEMENTOS");
for (var pg = 0; pg < doc.pages.length; pg++) {
  var page = doc.pages[pg];
  line("PAGINA " + (pg + 1));
  var items = page.allPageItems;
  for (var it = 0; it < items.length; it++) {
    var item = items[it];
    var label = "";
    try { label = item.label; } catch (ignore) {}
    var gb = "";
    try { gb = item.geometricBounds.join(", "); } catch (ignore2) {}
    var stroke = "";
    try { stroke = item.strokeColor.name + " " + item.strokeWeight; } catch (ignore3) {}
    var fill = "";
    try { fill = item.fillColor.name; } catch (ignore4) {}
    var contents = "";
    try {
      if (item.constructor.name === "TextFrame") {
        contents = item.contents.replace(/\r/g, " / ");
      }
    } catch (ignore5) {}
    line(item.constructor.name + " | gb=" + gb + " | fill=" + fill + " | stroke=" + stroke + " | label=" + label + " | text=" + contents);
  }
}

outFile.close();
doc.close(SaveOptions.NO);
