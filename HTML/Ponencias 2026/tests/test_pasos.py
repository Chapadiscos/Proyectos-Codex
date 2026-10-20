import os

from bs4 import BeautifulSoup

from depurar.__main__ import procesar
from depurar.informe import Informe
from depurar.pasos import (
    p01_estilos_capitulo,
    p02_limpieza,
    p03_correcciones_indesign,
    p04_imagenes,
    p05_reglas_helice,
    p06_inyectar,
    p07_salida,
)

CSS_CAPITULO = """
span.CharOverride-1 { font-size:8px; }
li.ParaOverride-1 { margin-left:9px; }
#_idContainer003 { position:relative; width:482px; }
#_idContainer001 { position:absolute; width:481.92px; }
#_idContainer005 { width:227px; }
"""


def _soup(html):
    return BeautifulSoup(html, "lxml")


def _ctx(tmp_path):
    return {
        "dir_entrada": str(tmp_path),
        "resolver": lambda r: os.path.join(tmp_path, r),
        "resolver_raiz": lambda r: os.path.join(tmp_path, r),
    }


def _con_css(tmp_path, cuerpo):
    (tmp_path / "css").mkdir(exist_ok=True)
    (tmp_path / "css" / "id.css").write_text(CSS_CAPITULO, encoding="utf-8")
    return _soup(f'<html><head><link href="css/id.css" rel="stylesheet"></head><body>{cuerpo}</body></html>')


def test_estilos_capitulo_anulaciones_e_imagenes(tmp_path):
    s = _con_css(
        tmp_path,
        '<p><span class="CharOverride-1">pie</span><span class="noPartir-PO26">a b</span></p>'
        '<ul><li class="X ParaOverride-1">x</li></ul>'
        '<div id="_idContainer003"><div id="_idContainer001"><img src="a.jpg"></div><p>pie</p></div>',
    )
    cfg = {
        "clases_anulacion": ["CharOverride-\\d+", "ParaOverride-\\d+"],
        "propiedades": {"span": ["font-size"], "li": []},
        "clases_a_estilo": {"noPartir-PO26": {"white-space": "nowrap"}},
    }
    p01_estilos_capitulo.aplicar(s, cfg, _ctx(tmp_path), Informe())
    spans = s.find_all("span")
    assert spans[0]["style"] == "font-size: 8px"
    assert spans[1]["style"] == "white-space: nowrap"
    assert not s.li.has_attr("style")  # los márgenes de lista los pone Hélice
    assert not s.find(id="_idContainer003").has_attr("style")  # sin anchos automáticos
    assert s.img["style"] == "display: block; max-width: 100%; height: auto; margin: 0 auto"


def test_limpieza_clases_ids_spans_y_divs(tmp_path):
    s = _soup(
        '<div class="_idGenObjectLayout-1"><p id="_idTextAnchor001" class="Normal ParaOverride-1">'
        '<span class="CharOverride-2">Ho</span><span class="negrita">la</span><span class="negrita"> mundo</span>'
        '<span></span></p></div><a href="#_idTextAnchor002">x</a><p id="_idTextAnchor002">y</p>'
    )
    cfg = {
        "clases_eliminar": ["_idGen.*", "CharOverride-\\d+", "ParaOverride-\\d+"],
        "ids_eliminar": ["_idTextAnchor\\d+"],
    }
    p02_limpieza.aplicar(s, cfg, _ctx(tmp_path), Informe())
    assert str(s.body) == (
        '<body><p class="Normal">Ho<span class="negrita">la mundo</span></p>'
        '<a href="#_idTextAnchor002">x</a><p id="_idTextAnchor002">y</p></body>'
    )


def test_correcciones_invisibles_reemplazos_y_br(tmp_path):
    inf = Informe()
    texto = p03_correcciones_indesign.pre(
        "<p>a﻿b  c<br/></p>", {"reemplazos": [{"buscar": "  ", "sustituir": " "}]}, {}, inf
    )
    s = _soup(texto)
    p03_correcciones_indesign.aplicar(s, {}, {}, inf)
    assert str(s.p) == "<p>ab c</p>"


def test_imagenes_por_contenido_no_por_orden(tmp_path):
    (tmp_path / "img").mkdir()
    (tmp_path / "img" / "A.jpg").write_bytes(b"imagen A")
    (tmp_path / "img" / "B.jpg").write_bytes(b"imagen B")
    # Hélice: la URL de B va primero en el .txt; la caché evita descargar en el test
    cache = tmp_path / ".cache"
    cache.mkdir()
    (cache / "111.jpg").write_bytes(b"imagen B")
    (cache / "222.jpg").write_bytes(b"imagen A")
    (cache / "333.jpg").write_bytes(b"otra")
    (tmp_path / "urls.txt").write_text("https://h/111.jpg\nhttps://h/222.jpg\nhttps://h/333.jpg\n", encoding="utf-8")

    s = _soup('<img src="img/A.jpg" alt="a"><img src="img/B.jpg" alt="b"><img src="img/C.jpg" alt="c">')
    inf = Informe()
    p04_imagenes.aplicar(s, {"cache": ".cache"}, _ctx(tmp_path), inf)
    assert [i["src"] for i in s.find_all("img")] == ["https://h/222.jpg", "https://h/111.jpg", "img/C.jpg"]
    assert any("C.jpg" in a for a in inf.avisos)
    assert any("1 URL del .txt no corresponden" in i for i in inf.informacion)  # 333.jpg: solo información


def test_inyectar_html_en_head(tmp_path):
    s = _soup("<html><head><title>t</title></head><body><p>x</p></body></html>")
    cfg = {"head": [{"html": '<link rel="stylesheet" href="https://use.typekit.net/k.css">'}]}
    p06_inyectar.aplicar(s, cfg, _ctx(tmp_path), Informe())
    assert s.head.link["href"] == "https://use.typekit.net/k.css"


def test_salida_fragmento_y_vista_previa(tmp_path):
    (tmp_path / "helice.css").write_text("p{}", encoding="utf-8")
    s = _soup("<html><head><title>t</title><style>a{}</style></head><body><p>x</p></body></html>")
    ctx = _ctx(tmp_path)
    p07_salida.aplicar(s, {"modo": "fragmento", "vista_previa_css": "helice.css"}, ctx, Informe())
    assert ctx["resultado"] == "<style>a{}</style><p>x</p>\n"
    assert "<style>\np{}\n</style>\n</head>" in ctx["vista_previa"]


def test_pipeline_completo(tmp_path):
    (tmp_path / "res" / "css").mkdir(parents=True)
    (tmp_path / "res" / "css" / "id.css").write_text("#_idContainer000 { width:482px; }", encoding="utf-8")
    (tmp_path / "res" / "a.jpg").write_bytes(b"A")
    cache = tmp_path / ".cache"
    cache.mkdir()
    (cache / "x.jpg").write_bytes(b"A")
    (tmp_path / "urls.txt").write_text("https://h/x.jpg\n", encoding="utf-8")
    entrada = tmp_path / "doc.html"
    entrada.write_text(
        '<html><head><link href="res/css/id.css" rel="stylesheet" /></head><body>'
        '<div class="_idGenObjectLayout-1"><div id="_idContainer000"><img src="res/a.jpg" alt="" /></div></div>'
        '<p class="Texto ParaOverride-1">Hola</p></body></html>',
        encoding="utf-8",
    )
    cfg = {
        "limpieza": {
            "clases_eliminar": ["_idGen.*", "ParaOverride-\\d+"],
            "ids_eliminar": ["_idContainer\\d+"],
            "css_eliminar": ["res/"],
        },
        "imagenes": {"cache": str(cache)},
    }
    destino, _ = procesar(str(entrada), cfg, str(tmp_path), str(tmp_path / "salida"))
    with open(destino, encoding="utf-8") as f:
        html = f.read()
    assert '<img alt="" src="https://h/x.jpg" style="display: block; max-width: 100%; height: auto; margin: 0 auto"/>' in html
    assert '<p class="Texto">Hola</p>' in html
    assert "<link" not in html


def test_salida_avisa_estilos_no_permitidos_y_sin_regla(tmp_path):
    (tmp_path / "helice.css").write_text("p.Texto-base-PO26 {}\nli.V-PO26::before {}", encoding="utf-8")
    s = _soup('<p class="Texto-base-PO26">a</p><p class="P-rrafo-b-sico">b</p><ul><li class="V-PO26">c</li></ul>')
    inf = Informe()
    cfg = {"vista_previa_css": "helice.css", "estilos_no_permitidos": ["P-rrafo-b-sico"]}
    p07_salida.aplicar(s, cfg, _ctx(tmp_path), inf)
    assert inf.avisos == [
        "estilo que no debe usarse en InDesign: P-rrafo-b-sico (1 elementos)",
        "clase sin regla en la CSS de Hélice: P-rrafo-b-sico (1 elementos)",
    ]


def test_pie_debajo_en_figura_y_suelto(tmp_path):
    s = _soup(
        '<div style="w"><p class="Pie-Figura-PO26">pie 1</p><img src="a.jpg"></div>'
        '<p>texto</p><p class="Pie-Figura-PO26">pie 2</p><div style="w"><img src="b.jpg"></div>'
    )
    p03_correcciones_indesign.aplicar(s, {"activas": ["pie_debajo"]}, {}, Informe())
    assert str(s.body) == (
        '<body><div style="w"><img src="a.jpg"/><p class="Pie-Figura-PO26">pie 1</p></div>'
        '<p>texto</p><div style="w"><img src="b.jpg"/></div><p class="Pie-Figura-PO26">pie 2</p></body>'
    )


def test_jerarquia_vinetas_con_imagen_entre_medias(tmp_path):
    s = _soup(
        '<ul><li class="V-Viñeta-1">a<ul><li class="V-Viñeta-2">b</li></ul></li></ul>'
        '<div><img src="x.jpg"></div>'
        '<ul><li class="V-Viñeta-2">c</li><li class="V-Viñeta-2">d<ul><li class="V-Viñeta-3">e</li></ul></li>'
        '<li class="V-Viñeta-1">f</li></ul><p>sigue</p>'
    )
    p03_correcciones_indesign.aplicar(s, {"activas": ["jerarquia_vinetas"]}, {}, Informe())
    assert str(s.body) == (
        '<body><ul><li class="V-Viñeta-1">a<ul><li class="V-Viñeta-2">b</li></ul><div><img src="x.jpg"/></div>'
        '<ul><li class="V-Viñeta-2">c</li><li class="V-Viñeta-2">d<ul><li class="V-Viñeta-3">e</li></ul></li></ul></li>'
        '<li class="V-Viñeta-1">f</li></ul><p>sigue</p></body>'
    )


def test_jerarquia_vinetas_no_toca_listas_independientes(tmp_path):
    html = '<body><ul><li class="V-Viñeta-1">a</li></ul><div><img src="x.jpg"/></div><ul><li class="V-Viñeta-1">b</li></ul></body>'
    s = _soup(html)
    p03_correcciones_indesign.aplicar(s, {"activas": ["jerarquia_vinetas"]}, {}, Informe())
    assert str(s.body) == html


REGLAS = {
    "entre_ladillos": '<p style="margin-top: -1.3em; margin-bottom: 0.3em;"></p>',
    "ideas_basicas": {"patron": "^IB\\d+\\."},
}


def test_reglas_helice_saltos_ladillos_alt_e_ideas_basicas(tmp_path):
    s = _soup(
        '<div style="width: 100%"><img src="X1.jpg" alt="algo"></div>'
        '<p class="Ladillos_Ladillo-1-PO26">L1</p><p class="Ladillos_Ladillo-2-PO26">L2</p>'
        '<p class="Texto">t1</p>'
        '<div style="width: 100%"><img src="F1.jpg"><p class="Pie-Figura-PO26">pie</p></div>'
        '<p class="Texto">t2</p>'
        '<img src="IB1.jpg" style="display: block; max-width: 100%">'
        '<p class="Ladillos_Ladillo-1-PO26">L3</p>'
    )
    p05_reglas_helice.aplicar(s, REGLAS, _ctx(tmp_path), Informe())
    assert str(s.body) == (
        '<body><br/><div style="width: 100%"><img alt="" src="X1.jpg"/></div>'
        '<p class="Ladillos_Ladillo-1-PO26">L1</p><p style="margin-top: -1.3em; margin-bottom: 0.3em;"></p>'
        '<p class="Ladillos_Ladillo-2-PO26">L2</p>'
        '<p class="Texto">t1</p><br/>'
        '<div style="width: 100%"><img alt="" src="F1.jpg"/><p class="Pie-Figura-PO26">pie</p></div><br/>'
        '<p class="Texto">t2</p><br/>'
        '<img alt="" src="IB1.jpg" style="display: block; max-width: 60%; margin: 0 auto"/>'
        '<p class="Ladillos_Ladillo-1-PO26">L3</p></body>'
    )


def test_reglas_helice_enlace_cabecera_desde_qr(tmp_path):
    import zxingcpp
    from PIL import Image

    qr = zxingcpp.create_barcode("https://ejemplo.org/cap", zxingcpp.BarcodeFormat.QRCode)
    Image.fromarray(qr.to_image(scale=4)).save(tmp_path / "C7.png")
    s = _soup('<div><img src="C7.png"></div><p>t</p>')
    inf = Informe()
    p05_reglas_helice.aplicar(s, REGLAS, _ctx(tmp_path), inf)
    a = s.find("a")
    assert a["href"] == "https://ejemplo.org/cap" and a["target"] == "_blank"
    assert a.img is not None


def test_capitulo_dentro_de_un_marco_de_texto(tmp_path):
    """Capítulo 33: todo el texto va en un div de marco; la figura no es ese div."""
    s = _soup(
        '<div class="Marco-texto"><p class="Texto">t1</p>'
        '<div class="M"><img src="F1.jpg"></div><p class="Pie-Figura-PO26">pie</p>'
        '<p class="Texto">t2</p><div class="M"><img src="F2.jpg"></div></div>'
    )
    p03_correcciones_indesign.aplicar(s, {"activas": ["pie_debajo"]}, {}, Informe())
    p05_reglas_helice.aplicar(s, REGLAS, _ctx(tmp_path), Informe())
    assert str(s.body) == (
        '<body><br/><div class="Marco-texto"><p class="Texto">t1</p><br/>'
        '<div class="M"><img alt="" src="F1.jpg"/></div><p class="Pie-Figura-PO26">pie</p><br/>'
        '<p class="Texto">t2</p><br/><div class="M"><img alt="" src="F2.jpg"/></div></div></body>'
    )


def test_urls_del_marcador_solo_acepta_listas_de_urls():
    from depurar.capitulo import urls_del_marcador

    lista = "https://h/uploads/app/1/files/a.jpg\nhttps://h/uploads/app/1/files/b.jpg\nhttps://h/uploads/app/1/files/a.jpg\n"
    assert urls_del_marcador(lista) == ["https://h/uploads/app/1/files/a.jpg", "https://h/uploads/app/1/files/b.jpg"]
    # El HTML de un capítulo anterior también contiene URL de Hélice: no vale
    assert urls_del_marcador('<img src="https://h/uploads/app/1/files/a.jpg"/>') == []
    assert urls_del_marcador("") == []


def test_informacion_no_cuenta_como_aviso():
    inf = Informe()
    inf.informar("enlace de C1.jpg: https://x")
    assert inf.avisos == [] and "Información:" in inf.texto()


def test_imagenes_por_parecido_visual_si_cambia_el_jpeg(tmp_path):
    from PIL import Image

    (tmp_path / "img").mkdir()
    cache = tmp_path / ".cache"
    cache.mkdir()
    base = Image.new("RGB", (40, 30), (120, 60, 30))
    base.save(tmp_path / "img" / "F1.jpg", quality=95)
    base.save(cache / "111.jpg", quality=90)  # misma imagen, otros bytes
    Image.new("RGB", (40, 30), (0, 200, 0)).save(cache / "222.jpg")  # misma talla, otra imagen
    (tmp_path / "urls.txt").write_text("https://h/111.jpg\nhttps://h/222.jpg\n", encoding="utf-8")

    s = _soup('<img src="img/F1.jpg">')
    inf = Informe()
    p04_imagenes.aplicar(s, {"cache": ".cache"}, _ctx(tmp_path), inf)
    assert s.img["src"] == "https://h/111.jpg"
    assert inf.cambios["imágenes con URL de Hélice (por parecido visual)"] == 1


def test_cursiva_light_no_engorda_por_font_weight_normal(tmp_path):
    """Bibliografía: InDesign exporta Avenir Light Oblique como oblique + font-weight normal."""
    (tmp_path / "css").mkdir()
    (tmp_path / "css" / "id.css").write_text(
        "span.CharOverride-1 { font-style:oblique; font-weight:normal; }\n"
        "span.CharOverride-2 { font-weight:bold; }",
        encoding="utf-8",
    )
    s = _soup(
        '<html><head><link href="css/id.css" rel="stylesheet"></head><body><ol><li class="Bibliografia-PO26">'
        '<span class="Italic-PO26 CharOverride-1">Ophthalmology</span> <span class="CharOverride-2">B</span></li></ol></body></html>'
    )
    cfg = {
        "clases_anulacion": ["CharOverride-\\d+"],
        "propiedades": {"span": ["font-style", "font-weight"]},
        "valores_descartar": {"font-weight": ["normal", "400"]},
        "equivalencias": {"font-style": {"oblique": "italic"}},
    }
    p01_estilos_capitulo.aplicar(s, cfg, _ctx(tmp_path), Informe())
    spans = s.find_all("span")
    assert spans[0]["style"] == "font-style: italic"
    assert spans[1]["style"] == "font-weight: bold"


def test_enlaces_de_varias_paginas_se_suman(tmp_path, monkeypatch):
    """Panel de Hélice con varias páginas: cada pulsación del marcador añade enlaces al .txt."""
    from depurar import capitulo

    u = [f"https://h/uploads/app/1/files/{i}.jpg" for i in range(4)]
    txt = tmp_path / "33Ponencias2026.txt"
    monkeypatch.setattr(capitulo, "pegar", lambda: "\n".join(u[:2]))
    capitulo._preparar_urls(str(tmp_path), 33, {})
    monkeypatch.setattr(capitulo, "pegar", lambda: "\n".join(u[1:]))  # repite una de la página anterior
    capitulo._preparar_urls(str(tmp_path), 33, {})
    assert sorted(txt.read_text(encoding="utf-8").split()) == u


def test_imagen_sin_url_se_apunta_y_las_urls_de_mas_no_avisan(tmp_path):
    (tmp_path / "img").mkdir()
    (tmp_path / "img" / "A.jpg").write_bytes(b"imagen A")
    cache = tmp_path / ".cache"
    cache.mkdir()
    (cache / "1.jpg").write_bytes(b"otra imagen")
    (tmp_path / "urls.txt").write_text("https://h/1.jpg\n", encoding="utf-8")
    s = _soup('<img src="img/A.jpg">')
    inf = Informe()
    p04_imagenes.aplicar(s, {"cache": ".cache"}, _ctx(tmp_path), inf)
    assert inf.sin_url == ["A.jpg"]
    assert inf.avisos == ["imagen sin URL en Hélice: A.jpg"]  # la URL sobrante es solo información


def test_jerarquia_vinetas_con_parrafo_de_texto_de_vineta(tmp_path):
    """Capítulo 46: V1, párrafo Texto-base---Viñeta y V2 sueltas -> V2 dentro de su V1."""
    s = _soup(
        '<ul><li class="V-Viñeta-1">Dermatitis</li></ul>'
        '<p class="Texto-base---Viñeta-PO26">Explicación</p>'
        '<ul><li class="V-Viñeta-2">Alérgica</li><li class="V-Viñeta-2">Irritativa</li></ul>'
        '<p class="Texto-base-PO26">Sigue</p>'
    )
    p03_correcciones_indesign.aplicar(s, {"activas": ["jerarquia_vinetas"]}, {}, Informe())
    assert str(s.body) == (
        '<body><ul><li class="V-Viñeta-1">Dermatitis'
        '<p class="Texto-base---Viñeta-PO26" style="margin-left: 0">Explicación</p>'
        '<ul><li class="V-Viñeta-2">Alérgica</li><li class="V-Viñeta-2">Irritativa</li></ul></li></ul>'
        '<p class="Texto-base-PO26">Sigue</p></body>'
    )


def test_jerarquia_vinetas_con_madre_numerada(tmp_path):
    """Capítulo 65: «1.» numerado (ol), párrafo de texto de viñeta y guiones de nivel 2."""
    s = _soup(
        '<ol><li class="V-Viñeta-1">Sustancias</li></ol>'
        '<p class="Texto-base---Viñeta-PO26">Explicación</p>'
        '<ul><li class="V-Viñeta-2">BSS</li></ul>'
        '<ul><li class="V-Viñeta-1">Otros</li></ul>'
    )
    p03_correcciones_indesign.aplicar(s, {"activas": ["jerarquia_vinetas"]}, {}, Informe())
    assert str(s.body) == (
        '<body><ol><li class="V-Viñeta-1">Sustancias'
        '<p class="Texto-base---Viñeta-PO26" style="margin-left: 0">Explicación</p>'
        '<ul><li class="V-Viñeta-2">BSS</li></ul></li></ol>'
        '<ul><li class="V-Viñeta-1">Otros</li></ul></body>'
    )


def test_vinetas_numeradas_con_subvineta_del_mismo_nivel(tmp_path):
    """Capítulo 70: «a.» (V2 numerada) con un «-» de V2 metido dentro, y la marca «-» del ::before."""
    s = _soup(
        '<ul><li class="V-Viñeta-1">Fijación<ol>'
        '<li class="V-Viñeta-2" style="list-style-type: lower-alpha">a'
        '<ul><li class="V-Viñeta-2">Reposición</li></ul></li></ol></li></ul>'
    )
    cfg = {"clase_numerada": "V-Viñeta-1", "clases_con_marca_propia": {"V-Viñeta-2": {"margin-left": "-28px"}}}
    p03_correcciones_indesign.aplicar(s, cfg, {}, Informe())
    assert str(s.body) == (
        '<body><ul><li class="V-Viñeta-1">Fijación<ol>'
        '<li class="V-Viñeta-1" style="list-style-type: lower-alpha; margin-left: -28px">a</li></ol>'
        '<ul><li class="V-Viñeta-2">Reposición</li></ul></li></ul></body>'
    )


def test_font_weight_normal_es_la_version_light_de_la_familia(tmp_path):
    """Cap. 52: cita en un ladillo (BC Civitas Light) y cap. 35: cursiva de bibliografía (Avenir Light)."""
    (tmp_path / "css").mkdir()
    (tmp_path / "css" / "id.css").write_text(
        "span.CharOverride-1 { color:#000000; font-weight:normal; }\n"
        "span.CharOverride-2 { font-style:oblique; font-weight:normal; }",
        encoding="utf-8",
    )
    (tmp_path / "helice.css").write_text(
        "p.Ladillo-1-PO26 { font-family: bc-civitas, sans-serif; font-weight: 700; }\n"
        "li.Bibliografia-PO26 { font-family: avenir-lt-pro, sans-serif; font-weight: 200; }",
        encoding="utf-8",
    )
    s = _soup(
        '<html><head><link href="css/id.css" rel="stylesheet"></head><body>'
        '<p class="Ladillo-1-PO26">PRUEBAS <span class="CharOverride-1">(2-15)</span></p>'
        '<ol><li class="Bibliografia-PO26"><span class="CharOverride-2">Ophthalmology</span></li></ol>'
        '<p class="Otro"><span class="CharOverride-1">x</span></p></body></html>'
    )
    cfg = {
        "clases_anulacion": ["CharOverride-\\d+"],
        "propiedades": {"span": ["color", "font-style", "font-weight"]},
        "css_helice": "helice.css",
        "peso_normal_por_familia": {"bc-civitas": "300", "avenir-lt-pro": "200"},
        "valores_descartar": {"font-weight": ["normal", "400"]},
        "equivalencias": {"font-style": {"oblique": "italic"}},
    }
    p01_estilos_capitulo.aplicar(s, cfg, _ctx(tmp_path), Informe())
    spans = s.find_all("span")
    assert spans[0]["style"] == "color: #000000; font-weight: 300"  # hereda negrita: Light
    assert spans[1]["style"] == "font-style: italic"  # hereda el 200 de la bibliografía
    assert spans[2]["style"] == "color: #000000"  # familia desconocida: se descarta como antes


def _caso_pesos(tmp_path, cuerpo, tsv=None):
    (tmp_path / "css").mkdir(exist_ok=True)
    (tmp_path / "css" / "id.css").write_text("span.CharOverride-1 { font-style:normal; font-weight:normal; }", encoding="utf-8")
    (tmp_path / "helice.css").write_text(
        "p.Pie-Figura-PO26 { font-family: bc-civitas, sans-serif; font-weight: 400; }\n"
        "span._5-Medium-PO26 { font-style:normal; font-weight:600; }",
        encoding="utf-8",
    )
    if tsv:
        (tmp_path / "salida").mkdir(exist_ok=True)
        (tmp_path / "salida" / "cap.fuentes.tsv").write_text(tsv, encoding="utf-8")
    s = _soup(f'<html><head><link href="css/id.css" rel="stylesheet"></head><body>{cuerpo}</body></html>')
    cfg = {
        "clases_anulacion": ["CharOverride-\\d+"],
        "propiedades": {"span": ["font-style", "font-weight"]},
        "css_helice": "helice.css",
        "pesos_indesign": {"BC Civitas": {"Light": 300, "Regular": 400, "Medium": 500, "Bold": 700},
                           "Neue Haas Grotesk Display Pro": {"Light": 400, "Medium": 600}},
        "peso_normal_por_familia": {"bc-civitas": "300"},
        "valores_descartar": {"font-weight": ["normal", "400"]},
    }
    ctx = {**_ctx(tmp_path), "ruta_html": str(tmp_path / "cap.html")}
    inf = Informe()
    p01_estilos_capitulo.aplicar(s, cfg, ctx, inf)
    return s.find_all("span"), inf


def test_pesos_reales_de_indesign(tmp_path):
    """Cap. 43: pie en BC Civitas Medium; cap. 35: Medium Italic con estilo propio."""
    spans, inf = _caso_pesos(
        tmp_path,
        '<p class="Pie-Figura-PO26"><span class="CharOverride-1">Celulitis preseptal </span>en paciente</p>'
        '<p><span class="_5-Medium-PO26 CharOverride-1">bypass</span></p>',
        "Celulitis preseptal \tBC Civitas\tMedium\nbypass\tNeue Haas Grotesk Display Pro\t66 Medium Italic\n",
    )
    assert spans[0]["style"] == "font-style: normal; font-weight: 500"
    assert spans[1]["style"] == "font-style: normal; font-weight: 600"
    assert any("tomados de InDesign" in i for i in inf.informacion)


def test_pesos_sin_indesign_respeta_el_estilo_propio_y_el_parrafo(tmp_path):
    spans, _ = _caso_pesos(
        tmp_path,
        '<p class="Pie-Figura-PO26"><span class="CharOverride-1">Celulitis</span></p>'
        '<p><span class="_5-Medium-PO26 CharOverride-1">bypass</span></p>',
    )
    assert spans[0]["style"] == "font-style: normal"  # el pie es 400: hereda
    assert spans[1]["style"] == "font-style: normal"  # su estilo _5-Medium manda (600)
