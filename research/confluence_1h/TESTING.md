# Validación efectiva

- Python3.12: **1065 tests globales,0 fallos**.
- Suite nueva: **32 tests,0 fallos**.
- Cuatro tests sintéticos originales del ZIP:4/4. No son evidencia de edge.
- Guardian/ML RSI safety PASS. V8 frozen refs PASS.
- Weekly boundary9/9; operabilidad boundary7/7. Guardas originales intactas.
- 151 archivos base protegidos sin cambios.
- Las900 combinaciones conservan WAIT780, WATCH_LONG59, WATCH_SHORT59,
  READY_LONG1, READY_SHORT1; SHA normalizado `1ffcf53c6b056e7bdf3b780f1fc4ebce49616363a66467e573c5c1a2ef71f014`.
- Diez artifacts numéricos reproducidos byte a byte, sin red, nuevos parámetros
  ni nuevas observaciones. Los hashes están en artifacts/reproducibility.json.
- 33 hashes verificados leyendo los bytes desde Git. Salidas LF explícitas;
  comprobación adicional demuestra que normalizar CRLF no cambia valores,
  decisiones ni PnL. El test de artifacts también funciona sin CSV sin comprimir.
- Compilación y ejecución real Pine: NO realizadas. Logs reales:0.
- Datos del incidente recibidos públicamente y calculados causalmente;
  observación post-hoc, nunca evidencia forward o un outcome24h fabricado.

Los dos fallos AST bajo Python3.13 se reproducen en la base intacta. Un intento
con Python3.12 embebido falló por import paths de sus children, no por fórmulas.
La ejecución final usa el entorno Python3.12 normal de las guardas. Una guarda
detectó una palabra reservada en una frase del generador de informe: se cambió
la frase, nunca el canario, protocolo o módulo protegido. La suite final queda
verde. Logs completos locales fuera de Git; hashes en validation.json.

CI remoto se informa únicamente después de consultar el HEAD publicado.
No descargas de mercado, entrenamiento, Railway o servicios durante la CI.
No modificación de producción, flags, volumen, Telegram, órdenes o credenciales.

SHADOW ONLY. TRADE AUTHORITY: NONE.
