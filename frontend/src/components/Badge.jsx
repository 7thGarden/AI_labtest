const TONES = ["success", "warning", "danger", "info", "primary", "neutral"];

export default function Badge({ tone = "neutral", children }) {
  const valid = TONES.includes(tone) ? tone : "neutral";
  return (
    <span className={`badge badge--${valid}`}>
      {children}
    </span>
  );
}
