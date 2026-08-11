import { useEffect, useState } from "react";
import api from "../api/api";

function Card({ title, value, color }) {
  return (
    <div
      className="card"
      style={{
        borderLeft: `4px solid ${color}`,
      }}
    >
      <h3>{title}</h3>
      <p>{value}</p>
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

  useEffect(() => {
    async function load() {
      try {
        const [
          clusterRes,
          nodesRes,
          podsRes,
          servicesRes,
          deploymentsRes,
        ] = await Promise.all([
          api.get("/kubernetes/clusters"),
          api.get("/kubernetes/nodes"),
          api.get("/kubernetes/pods"),
          api.get("/kubernetes/services"),
          api.get("/kubernetes/deployments"),
        ]);

        const clusterLines = (clusterRes.data.stdout || "")
          .split("\n")
          .map((line) => line.trim())
          .filter(Boolean);

        const nodeLines = (nodesRes.data.stdout || "")
          .split("\n")
          .slice(1)
          .filter(Boolean);

        const podLines = (podsRes.data.stdout || "")
          .split("\n")
          .slice(1)
          .filter(Boolean);

        const serviceLines = (servicesRes.data.stdout || "")
          .split("\n")
          .slice(1)
          .filter(Boolean);

        const deploymentLines = (deploymentsRes.data.stdout || "")
          .split("\n")
          .slice(1)
          .filter(Boolean);

        setClusters(clusterLines);

        setStats({
          clusters: clusterLines.length,
          nodes: nodeLines.length,
          pods: podLines.length,
          services: serviceLines.length,
          deployments: deploymentLines.length,
        });
      } catch (err) {
        console.error("Failed to load dashboard data:", err);
      } finally {
        setLoading(false);
      }
    }

    load();
  }, []);

  return (
    <>
      <h1>Dashboard</h1>

      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))",
          gap: "20px",
          marginBottom: "30px",
        }}
      >
        <Card
          title="Clusters"
          value={loading ? "..." : stats.clusters}
          color="#7c3aed"
        />

        <Card
          title="Nodes"
          value={loading ? "..." : stats.nodes}
          color="#16a34a"
        />

        <Card
          title="Pods"
          value={loading ? "..." : stats.pods}
          color="#2563eb"
        />

        <Card
          title="Services"
          value={loading ? "..." : stats.services}
          color="#ea580c"
        />

        <Card
          title="Deployments"
          value={loading ? "..." : stats.deployments}
          color="#0891b2"
        />
      </div>

      <br />

      <div className="table">
        <h2>Kubernetes Clusters</h2>

        <br />

        {loading ? (
          <p>Loading clusters...</p>
        ) : clusters.length === 0 ? (
          <p>No Kubernetes clusters detected.</p>
        ) : (
          <table width="100%">
            <thead>
              <tr>
                <th align="left">Cluster Context</th>
                <th align="left">Status</th>
              </tr>
            </thead>

            <tbody>
              {clusters.map((cluster) => (
                <tr key={cluster}>
                  <td>{cluster}</td>
                  <td>Available</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      <br />

      <div className="table">
        <h2>Cluster Health</h2>

        <br />

        <p>
          {stats.clusters === 0
            ? "No Kubernetes cluster detected."
            : `${stats.clusters} Kubernetes cluster${
                stats.clusters === 1 ? "" : "s"
              } detected.`}
        </p>

        <p>
          {stats.nodes} node{stats.nodes === 1 ? "" : "s"},{" "}
          {stats.pods} pod{stats.pods === 1 ? "" : "s"},{" "}
          {stats.services} service{stats.services === 1 ? "" : "s"} and{" "}
          {stats.deployments} deployment
          {stats.deployments === 1 ? "" : "s"} currently visible.
        </p>
      </div>
    </>
  );
}
