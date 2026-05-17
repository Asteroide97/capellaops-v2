export default function FeaturePlaceholder({
  title,
  subtitle,
  items,
  note,
  tone = "default",
}) {
  return (
    <section className={`feature-card ${tone}`}>
      <div className="feature-header">
        <p className="eyebrow">Módulo</p>
        <h2>{title}</h2>
        <p>{subtitle}</p>
      </div>

      <div className="feature-grid">
        {items.map((item) => (
          <article className="mini-card" key={item}>
            <strong>{item}</strong>
          </article>
        ))}
      </div>

      {note ? <p className="feature-note">{note}</p> : null}
    </section>
  );
}

