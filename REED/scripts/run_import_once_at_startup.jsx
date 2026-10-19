/* Temporary InDesign startup launcher. It runs the workspace importer once. */
(function () {
  var launcher = File($.fileName);
  var script = File("/Users/jose/Desktop/Pruebas/scripts/import_word_to_indesign.jsx");

  try {
    if (script.exists) {
      $.evalFile(script);
    } else {
      throw new Error("No se encuentra el importador: " + script.fsName);
    }
  } finally {
    try {
      launcher.remove();
    } catch (_) {}
  }
}());
