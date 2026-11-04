# Future controlled rollout — NOT EXECUTED

## Read-only observations, 04/11/2026

Project `igod-research-lab`.
Environment `production` is the research
project environment, not Guardian's production project. Two existing services
report SUCCESS: `bitman-market-data-test` and `igod-paper-simulator`, both in
`europe-west4-drams3a`. One existing500MB volume belongs to PAPER. No shared
variables or staged changes. Nothing has been changed.

Railway official CLI, read-only:

- Current and projected workspace usage were read successfully. Actual account
  billing totals/identifiers remain in the local audit, not this public PR.
- Workspace usageLimit=null: no configured workspace compute spending cutoff.
- The reported agent allowance is not a compute resource budget.
- The account plan was previously reported as paid Hobby by the owner. These
  usage queries do not independently expose the current subscription SKU.
- Existing service24h resource measurements were inspected, without changing
  them. Their measurements do not predict this service's future consumption.

No payment/customer identifiers or secret values are retained in this document.

## Proposed independent resources

- Name: **igod-killzone-price-observer** in this existing project/environment.
- Region: **europe-west4-drams3a**, Amsterdam. No move of an existing service.
- One replica, always-on application scheduler, no Railway cron/serverless sleep.
- New dedicated500MB volume `igod-killzone-price-data-v1` at `/price-observer-data`.
- Only public Binance Spot data; no access dependency on Guardian, PAPER,
  market-data, their APIs, tokens, volumes or state. No shared references.
- No public domain, TCP proxy, static outbound IP, Telegram or exchange keys.
- Image copies ONLY `igod_killzone_price_observer`, not the rest of I-GOD.
  Its Dockerfile-specific ignore file also excludes unrelated build context.
  CI builds the image and tests OFF startup without network, secrets or volume;
  real Railway mount, connectivity and enabled-capture acceptance remain pending.
- Start: `python -B -m igod_killzone_price_observer`; `PORT=8080`; private health
  `/health`; diagnostic `/status`; cached full `/report`.
- New service source pinned to the independently reviewed observer commit.
  No merge of an old research PR is necessary to deploy this separate source.

The default root railway.json belongs to Guardian. **Never rely on autodetection
of that root file for this service.** Configure the nested config path and
explicit Dockerfile/start command BEFORE connecting source/deploying anything:
`igod_killzone_price_observer/deploy/railway.json` and its Dockerfile.
All files here are proposals; no service is currently connected to them.

## Resource/cost estimate, not a quote

Official pricing consulted04/11/2026: memory$0.00000386/GB/s (~$10.01/GB/30days),
CPU$0.00000772/vCPU/s (~$20.01/vCPU/30days), volume$0.00000006/GB/s
(~$0.1555/GB/30days), service egress$0.05/GB.
[Published pricing](https://railway.com/pricing).

| Component | Planning assumption | Approx monthly resource cost |
|---|---|---:|
| Memory |0.064–0.192GB average; target peak<256MB, verify after deployment |$0.64–1.92|
| CPU |0.001–0.005vCPU average, most time asleep |$0.02–0.10|
| Volume |new0.5GB, independent |$0.08|
| Egress |very small public requests; responses are ingress |< $0.01 expected|
| Total |30-day planning range, not a hard spending cap |**about$0.75–2.25/month**|

Hobby's published minimum includes$5 resource credit. Do not add a new plan or
claim the increment is free: the eventual bill depends on total workspace use.
No Pro/static-IP feature is required by this design. The project currently has
2 services and1 volume; Hobby published limits allow this extra service/volume,
subject to real subscription/provisioning state at the future approval step.

Normal collection is roughly13 public GET/day plus one process-start clock check:
five server-time checks, one1000H1 context, four1m prefixes, three outcome calls.
Retries are bounded3/anchor and3/outcome/day. About0.4MB raw/day is a normal-order
estimate; plan<250MB over six months with metadata/retries, not a guaranteed cap.
Below32MiB free, data acquisition fails closed. Nothing is deleted automatically.
Raw/public data and failed attempts may consume more space during incidents.

Railway cron is not used: UTC scheduling,5min minimum separation and no exact
minute guarantee do not satisfy05:59 capture with a deadline before06:00.
[Cron limits](https://docs.railway.com/cron-jobs).
One volume writer also requires one replica; volume redeploys can cause downtime.
[Volume caveats](https://docs.railway.com/volumes/reference).

## Future approval and rollout sequence

1. Obtain explicit authorization of reviewed source SHA, new service, new volume
   and expected recurring resource cost. Revalidate no unrelated staged changes,
   subscription/limits and region availability. Do not change workspace limits.
2. Create ONLY the empty new service. Stage explicit nested Docker/config/start,
   regionAmsterdam, one replica, PORT8080, new volume and source pin. Zero secret
   references and zero public domain/proxy. Inspect exact staged diff before apply.
3. First deployment OFF (`PRICE_OBSERVER_ENABLED` absent/false). Wait terminal
   SUCCESS; check private health/status DISABLED. No raw, journal or public market
   queries from the disabled observer. No interaction with existing services.
   As a separately authorized read-only acceptance probe in this NEW runtime,
   check official Spot server time and one fully closed1m BTCUSDT candle. Keep
   that probe outside the forward journal; it is connectivity, not a prediction.
   A451/403 or failed source validation blocks activation. No fallback/geobypass.
4. Before the first cohort anchor, approve enabling ONLY this new service's flag.
   Verify persistent mount and exact source SHA. Redeploy ONLY this service.
   Activation timestamp is real; never set a past activation time.
5. Check logs/status HEALTHY, model/protocol hashes and ACTIVATION; no forecasts
   before due time. At a natural anchor, verify original response SHA, request/
   receipt/emission clocks and PREDICTION + post-fsync DURABILITY witness.
   If Binance returns451/403/429/invalid data, report DEGRADED; no proxy/fallback.
6. Verify all5 anchors, then at20NY+margin an OUTCOME with independent final inputs.
   Check first-touch chronology, coverage and point calibration; never validate
   the model from this first day. Original records persist, including losses in
   predictive quality, missed anchors, ambiguous labels and revisions.
7. In a separately approved restart window, restart ONLY this service. Confirm
   prior chain/tip preserved, one activation, RECOVERY and no duplicate forecasts.
   Past missed anchors stay missed; only matured outcomes can be recovered.
8. Measure real memory/CPU/disk/latencies against this estimate, before considering
   the deployment finished. Export an original evidence copy/checksum as backup;
   no external backup service is configured by this preparation.

The new Binance calendar stays05/11/2026→04/05/2027.181 planned cycles require172
complete, including all5 anchors and stable unambiguous outcomes. The DST gap
already consumes one of9 allowed missing cycles. Late rollout consumes remaining
coverage; it does not permit changing dates or inserting historical predictions.

## Stop/rollback

Disable ONLY `PRICE_OBSERVER_ENABLED` on the new service and redeploy/stop ONLY it.
Do not edit/delete/truncate its volume, reset its cohort, or repair a bad chain.
Pin the last reviewed observer source only if protocol/model hashes remain
identical. A different research model/protocol requires a different journal.
Guardian, V8, PAPER, market-data and their credentials/flags/deployments stay intact.
No trading capability exists to arm/disarm here.

## Outstanding acceptance evidence

- No image build/runtime in Railway yet; Docker is unavailable in the current
  local environment. Compilation/unit/integration tests do not substitute it.
- New-runtime Spot access, mount durability, real clock latency and resource
  consumption remain deployment acceptance checks, not reported as completed.
- No live predictions or matured prospective outcomes have been collected.
- No TradingView capture activated. CSV comparisons cannot validate that cohort.
- Fixed cohort completion, sample/class/coverage and predictive-quality gates,
  followed by independent review, are required. No automatic publication.

**NOT DEPLOYED. SHADOW ONLY. TRADE AUTHORITY: NONE.**
