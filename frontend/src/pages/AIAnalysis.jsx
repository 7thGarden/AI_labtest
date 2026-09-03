import { useEffect, useState, useRef } from "react";
import { Link } from "react-router-dom";
import api from "../api/api";
import Card from "../components/Card";
import Badge from "../components/Badge";
import ProblemFraming from "../components/ProblemFraming";
import ReportFindings from "../components/ReportFindings";
import { extractReport, extractRecommendedActions, stripAnsi } from "../utils/opensre";
import useSessionState from "../hooks/useSessionState";
import {
  BrainCircuit,
  Loader2,
  Send,
  ChevronDown,
  AlertTriangle,
  CheckCircle2,
  Sparkles,
  Search,
  Target,
  Gauge,
  ListChecks,
  FileText,
  Database,
  HardDrive,
  Layers,
  GitCommit,
  ExternalLink,
} from "lucide-react";

export default function AIAnalysis() {
  const [version, setVersion] = useState("");

  const [clusters, setClusters] = useSessionState("opensre:clusters", []);
  const [cluster, setCluster] = useSessionState("opensre:cluster", "");

  const [pods, setPods] = useSessionState("opensre:pods", []);
  const [namespace, setNamespace] = useSessionState("opensre:namespace", "");
  const [podName, setPodName] = useSessionState("opensre:pod", "");

  const [targetType, setTargetType] = useSessionState("opensre:targetType", "pod");
  const [dbHealth, setDbHealth] = useState(null);

  const [investigation, setInvestigation] = useSessionState(
    "opensre:investigation",
    null
  );
  const [investigationTarget, setInvestigationTarget] = useSessionState(
    "opensre:investigationTarget",
    ""
  );
  const [gitCorrelation, setGitCorrelation] = useState(null);
  const [loading, setLoading] = useState(false);

  const [message, setMessage] = useState("");
  const [chat, setChat] = useSessionState("opensre:chat", []);
  const [chatLoading, setChatLoading] = useState(false);

  const [podsLoading, setPodsLoading] = useState(false);

  const chatEndRef = useRef(null);
  const initialDataRef = useRef({ clusters: clusters.length, pods: pods.length });
  const skipPodLoadRef = useRef(pods.length > 0);

  useEffect(() => {
    async function loadInitialData() {
      try {
        const versionRes = await api.get("/opensre/version");
        setVersion(stripAnsi(versionRes.data.stdout || ""));

        if (initialDataRef.current.clusters > 0) return;

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
  }, [setCluster, setClusters]);

  useEffect(() => {
    if (!cluster) {
      setPods([]);
      setNamespace("");
      setPodName("");
      return;
    }

    if (skipPodLoadRef.current) {
      skipPodLoadRef.current = false;
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
  }, [cluster, setInvestigation, setNamespace, setPodName, setPods]);

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [chat, chatLoading]);

  useEffect(() => {
    if (targetType === "pod") {
      setDbHealth(null);
      return;
    }

    let cancelled = false;
    setDbHealth(null);

    if (targetType === "stack") {
      Promise.all([
        api.get("/metrics/health"),
        api.get("/metrics/grafana/health"),
      ])
        .then(([vmRes, grafanaRes]) => {
          if (cancelled) return;

          const vmOk = !!vmRes.data?.success;
          const grafanaOk = !!grafanaRes.data?.success;

          setDbHealth({
            success: vmOk && grafanaOk,
            label: `${vmOk ? "VM up" : "VM down"} · ${grafanaOk ? "Grafana up" : "Grafana down"}`,
          });
        })
        .catch(() => {
          if (!cancelled) setDbHealth(null);
        });

      return () => {
        cancelled = true;
      };
    }

    api
      .get(`/${targetType}/health`)
      .then((res) => {
        if (!cancelled) setDbHealth(res.data);
      })
      .catch(() => {
        if (!cancelled) setDbHealth(null);
      });

    return () => {
      cancelled = true;
    };
  }, [targetType]);

  async function investigatePod() {
    if (targetType === "pod" && (!namespace || !podName)) return;

    setLoading(true);
    setInvestigation(null);

    try {
      let response;

      if (targetType === "pod") {
        response = await api.get(
          `/opensre/investigate/pod/${namespace}/${podName}`,
          { params: { context: cluster } }
        );
      } else if (targetType === "stack") {
        response = await api.get("/opensre/investigate/stack", {
          params: { context: cluster },
        });
      } else {
        response = await api.get(
          `/opensre/investigate/target/${targetType}`
        );
      }

      const data = response.data;

      if (!data.success) {
        setInvestigation({
          error: data.stderr || "OpenSRE investigation failed.",
        });
        setGitCorrelation(null);
      } else {
        const stdout = stripAnsi(data.stdout || "");
        setInvestigation({ stdout, report: extractReport(stdout) });

        try {
          const corrRes = await api.get("/investigation/git-correlation", {
            params: { limit: 10 },
          });
          setGitCorrelation(corrRes.data.success ? corrRes.data : null);
        } catch {
          setGitCorrelation(null);
        }
      }

      setInvestigationTarget(
        targetType === "pod"
          ? `${namespace}/${podName}`
          : targetType === "stack"
            ? "Full stack (all components)"
            : targetType
      );
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
      const payload = { message: text };

      if (targetType === "pod") {
        payload.cluster = cluster;
        payload.namespace = namespace;
        payload.pod = podName;
      } else {
        if (targetType === "stack") {
          payload.cluster = cluster;
        }
        payload.target_type = targetType;
      }

      const response = await api.post("/opensre/chat", payload);

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

  const validityScore =
    report?.validity_score != null ? Math.round(report.validity_score * 100) : null;

  const scoreTone =
    validityScore == null
      ? "neutral"
      : validityScore >= 75
        ? "success"
        : validityScore >= 40
          ? "warning"
          : "danger";

  const recommendedActions = extractRecommendedActions(report);

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
            disabled={
              loading ||
              podsLoading ||
              (targetType === "pod" && (!namespace || !podName))
            }
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
            <label htmlFor="ai-target">Target</label>
            <select
              id="ai-target"
              className="select"
              value={targetType}
              onChange={(e) => setTargetType(e.target.value)}
            >
              <option value="pod">Kubernetes pod</option>
              <option value="aerospike">Aerospike</option>
              <option value="yugabyte">YugabyteDB</option>
              <option value="stack">Full stack</option>
            </select>
          </div>

          {targetType === "pod" ? (
            <>
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
            </>
          ) : (
            <div className="field">
              <label>Service</label>
              <div className="target-readout">
                <span className="target-readout__icon">
                  {targetType === "stack" ? (
                    <Layers size={16} />
                  ) : targetType === "aerospike" ? (
                    <Database size={16} />
                  ) : (
                    <HardDrive size={16} />
                  )}
                </span>
                <div className="target-readout__body">
                  <div className="target-readout__name">
                    {targetType === "stack"
                      ? "Observability stack"
                      : targetType === "aerospike"
                        ? "Aerospike"
                        : "YugabyteDB"}
                  </div>
                  <div className="target-readout__meta">
                    {targetType === "stack"
                      ? "K8s · VictoriaMetrics · OTel · Grafana"
                      : targetType === "aerospike"
                        ? "Host container · 127.0.0.1:3001"
                        : "Host container · 127.0.0.1:5433"}
                  </div>
                </div>
                {dbHealth && (
                  <Badge tone={dbHealth.success ? "success" : "danger"}>
                    {dbHealth.label ?? (dbHealth.success ? "Up" : "Down")}
                  </Badge>
                )}
              </div>
            </div>
          )}
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
          subtitle={`Target · ${investigationTarget}`}
          actions={
            <>
              <Link to="/incident" className="btn btn--ghost btn--sm">
                <FileText size={13} /> Open incident report
              </Link>
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
            </>
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
                  <div className="report-cards">
                    <div className="report-card report-card--root">
                      <div className="report-card__icon">
                        <Target size={18} />
                      </div>
                      <div>
                        <div className="report-card__label">Root cause</div>
                        <div className="report-card__value">
                          {report.root_cause || "Not determined"}
                        </div>
                        <div className="report-card__meta">
                          <Badge
                            tone={report.is_noise ? "warning" : "info"}
                          >
                            {report.is_noise
                              ? "Noise / low signal"
                              : "Incident"}
                          </Badge>
                        </div>
                      </div>
                    </div>

                    <div className="report-card report-card--score">
                      <div className="report-card__icon">
                        <Gauge size={18} />
                      </div>
                      <div>
                        <div className="report-card__label">
                          Validity score
                        </div>
                        <div className="report-card__value">
                          {validityScore != null ? `${validityScore}%` : "—"}
                        </div>
                        <div className="score-bar">
                          <div
                            className={`score-bar__track score-bar__track--${scoreTone}`}
                          >
                            <div
                              className="score-bar__fill"
                              style={{
                                width: `${validityScore ?? 0}%`,
                              }}
                            />
                          </div>
                        </div>
                      </div>
                    </div>

                    <div className="report-card report-card--actions">
                      <div className="report-card__icon">
                        <ListChecks size={18} />
                      </div>
                      <div>
                        <div className="report-card__label">
                          Recommended actions
                        </div>
                        {recommendedActions.length > 0 ? (
                          <ul className="action-list">
                            {recommendedActions.map((action, index) => (
                              <li key={index}>{action}</li>
                            ))}
                          </ul>
                        ) : (
                          <div className="report-card__value">—</div>
                        )}
                      </div>
                    </div>
                  </div>

                  {gitCorrelation?.suspected_commit && (
                    <div style={{
                      padding: "var(--space-3)",
                      border: "2px solid var(--primary)",
                      borderRadius: 6,
                      background: "var(--bg-muted)",
                      marginTop: "var(--space-3)",
                    }}>
                      <div style={{ fontSize: 12, color: "var(--muted)", marginBottom: "var(--space-1)", display: "flex", alignItems: "center", gap: "var(--space-1)" }}>
                        <GitCommit size={13} /> Suspected change-point commit
                      </div>
                      <div style={{ display: "flex", alignItems: "center", gap: "var(--space-2)", flexWrap: "wrap" }}>
                        <code style={{ fontSize: 13, fontWeight: 600 }}>
                          {gitCorrelation.suspected_commit.sha?.substring(0, 7)}
                        </code>
                        <span style={{ fontSize: 13 }}>
                          {gitCorrelation.suspected_commit.message}
                        </span>
                      </div>
                      <div style={{ fontSize: 12, color: "var(--muted)", marginTop: "var(--space-1)", display: "flex", gap: "var(--space-3)" }}>
                        <span>by {gitCorrelation.suspected_commit.author || "—"}</span>
                        <span>{gitCorrelation.suspected_commit.date ? new Date(gitCorrelation.suspected_commit.date).toLocaleString() : "—"}</span>
                      </div>
                      <div style={{ marginTop: "var(--space-2)" }}>
                        <a
                          href={`https://github.com/${gitCorrelation.repo || ""}/commit/${gitCorrelation.suspected_commit.sha}`}
                          target="_blank"
                          rel="noreferrer"
                          className="btn btn--ghost btn--sm"
                        >
                          <ExternalLink size={12} /> View on GitHub
                        </a>
                      </div>
                    </div>
                  )}

                  {gitCorrelation?.no_commit_found && (
                    <div style={{
                      padding: "var(--space-3)",
                      border: "1px solid var(--border)",
                      borderRadius: 6,
                      background: "var(--bg-muted)",
                      marginTop: "var(--space-3)",
                      fontSize: 13,
                      color: "var(--muted)",
                    }}>
                      No commit found at-or-before the incident start on branch <code>{gitCorrelation.branch || "default"}</code>.
                      Attribution is inconclusive — the incident may pre-date deploy history.
                    </div>
                  )}

                  {report.problem_md && (
                    <ProblemFraming
                      markdown={report.problem_md}
                      cluster={cluster}
                    />
                  )}

                  {report.report && (
                    <ReportFindings markdown={report.report} />
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
        {targetType === "pod" && cluster && (
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

        {targetType !== "pod" && (
          <div className="chat__context">
            <span className="chat__context-chip">
              Target <span>{targetType}</span>
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