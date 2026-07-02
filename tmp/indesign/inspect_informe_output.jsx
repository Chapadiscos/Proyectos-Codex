var doc = app.open(File('/Volumes/DATOS/Proyectos Codex/Extraer textos/InformeAnual_2025_indices_maquetado.indd'), false);
var report=[];
report.push('pages=' + doc.pages.length);
for (var p=0; p<doc.pages.length; p++) {
  report.push('PAGE ' + (p+1) + ' frames=' + doc.pages[p].textFrames.length);
  for (var f=0; f<doc.pages[p].textFrames.length; f++) {
    var tf=doc.pages[p].textFrames[f];
    var s=tf.contents.replace(/\r/g,' | ');
    report.push('frame ' + f + ' chars=' + tf.contents.length + ' overset=' + tf.overflows + ' contents=' + s.substring(0,220));
  }
}
doc.close(SaveOptions.NO);
report.join('\n');
