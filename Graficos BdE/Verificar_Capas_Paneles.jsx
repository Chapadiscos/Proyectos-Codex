#target illustrator

(function () {
    var PANEL_PREFIX = "Panel ";
    var LEGEND_LAYER_PREFIX = "leyendas panel ";
    var MAX_PANELS = 3;
    var REPORT_PATH = "/tmp/bde_panel_layer_check.txt";

    function fail(message) {
        throw new Error(message);
    }

    function findLayerByName(collection, name) {
        var index;

        for (index = 0; index < collection.length; index += 1) {
            if (collection[index].name === name) {
                return collection[index];
            }
        }
        return null;
    }

    function findLayerContaining(collection, text) {
        var index;

        for (index = 0; index < collection.length; index += 1) {
            if (collection[index].name.indexOf(text) >= 0) {
                return collection[index];
            }
        }
        return null;
    }

    function getMainLayer(documentRef) {
        var layer = findLayerContaining(documentRef.layers, "CUADROS");

        if (!layer) {
            fail('No se encuentra la capa principal que contiene "CUADROS".');
        }
        return layer;
    }

    function getPanelLayer(documentRef, panelNumber) {
        var layer = findLayerByName(
            getMainLayer(documentRef).layers,
            PANEL_PREFIX + panelNumber
        );

        if (!layer) {
            fail("No se encuentra la capa " + PANEL_PREFIX + panelNumber + ".");
        }
        return layer;
    }

    function getLegendLayer(documentRef, panelNumber) {
        var layer = findLayerByName(
            getPanelLayer(documentRef, panelNumber).layers,
            LEGEND_LAYER_PREFIX + panelNumber
        );

        if (!layer) {
            fail("No se encuentra la capa " + LEGEND_LAYER_PREFIX + panelNumber + ".");
        }
        return layer;
    }

    function getPanelTitleFrame(panelLayer) {
        function findTitleFrame(items) {
            var index;
            var item;
            var found;

            for (index = 0; index < items.length; index += 1) {
                item = items[index];
                if (item.typename === "TextFrame" && item.geometricBounds[0] < 100) {
                    return item;
                }
                if (item.typename === "GroupItem") {
                    found = findTitleFrame(item.pageItems);
                    if (found) {
                        return found;
                    }
                }
            }
            return null;
        }

        return findTitleFrame(panelLayer.pageItems);
    }

    function itemContainsItem(container, target) {
        var index;

        if (container === target) {
            return true;
        }
        if (container.typename !== "GroupItem") {
            return false;
        }

        for (index = 0; index < container.pageItems.length; index += 1) {
            if (itemContainsItem(container.pageItems[index], target)) {
                return true;
            }
        }
        return false;
    }

    function isPanelTitleItem(item, titleFrame) {
        if (!titleFrame) {
            return false;
        }
        return itemContainsItem(item, titleFrame);
    }

    function isExpectedLegendItem(item) {
        return /^Leyenda [1-6]$/.test(item.name || "") ||
            /^Texto leyenda [1-6]$/.test(item.name || "");
    }

    function countDirectPanelArtwork(panelLayer) {
        var titleFrame = getPanelTitleFrame(panelLayer);
        var count = 0;
        var index;
        var item;

        for (index = 0; index < panelLayer.pageItems.length; index += 1) {
            item = panelLayer.pageItems[index];
            if (!item.hidden && !isPanelTitleItem(item, titleFrame)) {
                count += 1;
            }
        }
        return count;
    }

    function getUnexpectedLegendItems(legendLayer) {
        var result = [];
        var index;
        var item;

        for (index = 0; index < legendLayer.pageItems.length; index += 1) {
            item = legendLayer.pageItems[index];
            if (!item.hidden && !isExpectedLegendItem(item)) {
                result.push(item);
            }
        }
        return result;
    }

    function describeItems(items) {
        var descriptions = [];
        var index;
        var itemName;

        for (index = 0; index < items.length && index < 6; index += 1) {
            itemName = items[index].name || "(sin nombre)";
            descriptions.push(items[index].typename + " " + itemName);
        }
        if (items.length > 6) {
            descriptions.push("... +" + (items.length - 6) + " mas");
        }
        return descriptions.join(", ");
    }

    function writeReport(text) {
        var reportFile = new File(REPORT_PATH);

        reportFile.encoding = "UTF-8";
        reportFile.open("w");
        reportFile.write(text);
        reportFile.close();
    }

    function showReport(text) {
        writeReport(text);
        if (app.userInteractionLevel !== UserInteractionLevel.DONTDISPLAYALERTS) {
            alert(text);
        }
    }

    function verifyPanel(documentRef, panelNumber) {
        var panelLayer = getPanelLayer(documentRef, panelNumber);
        var legendLayer = getLegendLayer(documentRef, panelNumber);
        var directArtworkCount = countDirectPanelArtwork(panelLayer);
        var unexpectedLegendItems = getUnexpectedLegendItems(legendLayer);
        var lines = [];

        lines.push(
            "Panel " + panelNumber + ": " +
            directArtworkCount + " elemento(s) de grafico directamente en la capa del panel."
        );

        if (unexpectedLegendItems.length > 0) {
            lines.push(
                "  Revisar: hay " + unexpectedLegendItems.length +
                " elemento(s) no esperados dentro de " + legendLayer.name + ": " +
                describeItems(unexpectedLegendItems)
            );
        }

        if (directArtworkCount === 0 && unexpectedLegendItems.length === 0) {
            lines.push("  Aviso: no se detecta arte de grafico en este panel.");
        }

        return {
            ok: unexpectedLegendItems.length === 0,
            lines: lines
        };
    }

    function run() {
        var documentRef;
        var panelNumber;
        var report = [];
        var hasProblems = false;
        var result;

        if (app.documents.length === 0) {
            alert("Abre primero un documento de Illustrator.");
            return;
        }

        documentRef = app.activeDocument;
        report.push("Verificacion de capas de paneles");
        report.push(documentRef.name);
        report.push("");

        for (panelNumber = 1; panelNumber <= MAX_PANELS; panelNumber += 1) {
            result = verifyPanel(documentRef, panelNumber);
            if (!result.ok) {
                hasProblems = true;
            }
            report = report.concat(result.lines);
            report.push("");
        }

        if (hasProblems) {
            report.push("Resultado: revisar capas de leyendas antes de recalcular posiciones.");
        } else {
            report.push("Resultado: no se detecta arte de grafico dentro de capas de leyendas.");
        }

        showReport(report.join("\n"));
        return report.join("\n");
    }

    try {
        return run();
    } catch (error) {
        showReport("No se pudo verificar:\n" + error.message);
        return "ERROR: " + error.message;
    }
}());
