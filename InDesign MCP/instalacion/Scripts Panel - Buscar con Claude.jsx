#targetengine "indesign_mcp"
// Lanzador de la ventana «Buscar con Claude» (proyecto InDesign MCP).
var INDESIGN_MCP = "/Volumes/DATOS/Proyectos Codex/InDesign MCP";
$.evalFile(File(INDESIGN_MCP + "/jsx/buscador.jsx"));
