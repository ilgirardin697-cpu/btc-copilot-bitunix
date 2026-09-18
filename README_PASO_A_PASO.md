# GUÍA PASO A PASO — BTC COPILOT + TELEGRAM + GITHUB + RAILWAY

No necesitas API keys de Bitunix. El bot SOLO lee datos públicos y te avisa por Telegram.

---

## PARTE 1 — CREAR EL BOT DE TELEGRAM

1. Abre Telegram.
2. Busca exactamente: `@BotFather`.
3. Pulsa START.
4. Escribe: `/newbot`
5. BotFather te pedirá un nombre. Puedes poner:
   `IGOD BTC Copilot`
6. Luego te pide un username. Debe terminar en `bot`. Ejemplo:
   `IGOD_BTC_Copilot_bot`
7. BotFather te dará un TOKEN largo.

IMPORTANTE:
- NO lo publiques.
- NO lo metas en GitHub.
- Lo utilizaremos únicamente como Variable de Railway.

8. Ahora abre tu nuevo bot en Telegram.
9. Pulsa START o escribe `/start`.

---

## PARTE 2 — SACAR TU CHAT ID

1. Descomprime este ZIP en el Escritorio.
2. Entra en la carpeta.
3. Haz doble clic en:
   `1_OBTENER_CHAT_ID.bat`
4. La primera vez instalará lo necesario.
5. Cuando te lo pida, pega el TOKEN de BotFather.
   El token no se mostrará en pantalla.
6. Te mostrará un número, por ejemplo:
   `123456789`
7. Ese número es tu `TELEGRAM_CHAT_ID`.
8. Guárdalo junto con el TOKEN.

---

## PARTE 3 — SUBIR EL PROYECTO A GITHUB

1. Entra en GitHub.
2. Pulsa `+` -> `New repository`.
3. Nombre:
   `btc-copilot-bitunix`
4. Marca `Private`.
5. Pulsa `Create repository`.

Ahora en el repositorio vacío:

6. Pulsa `uploading an existing file`
   (o `Add file` -> `Upload files`).
7. Arrastra TODOS los archivos de esta carpeta:
   - main.py
   - telegram_setup.py
   - requirements.txt
   - railway.json
   - .gitignore
   - .env.example
   - README.md
   - README_PASO_A_PASO.md
   - 1_OBTENER_CHAT_ID.bat
8. NO subas `.venv`.
9. NO subas ningún archivo que contenga tu token.
10. Pulsa `Commit changes`.

---

## PARTE 4 — RAILWAY 24/7

1. Entra en Railway.
2. Pulsa `New Project`.
3. Elige `Deploy from GitHub repo`.
4. Si lo pide, conecta tu cuenta GitHub.
5. Selecciona:
   `btc-copilot-bitunix`

Railway detectará Python por `requirements.txt`.
`railway.json` le indica que arranque con:

`python main.py`

### VARIABLES

Antes o después del primer deploy, entra en tu servicio -> `Variables`.

Añade:

`TELEGRAM_BOT_TOKEN`
Valor = el token secreto que te dio BotFather.

Añade:

`TELEGRAM_CHAT_ID`
Valor = el número que sacaste con `1_OBTENER_CHAT_ID.bat`.

Puedes añadir también:

`TIMEZONE`
`Europe/Madrid`

No necesitas ninguna API key de Bitunix.

Al guardar las variables, Railway volverá a desplegar el servicio.

---

## PARTE 5 — COMPROBAR QUE FUNCIONA

En Railway abre:

`Deployments` -> último deployment -> `View Logs`

Deberías ver algo parecido a:

`BTC COPILOT TELEGRAM starting...`

`Public Bitunix data only — NO order execution.`

y después:

`READY`

En Telegram deberías recibir:

`BTC Copilot conectado`

junto al estado actual de BTCUSDT.

---

## QUÉ MENSAJES TE ENVIARÁ

### Cada mañana

`☀️ PLAN BTC DEL DÍA`

Incluye:
- sesgo macro
- precio
- 1W / 1D / 4H / 1H
- RSI
- ADX
- funding
- estado actual
- qué espera

### Cuando detecta entrada

`🚨 SETUP CONFIRMADO — REVISA ENTRADA AHORA`

Puede decir:

`ENTER LONG NOW`

o:

`ENTER SHORT NOW`

Y mostrará:
- zona de entrada
- invalidación / SL técnico
- TP1
- TP2
- TP3
- R:R restante
- razones del setup

### Si el mercado va en una dirección pero no debes entrar

Mostrará:

`WAIT`

o:

`TOO LATE`

Así `LONG` nunca significa automáticamente `COMPRA YA`.

---

## COMANDOS DE TELEGRAM

Escribe a tu bot:

`/status`
Análisis actual.

`/plan`
Igual que status.

`/pause`
Pausa avisos automáticos de setups.

`/resume`
Reactiva avisos.

`/help`
Muestra los comandos.

---

## CÓMO ANALIZA

Jerarquía:

1W -> contexto macro
1D -> tendencia principal
4H -> estructura y fuerza
1H -> setup/pullback
15m -> confirmación
5m -> timing

Indicadores / datos:
- EMA 20 / 50 / 200
- RSI
- MACD
- Awesome Oscillator
- ATR
- ADX
- +DI / -DI
- VWAP
- volumen
- Donchian
- pivots HH/HL/LH/LL
- divergencias RSI
- order book Bitunix
- flujo reciente de operaciones
- funding

Regla fundamental:
un RSI 1H bajista NO convierte por sí solo una estructura 1D/4H alcista en SHORT.

---

## IMPORTANTE

Esta primera versión tiene que probarse.

Que aparezca `ENTER NOW` significa que se cumplieron las reglas programadas,
NO que el trade sea seguro.

No persigue una cuota de operaciones ni fuerza un +10% diario.
Si el mercado no ofrece un setup válido, debe decir WAIT/NO TRADE.

Primero observamos sus avisos y comprobamos si interpreta correctamente
situaciones como la que te ocurrió con el SHORT antes del movimiento alcista.
