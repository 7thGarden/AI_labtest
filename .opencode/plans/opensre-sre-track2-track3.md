# SRE Improvements — Implementation Plan (Track 2 + Track 3)

Scope approved by user: **Track 2 (Observability coverage)** + **Track 3 (Chaos maturity)**, all
implemented in one pass, then verified end-to-end. Catalog-api latency spike stays active at 5000ms
(do NOT clear). No cluster recreate, no secrets touched.

Current pinned chart versions (live cluster, 2026-09-02):
- victoria-metrics-single **0.45.0** (v1.150.0), vmagent **0.46.0**, grafana **10.5.15**,
  opentelemetry-collector **0.172.0** (keep as-is)
- NEW: prometheus-community/kube-state-metrics **8.4.1**, prometheus-node-exporter **4.56.3**

Verified facts:
- vmagent SA token mounted at `/var/run/secrets/kubernetes.io/serviceaccount/token`;
  ClusterRole `vmagent-victoria-metrics-agent` already grants `nodes` + `nodes/metrics` GET/LIST/WATCH
  → cAdvisor via https://<node>:10250/metrics/cadvisor needs NO extra RBAC.
- VM single chart 0.45.0 defaults already enable `server.persistentVolume` (16Gi, storageClass
  `standard` = rancher local-path, verified present) + `server.retentionPeriod: 1` → make explicit +
  add resources in `vm-values.yaml`.
- kube-state-metrics Service port name = `http` (8080), also carries prometheus.io annotations
  (pod-job will scrape it too — acceptable).
- node-exporter: `hostNetwork: true`, `hostPID: true` → `role: node` → nodeIP:9100 works.
- Dedupe of static `catalog-api` scrape verified safe: backend `victoriametrics.py` + frontend only
  query `job="kubernetes-pods"`; Grafana dashboard filters by `instance`/`pod` labels, not `job`.

---

## Track 2 — Observability coverage

### 2.1 `observability/vm-values.yaml` (NEW)
Explicit, reproducible VM single-server settings:
```yaml
server:
  retentionPeriod: "1"
  persistentVolume:
    enabled: true
    size: 16Gi
  resources:
    requests: { cpu: 50m, memory: 200Mi }
    limits:   { cpu: 500m, memory: 2Gi }
```

### 2.2 `observability/vmagent-values.yaml` (REWRITE)
- Keep `kubernetes-pods` job + remoteWrite URL unchanged (remove the static `catalog-api` job).
- ADD job `kube-state-metrics`: `role: endpoints`, namespace `observability`, service keep regex
  `kube-state-metrics`, port-name keep regex `http|http-metrics|metrics`.
- ADD job `node`: `role: node`, relabel `__address__` → `<node-ip>:9100`, add `node` label.
- ADD job `kubernetes-nodes-cadvisor`: scheme https, `role: node`, relabel → `<node-ip>:10250`,
  `__metrics_path__: /metrics/cadvisor`, `bearer_token_file: /var/run/secrets/kubernetes.io/serviceaccount/token`,
  `tls_config.insecure_skip_verify: true`, metric relabel keep `id` matching `/kubepods\.slice/.+`.

### 2.3 `observability/install.sh` (NEW — reproducible + pinned)
Idempotent (`helm upgrade --install`), ensures NS, `helm repo add` vm/grafana/open-telemetry/
prometheus-community, then installs with pinned `--version`:
victoriametrics (vm-values.yaml), grafana (grafana-values.yaml), otel-collector (otel-values.yaml),
vmagent (vmagent-values.yaml), kube-state-metrics 8.4.1, node-exporter 4.56.3.

### 2.4 Apply
```
observability/install.sh
```
(`mkdir -p observability` already exists). This upgrades VM (retention/PV/resources, data kept),
upgrades vmagent (new jobs), installs ksm + node-exporter.

### 2.5 README
Update `# Deploy Observability Stack` to point at `observability/install.sh` + mention exporters
and retention.

---

## Track 3 — Chaos maturity

### 3.1 Experiment registry
- `chaos/experiments/` (NEW, gitignored): `events.jsonl` (one JSON object per line) + `active.json`.
- `chaos/runbook.sh` (EDIT):
  - helper `risk/record <kind> <fault> <target> <params> [note]` guarded by `flock` on
    `chaos/experiments/.lock`; writes `{id, kind, fault, target, params, ts, note}`.
  - inject actions: after success write record + append/update `active.json` (key = fault, value =
    {id, started}) or remove on recovery.
  - `status` shows active faults from `active.json`.
- `.gitignore` (EDIT): add `chaos/experiments/`.

### 3.2 Game-day automation — backend
- `opensre-backend/app/services/game_day.py` (NEW): baseline → inject → during → recover → after;
  samples `{up, req/s, 5xx/s, 5xx%, p50, p95, p99}` for the target using existing
  `victoriametrics.py` helpers; verdict = steady-state (e.g. during-p99 <= 3x baseline ⇒ pass).
  Persists report JSON to `chaos/experiments/<id>.json`.
- `opensre-backend/app/routes/chaos.py` (EDIT): add
  `GET /api/chaos/history`, `GET /api/chaos/active`, `POST /api/chaos/game-day {action, duration_s}`.
- Health-gated recover: runbook `recover` asserts target health (doc at cursor / kubectl rollout status
  / docker inspect) before OK.

### 3.3 New faults (runbook + backend whitelist + UI cards)
- `node-network-latency` (+ `latency-off` recovery): `docker exec opensre-demo-worker tc qdisc add dev
  eth0 root netem delay 500ms`; reversible `tc qdisc del dev eth0 root`.
- `flaky-latency` (+ `latency-off` — NOTE: reuse a distinct recover key `flaky-latency-off` to avoid
  collision with catalog `latency-off`): add persistent latency endpoint to
  `fault-apps/flaky-service/app/main.py` (`/latency?ms`, `/latency/status`, same pattern as
  catalog-api), rebuild `localhost/flaky-service:v1`, `kind load`, rollout.
- `pod-crash` → real crash: `kubectl exec <pod> -- curl -s localhost:8000/failure/crash` (existing
  `os._exit(1)`) instead of scale-to-0/1.
- No resource-limit change to catalog-api (keep latency spike stable).

### 3.4 Frontend `frontend/src/pages/Chaos.jsx` (EDIT)
- "Active faults" chips (from `/active`).
- History list (from `/history`) with link to investigation.
- Game-Day card: fault select + duration + Run → renders report (baseline/during/after + verdict).

### 3.5 Docs
- `chaos/README.md`: new faults, game-day usage, history/active endpoints, registry notes.
- `README.md`: chaos API reference additions.

---

## Verification (all changes, single pass)
1. `observability/install.sh` completes; `kubectl -n observability get pods` → ksm + node-exporter
   daemonset Running; `helm -n observability ls` shows pinned versions.
2. vmagent targets: `kubectl -n observability exec deploy/vmagent-victoria-metrics-agent -- wget -qO- http://localhost:8429/api/v1/targets`
   → kube-state-metrics / node / kubernetes-nodes-cadvisor UP.
3. PromQL sanity via VM (port-forward 8428):
   - `kube_pod_container_status_restarts_total{namespace="opensre"}`
   - `node_cpu_seconds_total`
   - `container_memory_working_set_bytes{namespace="opensre", name!=""}`
4. Game-day on catalog-api latency: baseline p50 < 50ms → during ~5s → after back to baseline;
   report + verdict written; `/history` + UI populated.
5. `node-network-latency` → latency climbs (traffic-gen p99), recover → active.json clears.
6. `pod-crash` → Kubernetes page restarts climb (real crash).
7. `flaky-latency` → flaky p50/p95/p99 climbs on Latency page; recover works.
8. Existing catalog-api 5000ms spike untouched throughout.