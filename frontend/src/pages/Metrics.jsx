import { useEffect, useState, useCallback } from "react";
import api from "../api/api";
import Card from "../components/Card";
import Badge from "../components/Badge";
import Skeleton from "../components/Skeleton";
import {
  Database,
  CheckCircle2,
  XCircle,
  Loader2,
  ExternalLink,
  LayoutDashboard,
  Cpu,
  Boxes,
  RefreshCw,
  Layers,
} from "lucide-react";

const POLL_INTERVAL = 30000;
const GRAFANA_BASE = "http://localhost:3000";

function TargetSelect({ label, icon: Icon, value, options, onChange, disabled }) {
  return (
    <div className="field">
      <label htmlFor={`metrics-${label}`}>
        <Icon size={13} style={{ verticalAlign: "middle", marginRight: 4 }} />
        {label}
      </label>
      <select
        id={`metrics-${label}`}
        className="select"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        disabled={disabled}
      >
        <option value="__all">All {label} targets</option>
        {(options || []).map((opt) => (
          <option key={opt} value={opt}>
            {opt}
          </option>
        ))}
      </select>
    </div>
  );
}

export default function Metrics() {
  const [vmStatus, setVmStatus] = useState(null);
  const [vmChecking, setVmChecking] = useState(true);

  const [clusters, setClusters] = useState([]);
  const [nodes, setNodes] = useState([]);
  const [pods, setPods] = useState([]);
  const [instances, setInstances] = useState([]);

  const [selectedCluster, setSelectedCluster] = useState("__all");
  const [selectedNode, setSelectedNode] = useState("__all");
  const [selectedPod, setSelectedPod] = useState("__all");
  const [selectedInstance, setSelectedInstance] = useState("__all");

  const [targetsLoading, setTargetsLoading] = useState(false);
  const [targetsError, setTargetsError] = useState(null);

  const checkVmHealth = useCallback(async () => {
    setVmChecking(true);
    try {
      const res = await api.get("/metrics/health");
      setVmStatus(res.data.success ? "connected" : "unreachable");
    } catch {
      setVmStatus("backend-offline");
    } finally {
      setVmChecking(false);
    }
  }, []);

  useEffect(() => {
    checkVmHealth();
  }, [checkVmHealth]);

  useEffect(() => {
    const interval = setInterval(() => {
      checkVmHealth();
    }, POLL_INTERVAL);
    return () => clearInterval(interval);
  }, [checkVmHealth]);

  const loadTargets = useCallback(async () => {
    setTargetsLoading(true);
    setTargetsError(null);
    try {
      const [targetRes, clusterRes] = await Promise.all([
        api.get("/metrics/targets"),
        api.get("/kubernetes/clusters"),
      ]);

      const data = targetRes.data;
      if (!data.success) throw new Error(data.error || "Failed to load targets");

      const clusterLines = (clusterRes.data.stdout || "")
        .split("\n")
        .map((line) => line.trim())
        .filter(Boolean);

      setClusters(clusterLines);
      setNodes(data.data.nodes || []);
      setPods(data.data.pods || []);
      setInstances(data.data.instances || []);
    } catch (err) {
      console.error(err);
      setTargetsError(err.message);
    } finally {
      setTargetsLoading(false);
    }
  }, []);

  useEffect(() => {
    if (vmStatus === "connected") loadTargets();
  }, [vmStatus, loadTargets]);

  const vmTone =
    vmStatus === "connected"
      ? "success"
      : vmStatus === "unreachable" || vmStatus === "backend-offline"
        ? "danger"
        : "neutral";

  const vmLabel =
    vmStatus === "connected"
      ? "Connected"
      : vmStatus === "unreachable"
        ? "Unreachable"
        : vmStatus === "backend-offline"
          ? "Backend offline"
          : "Checking…";

  const varParams = new URLSearchParams();
  if (selectedInstance !== "__all") varParams.set("var-instance", selectedInstance);
  if (selectedPod !== "__all") varParams.set("var-pod", selectedPod);
  if (selectedNode !== "__all") varParams.set("var-node", selectedNode);

  const dashParams = new URLSearchParams({
    from: "now-15m",
    to: "now",
    refresh: "5s",
    kiosk: "",
    theme: "dark",
  });
  varParams.forEach((value, key) => dashParams.set(key, value));

  const dashUrl = `${GRAFANA_BASE}/d/opensre-overview/opensre-cluster-and-pod-overview?${dashParams.toString()}`;
  const fullUrl = `${GRAFANA_BASE}/d/opensre-overview/opensre-cluster-and-pod-overview`;

  const hasFilter =
    selectedNode !== "__all" ||
    selectedPod !== "__all" ||
    selectedInstance !== "__all";

  return (
    <>
      <div className="page-head">
        <div>
          <h1>Metrics</h1>
          <p className="page-head__sub">
            Filter the Grafana dashboard by cluster, node, or pod and watch it
            re-render live.
          </p>
        </div>
      </div>

      <div className="grid-2">
        <Card
          title="VictoriaMetrics"
          subtitle="Time-series database · health endpoint"
          actions={
            <Badge tone={vmTone}>
              {vmChecking ? (
                <Loader2 size={12} className="btn__spinner" />
              ) : vmTone === "success" ? (
                <CheckCircle2 size={12} />
              ) : (
                <XCircle size={12} />
              )}
              {vmChecking ? "Checking…" : vmLabel}
            </Badge>
          }
        >
          <div className="row">
            <div className="health-item__icon">
              <Database size={17} strokeWidth={1.8} />
            </div>
            <div>
              <div className="text-muted" style={{ fontSize: 13 }}>
                Scraped by vmagent · queried by OpenSRE evidence collection
              </div>
              <div className="cell-mono" style={{ fontSize: 12 }}>
                http://localhost:8428
              </div>
            </div>
          </div>
        </Card>

        <Card
          title="Dashboard scope"
          subtitle="Pick what the embedded dashboard should focus on"
          actions={
            <button
              type="button"
              className="btn btn--ghost"
              disabled={targetsLoading}
              onClick={loadTargets}
            >
              <RefreshCw size={14} className={targetsLoading ? "btn__spinner" : ""} />{" "}
              Refresh targets
            </button>
          }
        >
          <div className="form-grid">
            <TargetSelect
              label="Instance / Target"
              icon={Cpu}
              value={selectedInstance}
              options={instances}
              onChange={setSelectedInstance}
              disabled={targetsLoading}
            />
            <TargetSelect
              label="Cluster context"
              icon={LayoutDashboard}
              value={selectedCluster}
              options={clusters}
              onChange={setSelectedCluster}
              disabled={targetsLoading}
            />
            <TargetSelect
              label="Node"
              icon={Boxes}
              value={selectedNode}
              options={nodes}
              onChange={setSelectedNode}
              disabled={targetsLoading}
            />
            <TargetSelect
              label="Pod"
              icon={Layers}
              value={selectedPod}
              options={pods}
              onChange={setSelectedPod}
              disabled={targetsLoading}
            />
          </div>

          {targetsError && (
            <div className="alert alert--danger" style={{ marginTop: "var(--space-2)" }}>
              {targetsError}
            </div>
          )}

          {targetsLoading ? (
            <div className="stack stack--tight" style={{ marginTop: "var(--space-3)" }}>
              <Skeleton height={34} />
            </div>
          ) : (
            <div
              className="stack stack--tight"
              style={{ marginTop: "var(--space-3)" }}
            >
              <div className="row" style={{ gap: 20, flexWrap: "wrap" }}>
                <div>
                  <div className="text-muted" style={{ fontSize: 12 }}>
                    Discovered nodes
                  </div>
                  <div className="cell-strong">{nodes.length}</div>
                </div>
                <div>
                  <div className="text-muted" style={{ fontSize: 12 }}>
                    Discovered pods
                  </div>
                  <div className="cell-strong">{pods.length}</div>
                </div>
                <div>
                  <div className="text-muted" style={{ fontSize: 12 }}>
                    Instances
                  </div>
                  <div className="cell-strong">{instances.length}</div>
                </div>
              </div>
              {hasFilter && (
                <Badge tone="info">
                  <Cpu size={12} /> Filtered view active
                </Badge>
              )}
            </div>
          )}
        </Card>
      </div>

      <div className="section-label" style={{ marginTop: "var(--space-4)" }}>
        Grafana live dashboard
      </div>

      <Card
        title="OpenSRE Cluster & Pod Overview"
        subtitle={
          hasFilter
            ? `Filtered · instance=${selectedInstance} node=${selectedNode} pod=${selectedPod}`
            : "Live metrics rendered by Grafana (VictoriaMetrics datasource)"
        }
        actions={
          <a
            href={fullUrl}
            target="_blank"
            rel="noreferrer"
            className="btn btn--ghost btn--sm"
          >
            <ExternalLink size={14} /> Open in Grafana
          </a>
        }
      >
        <iframe
          src={dashUrl}
          title="Grafana: OpenSRE Cluster & Pod Overview"
          style={{
            width: "100%",
            height: 900,
            border: "1px solid var(--border)",
            borderRadius: "var(--radius)",
            background: "var(--surface-2, #111)",
          }}
          frameBorder="0"
        />
        <div className="text-muted" style={{ fontSize: 12, marginTop: "var(--space-2)" }}>
          Auto-refreshes every 5 seconds. Changing the node or pod selector
          above re-filters every panel in real time.
        </div>
      </Card>
    </>
  );
}