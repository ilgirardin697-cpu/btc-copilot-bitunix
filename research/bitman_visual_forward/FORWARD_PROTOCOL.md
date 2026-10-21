# BITMAN ENTRY FORWARD RESEARCH V0 — DISEÑO

**POST-HOC CANDIDATE SELECTION. HYPOTHESIS FOR FORWARD OBSERVATION.**
SHADOW ONLY. TRADE AUTHORITY: NONE.
Este PR solo aporta contratos puros y pruebas offline. No contiene observer,
scheduler, host, worker, fetcher, journal en disco ni integración productiva.

## Identidad y activación futura
ID: BITMAN_ENTRY_FORWARD_RESEARCH_V0_DESIGN; schema1.
protocol_manifest.json fija fuentes/constantes y selección. No es el protocolo
BITMAN_WEEKLY_FORWARD_V1 y no comparte journal, estado ni interpretación.

activation_at queda UNSET. Una revisión independiente debe fijar una hora UTC
futura y aprobar datos/almacenamiento antes de construir o activar nada.
El primer registro real deberá incluir hora efectiva, plan/hash, source SHA,
versión, seed, bootstrap hash, source venue y última vela de warmup.
No hay un registro real de activación en este PR.

Solo una vela que ABRA después o en activation_at y cierre posteriormente puede
generar una observación prospectiva. Warmup conserva hashes de mercado y estado
técnico, nunca señales históricas forward. Un cierre recuperado después del
siguiente cierre1H se registra LATE_RECOVERY_NOT_PROSPECTIVE, sin nueva entrada.
Nunca backdatear created_at/observed_at ni resucitar setups pasados.

## Candidatos elegidos POST-HOC
Solo A AO_CONTEXT + STRUCTURE_2R; A AO_FE + STRUCTURE_2R; y A AO_ONLY + STRUCTURE_2R
como referencia. La elección usa PR33f719472…; NO es selección independiente.
No se cambian PR33, sus resultados ni parámetros. No buscamos otra duración,
umbral FE, AO, DMI, ADX, stop o target después de observar resultados.

A: s*AO>0 en t,t−1,t−2; s*slope[t]>0; s*slope[t−1]<0 y s*slope[t−2]<0.
s=+1 LONG hipotético, −1 SHORT hipotético.
Contexto: s*AO4H>0, s*AO1D>0, y cierre rompe máximo previo3/ mínimo previo3.
FE: gamma13 público actual < anterior; FE desconocido excluye AO_FE, no se sustituye.
Stop: mínimo previo6 −0.25ATR LONG; máximo previo6 +0.25ATR SHORT.
Al conocerse precio de entrada, riesgo válido0.5–4ATR. Target2R, máximo48h.
No fallback ATR, trailing, breakeven ni decisiones discrecionales.

Un anchor AO compartido cada>=48h, incluso si los filtros rechazan todos salvo
AO_ONLY. El reloj de anchors comienza en activación, no heredando señales forward
históricas. No reponer señales filtradas para aumentar n. Conservar también
horas sin evento, cooldowns, datos ausentes y entradas invalidadas.
Las comparaciones entre candidatos son anidadas y nunca se suman como trades
independientes.

## AO + ADX/DMI como diagnóstico predeclarado
Guardar ADX, slope, slope anterior y turno<=0→>0; DI+/− y dominancia relativa
al lado hipotético. Estratos fijos: giro ADX sí/no × DMI supporting sí/no.
No son nuevos filtros operativos de los tres candidatos. Reportar los cuatro
estratos, incluido el desfavorable, sin elegir uno después.
Esto permite medir la motivación visual sin cambiar las reglas seleccionadas.

## Fuente, causalidad y warmup
BTCUSDT / BINANCE_USDM_PERPETUAL exclusivamente; no Bitunix, Spot ni fallback.
Velas normales, no Heikin Ashi/Renko. 1H cerrado;4H/1D agregados completos UTC,
con available_at<=cierre de señal. Sin pivots futuros.
Warmup propuesto300 días cerrados, fijado/hash antes de activación. Preservar
ese prefijo y continuar RMA/ventanas causalmente; no reseedear una ventana móvil
en restart y fingir identidad. Se documentará cualquier gap y el reset resultante.
La semilla difiere del inicio2020 de PR33; no prometer igualdad exacta de RMA sin
prefijos iguales. AO finito conserva5/34; FE13 y ATR14 no se modifican.

El gateway actual solo permite1H; NO provee5m ni funding. Este diseño necesita
un contrato de datos oficial/autorizado adicional, sujeto a aprobación separada.
No se implementa, no se amplía el gateway y no se evade HTTP451.
Nunca reconstruir velas faltantes ni usar un dataset distinto.

## Señal, disponibilidad y entrada
Guardar available_at teórico, observed_at real, source_received_at y committed_at.
El next1H open de PR33 coincide con el cierre de señal; puede estar ya pasado
cuando se detecta. NO fingir un fill causal allí.

Primario prospectivo: primera apertura5m estrictamente posterior a observed_at,
con ENTRY_PLAN persistido antes de dicha apertura. El precio se incorpora después
con entry_time lógico y entry_recorded_at real. Es una estimación paper precomprometida,
no una ejecución ni una observación de precio anticipada.
Si el plan no quedó persistido antes, NO crear ese fill.
Se permite recuperar el precio de un plan previo inmutable con un registro
RECOVERY y subtipo RECOVERED_PAPER_PRICE, manteniendo created_at real; no crear señales retrospectivas.

Esto es una adaptación operacional explícita, no un cambio de los parámetros
técnicos seleccionados. Sus resultados NO son directamente los fills ideales
de PR33. La referencia ideal puede registrarse aparte como COUNTERFACTUAL,
nunca como entrada disponible en tiempo real.

El stop absoluto queda fijado con los datos de señal. Target queda PENDING hasta
conocer apertura paper y riesgo. Gap que deja riesgo fuera de límites o nivel
no positivo => ENTRY_INVALIDATED, registrado, sin sustituir la oportunidad.

## Seguimiento, costes y maduración
Cada 5m cerrado durante 48h alimentaría BAR_ATTESTATION con subtipo PATH_UPDATE,
hash/fuente/received_at, dentro de los tipos de registro definidos abajo.
Primer stop/target/time determina PAPER_EXIT; mismo5m tocando ambos => adverso
primero, gap adverso a apertura y target sin mejora favorable. Preservar el
framework PR33 y documentar la resolución intrabar limitada.

OUTCOME_MATURED únicamente después de entry_time+48h; no contar una operación
pendiente como ganadora. Conservar gross/net R, retorno, MAE/MFE conservadores,
duración, ambigüedad, motivo de salida, excursiones y evolución temporal.
El mercado posterior al exit puede ser diagnóstico48h separado, no PnL añadido.

BASE fee5bp+slip1bp por lado; CONSERVATIVE7.5+3; STRESS10+5.
Aplicar sobre nominal de entrada/salida, como PR33. Funding con rate y timestamps
reales; mark exacto si existe o proxy declarado, nunca llamarlo coste exacto
cuando es estimado. Créditos ambiguos no se conceden.
Funding desconocido => NET UNKNOWN, nunca0. Posterior COST_COMPLETION es un
nuevo registro, con hora real; no reescribe el outcome incompleto.
Gap/partial/revisión de path => CENSORED; mantener el evento y denominador,
incluidas razones y fecha de descubrimiento. No filtrar por completitud futura
en el instante de señal, a diferencia del censor histórico previo al análisis.

## Referencias
AO_ONLY es la referencia principal de filtros. Registrar todos los anchors,
incluidos los rechazados por CONTEXT/FE, para medir oportunidad perdida y valor
incremental sin variar el universo.

Referencia calendario adicional: lunes/jueves00UTC, lado derivado de SHA256(seed,
timestamp), independiente del precio. Slots separados>=72h. Se comprometen
por calendario antes del futuro dato, y cada slot se registra aunque falle datos,
no tenga stop válido o resulte desfavorable.
No copiar el matching retrospectivo de PR33 como si eligiera causalmente una
fecha futura del mismo mes. Comparaciones posteriores pueden estratificar todos
los registros ya prospectivos por mes, lado y régimen4H SMA200, sin escogerlos
por PnL. Informar unmatched/exclusiones y dependencia entre familias.

## Journal futuro: propuesta, NO implementado aquí
Registro append-only independiente con record_id determinista, schema/protocol,
activation_id, logical_key, created_at real, available_at/observed_at, mercado,
hashes de inputs, prev_hash y record_hash.
Tipos: ACTIVATION, WARMUP_ATTESTATION, BAR_ATTESTATION, SIGNAL_ASSESSMENT,
ENTRY_PLAN, PAPER_ENTRY, ENTRY_INVALIDATED, PAPER_EXIT, OUTCOME_MATURED, CENSORING, DATA_GAP,
DATA_REVISION, RECOVERY, CONTROL_REFERENCE, COST_COMPLETION.

SIGNAL_ASSESSMENT guarda features congeladas, lado hipotético y cada condición
presente/faltante por candidato. Ningún dato posterior modifica esa fila.
IDs repetidos con igual payload => no write; conflicto => fail closed.
Hash-chain rota => no reparar/truncar/sobrescribir, observador degradado.
Restart debe reproducir prefijo, continuar horas faltantes en orden y distinguir
RECOVERY de observación prospectiva. Todo fallo permanece fuera del trading.

Un writer posterior requerirá lock de escritor único, flush+fsync, pruebas de
crash/fsync/truncation y estado derivado reconstruible. ledger_contract.py SOLO
prueba estructuras en memoria, no demuestra durabilidad de filesystem ni
autenticidad frente a un atacante capaz de rehacer toda la cadena.
Conservar tips independientes para detección de reescritura completa.

## Análisis y tamaño de muestra
Reportar todos los candidatos/lados/meses, rechazos, censura, latencia y tasas
de completitud. Bootstrap por bloques30 días, comparación conjunta anidada,
costes, ex-best1/3 y años/regímenes, sin optimizar luego. Los estratos ADX/DMI
son descriptivos; cualquier regla nueva requerirá otro protocolo y otra muestra.

Dos contrastes primarios: CONTEXT−AO_ONLY y FE−CONTEXT. Para conclusiones formales
preespecificar corrección por ambos, y exigir esperanza neta conservadora más
ventaja incremental con incertidumbre positiva y estabilidad. No prometer que
un N fijo valide nada. Ventana administrativa12 meses, informes descriptivos
trimestrales; no parar por rentabilidad o significancia.
Revisión final puede seguir siendo INSUFFICIENT aun tras12 meses.
No escalar a ejecución, alertas o gates por decisión automática.

## Estado
NO-GO para construir un observer conectado mientras falten referencia verificable,
contrato5m/funding, revisión de latencia y aprobación del writer/recovery.
GO únicamente para recoger exportaciones y continuar validación offline.
No activar ni crear flags, servicios, dominios, redes, bots o credenciales.
