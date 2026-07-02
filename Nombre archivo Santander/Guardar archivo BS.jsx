#target "InDesign"

/*
 * Genera un nombre normalizado a partir de un texto como:
 * P60022Crédito documentario de exportación - liquidación de comisiones y gastos
 *
 * Resultado:
 * P60022_SIUD_CREDITO_DOCUMENTARIO_EXPORTACION_LIQUIDACION_COMISIONES_GASTOS.indd
 */

(function () {
    var documentRef;
    var initialText;
    var dialog;
    var input;
    var digitalOption;
    var physicalOption;
    var preview;
    var saveButton;
    var result;
    var generatedName;
    var destinationFolder;
    var destinationFile;

    function trim(value) {
        return String(value).replace(/^\s+|\s+$/g, "");
    }

    function removeAccents(value) {
        var accented = "ÁÀÂÄÃÅÉÈÊËÍÌÎÏÓÒÔÖÕÚÙÛÜÑÇáàâäãåéèêëíìîïóòôöõúùûüñç";
        var plain =    "AAAAAAEEEEIIIIOOOOOUUUUNCaaaaaaeeeeiiiiooooouuuunc";
        var output = "";
        var index;
        var position;

        for (index = 0; index < value.length; index += 1) {
            position = accented.indexOf(value.charAt(index));
            output += position >= 0 ? plain.charAt(position) : value.charAt(index);
        }
        return output;
    }

    function getSelectedText() {
        var selected;
        var contents;

        try {
            if (app.selection.length === 0) {
                return "";
            }
            selected = app.selection[0];
            contents = selected.contents;
            return trim(contents);
        } catch (error) {
            // Si la selección no contiene texto, se deja el campo vacío.
        }
        return "";
    }

    function buildName(sourceText, prefix) {
        var cleaned = trim(removeAccents(sourceText));
        var match = cleaned.match(/^([A-Za-z]\d+)\s*(.*)$/);
        var code;
        var description;
        var words;
        var acceptedWords = [];
        var ignoredWords = {
            "DE": true,
            "DEL": true,
            "EL": true,
            "LA": true,
            "LOS": true,
            "LAS": true,
            "Y": true,
            "E": true
        };
        var index;
        var word;

        if (!match) {
            throw new Error("El texto debe comenzar con un código, por ejemplo P60022.");
        }

        code = match[1].toUpperCase();
        description = match[2].toUpperCase();
        description = description.replace(/[^A-Z0-9]+/g, " ");
        words = trim(description).split(/\s+/);

        for (index = 0; index < words.length; index += 1) {
            word = words[index];
            if (word && !ignoredWords[word]) {
                acceptedWords.push(word);
            }
        }

        if (acceptedWords.length === 0) {
            throw new Error("Añade una descripción después del código.");
        }

        return code + "_" + prefix + "_" + acceptedWords.join("_");
    }

    function updatePreview() {
        var prefix = digitalOption.value ? "SIUD" : "SIUF";

        try {
            preview.text = buildName(input.text, prefix) + ".indd";
            saveButton.enabled = true;
        } catch (error) {
            preview.text = "Introduce un código y una descripción válidos.";
            saveButton.enabled = false;
        }
    }

    function confirmReplacement(fileRef) {
        if (!fileRef.exists) {
            return true;
        }
        return confirm(
            "Ya existe un archivo con este nombre:\n\n" +
            fileRef.fsName +
            "\n\n¿Quieres reemplazarlo?"
        );
    }

    if (app.documents.length === 0) {
        alert("Abre el documento de InDesign que quieres guardar y vuelve a ejecutar el script.");
        return;
    }

    documentRef = app.activeDocument;
    initialText = getSelectedText();

    if (!initialText) {
        alert(
            "Selecciona el texto completo que contiene el código y la descripción " +
            "y vuelve a ejecutar el script."
        );
        return;
    }

    dialog = new Window("dialog", "Guardar con nombre SIUD / SIUF");
    dialog.orientation = "column";
    dialog.alignChildren = ["fill", "top"];
    dialog.spacing = 12;
    dialog.margins = 18;

    dialog.add("statictext", undefined, "Texto seleccionado:");
    input = dialog.add("edittext", undefined, initialText, {readonly: true});
    input.characters = 72;

    var prefixPanel = dialog.add("panel", undefined, "Tipo de archivo");
    prefixPanel.orientation = "row";
    prefixPanel.alignChildren = ["left", "center"];
    prefixPanel.margins = 12;
    digitalOption = prefixPanel.add("radiobutton", undefined, "SIUD (Digital)");
    physicalOption = prefixPanel.add("radiobutton", undefined, "SIUF (Físico)");
    digitalOption.value = true;

    dialog.add("statictext", undefined, "Nombre resultante:");
    preview = dialog.add("edittext", undefined, "", {readonly: true});
    preview.characters = 72;

    var buttons = dialog.add("group");
    buttons.alignment = "right";
    buttons.add("button", undefined, "Cancelar", {name: "cancel"});
    saveButton = buttons.add("button", undefined, "Elegir carpeta y guardar", {name: "ok"});

    digitalOption.onClick = updatePreview;
    physicalOption.onClick = updatePreview;
    updatePreview();

    result = dialog.show();
    if (result !== 1) {
        return;
    }

    try {
        generatedName = buildName(
            input.text,
            digitalOption.value ? "SIUD" : "SIUF"
        );
    } catch (error) {
        alert(error.message);
        return;
    }

    destinationFolder = Folder.selectDialog("Elige la carpeta donde guardar el documento");
    if (!destinationFolder) {
        return;
    }

    destinationFile = new File(destinationFolder.fsName + "/" + generatedName + ".indd");
    if (!confirmReplacement(destinationFile)) {
        return;
    }

    try {
        documentRef.save(destinationFile);
        alert("Documento guardado como:\n\n" + destinationFile.fsName);
    } catch (error) {
        alert("No se pudo guardar el documento.\n\n" + error.message);
    }
}());
