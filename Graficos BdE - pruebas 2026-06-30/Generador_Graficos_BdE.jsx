#target illustrator

/*
 * Base modular del generador de gráficos BdE.
 *
 * Personaliza el tipo de ilustración y el color del tema. Si se elige Gráfico,
 * continúa solicitando los datos específicos del gráfico.
 */

(function () {
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
    var SOURCE_TAB_POSITION = 8.50393962860107;
    var SOURCE_HEIGHT_PADDING_MM = 1.5;
    var CHART_PATTERN_MIN_AREA_MM2 = 3;
    var CHART_PATTERN_VIEW_MARGIN_MM = 18;
    var PANEL_GRAPH_LEFT_MM = 3;
    var PANEL_GRAPH_UNIT_OFFSET_MM = 3.5;
    var PANEL_GRAPH_GAP_MM = 8.5;
    var SOURCE_PANEL_GAP_MM = 5;
    var PANEL_TITLE_TO_GRAPH_GAP_MM = [7.377, 7.415, 7.323];
    var PANEL_GRAPH_START_WITH_TITLE = [-67.53, -81.81, -91.47];
    var PANEL_GRAPH_START_WITHOUT_TITLE = [-50.57, -64.85, -74.51];
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
        {label: "Marcador - Cuadrado", type: "brush", name: "Marcador Cuadrado"},
        {label: "Marcador - Triángulo", type: "brush", name: "Marcados Triángulo"},
        {label: "Marcador - Redondo", type: "brush", name: "Marcador Redondo"},
        {label: "Marcador - Línea", type: "brush", name: "Marcador Linea"},
        {label: "Marcador - Diamante", type: "brush", name: "Marcador Diamante"},
        {label: "Marcador - Línea 2", type: "brush", name: "Marcador Linea 2"},
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
        {label: "Trama - Marrón", type: "style", name: "Marron trama"}
    ];

    var THEME_COLORS = {
        "Documento DO": {
            mode: "CMYK",
            values: [9.18, 71.85, 98.2, 1.36]
        },
        "Biblioteca": {
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

    function decodeBase64ToBinary(base64Text) {
        var alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";
        var output = "";
        var buffer = 0;
        var bits = 0;
        var index;
        var character;
        var value;

        for (index = 0; index < base64Text.length; index += 1) {
            character = base64Text.charAt(index);
            if (character === "=") {
                break;
            }
            value = alphabet.indexOf(character);
            if (value < 0) {
                continue;
            }
            buffer = (buffer << 6) | value;
            bits += 6;
            if (bits >= 8) {
                bits -= 8;
                output += String.fromCharCode((buffer >> bits) & 255);
            }
        }
        return output;
    }

    function getDownloadIconFile() {
        var iconFile = File(Folder.temp.fsName + "/bde_download_icon_v2.png");

        if (!iconFile.exists) {
            iconFile.encoding = "BINARY";
            iconFile.open("w");
            iconFile.write(decodeBase64ToBinary(DOWNLOAD_ICON_PNG_BASE64));
            iconFile.close();
        }
        return iconFile;
    }

    function addDownloadIcon(parent) {
        var image;

        try {
            image = parent.add("image", undefined, getDownloadIconFile());
            image.preferredSize = [38, 38];
            image.helpTip = "Botón Descargar";
        } catch (error) {
            parent.add("statictext", undefined, "↓");
        }
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
                    !/^Texto leyenda [1-6]$/.test(item.name || "")
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
            guides: []
        };

        function unlockLayer(layerToUnlock) {
            var layerIndex;
            var itemIndex;

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
        return /^Leyenda [1-6]$/.test(item.name || "") ||
            /^Texto leyenda [1-6]$/.test(item.name || "");
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
                !isPanelTitleItem(item, titleFrame)
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

        if (artworkGroup) {
            items.push(artworkGroup);
        }
        if (titleFrame && !titleFrame.hidden) {
            items.push(titleFrame);
        }
        for (index = 0; index < legendItems.length; index += 1) {
            items.push(legendItems[index]);
        }
        return getItemsBounds(items);
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
        view.centerPoint = [
            (bounds[0] + bounds[2]) / 2,
            (bounds[1] + bounds[3]) / 2
        ];
        viewBounds = view.bounds;
        viewWidth = viewBounds[2] - viewBounds[0];
        viewHeight = viewBounds[1] - viewBounds[3];
        zoom = Math.min(viewWidth / width, viewHeight / height) * 0.9;
        if (zoom > 0) {
            view.zoom = zoom;
        }
    }

    function preparePanelForLegendInput(documentRef, panelNumber, titleLineCount, panelConfigurations) {
        var panelConfiguration = panelConfigurations[panelNumber - 1];

        positionPanelArtworkForInput(
            documentRef,
            panelNumber,
            titleLineCount,
            panelConfigurations
        );
        focusViewOnBounds(
            documentRef,
            getPanelFocusBounds(documentRef, panelNumber, panelConfiguration.legendCount),
            PANEL_VIEW_MARGIN_MM
        );
        refreshDocument();
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

    function setMainTitle(documentRef, illustrationType, graphNumber, titleText) {
        var frames = getMainTitleFrames(documentRef);
        var lineCount = measureTitleLines(frames.title, titleText);
        var backgroundIndex;

        if (lineCount > 3) {
            fail("El título ocupa " + lineCount + " líneas. El máximo permitido es 3.");
        }

        frames.number.contents = illustrationType + " " + graphNumber;
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

    function setPanelTitle(documentRef, panelNumber, graphNumber, titleText) {
        var panelLetters = ["a", "b", "c"];
        var titleFrame = getPanelTitleFrame(documentRef, panelNumber);

        if (titleText === "") {
            titleFrame.contents = "";
            titleFrame.hidden = true;
        } else {
            titleFrame.hidden = false;
            titleFrame.contents =
                graphNumber + "." + panelLetters[panelNumber - 1] + "  " + titleText;
        }
    }

    function setPanelLegendCount(documentRef, panelNumber, legendCount) {
        var legendLayer = getLegendLayer(documentRef, panelNumber);
        var legendNumber;
        var visible;

        for (legendNumber = 1; legendNumber <= 6; legendNumber += 1) {
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

    function parseSourceParagraphs(text) {
        var lines = text.split(/\r\n|\r|\n/);
        var result = [];
        var index;

        for (index = 0; index < lines.length; index += 1) {
            if (lines[index] !== "") {
                result.push(normalizeSourceLabelText(lines[index]));
            }
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

    function getSourceLabelParts(text) {
        var labelMatch = text.match(/^\s*(FUENTES|FUENTE|NOTAS|NOTA)\s*(:|\.|\s|$)/i);
        var label = labelMatch ? labelMatch[1].toUpperCase() + ":" : "FUENTE:";
        var body = labelMatch ?
            text.substring(labelMatch[0].length).replace(/^\s+/, "") :
            text;

        return {
            label: label,
            body: body
        };
    }

    function getSourceParagraphLabelParts(text) {
        var labelMatch = text.match(/^\s*(FUENTES|FUENTE|NOTAS|NOTA)\s*(:|\.|\s|$)/i);
        var label = labelMatch ? labelMatch[1].toUpperCase() + ":" : "";
        var body = labelMatch ?
            text.substring(labelMatch[0].length).replace(/^\s+/, "") :
            text;

        return {
            label: label,
            body: body
        };
    }

    function isSourceLabelParagraph(text) {
        return /^\s*(FUENTES|FUENTE|NOTAS|NOTA)\s*(:|\.|\s|$)/i.test(text);
    }

    function normalizeSourceLabelText(text) {
        var labelParts;

        if (!isSourceLabelParagraph(text)) {
            return text;
        }

        labelParts = getSourceParagraphLabelParts(text);
        return labelParts.label + " " + labelParts.body;
    }

    function setSourceFrameText(textFrame, sourceText, paragraphs) {
        var mediumFont = app.textFonts.getByName("Roboto-Medium");
        var lightFont = app.textFonts.getByName("Roboto-Light");
        var sourceParts = getSourceLabelParts(sourceText);
        var content = sourceParts.label + " " + sourceParts.body;
        var mediumRanges = [{start: 0, length: sourceParts.label.length}];
        var labelParts;
        var paragraphIndex;
        var isLabelParagraph;
        var letterMatch;
        var tabStop;
        var paragraph;
        var additionalParagraphStart;
        var sourceParagraphIndex;

        if (paragraphs.length > 0) {
            content += "\r\r";
        }

        for (paragraphIndex = 0; paragraphIndex < paragraphs.length; paragraphIndex += 1) {
            isLabelParagraph = isSourceLabelParagraph(paragraphs[paragraphIndex]);
            if (isLabelParagraph) {
                labelParts = getSourceParagraphLabelParts(paragraphs[paragraphIndex]);
                mediumRanges.push({start: content.length, length: labelParts.label.length});
                content += labelParts.label + " " + labelParts.body;
            } else {
                letterMatch = paragraphs[paragraphIndex].match(/^([a-zA-Z])(?:\.|[\t ]+)(?:[\t ]*)(.*)$/);
                if (letterMatch) {
                    mediumRanges.push({start: content.length, length: 1});
                    content += letterMatch[1] + "\t" + letterMatch[2];
                } else {
                    content += paragraphs[paragraphIndex];
                }
            }
            if (paragraphIndex < paragraphs.length - 1) {
                content += "\r";
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

        additionalParagraphStart = textFrame.paragraphs.length - paragraphs.length;
        for (sourceParagraphIndex = 0;
            sourceParagraphIndex < additionalParagraphStart - 1;
            sourceParagraphIndex += 1) {
            paragraph = textFrame.paragraphs[sourceParagraphIndex];
            paragraph.paragraphAttributes.firstLineIndent = 0;
            paragraph.paragraphAttributes.leftIndent = 0;
            paragraph.paragraphAttributes.tabStops = [];
        }

        for (paragraphIndex = 0; paragraphIndex < paragraphs.length; paragraphIndex += 1) {
            paragraph = textFrame.paragraphs[additionalParagraphStart + paragraphIndex];
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

    function configureDownloadButton(documentRef, addDownload) {
        var sourceLayer = getByName(
            getMainLayer(documentRef).layers,
            NAMES.sourceLayer,
            "la capa de fuentes"
        );
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

        noButtonFrame.hidden = addDownload;
        downloadFrame.hidden = !addDownload;
        infoFrame.hidden = true;

        getByName(sourceLayer.groupItems, "DESCARGAR", "el botón Descargar").hidden =
            !addDownload;
        getByName(sourceLayer.groupItems, "DOWNLOAD", "el botón Download").hidden = true;
        getByName(sourceLayer.groupItems, "+INFO", "el botón Más información").hidden = true;

        if (addDownload) {
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

    function positionSourcesAfterLastPanel(documentRef, panelCount) {
        var sourceLayer = getByName(
            getMainLayer(documentRef).layers,
            NAMES.sourceLayer,
            "la capa de fuentes"
        );
        var lastPanelBounds = getLayerContentBounds(getPanelLayer(documentRef, panelCount));
        var sourceBounds = getLayerContentBounds(sourceLayer);
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

    function setSourceText(documentRef, sourceText, paragraphText, addDownload) {
        var sourceFrames = getSourceFrames(documentRef);
        var paragraphs = parseSourceParagraphs(paragraphText);
        var index;

        configureDownloadButton(documentRef, addDownload);
        for (index = 0; index < sourceFrames.length; index += 1) {
            setSourceFrameText(sourceFrames[index], sourceText, paragraphs);
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
        var panelGroup = dialog.add("panel", undefined, "Número de paneles");
        var buttons = dialog.add("group");
        var graphCheck;
        var tableCheck;
        var boxCheck;
        var illustrationChecks = [];
        var themeNames = ["Documento DO", "Biblioteca", "Gris", "Celeste", "Azul"];
        var themeChecks = [];
        var themeIndex;
        var panelChecks = [];
        var panelNumber;

        dialog.orientation = "column";
        dialog.alignChildren = ["fill", "top"];
        dialog.spacing = 18;
        dialog.margins = 18;

        typePanel.orientation = "row";
        typePanel.alignChildren = ["left", "center"];
        typePanel.margins = 14;
        graphCheck = typePanel.add("checkbox", undefined, "Gráfico");
        tableCheck = typePanel.add("checkbox", undefined, "Cuadro");
        boxCheck = typePanel.add("checkbox", undefined, "Recuadro");
        illustrationChecks = [graphCheck, tableCheck, boxCheck];

        function selectIllustration(selectedIndex) {
            var index;
            for (index = 0; index < illustrationChecks.length; index += 1) {
                illustrationChecks[index].value = index === selectedIndex;
            }
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

        function selectTheme(selectedIndex) {
            var index;
            for (index = 0; index < themeChecks.length; index += 1) {
                themeChecks[index].value = index === selectedIndex;
            }
        }

        for (themeIndex = 0; themeIndex < themeNames.length; themeIndex += 1) {
            themeChecks.push(themePanel.add("checkbox", undefined, themeNames[themeIndex]));
            themeChecks[themeChecks.length - 1].onClick = (function (selectedIndex) {
                return function () {
                    selectTheme(selectedIndex);
                };
            }(themeIndex));
        }
        selectTheme(0);

        panelGroup.orientation = "column";
        panelGroup.alignChildren = ["left", "center"];
        panelGroup.margins = 14;
        var panelChecksGroup = panelGroup.add("group");
        panelChecksGroup.orientation = "row";
        panelChecksGroup.alignChildren = ["left", "center"];

        function selectPanel(selectedIndex) {
            var index;
            for (index = 0; index < panelChecks.length; index += 1) {
                panelChecks[index].value = index === selectedIndex;
            }
        }

        for (panelNumber = 1; panelNumber <= 3; panelNumber += 1) {
            panelChecks.push(panelChecksGroup.add("checkbox", undefined, String(panelNumber)));
            panelChecks[panelChecks.length - 1].onClick = (function (selectedIndex) {
                return function () {
                    selectPanel(selectedIndex);
                };
            }(panelNumber - 1));
        }
        selectPanel(2);

        buttons.alignment = "right";
        buttons.add("button", undefined, "Cancelar", {name: "cancel"});
        buttons.add("button", undefined, "Continuar", {name: "ok"});
        selectIllustration(0);

        if (dialog.show() !== 1) {
            return null;
        }

        return {
            illustrationType: graphCheck.value ? "Gráfico" :
                (tableCheck.value ? "Cuadro" : "Recuadro"),
            themeType: themeChecks[0].value ? themeNames[0] :
                (themeChecks[1].value ? themeNames[1] :
                    (themeChecks[2].value ? themeNames[2] :
                        (themeChecks[3].value ? themeNames[3] : themeNames[4]))),
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

    function showPanelConfigurationDialog(panelNumber) {
        var dialog = new Window("dialog", "Configuración del Panel " + panelNumber);
        var titleGroup = dialog.add("group");
        var optionsGroup = dialog.add("group");
        var legendPanel = dialog.add("panel", undefined, "Número de leyendas");
        var buttons = dialog.add("group");
        var titleField;
        var unitsCheck;
        var legendChecks = [];
        var legendNumber;

        dialog.orientation = "column";
        dialog.alignChildren = ["fill", "top"];
        dialog.spacing = 18;
        dialog.margins = 18;

        titleGroup.add("statictext", undefined, "Título del panel:");
        titleField = titleGroup.add("edittext", undefined, "");
        titleField.characters = 38;

        optionsGroup.orientation = "row";
        optionsGroup.alignChildren = ["left", "center"];
        unitsCheck = optionsGroup.add("checkbox", undefined, "El gráfico tiene unidades");
        unitsCheck.value = false;

        legendPanel.orientation = "row";
        legendPanel.alignChildren = ["left", "center"];
        legendPanel.margins = 14;

        function selectLegendCount(selectedIndex) {
            var index;
            for (index = 0; index < legendChecks.length; index += 1) {
                legendChecks[index].value = index === selectedIndex;
            }
        }

        for (legendNumber = 0; legendNumber <= 6; legendNumber += 1) {
            legendChecks.push(
                legendPanel.add("checkbox", undefined, String(legendNumber))
            );
            legendChecks[legendChecks.length - 1].onClick = (function (selectedIndex) {
                return function () {
                    selectLegendCount(selectedIndex);
                };
            }(legendNumber));
        }
        selectLegendCount(6);

        buttons.alignment = "right";
        buttons.add("button", undefined, "Cancelar", {name: "cancel"});
        buttons.add("button", undefined, "Continuar", {name: "ok"});

        if (dialog.show() !== 1) {
            return null;
        }

        for (legendNumber = 0; legendNumber <= 6; legendNumber += 1) {
            if (legendChecks[legendNumber].value) {
                return {
                    title: titleField.text,
                    hasUnits: unitsCheck.value,
                    legendCount: legendNumber
                };
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
        var sourceGroup = dialog.add("group");
        var paragraphsGroup = dialog.add("group");
        var buttons = dialog.add("group");
        var sourceField;
        var paragraphsField;
        var defaultSourceCheck;
        var downloadCheck;
        var downloadGroup;
        var validationPassed = false;

        dialog.orientation = "column";
        dialog.alignChildren = ["fill", "top"];
        dialog.spacing = 18;
        dialog.margins = 18;

        sourceGroup.orientation = "column";
        sourceGroup.alignChildren = ["fill", "top"];
        sourceGroup.add(
            "statictext",
            undefined,
            "Fuente, con uno o más párrafos:"
        );
        defaultSourceCheck = sourceGroup.add(
            "checkbox",
            undefined,
            "FUENTE: Banco de España."
        );
        defaultSourceCheck.value = false;
        sourceField = sourceGroup.add("edittext", undefined, "", {
            multiline: true,
            scrolling: true
        });
        sourceField.preferredSize = [480, 100];

        defaultSourceCheck.onClick = function () {
            if (defaultSourceCheck.value) {
                sourceField.text = "FUENTE: Banco de España.";
            }
        };

        paragraphsGroup.orientation = "column";
        paragraphsGroup.alignChildren = ["fill", "top"];
        paragraphsGroup.add(
            "statictext",
            undefined,
            "Párrafos adicionales, uno por línea. Incluye las letras a, b, c..."
        );
        paragraphsField = paragraphsGroup.add("edittext", undefined, "", {
            multiline: true,
            scrolling: true
        });
        paragraphsField.preferredSize = [480, 150];

        downloadGroup = dialog.add("group");
        downloadGroup.orientation = "row";
        downloadGroup.alignChildren = ["left", "center"];
        downloadCheck = downloadGroup.add("checkbox", undefined, "Añadir botón Descargar");
        downloadCheck.value = false;
        addDownloadIcon(downloadGroup);

        buttons.alignment = "right";
        buttons.add("button", undefined, "Cancelar", {name: "cancel"});
        var continueButton = buttons.add("button", undefined, "Aplicar");

        continueButton.onClick = function () {
            if (sourceField.text === "") {
                alert("Introduce el texto de la fuente.");
                return;
            }
            validationPassed = true;
            dialog.close(1);
        };

        if (dialog.show() !== 1 || !validationPassed) {
            return null;
        }

        return {
            source: sourceField.text,
            paragraphs: paragraphsField.text,
            addDownload: downloadCheck.value
        };
    }

    function run() {
        var documentRef;
        var values;
        var titleValues;
        var titleLineCount;
        var panelValues;
        var panelNumber;
        var panelConfigurations = [];
        var panelLegendFormats = [];
        var legendValues;
        var legendNumber;
        var sourceValues;

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
                    sourceValues.source,
                    sourceValues.paragraphs,
                    sourceValues.addDownload
                );
                refreshDocument();
                return;
            }

            movePanelsForTitle(documentRef, titleLineCount, values.panelCount);
            refreshDocument();

            for (panelNumber = 1; panelNumber <= values.panelCount; panelNumber += 1) {
                panelValues = showPanelConfigurationDialog(panelNumber);
                if (!panelValues) {
                    return;
                }

                setPanelTitle(
                    documentRef,
                    panelNumber,
                    titleValues.graphNumber,
                    panelValues.title
                );
                setPanelLegendCount(
                    documentRef,
                    panelNumber,
                    panelValues.legendCount
                );
                panelConfigurations.push(panelValues);
                refreshDocument();
            }

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

            sourceValues = showSourceDialog();
            if (!sourceValues) {
                return;
            }
            setSourceText(
                documentRef,
                sourceValues.source,
                sourceValues.paragraphs,
                sourceValues.addDownload
            );
            positionSourcesAfterLastPanel(documentRef, values.panelCount);
            refreshDocument();
            if (!previewChartPatternsFromLegendFormats(documentRef, panelLegendFormats)) {
                return;
            }
            refreshDocument();
        } catch (error) {
            alert("No se pudo aplicar la configuración:\n" + error.message);
        }
    }

    run();
}());
