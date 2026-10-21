import { CANDIDATE_MATCH_CAVEAT } from '@/types';
import { formatDeg } from '@/utils/format';

/** Spectral angle + mandatory candidate caveat. Color is muted (never a confident "detected"). */
export function SpectralAngleBadge({
  angleDeg,
  classLabel,
  synthetic,
}: {
  angleDeg: number | null;
  classLabel: string;
  synthetic: boolean;
}): React.ReactElement {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
        <span className="badge" style={{ borderColor: 'var(--warn)', color: 'var(--warn)' }}>
          {classLabel}
        </span>
        <span style={{ fontSize: 13 }}>
          SAM angle: <strong>{angleDeg != null ? formatDeg(angleDeg) : 'n/a'}</strong>
        </span>
        {synthetic ? <span className="badge syn">SYNTHETIC (offline sample)</span> : null}
      </div>
      <div className="caveat" role="note">
        <strong>Candidate spectral match — not a confirmed mineral deposit. </strong>
        {CANDIDATE_MATCH_CAVEAT}
      </div>
    </div>
  );
}
