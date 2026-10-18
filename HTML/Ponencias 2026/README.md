# Ponencias 2026: de InDesign HTML a Hélice

Depura el HTML de **Archivo > Exportar > HTML (heredado)** de InDesign para publicarlo en https://avpm.helice.app/.

## Instalación (una vez)
```sh
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

## Uso: app «InDesign a HTML» (del 33 en adelante)
La app está en `herramientas/InDesign a HTML.app`; arrástrala al Dock. Si cambias su código (`herramientas/InDesign a HTML.applescript`), vuelve a crearla con `herramientas/compilar_app.sh`.

1. **Abre la app** y elige el `.indd` del capítulo.
2. **InDesign lo exporta** a HTML (heredado) en su misma carpeta, con los ajustes HTML del propio documento (`herramientas/exportar_html.jsx`).
3. **Pausa:** se abre en el Finder la carpeta `…-web-resources/image`.
   - Sube esas imágenes a la carpeta del capítulo en Hélice (no los .jpg sueltos de la carpeta del capítulo).
   - Abre esa carpeta en Hélice y pulsa el marcador **«Enlaces Hélice»**, que copia las URL al portapapeles. Para instalarlo, abre `herramientas/instalar_marcador.html` y arrastra el botón a la barra de marcadores.
   - Vuelve a la app y pulsa **Continuar**.
4. **Depuración:** se genera `… - Helice.html` en la carpeta del capítulo. La vista previa y el informe van a `salida/` del proyecto.
   - **Sin avisos:** el HTML queda copiado en el portapapeles. Pégalo en Hélice con ⌘V.
   - **Con avisos:** se muestran y puedes ver la vista previa o copiarlo igualmente.
   - El enlace leído del QR de la cabecera se muestra como información, no como aviso.

La primera vez, macOS pedirá permiso para que la app controle InDesign y el Finder.

### Desde el Terminal
```sh
./capitulo 33                      # o la ruta al .indd, al .html o a la carpeta del capítulo
./capitulo 33 --copiar             # copia al portapapeles aunque haya avisos
```
Si el portapapeles solo contiene URL (las del marcador), se guardan en el `.txt` del capítulo; si no, se usan las que ya tenga el `.txt`.

Para un HTML suelto: `.venv/bin/python -m depurar ruta/al/archivo.html` (sale en `salida/`).

## Pasos (`depurar/pasos/`)
| Paso | Qué hace |
|---|---|
| `p01_estilos_capitulo` | Pasa a `style=""` lo que solo está en la CSS del capítulo: anulaciones de carácter (`CharOverride-N`), `noPartir`, e imágenes a tamaño natural, centradas y sin pasar del ancho del visor (el % de ancho se pone a mano si hace falta) |
| `p02_limpieza` | Quita clases e ids autogenerados, el `<link>` a la CSS local, los `span` y `div` sobrantes, y une los `span` partidos iguales |
| `p03_correcciones_indesign` | Errores de la exportación: caracteres invisibles, `<br>` finales, **pie de figura debajo de la imagen** y **jerarquía de viñetas** cuando una imagen parte la lista |
| `p04_imagenes` | Descarga las URL del `.txt` y las empareja **por contenido** con las imágenes locales; si InDesign ha recodificado un JPEG al reexportar, **por parecido visual** |
| `p05_reglas_helice` | Reglas del libro en Hélice (abajo) |
| `p06_inyectar` | Añade al `<head>` el `<link>` de Adobe Fonts (Typekit) |
| `p07_salida` | Página completa o fragmento, vista previa y aviso de clases sin regla en la CSS de Hélice o no permitidas (`P-rrafo-b-sico`) |

## Reglas del HTML en Hélice
1. Las imágenes no llevan texto alternativo (`alt=""`).
2. Los pies de figura van siempre debajo de la imagen.
3. Se respeta la jerarquía de las viñetas aunque haya imágenes entre ellas.
4. `<br>` entre un párrafo y una imagen, y entre la imagen o su pie y el párrafo siguiente, salvo si es un ladillo.
5. El HTML empieza con un `<br>`.
6. La cabecera `CXX` enlaza (en pestaña nueva) a la URL de su QR, que se lee automáticamente de la imagen.
7. Entre dos ladillos seguidos: `<p style="margin-top: -1.3em; margin-bottom: 0.3em;"></p>`.
8. Las imágenes `IBXX` (estrechas): `max-width: 60%; display: block; margin: 0 auto;`.

Todo se configura en `config/config.yaml`. `config/helice_ponencias2026.css` es una copia de la CSS subida a Hélice, solo para la vista previa.

## Por qué así
- Hélice solo tiene la CSS de los **estilos del libro**. Las clases `ParaOverride-N`, `CharOverride-N` e `#_idContainerNNN` se numeran por capítulo y no existen allí.
- Al emparejar las imágenes por orden (el antiguo `codigo.py`), en los capítulos 04, 09, 11, 17, 19 y 32 quedaron imágenes cruzadas. Por contenido no puede pasar.

## Tests
```sh
.venv/bin/python -m pytest
```
