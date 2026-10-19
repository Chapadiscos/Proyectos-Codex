//DESCRIPTION: Convierte los espacios normales del texto seleccionado en espacios de no separacion (nbsp).

(function () {
	var NBSP = " ";

	function convertSelectionRange(textRange) {
		var chars = textRange.characters.everyItem().getElements();
		var modified = 0;

		for (var i = 0; i < chars.length; i++) {
			if (chars[i].contents === " ") {
				chars[i].contents = NBSP;
				modified++;
			}
		}

		return modified;
	}

	function run() {
		if (!app.documents.length) {
			alert("Abre un documento antes de ejecutar el script.");
			return;
		}

		var sel = app.selection;
		if (!sel || sel.length === 0) {
			alert("Selecciona texto antes de ejecutar el script.");
			return;
		}

		app.doScript(
			function () {
				for (var i = 0; i < sel.length; i++) {
					var item = sel[i];
					try {
						if (item.hasOwnProperty("characters")) {
							convertSelectionRange(item);
						}
					} catch (e) {
					}
				}
			},
			ScriptLanguage.JAVASCRIPT,
			undefined,
			UndoModes.ENTIRE_SCRIPT,
			"Espacios de no separacion"
		);
	}

	run();
}());
