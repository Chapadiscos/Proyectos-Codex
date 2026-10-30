// Búsqueda inteligente: buscar y cambiar en InDesign describiendo en español lo que se quiere.
// Es la ventana «Buscar con Claude» de InDesign hecha app de Mac: Claude Code busca en segundo
// plano con el servidor MCP de «Ventana Buscar con Claude en Indesign» (sin modificarlo) y aquí
// se ve en directo cada paso; la revisión (Cambiar / Omitir / Cambiar todo, un solo paso de
// deshacer por documento) la ejecuta jsx/revision.jsx dentro de InDesign.
// No instala nada en InDesign. Compilar con app/compilar_app.sh.

import SwiftUI
import AppKit
import UniformTypeIdentifiers

// MARK: - Rutas

/// Carpeta del proyecto: la que contiene la .app
let proyecto = Bundle.main.bundleURL.deletingLastPathComponent()
let ajustes = UserDefaults.standard

/// Carpeta del servidor MCP (servidor.py y su .venv); se cambia con
/// `defaults write es.estudioencuadre.busqueda-inteligente motor "<ruta>"`
let motor: URL = {
    if let ruta = ajustes.string(forKey: "motor") { return URL(fileURLWithPath: ruta) }
    return proyecto.deletingLastPathComponent().appendingPathComponent("Ventana Buscar con Claude en Indesign")
}()
let revisionJSX = proyecto.appendingPathComponent("jsx/revision.jsx")
let carpetaClaude = proyecto.appendingPathComponent("claude")
let idInDesign = "com.adobe.InDesign"
let herramientas = "mcp__indesign__estado,mcp__indesign__consultar,mcp__indesign__ver_pagina,mcp__indesign__probar_cambio"

let temporal: URL = {
    let u = FileManager.default.temporaryDirectory.appendingPathComponent("busqueda_inteligente")
    try? FileManager.default.createDirectory(at: u, withIntermediateDirectories: true)
    return u
}()

/// El claude de la extensión de VS Code (la versión más alta), o el que se indique con
/// `defaults write es.estudioencuadre.busqueda-inteligente claude "<ruta>"`
func claudeEjecutable() -> URL? {
    let fm = FileManager.default
    if let ruta = ajustes.string(forKey: "claude") { return URL(fileURLWithPath: ruta) }
    let extensiones = fm.homeDirectoryForCurrentUser.appendingPathComponent(".vscode/extensions")
    let candidatos = ((try? fm.contentsOfDirectory(atPath: extensiones.path)) ?? [])
        .filter { $0.hasPrefix("anthropic.claude-code-") }
        .sorted { $0.compare($1, options: .numeric) == .orderedAscending }
        .map { extensiones.appendingPathComponent("\($0)/resources/native-binary/claude") }
        .filter { fm.isExecutableFile(atPath: $0.path) }
    if let c = candidatos.last { return c }
    for ruta in ["~/.local/bin/claude", "/opt/homebrew/bin/claude", "/usr/local/bin/claude"] {
        let p = (ruta as NSString).expandingTildeInPath
        if fm.isExecutableFile(atPath: p) { return URL(fileURLWithPath: p) }
    }
    return nil
}

func inDesignAbierto() -> NSRunningApplication? {
    NSRunningApplication.runningApplications(withBundleIdentifier: idInDesign).first
}

// MARK: - Modelo

enum Ambito: String, CaseIterable, Identifiable {
    case seleccion, articulo, documento, documentos, libro

    var id: String { rawValue }

    var titulo: String {
        switch self {
        case .seleccion: return "Selección"
        case .articulo: return "Artículo"
        case .documento: return "Documento"
        case .documentos: return "Todos los documentos"
        case .libro: return "Libro"
        }
    }

    var icono: String {
        switch self {
        case .seleccion: return "character.cursor.ibeam"
        case .articulo: return "text.alignleft"
        case .documento: return "doc.text"
        case .documentos: return "doc.on.doc"
        case .libro: return "books.vertical"
        }
    }
}

struct DocAbierto: Identifiable, Hashable {
    let nombre: String
    let ventana: Bool
    let modificado: Bool
    var id: String { nombre }
}

struct LibroAbierto: Identifiable, Hashable {
    let nombre: String
    let ruta: String
    var id: String { ruta }
}

/// Lo que hay abierto en InDesign y los ámbitos que tienen sentido con su selección
struct Contexto {
    var abierto = false
    var version = ""
    var documentos: [DocAbierto] = []
    var libros: [LibroAbierto] = []
    var activo: String?
    var opciones: [Ambito] = []
    var selRef: String?
    var artRef: String?
    var seleccion: String?
    var propia = false
    var firma = ""
}

/// Dónde busca Claude (lo mismo que recibía buscar.py)
struct Alcance {
    let tipo: Ambito
    var documentos: [String]
    var ref: String?
    var libro: String?

    var paraClaude: String {
        let docs = documentos.map { "«\($0)»" }.joined(separator: ", ")
        switch tipo {
        case .seleccion: return "Ámbito: solo el texto seleccionado en \(docs): resolve(\"\(ref ?? "")\")."
        case .articulo: return "Ámbito: solo el artículo (historia) donde está el cursor en \(docs): resolve(\"\(ref ?? "")\")."
        case .libro: return "Ámbito: todos los capítulos del libro «\(libro ?? "")»: \(docs) (abiertos, algunos sin ventana)."
        case .documentos: return "Ámbito: todos estos documentos abiertos: \(docs)."
        case .documento: return "Ámbito: todo el documento \(docs)."
        }
    }

    var resumen: String {
        switch tipo {
        case .seleccion: return "la selección de «\(corto(documentos.first ?? ""))»"
        case .articulo: return "el artículo de «\(corto(documentos.first ?? ""))»"
        case .documento: return "«\(corto(documentos.first ?? ""))»"
        case .documentos: return "\(documentos.count) documentos"
        case .libro: return "\(documentos.count) capítulos de «\(corto(libro ?? ""))»"
        }
    }
}

enum EstadoCaso: String {
    case pendiente = "", hecho, omitido, error
}

/// Un resultado de la búsqueda
struct Caso: Identifiable {
    let id: Int
    let documento: String
    let pagina: String
    let pre: String
    let encontrado: String
    let post: String
    let descripcion: String   // objetos (marcos, imágenes…): no son texto
    let propuesta: String
    let dudoso: Bool
    let motivo: String
    var estado: EstadoCaso = .pendiente
    var error = ""
}

struct Cambio {
    let descripcion: String
    let codigo: String
}

/// Antes y después del resultado elegido, con su contexto
struct Detalle {
    let k: Int
    let pre: String
    let antes: String
    let despues: String
    let post: String
}

struct Ejemplo: Identifiable {
    let id = UUID()
    let antes: String
    let despues: String
}

/// Un paso de lo que hace Claude, para la pestaña Actividad
struct Paso: Identifiable {
    enum Tipo { case inicio, idea, nota, herramienta, aviso, fin }

    let id = UUID()
    let tipo: Tipo
    var titulo: String
    var detalle = ""        // el código que ejecuta, o su razonamiento
    var respuesta = ""      // lo que contestó InDesign, resumido
    var completa = ""       // la respuesta entera
    var ejemplos: [Ejemplo] = []
    var ok: Bool?
    var herramienta = ""
    let hora = Date()
    var fin: Date?
}

struct Reciente: Codable, Identifiable, Hashable {
    let texto: String
    let ambito: String
    let fecha: Date
    let resultados: Int
    var id: String { texto }
}

struct Aviso: Identifiable {
    let id = UUID()
    let titulo: String
    let texto: String
}

enum Filtro: String, CaseIterable, Identifiable {
    case todos, pendientes, dudosos, cambiados
    var id: String { rawValue }
}

enum Panel: Hashable {
    case revision, actividad
}

// MARK: - Utilidades

func corto(_ nombre: String) -> String {
    nombre.replacingOccurrences(of: ".indd", with: "", options: [.caseInsensitive, .anchored, .backwards])
        .replacingOccurrences(of: ".indb", with: "", options: [.caseInsensitive, .anchored, .backwards])
}

func leer(_ url: URL) -> String {
    (try? String(contentsOf: url, encoding: .utf8)) ?? ""
}

func primeraLinea(_ s: String, _ maximo: Int) -> String {
    let l = s.trimmingCharacters(in: .whitespacesAndNewlines).components(separatedBy: .newlines).first ?? ""
    return l.count > maximo ? String(l.prefix(maximo)) + "…" : l
}

func segundos(_ t: TimeInterval) -> String {
    let s = Int(t.rounded())
    return s < 60 ? "\(s) s" : "\(s / 60) min \(s % 60) s"
}

/// «claude-opus-5-5» → «Opus 5.5»
func nombreModelo(_ id: String) -> String {
    let partes = id.replacingOccurrences(of: "claude-", with: "").split(separator: "-").map(String.init)
    guard let primero = partes.first else { return id }
    return ([primero.capitalized] + [partes.dropFirst().joined(separator: ".")]).joined(separator: " ")
}

/// Cadena de AppleScript entre comillas
func cadenaAS(_ s: String) -> String {
    "\"" + s.replacingOccurrences(of: "\\", with: "\\\\").replacingOccurrences(of: "\"", with: "\\\"") + "\""
}

/// Ejecuta un AppleScript con osascript y lo corta si pasa del tiempo (InDesign ocupado o con un
/// diálogo abierto). Devuelve si fue bien y la salida.
func osascript(_ guion: String, espera: TimeInterval) async -> (ok: Bool, texto: String) {
    await withCheckedContinuation { continuacion in
        DispatchQueue.global().async {
            let p = Process()
            p.executableURL = URL(fileURLWithPath: "/usr/bin/osascript")
            p.arguments = ["-e", guion]
            let salida = Pipe(), errores = Pipe()
            p.standardOutput = salida
            p.standardError = errores
            do { try p.run() } catch {
                continuacion.resume(returning: (false, error.localizedDescription))
                return
            }
            let limite = DispatchWorkItem { if p.isRunning { p.terminate() } }
            DispatchQueue.global().asyncAfter(deadline: .now() + espera, execute: limite)
            let datos = salida.fileHandleForReading.readDataToEndOfFile()
            let error = errores.fileHandleForReading.readDataToEndOfFile()
            p.waitUntilExit()
            limite.cancel()
            let ok = p.terminationStatus == 0
            let texto = String(decoding: ok ? datos : error, as: UTF8.self).trimmingCharacters(in: .whitespacesAndNewlines)
            continuacion.resume(returning: (ok, texto))
        }
    }
}

/// Ejecuta una acción de jsx/revision.jsx dentro de InDesign y devuelve su respuesta.
/// Los datos van en un .json aparte (pueden ser cientos de resultados). Nunca abre InDesign.
func enInDesign(_ accion: String, _ datos: [String: Any]? = nil, espera: TimeInterval = 120) async -> [String: Any] {
    guard inDesignAbierto() != nil else { return ["error": "InDesign no está abierto"] }
    var ruta = ""
    if let datos, let json = try? JSONSerialization.data(withJSONObject: datos) {
        // ExtendScript no admite estos dos separadores sin escapar dentro de una cadena
        let texto = String(decoding: json, as: UTF8.self)
            .replacingOccurrences(of: "\u{2028}", with: "\\u2028").replacingOccurrences(of: "\u{2029}", with: "\\u2029")
        let url = temporal.appendingPathComponent("datos-\(UUID().uuidString).json")
        try? texto.write(to: url, atomically: true, encoding: .utf8)
        ruta = url.path
    }
    defer { if !ruta.isEmpty { try? FileManager.default.removeItem(atPath: ruta) } }
    // POSIX file dentro del tell de InDesign falla (-1708): se convierte fuera
    let guion = """
    set archivo to POSIX file \(cadenaAS(revisionJSX.path))
    with timeout of \(Int(espera)) seconds
    tell application id "\(idInDesign)"
    return do script archivo language javascript with arguments {\(cadenaAS(accion)), \(cadenaAS(ruta))}
    end tell
    end timeout
    """
    let r = await osascript(guion, espera: espera + 5)
    guard r.ok else {
        if r.texto.contains("-1712") || r.texto.isEmpty { return ["error": "InDesign no ha respondido (¿hay un diálogo abierto?)"] }
        if r.texto.contains("-1743") { return ["error": "macOS no deja que la app controle InDesign: actívalo en Ajustes › Privacidad y seguridad › Automatización"] }
        return ["error": r.texto]
    }
    guard let obj = try? JSONSerialization.jsonObject(with: Data(r.texto.utf8)) as? [String: Any] else {
        return ["error": "Respuesta inesperada de InDesign: \(r.texto.prefix(300))"]
    }
    return obj
}

/// Texto de un tool_result (cadena o lista de bloques)
func textoDe(_ contenido: Any?) -> String {
    if let s = contenido as? String { return s }
    let bloques = contenido as? [[String: Any]] ?? []
    return bloques.compactMap { $0["type"] as? String == "text" ? $0["text"] as? String : nil }.joined(separator: "\n")
}

func describirValor(_ v: Any?) -> String {
    switch v {
    case let a as [Any]:
        return a.isEmpty ? "No encuentra nada" : "Encuentra \(a.count) elemento\(a.count == 1 ? "" : "s")"
    case let d as [String: Any]:
        let partes = d.keys.sorted().prefix(5).map { k -> String in
            switch d[k] {
            case let a as [Any]: return "\(k): \(a.count)"
            case let n as NSNumber: return "\(k): \(n)"
            case let s as String: return "\(k): \(primeraLinea(s, 40))"
            default: return k
            }
        }
        return partes.joined(separator: " · ")
    case let n as NSNumber: return "Responde \(n)"
    case let s as String: return primeraLinea(s, 200)
    default: return "Sin datos"
    }
}

/// Resume lo que contestó InDesign a una herramienta de Claude
func resumir(_ herramienta: String, _ texto: String, error: Bool) -> (String, [Ejemplo]) {
    if error { return ("Error: " + primeraLinea(texto, 240), []) }
    let obj = try? JSONSerialization.jsonObject(with: Data(texto.utf8), options: [.fragmentsAllowed])
    switch herramienta {
    case "estado":
        if let d = obj as? [String: Any] {
            let n = (d["documentos"] as? [Any])?.count ?? 0
            let activo = ((d["activo"] as? [String: Any])?["nombre"] as? String).map { " · activo «\(corto($0))»" } ?? ""
            return ("\(n) documento\(n == 1 ? "" : "s") abierto\(n == 1 ? "" : "s")\(activo)", [])
        }
    case "consultar":
        if let d = obj as? [String: Any] { return (describirValor(d["resultado"]), []) }
    case "probar_cambio":
        if let l = obj as? [[String: Any]] {
            let ejemplos = l.map { p -> Ejemplo in
                let despues = (p["despues"] as? String) ?? (p["error"] as? String).map { "Error: \($0)" } ?? (p["aviso"] as? String) ?? ""
                return Ejemplo(antes: (p["antes"] as? String ?? "").replacingOccurrences(of: "\r", with: " ¶ "),
                               despues: despues.replacingOccurrences(of: "\r", with: " ¶ "))
            }
            let mal = l.filter { $0["error"] != nil || $0["aviso"] != nil }.count
            return (mal == 0 ? "El cambio sale bien en \(l.count == 1 ? "la prueba" : "las \(l.count) pruebas")"
                             : "\(mal) de \(l.count) pruebas no salen bien", ejemplos)
        }
    case "ver_pagina": return ("Ha visto la imagen de la página", [])
    case "StructuredOutput": return ("", [])
    default: break
    }
    return (primeraLinea(texto, 240), [])
}

/// Qué hace Claude con cada herramienta, en palabras del maquetador; y el código, si lo hay
func describirHerramienta(_ nombre: String, _ input: [String: Any]) -> (titulo: String, codigo: String) {
    switch nombre {
    case "estado": return ("Mira qué hay abierto en InDesign", "")
    case "consultar":
        let d = input["documento"] as? String ?? ""
        return (d.isEmpty ? "Consulta el documento activo" : "Consulta «\(corto(d))»", input["codigo"] as? String ?? "")
    case "ver_pagina":
        let p = input["pagina"] as? String ?? ""
        return (p.isEmpty ? "Mira la página visible" : "Mira la página \(p)", "")
    case "probar_cambio":
        let n = (input["refs"] as? [Any])?.count ?? 0
        return ("Prueba el cambio en \(n) resultado\(n == 1 ? "" : "s") y lo deshace", input["aplicar"] as? String ?? "")
    case "StructuredOutput":
        let n = (input["resultados"] as? [Any])?.count ?? 0
        return ("Entrega \(n) resultado\(n == 1 ? "" : "s")", "")
    default:
        let datos = (try? JSONSerialization.data(withJSONObject: input, options: [.prettyPrinted])).map { String(decoding: $0, as: UTF8.self) } ?? ""
        return (nombre, datos)
    }
}

/// «…texto ⟦marcado⟧ texto…» con lo marcado resaltado
func conMarcas(_ s: String, color: Color) -> AttributedString {
    var r = AttributedString()
    var resto = Substring(s)
    while let a = resto.range(of: "⟦") {
        r.append(AttributedString(String(resto[..<a.lowerBound])))
        resto = resto[a.upperBound...]
        let b = resto.range(of: "⟧")
        // Los espacios se ven como en los caracteres ocultos de InDesign: si no, un espacio resaltado no se distingue
        let marcado = String(resto[..<(b?.lowerBound ?? resto.endIndex)])
            .replacingOccurrences(of: "[\\p{Zs}\\t]", with: "·", options: .regularExpression)
        var m = AttributedString(marcado)
        m.backgroundColor = color.opacity(0.22)
        m.inlinePresentationIntent = .stronglyEmphasized
        r.append(m)
        resto = b.map { resto[$0.upperBound...] } ?? ""
    }
    r.append(AttributedString(String(resto)))
    return r
}

func resaltado(_ pre: String, _ medio: String, _ post: String, color: Color) -> AttributedString {
    conMarcas(pre + "⟦" + (medio.isEmpty ? "∅" : medio) + "⟧" + post, color: color)
}

// MARK: - Buscador

@MainActor
final class Buscador: ObservableObject {
    @Published var texto = ""
    @Published var ambito: Ambito = .documento
    @Published var contexto = Contexto()
    @Published var libro: LibroAbierto?
    @Published var buscando = false
    @Published var inicio: Date?
    @Published var duracion: TimeInterval?
    @Published var pasos: [Paso] = []
    @Published var alcance: Alcance?
    @Published var resumen = ""
    @Published var errorBusqueda: String?
    @Published var buscada = false
    @Published var casos: [Caso] = []
    @Published var cambio: Cambio?
    @Published var seleccion: Int?
    @Published var detalle: Detalle?
    @Published var filtro: Filtro = .todos
    @Published var panel: Panel = .revision
    @Published var mensaje = ""
    @Published var ocupado = false
    @Published var uso: Double?
    @Published var modelo = ""
    @Published var recientes: [Reciente] = []
    @Published var aviso: Aviso?

    private var proceso: Process?
    private var detenida = false
    private var ultimoAlcance: Alcance?
    private var firma = ""
    private var textoBuscado = ""
    private var resultadoFinal: [String: Any]?
    private var errorFinal: String?
    private var pasoDeHerramienta: [String: Int] = [:]
    private var leyendoContexto = false

    init() {
        if let datos = ajustes.data(forKey: "recientes"),
           let l = try? JSONDecoder().decode([Reciente].self, from: datos) { recientes = l }
    }

    // MARK: Contexto de InDesign

    var ambitosDisponibles: [Ambito] {
        contexto.abierto ? contexto.opciones + [.libro] : [.documento]
    }

    var hechos: Int { casos.filter { $0.estado == .hecho }.count }
    var pendientes: Int { casos.filter { $0.estado == .pendiente }.count }
    var dudosos: Int { casos.filter { $0.dudoso }.count }

    var casosFiltrados: [Caso] {
        switch filtro {
        case .todos: return casos
        case .pendientes: return casos.filter { $0.estado == .pendiente }
        case .dudosos: return casos.filter { $0.dudoso }
        case .cambiados: return casos.filter { $0.estado == .hecho }
        }
    }

    func leerContexto() async -> Contexto? {
        guard inDesignAbierto() != nil else { return Contexto() }
        let r = await enInDesign("contexto", espera: 20)
        if let e = r["error"] as? String {
            mensaje = e
            return nil
        }
        var c = Contexto()
        c.abierto = true
        c.version = r["version"] as? String ?? ""
        c.documentos = (r["documentos"] as? [[String: Any]] ?? []).map {
            DocAbierto(nombre: $0["nombre"] as? String ?? "", ventana: $0["ventana"] as? Bool ?? true,
                       modificado: $0["modificado"] as? Bool ?? false)
        }
        c.libros = (r["libros"] as? [[String: Any]] ?? []).map {
            LibroAbierto(nombre: $0["nombre"] as? String ?? "", ruta: $0["ruta"] as? String ?? "")
        }
        c.activo = r["activo"] as? String
        c.opciones = (r["opciones"] as? [String] ?? []).compactMap(Ambito.init(rawValue:))
        c.selRef = r["selRef"] as? String
        c.artRef = r["artRef"] as? String
        c.seleccion = r["seleccion"] as? String
        c.propia = r["propia"] as? Bool ?? false
        c.firma = r["firma"] as? String ?? ""
        return c
    }

    /// Al volver a la app: lo que haya seleccionado el usuario en InDesign propone el ámbito
    func refrescarContexto() async {
        guard !leyendoContexto else { return }
        leyendoContexto = true
        defer { leyendoContexto = false }
        guard let c = await leerContexto() else { return }
        contexto = c
        if c.firma != firma {
            firma = c.firma
            // Lo seleccionado es un resultado que puso la app: no es una selección del usuario
            if c.propia { ambito = ultimoAlcance.map(\.tipo).flatMap { c.opciones.contains($0) || $0 == .libro ? $0 : nil } ?? .documento }
            else if ambito != .libro { ambito = c.opciones.first ?? .documento }
        }
        if !ambitosDisponibles.contains(ambito) { ambito = ambitosDisponibles.first ?? .documento }
        if libro == nil || !c.libros.contains(where: { $0.ruta == libro?.ruta }) {
            if let l = c.libros.first, libro == nil { libro = l }
        }
    }

    var descripcionAmbito: String {
        guard contexto.abierto else { return "InDesign no está abierto" }
        let doc = contexto.activo.map { "«\(corto($0))»" } ?? "ningún documento"
        switch ambito {
        case .seleccion: return "\(contexto.seleccion ?? "El texto seleccionado") en \(doc)"
        case .articulo: return "El artículo donde está el cursor, en \(doc)"
        case .documento: return contexto.activo == nil ? "No hay ningún documento abierto" : "Todo \(doc)"
        case .documentos: return "Los \(contexto.documentos.filter(\.ventana).count) documentos abiertos"
        case .libro: return libro.map { "Todos los capítulos de «\(corto($0.nombre))», aunque estén cerrados" } ?? "Elige un libro"
        }
    }

    func elegirLibroEnDisco() {
        let panel = NSOpenPanel()
        panel.title = "Elige el libro de InDesign"
        panel.allowedContentTypes = [UTType(filenameExtension: "indb") ?? .data]
        if let ultima = ajustes.string(forKey: "carpetaLibro") { panel.directoryURL = URL(fileURLWithPath: ultima) }
        guard panel.runModal() == .OK, let url = panel.url else { return }
        ajustes.set(url.deletingLastPathComponent().path, forKey: "carpetaLibro")
        libro = LibroAbierto(nombre: url.lastPathComponent, ruta: url.path)
        ambito = .libro
    }

    // MARK: Búsqueda

    func buscar() {
        let t = texto.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !buscando else { return }
        guard !t.isEmpty else { mensaje = "Escribe qué quieres buscar"; return }
        guard let claude = claudeEjecutable() else {
            aviso = Aviso(titulo: "No encuentro Claude Code",
                          texto: "La búsqueda usa el Claude Code de la extensión de VS Code. Instálala o indica otra ruta con\ndefaults write es.estudioencuadre.busqueda-inteligente claude \"<ruta>\"")
            return
        }
        let python = motor.appendingPathComponent(".venv/bin/python")
        let servidor = motor.appendingPathComponent("servidor.py")
        guard FileManager.default.isExecutableFile(atPath: python.path), FileManager.default.fileExists(atPath: servidor.path) else {
            aviso = Aviso(titulo: "No encuentro el servidor de InDesign",
                          texto: "La búsqueda usa servidor.py y su .venv en\n\(motor.path)\nPara otra carpeta:\ndefaults write es.estudioencuadre.busqueda-inteligente motor \"<ruta>\"")
            return
        }
        guard let indesign = inDesignAbierto() else {
            aviso = Aviso(titulo: "InDesign no está abierto", texto: "Abre InDesign y el documento donde quieres buscar.")
            return
        }
        if ambito == .libro && libro == nil { elegirLibroEnDisco(); guard libro != nil else { return } }
        let nombreApp = indesign.bundleURL?.deletingPathExtension().lastPathComponent ?? "Adobe InDesign 2026"

        // Empieza de cero: la revisión anterior se cierra (sus cambios se quedan, como «Terminar»)
        buscando = true
        detenida = false
        inicio = Date()
        duracion = nil
        pasos = []
        resumen = ""
        errorBusqueda = nil
        buscada = false
        casos = []
        cambio = nil
        seleccion = nil
        detalle = nil
        filtro = .todos
        panel = .actividad
        textoBuscado = t
        resultadoFinal = nil
        errorFinal = nil
        pasoDeHerramienta = [:]
        mensaje = ""

        Task {
            _ = await enInDesign("cerrar")
            guard let c = await leerContexto() else { fallo(mensaje); return }
            contexto = c
            guard let a = await prepararAlcance(c) else { return }
            guard buscando, !detenida else { return }
            alcance = a
            ultimoAlcance = a
            lanzar(claude: claude, python: python, servidor: servidor, nombreApp: nombreApp, alcance: a, texto: t)
        }
    }

    private func fallo(_ texto: String) {
        buscando = false
        errorBusqueda = texto
        pasos.append(Paso(tipo: .aviso, titulo: texto, ok: false))
    }

    private func prepararAlcance(_ c: Contexto) async -> Alcance? {
        switch ambito {
        case .seleccion, .articulo:
            // Lo seleccionado es un resultado puesto por la app: mismo ámbito que la vez anterior
            if c.propia, let u = ultimoAlcance, u.tipo == ambito { return u }
            guard let doc = c.activo, let ref = ambito == .seleccion ? c.selRef : c.artRef else {
                fallo(ambito == .seleccion ? "Ya no hay texto seleccionado en InDesign" : "El cursor ya no está en un texto")
                return nil
            }
            return Alcance(tipo: ambito, documentos: [doc], ref: ref)
        case .documento:
            guard let doc = c.activo else { fallo("No hay ningún documento abierto en InDesign"); return nil }
            return Alcance(tipo: .documento, documentos: [doc])
        case .documentos:
            let docs = c.documentos.filter(\.ventana).map(\.nombre)
            guard !docs.isEmpty else { fallo("No hay ningún documento abierto en InDesign"); return nil }
            return Alcance(tipo: .documentos, documentos: docs)
        case .libro:
            guard let l = libro else { fallo("Elige un libro"); return nil }
            var p = Paso(tipo: .herramienta, titulo: "Abre los capítulos de «\(corto(l.nombre))» sin ventana")
            pasos.append(p)
            let r = await enInDesign("abrirLibro", ["ruta": l.ruta], espera: 900)
            p.fin = Date()
            if let e = r["error"] as? String {
                pasos[pasos.count - 1].ok = false
                fallo("No se pudo abrir el libro: \(e)")
                return nil
            }
            let docs = r["documentos"] as? [String] ?? []
            let faltan = r["faltan"] as? [String] ?? []
            p.ok = !docs.isEmpty
            p.respuesta = "\(docs.count) capítulos" + (faltan.isEmpty ? "" : " · no se encuentran: " + faltan.joined(separator: ", "))
            pasos[pasos.count - 1] = p
            guard !docs.isEmpty else { fallo("El libro no tiene capítulos que se puedan abrir"); return nil }
            return Alcance(tipo: .libro, documentos: docs, libro: r["libro"] as? String ?? l.nombre)
        }
    }

    private func lanzar(claude: URL, python: URL, servidor: URL, nombreApp: String, alcance a: Alcance, texto t: String) {
        let mcp: [String: Any] = ["mcpServers": ["indesign": [
            "command": python.path, "args": [servidor.path], "env": ["INDESIGN_APP": nombreApp]]]]
        let configuracion = String(decoding: (try? JSONSerialization.data(withJSONObject: mcp)) ?? Data(), as: UTF8.self)
        let esquema = leer(carpetaClaude.appendingPathComponent("esquema.json"))
        let p = Process()
        p.executableURL = claude
        p.currentDirectoryURL = motor
        p.arguments = ["-p", "\(a.paraClaude)\nBúsqueda: \(t)",
                       "--append-system-prompt", leer(carpetaClaude.appendingPathComponent("instrucciones.md")),
                       "--mcp-config", configuracion, "--strict-mcp-config",
                       "--tools", "", "--allowedTools", herramientas,
                       "--setting-sources", "", "--no-session-persistence",
                       "--output-format", "stream-json", "--verbose", "--json-schema", esquema]
        let salida = Pipe(), errores = Pipe()
        p.standardOutput = salida
        p.standardError = errores
        p.standardInput = FileHandle.nullDevice
        pasos.append(Paso(tipo: .inicio, titulo: "Busca en \(a.resumen)", respuesta: "«\(t)»"))
        do { try p.run() } catch {
            fallo("No se pudo lanzar Claude Code: \(error.localizedDescription)")
            return
        }
        proceso = p
        Task.detached {
            let textoErrores = Task.detached { String(decoding: errores.fileHandleForReading.readDataToEndOfFile(), as: UTF8.self) }
            do {
                for try await linea in salida.fileHandleForReading.bytes.lines {
                    await self.procesar(linea)
                }
            } catch {}
            p.waitUntilExit()
            let err = await textoErrores.value
            await self.terminada(p, errores: err)
        }
    }

    func detener() {
        guard buscando else { return }
        detenida = true
        if let p = proceso, p.isRunning { p.terminate() }
        else {
            buscando = false
            pasos.append(Paso(tipo: .fin, titulo: "Búsqueda detenida", ok: false))
        }
        mensaje = "Búsqueda detenida"
    }

    /// Cada línea de stream-json de Claude Code: lo que piensa, lo que consulta y lo que le contesta InDesign
    func procesar(_ linea: String) {
        guard proceso != nil, let d = try? JSONSerialization.jsonObject(with: Data(linea.utf8)) as? [String: Any] else { return }
        switch d["type"] as? String {
        case "system":
            guard d["subtype"] as? String == "init" else { return }
            modelo = nombreModelo(d["model"] as? String ?? "")
            let servidores = d["mcp_servers"] as? [[String: Any]] ?? []
            let conectado = servidores.contains { $0["name"] as? String == "indesign" && $0["status"] as? String == "connected" }
            pasos.append(Paso(tipo: conectado ? .inicio : .aviso,
                              titulo: conectado ? "Claude conectado con InDesign" : "Claude no ha podido conectar con InDesign",
                              respuesta: "Modelo: \(modelo)", ok: conectado))
        case "assistant":
            let contenido = (d["message"] as? [String: Any])?["content"] as? [[String: Any]] ?? []
            for c in contenido {
                switch c["type"] as? String {
                case "thinking":
                    let t = (c["thinking"] as? String ?? "").trimmingCharacters(in: .whitespacesAndNewlines)
                    if !t.isEmpty { pasos.append(Paso(tipo: .idea, titulo: "Piensa", detalle: t)) }
                case "text":
                    let t = (c["text"] as? String ?? "").trimmingCharacters(in: .whitespacesAndNewlines)
                    if !t.isEmpty { pasos.append(Paso(tipo: .nota, titulo: t)) }
                case "tool_use":
                    let nombre = (c["name"] as? String ?? "").replacingOccurrences(of: "mcp__indesign__", with: "")
                    let (titulo, codigo) = describirHerramienta(nombre, c["input"] as? [String: Any] ?? [:])
                    var p = Paso(tipo: .herramienta, titulo: titulo, detalle: codigo)
                    p.herramienta = nombre
                    pasos.append(p)
                    if let id = c["id"] as? String { pasoDeHerramienta[id] = pasos.count - 1 }
                default: break
                }
            }
        case "user":
            let contenido = (d["message"] as? [String: Any])?["content"] as? [[String: Any]] ?? []
            for c in contenido where c["type"] as? String == "tool_result" {
                guard let id = c["tool_use_id"] as? String, let i = pasoDeHerramienta[id], i < pasos.count else { continue }
                let texto = textoDe(c["content"])
                let error = c["is_error"] as? Bool ?? false
                let (respuesta, ejemplos) = resumir(pasos[i].herramienta, texto, error: error)
                pasos[i].fin = Date()
                pasos[i].ok = !error
                pasos[i].respuesta = respuesta
                pasos[i].ejemplos = ejemplos
                pasos[i].completa = String(texto.prefix(20000))
            }
        case "rate_limit_event":
            let info = d["rate_limit_info"] as? [String: Any]
            if let v = ((info?["unifiedWindows"] as? [String: Any])?["five_hour"] as? [String: Any])?["utilization"] as? Double { uso = v }
        case "result":
            if d["is_error"] as? Bool != true, let s = d["structured_output"] as? [String: Any] { resultadoFinal = s }
            else { errorFinal = (d["result"] as? String).map { primeraLinea($0, 500) } ?? "Claude no devolvió resultado" }
        default: break
        }
    }

    func terminada(_ p: Process, errores: String) async {
        guard proceso === p else { return }
        proceso = nil
        duracion = inicio.map { Date().timeIntervalSince($0) }
        if detenida {
            buscando = false
            pasos.append(Paso(tipo: .fin, titulo: "Búsqueda detenida", ok: false))
            return
        }
        guard let datos = resultadoFinal else {
            let e = errorFinal ?? primeraLinea(errores, 500)
            fallo(e.isEmpty ? "Claude no devolvió resultado" : e)
            return
        }
        resumen = datos["resumen"] as? String ?? ""
        let resultados = datos["resultados"] as? [[String: Any]] ?? []
        var p = Paso(tipo: .herramienta, titulo: "Prepara la revisión en InDesign")
        pasos.append(p)
        let r = await enInDesign("cargar", ["resultados": resultados, "cambio": datos["cambio"] ?? [:]], espera: 600)
        buscando = false
        p.fin = Date()
        if let e = r["error"] as? String {
            p.ok = false
            p.respuesta = e
            pasos[pasos.count - 1] = p
            errorBusqueda = "No se pudo preparar la revisión en InDesign: \(e)"
            return
        }
        let items = r["items"] as? [[String: Any]] ?? []
        casos = items.enumerated().map { i, x in
            Caso(id: i, documento: x["documento"] as? String ?? "", pagina: x["pagina"] as? String ?? "",
                 pre: x["pre"] as? String ?? "", encontrado: x["enc"] as? String ?? "", post: x["post"] as? String ?? "",
                 descripcion: x["desc"] as? String ?? "", propuesta: x["propuesta"] as? String ?? "",
                 dudoso: x["dudoso"] as? Bool ?? false, motivo: x["motivo"] as? String ?? "")
        }
        aplicarEstados(r)
        if r["hayCambio"] as? Bool == true, let c = datos["cambio"] as? [String: Any] {
            cambio = Cambio(descripcion: c["descripcion"] as? String ?? "", codigo: c["aplicar"] as? String ?? "")
        }
        p.ok = true
        p.respuesta = (r["aviso"] as? String).flatMap { $0.isEmpty ? nil : $0 } ?? "Lista para revisar"
        pasos[pasos.count - 1] = p
        pasos.append(Paso(tipo: .fin, titulo: "\(casos.count) resultado\(casos.count == 1 ? "" : "s") en \(segundos(duracion ?? 0))", ok: true))
        buscada = true
        mensaje = "\(casos.count) resultado\(casos.count == 1 ? "" : "s") · \(segundos(duracion ?? 0))"
        guardarReciente()
        panel = .revision
        if let k = casos.first(where: { $0.estado != .error })?.id { elegir(k) }
        if CommandLine.arguments.contains("--recorrer") { verEnInDesign() }
    }

    private func guardarReciente() {
        recientes.removeAll { $0.texto == textoBuscado }
        recientes.insert(Reciente(texto: textoBuscado, ambito: alcance?.tipo.titulo ?? "", fecha: Date(), resultados: casos.count), at: 0)
        if recientes.count > 30 { recientes.removeLast(recientes.count - 30) }
        guardarRecientes()
    }

    func guardarRecientes() {
        if let datos = try? JSONEncoder().encode(recientes) { ajustes.set(datos, forKey: "recientes") }
    }

    func usar(_ r: Reciente) {
        texto = r.texto
        if let a = Ambito.allCases.first(where: { $0.titulo == r.ambito }), ambitosDisponibles.contains(a) { ambito = a }
    }

    // MARK: Revisión

    func aplicarEstados(_ r: [String: Any]) {
        guard let l = r["estados"] as? [[String: Any]], l.count == casos.count else { return }
        for (i, s) in l.enumerated() {
            casos[i].estado = EstadoCaso(rawValue: s["estado"] as? String ?? "") ?? .pendiente
            casos[i].error = s["error"] as? String ?? ""
        }
    }

    /// Elige un resultado: InDesign lo selecciona y la app enseña su antes y después
    func elegir(_ k: Int?) {
        seleccion = k
        guard let k, k < casos.count else { detalle = nil; return }
        Task {
            let r = await enInDesign("mostrar", ["k": k], espera: 60)
            guard seleccion == k else { return }  // el usuario ya está en otro
            aplicarEstados(r)
            if let e = r["error"] as? String {
                detalle = nil
                if casos[k].error.isEmpty { casos[k].error = e }
                return
            }
            if let a = r["aviso"] as? String { mensaje = a }
            detalle = Detalle(k: k, pre: r["pre"] as? String ?? "", antes: r["antes"] as? String ?? "",
                              despues: r["despues"] as? String ?? "", post: r["post"] as? String ?? "")
        }
    }

    func siguiente(_ k: Int) -> Int? {
        casos.first(where: { $0.id > k && $0.estado == .pendiente })?.id ?? casos.first(where: { $0.estado == .pendiente })?.id
    }

    private func accion(_ nombre: String, _ datos: [String: Any]? = nil, luego: @escaping ([String: Any]) -> Void) {
        guard !ocupado else { return }
        ocupado = true
        Task {
            let r = await enInDesign(nombre, datos, espera: 900)
            ocupado = false
            if let e = r["error"] as? String { mensaje = "Error: \(e)"; return }
            aplicarEstados(r)
            if let m = r["mensaje"] as? String { mensaje = m }
            luego(r)
        }
    }

    var actualPendiente: Int? {
        if let k = seleccion, k < casos.count, casos[k].estado == .pendiente { return k }
        return nil
    }

    func cambiar() {
        guard let k = actualPendiente ?? siguiente(-1) else { return }
        accion("cambiar", ["k": k]) { _ in
            self.mensaje = self.casos[k].estado == .error ? "No se pudo cambiar: \(self.casos[k].error)" : "Cambiado (pág. \(self.casos[k].pagina))"
            self.elegir(self.siguiente(k))
        }
    }

    func omitir() {
        guard let k = actualPendiente ?? siguiente(-1) else { return }
        accion("omitir", ["k": k]) { _ in self.elegir(self.siguiente(k)) }
    }

    func cambiarTodo() {
        accion("cambiarTodo") { _ in
            if let k = self.seleccion { self.elegir(k) }
        }
    }

    func cancelarRevision() {
        accion("cancelar") { _ in self.vaciarRevision() }
    }

    func terminarRevision() {
        accion("cerrar") { _ in self.vaciarRevision() }
    }

    private func vaciarRevision() {
        casos = []
        cambio = nil
        detalle = nil
        seleccion = nil
        resumen = ""
        buscada = false
    }

    /// Deja todo como al abrir la app; los cambios ya hechos se quedan
    func nuevaBusqueda() {
        if buscando { detener() }
        Task { _ = await enInDesign("cerrar") }
        vaciarRevision()
        texto = ""
        pasos = []
        errorBusqueda = nil
        alcance = nil
        ultimoAlcance = nil
        firma = ""
        mensaje = ""
        panel = .revision
        Task { await refrescarContexto() }
    }

    /// InDesign delante y, encima, la ventanita «Recorrer» para ir de un resultado a otro sin taparlo
    func verEnInDesign() {
        inDesignAbierto()?.activate()
        Recorrido.shared.abrir(self)
    }

    func volverALaApp() {
        Recorrido.shared.cerrar()
        NSApp.activate(ignoringOtherApps: true)
        NSApp.windows.first { !Recorrido.shared.esEl($0) && $0.canBecomeMain }?.makeKeyAndOrderFront(nil)
    }
}

// MARK: - Recorrer en InDesign

/// Ventanita flotante como las paletas de InDesign: no activa la app al pulsar en ella, así que InDesign
/// sigue delante y va enseñando cada resultado que se elige.
@MainActor
final class Recorrido {
    static let shared = Recorrido()
    private var panel: NSPanel?

    func abrir(_ b: Buscador) {
        if panel == nil {
            let p = NSPanel(contentRect: NSRect(x: 0, y: 0, width: 400, height: 560),
                            styleMask: [.titled, .closable, .resizable, .utilityWindow, .nonactivatingPanel],
                            backing: .buffered, defer: false)
            p.title = "Búsqueda inteligente"
            p.isFloatingPanel = true
            p.level = NSWindow.Level(rawValue: NSWindow.Level.floating.rawValue + 1)  // por encima de los paneles flotantes de InDesign
            p.hidesOnDeactivate = false
            p.becomesKeyOnlyIfNeeded = true
            p.isReleasedWhenClosed = false
            p.collectionBehavior = [.canJoinAllSpaces, .fullScreenAuxiliary]
            p.contentView = NSHostingView(rootView: Recorrer(b: b))
            p.minSize = NSSize(width: 320, height: 380)
            if !p.setFrameUsingName("recorrer"), let pantalla = NSScreen.main?.visibleFrame {
                // la primera vez, a la derecha de la pantalla
                p.setFrameOrigin(NSPoint(x: pantalla.maxX - p.frame.width - 24, y: pantalla.maxY - p.frame.height - 24))
            }
            p.setFrameAutosaveName("recorrer")
            panel = p
        }
        panel?.orderFrontRegardless()
    }

    func cerrar() { panel?.orderOut(nil) }

    func esEl(_ ventana: Any?) -> Bool { (ventana as? NSWindow) === panel }
}

struct Recorrer: View {
    @ObservedObject var b: Buscador

    var body: some View {
        VStack(spacing: 0) {
            VStack(alignment: .leading, spacing: 4) {
                Text(b.cambio?.descripcion ?? (b.casos.isEmpty ? "Sin revisión" : "Resultados"))
                    .font(.headline).lineLimit(1)
                HStack(spacing: 10) {
                    Label("\(b.hechos)", systemImage: "checkmark.circle.fill").foregroundStyle(.green)
                    Label("\(b.pendientes)", systemImage: "circle").foregroundStyle(.secondary)
                    if b.dudosos > 0 { Label("\(b.dudosos)", systemImage: "questionmark.circle.fill").foregroundStyle(.orange) }
                    Spacer()
                    if b.ocupado { ProgressView().controlSize(.mini) }
                }
                .font(.caption)
            }
            .padding(10)
            Divider()
            if b.casos.isEmpty {
                Text(b.mensaje.isEmpty ? "No hay resultados que recorrer." : b.mensaje)
                    .foregroundStyle(.secondary).multilineTextAlignment(.center)
                    .padding(20).frame(maxWidth: .infinity, maxHeight: .infinity)
            } else {
                // Filas como botones: una List no cambia la selección en una ventana que no está activa
                ScrollViewReader { proxy in
                    ScrollView {
                        LazyVStack(spacing: 2) {
                            ForEach(b.casos) { c in
                                Button { b.elegir(c.id) } label: {
                                    FilaCaso(caso: c)
                                        .padding(.horizontal, 8)
                                        .frame(maxWidth: .infinity, alignment: .leading)
                                        .background(RoundedRectangle(cornerRadius: 6)
                                            .fill(b.seleccion == c.id ? Color.accentColor.opacity(0.18) : Color.clear))
                                        .contentShape(Rectangle())
                                }
                                .buttonStyle(.plain)
                                .id(c.id)
                            }
                        }
                        .padding(6)
                    }
                    .onChange(of: b.seleccion) { _, k in
                        if let k { withAnimation { proxy.scrollTo(k) } }
                    }
                }
                if let k = b.seleccion, k < b.casos.count, let d = b.detalle, d.k == k, b.cambio != nil, !d.despues.isEmpty {
                    let objeto = !b.casos[k].descripcion.isEmpty
                    VStack(alignment: .leading, spacing: 4) {
                        Text(objeto ? AttributedString(d.antes) : resaltado(d.pre, d.antes, d.post, color: .red)).lineLimit(3)
                        Text(objeto ? AttributedString(d.despues) : resaltado(d.pre, d.despues, d.post, color: .green)).lineLimit(3)
                    }
                    .font(.callout)
                    .padding(10)
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .background(Color.secondary.opacity(0.06))
                }
                if b.cambio != nil {
                    Divider()
                    VStack(spacing: 6) {
                        HStack(spacing: 6) {
                            Button { b.cambiar() } label: { Text("Cambiar").frame(maxWidth: .infinity) }
                                .buttonStyle(.borderedProminent)
                            Button { b.omitir() } label: { Text("Omitir").frame(maxWidth: .infinity) }
                        }
                        .disabled(b.ocupado || b.pendientes == 0)
                        Button { b.cambiarTodo() } label: { Text("Cambiar todo").frame(maxWidth: .infinity) }
                            .disabled(b.ocupado || b.pendientes == 0)
                            .help("Todos los pendientes salvo los dudosos")
                    }
                    .padding(10)
                }
            }
            Divider()
            Button { b.volverALaApp() } label: {
                Label("Volver a la app", systemImage: "arrow.down.left.and.arrow.up.right").frame(maxWidth: .infinity)
            }
            .buttonStyle(.borderless)
            .padding(8)
        }
    }
}

// MARK: - Vistas

struct Ventana: View {
    @ObservedObject var b: Buscador

    var body: some View {
        NavigationSplitView {
            BarraLateral(b: b)
                .navigationSplitViewColumnWidth(min: 220, ideal: 250, max: 340)
        } detail: {
            VStack(spacing: 0) {
                Cabecera(b: b)
                Divider()
                HSplitView {
                    PanelResultados(b: b)
                        .frame(minWidth: 440, maxWidth: .infinity, maxHeight: .infinity)
                    Inspector(b: b)
                        .frame(minWidth: 340, idealWidth: 420, maxWidth: 620, maxHeight: .infinity)
                }
                Divider()
                BarraEstado(b: b)
            }
        }
        .onReceive(NotificationCenter.default.publisher(for: NSApplication.didBecomeActiveNotification)) { _ in
            Task { await b.refrescarContexto() }
        }
        .task { await b.refrescarContexto() }
        .onReceive(NotificationCenter.default.publisher(for: NSWindow.didBecomeKeyNotification)) { n in
            if !Recorrido.shared.esEl(n.object) { Recorrido.shared.cerrar() }
        }
        .alert(item: $b.aviso) { a in
            Alert(title: Text(a.titulo), message: Text(a.texto), dismissButton: .default(Text("Aceptar")))
        }
    }
}

// MARK: Barra lateral

struct BarraLateral: View {
    @ObservedObject var b: Buscador

    var body: some View {
        List {
            Section("InDesign") {
                if b.contexto.abierto {
                    Label("InDesign \(b.contexto.version.split(separator: ".").prefix(2).joined(separator: "."))", systemImage: "checkmark.circle.fill")
                        .foregroundStyle(.green)
                    if b.contexto.documentos.isEmpty {
                        Text("Ningún documento abierto").foregroundStyle(.secondary)
                    }
                    ForEach(b.contexto.documentos) { d in
                        HStack(spacing: 6) {
                            Image(systemName: d.nombre == b.contexto.activo ? "doc.text.fill" : "doc.text")
                                .foregroundStyle(d.nombre == b.contexto.activo ? Color.accentColor : .secondary)
                            Text(corto(d.nombre)).lineLimit(1).truncationMode(.middle)
                                .fontWeight(d.nombre == b.contexto.activo ? .semibold : .regular)
                            Spacer(minLength: 0)
                            if !d.ventana { Text("sin ventana").font(.caption2).foregroundStyle(.tertiary) }
                            if d.modificado {
                                Circle().fill(.orange).frame(width: 6, height: 6).help("Cambios sin guardar")
                            }
                        }
                    }
                    if let s = b.contexto.seleccion {
                        Label(s, systemImage: "cursorarrow.rays")
                            .font(.caption).foregroundStyle(.secondary).lineLimit(2)
                    }
                } else {
                    Label("InDesign no está abierto", systemImage: "exclamationmark.triangle.fill")
                        .foregroundStyle(.orange)
                }
                Button {
                    Task { await b.refrescarContexto() }
                } label: {
                    Label("Actualizar", systemImage: "arrow.clockwise")
                }
                .buttonStyle(.borderless)
                .font(.caption)
            }

            Section("Búsquedas recientes") {
                if b.recientes.isEmpty {
                    Text("Aquí quedarán tus búsquedas para repetirlas").font(.caption).foregroundStyle(.secondary)
                }
                ForEach(b.recientes) { r in
                    Button { b.usar(r) } label: {
                        VStack(alignment: .leading, spacing: 2) {
                            Text(r.texto).lineLimit(2).foregroundStyle(.primary)
                            Text("\(r.ambito) · \(r.resultados) resultado\(r.resultados == 1 ? "" : "s") · \(r.fecha.formatted(.relative(presentation: .named)))")
                                .font(.caption2).foregroundStyle(.secondary)
                        }
                        .frame(maxWidth: .infinity, alignment: .leading)
                        .contentShape(Rectangle())
                    }
                    .buttonStyle(.plain)
                    .help("Usar esta búsqueda")
                    .contextMenu {
                        Button("Quitar de la lista") {
                            b.recientes.removeAll { $0.id == r.id }
                            b.guardarRecientes()
                        }
                    }
                }
            }
        }
        .listStyle(.sidebar)
    }
}

// MARK: Cabecera

struct Cabecera: View {
    @ObservedObject var b: Buscador

    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            HStack(alignment: .top, spacing: 12) {
                ZStack(alignment: .topLeading) {
                    TextEditor(text: $b.texto)
                        .font(.system(size: 14))
                        .scrollContentBackground(.hidden)
                        .padding(.horizontal, 5)
                        .padding(.vertical, 7)
                    if b.texto.isEmpty {
                        Text("Describe qué quieres buscar o cambiar, como se lo dirías a un compañero…")
                            .font(.system(size: 14))
                            .foregroundStyle(.tertiary)
                            .padding(.horizontal, 10)
                            .padding(.vertical, 7)
                            .allowsHitTesting(false)
                    }
                }
                .frame(height: 70)
                .background(RoundedRectangle(cornerRadius: 8).fill(Color(nsColor: .textBackgroundColor)))
                .overlay(RoundedRectangle(cornerRadius: 8).stroke(Color.secondary.opacity(0.3)))
                .disabled(b.buscando)

                VStack(spacing: 8) {
                    if b.buscando {
                        Button { b.detener() } label: {
                            Label("Detener", systemImage: "stop.fill").frame(minWidth: 120)
                        }
                        .controlSize(.large)
                        .keyboardShortcut(".", modifiers: .command)
                        .help("Detiene la búsqueda en curso (⌘.)")
                    } else {
                        Button { b.buscar() } label: {
                            Label("Buscar", systemImage: "sparkle.magnifyingglass").frame(minWidth: 120)
                        }
                        .buttonStyle(.borderedProminent)
                        .controlSize(.large)
                        .keyboardShortcut(.return, modifiers: .command)
                        .disabled(b.texto.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty)
                        .help("Busca con Claude (⌘↩)")
                    }
                    Button { b.nuevaBusqueda() } label: {
                        Label("Nueva búsqueda", systemImage: "square.and.pencil").frame(minWidth: 120)
                    }
                    .help("Borra la descripción y los resultados para empezar otra búsqueda. Los cambios ya hechos se conservan.")
                }
            }

            HStack(spacing: 10) {
                Text("Buscar en").foregroundStyle(.secondary)
                Picker("Buscar en", selection: $b.ambito) {
                    ForEach(b.ambitosDisponibles) { a in
                        Label(a.titulo, systemImage: a.icono).tag(a)
                    }
                }
                .labelsHidden()
                .fixedSize()
                .disabled(b.buscando || !b.contexto.abierto)
                if b.ambito == .libro {
                    Menu {
                        ForEach(b.contexto.libros) { l in
                            Button(corto(l.nombre)) { b.libro = l }
                        }
                        if !b.contexto.libros.isEmpty { Divider() }
                        Button("Otro libro…") { b.elegirLibroEnDisco() }
                    } label: {
                        Label(b.libro.map { corto($0.nombre) } ?? "Elige un libro…", systemImage: "book.closed")
                    }
                    .fixedSize()
                    .disabled(b.buscando)
                }
                Image(systemName: b.ambito.icono).foregroundStyle(.secondary)
                Text(b.descripcionAmbito)
                    .foregroundStyle(.secondary)
                    .lineLimit(1)
                    .truncationMode(.middle)
                Spacer()
            }
            .font(.callout)
        }
        .padding(14)
    }
}

// MARK: Resultados

struct PanelResultados: View {
    @ObservedObject var b: Buscador

    var body: some View {
        if b.buscando && b.casos.isEmpty {
            Espera(b: b)
        } else if let e = b.errorBusqueda, b.casos.isEmpty {
            Vacio(icono: "exclamationmark.triangle", color: .orange, titulo: "No se pudo buscar", texto: e)
        } else if b.casos.isEmpty && b.buscada {
            Vacio(icono: "magnifyingglass", color: .secondary, titulo: "Sin resultados",
                  texto: b.resumen.isEmpty ? "Claude no ha encontrado nada que encaje." : b.resumen)
        } else if b.casos.isEmpty {
            Bienvenida(b: b)
        } else {
            VStack(alignment: .leading, spacing: 0) {
                if !b.resumen.isEmpty {
                    HStack(alignment: .top, spacing: 10) {
                        Image(systemName: "sparkles").foregroundStyle(.purple)
                        Text(b.resumen).textSelection(.enabled).fixedSize(horizontal: false, vertical: true)
                    }
                    .padding(12)
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .background(RoundedRectangle(cornerRadius: 8).fill(Color.purple.opacity(0.08)))
                    .padding([.horizontal, .top], 12)
                }
                Picker("Mostrar", selection: $b.filtro) {
                    Text("Todos (\(b.casos.count))").tag(Filtro.todos)
                    Text("Pendientes (\(b.pendientes))").tag(Filtro.pendientes)
                    Text("Dudosos (\(b.dudosos))").tag(Filtro.dudosos)
                    Text("Cambiados (\(b.hechos))").tag(Filtro.cambiados)
                }
                .pickerStyle(.segmented)
                .labelsHidden()
                .padding(12)
                ScrollViewReader { proxy in
                    List(selection: Binding(get: { b.seleccion }, set: { b.elegir($0) })) {
                        ForEach(b.casosFiltrados) { c in
                            FilaCaso(caso: c).tag(c.id).id(c.id)
                        }
                    }
                    .listStyle(.inset(alternatesRowBackgrounds: true))
                    .contextMenu(forSelectionType: Int.self) { _ in
                        Button("Ver en InDesign") { b.verEnInDesign() }
                    } primaryAction: { _ in
                        b.verEnInDesign()
                    }
                    .onChange(of: b.seleccion) { _, k in
                        if let k { withAnimation { proxy.scrollTo(k) } }
                    }
                }
            }
        }
    }
}

struct FilaCaso: View {
    let caso: Caso

    var icono: (String, Color) {
        switch caso.estado {
        case .hecho: return ("checkmark.circle.fill", .green)
        case .omitido: return ("minus.circle", .secondary)
        case .error: return ("exclamationmark.triangle.fill", .red)
        case .pendiente: return caso.dudoso ? ("questionmark.circle.fill", .orange) : ("circle", .secondary)
        }
    }

    var body: some View {
        HStack(alignment: .top, spacing: 10) {
            Image(systemName: icono.0).foregroundStyle(icono.1).font(.system(size: 15)).frame(width: 18)
            VStack(alignment: .leading, spacing: 3) {
                Group {
                    if caso.descripcion.isEmpty {
                        Text(resaltado(caso.pre, caso.encontrado, caso.post, color: .accentColor))
                    } else {
                        Text(caso.descripcion)
                    }
                }
                .lineLimit(2)
                .strikethrough(caso.estado == .omitido, color: .secondary)
                .foregroundStyle(caso.estado == .omitido ? .secondary : .primary)
                HStack(spacing: 8) {
                    Text("\(corto(caso.documento)) · pág. \(caso.pagina)").foregroundStyle(.secondary)
                    if !caso.propuesta.isEmpty {
                        Text("→ \(caso.propuesta)").foregroundStyle(caso.estado == .hecho ? .green : .accentColor).lineLimit(1)
                    }
                    if caso.dudoso {
                        Text(caso.motivo.isEmpty ? "Dudoso" : caso.motivo).foregroundStyle(.orange).lineLimit(1)
                    }
                    if !caso.error.isEmpty {
                        Text(caso.error).foregroundStyle(.red).lineLimit(1)
                    }
                }
                .font(.caption)
            }
        }
        .padding(.vertical, 3)
    }
}

struct Espera: View {
    @ObservedObject var b: Buscador

    var body: some View {
        VStack(spacing: 14) {
            ProgressView().controlSize(.large)
            Text(b.alcance.map { "Claude está buscando en \($0.resumen)" } ?? "Preparando la búsqueda…")
                .font(.title3)
            if let inicio = b.inicio {
                TimelineView(.periodic(from: inicio, by: 1)) { t in
                    Text(segundos(t.date.timeIntervalSince(inicio))).monospacedDigit().foregroundStyle(.secondary)
                }
            }
            if let ultimo = b.pasos.last(where: { $0.tipo == .herramienta || $0.tipo == .nota }) {
                Text(ultimo.titulo)
                    .foregroundStyle(.secondary)
                    .multilineTextAlignment(.center)
                    .lineLimit(3)
                    .frame(maxWidth: 420)
                    .animation(.default, value: ultimo.id)
            }
            Text("En la pestaña Actividad ves cada paso que da.")
                .font(.caption).foregroundStyle(.tertiary)
        }
        .padding(30)
        .frame(maxWidth: .infinity, maxHeight: .infinity)
    }
}

struct Vacio: View {
    let icono: String
    let color: Color
    let titulo: String
    let texto: String

    var body: some View {
        VStack(spacing: 12) {
            Image(systemName: icono).font(.system(size: 38)).foregroundStyle(color)
            Text(titulo).font(.title3).bold()
            Text(texto).foregroundStyle(.secondary).multilineTextAlignment(.center).textSelection(.enabled).frame(maxWidth: 460)
        }
        .padding(30)
        .frame(maxWidth: .infinity, maxHeight: .infinity)
    }
}

struct Bienvenida: View {
    @ObservedObject var b: Buscador

    let ejemplos = [
        "Dobles espacios entre palabras",
        "Números de cinco cifras o más sin punto de millar en el texto base",
        "Comillas rectas \" que deberían ser angulares « »",
        "Palabras en inglés sin cursiva en el texto base",
        "Pasa a 85 Heavy los años que estén en 45 Book",
        "Marcos de texto con texto desbordado",
    ]

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 18) {
                HStack(spacing: 12) {
                    Image(systemName: "sparkle.magnifyingglass").font(.system(size: 34)).foregroundStyle(.purple)
                    VStack(alignment: .leading, spacing: 3) {
                        Text("Busca con tus palabras").font(.title2).bold()
                        Text("Claude busca en InDesign lo que describas y, si pides un cambio, lo prepara para que lo revises uno a uno.")
                            .foregroundStyle(.secondary)
                    }
                }
                VStack(alignment: .leading, spacing: 8) {
                    Text("Por ejemplo").font(.headline)
                    ForEach(ejemplos, id: \.self) { e in
                        Button { b.texto = e } label: {
                            HStack {
                                Image(systemName: "text.bubble").foregroundStyle(.secondary)
                                Text(e).foregroundStyle(.primary)
                                Spacer()
                            }
                            .padding(.horizontal, 12)
                            .padding(.vertical, 8)
                            .background(RoundedRectangle(cornerRadius: 8).fill(Color.secondary.opacity(0.08)))
                            .contentShape(Rectangle())
                        }
                        .buttonStyle(.plain)
                    }
                }
                VStack(alignment: .leading, spacing: 6) {
                    Text("Cómo funciona").font(.headline)
                    Label("Elige dónde buscar: lo que tengas seleccionado en InDesign propone el ámbito.", systemImage: "1.circle")
                    Label("Mientras busca, la pestaña Actividad enseña cada consulta y cada prueba.", systemImage: "2.circle")
                    Label("Revisa: al elegir un resultado, InDesign lo enseña; Cambiar, Omitir o Cambiar todo.", systemImage: "3.circle")
                    Label("Todos los cambios de un documento se deshacen con un solo Cmd+Z.", systemImage: "arrow.uturn.backward.circle")
                }
                .foregroundStyle(.secondary)
            }
            .padding(24)
            .frame(maxWidth: 620, alignment: .leading)
            .frame(maxWidth: .infinity)
        }
    }
}

// MARK: Inspector

struct Inspector: View {
    @ObservedObject var b: Buscador

    var body: some View {
        VStack(spacing: 0) {
            Picker("Panel", selection: $b.panel) {
                Text("Revisión").tag(Panel.revision)
                Text(b.pasos.isEmpty ? "Actividad" : "Actividad (\(b.pasos.filter { $0.tipo == .herramienta }.count))").tag(Panel.actividad)
            }
            .pickerStyle(.segmented)
            .labelsHidden()
            .padding(10)
            Divider()
            switch b.panel {
            case .revision: PanelRevision(b: b)
            case .actividad: PanelActividad(b: b)
            }
        }
        .background(Color(nsColor: .windowBackgroundColor))
    }
}

struct Caja: View {
    let titulo: String
    let icono: String
    let color: Color
    let texto: AttributedString
    var nota: String?

    var body: some View {
        VStack(alignment: .leading, spacing: 6) {
            Label(titulo, systemImage: icono).font(.caption.bold()).foregroundStyle(color)
            Text(texto).font(.system(size: 14)).textSelection(.enabled).fixedSize(horizontal: false, vertical: true)
            if let nota, !nota.isEmpty {
                Text(nota).font(.callout).foregroundStyle(color)
            }
        }
        .padding(12)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(RoundedRectangle(cornerRadius: 8).fill(color.opacity(0.07)))
        .overlay(RoundedRectangle(cornerRadius: 8).stroke(color.opacity(0.25)))
    }
}

struct PanelRevision: View {
    @ObservedObject var b: Buscador
    @State private var verCodigo = false

    var body: some View {
        VStack(spacing: 0) {
            ScrollView {
                VStack(alignment: .leading, spacing: 14) {
                    if let c = b.cambio {
                        VStack(alignment: .leading, spacing: 6) {
                            Label("Cambio propuesto", systemImage: "wand.and.stars").font(.caption.bold()).foregroundStyle(.purple)
                            Text(c.descripcion).font(.headline)
                            DisclosureGroup("Código que se aplicará", isExpanded: $verCodigo) {
                                Text(c.codigo).font(.system(size: 11, design: .monospaced)).textSelection(.enabled)
                                    .frame(maxWidth: .infinity, alignment: .leading)
                                    .padding(8)
                                    .background(RoundedRectangle(cornerRadius: 6).fill(Color.secondary.opacity(0.08)))
                            }
                            .font(.caption)
                        }
                        .padding(12)
                        .frame(maxWidth: .infinity, alignment: .leading)
                        .background(RoundedRectangle(cornerRadius: 8).fill(Color.purple.opacity(0.07)))
                    } else if !b.casos.isEmpty {
                        Label("Solo búsqueda: Claude no propone ningún cambio. Elige un resultado para verlo en InDesign.", systemImage: "info.circle")
                            .foregroundStyle(.secondary)
                    }

                    if let k = b.seleccion, k < b.casos.count {
                        detalleCaso(b.casos[k])
                    } else if !b.casos.isEmpty {
                        Text("Elige un resultado de la lista").foregroundStyle(.secondary).frame(maxWidth: .infinity).padding(.top, 30)
                    } else if !b.buscando {
                        Vacio(icono: "checklist", color: .secondary, titulo: "Revisión",
                              texto: "Aquí verás el antes y el después de cada resultado.")
                    }
                }
                .padding(14)
            }
            if b.cambio != nil && !b.casos.isEmpty {
                Divider()
                botonera
            }
        }
    }

    @ViewBuilder
    func detalleCaso(_ c: Caso) -> some View {
        HStack {
            Label("\(corto(c.documento)) · pág. \(c.pagina)", systemImage: "doc.text").font(.callout.bold())
            Spacer()
            switch c.estado {
            case .hecho: Etiqueta(texto: "Cambiado", color: .green)
            case .omitido: Etiqueta(texto: "Omitido", color: .secondary)
            case .error: Etiqueta(texto: "Error", color: .red)
            case .pendiente: Etiqueta(texto: c.dudoso ? "Dudoso" : "Pendiente", color: c.dudoso ? .orange : .accentColor)
            }
        }
        if c.dudoso {
            Label {
                VStack(alignment: .leading, spacing: 2) {
                    Text("Caso dudoso").bold()
                    Text(c.motivo.isEmpty ? "Encaja con la búsqueda, pero quizá no deba cambiarse." : c.motivo)
                    Text("«Cambiar todo» no lo cambia: decide tú con Cambiar u Omitir.").font(.caption).foregroundStyle(.secondary)
                }
            } icon: {
                Image(systemName: "questionmark.circle.fill").foregroundStyle(.orange)
            }
            .padding(10)
            .frame(maxWidth: .infinity, alignment: .leading)
            .background(RoundedRectangle(cornerRadius: 8).fill(Color.orange.opacity(0.1)))
        }
        if !c.error.isEmpty {
            Label(c.error, systemImage: "exclamationmark.triangle.fill").foregroundStyle(.red)
        }
        if let d = b.detalle, d.k == c.id {
            let objeto = !c.descripcion.isEmpty
            Caja(titulo: "Antes", icono: "minus.circle", color: .red,
                 texto: objeto ? AttributedString(d.antes) : resaltado(d.pre, d.antes, d.post, color: .red))
            if b.cambio != nil && !d.despues.isEmpty {
                let soloFormato = d.despues == d.antes
                Caja(titulo: c.estado == .hecho ? "Ahora" : "Después", icono: "plus.circle", color: .green,
                     texto: objeto ? AttributedString(d.despues) : resaltado(d.pre, d.despues, d.post, color: .green),
                     nota: soloFormato ? "El texto no cambia; cambia el formato: \(c.propuesta)" : nil)
            }
        } else if c.estado != .error {
            HStack { ProgressView().controlSize(.small); Text("Mirando en InDesign…").foregroundStyle(.secondary) }
        }
        Button { b.verEnInDesign() } label: { Label("Ver en InDesign", systemImage: "arrow.up.forward.app") }
            .buttonStyle(.link)
            .help("Pasa a InDesign: el resultado ya está seleccionado (también con doble clic en la lista)")
    }

    var botonera: some View {
        VStack(spacing: 10) {
            HStack(spacing: 8) {
                Button { b.cambiar() } label: { Label("Cambiar", systemImage: "checkmark").frame(maxWidth: .infinity) }
                    .buttonStyle(.borderedProminent)
                    .keyboardShortcut("y", modifiers: .command)
                    .help("Cambia este resultado y pasa al siguiente (⌘Y)")
                Button { b.omitir() } label: { Label("Omitir", systemImage: "forward").frame(maxWidth: .infinity) }
                    .keyboardShortcut("n", modifiers: [.command, .option])
                    .help("No se realizará el cambio (⌥⌘N)")
            }
            .disabled(b.ocupado || b.pendientes == 0)
            .controlSize(.large)
            Button { b.cambiarTodo() } label: { Label("Cambiar todo", systemImage: "checkmark.circle").frame(maxWidth: .infinity) }
                .disabled(b.ocupado || b.pendientes == 0)
                .help("Se realizarán todos los cambios excepto los omitidos previamente. Los casos dudosos tampoco se cambian: hazlo uno a uno con Cambiar.")
            HStack(spacing: 8) {
                Button(role: .destructive) { b.cancelarRevision() } label: { Text("Cancelar").frame(maxWidth: .infinity) }
                    .disabled(b.ocupado || b.hechos == 0)
                    .help("No se realizará ningún cambio: se deshacen los cambios de esta revisión y el documento queda como estaba.")
                Button { b.terminarRevision() } label: { Text("Terminar").frame(maxWidth: .infinity) }
                    .disabled(b.ocupado)
                    .help("Termina la revisión y conserva los cambios hechos hasta ahora.")
            }
            HStack(spacing: 14) {
                Label("\(b.hechos) cambiados", systemImage: "checkmark.circle.fill").foregroundStyle(.green)
                Label("\(b.pendientes) pendientes", systemImage: "circle").foregroundStyle(.secondary)
                if b.dudosos > 0 { Label("\(b.dudosos) dudosos", systemImage: "questionmark.circle.fill").foregroundStyle(.orange) }
                if b.ocupado { ProgressView().controlSize(.mini) }
            }
            .font(.caption)
        }
        .padding(12)
    }
}

struct Etiqueta: View {
    let texto: String
    let color: Color

    var body: some View {
        Text(texto).font(.caption.bold())
            .padding(.horizontal, 8).padding(.vertical, 3)
            .background(Capsule().fill(color.opacity(0.15)))
            .foregroundStyle(color)
    }
}

// MARK: Actividad

struct PanelActividad: View {
    @ObservedObject var b: Buscador

    var body: some View {
        if b.pasos.isEmpty {
            Vacio(icono: "list.bullet.rectangle", color: .secondary, titulo: "Actividad",
                  texto: "Al buscar, aquí verás en directo lo que hace Claude: qué consulta en InDesign, qué encuentra y cómo prueba el cambio.")
        } else {
            VStack(spacing: 0) {
                ScrollViewReader { proxy in
                    ScrollView {
                        LazyVStack(alignment: .leading, spacing: 0) {
                            ForEach(b.pasos) { p in
                                FilaPaso(paso: p, inicio: b.inicio ?? p.hora, enMarcha: b.buscando).id(p.id)
                            }
                        }
                        .padding(12)
                    }
                    .onChange(of: b.pasos.count) { _, _ in
                        if let u = b.pasos.last { withAnimation { proxy.scrollTo(u.id, anchor: .bottom) } }
                    }
                }
                Divider()
                HStack(spacing: 10) {
                    if b.buscando, let inicio = b.inicio {
                        ProgressView().controlSize(.small)
                        TimelineView(.periodic(from: inicio, by: 1)) { t in
                            Text("Buscando · \(segundos(t.date.timeIntervalSince(inicio)))").monospacedDigit()
                        }
                    } else if let d = b.duracion {
                        Image(systemName: "clock")
                        Text("\(segundos(d)) · \(b.pasos.filter { $0.tipo == .herramienta }.count) pasos")
                    }
                    Spacer()
                    if !b.modelo.isEmpty { Text(b.modelo) }
                }
                .font(.caption)
                .foregroundStyle(.secondary)
                .padding(10)
            }
        }
    }
}

struct FilaPaso: View {
    let paso: Paso
    let inicio: Date
    let enMarcha: Bool
    @State private var abierto = false

    var icono: (String, Color) {
        switch paso.tipo {
        case .inicio: return ("play.circle.fill", .accentColor)
        case .idea: return ("brain", .purple)
        case .nota: return ("text.bubble.fill", .purple)
        case .aviso: return ("exclamationmark.triangle.fill", .orange)
        case .fin: return paso.ok == false ? ("stop.circle.fill", .secondary) : ("flag.checkered.circle.fill", .green)
        case .herramienta:
            switch paso.ok {
            case .some(true): return ("checkmark.circle.fill", .green)
            case .some(false): return ("xmark.circle.fill", .red)
            case .none: return ("circle.dotted", .secondary)
            }
        }
    }

    var body: some View {
        HStack(alignment: .top, spacing: 10) {
            ZStack {
                if paso.tipo == .herramienta && paso.ok == nil && enMarcha {
                    ProgressView().controlSize(.small)
                } else {
                    Image(systemName: icono.0).foregroundStyle(icono.1).font(.system(size: 15))
                }
            }
            .frame(width: 20, height: 20)
            VStack(alignment: .leading, spacing: 4) {
                HStack(alignment: .firstTextBaseline) {
                    Text(paso.titulo)
                        .font(paso.tipo == .nota ? .callout.italic() : .callout.weight(paso.tipo == .herramienta ? .medium : .regular))
                        .foregroundStyle(paso.tipo == .idea ? .secondary : .primary)
                        .fixedSize(horizontal: false, vertical: true)
                    Spacer(minLength: 6)
                    Text("+" + segundos(paso.hora.timeIntervalSince(inicio)))
                        .font(.caption2).monospacedDigit().foregroundStyle(.tertiary)
                }
                if !paso.respuesta.isEmpty {
                    Text(paso.respuesta + (paso.fin.map { " · " + String(format: "%.1f s", $0.timeIntervalSince(paso.hora)) } ?? ""))
                        .font(.caption)
                        .foregroundStyle(paso.ok == false ? .red : .secondary)
                        .textSelection(.enabled)
                        .fixedSize(horizontal: false, vertical: true)
                }
                ForEach(paso.ejemplos) { e in
                    VStack(alignment: .leading, spacing: 2) {
                        Text(conMarcas(e.antes, color: .red)).foregroundStyle(.secondary)
                        Text(conMarcas(e.despues, color: .green))
                    }
                    .font(.caption)
                    .padding(6)
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .background(RoundedRectangle(cornerRadius: 6).fill(Color.secondary.opacity(0.07)))
                }
                if !paso.detalle.isEmpty || !paso.completa.isEmpty {
                    DisclosureGroup(isExpanded: $abierto) {
                        VStack(alignment: .leading, spacing: 6) {
                            if !paso.detalle.isEmpty {
                                Text(paso.detalle)
                                    .font(paso.tipo == .idea ? .caption : .system(size: 11, design: .monospaced))
                                    .textSelection(.enabled)
                                    .frame(maxWidth: .infinity, alignment: .leading)
                            }
                            if !paso.completa.isEmpty {
                                Text("Respuesta de InDesign").font(.caption2.bold()).foregroundStyle(.secondary)
                                Text(paso.completa.count > 3000 ? String(paso.completa.prefix(3000)) + "…" : paso.completa)
                                    .font(.system(size: 10, design: .monospaced))
                                    .foregroundStyle(.secondary)
                                    .textSelection(.enabled)
                                    .frame(maxWidth: .infinity, alignment: .leading)
                            }
                        }
                        .padding(8)
                        .background(RoundedRectangle(cornerRadius: 6).fill(Color.secondary.opacity(0.07)))
                    } label: {
                        Text(paso.tipo == .idea ? "Ver razonamiento" : "Ver el detalle").font(.caption).foregroundStyle(.secondary)
                    }
                }
            }
        }
        .padding(.vertical, 6)
    }
}

// MARK: Barra de estado

struct BarraEstado: View {
    @ObservedObject var b: Buscador

    var body: some View {
        HStack(spacing: 12) {
            Text(b.mensaje).lineLimit(1).truncationMode(.tail)
            Spacer()
            if let u = b.uso {
                Label("Uso de Claude en las últimas 5 h: \(Int((u * 100).rounded())) %", systemImage: "gauge.with.dots.needle.33percent")
                    .help("Lo que llevas gastado de la suscripción en la ventana de 5 horas")
            }
        }
        .font(.caption)
        .foregroundStyle(.secondary)
        .padding(.horizontal, 12)
        .padding(.vertical, 6)
    }
}

// MARK: - App

final class Delegado: NSObject, NSApplicationDelegate {
    // Si arranca en segundo plano, SwiftUI no crea la ventana hasta que la app se activa
    func applicationDidFinishLaunching(_ notification: Notification) { NSApp.activate(ignoringOtherApps: true) }

    func applicationShouldTerminateAfterLastWindowClosed(_ sender: NSApplication) -> Bool { true }
}

@main
struct BusquedaInteligenteApp: App {
    @NSApplicationDelegateAdaptor(Delegado.self) private var delegado
    @StateObject private var b = Buscador()

    var body: some Scene {
        Window("Búsqueda inteligente", id: "principal") {
            Ventana(b: b)
                .frame(minWidth: 1080, minHeight: 640)
                .task {
                    // Para pruebas: BusquedaInteligente --buscar "<descripción>" lanza la búsqueda al abrir
                    let a = CommandLine.arguments
                    if let i = a.firstIndex(of: "--buscar"), i + 1 < a.count {
                        await b.refrescarContexto()
                        b.texto = a[i + 1]
                        b.buscar()
                    }
                }
        }
        .defaultSize(width: 1280, height: 820)
        .commands {
            CommandGroup(replacing: .newItem) {
                Button("Nueva búsqueda") { b.nuevaBusqueda() }.keyboardShortcut("n")
            }
        }
    }
}
