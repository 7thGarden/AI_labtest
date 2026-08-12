const ESC = String.fromCharCode(27);
const CSI_RE = /^\[[0-9;]*[a-zA-Z]/;

export function stripAnsi(text = "") {
  return text
    .split(ESC)
    .map((segment, index) => (index === 0 ? segment : segment.replace(CSI_RE, "")))
    .join("")
    .replace(/\r/g, "");
}

export function extractReport(stdout = "") {
  const text = stripAnsi(stdout);

  const lastBrace = text.lastIndexOf("{");
  if (lastBrace === -1) {
    return null;
  }

  try {
    const parsed = JSON.parse(text.slice(lastBrace));
    if (parsed && typeof parsed === "object" && "report" in parsed) {
      return parsed;
    }
  } catch {
    return null;
  }

  return null;
}

export function podTone(status = "") {
  const value = status.toLowerCase();

  if (value === "running" || value === "succeeded" || value === "completed") {
    return "success";
  }

  if (value === "pending" || value === "containercreating" || value === "terminating") {
    return "warning";
  }

  if (
    value.includes("error") ||
    value.includes("crash") ||
    value.includes("failed") ||
    value.includes("evicted") ||
    value.includes("oom") ||
    value.includes("unhealthy")
  ) {
    return "danger";
  }

  return "neutral";
}

export function nodeTone(status = "") {
  return status.toLowerCase() === "ready" ? "success" : "danger";
}

export function readyTone(ready = "") {
  const [readyCount, total] = ready.split("/").map(Number);
  if (Number.isFinite(readyCount) && Number.isFinite(total)) {
    return readyCount >= total && total > 0 ? "success" : "warning";
  }
  return "neutral";
}
