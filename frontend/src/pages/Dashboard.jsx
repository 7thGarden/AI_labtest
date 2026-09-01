import { useEffect, useState, useCallback, useRef } from "react";
import { Link } from "react-router-dom";
import api from "../api/api";
import Card from "../components/Card";
import Badge from "../components/Badge";
import StatCard from "../components/StatCard";
import Skeleton from "../components/Skeleton";
import {
  Activity,
  AlertTriangle,
  Boxes,
  BrainCircuit,
  CheckCircle2,
  Container,
  Database,
  Gauge,
  Layers,
  Network,
  Package,
  Radar,
  RefreshCw,
  Rocket,
  Server,
  ShieldCheck,
  Share2,
  XCircle,
  Zap,
} from "lucide-react";

const STAT_CONFIG = [
  { key: "clusters", label: "Clusters", icon: Network },
  { key: "nodes", label: "Node Count", icon: Server },
  { key: "pods", label: "Pods", icon: Layers },
  { key: "deployments", label: "Deployments", icon: Package },
  { key: "services", label: "Services", icon: Share2 },
];

const TRAFFIC_QUERIES = {
  rps: "sum(rate(http_requests_total[1m]))",
  errps: 'sum(rate(http_requests_total{status="5xx"}[1m]))',
  errShare:
    'sum(rate(http_requests_total{status="5xx"}[1m])) / clamp_min(sum(rate(http_requests_total[1m])), 1e-3) * 100',
  p95: "histogram_quantile(0.95, sum(rate(http_request_duration_seconds_bucket[1m])) by (le))",
};

const STATUS_TONE = {
  Running: "success",
  Pending: "warning",
  ContainerCreating: "warning",
  CrashLoopBackOff: "danger",
  ImagePullBackOff: "danger",
  Error: "danger",
  Failed: "danger",
};

const GROUP_ORDER = [
  "Running",
  "Pending",
  "CrashLoopBackOff",
  "ImagePullBackOff",
];

function groupPods(pods) {
  const groups = { Running: 0, Pending: 0, CrashLoopBackOff: 0, ImagePullBackOff: 0, Other: 0 };
  for (const pod of pods) {
    const key = GROUP_ORDER.includes(pod.status) ? pod.status : "Other";
    groups[key] += 1;
  }
  return groups;
}

function isDegraded(pod) {
  if (["Running", "Succeeded", "Completed"].includes(pod.status)) return false;
  const [ready, desired] = pod.ready.split("/").map(Number);
  if (desired >= 0 && ready < desired && !["Terminating"].includes(pod.status)) {
    return true;
  }
  return false;
}

function formatRate(value) {
  if (value == null || Number.isNaN(value)) return "—";
  return `${value.toFixed(1)}`;
}

function formatLatency(seconds) {
  if (seconds == null || Number.isNaN(seconds)) return "—";
  if (seconds < 1) return `${Math.round(seconds * 1000)} ms`;
  if (seconds < 10) return `${seconds.toFixed(2)} s`;
  return `${Math.round(seconds)} s`;
}

function HealthItem({ icon: Icon, name, detail, ok }) {
  return (
    <div className="health-item">
      <div className="health-item__icon">
        <Icon size={16} strokeWidth={1.8} />
      </div>

      <div>
        <div className="health-item__name">{name}</div>
        <div className="health-item__detail">{detail}</div>
      </div>

      <div className="health-item__status">
        {ok ? (
          <Badge tone="success">
            <CheckCircle2 size={12} /> Operational
          </Badge>
        ) : (
          <Badge tone="danger">
            <XCircle size={12} /> Offline
          </Badge>
        )}
      </div>
    </div>
  );
}

function TrafficTile({ label, value, tone, sub, icon: Icon }) {
  return (
    <div className="metric-tile">
      <div className="metric-tile__icon">
        <Icon size={15} strokeWidth={2} />
      </div>
      <div>
        <div className={`metric-tile__value metric-tile__value--${tone || "neutral"}`}>
          {value}
        </div>
        <div className="metric-tile__label">{label}</div>
        {sub && <div className="metric-tile__sub">{sub}</div>}
      </div>
    </div>
  );
}

export default function Dashboard() {
  const [stats, setStats] = useState({
    clusters: 0,
    nodes: 0,
    pods: 0,
    services: 0,
    deployments: 0,
  });
  const [clusters, setClusters] = useState([]);
  const [nodes, setNodes] = useState([]);
  const [pods, setPods] = useState([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [recent, setRecent] = useState(null);
  const [live, setLive] = useState(true);
  const [traffic, setTraffic] = useState({
    rps: null,
    errps: null,
    errShare: null,
    p95: null,
  });
  const [health, setHealth] = useState({
    backend: null,
    kubernetes: null,
    metrics: null,
    opensre: null,
  });

  const liveRef = useRef(live);
  liveRef.current = live;

  const splitLines = useCallback((output, header = true) => {
    return (output || "")
      .split("\n")
      .slice(header ? 1 : 0)
      .map((line) => line.trim())
      .filter(Boolean);
  }, []);

  const load = useCallback(async () => {
    const [clusterRes, nodesRes, podsRes, servicesRes, deploymentsRes] =
      await Promise.all([
        api.get("/kubernetes/clusters"),
        api.get("/kubernetes/nodes"),
        api.get("/kubernetes/pods"),
        api.get("/kubernetes/services"),
        api.get("/kubernetes/deployments"),
      ]);

    const clusterLines = splitLines(clusterRes.data.stdout, false);

    const nodes = splitLines(nodesRes.data.stdout).map((line) => {
      const cols = line.split(/\s+/);
      return {
        name: cols[0],
        status: cols[1],
        roles: cols[2] === "<none>" ? "worker" : cols[2],
        ip: cols[5],
      };
    });

    const pods = splitLines(podsRes.data.stdout).map((line) => {
      const cols = line.split(/\s+/);
      return {
        namespace: cols[0],
        name: cols[1],
        ready: cols[2],
        status: cols[3],
        restarts: cols[4],
      };
    });

    return {
      clusters: clusterLines,
      nodes,
      pods,
      stats: {
        clusters: clusterLines.length,
        nodes: nodes.length,
        pods: pods.length,
        services: splitLines(servicesRes.data.stdout).length,
        deployments: splitLines(deploymentsRes.data.stdout).length,
      },
    };
  }, [splitLines]);

  const loadTraffic = useCallback(async () => {
    if (!liveRef.current) return;

    const entries = await Promise.all(
      Object.entries(TRAFFIC_QUERIES).map(async ([key, query]) => {
        try {
          const res = await api.get("/metrics/query", { params: { query } });
          const result = res.data?.data?.data?.result;
          const value = result?.[0]?.value;
          return [key, value ? Number(value[1]) : null];
        } catch {
          return [key, null];
        }
      })
    );

    setTraffic(Object.fromEntries(entries));
  }, []);

  const loadHealth = useCallback(async () => {
    const checks = {
      backend: async () => (await api.get("/health")).data.status === "UP",
      kubernetes: async () => (await api.get("/kubernetes/nodes")).data.success,
      metrics: async () => (await api.get("/metrics/health")).data.success,
      opensre: async () => (await api.get("/opensre/version")).data.success,
    };

    const entries = await Promise.all(
      Object.entries(checks).map(async ([key, fn]) => {
        try {
          return [key, await fn()];
        } catch {
          return [key, false];
        }
      })
    );

    return Object.fromEntries(entries);
  }, []);

  const refreshAll = useCallback(async () => {
    const [result, healthResult] = await Promise.all([load(), loadHealth()]);
    setClusters(result.clusters);
    setNodes(result.nodes);
    setPods(result.pods);
    setStats(result.stats);
    setHealth(healthResult);
    setRecent(new Date());
  }, [load, loadHealth]);

  useEffect(() => {
    let cancelled = false;

    refreshAll()
      .then(() => loadTraffic())
      .catch((err) => console.error("Failed to load dashboard data:", err))
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [refreshAll, loadTraffic]);

  useEffect(() => {
    const timer = setInterval(() => {
      loadTraffic().catch(() => {});
    }, 15000);
    return () => clearInterval(timer);
  }, [loadTraffic]);

  const degraded = pods.filter(isDegraded);
  const groups = groupPods(pods);
  const healthyCount = pods.length - degraded.length;
  const healthyPct = pods.length ? Math.round((healthyCount / pods.length) * 100) : 0;
  const degradedPct = pods.length ? Math.round((degraded.length / pods.length) * 100) : 0;
  const systemsOk = Object.values(health).every((value) => value !== false);

  const sortedPods = [...pods].sort((a, b) => {
    const toneRank = (pod) =>
      isDegraded(pod) ? 0 : pod.status === "Running" ? 1 : 2;
    return toneRank(a) - toneRank(b) || a.namespace.localeCompare(b.namespace);
  });

  const shownPods = sortedPods.slice(0, 12);

  const trafficHealthy = (traffic.errShare ?? 0) < 1;

  return (
    <>
      <div className="page-head">
        <div>
          <h1>Dashboard</h1>
          <p className="page-head__sub">
            A real-time view of your Kubernetes estate and observability stack.
          </p>
        </div>

        <div className="page-head__actions">
          {recent && !loading && (
            <>
              <span className="live-indicator">
                <span className={`live-dot${live ? " live-dot--on" : ""}`} />
                {live ? "Live" : "Paused"}
              </span>
              <span className="text-muted">
                Updated {recent.toLocaleTimeString()}
              </span>
            </>
          )}
          <button
            type="button"
            className="btn btn--ghost"
            disabled={refreshing}
            onClick={() => {
              setRefreshing(true);
              refreshAll()
                .then(() => loadTraffic())
                .catch((err) => console.error("Failed to refresh:", err))
                .finally(() => setRefreshing(false));
            }}
          >
            <RefreshCw size={14} className={refreshing ? "btn__spinner" : ""} />
            Refresh
          </button>
        </div>
      </div>

      {!loading &&
        (degraded.length > 0 ? (
          <div className="status-banner status-banner--danger">
            <div className="status-banner__icon">
              <AlertTriangle size={18} />
            </div>
            <div className="status-banner__body">
              <div className="status-banner__title">
                {degraded.length} workload{degraded.length === 1 ? " is" : "s are"} degraded
              </div>
              <div className="status-banner__text">
                {degraded
                  .map((pod) => `${pod.name} (${pod.status})`)
                  .join(" · ")}
              </div>
            </div>
            <div className="status-banner__actions">
              <Link to="/analysis" className="btn btn--sm btn--light">
                <BrainCircuit size={13} /> Investigate
              </Link>
              <Link to="/chaos" className="btn btn--sm btn--light">
                <Zap size={13} /> Failure injection
              </Link>
            </div>
          </div>
        ) : (
          <div className="status-banner status-banner--success">
            <div className="status-banner__icon">
              <ShieldCheck size={18} />
            </div>
            <div className="status-banner__body">
              <div className="status-banner__title">All systems operational</div>
              <div className="status-banner__text">
                {pods.length} pods healthy across {stats.nodes} nodes.
              </div>
            </div>
            <div className="status-banner__actions">
              <Link to="/analysis" className="btn btn--sm btn--light">
                <BrainCircuit size={13} /> Run an investigation
              </Link>
            </div>
          </div>
        ))}

      <div className="stat-grid">
        {STAT_CONFIG.map((stat) => (
          <StatCard
            key={stat.key}
            label={stat.label}
            value={stats[stat.key]}
            icon={stat.icon}
            loading={loading}
          />
        ))}

        <StatCard
          label="Degraded"
          value={loading ? undefined : degraded.length}
          icon={AlertTriangle}
          loading={loading}
          tone="danger"
          trend={loading ? undefined : `${degradedPct}% of pods not healthy`}
        />
      </div>

      <div className="dash-grid-3">
        <Card
          title="Pod health"
          subtitle="Distribution of workload states"
          actions={
            <Badge tone="primary">
              <Radar size={12} /> {healthyPct}% healthy
            </Badge>
          }
        >
          {loading ? (
            <Skeleton height={96} />
          ) : (
            <>
              <div
                className="stacked-bar"
                style={{
                  gridTemplateColumns: `${groups.Running}fr ${groups.Pending}fr ${groups.CrashLoopBackOff}fr ${groups.ImagePullBackOff}fr ${groups.Other}fr`,
                }}
              >
                {groups.Running > 0 && (
                  <div
                    className="stacked-bar__seg stacked-bar__seg--success"
                    title={`${groups.Running} running`}
                  />
                )}
                {groups.Pending > 0 && (
                  <div
                    className="stacked-bar__seg stacked-bar__seg--warning"
                    title={`${groups.Pending} pending`}
                  />
                )}
                {groups.CrashLoopBackOff > 0 && (
                  <div
                    className="stacked-bar__seg stacked-bar__seg--danger"
                    title={`${groups.CrashLoopBackOff} crash-looping`}
                  />
                )}
                {groups.ImagePullBackOff > 0 && (
                  <div
                    className="stacked-bar__seg stacked-bar__seg--danger"
                    title={`${groups.ImagePullBackOff} image pull failing`}
                  />
                )}
                {groups.Other > 0 && (
                  <div
                    className="stacked-bar__seg stacked-bar__seg--neutral"
                    title={`${groups.Other} other`}
                  />
                )}
              </div>

              <div className="status-chips">
                {Object.entries(groups)
                  .filter(([, count]) => count > 0)
                  .map(([status, count]) => (
                    <span
                      key={status}
                      className={`status-chip${STATUS_TONE[status] ? ` status-chip--${STATUS_TONE[status]}` : ""}`}
                    >
                      {count} {status}
                    </span>
                  ))}
              </div>
            </>
          )}
        </Card>

        <Card
          title="Live traffic"
          subtitle="HTTP ingress measured by VictoriaMetrics"
          actions={
            <button
              type="button"
              className="btn btn--ghost btn--sm"
              onClick={() => {
                setLive((value) => !value);
              }}
              disabled={loading}
            >
              {live ? "Pause" : "Resume"}
            </button>
          }
        >
          {loading ? (
            <Skeleton height={96} />
          ) : (
            <div className="metric-grid">
              <TrafficTile
                label="Request rate"
                sub="requests / sec"
                value={formatRate(traffic.rps)}
                icon={Activity}
              />
              <TrafficTile
                label="Error rate"
                sub="5xx / sec"
                value={formatRate(traffic.errps)}
                tone={traffic.errps > 0 ? "danger" : "success"}
                icon={XCircle}
              />
              <TrafficTile
                label="Error share"
                sub={`${trafficHealthy ? "within" : "above"} noise budget`}
                value={
                  traffic.errShare == null || Number.isNaN(traffic.errShare)
                    ? "—"
                    : `${traffic.errShare.toFixed(1)}%`
                }
                tone={trafficHealthy ? "success" : "warning"}
                icon={Gauge}
              />
              <TrafficTile
                label="p95 latency"
                sub="request duration"
                value={formatLatency(traffic.p95)}
                icon={Rocket}
              />
            </div>
          )}
        </Card>

        <Card
          title="Component health"
          subtitle="Liveness of connected services"
          actions={
            systemsOk ? (
              <Badge tone="success">
                <CheckCircle2 size={12} /> Ready
              </Badge>
            ) : (
              <Badge tone="danger">
                <AlertTriangle size={12} /> Attention
              </Badge>
            )
          }
        >
          <div className="health-list">
            <HealthItem
              icon={Layers}
              name="Backend API"
              detail="OpenSRE backend · :8001"
              ok={health.backend}
            />
            <HealthItem
              icon={Container}
              name="Kubernetes"
              detail={`${stats.nodes} node${stats.nodes === 1 ? "" : "s"} reachable`}
              ok={health.kubernetes}
            />
            <HealthItem
              icon={Database}
              name="VictoriaMetrics"
              detail="Metrics backend · :8428"
              ok={health.metrics}
            />
            <HealthItem
              icon={BrainCircuit}
              name="OpenSRE"
              detail="AI investigation engine"
              ok={health.opensre}
            />
          </div>
        </Card>
      </div>

      <Card
        title="Workloads"
        subtitle="All pods, degraded first"
        actions={
          <Badge tone="primary">
            <Boxes size={12} /> {pods.length}
          </Badge>
        }
      >
        {loading ? (
          <div className="stack stack--tight">
            {[0, 1, 2].map((i) => (
              <Skeleton key={i} height={40} />
            ))}
          </div>
        ) : pods.length === 0 ? (
          <div className="empty-state">
            <Container size={26} /> No pods detected.
          </div>
        ) : (
          <>
            <div className="table-wrap">
              <table className="table">
                <thead>
                  <tr>
                    <th>Pod</th>
                    <th>Namespace</th>
                    <th className="cell-center">Ready</th>
                    <th>Status</th>
                    <th className="cell-end">Restarts</th>
                  </tr>
                </thead>
                <tbody>
                  {shownPods.map((pod) => {
                    const [ready, desired] = pod.ready.split("/").map(Number);
                    const notReady = desired > 0 && ready < desired;
                    return (
                      <tr key={`${pod.namespace}/${pod.name}`}>
                        <td className="cell-strong cell-mono">{pod.name}</td>
                        <td>
                          <Badge tone="neutral">{pod.namespace}</Badge>
                        </td>
                        <td className="cell-center">
                          <span
                            className={notReady ? "text-danger" : "text-muted"}
                          >
                            {pod.ready}
                          </span>
                        </td>
                        <td>
                          <Badge tone={STATUS_TONE[pod.status] || "info"}>
                            {pod.status}
                          </Badge>
                        </td>
                        <td className="cell-end">
                          <span className="text-muted">{pod.restarts}</span>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
            {pods.length > shownPods.length && (
              <p className="text-muted" style={{ marginTop: "var(--space-3)" }}>
                …and {pods.length - shownPods.length} more workloads.
              </p>
            )}
          </>
        )}
      </Card>

      <div className="dash-grid-2">
        <Card
          title="Nodes"
          subtitle="Cluster node inventory"
          actions={
            <Badge tone="success">
              <Server size={12} /> {nodes.length}
            </Badge>
          }
        >
          {loading ? (
            <div className="stack stack--tight">
              {[0, 1].map((i) => (
                <Skeleton key={i} height={40} />
              ))}
            </div>
          ) : nodes.length === 0 ? (
            <div className="empty-state">
              <Container size={26} /> No nodes detected.
            </div>
          ) : (
            <div className="table-wrap">
              <table className="table">
                <thead>
                  <tr>
                    <th>Node</th>
                    <th>Role</th>
                    <th>IP</th>
                    <th className="cell-end">Status</th>
                  </tr>
                </thead>
                <tbody>
                  {nodes.map((node) => (
                    <tr key={node.name}>
                      <td className="cell-strong cell-mono">{node.name}</td>
                      <td className="cell-muted">{node.roles}</td>
                      <td className="cell-mono cell-muted">{node.ip}</td>
                      <td className="cell-end">
                        <Badge tone="success">{node.status}</Badge>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Card>

        <Card
          title="Cluster contexts"
          subtitle="Active kubeconfig contexts"
          actions={
            <Badge tone="primary">
              <Radar size={12} /> {clusters.length}
            </Badge>
          }
        >
          {loading ? (
            <div className="stack stack--tight">
              {[0, 1].map((i) => (
                <Skeleton key={i} height={40} />
              ))}
            </div>
          ) : clusters.length === 0 ? (
            <div className="empty-state">
              <Container size={26} /> No Kubernetes clusters detected.
            </div>
          ) : (
            <div className="table-wrap">
              <table className="table">
                <thead>
                  <tr>
                    <th>Cluster context</th>
                    <th className="cell-end">Status</th>
                  </tr>
                </thead>
                <tbody>
                  {clusters.map((cluster) => (
                    <tr key={cluster}>
                      <td className="cell-strong cell-mono">{cluster}</td>
                      <td className="cell-end">
                        <Badge tone="success">Available</Badge>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Card>
      </div>
    </>
  );
}