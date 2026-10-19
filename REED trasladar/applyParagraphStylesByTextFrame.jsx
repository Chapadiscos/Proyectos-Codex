/*
  applyParagraphStylesByTextFrame.jsx
  Script para Adobe InDesign CC / InDesign 2020+.
  Mueve texto con estilos de párrafo determinados desde las páginas visibles
  hacia marcos de texto específicos, borrando el contenido destino antes de pegar.
*/

(function () {
    try {
        app.doScript(
            run,
            ScriptLanguage.JAVASCRIPT,
            undefined,
            UndoModes.ENTIRE_SCRIPT,
            'Trasladar estilos por marco de texto'
        );
    } catch (e) {
        alert('Error: ' + e.message + (e.line ? ' (linea ' + e.line + ')' : ''));
    }

    function run() {
        if (app.documents.length === 0) {
            throw new Error('No hay ningún documento abierto en InDesign.');
        }

        var doc = app.activeDocument;
        var win = app.activeWindow;

        if (!win || win.constructor.name !== 'LayoutWindow') {
            throw new Error('Debes ejecutar el script desde una ventana de maquetación activa.');
        }

        var visiblePages = win.activeSpread.pages;
        if (!visiblePages || visiblePages.length === 0) {
            throw new Error('No se encontraron páginas visibles en la ventana activa.');
        }

        // Mapeo de estilos de párrafo hacia marcos de texto destino.
        // Si un mapeo tiene characterStyle, se aplica al texto movido.
        var mappings = [
            {
                index: 1,
                paragraphStyles: ['Titulo'],
                destinationFrameName: 'Titulo',
                characterStyle: 'Titulo'
            },
            {
                index: 2,
                paragraphStyles: ['Autor', 'Cargos'],
                destinationFrameName: 'Autor+Cargos'
            },
            {
                index: 3,
                paragraphStyles: ['Recibido-Aceptado'],
                destinationFrameName: 'Recibido'
            },
            {
                index: 4,
                paragraphStyles: ['Conflicto intereses'],
                destinationFrameName: 'Conflicto'
            }
        ];

        var movedCount = 0;
        var convertedDoiVariablesCount = 0;
        var cleanedDoiReferenceMarkersCount = 0;
        var missingFrames = [];
        var missingStyles = [];
        var noTextFound = [];

        for (var m = 0; m < mappings.length; m++) {
            var map = mappings[m];
            var paragraphStyles = map.paragraphStyles;
            var destinationFrame = findTextFrameByName(doc, map.destinationFrameName);

            if (!destinationFrame) {
                missingFrames.push(map.destinationFrameName);
                continue;
            }

            var paragraphStyleObjects = [];
            for (var s = 0; s < paragraphStyles.length; s++) {
                var style = findParagraphStyleByName(doc, paragraphStyles[s]);
                if (!style) {
                    missingStyles.push(paragraphStyles[s]);
                } else {
                    paragraphStyleObjects.push(style);
                }
            }

            if (paragraphStyleObjects.length === 0) {
                continue;
            }

            var characterStyle = null;
            if (map.characterStyle) {
                characterStyle = findCharacterStyleByName(doc, map.characterStyle);
                if (!characterStyle) {
                    missingStyles.push('Character: ' + map.characterStyle);
                }
            }

            destinationFrame.contents = '';

            var sourceParagraphs = collectVisibleParagraphsByStyles(visiblePages, paragraphStyleObjects, destinationFrame);
            if (sourceParagraphs.length === 0) {
                noTextFound.push(map.index + ' (' + map.destinationFrameName + ')');
                continue;
            }

            movedCount += moveParagraphsToFrame(sourceParagraphs, destinationFrame, characterStyle);
        }

        var doiFrames = findDoiTextFrames(doc, visiblePages);
        if (doiFrames.length > 0) {
            for (var d = 0; d < doiFrames.length; d++) {
                convertedDoiVariablesCount += convertTextVariablesToText(doiFrames[d]);
                cleanedDoiReferenceMarkersCount += cleanDoiPieReferenceMarkers(doiFrames[d]);
            }
        } else {
            missingFrames.push('DOI');
        }

        var report = 'Resultados:\n';
        report += '- Párrafos movidos: ' + movedCount + '\n';
        report += '- Variables DOI convertidas a texto: ' + convertedDoiVariablesCount + '\n';
        report += '- Marcadores limpiados en DOI Pie: ' + cleanedDoiReferenceMarkersCount + '\n';
        if (missingFrames.length) {
            report += '- Marcos destino no encontrados: ' + missingFrames.join(', ') + '\n';
        }
        if (missingStyles.length) {
            report += '- Estilos no encontrados: ' + missingStyles.join(', ') + '\n';
        }
        if (noTextFound.length) {
            report += '- No se encontró texto para los destinos: ' + noTextFound.join(', ') + '\n';
        }

        alert(report);
    }

    function findTextFrameByName(doc, name) {
        var frames = doc.textFrames;
        for (var i = 0; i < frames.length; i++) {
            if (frames[i].name === name) {
                return frames[i];
            }
        }
        return null;
    }

    function findDoiTextFrames(doc, visiblePages) {
        var namedFrame = findTextFrameByNameOrLabel(doc, 'DOI');
        if (namedFrame) {
            return [namedFrame];
        }

        var framesByStyle = findVisibleTextFramesByFirstParagraphStyle(visiblePages, 'DOI Pie');
        if (framesByStyle.length > 0) {
            return framesByStyle;
        }

        return findVisibleTextFramesByContent(visiblePages, 'DOI:');
    }

    function findTextFrameByNameOrLabel(doc, value) {
        var frames = doc.textFrames;
        for (var i = 0; i < frames.length; i++) {
            if (frames[i].name === value || getTextFrameLabel(frames[i]) === value) {
                return frames[i];
            }
        }
        return null;
    }

    function getTextFrameLabel(textFrame) {
        try {
            return textFrame.label;
        } catch (e) {
            return '';
        }
    }

    function findVisibleTextFramesByFirstParagraphStyle(visiblePages, styleName) {
        var found = [];
        for (var p = 0; p < visiblePages.length; p++) {
            var frames = visiblePages[p].textFrames;
            for (var f = 0; f < frames.length; f++) {
                try {
                    if (frames[f].paragraphs.length > 0 && frames[f].paragraphs[0].appliedParagraphStyle.name === styleName) {
                        found.push(frames[f]);
                    }
                } catch (e) {}
            }
        }
        return found;
    }

    function findVisibleTextFramesByContent(visiblePages, text) {
        var found = [];
        for (var p = 0; p < visiblePages.length; p++) {
            var frames = visiblePages[p].textFrames;
            for (var f = 0; f < frames.length; f++) {
                if (String(frames[f].contents).indexOf(text) >= 0) {
                    found.push(frames[f]);
                }
            }
        }
        return found;
    }

    function findParagraphStyleByName(doc, styleName) {
        return findStyleByNameInContainer(
            doc,
            'paragraphStyles',
            'paragraphStyleGroups',
            styleName
        );
    }

    function findCharacterStyleByName(doc, styleName) {
        return findStyleByNameInContainer(
            doc,
            'characterStyles',
            'characterStyleGroups',
            styleName
        );
    }

    function findStyleByNameInContainer(container, stylesProperty, groupsProperty, styleName) {
        var styles = container[stylesProperty];
        for (var i = 0; i < styles.length; i++) {
            if (styles[i].name === styleName) {
                return styles[i];
            }
        }

        var groups = container[groupsProperty];
        for (var g = 0; g < groups.length; g++) {
            var found = findStyleByNameInContainer(groups[g], stylesProperty, groupsProperty, styleName);
            if (found) {
                return found;
            }
        }

        return null;
    }

    function collectVisibleParagraphsByStyles(visiblePages, paragraphStyles, destinationFrame) {
        var collected = [];
        for (var p = 0; p < visiblePages.length; p++) {
            var page = visiblePages[p];
            var frames = page.textFrames;
            for (var f = 0; f < frames.length; f++) {
                var frame = frames[f];
                if (frame === destinationFrame) {
                    continue;
                }
                var paragraphs = frame.paragraphs;
                for (var j = 0; j < paragraphs.length; j++) {
                    var para = paragraphs[j];
                    for (var k = 0; k < paragraphStyles.length; k++) {
                        if (para.appliedParagraphStyle === paragraphStyles[k] || para.appliedParagraphStyle.name === paragraphStyles[k].name) {
                            collected.push(para);
                            break;
                        }
                    }
                }
            }
        }
        return collected;
    }

    function moveParagraphsToFrame(paragraphs, destinationFrame, characterStyle) {
        var parts = [];
        var appliedParagraphStyles = [];

        for (var i = 0; i < paragraphs.length; i++) {
            var paragraphText = removeTrailingReturns(paragraphs[i].contents);
            if (paragraphText.length > 0) {
                parts.push(paragraphText);
                appliedParagraphStyles.push(paragraphs[i].appliedParagraphStyle);
            }
        }

        var textToMove = parts.join('\r');

        if (textToMove.length > 0) {
            destinationFrame.insertionPoints[-1].contents = textToMove;
            var destParagraphs = destinationFrame.paragraphs;
            for (var k = 0; k < destParagraphs.length && k < appliedParagraphStyles.length; k++) {
                destParagraphs[k].appliedParagraphStyle = appliedParagraphStyles[k];
                if (characterStyle) {
                    destParagraphs[k].characters.everyItem().appliedCharacterStyle = characterStyle;
                }
            }
        }

        for (var r = paragraphs.length - 1; r >= 0; r--) {
            try {
                paragraphs[r].remove();
            } catch (e) {
                // Ignorar si ya no existe o si la eliminación falla.
            }
        }

        return appliedParagraphStyles.length;
    }

    function removeTrailingReturns(text) {
        return String(text).replace(/[\r\n]+$/g, '');
    }

    function isParagraphStyle(paragraph, styleName) {
        try {
            return paragraph.appliedParagraphStyle.name === styleName;
        } catch (e) {
            return false;
        }
    }

    function convertTextVariablesToText(textFrame) {
        var instances = getTextVariableInstances(textFrame);
        var convertedCount = 0;

        for (var i = instances.length - 1; i >= 0; i--) {
            try {
                instances[i].convertToText();
                convertedCount++;
            } catch (e) {
                // Ignorar instancias que InDesign no permita convertir.
            }
        }

        return convertedCount;
    }

    function cleanDoiPieReferenceMarkers(textFrame) {
        var cleanedCount = 0;
        var paragraphs = textFrame.paragraphs;

        for (var i = 0; i < paragraphs.length; i++) {
            var paragraph = paragraphs[i];
            if (!isParagraphStyle(paragraph, 'DOI Pie')) {
                continue;
            }

            var originalText = removeTrailingReturns(paragraph.contents);
            var cleanedText = removeDoiAuthorReferenceMarkers(originalText);

            if (cleanedText !== originalText) {
                paragraph.contents = cleanedText;
                cleanedCount++;
            }
        }

        return cleanedCount;
    }

    function removeDoiAuthorReferenceMarkers(text) {
        return String(text).replace(/([A-Za-zÀ-ÖØ-öø-ÿ])\d+(?:\s*[,-]\s*\d+)*/g, '$1');
    }

    function getTextVariableInstances(textFrame) {
        try {
            return textFrame.texts[0].textVariableInstances.everyItem().getElements();
        } catch (e) {
            return [];
        }
    }
})();
