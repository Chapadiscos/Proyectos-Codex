(function () {
    var docPath = '/Users/jose/Desktop/REED trasladar/Maqueta REED traspaso texto - TEST Codex.indd';
    var reportPath = '/Users/jose/Desktop/REED trasladar/applyParagraphStylesByTextFrame.verify-report.txt';
    var targetFrameNames = ['Titulo', 'Autor+Cargos', 'Recibido', 'Conflicto'];

    function writeReport(text) {
        var file = File(reportPath);
        file.encoding = 'UTF-8';
        file.open('w');
        file.write(text);
        file.close();
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

    function cleanSnippet(text) {
        text = String(text).replace(/\r/g, ' / ').replace(/\n/g, ' / ');
        if (text.length > 220) {
            text = text.substring(0, 220) + '...';
        }
        return text;
    }

    function countSuperscriptDigitsAndCommas(textFrame) {
        var count = 0;
        for (var i = 0; i < textFrame.characters.length; i++) {
            try {
                if (textFrame.characters[i].appliedCharacterStyle.name === 'Super' && /^[0-9,]+$/.test(textFrame.characters[i].contents)) {
                    count++;
                }
            } catch (e) {}
        }
        return count;
    }

    function findDoiTextFrames(doc) {
        var found = [];
        var frames = doc.textFrames;
        for (var i = 0; i < frames.length; i++) {
            try {
                if (frames[i].name === 'DOI' || frames[i].label === 'DOI') {
                    found.push(frames[i]);
                } else if (frames[i].paragraphs.length > 0 && frames[i].paragraphs[0].appliedParagraphStyle.name === 'DOI Pie') {
                    found.push(frames[i]);
                } else if (String(frames[i].contents).indexOf('DOI') >= 0) {
                    found.push(frames[i]);
                }
            } catch (e) {}
        }
        return found;
    }

    function countTextVariableInstances(textFrame) {
        try {
            return textFrame.texts[0].textVariableInstances.length;
        } catch (e) {
            return 0;
        }
    }

    try {
        var doc = app.open(File(docPath));
        var report = 'VERIFICACION DOCUMENTO DE PRUEBA\n\n';

        for (var i = 0; i < targetFrameNames.length; i++) {
            var frameName = targetFrameNames[i];
            var frame = findTextFrameByName(doc, frameName);
            if (!frame) {
                report += frameName + ': marco no encontrado\n';
                continue;
            }

            report += frameName + ': chars=' + frame.characters.length + ', paragraphs=' + frame.paragraphs.length + '\n';
            report += '  texto: ' + cleanSnippet(frame.contents) + '\n';
            if (frameName === 'Autor+Cargos') {
                report += '  super digitos/comas: ' + countSuperscriptDigitsAndCommas(frame) + '\n';
            }
            for (var p = 0; p < frame.paragraphs.length; p++) {
                try {
                    report += '  p' + (p + 1) + ': ' + frame.paragraphs[p].appliedParagraphStyle.name + '\n';
                } catch (e) {}
            }
        }

        var doiFrames = findDoiTextFrames(doc);
        for (var d = 0; d < doiFrames.length; d++) {
            report += 'DOI frame ' + (d + 1) + ': chars=' + doiFrames[d].characters.length + ', variables=' + countTextVariableInstances(doiFrames[d]) + '\n';
            report += '  texto: ' + cleanSnippet(doiFrames[d].contents) + '\n';
        }

        writeReport(report);
        doc.close(SaveOptions.NO);
    } catch (e) {
        writeReport('Error en verificacion ID2026: ' + e.message + (e.line ? ' (linea ' + e.line + ')' : ''));
    }
})();
