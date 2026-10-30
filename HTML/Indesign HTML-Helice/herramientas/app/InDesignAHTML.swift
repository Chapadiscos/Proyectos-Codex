// InDesign a HTML: de un capítulo de InDesign a su sección publicada en Hélice, con una
// ventana que enseña en todo momento en qué paso está, los avisos y la vista previa.
//
// A la izquierda, el libro (con sus capítulos y en qué punto está cada uno); en el centro,
// el paso actual con sus botones, los avisos y el registro; a la derecha, la vista previa
// del HTML depurado.
// 1. Eliges el .indd (o un capítulo de la lista). Si es el de imprenta o un archivo de
//    sección, se prepara antes la copia para HTML (./preparar); si ya es esa copia, se usa.
// 2. InDesign exporta el HTML (./libro exportar).
// 3. Las imágenes se suben solas a Ficheros de Hélice desde la pestaña del panel abierta en
//    Safari o Chrome (./subir); si no se puede, con el marcador.
// 4. Se depura el HTML (./capitulo) y, si el libro lo tiene configurado, se publica (./publicar).
// También: alta de un libro nuevo y edición de su estructura en Hélice (./libro), subida
// de las fuentes propias del libro (./subir --fuentes) y CSS nueva (./css_libro --copiar).
// Se puede soltar un .indd sobre el icono de la app.
// Compilar: herramientas/app/compilar_app.sh

import AppKit
import SwiftUI
import UniformTypeIdentifiers
import WebKit

/// Carpeta del proyecto: la de herramientas/.. si la app está ahí, si no la fija.
let proyecto: URL = {
    let junto = Bundle.main.bundleURL.deletingLastPathComponent().deletingLastPathComponent()
    if FileManager.default.fileExists(atPath: junto.appendingPathComponent("preparar").path) {
        return junto
    }
    return URL(fileURLWithPath: "/Volumes/DATOS/Proyectos Codex/HTML/Indesign HTML-Helice")
}()
let indesign = "Adobe InDesign 2026"
let libros = "/Volumes/MACLINE SERVER/LIBROS"

// MARK: - Datos de ./libro (JSON)

struct LibroResumen: Codable, Identifiable, Hashable {
    let id: String
    let nombre: String
    let raiz: String
    let existe: Bool
}

struct Capitulo: Codable, Identifiable, Hashable {
    let n: Int
    let carpeta: String
    let preparado: String
    let html: String
    let imagenes: Int
    let depurado: String
    let tema: String
    let conSeccion: Bool
    let publicado: String
    var id: Int { n }
    var titulo: String { String(format: "Capítulo %02d", n) }
    /// La vista previa que deja ./capitulo en salida/
    var vista: URL? {
        guard !depurado.isEmpty else { return nil }
        let nombre = URL(fileURLWithPath: depurado).deletingPathExtension().lastPathComponent
        let url = proyecto.appendingPathComponent("salida/\(nombre).vista.html")
        return FileManager.default.fileExists(atPath: url.path) ? url : nil
    }
}

struct EstadoLibro: Codable {
    let id: String
    let nombre: String
    let raiz: String
    let carpeta: String
    let existe: Bool
    let config: String
    let css: String
    let cssPendiente: Bool
    let fuentesPropias: Int
    let fuentesEnHelice: Int
    let puedeSubirFuentes: Bool
    let publicar: Bool
    let capitulos: [Capitulo]
}

struct Linea: Identifiable {
    enum Tipo { case normal, paso, aviso, error, ok }
    let id: Int
    let texto: String
    let tipo: Tipo
}

/// Ejecuta un lanzador del proyecto (./preparar, ./capitulo…) y devuelve toda su salida.
func lanzar(_ programa: String, _ argumentos: [String], entrada: Data? = nil) async -> String {
    await withCheckedContinuation { continuacion in
        DispatchQueue.global().async {
            let p = Process()
            p.executableURL = proyecto.appendingPathComponent(programa)
            p.arguments = argumentos
            p.currentDirectoryURL = proyecto
            var entorno = ProcessInfo.processInfo.environment
            entorno["LANG"] = "es_ES.UTF-8"     // pbcopy y pbpaste, con acentos
            entorno["LC_ALL"] = "es_ES.UTF-8"
            entorno["PYTHONUNBUFFERED"] = "1"
            p.environment = entorno
            let salida = Pipe()
            p.standardOutput = salida
            p.standardError = salida
            let tuberiaEntrada = Pipe()
            if entrada != nil { p.standardInput = tuberiaEntrada }
            do {
                try p.run()
            } catch {
                continuacion.resume(returning: "ERROR\n\nNo se ha podido lanzar ./\(programa): \(error.localizedDescription)")
                return
            }
            if let entrada {
                tuberiaEntrada.fileHandleForWriting.write(entrada)
                try? tuberiaEntrada.fileHandleForWriting.close()
            }
            let datos = salida.fileHandleForReading.readDataToEndOfFile()
            p.waitUntilExit()
            continuacion.resume(returning: String(decoding: datos, as: UTF8.self))
        }
    }
}

func lineas(_ texto: String) -> [String] {
    texto.components(separatedBy: "\n")
}

/// Las líneas desde la n (1 = la primera), como en la app de AppleScript
func desde(_ texto: String, _ n: Int) -> String {
    let l = lineas(texto)
    return l.count < n ? "" : l[(n - 1)...].joined(separator: "\n").trimmingCharacters(in: .whitespacesAndNewlines)
}

func decodificar<T: Decodable>(_ tipo: T.Type, _ texto: String) throws -> T {
    let datos = Data(texto.utf8)
    if let error = (try? JSONSerialization.jsonObject(with: datos)) as? [String: Any], let mensaje = error["error"] as? String {
        throw NSError(domain: "libro", code: 1, userInfo: [NSLocalizedDescriptionKey: mensaje])
    }
    let d = JSONDecoder()
    d.keyDecodingStrategy = .convertFromSnakeCase
    return try d.decode(tipo, from: datos)
}

// MARK: - El proceso de un capítulo

struct OpcionCapitulo: Identifiable, Hashable {
    let n: Int
    let copia: String
    let existe: Bool
    var id: Int { n }
}

@MainActor
final class Taller: ObservableObject {
    enum Paso: Equatable {
        case inicio
        case trabajando(String)
        case elegirCapitulo([OpcionCapitulo])
        case yaPreparado(OpcionCapitulo)
        case preparado(conAvisos: Bool, recienPreparado: Bool)
        case enInDesign
        case exportado(String)
        case subidaManual(String, seguirSinEllas: Bool)
        case depurado
        case publicado(String)
        case error(String)
    }

    @Published var paso: Paso = .inicio
    @Published var lineasRegistro: [Linea] = []
    @Published var avisos: [String] = []
    @Published var vista: URL?
    @Published var inicioTrabajo = Date()

    // Libros
    @Published var listaLibros: [LibroResumen] = []
    @Published var libroID: String = UserDefaults.standard.string(forKey: "libro") ?? "" {
        didSet { UserDefaults.standard.set(libroID, forKey: "libro") }
    }
    @Published var libro: EstadoLibro?
    @Published var errorLibro = ""
    @Published var capituloElegido: Int?

    // El capítulo en curso
    @Published var rutaIndd = ""
    @Published var numero: Int?
    @Published var copia = ""
    @Published var rutaHtml = ""
    @Published var rutaFinal = ""
    @Published var estadoDepurado = ""     // OK | AVISOS
    @Published var publicable = false
    @Published var temaPublicacion = ""
    @Published var yaPublicado = ""
    @Published var cssNueva = false
    @Published var cssCopiada = false
    @Published var htmlCopiado = false

    private var ultimaSalida = ""
    private var reintento: (() -> Void)?

    /// Lo que muestra la ventana de un capítulo: se guarda al cambiar a otro y se recupera al volver
    struct Sesion {
        var paso: Paso = .inicio
        var lineasRegistro: [Linea] = []
        var avisos: [String] = []
        var vista: URL?
        var rutaIndd = ""
        var numero: Int?
        var copia = ""
        var rutaHtml = ""
        var rutaFinal = ""
        var estadoDepurado = ""
        var publicable = false
        var temaPublicacion = ""
        var yaPublicado = ""
        var cssNueva = false
        var cssCopiada = false
        var htmlCopiado = false
        var ultimaSalida = ""
        var reintento: (() -> Void)?
    }

    private var sesiones: [String: Sesion] = [:]
    private var claveActual: String?   // libro/capítulo de lo que se ve

    var trabajando: Bool {
        if case .trabajando = paso { return true }
        return false
    }

    var nombreCapitulo: String {
        if let numero { return String(format: "Capítulo %02d", numero) }
        return rutaIndd.isEmpty ? "" : URL(fileURLWithPath: rutaIndd).lastPathComponent
    }

    // MARK: Registro

    func anotar(_ texto: String, _ tipo: Linea.Tipo? = nil) {
        for t in lineas(texto) {
            var clase = tipo ?? .normal
            if tipo == nil {
                if t.hasPrefix("⚠️") {
                    clase = .aviso
                    if !t.hasPrefix("⚠️ AVISOS") {
                        let aviso = t.replacingOccurrences(of: "⚠️", with: "").trimmingCharacters(in: .whitespaces)
                        if !aviso.isEmpty && !avisos.contains(aviso) { avisos.append(aviso) }
                    }
                } else if t.hasPrefix("ERROR") || t.contains("Traceback") {
                    clase = .error
                }
            }
            lineasRegistro.append(Linea(id: lineasRegistro.count, texto: t, tipo: clase))
        }
    }

    private func titulo(_ texto: String) {
        if !lineasRegistro.isEmpty { anotar("", .normal) }
        anotar("▸ " + texto, .paso)
    }

    private func trabajar(_ texto: String) {
        inicioTrabajo = Date()
        paso = .trabajando(texto)
    }

    private func fallo(_ texto: String, reintentar: (() -> Void)?) {
        anotar("ERROR: " + texto, .error)
        reintento = reintentar
        paso = .error(texto)
    }

    func reintentar() { reintento?() }

    // MARK: Un capítulo cada vez

    private func clave(_ n: Int) -> String { "\(libroID)/\(n)" }

    private var sesion: Sesion {
        get {
            Sesion(paso: paso, lineasRegistro: lineasRegistro, avisos: avisos, vista: vista, rutaIndd: rutaIndd,
                   numero: numero, copia: copia, rutaHtml: rutaHtml, rutaFinal: rutaFinal, estadoDepurado: estadoDepurado,
                   publicable: publicable, temaPublicacion: temaPublicacion, yaPublicado: yaPublicado, cssNueva: cssNueva,
                   cssCopiada: cssCopiada, htmlCopiado: htmlCopiado, ultimaSalida: ultimaSalida, reintento: reintento)
        }
        set {
            paso = newValue.paso
            lineasRegistro = newValue.lineasRegistro
            avisos = newValue.avisos
            vista = newValue.vista
            rutaIndd = newValue.rutaIndd
            numero = newValue.numero
            copia = newValue.copia
            rutaHtml = newValue.rutaHtml
            rutaFinal = newValue.rutaFinal
            estadoDepurado = newValue.estadoDepurado
            publicable = newValue.publicable
            temaPublicacion = newValue.temaPublicacion
            yaPublicado = newValue.yaPublicado
            cssNueva = newValue.cssNueva
            cssCopiada = newValue.cssCopiada
            htmlCopiado = newValue.htmlCopiado
            ultimaSalida = newValue.ultimaSalida
            reintento = newValue.reintento
        }
    }

    private func guardarSesion() {
        if let claveActual { sesiones[claveActual] = sesion }
    }

    /// El capítulo en curso pasa a ser n (sin cambiar lo que se ve)
    private func asignar(_ n: Int) {
        numero = n
        claveActual = clave(n)
        capituloElegido = n
    }

    /// Al elegir un capítulo en la lista: se guarda cómo queda el actual y se muestra
    /// el elegido como se dejó o, si no se ha tocado en esta sesión, según lo que hay en disco
    func mostrarCapitulo() {
        guard !trabajando, let n = capituloElegido, clave(n) != claveActual else { return }
        guard let cap = libro?.capitulos.first(where: { $0.n == n }), libro?.id == libroID else { return }
        guardarSesion()
        claveActual = clave(n)
        if let s = sesiones[clave(n)] {
            sesion = s
        } else {
            reconstruir(cap)
        }
    }

    private func reconstruir(_ cap: Capitulo) {
        sesion = Sesion(numero: cap.n)
        guard !cap.preparado.isEmpty || !cap.depurado.isEmpty else { return }   // sin empezar
        rutaIndd = cap.preparado
        copia = cap.preparado
        rutaHtml = cap.html
        titulo("Estado guardado del capítulo")
        if !cap.preparado.isEmpty { anotar("Versión preparada: \(URL(fileURLWithPath: cap.preparado).lastPathComponent)") }
        if !cap.html.isEmpty { anotar("HTML exportado: \(URL(fileURLWithPath: cap.html).lastPathComponent)") }
        if cap.imagenes > 0 { anotar("\(cap.imagenes) imágenes con su URL de Hélice") }

        if !cap.depurado.isEmpty {
            rutaFinal = cap.depurado
            vista = cap.vista
            anotar("HTML depurado: \(URL(fileURLWithPath: cap.depurado).lastPathComponent)")
            let nombre = URL(fileURLWithPath: cap.depurado).deletingPathExtension().lastPathComponent
            estadoDepurado = leerInformeDepurado(proyecto.appendingPathComponent("salida/\(nombre).informe.txt").path)
            if !cap.publicado.isEmpty {
                anotar("Publicado en Hélice el \(cap.publicado)", .ok)
                paso = .publicado("Publicado en Hélice el \(cap.publicado)")
            } else {
                planPublicacion()
            }
            return
        }
        let base = URL(fileURLWithPath: cap.preparado).deletingPathExtension().lastPathComponent
        if let informe = try? String(contentsOfFile: proyecto.appendingPathComponent("salida/\(base).preparar.txt").path, encoding: .utf8) {
            titulo("Informe de la preparación")
            anotar(informe.trimmingCharacters(in: .whitespacesAndNewlines))
        }
        if !cap.html.isEmpty {
            paso = .exportado(String(contarImagenes(cap.html)))
        } else {
            paso = .preparado(conAvisos: !avisos.isEmpty, recienPreparado: false)
        }
    }

    /// Lee el informe de ./capitulo y pasa sus avisos al panel; devuelve OK o AVISOS
    private func leerInformeDepurado(_ ruta: String) -> String {
        guard let texto = try? String(contentsOfFile: ruta, encoding: .utf8) else { return "" }
        titulo("Informe de la depuración")
        var enAvisos = false
        for l in lineas(texto) {
            if l == "Avisos:" { enAvisos = true }
            if enAvisos && l.hasPrefix("  - ") {
                anotar("⚠️ " + l.dropFirst(4))
            } else {
                anotar(l)
            }
        }
        return avisos.isEmpty ? "OK" : "AVISOS"
    }

    private func contarImagenes(_ html: String) -> Int {
        let url = URL(fileURLWithPath: html)
        let carpeta = url.deletingLastPathComponent()
            .appendingPathComponent(url.deletingPathExtension().lastPathComponent.replacingOccurrences(of: " ", with: "_") + "-web-resources/image")
        return (try? FileManager.default.contentsOfDirectory(atPath: carpeta.path).filter { !$0.hasPrefix(".") }.count) ?? 0
    }

    // MARK: Libros

    func cargarLibros() {
        Task {
            let salida = await lanzar("libro", ["listar"])
            do {
                listaLibros = try decodificar([LibroResumen].self, salida)
                if !listaLibros.contains(where: { $0.id == libroID }) { libroID = listaLibros.first?.id ?? "" }
                refrescarLibro()
            } catch {
                errorLibro = "No se han podido leer los libros: \(error.localizedDescription)"
            }
        }
    }

    func refrescarLibro() {
        guard !libroID.isEmpty else { libro = nil; return }
        let id = libroID
        Task {
            let salida = await lanzar("libro", ["estado", id])
            guard id == libroID else { return }
            do {
                libro = try decodificar(EstadoLibro.self, salida)
                errorLibro = ""
                mostrarCapitulo()
            } catch {
                libro = nil
                errorLibro = error.localizedDescription
            }
        }
    }

    func elegirLibro(nombre: String) {
        if let l = listaLibros.first(where: { $0.nombre == nombre }), l.id != libroID {
            libroID = l.id
        }
        refrescarLibro()
    }

    func abrirConfiguracion() {
        guard let libro else { return }
        abrir(["-e", libro.config])
    }

    func subirFuentes() {
        guard let libro else { return }
        let id = libro.id
        titulo("Fuentes de «\(libro.nombre)» a Hélice")
        trabajar("Subiendo las fuentes a Hélice…")
        Task {
            let r = await lanzar("subir", ["--fuentes", "--libro", id])
            if r.hasPrefix("OK") {
                anotar(desde(r, 2), .ok)
                paso = .inicio
            } else {
                fallo(desde(r, 2), reintentar: { [weak self] in self?.subirFuentes() })
            }
            refrescarLibro()
        }
    }

    func copiarCSS(entera: Bool = false) {
        guard let libro else { return }
        Task {
            var args = ["--copiar", "--libro", libro.id]
            if entera { args.append("--todo") }
            let r = await lanzar("css_libro", args)
            anotar(r.trimmingCharacters(in: .whitespacesAndNewlines), .ok)
            if !entera {
                cssCopiada = true
                cssNueva = false
            }
            refrescarLibro()
        }
    }

    // MARK: Empezar

    func elegirIndd(en carpeta: String? = nil) {
        let panel = NSOpenPanel()
        panel.title = "Elige el capítulo de InDesign"
        panel.message = "El de imprenta, un archivo de sección o la versión ya preparada para HTML"
        panel.allowedContentTypes = [UTType(filenameExtension: "indd") ?? .data]
        if let carpeta, FileManager.default.fileExists(atPath: carpeta) {
            panel.directoryURL = URL(fileURLWithPath: carpeta)
        } else {
            panel.directoryURL = UserDefaults.standard.url(forKey: "ultimaCarpeta") ?? URL(fileURLWithPath: libros)
        }
        guard panel.runModal() == .OK, let url = panel.url else { return }
        UserDefaults.standard.set(url.deletingLastPathComponent(), forKey: "ultimaCarpeta")
        empezar(con: url.path)
    }

    /// Un capítulo de la lista desde el principio: su copia preparada o, si aún no la tiene, elegir el original
    func procesar(_ cap: Capitulo) {
        if !cap.preparado.isEmpty {
            empezar(con: cap.preparado)
        } else {
            elegirIndd(en: libro?.raiz)
        }
    }

    func empezar(con ruta: String) {
        // Lo que se veía se guarda con su capítulo; este aún no sabe cuál es
        guardarSesion()
        claveActual = nil
        capituloElegido = nil
        sesion = Sesion(rutaIndd: ruta)
        titulo(URL(fileURLWithPath: ruta).lastPathComponent)
        trabajar("Leyendo el capítulo en InDesign…")
        Task {
            let plan = await lanzar("preparar", ["--plan", ruta])
            let l = lineas(plan)
            let tipo = l.first ?? "ERROR"
            if tipo == "ERROR" || l.count < 3 {
                fallo(desde(plan, 3).isEmpty ? plan : desde(plan, 3), reintentar: { [weak self] in self?.empezar(con: ruta) })
                return
            }
            elegirLibro(nombre: l[1])
            anotar("Libro: \(l[1])")
            let opciones: [OpcionCapitulo] = l[2...].compactMap { linea in
                let p = linea.components(separatedBy: "|")
                guard p.count == 3, let n = Int(p[0]) else { return nil }
                return OpcionCapitulo(n: n, copia: p[1], existe: p[2] == "EXISTE")
            }
            switch tipo {
            case "PREPARADO":
                if let n = opciones.first?.n { asignar(n) }
                copia = ruta
                anotar("Es la versión ya preparada para HTML.")
                paso = .preparado(conAvisos: false, recienPreparado: false)
            case "SECCION":
                anotar("Archivo de sección con los capítulos " + opciones.map { String($0.n) }.joined(separator: ", "))
                paso = .elegirCapitulo(opciones)
            default:
                if let o = opciones.first { elegir(o) }
            }
        }
    }

    func elegir(_ o: OpcionCapitulo) {
        asignar(o.n)
        copia = o.copia
        if o.existe {
            paso = .yaPreparado(o)
        } else {
            preparar(forzar: false)
        }
    }

    // MARK: 1. Preparar

    func usarPreparada() {
        anotar("Se usa la versión preparada: \(copia)")
        paso = .preparado(conAvisos: false, recienPreparado: false)
    }

    func preparar(forzar: Bool) {
        guard let numero else { return }
        titulo("Preparar el capítulo \(numero) para HTML")
        trabajar("Preparando el capítulo \(numero) en InDesign…")
        avisos = []
        let ruta = rutaIndd
        Task {
            var args = [ruta, "--resumen"]
            if forzar { args.append("--forzar") }
            args += ["--capitulo", String(numero)]
            let r = await lanzar("preparar", args)
            let estado = lineas(r).first ?? "ERROR"
            if estado == "ERROR" {
                fallo("No se ha podido preparar el capítulo: " + desde(r, 3), reintentar: { [weak self] in self?.preparar(forzar: forzar) })
                return
            }
            copia = lineas(r).count > 1 ? lineas(r)[1] : copia
            anotar(desde(r, 3))
            paso = .preparado(conAvisos: estado == "AVISOS", recienPreparado: true)
            refrescarLibro()
        }
    }

    func abrirEnInDesign() {
        abrir(["-a", indesign, copia])
        anotar("Abierta en InDesign: \(copia)")
        paso = .enInDesign
    }

    // MARK: 2. Exportar

    func exportar() {
        titulo("Exportar a HTML")
        trabajar("InDesign está exportando el HTML…")
        let indd = copia
        Task {
            let r = await lanzar("libro", ["exportar", indd])
            let l = lineas(r)
            guard l.first == "OK", l.count >= 3 else {
                fallo(desde(r, 3).isEmpty ? r : desde(r, 3), reintentar: { [weak self] in self?.exportar() })
                return
            }
            rutaHtml = l[1]
            anotar("HTML exportado con \(l[2]) imágenes: \(URL(fileURLWithPath: rutaHtml).lastPathComponent)", .ok)
            subirImagenes(cuantas: l[2])
        }
    }

    // MARK: 3. Imágenes a Hélice

    /// Un capítulo exportado en otra sesión: sigue con la subida de las imágenes
    func seguirExportado() {
        if case .exportado(let cuantas) = paso { subirImagenes(cuantas: cuantas) }
    }

    private func subirImagenes(cuantas: String) {
        let html = rutaHtml
        Task {
            let manifiesto = await lanzar("publicar", ["--manifiesto", html]).trimmingCharacters(in: .whitespacesAndNewlines)
            let carpeta = URL(fileURLWithPath: html).deletingLastPathComponent().path
            if manifiesto.isEmpty {
                paso = .subidaManual(
                    "1. Sube a Hélice, en la carpeta del capítulo, las \(cuantas) imágenes de la carpeta «…-web-resources/image» de:\n\(carpeta)\n" +
                    "2. Abre esa carpeta en Hélice y pulsa el marcador «Enlaces Hélice».\n3. Pulsa Continuar.",
                    seguirSinEllas: false)
                return
            }
            titulo("Subir las imágenes a Hélice")
            trabajar("Subiendo a Hélice las \(cuantas) imágenes desde la pestaña del panel…")
            let r = await lanzar("subir", [html])
            if r.hasPrefix("OK") {
                anotar(desde(r, 2), .ok)
                depurar()
            } else {
                anotar("No se han podido subir automáticamente: " + desde(r, 2), .aviso)
                paso = .subidaManual(
                    "No se han podido subir las imágenes automáticamente:\n\(desde(r, 2))\n\n" +
                    "Puedes subirlas con el marcador: en el panel de Hélice pulsa «Subir a Hélice», elige la carpeta del capítulo\n\(carpeta)\n" +
                    "y, cuando haya copiado los enlaces, pulsa Continuar. O arregla el motivo y pulsa Reintentar la subida.",
                    seguirSinEllas: false)
                reintento = { [weak self] in self?.subirImagenes(cuantas: cuantas) }
            }
        }
    }

    // MARK: 4. Depurar

    func depurar() {
        titulo("Depurar el HTML")
        trabajar("Depurando el HTML…")
        let html = rutaHtml
        Task {
            let salida = await lanzar("capitulo", [html, "--resumen"])
            ultimaSalida = salida
            let estado = lineas(salida).first ?? "ERROR"
            switch estado {
            case "FALTAN_URLS":
                paso = .subidaManual("No hay enlaces de Hélice en el portapapeles.\n\nAbre en Hélice la carpeta con las imágenes del capítulo, " +
                                     "pulsa el marcador «Enlaces Hélice» y vuelve a pulsar Continuar.", seguirSinEllas: false)
            case "FALTAN_IMAGENES":
                anotar(desde(salida, 4), .aviso)
                paso = .subidaManual(desde(salida, 4), seguirSinEllas: true)
            default:
                resultado(salida, estado: estado)
            }
        }
    }

    func seguirSinImagenes() { resultado(ultimaSalida, estado: "AVISOS") }

    private func resultado(_ salida: String, estado: String) {
        let l = lineas(salida)
        let detalle = desde(salida, 4)
        if estado == "ERROR" || l.count < 3 {
            fallo("No se ha podido depurar el HTML: " + (detalle.isEmpty ? salida : detalle), reintentar: { [weak self] in self?.depurar() })
            return
        }
        rutaFinal = l[1]
        estadoDepurado = estado
        htmlCopiado = estado == "OK"   // ./capitulo lo copia si no hay avisos
        if !l[2].isEmpty { vista = URL(fileURLWithPath: l[2]) }
        if !detalle.isEmpty { anotar(detalle) }
        cssNueva = detalle.contains("la CSS del libro ha cambiado")
        anotar(estado == "OK" ? "HTML depurado sin avisos." : "HTML depurado con avisos.", estado == "OK" ? .ok : .aviso)
        planPublicacion()
    }

    /// Si el HTML depurado se puede publicar por la API, y dónde
    private func planPublicacion() {
        let final = rutaFinal
        trabajar("Comprobando dónde se publica…")
        Task {
            let plan = await lanzar("publicar", ["--plan", final])
            let p = lineas(plan)
            publicable = p.first == "SI"
            temaPublicacion = publicable && p.count > 1 ? p[1] : ""
            yaPublicado = p.first == "YA" && p.count > 1 ? p[1] : ""
            paso = .depurado
            refrescarLibro()
        }
    }

    func copiarHTML() {
        guard !rutaFinal.isEmpty, let texto = try? String(contentsOfFile: rutaFinal, encoding: .utf8) else { return }
        NSPasteboard.general.clearContents()
        NSPasteboard.general.setString(texto, forType: .string)
        htmlCopiado = true
        anotar("HTML copiado al portapapeles: pégalo en Hélice con ⌘V.", .ok)
    }

    func copiarCSSNueva() {
        let final = rutaFinal
        Task {
            let r = await lanzar("css_libro", ["--copiar", final])
            anotar(r.trimmingCharacters(in: .whitespacesAndNewlines), .ok)
            cssCopiada = true
            refrescarLibro()
        }
    }

    // MARK: 5. Publicar

    func publicar() {
        titulo("Publicar en Hélice")
        trabajar("Publicando en Hélice…")
        let final = rutaFinal
        Task {
            let r = await lanzar("publicar", [final]).trimmingCharacters(in: .whitespacesAndNewlines)
            if r.hasPrefix("ERROR") || r.contains("Traceback") {
                fallo(r.replacingOccurrences(of: "ERROR: ", with: ""), reintentar: { [weak self] in self?.publicar() })
            } else {
                anotar(r, .ok)
                paso = .publicado(r)
            }
            refrescarLibro()
        }
    }

    // MARK: Utilidades

    func verPreviaEnNavegador() {
        if let vista { NSWorkspace.shared.open(vista) }
    }

    func mostrarEnFinder(_ ruta: String) {
        guard !ruta.isEmpty else { return }
        NSWorkspace.shared.activateFileViewerSelecting([URL(fileURLWithPath: ruta)])
    }

    func abrir(_ argumentos: [String]) {
        let p = Process()
        p.executableURL = URL(fileURLWithPath: "/usr/bin/open")
        p.arguments = argumentos
        try? p.run()
    }
}

// MARK: - Vista previa

struct VistaWeb: NSViewRepresentable {
    let url: URL

    func makeNSView(context: Context) -> WKWebView {
        WKWebView()
    }

    func updateNSView(_ vista: WKWebView, context: Context) {
        if vista.url != url {
            // Lee la CSS del libro y sus fuentes, que están en otras carpetas
            vista.loadFileURL(url, allowingReadAccessTo: URL(fileURLWithPath: "/"))
        }
    }
}

// MARK: - Ventana

struct Ventana: View {
    @ObservedObject var taller: Taller
    @State private var formulario: FormLibro?

    var body: some View {
        HSplitView {
            BarraLibro(taller: taller, formulario: $formulario)
                .frame(minWidth: 250, idealWidth: 280, maxWidth: 360)
            Centro(taller: taller)
                .frame(minWidth: 460, idealWidth: 560)
            Group {
                if let url = taller.vista {
                    VistaWeb(url: url)
                } else {
                    VStack(spacing: 8) {
                        Image(systemName: "doc.richtext")
                            .font(.system(size: 44))
                        Text("Aquí aparecerá la vista previa del HTML depurado")
                    }
                    .foregroundStyle(.secondary)
                    .frame(maxWidth: .infinity, maxHeight: .infinity)
                }
            }
            .frame(minWidth: 360, idealWidth: 520)
        }
        .frame(minWidth: 1150, minHeight: 680)
        .sheet(item: $formulario) { f in
            VistaFormLibro(form: f, taller: taller) { formulario = nil }
        }
    }
}

// MARK: Barra del libro

struct BarraLibro: View {
    @ObservedObject var taller: Taller
    @Binding var formulario: FormLibro?

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            VStack(alignment: .leading, spacing: 8) {
                HStack {
                    Picker("Libro", selection: $taller.libroID) {
                        ForEach(taller.listaLibros) { l in Text(l.nombre).tag(l.id) }
                    }
                    .labelsHidden()
                    .onChange(of: taller.libroID) { _, _ in taller.refrescarLibro() }
                    Menu {
                        Button("Nuevo libro…") { formulario = FormLibro(nuevo: true) }
                        Button("Editar la estructura en Hélice…") { editar() }
                            .disabled(taller.libro == nil)
                        Divider()
                        Button("Abrir su configuración (.yaml)") { taller.abrirConfiguracion() }
                            .disabled(taller.libro == nil)
                        Button("Mostrar la carpeta del libro") { taller.mostrarEnFinder(taller.libro?.carpeta ?? "") }
                            .disabled(taller.libro == nil)
                        Divider()
                        Button("Copiar la CSS entera del libro") { taller.copiarCSS(entera: true) }
                            .disabled(taller.libro?.css.isEmpty ?? true)
                        Button("Actualizar") { taller.cargarLibros() }
                    } label: {
                        Image(systemName: "ellipsis.circle")
                    }
                    .menuStyle(.borderlessButton)
                    .fixedSize()
                }
                if !taller.errorLibro.isEmpty {
                    Text(taller.errorLibro).font(.caption).foregroundStyle(.red)
                }
                if let l = taller.libro {
                    if !l.existe {
                        Label("No encuentro la carpeta del libro:\n\(l.raiz)", systemImage: "exclamationmark.triangle")
                            .font(.caption).foregroundStyle(.orange)
                    }
                    if l.fuentesPropias > 0 && l.existe {
                        let faltan = l.fuentesEnHelice < l.fuentesPropias
                        HStack {
                            Label(faltan ? "Fuentes: \(l.fuentesEnHelice) de \(l.fuentesPropias) en Hélice" : "Fuentes en Hélice (\(l.fuentesPropias))",
                                  systemImage: faltan ? "textformat.alt" : "checkmark.circle")
                                .font(.caption)
                                .foregroundStyle(faltan ? .orange : .secondary)
                            Spacer()
                            if faltan && l.puedeSubirFuentes {
                                Button("Subir") { taller.subirFuentes() }
                                    .controlSize(.small)
                                    .disabled(taller.trabajando)
                            }
                        }
                    }
                    if l.cssPendiente {
                        HStack {
                            Label("Hay CSS nueva para Hélice", systemImage: "paintbrush")
                                .font(.caption).foregroundStyle(.orange)
                            Spacer()
                            Button("Copiar") { taller.copiarCSS() }.controlSize(.small)
                        }
                    }
                }
            }
            .padding(10)
            Divider()
            List(selection: $taller.capituloElegido) {
                ForEach(taller.libro?.capitulos ?? []) { cap in
                    FilaCapitulo(cap: cap).tag(cap.n)
                        .contextMenu {
                            Button(cap.preparado.isEmpty ? "Elegir su original…" : "Volver a empezar") { taller.procesar(cap) }
                            Button("Mostrar en el Finder") { taller.mostrarEnFinder(cap.carpeta) }
                                .disabled(cap.carpeta.isEmpty)
                        }
                }
            }
            .listStyle(.sidebar)
            .disabled(taller.trabajando)
            .onChange(of: taller.capituloElegido) { _, _ in taller.mostrarCapitulo() }
            Divider()
            acciones
        }
    }

    @ViewBuilder
    private var acciones: some View {
        VStack(alignment: .leading, spacing: 6) {
            Text("Cada capítulo se muestra como se dejó. Un archivo de sección o fuera de la lista:")
                .font(.caption).foregroundStyle(.secondary)
                .fixedSize(horizontal: false, vertical: true)
            Button("Elegir un .indd…") { taller.elegirIndd() }
                .disabled(taller.trabajando)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(10)
    }

    private func editar() {
        guard let l = taller.libro else { return }
        Task {
            let datos = await lanzar("libro", ["datos", l.id])
            if let d = try? decodificar(DatosLibro.self, datos) {
                formulario = FormLibro(editar: d)
            } else {
                taller.anotar("ERROR: no se han podido leer los datos del libro: \(datos)", .error)
            }
        }
    }
}

struct FilaCapitulo: View {
    let cap: Capitulo

    var body: some View {
        HStack(spacing: 6) {
            VStack(alignment: .leading, spacing: 1) {
                Text(cap.titulo)
                if !cap.tema.isEmpty {
                    Text(cap.tema).font(.caption2).foregroundStyle(.secondary)
                }
            }
            Spacer()
            icono("wand.and.stars", cap.preparado.isEmpty ? nil : "Preparado para HTML")
            icono("photo.on.rectangle", cap.imagenes > 0 ? "\(cap.imagenes) imágenes en Hélice" : nil)
            icono("checkmark.seal", cap.depurado.isEmpty ? nil : "HTML depurado")
            icono("paperplane.fill", cap.publicado.isEmpty ? nil : "Publicado el \(cap.publicado)", color: .green)
        }
    }

    private func icono(_ nombre: String, _ ayuda: String?, color: Color = .accentColor) -> some View {
        Image(systemName: nombre)
            .font(.caption)
            .foregroundStyle(ayuda == nil ? Color.secondary.opacity(0.25) : color)
            .help(ayuda ?? "")
    }
}

// MARK: Centro: paso actual, avisos y registro

struct Centro: View {
    @ObservedObject var taller: Taller

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            TarjetaPaso(taller: taller)
                .padding(12)
            if !taller.avisos.isEmpty {
                Divider()
                PanelAvisos(avisos: taller.avisos)
            }
            Divider()
            registro
        }
    }

    private var registro: some View {
        ScrollViewReader { desplazar in
            ScrollView {
                LazyVStack(alignment: .leading, spacing: 1) {
                    ForEach(taller.lineasRegistro) { linea in
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
            .onChange(of: taller.lineasRegistro.count) { _, _ in
                if let ultima = taller.lineasRegistro.last { desplazar.scrollTo(ultima.id, anchor: .bottom) }
            }
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

struct PanelAvisos: View {
    let avisos: [String]

    var body: some View {
        VStack(alignment: .leading, spacing: 6) {
            Label("\(avisos.count) aviso\(avisos.count == 1 ? "" : "s") para revisar", systemImage: "exclamationmark.triangle.fill")
                .font(.headline)
                .foregroundStyle(.orange)
            ScrollView {
                VStack(alignment: .leading, spacing: 4) {
                    ForEach(Array(avisos.enumerated()), id: \.offset) { _, a in
                        HStack(alignment: .firstTextBaseline, spacing: 6) {
                            Text("•")
                            Text(a).fixedSize(horizontal: false, vertical: true)
                        }
                    }
                }
                .textSelection(.enabled)
                .frame(maxWidth: .infinity, alignment: .leading)
            }
            .frame(maxHeight: 160)
        }
        .padding(12)
        .background(Color.orange.opacity(0.12))
    }
}

struct TarjetaPaso: View {
    @ObservedObject var taller: Taller

    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            HStack(alignment: .firstTextBaseline) {
                Text(taller.nombreCapitulo.isEmpty ? "InDesign a HTML" : taller.nombreCapitulo)
                    .font(.title2.weight(.semibold))
                Spacer()
                if !taller.rutaIndd.isEmpty {
                    Text(URL(fileURLWithPath: taller.rutaIndd).lastPathComponent)
                        .font(.caption).foregroundStyle(.secondary)
                        .lineLimit(1).truncationMode(.middle)
                }
            }
            contenido
        }
    }

    @ViewBuilder
    private var contenido: some View {
        switch taller.paso {
        case .inicio:
            if taller.numero != nil {
                Text("Capítulo sin empezar. Elige su original de imprenta o el archivo de sección que lo contiene. " +
                     "Antes de seguir, deja abierta en Safari o Chrome una pestaña del panel de Hélice con la sesión iniciada.")
                    .foregroundStyle(.secondary)
                HStack {
                    Spacer()
                    Button("Elegir su original…") { taller.elegirIndd(en: taller.libro?.raiz) }.keyboardShortcut(.defaultAction)
                }
            } else {
                Text("Elige un capítulo de la lista o un .indd (el de imprenta, un archivo de sección o la versión ya preparada). " +
                     "Antes de empezar, deja abierta en Safari o Chrome una pestaña del panel de Hélice con la sesión iniciada.")
                    .foregroundStyle(.secondary)
                HStack {
                    Spacer()
                    Button("Elegir un .indd…") { taller.elegirIndd() }.keyboardShortcut(.defaultAction)
                }
            }

        case .trabajando(let texto):
            HStack(spacing: 10) {
                ProgressView().controlSize(.small)
                Text(texto)
                Spacer()
                TimelineView(.periodic(from: taller.inicioTrabajo, by: 1)) { ctx in
                    Text(tiempo(ctx.date.timeIntervalSince(taller.inicioTrabajo)))
                        .monospacedDigit().foregroundStyle(.secondary)
                }
            }

        case .elegirCapitulo(let opciones):
            Text("Este archivo tiene varios capítulos. ¿Cuál pasas a Hélice?")
            ScrollView(.horizontal) {
                HStack {
                    ForEach(opciones) { o in
                        Button(String(format: "Capítulo %02d", o.n) + (o.existe ? " ✓" : "")) { taller.elegir(o) }
                            .help(o.existe ? "Ya tiene su versión preparada" : "")
                    }
                }
            }
            Text("✓ = ya tiene su versión preparada para HTML").font(.caption).foregroundStyle(.secondary)

        case .yaPreparado:
            Text("Este capítulo ya tiene su versión preparada para HTML:")
            ruta(taller.copia)
            Text("¿La usas tal cual o la preparas de nuevo desde este original? La actual se guarda como «(anterior)».")
                .foregroundStyle(.secondary)
            HStack {
                Spacer()
                Button("Preparar de nuevo") { taller.preparar(forzar: true) }
                Button("Usar la preparada") { taller.usarPreparada() }.keyboardShortcut(.defaultAction)
            }

        case .preparado(let conAvisos, let recien):
            if recien {
                Label(conAvisos ? "Capítulo preparado, con avisos: revísalos en la copia antes de exportar." : "Capítulo preparado.",
                      systemImage: conAvisos ? "exclamationmark.triangle.fill" : "checkmark.circle.fill")
                    .foregroundStyle(conAvisos ? .orange : .green)
            } else {
                Text("Versión preparada para HTML:")
            }
            ruta(taller.copia)
            HStack {
                Button("Mostrar en el Finder") { taller.mostrarEnFinder(taller.copia) }
                Spacer()
                Button("Abrir en InDesign") { taller.abrirEnInDesign() }
                Button("Exportar a HTML") { taller.exportar() }.keyboardShortcut(.defaultAction)
            }

        case .enInDesign:
            Text("Revisa la copia en InDesign y guárdala. Después pulsa Exportar a HTML: se exporta tal como esté en InDesign.")
            ruta(taller.copia)
            HStack {
                Spacer()
                Button("Exportar a HTML") { taller.exportar() }.keyboardShortcut(.defaultAction)
            }

        case .exportado(let cuantas):
            Text("HTML exportado\(cuantas == "0" ? "" : " con \(cuantas) imágenes"). Falta subir las imágenes a Hélice y depurarlo.")
            ruta(taller.rutaHtml)
            HStack {
                Button("Abrir en InDesign") { taller.abrirEnInDesign() }
                Button("Exportar de nuevo") { taller.exportar() }
                Spacer()
                Button("Subir las imágenes y depurar") { taller.seguirExportado() }.keyboardShortcut(.defaultAction)
            }

        case .subidaManual(let texto, let seguir):
            Label("Imágenes en Hélice", systemImage: "photo.on.rectangle").font(.headline)
            Text(texto).textSelection(.enabled).fixedSize(horizontal: false, vertical: true)
            HStack {
                Button("Reintentar la subida") { taller.reintentar() }
                Spacer()
                if seguir { Button("Seguir sin ellas") { taller.seguirSinImagenes() } }
                Button("Continuar") { taller.depurar() }.keyboardShortcut(.defaultAction)
            }

        case .depurado:
            depurado

        case .publicado(let texto):
            Label(texto, systemImage: "paperplane.fill").foregroundStyle(.green)
            Text("Pon el icono del capítulo en el panel de Hélice.").foregroundStyle(.secondary)
            HStack {
                Spacer()
                Button("Otro capítulo…") { taller.elegirIndd() }.keyboardShortcut(.defaultAction)
            }

        case .error(let texto):
            Label("Algo ha fallado", systemImage: "xmark.octagon.fill").foregroundStyle(.red).font(.headline)
            Text(texto).textSelection(.enabled).fixedSize(horizontal: false, vertical: true)
            HStack {
                Button("Elegir otro .indd…") { taller.elegirIndd() }
                Spacer()
                Button("Reintentar") { taller.reintentar() }.keyboardShortcut(.defaultAction)
            }
        }
    }

    @ViewBuilder
    private var depurado: some View {
        let conAvisos = taller.estadoDepurado != "OK"
        Label(conAvisos ? "HTML depurado con avisos: revísalos antes de \(taller.publicable ? "publicarlo" : "pegarlo")." : "HTML depurado sin avisos.",
              systemImage: conAvisos ? "exclamationmark.triangle.fill" : "checkmark.circle.fill")
            .foregroundStyle(conAvisos ? .orange : .green)
        if taller.cssNueva {
            HStack {
                Label(taller.cssCopiada ? "CSS nueva copiada: añádela al final de la CSS del libro en Hélice."
                      : "Este capítulo trae CSS nueva: cópiala y añádela al final de la CSS del libro en Hélice antes de publicar.",
                      systemImage: "paintbrush")
                    .foregroundStyle(taller.cssCopiada ? Color.secondary : Color.orange)
                    .fixedSize(horizontal: false, vertical: true)
                Spacer()
                Button(taller.cssCopiada ? "Copiar otra vez" : "Copiar la CSS nueva") { taller.copiarCSSNueva() }
            }
        }
        if !taller.yaPublicado.isEmpty {
            Text("Ya está publicado en Hélice (\(taller.yaPublicado)): las correcciones, en el panel.")
                .foregroundStyle(.secondary)
        } else if taller.publicable {
            Text("Se publicará en «\(taller.temaPublicacion)» como sección «\(taller.nombreCapitulo)». Solo se publica una vez: las correcciones, en el panel.")
                .foregroundStyle(.secondary)
        } else if taller.htmlCopiado {
            Text("HTML copiado al portapapeles: pégalo en Hélice con ⌘V.").foregroundStyle(.secondary)
        }
        HStack {
            Button("Ver en el navegador") { taller.verPreviaEnNavegador() }.disabled(taller.vista == nil)
            Button("Mostrar en el Finder") { taller.mostrarEnFinder(taller.rutaFinal) }
            Spacer()
            if taller.publicable {
                Button("Copiar el HTML") { taller.copiarHTML() }
                Button("Publicar en Hélice") { taller.publicar() }.keyboardShortcut(.defaultAction)
            } else {
                Button(taller.htmlCopiado ? "Copiar otra vez" : "Copiar el HTML") { taller.copiarHTML() }
                Button("Otro capítulo…") { taller.elegirIndd() }.keyboardShortcut(.defaultAction)
            }
        }
    }

    private func ruta(_ r: String) -> some View {
        Text(r).font(.caption).foregroundStyle(.secondary).textSelection(.enabled)
            .lineLimit(2).truncationMode(.middle)
    }

    private func tiempo(_ s: TimeInterval) -> String {
        let t = Int(s)
        return t < 60 ? "\(t) s" : "\(t / 60) min \(t % 60) s"
    }
}

// MARK: - Libro nuevo y estructura en Hélice

struct DatosLibro: Codable {
    struct Tema: Codable { var nombre: String; var capitulos: String; var seccion: String }
    struct Bloque: Codable { var nombre: String; var seccion: String; var temas: [Tema] }
    let id: String
    let nombre: String
    let carpetaFicheros: String
    let bloques: [Bloque]
}

struct InfoFuente: Codable, Identifiable {
    var archivo: String
    var familia: String
    var estiloIndesign: String
    var base: String
    var peso: Int
    var estilo: String
    var id: String { archivo }
}

final class TemaF: ObservableObject, Identifiable {
    let id = UUID()
    @Published var nombre: String
    @Published var capitulos: String
    @Published var seccion: String
    init(nombre: String = "", capitulos: String = "", seccion: String = "") {
        self.nombre = nombre; self.capitulos = capitulos; self.seccion = seccion
    }
}

final class BloqueF: ObservableObject, Identifiable {
    let id = UUID()
    @Published var nombre: String
    @Published var seccion: String
    @Published var temas: [TemaF]
    init(nombre: String = "", seccion: String = "", temas: [TemaF] = []) {
        self.nombre = nombre; self.seccion = seccion; self.temas = temas
    }
}

@MainActor
final class FormLibro: ObservableObject, Identifiable {
    let id = UUID()
    let nuevo: Bool
    var libroID = ""
    @Published var nombre = ""
    @Published var raiz = ""
    @Published var carpeta = ""
    @Published var nombreArchivos = ""
    @Published var sufijo = ""
    @Published var carpetaFicheros = ""
    @Published var tipoFuentes = "propias"
    @Published var fuentes: [InfoFuente] = []
    @Published var kit = ""
    @Published var familiasKit = ""
    @Published var bloques: [BloqueF] = [BloqueF(nombre: "Bloque 1", temas: [TemaF(nombre: "Tema 1")])]
    @Published var error = ""
    @Published var guardando = false

    init(nuevo: Bool) { self.nuevo = nuevo }

    init(editar d: DatosLibro) {
        nuevo = false
        libroID = d.id
        nombre = d.nombre
        carpetaFicheros = d.carpetaFicheros
        bloques = d.bloques.map { b in
            BloqueF(nombre: b.nombre, seccion: b.seccion, temas: b.temas.map { TemaF(nombre: $0.nombre, capitulos: $0.capitulos, seccion: $0.seccion) })
        }
    }

    var archivos: String { nombreArchivos.isEmpty ? nombre : nombreArchivos }
    /// El sufijo sin el guion de delante (lo pone ./libro nuevo)
    var sufijoLimpio: String {
        String(sufijo.trimmingCharacters(in: .whitespaces).drop(while: { $0 == "-" }))
    }
    var carpetaSalida: String {
        if !carpeta.isEmpty { return carpeta }
        return raiz.isEmpty ? "" : (raiz as NSString).appendingPathComponent("\(archivos) (APP)")
    }

    func elegirCarpeta(_ destino: ReferenceWritableKeyPath<FormLibro, String>, titulo: String) {
        let panel = NSOpenPanel()
        panel.title = titulo
        panel.canChooseDirectories = true
        panel.canChooseFiles = false
        panel.canCreateDirectories = true
        panel.directoryURL = URL(fileURLWithPath: self[keyPath: destino].isEmpty ? (raiz.isEmpty ? libros : raiz) : self[keyPath: destino])
        if panel.runModal() == .OK, let url = panel.url { self[keyPath: destino] = url.path }
    }

    func elegirFuentes() {
        let panel = NSOpenPanel()
        panel.title = "Elige las fuentes del libro"
        panel.message = "Todos los pesos y estilos que usa el libro (.otf o .ttf); se subirán a Hélice"
        panel.allowsMultipleSelection = true
        panel.allowedContentTypes = ["otf", "ttf"].compactMap { UTType(filenameExtension: $0) }
        panel.directoryURL = FileManager.default.homeDirectoryForCurrentUser.appendingPathComponent("Library/Fonts")
        guard panel.runModal() == .OK else { return }
        let rutas = (fuentes.map(\.archivo) + panel.urls.map(\.path))
        Task {
            let r = await lanzar("libro", ["fuentes"] + Array(Set(rutas)).sorted())
            do {
                fuentes = try decodificar([InfoFuente].self, r).sorted { ($0.familia, $0.peso, $0.estilo) < ($1.familia, $1.peso, $1.estilo) }
            } catch {
                self.error = "No se han podido leer las fuentes: \(error.localizedDescription)"
            }
        }
    }

    private func estructura() -> [[String: Any]] {
        bloques.map { b in
            ["nombre": b.nombre, "seccion": b.seccion,
             "temas": b.temas.map { ["nombre": $0.nombre, "capitulos": $0.capitulos, "seccion": $0.seccion] }]
        }
    }

    func validar() -> String {
        if nuevo {
            if nombre.trimmingCharacters(in: .whitespaces).isEmpty { return "Falta el nombre del libro" }
            if raiz.isEmpty { return "Falta la carpeta de los originales" }
            if sufijoLimpio.isEmpty { return "Falta el sufijo de las clases" }
            if sufijoLimpio.contains(where: { !($0.isASCII && ($0.isLetter || $0.isNumber)) }) {
                return "El sufijo de las clases solo puede llevar letras sin acento y números (el guion lo pone la app)"
            }
            if tipoFuentes == "propias" && fuentes.isEmpty { return "Elige las fuentes del libro (o marca Adobe Fonts)" }
        }
        for b in bloques {
            if b.nombre.isEmpty { return "Hay un bloque sin nombre" }
            for t in b.temas where t.nombre.isEmpty || t.capitulos.isEmpty {
                return "«\(b.nombre)»: cada tema necesita nombre y capítulos"
            }
        }
        return ""
    }

    func guardar(taller: Taller, cerrar: @escaping () -> Void) {
        error = validar()
        guard error.isEmpty else { return }
        var datos: [String: Any] = ["carpeta_ficheros": carpetaFicheros.isEmpty ? nombre : carpetaFicheros, "bloques": estructura()]
        var args = ["estructura", libroID]
        if nuevo {
            args = ["nuevo"]
            datos["nombre"] = nombre
            datos["raiz"] = raiz
            datos["carpeta"] = carpetaSalida
            datos["nombre_archivos"] = archivos
            datos["sufijo"] = sufijoLimpio
            if tipoFuentes == "propias" {
                datos["fuentes"] = ["tipo": "propias", "detalle": fuentes.map {
                    ["archivo": $0.archivo, "familia": $0.familia, "base": $0.base, "peso": $0.peso, "estilo": $0.estilo] as [String: Any]
                }]
            } else {
                var familias: [String: String] = [:]
                for l in familiasKit.components(separatedBy: "\n") {
                    let p = l.components(separatedBy: "=").map { $0.trimmingCharacters(in: .whitespaces) }
                    if p.count == 2 && !p[0].isEmpty && !p[1].isEmpty { familias[p[0]] = p[1] }
                }
                datos["fuentes"] = ["tipo": "adobe", "kit": kit, "familias": familias]
            }
        }
        guard let json = try? JSONSerialization.data(withJSONObject: datos) else { return }
        guardando = true
        Task {
            let r = await lanzar("libro", args, entrada: json)
            guardando = false
            if let obj = (try? JSONSerialization.jsonObject(with: Data(r.utf8))) as? [String: Any], obj["ok"] as? Bool == true {
                if let id = obj["id"] as? String { taller.libroID = id }
                taller.anotar((nuevo ? "Libro creado: " : "Estructura guardada: ") + ((obj["config"] as? String) ?? ""), .ok)
                taller.cargarLibros()
                cerrar()
            } else if let obj = (try? JSONSerialization.jsonObject(with: Data(r.utf8))) as? [String: Any], let e = obj["error"] as? String {
                error = e
            } else {
                error = r
            }
        }
    }
}

struct VistaFormLibro: View {
    @ObservedObject var form: FormLibro
    @ObservedObject var taller: Taller
    let cerrar: () -> Void
    @State private var cambiarNombre = false

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            Text(form.nuevo ? "Libro nuevo" : "«\(form.nombre)»: estructura en Hélice")
                .font(.title2.weight(.semibold))
                .padding([.top, .horizontal], 16)
            Form {
                if form.nuevo {
                    Section("Libro") {
                        TextField("Nombre", text: $form.nombre, prompt: Text("Ponencias SEO 2027"))
                        HStack {
                            TextField("Carpeta de los originales", text: $form.raiz)
                            Button("Elegir…") { form.elegirCarpeta(\.raiz, titulo: "Carpeta del libro (originales de InDesign)") }
                        }
                        if cambiarNombre {
                            HStack {
                                TextField("Nombre de los archivos", text: $form.nombreArchivos, prompt: Text(form.nombre.isEmpty ? "Ponencias 2027" : form.nombre))
                                Button("Como el libro") {
                                    form.nombreArchivos = ""
                                    cambiarNombre = false
                                }
                            }
                        } else {
                            LabeledContent("Nombre de los archivos") {
                                HStack {
                                    Text(form.archivos.isEmpty ? "(el del libro)" : form.archivos)
                                    Button("Cambiar…") { cambiarNombre = true }
                                }
                            }
                        }
                        Text("Cada capítulo preparado se guarda como «NN \(form.archivos.isEmpty ? "…" : form.archivos) (APP).indd», " +
                             "en su carpeta «NN \(form.archivos.isEmpty ? "…" : form.archivos) (APP)», dentro de:\n" +
                             (form.carpetaSalida.isEmpty ? "…" : form.carpetaSalida))
                            .font(.caption).foregroundStyle(.secondary)
                            .fixedSize(horizontal: false, vertical: true)
                        HStack {
                            TextField("Carpeta de salida (APP)", text: $form.carpeta, prompt: Text(form.carpetaSalida))
                            Button("Elegir…") { form.elegirCarpeta(\.carpeta, titulo: "Carpeta de la versión APP") }
                        }
                        TextField("Sufijo de las clases", text: $form.sufijo, prompt: Text("PO27"))
                        Text("Solo letras y números, sin guion: la app lo añade delante. " +
                             "Las clases quedarán así: «Texto-base-\(form.sufijoLimpio.isEmpty ? "PO27" : form.sufijoLimpio)». " +
                             "Tiene que ser distinto en cada libro, para que sus estilos no pisen los de otros libros en Hélice.")
                            .font(.caption).foregroundStyle(.secondary)
                            .fixedSize(horizontal: false, vertical: true)
                    }
                    Section("Fuentes") {
                        Picker("Fuentes", selection: $form.tipoFuentes) {
                            Text("Propias (se suben a Hélice)").tag("propias")
                            Text("Adobe Fonts (kit)").tag("adobe")
                        }
                        .pickerStyle(.segmented)
                        if form.tipoFuentes == "propias" {
                            ForEach($form.fuentes) { $f in
                                HStack {
                                    TextField("Familia", text: $f.familia).frame(minWidth: 160)
                                    Text("\(f.base) · \(f.peso) · \(f.estilo == "italic" ? "cursiva" : "redonda")")
                                        .font(.caption).foregroundStyle(.secondary)
                                    Spacer()
                                    Button { form.fuentes.removeAll { $0.archivo == f.archivo } } label: { Image(systemName: "minus.circle") }
                                        .buttonStyle(.borderless)
                                }
                                .help(f.archivo)
                            }
                            HStack {
                                Button("Elegir fuentes…") { form.elegirFuentes() }
                                Text("La familia tiene que ser la que usa InDesign.").font(.caption).foregroundStyle(.secondary)
                            }
                        } else {
                            TextField("Enlace del kit", text: $form.kit, prompt: Text("https://use.typekit.net/xxxxxxx.css"))
                            TextField("Familias (una por línea: Fuente de InDesign = familia web)", text: $form.familiasKit, axis: .vertical)
                                .lineLimit(2...5)
                        }
                    }
                }
                Section("Hélice: archivos") {
                    TextField("Carpeta en Ficheros", text: $form.carpetaFicheros, prompt: Text(form.nombre.isEmpty ? "Ponencias 2027" : form.nombre))
                    Text("La carpeta del libro en Ficheros de Hélice. Si no existe, la app la crea al subir lo primero. Dentro organiza:\n" +
                         "  · las imágenes de cada capítulo, en «Bloque / Tema / Capítulo NN»;\n" +
                         "  · las fuentes propias, en «Fuentes».\n" +
                         "Lo que ya está subido no se vuelve a subir.")
                        .font(.caption).foregroundStyle(.secondary)
                        .fixedSize(horizontal: false, vertical: true)
                }
                Section("Hélice: secciones del libro") {
                    AyudaHelice()
                    ForEach(form.bloques) { b in
                        EditorBloque(bloque: b) { form.bloques.removeAll { $0.id == b.id } }
                    }
                    Button("Añadir bloque") {
                        form.bloques.append(BloqueF(nombre: "Bloque \(form.bloques.count + 1)", temas: [TemaF(nombre: "Tema 1")]))
                    }
                }
            }
            .formStyle(.grouped)
            HStack {
                if !form.error.isEmpty {
                    Text(form.error).foregroundStyle(.red).font(.callout).fixedSize(horizontal: false, vertical: true)
                }
                Spacer()
                if form.guardando { ProgressView().controlSize(.small) }
                Button("Cancelar") { cerrar() }.keyboardShortcut(.cancelAction)
                Button(form.nuevo ? "Crear el libro" : "Guardar") { form.guardar(taller: taller, cerrar: cerrar) }
                    .keyboardShortcut(.defaultAction)
                    .disabled(form.guardando)
            }
            .padding(16)
        }
        .frame(width: 720, height: 680)
    }
}

/// Cómo se monta un libro en Hélice y qué hace la app con cada dato
struct AyudaHelice: View {
    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text("Así queda el libro en el panel de Hélice:")
            Text("""
                 Libro                     Menú, a mano
                 └─ Bloque 1               Menú, a mano   ← enlace del bloque
                    └─ Tema 1              Menú, a mano   ← enlace del tema
                       └─ Capítulo 01      Información: la crea la app al publicar, con el HTML
                 """)
                .font(.system(size: 11, design: .monospaced))
                .padding(8)
                .frame(maxWidth: .infinity, alignment: .leading)
                .background(Color.secondary.opacity(0.08), in: RoundedRectangle(cornerRadius: 6))
            Text("""
                 1. En el panel, crea a mano la sección del libro, un Menú por bloque dentro de ella y, dentro de cada bloque, un Menú por tema. La API de Hélice no puede crear Menús.
                 2. Abre cada Menú en el panel, copia la dirección del navegador y pégala aquí, en su fila. También vale solo su número de sección; la app se queda con ese número.
                 3. En «Capítulos», pon los capítulos de cada tema: «1-3, 5» son el 1, el 2, el 3 y el 5. Cada capítulo va en un solo tema.
                 4. Escribe los nombres de los bloques y de los temas igual que en el panel. Con esos nombres se crean también las carpetas de Ficheros.
                 """)
                .fixedSize(horizontal: false, vertical: true)
            Text("""
                 · Para publicar hace falta el enlace del tema. El del bloque es opcional y sirve de referencia.
                 · Al publicar, la app crea dentro del tema la sección «Capítulo NN» con el HTML depurado. Cada capítulo se publica una sola vez: las correcciones se hacen en el panel. Los iconos de las secciones se ponen a mano en el panel.
                 · Un capítulo cuyo tema no tiene enlace no se puede publicar: la app copia su HTML para que lo pegues tú.
                 · Si lo dejas a medias, puedes completarlo después en ⋯ › Editar la estructura en Hélice.
                 """)
                .foregroundStyle(.secondary)
                .fixedSize(horizontal: false, vertical: true)
        }
        .font(.caption)
    }
}

struct EditorBloque: View {
    @ObservedObject var bloque: BloqueF
    let quitar: () -> Void

    var body: some View {
        VStack(alignment: .leading, spacing: 6) {
            HStack {
                TextField("Bloque", text: $bloque.nombre).frame(width: 140)
                TextField("Enlace del Menú del bloque en Hélice", text: $bloque.seccion)
                Button(action: quitar) { Image(systemName: "trash") }.buttonStyle(.borderless).help("Quitar el bloque")
            }
            .font(.headline)
            ForEach(bloque.temas) { t in
                FilaTema(tema: t) { bloque.temas.removeAll { $0.id == t.id } }
                    .padding(.leading, 16)
            }
            Button("Añadir tema") { bloque.temas.append(TemaF(nombre: "Tema \(bloque.temas.count + 1)")) }
                .buttonStyle(.borderless)
                .padding(.leading, 16)
        }
        .padding(.vertical, 4)
    }
}

struct FilaTema: View {
    @ObservedObject var tema: TemaF
    let quitar: () -> Void

    var body: some View {
        HStack {
            TextField("Tema", text: $tema.nombre).frame(width: 110)
            TextField("Capítulos", text: $tema.capitulos, prompt: Text("1-3, 5")).frame(width: 90)
            TextField("Enlace del Menú del tema en Hélice", text: $tema.seccion)
            Button(action: quitar) { Image(systemName: "minus.circle") }.buttonStyle(.borderless)
        }
    }
}

// MARK: - Arranque
// La ventana se crea a mano (sin la escena de SwiftUI) para que aparezca también cuando
// la app se abre con un .indd soltado sobre su icono.

@main
@MainActor
final class Delegado: NSObject, NSApplicationDelegate {
    let taller = Taller()
    var ventana: NSWindow?
    var inddInicial: String?

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
        let v = NSWindow(contentRect: NSRect(x: 0, y: 0, width: 1400, height: 820),
                         styleMask: [.titled, .closable, .miniaturizable, .resizable],
                         backing: .buffered, defer: false)
        v.title = "InDesign a HTML"
        v.contentView = NSHostingView(rootView: Ventana(taller: taller))
        v.isReleasedWhenClosed = false
        v.setFrameAutosaveName("principal")
        if !v.setFrameUsingName("principal") { v.center() }
        v.makeKeyAndOrderFront(nil)
        ventana = v
        NSApp.activate(ignoringOtherApps: true)
        taller.cargarLibros()
        if let indd = inddInicial { taller.empezar(con: indd) }
    }

    // .indd soltado sobre el icono (al arrancar llega antes que DidFinishLaunching)
    func application(_ sender: NSApplication, open urls: [URL]) {
        guard let indd = urls.first(where: { $0.pathExtension.lowercased() == "indd" }) else { return }
        if ventana == nil {
            inddInicial = indd.path
        } else if !taller.trabajando {
            taller.empezar(con: indd.path)
        }
    }

    func applicationShouldTerminateAfterLastWindowClosed(_ sender: NSApplication) -> Bool { true }

    @objc func elegirIndd() {
        if !taller.trabajando { taller.elegirIndd() }
    }

    private func menu() -> NSMenu {
        let principal = NSMenu()

        let app = NSMenu()
        app.addItem(withTitle: "Ocultar InDesign a HTML", action: #selector(NSApplication.hide(_:)), keyEquivalent: "h")
        app.addItem(.separator())
        app.addItem(withTitle: "Salir de InDesign a HTML", action: #selector(NSApplication.terminate(_:)), keyEquivalent: "q")

        let archivo = NSMenu(title: "Archivo")
        archivo.addItem(withTitle: "Elegir un .indd…", action: #selector(elegirIndd), keyEquivalent: "o").target = self
        archivo.addItem(.separator())
        archivo.addItem(withTitle: "Cerrar", action: #selector(NSWindow.performClose(_:)), keyEquivalent: "w")

        let edicion = NSMenu(title: "Edición")
        edicion.addItem(withTitle: "Deshacer", action: Selector(("undo:")), keyEquivalent: "z")
        edicion.addItem(.separator())
        edicion.addItem(withTitle: "Cortar", action: #selector(NSText.cut(_:)), keyEquivalent: "x")
        edicion.addItem(withTitle: "Copiar", action: #selector(NSText.copy(_:)), keyEquivalent: "c")
        edicion.addItem(withTitle: "Pegar", action: #selector(NSText.paste(_:)), keyEquivalent: "v")
        edicion.addItem(withTitle: "Seleccionar todo", action: #selector(NSText.selectAll(_:)), keyEquivalent: "a")

        for submenu in [app, archivo, edicion] {
            let item = NSMenuItem()
            item.submenu = submenu
            principal.addItem(item)
        }
        return principal
    }
}
