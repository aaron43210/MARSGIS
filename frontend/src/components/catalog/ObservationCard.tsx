import { useStore } from '@/store';
import type { ObservationSummary } from '@/types';
import { formatLonLat } from '@/utils/format';
import { Badge } from '@/components/common';

export function ObservationCard({ obs }: { obs: ObservationSummary }): React.ReactElement {
  const selectedId = useStore((s) => s.selectedObservationId);
  const hoveredId = useStore((s) => s.hoveredObservationId);
  const selectObservation = useStore((s) => s.selectObservation);
  const hoverObservation = useStore((s) => s.hoverObservation);

  const selected = selectedId === obs.id;
  const hovered = hoveredId === obs.id;

  return (
    <div
      className={`card${selected ? ' selected' : ''}`}
      style={hovered && !selected ? { borderColor: 'var(--border-strong)' } : undefined}
      onClick={() => selectObservation(obs.id)}
      onMouseEnter={() => hoverObservation(obs.id)}
      onMouseLeave={() => hoverObservation(null)}
      role="button"
      tabIndex={0}
      onKeyDown={(e) => {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault();
          selectObservation(obs.id);
        }
      }}
    >
      <div className="title">
        {obs.id}{' '}
        {!obs.analysis_suitable ? <Badge>not suitable</Badge> : null}
      </div>
      <div className="meta">{obs.title}</div>
      <div className="meta">
        {obs.instrument} · {obs.product_type} · {formatLonLat(obs.center.lon, obs.center.lat)}
        {obs.acquired_at ? ` · ${obs.acquired_at.slice(0, 10)}` : ''}
      </div>
    </div>
  );
}
