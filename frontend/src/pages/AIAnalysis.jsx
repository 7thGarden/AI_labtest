import { useEffect, useState, useRef } from "react";
import api from "../api/api";
import Card from "../components/Card";
import Badge from "../components/Badge";
import { extractReport, stripAnsi } from "../utils/opensre";
import {
  BrainCircuit,
  Loader2,
  Send,
  ChevronDown,
  AlertTriangle,
  CheckCircle2,
  Sparkles,
  Search,
} from "lucide-react";

function Meta({ label, children }) {
  return (
    <div className="report-metric">
      <div className="report-metric__label">{label}</div>
      <div className="report-metric__value">{children}</div>
    </div>
  );
}

export default function AIAnalysis() {
  const [version, setVersion] = useState("");

  const [clusters, setClusters] = useState([]);
  const [cluster, setCluster] = useState("");

  const [pods, setPods] = useState([]);
  const [namespace, setNamespace] = useState("");
  const [podName, setPodName] = useState("");

  const [investigation, setInvestigation] = useState(null);
  const [loading, setLoading] = useState(false);

  const [message, setMessage] = useState("");
  const [chat, setChat] = useState([]);
  const [chatLoading, setChatLoading] = useState(false);

  const [podsLoading, setPodsLoading] = useState(false);

  const chatEndRef = useRef(null);

  useEffect(() => {
    async function loadInitialData() {
      try {
        const versionRes = await api.get("/opensre/version");
        setVersion(stripAnsi(versionRes.data.stdout || ""));

        const clusterRes = await api.get("/kubernetes/clusters");
        const clusterLines = (clusterRes.data.stdout || "")
          .split("\n")
          .map((line) => line.trim())
          .filter(Boolean);

        setClusters(clusterLines);
        if (clusterLines.length > 0) {
          setCluster(clusterLines[0]);
        }
      } catch {
        setVersion("");
      }
    }

    loadInitialData();
  }, []);

  useEffect(() => {
    if (!cluster) {
      setPods([]);
      setNamespace("");
      setPodName("");
      return;
    }

    async function loadPods() {
      setPodsLoading(true);

      try {
        const response = await api.get("/kubernetes/pods", {
          params: { context: cluster },
        });

        const podLines = (response.data.stdout || "")
          .split("\n")
          .slice(1)
          .filter(Boolean);

        const podData = podLines.map((line) => {
          const cols = line.trim().split(/\s+/);
          return {
            namespace: cols[0],
            name: cols[1],
            ready: cols[2],
            status: cols[3],
          };
        });

        setPods(podData);
        setNamespace(podData[0]?.namespace || "");
        setPodName(podData[0]?.name || "");
        setInvestigation(null);
      } catch (err) {
        console.error("Failed to load pods:", err);
        setPods([]);
        setNamespace("");
        setPodName("");
      } finally {
        setPodsLoading(false);
      }
    }

    loadPods();
  }, [cluster]);

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [chat, chatLoading]);

  async function investigatePod() {
    if (!namespace || !podName) return;

    setLoading(true);
    setInvestigation(null);

    try {
      const response = await api.get(
        `/opensre/investigate/pod/${namespace}/${podName}`,
        { params: { context: cluster } }
      );

      const data = response.data;

      if (!data.success) {
        setInvestigation({
          error: data.stderr || "OpenSRE investigation failed.",
        });
      } else {
        const stdout = stripAnsi(data.stdout || "");
        setInvestigation({ stdout, report: extractReport(stdout) });
      }
    } catch (err) {
      console.error(err);
      setInvestigation({ error: err.message });
    } finally {
      setLoading(false);
    }
  }

  async function sendMessage() {
    const text = message.trim();
    if (!text || chatLoading) return;

    setChat((previous) => [...previous, { role: "user", content: text }]);
    setMessage("");
    setChatLoading(true);

    try {
      const response = await api.post("/opensre/chat", {
        message: text,
        cluster,
        namespace,
        pod: podName,
      });

      const data = response.data;
      const output = [
        data.stdout || "",
        data.stderr ? `\n\n--- STDERR ---\n${data.stderr}` : "",
      ].join("");

      setChat((previous) => [
        ...previous,
        {
          role: "opensre",
          content: output || "OpenSRE returned no output.",
        },
      ]);
    } catch (err) {
      console.error(err);
      setChat((previous) => [
        ...previous,
        { role: "opensre", content: `OpenSRE request failed.\n\n${err.message}` },
      ]);
    } finally {
      setChatLoading(false);
    }
  }

  function handleKeyDown(event) {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      sendMessage();
    }
  }

  const namespaces = [...new Set(pods.map((pod) => pod.namespace))];
  const selectedNamespacePods = pods.filter((pod) => pod.namespace === namespace);
  const report = investigation?.report;

  return (
    <>
      <div className="page-head">
        <div>
          <h1>AI Analysis</h1>
          <p className="page-head__sub">
            Run live root-cause investigations and chat with OpenSRE.
          </p>
        </div>

        <div className="page-head__actions">
          {version && (
            <Badge tone="primary">
              <Sparkles size={12} /> OpenSRE · {version}
            </Badge>
          )}
        </div>
      </div>

      <Card
        title="Run investigation"
        subtitle="Select a workload to launch a live root-cause analysis"
        actions={
          <button
            type="button"
            className="btn btn--primary"
            onClick={investigatePod}
            disabled={loading || podsLoading || !namespace || !podName}
          >
            {loading ? (
              <>
                <Loader2 size={15} className="btn__spinner" /> Investigating…
              </>
            ) : (
              <>
                <Search size={15} /> Run investigation
              </>
            )}
          </button>
        }
      >
        <div className="form-grid">
          <div className="field">
            <label htmlFor="ai-cluster">Cluster</label>
            <select
              id="ai-cluster"
              className="select"
              value={cluster}
              onChange={(e) => setCluster(e.target.value)}
              disabled={clusters.length === 0}
            >
              {clusters.length === 0 && <option value="">No contexts</option>}
              {clusters.map((item) => (
                <option key={item} value={item}>
                  {item}
                </option>
              ))}
            </select>
          </div>

          <div className="field">
            <label htmlFor="ai-namespace">Namespace</label>
            <select
              id="ai-namespace"
              className="select"
              value={namespace}
              onChange={(e) => {
                const newNamespace = e.target.value;
                setNamespace(newNamespace);
                setPodName(
                  pods.find((pod) => pod.namespace === newNamespace)?.name || ""
                );
              }}
              disabled={podsLoading || namespaces.length === 0}
            >
              {namespaces.length === 0 && <option value="">Loading…</option>}
              {namespaces.map((ns) => (
                <option key={ns} value={ns}>
                  {ns}
                </option>
              ))}
            </select>
          </div>

          <div className="field">
            <label htmlFor="ai-pod">Pod</label>
            <select
              id="ai-pod"
              className="select"
              value={podName}
              onChange={(e) => setPodName(e.target.value)}
              disabled={podsLoading || selectedNamespacePods.length === 0}
            >
              {selectedNamespacePods.length === 0 && (
                <option value="">Loading…</option>
              )}
              {selectedNamespacePods.map((pod) => (
                <option key={pod.name} value={pod.name}>
                  {pod.name}
                </option>
              ))}
            </select>
          </div>
        </div>

        {podsLoading && (
          <p className="text-muted" style={{ marginTop: "var(--space-3)", fontSize: 13 }}>
            <Loader2 size={13} className="btn__spinner" /> Loading pods from
            selected cluster…
          </p>
        )}
      </Card>

      {investigation && (
        <Card
          title="Investigation report"
          subtitle={`Target · ${namespace}/${podName}`}
          actions={
            <Badge tone={report ? "success" : "warning"}>
              {report ? (
                <>
                  <CheckCircle2 size={12} /> Analyzed
                </>
              ) : (
                <>
                  <AlertTriangle size={12} /> Inconclusive
                </>
              )}
            </Badge>
          }
        >
          {investigation.error ? (
            <div className="empty-state">
              <AlertTriangle size={26} />
              <div>
                <strong>Investigation failed</strong>
                <p style={{ marginTop: "var(--space-1)" }}>
                  {investigation.error}
                </p>
              </div>
            </div>
          ) : (
            <>
              {report && (
                <>
                  <div className="report-grid">
                    <Meta label="Root cause">
                      {report.root_cause || "Not determined"}
                    </Meta>
                    <Meta label="Validity score">
                      {report.validity_score != null
                        ? `${Math.round(report.validity_score * 100)}%`
                        : "—"}
                    </Meta>
                    <Meta label="Classification">
                      {report.is_noise ? "Noise / low signal" : "Incident"}
                    </Meta>
                  </div>

                  {report.problem_md && (
                    <div className="report-section">
                      <div className="report-section__title">
                        Problem framing
                      </div>
                      <div className="report-section__body">
                        {stripAnsi(report.problem_md)}
                      </div>
                    </div>
                  )}

                  {report.report && (
                    <div className="report-section">
                      <div className="report-section__title">Findings</div>
                      <div className="report-section__body">
                        {stripAnsi(report.report)}
                      </div>
                    </div>
                  )}
                </>
              )}

              {investigation.stdout && (
                <details className="raw-output">
                  <summary>
                    <ChevronDown size={14} style={{ verticalAlign: "middle" }} />
                    Raw CLI output
                  </summary>
                  <pre className="code-block">{investigation.stdout}</pre>
                </details>
              )}
            </>
          )}
        </Card>
      )}

      <Card
        title="Assistant"
        subtitle="Ask OpenSRE questions about the selected workload"
      >
        {cluster && (
          <div className="chat__context">
            <span className="chat__context-chip">
              Cluster <span>{cluster || "—"}</span>
            </span>
            <span className="chat__context-chip">
              Namespace <span>{namespace || "—"}</span>
            </span>
            <span className="chat__context-chip">
              Pod <span>{podName || "—"}</span>
            </span>
          </div>
        )}

        <div className="chat__window">
          {chat.length === 0 ? (
            <div className="empty-state" style={{ margin: "auto" }}>
              <BrainCircuit size={30} />
              <div>
                <strong>OpenSRE is ready.</strong>
                <p style={{ marginTop: "var(--space-1)", maxWidth: 420 }}>
                  Ask about the selected pod or this environment — it will
                  collect live evidence before responding.
                </p>
              </div>
            </div>
          ) : (
            chat.map((item, index) => (
              <div
                key={index}
                className={`chat__msg chat__msg--${item.role === "user" ? "user" : "opensre"}`}
              >
                <div className="chat__bubble">{item.content}</div>
                <div className="chat__meta">
                  {item.role === "user" ? "You" : "OpenSRE"}
                </div>
              </div>
            ))
          )}

          {chatLoading && (
            <div className="chat__msg chat__msg--opensre">
              <div className="chat__thinking">
                <span className="chat__typing">
                  <span />
                  <span />
                  <span />
                </span>
                Investigating…
              </div>
            </div>
          )}

          <div ref={chatEndRef} />
        </div>

        <div className="chat__footer">
          <textarea
            className="textarea"
            value={message}
            onChange={(e) => setMessage(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Ask OpenSRE about this pod…"
            rows={2}
            disabled={chatLoading}
            style={{ flex: 1 }}
          />

          <button
            type="button"
            className="btn btn--primary"
            onClick={sendMessage}
            disabled={chatLoading || !message.trim()}
            aria-label="Send message"
          >
            {chatLoading ? (
              <Loader2 size={16} className="btn__spinner" />
            ) : (
              <Send size={16} />
            )}
          </button>
        </div>
      </Card>
    </>
  );
}