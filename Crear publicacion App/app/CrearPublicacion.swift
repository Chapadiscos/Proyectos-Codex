// Crear Publicación: del Word a InDesign en tres pasos independientes (Galerada, Tipografía y
// Cierre), sobre el documento activo de InDesign, uno elegido a mano o todos los abiertos.
// Usa el motor de «Ventana Formatear Word Indesign» (sus .py y .jsx) sin modificarlo: lanza los
// .py en segundo plano y abre las ventanas de revisión dentro de InDesign.
// Compilar con app/compilar_app.sh.

import SwiftUI
import AppKit
import UniformTypeIdentifiers

// MARK: - Rutas

/// Carpeta del proyecto: la que contiene la .app
let proyecto = Bundle.main.bundleURL.deletingLastPathComponent()

/// Carpeta del motor; se cambia con
/// `defaults write es.estudioencuadre.crear-publicacion motor "<ruta>"`
let motor: URL = {
    if let ruta = UserDefaults.standard.string(forKey: "motor") { return URL(fileURLWithPath: ruta) }
    return proyecto.deletingLastPathComponent().appendingPathComponent("Ventana Formatear Word Indesign")
}()

/// Desde una app, el python3 del sistema es el 3.9 (sin tomllib): ruta completa del 3.14
let python = "/Library/Frameworks/Python.framework/Versions/3.14/bin/python3"
let lanzadorJSX = proyecto.appendingPathComponent("jsx/abrir_en_indesign.jsx")
let idInDesign = "com.adobe.InDesign"

// MARK: - Modelo

enum Seccion: String, CaseIterable, Codable, Identifiable {
    case galerada, tipografia, cierre

    var id: String { rawValue }
    var numero: Int { Seccion.allCases.firstIndex(of: self)! + 1 }

    var titulo: String {
        switch self {
        case .galerada: return "Galerada"
        case .tipografia: return "Tipografía"
        case .cierre: return "Cierre"
        }
    }

    var lema: String {
        switch self {
        case .galerada: return "Del Word a la maqueta, con sus estilos y las dudas marcadas"
        case .tipografia: return "Correcciones ortotipográficas y dudas con Claude"
        case .cierre: return "Remate del capítulo ya corregido"
        }
    }

    var icono: String {
        switch self {
        case .galerada: return "doc.richtext"
        case .tipografia: return "textformat"
        case .cierre: return "checkmark.seal"
        }
    }

    var color: Color {
        switch self {
        case .galerada: return Color(red: 0.16, green: 0.47, blue: 0.96)
        case .tipografia: return Color(red: 0.58, green: 0.33, blue: 0.93)
        case .cierre: return Color(red: 0.13, green: 0.66, blue: 0.42)
        }
    }
}

/// Dónde trabajan Tipografía y Cierre
enum Destino: Hashable {
    case activo
    case documento(String)
    case todos
}

struct DocInDesign: Identifiable, Hashable {
    let nombre: String
    let ruta: String
    var id: String { nombre }
}

struct Publicacion: Identifiable, Hashable {
    let nombre: String
    let ruta: String
    var id: String { ruta }
}

/// Lo último que se hizo de cada paso en cada documento
struct Hecho: Codable {
    let accion: String
    let fecha: Date
    let ok: Bool
}

struct Ejecucion: Identifiable {
    let id = UUID()
    let seccion: Seccion?
    let titulo: String
    let accion: String
    let documento: String?
    let inicio = Date()
    var fin: Date?
    var ok: Bool?
    var texto = ""
}

struct Aviso: Identifiable {
    let id = UUID()
    let titulo: String
    let texto: String
}

struct Pregunta: Identifiable {
    let id = UUID()
    let titulo: String
    let texto: String
    let boton: String
    let hacer: () -> Void
}

/// Word elegidos o arrastrados, a la espera de confirmar la publicación
struct Importacion: Identifiable {
    let id = UUID()
    let nombre: String
    let words: [URL]
}

struct NuevaPublicacion: Identifiable {
    let id = UUID()
    let maquetado: URL
    var nombre: String
}

struct DatosPublicacion {
    let maqueta: URL?
    let maquetado: String
    var nueva: URL? { maqueta.map { URL(fileURLWithPath: $0.path.replacingOccurrences(of: ".indd", with: "") + " (nueva).indd") } }
    var pendiente: URL? { maqueta.map { URL(fileURLWithPath: $0.path.replacingOccurrences(of: ".indd", with: "") + " (nueva).json") } }
}

struct InformeActualizacion: Identifiable {
    let id = UUID()
    let publicacion: Publicacion
    let informe: String
    let avisos: Int
}

// MARK: - Utilidades

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

func leer(_ url: URL) -> String {
    (try? String(contentsOf: url, encoding: .utf8)) ?? ""
}

func primerGrupo(_ patron: String, _ texto: String) -> String? {
    guard let re = try? NSRegularExpression(pattern: patron, options: [.anchorsMatchLines]),
          let m = re.firstMatch(in: texto, range: NSRange(texto.startIndex..., in: texto)),
          let r = Range(m.range(at: 1), in: texto) else { return nil }
    return String(texto[r])
}

/// Como el slug de nueva_publicacion.py: «Revista GHHO» → «revista-ghho»
func slug(_ nombre: String) -> String {
    let s = nombre.folding(options: [.diacriticInsensitive, .caseInsensitive], locale: Locale(identifier: "es"))
        .lowercased()
        .replacingOccurrences(of: "[^0-9a-z]+", with: "-", options: .regularExpression)
    return s.trimmingCharacters(in: CharacterSet(charactersIn: "-"))
}

let formatoHora: DateFormatter = {
    let f = DateFormatter()
    f.locale = Locale(identifier: "es_ES")
    f.dateFormat = "HH:mm"
    return f
}()

func cuando(_ fecha: Date) -> String {
    let cal = Calendar.current
    if cal.isDateInToday(fecha) { return "hoy, " + formatoHora.string(from: fecha) }
    if cal.isDateInYesterday(fecha) { return "ayer, " + formatoHora.string(from: fecha) }
    let f = DateFormatter()
    f.locale = Locale(identifier: "es_ES")
    f.dateFormat = "d MMM, HH:mm"
    return f.string(from: fecha)
}

func duracion(_ segundos: Int) -> String {
    segundos < 60 ? "\(segundos) s" : "\(segundos / 60) min \(segundos % 60) s"
}

// MARK: - Taller

@MainActor
final class Taller: ObservableObject {
    @Published var indesign = false
    @Published var documentos: [DocInDesign] = []
    @Published var activo: String?
    @Published var problema: String?
    @Published var destino: Destino = .activo
    @Published var publicaciones: [Publicacion] = []
    @Published var publicacion = "" {
        didSet { UserDefaults.standard.set(publicacion, forKey: "publicacion") }
    }
    @Published var conClaude = true
    @Published var ejecuciones: [Ejecucion] = []
    @Published var vista: UUID?
    @Published var enCurso: UUID?
    @Published var ahora = Date()
    @Published var estados: [String: [String: Hecho]] = [:]
    @Published var aviso: Aviso?
    @Published var pregunta: Pregunta?
    @Published var nuevaPublicacion: NuevaPublicacion?
    @Published var actualizando: Publicacion?
    @Published var informe: InformeActualizacion?
    @Published var importacion: Importacion?

    private var proceso: Process?
    private var detenido = false
    private var leyendo = false
    private var pendiente = Data()
    private var tictac = 0

    init() {
        if let datos = UserDefaults.standard.data(forKey: "estados"),
           let e = try? JSONDecoder().decode([String: [String: Hecho]].self, from: datos) { estados = e }
        cargarPublicaciones()
        actualizarDocumentos()
        Timer.scheduledTimer(withTimeInterval: 1, repeats: true) { [weak self] _ in
            MainActor.assumeIsolated { self?.latido() }
        }
        NotificationCenter.default.addObserver(forName: NSApplication.didBecomeActiveNotification, object: nil, queue: .main) { [weak self] _ in
            MainActor.assumeIsolated { self?.actualizarDocumentos() }
        }
    }

    private func latido() {
        if enCurso != nil { ahora = Date() }
        tictac += 1
        if tictac % 4 == 0 && NSApp.isActive { actualizarDocumentos() }
    }

    // MARK: Documentos de InDesign

    var motorEncontrado: Bool { FileManager.default.fileExists(atPath: motor.appendingPathComponent("importar.py").path) }

    /// Nombre del documento con el que se trabaja (nil = todos)
    var nombreDestino: String? {
        switch destino {
        case .activo: return activo
        case .documento(let n): return n
        case .todos: return nil
        }
    }

    var rutaDestino: String? {
        guard let n = nombreDestino else { return nil }
        return documentos.first { $0.nombre == n }?.ruta
    }

    func actualizarDocumentos() {
        indesign = !NSRunningApplication.runningApplications(withBundleIdentifier: idInDesign).isEmpty
        guard indesign else {
            documentos = []
            activo = nil
            return
        }
        // Mientras trabaja el motor, InDesign está ocupado: no se le pregunta
        guard enCurso == nil, !leyendo else { return }
        leyendo = true
        let guion = """
        tell application id "com.adobe.InDesign"
        set r to ""
        if (count documents) > 0 then
        set r to name of active document
        repeat with d in documents
        set r to r & linefeed & (name of d) & tab
        try
        set r to r & (POSIX path of (full name of d as alias))
        end try
        end repeat
        end if
        return r
        end tell
        """
        Task {
            let r = await osascript(guion, espera: 6)
            leyendo = false
            guard r.ok else {
                // Lo normal la primera vez: macOS aún no ha dado permiso para controlar InDesign
                problema = r.texto.contains("-1743") || r.texto.contains("Not authorized")
                    ? "macOS no deja a la app controlar InDesign: actívalo en Ajustes › Privacidad › Automatización."
                    : "InDesign no responde (¿hay un diálogo abierto?)."
                return
            }
            problema = nil
            let l = r.texto.components(separatedBy: "\n")
            let docs = l.dropFirst().map { fila -> DocInDesign in
                let partes = fila.components(separatedBy: "\t")
                return DocInDesign(nombre: partes[0], ruta: partes.count > 1 ? partes[1] : "")
            }
            if docs != documentos { documentos = docs }
            let nuevo = r.texto.isEmpty ? nil : l[0]
            if nuevo != activo { activo = nuevo }
            // El documento elegido se ha cerrado: vuelve al activo
            if case .documento(let n) = destino, !docs.contains(where: { $0.nombre == n }) { destino = .activo }
        }
    }

    func abrirDocumento() {
        let panel = NSOpenPanel()
        panel.title = "Elige el documento de InDesign"
        panel.allowedContentTypes = [UTType(filenameExtension: "indd") ?? .data]
        if let ultima = UserDefaults.standard.string(forKey: "carpetaIndd") { panel.directoryURL = URL(fileURLWithPath: ultima) }
        guard panel.runModal() == .OK, let url = panel.url else { return }
        UserDefaults.standard.set(url.deletingLastPathComponent().path, forKey: "carpetaIndd")
        let guion = """
        with timeout of 600 seconds
        tell application id "com.adobe.InDesign"
        activate
        set d to open (POSIX file \(cadenaAS(url.path)))
        return name of d
        end tell
        end timeout
        """
        Task {
            let r = await osascript(guion, espera: 600)
            guard r.ok else {
                aviso = Aviso(titulo: "No se ha podido abrir", texto: r.texto)
                return
            }
            destino = .documento(r.texto)
            leyendo = false
            actualizarDocumentos()
        }
    }

    /// Argumentos --documento de los .py; nil (con aviso) si no se puede trabajar
    func argsDocumento(admiteTodos: Bool) -> [String]? {
        guard indesign, !documentos.isEmpty else {
            aviso = Aviso(titulo: "No hay documentos", texto: "Abre en InDesign el documento con el que quieres trabajar, o elígelo con «Abrir documento…».")
            return nil
        }
        if destino == .todos {
            if admiteTodos { return [] }
            aviso = Aviso(titulo: "Elige un documento", texto: "Esta acción trabaja con un solo documento: elige uno a la izquierda.")
            return nil
        }
        guard let n = nombreDestino, documentos.contains(where: { $0.nombre == n }) else {
            aviso = Aviso(titulo: "Documento cerrado", texto: "El documento elegido ya no está abierto en InDesign.")
            return nil
        }
        return ["--documento", n]
    }

    var textoDestino: String {
        nombreDestino.map { "«\($0)»" } ?? "todos los documentos abiertos"
    }

    // MARK: Publicaciones

    func cargarPublicaciones(elegir: String? = nil) {
        let carpeta = motor.appendingPathComponent("publicaciones")
        let tomls = (try? FileManager.default.contentsOfDirectory(at: carpeta, includingPropertiesForKeys: nil)) ?? []
        publicaciones = tomls
            .filter { $0.pathExtension == "toml" && $0.lastPathComponent != "ortotipografia.toml" }
            .map { url in
                let cabecera = String(leer(url).prefix(300))
                let nombre = primerGrupo("Configuración de «([^»]+)»", cabecera)
                    ?? (url.lastPathComponent.hasPrefix("maqueta-base") ? "Ponencias (maqueta base)" : url.lastPathComponent)
                return Publicacion(nombre: nombre, ruta: url.path)
            }
            .sorted { $0.nombre < $1.nombre }
        // La de la ventana de InDesign, si aún no se ha elegido ninguna aquí
        let deLaVentana = leer(FileManager.default.homeDirectoryForCurrentUser
            .appendingPathComponent("Library/Application Support/formatear_word_publicacion.txt"))
        let candidatas = [elegir, UserDefaults.standard.string(forKey: "publicacion"), deLaVentana]
        publicacion = candidatas.compactMap { $0 }.first { c in publicaciones.contains { $0.ruta == c } }
            ?? publicaciones.first { $0.ruta.hasSuffix("maqueta-base.toml") }?.ruta
            ?? publicaciones.first?.ruta ?? ""
    }

    var publicacionActual: Publicacion? { publicaciones.first { $0.ruta == publicacion } }

    func datos(_ p: Publicacion) -> DatosPublicacion {
        let t = leer(URL(fileURLWithPath: p.ruta))
        let quitarEscapes = { (s: String) in s.replacingOccurrences(of: "\\\\(.)", with: "$1", options: .regularExpression) }
        let maqueta = primerGrupo("^maqueta\\s*=\\s*\"([^\"]*)\"", t).map { motor.appendingPathComponent(quitarEscapes($0)) }
        return DatosPublicacion(maqueta: maqueta, maquetado: primerGrupo("^maquetado\\s*=\\s*\"([^\"]*)\"", t).map(quitarEscapes) ?? "")
    }

    func elegirMaquetado() {
        let panel = NSOpenPanel()
        panel.title = "Elige el último InDesign maquetado de la publicación (no se modifica: se trabaja con una copia)"
        panel.allowedContentTypes = [UTType(filenameExtension: "indd") ?? .data]
        guard panel.runModal() == .OK, let url = panel.url else { return }
        let propuesto = url.deletingPathExtension().lastPathComponent
            .replacingOccurrences(of: "\\s*N\\.?\\s*\\d+$", with: "", options: [.regularExpression, .caseInsensitive])
        nuevaPublicacion = NuevaPublicacion(maquetado: url, nombre: propuesto)
    }

    func crearPublicacion(_ n: NuevaPublicacion) {
        let nombre = n.nombre.trimmingCharacters(in: .whitespaces)
        guard !nombre.isEmpty else { return }
        ejecutar(nil, "Creando la publicación «\(nombre)»", accion: "Publicación creada", documento: nil,
                 programa: "nueva_publicacion.py", args: [n.maquetado.path, "--nombre", nombre]) { [weak self] _ in
            self?.cargarPublicaciones(elegir: motor.appendingPathComponent("publicaciones/\(slug(nombre)).toml").path)
        }
    }

    func prepararActualizacion(_ pub: Publicacion) {
        let d = datos(pub)
        guard let maqueta = d.maqueta else { return }
        if let abierto = documentos.first(where: { $0.ruta == maqueta.path || $0.ruta == d.nueva?.path }) {
            aviso = Aviso(titulo: "Documento abierto", texto: "«\(abierto.nombre)» está abierto: ciérralo antes de actualizar la maqueta.")
            return
        }
        let panel = NSOpenPanel()
        panel.title = "Elige el InDesign maquetado más reciente de «\(pub.nombre)» (no se modifica: se trabaja con una copia)"
        panel.allowedContentTypes = [UTType(filenameExtension: "indd") ?? .data]
        if !d.maquetado.isEmpty {
            panel.directoryURL = URL(fileURLWithPath: d.maquetado).deletingLastPathComponent().deletingLastPathComponent()
        }
        guard panel.runModal() == .OK, let url = panel.url else { return }
        ejecutar(nil, "Preparando la maqueta nueva de «\(pub.nombre)»", accion: "Maqueta preparada", documento: nil,
                 programa: "nueva_publicacion.py", args: [url.path, "--actualizar", pub.ruta]) { [weak self] _ in
            guard let self, let json = d.pendiente, let datos = try? Data(contentsOf: json),
                  let o = try? JSONSerialization.jsonObject(with: datos) as? [String: Any] else { return }
            self.informe = InformeActualizacion(publicacion: pub, informe: o["informe"] as? String ?? "",
                                                avisos: o["avisos"] as? Int ?? 0)
        }
    }

    /// La de por defecto del motor: su maqueta («Maqueta base.indd») es la del proyecto y no se borra
    func esBase(_ p: Publicacion) -> Bool { p.ruta.hasSuffix("/maqueta-base.toml") }

    /// Todo lo que deja una publicación: su .toml, su maqueta, las anteriores guardadas al
    /// actualizarla («<maqueta> 2026-10-27.indd») y una actualización a medias («(nueva)»)
    func archivos(_ p: Publicacion) -> [URL] {
        let fm = FileManager.default
        var r = [URL(fileURLWithPath: p.ruta)]
        let d = datos(p)
        let maquetas = motor.appendingPathComponent("publicaciones/maquetas")
        guard let maqueta = d.maqueta, maqueta.path.hasPrefix(maquetas.path + "/") else { return r }
        r += [maqueta, d.nueva, d.pendiente].compactMap { $0 }.filter { fm.fileExists(atPath: $0.path) }
        let base = NSRegularExpression.escapedPattern(for: maqueta.deletingPathExtension().lastPathComponent)
        let anteriores = maquetas.appendingPathComponent("anteriores")
        let nombres = (try? fm.contentsOfDirectory(atPath: anteriores.path)) ?? []
        r += nombres.filter { $0.range(of: "^\(base) \\d{4}-\\d{2}-\\d{2}(-\\d+)?\\.indd$", options: .regularExpression) != nil }
            .sorted().map { anteriores.appendingPathComponent($0) }
        return r
    }

    func borrarPublicacion() {
        guard let p = publicacionActual else { return }
        guard !esBase(p) else {
            aviso = Aviso(titulo: "No se puede borrar", texto: "«\(p.nombre)» es la publicación por defecto del motor.")
            return
        }
        let lista = archivos(p)
        if let abierto = documentos.first(where: { d in lista.contains { $0.path == d.ruta } }) {
            aviso = Aviso(titulo: "Documento abierto", texto: "«\(abierto.nombre)» está abierto: ciérralo antes de borrar la publicación.")
            return
        }
        let relativos = lista.map { $0.path.replacingOccurrences(of: motor.path + "/", with: "") }
        pregunta = Pregunta(titulo: "¿Borrar la publicación «\(p.nombre)»?",
                            texto: "Van a la Papelera (se pueden recuperar desde allí):\n\n" + relativos.map { "• " + $0 }.joined(separator: "\n") +
                                "\n\nLos capítulos ya montados con ella no se tocan.",
                            boton: "Borrar") { [weak self] in
            guard let self else { return }
            var e = Ejecucion(seccion: nil, titulo: "Publicación «\(p.nombre)» borrada", accion: "Publicación borrada", documento: nil)
            var ok = true
            for (url, rel) in zip(lista, relativos) {
                do {
                    try FileManager.default.trashItem(at: url, resultingItemURL: nil)
                    e.texto += "A la Papelera: \(rel)\n"
                } catch {
                    ok = false
                    e.texto += "Error con \(rel): \(error.localizedDescription)\n"
                }
            }
            e.fin = Date()
            e.ok = ok
            self.ejecuciones.append(e)
            self.vista = e.id
            self.cargarPublicaciones()
        }
    }

    func cerrarActualizacion(_ i: InformeActualizacion, guardar: Bool) {
        ejecutar(nil, (guardar ? "Guardando" : "Descartando") + " la maqueta nueva de «\(i.publicacion.nombre)»",
                 accion: guardar ? "Maqueta guardada" : "Maqueta descartada", documento: nil,
                 programa: "nueva_publicacion.py", args: [guardar ? "--confirmar" : "--descartar", i.publicacion.ruta])
    }

    // MARK: Procesos

    var ejecucionEnCurso: Ejecucion? { ejecuciones.first { $0.id == enCurso } }
    var ejecucionVista: Ejecucion? { ejecuciones.first { $0.id == vista } ?? ejecuciones.last }

    func segundos(_ e: Ejecucion) -> Int { Int((e.fin ?? ahora).timeIntervalSince(e.inicio)) }

    /// Lanza «python3 -I programa args» en la carpeta del motor y va recogiendo su salida
    func ejecutar(_ seccion: Seccion?, _ titulo: String, accion: String, documento: String?,
                  programa: String, args: [String], alTerminar: ((Bool) -> Void)? = nil) {
        guard enCurso == nil else {
            aviso = Aviso(titulo: "Hay un paso en marcha", texto: "Espera a que termine «\(ejecucionEnCurso?.titulo ?? "")» o detenlo.")
            return
        }
        guard motorEncontrado else {
            aviso = Aviso(titulo: "No encuentro el motor", texto: "Falta la carpeta «\(motor.path)».")
            return
        }
        let e = Ejecucion(seccion: seccion, titulo: titulo, accion: accion, documento: documento)
        ejecuciones.append(e)
        enCurso = e.id
        vista = e.id
        ahora = Date()
        detenido = false
        pendiente = Data()

        let p = Process()
        p.executableURL = URL(fileURLWithPath: python)
        p.arguments = ["-I", programa] + args
        p.currentDirectoryURL = motor
        var entorno = ProcessInfo.processInfo.environment
        entorno["LANG"] = "es_ES.UTF-8"
        entorno["LC_ALL"] = "es_ES.UTF-8"
        entorno["PYTHONUNBUFFERED"] = "1"
        p.environment = entorno
        let tubo = Pipe()
        p.standardOutput = tubo
        p.standardError = tubo
        p.standardInput = FileHandle.nullDevice
        do { try p.run() } catch {
            anadir(e.id, Data("No se ha podido lanzar \(programa): \(error.localizedDescription)\n".utf8))
            terminar(e.id, estado: 1, alTerminar: alTerminar)
            return
        }
        proceso = p
        // Leer y terminar desde el mismo hilo: la salida llega entera y en orden antes del final
        DispatchQueue.global().async {
            let lector = tubo.fileHandleForReading
            while true {
                let datos = lector.availableData
                if datos.isEmpty { break }
                DispatchQueue.main.async { MainActor.assumeIsolated { self.anadir(e.id, datos) } }
            }
            p.waitUntilExit()
            let estado = p.terminationStatus
            DispatchQueue.main.async { MainActor.assumeIsolated { self.terminar(e.id, estado: estado, alTerminar: alTerminar) } }
        }
    }

    private func anadir(_ id: UUID, _ datos: Data, final: Bool = false) {
        pendiente.append(datos)
        // Solo hasta el último salto de línea: un carácter de varios bytes puede venir partido
        let corte = final ? pendiente.endIndex : (pendiente.lastIndex(of: 0x0A).map { pendiente.index(after: $0) } ?? pendiente.startIndex)
        guard corte > pendiente.startIndex, let i = ejecuciones.firstIndex(where: { $0.id == id }) else { return }
        ejecuciones[i].texto += String(decoding: pendiente[..<corte], as: UTF8.self)
        pendiente = Data(pendiente[corte...])
    }

    private func terminar(_ id: UUID, estado: Int32, alTerminar: ((Bool) -> Void)?) {
        anadir(id, Data(), final: true)
        proceso = nil
        enCurso = nil
        guard let i = ejecuciones.firstIndex(where: { $0.id == id }) else { return }
        let texto = ejecuciones[i].texto
        let ok = estado == 0 && !detenido && !texto.contains("Traceback (most recent call last)")
        ejecuciones[i].fin = Date()
        ejecuciones[i].ok = ok
        if detenido { ejecuciones[i].texto += "\n— Detenido —" }
        let e = ejecuciones[i]
        if let s = e.seccion, let doc = e.documento { anotar(doc, s, e.accion, ok) }
        // Si se estaba en InDesign, el icono del Dock avisa de que ha terminado
        if !NSApp.isActive { NSApp.requestUserAttention(.informationalRequest) }
        alTerminar?(ok)
        actualizarDocumentos()
    }

    func detener() {
        guard let p = proceso, p.isRunning else { return }
        detenido = true
        // También los hijos (el osascript que habla con InDesign)
        let pkill = Process()
        pkill.executableURL = URL(fileURLWithPath: "/usr/bin/pkill")
        pkill.arguments = ["-TERM", "-P", String(p.processIdentifier)]
        try? pkill.run()
        pkill.waitUntilExit()
        p.terminate()
    }

    func anotar(_ documento: String, _ s: Seccion, _ accion: String, _ ok: Bool) {
        estados[documento, default: [:]][s.rawValue] = Hecho(accion: accion, fecha: Date(), ok: ok)
        if let datos = try? JSONEncoder().encode(estados) { UserDefaults.standard.set(datos, forKey: "estados") }
    }

    /// Abre una ventana del motor dentro de InDesign con el documento elegido delante
    func abrirEnInDesign(_ jsx: String, _ titulo: String, _ seccion: Seccion) {
        guard enCurso == nil else {
            aviso = Aviso(titulo: "Hay un paso en marcha", texto: "Espera a que termine «\(ejecucionEnCurso?.titulo ?? "")».")
            return
        }
        guard let a = argsDocumento(admiteTodos: false) else { return }
        let documento = a[1]
        let guion = """
        with timeout of 300 seconds
        tell application id "com.adobe.InDesign"
        activate
        do script (POSIX file \(cadenaAS(lanzadorJSX.path))) language javascript with arguments {\(cadenaAS(motor.appendingPathComponent("jsx/" + jsx).path)), \(cadenaAS(documento)), \(cadenaAS(publicacion))}
        end tell
        end timeout
        """
        var e = Ejecucion(seccion: seccion, titulo: titulo, accion: titulo, documento: documento)
        e.texto = "Abriendo «\(titulo)» en InDesign con «\(documento)» delante…\n"
        ejecuciones.append(e)
        vista = e.id
        Task {
            let r = await osascript(guion, espera: 300)
            guard let i = ejecuciones.firstIndex(where: { $0.id == e.id }) else { return }
            let ok = r.ok && r.texto == "ok"
            ejecuciones[i].texto += ok ? "La ventana está abierta en InDesign: sigue allí." : (r.texto.isEmpty ? "InDesign no ha respondido." : r.texto)
            ejecuciones[i].fin = Date()
            ejecuciones[i].ok = ok
        }
    }

    // MARK: Galerada

    func elegirWord() {
        let panel = NSOpenPanel()
        panel.title = "Elige el Word del capítulo (varios con Cmd si las tablas o figuras vienen aparte)"
        panel.message = "Las imágenes no hace falta elegirlas: se cogen de la misma carpeta, que da nombre al capítulo."
        panel.allowsMultipleSelection = true
        panel.allowedContentTypes = ["docx", "doc"].compactMap { UTType(filenameExtension: $0) }
        let ultima = UserDefaults.standard.string(forKey: "carpetaWord").map { URL(fileURLWithPath: $0) }
        panel.directoryURL = ultima ?? motor.appendingPathComponent("Documentos Word")
        guard panel.runModal() == .OK else { return }
        importar(panel.urls)
    }

    func importar(_ urls: [URL]) {
        let words = urls.filter { ["docx", "doc"].contains($0.pathExtension.lowercased()) && !$0.lastPathComponent.hasPrefix("~$") }
        guard let primero = words.first else {
            aviso = Aviso(titulo: "No es un Word", texto: "Arrastra uno o varios .docx (o .doc) del capítulo.")
            return
        }
        let carpeta = primero.deletingLastPathComponent()
        guard words.allSatisfy({ $0.deletingLastPathComponent().path == carpeta.path }) else {
            aviso = Aviso(titulo: "Carpetas distintas", texto: "Los Word de un capítulo tienen que estar en la misma carpeta.")
            return
        }
        let nombre = carpeta.lastPathComponent
        if documentos.contains(where: { $0.nombre == nombre + ".indd" }) {
            aviso = Aviso(titulo: "Documento abierto", texto: "«\(nombre).indd» está abierto: ciérralo antes de volver a importarlo.")
            return
        }
        UserDefaults.standard.set(carpeta.deletingLastPathComponent().path, forKey: "carpetaWord")
        // Antes de importar, confirmar con qué publicación (se puede cambiar en la hoja)
        importacion = Importacion(nombre: nombre, words: words)
    }

    func confirmarImportacion(_ i: Importacion) {
        let titulo = "Importando «\(i.nombre)»" + (i.words.count > 1 ? " (\(i.words.count) Word)" : "") +
            " con «\(publicacionActual?.nombre ?? "")»"
        ejecutar(.galerada, titulo, accion: "Galerada montada", documento: i.nombre + ".indd",
                 programa: "importar.py", args: i.words.map(\.path) + ["--publicacion", publicacion]) { [weak self] ok in
            if ok { self?.destino = .documento(i.nombre + ".indd") }
        }
    }

    // MARK: Tipografía

    func contarCorrecciones() {
        guard let a = argsDocumento(admiteTodos: true) else { return }
        ejecutar(.tipografia, "Contando correcciones en \(textoDestino)", accion: "Correcciones contadas", documento: nombreDestino,
                 programa: "ortotipografia.py", args: a + ["--maqueta", publicacion])
    }

    func aplicarCorrecciones() {
        guard let a = argsDocumento(admiteTodos: true) else { return }
        pregunta = Pregunta(titulo: "¿Aplicar las correcciones seguras?",
                            texto: "En \(textoDestino). Cada documento se deshace con un Cmd+Z.", boton: "Aplicar") { [weak self] in
            guard let self else { return }
            self.ejecutar(.tipografia, "Aplicando correcciones en \(self.textoDestino)", accion: "Correcciones aplicadas",
                          documento: self.nombreDestino, programa: "ortotipografia.py", args: a + ["--aplicar", "--maqueta", self.publicacion])
        }
    }

    func buscarDudas() {
        guard let a = argsDocumento(admiteTodos: true) else { return }
        pregunta = Pregunta(titulo: "¿Buscar dudas?",
                            texto: "En \(textoDestino). Se vuelven a marcar todas: lo que no hayas revisado de una pasada anterior vuelve a aparecer.",
                            boton: "Buscar") { [weak self] in
            guard let self else { return }
            var args = a + ["--marcar", "--maqueta", self.publicacion]
            if self.conClaude { args.append("--claude") }
            self.ejecutar(.tipografia, "Buscando dudas en \(self.textoDestino)" + (self.conClaude ? " (con Claude)" : ""),
                          accion: "Dudas marcadas", documento: self.nombreDestino, programa: "dudas.py", args: args)
        }
    }

    // MARK: Cierre

    func cierre(aplicar: Bool) {
        guard let a = argsDocumento(admiteTodos: true) else { return }
        ejecutar(.cierre, (aplicar ? "Finalizando " : "Simulando el cierre de ") + textoDestino,
                 accion: aplicar ? "Capítulo finalizado" : "Cierre simulado", documento: nombreDestino,
                 programa: "finalizar.py", args: a + (aplicar ? ["--aplicar"] : []) + ["--publicacion", publicacion])
    }
}

// MARK: - Ventana

struct Ventana: View {
    @ObservedObject var taller: Taller
    @AppStorage("alturaConsola") private var alturaConsola = 200.0
    @State private var alturaInicial: Double?

    var body: some View {
        NavigationSplitView {
            BarraLateral(taller: taller)
                .navigationSplitViewColumnWidth(min: 250, ideal: 280, max: 340)
        } detail: {
            VStack(spacing: 0) {
                ScrollView {
                    VStack(spacing: 0) {
                        Cabecera(taller: taller)
                        // Las tres tarjetas, a la altura de la más alta
                        HStack(alignment: .top, spacing: 14) {
                            ForEach(Seccion.allCases) { s in
                                TarjetaSeccion(taller: taller, seccion: s)
                            }
                        }
                        .fixedSize(horizontal: false, vertical: true)
                        .padding(.horizontal, 20)
                        .padding(.bottom, 18)
                    }
                }
                // Separador que se arrastra para dar más o menos sitio a la consola
                Rectangle()
                    .fill(Color.primary.opacity(0.12))
                    .frame(height: 1)
                    .padding(.vertical, 3)
                    .contentShape(Rectangle())
                    .onHover { dentro in if dentro { NSCursor.resizeUpDown.push() } else { NSCursor.pop() } }
                    .gesture(DragGesture()
                        .onChanged { g in
                            let inicio = alturaInicial ?? alturaConsola
                            alturaInicial = inicio
                            alturaConsola = min(max(inicio - g.translation.height, 90), 600)
                        }
                        .onEnded { _ in alturaInicial = nil })
                Consola(taller: taller)
                    .frame(height: alturaConsola)
            }
            .navigationTitle("")
            .background(Color(nsColor: .windowBackgroundColor))
        }
        .alert(taller.aviso?.titulo ?? "", isPresented: Binding(get: { taller.aviso != nil }, set: { if !$0 { taller.aviso = nil } }),
               presenting: taller.aviso) { _ in
            Button("Aceptar") {}
        } message: { a in Text(a.texto) }
        .alert(taller.pregunta?.titulo ?? "", isPresented: Binding(get: { taller.pregunta != nil }, set: { if !$0 { taller.pregunta = nil } }),
               presenting: taller.pregunta) { p in
            Button(p.boton) { p.hacer() }
            Button("Cancelar", role: .cancel) {}
        } message: { p in Text(p.texto) }
        .sheet(item: $taller.nuevaPublicacion) { n in
            HojaNuevaPublicacion(taller: taller, nueva: n)
        }
        .sheet(item: $taller.actualizando) { p in
            HojaActualizar(taller: taller, elegida: p)
        }
        .sheet(item: $taller.informe) { i in
            HojaInforme(taller: taller, informe: i)
        }
        .sheet(item: $taller.importacion) { i in
            HojaImportar(taller: taller, importacion: i)
        }
    }
}

// MARK: - Barra lateral

struct BarraLateral: View {
    @ObservedObject var taller: Taller

    var body: some View {
        VStack(alignment: .leading, spacing: 18) {
            HStack(spacing: 10) {
                ZStack {
                    RoundedRectangle(cornerRadius: 9)
                        .fill(LinearGradient(colors: Seccion.allCases.map(\.color), startPoint: .topLeading, endPoint: .bottomTrailing))
                    Image(systemName: "text.book.closed.fill").foregroundStyle(.white).font(.system(size: 17, weight: .semibold))
                }
                .frame(width: 36, height: 36)
                VStack(alignment: .leading, spacing: 1) {
                    Text("Crear Publicación").font(.system(size: 15, weight: .bold))
                    Text("Del Word a InDesign").font(.system(size: 11)).foregroundStyle(.secondary)
                }
            }
            .padding(.top, 6)

            VStack(alignment: .leading, spacing: 8) {
                Rotulo("Publicación")
                HStack(spacing: 6) {
                    Picker("", selection: $taller.publicacion) {
                        ForEach(taller.publicaciones) { p in Text(p.nombre).tag(p.ruta) }
                    }
                    .labelsHidden()
                    Menu {
                        Button("Nueva publicación…") { taller.elegirMaquetado() }
                        Button("Actualizar publicación…") { taller.actualizando = taller.publicacionActual }
                            .disabled(taller.publicacionActual == nil)
                        Divider()
                        Button("Mostrar su configuración en el Finder") {
                            NSWorkspace.shared.activateFileViewerSelecting([URL(fileURLWithPath: taller.publicacion)])
                        }
                        Divider()
                        Button("Borrar publicación…", role: .destructive) { taller.borrarPublicacion() }
                            .disabled(taller.publicacionActual.map(taller.esBase) ?? true)
                    } label: { Image(systemName: "ellipsis.circle") }
                    .menuStyle(.borderlessButton)
                    .fixedSize()
                    .disabled(taller.enCurso != nil)
                }
                Text("Estilos y maqueta con los que se importa y se corrige").font(.system(size: 10.5)).foregroundStyle(.tertiary)
            }

            VStack(alignment: .leading, spacing: 8) {
                HStack {
                    Rotulo("Trabajar en")
                    Spacer()
                    HStack(spacing: 4) {
                        Circle().fill(taller.indesign ? Color.green : Color.secondary.opacity(0.5)).frame(width: 7, height: 7)
                        Text(taller.indesign ? "InDesign abierto" : "InDesign cerrado").font(.system(size: 10.5)).foregroundStyle(.secondary)
                    }
                }
                if let problema = taller.problema, taller.indesign {
                    VStack(alignment: .leading, spacing: 6) {
                        Label(problema, systemImage: "exclamationmark.triangle.fill")
                            .font(.system(size: 11)).foregroundStyle(.orange).fixedSize(horizontal: false, vertical: true)
                        Button("Abrir Automatización") {
                            NSWorkspace.shared.open(URL(string: "x-apple.systempreferences:com.apple.preference.security?Privacy_Automation")!)
                        }
                        .controlSize(.small)
                    }
                    .padding(8)
                    .background(RoundedRectangle(cornerRadius: 8).fill(Color.orange.opacity(0.1)))
                }
                ScrollView {
                    VStack(spacing: 3) {
                        FilaDestino(icono: "scope", titulo: "Documento activo",
                                    detalle: taller.activo ?? "Ninguno", elegida: taller.destino == .activo) { taller.destino = .activo }
                        if !taller.documentos.isEmpty {
                            Divider().padding(.vertical, 4)
                            ForEach(taller.documentos) { d in
                                FilaDestino(icono: d.nombre == taller.activo ? "doc.fill" : "doc", titulo: d.nombre,
                                            detalle: d.ruta.isEmpty ? "Sin guardar" : URL(fileURLWithPath: d.ruta).deletingLastPathComponent().lastPathComponent,
                                            elegida: taller.destino == .documento(d.nombre)) { taller.destino = .documento(d.nombre) }
                            }
                            Divider().padding(.vertical, 4)
                            FilaDestino(icono: "square.stack.3d.up", titulo: "Todos los abiertos",
                                        detalle: "Solo Tipografía y Cierre", elegida: taller.destino == .todos) { taller.destino = .todos }
                        }
                    }
                }
                Button { taller.abrirDocumento() } label: {
                    Label("Abrir documento…", systemImage: "folder").frame(maxWidth: .infinity)
                }
                .controlSize(.large)
            }

            Spacer(minLength: 0)

            Button {
                NSWorkspace.shared.activateFileViewerSelecting([motor])
            } label: {
                HStack(spacing: 6) {
                    Image(systemName: taller.motorEncontrado ? "gearshape.2" : "exclamationmark.triangle.fill")
                        .foregroundStyle(taller.motorEncontrado ? Color.secondary : Color.orange)
                    VStack(alignment: .leading, spacing: 0) {
                        Text("Motor").font(.system(size: 10.5, weight: .semibold))
                        Text(motor.lastPathComponent).font(.system(size: 10.5)).lineLimit(1).truncationMode(.middle)
                    }
                    .foregroundStyle(.secondary)
                }
            }
            .buttonStyle(.plain)
            .help(motor.path)
        }
        .padding(14)
    }
}

struct Rotulo: View {
    let texto: String
    init(_ texto: String) { self.texto = texto }
    var body: some View {
        Text(texto.uppercased()).font(.system(size: 10.5, weight: .semibold)).tracking(0.6).foregroundStyle(.secondary)
    }
}

struct FilaDestino: View {
    let icono: String
    let titulo: String
    let detalle: String
    let elegida: Bool
    let hacer: () -> Void
    @State private var encima = false

    var body: some View {
        Button(action: hacer) {
            HStack(spacing: 9) {
                Image(systemName: icono)
                    .font(.system(size: 13))
                    .frame(width: 18)
                    .foregroundStyle(elegida ? Color.white : Color.accentColor)
                VStack(alignment: .leading, spacing: 1) {
                    Text(titulo).font(.system(size: 12.5, weight: .medium)).lineLimit(1).truncationMode(.middle)
                    Text(detalle).font(.system(size: 10.5)).lineLimit(1).truncationMode(.middle)
                        .foregroundStyle(elegida ? Color.white.opacity(0.8) : Color.secondary)
                }
                Spacer(minLength: 0)
            }
            .foregroundStyle(elegida ? Color.white : Color.primary)
            .padding(.horizontal, 8)
            .padding(.vertical, 6)
            .background(RoundedRectangle(cornerRadius: 7)
                .fill(elegida ? Color.accentColor : (encima ? Color.primary.opacity(0.06) : Color.clear)))
            .contentShape(Rectangle())
        }
        .buttonStyle(.plain)
        .onHover { encima = $0 }
        .animation(.easeOut(duration: 0.15), value: elegida)
    }
}

// MARK: - Cabecera

struct Cabecera: View {
    @ObservedObject var taller: Taller

    var body: some View {
        HStack(alignment: .center, spacing: 14) {
            Image(systemName: taller.destino == .todos ? "square.stack.3d.up.fill" : "doc.text.fill")
                .font(.system(size: 26))
                .foregroundStyle(.tint)
            VStack(alignment: .leading, spacing: 3) {
                Text(titulo).font(.system(size: 20, weight: .bold)).lineLimit(1).truncationMode(.middle)
                Text(detalle).font(.system(size: 12)).foregroundStyle(.secondary).lineLimit(1).truncationMode(.middle)
            }
            Spacer()
            if let e = taller.ejecucionEnCurso {
                HStack(spacing: 8) {
                    ProgressView().controlSize(.small)
                    Text("\(e.seccion?.titulo ?? "Publicación") · \(duracion(taller.segundos(e)))")
                        .font(.system(size: 12, weight: .medium)).monospacedDigit()
                }
                .padding(.horizontal, 12)
                .padding(.vertical, 6)
                .background(Capsule().fill((e.seccion?.color ?? .accentColor).opacity(0.14)))
                .transition(.scale.combined(with: .opacity))
            }
        }
        .animation(.spring(duration: 0.3), value: taller.enCurso)
        .padding(.horizontal, 22)
        .padding(.top, 18)
        .padding(.bottom, 14)
    }

    var titulo: String {
        switch taller.destino {
        case .todos: return "Todos los documentos abiertos"
        default: return taller.nombreDestino ?? "Ningún documento"
        }
    }

    var detalle: String {
        let pub = "Publicación: " + (taller.publicacionActual?.nombre ?? "—")
        switch taller.destino {
        case .activo: return (taller.activo == nil ? "Abre un documento en InDesign o elige uno" : "Documento activo de InDesign") + " · " + pub
        case .documento: return (taller.rutaDestino.map { URL(fileURLWithPath: $0).deletingLastPathComponent().path } ?? "Elegido a mano") + " · " + pub
        case .todos: return "\(taller.documentos.count) abiertos en InDesign · " + pub
        }
    }
}

// MARK: - Tarjetas

struct TarjetaSeccion: View {
    @ObservedObject var taller: Taller
    let seccion: Seccion
    @State private var soltando = false

    var trabajando: Bool { taller.ejecucionEnCurso?.seccion == seccion }
    var color: Color { seccion.color }

    var body: some View {
        VStack(alignment: .leading, spacing: 14) {
            HStack(alignment: .top, spacing: 12) {
                ZStack {
                    RoundedRectangle(cornerRadius: 11).fill(color.gradient)
                    Image(systemName: seccion.icono).font(.system(size: 19, weight: .semibold)).foregroundStyle(.white)
                        .symbolEffect(.pulse, isActive: trabajando)
                }
                .frame(width: 42, height: 42)
                VStack(alignment: .leading, spacing: 2) {
                    Text("PASO \(seccion.numero)").font(.system(size: 10, weight: .bold)).tracking(0.8).foregroundStyle(color)
                    Text(seccion.titulo).font(.system(size: 17, weight: .bold))
                }
                Spacer(minLength: 0)
            }
            Text(seccion.lema).font(.system(size: 12)).foregroundStyle(.secondary).fixedSize(horizontal: false, vertical: true)

            acciones
                .disabled(taller.enCurso != nil)

            Spacer(minLength: 0)
            estado
        }
        .padding(16)
        .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .topLeading)
        .background(
            RoundedRectangle(cornerRadius: 16)
                .fill(Color(nsColor: .controlBackgroundColor))
                .shadow(color: .black.opacity(0.07), radius: 6, y: 2)
        )
        .overlay(
            RoundedRectangle(cornerRadius: 16)
                .strokeBorder(trabajando || soltando ? color : Color.primary.opacity(0.07), lineWidth: trabajando || soltando ? 2 : 1)
        )
        .animation(.easeInOut(duration: 0.25), value: trabajando)
    }

    @ViewBuilder var acciones: some View {
        switch seccion {
        case .galerada:
            VStack(alignment: .leading, spacing: 8) {
                Button { taller.elegirWord() } label: {
                    VStack(spacing: 8) {
                        Image(systemName: soltando ? "arrow.down.doc.fill" : "doc.badge.plus")
                            .font(.system(size: 28, weight: .light))
                            .foregroundStyle(color)
                            .symbolEffect(.bounce, value: soltando)
                        Text("Importar Word…").font(.system(size: 13, weight: .semibold))
                        Text("Haz clic o arrastra aquí el Word del capítulo (varios si las tablas o figuras vienen aparte)")
                            .font(.system(size: 11)).foregroundStyle(.secondary).multilineTextAlignment(.center)
                            .fixedSize(horizontal: false, vertical: true)
                        Label("Publicación: \(taller.publicacionActual?.nombre ?? "ninguna")", systemImage: "books.vertical")
                            .font(.system(size: 11, weight: .semibold))
                            .foregroundStyle(color)
                            .padding(.horizontal, 10)
                            .padding(.vertical, 4)
                            .background(Capsule().fill(color.opacity(0.12)))
                    }
                    .padding(14)
                    .frame(maxWidth: .infinity)
                    .background(RoundedRectangle(cornerRadius: 12).fill(color.opacity(soltando ? 0.16 : 0.06)))
                    .overlay(RoundedRectangle(cornerRadius: 12).strokeBorder(color.opacity(0.5), style: StrokeStyle(lineWidth: 1.5, dash: [6, 4])))
                    .contentShape(Rectangle())
                }
                .buttonStyle(.plain)
                .help("Monta la galerada en un documento nuevo con la maqueta de la publicación y resalta Tabla, Figura, Algoritmo… («Risk word»). Las figuras se buscan en la carpeta del Word, que da nombre al capítulo")
                .onDrop(of: [.fileURL], isTargeted: $soltando) { proveedores in
                    recoger(proveedores)
                    return true
                }
                Accion(icono: "flag.2.crossed", titulo: "Recorrer marcas…", detalle: "Las dudas de la importación en orden de página, con su motivo",
                       color: color, enInDesign: true) { taller.abrirEnInDesign("recorrer_marcas.jsx", "Recorrer marcas", .galerada) }
            }
        case .tipografia:
            VStack(alignment: .leading, spacing: 4) {
                Rotulo("Correcciones seguras")
                Accion(icono: "eye", titulo: "Revisar una a una…", detalle: "Antes y después de cada corrección, para aceptarla u omitirla",
                       color: color, enInDesign: true) { taller.abrirEnInDesign("revisar_correcciones.jsx", "Revisar correcciones", .tipografia) }
                Accion(icono: "number", titulo: "Contar cambios", detalle: "Lo que cambiaría cada regla, sin tocar nada",
                       color: color) { taller.contarCorrecciones() }
                Accion(icono: "wand.and.stars", titulo: "Aplicar correcciones", detalle: "Todas las reglas seguras de golpe (Cmd+Z lo deshace)",
                       color: color, principal: true) { taller.aplicarCorrecciones() }
                Rotulo("Dudas").padding(.top, 8)
                Accion(icono: "questionmark.bubble", titulo: "Buscar dudas", detalle: "Tildes, palabras desconocidas, extranjerismos, cursivas…",
                       color: color) { taller.buscarDudas() }
                Toggle(isOn: $taller.conClaude) {
                    Label("Con propuestas de Claude", systemImage: "sparkles").font(.system(size: 11.5))
                }
                .toggleStyle(.switch).controlSize(.mini).padding(.leading, 48)
                Accion(icono: "list.bullet.rectangle", titulo: "Revisar dudas…", detalle: "Recorrerlas y cambiar u omitir cada una",
                       color: color, enInDesign: true) { taller.abrirEnInDesign("revisar_dudas.jsx", "Revisar dudas", .tipografia) }
            }
        case .cierre:
            VStack(alignment: .leading, spacing: 4) {
                // Lo que hace jsx/finalizar.jsx del motor
                VStack(alignment: .leading, spacing: 7) {
                    Rotulo("Qué hace «Finalizar capítulo»")
                    Text("Puntuación").font(.system(size: 11, weight: .semibold)).foregroundStyle(color).padding(.top, 2)
                    PasoCierre(numero: 1, color: color, texto: "La puntuación pegada detrás de una palabra toma su formato",
                               ejemplo: ". , ; : ) ] } » ” ’ ! ? … /   →   «Epiescleritis.»")
                    PasoCierre(numero: 2, color: color, texto: "La de apertura pegada delante, también",
                               ejemplo: "( [ { « “ ‘ ¿ ¡   →   «(Fusarium)»")
                    PasoCierre(numero: 3, color: color, texto: "Guiones y rayas entre palabras con el mismo formato",
                               ejemplo: "- – —   →   «Fusarium–Aspergillus»")
                    PasoCierre(numero: 4, color: color, texto: "No pasan a la puntuación el superíndice ni el estilo de los símbolos",
                               ejemplo: "«10⁶.» no lleva el punto volado")
                    Text("Enlaces").font(.system(size: 11, weight: .semibold)).foregroundStyle(color).padding(.top, 4)
                    PasoCierre(numero: 5, color: color, texto: "Las URLs pasan a hipervínculos sin cambiar su formato ni su estilo, y sin borde visible",
                               ejemplo: "http://…   https://…   www.…")
                    PasoCierre(numero: 6, color: color, texto: "Los DOI se enlazan a doi.org, solo el identificador",
                               ejemplo: "doi: 10.1016/…   →   https://doi.org/10.1016/…")
                    PasoCierre(numero: 7, color: color, texto: "La puntuación final queda fuera del enlace, y lo que ya era hipervínculo no se toca",
                               ejemplo: "«…/index.html).»")
                    Label("Un Cmd+Z por documento lo deshace todo", systemImage: "arrow.uturn.backward")
                        .font(.system(size: 10.5)).foregroundStyle(.secondary).padding(.top, 2)
                }
                .padding(10)
                .background(RoundedRectangle(cornerRadius: 10).fill(color.opacity(0.06)))
                .padding(.bottom, 8)
                Accion(icono: "eye", titulo: "Simular cierre", detalle: "Cuenta lo que cambiaría, sin tocar nada",
                       color: color) { taller.cierre(aplicar: false) }
                Accion(icono: "checkmark.seal.fill", titulo: "Finalizar capítulo", detalle: "Aplica el cierre (Cmd+Z lo deshace)",
                       color: color, principal: true) { taller.cierre(aplicar: true) }
            }
        }
    }

    @ViewBuilder var estado: some View {
        let doc = taller.nombreDestino
        let hecho = doc.flatMap { taller.estados[$0]?[seccion.rawValue] }
        HStack(spacing: 6) {
            if trabajando {
                ProgressView().controlSize(.mini)
                Text("Trabajando… \(duracion(taller.ejecucionEnCurso.map { taller.segundos($0) } ?? 0))").monospacedDigit()
            } else if let hecho {
                Image(systemName: hecho.ok ? "checkmark.circle.fill" : "exclamationmark.circle.fill")
                    .foregroundStyle(hecho.ok ? color : Color.orange)
                Text("\(hecho.accion) · \(cuando(hecho.fecha))")
            } else {
                Image(systemName: "circle.dashed").foregroundStyle(.tertiary)
                Text(taller.destino == .todos ? "Varios documentos" : doc == nil ? "Sin documento" : "Aún sin hacer en este documento")
            }
        }
        .font(.system(size: 11))
        .foregroundStyle(.secondary)
        .padding(.top, 8)
        .frame(maxWidth: .infinity, alignment: .leading)
        .overlay(alignment: .top) { Divider() }
    }

    private func recoger(_ proveedores: [NSItemProvider]) {
        var urls: [URL] = []
        let grupo = DispatchGroup()
        for p in proveedores {
            grupo.enter()
            _ = p.loadObject(ofClass: URL.self) { url, _ in
                if let url { DispatchQueue.main.async { urls.append(url) } }
                grupo.leave()
            }
        }
        grupo.notify(queue: .main) { taller.importar(urls) }
    }
}

struct PasoCierre: View {
    let numero: Int
    let color: Color
    let texto: String
    let ejemplo: String

    var body: some View {
        HStack(alignment: .firstTextBaseline, spacing: 7) {
            Text("\(numero)")
                .font(.system(size: 9.5, weight: .bold))
                .foregroundStyle(.white)
                .frame(width: 16, height: 16)
                .background(Circle().fill(color.opacity(0.85)))
                .alignmentGuide(.firstTextBaseline) { $0[VerticalAlignment.center] + 4 }
            VStack(alignment: .leading, spacing: 2) {
                Text(texto).font(.system(size: 11.5)).fixedSize(horizontal: false, vertical: true)
                Text(ejemplo).font(.system(size: 10.5)).foregroundStyle(.secondary)
                    .fixedSize(horizontal: false, vertical: true)
            }
        }
    }
}

struct Accion: View {
    let icono: String
    let titulo: String
    let detalle: String
    let color: Color
    var principal = false
    var enInDesign = false
    let hacer: () -> Void
    @State private var encima = false
    @Environment(\.isEnabled) private var activa

    var body: some View {
        Button(action: hacer) {
            HStack(spacing: 10) {
                Image(systemName: icono)
                    .font(.system(size: 14, weight: .semibold))
                    .frame(width: 32, height: 32)
                    .background(RoundedRectangle(cornerRadius: 8).fill(principal ? AnyShapeStyle(color.gradient) : AnyShapeStyle(color.opacity(0.13))))
                    .foregroundStyle(principal ? Color.white : color)
                VStack(alignment: .leading, spacing: 1) {
                    Text(titulo).font(.system(size: 13, weight: .semibold))
                    Text(detalle).font(.system(size: 10.5)).foregroundStyle(.secondary).lineLimit(3)
                        .fixedSize(horizontal: false, vertical: true)
                }
                Spacer(minLength: 2)
                if enInDesign {
                    Image(systemName: "arrow.up.forward.app").font(.system(size: 11)).foregroundStyle(.tertiary)
                        .help("Se abre en una ventana de InDesign")
                }
            }
            .padding(6)
            .background(RoundedRectangle(cornerRadius: 10).fill(encima && activa ? color.opacity(0.09) : Color.clear))
            .contentShape(Rectangle())
        }
        .buttonStyle(.plain)
        .opacity(activa ? 1 : 0.45)
        .onHover { encima = $0 }
        .animation(.easeOut(duration: 0.12), value: encima)
    }
}

// MARK: - Consola

struct Consola: View {
    @ObservedObject var taller: Taller

    var body: some View {
        VStack(spacing: 0) {
            HStack(spacing: 10) {
                if let e = taller.ejecucionVista {
                    icono(e)
                    Text(e.titulo).font(.system(size: 12, weight: .semibold)).lineLimit(1).truncationMode(.middle)
                    Text(e.fin == nil ? duracion(taller.segundos(e)) : cuando(e.inicio) + " · " + duracion(taller.segundos(e)))
                        .font(.system(size: 11)).foregroundStyle(.secondary).monospacedDigit()
                } else {
                    Image(systemName: "terminal").foregroundStyle(.secondary)
                    Text("Actividad").font(.system(size: 12, weight: .semibold))
                }
                Spacer()
                if taller.ejecuciones.count > 1 {
                    Menu {
                        ForEach(taller.ejecuciones.reversed()) { e in
                            Button("\(formatoHora.string(from: e.inicio))  \(e.titulo)") { taller.vista = e.id }
                        }
                    } label: { Label("Historial", systemImage: "clock.arrow.circlepath") }
                    .menuStyle(.borderlessButton)
                    .fixedSize()
                }
                if let e = taller.ejecucionVista, !e.texto.isEmpty {
                    Button {
                        NSPasteboard.general.clearContents()
                        NSPasteboard.general.setString(e.texto, forType: .string)
                    } label: { Image(systemName: "doc.on.doc") }
                    .buttonStyle(.borderless)
                    .help("Copiar la salida")
                }
                if taller.enCurso != nil {
                    Button(role: .destructive) { taller.detener() } label: { Label("Detener", systemImage: "stop.fill") }
                        .controlSize(.small)
                        .tint(.red)
                }
            }
            .padding(.horizontal, 14)
            .frame(height: 36)
            Divider()
            if let e = taller.ejecucionVista {
                ScrollViewReader { proxy in
                    ScrollView {
                        VStack(alignment: .leading, spacing: 1) {
                            ForEach(Array(e.texto.components(separatedBy: "\n").enumerated()), id: \.offset) { _, linea in
                                Text(linea.isEmpty ? " " : linea)
                                    .font(.system(size: 11.5, design: .monospaced))
                                    .foregroundStyle(color(linea))
                                    .frame(maxWidth: .infinity, alignment: .leading)
                            }
                            Color.clear.frame(height: 1).id("fin")
                        }
                        .textSelection(.enabled)
                        .padding(12)
                    }
                    .onChange(of: e.texto.count) { proxy.scrollTo("fin", anchor: .bottom) }
                    .onChange(of: e.id) { proxy.scrollTo("fin", anchor: .bottom) }
                }
            } else {
                VStack(spacing: 6) {
                    Image(systemName: "text.alignleft").font(.system(size: 22)).foregroundStyle(.tertiary)
                    Text("Aquí verás lo que va haciendo cada paso").font(.system(size: 12)).foregroundStyle(.secondary)
                }
                .frame(maxWidth: .infinity, maxHeight: .infinity)
            }
        }
        .background(Color(nsColor: .textBackgroundColor))
    }

    @ViewBuilder func icono(_ e: Ejecucion) -> some View {
        if e.fin == nil {
            ProgressView().controlSize(.small)
        } else {
            Image(systemName: e.ok == true ? "checkmark.circle.fill" : "xmark.octagon.fill")
                .foregroundStyle(e.ok == true ? (e.seccion?.color ?? .green) : .red)
        }
    }

    func color(_ linea: String) -> Color {
        if linea.contains("Traceback") || linea.hasPrefix("Error") || linea.contains("ERROR") || linea.hasPrefix("— Detenido") { return .red }
        if linea.contains("⚠") { return .orange }
        return .primary
    }
}

// MARK: - Hojas de publicación

struct HojaNuevaPublicacion: View {
    @ObservedObject var taller: Taller
    @State var nueva: NuevaPublicacion
    @Environment(\.dismiss) private var cerrar

    var body: some View {
        VStack(alignment: .leading, spacing: 14) {
            Text("Nueva publicación").font(.title3.bold())
            Text("Se saca la maqueta y la configuración de estilos de:").font(.callout).foregroundStyle(.secondary)
            Label(nueva.maquetado.lastPathComponent, systemImage: "doc").font(.callout)
            TextField("Nombre de la publicación", text: $nueva.nombre).textFieldStyle(.roundedBorder)
            Text("Después revisa las líneas con ⚠ de su .toml.").font(.caption).foregroundStyle(.secondary)
            HStack {
                Spacer()
                Button("Cancelar", role: .cancel) { cerrar() }.keyboardShortcut(.cancelAction)
                Button("Crear") { taller.crearPublicacion(nueva); cerrar() }
                    .keyboardShortcut(.defaultAction)
                    .disabled(nueva.nombre.trimmingCharacters(in: .whitespaces).isEmpty)
            }
        }
        .padding(22)
        .frame(width: 440)
    }
}

struct HojaActualizar: View {
    @ObservedObject var taller: Taller
    @State var elegida: Publicacion
    @Environment(\.dismiss) private var cerrar

    var body: some View {
        let d = taller.datos(elegida)
        VStack(alignment: .leading, spacing: 14) {
            Text("Actualizar publicación").font(.title3.bold())
            Text("Rehace la maqueta desde un número más reciente. Antes de guardar verás qué cambia; la configuración no cambia.")
                .font(.callout).foregroundStyle(.secondary).fixedSize(horizontal: false, vertical: true)
            Picker("Publicación:", selection: $elegida) {
                ForEach(taller.publicaciones) { p in Text(p.nombre).tag(p) }
            }
            Grid(alignment: .leading, verticalSpacing: 6) {
                GridRow {
                    Text("Maqueta actual").foregroundStyle(.secondary)
                    Text(d.maqueta?.path ?? "(no tiene)").lineLimit(2).truncationMode(.middle).textSelection(.enabled)
                }
                GridRow {
                    Text("Último maquetado").foregroundStyle(.secondary)
                    Text(d.maquetado.isEmpty ? "(no consta)" : d.maquetado).lineLimit(2).truncationMode(.middle).textSelection(.enabled)
                }
            }
            .font(.system(size: 11.5))
            HStack {
                Spacer()
                Button("Cancelar", role: .cancel) { cerrar() }.keyboardShortcut(.cancelAction)
                Button("Elegir el InDesign nuevo…") {
                    cerrar()
                    let p = elegida
                    DispatchQueue.main.async { taller.prepararActualizacion(p) }
                }
                .keyboardShortcut(.defaultAction)
                .disabled(d.maqueta == nil)
            }
        }
        .padding(22)
        .frame(width: 560)
    }
}

struct HojaImportar: View {
    @ObservedObject var taller: Taller
    let importacion: Importacion
    @Environment(\.dismiss) private var cerrar

    var body: some View {
        let color = Seccion.galerada.color
        let maqueta = taller.publicacionActual.flatMap { taller.datos($0).maqueta }
        VStack(alignment: .leading, spacing: 16) {
            HStack(spacing: 12) {
                ZStack {
                    RoundedRectangle(cornerRadius: 10).fill(color.gradient)
                    Image(systemName: "doc.richtext").font(.system(size: 18, weight: .semibold)).foregroundStyle(.white)
                }
                .frame(width: 40, height: 40)
                VStack(alignment: .leading, spacing: 2) {
                    Text("Importar «\(importacion.nombre)»").font(.title3.bold())
                    Text("Se crea «\(importacion.nombre).indd» con la maqueta de la publicación")
                        .font(.callout).foregroundStyle(.secondary)
                }
            }

            VStack(alignment: .leading, spacing: 6) {
                Rotulo(importacion.words.count > 1 ? "Word (\(importacion.words.count))" : "Word")
                ForEach(importacion.words, id: \.self) { w in
                    Label(w.lastPathComponent, systemImage: "doc.text").font(.system(size: 12)).lineLimit(1).truncationMode(.middle)
                }
            }

            VStack(alignment: .leading, spacing: 8) {
                Rotulo("Publicación")
                Picker("", selection: $taller.publicacion) {
                    ForEach(taller.publicaciones) { p in Text(p.nombre).tag(p.ruta) }
                }
                .labelsHidden()
                .frame(maxWidth: 320)
                Label(maqueta.map { "Maqueta: " + $0.lastPathComponent } ?? "Esta publicación no tiene maqueta",
                      systemImage: maqueta == nil ? "exclamationmark.triangle.fill" : "rectangle.split.2x1")
                    .font(.system(size: 11.5))
                    .foregroundStyle(maqueta == nil ? Color.orange : Color.secondary)
            }
            .padding(12)
            .frame(maxWidth: .infinity, alignment: .leading)
            .background(RoundedRectangle(cornerRadius: 10).fill(color.opacity(0.08)))
            .overlay(RoundedRectangle(cornerRadius: 10).strokeBorder(color.opacity(0.35)))

            HStack {
                Spacer()
                Button("Cancelar", role: .cancel) { cerrar() }.keyboardShortcut(.cancelAction)
                Button("Importar con «\(taller.publicacionActual?.nombre ?? "")»") {
                    taller.confirmarImportacion(importacion)
                    cerrar()
                }
                .keyboardShortcut(.defaultAction)
                .disabled(taller.publicacionActual == nil)
            }
        }
        .padding(22)
        .frame(width: 520)
    }
}

struct HojaInforme: View {
    @ObservedObject var taller: Taller
    let informe: InformeActualizacion
    @Environment(\.dismiss) private var cerrar

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("Actualizar «\(informe.publicacion.nombre)»: ¿guardar la maqueta nueva?").font(.title3.bold())
            Text(informe.avisos > 0 ? "Revisa los avisos (⚠) antes de guardar:" : "Esto es lo que cambia:")
                .foregroundStyle(informe.avisos > 0 ? Color.orange : Color.secondary)
            ScrollView {
                Text(informe.informe).font(.system(size: 11.5, design: .monospaced)).textSelection(.enabled)
                    .frame(maxWidth: .infinity, alignment: .leading).padding(10)
            }
            .background(RoundedRectangle(cornerRadius: 8).fill(Color(nsColor: .textBackgroundColor)))
            HStack {
                Spacer()
                Button("Descartar", role: .destructive) { taller.cerrarActualizacion(informe, guardar: false); cerrar() }
                Button("Guardar") { taller.cerrarActualizacion(informe, guardar: true); cerrar() }.keyboardShortcut(.defaultAction)
            }
        }
        .padding(22)
        .frame(width: 760, height: 520)
        .interactiveDismissDisabled()
    }
}

// MARK: - App

final class Delegado: NSObject, NSApplicationDelegate {
    // Si arranca en segundo plano, SwiftUI no crea la ventana hasta que la app se activa
    func applicationDidFinishLaunching(_ notification: Notification) { NSApp.activate(ignoringOtherApps: true) }

    func applicationShouldTerminateAfterLastWindowClosed(_ sender: NSApplication) -> Bool { true }
}

@main
struct CrearPublicacionApp: App {
    @NSApplicationDelegateAdaptor(Delegado.self) private var delegado
    @StateObject private var taller = Taller()

    var body: some Scene {
        Window("Crear Publicación", id: "principal") {
            Ventana(taller: taller)
                .frame(minWidth: 1100, minHeight: 700)
        }
        .defaultSize(width: 1240, height: 880)
        .commands {
            CommandGroup(replacing: .newItem) {
                Button("Importar Word…") { taller.elegirWord() }.keyboardShortcut("i")
                Button("Abrir documento…") { taller.abrirDocumento() }.keyboardShortcut("o")
            }
        }
    }
}
