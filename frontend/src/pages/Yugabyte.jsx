import { useEffect, useState } from "react";
import api from "../api/api";
import Card from "../components/Card";
import Badge from "../components/Badge";
import {
  HardDrive,
  CheckCircle2,
  XCircle,
  Loader2,
  Terminal,
  Play,
  Table,
  List,
  Plus,
} from "lucide-react";

const DEFAULT_TABLE = "test_table";

export default function Yugabyte() {
  const [status, setStatus] = useState(null);
  const [checking, setChecking] = useState(true);
  const [query, setQuery] = useState("SELECT version();");
  const [queryResult, setQueryResult] = useState(null);
  const [queryError, setQueryError] = useState(null);
  const [queryLoading, setQueryLoading] = useState(false);
  const [tableName, setTableName] = useState(DEFAULT_TABLE);
  const [tableData, setTableData] = useState([]);
  const [tableLoading, setTableLoading] = useState(false);
  const [tableError, setTableError] = useState(null);
  const [insertData, setInsertData] = useState({ id: "", name: "" });
  const [insertResult, setInsertResult] = useState(null);
  const [insertError, setInsertError] = useState(null);
  const [insertLoading, setInsertLoading] = useState(false);

  useEffect(() => {
    async function load() {
      setChecking(true);
      try {
        const res = await api.get("/yugabyte/health");
        setStatus(res.data.success ? "connected" : "unreachable");
      } catch {
        setStatus("backend-offline");
      } finally {
        setChecking(false);
      }
    }
    load();
  }, []);

  const handleQuery = async () => {
    setQueryLoading(true);
    setQueryError(null);
    setQueryResult(null);
    try {
      const res = await api.post("/yugabyte/query", { sql: query });
      if (res.data.success) {
        setQueryResult(res.data.data);
      } else {
        setQueryError(res.data.error);
      }
    } catch (e) {
      setQueryError(e.message);
    } finally {
      setQueryLoading(false);
    }
  };

  const loadTable = async () => {
    setTableLoading(true);
    setTableError(null);
    setTableData([]);
    try {
      const res = await api.post("/yugabyte/query", {
        sql: `SELECT * FROM ${tableName} LIMIT 50;`,
      });
      if (res.data.success) {
        setTableData(res.data.data || []);
      } else {
        setTableError(res.data.error);
      }
    } catch (e) {
      setTableError(e.message);
    } finally {
      setTableLoading(false);
    }
  };

  const handleInsert = async () => {
    if (!insertData.id || !insertData.name) return;
    setInsertLoading(true);
    setInsertError(null);
    setInsertResult(null);
    try {
      const res = await api.post("/yugabyte/insert", {
        table: tableName,
        data: { id: parseInt(insertData.id), name: insertData.name },
      });
      if (res.data.success) {
        setInsertResult(res.data.data);
        setInsertData({ id: "", name: "" });
        loadTable();
      } else {
        setInsertError(res.data.error);
      }
    } catch (e) {
      setInsertError(e.message);
    } finally {
      setInsertLoading(false);
    }
  };

  const createTable = async () => {
    setQueryLoading(true);
    setQueryError(null);
    try {
      const res = await api.post("/yugabyte/execute", {
        sql: `CREATE TABLE IF NOT EXISTS ${tableName} (id INT PRIMARY KEY, name TEXT);`,
      });
      if (res.data.success) {
        setQueryResult("Table created/verified");
        loadTable();
      } else {
        setQueryError(res.data.error);
      }
    } catch (e) {
      setQueryError(e.message);
    } finally {
      setQueryLoading(false);
    }
  };

  useEffect(() => {
    if (status === "connected") loadTable();
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

  const formatResult = (data) => {
    if (!data) return "No data";
    if (Array.isArray(data)) {
      if (data.length === 0) return "Empty result";
      return JSON.stringify(data, null, 2);
    }
    return JSON.stringify(data, null, 2);
  };

  const renderTable = (data) => {
    if (!data || !Array.isArray(data) || data.length === 0) return null;
    const columns = Object.keys(data[0]);
    return (
      <div style={{ overflowX: "auto" }}>
        <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 12 }}>
          <thead>
            <tr style={{ borderBottom: "1px solid var(--border)" }}>
              {columns.map((col) => (
                <th key={col} style={{ textAlign: "left", padding: "var(--space-2)" }}>
                  {col}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {data.slice(0, 50).map((row, i) => (
              <tr key={i} style={{ borderBottom: "1px solid var(--border)" }}>
                {columns.map((col) => (
                  <td key={col} style={{ padding: "var(--space-2)", fontFamily: "monospace" }}>
                    {row[col] ?? "NULL"}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    );
  };

  return (
    <>
      <div className="page-head">
        <div>
          <h1>YugabyteDB (YSQL)</h1>
          <p className="page-head__sub">
            Distributed PostgreSQL-compatible database · SQL operations
          </p>
        </div>
      </div>

      <div className="grid-2">
        <Card
          title="Connection"
          subtitle="YSQL API · PostgreSQL wire protocol"
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
              <HardDrive size={17} strokeWidth={1.8} />
            </div>
            <div>
              <div className="text-muted" style={{ fontSize: 13 }}>
                YugabyteDB server: localhost:5433
              </div>
            </div>
          </div>
        </Card>

        <Card title="Quick Actions" subtitle="Common database operations">
          <div style={{ display: "flex", gap: "var(--space-2)", flexWrap: "wrap", marginBottom: "var(--space-4)" }}>
            <button onClick={createTable} className="btn btn--primary btn--sm" disabled={queryLoading}>
              <Table size={14} /> Create Table
            </button>
            <button onClick={loadTable} className="btn btn--ghost btn--sm" disabled={tableLoading}>
              <List size={14} /> Refresh Table
            </button>
          </div>
        </Card>
      </div>

      <div className="grid-2">
        <Card title="SQL Query" subtitle="Execute arbitrary SQL">
          <div style={{ display: "flex", gap: "var(--space-2)", marginBottom: "var(--space-3)" }}>
            <textarea
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              rows={4}
              style={{ flex: 1, fontFamily: "monospace", fontSize: 13 }}
              placeholder="SELECT * FROM test_table;"
            />
            <button onClick={handleQuery} className="btn btn--primary" disabled={queryLoading} style={{ alignSelf: "flex-end" }}>
              <Play size={14} /> Run
            </button>
          </div>

          {queryError && (
            <div className="alert alert--danger" style={{ marginBottom: "var(--space-3)" }}>
              {queryError}
            </div>
          )}
          {queryResult !== null && (
            <div style={{ background: "var(--bg-tertiary)", borderRadius: "var(--radius-sm)", padding: "var(--space-3)", fontFamily: "monospace", fontSize: 12, whiteSpace: "pre-wrap", maxHeight: 300, overflow: "auto" }}>
              {formatResult(queryResult)}
            </div>
          )}
        </Card>

        <Card title={`Table: ${tableName}`} subtitle="Data browser & insert">
          <div style={{ marginBottom: "var(--space-3)" }}>
            <input
              type="text"
              value={tableName}
              onChange={(e) => setTableName(e.target.value)}
              placeholder="Table name"
              style={{ width: "100%", maxWidth: 200, marginBottom: "var(--space-2)" }}
            />
            <div style={{ display: "flex", gap: "var(--space-2)", flexWrap: "wrap" }}>
              <input
                type="text"
                placeholder="ID (int)"
                value={insertData.id}
                onChange={(e) => setInsertData({ ...insertData, id: e.target.value })}
                style={{ width: 80 }}
              />
              <input
                type="text"
                placeholder="Name"
                value={insertData.name}
                onChange={(e) => setInsertData({ ...insertData, name: e.target.value })}
                style={{ flex: 1, minWidth: 120 }}
              />
              <button onClick={handleInsert} className="btn btn--primary btn--sm" disabled={insertLoading}>
                <Plus size={14} /> Insert
              </button>
            </div>
          </div>

          {insertError && (
            <div className="alert alert--danger" style={{ marginBottom: "var(--space-3)" }}>
              {insertError}
            </div>
          )}
          {insertResult && (
            <div className="alert alert--success" style={{ marginBottom: "var(--space-3)" }}>
              Inserted: {JSON.stringify(insertResult)}
            </div>
          )}

          {tableError && (
            <div className="alert alert--danger" style={{ marginBottom: "var(--space-3)" }}>
              {tableError}
            </div>
          )}

          {tableLoading ? (
            <div style={{ textAlign: "center", padding: "var(--space-4)" }}>
              <Loader2 size={16} className="btn__spinner" /> Loading…
            </div>
          ) : (
            renderTable(tableData)
          )}
        </Card>
      </div>
    </>
  );
}