#targetengine "indesign_mcp"
// Añade Ventana > Buscar con Claude al arrancar InDesign (proyecto InDesign MCP).
var INDESIGN_MCP = "/Volumes/DATOS/Proyectos Codex/Ventana Buscar con Claude en Indesign";
$.evalFile(File(INDESIGN_MCP + "/jsx/menu.jsx"));
