//DESCRIPTION: Add style-panel context-menu commands to find the clicked paragraph or character style.
#targetengine "findStyleFromStylePanelContextMenu"

(function () {
	var NOTHING = NothingEnum.NOTHING || NothingEnum.nothing;
	var ACTION_PARAGRAPH = "Buscar estilo parrafo";
	var ACTION_CHARACTER = "Buscar estilo caracter";
	var OLD_ACTION_PARAGRAPH = "Buscar este estilo de parrafo";
	var OLD_ACTION_CHARACTER = "Buscar este estilo de caracter";
	var STYLE_LIST_MENU = "$ID/RtMenuStyleListItem";

	function removeScriptMenuAction(name) {
		try {
			var action = app.scriptMenuActions.itemByName(name);
			if (action.isValid) {
				action.remove();
			}
		} catch (e) {
		}
	}

	function resetFindChange() {
		app.findTextPreferences = NOTHING;
		app.changeTextPreferences = NOTHING;
		app.findGrepPreferences = NOTHING;
		app.changeGrepPreferences = NOTHING;
	}

	function getMenuByNames(names) {
		for (var i = 0; i < names.length; i++) {
			try {
				var menu = app.menus.itemByName(names[i]);
				if (menu.isValid) {
					return menu;
				}
			} catch (e) {
			}

			try {
				menu = app.menus.item(names[i]);
				if (menu.isValid) {
					return menu;
				}
			} catch (e2) {
			}
		}

		return null;
	}

	function stripAccelerator(text) {
		return text.replace(/&/g, "");
	}

	function extractQuotedName(text) {
		var cleaned = stripAccelerator(text);
		var match = cleaned.match(/["\u201C\u201D](.+?)["\u201C\u201D]/);
		if (match) {
			return match[1];
		}

		return null;
	}

	function getStyleNameFromContextMenu() {
		var menu = getMenuByNames([STYLE_LIST_MENU, "Text Style List Context Menu"]);
		if (!menu) {
			return null;
		}

		var elements = menu.menuElements.everyItem().getElements();
		for (var i = 0; i < elements.length; i++) {
			if (elements[i].constructor.name == "MenuSeparator") {
				continue;
			}

			var title = "";
			try {
				title = elements[i].title || elements[i].name || "";
			} catch (e) {
			}

			if (
				title.match(/^\s*(Edit|Editar)\s+["\u201C\u201D]/i) ||
				title.match(/^\s*(Apply|Aplicar)\s+["\u201C\u201D]/i) ||
				title.match(/^\s*(Convert|Convertir).+["\u201C\u201D]/i)
			) {
				var styleName = extractQuotedName(title);
				if (styleName) {
					return styleName;
				}
			}
		}

		return null;
	}

	function collectStyles(container, collectionName, styles) {
		var collection = container[collectionName];
		for (var i = 0; i < collection.length; i++) {
			styles.push(collection[i]);
		}
	}

	function collectStyleGroups(groups, styleCollectionName, groupCollectionName, styles) {
		for (var i = 0; i < groups.length; i++) {
			collectStyles(groups[i], styleCollectionName, styles);
			collectStyleGroups(groups[i][groupCollectionName], styleCollectionName, groupCollectionName, styles);
		}
	}

	function getStylesByName(kind, styleName) {
		var documentRef = app.activeDocument;
		var styles = [];

		if (kind == "paragraph") {
			collectStyles(documentRef, "paragraphStyles", styles);
			collectStyleGroups(documentRef.paragraphStyleGroups, "paragraphStyles", "paragraphStyleGroups", styles);
		} else {
			collectStyles(documentRef, "characterStyles", styles);
			collectStyleGroups(documentRef.characterStyleGroups, "characterStyles", "characterStyleGroups", styles);
		}

		var matches = [];
		for (var i = 0; i < styles.length; i++) {
			if (styles[i].isValid && styles[i].name == styleName) {
				matches.push(styles[i]);
			}
		}

		return matches;
	}

	function getSelectedStyleFromPanelFallback(kind) {
		var documentRef = app.activeDocument;
		if (!documentRef.pages.length) {
			return null;
		}

		var frame = null;
		try {
			frame = documentRef.pages[0].textFrames.add({
				geometricBounds: ["0p", "0p", "1p", "12p"],
				contents: "x"
			});

			var insertionPoint = frame.parentStory.insertionPoints[0];
			if (kind == "paragraph") {
				return insertionPoint.appliedParagraphStyle;
			}

			return insertionPoint.appliedCharacterStyle;
		} catch (e) {
			return null;
		} finally {
			try {
				if (frame && frame.isValid) {
					frame.remove();
				}
			} catch (e2) {
			}
		}
	}

	function setFindStyle(kind, style) {
		if (kind == "paragraph") {
			app.findTextPreferences.properties = {
				appliedParagraphStyle: style
			};
			app.findGrepPreferences.properties = {
				appliedParagraphStyle: style
			};
		} else {
			app.findTextPreferences.properties = {
				appliedCharacterStyle: style
			};
			app.findGrepPreferences.properties = {
				appliedCharacterStyle: style
			};
		}
	}

	function openFindChangeDialog() {
		var action = app.menuActions.itemByName("$ID/Find/Change...");
		if (!action.isValid) {
			action = app.menuActions.itemByName("Find/Change...");
		}
		if (!action.isValid) {
			action = app.menuActions.itemByName("Buscar/Cambiar...");
		}

		if (action.isValid) {
			action.invoke();
		} else {
			alert("No se pudo abrir Buscar/Cambiar.");
		}
	}

	function findStyleFromPanel(kind) {
		if (!app.documents.length) {
			alert("Abre un documento antes de buscar un estilo.");
			return;
		}

		var styleName = getStyleNameFromContextMenu();
		var style = null;

		if (styleName) {
			var matches = getStylesByName(kind, styleName);
			if (!matches.length) {
				alert("No se encontro un estilo de " + (kind == "paragraph" ? "parrafo" : "caracter") + ' llamado "' + styleName + '".');
				return;
			}
			if (matches.length > 1) {
				alert('Hay mas de un estilo llamado "' + styleName + '". Se usara el primero encontrado.');
			}
			style = matches[0];
		} else {
			style = getSelectedStyleFromPanelFallback(kind);
		}

		if (!style || !style.isValid) {
			alert("No se pudo detectar el estilo del panel.");
			return;
		}

		resetFindChange();
		setFindStyle(kind, style);
		openFindChangeDialog();
	}

	function createAction(name, kind) {
		removeScriptMenuAction(name);

		var action = app.scriptMenuActions.add(name);
		action.eventListeners.add("onInvoke", function () {
			findStyleFromPanel(kind);
		});
		return action;
	}

	function installMenuItem(menu, action) {
		try {
			var oldItem = menu.menuItems.itemByName(action.name);
			if (oldItem.isValid) {
				oldItem.remove();
			}
		} catch (e) {
		}

		menu.menuItems.add(action);
	}

	var styleListMenu = getMenuByNames([STYLE_LIST_MENU, "Text Style List Context Menu"]);
	if (styleListMenu) {
		try {
			styleListMenu.menuItems.itemByName(OLD_ACTION_PARAGRAPH).remove();
		} catch (e) {
		}
		try {
			styleListMenu.menuItems.itemByName(OLD_ACTION_CHARACTER).remove();
		} catch (e2) {
		}
		removeScriptMenuAction(OLD_ACTION_PARAGRAPH);
		removeScriptMenuAction(OLD_ACTION_CHARACTER);
		installMenuItem(styleListMenu, createAction(ACTION_PARAGRAPH, "paragraph"));
		installMenuItem(styleListMenu, createAction(ACTION_CHARACTER, "character"));
	} else {
		alert("No se encontro el menu contextual de la lista de estilos de InDesign.");
	}
}());
