// Marcador «Subir a Hélice»: sube a Ficheros de Hélice las imágenes de un capítulo, en
// su carpeta (Ponencias Prueba / Bloque 1 / Tema 2 / Capítulo 06), y copia sus URL al
// portapapeles para la app «InDesign a HTML».
// Se pulsa con el panel de Hélice abierto (usa la sesión iniciada) y se elige la carpeta
// del capítulo: en ella la app ha dejado «helice_subida.json» con la ruta en Ficheros y
// los archivos que hay que subir. Crea las carpetas que falten y no sube lo que ya está.
// Usa las mismas llamadas que el panel (/cloud-create-folder, /cloud-upload-file): no son
// de la API oficial y Hélice podría cambiarlas.
// instalar_marcador.html construye el marcador a partir de esta función.
//
// La app también la usa sin marcador (depurar/subida.py): ejecuta esta función en la
// pestaña del panel con desdeApp = {ruta, archivos} después de dejar el contenido de cada
// archivo, en base64, en window.__subidaArchivos[ruta relativa]. El progreso y el
// resultado quedan en window.__subidaHelice, que la app va consultando.
function subirHelice(desdeApp) {
  var app = (location.pathname.match(/\/panel\/([^\/?#]+)/) || [])[1];
  var estado = window.__subidaHelice = { estado: "en curso", log: [], urls: [], error: "" };
  var id = "subir-helice-aviso";
  var viejo = document.getElementById(id);
  if (viejo) viejo.remove();
  var caja = document.createElement("div");
  caja.id = id;
  caja.style.cssText = "position:fixed;top:16px;right:16px;z-index:2147483647;width:460px;max-width:90vw;" +
    "background:#fff;color:#222;border:2px solid #c55b17;border-radius:8px;box-shadow:0 4px 20px rgba(0,0,0,.3);" +
    "font:13px/1.4 -apple-system,Helvetica,sans-serif;padding:12px;text-align:left";
  var cerrar = document.createElement("span");
  cerrar.textContent = "×";
  cerrar.style.cssText = "float:right;cursor:pointer;font-size:20px;line-height:1;margin-left:8px";
  cerrar.onclick = function () { caja.remove(); };
  var titulo = document.createElement("div");
  titulo.style.cssText = "font-weight:600;margin-bottom:6px";
  var registro = document.createElement("div");
  registro.style.cssText = "max-height:180px;overflow:auto;font:11px/1.4 Menlo,monospace;white-space:pre-wrap";
  var boton = document.createElement("button");
  boton.style.cssText = "margin-top:8px;padding:6px 12px;font-size:13px;cursor:pointer";
  caja.append(cerrar, titulo, registro, boton);
  document.body.append(caja);
  function linea(t) { registro.textContent += t + "\n"; registro.scrollTop = 1e9; estado.log.push(t); }

  if (!app) {
    titulo.textContent = "Abre el panel de Hélice (panel/…) y vuelve a pulsar el marcador";
    boton.remove();
    estado.estado = "error";
    estado.error = "La pestaña no es del panel de Hélice";
    return;
  }

  // Contenido de una carpeta de Ficheros (o de la raíz): {token, carpetas: {nombre: id}, archivos: {nombre: url}}
  function listar(carpeta) {
    var url = "/panel/" + app + "/cloud/files?c=1" + (carpeta ? "&file=" + carpeta : "");
    return fetch(url, { credentials: "include", headers: { "X-Requested-With": "XMLHttpRequest" } })
      .then(function (r) { return r.text(); })
      .then(function (html) {
        var doc = new DOMParser().parseFromString(html, "text/html");
        var token = doc.querySelector("input[name=_token]");
        var r = { token: token ? token.value : "", carpetas: {}, archivos: {} };
        doc.querySelectorAll("tr").forEach(function (tr) {
          var bajar = tr.querySelector('a[href^="/fdownload?file="]');
          var abrir = tr.querySelector('a.cajax[href*="file="]');
          var texto = tr.textContent.replace(/\s+/g, " ").trim();
          if (bajar) {
            var m = texto.match(/^(.+?\.[A-Za-z0-9]{2,5}) [\d.,]+ ?[KMG]?B/);
            if (m) r.archivos[m[1]] = location.origin + "/" + bajar.getAttribute("href").split("file=")[1];
          } else if (abrir && tr.querySelector(".fa-folder-closed, .fa-folder")) {
            // El enlace lleva también «Última actualización - fecha»: solo el nombre
            var nombre = abrir.textContent.replace(/\s+/g, " ").replace(/\s*Última actualización.*$/, "").trim();
            r.carpetas[nombre] = abrir.getAttribute("href").split("file=")[1];
          }
        });
        return r;
      });
  }

  function enviar(ruta, datos) {
    var fd = new FormData();
    for (var k in datos) {
      if (Array.isArray(datos[k])) datos[k].forEach(function (v) { fd.append(k, v); });
      else fd.append(k, datos[k]);
    }
    return fetch(ruta, { method: "POST", body: fd, credentials: "include", headers: { "X-Requested-With": "XMLHttpRequest" } })
      .then(function (r) { return r.json(); })
      .then(function (j) { if (j.status != 200) throw new Error(ruta + ": " + (j.msg || j.error || JSON.stringify(j))); return j; });
  }

  // Recorre la ruta creando lo que falte; devuelve el id de la última carpeta
  function asegurarRuta(ruta) {
    var padre = "";
    return ruta.reduce(function (p, nombre) {
      return p.then(function () { return listar(padre); }).then(function (l) {
        if (l.carpetas[nombre]) { padre = l.carpetas[nombre]; return; }
        linea("Creando carpeta «" + nombre + "»…");
        return enviar("/cloud-create-folder", { _token: l.token, app: app, folder_father: padre, name: nombre })
          .then(function () { return listar(padre); })
          .then(function (l2) {
            if (!l2.carpetas[nombre]) throw new Error("No encuentro la carpeta «" + nombre + "» después de crearla");
            padre = l2.carpetas[nombre];
          });
      });
    }, Promise.resolve()).then(function () { return padre; });
  }

  function subir(archivos, carpeta) {  // de 5 en 5
    var lotes = [];
    for (var i = 0; i < archivos.length; i += 5) lotes.push(archivos.slice(i, i + 5));
    return lotes.reduce(function (p, lote) {
      return p.then(function () { return listar(carpeta); }).then(function (l) {
        linea("Subiendo " + lote.map(function (f) { return f.name; }).join(", "));
        return enviar("/cloud-upload-file", { _token: l.token, app: app, folder: carpeta, "file[]": lote });
      });
    }, Promise.resolve());
  }

  function copiar(texto) {
    var area = document.createElement("textarea");
    area.value = texto;
    area.readOnly = true;
    area.style.cssText = "width:100%;height:110px;margin-top:8px;font:11px/1.3 Menlo,monospace;box-sizing:border-box";
    caja.insertBefore(area, boton);
    boton.textContent = "Copiar los enlaces";
    boton.style.display = "";
    boton.onclick = function () {
      area.select();
      navigator.clipboard.writeText(texto).then(
        function () { titulo.textContent = "Enlaces copiados: vuelve a la app y pulsa Continuar"; },
        function () { document.execCommand("copy"); titulo.textContent = "Enlaces copiados: vuelve a la app y pulsa Continuar"; });
    };
    return navigator.clipboard.writeText(texto).then(function () { return true; }, function () { return false; });
  }

  // Sube lo que falte de datos.archivos (rutas relativas) a datos.ruta; porRuta da el File de cada una
  function procesar(datos, porRuta) {
    titulo.textContent = "Subiendo a " + datos.ruta.join(" / ");
    return asegurarRuta(datos.ruta).then(function (carpeta) {
      return listar(carpeta).then(function (l) {
        var faltan = [], ausentes = [];
        datos.archivos.forEach(function (r) {
          var f = porRuta[r];
          if (!f) ausentes.push(r);
          else if (!l.archivos[f.name]) faltan.push(f);
        });
        if (ausentes.length) linea("No están en la carpeta del capítulo: " + ausentes.join(", "));
        linea((datos.archivos.length - faltan.length - ausentes.length) + " ya estaban en Hélice; se suben " + faltan.length);
        return subir(faltan, carpeta).then(function () { return listar(carpeta); });
      });
    }).then(function (l) {
      var urls = [], sinUrl = [];
      datos.archivos.forEach(function (r) {
        var nombre = r.split("/").pop();
        if (l.archivos[nombre]) urls.push(l.archivos[nombre]); else sinUrl.push(nombre);
      });
      if (sinUrl.length) linea("¡Sin URL en Hélice!: " + sinUrl.join(", "));
      return urls;
    });
  }

  function fallo(e) {
    titulo.textContent = "No se ha podido subir";
    linea(String(e));
    estado.estado = "error";
    estado.error = String(e);
  }

  if (desdeApp) {  // la app ha dejado los archivos en base64: sin elegir carpeta
    boton.style.display = "none";
    var porRuta = {};
    desdeApp.archivos.forEach(function (r) {
      var b64 = (window.__subidaArchivos || {})[r];
      if (!b64) return;
      var bin = atob(b64), bytes = new Uint8Array(bin.length);
      for (var i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
      porRuta[r] = new File([bytes], r.split("/").pop(), { type: /\.png$/i.test(r) ? "image/png" : "image/jpeg" });
    });
    procesar(desdeApp, porRuta).then(function (urls) {
      estado.urls = urls;
      estado.estado = "ok";
      titulo.textContent = urls.length + " archivos en Hélice: la app sigue sola";
      delete window.__subidaArchivos;
      setTimeout(function () { caja.remove(); }, 8000);
    }).catch(fallo);
    return;
  }

  var selector = document.createElement("input");
  selector.type = "file";
  selector.webkitdirectory = true;
  selector.multiple = true;
  titulo.textContent = "Subir a Hélice";
  linea("Elige la carpeta del capítulo (la que tiene helice_subida.json).");
  boton.textContent = "Elegir la carpeta del capítulo…";
  boton.onclick = function () { selector.click(); };
  selector.onchange = function () {
    var todos = Array.from(selector.files), porRuta = {};
    todos.forEach(function (f) { porRuta[f.webkitRelativePath.split("/").slice(1).join("/")] = f; });
    var manifiesto = porRuta["helice_subida.json"];
    boton.style.display = "none";
    if (!manifiesto) { titulo.textContent = "Esa carpeta no tiene helice_subida.json: elige la del capítulo"; boton.style.display = ""; return; }
    manifiesto.text().then(function (t) {
      return procesar(JSON.parse(t), porRuta);
    }).then(function (urls) {
      estado.urls = urls;
      estado.estado = "ok";
      return copiar(urls.join("\n")).then(function (ok) {
        titulo.textContent = urls.length + " enlaces" + (ok ? " copiados: vuelve a la app y pulsa Continuar" : ": pulsa «Copiar los enlaces»");
      });
    }).catch(fallo);
  };
}
