import { useStore } from '@/store';
import { ObservationCard } from './ObservationCard';
import { CrosshairIcon } from '@/components/common';

export function ObservationList(): React.ReactElement {
  const observations = useStore((s) => s.observations);
  const total = useStore((s) => s.total);
  const requestFlyTo = useStore((s) => s.requestFlyTo);

  if (observations.length === 0) {
    return <div style={{ color: 'var(--text-dim)', fontSize: 12 }}>No observations match.</div>;
  }

  return (
    <div className="list" role="listbox" aria-label="Observations">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontSize: 11, color: 'var(--text-dim)', padding: '2px 0' }}>
        <span>Showing {observations.length} of {total}</span>
        <button
          className="btn btn-ghost"
          onClick={() => requestFlyTo(null)}
          title="Auto-center and Zoom to Observation Layer"
          style={{ fontSize: 11, padding: '2px 6px', display: 'inline-flex', alignItems: 'center', gap: 4 }}
        >
          <CrosshairIcon size={12} />
          <span>Zoom to layer</span>
        </button>
      </div>
      {observations.map((obs) => (
        <ObservationCard key={obs.id} obs={obs} />
      ))}
    </div>
  );
}
