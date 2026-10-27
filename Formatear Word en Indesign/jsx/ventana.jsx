// Ventana «Formatear Word» (Ventana > Formatear Word): todo el proyecto desde InDesign.
// Lanza en segundo plano los programas de Python del proyecto (importar.py, que también resalta
// las palabras de la lista; ortotipografia.py, dudas.py, finalizar.py) y enseña su resultado al
// terminar; mientras, InDesign sigue libre. La configuración (reglas, diccionario, publicación)
// no se edita desde aquí: el usuario pide los cambios a Claude.
// Motor persistente "formatear_word"; la ventana vive en $.global.formatearWord.

#targetengine "formatear_word"

(function () {
    var RAIZ = File($.fileName).parent.parent.fsName;     // carpeta del proyecto
    // Desde InDesign el python3 del sistema es el 3.9 (sin tomllib): ruta completa del 3.14.
    var PYTHON = "/Library/Frameworks/Python.framework/Versions/3.14/bin/python3";
    var TMP = Folder.temp.fsName;

    if ($.global.formatearWord && $.global.formatearWord.ventana) {
        $.global.formatearWord.limpiar();       // al volver a abrirla, sin los datos de la vez anterior
        $.global.formatearWord.ventana.show();
        return;
    }
    var F = $.global.formatearWord = {};

    // ---- procesos en segundo plano --------------------------------------------------------
    function q(s) { return "'" + String(s).replace(/'/g, "'\\''") + "'"; }
    function shell(orden) {
        return app.doScript('do shell script "' + orden.replace(/\\/g, "\\\\").replace(/"/g, '\\"') + '"',
                            ScriptLanguage.APPLESCRIPT_LANGUAGE);
    }
    function leer(f) {
        f.encoding = "UTF-8";
        if (!f.open("r")) return "";
        var s = f.read();
        f.close();
        return s;
    }

    // Lanza «python3 -I programa args» en la carpeta del proyecto; al acabar escribe __FIN__.
    function lanzar(titulo, programa, args) {
        if (F.proceso) { estado.text = "Espera a que termine: " + F.proceso.titulo; return; }
        var log = File(TMP + "/formatear_word_" + new Date().getTime() + ".log");
        // Todo dentro del paréntesis y con la salida y la entrada redirigidas: si el proceso en
        // segundo plano se queda con la salida de «do shell script», InDesign espera a que acabe y
        // el osascript del programa no puede hablar con InDesign (se bloquean los dos).
        var orden = "(cd " + q(RAIZ) + " && " + q(PYTHON) + " -I " + q(programa);
        for (var i = 0; i < args.length; i++) orden += " " + q(args[i]);
        orden += "; echo __FIN__) > " + q(log.fsName) + " 2>&1 < /dev/null & echo $!";
        var pid = shell(orden);
        F.proceso = { titulo: titulo, log: log, pid: pid, inicio: new Date() };
        F.docResultado = documentoActivo();
        estado.text = titulo + "…";
        salida.text = "";
        botones(false);
        F.tarea = app.idleTasks.add({ name: "formatear_word", sleep: 1000 });
        F.tarea.addEventListener(IdleEvent.ON_IDLE, comprobar);
    }

    function comprobar() {
        var p = F.proceso;
        if (!p) return;
        var s = leer(p.log), seg = Math.round((new Date() - p.inicio) / 1000);
        if (s.indexOf("__FIN__") < 0) {
            estado.text = p.titulo + "… " + seg + " s";
            if (s) salida.text = s;
            return;
        }
        terminar();
        salida.text = s.replace(/\n?__FIN__\s*$/, "");
        estado.text = p.titulo + ": terminado en " + seg + " s";
        try { p.log.remove(); } catch (e) {}
        if (F.alTerminar) { var f = F.alTerminar; F.alTerminar = null; try { f(); } catch (e) {} }
    }

    function terminar() {
        if (F.tarea && F.tarea.isValid) F.tarea.remove();
        F.tarea = null;
        F.proceso = null;
        botones(true);
    }

    function detener() {
        var p = F.proceso;
        if (!p) return;
        try { shell("pkill -TERM -P " + p.pid + "; kill -TERM " + p.pid + " 2>/dev/null; true"); } catch (e) {}
        terminar();
        estado.text = p.titulo + ": detenido";
    }

    // ---- ámbito ----------------------------------------------------------------------------
    // Documento activo o todos los «Capitulo…» abiertos: argumentos --documento para los scripts.
    function argsDocumento() {
        if (!app.documents.length) { estado.text = "No hay ningún documento abierto"; return null; }
        if (ambito.selection.index == 1) return [];
        return ["--documento", app.activeDocument.name];
    }
    function nombreAmbito() {
        return ambito.selection.index == 1 ? "los capítulos abiertos" : "«" + app.activeDocument.name + "»";
    }

    // ---- ventana ---------------------------------------------------------------------------
    F.docResultado = null;
    var w = F.ventana = new Window("palette", "Formatear Word", undefined, { resizeable: true });
    w.orientation = "column";
    w.alignChildren = ["fill", "top"];
    w.spacing = 8;

    // ---- publicación: publicaciones/*.toml (menos las reglas) --------------------------------
    var PREFS = File(Folder.userData.fsName + "/formatear_word_publicacion.txt");
    function publicaciones() {
        var fs = Folder(RAIZ + "/publicaciones").getFiles("*.toml"), res = [];
        for (var i = 0; i < fs.length; i++) {
            if (/^ortotipografia\.toml$/.test(decodeURI(fs[i].name))) continue;
            var cab = leer(fs[i]).substr(0, 300), m = cab.match(/Configuraci\u00f3n de \u00ab([^\u00bb]+)\u00bb/);
            var nombre = m ? m[1] : (/^maqueta-base/.test(decodeURI(fs[i].name)) ? "Ponencias (maqueta base)" : decodeURI(fs[i].name));
            res.push({ nombre: nombre, ruta: fs[i].fsName });
        }
        res.sort(function (a, b) { return a.nombre < b.nombre ? -1 : 1; });
        return res;
    }
    function rellenarPublicaciones(elegir) {
        F.pubs = publicaciones();
        publicacion.removeAll();
        var sel = 0;
        if (!elegir) { try { PREFS.open("r"); elegir = PREFS.read(); PREFS.close(); } catch (e) {} }
        for (var i = 0; i < F.pubs.length; i++) {
            publicacion.add("item", F.pubs[i].nombre);
            if (F.pubs[i].ruta == elegir || (!elegir && /maqueta-base/.test(F.pubs[i].ruta))) sel = i;
        }
        publicacion.selection = sel;
    }
    function rutaPublicacion() { return F.pubs[publicacion.selection.index].ruta; }

    var gPub = w.add("group");
    gPub.add("statictext", undefined, "Publicación:");
    var publicacion = gPub.add("dropdownlist", undefined, []);
    publicacion.helpTip = "Estilos y maqueta con los que se importa y se corrige (publicaciones/*.toml)";
    var bNueva = gPub.add("button", undefined, "Nueva publicación…");
    bNueva.helpTip = "Elige el último InDesign maquetado de la publicación: se saca de él la maqueta y la " +
                     "configuración de estilos (revisa luego las líneas con ⚠ de su .toml)";
    var bActualizar = gPub.add("button", undefined, "Actualizar publicación…");
    bActualizar.helpTip = "Rehace la maqueta de una publicación desde un número más reciente; antes de guardar " +
                          "enseña qué cambia y dónde se guarda (la configuración no cambia)";
    publicacion.onChange = function () {
        if (!publicacion.selection) return;
        $.global.formatearWordPublicacion = rutaPublicacion();
        try { PREFS.open("w"); PREFS.write(rutaPublicacion()); PREFS.close(); } catch (e) {}
    };
    rellenarPublicaciones();
    publicacion.onChange();

    var gAmb = w.add("group");
    gAmb.add("statictext", undefined, "Trabajar en:");
    var ambito = gAmb.add("dropdownlist", undefined, ["Documento activo", "Todos los capítulos abiertos"]);
    ambito.selection = 0;
    ambito.helpTip = "Para Ortotipografía y Cierre; Importar trabaja siempre con la carpeta que elijas";

    var pImp = w.add("panel", undefined, "1. Galerada");
    pImp.alignChildren = ["fill", "top"];
    var gImp = pImp.add("group");
    var bImportar = gImp.add("button", undefined, "Importar Word…");
    bImportar.helpTip = "Elige el Word del capítulo (o varios, si las tablas o las figuras vienen en otro Word; con Cmd), " +
                        "monta la galerada en la maqueta de la publicación y resalta Tabla, Figura, Algoritmo… («Risk word»). " +
                        "Las figuras se buscan en la carpeta de los Word, que da nombre al capítulo";
    var bMarcas = gImp.add("button", undefined, "Recorrer marcas…");
    bMarcas.helpTip = "Recorre en orden el texto condicional del documento activo (Duda…, Revisar…) " +
                      "con el motivo de cada marca";

    var pOrt = w.add("panel", undefined, "2. Ortotipografía");
    pOrt.alignChildren = ["fill", "top"];
    var gCor = pOrt.add("group");
    var bSimular = gCor.add("button", undefined, "Simular correcciones");
    bSimular.helpTip = "Documento activo: abre «Revisar correcciones» para ver cada corrección (antes y después) y aceptarla u " +
                       "omitirla. Todos los capítulos: cuenta lo que cambiaría cada regla, sin tocar nada";
    var bAplicar = gCor.add("button", undefined, "Aplicar correcciones");
    bAplicar.helpTip = "Aplica las reglas seguras (un Cmd+Z por documento las deshace)";
    var gDud = pOrt.add("group");
    var bDudas = gDud.add("button", undefined, "Buscar dudas");
    bDudas.helpTip = "Marca las dudas («Revisar …») y, si está marcado, pide a Claude una propuesta para cada una";
    var conClaude = gDud.add("checkbox", undefined, "con propuestas de Claude");
    conClaude.value = true;
    var bRevisar = gDud.add("button", undefined, "Revisar dudas…");
    bRevisar.helpTip = "Abre la ventana para recorrer las dudas del documento activo";

    var pCie = w.add("panel", undefined, "3. Cierre (capítulo ya corregido)");
    pCie.alignChildren = ["fill", "top"];
    var gCie = pCie.add("group");
    var bSimCierre = gCie.add("button", undefined, "Simular cierre");
    bSimCierre.helpTip = "Cuenta la puntuación que tomaría el formato de su palabra y las URLs y DOI que pasarían a hipervínculo";
    var bCierre = gCie.add("button", undefined, "Finalizar capítulo");
    bCierre.helpTip = "La puntuación pegada a una palabra toma su formato («(Fusarium)», «Epiescleritis.», «Fusarium/Aspergillus») " +
                      "y las URLs y los DOI pasan a hipervínculos sin cambiar su formato (un Cmd+Z por documento lo deshace)";

    var gEst = w.add("group");
    gEst.alignment = ["fill", "top"];
    var estado = gEst.add("statictext", undefined, "Listo", { truncate: "end" });
    estado.alignment = ["fill", "center"];
    var bDetener = gEst.add("button", undefined, "Detener");
    bDetener.enabled = false;
    var salida = w.add("edittext", [0, 0, 560, 220], "", { multiline: true, readonly: true, scrolling: true });
    salida.alignment = ["fill", "fill"];

    function botones(libres) {
        bImportar.enabled = bNueva.enabled = bActualizar.enabled = bSimular.enabled = bAplicar.enabled = bDudas.enabled =
            bSimCierre.enabled = bCierre.enabled = libres;
        bDetener.enabled = !libres;
    }

    // ---- acciones ----------------------------------------------------------------------------
    // Uno o varios Word (con Cmd): el de texto y, si vienen aparte, los de tablas y figuras.
    bImportar.onClick = function () {
        var inicio = F.ultimaCarpeta && F.ultimaCarpeta.exists ? F.ultimaCarpeta : Folder(RAIZ + "/Documentos Word");
        if (!inicio.exists) inicio = Folder(RAIZ);
        var elegidos = File(inicio.fsName + "/ ").openDlg("Elige el Word del capítulo (varios con Cmd si las tablas o figuras vienen aparte). Las imágenes no hace falta elegirlas: se cogen de la misma carpeta",
            function (f) { return f instanceof Folder || /\.docx?$/i.test(f.name); }, true);
        if (!elegidos) return;
        if (!(elegidos instanceof Array)) elegidos = [elegidos];
        var carpeta = elegidos[0].parent, rutas = [];
        for (var i = 0; i < elegidos.length; i++) {
            if (elegidos[i].parent.fsName != carpeta.fsName) { alert("Los Word de un capítulo tienen que estar en la misma carpeta."); return; }
            if (/^~\$/.test(decodeURI(elegidos[i].name))) continue;      // archivo temporal de Word abierto
            rutas.push(elegidos[i].fsName);
        }
        if (!rutas.length) return;
        F.ultimaCarpeta = carpeta.parent;
        var nombre = decodeURI(carpeta.name), abierto = app.documents.itemByName(nombre + ".indd");
        if (abierto.isValid) { alert("«" + abierto.name + "» está abierto: ciérralo antes de volver a importarlo."); return; }
        lanzar("Importando «" + nombre + "»" + (rutas.length > 1 ? " (" + rutas.length + " Word)" : ""), "importar.py",
               rutas.concat(["--publicacion", rutaPublicacion()]));
    };
    bNueva.onClick = function () {
        var f = File.openDialog("Elige el último InDesign maquetado de la publicación (no se modifica: se trabaja con una copia)",
            function (f) { return f instanceof Folder || /\.indd$/i.test(f.name); }, false);
        if (!f) return;
        var nombre = prompt("Nombre de la publicación:", decodeURI(f.name).replace(/\.indd$/i, "").replace(/\s*N\.?\s*\d+$/i, ""));
        if (!nombre) return;
        F.alTerminar = function () {
            var slug = nombre.toLowerCase().replace(/[\u00e1\u00e0]/g, "a").replace(/[\u00e9\u00e8]/g, "e").replace(/[\u00ed]/g, "i")
                .replace(/[\u00f3]/g, "o").replace(/[\u00fa\u00fc]/g, "u").replace(/\u00f1/g, "n").replace(/[^0-9a-z]+/g, "-").replace(/^-|-$/g, "");
            rellenarPublicaciones(File(RAIZ + "/publicaciones/" + slug + ".toml").fsName);
            publicacion.onChange();
        };
        lanzar("Creando la publicación «" + nombre + "»", "nueva_publicacion.py", [f.fsName, "--nombre", nombre]);
    };
    // Actualizar: se elige la publicación y el maquetado nuevo; nueva_publicacion.py prepara la
    // maqueta aparte y la compara con la actual, y solo se guarda si se acepta lo que implica.
    function datosPublicacion(toml) {
        var t = leer(File(toml)), m = t.match(/^maqueta\s*=\s*"([^"]*)"/m), d = t.match(/^maquetado\s*=\s*"([^"]*)"/m);
        var maqueta = m ? File(RAIZ + "/" + m[1].replace(/\\(.)/g, "$1")) : null;
        return { maqueta: maqueta, maquetado: d ? d[1].replace(/\\(.)/g, "$1") : "",
                 nueva: maqueta ? File(maqueta.fsName.replace(/\.indd$/i, "") + " (nueva).indd") : null,
                 pendiente: maqueta ? File(maqueta.fsName.replace(/\.indd$/i, "") + " (nueva).json") : null };
    }
    function abiertoEnInDesign(f) {
        for (var i = 0; i < app.documents.length; i++)
            try { if (app.documents[i].fullName.fsName == f.fsName) return app.documents[i]; } catch (e) {}
        return null;
    }
    bActualizar.onClick = function () {
        var dlg = new Window("dialog", "Actualizar publicación");
        dlg.alignChildren = ["fill", "top"];
        var g = dlg.add("group");
        g.add("statictext", undefined, "Publicación:");
        var lista = g.add("dropdownlist", undefined, []);
        for (var i = 0; i < F.pubs.length; i++) lista.add("item", F.pubs[i].nombre);
        var info = dlg.add("statictext", undefined, "", { multiline: true });
        info.preferredSize = [560, 70];
        var gb = dlg.add("group");
        gb.alignment = "right";
        gb.add("button", undefined, "Cancelar", { name: "cancel" });
        var bOk = gb.add("button", undefined, "Elegir el InDesign nuevo…", { name: "ok" });
        lista.onChange = function () {
            var d = datosPublicacion(F.pubs[lista.selection.index].ruta);
            info.text = "Maqueta actual: " + (d.maqueta ? d.maqueta.fsName : "(no tiene)") +
                        "\nÚltimo maquetado: " + (d.maquetado || "(no consta)");
            bOk.enabled = !!d.maqueta;
        };
        lista.selection = publicacion.selection.index;
        if (dlg.show() != 1) return;

        var pub = F.pubs[lista.selection.index], d = datosPublicacion(pub.ruta);
        var abierto = abiertoEnInDesign(d.maqueta) || abiertoEnInDesign(d.nueva);
        if (abierto) { alert("«" + abierto.name + "» está abierto: ciérralo antes de actualizar la maqueta."); return; }
        var inicio = d.maquetado ? File(d.maquetado).parent.parent : null;     // la carpeta de los números
        if (!inicio || !inicio.exists) inicio = Folder(RAIZ);
        var f = File(inicio.fsName + "/ ").openDlg("Elige el InDesign maquetado más reciente de «" + pub.nombre +
            "» (no se modifica: se trabaja con una copia)", function (f) { return f instanceof Folder || /\.indd$/i.test(f.name); }, false);
        if (!f) return;
        F.alTerminar = function () { revisarActualizacion(pub, d); };
        lanzar("Preparando la maqueta nueva de «" + pub.nombre + "»", "nueva_publicacion.py", [f.fsName, "--actualizar", pub.ruta]);
    };
    function revisarActualizacion(pub, d) {
        if (!d.pendiente.exists) return;            // ha fallado: el motivo está en la salida
        var p = eval("(" + leer(d.pendiente) + ")");
        var dlg = new Window("dialog", "Actualizar «" + pub.nombre + "»: ¿guardar la maqueta nueva?");
        dlg.alignChildren = ["fill", "top"];
        dlg.add("statictext", undefined, p.avisos ? "Revisa los avisos (⚠) antes de guardar:" : "Esto es lo que cambia:");
        var t = dlg.add("edittext", undefined, p.informe, { multiline: true, readonly: true, scrolling: true });
        t.preferredSize = [720, 380];
        var gb = dlg.add("group");
        gb.alignment = "right";
        gb.add("button", undefined, "Descartar", { name: "cancel" });
        gb.add("button", undefined, "Guardar", { name: "ok" });
        if (dlg.show() == 1)
            lanzar("Guardando la maqueta nueva de «" + pub.nombre + "»", "nueva_publicacion.py", ["--confirmar", pub.ruta]);
        else
            lanzar("Descartando la maqueta nueva de «" + pub.nombre + "»", "nueva_publicacion.py", ["--descartar", pub.ruta]);
    }
    bSimular.onClick = function () {
        var a = argsDocumento();
        if (!a) return;
        if (ambito.selection.index == 0) $.evalFile(File(RAIZ + "/jsx/revisar_correcciones.jsx"));    // una a una
        else lanzar("Simulando correcciones en " + nombreAmbito(), "ortotipografia.py", a.concat(["--maqueta", rutaPublicacion()]));
    };
    bAplicar.onClick = function () {
        var a = argsDocumento();
        if (!a || !confirm("¿Aplicar las correcciones seguras en " + nombreAmbito() + "?\nCada documento se deshace con un Cmd+Z.")) return;
        lanzar("Aplicando correcciones en " + nombreAmbito(), "ortotipografia.py", a.concat(["--aplicar", "--maqueta", rutaPublicacion()]));
    };
    bDudas.onClick = function () {
        var a = argsDocumento();
        if (!a) return;
        if (!confirm("¿Buscar dudas en " + nombreAmbito() + "?\nSe vuelven a marcar todas: lo que no hayas revisado de una pasada anterior vuelve a aparecer.")) return;
        a = a.concat(["--marcar", "--maqueta", rutaPublicacion()]);
        if (conClaude.value) a.push("--claude");
        // Al terminar, si la ventana de revisión está abierta, que relea las dudas.
        F.alTerminar = function () { if ($.global.revisorDudas && $.global.revisorDudas.cargar) $.global.revisorDudas.cargar(); };
        lanzar("Buscando dudas en " + nombreAmbito() + (conClaude.value ? " (con Claude)" : ""), "dudas.py", a);
    };
    bSimCierre.onClick = function () {
        var a = argsDocumento();
        if (a) lanzar("Simulando el cierre de " + nombreAmbito(), "finalizar.py", a.concat(["--publicacion", rutaPublicacion()]));
    };
    bCierre.onClick = function () {
        var a = argsDocumento();
        if (a) lanzar("Finalizando " + nombreAmbito(), "finalizar.py", a.concat(["--aplicar", "--publicacion", rutaPublicacion()]));
    };
    bRevisar.onClick = function () { $.evalFile(File(RAIZ + "/jsx/revisar_dudas.jsx")); };
    bMarcas.onClick = function () { $.evalFile(File(RAIZ + "/jsx/recorrer_marcas.jsx")); };

    bDetener.onClick = detener;

    // Estado y resultado son del documento con el que se lanzó la última acción: al cambiar de
    // documento o volver a abrir la ventana se vacían (salvo con una acción en marcha).
    F.limpiar = function () {
        if (F.proceso) return;
        estado.text = "Listo";
        salida.text = "";
        F.docResultado = null;
    };
    function documentoActivo() { try { return app.documents.length ? app.activeDocument.name : ""; } catch (e) { return ""; } }
    function alCambiarDocumento() { if (F.docResultado !== null && documentoActivo() != F.docResultado) F.limpiar(); }
    F.oyente = app.addEventListener("afterActivate", alCambiarDocumento);
    w.onActivate = alCambiarDocumento;

    w.onResizing = w.onResize = function () { this.layout.resize(); };
    // Para probar desde fuera (#targetengine "formatear_word").
    F.botones = { importar: bImportar, nueva: bNueva, simular: bSimular, aplicar: bAplicar, dudas: bDudas,
                  simCierre: bSimCierre, cierre: bCierre,
                  revisar: bRevisar, marcas: bMarcas, detener: bDetener };
    F.campos = { publicacion: publicacion, ambito: ambito, conClaude: conClaude, estado: estado, salida: salida };
    F.lanzar = lanzar;
    F.comprobar = comprobar;
    F.destruir = function () {
        detener();
        try { F.oyente.remove(); } catch (e) {}
        try { w.close(); } catch (e) {}
        $.global.formatearWord = null;
    };
    w.show();
})();
