# Public collector preparation — separate independent DRAFT

Base PR #52:`9f307fd9feda6279253c0a0813d49b47d3f1d9b2`. 18 offline tests passed,0 failed. Real endpoint requests: **0**. Real prospective observations: **0**. Observer connected: **NO**.

Only unsigned public BTCUSDT USD-M H1/funding and clock GETs are available. No credentials, private/account/order endpoints, arbitrary hosts, redirects, proxy or exchange fallback. Raw SQLite receipts are atomic and append-only at application level, hash chained and single-writer. Raw request/receive/monotonic times, exchange-clock reference, status, original bytes and SHA are retained. No module imports the observer or production paths.

The60s post-close wait is provisional. Qualification requires separately authorized actual publication/revision sampling; synthetic fixtures never qualify. Tests cover data gaps/duplicates/schema, unsupported funding types, clock skew/discontinuity, body cap, non200/451, no redirect/fallback, disabled silence, real-network permission, raw integrity and append-only spool.

Pinned target: Python3.12.12 /NumPy2.3.5. Local fixtures ran there; inherited latest CI is compatibility evidence. Pinned Linux/network parity and actual-volume locking remain pending. No cloud resources, variables, public domains, schedules or services were created. Future resource costs depend on measured payloads and approved independent volume/backup retention; no quote or plan change is claimed.

Decision: **NO-GO for continuous capture or observer connection** until independent review, real revision qualification and infrastructure approval. No trading, merge or deploy.
