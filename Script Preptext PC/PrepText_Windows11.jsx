//DESCRIPTION: PrepText Windows 11 - converts local text formatting to character styles
#target "indesign"

(function () {
    var SCRIPT_NAME = "PrepText Windows 11";

    if (!app.documents.length) {
        alert("Open an InDesign document before running " + SCRIPT_NAME + ".");
        return;
    }

    var doc = app.activeDocument;
    if (!doc.selection.length || doc.selection[0].constructor.name !== "InsertionPoint") {
        var selectionName = doc.selection.length ? doc.selection[0].constructor.name : "nothing";
        alert("Cursor is in " + selectionName + ".\nPlease put the cursor inside a text frame.");
        return;
    }

    app.doScript(function () {
        run(doc, doc.selection[0]);
    }, ScriptLanguage.JAVASCRIPT, undefined, UndoModes.ENTIRE_SCRIPT, SCRIPT_NAME);

    function run(documentRef, insertionPoint) {
        var scope = getTextScope(insertionPoint);
        var ranges = collectRangesToChange(documentRef, scope);
        var progress = createProgressPanel(Math.max(ranges.length, 1));
        var report = {
            changed: 0,
            stylesCreated: 0,
            stylesReused: 0,
            skipped: 0
        };

        try {
            progress.show();
            if (!ranges.length) {
                progress.label.text = "No local formatting found.";
                updateProgress(progress);
                $.sleep(150);
            }

            for (var index = 0; index < ranges.length; index++) {
                progress.bar.value = index + 1;
                progress.label.text = "Processing " + (index + 1) + " of " + ranges.length;
                updateProgress(progress);

                try {
                    applyCharacterStyle(documentRef, ranges[index], report);
                } catch (error) {
                    report.skipped++;
                }
            }
        } finally {
            resetFindChangePreferences();
            try {
                progress.close();
            } catch (error) {
            }
        }

        alert(
            SCRIPT_NAME + " complete.\n\n" +
            "Text ranges changed: " + report.changed + "\n" +
            "Styles created: " + report.stylesCreated + "\n" +
            "Existing styles reused: " + report.stylesReused + "\n" +
            "Skipped ranges: " + report.skipped
        );
    }

    function collectRangesToChange(documentRef, scope) {
        var ranges = [];
        var noneStyle = documentRef.characterStyles[0];
        collectTextStyleRanges(scope, noneStyle, ranges);
        collectFootnoteRanges(scope, noneStyle, ranges);

        return ranges;
    }

    function collectTextStyleRanges(textObject, noneStyle, ranges) {
        var textStyleRanges;
        try {
            textStyleRanges = textObject.textStyleRanges;
        } catch (error) {
            return;
        }

        if (!textStyleRanges || !textStyleRanges.length) {
            return;
        }

        for (var index = 0; index < textStyleRanges.length; index++) {
            var textRange = textStyleRanges[index];
            if (!textRange.isValid || !usesNoneCharacterStyle(textRange, noneStyle)) {
                continue;
            }

            var attributes = getLocalAttributes(textRange);
            if (!hasConvertibleFormatting(attributes)) {
                continue;
            }

            ranges.push({
                textRange: textRange,
                attributes: attributes,
                styleName: makeStyleName(attributes)
            });
        }
    }

    function collectFootnoteRanges(scope, noneStyle, ranges) {
        var footnotes;
        try {
            footnotes = scope.footnotes;
        } catch (error) {
            return;
        }

        if (!footnotes || !footnotes.length) {
            return;
        }

        for (var index = 0; index < footnotes.length; index++) {
            var footnote = footnotes[index];
            if (!footnote.isValid) {
                continue;
            }

            try {
                if (footnote.texts.length) {
                    collectTextStyleRanges(footnote.texts[0], noneStyle, ranges);
                }
            } catch (error) {
                collectTextStyleRanges(footnote, noneStyle, ranges);
            }
        }
    }

    function applyCharacterStyle(documentRef, rangeInfo, report) {
        if (!rangeInfo.textRange.isValid) {
            report.skipped++;
            return;
        }

        var style = getOrCreateCharacterStyle(documentRef, rangeInfo, report);
        rangeInfo.textRange.appliedCharacterStyle = style;
        report.changed++;
    }

    function getTextScope(insertionPoint) {
        try {
            if (insertionPoint.parentStory && insertionPoint.parentStory.isValid) {
                return insertionPoint.parentStory;
            }
        } catch (error) {
        }
        return insertionPoint.parent;
    }

    function usesNoneCharacterStyle(textRange, noneStyle) {
        try {
            return textRange.appliedCharacterStyle === noneStyle ||
                textRange.appliedCharacterStyle.name === noneStyle.name;
        } catch (error) {
            return false;
        }
    }

    function getLocalAttributes(textRange) {
        var fontStyle = getStringProperty(textRange, "fontStyle");
        var position = getProperty(textRange, "position", Position.normal);
        var capitalization = getProperty(textRange, "capitalization", Capitalization.normal);

        return {
            bold: isBoldFontStyle(fontStyle),
            italic: isItalicFontStyle(fontStyle),
            fontStyle: fontStyle,
            superscript: position === Position.superscript,
            subscript: position === Position.subscript,
            underline: getProperty(textRange, "underline", false) === true,
            strikeout: false,
            smallcaps: capitalization === Capitalization.smallCaps
        };
    }

    function hasConvertibleFormatting(attributes) {
        return attributes.bold ||
            attributes.italic ||
            attributes.superscript ||
            attributes.subscript ||
            attributes.underline ||
            attributes.smallcaps;
    }

    function getOrCreateCharacterStyle(documentRef, rangeInfo, report) {
        var style = documentRef.characterStyles.itemByName(rangeInfo.styleName);
        if (style.isValid) {
            report.stylesReused++;
            return style;
        }

        style = documentRef.characterStyles.add({ name: rangeInfo.styleName });
        applyAttributesToStyle(style, rangeInfo.attributes);
        report.stylesCreated++;
        return style;
    }

    function applyAttributesToStyle(style, attributes) {
        if ((attributes.bold || attributes.italic) && attributes.fontStyle) {
            try {
                style.fontStyle = attributes.fontStyle;
            } catch (error) {
            }
        }
        if (attributes.superscript) {
            style.position = Position.superscript;
        }
        if (attributes.subscript) {
            style.position = Position.subscript;
        }
        if (attributes.underline) {
            style.underline = true;
        }
        if (attributes.smallcaps) {
            style.capitalization = Capitalization.smallCaps;
        }
    }

    function makeStyleName(attributes) {
        var parts = [];
        if (attributes.bold && attributes.italic) {
            parts.push("Bold Italic");
        } else if (attributes.bold) {
            parts.push("Bold");
        } else if (attributes.italic) {
            parts.push("Italic");
        }
        if (attributes.superscript) {
            parts.push("Super");
        }
        if (attributes.subscript) {
            parts.push("Sub");
        }
        if (attributes.underline) {
            parts.push("Underline");
        }
        if (attributes.smallcaps) {
            parts.push("Scaps");
        }
        return parts.join(" + ");
    }

    function isBoldFontStyle(fontStyle) {
        var normalized = fontStyle.toLowerCase();
        return contains(normalized, "bold") ||
            contains(normalized, "semibold") ||
            contains(normalized, "demi") ||
            contains(normalized, "black") ||
            contains(normalized, "heavy") ||
            contains(normalized, "negrita");
    }

    function isItalicFontStyle(fontStyle) {
        var normalized = fontStyle.toLowerCase();
        return contains(normalized, "italic") ||
            contains(normalized, "oblique") ||
            contains(normalized, "cursiva") ||
            contains(normalized, "italica") ||
            contains(normalized, "italique");
    }

    function contains(value, needle) {
        return value.indexOf(needle) !== -1;
    }

    function getStringProperty(objectRef, propertyName) {
        try {
            return String(objectRef[propertyName]);
        } catch (error) {
            return "";
        }
    }

    function getProperty(objectRef, propertyName, defaultValue) {
        try {
            return objectRef[propertyName];
        } catch (error) {
            return defaultValue;
        }
    }

    function createProgressPanel(maximumValue) {
        var panel = new Window("palette", SCRIPT_NAME);
        panel.orientation = "column";
        panel.alignChildren = ["fill", "top"];
        panel.margins = 12;
        panel.label = panel.add("statictext", undefined, "Preparing...");
        panel.bar = panel.add("progressbar", undefined, 0, maximumValue);
        panel.bar.preferredSize = [420, 16];
        return panel;
    }

    function updateProgress(progress) {
        try {
            progress.update();
        } catch (error) {
        }
    }

    function resetFindChangePreferences() {
        app.findTextPreferences = NothingEnum.nothing;
        app.changeTextPreferences = NothingEnum.nothing;
    }
}());
