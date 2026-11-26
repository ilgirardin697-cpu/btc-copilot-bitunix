# I-GOD silent notification radar — review only

Status: DISABLED BY DEFAULT. No deployment, Railway variable change or real Telegram test performed.
This is presentation/routing, never a trading, risk or operability gate. SHADOW ONLY. TRADE AUTHORITY: NONE.

## Read-only emitter inventory, 2026-11-26

Guardian production source: `9d40020d539033cefb8f01734db8c6a6fdbba2e3`, deployment
`79d03f47-07e0-49aa-9e6b-54635b42577c`. Existing single owner-only command poller.
ML RSI, Manual Copilot and daily plan automatic messages pass through Guardian.
The daily planner has no Telegram variables; its private bridge is the emission seam.
V8 source: `724f14fdd723eabf9ebcf3dbd51b4ab271aec9e6`, deployment
`3528cb0c-9d11-4ae2-83ce-98a14da23071`; separate outbound sender, no second poller.
Paper and PRICE observer services have no Telegram variable names in their read-only configuration.
Older one-off backtest runtime had no Telegram configuration identified; its ephemeral code was not independently inspected.
No service was mutated. V8_LIVE_EXECUTION=false is the owner's previous manual check, not a new independent read of its value.

Guardian logs in a bounded 301-entry sample, 07:35:26–07:59:46 UTC, contained 146
`GUARDIAN_BLIND_CODE=AMBIGUOUS_POSITIONS` entries. This is a real private-read verification problem,
not evidence of a safe position or a verified stop. The notification change must not conceal it.
Inspect position/stop coverage directly in Bitunix; resolving account ambiguity is outside this patch.

## Central ownership and lifecycle

Guardian owns the sole durable notification state machine. Producers submit typed observations.
`PRE_LONG`/`PRE_SHORT` → later `CONFIRMED` → `INVALIDATED`, or PRE → INVALIDATED.
There is no confirmation/invalidation without a previous PRE, no same-bar confirmation,
no resurrection of a terminal opportunity, and one active opportunity per logical slot.
The opportunity ID survives restarts. Producer readiness memory prevents a new ID on every bar.
Unchanged events from multiple producers deduplicate centrally. Signals are experimental context, never orders.

The Manual Copilot adapter consumes its EXISTING closed-price WAIT_RECLAIM/CONFIRMED_RECLAIM
facts, known structural level and existing aligned context. It changes no indicator or strategy threshold.
Already-confirmed context at startup does not invent a prealert. An isolated indicator cannot confirm anything.
ML RSI color changes alone, V8 LONG/SHORT/FLAT snapshots, startup, WAIT, neutral and routine daily summaries
are observations only. No new research signal is connected. Manual /bitman and every existing query remain available.
PRE/CONFIRMED require at least two existing evidence categories; CONFIRMED also requires the existing price reclaim.
Panel text states timeframe, 4H/1H context, actual evidence, pending confirmation, ID and no authority.

Critical incidents bypass opportunity silence. First occurrence, severity escalation, material safety change
(including protection-order/coverage fingerprint, risk-state or private error-code change), recovery and
hourly unresolved reminders notify. Changing mark/PnL text alone does not. Blindness stages share one incident.
Old delayed packets cannot resurrect a resolved incident. A safety-action confirmation is NOT a trading opportunity CONFIRMED.
Unknown automatic safety messages are conservatively retained. A notice never certifies an exchange stop.

## Persistence, concurrency and failure

Own directory under existing Guardian state volume: `/data/notification_radar_v1/`.
SQLite `radar.sqlite3`: events, opportunities, incidents, producer memory, preferences, durable outbox,
recipient delivery acknowledgements. WAL, synchronous FULL, OS single-writer lock and quick_check.
No capital journal, weekly V1 journal, cache or campaign is reset, migrated or edited.
Corrupt notification DB is not silently rebuilt. Critical notifications fall back to the EXISTING sender;
routine observations do not become fallback spam.

Main Guardian cycle uses bounded put_nowait only, after its existing cycle; SQLite, sending and private
ingress run in daemon threads. No exchange client/account or credential is passed into a research module.
The existing Telegram sender and retry queue remain intact. Manual responses bypass the automatic policy.
Notification queue failure cannot stop protection. Critical deliveries have priority and retry; offline
opportunities older than 30 minutes are suppressed. A confirmation waits for prior PRE delivery.
After an ambiguous crash mid-send, safety retries; opportunities remain UNCERTAIN rather than spamming.

V8 companion uses the identical hashed SDK, a separate spool on its existing own volume and a private
HMAC-authenticated bounded endpoint at Guardian port8091. It adds no poller, public domain or trading permission.
Only source=v8 and observation/safety kinds are accepted remotely. URL is an exact private allowlist;
no redirects/environmental proxy. New crises are not blocked behind an old failed relay record.
V8's fallback retains the original outbound sender and asynchronously coalesces an unchanged crisis.

Telegram sendMessage offers no application idempotency token. A network/crash ambiguity, or fallback and
relay both succeeding, can still duplicate a critical message. Network/Telegram outage can delay delivery;
this patch cannot guarantee delivery. Safety is favored over absolute exactly-once delivery. The unchanged
legacy V8 sender does not provide per-recipient delivery acknowledgements; that fallback remains best effort.

## Commands and later rollout plan — approval still required

Default `IGOD_NOTIFICATION_RADAR_ENABLED=false` preserves current behavior, opens no new listener/store.
When enabled, `/alertas` queries central preferences, `/alertas on|off`, `/silencio` and `/silencio off`
change only opportunity notification preferences, persisted between restarts. Critical safety never mutes.
Other manual commands, including /status /risk /position /mlrsi /bitman /diario /resumen /niveles, retain their handlers.
Daily automatic sends are suppressed; its analysis and manual reads continue. Existing alerts are not deleted.

Review both source-specific draft PRs before any rollout: Guardian base9d40020 and V8 base724f14f.
Do not merge one into the other's source branch or move either production source pin now.
Later, back up only the new notification store, verify volume space, single replicas and private DNS,
then deploy approved code with flag OFF. Validate existing commands/protection and zero new writes/listener.
Enable Guardian and configure a newly generated notification-only HMAC secret in the two services;
no Bitunix/Telegram key reuse, no secret values in Git. Confirm private health/auth and closed-fixture dry-run
before enabling the V8 relay. Confirm preserved execution flags (especially V8 false), volume and source SHAs.
Never generate a fake production opportunity or touch orders to test notifications.
Rollback: disable only the notification flag, restoring legacy routing, or restore reviewed source pin.
Keep notification files for audit. No trading flag, risk threshold, campaign or manual order changes.

## Verification

Offline tests cover 100 evaluations, restart, lifecycle, mute/recovery, critical priority, coverage changes,
queue/DB/network failure, single writer, old packets, retained commands and exact source/AST preservation.
The normalizer removes only exact reviewed notification seams; old safety hashes are not refrozen.
Mutating an emergency condition still fails. Frozen engine, readiness900 results, ML RSI math,
Guardian capital policy/execution and V8 strategy/execution modules remain unchanged.
The weekly V1 protocol hash remains d4fe75fce89e8f248123409c293b1114f9af2eb16b8aee5572b40802a54aefe8.
No paid vidIQ call; no Railway mutation; no real Telegram/Bitunix request in tests.
