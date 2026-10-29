#target illustrator
#targetengine "bde_generator"

/*
 * Base modular del generador de gráficos BdE.
 *
 * Personaliza el tipo de ilustración y el color del tema. Si se elige Gráfico,
 * continúa solicitando los datos específicos del gráfico.
 */

(function () {
    var scriptLanguage = "es";

    var NAMES = {
        mainLayer: "GRÁFICOS-CUADROS",
        panelPrefix: "Panel ",
        legendLayerPrefix: "leyendas panel ",
        legendTextPrefix: "Texto leyenda ",
        legendGraphicPrefix: "Leyenda ",
        sourceLayer: "FUENTES",
        guidesLayer: "BdeE Reticula Oficial",
        boxLayer: "RECUADRO",
        colorsLayer: "Colores",
        legendLibraryLayer: "Lineas y tramas dibujos",
        themeSpot: "Color del tema",
        titleTextGroup: "Textos",
        titleBackgrounds: [
            "Fondo Título 1 Línea",
            "Fondo Título 2 líneas",
            "Fondo Titulo 3 líneas"
        ]
    };

    var TITLE_FRAME_HEIGHTS = [9.13, 23.3, 33.2];
    var PANEL_OFFSETS_MM = [0, 5, 8.5];
    var LEGEND_TEXT_WIDTH_MM = 40.4;
    var LEGEND_LINE_OFFSET_MM = 2.822;
    var LEGEND_TEXT_BASE_HEIGHT = 7.7;
    var MAX_LEGEND_COUNT = 7;
    var PANEL_LETTER_ALPHABET = ["a", "b", "c", "d", "e", "f", "g", "h", "i"];
    var PANEL_START_LETTER_OPTIONS = ["c", "d", "e"];
    var PANEL_START_LETTER_INDICES = [2, 3, 4];
    var PANEL_UNITS_LEFT_MM = 8;
    var PANEL_UNITS_UP_OFFSET_MM = 0.35;
    var PANEL_UNITS_PANEL_TITLE_GAP_MM = 2.5;
    var PANEL_UNITS_MAIN_TITLE_GAP_MM = 4.5;
    var PANEL_UNITS_GRAPH_START_GAP_MM = 2.5;
    var SOURCE_TAB_POSITION = 8.50393962860107;
    var SOURCE_HEIGHT_PADDING_MM = 1.5;
    var SOURCE_INFO_ONLY_OFFSET_MM = 12;
    var CHART_PATTERN_MIN_AREA_MM2 = 3;
    var CHART_PATTERN_VIEW_MARGIN_MM = 18;
    var PANEL_GRAPH_LEFT_MM = 3;
    var PANEL_GRAPH_UP_OFFSET_MM = 0.5;
    var PANEL_GRAPH_UNIT_OFFSET_MM = 0.7;
    var PANEL_GRAPH_GAP_MM = 8.5;
    var SOURCE_PANEL_GAP_MM = 5;
    var PANEL_TITLE_TO_GRAPH_GAP_MM = [7.377, 7.415, 7.323];
    var PANEL_GRAPH_START_WITH_TITLE = [-67.53, -81.81, -91.47];
    var PANEL_GRAPH_START_WITHOUT_TITLE = [-50.57, -64.85, -74.51];
    var PANEL_TITLE_MAX_LINES = 3;
    var PANEL_TITLE_LEADING_PT = 9.6;
    var PANEL_TITLE_GUIDE_BACKGROUND_BY_PANEL = {
        1: "Fondo Título 2 líneas",
        2: "Fondo Titulo 3 líneas"
    };
    var OVERSIZED_ARTWORK_WIDTH_MM = 190;
    var OVERSIZED_ARTWORK_HEIGHT_MM = 260;
    var PANEL_VIEW_MARGIN_MM = 8;
    var DOWNLOAD_ICON_PNG_BASE64 =
        "iVBORw0KGgoAAAANSUhEUgAAABMAAAATCAYAAAByUDbMAAACrUlEQVR4nIVUMUsjQRT+3uzOBglYiXAuBBTEFFeJhXCdtY0o6C84lIOziSDoLzgL4QqRgysklTa2YhCDYGNxCVgY0MbGSiwUi+wm+45v2I2bnHIPhp2dmfe977355gFvZnLzzyKyIyJNEXkVkYRfAE0AO9z/wK9voSAiPwDQUQeHMSabc5/nCoOA2eQTgKvM0VrbsdYm1lrO1fM8rici0hGRDPQq9XM4AsADYI0xl0mSTE9MTETVatWKCPfAT5IkKBQKOD8/x8bGBshQVWNVDQD8AfAFQJyx20kjR8vLy3p6eqpjY2NaKpXc4LxSqejT05Nub2/2UhaRKGXIOsIHUAbwnSnwP45jPD4+4uHhoa+o7XYbrVYL6+vrCMMQa2trZOirapL6/2a9vgII0gguO9/3XXrWWjo4sJOTE9Trdezv72N+fh4jIyNMn+c19ScOrsnK87wuARcXF/Xo6MilwtR939e5ubm+W724uNAwDN1cROhHdtcMO0lG7+ml2+0iCAJsbW2hWCw6lkNDQ46xqubVQP9Jk9PKPzY8PIxOp4Pn52eXNoHjuHdpg1YgWHtw1fOoFmBpaQm7u7toNBo4PDxEuVx2bLM6Dlibq7dpLZJ8erRqteqYraysoFarodlsOr1RdzlLUv9bSqOWvrXeCabE6EyJUlhYWMDx8bHb07daZcYFkqoR7BeAb6nmnDyiKHLRNzc3MTU15XRHwLOzMxwcHOSZufMUO3EI0ALwE0CFT8IYY8fHxzEzM4Obmxvc3d05lmT08vKC2dlZjI6OZmAdPsXUv9V7myJyqarTYRhGe3t7tlgsCtPM14egQRDg/v5eV1dX4ziOA1Xte5vvdo00albcbPCf6+92jV7QTCvsZ8aYVz7kj4bneR/2s0FAGm+XnYCdlY5k9N9O+xfWfzA4xKDmxgAAAABJRU5ErkJggg==";
    var CHART_PATTERN_SWATCHES = {
        "Trama - Negro": "Trama franjas horizontales",
        "Trama - Verde": "Trama puntos",
        "Trama - Amarillo": "Trama lineas oblicuas arriba",
        "Trama - Naranja": "Trama zigzag",
        "Trama - Azul": "Trama lineas verticales",
        "Trama - Rosa": "Trama lineas oblicuas abajo"
    };
    var LEGEND_FORMATS = [
        {label: "Línea - Negro", type: "style", name: "Negro línea"},
        {label: "Línea - Verde", type: "style", name: "Verde linea"},
        {label: "Línea - Amarillo", type: "style", name: "Amarillo linea"},
        {label: "Línea - Naranja", type: "style", name: "Naranja linea"},
        {label: "Línea - Azul", type: "style", name: "Azul linea"},
        {label: "Línea - Rosa", type: "style", name: "Rosa linea"},
        {label: "Línea - Marrón", type: "style", name: "Marron linea"},
        {label: "Línea - Negro 2", type: "style", name: "Negro línea 2"},
        {label: "Línea - Negro 3", type: "style", name: "Negro línea 3"},
        {label: "Trama - Negro", type: "style", name: "Negro trama"},
        {label: "Trama - Verde", type: "style", name: "Verde trama "},
        {label: "Trama - Amarillo", type: "style", name: "Amarillo trama"},
        {label: "Trama - Naranja", type: "style", name: "Naranja trama"},
        {label: "Trama - Azul", type: "style", name: "Azul trama"},
        {label: "Trama - Rosa", type: "style", name: "Rosa trama"},
        {label: "Trama - Marrón", type: "style", name: "Marron trama"},
        {label: "Marcador - Cuadrado", type: "brush", name: "Marcador Cuadrado"},
        {label: "Marcador - Triángulo", type: "brush", name: "Marcados Triángulo"},
        {label: "Marcador - Redondo", type: "brush", name: "Marcador Redondo"},
        {label: "Marcador - Línea", type: "brush", name: "Marcador Linea"},
        {label: "Marcador - Diamante", type: "brush", name: "Marcador Diamante"},
        {label: "Marcador - Línea 2", type: "brush", name: "Marcador Linea 2"}
    ];

    var THEME_COLORS = {
        "Naranja (DO)": {
            mode: "CMYK",
            values: [9.18, 71.85, 98.2, 1.36]
        },
        "Rojo/Cobre": {
            mode: "CMYK",
            values: [29, 76, 46, 26]
        },
        "Marrón (Biblioteca)": {
            mode: "CMYK",
            values: [21.2, 72.67, 70.61, 10.57]
        },
        "Gris": {
            mode: "Lab",
            values: [42, 2, 5]
        },
        "Celeste": {
            mode: "CMYK",
            values: [81.52, 24.61, 36.62, 7.49]
        },
        "Azul": {
            mode: "Lab",
            values: [30, -10, -28]
        }
    };

    function fail(message) {
        throw new Error(message);
    }

    function refreshDocument() {
        app.redraw();
        $.sleep(150);
    }

    function normalizeWindowBounds(bounds) {
        var left;
        var top;
        var right;
        var bottom;

        if (!bounds) {
            return null;
        }

        if (bounds.length === 4) {
            left = bounds[0];
            top = bounds[1];
            right = bounds[2];
            bottom = bounds[3];
        } else if (
            typeof bounds.left === "number" &&
            typeof bounds.top === "number" &&
            typeof bounds.right === "number" &&
            typeof bounds.bottom === "number"
        ) {
            left = bounds.left;
            top = bounds.top;
            right = bounds.right;
            bottom = bounds.bottom;
        } else {
            return null;
        }

        if (
            typeof left !== "number" ||
            typeof top !== "number" ||
            typeof right !== "number" ||
            typeof bottom !== "number" ||
            isNaN(left) ||
            isNaN(top) ||
            isNaN(right) ||
            isNaN(bottom)
        ) {
            return null;
        }

        return [
            Math.min(left, right),
            Math.min(top, bottom),
            Math.max(left, right),
            Math.max(top, bottom)
        ];
    }

    function getActiveWindowBounds() {
        var bounds = null;

        try {
            if (app.activeWindow && app.activeWindow.bounds) {
                bounds = normalizeWindowBounds(app.activeWindow.bounds);
                if (bounds) {
                    return bounds;
                }
            }
        } catch (error1) {}

        try {
            if (app.windows && app.windows.length > 0 && app.windows[0].bounds) {
                bounds = normalizeWindowBounds(app.windows[0].bounds);
                if (bounds) {
                    return bounds;
                }
            }
        } catch (error2) {}

        try {
            if (
                app.activeDocument &&
                app.activeDocument.windows &&
                app.activeDocument.windows.length > 0 &&
                app.activeDocument.windows[0].bounds
            ) {
                bounds = normalizeWindowBounds(app.activeDocument.windows[0].bounds);
                if (bounds) {
                    return bounds;
                }
            }
        } catch (error3) {}

        try {
            if (app.layoutWindows && app.layoutWindows.length > 0) {
                bounds = normalizeWindowBounds(app.layoutWindows[0].bounds);
                if (bounds) {
                    return bounds;
                }
            }
        } catch (error4) {}

        return null;
    }

    function getBoundsIntersectionArea(firstBounds, secondBounds) {
        var left = Math.max(firstBounds[0], secondBounds[0]);
        var top = Math.max(firstBounds[1], secondBounds[1]);
        var right = Math.min(firstBounds[2], secondBounds[2]);
        var bottom = Math.min(firstBounds[3], secondBounds[3]);

        if (right <= left || bottom <= top) {
            return 0;
        }
        return (right - left) * (bottom - top);
    }

    function getScreenBoundsForHostBounds(hostBounds) {
        var screens;
        var screenBounds;
        var bestBounds = null;
        var bestArea = 0;
        var area;
        var index;

        try {
            screens = $.screens;
        } catch (screensError) {
            screens = null;
        }

        if (!screens || screens.length === 0 || !hostBounds) {
            return hostBounds;
        }

        for (index = 0; index < screens.length; index += 1) {
            screenBounds = normalizeWindowBounds(
                screens[index].visibleBounds || screens[index].bounds
            );
            if (!screenBounds) {
                continue;
            }
            area = getBoundsIntersectionArea(hostBounds, screenBounds);
            if (area > bestArea) {
                bestArea = area;
                bestBounds = screenBounds;
            }
        }

        return bestBounds || hostBounds;
    }

    function applyWindowLocation(windowRef, left, top) {
        try {
            windowRef.frameLocation = [left, top];
        } catch (frameError) {}
        try {
            windowRef.location = [left, top];
        } catch (locationError) {}
    }

    function positionDialogOnActiveWindow(dialog) {
        var hostBounds = getActiveWindowBounds();
        var targetBounds;
        var dialogSize;
        var width;
        var height;
        var left;
        var top;
        var previousOnShow = dialog.onShow;

        try {
            dialog.layout.layout(true);
        } catch (layoutError) {}

        if (!hostBounds) {
            dialog.center();
            return;
        }

        dialogSize = dialog.preferredSize || dialog.size || [0, 0];
        width = dialogSize[0] || 0;
        height = dialogSize[1] || 0;

        if (width <= 0 || height <= 0) {
            dialog.center();
            return;
        }

        targetBounds = getScreenBoundsForHostBounds(hostBounds);
        left = targetBounds[0] + Math.round((targetBounds[2] - targetBounds[0] - width) / 2);
        top = targetBounds[1] + Math.round((targetBounds[3] - targetBounds[1] - height) / 2);
        applyWindowLocation(dialog, left, top);
        dialog.onShow = function () {
            if (previousOnShow) {
                previousOnShow.call(dialog);
            }
            applyWindowLocation(dialog, left, top);
        };
    }

    function getByName(collection, name, description) {
        try {
            return collection.getByName(name);
        } catch (error) {
            fail("No se encuentra " + description + ' "' + name + '".');
        }
    }

    function getMainLayer(documentRef) {
        return getByName(documentRef.layers, NAMES.mainLayer, "la capa principal");
    }

    function getPanelLayer(documentRef, panelNumber) {
        return getByName(
            getMainLayer(documentRef).layers,
            NAMES.panelPrefix + panelNumber,
            "la capa del panel"
        );
    }

    function getLegendLayer(documentRef, panelNumber) {
        return getByName(
            getPanelLayer(documentRef, panelNumber).layers,
            NAMES.legendLayerPrefix + panelNumber,
            "la capa de leyendas"
        );
    }

    function isPanelPlacementHelperName(name) {
        name = name || "";
        return name === "Texto+flecha Grafico" ||
            name.indexOf("Texto+flecha Titulo") === 0 ||
            /^Guia (inicio grafico|titulo) panel [1-3]$/.test(name);
    }

    function isPanelPlacementHelperItem(item) {
        return Boolean(item.guides) || isPanelPlacementHelperName(item.name || "");
    }

    function isPanelUnitsFrameName(name) {
        return /^Unidades panel [1-3]$/.test(name || "");
    }

    function getPanelTitleFrame(documentRef, panelNumber) {
        var panelLayer = getPanelLayer(documentRef, panelNumber);
        var artworkGroupName = "Grafico panel " + panelNumber;

        function findTitleFrame(items) {
            var index;
            var item;
            var found;

            for (index = 0; index < items.length; index += 1) {
                item = items[index];
                if (
                    item.typename === "GroupItem" &&
                    (item.name === artworkGroupName || isPanelPlacementHelperItem(item))
                ) {
                    continue;
                }
                if (
                    item.typename === "TextFrame" &&
                    item.geometricBounds[0] < 100 &&
                    !isExpectedLegendItem(item) &&
                    !isPanelUnitsFrameName(item.name)
                ) {
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

        var titleFrame = findTitleFrame(panelLayer.pageItems);
        if (titleFrame) {
            return titleFrame;
        }
        fail("No se encuentra el título del Panel " + panelNumber + ".");
    }

    function setLayerVisibleIfPresent(collection, name, visible) {
        try {
            collection.getByName(name).visible = visible;
        } catch (error) {
            // Algunas variantes de plantilla no incluyen todas las capas auxiliares.
        }
    }

    function setPanelCount(documentRef, panelCount) {
        var panelNumber;
        for (panelNumber = 1; panelNumber <= 3; panelNumber += 1) {
            getPanelLayer(documentRef, panelNumber).visible = panelNumber <= panelCount;
        }
    }

    function millimetersToPoints(millimeters) {
        return millimeters * 72 / 25.4;
    }

    function rememberAndUnlock(item, lockStates) {
        try {
            lockStates.push({
                item: item,
                locked: item.locked
            });
            item.locked = false;
        } catch (error) {
            // Algunos objetos especiales no exponen bloqueo editable.
        }
    }

    function rememberAndDisableGuide(item, guideStates) {
        try {
            if (item.guides) {
                guideStates.push({
                    item: item,
                    guides: item.guides
                });
                item.guides = false;
            }
        } catch (error) {
            // No todos los PageItems exponen la propiedad guides.
        }
    }

    function rememberAndShowLayer(layer, visibilityStates) {
        try {
            visibilityStates.push({
                layer: layer,
                visible: layer.visible
            });
            layer.visible = true;
        } catch (error) {
            // Algunas capas especiales no permiten cambiar la visibilidad por script.
        }
    }

    function unlockPageItemTree(item, lockStates, guideStates) {
        var index;

        rememberAndUnlock(item, lockStates);
        rememberAndDisableGuide(item, guideStates);

        if (item.typename === "GroupItem") {
            for (index = 0; index < item.pageItems.length; index += 1) {
                unlockPageItemTree(item.pageItems[index], lockStates, guideStates);
            }
        }
    }

    function unlockLayerTree(layer) {
        var states = {
            locks: [],
            guides: [],
            visibility: []
        };

        function unlockLayer(layerToUnlock) {
            var layerIndex;
            var itemIndex;

            rememberAndShowLayer(layerToUnlock, states.visibility);
            rememberAndUnlock(layerToUnlock, states.locks);

            for (layerIndex = 0; layerIndex < layerToUnlock.layers.length; layerIndex += 1) {
                unlockLayer(layerToUnlock.layers[layerIndex]);
            }

            for (itemIndex = 0; itemIndex < layerToUnlock.pageItems.length; itemIndex += 1) {
                unlockPageItemTree(
                    layerToUnlock.pageItems[itemIndex],
                    states.locks,
                    states.guides
                );
            }
        }

        unlockLayer(layer);
        return states;
    }

    function restoreVisibilityStates(visibilityStates) {
        var index;

        for (index = visibilityStates.length - 1; index >= 0; index -= 1) {
            try {
                visibilityStates[index].layer.visible = visibilityStates[index].visible;
            } catch (error) {
                // Si Illustrator no permite restaurar una capa concreta, seguimos.
            }
        }
    }

    function restoreGuideStates(guideStates) {
        var index;

        for (index = guideStates.length - 1; index >= 0; index -= 1) {
            try {
                guideStates[index].item.guides = guideStates[index].guides;
            } catch (error) {
                // Si Illustrator no permite restaurar una guía concreta, seguimos.
            }
        }
    }

    function restoreLockStates(lockStates) {
        var index;

        for (index = lockStates.length - 1; index >= 0; index -= 1) {
            try {
                lockStates[index].item.locked = lockStates[index].locked;
            } catch (error) {
                // Si Illustrator ya no permite restaurar un objeto, seguimos con el resto.
            }
        }
    }

    function translateLayerContents(layer, verticalOffset) {
        var index;

        for (index = 0; index < layer.pageItems.length; index += 1) {
            layer.pageItems[index].translate(0, verticalOffset);
        }

        for (index = 0; index < layer.layers.length; index += 1) {
            translateLayerContents(layer.layers[index], verticalOffset);
        }
    }

    function translateLayerContentsTemporarilyUnlocked(layer, verticalOffset) {
        var states = unlockLayerTree(layer);

        try {
            translateLayerContents(layer, verticalOffset);
        } finally {
            restoreGuideStates(states.guides);
            restoreVisibilityStates(states.visibility);
            restoreLockStates(states.locks);
        }
    }

    function translateItemTemporarilyUnlocked(item, horizontalOffset, verticalOffset) {
        var states = {
            locks: [],
            guides: []
        };

        unlockPageItemTree(item, states.locks, states.guides);
        try {
            item.translate(horizontalOffset || 0, verticalOffset || 0);
        } finally {
            restoreGuideStates(states.guides);
            restoreLockStates(states.locks);
        }
    }

    function movePanelsForTitle(documentRef, lineCount, panelCount) {
        var offset = -millimetersToPoints(PANEL_OFFSETS_MM[lineCount - 1]);
        var panelNumber;

        if (offset === 0) {
            return;
        }

        for (panelNumber = 1; panelNumber <= panelCount; panelNumber += 1) {
            translateLayerContentsTemporarilyUnlocked(
                getPanelLayer(documentRef, panelNumber),
                offset
            );
        }
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
        var match = /^(Leyenda|Texto leyenda) ([0-9]+)$/.exec(item.name || "");
        var legendNumber;

        if (!match) {
            return false;
        }
        legendNumber = parseInt(match[2], 10);
        return legendNumber >= 1 && legendNumber <= MAX_LEGEND_COUNT;
    }

    function getUnexpectedLegendArtworkItems(legendLayer) {
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

    function getPanelArtworkItems(documentRef, panelNumber) {
        var panelLayer = getPanelLayer(documentRef, panelNumber);
        var titleFrame = getPanelTitleFrame(documentRef, panelNumber);
        var result = [];
        var index;
        var item;

        for (index = 0; index < panelLayer.pageItems.length; index += 1) {
            item = panelLayer.pageItems[index];
            if (
                !item.hidden &&
                !isPanelPlacementHelperItem(item) &&
                !isPanelTitleItem(item, titleFrame) &&
                !isPanelUnitsFrameName(item.name)
            ) {
                result.push(item);
            }
        }
        return result;
    }

    function getLooseGraphArtworkItems(documentRef) {
        var mainLayer = getMainLayer(documentRef);
        var result = [];
        var index;
        var item;

        for (index = 0; index < mainLayer.pageItems.length; index += 1) {
            item = mainLayer.pageItems[index];
            if (
                !item.hidden &&
                item.name !== "Filete superior" &&
                item.name !== "Título"
            ) {
                result.push(item);
            }
        }

        result.sort(function (a, b) {
            return b.geometricBounds[1] - a.geometricBounds[1];
        });
        return result;
    }

    function moveItemsToLayer(items, layer) {
        var index;

        for (index = 0; index < items.length; index += 1) {
            items[index].move(layer, ElementPlacement.PLACEATEND);
        }
    }

    function getPanelArtworkGroupName(panelNumber) {
        return "Grafico panel " + panelNumber;
    }

    function getPanelArtworkGroup(documentRef, panelNumber) {
        var panelLayer = getPanelLayer(documentRef, panelNumber);
        var groupName = getPanelArtworkGroupName(panelNumber);

        try {
            return panelLayer.groupItems.getByName(groupName);
        } catch (error) {
            return null;
        }
    }

    function groupPanelArtwork(documentRef, panelNumber) {
        var panelLayer = getPanelLayer(documentRef, panelNumber);
        var artworkItems = getPanelArtworkItems(documentRef, panelNumber);
        var groupName = getPanelArtworkGroupName(panelNumber);
        var group;
        var index;

        if (artworkItems.length === 0) {
            return null;
        }

        if (
            artworkItems.length === 1 &&
            artworkItems[0].typename === "GroupItem" &&
            artworkItems[0].name === groupName
        ) {
            return artworkItems[0];
        }

        group = panelLayer.groupItems.add();
        group.name = groupName;
        for (index = 0; index < artworkItems.length; index += 1) {
            artworkItems[index].move(group, ElementPlacement.PLACEATEND);
        }
        return group;
    }

    function mergeBounds(bounds, candidate) {
        if (!candidate || candidate.length !== 4) {
            return bounds;
        }
        if (!bounds) {
            return [candidate[0], candidate[1], candidate[2], candidate[3]];
        }

        bounds[0] = Math.min(bounds[0], candidate[0]);
        bounds[1] = Math.max(bounds[1], candidate[1]);
        bounds[2] = Math.max(bounds[2], candidate[2]);
        bounds[3] = Math.min(bounds[3], candidate[3]);
        return bounds;
    }

    function getTextFrameLineCount(textFrame, contents) {
        var documentRef = app.activeDocument;
        var bounds = textFrame.geometricBounds;
        var width = Math.abs(bounds[2] - bounds[0]);
        var tempLayer;
        var tempBox;
        var testFrame;
        var lineCount;

        function copyTextStyle(sourceFrame, targetFrame) {
            var sourceCharacters = sourceFrame.textRange.characterAttributes;
            var targetCharacters = targetFrame.textRange.characterAttributes;
            var sourceParagraph = sourceFrame.paragraphs[0].paragraphAttributes;
            var targetParagraph = targetFrame.paragraphs[0].paragraphAttributes;

            try { targetCharacters.textFont = sourceCharacters.textFont; } catch (error1) {}
            try { targetCharacters.size = sourceCharacters.size; } catch (error2) {}
            try { targetCharacters.leading = sourceCharacters.leading; } catch (error3) {}
            try { targetCharacters.tracking = sourceCharacters.tracking; } catch (error4) {}
            try { targetCharacters.horizontalScale = sourceCharacters.horizontalScale; } catch (error5) {}
            try { targetCharacters.verticalScale = sourceCharacters.verticalScale; } catch (error6) {}
            try { targetParagraph.justification = sourceParagraph.justification; } catch (error7) {}
        }

        tempLayer = documentRef.layers.add();
        tempLayer.name = "__bde_medicion_titulo_panel__";
        try {
            tempBox = tempLayer.pathItems.rectangle(0, 0, width, 200);
            tempBox.stroked = false;
            tempBox.filled = false;
            testFrame = tempLayer.textFrames.areaText(tempBox);
            testFrame.contents = contents;
            copyTextStyle(textFrame, testFrame);
            app.redraw();
            lineCount = testFrame.lines.length;
        } finally {
            tempLayer.remove();
        }

        return Math.max(1, lineCount);
    }

    function isOversizedArtworkBounds(bounds) {
        var width;
        var height;

        if (!bounds || bounds.length !== 4) {
            return false;
        }

        width = Math.abs(bounds[2] - bounds[0]);
        height = Math.abs(bounds[1] - bounds[3]);
        return width > millimetersToPoints(OVERSIZED_ARTWORK_WIDTH_MM) &&
            height > millimetersToPoints(OVERSIZED_ARTWORK_HEIGHT_MM);
    }

    function getArtworkItemBounds(item) {
        var bounds = null;
        var index;
        var childBounds;

        if (item.hidden || isPanelPlacementHelperItem(item)) {
            return null;
        }

        if (item.typename === "GroupItem") {
            for (index = 0; index < item.pageItems.length; index += 1) {
                childBounds = getArtworkItemBounds(item.pageItems[index]);
                bounds = mergeBounds(bounds, childBounds);
            }
            return bounds;
        }

        bounds = item.visibleBounds;
        if (isOversizedArtworkBounds(bounds)) {
            return null;
        }
        return bounds;
    }

    function getItemsBounds(items) {
        var bounds = null;
        var index;
        var itemBounds;

        for (index = 0; index < items.length; index += 1) {
            itemBounds = getArtworkItemBounds(items[index]);
            bounds = mergeBounds(bounds, itemBounds);
        }
        return bounds;
    }

    function getLayerContentBounds(layer) {
        var bounds = null;
        var index;

        if (isPanelPlacementHelperName(layer.name || "")) {
            return null;
        }

        for (index = 0; index < layer.pageItems.length; index += 1) {
            bounds = mergeBounds(bounds, getArtworkItemBounds(layer.pageItems[index]));
        }
        for (index = 0; index < layer.layers.length; index += 1) {
            bounds = mergeBounds(bounds, getLayerContentBounds(layer.layers[index]));
        }
        return bounds;
    }

    function getFirstLegendTextFrame(documentRef, panelNumber) {
        try {
            return getLegendLayer(documentRef, panelNumber).textFrames.getByName(
                NAMES.legendTextPrefix + "1"
            );
        } catch (error) {
            return null;
        }
    }

    function findGuideYInItems(items, guideName) {
        var index;
        var item;
        var found;

        for (index = 0; index < items.length; index += 1) {
            item = items[index];
            if (item.name === guideName && item.geometricBounds) {
                return item.geometricBounds[1];
            }
            if (item.typename === "GroupItem") {
                found = findGuideYInItems(item.pageItems, guideName);
                if (found !== null) {
                    return found;
                }
            }
        }
        return null;
    }

    function findGuideYInLayer(layer, guideName) {
        var found = findGuideYInItems(layer.pageItems, guideName);
        var index;

        if (found !== null) {
            return found;
        }

        for (index = 0; index < layer.layers.length; index += 1) {
            found = findGuideYInLayer(layer.layers[index], guideName);
            if (found !== null) {
                return found;
            }
        }
        return null;
    }

    function getPanelGraphStartGuideY(documentRef, panelNumber) {
        return findGuideYInLayer(
            getPanelLayer(documentRef, panelNumber),
            "Guia inicio grafico panel " + panelNumber
        );
    }

    function getSplitSourceGroup(blockItem) {
        var current = blockItem;

        while (
            current &&
            current.typename === "GroupItem" &&
            current.pageItems.length === 1 &&
            current.pageItems[0].typename === "GroupItem"
        ) {
            current = current.pageItems[0];
        }
        return current && current.typename === "GroupItem" ? current : null;
    }

    function getVerticalArtworkCandidates(group) {
        var result = [];
        var index;
        var item;
        var bounds;

        for (index = 0; index < group.pageItems.length; index += 1) {
            item = group.pageItems[index];
            if (item.hidden) {
                continue;
            }

            bounds = getArtworkItemBounds(item);
            if (bounds) {
                result.push({
                    item: item,
                    bounds: bounds,
                    centerY: (bounds[1] + bounds[3]) / 2
                });
            }
        }

        result.sort(function (a, b) {
            return b.centerY - a.centerY;
        });
        return result;
    }

    function getClusterSplitIndexes(candidates, clusterCount) {
        var gaps = [];
        var index;
        var splitIndexes = [];

        for (index = 1; index < candidates.length; index += 1) {
            gaps.push({
                index: index,
                gap: candidates[index - 1].centerY - candidates[index].centerY
            });
        }

        gaps.sort(function (a, b) {
            return b.gap - a.gap;
        });

        for (index = 0; index < clusterCount - 1 && index < gaps.length; index += 1) {
            splitIndexes.push(gaps[index].index);
        }

        splitIndexes.sort(function (a, b) {
            return a - b;
        });
        return splitIndexes;
    }

    function splitArtworkCandidates(candidates, clusterCount) {
        var splitIndexes = getClusterSplitIndexes(candidates, clusterCount);
        var clusters = [];
        var startIndex = 0;
        var splitNumber;
        var endIndex;

        for (splitNumber = 0; splitNumber <= splitIndexes.length; splitNumber += 1) {
            endIndex = splitNumber < splitIndexes.length ?
                splitIndexes[splitNumber] :
                candidates.length;
            clusters.push(candidates.slice(startIndex, endIndex));
            startIndex = endIndex;
        }

        return clusters;
    }

    function moveArtworkClusterToLayer(cluster, layer) {
        var items = [];
        var index;

        for (index = 0; index < cluster.length; index += 1) {
            items.push(cluster[index].item);
        }
        moveItemsToLayer(items, layer);
    }

    function removeItemIfEmpty(item) {
        try {
            if (item.typename === "GroupItem" && item.pageItems.length === 0) {
                item.remove();
            }
        } catch (error) {
            // Si Illustrator no permite retirar el contenedor, no afecta a la colocación.
        }
    }

    function distributeLooseArtworkBlock(documentRef, panelCount, looseArtworkItems) {
        var sourceGroup;
        var candidates;
        var clusters;
        var panelNumber;

        if (panelCount <= 1 || looseArtworkItems.length !== 1) {
            return false;
        }

        sourceGroup = getSplitSourceGroup(looseArtworkItems[0]);
        if (!sourceGroup) {
            return false;
        }

        candidates = getVerticalArtworkCandidates(sourceGroup);
        if (candidates.length < panelCount) {
            return false;
        }

        clusters = splitArtworkCandidates(candidates, panelCount);
        if (clusters.length !== panelCount) {
            return false;
        }

        for (panelNumber = 1; panelNumber <= panelCount; panelNumber += 1) {
            moveArtworkClusterToLayer(
                clusters[panelNumber - 1],
                getPanelLayer(documentRef, panelNumber)
            );
        }

        removeItemIfEmpty(sourceGroup);
        removeItemIfEmpty(looseArtworkItems[0]);
        return true;
    }

    function translateItems(items, horizontalOffset, verticalOffset) {
        var index;

        for (index = 0; index < items.length; index += 1) {
            items[index].translate(horizontalOffset, verticalOffset);
        }
    }

    function getPanelOneGraphStartY(titleLineCount, hasPanelTitle, hasUnits) {
        var starts = hasPanelTitle ?
            PANEL_GRAPH_START_WITH_TITLE :
            PANEL_GRAPH_START_WITHOUT_TITLE;
        var startY = starts[titleLineCount - 1];

        if (hasUnits) {
            startY += millimetersToPoints(PANEL_GRAPH_UNIT_OFFSET_MM);
        }
        return startY;
    }

    function positionPanelArtworkX(documentRef, panelNumber) {
        var artworkGroup = getPanelArtworkGroup(documentRef, panelNumber);
        var bounds;
        var horizontalOffset;

        if (!artworkGroup) {
            return false;
        }

        bounds = getItemsBounds([artworkGroup]);
        if (!bounds) {
            return false;
        }

        horizontalOffset = millimetersToPoints(PANEL_GRAPH_LEFT_MM) - bounds[0];
        artworkGroup.translate(horizontalOffset, 0);
        return true;
    }

    function positionPanelOneArtwork(documentRef, titleLineCount, panelConfiguration) {
        var artworkGroup = getPanelArtworkGroup(documentRef, 1);
        var bounds;
        var desiredTop;
        var verticalOffset;

        if (!artworkGroup) {
            return false;
        }

        bounds = getItemsBounds([artworkGroup]);
        if (!bounds) {
            return false;
        }

        desiredTop = getPanelOneGraphStartY(
            titleLineCount,
            panelConfiguration.title !== "",
            panelConfiguration.hasUnits
        );
        desiredTop += millimetersToPoints(PANEL_GRAPH_UP_OFFSET_MM);
        desiredTop -= panelConfiguration.titleExtraOffset || 0;
        verticalOffset = desiredTop - bounds[1];
        artworkGroup.translate(0, verticalOffset);
        return true;
    }

    function alignPanelOneLegendsWithoutTitle(documentRef, titleLineCount, panelConfiguration) {
        var firstLegendTextFrame;
        var legendBounds;
        var desiredLegendTop;
        var verticalOffset;

        if (panelConfiguration.title !== "") {
            return false;
        }

        firstLegendTextFrame = getFirstLegendTextFrame(documentRef, 1);
        if (!firstLegendTextFrame || firstLegendTextFrame.hidden) {
            return false;
        }

        legendBounds = getItemsBounds([firstLegendTextFrame]);
        if (!legendBounds) {
            return false;
        }

        desiredLegendTop = getPanelOneGraphStartY(titleLineCount, false, false);
        verticalOffset = desiredLegendTop - legendBounds[1];
        translateLayerContents(getLegendLayer(documentRef, 1), verticalOffset);
        return true;
    }

    function alignPanelArtworkToFirstLegend(documentRef, panelNumber, panelConfiguration) {
        var artworkGroup = getPanelArtworkGroup(documentRef, panelNumber);
        var firstLegendTextFrame = getFirstLegendTextFrame(documentRef, panelNumber);
        var artworkBounds;
        var legendBounds;
        var verticalOffset;

        if (!artworkGroup || !firstLegendTextFrame || firstLegendTextFrame.hidden) {
            return false;
        }

        artworkBounds = getItemsBounds([artworkGroup]);
        legendBounds = getItemsBounds([firstLegendTextFrame]);
        if (!artworkBounds || !legendBounds) {
            return false;
        }

        verticalOffset = legendBounds[1] - artworkBounds[1];
        verticalOffset += millimetersToPoints(PANEL_GRAPH_UP_OFFSET_MM);
        if (panelConfiguration.hasUnits) {
            verticalOffset += millimetersToPoints(PANEL_GRAPH_UNIT_OFFSET_MM);
        }

        artworkGroup.translate(0, verticalOffset);
        return true;
    }

    function alignFollowingPanelArtworkStart(documentRef, panelNumber, titleLineCount, panelConfiguration) {
        var artworkGroup = getPanelArtworkGroup(documentRef, panelNumber);
        var titleFrame;
        var artworkBounds;
        var titleToGraphGap;
        var desiredGraphTop;
        var verticalOffset;
        var graphStartGuideY = getPanelGraphStartGuideY(documentRef, panelNumber);

        if (!artworkGroup) {
            return false;
        }

        artworkBounds = getItemsBounds([artworkGroup]);
        if (!artworkBounds) {
            return false;
        }

        if (graphStartGuideY !== null) {
            desiredGraphTop = graphStartGuideY;
            desiredGraphTop += millimetersToPoints(PANEL_GRAPH_UP_OFFSET_MM);
            if (panelConfiguration.hasUnits) {
                desiredGraphTop += millimetersToPoints(PANEL_GRAPH_UNIT_OFFSET_MM);
            }
            artworkGroup.translate(0, desiredGraphTop - artworkBounds[1]);
            return true;
        }

        if (panelConfiguration.title === "") {
            return alignPanelArtworkToFirstLegend(documentRef, panelNumber, panelConfiguration);
        }

        titleFrame = getPanelTitleFrame(documentRef, panelNumber);
        if (!titleFrame || titleFrame.hidden) {
            return false;
        }

        titleToGraphGap = PANEL_TITLE_TO_GRAPH_GAP_MM[titleLineCount - 1];
        if (panelConfiguration.hasUnits) {
            titleToGraphGap -= PANEL_GRAPH_UNIT_OFFSET_MM;
        }

        desiredGraphTop =
            titleFrame.geometricBounds[3] - millimetersToPoints(titleToGraphGap);
        desiredGraphTop += millimetersToPoints(PANEL_GRAPH_UP_OFFSET_MM);
        verticalOffset = desiredGraphTop - artworkBounds[1];
        artworkGroup.translate(0, verticalOffset);
        return true;
    }

    function positionFollowingPanelArtwork(documentRef, panelNumber, titleLineCount, panelConfiguration) {
        var previousPanelLayer = getPanelLayer(documentRef, panelNumber - 1);
        var currentPanelLayer = getPanelLayer(documentRef, panelNumber);
        var previousBounds;
        var currentBounds;
        var desiredPanelTop;
        var verticalOffset;

        alignFollowingPanelArtworkStart(
            documentRef,
            panelNumber,
            titleLineCount,
            panelConfiguration
        );

        previousBounds = getLayerContentBounds(previousPanelLayer);
        currentBounds = getLayerContentBounds(currentPanelLayer);
        if (!previousBounds || !currentBounds) {
            return false;
        }

        desiredPanelTop = previousBounds[3] - millimetersToPoints(PANEL_GRAPH_GAP_MM);
        verticalOffset = desiredPanelTop - currentBounds[1];
        translateLayerContentsTemporarilyUnlocked(currentPanelLayer, verticalOffset);
        return true;
    }

    function positionPanelArtworkForInput(documentRef, panelNumber, titleLineCount, panelConfigurations) {
        positionPanelArtworkX(documentRef, panelNumber);
        if (panelNumber === 1) {
            positionPanelOneArtwork(
                documentRef,
                titleLineCount,
                panelConfigurations[0]
            );
            alignPanelOneLegendsWithoutTitle(
                documentRef,
                titleLineCount,
                panelConfigurations[0]
            );
            return true;
        }
        return positionFollowingPanelArtwork(
            documentRef,
            panelNumber,
            titleLineCount,
            panelConfigurations[panelNumber - 1]
        );
    }

    function placePanelArtwork(documentRef, panelCount, panelConfigurations, titleLineCount) {
        var looseArtworkItems = getLooseGraphArtworkItems(documentRef);
        var panelNumber;
        var panelLayer;
        var legendLayer;
        var misplacedArtworkItems;
        var panelArtworkItems;
        var missingPanels = [];

        if (distributeLooseArtworkBlock(documentRef, panelCount, looseArtworkItems)) {
            looseArtworkItems = getLooseGraphArtworkItems(documentRef);
        }

        for (panelNumber = 1; panelNumber <= panelCount; panelNumber += 1) {
            panelLayer = getPanelLayer(documentRef, panelNumber);
            legendLayer = getLegendLayer(documentRef, panelNumber);
            misplacedArtworkItems = getUnexpectedLegendArtworkItems(legendLayer);

            if (misplacedArtworkItems.length > 0) {
                moveItemsToLayer(misplacedArtworkItems, panelLayer);
            }

            panelArtworkItems = getPanelArtworkItems(documentRef, panelNumber);
            if (panelArtworkItems.length === 0 && looseArtworkItems.length > 0) {
                moveItemsToLayer([looseArtworkItems.shift()], panelLayer);
                panelArtworkItems = getPanelArtworkItems(documentRef, panelNumber);
            }

            if (panelArtworkItems.length === 0) {
                missingPanels.push(panelNumber);
            } else {
                groupPanelArtwork(documentRef, panelNumber);
            }
        }

        if (missingPanels.length > 0) {
            alert(
                "No se ha detectado arte de grafico para el Panel " +
                missingPanels.join(", ") +
                ". Pega o coloca cada grafico en su panel antes de recalcular posiciones."
            );
            return false;
        }
        return true;
    }

    function getPanelUnitsFrameName(panelNumber) {
        return "Unidades panel " + panelNumber;
    }

    function getVerticalAxisCandidateX(item) {
        var bounds;
        var width;
        var height;

        if (!item || item.hidden || item.typename !== "PathItem" || item.guides) {
            return null;
        }
        try {
            if (!item.stroked || item.filled) {
                return null;
            }
        } catch (styleError) {}

        try {
            bounds = item.geometricBounds;
        } catch (boundsError) {
            return null;
        }

        width = Math.abs(bounds[2] - bounds[0]);
        height = Math.abs(bounds[1] - bounds[3]);
        if (
            width <= millimetersToPoints(0.35) &&
            height >= millimetersToPoints(5)
        ) {
            return (bounds[0] + bounds[2]) / 2;
        }
        return null;
    }

    function findLeftmostVerticalAxisX(item, currentX) {
        var index;
        var candidateX = getVerticalAxisCandidateX(item);

        if (candidateX !== null && (currentX === null || candidateX < currentX)) {
            currentX = candidateX;
        }

        if (item && item.pageItems) {
            for (index = 0; index < item.pageItems.length; index += 1) {
                currentX = findLeftmostVerticalAxisX(item.pageItems[index], currentX);
            }
        }
        return currentX;
    }

    function getPanelUnitsLeftX(documentRef, panelNumber) {
        var artworkGroup = getPanelArtworkGroup(documentRef, panelNumber);
        var axisX;

        if (artworkGroup) {
            axisX = findLeftmostVerticalAxisX(artworkGroup, null);
            if (axisX !== null) {
                return axisX;
            }
        }
        return millimetersToPoints(PANEL_UNITS_LEFT_MM);
    }

    function removeExistingPanelUnitsFrame(documentRef, panelNumber) {
        var panelLayer = getPanelLayer(documentRef, panelNumber);
        var frameName = getPanelUnitsFrameName(panelNumber);
        var existingFrame = findDescendantByName(panelLayer, function (name) {
            return name === frameName;
        });
        var states;

        if (!existingFrame) {
            return;
        }

        states = unlockLayerTree(panelLayer);
        try {
            existingFrame.remove();
        } finally {
            restoreGuideStates(states.guides);
            restoreVisibilityStates(states.visibility);
            restoreLockStates(states.locks);
        }
    }

    function copyCharacterStyle(sourceFrame, targetFrame) {
        var sourceAttributes;
        var targetAttributes;

        if (!sourceFrame) {
            return;
        }

        sourceAttributes = sourceFrame.textRange.characterAttributes;
        targetAttributes = targetFrame.textRange.characterAttributes;
        try { targetAttributes.textFont = sourceAttributes.textFont; } catch (error1) {}
        try { targetAttributes.size = sourceAttributes.size; } catch (error2) {}
        try { targetAttributes.leading = sourceAttributes.leading; } catch (error3) {}
        try { targetAttributes.tracking = sourceAttributes.tracking; } catch (error4) {}
        try { targetAttributes.horizontalScale = sourceAttributes.horizontalScale; } catch (error5) {}
        try { targetAttributes.verticalScale = sourceAttributes.verticalScale; } catch (error6) {}
        try {
            targetFrame.textRange.paragraphAttributes.justification =
                sourceFrame.textRange.paragraphAttributes.justification;
        } catch (error7) {}
    }

    function applyDefaultUnitsTextStyle(textFrame) {
        try {
            textFrame.textRange.characterAttributes.textFont =
                app.textFonts.getByName("Roboto-Regular");
        } catch (error1) {}
        try { textFrame.textRange.characterAttributes.size = 7; } catch (error2) {}
        try { textFrame.textRange.characterAttributes.leading = 7; } catch (error3) {}
    }

    function getMainTitleLastLineY(documentRef) {
        return getMainTitleFrames(documentRef).title.geometricBounds[3];
    }

    function getPanelTitleLastLineY(documentRef, panelNumber) {
        return getPanelTitleFrame(documentRef, panelNumber).geometricBounds[3];
    }

    function getPanelUnitsBaselineY(documentRef, panelNumber, panelConfigurations) {
        var panelConfiguration = panelConfigurations[panelNumber - 1];
        var artworkGroup;
        var artworkBounds;

        if (panelConfiguration.title !== "") {
            return getPanelTitleLastLineY(documentRef, panelNumber) -
                millimetersToPoints(PANEL_UNITS_PANEL_TITLE_GAP_MM);
        }

        if (panelNumber === 1) {
            return getMainTitleLastLineY(documentRef) -
                millimetersToPoints(PANEL_UNITS_MAIN_TITLE_GAP_MM);
        }

        try {
            return getPanelTitleLastLineY(documentRef, panelNumber) -
                millimetersToPoints(PANEL_UNITS_PANEL_TITLE_GAP_MM);
        } catch (titleError) {}

        artworkGroup = getPanelArtworkGroup(documentRef, panelNumber);
        if (!artworkGroup) {
            return null;
        }
        artworkBounds = getItemsBounds([artworkGroup]);
        if (!artworkBounds) {
            return null;
        }
        return artworkBounds[1] +
            millimetersToPoints(PANEL_UNITS_GRAPH_START_GAP_MM);
    }

    function setPanelUnits(documentRef, panelNumber, panelConfigurations) {
        var panelLayer = getPanelLayer(documentRef, panelNumber);
        var artworkGroup = getPanelArtworkGroup(documentRef, panelNumber);
        var panelConfiguration = panelConfigurations[panelNumber - 1];
        var unitsText = panelConfiguration.units || "";
        var unitsFrame;
        var baselineY;
        var states;

        removeExistingPanelUnitsFrame(documentRef, panelNumber);
        if (unitsText === "" || !artworkGroup) {
            return false;
        }

        baselineY = getPanelUnitsBaselineY(documentRef, panelNumber, panelConfigurations);
        if (baselineY === null) {
            return false;
        }

        states = unlockLayerTree(panelLayer);
        try {
            unitsFrame = panelLayer.textFrames.add();
            unitsFrame.name = getPanelUnitsFrameName(panelNumber);
            unitsFrame.contents = unitsText;
            unitsFrame.position = [
                getPanelUnitsLeftX(documentRef, panelNumber) +
                    millimetersToPoints(panelConfiguration.unitsManualOffsetX || 0),
                baselineY + millimetersToPoints(PANEL_UNITS_UP_OFFSET_MM)
            ];
            applyDefaultUnitsTextStyle(unitsFrame);
        } finally {
            restoreGuideStates(states.guides);
            restoreVisibilityStates(states.visibility);
            restoreLockStates(states.locks);
        }

        return unitsFrame;
    }

    function setPanelUnitsForAllPanels(documentRef, panelCount, panelConfigurations) {
        var panelNumber;

        for (panelNumber = 1; panelNumber <= panelCount; panelNumber += 1) {
            setPanelUnits(documentRef, panelNumber, panelConfigurations);
        }
    }

    function removePanelUnitsForAllPanels(documentRef, panelCount) {
        var panelNumber;

        for (panelNumber = 1; panelNumber <= panelCount; panelNumber += 1) {
            removeExistingPanelUnitsFrame(documentRef, panelNumber);
        }
    }

    function showPanelUnitsAdjustmentDialog(unitsFrame, panelConfiguration, panelNumber) {
        var dialog;
        var controls;
        var leftButton;
        var rightButton;
        var resetButton;
        var offsetLabel;
        var closeButton;
        var stepMillimeters = 0.2;
        var currentOffset = panelConfiguration.unitsManualOffsetX || 0;

        if (!unitsFrame || (panelConfiguration.units || "") === "") {
            return;
        }

        dialog = new Window("dialog", "Ajustar unidades Panel " + panelNumber);
        dialog.orientation = "column";
        dialog.alignChildren = ["fill", "top"];
        dialog.spacing = 12;
        dialog.margins = 16;

        offsetLabel = dialog.add("statictext", undefined, "");
        controls = dialog.add("group");
        controls.orientation = "row";
        controls.alignChildren = ["center", "center"];
        leftButton = controls.add("button", undefined, "<");
        resetButton = controls.add("button", undefined, "0");
        rightButton = controls.add("button", undefined, ">");

        dialog.add(
            "statictext",
            undefined,
            "Mantén pulsada ← o → del teclado para mover de forma continua."
        );

        closeButton = dialog.add("button", undefined, "Continuar", {name: "ok"});

        function updateLabel() {
            offsetLabel.text =
                "Ajuste horizontal: " +
                (Math.round(currentOffset * 10) / 10) +
                " mm";
        }

        function moveUnits(deltaMillimeters) {
            currentOffset = Math.round((currentOffset + deltaMillimeters) * 10) / 10;
            panelConfiguration.unitsManualOffsetX = currentOffset;
            unitsFrame.translate(millimetersToPoints(deltaMillimeters), 0);
            updateLabel();
            refreshDocument();
        }

        leftButton.onClick = function () {
            moveUnits(-stepMillimeters);
        };
        rightButton.onClick = function () {
            moveUnits(stepMillimeters);
        };
        resetButton.onClick = function () {
            if (currentOffset !== 0) {
                moveUnits(-currentOffset);
            }
        };

        dialog.addEventListener("keydown", function (event) {
            if (event.keyName === "Left") {
                moveUnits(-stepMillimeters);
                event.preventDefault();
            } else if (event.keyName === "Right") {
                moveUnits(stepMillimeters);
                event.preventDefault();
            }
        });

        dialog.onShow = function () {
            leftButton.active = true;
        };

        updateLabel();
        positionDialogOnActiveWindow(dialog);
        dialog.show();
    }

    function showPreSaveChecklist(documentRef) {
        var palette = new Window("palette", "Comprobaciones");
        var warningText = palette.add(
            "statictext",
            undefined,
            "⚠ No guardes ni cierres este archivo desde el menú de Illustrator " +
                "hasta marcar todas las comprobaciones y usar los botones de abajo.",
            {multiline: true}
        );
        var checksPanel = palette.add("panel", undefined, "Revisar");
        var buttons = palette.add("group");
        var checklistItems = [
            "Cambiar tramas",
            "Correspondencia color Leyendas (Ver PDF)",
            "Eje 0 y/o Línea base",
            "Textos (espacio fino, %, cursivas, I TR, ...)"
        ];
        var checks = [];
        var index;
        var saveButton;
        var closeButton;

        palette.orientation = "column";
        palette.alignChildren = ["fill", "top"];
        palette.spacing = 14;
        palette.margins = 16;

        try {
            warningText.graphics.font = ScriptUI.newFont(
                warningText.graphics.font.name,
                "BOLD",
                warningText.graphics.font.size
            );
        } catch (fontError) {}
        warningText.preferredSize.width = 320;

        checksPanel.orientation = "column";
        checksPanel.alignChildren = ["left", "top"];
        checksPanel.margins = 14;

        function allChecked() {
            var checkIndex;

            for (checkIndex = 0; checkIndex < checks.length; checkIndex += 1) {
                if (!checks[checkIndex].value) {
                    return false;
                }
            }
            return true;
        }

        function updateSaveState() {
            var ready = allChecked();

            closeButton.enabled = ready;
            saveButton.enabled = ready;
        }

        for (index = 0; index < checklistItems.length; index += 1) {
            checks.push(checksPanel.add("checkbox", undefined, checklistItems[index]));
            checks[index].value = false;
            checks[index].onClick = updateSaveState;
        }

        buttons.orientation = "row";
        buttons.alignment = "right";
        closeButton = buttons.add("button", undefined, "Cerrar");
        saveButton = buttons.add("button", undefined, "Guardar");
        closeButton.enabled = false;
        saveButton.enabled = false;

        closeButton.onClick = function () {
            palette.close();
        };

        palette.onClose = function () {
            if (!allChecked()) {
                alert("Marca todas las comprobaciones antes de cerrar.");
                return false;
            }
            return true;
        };

        saveButton.onClick = function () {
            if (!allChecked()) {
                alert("Marca todas las comprobaciones antes de guardar.");
                return;
            }
            try {
                documentRef.save();
                palette.close();
            } catch (saveError) {
                try {
                    app.activeDocument = documentRef;
                } catch (activeError) {}
                try {
                    app.executeMenuCommand("save");
                    palette.close();
                } catch (menuSaveError) {
                    alert("No se ha podido guardar el archivo:\n" + menuSaveError.message);
                }
            }
        };

        positionDialogOnActiveWindow(palette);
        palette.show();
    }

    function getPanelLegendFocusItems(documentRef, panelNumber, legendCount) {
        var legendLayer = getLegendLayer(documentRef, panelNumber);
        var result = [];
        var legendNumber;
        var textFrame;
        var graphic;

        for (legendNumber = 1; legendNumber <= legendCount; legendNumber += 1) {
            textFrame = getByName(
                legendLayer.textFrames,
                NAMES.legendTextPrefix + legendNumber,
                "el texto de leyenda"
            );
            graphic = getByName(
                legendLayer.pathItems,
                NAMES.legendGraphicPrefix + legendNumber,
                "el gráfico de leyenda"
            );
            if (!textFrame.hidden) {
                result.push(textFrame);
            }
            if (!graphic.hidden) {
                result.push(graphic);
            }
        }
        return result;
    }

    function getPanelFocusBounds(documentRef, panelNumber, legendCount) {
        var items = [];
        var artworkGroup = getPanelArtworkGroup(documentRef, panelNumber);
        var titleFrame = getPanelTitleFrame(documentRef, panelNumber);
        var legendItems = getPanelLegendFocusItems(documentRef, panelNumber, legendCount);
        var index;
        var bounds;
        var titleBounds;

        if (artworkGroup) {
            items.push(artworkGroup);
        }
        for (index = 0; index < legendItems.length; index += 1) {
            items.push(legendItems[index]);
        }
        bounds = getItemsBounds(items);

        // El marco de título ocupa casi todo el ancho de página; si se
        // incluyera entero, esa anchura dominaría el encuadre y forzaría
        // un zoom que revela mucha más altura de la necesaria (paneles
        // vecinos). Por eso solo se usa para extender el borde superior.
        if (titleFrame && !titleFrame.hidden) {
            titleBounds = titleFrame.geometricBounds;
            if (bounds) {
                bounds = [bounds[0], Math.max(bounds[1], titleBounds[1]), bounds[2], bounds[3]];
            } else {
                bounds = titleBounds;
            }
        }

        return bounds;
    }

    function focusViewOnBounds(documentRef, bounds, marginMillimeters) {
        var margin;
        var width;
        var height;
        var view;
        var viewBounds;
        var viewWidth;
        var viewHeight;
        var zoom;

        if (!bounds) {
            return;
        }

        try {
            app.activeDocument = documentRef;
        } catch (activeError) {}

        margin = millimetersToPoints(marginMillimeters);
        bounds = [
            bounds[0] - margin,
            bounds[1] + margin,
            bounds[2] + margin,
            bounds[3] - margin
        ];
        width = bounds[2] - bounds[0];
        height = bounds[1] - bounds[3];
        if (width <= 0 || height <= 0) {
            return;
        }

        view = documentRef.activeView;

        // view.bounds está expresado en puntos de documento visibles al
        // zoom ACTUAL, así que su tamaño cambia con el zoom previo. Sin
        // fijar antes un zoom de referencia, el cálculo del zoom final
        // queda contaminado por el zoom que dejó el panel anterior.
        view.zoom = 1;
        viewBounds = view.bounds;
        viewWidth = viewBounds[2] - viewBounds[0];
        viewHeight = viewBounds[1] - viewBounds[3];

        view.centerPoint = [
            (bounds[0] + bounds[2]) / 2,
            (bounds[1] + bounds[3]) / 2
        ];
        zoom = Math.min(viewWidth / width, viewHeight / height) * 0.9;
        if (zoom > 0) {
            view.zoom = zoom;
        }
    }

    function preparePanelForLegendInput(documentRef, panelNumber, titleLineCount, panelConfigurations) {
        var panelConfiguration = panelConfigurations[panelNumber - 1];
        var unitsFrame;

        removeExistingPanelUnitsFrame(documentRef, panelNumber);
        positionPanelArtworkForInput(
            documentRef,
            panelNumber,
            titleLineCount,
            panelConfigurations
        );
        unitsFrame = setPanelUnits(documentRef, panelNumber, panelConfigurations);
        focusViewOnBounds(
            documentRef,
            getPanelFocusBounds(documentRef, panelNumber, panelConfiguration.legendCount),
            PANEL_VIEW_MARGIN_MM
        );
        refreshDocument();
        showPanelUnitsAdjustmentDialog(unitsFrame, panelConfiguration, panelNumber);
    }

    function measureLegendLines(textFrame) {
        var testFrame = textFrame.duplicate();
        var lineCount;

        try {
            testFrame.textPath.width = millimetersToPoints(LEGEND_TEXT_WIDTH_MM);
            testFrame.textPath.height = 200;
            app.redraw();
            lineCount = testFrame.lines.length;
        } finally {
            testFrame.remove();
        }

        return Math.max(1, lineCount);
    }

    function layoutPanelLegends(documentRef, panelNumber, legendCount) {
        var legendLayer = getLegendLayer(documentRef, panelNumber);
        var accumulatedOffset = 0;
        var lineOffset = millimetersToPoints(LEGEND_LINE_OFFSET_MM);
        var legendNumber;
        var textFrame;
        var graphic;
        var lineCount;

        for (legendNumber = 1; legendNumber <= legendCount; legendNumber += 1) {
            textFrame = getByName(
                legendLayer.textFrames,
                NAMES.legendTextPrefix + legendNumber,
                "el texto de leyenda"
            );
            graphic = getByName(
                legendLayer.pathItems,
                NAMES.legendGraphicPrefix + legendNumber,
                "el gráfico de leyenda"
            );

            textFrame.translate(0, -accumulatedOffset);
            graphic.translate(0, -accumulatedOffset);

            textFrame.textPath.width = millimetersToPoints(LEGEND_TEXT_WIDTH_MM);
            lineCount = measureLegendLines(textFrame);
            textFrame.textPath.height =
                LEGEND_TEXT_BASE_HEIGHT + ((lineCount - 1) * lineOffset);

            accumulatedOffset += (lineCount - 1) * lineOffset;
        }
    }

    function setIllustrationType(documentRef, illustrationType) {
        getByName(
            documentRef.layers,
            NAMES.mainLayer,
            "la capa principal de gráficos"
        ).visible = illustrationType === "Gráfico" || illustrationType === "Cuadro";

        getByName(
            documentRef.layers,
            NAMES.boxLayer,
            "la capa de recuadro"
        ).visible = illustrationType === "Recuadro";
    }

    function getMainTitleFrames(documentRef) {
        var textGroup = getByName(
            documentRef.groupItems,
            NAMES.titleTextGroup,
            "el grupo de textos del título"
        );
        var result = {
            number: null,
            title: null
        };
        var index;
        var textFrame;

        for (index = 0; index < textGroup.textFrames.length; index += 1) {
            textFrame = textGroup.textFrames[index];
            if (textFrame.kind === TextType.POINTTEXT) {
                result.number = textFrame;
            } else if (textFrame.kind === TextType.AREATEXT) {
                result.title = textFrame;
            }
        }

        if (!result.number || !result.title) {
            fail("No se encuentran los marcos del número y el título del gráfico.");
        }
        return result;
    }

    function measureTitleLines(titleFrame, titleText) {
        var testFrame = titleFrame.duplicate();
        var lineCount;

        try {
            testFrame.contents = titleText;
            formatMainTitleSuffix(testFrame);
            testFrame.textPath.height = 200;
            app.redraw();
            lineCount = testFrame.lines.length;
        } finally {
            testFrame.remove();
        }

        return Math.max(1, lineCount);
    }

    function titleHasContinuationSuffix(titleText) {
        return /\((?:cont\.|cont['’]d)\)\s*$/i.test(titleText || "");
    }

    function formatMainTitleSuffix(titleFrame) {
        var suffixMatch = titleFrame.contents.match(
            /\((?:[a-z]|cont\.|cont['’]d)\)\s*$/i
        );
        var mediumFont;
        var index;
        var suffixEnd;

        if (!suffixMatch) {
            return;
        }

        mediumFont = app.textFonts.getByName("Roboto-Medium");
        suffixEnd = suffixMatch.index + suffixMatch[0].replace(/\s+$/, "").length;
        for (index = suffixMatch.index; index < suffixEnd; index += 1) {
            titleFrame.characters[index].characterAttributes.textFont = mediumFont;
        }
    }

    function translateIllustrationType(illustrationType) {
        if (scriptLanguage === "en" && illustrationType === "Gráfico") {
            return "Chart";
        }
        return illustrationType;
    }

    function setMainTitle(documentRef, illustrationType, graphNumber, titleText) {
        var frames = getMainTitleFrames(documentRef);
        var lineCount = measureTitleLines(frames.title, titleText);
        var backgroundIndex;

        if (lineCount > 3) {
            fail("El título ocupa " + lineCount + " líneas. El máximo permitido es 3.");
        }

        frames.number.contents = translateIllustrationType(illustrationType) + " " + graphNumber;
        frames.title.contents = titleText;
        formatMainTitleSuffix(frames.title);
        frames.title.textPath.height = TITLE_FRAME_HEIGHTS[lineCount - 1];

        for (backgroundIndex = 0; backgroundIndex < NAMES.titleBackgrounds.length; backgroundIndex += 1) {
            getByName(
                documentRef.groupItems,
                NAMES.titleBackgrounds[backgroundIndex],
                "el fondo del título"
            ).hidden = backgroundIndex !== lineCount - 1;
        }

        return lineCount;
    }

    function applyLegendFormat(documentRef, graphic, format) {
        if (format.type === "brush") {
            getByName(
                documentRef.brushes,
                format.name,
                "el pincel de marcador"
            ).applyTo(graphic);
        } else {
            getByName(
                documentRef.graphicStyles,
                format.name,
                "el estilo gráfico"
            ).applyTo(graphic);
        }
    }

    function pointsAreaToSquareMillimeters(area) {
        return Math.abs(area) * Math.pow(25.4 / 72, 2);
    }

    function getPanelLowerBoundary(documentRef, panelNumber) {
        if (panelNumber < 3) {
            return getPanelTitleFrame(documentRef, panelNumber + 1).geometricBounds[1];
        }
        return getVisibleSourceFrame(documentRef).geometricBounds[1];
    }

    function getColorKey(color, fallbackIndex) {
        if (color.typename === "PatternColor") {
            try {
                return "Pattern:" + color.pattern.name;
            } catch (error) {
                return "Pattern:" + fallbackIndex;
            }
        }
        if (color.typename === "SpotColor") {
            return "Spot:" + color.spot.name;
        }
        if (color.typename === "CMYKColor") {
            return "CMYK:" + Math.round(color.cyan) + "," +
                Math.round(color.magenta) + "," +
                Math.round(color.yellow) + "," +
                Math.round(color.black);
        }
        if (color.typename === "RGBColor") {
            return "RGB:" + Math.round(color.red) + "," +
                Math.round(color.green) + "," +
                Math.round(color.blue);
        }
        if (color.typename === "GrayColor") {
            return "Gray:" + Math.round(color.gray);
        }
        return color.typename;
    }

    function addChartPatternGroup(patternGroups, colorKey, pathItem, order) {
        var index;

        for (index = 0; index < patternGroups.length; index += 1) {
            if (patternGroups[index].colorKey === colorKey) {
                patternGroups[index].items.push(pathItem);
                return;
            }
        }

        patternGroups.push({
            colorKey: colorKey,
            order: order,
            items: [pathItem]
        });
    }

    function collectPanelChartPatternGroups(item, upperBoundary, lowerBoundary, patternGroups, state) {
        var index;
        var bounds;
        var centerY;
        var colorKey;

        if (item.hidden) {
            return;
        }

        if (item.typename === "PathItem") {
            state.order += 1;
            if (!item.filled) {
                return;
            }
            if (pointsAreaToSquareMillimeters(item.area) < CHART_PATTERN_MIN_AREA_MM2) {
                return;
            }

            bounds = item.geometricBounds;
            centerY = (bounds[1] + bounds[3]) / 2;
            if (centerY >= upperBoundary || centerY <= lowerBoundary) {
                return;
            }

            colorKey = getColorKey(item.fillColor, state.order);
            addChartPatternGroup(patternGroups, colorKey, item, state.order);
            return;
        }

        if (item.typename === "GroupItem" || item.typename === "Layer") {
            for (index = 0; index < item.pageItems.length; index += 1) {
                collectPanelChartPatternGroups(
                    item.pageItems[index],
                    upperBoundary,
                    lowerBoundary,
                    patternGroups,
                    state
                );
            }
            return;
        }

        if (item.typename === "CompoundPathItem") {
            for (index = 0; index < item.pathItems.length; index += 1) {
                collectPanelChartPatternGroups(
                    item.pathItems[index],
                    upperBoundary,
                    lowerBoundary,
                    patternGroups,
                    state
                );
            }
        }
    }

    function duplicateColor(color) {
        var newColor;

        if (color.typename === "PatternColor") {
            return color;
        }
        if (color.typename === "SpotColor") {
            newColor = new SpotColor();
            newColor.spot = color.spot;
            newColor.tint = color.tint;
            return newColor;
        }
        if (color.typename === "CMYKColor") {
            newColor = new CMYKColor();
            newColor.cyan = color.cyan;
            newColor.magenta = color.magenta;
            newColor.yellow = color.yellow;
            newColor.black = color.black;
            return newColor;
        }
        if (color.typename === "RGBColor") {
            newColor = new RGBColor();
            newColor.red = color.red;
            newColor.green = color.green;
            newColor.blue = color.blue;
            return newColor;
        }
        if (color.typename === "GrayColor") {
            newColor = new GrayColor();
            newColor.gray = color.gray;
            return newColor;
        }
        return color;
    }

    function getChartPatternSwatch(documentRef, format) {
        var swatchName = CHART_PATTERN_SWATCHES[format.label];
        var swatch;

        if (!swatchName) {
            return null;
        }

        swatch = getByName(
            documentRef.swatches,
            swatchName,
            "la muestra de trama"
        );
        if (swatch.color.typename !== "PatternColor") {
            fail('La muestra "' + swatchName + '" no es una trama de relleno.');
        }

        return swatch;
    }

    function collectChartPatternChanges(documentRef, panelNumber, formats) {
        var upperBoundary;
        var lowerBoundary;
        var patternGroups = [];
        var changes = [];
        var state = {order: 0};
        var tramaFormats = [];
        var formatIndex;
        var groupIndex;
        var itemIndex;
        var legendIndex;
        var patternSwatch;

        for (formatIndex = 0; formatIndex < formats.length; formatIndex += 1) {
            if (CHART_PATTERN_SWATCHES[formats[formatIndex].label]) {
                tramaFormats.push(formats[formatIndex]);
            }
        }

        if (tramaFormats.length === 0) {
            return changes;
        }

        upperBoundary = getPanelTitleFrame(documentRef, panelNumber).geometricBounds[3];
        lowerBoundary = getPanelLowerBoundary(documentRef, panelNumber);
        collectPanelChartPatternGroups(
            getMainLayer(documentRef),
            upperBoundary,
            lowerBoundary,
            patternGroups,
            state
        );

        patternGroups.sort(function (left, right) {
            return left.order - right.order;
        });

        for (groupIndex = 0; groupIndex < patternGroups.length; groupIndex += 1) {
            legendIndex = patternGroups.length - 1 - groupIndex;
            if (legendIndex >= tramaFormats.length) {
                continue;
            }

            patternSwatch = getChartPatternSwatch(documentRef, tramaFormats[legendIndex]);
            if (!patternSwatch) {
                continue;
            }

            for (itemIndex = 0; itemIndex < patternGroups[groupIndex].items.length; itemIndex += 1) {
                changes.push({
                    item: patternGroups[groupIndex].items[itemIndex],
                    swatch: patternSwatch,
                    originalFilled: patternGroups[groupIndex].items[itemIndex].filled,
                    originalFillColor: duplicateColor(
                        patternGroups[groupIndex].items[itemIndex].fillColor
                    )
                });
            }
        }

        return changes;
    }

    function collectAllChartPatternChanges(documentRef, panelFormats) {
        var changes = [];
        var panelIndex;
        var panelChanges;
        var changeIndex;

        for (panelIndex = 0; panelIndex < panelFormats.length; panelIndex += 1) {
            if (!panelFormats[panelIndex]) {
                continue;
            }
            panelChanges = collectChartPatternChanges(
                documentRef,
                panelIndex + 1,
                panelFormats[panelIndex]
            );
            for (changeIndex = 0; changeIndex < panelChanges.length; changeIndex += 1) {
                changes.push(panelChanges[changeIndex]);
            }
        }

        return changes;
    }

    function applyChartPatternChanges(changes) {
        var index;

        for (index = 0; index < changes.length; index += 1) {
            changes[index].item.fillColor = changes[index].swatch.color;
            changes[index].item.fillColor = changes[index].swatch.color;
        }
        refreshDocument();
    }

    function restoreChartPatternChanges(changes) {
        var index;

        for (index = 0; index < changes.length; index += 1) {
            changes[index].item.filled = changes[index].originalFilled;
            if (changes[index].originalFilled) {
                try {
                    changes[index].item.fillColor = duplicateColor(changes[index].originalFillColor);
                } catch (error) {
                    // Si Illustrator no deja reponer el patrón importado, se mantiene el estado actual.
                }
            }
        }
        refreshDocument();
    }

    function zoomViewToChartChanges(documentRef, changes) {
        var bounds;
        var itemBounds;
        var index;
        var margin = millimetersToPoints(CHART_PATTERN_VIEW_MARGIN_MM);
        var width;
        var height;
        var zoom;
        var view;
        var viewBounds;
        var viewWidth;
        var viewHeight;

        if (changes.length === 0 || !documentRef.activeView) {
            return;
        }

        bounds = changes[0].item.visibleBounds;
        bounds = [bounds[0], bounds[1], bounds[2], bounds[3]];
        for (index = 1; index < changes.length; index += 1) {
            itemBounds = changes[index].item.visibleBounds;
            bounds[0] = Math.min(bounds[0], itemBounds[0]);
            bounds[1] = Math.max(bounds[1], itemBounds[1]);
            bounds[2] = Math.max(bounds[2], itemBounds[2]);
            bounds[3] = Math.min(bounds[3], itemBounds[3]);
        }

        bounds[0] -= margin;
        bounds[1] += margin;
        bounds[2] += margin;
        bounds[3] -= margin;
        width = bounds[2] - bounds[0];
        height = bounds[1] - bounds[3];
        view = documentRef.activeView;
        view.centerPoint = [
            (bounds[0] + bounds[2]) / 2,
            (bounds[1] + bounds[3]) / 2
        ];

        viewBounds = view.bounds;
        viewWidth = viewBounds[2] - viewBounds[0];
        viewHeight = viewBounds[1] - viewBounds[3];
        zoom = Math.min(
            viewWidth / width,
            viewHeight / height
        ) * 0.9;
        if (zoom > 0) {
            view.zoom = zoom;
        }
        refreshDocument();
    }

    function previewChartPatternsFromLegendFormats(documentRef, panelFormats) {
        var changes = collectAllChartPatternChanges(documentRef, panelFormats);
        var dialog;
        var message;
        var buttons;
        var applyButton;
        var restoreButton;
        var applied = false;

        if (changes.length === 0) {
            return true;
        }

        zoomViewToChartChanges(documentRef, changes);

        dialog = new Window("dialog", "Resultado de tramas");
        dialog.orientation = "column";
        dialog.alignChildren = ["fill", "top"];
        dialog.spacing = 16;
        dialog.margins = 18;

        message = dialog.add(
            "statictext",
            undefined,
            "El gráfico está centrado para revisar las tramas. Usa Ver tramas BdE para aplicar la propuesta, Ver original para comparar con el gráfico importado y Aceptar para mantener el estado que esté visible.",
            {multiline: true}
        );
        message.preferredSize.width = 520;

        buttons = dialog.add("group");
        buttons.alignment = "right";
        applyButton = buttons.add("button", undefined, "Ver tramas BdE");
        restoreButton = buttons.add("button", undefined, "Ver original");
        buttons.add("button", undefined, "Aceptar", {name: "ok"});

        applyButton.onClick = function () {
            if (applied) {
                return;
            }
            applyChartPatternChanges(changes);
            applied = true;
        };

        restoreButton.onClick = function () {
            if (!applied) {
                return;
            }
            restoreChartPatternChanges(changes);
            applied = false;
        };

        positionDialogOnActiveWindow(dialog);
        if (dialog.show() !== 1 && applied) {
            restoreChartPatternChanges(changes);
        }
        return true;
    }

    function setLegend(documentRef, panelNumber, legendNumber, text, format) {
        var legendLayer = getLegendLayer(documentRef, panelNumber);
        var textFrame = getByName(
            legendLayer.textFrames,
            NAMES.legendTextPrefix + legendNumber,
            "el texto de leyenda"
        );
        var graphic = getByName(
            legendLayer.pathItems,
            NAMES.legendGraphicPrefix + legendNumber,
            "el gráfico de leyenda"
        );
        var hasText = text !== "";

        textFrame.contents = text;
        textFrame.hidden = !hasText;
        graphic.hidden = !hasText;

        if (hasText && format) {
            applyLegendFormat(documentRef, graphic, format);
        }
    }

    function measureTextWidthLikeFrame(referenceFrame, text) {
        var parentLayer = referenceFrame.layer;
        var tempFrame = parentLayer.textFrames.add();
        var width = 0;

        try {
            copyCharacterStyle(referenceFrame, tempFrame);
            tempFrame.contents = text;
            app.redraw();
            width = tempFrame.geometricBounds[2] - tempFrame.geometricBounds[0];
        } finally {
            tempFrame.remove();
        }
        return width;
    }

    function applyPanelTitleHangingIndent(titleFrame, prefix, lineCount) {
        var paragraph = titleFrame.paragraphs[0];
        var indentWidth;

        if (lineCount > 1) {
            indentWidth = measureTextWidthLikeFrame(titleFrame, prefix);
            paragraph.paragraphAttributes.leftIndent = indentWidth;
            paragraph.paragraphAttributes.firstLineIndent = -indentWidth;
        } else {
            paragraph.paragraphAttributes.leftIndent = 0;
            paragraph.paragraphAttributes.firstLineIndent = 0;
        }

        // Illustrator no recompone el ajuste de línea del area text al
        // cambiar solo paragraphAttributes; forzar una reasignación del
        // contenido para que la sangría se refleje visualmente.
        titleFrame.contents = titleFrame.contents;
    }

    function fitPanelTitleFrameHeight(titleFrame, lineCount, originalTop, baseHeight) {
        var titleExtraOffset = Math.max(0, lineCount - 1) * PANEL_TITLE_LEADING_PT;
        var newTop;

        if (originalTop === undefined) {
            originalTop = titleFrame.geometricBounds[1];
        }
        if (baseHeight === undefined) {
            baseHeight = Math.abs(originalTop - titleFrame.geometricBounds[3]);
        }

        try {
            titleFrame.textPath.height = baseHeight + titleExtraOffset;
            app.redraw();
            newTop = titleFrame.geometricBounds[1];
            titleFrame.translate(0, originalTop - newTop);
        } catch (error) {
            // Algunas plantillas bloquean la altura del texto; el desplazamiento depende del interlineado.
        }
        return titleExtraOffset;
    }

    function getPanelGraphGuideGroup(documentRef, panelNumber) {
        try {
            return getPanelLayer(documentRef, panelNumber).groupItems.getByName(
                "Texto+flecha Grafico"
            );
        } catch (error) {
            return null;
        }
    }

    function normalizeItemName(name) {
        name = (name || "").toLowerCase();
        name = name.replace(/[áà]/g, "a");
        name = name.replace(/[éè]/g, "e");
        name = name.replace(/[íì]/g, "i");
        name = name.replace(/[óò]/g, "o");
        name = name.replace(/[úù]/g, "u");
        return name;
    }

    function isPanelTitleGuideName(name) {
        return normalizeItemName(name).indexOf("texto+flecha titulo") === 0;
    }

    function isGuidesContainerName(name) {
        return normalizeItemName(name) === "guias";
    }

    function translateGroupContents(group, verticalOffset) {
        var itemIndex;

        for (itemIndex = 0; itemIndex < group.pageItems.length; itemIndex += 1) {
            group.pageItems[itemIndex].translate(0, verticalOffset);
        }
    }

    function translateContainerContents(container, verticalOffset) {
        if (!container) {
            return;
        }
        if (container.typename === "Layer") {
            translateLayerContents(container, verticalOffset);
        } else if (container.typename === "GroupItem") {
            translateGroupContents(container, verticalOffset);
        } else {
            container.translate(0, verticalOffset);
        }
    }

    function findDescendantByName(container, nameMatcher) {
        var index;
        var item;
        var found;

        if (!container) {
            return null;
        }

        if (nameMatcher(container.name)) {
            return container;
        }

        if (container.layers) {
            for (index = 0; index < container.layers.length; index += 1) {
                found = findDescendantByName(container.layers[index], nameMatcher);
                if (found) {
                    return found;
                }
            }
        }

        if (container.pageItems) {
            for (index = 0; index < container.pageItems.length; index += 1) {
                item = container.pageItems[index];
                found = findDescendantByName(item, nameMatcher);
                if (found) {
                    return found;
                }
            }
        }

        return null;
    }

    function movePanelTitleBackgroundGuides(documentRef, panelNumber, verticalOffset) {
        var backgroundName = PANEL_TITLE_GUIDE_BACKGROUND_BY_PANEL[panelNumber];
        var backgroundGroup;
        var guidesContainer;

        if (!backgroundName) {
            return;
        }

        try {
            backgroundGroup = documentRef.groupItems.getByName(backgroundName);
        } catch (error) {
            return;
        }

        guidesContainer = findDescendantByName(backgroundGroup, isGuidesContainerName);
        translateContainerContents(guidesContainer, verticalOffset);
    }

    function movePanelTitleAuxiliaryItemsInLayer(layer, verticalOffset) {
        var layerIndex;
        var itemIndex;
        var item;

        if (isPanelTitleGuideName(layer.name)) {
            translateLayerContents(layer, verticalOffset);
            return;
        }

        for (itemIndex = 0; itemIndex < layer.pageItems.length; itemIndex += 1) {
            item = layer.pageItems[itemIndex];
            if (isPanelTitleGuideName(item.name)) {
                item.translate(0, verticalOffset);
            } else if (item.typename === "GroupItem") {
                movePanelTitleAuxiliaryItemsInGroup(item, verticalOffset);
            }
        }

        for (layerIndex = 0; layerIndex < layer.layers.length; layerIndex += 1) {
            movePanelTitleAuxiliaryItemsInLayer(layer.layers[layerIndex], verticalOffset);
        }
    }

    function movePanelTitleAuxiliaryItemsInGroup(group, verticalOffset) {
        var itemIndex;
        var item;

        for (itemIndex = 0; itemIndex < group.pageItems.length; itemIndex += 1) {
            item = group.pageItems[itemIndex];
            if (isPanelTitleGuideName(item.name)) {
                item.translate(0, verticalOffset);
            } else if (item.typename === "GroupItem") {
                movePanelTitleAuxiliaryItemsInGroup(item, verticalOffset);
            }
        }
    }

    function movePanelTitleDependentItems(documentRef, panelNumber, verticalOffset) {
        var panelLayer = getPanelLayer(documentRef, panelNumber);
        var graphGuideGroup = getPanelGraphGuideGroup(documentRef, panelNumber);
        var states;

        if (verticalOffset === 0) {
            return;
        }

        states = unlockLayerTree(getMainLayer(documentRef));
        try {
            if (graphGuideGroup) {
                graphGuideGroup.translate(0, verticalOffset);
            }
            translateLayerContents(getLegendLayer(documentRef, panelNumber), verticalOffset);
            movePanelTitleAuxiliaryItemsInLayer(panelLayer, verticalOffset);
            movePanelTitleBackgroundGuides(documentRef, panelNumber, verticalOffset);
        } finally {
            restoreGuideStates(states.guides);
            restoreVisibilityStates(states.visibility);
            restoreLockStates(states.locks);
        }
    }

    function setPanelTitle(documentRef, panelNumber, graphNumber, titleText, letterIndex) {
        var titleFrame;
        var titlePrefix;
        var contents;
        var lineCount;
        var titleExtraOffset = 0;
        var titleOriginalTop;
        var titleBaseHeight;
        var states = unlockLayerTree(getMainLayer(documentRef));

        try {
            titleFrame = getPanelTitleFrame(documentRef, panelNumber);
            titleOriginalTop = titleFrame.geometricBounds[1];
            titleBaseHeight = Math.abs(titleOriginalTop - titleFrame.geometricBounds[3]);
            if (titleText === "") {
                titleFrame.contents = "";
                if (!titleFrame.hidden) {
                    titleFrame.hidden = true;
                }
            } else {
                if (titleFrame.hidden) {
                    titleFrame.hidden = false;
                }
                titlePrefix = graphNumber + "." +
                    PANEL_LETTER_ALPHABET[letterIndex === undefined ? panelNumber - 1 : letterIndex] +
                    "  ";
                contents = titlePrefix + titleText;
                lineCount = getTextFrameLineCount(titleFrame, contents);
                if (lineCount > PANEL_TITLE_MAX_LINES) {
                    fail(
                        "El título del Panel " + panelNumber + " ocupa " + lineCount +
                        " líneas. El máximo permitido es " + PANEL_TITLE_MAX_LINES + "."
                    );
                }
                if (titleFrame.contents !== contents) {
                    titleFrame.contents = contents;
                }
                applyPanelTitleHangingIndent(titleFrame, titlePrefix, lineCount);
                titleExtraOffset = fitPanelTitleFrameHeight(
                    titleFrame,
                    lineCount,
                    titleOriginalTop,
                    titleBaseHeight
                );
                movePanelTitleDependentItems(documentRef, panelNumber, -titleExtraOffset);
            }
        } finally {
            restoreGuideStates(states.guides);
            restoreVisibilityStates(states.visibility);
            restoreLockStates(states.locks);
        }
        return titleExtraOffset;
    }

    function setPanelLegendCount(documentRef, panelNumber, legendCount) {
        var legendLayer = getLegendLayer(documentRef, panelNumber);
        var legendNumber;
        var visible;

        for (legendNumber = 1; legendNumber <= MAX_LEGEND_COUNT; legendNumber += 1) {
            visible = legendNumber <= legendCount;
            getByName(
                legendLayer.textFrames,
                NAMES.legendTextPrefix + legendNumber,
                "el texto de leyenda"
            ).hidden = !visible;
            getByName(
                legendLayer.pathItems,
                NAMES.legendGraphicPrefix + legendNumber,
                "el gráfico de leyenda"
            ).hidden = !visible;
        }

        legendLayer.visible = legendCount > 0;
    }

    function createThemeColor(themeColor) {
        var color;

        if (!themeColor) {
            return null;
        }

        if (themeColor.mode === "CMYK") {
            color = new CMYKColor();
            color.cyan = themeColor.values[0];
            color.magenta = themeColor.values[1];
            color.yellow = themeColor.values[2];
            color.black = themeColor.values[3];
            return color;
        }

        if (themeColor.mode === "Lab") {
            color = new LabColor();
            color.l = themeColor.values[0];
            color.a = themeColor.values[1];
            color.b = themeColor.values[2];
            return color;
        }

        return null;
    }

    function setThemeColor(documentRef, themeColor) {
        var color;
        var themeSpot;

        color = createThemeColor(themeColor);
        if (!color) {
            return;
        }

        themeSpot = getByName(documentRef.spots, NAMES.themeSpot, "la tinta del tema");
        themeSpot.color = color;
    }

    function getSourceFrames(documentRef) {
        var sourceLayer = getByName(
            getMainLayer(documentRef).layers,
            NAMES.sourceLayer,
            "la capa de fuentes"
        );
        var frames = [];
        var index;

        for (index = 0; index < sourceLayer.textFrames.length; index += 1) {
            if (sourceLayer.textFrames[index].name.indexOf("FUENTE:") === 0) {
                frames.push(sourceLayer.textFrames[index]);
            }
        }
        if (frames.length === 0) {
            fail("No se encuentran los marcos de texto de FUENTES.");
        }
        return frames;
    }

    function parseSingleSourceInput(text, forceSourcesPlural) {
        var lines = text.split(/\r\n|\r|\n/);
        var sourceText = "";
        var paragraphs = [];
        var index;
        var lineText;

        for (index = 0; index < lines.length; index += 1) {
            if (/^\s*$/.test(lines[index])) {
                continue;
            }
            if (sourceText === "") {
                sourceText = lines[index];
                continue;
            }

            lineText = normalizeSourceLabelText(lines[index], forceSourcesPlural);
            if (!isNewSourceParagraphStart(lineText) &&
                appendSourceContinuation(paragraphs, lineText)) {
                continue;
            }
            paragraphs.push(lineText);
        }

        return {
            sourceText: sourceText,
            paragraphs: paragraphs
        };
    }

    function parseSourceParagraphs(text) {
        var lines = text.split(/\r\n|\r|\n/);
        var result = [];
        var index;
        var lineText;

        for (index = 0; index < lines.length; index += 1) {
            if (/^\s*$/.test(lines[index])) {
                continue;
            }
            lineText = normalizeSourceLabelText(lines[index]);
            if (!isNewSourceParagraphStart(lineText) &&
                appendSourceContinuation(result, lineText)) {
                continue;
            }
            result.push(lineText);
        }
        return result;
    }

    function applyFontToCharacters(textFrame, start, length, font) {
        var index;
        var end = Math.min(start + length, textFrame.characters.length);

        for (index = start; index < end; index += 1) {
            textFrame.characters[index].characterAttributes.textFont = font;
        }
    }

    function fitSourceFrameHeightFromBottom(textFrame) {
        var originalBottom = textFrame.geometricBounds[3];
        var testFrame = textFrame.duplicate();
        var outlinedText = null;
        var measuredHeight;
        var newBottom;

        try {
            testFrame.hidden = false;
            testFrame.textPath.height = 500;
            app.redraw();
            outlinedText = testFrame.createOutline();
            measuredHeight =
                Math.abs(outlinedText.visibleBounds[1] - outlinedText.visibleBounds[3]) +
                millimetersToPoints(SOURCE_HEIGHT_PADDING_MM);
        } finally {
            if (outlinedText) {
                outlinedText.remove();
            } else {
                testFrame.remove();
            }
        }

        textFrame.textPath.height = measuredHeight;
        newBottom = textFrame.geometricBounds[3];
        textFrame.translate(0, originalBottom - newBottom);
    }

    function translateSourceLabel(label) {
        if (scriptLanguage !== "en") {
            return label;
        }
        if (label === "FUENTE:") {
            return "SOURCE:";
        }
        if (label === "FUENTES:") {
            return "SOURCES:";
        }
        return label;
    }

    function getSourceLabelParts(text, forcedSourceLabel) {
        var labelMatch = text.match(/^\s*(FUENTES|FUENTE|SOURCES|SOURCE|NOTAS|NOTA)\s*(:|\.|\s|$)/i);
        var rawLabel = labelMatch ? labelMatch[1].toUpperCase() : "";
        var label = labelMatch ? rawLabel + ":" : "FUENTE:";
        var body = labelMatch ?
            text.substring(labelMatch[0].length).replace(/^\s+/, "") :
            text;

        if (forcedSourceLabel === "FUENTE") {
            label = "FUENTE:";
        } else if (forcedSourceLabel === "FUENTES") {
            label = "FUENTES:";
        }

        return {
            label: translateSourceLabel(label),
            body: body
        };
    }

    function getSourceParagraphLabelParts(text, forceSourcesPlural) {
        var labelMatch = text.match(/^\s*(FUENTES|FUENTE|SOURCES|SOURCE|NOTAS|NOTA)\s*(:|\.|\s|$)/i);
        var rawLabel = labelMatch ? labelMatch[1].toUpperCase() : "";
        var label = labelMatch ? rawLabel + ":" : "";
        var body = labelMatch ?
            text.substring(labelMatch[0].length).replace(/^\s+/, "") :
            text;

        if (forceSourcesPlural) {
            if (rawLabel === "FUENTE" || rawLabel === "SOURCE") {
                label = "FUENTES:";
            }
        } else {
            if (rawLabel === "FUENTES" || rawLabel === "SOURCES") {
                label = "FUENTE:";
            }
        }

        return {
            label: translateSourceLabel(label),
            body: body
        };
    }

    function isSourceLabelParagraph(text) {
        return /^\s*(FUENTES|FUENTE|SOURCES|SOURCE|NOTAS|NOTA)\s*(:|\.|\s|$)/i.test(text);
    }

    function isSourceNoteParagraph(text) {
        return /^\s*(NOTAS|NOTA)\s*(:|\.|\s|$)/i.test(text);
    }

    function isSourceLetterParagraph(text) {
        return /^\s*[a-z](?:\.|\t)(?:[\t ]*)(.*)$/.test(text);
    }

    function isNewSourceParagraphStart(text) {
        return isSourceLabelParagraph(text) || isSourceLetterParagraph(text);
    }

    function appendSourceContinuation(paragraphs, text) {
        var lastIndex = paragraphs.length - 1;

        if (lastIndex >= 0 && isSourceLetterParagraph(paragraphs[lastIndex])) {
            paragraphs[lastIndex] += " " + text.replace(/^\s+/, "");
            return true;
        }
        return false;
    }

    function normalizeSourceLabelText(text, forceSourcesPlural) {
        var labelParts;

        if (!isSourceLabelParagraph(text)) {
            return text;
        }

        labelParts = getSourceParagraphLabelParts(text, forceSourcesPlural);
        return labelParts.label + " " + labelParts.body;
    }

    function getSourceParagraphSeparator(currentParagraph, nextParagraph) {
        if (!nextParagraph) {
            return "";
        }
        if (isSourceNoteParagraph(currentParagraph)) {
            return "\r\r";
        }
        return "\r";
    }

    function setSourceFrameText(textFrame, sourceText, paragraphs, forceSourcesPlural, forcedSourceLabel) {
        var mediumFont = app.textFonts.getByName("Roboto-Medium");
        var lightFont = app.textFonts.getByName("Roboto-Light");
        var sourceParts = getSourceLabelParts(sourceText, forcedSourceLabel);
        var content = sourceParts.label + " " + sourceParts.body;
        var mediumRanges = /^NOTAS?:$/i.test(sourceParts.label) ? [] : [
            {start: 0, length: sourceParts.label.length}
        ];
        var labelParts;
        var paragraphIndex;
        var isLabelParagraph;
        var letterMatch;
        var tabStop;
        var paragraph;
        var paragraphFrameIndexes = [];
        var frameParagraphIndex = 0;
        var firstParagraphIsNote;
        var separator;

        firstParagraphIsNote = paragraphs.length > 0 && isSourceNoteParagraph(paragraphs[0]);
        if (paragraphs.length > 0) {
            separator = firstParagraphIsNote ? "\r" : "\r\r";
            content += separator;
            frameParagraphIndex += separator.length;
        }

        for (paragraphIndex = 0; paragraphIndex < paragraphs.length; paragraphIndex += 1) {
            paragraphFrameIndexes[paragraphIndex] = frameParagraphIndex;
            isLabelParagraph = isSourceLabelParagraph(paragraphs[paragraphIndex]);
            if (isLabelParagraph) {
                labelParts = getSourceParagraphLabelParts(
                    paragraphs[paragraphIndex],
                    forceSourcesPlural
                );
                if (!isSourceNoteParagraph(paragraphs[paragraphIndex])) {
                    mediumRanges.push({start: content.length, length: labelParts.label.length});
                }
                content += labelParts.label + " " + labelParts.body;
            } else {
                letterMatch = paragraphs[paragraphIndex].match(/^([a-z])(?:\.|\t)(?:[\t ]*)(.*)$/);
                if (letterMatch && isSourceLetterParagraph(paragraphs[paragraphIndex])) {
                    mediumRanges.push({start: content.length, length: 1});
                    content += letterMatch[1] + "\t" + letterMatch[2];
                } else {
                    content += paragraphs[paragraphIndex];
                }
            }
            if (paragraphIndex < paragraphs.length - 1) {
                separator = getSourceParagraphSeparator(
                    paragraphs[paragraphIndex],
                    paragraphs[paragraphIndex + 1]
                );
                content += separator;
                frameParagraphIndex += separator.length;
            }
        }

        textFrame.contents = content;
        applyFontToCharacters(textFrame, 0, textFrame.characters.length, lightFont);
        for (paragraphIndex = 0; paragraphIndex < mediumRanges.length; paragraphIndex += 1) {
            applyFontToCharacters(
                textFrame,
                mediumRanges[paragraphIndex].start,
                mediumRanges[paragraphIndex].length,
                mediumFont
            );
        }
        paragraph = textFrame.paragraphs[0];
        paragraph.paragraphAttributes.firstLineIndent = 0;
        paragraph.paragraphAttributes.leftIndent = 0;
        paragraph.paragraphAttributes.tabStops = [];

        for (paragraphIndex = 0; paragraphIndex < textFrame.paragraphs.length; paragraphIndex += 1) {
            paragraph = textFrame.paragraphs[paragraphIndex];
            paragraph.paragraphAttributes.firstLineIndent = 0;
            paragraph.paragraphAttributes.leftIndent = 0;
            paragraph.paragraphAttributes.tabStops = [];
        }

        for (paragraphIndex = 0; paragraphIndex < paragraphs.length; paragraphIndex += 1) {
            paragraph = textFrame.paragraphs[paragraphFrameIndexes[paragraphIndex]];
            isLabelParagraph = isSourceLabelParagraph(paragraphs[paragraphIndex]);

            if (isLabelParagraph) {
                paragraph.paragraphAttributes.firstLineIndent = 0;
                paragraph.paragraphAttributes.leftIndent = 0;
                paragraph.paragraphAttributes.tabStops = [];
            } else {
                letterMatch = paragraph.contents.match(/^([a-zA-Z])\t/);
                if (letterMatch) {
                    paragraph.paragraphAttributes.firstLineIndent = -8.5;
                    paragraph.paragraphAttributes.leftIndent = 8.5;
                    tabStop = new TabStopInfo();
                    tabStop.position = SOURCE_TAB_POSITION;
                    tabStop.alignment = TabStopAlignment.Left;
                    paragraph.paragraphAttributes.tabStops = [tabStop];
                } else {
                    paragraph.paragraphAttributes.firstLineIndent = 0;
                    paragraph.paragraphAttributes.leftIndent = 0;
                    paragraph.paragraphAttributes.tabStops = [];
                }
            }
        }

        fitSourceFrameHeightFromBottom(textFrame);
    }

    function getStoredInfoOffset(infoGroup) {
        var match;

        try {
            match = String(infoGroup.note || "").match(/BDE_INFO_OFFSET_MM=([-0-9.]+)/);
            if (match) {
                return parseFloat(match[1]);
            }
        } catch (error) {}
        return 0;
    }

    function setStoredInfoOffset(infoGroup, offsetMillimeters) {
        try {
            infoGroup.note = "BDE_INFO_OFFSET_MM=" + offsetMillimeters;
        } catch (error) {}
    }

    function setInfoGroupOffset(infoGroup, desiredOffsetMillimeters) {
        var currentOffset = getStoredInfoOffset(infoGroup);
        var delta = desiredOffsetMillimeters - currentOffset;

        if (Math.abs(delta) > 0.001) {
            translateItemTemporarilyUnlocked(
                infoGroup,
                millimetersToPoints(delta),
                0
            );
        }
        setStoredInfoOffset(infoGroup, desiredOffsetMillimeters);
    }

    function configureDownloadButton(documentRef, sourceButtonMode) {
        var sourceLayer = getByName(
            getMainLayer(documentRef).layers,
            NAMES.sourceLayer,
            "la capa de fuentes"
        );
        var mode = sourceButtonMode || "none";
        var noButtonFrame = getByName(
            sourceLayer.textFrames,
            "FUENTE: SIN BOTÓN",
            "el marco de fuente sin botón"
        );
        var downloadFrame = getByName(
            sourceLayer.textFrames,
            "FUENTE: DESCARGA",
            "el marco de fuente con descarga"
        );
        var infoFrame = getByName(
            sourceLayer.textFrames,
            "FUENTE: + INFO",
            "el marco de fuente con información"
        );
        var useEnglishDownloadButton = scriptLanguage === "en";
        var downloadGroup = getByName(
            sourceLayer.groupItems,
            useEnglishDownloadButton ? "DOWNLOAD" : "DESCARGAR",
            useEnglishDownloadButton ? "el botón Download" : "el botón Descargar"
        );
        var otherDownloadGroup = getByName(
            sourceLayer.groupItems,
            useEnglishDownloadButton ? "DESCARGAR" : "DOWNLOAD",
            useEnglishDownloadButton ? "el botón Descargar" : "el botón Download"
        );
        var infoGroup = getByName(
            sourceLayer.groupItems,
            "+INFO",
            "el botón Más información"
        );
        var showInfoGroup = mode === "info" || mode === "downloadInfo";

        noButtonFrame.hidden = mode !== "none";
        downloadFrame.hidden = !(mode === "download" || mode === "info");
        infoFrame.hidden = mode !== "downloadInfo";

        downloadGroup.hidden = !(mode === "download" || mode === "downloadInfo");
        otherDownloadGroup.hidden = true;
        infoGroup.hidden = false;
        setInfoGroupOffset(
            infoGroup,
            mode === "info" ? SOURCE_INFO_ONLY_OFFSET_MM : 0
        );
        infoGroup.hidden = !showInfoGroup;

        if (mode === "download" || mode === "info") {
            downloadFrame.textPath.width = millimetersToPoints(160);
        }
    }

    function getVisibleSourceFrame(documentRef) {
        var sourceFrames = getSourceFrames(documentRef);
        var index;

        for (index = 0; index < sourceFrames.length; index += 1) {
            if (!sourceFrames[index].hidden) {
                return sourceFrames[index];
            }
        }
        fail("No se encuentra un marco visible en la capa FUENTES.");
    }

    function addVisibleSourceButtonIfPresent(sourceLayer, items, buttonName) {
        var buttonGroup;

        try {
            buttonGroup = sourceLayer.groupItems.getByName(buttonName);
            if (!buttonGroup.hidden) {
                items.push(buttonGroup);
            }
        } catch (error) {}
    }

    function getVisibleSourcePositionItems(documentRef) {
        var sourceLayer = getByName(
            getMainLayer(documentRef).layers,
            NAMES.sourceLayer,
            "la capa de fuentes"
        );
        var items = [getVisibleSourceFrame(documentRef)];

        addVisibleSourceButtonIfPresent(sourceLayer, items, "DESCARGAR");
        addVisibleSourceButtonIfPresent(sourceLayer, items, "+INFO");
        addVisibleSourceButtonIfPresent(sourceLayer, items, "DOWNLOAD");
        return items;
    }

    function positionSourcesAfterLastPanel(documentRef, panelCount) {
        var sourceLayer = getByName(
            getMainLayer(documentRef).layers,
            NAMES.sourceLayer,
            "la capa de fuentes"
        );
        var lastPanelBounds = getLayerContentBounds(getPanelLayer(documentRef, panelCount));
        var sourceBounds = getItemsBounds(getVisibleSourcePositionItems(documentRef));
        var desiredSourceTop;
        var verticalOffset;

        if (!lastPanelBounds || !sourceBounds) {
            return false;
        }

        desiredSourceTop = lastPanelBounds[3] - millimetersToPoints(SOURCE_PANEL_GAP_MM);
        verticalOffset = desiredSourceTop - sourceBounds[1];
        translateLayerContents(sourceLayer, verticalOffset);
        return true;
    }

    function setSourceText(documentRef, allText, sourceButtonMode, forceSourcesPlural) {
        var sourceFrames = getSourceFrames(documentRef);
        var parsedText = parseSingleSourceInput(allText, forceSourcesPlural);
        var forcedSourceLabel = forceSourcesPlural ? "FUENTES" : "FUENTE";
        var index;

        configureDownloadButton(documentRef, sourceButtonMode);
        for (index = 0; index < sourceFrames.length; index += 1) {
            setSourceFrameText(
                sourceFrames[index],
                parsedText.sourceText,
                parsedText.paragraphs,
                forceSourcesPlural,
                forcedSourceLabel
            );
        }
    }

    function validateTemplate(documentRef) {
        var panelNumber;
        getMainLayer(documentRef);
        getByName(documentRef.layers, NAMES.boxLayer, "la capa de recuadro");
        for (panelNumber = 1; panelNumber <= 3; panelNumber += 1) {
            getPanelLayer(documentRef, panelNumber);
            getLegendLayer(documentRef, panelNumber);
        }
        getByName(documentRef.spots, NAMES.themeSpot, "la tinta del tema");
    }

    function showInitialDialog() {
        var dialog = new Window("dialog", "Generador de gráficos BdE");
        var typePanel = dialog.add("panel", undefined, "Tipo de ilustración");
        var themePanel = dialog.add("panel", undefined, "Tipo de documento");
        var languagePanel = dialog.add("panel", undefined, "Idioma");
        var panelGroup = dialog.add("panel", undefined, "Número de paneles");
        var buttons = dialog.add("group");
        var graphCheck;
        var tableCheck;
        var boxCheck;
        var illustrationChecks = [];
        var themeNames = [
            "Azul",
            "Rojo/Cobre",
            "Naranja (DO)",
            "Celeste",
            "Gris",
            "Marrón (Biblioteca)"
        ];
        var themeChecks = [];
        var themeIndex;
        var spanishCheck;
        var englishCheck;
        var panelChecks = [];
        var panelNumber;

        dialog.orientation = "column";
        dialog.alignChildren = ["fill", "top"];
        dialog.spacing = 18;
        dialog.margins = 18;

        typePanel.orientation = "row";
        typePanel.alignChildren = ["left", "center"];
        typePanel.margins = 14;
        graphCheck = typePanel.add("radiobutton", undefined, "Gráfico");
        tableCheck = typePanel.add("radiobutton", undefined, "Cuadro");
        boxCheck = typePanel.add("radiobutton", undefined, "Recuadro");
        illustrationChecks = [graphCheck, tableCheck, boxCheck];

        function selectIllustration(selectedIndex) {
            panelGroup.visible = selectedIndex === 0;
            dialog.layout.layout(true);
        }

        graphCheck.onClick = function () {
            selectIllustration(0);
        };
        tableCheck.onClick = function () {
            selectIllustration(1);
        };
        boxCheck.onClick = function () {
            selectIllustration(2);
        };
        themePanel.orientation = "column";
        themePanel.alignChildren = ["left", "center"];
        themePanel.margins = 14;

        for (themeIndex = 0; themeIndex < themeNames.length; themeIndex += 1) {
            themeChecks.push(themePanel.add("radiobutton", undefined, themeNames[themeIndex]));
        }
        themeChecks[0].value = true;

        languagePanel.orientation = "row";
        languagePanel.alignChildren = ["left", "center"];
        languagePanel.margins = 14;
        spanishCheck = languagePanel.add("radiobutton", undefined, "Español");
        englishCheck = languagePanel.add("radiobutton", undefined, "Inglés");
        spanishCheck.value = true;

        panelGroup.orientation = "column";
        panelGroup.alignChildren = ["left", "center"];
        panelGroup.margins = 14;
        var panelChecksGroup = panelGroup.add("group");
        panelChecksGroup.orientation = "row";
        panelChecksGroup.alignChildren = ["left", "center"];

        for (panelNumber = 1; panelNumber <= 3; panelNumber += 1) {
            panelChecks.push(panelChecksGroup.add("radiobutton", undefined, String(panelNumber)));
        }
        panelChecks[2].value = true;

        buttons.alignment = "right";
        buttons.add("button", undefined, "Cancelar", {name: "cancel"});
        buttons.add("button", undefined, "Continuar", {name: "ok"});
        graphCheck.value = true;
        selectIllustration(0);

        positionDialogOnActiveWindow(dialog);
        if (dialog.show() !== 1) {
            return null;
        }

        for (themeIndex = 0; themeIndex < themeChecks.length; themeIndex += 1) {
            if (themeChecks[themeIndex].value) {
                break;
            }
        }

        return {
            illustrationType: graphCheck.value ? "Gráfico" :
                (tableCheck.value ? "Cuadro" : "Recuadro"),
            themeType: themeNames[themeIndex],
            language: englishCheck.value ? "en" : "es",
            panelCount: panelChecks[0].value ? 1 : (panelChecks[1].value ? 2 : 3)
        };
    }

    function showTitleDialog(illustrationType) {
        var illustrationLabel = illustrationType === "Cuadro" ? "cuadro" : "gráfico";
        var dialog = new Window("dialog", "Título del " + illustrationLabel);
        var numberGroup = dialog.add("group");
        var titleGroup = dialog.add("group");
        var buttons = dialog.add("group");
        var numberField;
        var titleField;

        dialog.orientation = "column";
        dialog.alignChildren = ["fill", "top"];
        dialog.spacing = 18;
        dialog.margins = 18;

        numberGroup.add("statictext", undefined, "Número de " + illustrationLabel + ":");
        numberField = numberGroup.add("edittext", undefined, "");
        numberField.characters = 16;

        titleGroup.orientation = "column";
        titleGroup.alignChildren = ["fill", "top"];
        titleGroup.add("statictext", undefined, "Título:");
        titleField = titleGroup.add("edittext", undefined, "", {
            multiline: true,
            scrolling: true
        });
        titleField.preferredSize = [420, 90];

        buttons.alignment = "right";
        buttons.add("button", undefined, "Cancelar", {name: "cancel"});
        buttons.add("button", undefined, "Continuar", {name: "ok"});

        positionDialogOnActiveWindow(dialog);
        if (dialog.show() !== 1) {
            return null;
        }

        if (numberField.text === "" || titleField.text === "") {
            alert("Introduce el número de " + illustrationLabel + " y el título.");
            return showTitleDialog(illustrationType);
        }

        return {
            graphNumber: numberField.text,
            title: titleField.text
        };
    }

    function showPanelConfigurationDialog(panelNumber, showLetterSelector) {
        var dialog = new Window("dialog", "Configuración del Panel " + panelNumber);
        var titleGroup = dialog.add("group");
        var letterPanel;
        var optionsGroup;
        var legendPanel;
        var buttons;
        var titleField;
        var unitsField;
        var unitsText;
        var legendChecks = [];
        var legendNumber;
        var letterChecks = [];
        var letterIndex;
        var result;
        var continueButton;
        var validationPassed = false;

        dialog.orientation = "column";
        dialog.alignChildren = ["fill", "top"];
        dialog.spacing = 18;
        dialog.margins = 18;

        titleGroup.add("statictext", undefined, "Título del panel:");
        titleField = titleGroup.add("edittext", undefined, "");
        titleField.characters = 38;

        if (showLetterSelector) {
            letterPanel = dialog.add(
                "panel",
                undefined,
                "Numerar paneles a partir de la letra"
            );
            letterPanel.orientation = "row";
            letterPanel.alignChildren = ["left", "center"];
            letterPanel.margins = 14;
            for (letterIndex = 0; letterIndex < PANEL_START_LETTER_OPTIONS.length; letterIndex += 1) {
                letterChecks.push(
                    letterPanel.add(
                        "radiobutton",
                        undefined,
                        PANEL_START_LETTER_OPTIONS[letterIndex]
                    )
                );
            }
        }

        optionsGroup = dialog.add("group");
        optionsGroup.orientation = "row";
        optionsGroup.alignChildren = ["left", "center"];
        optionsGroup.add("statictext", undefined, "Unidades:");
        unitsField = optionsGroup.add("edittext", undefined, "");
        unitsField.characters = 24;

        legendPanel = dialog.add("panel", undefined, "Número de leyendas");
        legendPanel.orientation = "row";
        legendPanel.alignChildren = ["left", "center"];
        legendPanel.margins = 14;

        for (legendNumber = 0; legendNumber <= MAX_LEGEND_COUNT; legendNumber += 1) {
            legendChecks.push(
                legendPanel.add("radiobutton", undefined, String(legendNumber))
            );
        }
        legendChecks[MAX_LEGEND_COUNT].value = true;

        buttons = dialog.add("group");
        buttons.alignment = "right";
        buttons.add("button", undefined, "Cancelar", {name: "cancel"});
        continueButton = buttons.add("button", undefined, "Continuar");

        continueButton.onClick = function () {
            var letterSelected = false;

            if (showLetterSelector) {
                for (letterIndex = 0; letterIndex < letterChecks.length; letterIndex += 1) {
                    if (letterChecks[letterIndex].value) {
                        letterSelected = true;
                        break;
                    }
                }
                if (!letterSelected) {
                    alert("Selecciona la letra por la que deben empezar los paneles.");
                    return;
                }
            }
            validationPassed = true;
            dialog.close(1);
        };

        positionDialogOnActiveWindow(dialog);
        if (dialog.show() !== 1 || !validationPassed) {
            return null;
        }

        for (legendNumber = 0; legendNumber <= MAX_LEGEND_COUNT; legendNumber += 1) {
            if (legendChecks[legendNumber].value) {
                unitsText = unitsField.text.replace(/^\s+|\s+$/g, "");
                result = {
                    title: titleField.text,
                    units: unitsText,
                    hasUnits: unitsText !== "",
                    legendCount: legendNumber,
                    startLetterIndex: 0
                };
                if (showLetterSelector) {
                    for (letterIndex = 0; letterIndex < letterChecks.length; letterIndex += 1) {
                        if (letterChecks[letterIndex].value) {
                            result.startLetterIndex = PANEL_START_LETTER_INDICES[letterIndex];
                            break;
                        }
                    }
                }
                return result;
            }
        }

        return null;
    }

    function splitLegendTexts(text) {
        var lines = text.split(/\r\n|\r|\n/);

        while (lines.length > 0 && lines[lines.length - 1] === "") {
            lines.pop();
        }
        return lines;
    }

    function getLegendFormatIndex(label) {
        var index;

        for (index = 0; index < LEGEND_FORMATS.length; index += 1) {
            if (LEGEND_FORMATS[index].label === label) {
                return index;
            }
        }
        fail('No se encuentra el formato de leyenda "' + label + '".');
    }

    function showLegendDialog(graphNumber, panelNumber, panelTitle, legendCount) {
        var dialog = new Window("dialog", "Leyendas del Panel " + panelNumber);
        var identification = dialog.add("panel", undefined, "Identificación");
        var contentGroup = dialog.add("group");
        var formatGroup = contentGroup.add("panel", undefined, "Formato");
        var textGroup = contentGroup.add("panel", undefined, "Textos de leyenda");
        var buttons = dialog.add("group");
        var formatDropdowns = [];
        var formatLabels = [];
        var legendTextField;
        var legendNumber;
        var texts;
        var formats = [];
        var validationPassed = false;
        var lineBlackIndex = getLegendFormatIndex("Línea - Negro");

        dialog.orientation = "column";
        dialog.alignChildren = ["fill", "top"];
        dialog.spacing = 16;
        dialog.margins = 18;

        identification.orientation = "column";
        identification.alignChildren = ["left", "top"];
        identification.margins = 14;
        identification.add("statictext", undefined, "Gráfico " + graphNumber);
        identification.add(
            "statictext",
            undefined,
            graphNumber + "." + ["a", "b", "c"][panelNumber - 1] +
                (panelTitle === "" ? "  (sin título)" : "  " + panelTitle),
            {multiline: true}
        );

        contentGroup.orientation = "row";
        contentGroup.alignChildren = ["fill", "fill"];
        contentGroup.spacing = 12;

        formatGroup.orientation = "column";
        formatGroup.alignChildren = ["fill", "top"];
        formatGroup.margins = 14;

        for (legendNumber = 0; legendNumber < LEGEND_FORMATS.length; legendNumber += 1) {
            formatLabels.push(LEGEND_FORMATS[legendNumber].label);
        }

        for (legendNumber = 1; legendNumber <= legendCount; legendNumber += 1) {
            formatDropdowns.push(
                formatGroup.add("dropdownlist", undefined, formatLabels)
            );
            formatDropdowns[formatDropdowns.length - 1].selection = lineBlackIndex;
            formatDropdowns[formatDropdowns.length - 1].preferredSize.width = 190;
        }

        textGroup.orientation = "column";
        textGroup.alignChildren = ["fill", "fill"];
        textGroup.margins = 14;
        textGroup.add(
            "statictext",
            undefined,
            "Introduce una leyenda por línea, en el mismo orden que los formatos."
        );
        legendTextField = textGroup.add("edittext", undefined, "", {
            multiline: true,
            scrolling: true
        });
        legendTextField.preferredSize = [420, Math.max(100, legendCount * 30)];

        buttons.alignment = "right";
        buttons.add("button", undefined, "Cancelar", {name: "cancel"});
        var continueButton = buttons.add("button", undefined, "Continuar");

        continueButton.onClick = function () {
            var index;

            texts = splitLegendTexts(legendTextField.text);
            if (texts.length !== legendCount) {
                alert(
                    "El Panel " + panelNumber + " tiene " + legendCount +
                    " leyendas. Introduce exactamente " + legendCount +
                    " líneas de texto."
                );
                return;
            }

            for (index = 0; index < texts.length; index += 1) {
                if (texts[index] === "") {
                    alert("La leyenda " + (index + 1) + " no puede estar vacía.");
                    return;
                }
            }

            validationPassed = true;
            dialog.close(1);
        };

        positionDialogOnActiveWindow(dialog);
        if (dialog.show() !== 1 || !validationPassed) {
            return null;
        }

        for (legendNumber = 0; legendNumber < texts.length; legendNumber += 1) {
            formats.push(LEGEND_FORMATS[formatDropdowns[legendNumber].selection.index]);
        }

        return {
            texts: texts,
            formats: formats
        };
    }

    function showSourceDialog() {
        var dialog = new Window("dialog", "Fuente y notas");
        var textGroup = dialog.add("group");
        var optionsGroup = dialog.add("group");
        var buttons = dialog.add("group");
        var textField;
        var defaultSourceCheck;
        var sourceSingularCheck;
        var sourcePluralCheck;
        var downloadCheck;
        var infoCheck;
        var downloadInfoCheck;
        var buttonModeChecks = [];
        var downloadGroup;
        var validationPassed = false;
        var sourceSingularLabel = scriptLanguage === "en" ? "SOURCE" : "FUENTE";
        var sourcePluralLabel = scriptLanguage === "en" ? "SOURCES" : "FUENTES";
        var defaultSourceLabel = scriptLanguage === "en" ?
            "SOURCE: Banco de España." :
            "FUENTE: Banco de España.";

        dialog.orientation = "column";
        dialog.alignChildren = ["fill", "top"];
        dialog.spacing = 18;
        dialog.margins = 18;

        textGroup.orientation = "column";
        textGroup.alignChildren = ["fill", "top"];
        textGroup.add(
            "statictext",
            undefined,
            "Escribe la fuente y las notas, una línea por párrafo."
        );
        textField = textGroup.add("edittext", undefined, "", {
            multiline: true,
            scrolling: true
        });
        textField.preferredSize = [480, 210];

        optionsGroup.orientation = "row";
        optionsGroup.alignChildren = ["left", "center"];
        defaultSourceCheck = optionsGroup.add(
            "checkbox",
            undefined,
            defaultSourceLabel
        );
        defaultSourceCheck.value = false;
        sourceSingularCheck = optionsGroup.add("checkbox", undefined, sourceSingularLabel);
        sourceSingularCheck.value = false;
        sourcePluralCheck = optionsGroup.add("checkbox", undefined, sourcePluralLabel);
        sourcePluralCheck.value = false;

        function updateSourceHeadingVisibility() {
            var showHeadingChecks = !defaultSourceCheck.value;

            sourceSingularCheck.visible = showHeadingChecks;
            sourcePluralCheck.visible = showHeadingChecks;
            if (defaultSourceCheck.value) {
                sourceSingularCheck.value = false;
                sourcePluralCheck.value = false;
            }
            dialog.layout.layout(true);
        }

        function selectSourceHeading(usePlural) {
            sourceSingularCheck.value = !usePlural;
            sourcePluralCheck.value = usePlural;
        }

        defaultSourceCheck.onClick = function () {
            if (defaultSourceCheck.value) {
                textField.text = defaultSourceLabel;
            }
            updateSourceHeadingVisibility();
        };
        sourceSingularCheck.onClick = function () {
            defaultSourceCheck.value = false;
            selectSourceHeading(false);
            updateSourceHeadingVisibility();
        };
        sourcePluralCheck.onClick = function () {
            defaultSourceCheck.value = false;
            selectSourceHeading(true);
            updateSourceHeadingVisibility();
        };
        updateSourceHeadingVisibility();

        downloadGroup = dialog.add("group");
        downloadGroup.orientation = "row";
        downloadGroup.alignChildren = ["left", "center"];
        var downloadWordLabel = scriptLanguage === "en" ? "Download" : "Descargar";
        downloadCheck = downloadGroup.add(
            "checkbox",
            undefined,
            "Añadir botón " + downloadWordLabel
        );
        downloadCheck.value = false;
        infoCheck = downloadGroup.add("checkbox", undefined, "+Info");
        infoCheck.value = false;
        downloadInfoCheck = downloadGroup.add(
            "checkbox",
            undefined,
            "Añadir " + downloadWordLabel + " + +Info"
        );
        downloadInfoCheck.value = false;
        buttonModeChecks = [downloadCheck, infoCheck, downloadInfoCheck];

        function selectSourceButtonMode(selectedCheck) {
            var index;

            for (index = 0; index < buttonModeChecks.length; index += 1) {
                if (buttonModeChecks[index] !== selectedCheck) {
                    buttonModeChecks[index].value = false;
                }
            }
        }

        function getSourceButtonMode() {
            if (downloadInfoCheck.value) {
                return "downloadInfo";
            }
            if (infoCheck.value) {
                return "info";
            }
            if (downloadCheck.value) {
                return "download";
            }
            return "none";
        }

        downloadCheck.onClick = function () {
            if (downloadCheck.value) {
                selectSourceButtonMode(downloadCheck);
            }
        };
        infoCheck.onClick = function () {
            if (infoCheck.value) {
                selectSourceButtonMode(infoCheck);
            }
        };
        downloadInfoCheck.onClick = function () {
            if (downloadInfoCheck.value) {
                selectSourceButtonMode(downloadInfoCheck);
            }
        };

        buttons.alignment = "right";
        buttons.add("button", undefined, "Cancelar", {name: "cancel"});
        var continueButton = buttons.add("button", undefined, "Aplicar");

        continueButton.onClick = function () {
            if (textField.text === "") {
                alert("Introduce el texto de la fuente.");
                return;
            }
            if (!defaultSourceCheck.value &&
                !sourceSingularCheck.value &&
                !sourcePluralCheck.value) {
                alert('Selecciona si el encabezado debe ser "' + sourceSingularLabel +
                    '" o "' + sourcePluralLabel + '".');
                return;
            }
            validationPassed = true;
            dialog.close(1);
        };

        positionDialogOnActiveWindow(dialog);
        if (dialog.show() !== 1 || !validationPassed) {
            return null;
        }

        return {
            text: textField.text,
            forceSourcesPlural: defaultSourceCheck.value ? false : sourcePluralCheck.value,
            buttonMode: getSourceButtonMode()
        };
    }

    function run() {
        var documentRef;
        var values;
        var titleValues;
        var titleLineCount;
        var panelValues;
        var panelNumber;
        var isContinuationTitle;
        var startLetterIndex = 0;
        var panelConfigurations = [];
        var panelLegendFormats = [];
        var legendValues;
        var legendNumber;
        var sourceValues;
        var unitsFrame;

        if (app.documents.length === 0) {
            alert("Abre primero Plantilla Pruebas.ait y ejecuta de nuevo el script.");
            return;
        }

        documentRef = app.activeDocument;

        try {
            validateTemplate(documentRef);
            values = showInitialDialog();
            if (!values) {
                return;
            }
            scriptLanguage = values.language;

            setIllustrationType(documentRef, values.illustrationType);
            setThemeColor(documentRef, THEME_COLORS[values.themeType]);
            refreshDocument();

            if (values.illustrationType === "Recuadro") {
                return;
            }

            setPanelCount(
                documentRef,
                values.illustrationType === "Cuadro" ? 0 : values.panelCount
            );
            refreshDocument();

            titleValues = showTitleDialog(values.illustrationType);
            if (!titleValues) {
                return;
            }

            titleLineCount = setMainTitle(
                documentRef,
                values.illustrationType,
                titleValues.graphNumber,
                titleValues.title
            );

            if (values.illustrationType === "Cuadro") {
                refreshDocument();
                sourceValues = showSourceDialog();
                if (!sourceValues) {
                    return;
                }
                setSourceText(
                    documentRef,
                    sourceValues.text,
                    sourceValues.buttonMode,
                    sourceValues.forceSourcesPlural
                );
                refreshDocument();
                showPreSaveChecklist(documentRef);
                return;
            }

            movePanelsForTitle(documentRef, titleLineCount, values.panelCount);
            refreshDocument();

            isContinuationTitle = titleHasContinuationSuffix(titleValues.title);

            for (panelNumber = 1; panelNumber <= values.panelCount; panelNumber += 1) {
                panelValues = showPanelConfigurationDialog(
                    panelNumber,
                    panelNumber === 1 && isContinuationTitle
                );
                if (!panelValues) {
                    return;
                }
                if (panelNumber === 1) {
                    startLetterIndex = panelValues.startLetterIndex || 0;
                }

                panelValues.titleExtraOffset = setPanelTitle(
                    documentRef,
                    panelNumber,
                    titleValues.graphNumber,
                    panelValues.title,
                    startLetterIndex + panelNumber - 1
                );
                setPanelLegendCount(
                    documentRef,
                    panelNumber,
                    panelValues.legendCount
                );
                panelConfigurations.push(panelValues);
                refreshDocument();
            }

            removePanelUnitsForAllPanels(documentRef, values.panelCount);
            if (!placePanelArtwork(
                documentRef,
                values.panelCount,
                panelConfigurations,
                titleLineCount
            )) {
                return;
            }
            refreshDocument();

            for (panelNumber = 1; panelNumber <= values.panelCount; panelNumber += 1) {
                panelValues = panelConfigurations[panelNumber - 1];
                if (panelValues.legendCount === 0) {
                    removeExistingPanelUnitsFrame(documentRef, panelNumber);
                    positionPanelArtworkForInput(
                        documentRef,
                        panelNumber,
                        titleLineCount,
                        panelConfigurations
                    );
                    unitsFrame = setPanelUnits(documentRef, panelNumber, panelConfigurations);
                    focusViewOnBounds(
                        documentRef,
                        getPanelFocusBounds(documentRef, panelNumber, panelValues.legendCount),
                        PANEL_VIEW_MARGIN_MM
                    );
                    refreshDocument();
                    showPanelUnitsAdjustmentDialog(unitsFrame, panelValues, panelNumber);
                    continue;
                }

                preparePanelForLegendInput(
                    documentRef,
                    panelNumber,
                    titleLineCount,
                    panelConfigurations
                );

                legendValues = showLegendDialog(
                    titleValues.graphNumber,
                    panelNumber,
                    panelValues.title,
                    panelValues.legendCount
                );
                if (!legendValues) {
                    return;
                }

                for (legendNumber = 1; legendNumber <= panelValues.legendCount; legendNumber += 1) {
                    setLegend(
                        documentRef,
                        panelNumber,
                        legendNumber,
                        legendValues.texts[legendNumber - 1],
                        legendValues.formats[legendNumber - 1]
                    );
                }
                layoutPanelLegends(
                    documentRef,
                    panelNumber,
                    panelValues.legendCount
                );
                panelLegendFormats[panelNumber - 1] = legendValues.formats;
                refreshDocument();
            }

            setPanelUnitsForAllPanels(
                documentRef,
                values.panelCount,
                panelConfigurations
            );
            refreshDocument();

            sourceValues = showSourceDialog();
            if (!sourceValues) {
                return;
            }
            setSourceText(
                documentRef,
                sourceValues.text,
                sourceValues.buttonMode,
                sourceValues.forceSourcesPlural
            );
            positionSourcesAfterLastPanel(documentRef, values.panelCount);
            refreshDocument();
            if (!previewChartPatternsFromLegendFormats(documentRef, panelLegendFormats)) {
                return;
            }
            refreshDocument();
            showPreSaveChecklist(documentRef);
        } catch (error) {
            alert("No se pudo aplicar la configuración:\n" + error.message);
        }
    }

    run();
}());
