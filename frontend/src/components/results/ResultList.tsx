import { useStore } from '@/store';

export function ResultList(): React.ReactElement {
  const results = useStore((s) => s.results);
  const activeResultId = useStore((s) => s.activeResultId);
  const setActiveResult = useStore((s) => s.setActiveResult);

  const items = Object.values(results);
  if (items.length === 0) {
    return <div style={{ color: 'var(--text-dim)', fontSize: 12 }}>No results yet. Run an analysis.</div>;
  }

  return (
    <div className="list">
      {items.map((r) => (
        <div
          key={r.id}
          className={`card${activeResultId === r.id ? ' selected' : ''}`}
          onClick={() => setActiveResult(r.id)}
          role="button"
          tabIndex={0}
          onKeyDown={(e) => {
            if (e.key === 'Enter') setActiveResult(r.id);
          }}
        >
          <div className="title">{r.mineral}</div>
          <div className="meta">
            {r.algorithm} · obs {r.observation_id} · {r.created_at.slice(0, 10)}
          </div>
        </div>
      ))}
    </div>
  );
}
