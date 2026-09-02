import { useEffect, useState, useCallback, useMemo } from "react";
import api from "../api/api";
import Card from "../components/Card";
import Badge from "../components/Badge";
import Skeleton from "../components/Skeleton";
import {
  Activity,
  AlertTriangle,
  Gauge,
  Pause,
  Play,
  RefreshCw,
  Rocket,
  Server,
  Timer,
} from "lucide-react";

const QUANTILES = [
  { key: "p50", label: "P50", color: "var(--info)", strokeWidth: 2 },
  { key: "p95", label: "P95", color: "var(--warning)", strokeWidth: 2 },
  { key: "p99", label: "P99", color: "var(--danger)", strokeWidth: 2 },
];

const REFRESH_OPTIONS = [5, 10, 30];
const WINDOW = 180;
const STEP = 15;
const CHART_PAD = { top: 12, right: 12, bottom: 24, left: 46 };
const HIGH_LATENCY_S = 1.0;

function formatLatency(seconds) {
  if (seconds == null || Number.isNaN(seconds)) return "—";
  if (seconds < 1) return `${Math.round(seconds * 1000)} ms`;
  if (seconds < 10) return `${seconds.toFixed(2)} s`;
  return `${Math.round(seconds)} s`;
}

function latencyTone(seconds) {
  if (seconds == null || Number.isNaN(seconds)) return "neutral";
  if (seconds > 1) return "danger";
  if (seconds > 0.5) return "warning";
  return "success";
}

function latencyToneClass(seconds) {
  if (seconds == null || Number.isNaN(seconds)) return "lat--neutral";
  if (seconds > 1) return "lat--danger";
  if (seconds > 0.5) return "lat--warning";
  return "lat--success";
}

function Tile({ label, value, tone, icon: Icon, sub }) {
  return (
    <div className="metric-tile">
      <div className="metric-tile__icon">
        <Icon size={15} strokeWidth={2} />
      </div>
      <div>
        <div className={`metric-tile__value metric-tile__value--${tone}`}>
          {value}
        </div>
        <div className="metric-tile__label">{label}</div>
        {sub && <div className="metric-tile__sub">{sub}</div>}
      </div>
    </div>
  );
}

function SeriesChart({ series, height = 220 }) {
  const width = 980;
  const pad = CHART_PAD;

  const chart = useMemo(() => {
    const all = QUANTILES.flatMap(({ key }) => series[key] || []);
    const allV = all.map((p) => p.v);

    let max = Math.max(0, ...allV);
    let min = allV.length ? Math.min(...allV) : 0;

    if (max === min) {
      max = max + 1;
      min = 0;
    }

    const span = max - min || 1;
    const innerW = width - pad.left - pad.right;
    const innerH = height - pad.top - pad.bottom;

    const xFor = (t) =>
      pad.left + ((t - series.start) / (series.end - series.start || 1)) * innerW;
    const yFor = (v) => pad.top + (1 - (v - min) / span) * innerH;

    return { max, min, innerW, innerH, xFor, yFor };
  }, [series, height, pad.left, pad.right, pad.top, pad.bottom, width]);

  const yTicks = useMemo(() => {
    const { max, min } = chart;
    const ticks = [];
    for (let i = 0; i <= 4; i += 1) {
      ticks.push(min + ((max - min) * i) / 4);
    }
    return ticks;
  }, [chart]);

  return (
    <div style={{ overflowX: "auto" }}>
      <svg
        viewBox={`0 0 ${width} ${height}`}
        style={{ width: "100%", minWidth: 640, display: "block" }}
        role="img"
        aria-label="Request latency percentile chart"
      >
        {yTicks.map((tick, i) => (
          <g key={i}>
            <line
              x1={pad.left}
              x2={width - pad.right}
              y1={chart.yFor(tick)}
              y2={chart.yFor(tick)}
              stroke="var(--border)"
              strokeWidth={1}
              strokeDasharray="4 4"
            />
            <text
              x={width - pad.right}
              y={chart.yFor(tick) - 4}
              textAnchor="end"
              fontSize={10}
              fill="var(--text-3)"
            >
              {formatLatency(tick)}
            </text>
          </g>
        ))}

        {QUANTILES.map(({ key, color, strokeWidth }) => {
          const pts = series[key] || [];
          if (pts.length < 2) return null;

          const linePath = pts
            .map(
              (p) =>
                `${chart.xFor(p.t)},${chart.yFor(p.v)}`
            )
            .join(" ");

          return (
            <g key={key}>
              <polyline
                points={linePath}
                fill="none"
                stroke={color}
                strokeWidth={strokeWidth}
                strokeLinejoin="round"
                strokeLinecap="round"
              />
            </g>
          );
        })}
      </svg>
    </div>
  );
}

export default function Latency() {
  const [series, setSeries] = useState(null);
  const [pods, setPods] = useState([]);
  const [loading, setLoading] = useState(true);
  const [podsLoading, setPodsLoading] = useState(true);
  const [error, setError] = useState(null);
  const [podsError, setPodsError] = useState(null);
  const [selectedPod, setSelectedPod] = useState(null);
  const [refreshing, setRefreshing] = useState(false);
  const [live, setLive] = useState(true);
  const [interval, setIntervalMs] = useState(5);
  const [lastUpdated, setLastUpdated] = useState(null);

  const fetchLatency = useCallback(async () => {
    try {
      const params = { window: WINDOW, step: STEP };
      if (selectedPod) params.pod = selectedPod;

      const res = await api.get("/metrics/latency", { params });

      if (!res.data.success) throw new Error(res.data.error || "Failed to load latency");

      const s = res.data.data.series;
      const flat = QUANTILES.flatMap(({ key }) => s[key] || []);
      const times = flat.map((p) => p.t);
      const start = times.length ? Math.min(...times) : 0;
      const end = times.length ? Math.max(...times) : 0;

      setSeries({ ...s, start, end });
      setError(null);
      setLastUpdated(new Date());
    } catch (err) {
      setError(err.message);
    }
  }, [selectedPod]);

  const fetchPods = useCallback(async () => {
    try {
      const res = await api.get("/metrics/latency/pods");

      if (!res.data.success) throw new Error(res.data.error || "Failed to load pods");

      const list = res.data.data.pods || [];
      setPods(list);
      setPodsError(null);
      setSelectedPod((prev) => {
        if (prev && !list.some((p) => p.pod === prev)) return null;
        return prev;
      });
    } catch (err) {
      setPodsError(err.message);
    }
  }, []);

  useEffect(() => {
    let cancelled = false;

    const timer = setTimeout(() => {
      Promise.all([fetchLatency(), fetchPods()]).finally(() => {
        if (!cancelled) {
          setLoading(false);
          setPodsLoading(false);
        }
      });
    }, 0);

    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [fetchLatency, fetchPods]);

  useEffect(() => {
    if (!live) return undefined;

    const timer = setInterval(() => {
      setRefreshing(true);
      Promise.all([fetchLatency(), fetchPods()]).finally(() => setRefreshing(false));
    }, interval * 1000);

    return () => clearInterval(timer);
  }, [live, interval, fetchLatency, fetchPods]);

  const latest = useMemo(() => {
    const out = {};
    QUANTILES.forEach(({ key }) => {
      const pts = (series && series[key]) || [];
      out[key] = pts.length ? pts[pts.length - 1].v : null;
    });
    return out;
  }, [series]);

  const hasData = QUANTILES.some(({ key }) => (series && series[key] || []).length > 0);
  const highPods = pods.filter((p) => p.high);
  const focusedNoData =
    selectedPod != null && pods.some((p) => p.pod === selectedPod && !p.has_data);

  const handleFocus = (pod) => {
    const next = selectedPod === pod ? null : pod;
    setSelectedPod(next);
    setError(null);

    if (next) {
      const target = pods.find((p) => p.pod === next);
      if (target && !target.has_data) setSeries(null);
    }
  };

  const handleRefresh = () => {
    setRefreshing(true);
    Promise.all([fetchLatency(), fetchPods()])
      .catch(() => {})
      .finally(() => setRefreshing(false));
  };

  return (
    <>
      <div className="page-head">
        <div>
          <h1>Latency</h1>
          <p className="page-head__sub">
            Live request-latency percentiles, auto-refreshing every few seconds.
          </p>
        </div>

        <div className="page-head__actions">
          <span className="live-indicator">
            <span className={`live-dot${live ? " live-dot--on" : ""}`} />
            {live ? "Live" : "Paused"}
          </span>
          {lastUpdated && (
            <span className="text-muted">
              Updated {lastUpdated.toLocaleTimeString()}
            </span>
          )}
          <button
            type="button"
            className="btn btn--ghost"
            disabled={refreshing}
            onClick={handleRefresh}
          >
            <RefreshCw size={14} className={refreshing ? "btn__spinner" : ""} />
            Refresh
          </button>
        </div>
      </div>

      <div className="chips-row" style={{ marginBottom: "var(--space-4)" }}>
        <label className="pod-picker">
          <span className="pod-picker__label">
            <Server size={13} />
            Focus
          </span>
          <select
            className="select pod-picker__select"
            value={selectedPod ?? ""}
            disabled={pods.length === 0}
            onChange={(e) => handleFocus(e.target.value)}
          >
            <option value="">All pods</option>
            {pods.map((p) => (
              <option key={p.pod} value={p.pod}>
                {p.pod}
              </option>
            ))}
          </select>
        </label>
        <span className="text-muted" style={{ display: "inline-flex", alignItems: "center", gap: 8 }}>
          <Timer size={14} />
          Refresh every
        </span>
        <div className="segmented-control">
          {REFRESH_OPTIONS.map((sec) => (
            <button
              key={sec}
              type="button"
              className={`segmented-control__btn${interval === sec ? " segmented-control__btn--active" : ""}`}
              onClick={() => setIntervalMs(sec)}
            >
              {sec}s
            </button>
          ))}
        </div>
        <button
          type="button"
          className="btn btn--ghost btn--sm"
          onClick={() => setLive((value) => !value)}
        >
          {live ? <Pause size={13} /> : <Play size={13} />}
          {live ? "Pause" : "Resume"}
        </button>
      </div>

      {highPods.length > 0 && (
        <div className="alert alert--danger" style={{ marginBottom: "var(--space-4)" }}>
          <AlertTriangle size={14} />
          <strong>High latency:</strong>
          <span>
            {highPods.map((p) => `${p.pod} (p99 ${formatLatency(p.p99)})`).join(" · ")}
            {" "}— over {HIGH_LATENCY_S}s
          </span>
        </div>
      )}

      {podsError && !error && (
        <div className="alert alert--danger" style={{ marginBottom: "var(--space-4)" }}>
          <AlertTriangle size={14} />
          {podsError}
        </div>
      )}

      <div className="metric-grid metric-grid--4">
        <Tile
          label="P50 latency"
          sub="median request"
          value={formatLatency(latest.p50)}
          tone={latencyTone(latest.p50)}
          icon={Rocket}
        />
        <Tile
          label="P95 latency"
          sub="95th percentile"
          value={formatLatency(latest.p95)}
          tone={latencyTone(latest.p95)}
          icon={Rocket}
        />
        <Tile
          label="P99 latency"
          sub="99th percentile"
          value={formatLatency(latest.p99)}
          tone={latencyTone(latest.p99)}
          icon={Rocket}
        />
        <Tile
          label="Tail risk"
          sub="p99 - p50 spread"
          value={
            latest.p99 == null || Number.isNaN(latest.p99) || latest.p50 == null
              ? "—"
              : formatLatency(latest.p99 - latest.p50)
          }
          tone={latencyTone(latest.p99)}
          icon={Gauge}
        />
      </div>

      {error && !focusedNoData && (
        <div className="alert alert--danger" style={{ marginTop: "var(--space-3)" }}>
          {error}
        </div>
      )}

      <Card
        title="Latency over time"
        subtitle={`Last ${WINDOW / 60} min window · ${STEP}s resolution · rolling view`}
        actions={
          <Badge tone={live ? "success" : "neutral"}>
            {live ? <Activity size={12} /> : <Pause size={12} />}
            {live ? "Auto-refresh" : "Paused"}
          </Badge>
        }
        className="latency-card"
      >
        {loading ? (
          <Skeleton height={220} />
        ) : hasData ? (
          <SeriesChart series={series} />
        ) : (
          <div className="empty-state">
            <Activity size={26} />
            {focusedNoData
              ? `No latency data for "${selectedPod}" — this pod is not instrumentation-scraped (no HTTP latency metrics).`
              : "No latency data available yet."}
          </div>
        )}

        <div className="chart-legend">
          {QUANTILES.map(({ key, label, color }) => {
            const pts = (series && series[key]) || [];
            const last = pts.length ? formatLatency(pts[pts.length - 1].v) : "—";
            return (
              <span key={key} className="chart-legend__item">
                <span className="chart-legend__swatch" style={{ background: color }} />
                {label}
                <span className="chart-legend__value">{last}</span>
              </span>
            );
          })}
          <span className="text-muted" style={{ marginLeft: "auto", fontSize: 12 }}>
            {selectedPod ? `focused: ${selectedPod}` : ""}
            {series && !selectedPod ? `${series.end - series.start}s window` : ""}
          </span>
        </div>
      </Card>

      <Card
        title="Per-pod latency"
        subtitle="opensre namespace · live p50 / p95 / p99 per pod — click a pod to focus the chart above"
        actions={
          pods.length === 0 ? null : (
            <Badge tone={highPods.length ? "warning" : "success"}>
              {highPods.length ? `${highPods.length} high` : "all healthy"}
            </Badge>
          )
        }
      >
        {podsLoading ? (
          <Skeleton height={120} />
        ) : pods.length === 0 ? (
          <div className="empty-state">
            <Server size={26} /> No pod metrics yet.
          </div>
        ) : (
          <div className="pod-grid">
            {pods.map((p) => {
              const active = selectedPod === p.pod;
              return (
                <button
                  key={p.pod}
                  type="button"
                  className={`pod-card${active ? " pod-card--active" : ""}${p.high ? " pod-card--high" : ""}`}
                  onClick={() => handleFocus(p.pod)}
                  title={p.has_data ? `Focus ${p.pod}` : `${p.pod} — not instrumented`}
                >
                  <span className="pod-card__top">
                    <span className="pod-card__name">{p.pod}</span>
                    {!p.has_data ? (
                      <Badge tone="neutral">no data</Badge>
                    ) : p.high ? (
                      <Badge tone="danger">
                        <AlertTriangle size={11} /> HIGH
                      </Badge>
                    ) : (
                      <Badge tone="success">OK</Badge>
                    )}
                  </span>

                  <span className="pod-card__stats">
                    <span className="pod-card__stat">
                      <em>p50</em>
                      <b className={latencyToneClass(p.p50)}>{formatLatency(p.p50)}</b>
                    </span>
                    <span className="pod-card__stat">
                      <em>p95</em>
                      <b className={latencyToneClass(p.p95)}>{formatLatency(p.p95)}</b>
                    </span>
                    <span className="pod-card__stat">
                      <em>p99</em>
                      <b className={latencyToneClass(p.p99)}>{formatLatency(p.p99)}</b>
                    </span>
                  </span>

                  <span className="pod-card__foot">
                    {!p.has_data
                      ? "not monitored"
                      : p.rate == null
                        ? "no traffic"
                        : `${p.rate.toFixed(1)} req/s`}
                    {active ? " · focused" : ""}
                  </span>
                </button>
              );
            })}
          </div>
        )}
      </Card>
    </>
  );
}
