#!/usr/bin/env python3
"""Compara la hoja del cuadro de dos libros (p. ej. un MANUAL hecho con la app y su TERMINADO):
anchos de columna y altos de fila en puntos del Excel de Mac, cada celda (texto y formato) y las formas.
Uso: comparar.py <libro A> <libro B> [hoja A] [hoja B]"""
import sys, re, zipfile, html
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "motor"))
import maquetar_cuadros as m


def leer(ruta, hoja=None):
    z = zipfile.ZipFile(ruta)
    hoja = hoja or m.hoja_cuadro(z)[0]
    x = z.read(m.hoja_de(z, hoja)).decode("utf-8")
    est = m.Estilos(z.read("xl/styles.xml").decode("utf-8"))
    mdw = m.digito_maximo(est.xml)
    _, comp = m.leer_compartidos(z)
    celdas = m.celdas_hoja(x, comp)
    ancho = m.anchos_columnas(x)
    altos, defecto = m.altos_filas(z, hoja)

    def formato(s):
        xf = est.xf(s)
        f = est.fuente_de(s)
        nombre = re.search(r'<name val="([^"]*)"', f); sz = re.search(r'<sz val="([^"]*)"', f)
        color = re.search(r'<color\b([^>]*)/>', f)
        letra = f"{nombre.group(1) if nombre else '?'} {sz.group(1) if sz else '?'}" + (" negrita" if m.es_negrita(f) and 'Medium' not in (nombre.group(1) if nombre else '') else "")
        if color and re.search(r'rgb="FFFFFFFF"|theme="0"', color.group(1)):
            letra += " blanca"
        fid = int(re.search(r'fillId="(\d+)"', xf).group(1)) if 'fillId' in xf else 0
        relleno = (est.rellenos + est.nuevos_rellenos)[fid] if fid < len(est.rellenos) else ""
        rgb = re.search(r'<fgColor\b([^>]*)/>', relleno)
        relleno = ("" if 'patternType="none"' in relleno or not rgb else
                   re.sub(r'rgb="FF(\w+)"', r'#\1', rgb.group(1)).replace('theme=', 'tema').replace('tint=', 'tinte').replace('"', '').strip())
        bid = int(re.search(r'borderId="(\d+)"', xf).group(1)) if 'borderId' in xf else 0
        borde = (est.bordes)[bid] if bid < len(est.bordes) else ""
        lados = []
        for lado in ("left", "right", "top", "bottom"):
            b = re.search(rf'<{lado} style="(\w+)">(.*?)</{lado}>', borde, re.S)
            if b:
                c = re.search(r'rgb="FF(\w+)"|theme="(\d+)"(?:\s+tint="([-\d.]+)")?', b.group(2))
                col = (c.group(1) if c and c.group(1) else f"tema{c.group(2)}{'%+.2f' % float(c.group(3)) if c and c.group(3) else ''}" if c else "?")
                lados.append(f"{lado[0]}:{col}")
        al = est.alineacion(s)
        alin = "/".join(v for k, v in al.items() if k in ("horizontal", "vertical"))
        return letra, relleno, " ".join(lados), alin
    return {"hoja": hoja, "mdw": mdw, "celdas": celdas, "ancho": ancho, "altos": altos, "defecto": defecto,
            "formato": formato, "zip": z, "x": x}


a = leer(sys.argv[1], sys.argv[3] if len(sys.argv) > 3 else None)
b = leer(sys.argv[2], sys.argv[4] if len(sys.argv) > 4 else None)
print(f"A: {Path(sys.argv[1]).name} (hoja «{a['hoja']}»)\nB: {Path(sys.argv[2]).name} (hoja «{b['hoja']}»)\n")
ultima_col = max(c for c, f in list(a["celdas"]) + list(b["celdas"]) if a["celdas"].get((c, f), b["celdas"].get((c, f), {})).get("texto", "").strip() or True)
ultima_col = min(ultima_col, 30)
print("ANCHOS (pt, Excel de Mac)")
print("   " + "  ".join(f"{m.ref(c, 1)[:-1]}:{round(a['ancho'](c) * a['mdw'])}/{round(b['ancho'](c) * b['mdw'])}" for c in range(1, ultima_col + 1)))
ta = sum(round(a['ancho'](c) * a['mdw']) for c in range(1, ultima_col + 1)); tb = sum(round(b['ancho'](c) * b['mdw']) for c in range(1, ultima_col + 1))
ultima_fila = max(f for c, f in list(a["celdas"]) + list(b["celdas"]))
ultima_fila = min(ultima_fila, 80)
print("\nALTOS (pt)")
print("   " + "  ".join(f"{f}:{a['altos'].get(f - 1, a['defecto']) / 12700:g}/{b['altos'].get(f - 1, b['defecto']) / 12700:g}" for f in range(1, ultima_fila + 1)))
print("\nCELDAS (A | B), solo las distintas")
for f in range(1, ultima_fila + 1):
    for c in range(1, ultima_col + 1):
        ca, cb = a["celdas"].get((c, f)), b["celdas"].get((c, f))
        ta_, tb_ = (ca or {}).get("texto", ""), (cb or {}).get("texto", "")
        fa = a["formato"](ca["s"]) if ca else ("", "", "", "")
        fb = b["formato"](cb["s"]) if cb else ("", "", "", "")
        if not (ta_.strip() or tb_.strip() or fa[1] or fb[1] or fa[2] or fb[2]):
            continue
        dif = []
        if ta_ != tb_:
            dif.append(f"texto «{ta_[:40]}» | «{tb_[:40]}»")
        for nombre, x, y in zip(("letra", "relleno", "bordes", "alineación"), fa, fb):
            if x != y:
                dif.append(f"{nombre} {x or '—'} | {y or '—'}")
        if dif:
            print(f"   {m.ref(c, f)}: " + "; ".join(dif))


def formas(z, hoja):
    d = m.dibujo_de_hoja(z, hoja)
    salida = []
    if not d:
        return salida
    dib = z.read(d).decode("utf-8")
    caja = m.medidas_hoja(z, hoja, dib)
    for an in m.ANCLA.finditer(dib):
        x0 = an.group(0)
        texto = html.unescape(m.texto_forma(x0)).replace("\n", " / ").strip()
        if not texto and "<xdr:grpSp>" not in x0[:1500] and m.sin_relleno(x0):
            continue
        X, Y, W, H = caja(x0)
        tam = sorted(set(re.findall(r'<a:rPr\b[^>]*\bsz="(\d+)"', x0)))
        fuentes = sorted(set(re.findall(r'latin typeface="([^"]*)"', x0)))
        salida.append(f"{m.nombre_forma(x0)[:16]:16} y={Y / 36000:5.1f} h={H / 36000:5.1f} ancho={W / 36000:5.1f} mm  "
                      f"{','.join(t[:-2] for t in tam)} pt {','.join(fuentes)}  «{texto[:60]}»")
    return salida
print("\nFORMAS A"); [print("   " + l) for l in formas(a["zip"], a["hoja"])]
print("FORMAS B"); [print("   " + l) for l in formas(b["zip"], b["hoja"])]
