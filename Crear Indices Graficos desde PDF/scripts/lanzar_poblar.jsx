// Lanzador: edita las 4 rutas de abajo y ejecuta este archivo en InDesign
// (Archivo > Scripts > Otro script...) o vía "do script" desde fuera.
//
// TEMPLATE_PATH -> el .indd plantilla ("Indices limpio.indd"), nunca se modifica
// JSON_PATH     -> el .jsx generado por extraer_indice.py (paso 2)
// OUTPUT_PATH   -> dónde guardar el .indd resultante (se crea nuevo, no sobrescribe la plantilla)
// LOG_PATH      -> un .txt con el registro de lo que hizo el script

var CARPETA = "/Volumes/DATOS/Proyectos Codex/Crear Indices Graficos desde PDF/";

var TEMPLATE_PATH = CARPETA + "Indices limpio.indd";
var JSON_PATH = CARPETA + "scripts/indice_extraido.jsx";
var OUTPUT_PATH = CARPETA + "Indice_InformeAnual2025.indd";
var LOG_PATH = CARPETA + "scripts/poblar_log.txt";

$.evalFile(CARPETA + "scripts/poblar_indice.jsx");
