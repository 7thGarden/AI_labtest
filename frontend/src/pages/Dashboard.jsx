import { useEffect, useState } from "react";
import api from "../api/api";
import Card from "../components/Card";

export default function Dashboard() {
  const [stats, setStats] = useState({
    nodes: 0,
    pods: 0,
    services: 0,
    deployments: 0,
  });

  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function load() {
      try {
        const [nodes, pods, services, deployments] = await Promise.all([
          api.get("/kubernetes/nodes"),
          api.get("/kubernetes/pods"),
          api.get("/kubernetes/services"),
          api.get("/kubernetes/deployments"),
        ]);

        setStats({
          nodes: nodes.data.stdout.split("\n").slice(1).filter(Boolean).length,
          pods: pods.data.stdout.split("\n").slice(1).filter(Boolean).length,
          services: services.data.stdout.split("\n").slice(1).filter(Boolean).length,
          deployments: deployments.data.stdout
            .split("\n")
            .slice(1)
            .filter(Boolean).length,
        });
      } catch (err) {
        console.error(err);
      }

      setLoading(false);
    }

    load();
  }, []);

  if (loading) return <h2>Loading Dashboard...</h2>;

  return (
    <>
      <h1>Dashboard</h1>

      <div className="cards">
        <Card title="Nodes" value={stats.nodes} color="#16a34a" />
        <Card title="Pods" value={stats.pods} color="#2563eb" />
        <Card title="Services" value={stats.services} color="#ea580c" />
        <Card title="Deployments" value={stats.deployments} color="#9333ea" />
      </div>

      <div className="table">
        <h2>Cluster Health</h2>

        <br />

        <table>
          <tbody>
            <tr>
              <td>Kubernetes</td>
              <td>🟢 Running</td>
            </tr>

            <tr>
              <td>Catalog API</td>
              <td>🟢 Running</td>
            </tr>

            <tr>
              <td>VictoriaMetrics</td>
              <td>🟢 Running</td>
            </tr>

            <tr>
              <td>Grafana</td>
              <td>🟢 Running</td>
            </tr>

            <tr>
              <td>OpenTelemetry Collector</td>
              <td>🟢 Running</td>
            </tr>

            <tr>
              <td>vmagent</td>
              <td>🟢 Running</td>
            </tr>
          </tbody>
        </table>
      </div>
    </>
  );
}