# Crear Publicación

App de Mac (SwiftUI) para pasar un Word a InDesign en tres pasos independientes:

1. **Galerada**: importar el Word (clic o arrastrar) y recorrer las marcas.
2. **Tipografía**: revisar las correcciones una a una, contarlas o aplicarlas; buscar y revisar dudas (con Claude, si quieres).
3. **Cierre**: simular o finalizar el capítulo (puntuación con su formato, URLs y DOI enlazados).

Tipografía y Cierre trabajan con el **documento activo** de InDesign, con **uno elegido** en la lista de abiertos (o con «Abrir documento…»), o con **todos los abiertos**.

La app no tiene motor propio: usa los programas de `../Ventana Formatear Word Indesign/` (los .py en segundo plano y las ventanas .jsx dentro de InDesign) sin modificarlos. Para otra ruta:
`defaults write es.estudioencuadre.crear-publicacion motor "<ruta>"`.

- Compilar: `app/compilar_app.sh` → `Crear Publicación.app` en esta carpeta (no va a git).
- `jsx/abrir_en_indesign.jsx`: abre en InDesign las ventanas de revisión con el documento elegido delante, en el mismo motor (`formatear_word`) que la ventana de InDesign.
- La primera vez macOS pide permiso para que la app controle InDesign (Ajustes › Privacidad › Automatización).
