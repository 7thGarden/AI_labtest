import { useEffect, useState, useCallback } from "react";
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

const POLL_INTERVAL = 30000;

export default function Metrics() {
  const [vmStatus, setVmStatus] = useState(null);
  const [vmChecking, setVmChecking] = useState(true);

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

      <div className="section-label" style={{ marginTop: "var(--space-4)" }}>
        Grafana live dashboard
      </div>

      <Card
        title="Catalog API Overview"
        subtitle="Live metrics rendered by Grafana (VictoriaMetrics datasource)"
        actions={
          <a
            href="http://localhost:3000/d/catalog-api-overview/catalog-api-overview?from=now-6h&to=now&refresh=5s"
            target="_blank"
            rel="noreferrer"
            className="btn btn--ghost btn--sm"
          >
            <ExternalLink size={14} /> Open in Grafana
          </a>
        }
      >
        <iframe
          src="http://localhost:3000/d/catalog-api-overview/catalog-api-overview?from=now-5m&to=now&refresh=5s&kiosk&theme=dark"
          title="Grafana: Catalog API Overview"
          style={{
            width: "100%",
            height: 720,
            border: "1px solid var(--border)",
            borderRadius: "var(--radius)",
            background: "var(--surface-2, #111)",
          }}
          frameBorder="0"
        />
        <div className="text-muted" style={{ fontSize: 12, marginTop: "var(--space-2)" }}>
          Auto-refreshes every 5 seconds. All panels query VictoriaMetrics in real time.
        </div>
      </Card>
    </>
  );
}