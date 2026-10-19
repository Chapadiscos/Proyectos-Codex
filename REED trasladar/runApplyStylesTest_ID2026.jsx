(function () {
    var docPath = '/Users/jose/Desktop/REED trasladar/Maqueta REED traspaso texto - TEST Codex.indd';
    var scriptPath = '/Users/jose/Desktop/REED trasladar/applyParagraphStylesByTextFrame.jsx';
    var reportPath = '/Users/jose/Desktop/REED trasladar/applyParagraphStylesByTextFrame.test-report.txt';

    function writeReport(text) {
        var file = File(reportPath);
        file.encoding = 'UTF-8';
        file.open('w');
        file.write(text);
        file.close();
    }

    try {
        var docFile = File(docPath);
        if (!docFile.exists) {
            throw new Error('No existe el documento de prueba: ' + docPath);
        }

        var scriptFile = File(scriptPath);
        if (!scriptFile.exists) {
            throw new Error('No existe el script: ' + scriptPath);
        }

        var doc = app.open(docFile);
        if (doc.layoutWindows.length > 0) {
            app.activeWindow = doc.layoutWindows[0];
        }

        scriptFile.encoding = 'UTF-8';
        scriptFile.open('r');
        var source = scriptFile.read();
        scriptFile.close();

        var capturedAlert = '';
        source = source.replace(
            'alert(report);',
            'capturedAlert = report;'
        );
        source = source.replace(
            "alert('Error: ' + e.message + (e.line ? ' (linea ' + e.line + ')' : ''));",
            "capturedAlert = 'Error: ' + e.message + (e.line ? ' (linea ' + e.line + ')' : '');"
        );

        eval(source);

        if (!capturedAlert) {
            capturedAlert = 'El script finalizo sin devolver informe.';
        }

        doc.save();
        writeReport(capturedAlert);
    } catch (e) {
        writeReport('Error en runner ID2026: ' + e.message);
    }
})();
