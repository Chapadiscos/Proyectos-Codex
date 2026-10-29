"""Bloque 3: Claude propone qué hacer con cada duda ortotipográfica (cambiar u omitir).

Usa el Claude Code de la extensión de VS Code sin interfaz (`-p`), con la suscripción del
usuario y sin herramientas: solo lee las dudas y su contexto y responde con un JSON validado.
"""
import json
import subprocess
from pathlib import Path

ESQUEMA = {
    "type": "object",
    "required": ["propuestas"],
    "properties": {
        "propuestas": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["id", "accion", "texto_nuevo", "formato", "motivo", "diccionario"],
                "properties": {
                    "id": {"type": "integer"},
                    "accion": {"type": "string", "enum": ["cambiar", "omitir"]},
                    "texto_nuevo": {"type": "string"},
                    "formato": {"type": "string", "enum": ["", "cursiva", "redonda"]},
                    "motivo": {"type": "string"},
                    "diccionario": {"type": "boolean"},
                },
            },
        },
    },
}

SISTEMA = """Eres corrector ortotipográfico de una editorial de libros de medicina en español
(oftalmología, urgencias). Un revisor automático (LanguageTool y reglas propias) ha marcado
dudas en un capítulo. Para cada una decide qué hacer; el maquetador verá tu propuesta en
InDesign y la aceptará o no.

Criterios: Ortografía de la RAE y Fundéu; ante cualquier otra duda ortotipográfica, el
criterio de Vancouver (ICMJE). En concreto:
- Nombres científicos de organismos (género y especie, «spp.» aparte) en cursiva:
  Fusarium, Pseudomonas aeruginosa. Los nombres de fármacos, enfermedades y pruebas van en
  redonda y minúscula (aciclovir, valaciclovir); los epónimos en redonda (tinción de Gram).
- Extranjerismos crudos en cursiva (melting, flare, feathery); si hay una adaptación
  asentada en español, propón usarla (triage → triaje).
- Los términos médicos correctos que el diccionario no conoce (estromal, ketorolaco,
  penfigoide…) no son errores: omitir y diccionario = true.
- Las erratas claras se corrigen (hipostesia → hipoestesia, el el → el).
- LanguageTool se equivoca a menudo con la concordancia en textos técnicos (sobre todo en
  tablas y listas) y con homónimos («sangre» no es «sangré»): si la frase está bien, omitir.
- «Criterio»: el capítulo escribe lo mismo de dos maneras; propón la forma correcta según
  la norma (p. ej. «grampositivo», sin guion, según la RAE) aunque no sea la mayoritaria.

Para cada duda devuelve:
- id: el de la duda.
- accion: "cambiar" si cambias el texto o el formato; "omitir" si el fragmento se queda como está.
- texto_nuevo: si cambias el texto, el texto exacto que sustituirá al marcado entre [ ]
  (solo ese fragmento, con sus espacios); si no cambia el texto, cadena vacía.
- formato: "cursiva" o "redonda" si hay que cambiar el formato del fragmento; si no, "".
- motivo: una frase corta en español para el maquetador (sin nombres de reglas internas).
- diccionario: true solo si el fragmento es una palabra correcta que conviene añadir al
  diccionario de la publicación para no volver a marcarla."""


def claude_ejecutable():
    candidatos = sorted(Path.home().glob('.vscode/extensions/anthropic.claude-code-*/resources/native-binary/claude'),
                        key=lambda p: [int(x) if x.isdigit() else x for x in p.parts[-4].replace('-', '.').split('.')])
    if not candidatos:
        raise RuntimeError('No encuentro Claude Code (extensión de VS Code)')
    return str(candidatos[-1])


def proponer(dudas, capitulo, timeout=900):
    """dudas: lista de dicts (de Duda) con 'id'. Devuelve {id: propuesta}."""
    lineas = []
    for d in dudas:
        aviso = d['motivo'] + (' (sugerencia: %s)' % d['sugerencia'] if d['sugerencia'] else '')
        lineas.append(json.dumps({'id': d['id'], 'tipo': d['tipo'], 'texto': d['texto'], 'contexto': d['contexto'],
                                  'estilo': d['estilo'], 'aviso': aviso}, ensure_ascii=False))
    peticion = ('Capítulo «%s». Dudas (una por línea, en JSON; el fragmento dudoso va entre [ ] en el '
                'contexto):\n%s' % (capitulo, '\n'.join(lineas)))
    orden = [claude_ejecutable(), '-p', peticion, '--append-system-prompt', SISTEMA,
             '--tools', '', '--setting-sources', '', '--no-session-persistence',
             '--output-format', 'json', '--json-schema', json.dumps(ESQUEMA)]
    r = subprocess.run(orden, capture_output=True, text=True, timeout=timeout)
    datos = json.loads(r.stdout) if r.stdout.strip() else {}
    if datos.get('is_error') or 'structured_output' not in datos:
        raise RuntimeError((datos.get('result') or r.stderr or 'Claude no devolvió resultado').strip()[:500])
    props = {p['id']: p for p in datos['structured_output']['propuestas']}
    # A veces responde «omitir» y a la vez pide cursiva: si cambia texto o formato, es cambiar.
    textos = {d['id']: d['texto'] for d in dudas}
    for k, p in props.items():
        if p['formato'] or (p['texto_nuevo'] and p['texto_nuevo'] != textos.get(k)):
            p['accion'] = 'cambiar'
        if p['texto_nuevo'] == textos.get(k):
            p['texto_nuevo'] = ''
    return props
