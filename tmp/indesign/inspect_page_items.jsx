var doc = app.open(File('/Volumes/DATOS/Proyectos Codex/Extraer textos/Indices limpio.indd'), false);
var report = [];
for (var p = 0; p < doc.pages.length; p++) {
  report.push('PAGE ' + (p + 1));
  for (var i = 0; i < doc.pages[p].pageItems.length; i++) {
    var it = doc.pages[p].pageItems[i];
    var name = '';
    try { name = it.constructor.name; } catch(e) {}
    var fill = '';
    try { fill = it.fillColor.name; } catch(e) {}
    report.push(i + ' type=' + name + ' bounds=' + it.geometricBounds.join(',') + ' fill=' + fill);
  }
}
doc.close(SaveOptions.NO);
report.join('\n');
