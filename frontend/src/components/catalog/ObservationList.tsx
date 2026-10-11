import { useStore } from '@/store';
import { ObservationCard } from './ObservationCard';

export function ObservationList(): React.ReactElement {
  const observations = useStore((s) => s.observations);
  const total = useStore((s) => s.total);

  if (observations.length === 0) {
    return <div style={{ color: 'var(--text-dim)', fontSize: 12 }}>No observations match.</div>;
  }

  return (
    <div className="list" role="listbox" aria-label="Observations">
      <div style={{ fontSize: 11, color: 'var(--text-dim)' }}>
        Showing {observations.length} of {total}
      </div>
      {observations.map((obs) => (
        <ObservationCard key={obs.id} obs={obs} />
      ))}
    </div>
  );
}
