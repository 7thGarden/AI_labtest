import { useEffect, useState, useCallback } from "react";
import api from "../api/api";
import Card from "../components/Card";
import Badge from "../components/Badge";
import StatCard from "../components/StatCard";
import Skeleton from "../components/Skeleton";
import {
  Boxes,
  Layers,
  RefreshCw,
  CheckCircle2,
  XCircle,
  Database,
  BrainCircuit,
  Container,
  Radar,
  Network,
  Share2,
  Package,
} from "lucide-react";

const STAT_CONFIG = [
  { key: "clusters", label: "Clusters", icon: Network },
  { key: "nodes", label: "Nodes", icon: Boxes },
  { key: "pods", label: "Pods", icon: Layers },
  { key: "services", label: "Services", icon: Share2 },
  { key: "deployments", label: "Deployments", icon: Package },
];

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

export default function Dashboard() {
  const [stats, setStats] = useState({
    clusters: 0,
    nodes: 0,
    pods: 0,
    services: 0,
    deployments: 0,
  });
  const [clusters, setClusters] = useState([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [health, setHealth] = useState({
    backend: null,
    kubernetes: null,
    metrics: null,
    opensre: null,
  });

  const load = useCallback(async () => {
    const [clusterRes, nodesRes, podsRes, servicesRes, deploymentsRes] =
      await Promise.all([
        api.get("/kubernetes/clusters"),
        api.get("/kubernetes/nodes"),
        api.get("/kubernetes/pods"),
        api.get("/kubernetes/services"),
        api.get("/kubernetes/deployments"),
      ]);

    const splitLines = (output, header = true) =>
      (output || "")
        .split("\n")
        .slice(header ? 1 : 0)
        .map((line) => line.trim())
        .filter(Boolean);

    const clusterLines = splitLines(clusterRes.data.stdout, false);

    return {
      clusters: clusterLines,
      stats: {
        clusters: clusterLines.length,
        nodes: splitLines(nodesRes.data.stdout).length,
        pods: splitLines(podsRes.data.stdout).length,
        services: splitLines(servicesRes.data.stdout).length,
        deployments: splitLines(deploymentsRes.data.stdout).length,
      },
    };
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

  useEffect(() => {
    let cancelled = false;

    Promise.all([load(), loadHealth()]).then(
      ([result, healthResult]) => {
        if (cancelled) return;
        setClusters(result.clusters);
        setStats(result.stats);
        setHealth(healthResult);
        setLoading(false);
      },
      (err) => {
        console.error("Failed to load dashboard data:", err);
        if (!cancelled) setLoading(false);
      }
    );

    return () => {
      cancelled = true;
    };
  }, [load, loadHealth]);

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
          <button
            type="button"
            className="btn btn--ghost"
            disabled={refreshing}
            onClick={() => {
              setRefreshing(true);
              Promise.all([load(), loadHealth()])
                .then(([result, healthResult]) => {
                  setClusters(result.clusters);
                  setStats(result.stats);
                  setHealth(healthResult);
                })
                .catch((err) =>
                  console.error("Failed to load dashboard data:", err)
                )
                .finally(() => setRefreshing(false));
            }}
          >
            <RefreshCw size={14} className={refreshing ? "btn__spinner" : ""} />
            Refresh
          </button>
        </div>
      </div>

      <div className="stat-grid">
        {STAT_CONFIG.map((stat) => (
          <StatCard
            key={stat.key}
            label={stat.label}
            value={stats[stat.key]}
            icon={stat.icon}
            loading={loading}
            trend={
              loading ? undefined : `${stat.label} in current cluster context`
            }
          />
        ))}
      </div>

      <div className="grid-2">
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
              <Container size={26} />
              No Kubernetes clusters detected.
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

        <Card title="Component health" subtitle="Liveness of connected services">
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
    </>
  );
}