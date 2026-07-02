var docPath = File('/Volumes/DATOS/Proyectos Codex/Extraer textos/Indices limpio.indd');
var doc = app.open(docPath, false);
var report = [];
for (var p = 0; p < doc.pages.length; p++) {
  report.push('PAGE ' + (p+1));
  for (var f = 0; f < doc.pages[p].textFrames.length; f++) {
    var tf = doc.pages[p].textFrames[f];
    var s = tf.contents;
    s = s.replace(/\r/g, '<CR>');
    report.push('frame ' + f + ' bounds=' + tf.geometricBounds.join(',') + ' contents=' + s);
    try { report.push('  first style=' + tf.parentStory.paragraphs[0].appliedParagraphStyle.name); } catch(e) {}
  }
}
doc.close(SaveOptions.NO);
report.join('\n');
