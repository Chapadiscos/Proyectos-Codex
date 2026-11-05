// Gráficos Excel BdE: maqueta paso a paso el Excel que entrega el autor.
// Ventana general (publicación, pasos, versiones y actividad) y una ventana flotante con el gráfico
// tal como lo dibuja Excel en la versión elegida. El trabajo lo hace motor/maquetar_excel.py sobre una
// copia, con una versión por paso; la app lanza los pasos, va adelante y atrás y habla con Excel.
import AppKit
import SwiftUI
import UniformTypeIdentifiers

/// Carpeta del motor: junto a la app, o la que se diga con
/// `defaults write es.estudioencuadre.graficos-excel motor "<ruta>"`.
let motor: URL = {
    if let ruta = UserDefaults.standard.string(forKey: "motor") { return URL(fileURLWithPath: ruta) }
    return Bundle.main.bundleURL.deletingLastPathComponent().appendingPathComponent("motor")
}()
let idExcel = "com.microsoft.Excel"

/// ¿Está activado el Organizador visual (Stage Manager)? Entonces Excel y la app van en grupos distintos
/// y no se ven a la vez hasta que se juntan.
var organizadorVisual: Bool {
    (CFPreferencesCopyAppValue("GloballyEnabled" as CFString, "com.apple.WindowManager" as CFString) as? Bool) ?? false
}

// MARK: - Modelo

struct Paso: Decodable, Identifiable {
    let n: Int
    let titulo: String
    let archivo: String
    let detalle: [String]
    var id: Int { n }
}

struct Publicacion: Codable, Identifiable, Hashable {
    var id: String
    var nombre: String
    var color: String
    var tema: String?
}

/// Una pastilla del muestrario del archivo de retículas (solo de consulta)
struct Muestra: Decodable, Hashable {
    let nombre: String
    let color: String
}

struct ColorPaleta: Decodable, Hashable {
    let clave: String
    let hex: String
}

/// Una paleta de colores (tema) de las que Excel tiene instaladas
/// Se identifica por el archivo (sin .xml); el nombre de dentro puede repetirse con otros colores.
struct Paleta: Decodable, Identifiable, Hashable {
    let id: String
    let nombre: String
    let archivo: String
    let colores: [ColorPaleta]
}

/// Nombre de cada color de la paleta, como en Excel
let nombresColorPaleta = ["dk1": "Texto oscuro 1", "lt1": "Fondo claro 1", "dk2": "Texto oscuro 2", "lt2": "Fondo claro 2",
                          "accent1": "Énfasis 1", "accent2": "Énfasis 2", "accent3": "Énfasis 3",
                          "accent4": "Énfasis 4", "accent5": "Énfasis 5", "accent6": "Énfasis 6"]

struct Respuesta: Decodable {
    let ok: Bool
    let error: String?
    let trabajo: String?
    let idioma: String?
    let motivo_idioma: String?
    let actual: Int?
    let pasos: [Paso]?
    let publicaciones: [Publicacion]?
    let muestrario: [Muestra]?
    let publicacion: String?
    let reticula_pt: [Double]?
    let paletas: [Paleta]?
    let carpeta: String?
    let comparacion: [String]?
    let comparado: String?
    let original: String?
    let terminado: String?
    let borrados: [String]?
}

/// Los pasos de maquetación que la app sabe hacer, en orden
struct PasoMaquetacion: Identifiable {
    let id: Int
    let titulo: String
    let detalle: String
    let icono: String
    let orden: String
}

/// Herramienta puntual (no es un paso de todos los gráficos): se aplica cuando hace falta, sobre la versión elegida
let herramientaSinEje = PasoMaquetacion(id: 0, titulo: "Sin eje vertical, valor sobre cada barra",
    detalle: "Para gráficos de barras verticales que lo necesiten: quita el eje vertical (y sus líneas de división), pone el valor encima de cada barra (6 pt, con los decimales de los datos) apartando las que se montan, y alarga el trazado hasta el principio de la columna. Después de «Tamaño y colocación»; mejor al final.",
    icono: "chart.bar.doc.horizontal", orden: "sin_eje_vertical")

let pasosMaquetacion = [
    PasoMaquetacion(id: 1, titulo: "Retícula, pastilla y textos",
                    detalle: "Retícula y pastilla del archivo de retículas, en A1 y al fondo, con el color de la publicación; todo en Roboto: Gráfico NN y título con el marco de la plantilla; paneles, ejes, leyendas (en minúscula salvo siglas), unidades, interior y fuentes con su cuerpo; fechas, números de los ejes, (Escala dcha.), trimestres y dirección del eje horizontal (guía, págs. 10 y 11)",
                    icono: "square.grid.3x3.topleft.filled", orden: "paso1"),
    PasoMaquetacion(id: 2, titulo: "Tamaño y colocación",
                    detalle: "Paneles uno debajo de otro como en Illus: trazado en la columna 1 y leyenda en la 2; 9 filas hasta las categorías (trazado, mínimo 7); títulos de panel y FUENTES con las separaciones de Illus",
                    icono: "rectangle.split.1x2", orden: "paso2"),
    PasoMaquetacion(id: 3, titulo: "Ejes",
                    detalle: "Ejes 0,5 pt matiz 5 y divisiones 0,3 pt matiz 4, sin relieve y unión angular; eje en cero, marcas de graduación, etiquetas en Bajo a distancia 100 y límites fijos en un tramo (guía, pág. 15)",
                    icono: "chart.xyaxis.line", orden: "paso3"),
    PasoMaquetacion(id: 4, titulo: "Líneas interiores",
                    detalle: "Línea base si las unidades indican un dato de referencia (Base 100 = …; 100 o 50), gris como los ejes y oculta en la leyenda (guía, pág. 13); líneas divisorias negras de 1 pt (pág. 14); flechas como en el TERMINADO: negras de 0,5 pt con punta abierta; líneas guía de las etiquetas, si las hay: blanco matiz 5, 0,5 pt (pág. 16)",
                    icono: "chart.line.flattrend.xyaxis", orden: "paso4"),
    PasoMaquetacion(id: 5, titulo: "Tramas, colores y líneas",
                    detalle: "Tramas y estilos de línea de la paleta de la publicación (Excel. Guía líneas y tramas colores 2026), en el orden de la guía (pág. 7): primero las líneas, luego barras y áreas desde el eje y al final los marcadores; líneas de 2,25 pt, tramas sin borde; aviso a partir de la 8.ª serie",
                    icono: "paintpalette", orden: "paso5"),
]

struct Ejecucion: Identifiable {
    let id = UUID()
    let titulo: String
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

// MARK: - Utilidades

func cadenaAS(_ s: String) -> String {
    "\"" + s.replacingOccurrences(of: "\\", with: "\\\\").replacingOccurrences(of: "\"", with: "\\\"") + "\""
}

/// Ejecuta un programa y lo corta si pasa del tiempo (Excel con un diálogo abierto).
func ejecutar(_ programa: String, _ argumentos: [String], espera: TimeInterval, carpeta: URL? = nil) async -> (ok: Bool, texto: String) {
    await withCheckedContinuation { continuacion in
        DispatchQueue.global().async {
            let p = Process()
            p.executableURL = URL(fileURLWithPath: programa)
            p.arguments = argumentos
            if let carpeta { p.currentDirectoryURL = carpeta }
            let salida = Pipe(), errores = Pipe()
            p.standardOutput = salida
            p.standardError = errores
            do { try p.run() } catch {
                continuacion.resume(returning: (false, error.localizedDescription))
                return
            }
            var cortado = false
            let limite = DispatchWorkItem { if p.isRunning { cortado = true; p.terminate() } }
            DispatchQueue.global().asyncAfter(deadline: .now() + espera, execute: limite)
            let datos = salida.fileHandleForReading.readDataToEndOfFile()
            let error = errores.fileHandleForReading.readDataToEndOfFile()
            p.waitUntilExit()
            limite.cancel()
            if cortado { continuacion.resume(returning: (false, "no responde en \(Int(espera)) s")); return }
            let ok = p.terminationStatus == 0
            let texto = String(decoding: ok ? datos : (error.isEmpty ? datos : error), as: UTF8.self)
            continuacion.resume(returning: (ok, texto.trimmingCharacters(in: .whitespacesAndNewlines)))
        }
    }
}

/// Mientras se abre un libro como desde el Finder: si Excel pregunta por los vínculos externos, se pulsa «No
/// actualizar» (regla: los vínculos externos no se actualizan nunca). Con Accesibilidad; hasta que se cancela.
func noActualizarVinculos() async {
    let titulos: Set<String> = ["No actualizar", "Don't Update", "Don’t Update"]
    while !Task.isCancelled {
        if let excel = NSRunningApplication.runningApplications(withBundleIdentifier: idExcel).first {
            let app = AXUIElementCreateApplication(excel.processIdentifier)
            var valor: CFTypeRef?
            if AXUIElementCopyAttributeValue(app, kAXWindowsAttribute as CFString, &valor) == .success,
               let ventanas = valor as? [AXUIElement] {
                for ventana in ventanas {
                    if let boton = buscarBoton(en: ventana, titulos: titulos, nivel: 0) {
                        AXUIElementPerformAction(boton, kAXPressAction as CFString)
                    }
                }
            }
        }
        try? await Task.sleep(nanoseconds: 150_000_000)
    }
}

func buscarBoton(en elemento: AXUIElement, titulos: Set<String>, nivel: Int) -> AXUIElement? {
    if nivel > 4 { return nil }
    var rol: CFTypeRef?, titulo: CFTypeRef?, hijos: CFTypeRef?
    AXUIElementCopyAttributeValue(elemento, kAXRoleAttribute as CFString, &rol)
    if (rol as? String) == kAXButtonRole as String {
        AXUIElementCopyAttributeValue(elemento, kAXTitleAttribute as CFString, &titulo)
        if let t = titulo as? String, titulos.contains(t) { return elemento }
        return nil
    }
    guard AXUIElementCopyAttributeValue(elemento, kAXChildrenAttribute as CFString, &hijos) == .success,
          let lista = hijos as? [AXUIElement] else { return nil }
    for hijo in lista {
        if let b = buscarBoton(en: hijo, titulos: titulos, nivel: nivel + 1) { return b }
    }
    return nil
}

/// Cola propia para los AppleScript: NSAppleScript no admite dos a la vez.
let colaAppleScript = DispatchQueue(label: "es.estudioencuadre.graficos-excel.applescript")

/// Ejecuta un AppleScript dentro de la app (NSAppleScript), no con `osascript` aparte: lanzar un programa en
/// cada orden a Excel costaba segundos. Los argumentos llegan como `argv`, igual que con `osascript`.
func osascript(_ guion: String, _ argumentos: [String] = [], espera: TimeInterval) async -> (ok: Bool, texto: String) {
    let lista = "{" + argumentos.map(cadenaAS).joined(separator: ", ") + "}"
    let fuente = guion
        .replacingOccurrences(of: "on run argv", with: "on run\nset argv to \(lista)\nwith timeout of \(Int(espera)) seconds")
        .replacingOccurrences(of: "end run", with: "end timeout\nend run")
    return await withCheckedContinuation { continuacion in
        colaAppleScript.async {
            var error: NSDictionary?
            guard let script = NSAppleScript(source: fuente) else {
                continuacion.resume(returning: (false, "AppleScript no válido"))
                return
            }
            let r = script.executeAndReturnError(&error)
            if let error {
                let mensaje = error[NSAppleScript.errorMessage] as? String ?? "\(error)"
                continuacion.resume(returning: (false, mensaje))
                return
            }
            let texto = r.stringValue ?? (r.descriptorType == typeSInt32 ? String(r.int32Value) : "")
            continuacion.resume(returning: (true, texto))
        }
    }
}

func colorHex(_ hex: String) -> Color {
    let v = Int(hex.trimmingCharacters(in: CharacterSet(charactersIn: "#")), radix: 16) ?? 0
    return Color(red: Double((v >> 16) & 255) / 255, green: Double((v >> 8) & 255) / 255, blue: Double(v & 255) / 255)
}

func hexDe(_ color: Color) -> String {
    let c = NSColor(color).usingColorSpace(.sRGB) ?? .white
    return String(format: "%02X%02X%02X", Int(round(c.redComponent * 255)), Int(round(c.greenComponent * 255)), Int(round(c.blueComponent * 255)))
}

let formatoHora: DateFormatter = {
    let f = DateFormatter()
    f.dateFormat = "HH:mm:ss"
    return f
}()

func duracion(_ s: Int) -> String { s < 60 ? "\(s) s" : "\(s / 60) min \(s % 60) s" }

let colorApp = Color(red: 0.13, green: 0.55, blue: 0.36)
let colorVersiones = Color(red: 0.16, green: 0.47, blue: 0.96)

// MARK: - Taller

@MainActor
final class Taller: ObservableObject {
    @Published var trabajo: URL?
    @Published var idioma = "es"
    @Published var actual = 0
    @Published var pasos: [Paso] = []
    @Published var publicaciones: [Publicacion] = []
    @Published var muestrario: [Muestra] = []
    @Published var publicacion = UserDefaults.standard.string(forKey: "publicacion") ?? "documentos" {
        didSet { UserDefaults.standard.set(publicacion, forKey: "publicacion") }
    }
    /// Ancho y alto de la retícula (pt): Excel se encuadra para que quepa entera
    var reticula = (ancho: 471.4, alto: 702.3)
    /// Zoom de Excel ya calculado para el sitio que ocupa (se calcula una vez, no en cada versión)
    private var zoomExcel: (sitio: [Int], zoom: Int)?
    @Published var ejecuciones: [Ejecucion] = []
    @Published var vista: UUID?
    @Published var enCurso: UUID?
    @Published var excel = false
    @Published var aviso: Aviso?
    @Published var pregunta: Pregunta?
    @Published var editando: Publicacion?
    @Published var paletas: [Paleta] = []
    @Published var carpetaPaletas: String?
    @Published var errorPaletas: String?
    @Published var ahora = Date()
    /// Resultado de «Comparar con el original» (se borra al cambiar de versión: ya no vale)
    @Published var comparacion: [String] = []

    var motorEncontrado: Bool { FileManager.default.fileExists(atPath: motor.appendingPathComponent("maquetar_excel.py").path) }
    var publicacionActual: Publicacion? { publicaciones.first { $0.id == publicacion } }
    var carpetaPasos: URL? { trabajo.map { URL(fileURLWithPath: $0.deletingPathExtension().path + " (pasos)") } }
    var ejecucionVista: Ejecucion? { ejecuciones.first { $0.id == vista } ?? ejecuciones.last }
    var ejecucionEnCurso: Ejecucion? { ejecuciones.first { $0.id == enCurso } }
    var pasoActual: Paso? { pasos.indices.contains(actual) ? pasos[actual] : nil }

    init() {
        // «--abrir <xlsx>»: abre ese trabajo al arrancar (para probar la app sin el diálogo)
        if let i = CommandLine.arguments.firstIndex(of: "--abrir"), i + 1 < CommandLine.arguments.count {
            let url = URL(fileURLWithPath: CommandLine.arguments[i + 1])
            DispatchQueue.main.asyncAfter(deadline: .now() + 1.5) { [weak self] in self?.abrir(url) }
        }
        // Al volver de Excel a la app, las líneas guía activadas a mano se ponen con el formato de la guía
        NotificationCenter.default.addObserver(forName: NSApplication.didBecomeActiveNotification, object: nil, queue: .main) { _ in
            Task { @MainActor [weak self] in self?.revisarLineasGuia() }
        }
        Timer.scheduledTimer(withTimeInterval: 1, repeats: true) { _ in
            Task { @MainActor [weak self] in
                guard let self else { return }
                self.excel = !NSRunningApplication.runningApplications(withBundleIdentifier: idExcel).isEmpty
                // El contador solo corre con la ventana a la vista: cada redibujo con la ventana escondida (el
                // Organizador visual) dejaba la app esperando a que macOS lo mostrara, y parada mientras tanto
                if self.enCurso != nil, NSApp.windows.contains(where: { $0.isVisible && $0.occlusionState.contains(.visible) }) {
                    self.ahora = Date()
                }
            }
        }
        Task {
            _ = await llamarMotor(["publicaciones"], registro: nil)
            await cargarPaletas()
        }
    }

    /// Las paletas, de la copia que guarda el motor; con `actualizar`, leídas otra vez de Excel (por si se ha
    /// instalado alguna). Esa carpeta es de Excel: macOS puede pedir permiso a la app para entrar.
    func cargarPaletas(actualizar: Bool = false) async {
        let script = motor.appendingPathComponent("maquetar_excel.py").path
        let r = await ejecutar("/usr/bin/python3", ["-I", script, "paletas"] + (actualizar ? ["actualizar"] : []), espera: 60)
        guard let datos = r.texto.data(using: .utf8), let respuesta = try? JSONDecoder().decode(Respuesta.self, from: datos),
              respuesta.ok else {
            errorPaletas = r.texto.isEmpty ? "El motor no ha respondido" : r.texto
            return
        }
        paletas = respuesta.paletas ?? []
        carpetaPaletas = respuesta.carpeta
        errorPaletas = paletas.isEmpty ? "No hay paletas en la carpeta de Excel" : nil
    }

    func segundos(_ e: Ejecucion) -> Int { Int((e.fin ?? ahora).timeIntervalSince(e.inicio)) }

    // MARK: Actividad

    private func empezarEjecucion(_ titulo: String) -> UUID {
        let e = Ejecucion(titulo: titulo)
        ejecuciones.append(e)
        if ejecuciones.count > 40 { ejecuciones.removeFirst() }
        vista = e.id
        enCurso = e.id
        return e.id
    }

    func anotar(_ id: UUID?, _ linea: String) {
        guard let id, let i = ejecuciones.firstIndex(where: { $0.id == id }) else { return }
        ejecuciones[i].texto += (ejecuciones[i].texto.isEmpty ? "" : "\n") + linea
    }

    private func terminarEjecucion(_ id: UUID, ok: Bool) {
        if let i = ejecuciones.firstIndex(where: { $0.id == id }) {
            ejecuciones[i].fin = Date()
            ejecuciones[i].ok = ok
        }
        if enCurso == id { enCurso = nil }
    }

    /// Lanza una tarea con su entrada en la actividad; no deja empezar otra mientras dure.
    private func tarea(_ titulo: String, _ trabajo: @escaping (UUID) async -> Bool) {
        guard enCurso == nil else { return }
        let id = empezarEjecucion(titulo)
        // Sin siesta (App Nap) mientras dure: con el Organizador visual la app queda fuera de la vista mientras
        // Excel está delante, y macOS la frenaba (cada cambio esperaba a que se volviera a activar algo)
        let actividad = ProcessInfo.processInfo.beginActivity(options: [.userInitiated, .latencyCritical], reason: titulo)
        Task {
            let ok = await trabajo(id)
            terminarEjecucion(id, ok: ok)
            ProcessInfo.processInfo.endActivity(actividad)
        }
    }

    // MARK: Motor

    private func llamarMotor(_ argumentos: [String], registro: UUID?) async -> Respuesta? {
        let script = motor.appendingPathComponent("maquetar_excel.py").path
        let r = await ejecutar("/usr/bin/python3", ["-I", script] + argumentos, espera: 120)
        guard let datos = r.texto.data(using: .utf8),
              let respuesta = try? JSONDecoder().decode(Respuesta.self, from: datos) else {
            anotar(registro, "Error del motor: \(r.texto)")
            return nil
        }
        if !respuesta.ok { anotar(registro, "Error: \(respuesta.error ?? "sin detalle")") }
        if let p = respuesta.publicaciones { publicaciones = p }
        if let m = respuesta.muestrario { muestrario = m }
        if publicacionActual == nil, let primera = publicaciones.first { publicacion = primera.id }
        return respuesta.ok ? respuesta : nil
    }

    private func aplicar(_ r: Respuesta) {
        if let t = r.trabajo { trabajo = URL(fileURLWithPath: t) }
        idioma = r.idioma ?? idioma
        actual = r.actual ?? actual
        pasos = r.pasos ?? pasos
        comparacion = []
        if let m = r.reticula_pt, m.count == 2 { reticula = (m[0], m[1]) }
    }

    // MARK: Archivo

    func elegir() {
        let panel = NSOpenPanel()
        panel.allowedContentTypes = [UTType(filenameExtension: "xlsx")!]
        panel.message = "El Excel del autor, o su copia «… maquetado.xlsx» para seguir"
        if let ultima = UserDefaults.standard.string(forKey: "carpeta") { panel.directoryURL = URL(fileURLWithPath: ultima) }
        guard panel.runModal() == .OK, let url = panel.url else { return }
        abrir(url)
    }

    /// Con el original empieza una maquetación nueva; con la copia «… maquetado.xlsx», o con un original
    /// que ya tiene copia, sigue donde se quedó.
    func abrir(_ url: URL) {
        UserDefaults.standard.set(url.deletingLastPathComponent().path, forKey: "carpeta")
        var base = url.deletingPathExtension().lastPathComponent
        if base.hasSuffix(" maquetado (2)") { base = String(base.dropLast(4)) }   // la segunda copia: la primera
        let copia = base.hasSuffix(" maquetado") ? url.deletingLastPathComponent().appendingPathComponent(base + ".xlsx")
            : url.deletingLastPathComponent().appendingPathComponent(base + " maquetado.xlsx")
        let seguir = FileManager.default.fileExists(atPath: copia.deletingPathExtension().path + " (pasos)")
        let anterior = trabajo
        tarea(seguir ? "Seguir con \(copia.lastPathComponent)" : "Empezar \(url.lastPathComponent)") { id in
            // La ventana de Excel del trabajo anterior (o de este, si ya estaba abierto) se cierra: se abre de nuevo
            for t in Set([anterior, copia].compactMap { $0 }) { await self.cerrarEnExcel(t) }
            guard let r = await self.llamarMotor(seguir ? ["estado", copia.path] : ["empezar", url.path], registro: id) else { return false }
            self.aplicar(r)
            self.anotar(id, seguir ? "Sigue la maquetación en el paso \(self.actual)." : "Copia exacta creada: \(copia.lastPathComponent)")
            self.anotar(id, "Idioma: \(self.idioma == "en" ? "inglés" : "castellano") (\(r.motivo_idioma ?? "por el nombre del archivo"))")
            return await self.mostrar(id)
        }
    }

    // MARK: Pasos y versiones

    func hacer(_ paso: PasoMaquetacion) {
        guard let trabajo else { return }
        let lanzar = {
            self.tarea(paso.id > 0 ? "\(paso.id). \(paso.titulo)" : paso.titulo) { id in
                guard let r = await self.llamarMotor([paso.orden, trabajo.path, self.publicacion], registro: id) else { return false }
                self.aplicar(r)
                self.pasoActual?.detalle.forEach { self.anotar(id, "• " + $0) }
                return await self.mostrar(id)
            }
        }
        if actual + 1 < pasos.count {
            pregunta = Pregunta(titulo: "Hay versiones por delante",
                                texto: "Si haces «\(paso.titulo)» desde la versión \(actual), se descartan las posteriores.",
                                boton: "Hacerlo", hacer: lanzar)
        } else {
            lanzar()
        }
    }

    /// Ir a otra versión, como un deshacer: la copia de trabajo pasa a ser esa versión y Excel la recarga en la
    /// misma ventana. Lo hace la app sin el motor (lanzar Python a veces costaba segundos).
    func ir(_ n: Int) {
        guard let trabajo, let carpeta = carpetaPasos, pasos.indices.contains(n), n != actual else { return }
        tarea("Ir a la versión \(n)") { id in
            self.actual = n
            self.comparacion = []
            self.anotar(id, "Versión \(n): \(self.pasos[n].titulo)")
            do {
                let estadoURL = carpeta.appendingPathComponent("estado.json")
                guard var estado = try JSONSerialization.jsonObject(with: Data(contentsOf: estadoURL)) as? [String: Any] else {
                    throw CocoaError(.fileReadCorruptFile)
                }
                estado["actual"] = n
                try JSONSerialization.data(withJSONObject: estado, options: [.prettyPrinted]).write(to: estadoURL)
                // Se escriben los datos (no se copia el archivo): las versiones están en solo lectura y la copia no
                try Data(contentsOf: carpeta.appendingPathComponent(self.pasos[n].archivo)).write(to: trabajo)
            } catch {
                self.anotar(id, "Error al guardar la versión elegida: \(error.localizedDescription)")
                return false
            }
            return await self.mostrar(id)
        }
    }

    /// Volver a empezar desde el original del autor: se borran todas las versiones (se pregunta antes) y la
    /// copia de trabajo vuelve a ser la copia exacta.
    func reiniciar() {
        guard let trabajo, pasos.count > 1 else { return }
        pregunta = Pregunta(titulo: "¿Reiniciar desde el original?",
                            texto: "Se borran las versiones 1 a \(pasos.count - 1) y se vuelve a la copia exacta del Excel del autor. No se puede deshacer.",
                            boton: "Reiniciar") {
            self.tarea("Reiniciar desde el original") { id in
                guard let r = await self.llamarMotor(["reiniciar", trabajo.path], registro: id) else { return false }
                self.aplicar(r)
                self.anotar(id, "Versiones borradas; de nuevo la copia exacta del original")
                return await self.mostrar(id)
            }
        }
    }

    // MARK: Terminar

    /// Compara la copia de trabajo (lo guardado: la más reciente de las dos) con el Excel del autor: textos y
    /// cifras, no la colocación. Avisa de lo que falta y de lo que ha cambiado. No crea versión.
    func comparar() {
        guard let trabajo else { return }
        tarea("Comparar con el original") { id in
            guard let r = await self.llamarMotor(["comparar", trabajo.path], registro: id) else { return false }
            self.comparacion = r.comparacion ?? []
            if let c = r.comparado, let o = r.original {
                self.anotar(id, "«\(URL(fileURLWithPath: c).lastPathComponent)» (lo guardado) frente a «\(URL(fileURLWithPath: o).lastPathComponent)»")
            }
            self.comparacion.forEach { self.anotar(id, "• " + $0) }
            return true
        }
    }

    /// Nombre que tendrá el TERMINADO: el del original con «ORIGINAL» cambiado por «TERMINADO», o con
    /// « TERMINADO» al final (si ya existe, el motor le pone « (2)»…)
    var nombreTerminado: String {
        guard let trabajo else { return "" }
        var base = trabajo.deletingPathExtension().lastPathComponent
        if base.hasSuffix(" maquetado") { base = String(base.dropLast(" maquetado".count)) }
        if base.range(of: #"\bORIGINAL\b"#, options: .regularExpression) != nil {
            base = base.replacingOccurrences(of: #"\bORIGINAL\b"#, with: "TERMINADO", options: .regularExpression)
        } else {
            base += " TERMINADO"
        }
        return base + ".xlsx"
    }

    private static let guionGuardado = """
    on run argv
        if application "Microsoft Excel" is not running then return "sin libro"
        tell application "Microsoft Excel"
            repeat with i from 1 to (count workbooks)
                set n to full name of workbook i
                if n is item 1 of argv or n is item 2 of argv then
                    if saved of workbook i then return "guardado"
                    return "sin guardar"
                end if
            end repeat
        end tell
        return "sin libro"
    end run
    """

    /// Guarda el resultado como «… TERMINADO.xlsx» junto al original y borra lo generado (las dos copias de
    /// trabajo y la carpeta de pasos con todas las versiones). Antes: que no haya cambios sin guardar en Excel
    /// y confirmación.
    func terminar() {
        guard let trabajo, enCurso == nil else { return }
        Task {
            let estado = await osascript(Taller.guionGuardado, [trabajo.path, Taller.copiaB(trabajo).path], espera: 10)
            if estado.texto.contains("sin guardar") {
                self.aviso = Aviso(titulo: "Hay cambios sin guardar en Excel",
                                   texto: "Guarda el libro en Excel (⌘S) si quieres conservarlos, o deshazlos, y vuelve a pulsar «Guardar como TERMINADO».")
                return
            }
            self.pregunta = Pregunta(titulo: "¿Guardar como TERMINADO?",
                                     texto: "Se guarda «\(self.nombreTerminado)» junto al original (si ya existe, no se pisa: se añade « (2)»). Después se cierra en Excel y se borran la copia de trabajo, su copia « (2)» y la carpeta «(pasos)» con todas las versiones. El original del autor no se toca. No se puede deshacer.",
                                     boton: "Guardar y borrar") {
                self.tarea("Guardar como TERMINADO") { id in
                    await self.cerrarEnExcel(trabajo)
                    guard let r = await self.llamarMotor(["terminar", trabajo.path], registro: id),
                          let hecho = r.terminado else { return false }
                    let url = URL(fileURLWithPath: hecho)
                    self.anotar(id, "Guardado: \(url.lastPathComponent)")
                    (r.borrados ?? []).forEach { self.anotar(id, "Borrado: \($0)") }
                    self.trabajo = nil
                    self.pasos = []
                    self.actual = 0
                    self.comparacion = []
                    NSWorkspace.shared.activateFileViewerSelecting([url])
                    return true
                }
            }
        }
    }

    /// Tras cada cambio, la copia de trabajo recargada en Excel, a la derecha de la app y encuadrada en el gráfico.
    /// Las copias de trabajo son dos, «X maquetado.xlsx» y «X maquetado (2).xlsx», con la misma versión: al
    /// cambiar de versión, Excel abre la que no está abierta antes de cerrar la otra, y su ventana no desaparece
    /// (Excel no puede abrir dos veces el mismo archivo ni dos libros que se llamen igual).
    /// La posición y el tamaño de la ventana guardados en el libro (workbookView de xl/workbook.xml, en
    /// veinteavos de punto) pasan a ser `sitio` = {izquierda, arriba, derecha, abajo}.
    static func fijarVentana(_ archivo: URL, _ sitio: [Int]) async {
        guard sitio.count == 4 else { return }
        let lectura = await ejecutar("/usr/bin/unzip", ["-p", archivo.path, "xl/workbook.xml"], espera: 10)
        guard lectura.texto.contains("<workbookView") else { return }
        let valores = ["xWindow": sitio[0] * 20, "yWindow": sitio[1] * 20,
                       "windowWidth": (sitio[2] - sitio[0]) * 20, "windowHeight": (sitio[3] - sitio[1]) * 20]
        var xml = lectura.texto
        guard let vista = xml.range(of: #"<workbookView\b[^>]*>"#, options: .regularExpression) else { return }
        var etiqueta = String(xml[vista])
        for (nombre, valor) in valores {
            if let r = etiqueta.range(of: #"\b\#(nombre)="[^"]*""#, options: .regularExpression) {
                etiqueta.replaceSubrange(r, with: "\(nombre)=\"\(valor)\"")
            } else {
                etiqueta = etiqueta.replacingOccurrences(of: "<workbookView", with: "<workbookView \(nombre)=\"\(valor)\"")
            }
        }
        xml.replaceSubrange(vista, with: etiqueta)
        let carpeta = FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString)
        try? FileManager.default.createDirectory(at: carpeta.appendingPathComponent("xl"), withIntermediateDirectories: true)
        defer { try? FileManager.default.removeItem(at: carpeta) }
        guard (try? xml.write(to: carpeta.appendingPathComponent("xl/workbook.xml"), atomically: true, encoding: .utf8)) != nil else { return }
        _ = await ejecutar("/usr/bin/zip", ["-q", archivo.path, "xl/workbook.xml"], espera: 10, carpeta: carpeta)
    }

    static func copiaB(_ ruta: URL) -> URL {
        ruta.deletingLastPathComponent().appendingPathComponent(ruta.deletingPathExtension().lastPathComponent + " (2).xlsx")
    }

    private func mostrar(_ id: UUID) async -> Bool {
        await mostrarEnExcel(id, recargar: true)
    }

    /// Pone la app a la izquierda de la pantalla y devuelve el sitio de Excel, a la derecha, como
    /// {izquierda, arriba, derecha, abajo} en coordenadas de AppleScript (origen arriba a la izquierda).
    /// Excel empieza donde acaba de verdad la ventana de la app: con el Organizador visual, macOS la aparta a la
    /// derecha para dejar sitio a la tira, y con el sitio pedido Excel la tapaba.
    private func colocarVentanas() async -> [Int] {
        let ventana = NSApp.windows.first { $0.isVisible && $0.styleMask.contains(.titled) }
        guard let pantalla = ventana?.screen ?? NSScreen.main, let principal = NSScreen.screens.first else { return [] }
        let zona = pantalla.visibleFrame
        let anchoApp = min(max(980, zona.width * 0.42), zona.width - 640)
        let marco = NSRect(x: zona.minX, y: zona.minY, width: anchoApp, height: zona.height)
        // Solo si cambia el tamaño: el desplazamiento del Organizador visual se respeta (si no, se recolocaría siempre)
        if let ventana, abs(ventana.frame.width - marco.width) > 1 || abs(ventana.frame.height - marco.height) > 1 {
            ventana.setFrame(marco, display: true)
            try? await Task.sleep(nanoseconds: 300_000_000)
        }
        let izquierda = max(ventana?.frame.maxX ?? zona.minX + anchoApp, zona.minX + anchoApp)
        let alto = principal.frame.maxY
        return [Int(izquierda.rounded(.up)), Int(alto - zona.maxY), Int(zona.maxX), Int(alto - zona.minY)]
    }

    /// Excel enseña siempre la copia de trabajo, en una sola ventana: tras cada cambio (`recargar`) se cierra sin
    /// guardar y se vuelve a abrir en el mismo sitio, como un deshacer o rehacer. Sin actualizar vínculos, en la
    /// hoja «Gráfico», a la derecha de la app y con el zoom justo para ver la retícula entera desde A1. Siempre el
    /// mismo archivo: Excel (aislado) pide permiso por archivo, y con archivos nuevos en cada paso lo pedía cada vez
    /// con una ventana «Abrir» que el Organizador visual escondía. Sin `recargar` solo coloca y encuadra.
    private func mostrarEnExcel(_ id: UUID, recargar: Bool) async -> Bool {
        guard let paso = pasoActual, let ruta = trabajo else { return false }
        // La segunda copia, con la misma versión: es la que se abre si la primera está abierta
        if recargar { try? Data(contentsOf: ruta).write(to: Taller.copiaB(ruta)) }
        let sitio = await colocarVentanas()
        guard sitio.count == 4 else { return false }
        if !recargar { zoomExcel = nil }
        let zoom = zoomExcel.flatMap { $0.sitio == sitio ? $0.zoom : nil } ?? 0
        // Un 4 % de margen alrededor de la retícula
        let medidas = [Int(reticula.ancho * 1.04), Int(reticula.alto * 1.04)]
        // Excel abre cada libro donde dice el propio archivo: se escribe ahí el sitio, y la ventana nace colocada
        // (si no, asomaba un momento encima de la app antes de ir a su sitio)
        if recargar {
            for archivo in [ruta, Taller.copiaB(ruta)] { await Taller.fijarVentana(archivo, sitio) }
        }
        let guion = """
        -- Se abre como desde el Finder («open»): así macOS da a Excel permiso para ese archivo y no pregunta.
        -- Con «open workbook» Excel solo recibe la ruta y pide «Conceder acceso» por cada archivo nuevo.
        on abrirLibro(rutaLibro, comoFinder)
            if not comoFinder then
                tell application "Microsoft Excel" to return open workbook workbook file name rutaLibro update links do not update links
            end if
            do shell script "open -g -a 'Microsoft Excel' " & quoted form of rutaLibro
            set nombreLibro to do shell script "basename " & quoted form of rutaLibro
            tell application "Microsoft Excel"
                repeat 600 times
                    try
                        repeat with i from 1 to (count workbooks)
                            if full name of workbook i is rutaLibro or name of workbook i is nombreLibro then return workbook i
                        end repeat
                    end try
                    delay 0.1
                end repeat
                -- Si no llega (otro nombre de la ruta), como antes
                return open workbook workbook file name rutaLibro update links do not update links
            end tell
        end abrirLibro

        on run argv
            set ruta to item 1 of argv
            set sitio to {(item 2 of argv) as integer, (item 3 of argv) as integer, (item 4 of argv) as integer, (item 5 of argv) as integer}
            set anchoRet to (item 6 of argv) as integer
            set altoRet to (item 7 of argv) as integer
            set z to (item 8 of argv) as integer
            set recargar to (item 9 of argv) is "si"
            set arrancar to (item 10 of argv) is "si"
            set rutaB to item 11 of argv
            set organizador to (item 12 of argv) is "si"
            set comoFinder to (item 13 of argv) is "si"
            tell application "Microsoft Excel"
                -- Recién arrancado en segundo plano, Excel no enseña sus ventanas hasta que se le activa
                if arrancar then activate
                -- La copia que está abierta (una de las dos que se alternan)
                set viejo to missing value
                -- Por número: «repeat with … in every workbook» da error de parámetros
                repeat with i from 1 to (count workbooks)
                    set nombre to full name of workbook i
                    if nombre is ruta or nombre is rutaB then set viejo to workbook i
                end repeat
                if recargar then
                    -- Se abre la otra copia (ya con la versión elegida) y, colocada, se cierra la vieja: así siempre
                    -- hay una ventana de Excel a la vista. Con el Organizador visual, Excel delante: la ventana nueva
                    -- nace en el grupo de la app y no en uno aparte
                    set nueva to ruta
                    if viejo is not missing value then
                        if full name of viejo is ruta then set nueva to rutaB
                        if organizador then activate
                    end if
                    set wb to my abrirLibro(nueva, comoFinder)
                else if viejo is missing value then
                    set wb to my abrirLibro(ruta, comoFinder)
                else
                    set wb to viejo
                    activate object wb
                end if
                -- La hoja «Gráfico» o, si el autor la llamó de otra forma («G1»), la primera con gráficos
                try
                    activate object worksheet "Gráfico" of wb
                on error
                    repeat with i from 1 to (count worksheets of wb)
                        if (count chart objects of worksheet i of wb) > 0 then
                            activate object worksheet i of wb
                            exit repeat
                        end if
                    end repeat
                end try
                set w to active window
                try
                    set bounds of w to sitio
                end try
                if z is 0 then
                    set zoom of w to 100
                    set f to (width of visible range of w) / anchoRet
                    if (height of visible range of w) / altoRet < f then set f to (height of visible range of w) / altoRet
                    set z to round (100 * f) rounding down
                    if z > 400 then set z to 400
                    if z < 10 then set z to 10
                end if
                set zoom of w to z
                set scroll row of w to 1
                set scroll column of w to 1
                select range "A1" of active sheet
                if recargar and viejo is not missing value then close viejo saving no
                return z
            end tell
        end run
        """
        // Si Excel tarda, casi seguro que pide permiso para la carpeta con su ventana «Abrir» (que el Organizador
        // visual esconde): se trae Excel delante para verla.
        let vigilante = Task { @MainActor in
            do { try await Task.sleep(nanoseconds: 2_500_000_000) } catch { return }
            NSRunningApplication.runningApplications(withBundleIdentifier: idExcel).first?.activate()
            anotar(id, AXIsProcessTrusted()
                   ? "Excel tarda: si muestra alguna ventana, mírala en Excel."
                   : "Excel tarda: si muestra una ventana «Abrir», pide permiso para «\(ruta.lastPathComponent)». Pulsa «Conceder acceso». Para que no lo pida más, da permiso a «Gráficos Excel BdE» en Ajustes del Sistema → Privacidad y seguridad → Accesibilidad.")
        }
        let arrancar = NSRunningApplication.runningApplications(withBundleIdentifier: idExcel).isEmpty
        // Excel delante antes de abrir la otra copia solo si su ventana ya está con la app (en su grupo): así la
        // nueva nace ahí. Si está en otro grupo, se abre sin más y luego se junta
        let excelConLaApp = organizadorVisual && excelSeVe()
        // Con Accesibilidad, el libro se abre como desde el Finder (sin «Conceder acceso») y la app pulsa sola
        // «No actualizar» en el aviso de vínculos externos que Excel saca entonces (nunca se actualizan)
        let comoFinder = AXIsProcessTrusted()
        let vinculos = comoFinder ? Task.detached { await noActualizarVinculos() } : nil
        let r = await osascript(guion, [ruta.path] + (sitio + medidas + [zoom]).map(String.init)
                                + [recargar ? "si" : "no", arrancar ? "si" : "no", Taller.copiaB(ruta).path, excelConLaApp ? "si" : "no",
                                   comoFinder ? "si" : "no"],
                                espera: 120)
        vinculos?.cancel()
        vigilante.cancel()
        // La app vuelve delante para seguir con ⌘← y ⌘→, y con el Organizador visual se trae a su grupo la ventana
        // de Excel (que Excel crea en un grupo aparte, escondida en la tira de la izquierda)
        NSApp.activate(ignoringOtherApps: true)
        // Si se acaba de arrancar Excel, se deja terminar el cambio de grupo (mientras dura se ven las dos ventanas)
        if arrancar && organizadorVisual { try? await Task.sleep(nanoseconds: 1_000_000_000) }
        let juntas = organizadorVisual ? await juntarConExcel(sitio) : true
        if !juntas && !avisadoOrganizador {
            avisadoOrganizador = true
            anotar(id, "Organizador visual activado: para ver Excel junto a la app, da permiso a «Gráficos Excel BdE» en Ajustes del Sistema → Privacidad y seguridad → Accesibilidad. Mientras tanto, arrastra la ventana de Excel desde la tira de la izquierda hasta la app.")
        }
        guard r.ok else {
            anotar(id, "⚠ Excel no abrió la copia (\(r.texto)).")
            return false
        }
        if let z = Int(r.texto) {
            zoomExcel = (sitio, z)
            anotar(id, "En Excel: versión \(paso.n) · hoja del gráfico al \(z) %")
        } else {
            anotar(id, "En Excel: versión \(paso.n)")
        }
        return true
    }
    private var avisadoOrganizador = false

    /// Con el Organizador visual, mete en el grupo de la app la última ventana de Excel (la copia recién abierta),
    /// como si se arrastrara desde la tira de la izquierda: la acción «AXAddToStage» de su miniatura. Necesita el
    /// permiso de Accesibilidad (se pide la primera vez). Si la ventana ya está en el grupo, no hay miniatura.
    private func juntarConExcel(_ sitio: [Int]) async -> Bool {
        let opciones = [kAXTrustedCheckOptionPrompt.takeUnretainedValue(): true] as CFDictionary
        guard AXIsProcessTrustedWithOptions(opciones),
              let excel = NSRunningApplication.runningApplications(withBundleIdentifier: idExcel).first,
              let organizador = NSRunningApplication.runningApplications(withBundleIdentifier: "com.apple.WindowManager").first
        else { return false }
        // De las ventanas de Excel, la más nueva que esté en la tira (miniatura) o a la vista: Excel tiene además
        // ventanas internas (al arrancar, una de 500 × 500 más nueva que la del libro) que no están en ninguna.
        // Con Excel recién arrancado, su miniatura tarda en aparecer: se espera hasta 3 s.
        let tira = AXUIElementCreateApplication(organizador.processIdentifier)
        for _ in 0..<30 {
            let ventanas = (CGWindowListCopyWindowInfo([.optionAll], kCGNullWindowID) as? [[String: Any]] ?? [])
                .filter { ($0[kCGWindowOwnerPID as String] as? pid_t) == excel.processIdentifier && ($0[kCGWindowLayer as String] as? Int) == 0 }
                .compactMap { $0[kCGWindowNumber as String] as? Int }.sorted(by: >)
            let propia = NSApp.windows.first { $0.isVisible && $0.styleMask.contains(.titled) }?.windowNumber ?? 0
            for ventana in ventanas {
                if let miniatura = buscarMiniatura(de: ventana, en: tira) {
                    let ok = AXUIElementPerformAction(miniatura, "AXAddToStage" as CFString) == .success
                    // Al meterla en el grupo, el Organizador visual la coloca a su manera: se vuelve a poner en su sitio
                    try? await Task.sleep(nanoseconds: 400_000_000)
                    await recolocarExcel(sitio)
                    NSApp.activate(ignoringOtherApps: true)
                    return ok
                }
                // Ya están juntas si se ven a la vez y siguen viéndose al acabar la animación (durante el cambio de
                // grupo se ven un momento las dos aunque estén en grupos distintos)
                if seVe(ventana) && seVe(propia) {
                    try? await Task.sleep(nanoseconds: 600_000_000)
                    if seVe(ventana) && seVe(propia) { return true }
                }
            }
            try? await Task.sleep(nanoseconds: 100_000_000)
        }
        return true
    }

    /// La ventana de Excel otra vez en su sitio, a la derecha de la app.
    private func recolocarExcel(_ sitio: [Int]) async {
        let guion = """
        on run argv
            tell application "Microsoft Excel"
                try
                    set bounds of active window to {(item 1 of argv) as integer, (item 2 of argv) as integer, (item 3 of argv) as integer, (item 4 of argv) as integer}
                end try
            end tell
        end run
        """
        _ = await osascript(guion, sitio.map(String.init), espera: 10)
    }

    /// ¿Hay alguna ventana de Excel en pantalla a su tamaño?
    private func excelSeVe() -> Bool {
        guard let excel = NSRunningApplication.runningApplications(withBundleIdentifier: idExcel).first else { return false }
        return (CGWindowListCopyWindowInfo([.optionOnScreenOnly], kCGNullWindowID) as? [[String: Any]] ?? []).contains {
            ($0[kCGWindowOwnerPID as String] as? pid_t) == excel.processIdentifier && ($0[kCGWindowLayer as String] as? Int) == 0
                && ((($0[kCGWindowBounds as String] as? [String: Any])?["Width"] as? Double) ?? 0) > 300
        }
    }

    /// ¿La ventana `numero` está en pantalla a su tamaño (no como miniatura de la tira)?
    private func seVe(_ numero: Int) -> Bool {
        let info = CGWindowListCopyWindowInfo([.optionIncludingWindow], CGWindowID(numero)) as? [[String: Any]] ?? []
        guard let v = info.first, (v[kCGWindowIsOnscreen as String] as? Bool) == true,
              let caja = v[kCGWindowBounds as String] as? [String: Any], let ancho = caja["Width"] as? Double else { return false }
        return ancho > 300
    }

    /// La miniatura de la tira del Organizador visual que contiene la ventana `numero` (atributo «AXWindowsIDs»).
    private func buscarMiniatura(de numero: Int, en elemento: AXUIElement, nivel: Int = 0) -> AXUIElement? {
        var valor: CFTypeRef?
        if AXUIElementCopyAttributeValue(elemento, "AXWindowsIDs" as CFString, &valor) == .success,
           let ids = valor as? [NSNumber], ids.contains(where: { $0.intValue == numero }) {
            return elemento
        }
        guard nivel < 4, AXUIElementCopyAttributeValue(elemento, kAXChildrenAttribute as CFString, &valor) == .success,
              let hijos = valor as? [AXUIElement] else { return nil }
        for hijo in hijos {
            if let encontrado = buscarMiniatura(de: numero, en: hijo, nivel: nivel + 1) { return encontrado }
        }
        return nil
    }

    /// Cierra en Excel (sin guardar) la copia de trabajo y lo que tenga abierto de su carpeta de pasos.
    private func cerrarEnExcel(_ trabajo: URL) async {
        guard excel else { return }
        let carpeta = trabajo.deletingPathExtension().path + " (pasos)/"
        let guion = """
        on run argv
            tell application "Microsoft Excel"
                repeat with i from (count workbooks) to 1 by -1
                    set ruta to full name of workbook i
                    if ruta is item 1 of argv or ruta is item 3 of argv or ruta starts with item 2 of argv then close workbook i saving no
                end repeat
            end tell
        end run
        """
        _ = await osascript(guion, [trabajo.path, carpeta, Taller.copiaB(trabajo).path], espera: 20)
    }

    func verEnExcel() {
        tarea("Ver en Excel") { id in await self.mostrarEnExcel(id, recargar: false) }
    }

    func colocarExcel() {
        tarea("Colocar Excel") { id in await self.mostrarEnExcel(id, recargar: false) }
    }

    /// Líneas guía activadas a mano en Excel: Excel les pone su formato (negro, 0,75 pt) y no guarda otro para
    /// las desactivadas (los gráficos de los autores no tienen hoja de estilo), así que se les da el de la guía
    /// (pág. 16: blanco matiz 5, 0,5 pt) en el libro abierto. Solo a las que no lo tienen ya. Devuelve
    /// «corregidas/activadas», o «sin libro».
    private static let guionLineasGuia = """
    on run argv
        set ruta to item 1 of argv
        tell application "Microsoft Excel"
            set wb to missing value
            repeat with i from 1 to (count workbooks)
                if full name of workbook i is ruta or full name of workbook i is item 2 of argv then set wb to workbook i
            end repeat
            if wb is missing value then return "sin libro"
            set hechas to 0
            set activas to 0
            repeat with h from 1 to (count worksheets of wb)
                set hoja to worksheet h of wb
                repeat with k from 1 to (count chart objects of hoja)
                    set c to chart of chart object k of hoja
                    repeat with n from 1 to (count series of c)
                        set s to series n of c
                        try
                            if has leader lines of s then
                                set activas to activas + 1
                                set lf to line format of chart format of leader lines of s
                                set w to weight of lf
                                if (w > 0.51 or w < 0.49) or (fore color of lf) is not {128, 128, 128} then
                                    set weight of lf to 0.5
                                    set fore color of lf to {128, 128, 128}
                                    set hechas to hechas + 1
                                end if
                            end if
                        end try
                    end repeat
                end repeat
            end repeat
            return (hechas as text) & "/" & (activas as text)
        end tell
    end run
    """

    func lineasGuia() {
        guard let ruta = trabajo else { return }
        tarea("Líneas guía") { id in
            let r = await osascript(Taller.guionLineasGuia, [ruta.path, Taller.copiaB(ruta).path], espera: 60)
            guard r.ok else {
                self.anotar(id, "⚠ Excel no respondió (\(r.texto)).")
                return false
            }
            if r.texto == "sin libro" {
                self.anotar(id, "⚠ La copia de trabajo no está abierta en Excel: pulsa «Colocar Excel».")
                return false
            }
            let partes = r.texto.split(separator: "/").map { Int($0) ?? 0 }
            let (hechas, activas) = (partes.first ?? 0, partes.count > 1 ? partes[1] : 0)
            if activas == 0 {
                self.anotar(id, "No hay líneas guía activadas en ningún gráfico.")
            } else {
                self.anotar(id, hechas == 0 ? "Las líneas guía ya tenían el formato de la guía."
                            : "Líneas guía de \(hechas) serie\(hechas == 1 ? "" : "s") en blanco matiz 5 y 0,5 pt (guía, pág. 16). "
                              + "Están en el Excel abierto: guarda el libro (⌘S) para conservarlas; cambiar de versión las descarta.")
            }
            return true
        }
    }

    /// Al volver a la app (desde Excel), se revisan solas las líneas guía del libro abierto: si alguna activada
    /// no tiene el formato de la guía, se corrige y se anota. Sin tareas en marcha y con espera corta.
    func revisarLineasGuia() {
        guard let ruta = trabajo, enCurso == nil, excel else { return }
        Task {
            let r = await osascript(Taller.guionLineasGuia, [ruta.path, Taller.copiaB(ruta).path], espera: 8)
            let hechas = r.ok ? Int(r.texto.split(separator: "/").first ?? "") ?? 0 : 0
            guard hechas > 0 else { return }
            self.tarea("Líneas guía (al volver a la app)") { id in
                self.anotar(id, "Líneas guía activadas en Excel corregidas solas: \(hechas) serie\(hechas == 1 ? "" : "s") "
                            + "en blanco matiz 5 y 0,5 pt (guía, pág. 16). Guarda el libro (⌘S) para conservarlas.")
                return true
            }
        }
    }

    // MARK: Publicaciones

    func nuevaPublicacion() {
        editando = Publicacion(id: "", nombre: "", color: "FFFFFF", tema: publicacionActual?.tema)
    }

    func guardar(_ p: Publicacion) {
        tarea(p.id.isEmpty ? "Nueva publicación: \(p.nombre)" : "Publicación: \(p.nombre)") { id in
            guard let datos = try? JSONEncoder().encode(p), let json = String(data: datos, encoding: .utf8),
                  let r = await self.llamarMotor(["guardar_publicacion", json], registro: id) else { return false }
            if let nueva = r.publicacion { self.publicacion = nueva }
            self.anotar(id, "Guardada: \(p.nombre) · color \(p.color) · tema \(p.tema ?? "sin tema")")
            return true
        }
    }

    func borrarPublicacion() {
        guard let p = publicacionActual else { return }
        pregunta = Pregunta(titulo: "Borrar «\(p.nombre)»", texto: "Se quita de la lista de publicaciones.", boton: "Borrar") {
            self.tarea("Borrar publicación: \(p.nombre)") { id in
                guard await self.llamarMotor(["borrar_publicacion", p.id], registro: id) != nil else { return false }
                self.publicacion = self.publicaciones.first?.id ?? ""
                return true
            }
        }
    }
}

// MARK: - Ventana general

struct Ventana: View {
    @ObservedObject var taller: Taller

    var body: some View {
        NavigationSplitView {
            BarraLateral(taller: taller)
                .navigationSplitViewColumnWidth(min: 250, ideal: 280, max: 340)
        } detail: {
            VStack(spacing: 0) {
                ScrollView {
                    VStack(spacing: 0) {
                        Cabecera(taller: taller)
                        HStack(alignment: .top, spacing: 14) {
                            TarjetaMaquetar(taller: taller)
                            TarjetaVersiones(taller: taller)
                        }
                        .fixedSize(horizontal: false, vertical: true)
                        .padding(.horizontal, 20)
                        .padding(.bottom, 14)
                        TarjetaTerminar(taller: taller)
                            .padding(.horizontal, 20)
                            .padding(.bottom, 18)
                    }
                }
                Divider()
                Consola(taller: taller)
                    .frame(height: 190)
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
        .sheet(item: $taller.editando) { p in
            HojaPublicacion(taller: taller, publicacion: p)
        }
        .onAppear {
            // Un .xlsx pasado al arrancar (open -a … --args <ruta>) se abre directamente
            if let ruta = CommandLine.arguments.dropFirst().first(where: { $0.lowercased().hasSuffix(".xlsx") }) {
                taller.abrir(URL(fileURLWithPath: ruta))
            }
        }
    }
}

// MARK: - Barra lateral

struct BarraLateral: View {
    @ObservedObject var taller: Taller
    @State private var soltando = false

    var body: some View {
        VStack(alignment: .leading, spacing: 18) {
            HStack(spacing: 10) {
                ZStack {
                    RoundedRectangle(cornerRadius: 9)
                        .fill(LinearGradient(colors: [colorApp, colorVersiones], startPoint: .topLeading, endPoint: .bottomTrailing))
                    Image(systemName: "chart.bar.xaxis").foregroundStyle(.white).font(.system(size: 17, weight: .semibold))
                }
                .frame(width: 36, height: 36)
                VStack(alignment: .leading, spacing: 1) {
                    Text("Gráficos Excel BdE").font(.system(size: 15, weight: .bold))
                    Text("Del Excel del autor al gráfico").font(.system(size: 11)).foregroundStyle(.secondary)
                }
            }
            .padding(.top, 6)

            VStack(alignment: .leading, spacing: 8) {
                Rotulo("Publicación")
                HStack(spacing: 6) {
                    Picker("", selection: $taller.publicacion) {
                        ForEach(taller.publicaciones) { p in
                            Text(p.nombre).tag(p.id)
                        }
                    }
                    .labelsHidden()
                    .disabled(taller.publicaciones.isEmpty)
                    Menu {
                        Button("Nueva publicación…") { taller.nuevaPublicacion() }
                        Button("Editar publicación…") { taller.editando = taller.publicacionActual }
                            .disabled(taller.publicacionActual == nil)
                        Divider()
                        Button("Mostrar la lista en el Finder") {
                            NSWorkspace.shared.activateFileViewerSelecting([motor.appendingPathComponent("publicaciones.json")])
                        }
                        Divider()
                        Button("Borrar publicación…", role: .destructive) { taller.borrarPublicacion() }
                            .disabled(taller.publicacionActual == nil)
                    } label: { Image(systemName: "ellipsis.circle") }
                    .menuStyle(.borderlessButton)
                    .fixedSize()
                    .disabled(taller.enCurso != nil)
                }
                if taller.publicaciones.isEmpty {
                    VStack(alignment: .leading, spacing: 6) {
                        Text("Aún no hay publicaciones").font(.system(size: 11, weight: .medium)).foregroundStyle(.orange)
                        Button { taller.nuevaPublicacion() } label: { Label("Nueva publicación…", systemImage: "plus") }
                            .controlSize(.small)
                            .disabled(taller.enCurso != nil)
                    }
                }
                if let p = taller.publicacionActual {
                    HStack(spacing: 8) {
                        RoundedRectangle(cornerRadius: 4).fill(colorHex(p.color))
                            .overlay(RoundedRectangle(cornerRadius: 4).strokeBorder(Color.primary.opacity(0.15)))
                            .frame(width: 34, height: 18)
                        VStack(alignment: .leading, spacing: 0) {
                            Text("Pastilla #\(p.color)").font(.system(size: 11, weight: .medium))
                            Text("Tema: \(p.tema ?? "sin definir")").font(.system(size: 10.5))
                                .foregroundStyle(p.tema == nil ? Color.orange : Color.secondary)
                        }
                    }
                }
            }

            VStack(alignment: .leading, spacing: 8) {
                HStack {
                    Rotulo("Excel del autor")
                    Spacer()
                    HStack(spacing: 4) {
                        Circle().fill(taller.excel ? Color.green : Color.secondary.opacity(0.5)).frame(width: 7, height: 7)
                        Text(taller.excel ? "Excel abierto" : "Excel cerrado").font(.system(size: 10.5)).foregroundStyle(.secondary)
                    }
                }
                Button { taller.elegir() } label: {
                    VStack(spacing: 6) {
                        Image(systemName: soltando ? "arrow.down.doc.fill" : (taller.trabajo == nil ? "doc.badge.plus" : "tablecells"))
                            .font(.system(size: 24, weight: .light))
                            .foregroundStyle(colorApp)
                        if let t = taller.trabajo {
                            Text(t.lastPathComponent).font(.system(size: 12, weight: .semibold)).multilineTextAlignment(.center)
                                .lineLimit(2).truncationMode(.middle)
                            Text("Clic o arrastra otro para cambiar").font(.system(size: 10.5)).foregroundStyle(.secondary)
                        } else {
                            Text("Elegir Excel…").font(.system(size: 12.5, weight: .semibold))
                            Text("Clic o arrastra aquí el Excel del autor").font(.system(size: 10.5)).foregroundStyle(.secondary)
                                .multilineTextAlignment(.center)
                        }
                    }
                    .padding(12)
                    .frame(maxWidth: .infinity)
                    .background(RoundedRectangle(cornerRadius: 12).fill(colorApp.opacity(soltando ? 0.16 : 0.06)))
                    .overlay(RoundedRectangle(cornerRadius: 12).strokeBorder(colorApp.opacity(0.5), style: StrokeStyle(lineWidth: 1.5, dash: [6, 4])))
                    .contentShape(Rectangle())
                }
                .buttonStyle(.plain)
                .disabled(taller.enCurso != nil)
                .onDrop(of: [.fileURL], isTargeted: $soltando) { proveedores in
                    _ = proveedores.first?.loadObject(ofClass: URL.self) { url, _ in
                        if let url, url.pathExtension.lowercased() == "xlsx" { Task { @MainActor in taller.abrir(url) } }
                    }
                    return true
                }
                if let t = taller.trabajo {
                    HStack(spacing: 6) {
                        Button { taller.verEnExcel() } label: { Label("Abrir en Excel", systemImage: "arrow.up.forward.app") }
                            .disabled(taller.enCurso != nil)
                        Button { NSWorkspace.shared.activateFileViewerSelecting([t]) } label: { Image(systemName: "folder") }
                            .help("Mostrar en el Finder")
                    }
                    .controlSize(.small)
                }
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
                        Text(motor.path).font(.system(size: 10.5)).lineLimit(1).truncationMode(.middle)
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

// MARK: - Cabecera

struct Cabecera: View {
    @ObservedObject var taller: Taller

    var body: some View {
        HStack(alignment: .center, spacing: 14) {
            Image(systemName: "tablecells.fill")
                .font(.system(size: 26))
                .foregroundStyle(colorApp)
            VStack(alignment: .leading, spacing: 3) {
                Text(taller.trabajo?.lastPathComponent ?? "Ningún Excel").font(.system(size: 20, weight: .bold))
                    .lineLimit(1).truncationMode(.middle)
                Text(detalle).font(.system(size: 12)).foregroundStyle(.secondary).lineLimit(1).truncationMode(.middle)
            }
            Spacer()
            if let e = taller.ejecucionEnCurso {
                HStack(spacing: 8) {
                    // Fijo, sin ruedecita: una animación continua bloqueaba la app con el Organizador visual
                    Image(systemName: "hourglass").foregroundStyle(colorApp)
                    Text("\(e.titulo) · \(duracion(taller.segundos(e)))").font(.system(size: 12, weight: .medium)).monospacedDigit()
                }
                .padding(.horizontal, 12)
                .padding(.vertical, 6)
                .background(Capsule().fill(colorApp.opacity(0.14)))
                .transition(.scale.combined(with: .opacity))
            }
        }
        .animation(.spring(duration: 0.3), value: taller.enCurso)
        .padding(.horizontal, 22)
        .padding(.top, 18)
        .padding(.bottom, 14)
    }

    var detalle: String {
        guard taller.trabajo != nil else { return "Elige el Excel del autor para empezar · Publicación: " + (taller.publicacionActual?.nombre ?? "—") }
        return [taller.idioma == "en" ? "Inglés" : "Castellano",
                "Publicación: " + (taller.publicacionActual?.nombre ?? "—"),
                "Versión \(taller.actual) de \(max(taller.pasos.count - 1, 0))"].joined(separator: " · ")
    }
}

// MARK: - Tarjetas

struct Tarjeta<Contenido: View>: View {
    let numero: String
    let titulo: String
    let lema: String
    let icono: String
    let color: Color
    var trabajando = false
    @ViewBuilder let contenido: Contenido

    var body: some View {
        VStack(alignment: .leading, spacing: 14) {
            HStack(alignment: .top, spacing: 12) {
                ZStack {
                    RoundedRectangle(cornerRadius: 11).fill(color.gradient)
                    Image(systemName: icono).font(.system(size: 19, weight: .semibold)).foregroundStyle(.white)
                }
                .frame(width: 42, height: 42)
                VStack(alignment: .leading, spacing: 2) {
                    Text(numero).font(.system(size: 10, weight: .bold)).tracking(0.8).foregroundStyle(color)
                    Text(titulo).font(.system(size: 17, weight: .bold))
                }
                Spacer(minLength: 0)
            }
            Text(lema).font(.system(size: 12)).foregroundStyle(.secondary).fixedSize(horizontal: false, vertical: true)
            contenido
            Spacer(minLength: 0)
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
                .strokeBorder(trabajando ? color : Color.primary.opacity(0.07), lineWidth: trabajando ? 2 : 1)
        )
        .animation(.easeInOut(duration: 0.25), value: trabajando)
    }
}

struct TarjetaMaquetar: View {
    @ObservedObject var taller: Taller

    var body: some View {
        Tarjeta(numero: "PASOS", titulo: "Maquetar", lema: "Cada paso trabaja sobre la versión elegida y deja una versión nueva",
                icono: "wand.and.stars", color: colorApp, trabajando: taller.enCurso != nil) {
            VStack(alignment: .leading, spacing: 4) {
                ForEach(pasosMaquetacion) { p in
                    let hecho = taller.pasos.contains { $0.titulo == p.titulo && $0.n <= taller.actual }
                    Accion(icono: p.icono, titulo: "\(p.id). \(p.titulo)", detalle: p.detalle, color: colorApp,
                           principal: !hecho, marca: hecho ? "checkmark.circle.fill" : nil) { taller.hacer(p) }
                }
            }
            .disabled(taller.trabajo == nil || taller.publicacionActual == nil || taller.enCurso != nil)
            Rotulo("Excepciones a los gráficos")
            let colocado = taller.pasos.contains { $0.titulo == "Tamaño y colocación" && $0.n <= taller.actual }
            let hechaSinEje = taller.pasos.contains { $0.titulo == herramientaSinEje.titulo && $0.n <= taller.actual }
            Accion(icono: herramientaSinEje.icono, titulo: herramientaSinEje.titulo, detalle: herramientaSinEje.detalle,
                   color: colorApp, principal: false, marca: hechaSinEje ? "checkmark.circle.fill" : nil) { taller.hacer(herramientaSinEje) }
                .disabled(taller.trabajo == nil || taller.publicacionActual == nil || taller.enCurso != nil || !colocado)
            Label("Siguientes pasos: los iremos añadiendo", systemImage: "ellipsis")
                .font(.system(size: 10.5)).foregroundStyle(.tertiary)
        }
    }
}

struct TarjetaVersiones: View {
    @ObservedObject var taller: Taller

    var body: some View {
        Tarjeta(numero: "VERSIONES", titulo: "Adelante y atrás", lema: "Elige una versión para verla en Excel",
                icono: "clock.arrow.circlepath", color: colorVersiones) {
            VStack(alignment: .leading, spacing: 3) {
                if taller.pasos.isEmpty {
                    Text("Aún no hay versiones").font(.system(size: 11.5)).foregroundStyle(.secondary)
                }
                ForEach(taller.pasos) { p in
                    FilaVersion(paso: p, actual: p.n == taller.actual, futura: p.n > taller.actual) { taller.ir(p.n) }
                }
            }
            .disabled(taller.enCurso != nil)
            HStack(spacing: 6) {
                Button { taller.ir(taller.actual - 1) } label: { Image(systemName: "chevron.left") }
                    .disabled(taller.actual == 0)
                    .keyboardShortcut(.leftArrow, modifiers: .command)
                Button { taller.ir(taller.actual + 1) } label: { Image(systemName: "chevron.right") }
                    .disabled(taller.actual + 1 >= taller.pasos.count)
                    .keyboardShortcut(.rightArrow, modifiers: .command)
                Spacer()
                Button { taller.reiniciar() } label: { Label("Reiniciar", systemImage: "arrow.counterclockwise") }
                    .controlSize(.small)
                    .disabled(taller.pasos.count <= 1)
                    .help("Vuelve a empezar desde el Excel del autor: borra todas las versiones")
                Button { taller.colocarExcel() } label: { Label("Colocar Excel", systemImage: "rectangle.split.2x1") }
                    .controlSize(.small)
                    .help("Pone Excel a la derecha de la app, en la hoja «Gráfico» y con el gráfico entero a la vista")
                Button { taller.lineasGuia() } label: { Label("Líneas guía", systemImage: "line.diagonal") }
                    .controlSize(.small)
                    .help("Da el formato de la guía (blanco matiz 5, 0,5 pt) a las líneas guía que hayas activado a mano en Excel")
            }
            .disabled(taller.enCurso != nil || taller.pasos.isEmpty)
            Label("Si activas líneas guía en Excel, vuelve a la app (se corrigen solas) o pulsa «Líneas guía», y guarda el libro (⌘S).",
                  systemImage: "info.circle")
                .font(.system(size: 10.5)).foregroundStyle(.secondary).fixedSize(horizontal: false, vertical: true)
            if let p = taller.pasoActual, !p.detalle.isEmpty {
                VStack(alignment: .leading, spacing: 5) {
                    Rotulo("Cambios de la versión \(p.n)")
                    ForEach(p.detalle, id: \.self) { linea in
                        // Los avisos, en rojo y negrita: piden comprobar algo a mano
                        let aviso = linea.hasPrefix("Aviso")
                        HStack(alignment: .firstTextBaseline, spacing: 6) {
                            Image(systemName: aviso ? "exclamationmark.triangle.fill" : "circle.fill")
                                .font(.system(size: aviso ? 10 : 4))
                                .foregroundStyle(aviso ? Color.red : colorVersiones)
                            Text(linea).font(.system(size: 11.5, weight: aviso ? .bold : .regular))
                                .foregroundStyle(aviso ? Color.red : Color.primary)
                                .fixedSize(horizontal: false, vertical: true)
                        }
                    }
                }
                .padding(10)
                .frame(maxWidth: .infinity, alignment: .leading)
                .background(RoundedRectangle(cornerRadius: 10).fill(colorVersiones.opacity(0.06)))
            }
        }
    }
}

struct TarjetaTerminar: View {
    @ObservedObject var taller: Taller
    let color = Color(red: 0.55, green: 0.33, blue: 0.85)

    var body: some View {
        Tarjeta(numero: "FINAL", titulo: "Terminar", lema: "Comprueba que no falte nada del original y guarda el resultado",
                icono: "checkmark.seal", color: color, trabajando: taller.enCurso != nil) {
            HStack(alignment: .top, spacing: 14) {
                Accion(icono: "doc.text.magnifyingglass", titulo: "Comparar con el original",
                       detalle: "Textos, cifras y datos de todas las hojas frente al Excel del autor (no la colocación): avisa de lo que falte y de los cambios de cifras, fechas, trimestres, mayúsculas… No crea versión",
                       color: color, principal: taller.comparacion.isEmpty) { taller.comparar() }
                Accion(icono: "checkmark.circle", titulo: "Guardar como TERMINADO",
                       detalle: taller.trabajo == nil ? "Guarda el resultado junto al original y borra las copias y las versiones"
                           : "Guarda «\(taller.nombreTerminado)» junto al original y borra las copias de trabajo y la carpeta de versiones",
                       color: color, principal: !taller.comparacion.isEmpty) { taller.terminar() }
            }
            .disabled(taller.trabajo == nil || taller.pasos.isEmpty || taller.enCurso != nil)
            if !taller.comparacion.isEmpty {
                VStack(alignment: .leading, spacing: 5) {
                    Rotulo("Comparación con el original (versión \(taller.actual), lo guardado)")
                    ForEach(taller.comparacion, id: \.self) { linea in
                        let aviso = linea.hasPrefix("Aviso")
                        let cambio = linea.hasPrefix("Cambio")
                        HStack(alignment: .firstTextBaseline, spacing: 6) {
                            Image(systemName: aviso ? "exclamationmark.triangle.fill" : cambio ? "arrow.left.arrow.right" : "circle.fill")
                                .font(.system(size: aviso || cambio ? 10 : 4))
                                .foregroundStyle(aviso ? Color.red : cambio ? Color.orange : color)
                            Text(linea).font(.system(size: 11.5, weight: aviso ? .bold : .regular))
                                .foregroundStyle(aviso ? Color.red : Color.primary)
                                .fixedSize(horizontal: false, vertical: true)
                                .textSelection(.enabled)
                        }
                    }
                }
                .padding(10)
                .frame(maxWidth: .infinity, alignment: .leading)
                .background(RoundedRectangle(cornerRadius: 10).fill(color.opacity(0.06)))
            }
        }
    }
}

struct FilaVersion: View {
    let paso: Paso
    let actual: Bool
    let futura: Bool
    let hacer: () -> Void
    @State private var encima = false

    var body: some View {
        Button(action: hacer) {
            HStack(spacing: 9) {
                Text(String(format: "%02d", paso.n)).font(.system(size: 11, weight: .bold).monospacedDigit())
                    .foregroundStyle(actual ? Color.white : colorVersiones)
                    .frame(width: 26, height: 20)
                    .background(RoundedRectangle(cornerRadius: 5).fill(actual ? colorVersiones : colorVersiones.opacity(0.12)))
                Text(paso.titulo).font(.system(size: 12.5, weight: actual ? .semibold : .regular))
                    .foregroundStyle(futura ? Color.secondary : Color.primary)
                Spacer(minLength: 0)
            }
            .padding(.horizontal, 6)
            .padding(.vertical, 4)
            .background(RoundedRectangle(cornerRadius: 7).fill(encima ? Color.primary.opacity(0.06) : Color.clear))
            .contentShape(Rectangle())
        }
        .buttonStyle(.plain)
        .onHover { encima = $0 }
    }
}

struct Accion: View {
    let icono: String
    let titulo: String
    let detalle: String
    let color: Color
    var principal = false
    var marca: String?
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
                if let marca { Image(systemName: marca).foregroundStyle(color) }
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
                    Text(formatoHora.string(from: e.inicio) + " · " + duracion(taller.segundos(e)))
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
                                    .font(.system(size: 11.5, weight: linea.hasPrefix("• Aviso") ? .bold : .regular, design: .monospaced))
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
            Image(systemName: "hourglass").foregroundStyle(colorApp)
        } else {
            Image(systemName: e.ok == true ? "checkmark.circle.fill" : "xmark.octagon.fill")
                .foregroundStyle(e.ok == true ? colorApp : .red)
        }
    }

    func color(_ linea: String) -> Color {
        if linea.hasPrefix("Error") || linea.hasPrefix("• Aviso") { return .red }
        if linea.contains("⚠") { return .orange }
        return .primary
    }
}

// MARK: - Hoja de publicación

struct HojaPublicacion: View {
    @ObservedObject var taller: Taller
    @State var publicacion: Publicacion
    @Environment(\.dismiss) private var cerrar

    var esNueva: Bool { publicacion.id.isEmpty }
    var hex: String { publicacion.color.replacingOccurrences(of: "#", with: "").uppercased() }
    var hexValido: Bool { hex.range(of: "^[0-9A-F]{6}$", options: .regularExpression) != nil }
    var otras: [Publicacion] { taller.publicaciones.filter { esNueva || $0.id != publicacion.id } }
    var repetida: Publicacion? { otras.first { $0.color.uppercased() == hex } }
    var paletaElegida: Paleta? { taller.paletas.first { $0.id == publicacion.tema } }

    var body: some View {
        VStack(spacing: 0) {
            HStack {
                Text(esNueva ? "Nueva publicación" : "Editar publicación").font(.title3.bold())
                Spacer()
            }
            .padding(.horizontal, 20).padding(.vertical, 14)
            Divider()
            HStack(alignment: .top, spacing: 0) {
                muestrarioPastillas.frame(width: 320)
                Divider()
                ScrollView {
                    VStack(alignment: .leading, spacing: 18) {
                        datos
                        panelPaletas
                    }
                    .padding(20)
                }
            }
            Divider()
            HStack {
                if let carpeta = taller.carpetaPaletas {
                    Button { NSWorkspace.shared.open(URL(fileURLWithPath: carpeta)) } label: {
                        Label("Paletas de Excel en el Finder", systemImage: "folder")
                    }
                    .controlSize(.small)
                }
                Spacer()
                Button("Cancelar") { cerrar() }.keyboardShortcut(.cancelAction)
                Button(esNueva ? "Crear" : "Guardar") {
                    publicacion.color = hex
                    taller.guardar(publicacion)
                    cerrar()
                }
                .keyboardShortcut(.defaultAction)
                .disabled(publicacion.nombre.trimmingCharacters(in: .whitespaces).isEmpty || !hexValido)
            }
            .padding(.horizontal, 20).padding(.vertical, 12)
        }
        .frame(width: 940, height: 660)
        .task { await taller.cargarPaletas() }
    }

    // MARK: Muestrario

    var muestrarioPastillas: some View {
        VStack(alignment: .leading, spacing: 10) {
            Rotulo("Muestrario de pastillas")
            Text("Haz clic en una pastilla para usar su color.")
                .font(.system(size: 11)).foregroundStyle(.secondary).fixedSize(horizontal: false, vertical: true)
            ScrollView {
                VStack(alignment: .leading, spacing: 4) {
                    FilaMuestrario(publicacion: publicacion, editada: true, nueva: esNueva, elegida: false)
                    if !otras.isEmpty {
                        apartado("Publicaciones creadas")
                        ForEach(otras) { p in
                            muestra(p.nombre, p.color, tema: p.tema) { publicacion.color = p.color }
                                .contextMenu {
                                    if let t = p.tema { Button("Usar también su paleta (\(t))") { publicacion.color = p.color; publicacion.tema = t } }
                                }
                        }
                    }
                    apartado("Archivo de retículas, hoja «Gráfico»")
                    ForEach(taller.muestrario, id: \.self) { m in
                        muestra(m.nombre, m.color, tema: nil) {
                            publicacion.color = m.color
                            if publicacion.nombre.trimmingCharacters(in: .whitespaces).isEmpty { publicacion.nombre = m.nombre }
                        }
                    }
                }
            }
        }
        .padding(16)
        .frame(maxHeight: .infinity, alignment: .top)
        .background(Color.primary.opacity(0.03))
    }

    func apartado(_ texto: String) -> some View {
        Text(texto).font(.system(size: 10, weight: .semibold)).foregroundStyle(.secondary).padding(.top, 10).padding(.leading, 6)
    }

    func muestra(_ nombre: String, _ color: String, tema: String?, usar: @escaping () -> Void) -> some View {
        Button(action: usar) {
            FilaMuestrario(publicacion: Publicacion(id: "", nombre: nombre, color: color, tema: tema), editada: false, nueva: false,
                           elegida: hexValido && color.uppercased() == hex)
        }
        .buttonStyle(.plain)
        .help("Usar el color #\(color) de «\(nombre)»")
    }

    // MARK: Nombre y color

    var datos: some View {
        VStack(alignment: .leading, spacing: 14) {
            VStack(alignment: .leading, spacing: 6) {
                Rotulo("Nombre")
                TextField("Nombre de la publicación", text: $publicacion.nombre).textFieldStyle(.roundedBorder)
            }
            VStack(alignment: .leading, spacing: 6) {
                Rotulo("Color de la pastilla")
                HStack(spacing: 10) {
                    ColorPicker("", selection: Binding(get: { colorHex(hex) }, set: { publicacion.color = hexDe($0) }),
                                supportsOpacity: false)
                        .labelsHidden()
                    TextField("FFE0C9", text: $publicacion.color).textFieldStyle(.roundedBorder).frame(width: 90)
                        .font(.system(.body, design: .monospaced))
                    if !hexValido {
                        Label("Hacen falta 6 cifras hexadecimales", systemImage: "xmark.octagon.fill")
                            .font(.system(size: 11)).foregroundStyle(.red)
                    } else if let r = repetida {
                        Label("Ya lo usa «\(r.nombre)»", systemImage: "exclamationmark.triangle.fill")
                            .font(.system(size: 11)).foregroundStyle(.orange).lineLimit(2)
                    }
                }
                // La pastilla como queda en la hoja «Gráfico»
                ZStack(alignment: .leading) {
                    Rectangle().fill(hexValido ? colorHex(hex) : Color.clear)
                        .overlay(Rectangle().strokeBorder(hexValido ? Color.primary.opacity(0.12) : Color.red))
                    VStack(alignment: .leading, spacing: 1) {
                        Text("Gráfico X").font(.system(size: 11, weight: .bold))
                        Text("Título del gráfico").font(.system(size: 11))
                    }
                    .foregroundStyle(.black)
                    .padding(.leading, 8)
                }
                .frame(height: 40)
            }
        }
    }

    // MARK: Panel de paletas

    var panelPaletas: some View {
        VStack(alignment: .leading, spacing: 10) {
            HStack {
                Rotulo("Paleta de colores")
                Spacer()
                Button { Task { await taller.cargarPaletas(actualizar: true) } } label: { Image(systemName: "arrow.clockwise") }
                    .buttonStyle(.borderless).help("Volver a leer las paletas de Excel")
            }
            Text("Las paletas (temas de color) que tiene instaladas Excel. La publicación usará la elegida en sus gráficos.")
                .font(.system(size: 11)).foregroundStyle(.secondary)
            if let e = taller.errorPaletas {
                Label("No se pueden leer las paletas de Excel: \(e)", systemImage: "xmark.octagon.fill")
                    .font(.system(size: 11)).foregroundStyle(.red).textSelection(.enabled)
            }
            if let t = publicacion.tema, paletaElegida == nil, taller.errorPaletas == nil {
                Label("La paleta «\(t)» no está instalada en Excel", systemImage: "exclamationmark.triangle.fill")
                    .font(.system(size: 11)).foregroundStyle(.orange)
            }
            LazyVGrid(columns: [GridItem(.flexible(), spacing: 10), GridItem(.flexible(), spacing: 10)], spacing: 10) {
                TarjetaPaleta(nombre: "Sin paleta", detalle: "Se decide más adelante", colores: [],
                              usadaEn: [], elegida: publicacion.tema == nil) { publicacion.tema = nil }
                ForEach(taller.paletas) { p in
                    TarjetaPaleta(nombre: p.id, detalle: p.nombre == p.id ? "" : "dentro: «\(p.nombre)»",
                                  colores: p.colores.map(\.hex), usadaEn: otras.filter { $0.tema == p.id }.map(\.nombre),
                                  elegida: publicacion.tema == p.id) { publicacion.tema = p.id }
                }
            }
            if let p = paletaElegida {
                VStack(alignment: .leading, spacing: 8) {
                    Text("Colores de «\(p.id)»").font(.system(size: 12, weight: .semibold))
                    LazyVGrid(columns: Array(repeating: GridItem(.flexible(), spacing: 8), count: 5), spacing: 10) {
                        ForEach(p.colores, id: \.clave) { c in
                            VStack(spacing: 3) {
                                RoundedRectangle(cornerRadius: 5).fill(colorHex(c.hex))
                                    .overlay(RoundedRectangle(cornerRadius: 5).strokeBorder(Color.primary.opacity(0.15)))
                                    .frame(height: 30)
                                Text(nombresColorPaleta[c.clave] ?? c.clave).font(.system(size: 10)).lineLimit(1)
                                Text("#\(c.hex)").font(.system(size: 10, design: .monospaced)).foregroundStyle(.secondary)
                            }
                        }
                    }
                }
                .padding(12)
                .background(RoundedRectangle(cornerRadius: 10).fill(Color.primary.opacity(0.04)))
            }
        }
    }
}

struct FilaMuestrario: View {
    let publicacion: Publicacion
    let editada: Bool
    let nueva: Bool
    let elegida: Bool
    @State private var encima = false

    var body: some View {
        HStack(spacing: 10) {
            Rectangle().fill(colorHex(publicacion.color))
                .overlay(Rectangle().strokeBorder(Color.primary.opacity(0.15)))
                .frame(width: 92, height: 26)
            VStack(alignment: .leading, spacing: 1) {
                Text(publicacion.nombre.isEmpty ? "Publicación nueva" : publicacion.nombre)
                    .font(.system(size: 11.5, weight: editada ? .semibold : .regular))
                    .foregroundStyle(publicacion.nombre.isEmpty ? Color.secondary : Color.primary)
                    .lineLimit(2).fixedSize(horizontal: false, vertical: true)
                Text("#\(publicacion.color.uppercased())" + (publicacion.tema.map { " · \($0)" } ?? ""))
                    .font(.system(size: 10, design: .monospaced)).foregroundStyle(.secondary).lineLimit(1)
            }
            Spacer(minLength: 0)
            if editada {
                Text(nueva ? "NUEVA" : "EDITANDO").font(.system(size: 9, weight: .bold)).foregroundStyle(colorApp)
            } else if elegida {
                Image(systemName: "checkmark.circle.fill").foregroundStyle(colorApp)
            }
        }
        .padding(6)
        .background(RoundedRectangle(cornerRadius: 8).fill(editada ? colorApp.opacity(0.12)
                                                           : Color.primary.opacity(encima ? 0.07 : 0)))
        .overlay(RoundedRectangle(cornerRadius: 8).strokeBorder(editada ? colorApp.opacity(0.5)
                                                                : elegida ? colorApp.opacity(0.35) : Color.clear))
        .contentShape(Rectangle())
        .onHover { encima = $0 }
    }
}

struct TarjetaPaleta: View {
    let nombre: String
    let detalle: String
    let colores: [String]
    let usadaEn: [String]
    let elegida: Bool
    let elegir: () -> Void

    var body: some View {
        Button(action: elegir) {
            VStack(alignment: .leading, spacing: 6) {
                HStack {
                    Image(systemName: elegida ? "checkmark.circle.fill" : "circle")
                        .foregroundStyle(elegida ? colorApp : Color.secondary)
                    Text(nombre).font(.system(size: 12, weight: .semibold)).lineLimit(1)
                    Spacer(minLength: 0)
                    Text(detalle).font(.system(size: 10)).foregroundStyle(.secondary).lineLimit(1)
                }
                HStack(spacing: 2) {
                    if colores.isEmpty {
                        RoundedRectangle(cornerRadius: 3).strokeBorder(Color.secondary.opacity(0.4), style: StrokeStyle(lineWidth: 1, dash: [3, 3]))
                    } else {
                        ForEach(Array(colores.enumerated()), id: \.offset) { _, c in
                            Rectangle().fill(colorHex(c))
                        }
                    }
                }
                .frame(height: 18)
                .clipShape(RoundedRectangle(cornerRadius: 3))
                .overlay(RoundedRectangle(cornerRadius: 3).strokeBorder(Color.primary.opacity(colores.isEmpty ? 0 : 0.15)))
                Text(usadaEn.isEmpty ? " " : "Usada en: " + usadaEn.joined(separator: ", "))
                    .font(.system(size: 10)).foregroundStyle(.secondary).lineLimit(1).truncationMode(.tail)
                    .help(usadaEn.joined(separator: "\n"))
            }
            .padding(10)
            .background(RoundedRectangle(cornerRadius: 10).fill(elegida ? colorApp.opacity(0.10) : Color.primary.opacity(0.04)))
            .overlay(RoundedRectangle(cornerRadius: 10).strokeBorder(elegida ? colorApp : Color.primary.opacity(0.08), lineWidth: elegida ? 2 : 1))
            .contentShape(Rectangle())
        }
        .buttonStyle(.plain)
    }
}

// MARK: - App

final class Delegado: NSObject, NSApplicationDelegate {
    func applicationDidFinishLaunching(_ notification: Notification) { NSApp.activate(ignoringOtherApps: true) }

    func applicationShouldTerminateAfterLastWindowClosed(_ sender: NSApplication) -> Bool { true }
}

@main
struct GraficosExcelApp: App {
    @NSApplicationDelegateAdaptor(Delegado.self) private var delegado
    @StateObject private var taller = Taller()

    var body: some Scene {
        Window("Gráficos Excel BdE", id: "principal") {
            Ventana(taller: taller)
                .frame(minWidth: 960, minHeight: 640)
        }
        .defaultSize(width: 1080, height: 760)
        // Siempre se abre al arrancar (sin restaurar cómo estaba al salir: a veces volvía cerrada)
        .defaultLaunchBehavior(.presented)
        .restorationBehavior(.disabled)
        .commands {
            CommandGroup(replacing: .newItem) {
                Button("Elegir Excel…") { taller.elegir() }.keyboardShortcut("o")
                Button("Nueva publicación…") { taller.nuevaPublicacion() }.keyboardShortcut("n")
            }
        }
    }
}
