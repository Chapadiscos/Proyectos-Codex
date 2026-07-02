var scriptFile = File($.fileName);
var folder = scriptFile.parent;
var inddFile = File(folder.fsName + "/Algoritmos convertidos.indd");
var reportFile = File(folder.fsName + "/Algoritmos convertidos - verificacion.txt");

app.scriptPreferences.userInteractionLevel = UserInteractionLevels.NEVER_INTERACT;
var doc = app.open(inddFile, false);

reportFile.encoding = "UTF-8";
reportFile.open("w");
reportFile.writeln("VERIFICACION DE ALGORITMOS CONVERTIDOS");
reportFile.writeln("Paginas: " + doc.pages.length);

var overflowCount = 0;
for (var p = 0; p < doc.pages.length; p++) {
  var page = doc.pages[p];
  reportFile.writeln("Pagina " + (p + 1));
  var items = page.allPageItems;
  for (var i = 0; i < items.length; i++) {
    try {
      if (items[i].constructor.name === "TextFrame" && items[i].overflows) {
        overflowCount++;
        reportFile.writeln("  DESBORDE: " + items[i].geometricBounds.join(", ") + " | " + items[i].contents.replace(/\r/g, " / "));
      }
    } catch (e) {}
  }
}
reportFile.writeln("Total desbordes: " + overflowCount);

app.jpegExportPreferences.jpegQuality = JPEGOptionsQuality.MAXIMUM;
app.jpegExportPreferences.exportResolution = 160;
app.jpegExportPreferences.jpegRenderingStyle = JPEGOptionsFormat.BASELINE_ENCODING;
app.jpegExportPreferences.exportingSpread = false;

for (var pg = 0; pg < doc.pages.length; pg++) {
  app.jpegExportPreferences.pageString = String(pg + 1);
  doc.exportFile(ExportFormat.JPG, File(folder.fsName + "/Algoritmos convertidos - pagina " + (pg + 1) + ".jpg"), false);
}

reportFile.close();
doc.close(SaveOptions.NO);
