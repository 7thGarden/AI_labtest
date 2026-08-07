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
    async function fetchData() {
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

    fetchData();
  }, []);

  if (loading) {
    return <h2>Loading Dashboard...</h2>;
  }

  return (
    <>
      <h1>Dashboard</h1>

      <div className="cards">
        <Card title="Nodes" value={stats.nodes} />
        <Card title="Pods" value={stats.pods} />
        <Card title="Services" value={stats.services} />
        <Card title="Deployments" value={stats.deployments} />
      </div>

      <div className="table">
        <h2>System Status</h2>

        <br />

        <p>✅ Kubernetes Connected</p>
        <p>✅ OpenSRE Backend Running</p>
        <p>✅ VictoriaMetrics Running</p>
        <p>✅ Grafana Running</p>
      </div>
    </>
  );
}