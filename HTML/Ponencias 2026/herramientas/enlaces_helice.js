// Marcador «Enlaces Hélice»: copia al portapapeles las URL de todas las imágenes
// que aparecen en la página abierta del panel (carpeta de imágenes del capítulo).
// Versión legible; la de una línea está en instalar_marcador.html.
(() => {
  const re = /(?:https?:\/\/[^\s"'<>)]+)?\/uploads\/app\/\d+\/files\/[\w.-]+?\.(?:jpe?g|png|gif|webp)/gi;
  const urls = new Set();
  for (const m of document.documentElement.innerHTML.matchAll(re)) {
    urls.add(m[0].startsWith("/") ? location.origin + m[0] : m[0]);
  }
  const texto = [...urls].join("\n");
  if (!urls.size) return alert("No he encontrado enlaces de imágenes en esta página.");
  navigator.clipboard.writeText(texto).then(
    () => alert(urls.size + " enlaces copiados. Ahora ejecuta ./capitulo NN"),
    () => prompt("Copia estos enlaces (⌘C):", texto)
  );
})();
