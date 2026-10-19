(function () {
  var inddPath = "/Users/jose/Desktop/Pruebas/Maqueta REED.indd";
  var reportPath = "/Users/jose/Desktop/Pruebas/indesign_styles_report.txt";

  function namesOf(collection) {
    var names = [];
    for (var i = 0; i < collection.length; i += 1) {
      try {
        names.push(collection[i].name);
      } catch (_) {}
    }
    names.sort();
    return names;
  }

  var inddFile = File(inddPath);
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

  var lines = [];
  lines.push("PARAGRAPH STYLES");
  lines = lines.concat(namesOf(doc.allParagraphStyles || doc.paragraphStyles));
  lines.push("");
  lines.push("TABLE STYLES");
  lines = lines.concat(namesOf(doc.allTableStyles || doc.tableStyles));

  var report = File(reportPath);
  report.encoding = "UTF-8";
  report.open("w");
  report.write(lines.join("\n"));
  report.close();
}());
