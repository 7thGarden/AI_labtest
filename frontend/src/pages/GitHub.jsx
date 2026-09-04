import { useEffect, useState } from "react";
import api from "../api/api";
import Card from "../components/Card";
import Badge from "../components/Badge";
import {
  GitBranch,
  CheckCircle2,
  XCircle,
  Loader2,
  AlertCircle,
  GitCommit,
  GitMerge,
  Clock,
  User,
  ExternalLink,
  Search,
} from "lucide-react";

const TAB_CONFIG = [
  { id: "commits", label: "Commits", icon: GitCommit },
  { id: "workflows", label: "Workflows", icon: GitMerge },
  { id: "issues", label: "Issues", icon: AlertCircle },
  { id: "correlation", label: "Incident Correlation", icon: Search },
];

export default function GitHub() {
  const [status, setStatus] = useState(null);
  const [checking, setChecking] = useState(true);
  const [repoInfo, setRepoInfo] = useState(null);
  const [branches, setBranches] = useState([]);
  const [selectedBranch, setSelectedBranch] = useState("");
  const [activeTab, setActiveTab] = useState("commits");
  const [commits, setCommits] = useState([]);
  const [workflows, setWorkflows] = useState([]);
  const [issues, setIssues] = useState([]);
  const [loading, setLoading] = useState({ commits: false, workflows: false, issues: false });
  const [error, setError] = useState(null);
  const [since, setSince] = useState("");
  const [until, setUntil] = useState("");
  const [issueState, setIssueState] = useState("open");
  const [incidentStart, setIncidentStart] = useState("");
  const [correlationResult, setCorrelationResult] = useState(null);
  const [correlationLoading, setCorrelationLoading] = useState(false);
  const [correlationError, setCorrelationError] = useState(null);
  const [workflowInvestigation, setWorkflowInvestigation] = useState(null);
  const [workflowInvestigating, setWorkflowInvestigating] = useState(false);
  const [workflowInvestError, setWorkflowInvestError] = useState(null);

  useEffect(() => {
    async function load() {
      setChecking(true);
      try {
        const [healthRes, repoRes, branchesRes] = await Promise.all([
          api.get("/github/health"),
          api.get("/github/repo"),
          api.get("/github/branches"),
        ]);
        setStatus(healthRes.data.success ? "connected" : "unreachable");
        if (repoRes.data.success) setRepoInfo(repoRes.data.data);
        if (branchesRes.data.success) {
          setBranches(branchesRes.data.data || []);
          if (branchesRes.data.data?.length > 0) {
            setSelectedBranch(branchesRes.data.data[0]);
          }
        }
      } catch {
        setStatus("backend-offline");
      } finally {
        setChecking(false);
      }
    }
    load();
  }, []);

  const loadCommits = async (branch) => {
    setLoading((prev) => ({ ...prev, commits: true }));
    setError(null);
    try {
      const params = new URLSearchParams();
      if (branch) params.append("sha", branch);
      if (since) params.append("since", since);
      if (until) params.append("until", until);
      params.append("limit", "100");
      const res = await api.get(`/github/commits?${params.toString()}`);
      if (res.data.success) setCommits(res.data.data || []);
      else setError(res.data.error);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading((prev) => ({ ...prev, commits: false }));
    }
  };

  const loadWorkflows = async () => {
    setLoading((prev) => ({ ...prev, workflows: true }));
    setError(null);
    try {
      const res = await api.get("/github/workflows?limit=30");
      if (res.data.success) setWorkflows(res.data.data || []);
      else setError(res.data.error);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading((prev) => ({ ...prev, workflows: false }));
    }
  };

  const loadIssues = async () => {
    setLoading((prev) => ({ ...prev, issues: true }));
    setError(null);
    try {
      const res = await api.get(`/github/issues?state=${issueState}&limit=30`);
      if (res.data.success) setIssues(res.data.data || []);
      else setError(res.data.error);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading((prev) => ({ ...prev, issues: false }));
    }
  };

  const loadCorrelation = async () => {
    setCorrelationLoading(true);
    setCorrelationError(null);
    try {
      const params = new URLSearchParams();
      if (incidentStart) {
        const iso = new Date(incidentStart).toISOString();
        params.append("incident_start", iso);
      }
      if (selectedBranch) params.append("branch", selectedBranch);
      params.append("limit", "10");
      const res = await api.get(`/investigation/git-correlation?${params.toString()}`);
      if (res.data.success) setCorrelationResult(res.data);
      else setCorrelationError(res.data.error || "Correlation failed");
    } catch (e) {
      setCorrelationError(e.message);
    } finally {
      setCorrelationLoading(false);
    }
  };

  const investigateWorkflow = async (run) => {
    setWorkflowInvestigating(true);
    setWorkflowInvestigation(null);
    setWorkflowInvestError(null);
    try {
      const res = await api.get(`/github/workflow-runs/${run.id}/investigate`);
      const data = res.data;
      if (!data.success) {
        setWorkflowInvestError(data.stderr || data.error || "Investigation failed");
      } else {
        const stdout = data.stdout || "";
        setWorkflowInvestigation({
          run,
          stdout,
          success: data.success,
        });
      }
    } catch (e) {
      setWorkflowInvestError(e.message);
    } finally {
      setWorkflowInvestigating(false);
    }
  };

  useEffect(() => {
    if (status === "connected" && selectedBranch) {
      if (activeTab === "commits") loadCommits(selectedBranch);
      else if (activeTab === "workflows") loadWorkflows();
      else if (activeTab === "issues") loadIssues();
    }
  }, [status, activeTab, selectedBranch, issueState]);

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

  const formatDate = (dateStr) => {
    if (!dateStr) return "—";
    return new Date(dateStr).toLocaleString();
  };

  const getWorkflowStatus = (run) => {
    if (run.conclusion === "success") return { label: "Success", tone: "success", icon: CheckCircle2 };
    if (run.conclusion === "failure") return { label: "Failed", tone: "danger", icon: XCircle };
    if (run.status === "in_progress") return { label: "Running", tone: "neutral", icon: Loader2 };
    if (run.status === "queued") return { label: "Queued", tone: "neutral", icon: Clock };
    return { label: run.conclusion || run.status, tone: "neutral", icon: Clock };
  };

  const getIssueState = (issue) => {
    if (issue.state === "open") return { label: "Open", tone: "success", icon: AlertCircle };
    return { label: "Closed", tone: "neutral", icon: CheckCircle2 };
  };

  const renderCommits = () => {
    if (loading.commits) return <div className="loading"><Loader2 size={16} className="btn__spinner" /> Loading commits…</div>;
    if (!commits.length) return <div className="empty">No commits found</div>;
    return (
      <div style={{ overflowX: "auto" }}>
        <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
          <thead>
            <tr style={{ borderBottom: "1px solid var(--border)" }}>
              <th style={{ textAlign: "left", padding: "var(--space-2)" }}>Commit</th>
              <th style={{ textAlign: "left", padding: "var(--space-2)" }}>Message</th>
              <th style={{ textAlign: "left", padding: "var(--space-2)" }}>Author</th>
              <th style={{ textAlign: "left", padding: "var(--space-2)" }}>Date</th>
              <th style={{ textAlign: "left", padding: "var(--space-2)", width: 40 }}></th>
            </tr>
          </thead>
          <tbody>
            {commits.map((c) => (
              <tr key={c.sha} style={{ borderBottom: "1px solid var(--border)" }}>
                <td style={{ padding: "var(--space-2)", fontFamily: "monospace", fontSize: 12 }}>
                  {c.sha.substring(0, 7)}
                </td>
                <td style={{ padding: "var(--space-2)", maxWidth: 400, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
                  {c.commit?.message?.split("\n")[0] || "—"}
                </td>
                <td style={{ padding: "var(--space-2)" }}>
                  <User size={14} style={{ marginRight: 4, verticalAlign: "middle" }} />
                  {c.commit?.author?.name || c.author?.login || "—"}
                </td>
                <td style={{ padding: "var(--space-2)", whiteSpace: "nowrap", color: "var(--muted)" }}>
                  {formatDate(c.commit?.author?.date)}
                </td>
                <td style={{ padding: "var(--space-2)" }}>
                  <a href={c.html_url} target="_blank" rel="noreferrer" className="btn btn--ghost btn--sm" style={{ padding: "var(--space-1)" }}>
                    <ExternalLink size={12} />
                  </a>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    );
  };

  const renderWorkflows = () => {
    if (loading.workflows) return <div className="loading"><Loader2 size={16} className="btn__spinner" /> Loading workflows…</div>;
    if (!workflows.length) return <div className="empty">No workflow runs found</div>;
    return (
      <div>
        <div style={{ overflowX: "auto" }}>
          <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
            <thead>
              <tr style={{ borderBottom: "1px solid var(--border)" }}>
                <th style={{ textAlign: "left", padding: "var(--space-2)" }}>Workflow</th>
                <th style={{ textAlign: "left", padding: "var(--space-2)" }}>Branch</th>
                <th style={{ textAlign: "left", padding: "var(--space-2)" }}>Event</th>
                <th style={{ textAlign: "left", padding: "var(--space-2)" }}>Status</th>
                <th style={{ textAlign: "left", padding: "var(--space-2)" }}>Started</th>
                <th style={{ textAlign: "left", padding: "var(--space-2)", width: 80 }}></th>
              </tr>
            </thead>
            <tbody>
              {workflows.slice(0, 50).map((w) => {
                const statusInfo = getWorkflowStatus(w);
                const Icon = statusInfo.icon;
                const isFailed = w.conclusion === "failure";
                return (
                  <tr key={w.id} style={{ borderBottom: "1px solid var(--border)" }}>
                    <td style={{ padding: "var(--space-2)", fontWeight: 500 }}>{w.name}</td>
                    <td style={{ padding: "var(--space-2)", fontFamily: "monospace", fontSize: 12 }}>
                      {w.head_branch}
                    </td>
                    <td style={{ padding: "var(--space-2)", textTransform: "capitalize" }}>{w.event}</td>
                    <td style={{ padding: "var(--space-2)" }}>
                      <Badge tone={statusInfo.tone}>
                        <Icon size={12} /> {statusInfo.label}
                      </Badge>
                    </td>
                    <td style={{ padding: "var(--space-2)", whiteSpace: "nowrap", color: "var(--muted)" }}>
                      {formatDate(w.run_started_at)}
                    </td>
                    <td style={{ padding: "var(--space-2)", display: "flex", gap: "var(--space-1)" }}>
                      {isFailed && (
                        <button
                          className="btn btn--ghost btn--sm"
                          style={{ padding: "var(--space-1)" }}
                          onClick={() => investigateWorkflow(w)}
                          disabled={workflowInvestigating}
                        >
                          {workflowInvestigating && workflowInvestigation?.run?.id === w.id ? (
                            <Loader2 size={12} className="btn__spinner" />
                          ) : (
                            <Search size={12} />
                          )}
                        </button>
                      )}
                      <a href={w.html_url} target="_blank" rel="noreferrer" className="btn btn--ghost btn--sm" style={{ padding: "var(--space-1)" }}>
                        <ExternalLink size={12} />
                      </a>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>

        {workflowInvestError && (
          <div className="alert alert--danger" style={{ marginTop: "var(--space-3)" }}>
            {workflowInvestError}
          </div>
        )}

        {workflowInvestigation && (
          <div style={{ marginTop: "var(--space-4)" }}>
            <Card
              title="Investigation report"
              subtitle={`Run #${workflowInvestigation.run.id} · ${workflowInvestigation.run.name} · ${workflowInvestigation.run.conclusion}`}
              actions={
                <Badge tone={workflowInvestigation.success ? "success" : "warning"}>
                  {workflowInvestigation.success ? "Analyzed" : "Inconclusive"}
                </Badge>
              }
            >
              {workflowInvestigation.stdout && (
                <pre className="code-block" style={{ maxHeight: 400, overflow: "auto", fontSize: 12 }}>
                  {workflowInvestigation.stdout}
                </pre>
              )}
            </Card>
          </div>
        )}
      </div>
    );
  };

  const renderIssues = () => {
    if (loading.issues) return <div className="loading"><Loader2 size={16} className="btn__spinner" /> Loading issues…</div>;
    if (!issues.length) return <div className="empty">No issues found</div>;
    return (
      <div style={{ overflowX: "auto" }}>
        <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
          <thead>
            <tr style={{ borderBottom: "1px solid var(--border)" }}>
              <th style={{ textAlign: "left", padding: "var(--space-2)" }}>Issue</th>
              <th style={{ textAlign: "left", padding: "var(--space-2)" }}>Title</th>
              <th style={{ textAlign: "left", padding: "var(--space-2)" }}>State</th>
              <th style={{ textAlign: "left", padding: "var(--space-2)" }}>Author</th>
              <th style={{ textAlign: "left", padding: "var(--space-2)" }}>Updated</th>
              <th style={{ textAlign: "left", padding: "var(--space-2)", width: 40 }}></th>
            </tr>
          </thead>
          <tbody>
            {issues.slice(0, 50).map((i) => {
              const stateInfo = getIssueState(i);
              const Icon = stateInfo.icon;
              return (
                <tr key={i.id} style={{ borderBottom: "1px solid var(--border)" }}>
                  <td style={{ padding: "var(--space-2)", fontFamily: "monospace", color: "var(--primary)" }}>
                    #{i.number}
                  </td>
                  <td style={{ padding: "var(--space-2)", maxWidth: 400, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
                    {i.title}
                  </td>
                  <td style={{ padding: "var(--space-2)" }}>
                    <Badge tone={stateInfo.tone}>
                      <Icon size={12} /> {stateInfo.label}
                    </Badge>
                  </td>
                  <td style={{ padding: "var(--space-2)" }}>
                    <User size={14} style={{ marginRight: 4, verticalAlign: "middle" }} />
                    {i.user?.login || "—"}
                  </td>
                  <td style={{ padding: "var(--space-2)", whiteSpace: "nowrap", color: "var(--muted)" }}>
                    {formatDate(i.updated_at)}
                  </td>
                  <td style={{ padding: "var(--space-2)" }}>
                    <a href={i.html_url} target="_blank" rel="noreferrer" className="btn btn--ghost btn--sm" style={{ padding: "var(--space-1)" }}>
                      <ExternalLink size={12} />
                    </a>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    );
  };

  const renderCorrelation = () => {
    return (
      <div>
        <div style={{ display: "flex", gap: "var(--space-3)", alignItems: "flex-end", marginBottom: "var(--space-4)", flexWrap: "wrap" }}>
          <div>
            <label className="text-muted" style={{ fontSize: 12, display: "block", marginBottom: "var(--space-1)" }}>
              Incident start (UTC)
            </label>
            <input
              type="datetime-local"
              value={incidentStart}
              onChange={(e) => setIncidentStart(e.target.value)}
              style={{ width: 220 }}
            />
          </div>
          <button
            onClick={loadCorrelation}
            className="btn btn--primary btn--sm"
            disabled={correlationLoading}
          >
            {correlationLoading ? (
              <><Loader2 size={14} className="btn__spinner" /> Correlating…</>
            ) : (
              <><Search size={14} /> Find change-point</>
            )}
          </button>
        </div>

        {correlationError && (
          <div className="alert alert--danger" style={{ marginBottom: "var(--space-4)" }}>
            {correlationError}
          </div>
        )}

        {correlationResult && (
          <div style={{ display: "grid", gap: "var(--space-3)" }}>
            {correlationResult.no_commit_found ? (
              <div style={{
                padding: "var(--space-3)",
                border: "1px solid var(--border)",
                borderRadius: 6,
                background: "var(--bg-muted)",
              }}>
                <div style={{ fontWeight: 600, marginBottom: "var(--space-1)" }}>
                  No commit found before incident
                </div>
                <div style={{ fontSize: 13, color: "var(--muted)" }}>
                  The incident start ({correlationResult.incident_start || "not specified"}) predates all commits on
                  branch <code>{correlationResult.branch || "default"}</code>. Attribution is inconclusive — the incident may
                  pre-date the deploy history, or no deploy was performed before the incident.
                </div>
              </div>
            ) : correlationResult.suspected_commit ? (
              <>
                <div style={{
                  padding: "var(--space-3)",
                  border: "2px solid var(--primary)",
                  borderRadius: 6,
                  background: "var(--bg-muted)",
                }}>
                  <div style={{ fontSize: 12, color: "var(--muted)", marginBottom: "var(--space-1)" }}>
                    Suspected change-point commit
                  </div>
                  <div style={{ display: "flex", alignItems: "center", gap: "var(--space-2)", flexWrap: "wrap" }}>
                    <code style={{ fontSize: 13, fontWeight: 600 }}>
                      {correlationResult.suspected_commit.sha?.substring(0, 7)}
                    </code>
                    <span style={{ fontSize: 13 }}>
                      {correlationResult.suspected_commit.message}
                    </span>
                  </div>
                  <div style={{ fontSize: 12, color: "var(--muted)", marginTop: "var(--space-1)", display: "flex", gap: "var(--space-3)" }}>
                    <span><User size={12} style={{ verticalAlign: "middle" }} /> {correlationResult.suspected_commit.author || "—"}</span>
                    <span>{formatDate(correlationResult.suspected_commit.date)}</span>
                  </div>
                  <div style={{ marginTop: "var(--space-2)" }}>
                    <a
                      href={`https://github.com/${correlationResult.repo || ""}/commit/${correlationResult.suspected_commit.sha}`}
                      target="_blank"
                      rel="noreferrer"
                      className="btn btn--ghost btn--sm"
                    >
                      <ExternalLink size={12} /> View on GitHub
                    </a>
                  </div>
                </div>

                {correlationResult.window_before_incident?.length > 0 && (
                  <div>
                    <div style={{ fontSize: 12, color: "var(--muted)", marginBottom: "var(--space-1)" }}>
                      Commits before incident
                    </div>
                    <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
                      <thead>
                        <tr style={{ borderBottom: "1px solid var(--border)" }}>
                          <th style={{ textAlign: "left", padding: "var(--space-2)" }}>Commit</th>
                          <th style={{ textAlign: "left", padding: "var(--space-2)" }}>Message</th>
                          <th style={{ textAlign: "left", padding: "var(--space-2)" }}>Author</th>
                          <th style={{ textAlign: "left", padding: "var(--space-2)" }}>Date</th>
                        </tr>
                      </thead>
                      <tbody>
                        {correlationResult.window_before_incident.map((c) => (
                          <tr key={c.sha} style={{ borderBottom: "1px solid var(--border)" }}>
                            <td style={{ padding: "var(--space-2)", fontFamily: "monospace", fontSize: 12 }}>
                              {c.sha?.substring(0, 7)}
                            </td>
                            <td style={{ padding: "var(--space-2)", maxWidth: 400, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
                              {c.message}
                            </td>
                            <td style={{ padding: "var(--space-2)" }}>
                              <User size={12} style={{ marginRight: 4, verticalAlign: "middle" }} />
                              {c.author || "—"}
                            </td>
                            <td style={{ padding: "var(--space-2)", whiteSpace: "nowrap", color: "var(--muted)" }}>
                              {formatDate(c.date)}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </>
            ) : (
              <div style={{ padding: "var(--space-3)", fontSize: 13, color: "var(--muted)" }}>
                No result returned from correlation service.
              </div>
            )}
          </div>
        )}

        {!correlationResult && !correlationError && !correlationLoading && (
          <div className="empty-state" style={{ padding: "var(--space-6) 0" }}>
            <Search size={26} />
            <div>
              <strong>Correlate an incident with git history</strong>
              <p style={{ marginTop: "var(--space-1)", maxWidth: 420, fontSize: 13 }}>
                Enter the incident start time and click "Find change-point" to identify
                which commit was likely deployed before the incident began.
              </p>
            </div>
          </div>
        )}
      </div>
    );
  };

  return (
    <>
      <div className="page-head">
        <div>
          <h1>GitHub Integration</h1>
          <p className="page-head__sub">
            Track repository changes, workflows, and issues for incident correlation
          </p>
        </div>
      </div>

      <div className="grid-2">
        <Card
          title="Connection"
          subtitle={repoInfo ? `Repository: ${repoInfo.full_name}` : "Configure GITHUB_TOKEN and GITHUB_REPO"}
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
              <GitBranch size={17} strokeWidth={1.8} />
            </div>
            <div>
              {repoInfo && (
                <>
                  <div className="text-muted" style={{ fontSize: 13, marginBottom: "var(--space-1)" }}>
                    {repoInfo.description || "No description"}
                  </div>
                  <div className="row" style={{ gap: "var(--space-4)", fontSize: 12, color: "var(--muted)" }}>
                    <span>⭐ {repoInfo.stargazers_count}</span>
                    <span>🍴 {repoInfo.forks_count}</span>
                    <span>👁 {repoInfo.watchers_count}</span>
                    <span>{repoInfo.private ? "Private" : "Public"}</span>
                  </div>
                </>
              )}
            </div>
          </div>
        </Card>

        <Card title="Filters" subtitle="Filter data by branch, date range, and state">
          <div style={{ display: "flex", gap: "var(--space-3)", flexWrap: "wrap", alignItems: "flex-end" }}>
            {branches.length > 0 && (
              <div>
                <label className="text-muted" style={{ fontSize: 12, display: "block", marginBottom: "var(--space-1)" }}>
                  Branch
                </label>
                <select
                  value={selectedBranch}
                  onChange={(e) => setSelectedBranch(e.target.value)}
                  style={{ padding: "var(--space-1) var(--space-2)", minWidth: 150 }}
                >
                  {branches.map((b) => (
                    <option key={b} value={b}>{b}</option>
                  ))}
                </select>
              </div>
            )}
            {activeTab === "commits" && (
              <>
                <div>
                  <label className="text-muted" style={{ fontSize: 12, display: "block", marginBottom: "var(--space-1)" }}>
                    Since
                  </label>
                  <input
                    type="datetime-local"
                    value={since}
                    onChange={(e) => setSince(e.target.value)}
                    style={{ width: 200 }}
                  />
                </div>
                <div>
                  <label className="text-muted" style={{ fontSize: 12, display: "block", marginBottom: "var(--space-1)" }}>
                    Until
                  </label>
                  <input
                    type="datetime-local"
                    value={until}
                    onChange={(e) => setUntil(e.target.value)}
                    style={{ width: 200 }}
                  />
                </div>
              </>
            )}
            {activeTab === "issues" && (
              <div>
                <label className="text-muted" style={{ fontSize: 12, display: "block", marginBottom: "var(--space-1)" }}>
                  Issue State
                </label>
                <select
                  value={issueState}
                  onChange={(e) => setIssueState(e.target.value)}
                  style={{ padding: "var(--space-1) var(--space-2)" }}
                >
                  <option value="open">Open</option>
                  <option value="closed">Closed</option>
                  <option value="all">All</option>
                </select>
              </div>
            )}
            <button
              onClick={() => {
                if (activeTab === "commits") loadCommits(selectedBranch);
                else if (activeTab === "workflows") loadWorkflows();
                else if (activeTab === "issues") loadIssues();
                else if (activeTab === "correlation") loadCorrelation();
              }}
              className="btn btn--primary btn--sm"
              disabled={loading[activeTab] || (activeTab === "correlation" && correlationLoading)}
            >
              <Search size={14} /> Refresh
            </button>
          </div>
        </Card>
      </div>

      <div style={{ marginTop: "var(--space-4)" }}>
        <div style={{ display: "flex", gap: "var(--space-1)", marginBottom: "var(--space-4)", borderBottom: "1px solid var(--border)", paddingBottom: "var(--space-2)" }}>
          {TAB_CONFIG.map((tab) => {
            const Icon = tab.icon;
            return (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={`btn btn--sm ${activeTab === tab.id ? "btn--primary" : "btn--ghost"}`}
                style={{ display: "flex", alignItems: "center", gap: "var(--space-1)" }}
              >
                <Icon size={14} /> {tab.label}
              </button>
            );
          })}
        </div>

        {error && (
          <div className="alert alert--danger" style={{ marginBottom: "var(--space-4)" }}>
            {error}
          </div>
        )}

        <Card>
          {activeTab === "commits" && renderCommits()}
          {activeTab === "workflows" && renderWorkflows()}
          {activeTab === "issues" && renderIssues()}
          {activeTab === "correlation" && renderCorrelation()}
        </Card>
      </div>
    </>
  );
}