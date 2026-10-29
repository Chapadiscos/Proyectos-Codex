// Crear índices gráficos: del PDF de un informe al índice de cuadros, gráficos,
// esquemas y recuadros maquetado en InDesign.
// 1. Pide el PDF (se abre el selector nada más arrancar).
// 2. Extrae los datos (scripts/generar_indice.sh --solo-extraer). Si hay avisos,
//    se para para revisarlos y, si hace falta, corregir el .json.
// 3. Maqueta en InDesign (--solo-maquetar) y muestra el PDF del índice.
// La ventana enseña a la izquierda el registro del proceso en directo y a la
// derecha el índice resultante.
// También se puede soltar un PDF sobre el icono de la app.
// Compilar: app/compilar_app.sh

import AppKit
import PDFKit
import SwiftUI

/// Carpeta del proyecto: la de la app si está junto a scripts/, si no la fija.
let proyecto: URL = {
    let junto = Bundle.main.bundleURL.deletingLastPathComponent()
    if FileManager.default.fileExists(atPath: junto.appendingPathComponent("scripts/generar_indice.sh").path) {
        return junto
    }
    return URL(fileURLWithPath: "/Volumes/DATOS/Proyectos Codex/Extraer Indices PDF BdE + Hipervinculos")
}()
let indesign = "Adobe InDesign 2026"

struct Linea: Identifiable {
    enum Tipo { case normal, paso, aviso, error, ok }
    let id: Int
    let texto: String
    let tipo: Tipo
}

@MainActor
final class Proceso: ObservableObject {
    enum Estado: Equatable {
        case inicio
        case trabajando(String)
        case revisar     // extracción con avisos: se espera al usuario
        case terminado
        case error(String)
    }

    @Published var estado: Estado = .inicio
    @Published var lineas: [Linea] = []
    @Published var avisos: [String] = []
    @Published var documento: PDFDocument?
    @Published var pdfOrigen: URL?

    private var enAvisos = false
    private var ultimoPaso: (() -> Void)?

    private var nombre: String { pdfOrigen?.deletingPathExtension().lastPathComponent ?? "" }
    var json: URL { proyecto.appendingPathComponent("datos/indice_\(nombre).json") }
    var indd: URL { proyecto.appendingPathComponent("salida/Indice_\(nombre).indd") }
    var pdfSalida: URL { proyecto.appendingPathComponent("salida/Indice_\(nombre).pdf") }

    var trabajando: Bool {
        if case .trabajando = estado { return true }
        return false
    }

    // MARK: Pasos

    func elegirPDF() {
        let panel = NSOpenPanel()
        panel.title = "Elige el PDF del informe"
        panel.message = "Elige el PDF final del informe del que sacar el índice de cuadros, gráficos, esquemas y recuadros"
        panel.allowedContentTypes = [.pdf]
        panel.directoryURL = UserDefaults.standard.url(forKey: "ultimaCarpeta")
            ?? proyecto.appendingPathComponent("entrada")
        guard panel.runModal() == .OK, let url = panel.url else { return }
        UserDefaults.standard.set(url.deletingLastPathComponent(), forKey: "ultimaCarpeta")
        empezar(con: url)
    }

    func empezar(con url: URL) {
        pdfOrigen = url
        extraer()
    }

    func extraer() {
        lineas = []
        avisos = []
        documento = nil
        ultimoPaso = { [weak self] in self?.extraer() }
        ejecutar(["--solo-extraer"], titulo: "Extrayendo los datos del PDF…") { [weak self] codigo in
            guard let self else { return }
            if codigo != 0 {
                self.estado = .error("No se han podido extraer los datos del PDF.")
            } else if self.lineas.contains(where: { $0.texto.contains("No se ha encontrado ninguna etiqueta") }) {
                self.estado = .error("No se ha encontrado ningún cuadro, gráfico, esquema ni recuadro en este PDF.")
            } else if !self.avisos.isEmpty {
                self.estado = .revisar
            } else {
                self.maquetar()
            }
        }
    }

    func maquetar() {
        documento = nil
        ultimoPaso = { [weak self] in self?.maquetar() }
        ejecutar(["--solo-maquetar"], titulo: "Maquetando el índice en InDesign…") { [weak self] codigo in
            guard let self else { return }
            if codigo == 0, let doc = PDFDocument(url: self.pdfSalida) {
                self.documento = doc
                self.estado = .terminado
            } else {
                self.estado = .error("InDesign no ha podido maquetar el índice.")
            }
        }
    }

    func reintentar() { ultimoPaso?() }

    // MARK: Acciones sobre el resultado

    func editarDatos() { abrir(["-e", json.path]) }
    func abrirEnInDesign() { abrir(["-a", indesign, indd.path]) }
    func mostrarEnFinder() { NSWorkspace.shared.activateFileViewerSelecting([indd]) }
    func abrirPDF() { NSWorkspace.shared.open(pdfSalida) }

    private func abrir(_ argumentos: [String]) {
        let p = Process()
        p.executableURL = URL(fileURLWithPath: "/usr/bin/open")
        p.arguments = argumentos
        try? p.run()
    }

    // MARK: Ejecución del script, con su salida línea a línea en la ventana

    private func ejecutar(_ opciones: [String], titulo: String, fin: @escaping (Int32) -> Void) {
        guard let pdfOrigen else { return }
        estado = .trabajando(titulo)
        enAvisos = false
        if !lineas.isEmpty { anadir("") }

        let p = Process()
        p.executableURL = URL(fileURLWithPath: "/bin/bash")
        p.arguments = [proyecto.appendingPathComponent("scripts/generar_indice.sh").path] + opciones + [pdfOrigen.path]
        p.currentDirectoryURL = proyecto
        var entorno = ProcessInfo.processInfo.environment
        entorno["DESDE_APP"] = "1"
        entorno["INDESIGN_APP"] = indesign
        p.environment = entorno

        let tuberia = Pipe()
        p.standardOutput = tuberia
        p.standardError = tuberia
        var pendiente = Data()
        // Se parte por saltos de línea en bytes, para no cortar una letra
        // acentuada (dos bytes en UTF-8) entre dos lecturas.
        let trocear: (Data, Bool) -> Void = { [weak self] datos, final in
            pendiente.append(datos)
            var completas: [String] = []
            while let salto = pendiente.firstIndex(of: 0x0A) {
                completas.append(String(decoding: pendiente[pendiente.startIndex..<salto], as: UTF8.self))
                pendiente.removeSubrange(pendiente.startIndex...salto)
            }
            if final && !pendiente.isEmpty {
                completas.append(String(decoding: pendiente, as: UTF8.self))
                pendiente.removeAll()
            }
            if !completas.isEmpty {
                DispatchQueue.main.async { completas.forEach { self?.anadir($0) } }
            }
        }
        let cola = DispatchQueue(label: "salida")
        tuberia.fileHandleForReading.readabilityHandler = { handle in
            let datos = handle.availableData
            cola.sync { trocear(datos, false) }
        }
        p.terminationHandler = { proceso in
            tuberia.fileHandleForReading.readabilityHandler = nil
            let resto = tuberia.fileHandleForReading.readDataToEndOfFile()
            cola.sync { trocear(resto, true) }
            let codigo = proceso.terminationStatus
            DispatchQueue.main.async { fin(codigo) }
        }
        do {
            try p.run()
        } catch {
            anadir("ERROR: no se ha podido lanzar el script: \(error.localizedDescription)")
            estado = .error("No se ha podido lanzar el script.")
        }
    }

    private func anadir(_ texto: String) {
        let tipo: Linea.Tipo
        if texto.hasPrefix("Avisos para revisar") {
            enAvisos = true
            tipo = .aviso
        } else if enAvisos && texto.hasPrefix("  - ") {
            avisos.append(String(texto.dropFirst(4)))
            tipo = .aviso
        } else if texto.hasPrefix("== ") {
            tipo = .paso
        } else if texto.hasPrefix("ERROR") || texto.hasPrefix("!!") || texto.contains("Traceback") {
            tipo = .error
        } else if texto.contains("ADVERTENCIA") {
            tipo = .aviso
        } else if texto.hasPrefix("Listo") {
            tipo = .ok
        } else {
            tipo = .normal
        }
        lineas.append(Linea(id: lineas.count, texto: texto, tipo: tipo))
    }
}

// MARK: - Ventana

struct VistaPDF: NSViewRepresentable {
    let documento: PDFDocument

    func makeNSView(context: Context) -> PDFView {
        let vista = PDFView()
        vista.autoScales = true
        vista.displayMode = .singlePageContinuous
        vista.backgroundColor = .windowBackgroundColor
        return vista
    }

    func updateNSView(_ vista: PDFView, context: Context) {
        if vista.document !== documento { vista.document = documento }
    }
}

struct Ventana: View {
    @ObservedObject var proceso: Proceso

    var body: some View {
        HSplitView {
            VStack(alignment: .leading, spacing: 0) {
                cabecera
                Divider()
                registro
                Divider()
                botones
            }
            .frame(minWidth: 480, idealWidth: 560)

            Group {
                if let doc = proceso.documento {
                    VistaPDF(documento: doc)
                } else {
                    VStack(spacing: 8) {
                        Image(systemName: "doc.text.magnifyingglass")
                            .font(.system(size: 44))
                        Text("Aquí aparecerá el índice maquetado")
                    }
                    .foregroundStyle(.secondary)
                    .frame(maxWidth: .infinity, maxHeight: .infinity)
                }
            }
            .frame(minWidth: 380, idealWidth: 520)
        }
        .frame(minWidth: 900, minHeight: 600)
    }

    private var cabecera: some View {
        HStack(spacing: 10) {
            VStack(alignment: .leading, spacing: 2) {
                Text(proceso.pdfOrigen?.lastPathComponent ?? "Ningún PDF elegido")
                    .font(.headline)
                    .lineLimit(1)
                    .truncationMode(.middle)
                Text(textoEstado)
                    .font(.subheadline)
                    .foregroundStyle(colorEstado)
            }
            Spacer()
            if proceso.trabajando {
                ProgressView().controlSize(.small)
            }
        }
        .padding(12)
    }

    private var registro: some View {
        ScrollViewReader { desplazar in
            ScrollView {
                LazyVStack(alignment: .leading, spacing: 1) {
                    ForEach(proceso.lineas) { linea in
                        Text(linea.texto.isEmpty ? " " : linea.texto)
                            .font(.system(size: 12, design: .monospaced))
                            .fontWeight(linea.tipo == .paso ? .semibold : .regular)
                            .foregroundStyle(color(linea.tipo))
                            .frame(maxWidth: .infinity, alignment: .leading)
                            .id(linea.id)
                    }
                }
                .textSelection(.enabled)
                .padding(10)
            }
            .background(Color(nsColor: .textBackgroundColor))
            .onChange(of: proceso.lineas.count) { _, _ in
                if let ultima = proceso.lineas.last { desplazar.scrollTo(ultima.id, anchor: .bottom) }
            }
        }
    }

    @ViewBuilder
    private var botones: some View {
        HStack(spacing: 8) {
            switch proceso.estado {
            case .inicio:
                Spacer()
                Button("Elegir PDF…") { proceso.elegirPDF() }
                    .keyboardShortcut(.defaultAction)
            case .trabajando:
                Spacer()
                Button("Elegir PDF…") {}.disabled(true)
            case .revisar:
                Button("Otro PDF…") { proceso.elegirPDF() }
                Spacer()
                Button("Corregir datos…") { proceso.editarDatos() }
                Button("Maquetar") { proceso.maquetar() }
                    .keyboardShortcut(.defaultAction)
            case .terminado:
                Button("Otro PDF…") { proceso.elegirPDF() }
                Spacer()
                Button("Corregir datos…") { proceso.editarDatos() }
                Button("Volver a maquetar") { proceso.maquetar() }
                Menu("Ver") {
                    Button("PDF en Vista Previa") { proceso.abrirPDF() }
                    Button("Mostrar en el Finder") { proceso.mostrarEnFinder() }
                }
                .fixedSize()
                Button("Abrir en InDesign") { proceso.abrirEnInDesign() }
                    .keyboardShortcut(.defaultAction)
            case .error:
                Button("Otro PDF…") { proceso.elegirPDF() }
                Spacer()
                if FileManager.default.fileExists(atPath: proceso.json.path) {
                    Button("Corregir datos…") { proceso.editarDatos() }
                }
                Button("Reintentar") { proceso.reintentar() }
                    .keyboardShortcut(.defaultAction)
            }
        }
        .padding(12)
    }

    private var textoEstado: String {
        switch proceso.estado {
        case .inicio: return "Elige el PDF del informe para empezar"
        case .trabajando(let t): return t
        case .revisar:
            let n = proceso.avisos.count
            return "\(n) aviso\(n == 1 ? "" : "s") para revisar. Corrige los datos si hace falta y pulsa Maquetar"
        case .terminado: return "Índice listo: \(proceso.indd.lastPathComponent)"
        case .error(let t): return t
        }
    }

    private var colorEstado: Color {
        switch proceso.estado {
        case .revisar: return .orange
        case .terminado: return .green
        case .error: return .red
        default: return .secondary
        }
    }

    private func color(_ tipo: Linea.Tipo) -> Color {
        switch tipo {
        case .normal: return .primary
        case .paso: return .accentColor
        case .aviso: return .orange
        case .error: return .red
        case .ok: return .green
        }
    }
}

// MARK: - Arranque
// La ventana se crea a mano (sin la escena de SwiftUI) para que aparezca también
// cuando la app se abre con un PDF: arrastrándolo al icono o con
// open -a "Crear índices gráficos.app" ruta/Informe.pdf

@main
@MainActor
final class Delegado: NSObject, NSApplicationDelegate {
    let proceso = Proceso()
    var ventana: NSWindow?
    var pdfInicial: URL?

    static func main() {
        let app = NSApplication.shared
        let delegado = Delegado()
        app.delegate = delegado
        app.setActivationPolicy(.regular)
        app.run()
    }

    func applicationWillFinishLaunching(_ notification: Notification) {
        NSApp.mainMenu = menu()
    }

    func applicationDidFinishLaunching(_ notification: Notification) {
        let v = NSWindow(contentRect: NSRect(x: 0, y: 0, width: 1100, height: 720),
                         styleMask: [.titled, .closable, .miniaturizable, .resizable],
                         backing: .buffered, defer: false)
        v.title = "Crear índices gráficos"
        v.contentView = NSHostingView(rootView: Ventana(proceso: proceso))
        v.isReleasedWhenClosed = false
        v.setFrameAutosaveName("principal")
        if !v.setFrameUsingName("principal") { v.center() }
        v.makeKeyAndOrderFront(nil)
        ventana = v
        NSApp.activate(ignoringOtherApps: true)

        if let pdf = pdfInicial {
            proceso.empezar(con: pdf)
        } else {
            DispatchQueue.main.async { self.proceso.elegirPDF() }
        }
    }

    // PDF soltado sobre el icono (al arrancar llega antes que DidFinishLaunching)
    func application(_ sender: NSApplication, open urls: [URL]) {
        guard let pdf = urls.first(where: { $0.pathExtension.lowercased() == "pdf" }) else { return }
        if ventana == nil {
            pdfInicial = pdf
        } else if !proceso.trabajando {
            proceso.empezar(con: pdf)
        }
    }

    func applicationShouldTerminateAfterLastWindowClosed(_ sender: NSApplication) -> Bool { true }

    @objc func elegirPDF() {
        if !proceso.trabajando { proceso.elegirPDF() }
    }

    private func menu() -> NSMenu {
        let principal = NSMenu()

        let app = NSMenu()
        app.addItem(withTitle: "Ocultar Crear índices gráficos", action: #selector(NSApplication.hide(_:)), keyEquivalent: "h")
        app.addItem(.separator())
        app.addItem(withTitle: "Salir de Crear índices gráficos", action: #selector(NSApplication.terminate(_:)), keyEquivalent: "q")

        let archivo = NSMenu(title: "Archivo")
        archivo.addItem(withTitle: "Elegir PDF…", action: #selector(elegirPDF), keyEquivalent: "o").target = self
        archivo.addItem(.separator())
        archivo.addItem(withTitle: "Cerrar", action: #selector(NSWindow.performClose(_:)), keyEquivalent: "w")

        let edicion = NSMenu(title: "Edición")
        edicion.addItem(withTitle: "Copiar", action: #selector(NSText.copy(_:)), keyEquivalent: "c")
        edicion.addItem(withTitle: "Seleccionar todo", action: #selector(NSText.selectAll(_:)), keyEquivalent: "a")

        for submenu in [app, archivo, edicion] {
            let item = NSMenuItem()
            item.submenu = submenu
            principal.addItem(item)
        }
        return principal
    }
}
