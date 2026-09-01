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
} from "lucide-react";

const FAILURES = [
  { action: "aerospike-down", label: "Aerospike down", desc: "stop the Aerospike container", icon: Database, risk: "db" },
  { action: "yugabyte-down", label: "YugabyteDB down", desc: "stop the YugabyteDB container", icon: HardDrive, risk: "db" },
  { action: "pod-crash", label: "Pod crash", desc: "recreate the catalog-api pod", icon: Server, risk: "pod" },
  { action: "pod-delete", label: "Pod delete", desc: "delete the catalog-api pod (self-heal)", icon: Server, risk: "pod" },
  { action: "pod-cpu", label: "CPU spike", desc: "busy-loop the catalog-api CPU", icon: Fuel, risk: "pod" },
  { action: "pod-memory", label: "Memory spike", desc: "inflate catalog-api memory", icon: Server, risk: "pod" },
  { action: "system-pod-kill", label: "Kill system pod", desc: "delete a kube-system pod (coredns)", icon: Server, risk: "cluster" },
  { action: "node-cordon", label: "Cordon node", desc: "mark worker unschedulable", icon: Server, risk: "cluster" },
  { action: "node-drain", label: "Drain node", desc: "evict all pods off the worker", icon: Server, risk: "cluster" },
];

const RECOVERY = [
  { action: "aerospike-up", label: "Aerospike up", icon: Database },
  { action: "yugabyte-up", label: "YugabyteDB up", icon: HardDrive },
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

export default function Chaos() {
  const [status, setStatus] = useState(null);
  const [loading, setLoading] = useState(true);
  const [running, setRunning] = useState(null);
  const [log, setLog] = useState("");
  const [error, setError] = useState(null);

  const refreshStatus = async () => {
    try {
      const res = await api.get("/chaos/status");
      if (res.data.success) setStatus(res.data);
      else setError(res.data.error);
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

      <div className="grid-2">
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
                maxHeight: 260,
                overflow: "auto",
                whiteSpace: "pre-wrap",
              }}
            >
              {log || "Run an action to see its output here."}
            </pre>
          </div>
        </Card>
      </div>
    </>
  );
}