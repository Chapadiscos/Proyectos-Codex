var doc = app.open(File('/Volumes/DATOS/Proyectos Codex/Extraer textos/Indices limpio.indd'), false);
var report = [];
while (doc.pages.length > 1) {
  doc.pages[-1].remove();
}
var page = doc.pages[0];
var leftBody = null;
var rightBody = null;
for (var i = 0; i < page.textFrames.length; i++) {
  var tf = page.textFrames[i];
  var b = tf.geometricBounds;
  if (b[0] >= 75 && b[1] < 100) {
    leftBody = tf;
  }
  if (b[0] >= 75 && b[1] >= 100) {
    rightBody = tf;
  }
}
report.push('left=' + (leftBody ? leftBody.isValid : false));
report.push('right=' + (rightBody ? rightBody.isValid : false));
leftBody.geometricBounds = [80, 19, 276.5, 97.5];
rightBody.geometricBounds = [80, 112.5, 276.5, 191];
leftBody.nextTextFrame = rightBody;
leftBody.contents = 'uno\rdos\rtres';
report.push('left overflow=' + leftBody.overflows);
report.push('story chars=' + leftBody.parentStory.contents.length);
doc.close(SaveOptions.NO);
report.join('\n');
