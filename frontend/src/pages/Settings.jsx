import { useEffect, useState } from "react";
import api from "../api/api";

export default function Settings() {
  const [backend, setBackend] = useState("Checking...");
  const [kubernetes, setKubernetes] = useState("Checking...");
  const [metrics, setMetrics] = useState("Checking...");
  const [opensre, setOpensre] = useState("Checking...");

  useEffect(() => {
    async function load() {
      try {
        await api.get("/health");
        setBackend("🟢 Online");
      } catch {
        setBackend("🔴 Offline");
      }

      try {
        await api.get("/kubernetes/nodes");
        setKubernetes("🟢 Connected");
      } catch {
        setKubernetes("🔴 Disconnected");
      }

      try {
        await api.get("/metrics/health");
        setMetrics("🟢 Connected");
      } catch {
        setMetrics("🔴 Disconnected");
      }

      try {
        await api.get("/opensre/version");
        setOpensre("🟢 Installed");
      } catch {
        setOpensre("🔴 Not Found");
      }
    }

    load();
  }, []);

  return (
    <>
      <h1>Settings</h1>

      <div className="table">
        <table>
          <tbody>
            <tr>
              <td>Backend API</td>
              <td>{backend}</td>
            </tr>

            <tr>
              <td>Kubernetes Cluster</td>
              <td>{kubernetes}</td>
            </tr>

            <tr>
              <td>VictoriaMetrics</td>
              <td>{metrics}</td>
            </tr>

            <tr>
              <td>OpenSRE CLI</td>
              <td>{opensre}</td>
            </tr>

            <tr>
              <td>Backend URL</td>
              <td>http://127.0.0.1:8001/api</td>
            </tr>

            <tr>
              <td>Grafana</td>
              <td>
                <a
                  href="http://localhost:3000"
                  target="_blank"
                  rel="noreferrer"
                >
                  Open Grafana
                </a>
              </td>
            </tr>

            <tr>
              <td>Swagger Docs</td>
              <td>
                <a
                  href="http://127.0.0.1:8001/docs"
                  target="_blank"
                  rel="noreferrer"
                >
                  Open Swagger
                </a>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </>
  );
}