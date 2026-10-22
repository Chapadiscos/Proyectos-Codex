// Prepara un capítulo de InDesign (el de imprenta) para exportarlo a HTML (heredado).
// Uso (AppleScript): do script (POSIX file ".../preparar_html.jsx") language javascript
//                    with arguments {"/ruta/a/la/copia.indd", "/ruta/a/la/config.json", "5"}
// Trabaja SOBRE LA COPIA que le pasa ./preparar (el original no se abre) y la guarda.
// Devuelve "ok" o "error|<mensaje>", seguido de una línea por cambio: "OK|…", "AVISO|…".
// Con {"/ruta/al/original.indd", "capitulos"} solo lista sus capítulos (secciones de
// InDesign con marcador numérico): una línea "número|páginas" por capítulo.
//
// Pasos (las reglas de cada libro están en la sección "preparar" de config/libros/<libro>.yaml):
//  0. Si es un archivo de sección (varios capítulos), deja solo las páginas del capítulo.
//  1. Desbloquea, y borra lo que hay en la mesa de trabajo.
//  2. Convierte en JPG (como Exportar > JPEG de la selección) los bloques que en HTML
//     no se verían como en el libro: cabecera, tablas, cuadros (algoritmo, ideas básicas)
//     y figuras compuestas (varias imágenes con letras). Los coloca en su lugar.
//  3. Vacía las páginas maestras (cornisas y folios).
//  4. Texto: variables y marcadores a texto; quita guiones discrecionales, retornos
//     forzados (une «especia-⏎lizado») y saltos de columna, marco o página.
//  5. Ancla cada figura y tabla en un párrafo propio tras el párrafo que la cita
//     (si no se cita, tras el párrafo que tiene encima); la cabecera, al principio;
//     los cuadros, al final (antes de la bibliografía).
//  6. Fija los ajustes de exportación HTML y borra estilos y muestras sin uso.
// El texto alternativo no se toca: el depurador ya pone alt="" a todas las imágenes.

var INFORME = [];
function ok(s) { INFORME.push("OK|" + s); }
function aviso(s) { INFORME.push("AVISO|" + s); }

var ESP = "[\\s\\u00A0\\u2000-\\u200A\\u202F]";  // espacios, también los de InDesign

function leerJSON(ruta) {
    var f = File(ruta);
    f.encoding = "UTF-8";
    f.open("r");
    var t = f.read();
    f.close();
    return eval("(" + t + ")");  // ExtendScript no tiene JSON; el archivo lo escribe ./preparar
}

function enLista(valor, lista) {
    for (var i = 0; lista && i < lista.length; i++) if (lista[i] == valor) return true;
    return false;
}

function plantilla(p, cap, n) { return p.replace("{cap}", cap).replace("{n}", n); }

function tipo(it) { return it.constructor.name; }

function union(items) {
    var b = null;
    for (var i = 0; i < items.length; i++) {
        var g = items[i].visibleBounds;
        if (!b) b = [g[0], g[1], g[2], g[3]];
        else b = [Math.min(b[0], g[0]), Math.min(b[1], g[1]), Math.max(b[2], g[2]), Math.max(b[3], g[3])];
    }
    return b;
}

function distancia(a, b) {  // separación entre dos rectángulos (0 si se tocan)
    var dy = Math.max(0, Math.max(a[0], b[0]) - Math.min(a[2], b[2]));
    var dx = Math.max(0, Math.max(a[1], b[1]) - Math.min(a[3], b[3]));
    return Math.sqrt(dx * dx + dy * dy);
}

function marcosDeTexto(it) {
    if (tipo(it) == "TextFrame") return [it];
    var r = [], todos = it.allPageItems;
    for (var i = 0; i < todos.length; i++) if (tipo(todos[i]) == "TextFrame") r.push(todos[i]);
    return r;
}

function estilosDe(it) {  // nombres de los estilos de párrafo del texto del objeto
    var r = {}, marcos = marcosDeTexto(it);
    for (var i = 0; i < marcos.length; i++) {
        var pars = marcos[i].parentStory.paragraphs;
        if (!pars.length) continue;
        var ps = pars.everyItem().appliedParagraphStyle;
        for (var k = 0; k < ps.length; k++) r[ps[k].name] = true;
    }
    return r;
}

function tieneEstilo(estilos, lista) {
    for (var i = 0; lista && i < lista.length; i++) if (estilos[lista[i]]) return true;
    return false;
}

function estiloParrafo(doc, nombre) {
    var e = doc.allParagraphStyles;
    for (var i = 0; i < e.length; i++) if (e[i].name == nombre) return e[i];
    return doc.paragraphStyles[1];  // [Párrafo básico]
}

function describir(it) {
    var g = it.visibleBounds, pag = it.parentPage ? it.parentPage.name : "-";
    var txt = tipo(it) == "TextFrame" ? " «" + it.contents.substr(0, 30).replace(/[\r\n]/g, " ") + "»" : "";
    return tipo(it) + " pág. " + pag + " [" + Math.round(g[0]) + "," + Math.round(g[1]) + "]" + txt;
}

// ---------------------------------------------------------------------------
// JPG de un objeto, con los mismos ajustes en todos (Exportar > JPEG, selección)
function exportarJPG(it, carpeta, nombre, cfg) {
    var p = app.jpegExportPreferences, antes = {};
    var ajustes = {
        exportResolution: cfg.resolucion || 150,
        jpegQuality: JPEGOptionsQuality.MAXIMUM,
        jpegRenderingStyle: JPEGOptionsFormat.BASELINE_ENCODING,
        jpegColorSpace: JpegColorSpaceEnum.RGB,
        embedColorProfile: true,
        antiAlias: true,
        useDocumentBleeds: false,
        simulateOverprint: false
    };
    for (var k in ajustes) { antes[k] = p[k]; p[k] = ajustes[k]; }
    var f = File(carpeta + "/" + nombre + ".jpg");
    try { it.exportFile(ExportFormat.JPG, f); }
    finally { for (var k in antes) p[k] = antes[k]; }
    return f;
}

// Marco para un JPG generado: sin estilo de objeto ni contorno. Si no, toma el estilo
// por defecto del documento («Marco 80» en Ponencias 2025, con filete) y la exportación
// HTML con «Conservar aspecto» lo incrusta en la imagen
function marcoLimpio(doc, marco, f) {
    marco.appliedObjectStyle = doc.objectStyles[0];  // [Ninguno]
    marco.clearObjectStyleOverrides();
    marco.strokeWeight = 0;
    marco.strokeColor = doc.swatches[0];  // [Ninguno]
    marco.fillColor = doc.swatches[0];
    marco.place(f);
    marco.fit(FitOptions.FRAME_TO_CONTENT);
    return marco;
}

// Sustituye los objetos por un marco con su JPG en el mismo sitio y los borra
function rasterizar(doc, items, carpeta, nombre, cfg) {
    var spread = items[0].parent;
    while (tipo(spread) != "Spread" && tipo(spread) != "MasterSpread") spread = spread.parent;
    var obj = items.length == 1 ? items[0] : doc.groups.add(items);
    var vb = obj.visibleBounds;
    var f = exportarJPG(obj, carpeta, nombre, cfg);
    obj.remove();
    return marcoLimpio(doc, spread.rectangles.add({ geometricBounds: vb }), f);
}

// ---------------------------------------------------------------------------
// Capítulos del documento: secciones de InDesign cuyo marcador es un número
function capitulos(doc) {
    var r = [];
    for (var i = 0; i < doc.sections.length; i++) {
        var s = doc.sections[i];
        if (/^\d+$/.test(s.marker)) r.push({ n: parseInt(s.marker, 10), inicio: s.pageStart.documentOffset, paginas: s.length });
    }
    r.sort(function (a, b) { return a.inicio - b.inicio; });
    return r;
}

function quedarseConCapitulo(doc, cap) {
    var caps = capitulos(doc);
    if (caps.length < 2) return;
    var elegido = null;
    for (var i = 0; i < caps.length; i++) if (caps[i].n == cap) elegido = caps[i];
    if (!elegido) throw Error("El capítulo " + cap + " no está en este archivo de sección");
    var desde = elegido.inicio, hasta = elegido.inicio + elegido.paginas - 1;
    for (var p = doc.pages.length - 1; p >= 0; p--) if (p < desde || p > hasta) doc.pages[p].remove();
    ok("Archivo de sección: solo el capítulo " + cap + " (" + elegido.paginas + " páginas)");
}

function principal(doc, cfg, cap, carpeta) {
    quedarseConCapitulo(doc, cap);

    var cfgFig = cfg.figuras || {}, cfgTab = cfg.tablas || {}, cfgCab = cfg.cabecera || {};
    var cuadros = cfg.cuadros || [], limpiar = cfg.limpiar || {};
    var reTituloFig = new RegExp(cfgFig.titulo || "^Figura" + ESP + "+(\\d+)");
    // Tipos de figura: las figuras y los que añada el libro (otras_figuras: vídeos…), cada
    // uno con su pie, su numeración y su nombre de JPG
    var tiposFig = [{ clave: "figura", etiqueta: "Figura", re: reTituloFig, nombre: cfgFig.compuesta || "F{cap}.{n}", siempre: false }];
    var otras = cfg.otras_figuras || [];
    for (var i = 0; i < otras.length; i++) {
        tiposFig.push({ clave: otras[i].clave, etiqueta: otras[i].etiqueta, re: new RegExp(otras[i].titulo),
            nombre: otras[i].nombre, siempre: otras[i].siempre_jpg });
    }
    var reTituloTab = new RegExp(cfgTab.titulo || "Tabla" + ESP + "+(\\d+)");
    var reTituloTabPie = new RegExp("^(?:" + reTituloTab.source + ")");

    // 1. Desbloquear; mesa de trabajo fuera
    doc.layers.everyItem().locked = false;
    if (doc.pageItems.length) doc.pageItems.everyItem().locked = false;
    var historia = null;
    for (var i = 0; i < doc.stories.length; i++) {
        var st = doc.stories[i];
        if (st.textContainers.length && (!historia || st.characters.length > historia.characters.length)) historia = st;
    }
    historia = doc.stories.itemByID(historia.id);  // por id: los índices cambian al borrar historias
    if (limpiar.mesa_de_trabajo !== false) {
        var n = 0;
        for (var s = 0; s < doc.spreads.length; s++) {
            var its = doc.spreads[s].pageItems.everyItem().getElements();
            for (var k = 0; k < its.length; k++) if (!its[k].parentPage) { its[k].remove(); n++; }
        }
        if (n) ok("Mesa de trabajo: " + n + " objetos borrados");
    }

    // Objetos de maestra sobrescritos en las páginas (cornisas, folios): fuera
    if (limpiar.maestras !== false) {
        var n = 0, todos = doc.pages.everyItem().pageItems.everyItem().getElements();
        for (var k = 0; k < todos.length; k++) if (todos[k].overriddenMasterPageItem) { todos[k].remove(); n++; }
        if (n) ok("Objetos de maestra sobrescritos en las páginas: " + n + " borrados");
    }

    // Objetos ya anclados en la historia principal:
    //  - bloques (tabla, cuadro configurado, figura con pie): se sueltan para tratarlos
    //    igual que los sueltos;
    //  - otros marcos de texto (recuadros dentro del texto): JPG en el mismo sitio;
    //  - los pequeños (iconos) se quedan.
    var cfgCT = cfg.cuadros_en_texto || {}, minimo = cfgCT.minimo_mm || 15;
    app.findGrepPreferences = NothingEnum.nothing;
    app.findGrepPreferences.findWhat = "~a";
    var anclas = historia.findGrep(true);  // del final al principio
    app.findGrepPreferences = NothingEnum.nothing;
    var acciones = [], nTexto = 0;
    for (var a = 0; a < anclas.length; a++) {
        var ch = anclas[a];
        if (!ch.pageItems.length) continue;
        var it = ch.pageItems[0].getElements()[0], est = estilosDe(it), vb = it.visibleBounds;
        var esBloque = (tipo(it) == "TextFrame" && it.parentStory.tables.length) ||
            tieneEstilo(est, cfgFig.estilos_pie);
        for (var c = 0; c < cuadros.length; c++) if (tieneEstilo(est, cuadros[c].estilos)) esBloque = true;
        if (esBloque) acciones.push({ ch: ch, it: it, soltar: true });
        else if (cfgCT.activa !== false && tipo(it) == "TextFrame" && vb[2] - vb[0] >= minimo && vb[3] - vb[1] >= minimo) {
            acciones.push({ ch: ch, it: it, soltar: false });
            nTexto++;
        }
    }
    for (var a = 0; a < acciones.length; a++) {
        var it = acciones[a].it, idx = acciones[a].ch.index;
        if (acciones[a].soltar) {
            ok("Soltado para colocarlo de nuevo: " + describir(it));
            // Solo se pueden soltar los de posición personalizada (los «en línea» no)
            it.anchoredObjectSettings.anchoredPosition = AnchorPosition.ANCHORED;
            it.anchoredObjectSettings.releaseAnchoredObject();
            var par = historia.characters[Math.min(idx, historia.characters.length - 1)].paragraphs[0];
            if (par.contents == "\r" || par.contents == "") par.remove();
        } else {
            var nombre = plantilla(cfgCT.nombre || "CUADRO {cap}.{n}", cap, nTexto--);
            var vb = it.visibleBounds, f = exportarJPG(it, carpeta, nombre, cfg.jpeg || {});
            var resumen = it.parentStory.contents.substr(0, 40).replace(/[\r\n]/g, " ");
            it.remove();
            var marco = marcoLimpio(doc, historia.insertionPoints[idx].rectangles.add({
                geometricBounds: [0, 0, vb[2] - vb[0], vb[3] - vb[1]] }), f);
            marco.anchoredObjectSettings.anchoredPosition = AnchorPosition.ANCHORED;
            // En un párrafo propio y sin ajustes locales: si no, la exportación HTML lo
            // mete en la viñeta de encima (cap. 04)
            if (idx + 1 < historia.characters.length && historia.characters[idx + 1].contents != "\r") historia.insertionPoints[idx + 1].contents = "\r";
            if (idx > 0 && historia.characters[idx - 1].contents != "\r") { historia.insertionPoints[idx].contents = "\r"; idx++; }
            historia.characters[idx].paragraphs[0].applyParagraphStyle(estiloParrafo(doc, cfg.estilo_parrafo_ancla || "Texto base"), true);
            ok("Cuadro en el texto → " + nombre + ".jpg, en su sitio («" + resumen + "…»)");
        }
    }

    // 2. Clasificar los objetos sueltos de las páginas
    var colocar = [];   // {obj, clase: cabecera|figura|tabla|cuadro, n, orden, pagina, arriba}
    var usados = {};
    function libre(it) { return it.isValid && !usados[it.id]; }
    var sueltos = [];
    for (var p = 0; p < doc.pages.length; p++) {
        var its = doc.pages[p].pageItems.everyItem().getElements();
        for (var k = 0; k < its.length; k++) {
            var it = its[k];
            if (tipo(it) == "TextFrame" && it.parentStory.id == historia.id) continue;
            sueltos.push(it);
        }
    }
    function anotar(obj, clase, n, orden, etiqueta) {
        var pg = obj.parentPage;
        colocar.push({ obj: obj, clase: clase, n: n, orden: orden, etiqueta: etiqueta,
            pagina: pg ? pg.documentOffset : 0, arriba: obj.visibleBounds[0] });
    }

    // Cabecera: lo que hay en la primera página por encima del texto principal
    if (cfgCab.activa !== false) {
        var pag1 = doc.pages[0], arribaTexto = 1e9;
        for (var i = 0; i < historia.textContainers.length; i++) {
            var m = historia.textContainers[i];
            if (m.parentPage && m.parentPage.id == pag1.id) arribaTexto = Math.min(arribaTexto, m.geometricBounds[0]);
        }
        var cab = [];
        for (var i = 0; i < sueltos.length; i++) {
            var it = sueltos[i];
            if (it.parentPage && it.parentPage.id == pag1.id && it.visibleBounds[2] <= arribaTexto + 1) { cab.push(it); usados[it.id] = true; }
        }
        if (cab.length) {
            var nombre = plantilla(cfgCab.nombre || "C{cap}", cap, "");
            var marco = rasterizar(doc, cab, carpeta, nombre, cfg.jpeg || {});
            colocar.push({ obj: marco, clase: "cabecera", n: 0, orden: 0, pagina: 0, arriba: 0 });
            ok("Cabecera → " + nombre + ".jpg (" + cab.length + " objetos)");
        } else aviso("No se ha encontrado la cabecera en la primera página");
    }

    // Pies de figura y de cuadro (sueltos o dentro de un grupo)
    function esPie(tf) {
        if (tipo(tf) != "TextFrame" || tf.parentStory.id == historia.id) return false;
        return tieneEstilo(estilosDe(tf), cfgFig.estilos_pie);
    }
    function textoDe(tf) { return tf.parentStory.contents.replace(/^\uFEFF/, ""); }
    function tipoDePie(tf) {  // {t: tipo de figura, n: número} o null
        if (!esPie(tf)) return null;
        for (var i = 0; i < tiposFig.length; i++) {
            var m = tiposFig[i].re.exec(textoDe(tf));
            if (m) return { t: tiposFig[i], n: parseInt(m[1], 10) };
        }
        return null;
    }

    // Tablas
    var nSinTitulo = 0;
    for (var i = 0; i < sueltos.length; i++) {
        var it = sueltos[i];
        if (!libre(it) || tipo(it) != "TextFrame" || !it.parentStory.tables.length) continue;
        usados[it.id] = true;
        if (cfgTab.activa === false) continue;
        // «Tabla N» al principio del marco o en la primera celda (el texto de las celdas
        // no está en el de la historia: allí la tabla es un solo carácter)
        var mt = reTituloTabPie.exec(textoDe(it).replace(/^[\s\u0016]+/, "")) ||
            reTituloTabPie.exec(String(it.parentStory.tables[0].cells[0].contents));
        if (mt) {
            var n = parseInt(mt[1], 10), nombre = plantilla(cfgTab.nombre || "T{cap}.{n}", cap, n);
            anotar(rasterizar(doc, [it], carpeta, nombre, cfg.jpeg || {}), "tabla", n, 0);
            ok("Tabla " + n + " → " + nombre + ".jpg");
        } else {  // sin «Tabla N»: no se cita, va tras el párrafo que tiene encima
            var nombre = plantilla(cfgTab.sin_titulo || "TABLA {cap}.{n}", cap, ++nSinTitulo);
            anotar(rasterizar(doc, [it], carpeta, nombre, cfg.jpeg || {}), "sin_titulo", 0, 0);
            ok("Tabla sin título → " + nombre + ".jpg");
        }
    }

    // Figuras (y vídeos…): grupos con pie y pares imagen + pie sueltos. Lo que no es una
    // sola imagen (varias, letras o rótulos encima, QR con formas) pasa a un solo JPG
    function esSimple(objs) { return objs.length == 1 && tipo(objs[0]) != "Group" && objs[0].allGraphics.length == 1; }
    for (var i = 0; i < sueltos.length; i++) {
        var it = sueltos[i];
        if (!libre(it) || tipo(it) != "Group") continue;
        var hijos = it.pageItems.everyItem().getElements(), pie = null, tp = null, resto = [];
        for (var k = 0; k < hijos.length; k++) {
            var t = pie ? null : tipoDePie(hijos[k]);
            if (t) { pie = hijos[k]; tp = t; }
            else resto.push(hijos[k]);
        }
        if (!pie) continue;
        usados[it.id] = true;
        if (esSimple(resto) && !tp.t.siempre) { anotar(it, tp.t.clave, tp.n, 0, tp.t.etiqueta); continue; }
        it.ungroup();
        var nombre = plantilla(tp.t.nombre, cap, tp.n);
        var marco = rasterizar(doc, resto, carpeta, nombre, cfg.jpeg || {});
        anotar(doc.groups.add([marco, pie]), tp.t.clave, tp.n, 0, tp.t.etiqueta);
        ok(tp.t.etiqueta + " " + tp.n + " (" + resto.length + " objetos) → " + nombre + ".jpg");
    }
    var piesSueltos = [], imagenes = [];
    for (var i = 0; i < sueltos.length; i++) {
        var it = sueltos[i];
        if (!libre(it)) continue;
        if (tipoDePie(it)) piesSueltos.push(it);
        else if (tipo(it) != "TextFrame" && it.allGraphics.length) imagenes.push(it);
    }
    for (var i = 0; i < piesSueltos.length; i++) {
        var pie = piesSueltos[i], tp = tipoDePie(pie), mejor = null, dmin = 1e9;
        for (var k = 0; k < imagenes.length; k++) {
            var im = imagenes[k];
            if (!libre(im) || !im.parentPage || !pie.parentPage || im.parentPage.id != pie.parentPage.id) continue;
            var d = distancia(im.visibleBounds, pie.visibleBounds);
            if (d < dmin) { dmin = d; mejor = im; }
        }
        usados[pie.id] = true;
        if (!mejor || dmin > 10) { aviso(tp.t.etiqueta + " " + tp.n + ": no encuentro su imagen junto al pie (" + describir(pie) + ")"); continue; }
        usados[mejor.id] = true;
        if (esSimple([mejor]) && !tp.t.siempre) {
            anotar(doc.groups.add([mejor, pie]), tp.t.clave, tp.n, 0, tp.t.etiqueta);
            ok(tp.t.etiqueta + " " + tp.n + ": imagen y pie sueltos agrupados");
        } else {
            var nombre = plantilla(tp.t.nombre, cap, tp.n);
            var marco = rasterizar(doc, [mejor], carpeta, nombre, cfg.jpeg || {});
            anotar(doc.groups.add([marco, pie]), tp.t.clave, tp.n, 0, tp.t.etiqueta);
            ok(tp.t.etiqueta + " " + tp.n + ": con su pie suelto → " + nombre + ".jpg");
        }
    }
    var nSinPie = 0;
    for (var k = 0; k < imagenes.length; k++) {
        var im = imagenes[k];
        if (!libre(im)) continue;
        usados[im.id] = true;
        if (!esSimple([im])) {  // grupo sin pie: a JPG igualmente, para que se vea como en el libro
            var nombre = plantilla(cfg.imagen_sin_pie || "IMAGEN {cap}.{n}", cap, ++nSinPie);
            im = rasterizar(doc, [im], carpeta, nombre, cfg.jpeg || {});
            aviso("Grupo sin pie → " + nombre + ".jpg: se ancla donde está, revísalo");
        } else aviso("Imagen sin pie: " + describir(im) + " — se ancla donde está, revísala");
        anotar(im, "imagen", 0, 0);
    }
    // Cuadros (algoritmo, ideas básicas…): el texto con sus estilos más las líneas y
    // formas sueltas que lo rodean
    for (var c = 0; c < cuadros.length; c++) {
        var cd = cuadros[c], semillas = [];
        for (var i = 0; i < sueltos.length; i++) {
            var it = sueltos[i];
            if (!libre(it) || esPie(it)) continue;
            if (tieneEstilo(estilosDe(it), cd.estilos)) semillas.push(it);
        }
        if (!semillas.length) continue;
        var pagina = semillas[0].parentPage, piezas = [], b = union(semillas);  // b: zona del cuadro
        for (var i = 0; i < semillas.length; i++) { piezas.push(semillas[i]); usados[semillas[i].id] = true; }
        var crece = true;
        while (crece) {  // añade lo que toca la zona hasta que no crece más
            crece = false;
            for (var i = 0; i < sueltos.length; i++) {
                var it = sueltos[i];
                if (!libre(it) || !it.parentPage || it.parentPage.id != pagina.id || esPie(it) || it.allGraphics.length) continue;
                if (tipo(it) == "TextFrame" && it.parentStory.contents.length > 0 && !tieneEstilo(estilosDe(it), cd.estilos)) continue;
                if (distancia(it.visibleBounds, b) <= 3) {
                    piezas.push(it); usados[it.id] = true; b = union(piezas); crece = true;
                }
            }
        }
        // Su pie, pegado a él, va con la imagen y dice qué es: «Tabla 3. …» es la tabla 3
        // (se ancla donde se cita); «Algoritmo. …» u otro, un cuadro (va al final)
        var pie = null;
        for (var i = 0; i < sueltos.length; i++) {
            var it = sueltos[i];
            if (libre(it) && esPie(it) && it.parentPage && it.parentPage.id == pagina.id && distancia(it.visibleBounds, b) <= 5) { pie = it; break; }
        }
        var clase = "cuadro", n = 0, nombre = plantilla(cd.nombre, cap, ""), que = "Cuadro «" + cd.estilos[0] + "»";
        var mt = pie ? reTituloTabPie.exec(textoDe(pie)) : null, mf = pie ? tipoDePie(pie) : null;
        if (mt) { clase = "tabla"; n = parseInt(mt[1], 10); nombre = plantilla(cfgTab.nombre || "T{cap}.{n}", cap, n); que = "Tabla " + n + " (" + cd.estilos[0] + ")"; }
        else if (mf) { clase = mf.t.clave; n = mf.n; nombre = plantilla(mf.t.nombre, cap, n); que = mf.t.etiqueta + " " + n + " (" + cd.estilos[0] + ")"; }
        var obj = rasterizar(doc, piezas, carpeta, nombre, cfg.jpeg || {});
        if (pie) { usados[pie.id] = true; obj = doc.groups.add([obj, pie]); }
        anotar(obj, clase, n, c, mf ? mf.t.etiqueta : clase == "tabla" ? "Tabla" : "");
        ok(que + " → " + nombre + ".jpg (" + piezas.length + " objetos" + (pie ? " con su pie" : "") + ")");
    }

    for (var i = 0; i < sueltos.length; i++) {
        if (libre(sueltos[i])) aviso("Objeto sin clasificar, se deja donde está: " + describir(sueltos[i]));
    }

    // 3. Páginas maestras vacías
    if (limpiar.maestras !== false) {
        var n = 0;
        for (var m = 0; m < doc.masterSpreads.length; m++) {
            var its = doc.masterSpreads[m].pageItems;
            n += its.length;
            if (its.length) its.everyItem().remove();
        }
        if (n) ok("Páginas maestras: " + n + " objetos borrados (cornisas y folios)");
    }

    // 4. Texto
    limpiarTexto(doc, historia, limpiar);

    // 5. Anclar
    anclar(doc, historia, colocar, cfg);

    // Ajustes de Archivo > Exportar > HTML (heredado) que se guardan en el documento
    var h = cfg.html_export || {}, cambios = [];
    for (var k in h) {
        var v = h[k];
        if (typeof v == "string" && /^[A-Za-z]+\.[A-Z_]+$/.test(v)) v = eval(v);  // «ImageConversion.JPEG»
        doc.htmlExportPreferences[k] = v;
        cambios.push(k + "=" + h[k]);
    }
    if (cambios.length) ok("Ajustes de exportación HTML: " + cambios.join(", "));

    // 6. Estilos y muestras sin uso
    if (limpiar.estilos_sin_uso !== false) limpiarEstilos(doc);
    if (limpiar.muestras_sin_uso !== false) {
        var n = 0, sin = doc.unusedSwatches;
        for (var i = sin.length - 1; i >= 0; i--) {
            try { if (sin[i].name != "") { sin[i].remove(); n++; } } catch (e) {}
        }
        if (n) ok("Muestras sin uso: " + n + " borradas");
    }
}

// ---------------------------------------------------------------------------
function cambiarGrep(doc, buscar, cambiar) {
    app.findGrepPreferences = NothingEnum.nothing;
    app.changeGrepPreferences = NothingEnum.nothing;
    app.findGrepPreferences.findWhat = buscar;
    app.changeGrepPreferences.changeTo = cambiar;
    var r = doc.changeGrep();
    app.findGrepPreferences = NothingEnum.nothing;
    app.changeGrepPreferences = NothingEnum.nothing;
    return r.length;
}

function limpiarTexto(doc, historia, limpiar) {
    if (limpiar.variables !== false) {
        var n = 0;
        for (var s = 0; s < doc.stories.length; s++) {
            var v = doc.stories[s].textVariableInstances;
            n += v.length;
            if (v.length) v.everyItem().convertToText();
        }
        if (n) ok("Variables de texto convertidas a texto: " + n);
        // Marcadores de sección y números de página (en el GREP de InDesign «~x|~#» no
        // funciona: cada uno por separado)
        var marcas = ["~x", "~#", "~N", "~X"], n = 0;
        for (var k = 0; k < marcas.length; k++) {
            app.findGrepPreferences = NothingEnum.nothing;
            app.findGrepPreferences.findWhat = marcas[k];
            var r = doc.findGrep(true);
            app.findGrepPreferences = NothingEnum.nothing;
            for (var i = 0; i < r.length; i++) {
                var m = r[i], marco = m.parentTextFrames[0], pg = marco ? marco.parentPage : null;
                m.contents = !pg ? "" : marcas[k] == "~x" ? pg.appliedSection.marker : pg.name;
                n++;
            }
        }
        if (n) ok("Marcadores de sección y número de página a texto: " + n);
    }
    if (limpiar.guiones_discrecionales !== false) {
        var n = cambiarGrep(doc, "~-", "");
        if (n) ok("Guiones discrecionales quitados: " + n);
    }
    if (limpiar.retornos_forzados !== false) {
        // Palabra partida a mano («especia-⏎lizado»): se une sin guion
        app.findGrepPreferences = NothingEnum.nothing;
        app.findGrepPreferences.findWhat = "[[:alpha:]]+-\\n[[:lower:]]+";
        var r = doc.findGrep();
        for (var i = 0; i < r.length; i++) ok("Palabra partida unida: «" + r[i].contents.replace("\n", "⏎") + "» → «" + r[i].contents.replace("-\n", "") + "»");
        cambiarGrep(doc, "([[:alpha:]])-\\n([[:lower:]])", "$1$2");
        var n = cambiarGrep(doc, " *\\n *", " ");
        if (n) ok("Retornos forzados cambiados por espacio: " + n);
    }
    if (limpiar.saltos !== false) {
        // Salto de columna, marco o página: hacen de fin de párrafo
        var saltos = ["~M", "~R", "~P", "~L", "~E"], n = 0;  // «|» tampoco funciona con estos
        for (var k = 0; k < saltos.length; k++) n += cambiarGrep(doc, saltos[k] + "\\r?", "\\r");
        if (n) ok("Saltos de columna, marco o página cambiados por fin de párrafo: " + n);
    }
}

// ---------------------------------------------------------------------------
// Dónde se cita cada figura y tabla en la historia principal
function citas(textos, estilos, clave, ignorar) {
    var r = {};  // número -> {par, pos}
    var re = new RegExp("\\b(?:" + clave + ")\\.?" + ESP + "*(\\d[^).;:]{0,30})", "g");
    for (var i = 0; i < textos.length; i++) {
        if (enLista(estilos[i], ignorar)) continue;
        var m;
        re.lastIndex = 0;
        while ((m = re.exec(textos[i])) !== null) {
            var nums = m[1].match(/\d+/g), seps = m[1].split(/\d+/);
            for (var k = 0; k < nums.length; k++) {
                var n = parseInt(nums[k], 10);
                if (!r[n]) r[n] = { par: i, pos: m.index };
                // «3-5» o «3 a 5»: también 4
                if (k > 0 && /^\s*(-|–|a)\s*$/.test(seps[k])) {
                    for (var x = parseInt(nums[k - 1], 10) + 1; x < n; x++) if (!r[x]) r[x] = { par: i, pos: m.index };
                }
            }
        }
    }
    return r;
}

function anclar(doc, historia, colocar, cfg) {
    var pars = historia.paragraphs;
    var textos = pars.everyItem().contents, estilos = [];
    var ps = pars.everyItem().appliedParagraphStyle;
    for (var i = 0; i < ps.length; i++) estilos.push(ps[i].name);
    var cfgFig = cfg.figuras || {}, cfgTab = cfg.tablas || {};
    var citasPor = { figura: citas(textos, estilos, cfgFig.cita || "Figuras?", cfg.ignorar_citas_en) };
    var otras = cfg.otras_figuras || [];
    for (var i = 0; i < otras.length; i++) citasPor[otras[i].clave] = citas(textos, estilos, otras[i].cita, cfg.ignorar_citas_en);
    var citasTab = citas(textos, estilos, cfgTab.cita || "Tablas?", cfg.ignorar_citas_en);

    // Final: antes del primer párrafo que coincide con final_antes_de (la bibliografía)
    var fin = textos.length - 1, fa = cfg.final_antes_de;
    if (fa) {
        var reE = new RegExp(fa.estilo || "."), reT = new RegExp(fa.texto || ".");
        for (var i = 0; i < textos.length; i++) if (reE.test(estilos[i]) && reT.test(textos[i])) { fin = i - 1; break; }
    }

    // Por posición: el último párrafo que empieza por encima del objeto en su página
    var posiciones = null;
    function porPosicion(c) {
        if (!posiciones) {
            posiciones = [];
            var todos = pars.everyItem().getElements();
            for (var i = 0; i < todos.length; i++) {
                var ip = todos[i].insertionPoints[0], m = ip.parentTextFrames[0];
                posiciones.push(m && m.parentPage ? { pag: m.parentPage.documentOffset, y: ip.baseline } : null);
            }
        }
        var mejor = 0;
        for (var i = 0; i < posiciones.length; i++) {
            var p = posiciones[i];
            if (!p) continue;
            if (p.pag < c.pagina || (p.pag == c.pagina && p.y <= c.arriba)) mejor = i;
        }
        return mejor;
    }

    for (var i = 0; i < colocar.length; i++) {
        var c = colocar[i], cita = null;
        if (c.clase == "cabecera") { c.par = -1; continue; }
        if (c.clase == "cuadro") { c.par = fin; continue; }
        if (citasPor[c.clase]) cita = citasPor[c.clase][c.n];
        if (c.clase == "tabla") cita = citasTab[c.n];
        if (cita) { c.par = cita.par; c.orden = cita.pos; c.citado = true; }
        else {
            c.par = porPosicion(c);
            var que = c.clase == "tabla" ? "Tabla " + c.n : c.clase == "sin_titulo" ? "Tabla sin título" : (c.etiqueta || "Figura") + " " + c.n;
            if (c.clase != "imagen") aviso(que + ": no se cita en el texto; anclada tras el párrafo que tiene encima («" + textos[c.par].substr(0, 40) + "…»): revísalo");
        }
    }

    // Figuras y tablas citadas en una lista (viñetas seguidas con su texto de continuación):
    //  - si es la única de la lista, va al final de la lista (preferencia del usuario);
    //  - si hay varias, cada una tras su viñeta y las subviñetas de esta (no separa el
    //    punto de sus hijas; cap. 04, figura 1).
    var np = cfg.no_partir_vinetas;
    if (np) {
        var reNivel = new RegExp(np.nivel || "Viñeta (\\d+)");
        var nivel = function (i) { var m = reNivel.exec(estilos[i]); return m ? parseInt(m[1], 10) : 0; };
        // Los párrafos que solo llevan objetos anclados (un recuadro dentro de la lista) no la cortan
        var deLista = function (i) { return i >= 0 && i < textos.length && (nivel(i) > 0 || enLista(estilos[i], np.continuacion) || /^[\uFFFC\s]*$/.test(textos[i])); };
        var enLaLista = {};  // primer párrafo de la lista -> objetos citados en ella
        for (var i = 0; i < colocar.length; i++) {
            var c = colocar[i];
            if (!c.citado || !deLista(c.par)) continue;
            var ini = c.par, fin = c.par;
            while (deLista(ini - 1)) ini--;
            while (deLista(fin + 1)) fin++;
            c.lista = { ini: ini, fin: fin };
            enLaLista[ini] = (enLaLista[ini] || 0) + 1;
        }
        for (var i = 0; i < colocar.length; i++) {
            var c = colocar[i], j = c.par;
            if (!c.lista) continue;
            if (np.final_si_unica !== false && enLaLista[c.lista.ini] == 1) j = c.lista.fin;
            else {
                var base = nivel(c.par);
                for (var k = c.par; !base && k >= 0 && enLista(estilos[k], np.continuacion); k--) base = nivel(k - 1);
                if (!base) continue;
                while (j + 1 < textos.length && nivel(j + 1) > base) j++;
            }
            c.orden += c.par * 100000;  // varios tras el mismo párrafo: en el orden de sus citas
            c.par = j;
        }
    }

    // Del final al principio, para que no se muevan los índices de los párrafos
    colocar.sort(function (a, b) { return a.par != b.par ? b.par - a.par : b.orden - a.orden; });
    var estiloAncla = estiloParrafo(doc, cfg.estilo_parrafo_ancla || "Texto base");
    for (var i = 0; i < colocar.length; i++) {
        var c = colocar[i], ip;
        if (c.par < 0) {
            ip = historia.insertionPoints[0];
        } else {
            var par = historia.paragraphs[c.par], ultimo = par.characters[-1];
            if (ultimo.contents == "\r") { ultimo.insertionPoints[0].contents = "\r"; }
            else { par.insertionPoints[-1].contents = "\r"; }
            var nuevo = historia.paragraphs[c.par + 1];
            nuevo.applyParagraphStyle(estiloAncla, true);
            nuevo.applyCharacterStyle(doc.characterStyles[0]);
            ip = nuevo.insertionPoints[0];
        }
        c.obj.anchoredObjectSettings.insertAnchoredObject(ip, AnchorPosition.ANCHORED);
    }
    ok("Anclados en la historia principal: " + colocar.length + " objetos");
}

// ---------------------------------------------------------------------------
function limpiarEstilos(doc) {
    // Estilos de carácter usados por otros estilos (viñetas, anidados, GREP)
    var usadosCar = {};
    var pe = doc.allParagraphStyles;
    for (var i = 0; i < pe.length; i++) {
        var e = pe[i];
        try { usadosCar[e.bulletsCharacterStyle.name] = true; } catch (x) {}
        try { usadosCar[e.numberingCharacterStyle.name] = true; } catch (x) {}
        try { usadosCar[e.dropCapStyle.name] = true; } catch (x) {}
        var colecciones = ["nestedStyles", "nestedGrepStyles", "nestedLineStyles"];
        for (var c = 0; c < colecciones.length; c++) {
            try { var ns = e[colecciones[c]]; for (var k = 0; k < ns.length; k++) usadosCar[ns[k].appliedCharacterStyle.name] = true; } catch (x) {}
        }
    }
    var nP = borrarSinUso(doc, "par", {}), nC = borrarSinUso(doc, "car", usadosCar);
    if (nP || nC) ok("Estilos sin uso borrados: " + nP + " de párrafo, " + nC + " de carácter");
}

function borrarSinUso(doc, clase, protegidos) {
    var total = 0, borrado = true;
    while (borrado) {  // al borrar uno, su «basado en» puede quedarse sin uso
        borrado = false;
        var lista = clase == "par" ? doc.allParagraphStyles : doc.allCharacterStyles;
        var base = {};
        for (var i = 0; i < lista.length; i++) {
            try { base[lista[i].basedOn.name] = true; } catch (x) {}
            try { if (clase == "par") if (lista[i].nextStyle.id != lista[i].id) base[lista[i].nextStyle.name] = true; } catch (x) {}
        }
        for (var i = lista.length - 1; i >= 0; i--) {
            var e = lista[i];
            if (e.name.charAt(0) == "[" || base[e.name] || protegidos[e.name]) continue;
            app.findTextPreferences = NothingEnum.nothing;
            if (clase == "par") app.findTextPreferences.appliedParagraphStyle = e;
            else app.findTextPreferences.appliedCharacterStyle = e;
            var usos = doc.findText().length;
            app.findTextPreferences = NothingEnum.nothing;
            if (usos) continue;
            try { e.remove(); total++; borrado = true; } catch (x) {}
        }
    }
    // Grupos de estilos vacíos
    var grupos = clase == "par" ? doc.paragraphStyleGroups : doc.characterStyleGroups;
    for (var i = grupos.length - 1; i >= 0; i--) {
        try { if (grupos[i].allParagraphStyles ? !grupos[i].allParagraphStyles.length : !grupos[i].allCharacterStyles.length) grupos[i].remove(); } catch (x) {}
    }
    return total;
}

// ---------------------------------------------------------------------------
function listarCapitulos(indd) {
    var doc = null, abierto = false;
    for (var i = 0; i < app.documents.length; i++) if (app.documents[i].fullName.fsName == indd.fsName) { doc = app.documents[i]; abierto = true; }
    try {
        if (!doc) doc = app.open(indd, false);
        var caps = capitulos(doc), r = ["ok" + (abierto && doc.modified ? "|modificado" : "")];
        for (var i = 0; i < caps.length; i++) r.push(caps[i].n + "|" + caps[i].paginas);
        return r.join("\n");
    } catch (e) {
        return "error|" + e;
    } finally {
        if (doc && !abierto && doc.isValid) doc.close(SaveOptions.NO);  // el del usuario se queda abierto
    }
}

(function (ruta, rutaConfig, cap) {
    if (!ruta) return "error|No se ha indicado el .indd";
    var indd = File(ruta);
    if (!indd.exists) return "error|No existe " + indd.fsName;
    if (rutaConfig == "capitulos") return listarCapitulos(indd);
    for (var i = 0; i < app.documents.length; i++) {
        if (app.documents[i].fullName.fsName == indd.fsName) return "error|La copia ya está abierta en InDesign; ciérrala y vuelve a intentarlo";
    }
    var cfg = leerJSON(rutaConfig);
    var nivel = app.scriptPreferences.userInteractionLevel;
    var unidades = app.scriptPreferences.measurementUnit;
    app.scriptPreferences.userInteractionLevel = UserInteractionLevels.NEVER_INTERACT;
    app.scriptPreferences.measurementUnit = MeasurementUnits.MILLIMETERS;
    var doc = null;
    try {
        doc = app.open(indd, false);
        principal(doc, cfg, cap, indd.parent.fsName);
        doc.save(indd);
        return ["ok"].concat(INFORME).join("\n");
    } catch (e) {
        return ["error|" + e + (e.line ? " (línea " + e.line + ")" : "")].concat(INFORME).join("\n");
    } finally {
        app.findGrepPreferences = NothingEnum.nothing;
        app.findTextPreferences = NothingEnum.nothing;
        if (doc && doc.isValid) doc.close(SaveOptions.NO);
        app.scriptPreferences.userInteractionLevel = nivel;
        app.scriptPreferences.measurementUnit = unidades;
    }
})(arguments[0], arguments[1], arguments[2]); // el "arguments" de do script, no el de la función
