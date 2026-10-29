// Solo lectura: vuelca párrafos, estilos y estilos de carácter de los maquetados.
app.scriptPreferences.userInteractionLevel = UserInteractionLevels.NEVER_INTERACT;
var CARPETA = File($.fileName).parent.parent + "/Maquetados", SALIDA = File($.fileName).parent + "/volcados";
Folder(SALIDA).create();
var archivos = Folder(CARPETA).getFiles("*.indd");
var resumen = [];
function ruta(s) { var r = s.name, p = s.parent; while (p && p.constructor && /Group$/.test(p.constructor.name)) { r = p.name + "/" + r; p = p.parent; } return r; }
for (var a = 0; a < archivos.length; a++) {
  var d = app.open(archivos[a], false), o = [];
  try {
    var hs = d.stories;
    // ordenar historias por la página del primer marco
    var lista = [];
    for (var i = 0; i < hs.length; i++) {
      var st = hs[i], pag = 99999, y = 0;
      try { var tc = st.textContainers[0]; pag = tc.parentPage ? tc.parentPage.documentOffset : 99998; y = tc.geometricBounds[0] + (tc.geometricBounds[1] > 105 ? 0.1 : 0); } catch (e) {}
      lista.push([pag, y, i]);
    }
    lista.sort(function (p, q) { return p[0] - q[0] || p[1] - q[1]; });
    for (var n = 0; n < lista.length; n++) {
      var st = hs[lista[n][2]];
      if (!st.contents.replace(/\s/g, "")) continue;
      o.push("### HISTORIA pág " + lista[n][0] + " (" + st.paragraphs.length + " párr, tablas " + st.tables.length + ")");
      var ps = st.paragraphs;
      for (var j = 0; j < ps.length; j++) {
        var p = ps[j], t = p.contents;
        if (typeof t != "string") t = String(t);
        var cs = [], rs = p.textStyleRanges;
        for (var k = 0; k < rs.length; k++) {
          var c = rs[k].appliedCharacterStyle.name;
          if (c != "[Ninguno]" && c != "[None]") cs.push("{" + c + ":" + String(rs[k].contents).substr(0, 25) + "}");
          else if (rs[k].fontStyle != p.appliedParagraphStyle.fontStyle || rs[k].position != Position.NORMAL) cs.push("<local " + rs[k].fontStyle + (rs[k].position != Position.NORMAL ? "," + rs[k].position : "") + ":" + String(rs[k].contents).substr(0, 25) + ">");
        }
        var lst = "";
        try { if (p.bulletsAndNumberingListType != p.appliedParagraphStyle.bulletsAndNumberingListType) lst = " [lista local " + p.bulletsAndNumberingListType + "]"; } catch (e) {}
        try { if (p.tables.length) lst += " [TABLA " + p.tables[0].rows.length + "x" + p.tables[0].columns.length + " estilo " + p.tables[0].appliedTableStyle.name + "]"; } catch (e) {}
        o.push("[" + ruta(p.appliedParagraphStyle) + "]" + lst + " " + t.replace(/\r/g, "").split(String.fromCharCode(0xFEFF)).join("<anclado>").substr(0, 150) + (cs.length ? "   " + cs.join(" ").substr(0, 400) : ""));
      }
    }
    o.push("### GRÁFICOS: " + d.allGraphics.length);
    for (var g = 0; g < d.allGraphics.length; g++) { try { var gr = d.allGraphics[g]; o.push("  " + gr.itemLink.name + " pág " + (gr.parent.parentPage ? gr.parent.parentPage.name : "-") + " objeto " + gr.parent.appliedObjectStyle.name + " anclado " + (gr.parent.parent.constructor.name == "Character")); } catch (e) {} }
    var f = File(SALIDA + "/" + d.name.replace(".indd", ".txt")); f.encoding = "UTF-8"; f.open("w"); f.write(o.join("\n")); f.close();
    resumen.push(d.name + ": " + o.length + " líneas");
  } catch (e) { resumen.push(d.name + " ERROR " + e); }
  d.close(SaveOptions.NO);
}
app.scriptPreferences.userInteractionLevel = UserInteractionLevels.INTERACT_WITH_ALL;
resumen.join("\n");
