// Utilidades que se anteponen a todos los scripts.
// ExtendScript no trae JSON: json(v) serializa objetos, arrays, cadenas, números y booleanos.
function json(v) {
    if (v === null || v === undefined) return "null";
    var t = typeof v;
    if (t === "number") return isFinite(v) ? String(v) : "null";
    if (t === "boolean") return String(v);
    if (t === "string") {
        var s = "";
        for (var n = 0; n < v.length; n++) {
            var c = v.charAt(n), cc = v.charCodeAt(n);
            if (c === '"' || c === "\\") s += "\\" + c;
            else if (cc < 32 || cc === 0x2028 || cc === 0x2029) s += "\\u" + ("0000" + cc.toString(16)).slice(-4);
            else s += c;
        }
        return '"' + s + '"';
    }
    if (v instanceof Array) {
        var a = [];
        for (var i = 0; i < v.length; i++) a.push(json(v[i]));
        return "[" + a.join(",") + "]";
    }
    var p = [];
    for (var k in v) if (v.hasOwnProperty(k)) p.push(json(String(k)) + ":" + json(v[k]));
    return "{" + p.join(",") + "}";
}
