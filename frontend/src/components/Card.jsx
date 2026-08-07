export default function Card({ title, value }) {
  return (
    <div className="card">

      <h3>{title}</h3>

      <h1>{value}</h1>

    </div>
  );
}