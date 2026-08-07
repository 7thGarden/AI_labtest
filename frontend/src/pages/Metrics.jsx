import { useEffect, useState } from "react";
import api from "../api/api";

export default function Metrics() {
  const [status, setStatus] = useState("Checking...");

  useEffect(() => {
    async function load() {
      try {
        const res = await api.get("/metrics/health");

        if (res.data.success) {
          setStatus("🟢 VictoriaMetrics Connected");
        } else {
          setStatus("🔴 VictoriaMetrics Unreachable");
        }
      } catch (err) {
        setStatus("🔴 Backend Connection Failed");
      }
    }

    load();
  }, []);

  return (
    <>
      <h1>Metrics</h1>

      <div className="table">
        <h2>VictoriaMetrics Status</h2>

        <br />

        <h3>{status}</h3>
      </div>

      <br />

      <div className="table">
        <h2>Grafana Dashboard</h2>

        <br />

        <iframe
          title="Grafana"
          src="http://localhost:3000"
          width="100%"
          height="700"
          style={{
            border: "none",
            borderRadius: "10px",
          }}
        />
      </div>
    </>
  );
}