import { useEffect, useState } from "react";
import api from "../api/api";
import Card from "../components/Card";
import Badge from "../components/Badge";
import {
  Loader2,
  Database,
  HardDrive,
  Server,
  Fuel,
  RotateCcw,
  RefreshCw,
  CheckCircle2,
  AlertTriangle,
  Terminal,
  Timer,
  Activity,
  ListChecks,
} from "lucide-react";

const FAILURES = [
  { action: "aerospike-down", label: "Aerospike down", desc: "stop the Aerospike container", icon: Database, risk: "db" },
  { action: "yugabyte-down", label: "YugabyteDB down", desc: "stop the YugabyteDB container", icon: HardDrive, risk: "db" },
  { action: "pod-crash", label: "Pod crash", desc: "crash the catalog-api container (real restart)", icon: Server, risk: "pod" },
  { action: "pod-delete", label: "Pod delete", desc: "delete the catalog-api pod (self-heal)", icon: Server, risk: "pod" },
  { action: "pod-cpu", label: "CPU spike", desc: "busy-loop the catalog-api CPU", icon: Fuel, risk: "pod" },
  { action: "pod-memory", label: "Memory spike", desc: "inflate catalog-api memory", icon: Server, risk: "pod" },
  { action: "pod-latency", label: "Latency spike (catalog)", desc: "add +5s latency to catalog-api traffic", icon: Timer, risk: "pod" },
  { action: "flaky-latency", label: "Latency spike (flaky)", desc: "add +3s latency to flaky-service traffic", icon: Timer, risk: "pod" },
  { action: "system-pod-kill", label: "Kill system pod", desc: "delete a kube-system pod (coredns)", icon: Server, risk: "cluster" },
  { action: "node-cordon", label: "Cordon node", desc: "mark worker unschedulable", icon: Server, risk: "cluster" },
  { action: "node-drain", label: "Drain node", desc: "evict all pods off the worker", icon: Server, risk: "cluster" },
  { action: "node-network-latency", label: "Node network latency", desc: "netem delay on worker egress", icon: Activity, risk: "cluster" },
];

const RECOVERY = [
  { action: "aerospike-up", label: "Aerospike up", icon: Database },
  { action: "yugabyte-up", label: "YugabyteDB up", icon: HardDrive },
  { action: "latency-off", label: "Clear catalog latency", icon: Timer },
  { action: "flaky-latency-off", label: "Clear flaky latency", icon: Timer },
  { action: "network-latency-off", label: "Clear netem delay", icon: Activity },
  { action: "uncordon", label: "Uncordon node", icon: Server },
  { action: "all", label: "Recover all", icon: RotateCcw },
];

function stateBadge(state) {
  if (state === "running" || state === "ready") {
    return <Badge tone="success"><CheckCircle2 size={12} /> {state}</Badge>;
  }
  if (state === "stopped" || state === "cordoned") {
    return <Badge tone="danger"><AlertTriangle size={12} /> {state}</Badge>;
  }
  return <Badge tone="neutral">{state}</Badge>;
}

function fmtSeconds(value) {
  if (value === null || value === undefined) return "—";
  const ms = value < 1 ? value * 1000 : value;
  return value < 1 ? `${ms.toFixed(0)} ms` : `${value.toFixed(2)} s`;
}

function signalRow(label, signals) {
  return (
    <div className="row" style={{ justifyContent: "space-between" }}>
      <span className="text-muted" style={{ fontSize: 13 }}>{label}</span>
      <span style={{ fontSize: 13, fontFamily: "var(--font-mono)" }}>
        req/s {signals.req_s === null || signals.req_s === undefined ? "—" : signals.req_s.toFixed(2)} · 5xx {signals["5xx_pct"] ?? "—"}% · p50 {fmtSeconds(signals.p50_s)} · p95 {fmtSeconds(signals.p95_s)} · p99 {fmtSeconds(signals.p99_s)}
      </span>
    </div>
  );
}

export default function Chaos() {
  const [status, setStatus] = useState(null);
  const [loading, setLoading] = useState(true);
  const [running, setRunning] = useState(null);
  const [log, setLog] = useState("");
  const [error, setError] = useState(null);
  const [activeFaults, setActiveFaults] = useState({});
  const [history, setHistory] = useState([]);
  const [gdFault, setGdFault] = useState("flaky-latency");
  const [gdDuration, setGdDuration] = useState(60);
  const [gdRunning, setGdRunning] = useState(false);
  const [gdReport, setGdReport] = useState(null);
  const [gdError, setGdError] = useState(null);

  const refreshStatus = async () => {
    try {
      const [s, a, h] = await Promise.all([
        api.get("/chaos/status"),
        api.get("/chaos/active"),
        api.get("/chaos/history"),
      ]);
      if (s.data.success) setStatus(s.data);
      else setError(s.data.error);
      setActiveFaults(a.data.data || {});
      setHistory(h.data.data || []);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    refreshStatus();
  }, []);

  const runAction = async (kind, action, label) => {
    if (
      !confirm(
        `Run "${label}"?\n\nThis injects a failure / recovery action against the demo cluster and databases.`
      )
    )
      return;

    setRunning(`${kind}:${action}`);
    setError(null);
    setLog("");
    try {
      const url = kind === "recover" ? "/chaos/recover" : kind === "seed" ? "/chaos/seed" : "/chaos/inject";
      const body = kind === "seed" ? {} : { action };
      const res = await api.post(url, body);
      if (res.data.success) {
        setLog(res.data.stdout || "(no output)");
      } else {
        setError(res.data.error || "Action failed");
        setLog(res.data.stdout || "");
      }
    } catch (e) {
      setError(e.message);
    } finally {
      setRunning(null);
      refreshStatus();
    }
  };

  const runGameDay = async () => {
    setGdRunning(true);
    setGdReport(null);
    setGdError(null);
    try {
      const res = await api.post("/chaos/game-day", {
        action: gdFault,
        duration_s: gdDuration,
      });
      if (res.data.success) setGdReport(res.data.report);
      else setGdError(res.data.error || "Game-day failed");
    } catch (e) {
      setGdError(e.message);
    } finally {
      setGdRunning(false);
      refreshStatus();
    }
  };

  const healthy = (status?.pods || []).filter((p) => p.status === "Running").length;
  const broken = (status?.pods || []).length - healthy;

  return (
    <>
      <div className="page-head">
        <div>
          <h1>Chaos Engineering</h1>
          <p className="page-head__sub">
            Inject and recover from failures with one click — no terminal needed
          </p>
        </div>
        <button
          onClick={() => { setLoading(true); refreshStatus(); }}
          className="btn btn--ghost btn--sm"
          disabled={loading}
        >
          <RefreshCw size={14} className={loading ? "btn__spinner" : ""} /> Refresh
        </button>
      </div>

      {Object.keys(activeFaults).length > 0 && (
        <div
          className="alert alert--warning"
          style={{ marginBottom: "var(--space-4)", display: "flex", gap: "var(--space-2)", alignItems: "center", flexWrap: "wrap" }}
        >
          <span className="text-muted" style={{ fontSize: 13 }}>Active faults:</span>
          {Object.entries(activeFaults).map(([fault, info]) => (
            <Badge key={fault} tone="danger">
              <AlertTriangle size={11} /> {fault} · {info.params || ""} · {info.started}
            </Badge>
          ))}
        </div>
      )}

      {error && (
        <div className="alert alert--danger" style={{ marginBottom: "var(--space-4)" }}>
          {error}
        </div>
      )}

      <div className="grid-3" style={{ marginBottom: "var(--space-4)" }}>
        <Card
          title="Aerospike"
          actions={loading ? <Loader2 size={14} className="btn__spinner" /> : stateBadge(status?.containers?.aerospike)}
        >
          <div className="row">
            <div className="health-item__icon"><Database size={16} /></div>
            <div className="text-muted" style={{ fontSize: 13 }}>local container</div>
          </div>
        </Card>

        <Card
          title="YugabyteDB"
          actions={loading ? <Loader2 size={14} className="btn__spinner" /> : stateBadge(status?.containers?.yugabyte)}
        >
          <div className="row">
            <div className="health-item__icon"><HardDrive size={16} /></div>
            <div className="text-muted" style={{ fontSize: 13 }}>local container</div>
          </div>
        </Card>

        <Card
          title="Worker node"
          actions={loading ? <Loader2 size={14} className="btn__spinner" /> : stateBadge(status?.node?.state)}
        >
          <div className="row">
            <div className="health-item__icon"><Server size={16} /></div>
            <div className="text-muted" style={{ fontSize: 13 }}>
              opensre-demo-worker · {broken} of {(status?.pods || []).length} pods degraded
            </div>
          </div>
        </Card>
      </div>

      <div className="grid-2" style={{ marginBottom: "var(--space-4)" }}>
        <Card
          title="Failure injection"
          subtitle="Click a failure to inject it now"
          actions={
            <Badge tone={broken > 0 ? "warning" : "success"}>
              {broken > 0 ? `${broken} degraded` : "healthy"}
            </Badge>
          }
        >
          <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-3)" }}>
            <div
              style={{
                display: "grid",
                gridTemplateColumns: "repeat(auto-fill, minmax(220px, 1fr))",
                gap: "var(--space-3)",
              }}
            >
              {FAILURES.map((f) => (
                <button
                  key={f.action}
                  className="btn btn--primary btn--sm"
                  onClick={() => runAction("inject", f.action, f.label)}
                  disabled={running !== null}
                  style={{ justifyContent: "space-between" }}
                  title={f.desc}
                >
                  <span style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
                    <f.icon size={14} />
                    {f.label}
                  </span>
                  {running === `inject:${f.action}` && <Loader2 size={13} className="btn__spinner" />}
                </button>
              ))}
            </div>

            <div style={{ marginTop: "var(--space-3)" }}>
              <button
                className="btn btn--ghost btn--sm"
                onClick={() => runAction("seed", null, "Seed database data")}
                disabled={running !== null}
              >
                {running === "seed:null" ? <Loader2 size={14} className="btn__spinner" /> : <Database size={14} />}
                Seed database data (Yugabyte + Aerospike)
              </button>
            </div>
          </div>
        </Card>

        <Card title="Recovery" subtitle="Restore the environment">
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(auto-fill, minmax(180px, 1fr))",
              gap: "var(--space-3)",
            }}
          >
            {RECOVERY.map((r) => (
              <button
                key={r.action}
                className="btn btn--ghost btn--sm"
                onClick={() => runAction("recover", r.action, r.label)}
                disabled={running !== null}
              >
                {running === `recover:${r.action}` ? <Loader2 size={14} className="btn__spinner" /> : <r.icon size={14} />}
                {r.label}
              </button>
            ))}
          </div>

          <div style={{ marginTop: "var(--space-4)" }}>
            <div className="text-muted" style={{ fontSize: 13, marginBottom: "var(--space-2)" }}>
              <Terminal size={13} style={{ verticalAlign: "middle", marginRight: 4 }} />
              Command output
            </div>
            <pre
              style={{
                background: "var(--surface-1)",
                border: "1px solid var(--border)",
                borderRadius: 8,
                padding: "var(--space-3)",
                fontSize: 12,
                maxHeight: 200,
                overflow: "auto",
                whiteSpace: "pre-wrap",
              }}
            >
              {log || "Run an action to see its output here."}
            </pre>
          </div>
        </Card>
      </div>

      <div className="grid-2">
        <Card
          title="Game-day"
          subtitle="Automated baseline → inject → measure → recover → report"
          actions={gdReport ? (
            <Badge tone={gdReport.verdict?.degraded ? "danger" : "neutral"}>
              {gdReport.verdict?.degraded ? "degraded" : "steady"}
            </Badge>
          ) : null}
        >
          <div style={{ display: "flex", gap: "var(--space-3)", alignItems: "center", flexWrap: "wrap" }}>
            <select
              className="btn btn--ghost btn--sm"
              value={gdFault}
              onChange={(e) => setGdFault(e.target.value)}
              disabled={gdRunning}
              style={{ minWidth: 220 }}
            >
              {FAILURES.map((f) => (
                <option key={f.action} value={f.action}>{f.label}</option>
              ))}
            </select>
            <input
              type="number"
              min={60}
              max={600}
              step={15}
              value={gdDuration}
              onChange={(e) => setGdDuration(Number(e.target.value))}
              className="btn btn--ghost btn--sm"
              style={{ width: 90 }}
              disabled={gdRunning}
            />
            <span className="text-muted" style={{ fontSize: 13 }}>s fault window</span>
            <button
              className="btn btn--primary btn--sm"
              onClick={runGameDay}
              disabled={gdRunning}
            >
              {gdRunning ? <Loader2 size={14} className="btn__spinner" /> : <Activity size={14} />}
              {gdRunning ? "Running game-day…" : "Run game-day"}
            </button>
          </div>

          {gdRunning && (
            <div className="text-muted" style={{ fontSize: 13, marginTop: "var(--space-3)" }}>
              Injecting, holding the fault, then recovering and re-measuring after
              the 1-minute metrics window flushes. Expect ~3 minutes per run.
            </div>
          )}

          {gdError && (
            <div className="alert alert--danger" style={{ marginTop: "var(--space-3)" }}>
              {gdError}
            </div>
          )}

          {gdReport && (
            <div style={{ marginTop: "var(--space-3)" }}>
              <div style={{ display: "flex", gap: "var(--space-2)", alignItems: "center", marginBottom: "var(--space-3)" }}>
                <Badge tone="neutral">exp {gdReport.id}</Badge>
                <span className="text-muted" style={{ fontSize: 13 }}>{gdReport.pod_target} · {gdReport.started}</span>
              </div>
              <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-2)" }}>
                {signalRow("Baseline (before)", gdReport.baseline)}
                {signalRow("During (fault)", gdReport.during)}
                {signalRow("After (recovered)", gdReport.after)}
              </div>
              <div style={{ marginTop: "var(--space-3)", display: "flex", gap: "var(--space-2)", flexWrap: "wrap", alignItems: "center" }}>
                <span className="text-muted" style={{ fontSize: 13 }}>Steady-state hypothesis:</span>
                <Badge tone={gdReport.verdict?.degraded ? "danger" : "success"}>
                  {gdReport.verdict?.degraded ? "degraded" : "steady"} (p99 &gt; {gdReport.verdict?.threshold_s}s)
                </Badge>
                <Badge tone={gdReport.verdict?.recovered ? "success" : "warning"}>
                  {gdReport.verdict?.recovered ? "recovered" : "not-recovered"}
                </Badge>
                {gdReport.recovery && (
                  <Badge tone={gdReport.recovery.success ? "success" : "danger"}>
                    recovery {gdReport.recovery.success ? "ok" : "failed"}
                  </Badge>
                )}
              </div>
            </div>
          )}
        </Card>

        <Card
          title="Experiment history"
          subtitle="chaos/experiments/events.jsonl"
          actions={<ListChecks size={14} />}
        >
          {history.length === 0 ? (
            <div className="text-muted" style={{ fontSize: 13 }}>
              No experiments recorded yet — inject or run a game-day to build the timeline.
            </div>
          ) : (
            <ul style={{ listStyle: "none", margin: 0, padding: 0, display: "flex", flexDirection: "column", gap: "var(--space-2)", maxHeight: 300, overflow: "auto" }}>
              {history.slice(0, 40).map((event) => (
                <li key={event.id} style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: "var(--space-2)" }}>
                  <span style={{ display: "inline-flex", alignItems: "center", gap: 6, fontSize: 13 }}>
                    <Badge tone={event.kind === "game-day" ? "warning" : "neutral"}>{event.kind}</Badge>
                    <span style={{ fontFamily: "var(--font-mono)" }}>{event.fault}</span>
                  </span>
                  <span className="text-muted" style={{ fontSize: 12 }}>
                    {event.ts} · {event.params || event.note || ""}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </Card>
      </div>
    </>
  );
}