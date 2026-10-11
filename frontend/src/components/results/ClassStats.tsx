import type { SummaryStats } from '@/types';
import { formatInt, formatPercent, formatAngle, radToDeg } from '@/utils/format';

/** Result statistics with neutral framing (candidate counts, never "confirmed"). */
export function ClassStats({ stats }: { stats: SummaryStats }): React.ReactElement {
  const detectedPct = stats.valid_pixel_count
    ? stats.detected_pixel_count / stats.valid_pixel_count
    : 0;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
      <div className="stat-grid">
        <div className="stat">
          <div className="label">Candidate pixels</div>
          <div className="value">{formatInt(stats.detected_pixel_count)}</div>
        </div>
        <div className="stat">
          <div className="label">Valid pixels</div>
          <div className="value">{formatInt(stats.valid_pixel_count)}</div>
        </div>
      </div>

      <div>
        <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12 }}>
          <span>Candidate fraction (of valid)</span>
          <span className="mono">{formatPercent(detectedPct)}</span>
        </div>
        <div className="bar">
          <span style={{ width: `${Math.min(100, detectedPct * 100)}%` }} />
        </div>
      </div>

      <div className="stat-grid">
        <div className="stat">
          <div className="label">Threshold</div>
          <div className="value" style={{ fontSize: 13 }}>
            {radToDeg(stats.threshold_rad).toFixed(2)}°
          </div>
        </div>
        <div className="stat">
          <div className="label">Mean SAM angle</div>
          <div className="value" style={{ fontSize: 13 }}>
            {stats.mean != null ? formatAngle(stats.mean) : '—'}
          </div>
        </div>
      </div>

      <div style={{ fontSize: 11, color: 'var(--text-dim)' }}>
        Total raster pixels: {formatInt(stats.pixel_count)} · reference: {stats.mineral}
      </div>
    </div>
  );
}
