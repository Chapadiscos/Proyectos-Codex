#targetengine "indesign_mcp"
// Lanzador de la ventana «Buscar con Claude» (proyecto InDesign MCP).
var INDESIGN_MCP = "/Volumes/DATOS/Proyectos Codex/Ventana Buscar con Claude en Indesign";
$.evalFile(File(INDESIGN_MCP + "/jsx/buscador.jsx"));
