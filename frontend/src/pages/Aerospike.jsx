import { useEffect, useState } from "react";
import api from "../api/api";
import Card from "../components/Card";
import Badge from "../components/Badge";
import {
  Database,
  CheckCircle2,
  XCircle,
  Loader2,
  Plus,
  Search,
  Trash2,
  List,
} from "lucide-react";

const NAMESPACE = "test";
const SET_NAME = "demo";

export default function Aerospike() {
  const [status, setStatus] = useState(null);
  const [checking, setChecking] = useState(true);
  const [records, setRecords] = useState([]);
  const [loadingRecords, setLoadingRecords] = useState(false);
  const [newRecord, setNewRecord] = useState({ key: "", bins: { name: "", value: "" } });
  const [error, setError] = useState(null);
  const [success, setSuccess] = useState(null);

  useEffect(() => {
    async function load() {
      setChecking(true);
      try {
        const res = await api.get("/aerospike/health");
        setStatus(res.data.success ? "connected" : "unreachable");
      } catch {
        setStatus("backend-offline");
      } finally {
        setChecking(false);
      }
    }
    load();
  }, []);

  const loadRecords = async () => {
    setLoadingRecords(true);
    try {
      const res = await api.post("/aerospike/scan", { namespace: NAMESPACE, set: SET_NAME });
      if (res.data.success) {
        setRecords(res.data.data || []);
      } else {
        setError(res.data.error);
      }
    } catch (e) {
      setError(e.message);
    } finally {
      setLoadingRecords(false);
    }
  };

  const handleWrite = async () => {
    if (!newRecord.key || !newRecord.bins.name) return;
    try {
      const res = await api.post("/aerospike/write", {
        namespace: NAMESPACE,
        set: SET_NAME,
        key: newRecord.key,
        bins: { name: newRecord.bins.name, value: newRecord.bins.value || 0 },
      });
      if (res.data.success) {
        setSuccess("Record written");
        setNewRecord({ key: "", bins: { name: "", value: "" } });
        loadRecords();
      } else {
        setError(res.data.error);
      }
    } catch (e) {
      setError(e.message);
    }
  };

  const handleDelete = async (key) => {
    if (!confirm(`Delete record ${key}?`)) return;
    try {
      const res = await api.post("/aerospike/delete", {
        namespace: NAMESPACE,
        set: SET_NAME,
        key,
      });
      if (res.data.success) {
        setSuccess("Record deleted");
        loadRecords();
      } else {
        setError(res.data.error);
      }
    } catch (e) {
      setError(e.message);
    }
  };

  useEffect(() => {
    if (status === "connected") loadRecords();
  }, [status]);

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
          <h1>Aerospike</h1>
          <p className="page-head__sub">
            High-performance NoSQL database · key-value operations
          </p>
        </div>
      </div>

      <div className="grid-2">
        <Card
          title="Connection"
          subtitle={`Namespace: ${NAMESPACE} · Set: ${SET_NAME}`}
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
                Aerospike server: localhost:3000
              </div>
            </div>
          </div>
        </Card>

        <Card title="Operations" subtitle="Read, write, and delete records">
          <div style={{ display: "flex", gap: "var(--space-3)", marginBottom: "var(--space-4)" }}>
            <input
              type="text"
              placeholder="Key"
              value={newRecord.key}
              onChange={(e) => setNewRecord({ ...newRecord, key: e.target.value })}
              style={{ flex: 1, maxWidth: 180 }}
            />
            <input
              type="text"
              placeholder="Name"
              value={newRecord.bins.name}
              onChange={(e) => setNewRecord({ ...newRecord, bins: { ...newRecord.bins, name: e.target.value } })}
              style={{ flex: 1, maxWidth: 180 }}
            />
            <input
              type="text"
              placeholder="Value"
              value={newRecord.bins.value}
              onChange={(e) => setNewRecord({ ...newRecord, bins: { ...newRecord.bins, value: e.target.value } })}
              style={{ flex: 1, maxWidth: 180 }}
            />
            <button onClick={handleWrite} className="btn btn--primary btn--sm">
              <Plus size={14} /> Write
            </button>
            <button onClick={loadRecords} className="btn btn--ghost btn--sm" disabled={loadingRecords}>
              <List size={14} /> Scan
            </button>
          </div>

          {error && (
            <div className="alert alert--danger" style={{ marginBottom: "var(--space-3)" }}>
              {error}
            </div>
          )}
          {success && (
            <div className="alert alert--success" style={{ marginBottom: "var(--space-3)" }}>
              {success}
            </div>
          )}

          <div style={{ overflowX: "auto" }}>
            <table style={{ width: "100%", borderCollapse: "collapse" }}>
              <thead>
                <tr style={{ borderBottom: "1px solid var(--border)" }}>
                  <th style={{ textAlign: "left", padding: "var(--space-2)" }}>Key</th>
                  <th style={{ textAlign: "left", padding: "var(--space-2)" }}>Bins</th>
                  <th style={{ textAlign: "left", padding: "var(--space-2)", width: 80 }}></th>
                </tr>
              </thead>
              <tbody>
                {loadingRecords ? (
                  <tr>
                    <td colSpan={3} style={{ padding: "var(--space-4)", textAlign: "center" }}>
                      <Loader2 size={16} className="btn__spinner" /> Loading…
                    </td>
                  </tr>
                ) : records.length === 0 ? (
                  <tr>
                    <td colSpan={3} style={{ padding: "var(--space-4)", textAlign: "center", color: "var(--muted)" }}>
                      No records found. Click "Scan" or write a new record.
                    </td>
                  </tr>
                ) : (
                  records.map((r) => (
                    <tr key={r.key} style={{ borderBottom: "1px solid var(--border)" }}>
                      <td style={{ padding: "var(--space-2)", fontFamily: "monospace", fontSize: 13 }}>
                        {r.key}
                      </td>
                      <td style={{ padding: "var(--space-2)", fontSize: 13 }}>
                        {JSON.stringify(r.bins)}
                      </td>
                      <td style={{ padding: "var(--space-2)" }}>
                        <button
                          onClick={() => handleDelete(r.key)}
                          className="btn btn--ghost btn--sm"
                          style={{ padding: "var(--space-1) var(--space-2)" }}
                        >
                          <Trash2 size={14} />
                        </button>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </Card>
      </div>
    </>
  );
}