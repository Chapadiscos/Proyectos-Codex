# Viudas Huerfanas

Panel de InDesign 2027 (ExtendScript + ScriptUI) para ajustar a mano el espaciado de los párrafos, al estilo de Typefitter, y buscar viudas, huérfanas, líneas cortas y texto desbordado.

- `scripts/Viudas Huerfanas.jsx`: el panel.
- `scripts/Apretar un paso.jsx` y `scripts/Aflojar un paso.jsx`: para asignarles atajos en Edición → Métodos abreviados de teclado → Área de producto «Scripts».
- `scripts/lib/ajuste.jsxinc`: el motor común.
- `instalar.sh`: copia los scripts al panel Scripts de InDesign 2027 (carpeta «Viudas Huerfanas»). Hay que ejecutarlo de nuevo después de cada cambio.

## Niveles del deslizador (−10 apretar … +10 aflojar)

Cada nivel se calcula desde el estilo de párrafo, así que 0 equivale a los valores del estilo.

| Nivel | Qué cambia |
|---|---|
| 1–4 | Espaciado entre palabras (mín./deseado/máx.) ±5 % por paso, hasta ±20 % |
| 5–7 | Además, espaciado entre letras ±1/±2/±3 % y escala de glifos ±1/±1/±2 % |
| 8–10 | Además, tracking ±5/±10/±15, sumado al que tenga cada tramo del texto |

- **Colores:** usan texto condicional que no se imprime. Hay 6 condiciones, «VH · Apretado 1–3» y «VH · Aflojado 1–3», y respetan las demás condiciones que tenga el texto. «Quitar colores» borra esas condiciones y deja el texto y los ajustes.
- **Viuda:** la última línea de un párrafo queda sola al principio de una columna o página. **Huérfana:** la primera línea queda sola al final.
- **Línea corta:** la última línea mide menos del porcentaje indicado respecto a la línea más ancha del párrafo. No se aplica a párrafos centrados ni alineados a la derecha.
- La búsqueda solo mira el texto que está en páginas: deja fuera la mesa de trabajo, las tablas y las notas al pie.
