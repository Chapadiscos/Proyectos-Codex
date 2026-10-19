/* Lobster Paws, 2026 / lobsterpaws.com */
#targetengine "session"
function main() {
    if (app.documents.length === 0) {
        // Only show pop-up if there is no way to proceed at all.
        alert("Ningún documento abierto");
        return;
    }
    if (app.selection.length === 0 || !(app.selection[0].hasOwnProperty('paragraphs')) || app.selection[0].paragraphs.length === 0) {
        // Only show pop-up if it's fundamentally impossible to proceed.
        alert("Selecciona el párrafo que deseas ajustar");
        return;
    }

    var para = app.selection[0].paragraphs[0];
    var origTracking = para.tracking;
    var maxAllowedTracking = 20;
    var maxTracking = 100;
    var trackingStep = 1;
    var prevLineCount = para.lines.length;
    var currTracking = origTracking;
    var found = false;
    var lastGoodTracking = origTracking;

    // Try to gain a line, but stop if we would go over maxAllowedTracking
    while (currTracking <= maxTracking) {
        if (currTracking > maxAllowedTracking) {
            break;
        }
        para.tracking = currTracking;
        var newLineCount = para.lines.length;
        if (newLineCount > prevLineCount) {
            found = true;
            lastGoodTracking = currTracking;
            break;
        }
        currTracking += trackingStep;
    }

    if (found) {
        para.tracking = lastGoodTracking;
        // NO POP-UP on normal success
    } else {
        para.tracking = origTracking;
        // Only alert if the increase cannot be accomplished
        alert("No se podía ganar una línea sin superar un tracking de +20.");
    }
}
app.doScript(main, ScriptLanguage.JAVASCRIPT, undefined, UndoModes.ENTIRE_SCRIPT, "LP_tracking_gain a line_v1");

function convertUnits(value, fromUnit, toUnit) {
    var conversionFactors = {
        POINTS: 1,
        MILLIMETERS: 2.83465,
        INCHES: 72,
        PICAS: 12,
        CENTIMETERS: 28.3465,
        PIXELS: 0.75
    };
    function getUnitString(unit) {
        switch(unit) {
            case MeasurementUnits.POINTS:
                return "POINTS";
            case MeasurementUnits.MILLIMETERS:
                return "MILLIMETERS";
            case MeasurementUnits.INCHES:
                return "INCHES";
            case MeasurementUnits.PICAS:
                return "PICAS";
            case MeasurementUnits.CENTIMETERS:
                return "CENTIMETERS";
            case MeasurementUnits.PIXELS:
                return "PIXELS";
            default:
                throw new Error("Unsupported unit: " + unit);
        }
    }
    var fromUnitStr = getUnitString(fromUnit);
    var toUnitStr = getUnitString(toUnit);
    if (fromUnitStr === toUnitStr) {
        return value;
    }
    if (!conversionFactors[fromUnitStr] || !conversionFactors[toUnitStr]) {
        throw new Error("Unsupported unit for conversion: from " + fromUnitStr + " to " + toUnitStr);
    }
    var valueInPoints = value * conversionFactors[fromUnitStr];
    var convertedValue = valueInPoints / conversionFactors[toUnitStr];
    return convertedValue;
}