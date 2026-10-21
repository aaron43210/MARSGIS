import type { Legend as LegendType } from '@/types';
import { stopsToCssGradient, discreteSwatches } from '@/utils/color';
import { CaveatBlock } from '@/components/common';

/** Render a result/quality legend from contract metadata (continuous bar or discrete swatches). */
export function Legend({ legend }: { legend: LegendType }): React.ReactElement {
  const isContinuous = legend.type === 'continuous';
  const range = legend.value_range;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
      <div style={{ fontSize: 12, fontWeight: 600 }}>{legend.title}</div>

      {isContinuous ? (
        <>
          <div className="legend-bar" style={{ background: stopsToCssGradient(legend.stops) }} />
          <div className="legend-labels">
            <span>{range ? range[0] : (legend.stops[0]?.value ?? '')}</span>
            {legend.units ? <span>{legend.units}</span> : null}
            <span>{range ? range[1] : (legend.stops.at(-1)?.value ?? '')}</span>
          </div>
        </>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
          {discreteSwatches(legend).map((s, i) => (
            <div key={i} style={{ fontSize: 12 }}>
              <span className="swatch" style={{ background: s.color }} />
              {s.label}
            </div>
          ))}
        </div>
      )}

      {legend.caveat ? <CaveatBlock text={legend.caveat} /> : null}
    </div>
  );
}
