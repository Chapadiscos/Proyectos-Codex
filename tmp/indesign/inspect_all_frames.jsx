var doc = app.open(File('/Volumes/DATOS/Proyectos Codex/Extraer textos/MS2025_indices_maquetado.indd'), false);
var report = [];
report.push('pages=' + doc.pages.length);
for (var p = 0; p < doc.pages.length; p++) {
  report.push('page ' + (p + 1) + ' bounds=' + doc.pages[p].bounds.join(',') + ' pageFrames=' + doc.pages[p].textFrames.length);
}
report.push('doc textFrames=' + doc.textFrames.length);
for (var i = 0; i < doc.textFrames.length; i++) {
  var tf = doc.textFrames[i];
  var parentName = 'none';
  try {
    parentName = tf.parentPage ? tf.parentPage.name : 'no parentPage';
  } catch (e) {}
  report.push(i + ' parent=' + parentName + ' bounds=' + tf.geometricBounds.join(',') + ' chars=' + tf.contents.length + ' sample=' + tf.contents.substring(0, 40));
}
doc.close(SaveOptions.NO);
report.join('\n');
