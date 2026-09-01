import { Activity, FileText, HardDrive, Server } from "lucide-react";
import Badge from "./Badge";
import { severityTone, stripAnsi } from "../utils/opensre";

export default function ProblemFraming({ markdown, cluster, context }) {
  const text = stripAnsi(markdown || "");
  const lines = text.split("\n");

  let title = "";
  let severity = null;
  let namespace = null;
  const extra = [];

  for (const raw of lines) {
    const trimmed = raw.trim();
    if (!trimmed) continue;

    const heading = trimmed.match(/^#+\s+(.+)$/);
    if (heading && !title) {
      title = heading[1].trim();
      continue;
    }

    const severityMatch = trimmed.match(/^Severity:\s*(.+)$/i);
    if (severityMatch) {
      severity = severityMatch[1].trim();
      continue;
    }

    const namespaceMatch = trimmed.match(/^Namespace:\s*(.+)$/i);
    if (namespaceMatch) {
      namespace = namespaceMatch[1].trim();
      continue;
    }

    const errorMatch = trimmed.match(/^Error:\s*(.+)$/i);
    if (errorMatch) {
      extra.push({ label: "Observed signal", value: errorMatch[1].trim() });
      continue;
    }

    extra.push({ label: "", value: trimmed });
  }

  return (
    <div className="problem-framing">
      <div className="problem-framing__head">
        <span className="problem-framing__icon">
          <FileText size={16} />
        </span>
        <div className="problem-framing__heading">
          <div className="problem-framing__eyebrow">Problem framing</div>
          <div className="problem-framing__title">
            {title || "Incident context"}
          </div>
        </div>
        {severity && (
          <Badge tone={severityTone(severity)}>{severity}</Badge>
        )}
      </div>

      {(namespace || cluster || context) && (
        <div className="problem-framing__chips">
          {namespace && (
            <span className="problem-framing__chip">
              <HardDrive size={12} /> Namespace · {namespace}
            </span>
          )}
          {cluster && (
            <span className="problem-framing__chip">
              <Server size={12} /> Cluster · {cluster}
            </span>
          )}
          {context && !cluster && (
            <span className="problem-framing__chip">
              <Server size={12} /> Context · {context}
            </span>
          )}
        </div>
      )}

      {extra.length > 0 && (
        <div className="problem-framing__rows">
          {extra.map((row, index) => (
            <div className="problem-framing__row" key={index}>
              {row.label && (
                <span className="problem-framing__row-label">
                  <Activity size={12} /> {row.label}
                </span>
              )}
              <div className="problem-framing__row-value">{row.value}</div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}