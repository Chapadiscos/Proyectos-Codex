var doc = app.open(File('/Volumes/DATOS/Proyectos Codex/Indices varios/MSR2025 Varios_indices_maquetado.indd'), false);
var report = [];
report.push('pages=' + doc.pages.length);
report.push('doc textFrames=' + doc.textFrames.length);
for (var i = 0; i < doc.textFrames.length; i++) {
  var tf = doc.textFrames[i];
  var parentName = 'none';
  try {
    parentName = tf.parentPage ? tf.parentPage.name : 'no parentPage';
  } catch (e) {}
  report.push(i + ' parent=' + parentName + ' overflows=' + tf.overflows + ' chars=' + tf.contents.length + ' sample=' + tf.contents.substring(0, 60));
}
doc.close(SaveOptions.NO);
report.join('\n');
