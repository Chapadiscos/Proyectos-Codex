var docPath = File('/Volumes/DATOS/Proyectos Codex/Extraer textos/Indices limpio.indd');
var doc = app.open(docPath, false);
var report = [];
report.push('name=' + doc.name);
report.push('pages=' + doc.pages.length);
report.push('textFrames=' + doc.textFrames.length);
report.push('paragraphStyles=' + doc.paragraphStyles.length);
for (var i = 0; i < doc.paragraphStyles.length; i++) {
  report.push('style=' + doc.paragraphStyles[i].name);
}
for (var p = 0; p < doc.pages.length; p++) {
  report.push('page ' + (p+1) + ' frames=' + doc.pages[p].textFrames.length);
  for (var f = 0; f < doc.pages[p].textFrames.length; f++) {
    var tf = doc.pages[p].textFrames[f];
    report.push('  frame ' + f + ' bounds=' + tf.geometricBounds.join(',') + ' chars=' + tf.contents.length);
  }
}
doc.close(SaveOptions.NO);
report.join('\n');
