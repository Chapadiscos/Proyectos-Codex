//DESCRIPTION: Evita que un nombre de autor se parta entre dos lineas en los parrafos de un estilo elegido.
// Convierte los espacios internos de cada nombre en espacios de no separacion (nbsp),
// dejando como espacio normal (separable) solo el que sigue a cada coma.
// Asi InDesign solo puede saltar de linea entre autores, nunca dentro de un nombre.

(function () {
	var NBSP = " ";
	var NB_HYPHEN = "‑";

	function repeat(str, n) {
		var s = "";
		for (var i = 0; i < n; i++) {
			s += str;
		}
		return s;
	}

	function buildStyleTree(container, depth, items) {
		var pstyles = container.paragraphStyles;
		for (var i = 0; i < pstyles.length; i++) {
			if (pstyles[i].name == "[No Paragraph Style]") {
				continue;
			}
			items.push({ style: pstyles[i], label: repeat("    ", depth) + pstyles[i].name, isGroup: false });
		}

		var groups = container.paragraphStyleGroups;
		for (var g = 0; g < groups.length; g++) {
			items.push({ style: null, label: repeat("    ", depth) + "[" + groups[g].name + "]", isGroup: true });
			buildStyleTree(groups[g], depth + 1, items);
		}
	}

	function askUserForStyle(doc) {
		var items = [];
		buildStyleTree(doc, 0, items);

		if (items.length === 0) {
			alert("El documento no tiene estilos de parrafo.");
			return null;
		}

		var w = new Window("dialog", "Evitar corte de nombres de autor");
		w.orientation = "column";
		w.alignChildren = "fill";
		w.spacing = 10;
		w.margins = 16;

		w.add("statictext", undefined, "Selecciona el estilo de parrafo (lista de autores separados por comas):");

		var list = w.add("listbox", undefined, [], { numberOfColumns: 1 });
		list.preferredSize = [360, 260];

		var firstSelectableIndex = -1;
		for (var i = 0; i < items.length; i++) {
			var li = list.add("item", items[i].label);
			li.enabled = !items[i].isGroup;
			li.itemData = items[i];
			if (firstSelectableIndex == -1 && !items[i].isGroup) {
				firstSelectableIndex = i;
			}
		}
		if (firstSelectableIndex >= 0) {
			list.selection = firstSelectableIndex;
		}

		var btnGroup = w.add("group");
		btnGroup.alignment = "right";
		btnGroup.add("button", undefined, "Cancelar", { name: "cancel" });
		btnGroup.add("button", undefined, "Aceptar", { name: "ok" });

		list.onDoubleClick = function () {
			if (list.selection && list.selection.enabled) {
				w.close(1);
			}
		};

		if (w.show() != 1) {
			return null;
		}

		if (!list.selection || !list.selection.enabled) {
			alert("Selecciona un estilo de parrafo (no un grupo).");
			return null;
		}

		return list.selection.itemData.style;
	}

	function protectAuthorNames(para) {
		var chars = para.characters.everyItem().getElements();
		var prevNonSpace = null;
		var modified = 0;

		for (var i = 0; i < chars.length; i++) {
			var c = chars[i].contents;

			if (c === " ") {
				if (prevNonSpace !== ",") {
					chars[i].contents = NBSP;
					modified++;
				}
			} else if (c === "-") {
				chars[i].contents = NB_HYPHEN;
				modified++;
				prevNonSpace = NB_HYPHEN;
			} else if (c !== NBSP && c !== NB_HYPHEN) {
				prevNonSpace = c;
			}
		}

		return modified;
	}

	function run() {
		if (!app.documents.length) {
			alert("Abre un documento antes de ejecutar el script.");
			return;
		}

		var doc = app.activeDocument;
		var targetStyle = askUserForStyle(doc);
		if (!targetStyle) {
			return;
		}

		app.doScript(
			function () {
				var stories = doc.stories.everyItem().getElements();
				var modifiedSpaces = 0;
				var matchedParagraphs = 0;

				for (var s = 0; s < stories.length; s++) {
					var paras = stories[s].paragraphs.everyItem().getElements();
					for (var p = 0; p < paras.length; p++) {
						var para = paras[p];
						try {
							if (para.appliedParagraphStyle.id == targetStyle.id) {
								matchedParagraphs++;
								modifiedSpaces += protectAuthorNames(para);
							}
						} catch (e) {
						}
					}
				}

				alert(
					"Estilo: " + targetStyle.name + "\n" +
					"Parrafos encontrados: " + matchedParagraphs + "\n" +
					"Espacios protegidos: " + modifiedSpaces
				);
			},
			ScriptLanguage.JAVASCRIPT,
			undefined,
			UndoModes.ENTIRE_SCRIPT,
			"Evitar corte de nombres de autor"
		);
	}

	run();
}());
