#target illustrator

(function () {
    var templateFile = new File("/Users/jose/Desktop/Graficos BdE/Plantilla Pruebas.ait");
    var documentRef;
    var lines = [];

    function clean(value) {
        return String(value)
            .replace(/\r/g, "\\r")
            .replace(/\n/g, "\\n")
            .replace(/\t/g, "\\t");
    }

    function boundsText(bounds) {
        if (!bounds || bounds.length !== 4) {
            return "";
        }
        return [
            Math.round(bounds[0] * 100) / 100,
            Math.round(bounds[1] * 100) / 100,
            Math.round(bounds[2] * 100) / 100,
            Math.round(bounds[3] * 100) / 100
        ].join(",");
    }

    function colorText(color) {
        if (!color) {
            return "";
        }

        if (color.typename === "SpotColor") {
            return "SpotColor(" + clean(color.spot.name) + ", tinta=" + color.tint + ")";
        }
        if (color.typename === "CMYKColor") {
            return "CMYK(" + [
                color.cyan,
                color.magenta,
                color.yellow,
                color.black
            ].join(",") + ")";
        }
        if (color.typename === "RGBColor") {
            return "RGB(" + [color.red, color.green, color.blue].join(",") + ")";
        }
        if (color.typename === "GrayColor") {
            return "Gray(" + color.gray + ")";
        }
        if (color.typename === "PatternColor") {
            return "Pattern(" + clean(color.pattern.name) + ")";
        }
        return color.typename;
    }

    function addLine(depth, kind, name, details) {
        lines.push([
            new Array(depth + 1).join("  "),
            kind,
            clean(name || "(sin nombre)"),
            details || ""
        ].join("\t"));
    }

    function describeItem(item, depth) {
        var details = [
            "visible=" + (!item.hidden),
            "locked=" + item.locked,
            "bounds=" + boundsText(item.geometricBounds)
        ];

        if (item.typename === "TextFrame") {
            details.push("contenido=" + clean(item.contents));
            details.push("tipo=" + item.kind);
            details.push("lineas=" + item.lines.length);
        }

        if (item.typename === "PathItem" && item.name) {
            details.push("trazo=" + item.stroked);
            if (item.stroked) {
                details.push("colorTrazo=" + colorText(item.strokeColor));
                details.push("grosor=" + item.strokeWidth);
                details.push("guiones=" + item.strokeDashes);
            }
            details.push("relleno=" + item.filled);
            if (item.filled) {
                details.push("colorRelleno=" + colorText(item.fillColor));
            }
        }

        addLine(depth, item.typename, item.name, details.join("\t"));

        if (item.typename === "GroupItem") {
            inspectPageItems(item.pageItems, depth + 1);
        }
    }

    function inspectPageItems(items, depth) {
        var index;
        for (index = 0; index < items.length; index += 1) {
            describeItem(items[index], depth);
        }
    }

    function inspectLayer(layer, depth) {
        var index;
        addLine(depth, "Layer", layer.name, [
            "visible=" + layer.visible,
            "locked=" + layer.locked,
            "printable=" + layer.printable,
            "pageItems=" + layer.pageItems.length,
            "sublayers=" + layer.layers.length
        ].join("\t"));

        inspectPageItems(layer.pageItems, depth + 1);

        for (index = 0; index < layer.layers.length; index += 1) {
            inspectLayer(layer.layers[index], depth + 1);
        }
    }

    if (!templateFile.exists) {
        throw new Error("No se encuentra la plantilla: " + templateFile.fsName);
    }

    documentRef = app.open(templateFile);

    try {
        var index;
        lines.push("DOCUMENTO\t" + clean(documentRef.name));
        lines.push("CAPAS\t" + documentRef.layers.length);
        lines.push("TEXTOS\t" + documentRef.textFrames.length);
        lines.push("MUESTRAS\t" + documentRef.swatches.length);
        lines.push("TINTAS PLANAS\t" + documentRef.spots.length);
        lines.push("ESTILOS GRÁFICOS\t" + documentRef.graphicStyles.length);
        lines.push("PINCELES\t" + documentRef.brushes.length);

        for (index = 0; index < documentRef.layers.length; index += 1) {
            inspectLayer(documentRef.layers[index], 0);
        }

        lines.push("");
        lines.push("LISTA DE MUESTRAS");
        for (index = 0; index < documentRef.swatches.length; index += 1) {
            lines.push(
                "Swatch\t" +
                clean(documentRef.swatches[index].name) +
                "\t" +
                colorText(documentRef.swatches[index].color)
            );
        }

        lines.push("");
        lines.push("LISTA DE TINTAS PLANAS");
        for (index = 0; index < documentRef.spots.length; index += 1) {
            lines.push(
                "Spot\t" +
                clean(documentRef.spots[index].name) +
                "\t" +
                colorText(documentRef.spots[index].color)
            );
        }

        lines.push("");
        lines.push("LISTA DE ESTILOS GRÁFICOS");
        for (index = 0; index < documentRef.graphicStyles.length; index += 1) {
            lines.push("GraphicStyle\t" + clean(documentRef.graphicStyles[index].name));
        }

        lines.push("");
        lines.push("LISTA DE PINCELES");
        for (index = 0; index < documentRef.brushes.length; index += 1) {
            lines.push("Brush\t" + clean(documentRef.brushes[index].name));
        }
    } finally {
        documentRef.close(SaveOptions.DONOTSAVECHANGES);
    }

    return lines.join("\n");
}());
