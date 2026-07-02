var doc = app.open(File('/Volumes/DATOS/Proyectos Codex/Extraer textos/Indices limpio.indd'), false);
var report = [];
while (doc.pages.length > 1) {
  doc.pages[-1].remove();
}
while (doc.pages.length < 4) {
  doc.pages[0].duplicate(LocationOptions.AFTER, doc.pages[-1]);
}
for (var p = 0; p < doc.pages.length; p++) {
  report.push('PAGE ' + (p + 1));
  for (var i = 0; i < doc.pages[p].textFrames.length; i++) {
    var tf = doc.pages[p].textFrames[i];
    report.push(i + ' bounds=' + tf.geometricBounds.join(',') + ' contents=' + tf.contents);
  }
}
doc.close(SaveOptions.NO);
report.join('\n');
