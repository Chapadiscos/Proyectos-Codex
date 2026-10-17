# Ponencias 2026: de InDesign HTML a Hélice

Depura el HTML de **Archivo > Exportar > HTML (heredado)** de InDesign para publicarlo en https://avpm.helice.app/.

## Instalación (una vez)
```sh
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

## Uso, capítulo a capítulo (del 33 en adelante)
Todo se hace en la carpeta del capítulo en el servidor (`libro.carpeta` en `config/config.yaml`).

1. **InDesign:** exporta el capítulo con *Archivo > Exportar > HTML (heredado)* en su carpeta.
2. **Hélice:** sube a la carpeta del capítulo las imágenes de `…-web-resources/image/` (no los .jpg sueltos de la carpeta).
3. Abre esa carpeta en Hélice y pulsa el marcador **«Enlaces Hélice»**: copia las URL al portapapeles.
   Para instalarlo, abre `herramientas/instalar_marcador.html` y arrastra el botón a la barra de marcadores.
4. En el Terminal:
   ```sh
   ./capitulo 33
   ```
   - Si el `.txt` del capítulo está vacío, guarda en él las URL del portapapeles. Si no hay URL, te dice qué imágenes subir.
   - Genera en la carpeta del capítulo `… - Helice.html` (el que se sube). La vista previa (`… - Helice.vista.html`) y el informe (`… - Helice.informe.txt`) van a `salida/` del proyecto.
   - Copia el HTML al portapapeles y abre la vista previa.
5. Revisa el informe y la vista previa, y pega el HTML en Hélice (⌘V).

Para un HTML suelto: `.venv/bin/python -m depurar ruta/al/archivo.html` (sale en `salida/`).

## Pasos (`depurar/pasos/`)
| Paso | Qué hace |
|---|---|
| `p01_estilos_capitulo` | Pasa a `style=""` lo que solo está en la CSS del capítulo: anulaciones de carácter (`CharOverride-N`), `noPartir`, e imágenes a tamaño natural, centradas y sin pasar del ancho del visor (el % de ancho se pone a mano si hace falta) |
| `p02_limpieza` | Quita clases e ids autogenerados, el `<link>` a la CSS local, los `span` y `div` sobrantes, y une los `span` partidos iguales |
| `p03_correcciones_indesign` | Errores de la exportación: caracteres invisibles, `<br>` finales, **pie de figura debajo de la imagen** y **jerarquía de viñetas** cuando una imagen parte la lista |
| `p04_imagenes` | Descarga las URL del `.txt` y las empareja **por contenido** con las imágenes locales |
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
