(function () {
    var reportPath = '/Users/jose/Desktop/REED trasladar/applyParagraphStylesByTextFrame.undo-report.txt';

    function writeReport(text) {
        var file = File(reportPath);
        file.encoding = 'UTF-8';
        file.open('w');
        file.write(text);
        file.close();
    }

    try {
        if (app.documents.length === 0) {
            throw new Error('No hay documentos abiertos.');
        }

        app.activeDocument.undo();
        writeReport('Undo ejecutado correctamente.');
    } catch (e) {
        writeReport('Error al ejecutar undo: ' + e.message + (e.line ? ' (linea ' + e.line + ')' : ''));
    }
})();
