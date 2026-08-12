export default function Skeleton({ width = "100%", height = 16, style, className = "" }) {
  return (
    <div
      className={`skeleton ${className}`.trim()}
      style={{ width, height, ...style }}
    />
  );
}
