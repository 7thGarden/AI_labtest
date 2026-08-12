import { useEffect, useState } from "react";
import api from "../api/api";
import Card from "../components/Card";
import Badge from "../components/Badge";
import {
  Database,
  CheckCircle2,
  XCircle,
  Loader2,
  ExternalLink,
} from "lucide-react";

export default function Metrics() {
  const [status, setStatus] = useState(null);
  const [checking, setChecking] = useState(true);

  useEffect(() => {
    async function load() {
      setChecking(true);

      try {
        const res = await api.get("/metrics/health");
        setStatus(res.data.success ? "connected" : "unreachable");
      } catch {
        setStatus("backend-offline");
      } finally {
        setChecking(false);
      }
    }

    load();
  }, []);

  const tone =
    status === "connected"
      ? "success"
      : status === "unreachable" || status === "backend-offline"
        ? "danger"
        : "neutral";

  const label =
    status === "connected"
      ? "Connected"
      : status === "unreachable"
        ? "Unreachable"
        : status === "backend-offline"
          ? "Backend offline"
          : "Checking…";

  return (
    <>
      <div className="page-head">
        <div>
          <h1>Metrics</h1>
          <p className="page-head__sub">
            Time-series collection and visualization.
          </p>
        </div>
      </div>

      <div className="grid-2">
        <Card
          title="VictoriaMetrics"
          subtitle="Time-series database · health endpoint"
          actions={
            <Badge tone={tone}>
              {checking ? (
                <Loader2 size={12} className="btn__spinner" />
              ) : tone === "success" ? (
                <CheckCircle2 size={12} />
              ) : (
                <XCircle size={12} />
              )}
              {checking ? "Checking…" : label}
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
          title="Grafana"
          subtitle="Dashboards and alerting"
          actions={
            <a
              href="http://localhost:3000"
              target="_blank"
              rel="noreferrer"
              className="btn btn--ghost btn--sm"
            >
              <ExternalLink size={14} /> Open
            </a>
          }
        >
          <p className="text-muted" style={{ fontSize: 13, maxWidth: 480 }}>
            Grafana may block being embedded in a page. Use the button above to
            open the full Grafana experience.
          </p>

          <iframe
            title="Grafana"
            src="http://localhost:3000"
            width="100%"
            height="520"
            style={{
              border: "1px solid var(--border)",
              borderRadius: "var(--radius-sm)",
              background: "#fff",
              marginTop: "var(--space-4)",
            }}
          />
        </Card>
      </div>
    </>
  );
}