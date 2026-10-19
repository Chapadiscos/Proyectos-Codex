(function () {
    var docPath = '/Users/jose/Desktop/REED trasladar/Maqueta REED traspaso texto.indd';
    var reportPath = '/Users/jose/Desktop/REED trasladar/indesign-structure-report.txt';

    function writeReport(text) {
        var file = File(reportPath);
        file.encoding = 'UTF-8';
        file.open('w');
        file.write(text);
        file.close();
    }

    function listParagraphStyles(container, prefix, out) {
        var styles = container.paragraphStyles;
        for (var i = 0; i < styles.length; i++) {
            out.push(prefix + styles[i].name);
        }

        var groups = container.paragraphStyleGroups;
        for (var g = 0; g < groups.length; g++) {
            listParagraphStyles(groups[g], prefix + groups[g].name + '/', out);
        }
    }

    function listCharacterStyles(container, prefix, out) {
        var styles = container.characterStyles;
        for (var i = 0; i < styles.length; i++) {
            out.push(prefix + styles[i].name);
        }

        var groups = container.characterStyleGroups;
        for (var g = 0; g < groups.length; g++) {
            listCharacterStyles(groups[g], prefix + groups[g].name + '/', out);
        }
    }

    function listTextFrames(doc, out) {
        var frames = doc.textFrames;
        for (var i = 0; i < frames.length; i++) {
            var frame = frames[i];
            var pageName = 'sin pagina';
            try {
                if (frame.parentPage) {
                    pageName = frame.parentPage.name;
                }
            } catch (e) {}

            out.push('pagina ' + pageName + ' | name="' + frame.name + '" | chars=' + frame.characters.length);
        }
    }

    function listUsedParagraphStyles(doc, out) {
        var seen = {};
        var stories = doc.stories;
        for (var s = 0; s < stories.length; s++) {
            var paragraphs = stories[s].paragraphs;
            for (var p = 0; p < paragraphs.length; p++) {
                try {
                    var styleName = paragraphs[p].appliedParagraphStyle.name;
                    if (!seen[styleName]) {
                        seen[styleName] = true;
                        out.push(styleName);
                    }
                } catch (e) {}
            }
        }
    }

    try {
        var doc = app.open(File(docPath));
        var paragraphStyles = [];
        var characterStyles = [];
        var textFrames = [];
        var usedParagraphStyles = [];

        listParagraphStyles(doc, '', paragraphStyles);
        listCharacterStyles(doc, '', characterStyles);
        listTextFrames(doc, textFrames);
        listUsedParagraphStyles(doc, usedParagraphStyles);

        var report = '';
        report += 'DOCUMENTO: ' + doc.name + '\n\n';
        report += 'ESTILOS DE PARRAFO:\n' + paragraphStyles.join('\n') + '\n\n';
        report += 'ESTILOS DE CARACTER:\n' + characterStyles.join('\n') + '\n\n';
        report += 'ESTILOS DE PARRAFO USADOS EN TEXTO:\n' + usedParagraphStyles.join('\n') + '\n\n';
        report += 'MARCOS DE TEXTO:\n' + textFrames.join('\n') + '\n';

        writeReport(report);
        doc.close(SaveOptions.NO);
    } catch (e) {
        writeReport('Error en dump ID2026: ' + e.message + (e.line ? ' (linea ' + e.line + ')' : ''));
    }
})();
