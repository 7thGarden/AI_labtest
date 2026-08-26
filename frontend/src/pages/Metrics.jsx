import { useEffect, useState, useCallback } from "react";
import api from "../api/api";
import Card from "../components/Card";
import Badge from "../components/Badge";
import {
  Database,
  CheckCircle2,
  XCircle,
  Loader2,
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
    </>
  );
}