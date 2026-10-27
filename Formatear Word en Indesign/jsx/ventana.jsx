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

    var gAmb = w.add("group");
    gAmb.add("statictext", undefined, "Trabajar en:");
    var ambito = gAmb.add("dropdownlist", undefined, ["Documento activo", "Todos los capítulos abiertos"]);
    ambito.selection = 0;
    ambito.helpTip = "Para Ortotipografía y Cierre; Importar trabaja siempre con la carpeta que elijas";

    var pImp = w.add("panel", undefined, "1. Galerada");
    pImp.alignChildren = ["fill", "top"];
    var gImp = pImp.add("group");
    var bImportar = gImp.add("button", undefined, "Importar Word…");
    bImportar.helpTip = "Elige la carpeta del capítulo (con su .docx y sus figuras), monta la galerada en la maqueta base " +
                        "y resalta Tabla, Figura, Algoritmo… («Risk word»)";
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
        bImportar.enabled = bSimular.enabled = bAplicar.enabled = bDudas.enabled =
            bSimCierre.enabled = bCierre.enabled = libres;
        bDetener.enabled = !libres;
    }

    // ---- acciones ----------------------------------------------------------------------------
    bImportar.onClick = function () {
        var inicio = Folder(RAIZ + "/Documentos Word");
        var carpeta = (inicio.exists ? inicio : Folder(RAIZ)).selectDlg("Carpeta del capítulo (con su .docx)");
        if (!carpeta) return;
        var abierto = app.documents.itemByName(decodeURI(carpeta.name) + ".indd");
        if (abierto.isValid) { alert("«" + abierto.name + "» está abierto: ciérralo antes de volver a importarlo."); return; }
        lanzar("Importando «" + decodeURI(carpeta.name) + "»", "importar.py", [carpeta.fsName]);
    };
    bSimular.onClick = function () {
        var a = argsDocumento();
        if (!a) return;
        if (ambito.selection.index == 0) $.evalFile(File(RAIZ + "/jsx/revisar_correcciones.jsx"));    // una a una
        else lanzar("Simulando correcciones en " + nombreAmbito(), "ortotipografia.py", a);
    };
    bAplicar.onClick = function () {
        var a = argsDocumento();
        if (!a || !confirm("¿Aplicar las correcciones seguras en " + nombreAmbito() + "?\nCada documento se deshace con un Cmd+Z.")) return;
        lanzar("Aplicando correcciones en " + nombreAmbito(), "ortotipografia.py", a.concat(["--aplicar"]));
    };
    bDudas.onClick = function () {
        var a = argsDocumento();
        if (!a) return;
        if (!confirm("¿Buscar dudas en " + nombreAmbito() + "?\nSe vuelven a marcar todas: lo que no hayas revisado de una pasada anterior vuelve a aparecer.")) return;
        a = a.concat(["--marcar"]);
        if (conClaude.value) a.push("--claude");
        // Al terminar, si la ventana de revisión está abierta, que relea las dudas.
        F.alTerminar = function () { if ($.global.revisorDudas && $.global.revisorDudas.cargar) $.global.revisorDudas.cargar(); };
        lanzar("Buscando dudas en " + nombreAmbito() + (conClaude.value ? " (con Claude)" : ""), "dudas.py", a);
    };
    bSimCierre.onClick = function () {
        var a = argsDocumento();
        if (a) lanzar("Simulando el cierre de " + nombreAmbito(), "finalizar.py", a);
    };
    bCierre.onClick = function () {
        var a = argsDocumento();
        if (a) lanzar("Finalizando " + nombreAmbito(), "finalizar.py", a.concat(["--aplicar"]));
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
    F.botones = { importar: bImportar, simular: bSimular, aplicar: bAplicar, dudas: bDudas,
                  simCierre: bSimCierre, cierre: bCierre,
                  revisar: bRevisar, marcas: bMarcas, detener: bDetener };
    F.campos = { ambito: ambito, conClaude: conClaude, estado: estado, salida: salida };
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
