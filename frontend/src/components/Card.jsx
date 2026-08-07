export default function Card({ title, value, color = "#2563eb" }) {
  return (
    <div className="card">
      <p className="card-title">{title}</p>

      <h1 style={{ color }}>{value}</h1>
    </div>
  );
}