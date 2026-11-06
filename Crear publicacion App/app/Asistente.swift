// Ventana «Afinar con Claude»: conversación con Claude Code sobre la publicación elegida, para
// dejar mejor definida su configuración (.toml) y los estilos de su maqueta.
// Usa el Claude Code de la extensión de VS Code sin interfaz (-p, como formatear/claude.py),
// en la carpeta del motor, y sigue la misma sesión de un mensaje a otro (--resume). Antes de
// cada petición guarda una copia de la configuración y la maqueta para poder deshacer.

import SwiftUI
import AppKit

// MARK: - Modelo

struct Mensaje: Identifiable, Codable, Equatable {
    enum Tipo: String, Codable { case usuario, claude, accion, aviso }
    var id = UUID()
    let tipo: Tipo
    var texto: String
    var fecha = Date()
}

/// Conversación guardada de una publicación
struct Hilo: Codable {
    var sesion: String?
    var mensajes: [Mensaje] = []
}

/// Carpeta de la app en Application Support: conversaciones y copias
let apoyo: URL = {
    let u = FileManager.default.homeDirectoryForCurrentUser.appendingPathComponent("Library/Application Support/Crear Publicacion")
    try? FileManager.default.createDirectory(at: u, withIntermediateDirectories: true)
    return u
}()

/// El Claude Code de la extensión de VS Code más reciente
func claudeEjecutable() -> URL? {
    let ext = FileManager.default.homeDirectoryForCurrentUser.appendingPathComponent(".vscode/extensions")
    let carpetas = (try? FileManager.default.contentsOfDirectory(at: ext, includingPropertiesForKeys: [.contentModificationDateKey])) ?? []
    return carpetas
        .filter { $0.lastPathComponent.hasPrefix("anthropic.claude-code-") }
        .sorted { a, b in
            let fa = (try? a.resourceValues(forKeys: [.contentModificationDateKey]).contentModificationDate) ?? .distantPast
            let fb = (try? b.resourceValues(forKeys: [.contentModificationDateKey]).contentModificationDate) ?? .distantPast
            return fa > fb
        }
        .map { $0.appendingPathComponent("resources/native-binary/claude") }
        .first { FileManager.default.isExecutableFile(atPath: $0.path) }
}

// MARK: - Asistente

@MainActor
final class Asistente: ObservableObject {
    @Published var publicacion: Publicacion?
    @Published var mensajes: [Mensaje] = []
    @Published var trabajando = false
    @Published var inicio = Date()
    @Published var hayCopias = false

    private var sesion: String?
    private var proceso: Process?
    private var detenido = false
    private var datos: DatosPublicacion?

    var slugActual: String { publicacion.map { URL(fileURLWithPath: $0.ruta).deletingPathExtension().lastPathComponent } ?? "" }
    private var archivoHilo: URL { apoyo.appendingPathComponent("conversaciones/\(slugActual).json") }
    private var carpetaCopias: URL { apoyo.appendingPathComponent("copias/\(slugActual)") }

    /// Carga la conversación de la publicación (cada una tiene la suya)
    func cargar(_ p: Publicacion?, datos d: DatosPublicacion?) {
        guard p?.ruta != publicacion?.ruta else { datos = d; return }
        guard !trabajando else { return }
        publicacion = p
        datos = d
        let hilo = (try? Data(contentsOf: archivoHilo)).flatMap { try? JSONDecoder().decode(Hilo.self, from: $0) } ?? Hilo()
        sesion = hilo.sesion
        mensajes = hilo.mensajes
        actualizarCopias()
    }

    private func guardar() {
        try? FileManager.default.createDirectory(at: archivoHilo.deletingLastPathComponent(), withIntermediateDirectories: true)
        if let d = try? JSONEncoder().encode(Hilo(sesion: sesion, mensajes: mensajes)) { try? d.write(to: archivoHilo) }
    }

    func nuevaConversacion() {
        guard !trabajando else { return }
        sesion = nil
        mensajes = []
        guardar()
    }

    // MARK: Copias para deshacer

    /// Los archivos de la publicación que Claude puede cambiar
    private var archivos: [URL] {
        guard let p = publicacion else { return [] }
        return [URL(fileURLWithPath: p.ruta)] + [datos?.maqueta].compactMap { $0 }
            .filter { FileManager.default.fileExists(atPath: $0.path) }
    }

    private func copias() -> [URL] {
        ((try? FileManager.default.contentsOfDirectory(at: carpetaCopias, includingPropertiesForKeys: nil)) ?? [])
            .filter { $0.hasDirectoryPath }
            .sorted { $0.lastPathComponent > $1.lastPathComponent }
    }

    private func actualizarCopias() { hayCopias = !copias().isEmpty }

    private func huella(_ u: URL) -> String {
        let a = try? FileManager.default.attributesOfItem(atPath: u.path)
        return "\((a?[.size] as? Int) ?? 0)-\((a?[.modificationDate] as? Date)?.timeIntervalSince1970 ?? 0)"
    }

    /// Copia la configuración y la maqueta antes de una petición
    private func copiar() -> (URL, [String: String])? {
        let f = DateFormatter()
        f.dateFormat = "yyyyMMdd-HHmmss"
        let destino = carpetaCopias.appendingPathComponent(f.string(from: Date()))
        do {
            try FileManager.default.createDirectory(at: destino, withIntermediateDirectories: true)
            var huellas: [String: String] = [:]
            for a in archivos {
                try FileManager.default.copyItem(at: a, to: destino.appendingPathComponent(a.lastPathComponent))
                huellas[a.path] = huella(a)
            }
            return (destino, huellas)
        } catch { return nil }
    }

    /// Tras la respuesta: si nada ha cambiado, la copia sobra; si algo cambió, se avisa
    private func revisarCambios(_ copia: (URL, [String: String])?) {
        guard let (carpeta, antes) = copia else { return }
        let cambiados = archivos.filter { antes[$0.path] != huella($0) }
        if cambiados.isEmpty {
            try? FileManager.default.removeItem(at: carpeta)
        } else {
            mensajes.append(Mensaje(tipo: .aviso, texto: "Ha cambiado: " + cambiados.map(\.lastPathComponent).joined(separator: ", ") +
                                    ". «Deshacer último cambio» lo devuelve a como estaba."))
            // Solo las 20 últimas
            for vieja in copias().dropFirst(20) { try? FileManager.default.removeItem(at: vieja) }
        }
        actualizarCopias()
    }

    /// Devuelve la configuración y la maqueta a la última copia; nil si fue bien
    func deshacer(abiertos: [String]) -> String? {
        guard let ultima = copias().first else { return "No hay cambios que deshacer." }
        if let maqueta = datos?.maqueta, abiertos.contains(maqueta.path) {
            return "La maqueta «\(maqueta.lastPathComponent)» está abierta en InDesign: ciérrala antes de deshacer."
        }
        for a in archivos {
            let copia = ultima.appendingPathComponent(a.lastPathComponent)
            guard FileManager.default.fileExists(atPath: copia.path) else { continue }
            do {
                _ = try FileManager.default.replaceItemAt(a, withItemAt: copia)
            } catch { return "No se ha podido recuperar \(a.lastPathComponent): \(error.localizedDescription)" }
        }
        try? FileManager.default.removeItem(at: ultima)
        let hora = String(ultima.lastPathComponent.suffix(6))
        mensajes.append(Mensaje(tipo: .aviso, texto: "Deshecho: la configuración y la maqueta vuelven a como estaban a las " +
                                "\(hora.prefix(2)):\(hora.dropFirst(2).prefix(2)). Claude no lo sabe: díselo si seguís hablando de ello."))
        guardar()
        actualizarCopias()
        return nil
    }

    // MARK: Conversación

    private func instrucciones() -> String {
        guard let p = publicacion else { return "" }
        let maqueta = datos?.maqueta?.path ?? "(sin maqueta)"
        let maquetado = datos?.maquetado ?? ""
        return """
        Estás dentro de la app «Crear Publicación», que pasa capítulos de Word a InDesign en tres pasos \
        (Galerada, Tipografía y Cierre) con el motor de esta carpeta. El usuario es maquetador profesional y te habla \
        para dejar mejor definida UNA publicación. Responde siempre en español, breve y sin tecnicismos de programación.

        Publicación: «\(p.nombre)»
        - Configuración: \(p.ruta)
        - Maqueta (la que usa la galerada, en este proyecto): \(maqueta)
        - Maquetado de origen (en el servidor): \(maquetado.isEmpty ? "(no consta)" : maquetado)

        Qué es cada cosa:
        - La configuración (.toml) dice qué estilo de la maqueta corresponde a cada papel: [parrafo] (título, ladillos, \
        texto, viñetas, tablas, pies…), [caracter] (negrita, cursiva, superíndice…), [caracter_por_grupo], [tabla], \
        [figuras], [resaltar] (palabras que se marcan al importar), [citas], [reglas]. Los comentarios de \
        publicaciones/maqueta-base.toml explican cada clave. Los estilos en grupos se escriben «Grupo/Estilo».
        - La maqueta (.indd) tiene los estilos de párrafo, carácter, tabla, celda y objeto, las muestras y las maestras.

        Puedes:
        - Leer cualquier archivo del motor para entender cómo funciona (importar.py, formatear/, jsx/).
        - Editar la configuración de esta publicación.
        - Cambiar estilos de su maqueta con InDesign 2026: escribe un .jsx en la carpeta temporal del Mac \
        (la de `getconf DARWIN_USER_TEMP_DIR`; InDesign no puede leer /private/tmp/claude-*) y lánzalo con \
        `osascript -e 'tell application id "com.adobe.InDesign" to do script (POSIX file "…") language javascript with arguments {…}'`. \
        Abre la maqueta sin ventana con app.open(archivo, false), cámbiala, guárdala y ciérrala. Si ya está abierta \
        en InDesign, pide al usuario que la cierre; nunca cierres documentos que haya abierto él. \
        Trampas de ExtendScript: dentro de una función `arguments` son los de la función (guárdalos fuera); no hay \
        Array.map ni forEach; los estilos raíz («[Párrafo básico]») fallan al leer casi cualquier propiedad.
        - Si te pide cambiar también el maquetado del servidor, guarda una copia nueva al lado; no lo sobrescribas.

        No toques (salvo que el usuario lo pida expresamente, avisando de que afecta a todas las publicaciones): \
        el código del motor (.py, jsx/), las demás publicaciones, publicaciones/ortotipografia.toml y \
        publicaciones/diccionario.txt, que son comunes.

        Forma de trabajar: si la petición es una decisión editorial dudosa, pregunta antes. Si el cambio es grande, \
        di primero qué vas a hacer. Al terminar, resume lo que has cambiado en una a tres líneas. La app guarda una \
        copia antes de cada petición y el usuario puede deshacer el último cambio.
        """
    }

    func enviar(_ texto: String) {
        let t = texto.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !t.isEmpty, !trabajando, publicacion != nil else { return }
        guard let claude = claudeEjecutable() else {
            mensajes.append(Mensaje(tipo: .aviso, texto: "No encuentro Claude Code: hace falta la extensión de Claude en VS Code."))
            return
        }
        mensajes.append(Mensaje(tipo: .usuario, texto: t))
        guardar()
        trabajando = true
        detenido = false
        inicio = Date()
        let copia = copiar()

        let p = Process()
        p.executableURL = claude
        var args = ["-p", t, "--output-format", "stream-json", "--verbose",
                    "--append-system-prompt", instrucciones(),
                    "--permission-mode", "acceptEdits",
                    "--allowedTools", "Read", "Edit", "Write", "Glob", "Grep",
                    "Bash(osascript:*)", "Bash(getconf:*)", "Bash(ls:*)", "Bash(cat:*)", "Bash(mkdir:*)",
                    "Bash(\(python):*)"]
        if let sesion { args += ["--resume", sesion] }
        p.arguments = args
        p.currentDirectoryURL = motor
        var entorno = ProcessInfo.processInfo.environment
        entorno["LANG"] = "es_ES.UTF-8"
        p.environment = entorno
        let tubo = Pipe()
        p.standardOutput = tubo
        p.standardError = tubo
        p.standardInput = FileHandle.nullDevice
        do { try p.run() } catch {
            mensajes.append(Mensaje(tipo: .aviso, texto: "No se ha podido lanzar Claude: \(error.localizedDescription)"))
            trabajando = false
            revisarCambios(copia)
            return
        }
        proceso = p
        DispatchQueue.global().async {
            let lector = tubo.fileHandleForReading
            var pendiente = Data()
            while true {
                let d = lector.availableData
                if d.isEmpty { break }
                pendiente.append(d)
                while let fin = pendiente.firstIndex(of: 0x0A) {
                    let linea = Data(pendiente[pendiente.startIndex..<fin])
                    pendiente = Data(pendiente[pendiente.index(after: fin)...])
                    DispatchQueue.main.async { MainActor.assumeIsolated { self.procesar(linea) } }
                }
            }
            p.waitUntilExit()
            let estado = p.terminationStatus
            DispatchQueue.main.async { MainActor.assumeIsolated { self.terminar(estado, copia) } }
        }
    }

    /// Una línea de stream-json: texto de Claude, herramientas que usa y el resultado
    private func procesar(_ linea: Data) {
        guard let o = (try? JSONSerialization.jsonObject(with: linea)) as? [String: Any] else {
            let t = String(decoding: linea, as: UTF8.self).trimmingCharacters(in: .whitespaces)
            if !t.isEmpty { mensajes.append(Mensaje(tipo: .aviso, texto: t)) }
            return
        }
        if let s = o["session_id"] as? String { sesion = s }
        switch o["type"] as? String {
        case "assistant":
            let contenido = ((o["message"] as? [String: Any])?["content"] as? [[String: Any]]) ?? []
            for c in contenido {
                if c["type"] as? String == "text", let t = c["text"] as? String, !t.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty {
                    mensajes.append(Mensaje(tipo: .claude, texto: t))
                } else if c["type"] as? String == "tool_use" {
                    mensajes.append(Mensaje(tipo: .accion, texto: describir(c["name"] as? String ?? "", c["input"] as? [String: Any] ?? [:])))
                }
            }
        case "result":
            if o["is_error"] as? Bool == true, let r = o["result"] as? String {
                mensajes.append(Mensaje(tipo: .aviso, texto: r))
            }
            if let negados = o["permission_denials"] as? [[String: Any]], !negados.isEmpty {
                let que = negados.compactMap { $0["tool_name"] as? String }.joined(separator: ", ")
                mensajes.append(Mensaje(tipo: .aviso, texto: "Claude quería usar \(que) y la app no se lo permite."))
            }
        default:
            break
        }
        guardar()
    }

    private func describir(_ herramienta: String, _ e: [String: Any]) -> String {
        let archivo = (e["file_path"] as? String).map { URL(fileURLWithPath: $0).lastPathComponent } ?? ""
        switch herramienta {
        case "Read": return "Leyendo \(archivo)"
        case "Edit", "MultiEdit": return "Editando \(archivo)"
        case "Write": return "Escribiendo \(archivo)"
        case "Glob", "Grep": return "Buscando en el motor"
        case "Bash":
            let orden = e["command"] as? String ?? ""
            if orden.contains("osascript") { return "Trabajando en InDesign" + ((e["description"] as? String).map { ": " + $0 } ?? "") }
            return (e["description"] as? String) ?? "Ejecutando una orden"
        case "TodoWrite": return "Organizando los pasos"
        default: return herramienta
        }
    }

    private func terminar(_ estado: Int32, _ copia: (URL, [String: String])?) {
        proceso = nil
        trabajando = false
        if detenido { mensajes.append(Mensaje(tipo: .aviso, texto: "Detenido.")) }
        else if estado != 0 && mensajes.last?.tipo == .usuario {
            mensajes.append(Mensaje(tipo: .aviso, texto: "Claude no ha contestado (código \(estado))."))
        }
        revisarCambios(copia)
        guardar()
        if !NSApp.isActive { NSApp.requestUserAttention(.informationalRequest) }
    }

    func detener() {
        guard let p = proceso, p.isRunning else { return }
        detenido = true
        let pkill = Process()
        pkill.executableURL = URL(fileURLWithPath: "/usr/bin/pkill")
        pkill.arguments = ["-TERM", "-P", String(p.processIdentifier)]
        try? pkill.run()
        pkill.waitUntilExit()
        p.terminate()
    }
}

// MARK: - Ventana

struct VentanaClaude: View {
    @ObservedObject var taller: Taller
    @ObservedObject var asistente: Asistente
    @State private var texto = ""
    @State private var aviso: String?
    @State private var confirmarDeshacer = false
    @FocusState private var escribiendo: Bool

    private let ideas = [
        "Revisa la configuración y dime qué falta o qué ves raro",
        "¿Qué estilo se aplica a cada parte del capítulo al importar?",
        "Las viñetas deben ir sin sangría, como en los capítulos de 2025",
        "Añade «Esquema» y «Vídeo» a las palabras que se resaltan",
    ]

    var body: some View {
        VStack(spacing: 0) {
            cabecera
            Divider()
            conversacion
            Divider()
            entrada
        }
        .background(Color(nsColor: .windowBackgroundColor))
        .onAppear { cargar() }
        .onChange(of: taller.publicacion) { cargar() }
        .alert("No se puede deshacer", isPresented: Binding(get: { aviso != nil }, set: { if !$0 { aviso = nil } })) {
            Button("Aceptar") {}
        } message: { Text(aviso ?? "") }
        .alert("¿Deshacer el último cambio?", isPresented: $confirmarDeshacer) {
            Button("Deshacer") { aviso = asistente.deshacer(abiertos: taller.documentos.map(\.ruta)) }
            Button("Cancelar", role: .cancel) {}
        } message: {
            Text("La configuración y la maqueta de «\(asistente.publicacion?.nombre ?? "")» vuelven a como estaban antes de la última petición que las cambió.")
        }
    }

    private func cargar() {
        asistente.cargar(taller.publicacionActual, datos: taller.publicacionActual.map(taller.datos))
    }

    var cabecera: some View {
        HStack(spacing: 12) {
            ZStack {
                RoundedRectangle(cornerRadius: 10)
                    .fill(LinearGradient(colors: [Color(red: 0.85, green: 0.47, blue: 0.34), Color(red: 0.58, green: 0.33, blue: 0.93)],
                                         startPoint: .topLeading, endPoint: .bottomTrailing))
                Image(systemName: "sparkles").font(.system(size: 18, weight: .semibold)).foregroundStyle(.white)
            }
            .frame(width: 38, height: 38)
            VStack(alignment: .leading, spacing: 2) {
                Text("Afinar con Claude").font(.system(size: 15, weight: .bold))
                Text(asistente.publicacion.map { "Publicación: \($0.nombre)" } ?? "Elige una publicación en la ventana principal")
                    .font(.system(size: 11.5)).foregroundStyle(.secondary).lineLimit(1)
            }
            Spacer()
            if asistente.hayCopias {
                Button { confirmarDeshacer = true } label: { Label("Deshacer último cambio", systemImage: "arrow.uturn.backward") }
                    .disabled(asistente.trabajando)
            }
            Menu {
                Button("Nueva conversación") { asistente.nuevaConversacion() }
                    .disabled(asistente.trabajando || asistente.mensajes.isEmpty)
                Divider()
                if let p = asistente.publicacion {
                    Button("Mostrar la configuración en el Finder") {
                        NSWorkspace.shared.activateFileViewerSelecting([URL(fileURLWithPath: p.ruta)])
                    }
                    if let m = taller.datos(p).maqueta {
                        Button("Mostrar la maqueta en el Finder") { NSWorkspace.shared.activateFileViewerSelecting([m]) }
                    }
                }
            } label: { Image(systemName: "ellipsis.circle") }
            .menuStyle(.borderlessButton)
            .fixedSize()
        }
        .padding(.horizontal, 16)
        .padding(.vertical, 12)
    }

    var conversacion: some View {
        ScrollViewReader { proxy in
            ScrollView {
                LazyVStack(alignment: .leading, spacing: 10) {
                    if asistente.mensajes.isEmpty { vacio }
                    ForEach(asistente.mensajes) { m in
                        Burbuja(mensaje: m).id(m.id)
                    }
                    if asistente.trabajando {
                        HStack(spacing: 8) {
                            ProgressView().controlSize(.small)
                            TimelineView(.periodic(from: .now, by: 1)) { t in
                                Text("Claude está trabajando… \(duracion(Int(t.date.timeIntervalSince(asistente.inicio))))")
                                    .font(.system(size: 12)).foregroundStyle(.secondary).monospacedDigit()
                            }
                        }
                        .padding(.leading, 4)
                    }
                    Color.clear.frame(height: 1).id("fin")
                }
                .padding(16)
            }
            .onChange(of: asistente.mensajes) { withAnimation { proxy.scrollTo("fin", anchor: .bottom) } }
            .onChange(of: asistente.trabajando) { withAnimation { proxy.scrollTo("fin", anchor: .bottom) } }
            .onAppear { proxy.scrollTo("fin", anchor: .bottom) }
        }
    }

    var vacio: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("Pide a Claude lo que quieras ajustar de la publicación: qué estilo va en cada parte, cómo son las tablas o las viñetas, qué palabras se resaltan… Lee la configuración y la maqueta, hace los cambios y te cuenta qué ha hecho.")
                .font(.system(size: 12.5)).foregroundStyle(.secondary).fixedSize(horizontal: false, vertical: true)
            Text("Por ejemplo").font(.system(size: 11, weight: .semibold)).foregroundStyle(.tertiary)
            ForEach(ideas, id: \.self) { idea in
                Button { texto = idea; escribiendo = true } label: {
                    HStack {
                        Image(systemName: "text.bubble").foregroundStyle(.tint)
                        Text(idea).font(.system(size: 12.5)).multilineTextAlignment(.leading)
                        Spacer()
                    }
                    .padding(10)
                    .background(RoundedRectangle(cornerRadius: 9).fill(Color.primary.opacity(0.05)))
                    .contentShape(Rectangle())
                }
                .buttonStyle(.plain)
            }
        }
        .padding(.bottom, 8)
    }

    var entrada: some View {
        HStack(alignment: .bottom, spacing: 10) {
            ZStack(alignment: .topLeading) {
                if texto.isEmpty {
                    Text("Escribe tu petición… (⌘↩ para enviar)")
                        .font(.system(size: 13)).foregroundStyle(.tertiary)
                        .padding(.horizontal, 5).padding(.vertical, 8)
                        .allowsHitTesting(false)
                }
                TextEditor(text: $texto)
                    .font(.system(size: 13))
                    .scrollContentBackground(.hidden)
                    .focused($escribiendo)
                    .frame(minHeight: 38, maxHeight: 120)
                    .fixedSize(horizontal: false, vertical: true)
            }
            .padding(6)
            .background(RoundedRectangle(cornerRadius: 10).fill(Color(nsColor: .textBackgroundColor)))
            .overlay(RoundedRectangle(cornerRadius: 10).strokeBorder(Color.primary.opacity(escribiendo ? 0.25 : 0.12)))
            if asistente.trabajando {
                Button(role: .destructive) { asistente.detener() } label: {
                    Image(systemName: "stop.fill").frame(width: 30, height: 30)
                }
                .buttonStyle(.borderedProminent)
                .tint(.red)
                .help("Detener")
            } else {
                Button {
                    asistente.enviar(texto)
                    texto = ""
                } label: {
                    Image(systemName: "arrow.up").font(.system(size: 14, weight: .bold)).frame(width: 30, height: 30)
                }
                .buttonStyle(.borderedProminent)
                .keyboardShortcut(.return, modifiers: .command)
                .disabled(texto.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty || asistente.publicacion == nil)
                .help("Enviar (⌘↩)")
            }
        }
        .padding(12)
    }
}

struct Burbuja: View {
    let mensaje: Mensaje

    var body: some View {
        switch mensaje.tipo {
        case .usuario:
            HStack {
                Spacer(minLength: 60)
                Text(mensaje.texto)
                    .font(.system(size: 13))
                    .foregroundStyle(.white)
                    .textSelection(.enabled)
                    .padding(.horizontal, 12).padding(.vertical, 8)
                    .background(RoundedRectangle(cornerRadius: 14).fill(Color.accentColor))
            }
        case .claude:
            HStack {
                Text(conFormato(mensaje.texto))
                    .font(.system(size: 13))
                    .textSelection(.enabled)
                    .padding(.horizontal, 12).padding(.vertical, 8)
                    .background(RoundedRectangle(cornerRadius: 14).fill(Color(nsColor: .controlBackgroundColor)))
                    .overlay(RoundedRectangle(cornerRadius: 14).strokeBorder(Color.primary.opacity(0.08)))
                Spacer(minLength: 60)
            }
        case .accion:
            Label(mensaje.texto, systemImage: icono)
                .font(.system(size: 11.5))
                .foregroundStyle(.secondary)
                .padding(.leading, 6)
        case .aviso:
            Label(mensaje.texto, systemImage: "info.circle.fill")
                .font(.system(size: 11.5))
                .foregroundStyle(.orange)
                .textSelection(.enabled)
                .padding(8)
                .frame(maxWidth: .infinity, alignment: .leading)
                .background(RoundedRectangle(cornerRadius: 8).fill(Color.orange.opacity(0.1)))
        }
    }

    var icono: String {
        let t = mensaje.texto
        if t.hasPrefix("Leyendo") { return "doc.text.magnifyingglass" }
        if t.hasPrefix("Editando") || t.hasPrefix("Escribiendo") { return "pencil" }
        if t.hasPrefix("Trabajando en InDesign") { return "wand.and.stars" }
        if t.hasPrefix("Buscando") { return "magnifyingglass" }
        return "gearshape"
    }

    /// Negritas, cursivas y código del Markdown de Claude, conservando los saltos de línea
    func conFormato(_ s: String) -> AttributedString {
        (try? AttributedString(markdown: s, options: .init(interpretedSyntax: .inlineOnlyPreservingWhitespace))) ?? AttributedString(s)
    }
}
