//DESCRIPTION: Jongware's PrepText

if (app.documents.length == 0 || app.selection.length == 0 || app.selection[0].constructor.name != "InsertionPoint")
{
	var selectedType = app.selection.length > 0 ? app.selection[0].constructor.name : "nothing";
	alert ("Cursor in "+selectedType+"\nPlease put the cursor into a text frame");
	exit(0);
}

var myDocument = app.activeDocument;
var mySelection = app.selection[0];
var myStory = mySelection.parent;
var myMaximumValue = 63;
var myProgressBarWidth = 384;
var myIncrement = myMaximumValue/myProgressBarWidth;
var myProgressPanel;
var b, i, s, u, k, c;

myCreateProgressPanel(100, 400);
myProgressPanel.myProgressBar.value = 0;
myProgressPanel.show();

for (b=0; b<2; b++)
{
	for (i=0; i<2; i++)
	{
		for (s=0; s<2; s++)
		{
			for (u=0; u<2; u++)
			{
			//	Don't process strikeout
				for (k=0; k<1; k++)
				{
					for (c=0; c<2; c++)
					{
						if (b+i+s+u+k+c)
						{
							myProgressPanel.myProgressBar.value = 32*b+16*i+8*s+4*u+2*k+c;
							findAttr (b, i, s, false, u, /*k*/false, c, "");
							if (s)
								findAttr (b, i, false, s, u, /*k*/false, c, "");
						}
					}
				}
			}
		}
	}
}
myProgressPanel.hide();

exit(0);

function myCreateProgressPanel(myMaximumValue, myProgressBarWidth)
{
	myProgressPanel = new Window('window', 'Prepping text');
	with(myProgressPanel)
	{
		myProgressPanel.myProgressBar = add('progressbar', [12, 12, myProgressBarWidth, 24], 0, myMaximumValue);
	}
}

function myGetStyleByName(StyleName)
{
	var cstyle = myDocument.characterStyles.itemByName(StyleName);
	if (cstyle.isValid) {
		return cstyle;
	}
	return null;
}

function myBuildStyleName(bold, italic, superscript, subscript, underline, strikeout, smallcaps)
{
	var StyleName = "";
	if (bold)
		StyleName = "Bold";
	if (italic)
	{
		if (bold)
			StyleName = "Bold Italic";
		else
			StyleName = "Italic";
	}
	if (superscript)
	{
		if (StyleName) StyleName += " + ";
		StyleName += "Super";
	}
	if (subscript)
	{
		if (StyleName) StyleName += " + ";
		StyleName += "Sub";
	}
	if (underline)
	{
		if (StyleName) StyleName += " + ";
		StyleName += "Underline";
	}
	if (strikeout)
	{
		if (StyleName) StyleName += " + ";
		StyleName += "Stkout";
	}
	if (smallcaps)
	{
		if (StyleName) StyleName += " + ";
		StyleName += "Scaps";
	}
	return StyleName;
}

function myGetOrCreateStyle(StyleName, bold, italic, superscript, subscript, underline, strikeout, smallcaps)
{
	var cstyle = myGetStyleByName(StyleName);
	if (!cstyle)
	{
		cstyle = myDocument.characterStyles.add({name:StyleName});
	}
	try {
		if (bold || italic) cstyle.fontStyle = app.findTextPreferences.fontStyle;
		if (superscript) cstyle.position = PositionOptions.SUPERSCRIPT;
		if (subscript) cstyle.position = PositionOptions.SUBSCRIPT;
		if (underline) cstyle.underline = app.findTextPreferences.underline;
		if (strikeout) cstyle.strikeThru = app.findTextPreferences.strikeThru;
		if (smallcaps) cstyle.capitalization = CapitalizeOptions.SMALL_CAPS;
	} catch (e) {
	}
	return cstyle;
}

function findAttr (bold, italic, superscript, subscript, underline, strikeout, smallcaps, StyleName)
{
	app.findTextPreferences = NothingEnum.nothing;
	app.changeTextPreferences = NothingEnum.nothing;
	
	// Buscar el estilo "[None]" de forma segura
	var noneStyle = null;
	if (myDocument.characterStyles.length > 0) {
		noneStyle = myDocument.characterStyles[0];
	}
	try {
		var candidate = myDocument.characterStyles.item("[None]");
		if (candidate.isValid) {
			noneStyle = candidate;
		}
	} catch (e) {
		// Ignorar errores de localización o estilos inexistentes.
	}
	
	if (noneStyle && noneStyle.isValid) {
		app.findTextPreferences.appliedCharacterStyle = noneStyle;
	}

	app.findTextPreferences.fontStyle = "Regular";
	app.findTextPreferences.position = PositionOptions.NORMAL;
	app.findTextPreferences.capitalization = CapitalizeOptions.NORMAL;
	app.findTextPreferences.underline = false;
	app.findTextPreferences.strikeThru = false;

	if (bold)
	{
		if (italic)
			app.findTextPreferences.fontStyle = "Bold Italic";
		else
			app.findTextPreferences.fontStyle = "Bold";
	} else
	{
		if (italic)
			app.findTextPreferences.fontStyle = "Italic";
	}
	if (superscript)
		app.findTextPreferences.position = PositionOptions.SUPERSCRIPT;

	if (subscript)
		app.findTextPreferences.position = PositionOptions.SUBSCRIPT;

	if (underline)
		app.findTextPreferences.underline = true;
	if (strikeout)
		app.findTextPreferences.strikeThru = true;
	if (smallcaps)
		app.findTextPreferences.capitalization = CapitalizeOptions.SMALL_CAPS;

	var foundItems = myStory.findText();

	if (foundItems.length > 0)
	{
		if (StyleName == "")
		{
			StyleName = myBuildStyleName(bold, italic, superscript, subscript, underline, strikeout, smallcaps);
		}
		var applyStyle = myGetOrCreateStyle(StyleName, bold, italic, superscript, subscript, underline, strikeout, smallcaps);
		app.changeTextPreferences.appliedCharacterStyle = applyStyle;
		myStory.changeText (false);
	}
}
