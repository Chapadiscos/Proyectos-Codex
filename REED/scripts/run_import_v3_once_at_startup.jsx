(function () {
  var launcher = File($.fileName);
  var script = File("/Users/jose/Desktop/Pruebas/scripts/import_word_to_indesign_v2.jsx");
  var debug = File("/Users/jose/Desktop/Pruebas/import_word_to_indesign_startup_debug.txt");

  function writeDebug(message) {
    debug.encoding = "UTF-8";
    debug.open("w");
    debug.write(message);
    debug.close();
  }

  try {
    writeDebug("Arrancando importador v3: " + new Date() + "\nScript: " + script.fsName);
    if (!script.exists) {
      throw new Error("No se encuentra el importador: " + script.fsName);
    }
    script.encoding = "UTF-8";
    script.open("r");
    var code = script.read();
    script.close();
    eval(code);
    writeDebug("Importador v3 terminado: " + new Date());
  } catch (error) {
    writeDebug("ERROR v3: " + error);
    throw error;
  } finally {
    try {
      launcher.remove();
    } catch (_) {}
  }
}());
