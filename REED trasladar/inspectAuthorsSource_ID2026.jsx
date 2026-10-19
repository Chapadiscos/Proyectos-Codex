(function () {
    var docPath = '/Users/jose/Desktop/REED trasladar/Maqueta REED traspaso texto.indd';
    var reportPath = '/Users/jose/Desktop/REED trasladar/authors-source-inspect.txt';

    function writeReport(text) {
        var file = File(reportPath);
        file.encoding = 'UTF-8';
        file.open('w');
        file.write(text);
        file.close();
    }

    try {
        var doc = app.open(File(docPath));
        var report = 'AUTORES ORIGEN\n\n';
        var stories = doc.stories;
        for (var s = 0; s < stories.length; s++) {
            var paragraphs = stories[s].paragraphs;
            for (var p = 0; p < paragraphs.length; p++) {
                try {
                    var styleName = paragraphs[p].appliedParagraphStyle.name;
                    if (styleName === 'Autor' || styleName === 'Cargos') {
                        report += 'PARRAFO ' + styleName + ': ' + paragraphs[p].contents + '\n';
                        var chars = paragraphs[p].characters;
                        for (var c = 0; c < chars.length; c++) {
                            var characterStyle = chars[c].appliedCharacterStyle.name;
                            if (/^[0-9,-]$/.test(chars[c].contents) || characterStyle === 'Super') {
                                report += '  "' + chars[c].contents + '" charStyle=' + characterStyle + '\n';
                            }
                        }
                    }
                } catch (e) {}
            }
        }

        writeReport(report);
        doc.close(SaveOptions.NO);
    } catch (e) {
        writeReport('Error: ' + e.message + (e.line ? ' (linea ' + e.line + ')' : ''));
    }
})();
