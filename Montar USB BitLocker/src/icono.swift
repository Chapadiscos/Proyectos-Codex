// Dibuja el icono: memoria USB con candado abierto sobre fondo azul redondeado.
import AppKit
func dibujar(_ s: CGFloat) -> NSBitmapImageRep {
  let rep = NSBitmapImageRep(bitmapDataPlanes: nil, pixelsWide: Int(s), pixelsHigh: Int(s), bitsPerSample: 8, samplesPerPixel: 4, hasAlpha: true, isPlanar: false, colorSpaceName: .deviceRGB, bytesPerRow: 0, bitsPerPixel: 0)!
  NSGraphicsContext.saveGraphicsState(); NSGraphicsContext.current = NSGraphicsContext(bitmapImageRep: rep)
  let k = s / 1024
  func R(_ x: CGFloat,_ y: CGFloat,_ w: CGFloat,_ h: CGFloat) -> NSRect { NSRect(x: x*k, y: y*k, width: w*k, height: h*k) }
  // Fondo (cuadrado redondeado de macOS, con margen)
  let fondo = NSBezierPath(roundedRect: R(100,100,824,824), xRadius: 185*k, yRadius: 185*k)
  NSGraphicsContext.saveGraphicsState()
  let sombra = NSShadow(); sombra.shadowColor = NSColor.black.withAlphaComponent(0.35); sombra.shadowBlurRadius = 24*k; sombra.shadowOffset = NSSize(width: 0, height: -10*k); sombra.set()
  NSGradient(colors: [NSColor(red: 0.20, green: 0.55, blue: 0.98, alpha: 1), NSColor(red: 0.05, green: 0.27, blue: 0.70, alpha: 1)])!.draw(in: fondo, angle: -90)
  NSGraphicsContext.restoreGraphicsState()
  // Memoria USB (inclinada)
  NSGraphicsContext.saveGraphicsState()
  let t = NSAffineTransform(); t.translateX(by: 470*k, yBy: 560*k); t.rotate(byDegrees: -35); t.concat()
  NSColor(white: 0.80, alpha: 1).setFill(); NSBezierPath(roundedRect: R(-80,150,160,150), xRadius: 14*k, yRadius: 14*k).fill()   // conector metálico
  NSColor(white: 0.45, alpha: 1).setFill(); NSBezierPath(rect: R(-45,225,30,40)).fill(); NSBezierPath(rect: R(15,225,30,40)).fill()
  NSGradient(colors: [NSColor(white: 0.98, alpha: 1), NSColor(white: 0.82, alpha: 1)])!.draw(in: NSBezierPath(roundedRect: R(-120,-260,240,430), xRadius: 50*k, yRadius: 50*k), angle: 0) // cuerpo
  NSColor(red: 0.05, green: 0.27, blue: 0.70, alpha: 0.9).setFill(); NSBezierPath(ovalIn: R(-25,-215,50,50)).fill() // anilla
  NSGraphicsContext.restoreGraphicsState()
  // Candado abierto (dorado), abajo a la derecha
  let oro = NSGradient(colors: [NSColor(red: 1.0, green: 0.84, blue: 0.35, alpha: 1), NSColor(red: 0.90, green: 0.60, blue: 0.10, alpha: 1)])!
  let arco = NSBezierPath(); arco.lineWidth = 46*k; arco.lineCapStyle = .round
  arco.move(to: NSPoint(x: 560*k, y: 440*k)); arco.line(to: NSPoint(x: 560*k, y: 520*k))
  arco.appendArc(withCenter: NSPoint(x: 660*k, y: 520*k), radius: 100*k, startAngle: 180, endAngle: 0, clockwise: true)
  arco.line(to: NSPoint(x: 760*k, y: 470*k))
  NSGraphicsContext.saveGraphicsState()
  let s2 = NSShadow(); s2.shadowColor = NSColor.black.withAlphaComponent(0.35); s2.shadowBlurRadius = 18*k; s2.shadowOffset = NSSize(width: 0, height: -8*k); s2.set()
  NSColor(white: 0.85, alpha: 1).setStroke()
  let a2 = arco.copy() as! NSBezierPath; let tr = NSAffineTransform(); tr.translateX(by: 40*k, yBy: 60*k); a2.transform(using: tr as AffineTransform); a2.stroke() // arco levantado = abierto
  oro.draw(in: NSBezierPath(roundedRect: R(500,180,330,280), xRadius: 40*k, yRadius: 40*k), angle: -90)
  NSGraphicsContext.restoreGraphicsState()
  NSColor(red: 0.45, green: 0.28, blue: 0.02, alpha: 1).setFill()
  NSBezierPath(ovalIn: R(637,320,56,56)).fill(); NSBezierPath(roundedRect: R(650,240,30,100), xRadius: 12*k, yRadius: 12*k).fill()
  NSGraphicsContext.restoreGraphicsState(); return rep
}
let dir = CommandLine.arguments[1]
for (n, s) in [("16",16),("32",32),("128",128),("256",256),("512",512)] as [(String,CGFloat)] {
  try! dibujar(s).representation(using: .png, properties: [:])!.write(to: URL(fileURLWithPath: "\(dir)/icon_\(n)x\(n).png"))
  try! dibujar(s*2).representation(using: .png, properties: [:])!.write(to: URL(fileURLWithPath: "\(dir)/icon_\(n)x\(n)@2x.png"))
}
