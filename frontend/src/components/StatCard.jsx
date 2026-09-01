export default function StatCard({ label, value, icon: Icon, trend, loading, tone }) {
  return (
    <div className="stat-card">
      <div className="stat-card__top">
        <div className="stat-card__icon">
          {Icon && <Icon size={17} strokeWidth={1.8} />}
        </div>
        <span className="stat-card__label">{label}</span>
      </div>

      {loading ? (
        <div className="skeleton" style={{ width: 52, height: 30 }} />
      ) : (
        <div
          className={`stat-card__value${tone ? ` stat-card__value--${tone}` : ""}`}
        >
          {value}
        </div>
      )}

      {trend && !loading && <div className="stat-card__trend">{trend}</div>}
    </div>
  );
}