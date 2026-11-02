// Gráficos Excel BdE: maqueta paso a paso el Excel que entrega el autor.
// Ventana general (publicación, pasos, versiones y actividad) y una ventana flotante con el gráfico
// tal como lo dibuja Excel en la versión elegida. El trabajo lo hace motor/maquetar_excel.py sobre una
// copia, con una versión por paso; la app lanza los pasos, va adelante y atrás y habla con Excel.
import AppKit
import PDFKit
import SwiftUI
import UniformTypeIdentifiers

/// Carpeta del motor: junto a la app, o la que se diga con
/// `defaults write es.estudioencuadre.graficos-excel motor "<ruta>"`.
let motor: URL = {
    if let ruta = UserDefaults.standard.string(forKey: "motor") { return URL(fileURLWithPath: ruta) }
    return Bundle.main.bundleURL.deletingLastPathComponent().appendingPathComponent("motor")
}()
let idExcel = "com.microsoft.Excel"
/// Excel está aislado (sandbox): aquí abre y guarda sin pedir permiso. Se usa para la vista previa.
let carpetaOffice = FileManager.default.homeDirectoryForCurrentUser
    .appendingPathComponent("Library/Group Containers/UBF8T346G9.Office/Graficos Excel BdE")

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
    let actual: Int?
    let pasos: [Paso]?
    let publicaciones: [Publicacion]?
    let muestrario: [Muestra]?
    let publicacion: String?
    let vista: String?
    let paletas: [Paleta]?
    let carpeta: String?
}

/// Los pasos de maquetación que la app sabe hacer, en orden
struct PasoMaquetacion: Identifiable {
    let id: Int
    let titulo: String
    let detalle: String
    let icono: String
    let orden: String
}

let pasosMaquetacion = [
    PasoMaquetacion(id: 1, titulo: "Retícula y pastilla",
                    detalle: "Borra las del autor y pone las del archivo de retículas, en A1 y al fondo, con el color de la publicación",
                    icono: "square.grid.3x3.topleft.filled", orden: "paso1"),
    PasoMaquetacion(id: 2, titulo: "Textos",
                    detalle: "Todo en Roboto: Gráfico NN y título con el marco de la plantilla; paneles, ejes, leyendas, unidades, interior y fuentes con su cuerpo, donde los dejó el autor",
                    icono: "textformat", orden: "paso2"),
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
func ejecutar(_ programa: String, _ argumentos: [String], espera: TimeInterval) async -> (ok: Bool, texto: String) {
    await withCheckedContinuation { continuacion in
        DispatchQueue.global().async {
            let p = Process()
            p.executableURL = URL(fileURLWithPath: programa)
            p.arguments = argumentos
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

func osascript(_ guion: String, _ argumentos: [String] = [], espera: TimeInterval) async -> (ok: Bool, texto: String) {
    await ejecutar("/usr/bin/osascript", ["-e", guion] + argumentos, espera: espera)
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
    @Published var conReticula = UserDefaults.standard.object(forKey: "conReticula") as? Bool ?? true {
        didSet { UserDefaults.standard.set(conReticula, forKey: "conReticula"); Task { await actualizarVista() } }
    }
    @Published var pdf: URL?
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

    var motorEncontrado: Bool { FileManager.default.fileExists(atPath: motor.appendingPathComponent("maquetar_excel.py").path) }
    var publicacionActual: Publicacion? { publicaciones.first { $0.id == publicacion } }
    var carpetaPasos: URL? { trabajo.map { URL(fileURLWithPath: $0.deletingPathExtension().path + " (pasos)") } }
    var ejecucionVista: Ejecucion? { ejecuciones.first { $0.id == vista } ?? ejecuciones.last }
    var ejecucionEnCurso: Ejecucion? { ejecuciones.first { $0.id == enCurso } }
    var pasoActual: Paso? { pasos.indices.contains(actual) ? pasos[actual] : nil }

    init() {
        Timer.scheduledTimer(withTimeInterval: 1, repeats: true) { _ in
            Task { @MainActor [weak self] in
                guard let self else { return }
                self.excel = !NSRunningApplication.runningApplications(withBundleIdentifier: idExcel).isEmpty
                if self.enCurso != nil { self.ahora = Date() }
            }
        }
        Task {
            _ = await llamarMotor(["publicaciones"], registro: nil)
            await cargarPaletas()
        }
    }

    /// Lee otra vez las paletas de Excel (por si se ha instalado alguna mientras tanto)
    func cargarPaletas() async {
        let script = motor.appendingPathComponent("maquetar_excel.py").path
        let r = await ejecutar("/usr/bin/python3", ["-I", script, "paletas"], espera: 30)
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
        Task {
            let ok = await trabajo(id)
            terminarEjecucion(id, ok: ok)
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
        let base = url.deletingPathExtension().lastPathComponent
        let copia = base.hasSuffix(" maquetado") ? url
            : url.deletingLastPathComponent().appendingPathComponent(base + " maquetado.xlsx")
        let seguir = FileManager.default.fileExists(atPath: copia.deletingPathExtension().path + " (pasos)")
        tarea(seguir ? "Seguir con \(copia.lastPathComponent)" : "Empezar \(url.lastPathComponent)") { id in
            guard let r = await self.llamarMotor(seguir ? ["estado", copia.path] : ["empezar", url.path], registro: id) else { return false }
            self.aplicar(r)
            self.anotar(id, seguir ? "Sigue la maquetación en el paso \(self.actual)." : "Copia exacta creada: \(copia.lastPathComponent)")
            self.anotar(id, "Idioma: \(self.idioma == "en" ? "inglés" : "castellano") (por el nombre del archivo)")
            return await self.mostrar(id)
        }
    }

    // MARK: Pasos y versiones

    func hacer(_ paso: PasoMaquetacion) {
        guard let trabajo else { return }
        let lanzar = {
            self.tarea("\(paso.id). \(paso.titulo)") { id in
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

    func ir(_ n: Int) {
        guard let trabajo, pasos.indices.contains(n), n != actual else { return }
        tarea("Ir a la versión \(n)") { id in
            guard let r = await self.llamarMotor(["ir", trabajo.path, String(n)], registro: id) else { return false }
            self.aplicar(r)
            self.anotar(id, "Versión \(n): \(self.pasoActual?.titulo ?? "")")
            return await self.mostrar(id)
        }
    }

    func pdfDe(_ paso: Paso) -> URL? {
        carpetaPasos?.appendingPathComponent((paso.archivo as NSString).deletingPathExtension + (conReticula ? "" : " sin retícula") + ".pdf")
    }

    /// Tras cada cambio: vista previa de la versión actual y la copia abierta en Excel.
    private func mostrar(_ id: UUID) async -> Bool {
        let vistaOk = await generarVista(id)
        let excelOk = await abrirEnExcel(id)
        return vistaOk && excelOk
    }

    func actualizarVista() async {
        guard trabajo != nil, enCurso == nil else { return }
        let id = empezarEjecucion("Vista previa")
        let ok = await generarVista(id)
        terminarEjecucion(id, ok: ok)
    }

    /// PDF de la hoja «Gráfico» de la versión actual, hecho por Excel. Cada versión guarda el suyo.
    private func generarVista(_ id: UUID) async -> Bool {
        guard let trabajo, let paso = pasoActual, let destino = pdfDe(paso) else { return false }
        if FileManager.default.fileExists(atPath: destino.path) {
            pdf = destino
            return true
        }
        anotar(id, "Vista previa: Excel exporta la hoja «Gráfico»…")
        var args = ["vista", trabajo.path, String(paso.n)]
        if !conReticula { args.append("sin_reticula") }
        guard let r = await llamarMotor(args, registro: id), let vista = r.vista else { return false }
        let fm = FileManager.default
        try? fm.createDirectory(at: carpetaOffice, withIntermediateDirectories: true)
        let libro = carpetaOffice.appendingPathComponent("vista.xlsx"), salida = carpetaOffice.appendingPathComponent("vista.pdf")
        try? fm.removeItem(at: libro)
        try? fm.removeItem(at: salida)
        do { try fm.moveItem(at: URL(fileURLWithPath: vista), to: libro) } catch {
            anotar(id, "Error: no se pudo preparar la vista previa (\(error.localizedDescription))")
            return false
        }
        let guion = """
        on run argv
            set rutaLibro to item 1 of argv
            set rutaSalida to item 2 of argv
            tell application "Microsoft Excel"
                repeat with wb in (every workbook)
                    if full name of wb is rutaLibro then close wb saving no
                end repeat
                set wb to open workbook workbook file name rutaLibro update links do not update links
                save as (worksheet "Gráfico" of wb) filename rutaSalida file format PDF file format
                close wb saving no
            end tell
        end run
        """
        let e = await osascript(guion, [libro.path, salida.path], espera: 90)
        try? fm.removeItem(at: libro)
        guard e.ok, fm.fileExists(atPath: salida.path) else {
            anotar(id, "Error: Excel no hizo la vista previa (\(e.texto))")
            return false
        }
        try? fm.removeItem(at: destino)
        try? fm.moveItem(at: salida, to: destino)
        pdf = destino
        anotar(id, "Vista previa lista: \(destino.lastPathComponent)")
        return true
    }

    /// Cierra la copia en Excel sin guardar (la versión buena está en la carpeta de pasos) y la vuelve a
    /// abrir sin actualizar vínculos externos.
    private func abrirEnExcel(_ id: UUID) async -> Bool {
        guard let trabajo else { return false }
        let guion = """
        on run argv
            set ruta to item 1 of argv
            tell application "Microsoft Excel"
                repeat with wb in (every workbook)
                    if full name of wb is ruta then close wb saving no
                end repeat
                open workbook workbook file name ruta update links do not update links
            end tell
        end run
        """
        let r = await osascript(guion, [trabajo.path], espera: 40)
        if r.ok {
            anotar(id, "Abierta en Excel: \(trabajo.lastPathComponent)")
        } else {
            anotar(id, "⚠ Excel no abrió la copia (\(r.texto)).")
            anotar(id, "⚠ Si Excel muestra una ventana «Abrir», es que pide permiso: elige la carpeta \(trabajo.deletingLastPathComponent().lastPathComponent) y pulsa «Conceder acceso». Solo hace falta una vez.")
        }
        return r.ok
    }

    func verEnExcel() {
        tarea("Abrir en Excel") { id in await self.abrirEnExcel(id) }
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
    @Environment(\.openWindow) private var abrirVentana

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
        .onChange(of: taller.pdf) { if taller.pdf != nil { abrirVentana(id: "vista") } }
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
                    ProgressView().controlSize(.small)
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
                        .symbolEffect(.pulse, isActive: trabajando)
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
            Label("Siguientes pasos: los iremos añadiendo", systemImage: "ellipsis")
                .font(.system(size: 10.5)).foregroundStyle(.tertiary)
        }
    }
}

struct TarjetaVersiones: View {
    @ObservedObject var taller: Taller
    @Environment(\.openWindow) private var abrirVentana

    var body: some View {
        Tarjeta(numero: "VERSIONES", titulo: "Adelante y atrás", lema: "Elige una versión para verla en la vista previa y en Excel",
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
                Toggle("Retícula", isOn: $taller.conReticula).toggleStyle(.switch).controlSize(.mini)
                    .help("Ver la retícula en la vista previa (en el PDF final no sale)")
                Button { abrirVentana(id: "vista") } label: { Image(systemName: "macwindow") }
                    .help("Mostrar la vista previa")
            }
            .disabled(taller.enCurso != nil || taller.pasos.isEmpty)
            if let p = taller.pasoActual, !p.detalle.isEmpty {
                VStack(alignment: .leading, spacing: 5) {
                    Rotulo("Cambios de la versión \(p.n)")
                    ForEach(p.detalle, id: \.self) { linea in
                        HStack(alignment: .firstTextBaseline, spacing: 6) {
                            Image(systemName: linea.hasPrefix("Aviso") ? "exclamationmark.triangle.fill" : "circle.fill")
                                .font(.system(size: linea.hasPrefix("Aviso") ? 10 : 4))
                                .foregroundStyle(linea.hasPrefix("Aviso") ? Color.orange : colorVersiones)
                            Text(linea).font(.system(size: 11.5)).fixedSize(horizontal: false, vertical: true)
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
                .foregroundStyle(e.ok == true ? colorApp : .red)
        }
    }

    func color(_ linea: String) -> Color {
        if linea.hasPrefix("Error") { return .red }
        if linea.contains("⚠") || linea.hasPrefix("• Aviso") { return .orange }
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
                Button { Task { await taller.cargarPaletas() } } label: { Image(systemName: "arrow.clockwise") }
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

// MARK: - Vista previa flotante

struct VistaPDF: NSViewRepresentable {
    let url: URL?

    func makeNSView(context: Context) -> PDFView {
        let v = PDFView()
        v.autoScales = true
        v.displayMode = .singlePage
        v.displaysPageBreaks = false
        v.backgroundColor = .windowBackgroundColor
        return v
    }

    func updateNSView(_ v: PDFView, context: Context) {
        guard v.document?.documentURL != url else { return }
        v.document = url.flatMap { PDFDocument(url: $0) }
        v.autoScales = true
    }
}

/// Pone la ventana que lo contiene por encima de las demás (también de Excel)
struct Flotante: NSViewRepresentable {
    func makeNSView(context: Context) -> NSView {
        let v = NSView()
        DispatchQueue.main.async {
            v.window?.level = .floating
            v.window?.collectionBehavior.insert(.fullScreenAuxiliary)
        }
        return v
    }

    func updateNSView(_ nsView: NSView, context: Context) {}
}

struct VentanaVista: View {
    @ObservedObject var taller: Taller

    var body: some View {
        ZStack {
            if taller.pdf != nil {
                VistaPDF(url: taller.pdf)
            } else {
                VStack(spacing: 8) {
                    Image(systemName: "chart.bar.doc.horizontal").font(.system(size: 30)).foregroundStyle(.tertiary)
                    Text("Aquí se verá el gráfico").foregroundStyle(.secondary)
                }
            }
            if taller.enCurso != nil {
                ProgressView().controlSize(.small).padding(8)
                    .background(.regularMaterial, in: Capsule())
                    .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .topTrailing)
                    .padding(8)
            }
        }
        .background(Flotante())
        .navigationTitle(taller.pasoActual.map { String(format: "%02d  %@", $0.n, $0.titulo) } ?? "Vista previa")
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
        .commands {
            CommandGroup(replacing: .newItem) {
                Button("Elegir Excel…") { taller.elegir() }.keyboardShortcut("o")
                Button("Nueva publicación…") { taller.nuevaPublicacion() }.keyboardShortcut("n")
            }
        }

        Window("Vista previa", id: "vista") {
            VentanaVista(taller: taller)
                .frame(minWidth: 320, minHeight: 420)
        }
        .defaultSize(width: 520, height: 720)
        .defaultPosition(.trailing)
    }
}
