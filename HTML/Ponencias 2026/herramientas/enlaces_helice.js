// Marcador «Enlaces Hélice»: copia al portapapeles las URL de todas las imágenes (y
// fuentes, para la CSS de un libro nuevo) que aparecen en la página abierta del panel
// y las muestra en un recuadro que se cierra solo, sin tener que confirmar nada.
// instalar_marcador.html construye el marcador a partir de esta función.
function enlacesHelice() {
  var re = /(?:https?:\/\/[^\s"'<>)]+)?\/uploads\/app\/\d+\/files\/[\w.-]+?\.(?:jpe?g|png|gif|webp|woff2?|otf|ttf)/gi;
  var urls = new Set();
  for (var m of document.documentElement.innerHTML.matchAll(re)) {
    urls.add(m[0].startsWith("/") ? location.origin + m[0] : m[0]);
  }
  var texto = Array.from(urls).join("\n");

  var id = "enlaces-helice-aviso";
  var viejo = document.getElementById(id);
  if (viejo) viejo.remove();
  var caja = document.createElement("div");
  caja.id = id;
  caja.style.cssText = "position:fixed;top:16px;right:16px;z-index:2147483647;width:440px;max-width:90vw;" +
    "background:#fff;color:#222;border:2px solid #c55b17;border-radius:8px;box-shadow:0 4px 20px rgba(0,0,0,.3);" +
    "font:13px/1.4 -apple-system,Helvetica,sans-serif;padding:12px;text-align:left";
  var cerrar = document.createElement("span");
  cerrar.textContent = "×";
  cerrar.style.cssText = "float:right;cursor:pointer;font-size:20px;line-height:1;margin-left:8px";
  cerrar.onclick = function () { caja.remove(); };
  var titulo = document.createElement("div");
  titulo.style.cssText = "font-weight:600;margin-bottom:6px";
  var lista = document.createElement("textarea");
  lista.value = texto;
  lista.readOnly = true;
  lista.style.cssText = "width:100%;height:150px;font:11px/1.3 Menlo,monospace;box-sizing:border-box;resize:vertical";
  caja.append(cerrar, titulo, lista);
  document.body.append(caja);

  // Se cierra solo: 4 s después de copiar. Con el ratón encima se pausa (para leerlo)
  // y al sacarlo se cierra a los 3 s. Antes la pausa no se reanudaba y, como el ratón
  // pasa por encima al bajar desde la barra de marcadores, el recuadro no se cerraba.
  var temporizador = null, autocierre = false;
  function programar(ms) {
    clearTimeout(temporizador);
    temporizador = setTimeout(function () { caja.remove(); }, ms);
  }
  caja.onmouseenter = function () { clearTimeout(temporizador); };
  caja.onmouseleave = function () { if (autocierre) programar(3000); };
  function terminar(copiado) {
    if (!urls.size) {
      titulo.textContent = "No he encontrado enlaces de imágenes ni fuentes en esta página";
      lista.style.display = "none";
    } else if (copiado) {
      titulo.textContent = urls.size + " enlaces copiados al portapapeles";
    } else {
      titulo.textContent = "No se han podido copiar: el texto está seleccionado, pulsa ⌘C";
      lista.focus();
      lista.select();
      return;  // se queda abierto para copiarlo a mano
    }
    autocierre = true;
    if (!caja.matches(":hover")) programar(4000);
  }
  if (!urls.size) return terminar(false);
  navigator.clipboard.writeText(texto).then(
    function () { terminar(true); },
    function () { lista.select(); terminar(document.execCommand("copy")); }
  );
}
