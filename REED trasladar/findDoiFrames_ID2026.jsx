(function () {
    var docPath = '/Users/jose/Desktop/REED trasladar/Maqueta REED traspaso texto.indd';
    var reportPath = '/Users/jose/Desktop/REED trasladar/doi-frame-report.txt';

    function writeReport(text) {
        var file = File(reportPath);
        file.encoding = 'UTF-8';
        file.open('w');
        file.write(text);
        file.close();
    }

    function snippet(text) {
        text = String(text).replace(/\r/g, ' / ').replace(/\n/g, ' / ');
        if (text.length > 180) {
            text = text.substring(0, 180) + '...';
        }
        return text;
    }

    try {
        var doc = app.open(File(docPath));
        var report = 'POSIBLES MARCOS DOI\n\n';
        var frames = doc.textFrames;

        for (var i = 0; i < frames.length; i++) {
            var frame = frames[i];
            var content = frame.contents;
            var label = '';
            var pageName = 'sin pagina';
            var firstStyle = '';

            try {
                label = frame.label;
            } catch (e) {}
            try {
                if (frame.parentPage) {
                    pageName = frame.parentPage.name;
                }
            } catch (e) {}
            try {
                if (frame.paragraphs.length > 0) {
                    firstStyle = frame.paragraphs[0].appliedParagraphStyle.name;
                }
            } catch (e) {}

            if (
                String(frame.name).toLowerCase().indexOf('doi') >= 0 ||
                String(label).toLowerCase().indexOf('doi') >= 0 ||
                String(content).toLowerCase().indexOf('doi') >= 0 ||
                String(firstStyle).toLowerCase().indexOf('doi') >= 0
            ) {
                report += 'pagina ' + pageName + ' | name="' + frame.name + '" | label="' + label + '" | estilo="' + firstStyle + '" | chars=' + frame.characters.length + '\n';
                report += '  texto: ' + snippet(content) + '\n\n';
            }
        }

        writeReport(report);
        doc.close(SaveOptions.NO);
    } catch (e) {
        writeReport('Error buscando DOI: ' + e.message + (e.line ? ' (linea ' + e.line + ')' : ''));
    }
})();
