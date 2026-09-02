# OpenSRE Demo — Chaos Runbook

Inject and recover from failures across YugabyteDB, Aerospike, and the Kubernetes
cluster so you can show them live and analyze them through OpenSRE.

## Production baseline (optional, recommended for the observability part)

A demo of "degraded production" is more convincing than a healthy one. This
boots a degraded order service, latencies, crash/OOM/ImagePullBackOff/Pending
workloads, and a traffic generator so the Grafana/Metrics page looks alive:

```bash
./chaos/productionize.sh up     # build+load images, deploy faults, start traffic
./chaos/productionize.sh busy   # show only the problematic workloads
./chaos/productionize.sh down   # remove everything, back to baseline
```

What it creates (all in the `opensre` namespace):

| Workload | State | Shows up as |
|---|---|---|
| `flaky-service` | `Running` but ~30% of `/orders` returns 500; `/slow` sleeps 3–9s | Grafana **Error Rate (5xx)**, **P50/P95/P99 latency** spikes |
| `memory-hog` | `CrashLoopBackOff` (OOMKilled, mem limit 96 Mi) | **Kubernetes** page restarts climbing; events `OOMKilled` |
| `crashloop` | `CrashLoopBackOff` (container exits 1) | **Kubernetes** page restarts climbing; events `BackOff` |
| `imagepull` | `ImagePullBackOff` (image doesn't exist) | **Kubernetes** page stuck `ImagePullBackOff` |
| `pending-pod` | `Pending` (requests 100 CPU) | **Kubernetes** page unschedulable; events `FailedScheduling` |
| `traffic-gen` | `Running`, hammers `/products`, `/orders`, `/slow`; includes a `probe` sidecar (`localhost/probe:v1`, `fault-apps/probe`) exposing `/metrics` | Request rate/latency/error panels stay moving; third live pod on the **Latency** page |

`flaky-service`, `catalog-api` and the `traffic-gen` probe sidecar are all annotated
for scraping, so the Grafana **pod** selector (and the Metrics/Latency page pod
selectors) includes `flaky-service-*`, `catalog-api-*` and `traffic-gen-*`.

Sources live in `fault-apps/` (`flaky-service`, `oom-hog`) and manifests in
`infra/k8s/faults/`. Requires `podman` (build + `kind load`) and `kind`,
`kubectl`.

## No-terminal option (dashboard + Swagger)

Every runbook failure is also exposed over the backend API, so you can trigger
them from the UI instead of a terminal:

- **Dashboard** → **Failure Injection** page (`/chaos`) — status cards for the
  databases and worker node, one-click failure/recovery buttons, seed-data
  button, and a command-output log.
- **Swagger** → backend `http://localhost:8001/docs` → **Chaos** group:

  | Endpoint | Purpose |
  |---|---|
  | `GET /api/chaos/status` | live state: Aerospike / Yugabyte / node / opensre pods |
  | `GET /api/chaos/actions` | available failure, recovery and ops actions |
  | `POST /api/chaos/inject` `{action}` | run a failure (e.g. `aerospike-down`) |
  | `POST /api/chaos/recover` `{action}` | run a recovery (e.g. `aerospike-up`) |
  | `POST /api/chaos/seed` | seed Yugabyte + Aerospike sample data |
  | `GET /api/chaos/history` | experiment timeline from `events.jsonl` (newest first) |
  | `GET /api/chaos/active` | currently-injected faults from `active.json` |
  | `POST /api/chaos/game-day` `{action, duration_s}` | full baseline→inject→measure→recover→report cycle |

```bash
# Example API one-liners
curl -s -X POST http://localhost:8001/api/chaos/inject \
  -H 'Content-Type: application/json' -d '{"action":"aerospike-down"}'
curl -s -X POST http://localhost:8001/api/chaos/recover \
  -H 'Content-Type: application/json' -d '{"action":"aerospike-up"}'
```

Actions are whitelisted on the backend (`app/routes/chaos.py`) and delegate to
`runbook.sh` / `seed-data.sh`, so behavior is identical to the terminal.

## Quick start

```bash
# Seed sample data into YugabyteDB & Aerospike (do this first)
./chaos/seed-data.sh

# See current state (safe, read-only)
./chaos/runbook.sh status

# Show the full command menu
./chaos/runbook.sh help

# Recover everything after a demo
./chaos/runbook.sh recover all
```

> **Seed data**: run `./chaos/seed-data.sh` before the demo so the database
> pages show content. It creates `test_table` (20 rows) in YugabyteDB and the
> `test:demo` set (13 records) in Aerospike, matching what the dashboard
> expects.

## Failure menu

| Command | What it does | Watch on dashboard |
|---|---|---|
| `./chaos/runbook.sh aerospike-down` | Stops the Aerospike container | **Aerospike** page → health flips to `Unreachable`, scan/query errors |
| `./chaos/runbook.sh yugabyte-down` | Stops the YugabyteDB container | **YugabyteDB** page → health `Unreachable`, SQL connection errors |
| `./chaos/runbook.sh pod-crash` | Real crash: execs `/failure/crash` inside catalog-api (the Python process `os._exit(1)`s, kubelet restarts the container) | **Kubernetes** page → container `RESTARTS` climbs |
| `./chaos/runbook.sh pod-delete` | Deletes the catalog-api pod (self-heal) | **Kubernetes** page → pod recreated, restart count +1 |
| `./chaos/runbook.sh pod-cpu` | CPU spike (20s) via `/failure/cpu` | **Metrics** / Grafana → CPU climbs |
| `./chaos/runbook.sh pod-memory` | Memory spike (~300 MB) via `/failure/memory` | **Metrics** / Grafana → resident memory climbs |
| `./chaos/runbook.sh pod-latency` | +5s extra latency on all catalog-api `/products` traffic (`POD_LATENCY_MS` overrides) | **Latency** page → catalog-api p50/p95/p99 climbs, per-pod card flags **HIGH** |
| `./chaos/runbook.sh flaky-latency` | +3s extra latency on all flaky-service traffic (`FLAKY_LATENCY_MS` overrides) | **Latency** page → flaky-service p50/p95/p99 climbs |
| `./chaos/runbook.sh node-network-latency` | Adds 500ms `netem` delay to the worker node egress (`NODE_LATENCY_MS` overrides) | **Latency** page → every in-cluster caller's latency climbs |
| `./chaos/runbook.sh system-pod-kill` | Deletes a kube-system pod (default `coredns`) | `kubectl get pods -A` → pod self-heals |
| `./chaos/runbook.sh node-cordon` | Marks worker `SchedulingDisabled` | **Kubernetes** page → node `SchedulingDisabled` |
| `./chaos/runbook.sh node-drain` | Evicts pods off the worker | **Kubernetes** page → workload pods evicted |

> **Latency spike** sets a persistent delay in the catalog-api app itself —
> every `/products` request is routed through the `inject_extra_latency`
> dependency, which sleeps `ms` before handling (the instrumentator histogram
> records it, so it shows up as real latency). Control endpoint
> `GET /failure/latency?ms=5000` (status check: `/failure/latency/status`).
> This requires the catalog-api image to be rebuilt with the middleware:
>
> ```bash
> docker build -f catalog-api/Containerfile -t localhost/catalog-api:v1 catalog-api
> kind load docker-image localhost/catalog-api:v1 --name opensre-demo
> kubectl -n opensre rollout restart deploy/catalog-api
> ```

## Recovery

```bash
./chaos/runbook.sh recover aerospike-up          # start Aerospike
./chaos/runbook.sh recover yugabyte-up           # start Yugabyte
./chaos/runbook.sh recover latency-off           # clear the injected catalog-api latency
./chaos/runbook.sh recover flaky-latency-off     # clear the injected flaky-service latency
./chaos/runbook.sh recover network-latency-off   # remove the node netem delay
./chaos/runbook.sh recover uncordon              # uncordon the worker node
./chaos/runbook.sh recover all                   # restore everything
```

Recovery is health-gated: `recover` verifies the affected target actually came
back (container up, node ready) and returns exit code 1 if the recovery did not
take effect.

## Experiment registry

Every inject/recover/game-day writes a line to `chaos/experiments/events.jsonl`
and the currently-active faults to `chaos/experiments/active.json` (gitignored —
these are runtime artifacts):

```bash
./chaos/runbook.sh status                      # live state incl. any active faults
cat chaos/experiments/active.json              # currently injected (non-recovered) faults
tail chaos/experiments/events.jsonl            # full experiment timeline
```

Helper subcommands: `exp-record <kind> <fault> <target> <params> <output-file>`,
`exp-active-add <fault> <id> [params]`, `exp-active-remove <fault>`,
`exp-active-show`. Writes are atomic under `flock` so concurrent invocations
cannot corrupt the files.

## Game-day (automated chaos experiment)

```bash
curl -s -X POST http://localhost:8001/api/chaos/game-day \
  -H 'Content-Type: application/json' -d '{"action":"flaky-latency","duration_s":60}'
```

Runs baseline → inject → hold the fault ≥ 60s → measure → recover → measure
again, then writes a `chaos/experiments/<id>.json` report and a `game-day`
event line. The latency percentiles come from a 1-minute `rate()` lookback, so
the fault is held long enough for the window to fill with faulted samples; the
`during` sample is reduced across repeats (max p99) and `after` (min p99) to
ignore phase-boundary artifacts. Expect ~3.5 minutes per run. Verdict:
**degraded** when during-p99 > 3×max(baseline-p99, 50ms), **recovered** when
the after-window returns to that bound.

## Suggested demo flow

1. `./chaos/runbook.sh status` — show healthy baseline.
2. **Aerospike + Yugabyte outage** — stop both DBs, open their dashboard pages
   to show `Unreachable`, then recover and show them turn green.
3. **Pod crash/restart** — `pod-crash` (or hit the app's `/failure/crash`
   endpoint) and watch `RESTARTS` climb on the Kubernetes page.
4. **Self-healing** — `system-pod-kill`, watch the pod come back instantly.
5. **Latency spikes** — `pod-latency` and `flaky-latency` push p50/p95/p99 up
   on the Latency page; `node-network-latency` (netem on the worker egress)
   shows every caller's latency climb.
6. **Game-day** — from the **Chaos** page, pick a fault and duration and watch
   the automated baseline/during/after report with the degraded/recovered
   verdict (Steady-state hypothesis).
7. **Node cordon/drain** — show `SchedulingDisabled` and evictions.
8. **Analyze with OpenSRE** — on the **AI Analysis** page, select the affected
   pod → **Run investigation** → show root-cause + validity score. Use the
   **Kubernetes** page "Investigate" button for the raw evidence (pod details,
   events, metrics).

## Options / environment

```bash
# Target a different cluster / node / system-pod pattern
CLUSTER=kind-opensre-demo ./chaos/runbook.sh node-cordon
WORKER_NODE=opensre-demo-worker ./chaos/runbook.sh node-cordon
SYSTEM_POD_PATTERN=coredns ./chaos/runbook.sh system-pod-kill
```

Requires `kubectl` with the demo cluster context, plus `docker` (or `podman` —
detected automatically) for the container-level failures.
