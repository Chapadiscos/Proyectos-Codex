// Dibuja el icono de la app (degradado violeta y una lupa con destellos) en la
// carpeta .iconset que se le pasa; compilar_app.sh lo convierte en icono.icns con iconutil.
import AppKit

let destino = CommandLine.arguments[1]
let colores = [NSColor(red: 0.31, green: 0.27, blue: 0.90, alpha: 1),
               NSColor(red: 0.58, green: 0.30, blue: 0.92, alpha: 1),
               NSColor(red: 0.85, green: 0.30, blue: 0.62, alpha: 1)]

func dibujar(_ lado: Int) -> Data {
    let rep = NSBitmapImageRep(bitmapDataPlanes: nil, pixelsWide: lado, pixelsHigh: lado, bitsPerSample: 8,
                               samplesPerPixel: 4, hasAlpha: true, isPlanar: false, colorSpaceName: .deviceRGB,
                               bytesPerRow: 0, bitsPerPixel: 0)!
    NSGraphicsContext.saveGraphicsState()
    NSGraphicsContext.current = NSGraphicsContext(bitmapImageRep: rep)
    let s = CGFloat(lado)
    // El margen y el redondeo de los iconos de macOS
    let forma = NSBezierPath(roundedRect: NSRect(x: s * 0.1, y: s * 0.1, width: s * 0.8, height: s * 0.8),
                             xRadius: s * 0.18, yRadius: s * 0.18)
    NSGradient(colors: colores)!.draw(in: forma, angle: -45)
    let conf = NSImage.SymbolConfiguration(pointSize: s * 0.36, weight: .semibold)
    if let simbolo = NSImage(systemSymbolName: "sparkle.magnifyingglass", accessibilityDescription: nil)?.withSymbolConfiguration(conf) {
        let blanco = NSImage(size: simbolo.size, flipped: false) { r in
            simbolo.draw(in: r)
            NSColor.white.set()
            r.fill(using: .sourceAtop)
            return true
        }
        let t = blanco.size
        blanco.draw(in: NSRect(x: (s - t.width) / 2, y: (s - t.height) / 2, width: t.width, height: t.height))
    }
    NSGraphicsContext.restoreGraphicsState()
    return rep.representation(using: .png, properties: [:])!
}

for lado in [16, 32, 128, 256, 512] {
    try! dibujar(lado).write(to: URL(fileURLWithPath: "\(destino)/icon_\(lado)x\(lado).png"))
    try! dibujar(lado * 2).write(to: URL(fileURLWithPath: "\(destino)/icon_\(lado)x\(lado)@2x.png"))
}
