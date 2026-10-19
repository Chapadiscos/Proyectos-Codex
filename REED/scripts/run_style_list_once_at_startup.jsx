(function () {
  var launcher = File($.fileName);
  var script = File("/Users/jose/Desktop/Pruebas/scripts/list_indesign_styles.jsx");

  try {
    $.evalFile(script);
  } finally {
    try {
      launcher.remove();
    } catch (_) {}
  }
}());
