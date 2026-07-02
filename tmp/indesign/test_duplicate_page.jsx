var doc = app.open(File('/Volumes/DATOS/Proyectos Codex/Extraer textos/Indices limpio.indd'), false);
var report = [];
while (doc.pages.length > 1) {
  doc.pages[-1].remove();
}
report.push('after remove pages=' + doc.pages.length);
while (doc.pages.length < 4) {
  doc.pages[0].duplicate(LocationOptions.AFTER, doc.pages[-1]);
  report.push('duplicated pages=' + doc.pages.length);
}
for (var p = 0; p < doc.pages.length; p++) {
  report.push('page ' + (p + 1) + ' frames=' + doc.pages[p].textFrames.length);
}
doc.close(SaveOptions.NO);
report.join('\n');
