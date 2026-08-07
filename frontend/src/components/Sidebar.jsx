import { Link } from "react-router-dom";

export default function Sidebar() {
  return (
    <div className="sidebar">
      <h2>OpenSRE</h2>

      <Link to="/">📊 Dashboard</Link>
      <Link to="/kubernetes">☸ Kubernetes</Link>
      <Link to="/metrics">📈 Metrics</Link>
      <Link to="/analysis">🤖 AI Analysis</Link>
      <Link to="/settings">⚙ Settings</Link>
    </div>
  );
}