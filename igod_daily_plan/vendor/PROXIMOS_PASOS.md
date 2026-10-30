# Integración segura (lista concreta de trabajo)

## Hecho en el ZIP

- Motor causal AO/ADX/DMI/BBWP (aproximado) + estructura 1H/4H + vigilancia semanal.
- Candidatos A/B, dos objetivos basados en pivotes, invalidación y cálculo conjunto de exposición/peor pérdida **modelada**.
- Datos Binance USD-M permitidos por GET `fapi/v1/klines` y sin credenciales.
- Pruebas sintéticas para LONG, SHORT y fail-closed.

## No hecho todavía

- Verificación numérica con la configuración exacta de AO, ADX, BBWP instalada en TradingOne 2.3.21.
- Alimentación pública LIVE validada en el entorno de Railway de este nuevo componente.
- Registro programado 07:00–09:00 Europa/Madrid + aviso de cambio confirmable en 1D/1W.
- Conexión al Telegram autorizado, sin secretos en repositorio y sin rutas de trading.
- Simulación forward independiente de los dos tramos con costes, barreras, potencial de gap y métricas de rendimiento.
- Aprobación para activar dinero real. No debería considerarse hasta que haya una ventaja verificada y controles de riesgo que sobrevivan a escenarios extraordinarios.

## Qué NO debe hacer Work / quien integre esto

- No `merge`, no editar V8 ni Guardian, no modificar `V8_LIVE_EXECUTION` ni habilitar órdenes reales.
- No editar archivos hash-protegidos ni reutilizar el journal PAPER V0 desde una versión con protocolo distinto.
- No promediar automáticamente sin nueva confirmación 15m, no incrementar margen/apalancamiento en una posición perdiendo.
- No rellenar datos de velas incoherentes, gaps, fuentes de distintas venues o valores BBWP faltantes.
- No describir como "señal en vivo" las capturas del 30/10/2026: las velas 1D/1W de esos gráficos aún estaban abiertas.
