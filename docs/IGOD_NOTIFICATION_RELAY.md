# V8 notification-only companion — review, not deployed

Base is the actual active V8 source724f14fdd723eabf9ebcf3dbd51b4ab271aec9e6.
Only the telegram(message) presentation seam delegates to the disabled-by-default relay.
The original sender is preserved as _legacy_telegram; LiveExecutor and every order/strategy branch
remain AST-identical after exact wrapper removal. No trading flag is set or changed.

See the companion Guardian draft's docs/IGOD_NOTIFICATION_RADAR.md for the central policy, inventory,
failure limits and review-first rollout. No runtime service or production source was changed.
With flag OFF, original behavior. With flag ON: V8 SIGNAL LONG/SHORT/FLAT and DISARMED are logs only;
safety uncertainty is relayed privately with HMAC and a durable local spool. Critical-only async fallback
uses the original sender if coordinator fails. No new poller/public URL/shared volume/trading credentials.
Same crisis coalesces across restart, while escalation and different material causes remain observable.
The legacy sender has no delivery ACK; fallback is best effort and can duplicate a safety message when
delivery is ambiguous. TradingView/research/weekly state never feed this relay or execution.

Default IGOD_NOTIFICATION_RADAR_ENABLED=false. Proposed config only after separate approval:
Guardian private URLhttp://igod-trade-guardian.railway.internal:8091/events and a new notification-only
IGOD_NOTIFICATION_INGEST_KEY shared with the Guardian ingress. Never reuse exchange or bot secrets.
V8_LIVE_EXECUTION stays false; this patch neither reads nor writes production variable values.
One V8 service writer on its own existing /data volume; spool lives under /data/v8/.
Rollback notification flag only; preserve spool and every real order/position.
SHADOW ONLY. TRADE AUTHORITY: NONE. No deployment performed.
