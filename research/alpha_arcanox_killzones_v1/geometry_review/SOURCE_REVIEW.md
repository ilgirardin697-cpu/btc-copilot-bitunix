# Dos capturas reales: segmento original y copia superior

**Comparación de archivos reales, no el esquema simbólico anterior.**
Continuación de `63a191b`, rama `alpha-arcanox-vertical-geometry-review`.
Se conservan intactos los 23 archivos originales del prototipo Alpha y todos
los resultados/ramas anteriores. Ninguna fórmula se registra para PAPER.

## Evidencia y reproducción

Se inspeccionaron `01_linea_original_circulos.png` (687×561) y
`02_linea_clonada_circulos.png` (485×436), además de ambos LEEME. SHA256:

```
01: 8cb3f56448834682d5195f7812d58cddc2bd193fe1f2184aa6256a6c23d8869a
02: 15e018e4440e91187e2e8ef5fd97222b12880f95e07fe7ad4aa2ad19987af5ac
```

[Galería vectorial de las capturas](artifacts/index.html) ·
[Lecturas reproducibles](artifacts/observations.json) · [Anotaciones](cases.json).
Los originales privados y las comparativas con el fondo real quedan LOCAL ONLY
en `research/cache/actual_blue_pair_review/`; nunca se alteran los PNG de origen.
Los SVG versionados trazan los elementos de esas fotos, sin inventar velas/OHLC.

Las posiciones se leen en píxeles, origen arriba-izquierda. Un análisis de color
detecta dos anillos azules de 80 píxeles cada uno por imagen, con diámetro de
14 píxeles entre extremos y radio visible aproximado de 7 píxeles. La resolución
de lectura es del orden de ±1 píxel; no implica precisión de precio o tick.

## 1. Los dos círculos y los recuadros

| Imagen / objeto | Centro superior (x,y) | Centro inferior (x,y) | Altura vertical |
|---|---|---|---:|
| 01: A, segmento ORIGINAL observado | (202,167) | (202,325) | 158 px |
| 02: B, copia SUPERIOR observada | (333,81) | (333,239) | 158 px |

En 01, el techo del recuadro izquierdo está en y=171 y el suelo del derecho en
y=329. Ambos centros están 4 píxeles por encima de esos bordes correspondientes.
Son alineaciones **aproximadas**, no coincidencias exactas centro-borde. La
distancia entre bordes también es 329−171=158 px en este ejemplo; no se extrapola
una regla de extremos globales para otros días ni para todas las mechas visibles.

El izquierdo es el recuadro superior y el derecho el inferior. Su identificación
Asia/Londres procede del contexto del propietario; el recorte no muestra horas
o etiquetas de sesión que permitan verificar independientemente ese calendario.

En 02, el recuadro inferior/derecho ocupa y=229…309. El círculo de apoyo de B
está en y=239: centro 10 px dentro de su techo; su borde alto está en y=232,
unos 3 px por debajo del borde de la caja. **El apoyo no está en el techo exacto.**
No se convierte automáticamente en HIGH ni en un máximo OHLC del mercado.
Los márgenes de 4 y 10 píxeles son lecturas de ESTAS imágenes, no constantes
del método, offsets de trading ni parámetros trasladables a otros zooms/días.
Se observa la posición final del apoyo, pero no una regla numérica que explique
por qué se eligió exactamente ese punto interior. No se atribuye esa función
a una de las otras líneas cian/rojas/verdes visibles.

## 2. Mismo tramo visible y clonación comprobada

Se usan seis esquinas moradas visibles de los recuadros para registrar las
imágenes, SIN utilizar los círculos de la copia o un target deseado. Las seis
coinciden bajo el desplazamiento de pantalla `(dx,dy)=(+57,−20)` px, con residual
0 px para esas coordenadas raster. El patrón de velas/mechas también coincide.
Esto vincula el tramo visual de las dos nuevas imágenes, no sus timestamps o venue.
Tampoco implica que se tomaran en el mismo instante o que la vela abierta no
hubiera cambiado entre capturas.

El original de 01 queda registrado en las coordenadas de 02 como:

```
A superior registrado: (202+57,167−20) = (259,147)
A inferior registrado: (202+57,325−20) = (259,305)
```

La posición de A en 02 se dibuja **ámbar discontinuo** porque allí no se ven
los círculos del original. No se presenta como una segunda medición observada.

Tomando SOLO el círculo inferior observado de la copia, `(333,239)`, el traslado
adicional es `(74,−66)`. Aplicado al círculo superior registrado:

```
(259,147) + (74,−66) = (333,81)
```

Predice exactamente el centro superior visible de B, sin ajustar con él. La
altura se conserva: 325−167 = 239−81 = 158 px, con Δx=0 en ambos segmentos.
**Es evidencia de una copia trasladada de la misma geometría en pantalla.**
El residual cero no prueba fórmula privada, precisión USDT, disponibilidad
prospectiva, ni que el anclaje se eligiera antes del movimiento visible.

## 3. Qué círculo apoya y qué falta en la copia inferior

**B observado:** apoya su círculo INFERIOR dentro de la zona alta del recuadro
inferior/derecho; su círculo SUPERIOR queda libre por encima. Eso sí puede
identificarse en la segunda imagen.

**C inferior:** no aparece una pareja de círculos que pruebe su colocación.
Se dibujan dos alternativas sobre la misma captura, ambas discontinuas y sin
selección por coincidencia con las mechas:

- `D_TOP`: círculo SUPERIOR dentro del borde alto del recuadro alto, con el
  anillo tocando ese borde por dentro. En 02, centro y=151+7=158; libre y=316.
- `D_BOTTOM`: círculo SUPERIOR dentro del borde bajo del recuadro alto, tocándolo
  por dentro. En 02, centro y=279−7=272; libre y=430.

Estas ubicaciones son **HIPÓTESIS de apoyo**, no círculos que se vean en la fuente.
Se usa el radio observado de 7 px para representar contacto interior. No se
traspasa el margen de 10 px del apoyo superior a la copia inferior ni se inventa
un offset simétrico. La x es el centro del recuadro SOLO para dibujar; no es un
anclaje temporal observado. Ninguna alternativa ha sido favorecida por precio,
mecha, resultado o por proximidad a INFERIOR=77095.25.

## 4. Matemática segura y límites de lo que significa

En pantalla, la copia observada satisface la traslación de ambos extremos y
preserva la altura vertical de 158 px. Los círculos están verticalmente alineados.
No se utilizan diagonales HH/LL ni una prolongación que confirme señales.

Si P+ y P− son los PRECIOS verificados de los círculos originales:

```
H = P+ − P−
Copia UP:   círculo inferior = A↑; círculo libre superior = A↑ + H
Copia DOWN: círculo superior = A↓; círculo libre inferior = A↓ − H
```

Las dos últimas igualdades en PRECIO requieren que la clonación conserve H en
la escala de precio utilizada. Las capturas prueban la geometría en píxeles;
no certifican escala lineal/log ni los dos precios completos de los anclajes.
Por eso `height_USDT` permanece UNKNOWN. El eje recortado y la etiqueta gris
del cursor no se convierten en un precio exacto del círculo inferior.

A↑ está identificado visualmente como apoyo interior observado, pero su precio
exacto no. A↓ ni siquiera está fijado. Tampoco se ha comprobado que un borde/centro
de círculo libre coincida exactamente con la etiqueta SUPERIOR o INFERIOR del
indicador: eso es distinto de reproducir un segmento dibujado.

No se deduce `SUPERIOR=HIGH+H` ni `INFERIOR=LOW−H`: requerirían, además, identificar
HIGH/LOW y demostrar su coincidencia con los apoyos respectivos. Los recortes
no tienen etiquetas HIGH/LOW oficiales. La línea gris de cursor y las curvas
de indicadores no se atribuyen a esos niveles.

## 5. Los cuatro niveles anteriores y la aceptación PAPER

Las dos nuevas capturas se vinculan entre sí por su escena, pero NO se han
vinculado al ejemplo HIGH=78285.00 / LOW=77517.20 / SUPERIOR=78653.44 /
INFERIOR=77095.25. No se mezclan sus coordenadas ni se calcula un residual o
un anclaje inverso para hacer coincidir esos targets.

| Resultado | Estado |
|---|---|
| A original identificado | Sí, dos círculos observados en 01 |
| B superior y apoyo identificados | Sí, dos círculos observados en 02 |
| Conservación de geometría en pantalla | Sí, 158 px; traslado registrado |
| C inferior y apoyo original | No; dos hipótesis explícitas |
| H exacta en USDT | No verificada |
| HIGH/LOW oficiales nuevos | No identificados |
| Reproducción numérica de los cuatro niveles anteriores | No establecida |
| PAPER operativo | BLOQUEADO, sin nuevas fórmulas aprobadas |

Los 23 archivos del prototipo padre siguen idénticos; horarios, confirmación,
ATR, SL, referencia al cierre, 1.5R y riesgo 0.25% no se modifican. No se hace
backtest, búsqueda de parámetros ni valoración de rentabilidad. Guardian V2,
V8, Railway y producción intactos. Sin órdenes, alertas, merge ni deploy.

Reproducir lecturas y comparativas locales (Pillow solo para leer los PNG):

```sh
python -m research.alpha_arcanox_killzones_v1.geometry_review.source_review \
  --source-dir /local/referencias_video/alpha_arcanox \
  --private-out research/cache/actual_blue_pair_review
```

SHADOW ONLY. TRADE AUTHORITY: NONE.

## Verificación local

- 81 tests dirigidos: prototipo padre, geometría y estas dos capturas; 0 fallos.
- Suite global con Python 3.12.12: 1114 tests, 0 fallos.
- Lectura real de ambos PNG: SHA256, dimensiones, anillos azules y seis
  esquinas moradas comprobados; originales sin modificación.
- Los 23 archivos congelados del prototipo padre conservan sus SHA256.
- Workflow de investigación actualizado para incluir los tests de estas
  anotaciones. Los tests de CI no simulan disponer de los PNG privados:
  validan contratos, anotaciones y reproducción de los SVG; la inspección
  de píxeles de las fuentes se ejecutó localmente con los archivos reales.
- Sin backtests ni acceso a servicios de producción durante esta revisión.
