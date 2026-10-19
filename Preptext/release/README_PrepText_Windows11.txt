PrepText Windows 11
===================

Version: 1.6.1

What it does
------------
This Adobe InDesign ExtendScript converts local text formatting into character
styles. Put the cursor inside a text frame and run the script. It scans the
current story and creates/applies character styles for combinations of:

- Bold
- Italic
- Superscript
- Subscript
- Underline
- Small caps

Strikeout is intentionally not processed, matching the original script behavior.
It applies those character styles and then clears all paragraph style overrides
from the active story and its footnotes so the imported Word text is left
cleaner.

Windows 11 installation
-----------------------
1. Open Adobe InDesign.
2. Open Window > Utilities > Scripts.
3. Right-click the User folder and choose Reveal in Explorer.
4. Copy PrepText_Windows11.jsx into the Scripts Panel folder.
5. Return to InDesign and double-click PrepText_Windows11.jsx from the Scripts panel.

Notes
-----
- The cursor must be inside a text frame before running the script.
- The script only changes text that currently has the [None] character style.
- The script runs as one undoable action.
- Version 1.0.1 removes app.refresh(), which is not available in some
  InDesign/Windows installations.
- Version 1.1.0 reads textStyleRanges directly instead of relying on
  findTextPreferences.fontStyle. This is more reliable with localized or
  font-specific style names such as Negrita, Cursiva, Oblique, and Bold Italic.
- Version 1.2.0 also processes footnote text ranges in the active story.
- Version 1.3.0 clears paragraph-only overrides in the active story and its
  footnotes after character styles have been applied.
- Version 1.5.0 tried to clear all paragraph style overrides before reapplying
  generated character styles.
- Version 1.6.0 applies generated character styles first and then clears all
  paragraph style overrides, avoiding expanded live ranges after cleanup.
- Version 1.6.1 translates the final summary alert and progress labels to
  Spanish.

Files
-----
- PrepText_Windows11.jsx: modernized script.
- preptext Windows original.jsx: untouched backup of the original script.
