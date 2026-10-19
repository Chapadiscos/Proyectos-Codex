//DESCRIPTION: Muestra los estilos de parrafo EN USO en el documento (incluidos los de carpetas/grupos)
// y, en el estilo elegido, evita que la linea termine en palabras cortas (articulos, preposiciones,
// conjunciones...) convirtiendo el espacio que las sigue en espacio de no separacion (nbsp).
// Asi, si la palabra corta no cabe junto con la siguiente en la linea, ambas saltan juntas a la
// linea de abajo y la linea nunca queda cortada en "la", "de", "un", "para", etc.
//
// Nota: InDesign no permite añadir entradas propias al desplegable nativo de estilos de parrafo
// de la ventana de Control mediante scripting. Este script ofrece el equivalente funcional: un
// listado (con la misma jerarquia de carpetas/grupos) pero limitado a los estilos que realmente
// se usan en el documento, con el numero de parrafos que los usan.

(function () {
	var NBSP = " ";

	// Lista editable de palabras "cortas" que no deben quedar como ultima palabra de linea.
	var STOP_WORDS = [
		"a", "al", "ante", "bajo", "cabe", "con", "contra", "de", "del", "desde",
		"donde", "durante", "el", "en", "entre", "es", "esa", "ese", "eso", "esta",
		"este", "esto", "hacia", "hasta", "la", "las", "le", "les", "lo", "los",
		"mi", "mis", "ni", "no", "o", "para", "pero", "por", "que", "se", "segun",
		"si", "sin", "sobre", "su", "sus", "te", "tras", "tu", "tus", "un", "una",
		"unas", "uno", "unos", "y", "ya"
	];

	var STOP_WORDS_SET = {};
	for (var sw = 0; sw < STOP_WORDS.length; sw++) {
		STOP_WORDS_SET[STOP_WORDS[sw]] = true;
	}

	var WORD_CHAR_RE = /[A-Za-zÀ-ÿ]/;

	function repeat(str, n) {
		var s = "";
		for (var i = 0; i < n; i++) {
			s += str;
		}
		return s;
	}

	function computeUsageMap(doc) {
		var map = {};
		var stories = doc.stories.everyItem().getElements();
		for (var s = 0; s < stories.length; s++) {
			var paras = stories[s].paragraphs.everyItem().getElements();
			for (var p = 0; p < paras.length; p++) {
				try {
					var st = paras[p].appliedParagraphStyle;
					map[st.id] = (map[st.id] || 0) + 1;
				} catch (e) {
				}
			}
		}
		return map;
	}

	// Recorre estilos y grupos (carpetas) de forma recursiva, incluyendo solo lo que esta en uso.
	function buildUsedStyleTree(container, depth, items, usageMap) {
		var localItems = [];

		var pstyles = container.paragraphStyles;
		for (var i = 0; i < pstyles.length; i++) {
			var st = pstyles[i];
			if (st.name === "[No Paragraph Style]") {
				continue;
			}
			var count = usageMap[st.id] || 0;
			if (count > 0) {
				localItems.push({
					style: st,
					label: repeat("    ", depth) + st.name + "  (" + count + ")",
					isGroup: false
				});
			}
		}

		var groups = container.paragraphStyleGroups;
		for (var g = 0; g < groups.length; g++) {
			var childItems = [];
			buildUsedStyleTree(groups[g], depth + 1, childItems, usageMap);
			if (childItems.length > 0) {
				localItems.push({
					style: null,
					label: repeat("    ", depth) + "[" + groups[g].name + "]",
					isGroup: true
				});
				for (var k = 0; k < childItems.length; k++) {
					localItems.push(childItems[k]);
				}
			}
		}

		for (var m = 0; m < localItems.length; m++) {
			items.push(localItems[m]);
		}
	}

	function askUserForStyle(doc, usageMap) {
		var items = [];
		buildUsedStyleTree(doc, 0, items, usageMap);

		if (items.length === 0) {
			alert("No se ha encontrado ningun estilo de parrafo en uso en este documento.");
			return null;
		}

		var w = new Window("dialog", "Evitar palabras cortas al final de linea");
		w.orientation = "column";
		w.alignChildren = "fill";
		w.spacing = 10;
		w.margins = 16;

		w.add("statictext", undefined, "Estilos de parrafo en uso (incluye carpetas/grupos). Elige uno:");

		var list = w.add("listbox", undefined, [], { numberOfColumns: 1 });
		list.preferredSize = [380, 280];

		var firstSelectableIndex = -1;
		for (var i = 0; i < items.length; i++) {
			var li = list.add("item", items[i].label);
			li.enabled = !items[i].isGroup;
			li.itemData = items[i];
			if (firstSelectableIndex === -1 && !items[i].isGroup) {
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

		if (w.show() !== 1) {
			return null;
		}

		if (!list.selection || !list.selection.enabled) {
			alert("Selecciona un estilo de parrafo (no una carpeta/grupo).");
			return null;
		}

		return list.selection.itemData.style;
	}

	// Convierte en nbsp el espacio que sigue a cada palabra corta encontrada en el parrafo.
	function protectShortWords(para) {
		var chars = para.characters.everyItem().getElements();
		var wordStart = -1;
		var modified = 0;

		for (var i = 0; i <= chars.length; i++) {
			var c = i < chars.length ? chars[i].contents : "";
			var isWordChar = c.length === 1 && WORD_CHAR_RE.test(c);

			if (isWordChar) {
				if (wordStart === -1) {
					wordStart = i;
				}
			} else {
				if (wordStart !== -1) {
					var word = "";
					for (var j = wordStart; j < i; j++) {
						word += chars[j].contents;
					}
					if (STOP_WORDS_SET[word.toLowerCase()] && c === " ") {
						chars[i].contents = NBSP;
						modified++;
					}
					wordStart = -1;
				}
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
		var usageMap = computeUsageMap(doc);
		var targetStyle = askUserForStyle(doc, usageMap);
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
							if (para.appliedParagraphStyle.id === targetStyle.id) {
								matchedParagraphs++;
								modifiedSpaces += protectShortWords(para);
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
			"Evitar palabras cortas al final de linea"
		);
	}

	run();
}());
