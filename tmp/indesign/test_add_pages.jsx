var doc = app.open(File('/Volumes/DATOS/Proyectos Codex/Extraer textos/Indices limpio.indd'), false);
var report = [];
while (doc.pages.length > 1) {
  doc.pages[-1].remove();
}
doc.documentPreferences.allowPageShuffle = true;
doc.spreads.everyItem().allowPageShuffle = true;
while (doc.pages.length < 4) {
  doc.pages.add(LocationOptions.AT_END);
}
for (var p = 0; p < doc.pages.length; p++) {
  report.push('page ' + (p + 1) + ' bounds=' + doc.pages[p].bounds.join(',') + ' frames=' + doc.pages[p].textFrames.length);
}
report.push('spreads=' + doc.spreads.length);
doc.close(SaveOptions.NO);
report.join('\n');
