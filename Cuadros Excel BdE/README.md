# Cuadros Excel BdE

App de Mac (SwiftUI) que maqueta, paso a paso, el Excel del **cuadro** que entrega el autor. Es una réplica de
«Gráficos Excel BdE» (misma ventana, mismas versiones adelante y atrás, Excel al lado), pero para cuadros:
tablas hechas en celdas, con la pastilla, «Cuadro N», el título, las unidades y la FUENTE como formas encima.

- Normas: `Resumen cuadros.pdf` (págs. 21-22 de la guía) y `Ejemplos cuadros.pdf` (con notas en rojo).
- Ejemplos: «Cuadros Excel ORIGINALES/TERMINADOS» (IA2025, Memoria de Supervisión) y «Cuadros Excel DO
  ORIGINALES/TERMINADOS» (Documentos Ocasionales; el TERMINADO lleva todos los cuadros del DO en un libro).
- Retícula, pastillas y marcos: hojas «Cuadro» y «Cuadro_Horizontal» de
  `SdE_Reticulas_Publicaciones_ImagenNueva2024_Roboto.xlsx` (copia de la de «Gráficos Excel BdE»).
- Compilar: `app/compilar_app.sh` (firma local con el identificador `es.estudioencuadre.cuadros-excel`). Como es
  una app nueva, macOS pide otra vez los permisos de **Automatización** (Excel) y **Accesibilidad**.
- La app se usa desde **Aplicaciones**; encuentra el motor por su ajuste
  `defaults write es.estudioencuadre.cuadros-excel motor "/Volumes/DATOS/Proyectos Codex/Cuadros Excel BdE/motor"`
  (sin él, lo busca junto a la app). `compilar_app.sh` también pone al día la copia de Aplicaciones si existe.
- Motor: `motor/maquetar_cuadros.py` (JSON por la salida estándar). Publicaciones en `motor/publicaciones.json`.
- **Color de la publicación**: cada publicación guarda un solo color, el **sólido**; de él salen los matices como en
  Excel (Resumen cuadros, pág. 22): matiz 1-3 un 80/60/40 % más claros y 4-5 un 25/50 % más oscuros. La
  **pastilla es el matiz 1** (comprobado con el archivo de retículas: 004081 → B3D9FF del Informe Anual, F06800 →
  FFE0C9 de los DO, A32938 → F3CED3 de las bianuales). La paleta de Excel queda en segundo plano (opcional).
  Publicación creada: «Informe Anual», sólido 004081.

## Cómo trabaja

- Se trabaja sobre una **copia**: del original `X.xlsx` sale `X maquetado.xlsx`, y cada paso deja su versión en
  `X maquetado (pasos)/` (`00 Copia exacta.xlsx`, `01 …`). Las dos copias de trabajo que se alternan en Excel,
  el «Reiniciar», el «No actualizar» vínculos y el Organizador visual funcionan igual que en Gráficos (ver su
  README).
- **Hoja del cuadro**: la primera hoja visible con el rótulo «Cuadro N» en sus formas; si ninguna lo tiene, la
  primera visible (los autores la llaman «Cuadro datos», «Cua», «C1», «Cuadro 2»…). Excel se abre en ella.
- Idioma: inglés si el nombre lleva «Ing» (`CIng_…`, `…_Ing`) o el rótulo es «Table N»; si no, castellano.
- Terminar: guarda «… TERMINADO.xlsx» («ORIGINALES» → «TERMINADOS») junto al original y borra copias y versiones.

## Pasos (se construyen y aprueban uno a uno)

0. **App y copia exacta** (hecho, 2026-11-13).
1. **Retícula, pastilla y textos** — pendiente.
2. **Celdas** — pendiente.
3. **Cabeceras** — pendiente.
4. **Líneas y fondos** — pendiente.
5. **Terminar** (comparar con el original y guardar) — guardar hecho; comparar pendiente.
