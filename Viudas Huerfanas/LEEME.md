# Viudas Huerfanas

Panel de InDesign 2027 (ExtendScript + ScriptUI) para ajustar a mano el espaciado de los párrafos, al estilo de Typefitter, y buscar viudas, huérfanas, líneas cortas y texto desbordado.

## Qué hace

**Ajuste del párrafo**
- **Deslizador** de −10 (apretar) a +10 (aflojar). Cambia el párrafo en tiempo real y siempre parte de su estilo, así que en 0 queda como el estilo. Ajusta por tramos:
  - Pasos 1–4: espacio entre palabras.
  - Pasos 5–7: además, espacio entre letras y escala de glifos.
  - Pasos 8–10: además, tracking.
- **−1 línea / +1 línea:** aprieta o afloja lo justo para que el párrafo pierda o gane una línea.
- **Restablecer:** devuelve el párrafo a los valores de su estilo.
- **Colorear ajustes:** marca lo apretado en magenta y lo aflojado en violeta, más intenso cuanto mayor es el ajuste. Usa texto condicional, así que no se imprime. «Quitar colores» borra las marcas y deja los ajustes.
- El panel muestra el paso aplicado, cuántas líneas tenía el párrafo y cuántas tiene ahora, y los valores de espaciado.

**Buscar problemas** (en todo el documento o en el artículo)
- **Viudas:** la última línea de un párrafo queda sola al principio de una columna o página.
- **Huérfanas:** la primera línea queda sola al final de una columna o página.
- **Líneas cortas:** la última línea mide menos del porcentaje que indiques (20 % por defecto).
- **Texto desbordado.**

Al hacer clic en un resultado, se selecciona el párrafo y se puede ajustar con el deslizador.

**Atajos:** los scripts «Apretar un paso» y «Aflojar un paso», para asignarles teclas.

Todo se deshace con Cmd+Z, un paso por acción; un arrastre entero del deslizador también cuenta como un solo paso.

## Archivos

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

- **Colores:** usan texto condicional que no se imprime. Hay 6 condiciones, «VH · Apretado 1–3» (magenta) y «VH · Aflojado 1–3» (violeta), y respetan las demás condiciones que tenga el texto. «Quitar colores» borra esas condiciones y deja el texto y los ajustes.
- **Viuda:** la última línea de un párrafo queda sola al principio de una columna o página. **Huérfana:** la primera línea queda sola al final.
- **Línea corta:** la última línea mide menos del porcentaje indicado respecto a la línea más ancha del párrafo. No se aplica a párrafos centrados ni alineados a la derecha.
- La búsqueda solo mira el texto que está en páginas: deja fuera la mesa de trabajo, las tablas y las notas al pie.
