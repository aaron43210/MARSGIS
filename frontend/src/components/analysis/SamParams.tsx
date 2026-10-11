import { useStore } from '@/store';
import { radToDeg, degToRad } from '@/utils/format';

const DEFAULT_THRESHOLD_RAD = 0.1;

/** SAM spectral-angle threshold. Shown in degrees; stored in radians (contract unit). */
export function SamParams(): React.ReactElement {
  const thresholdRad = useStore((s) => s.config.params.threshold_rad ?? DEFAULT_THRESHOLD_RAD);
  const setThresholdRad = useStore((s) => s.setThresholdRad);
  const thresholdDeg = radToDeg(thresholdRad);

  return (
    <div className="field">
      <span>
        Detection threshold: <strong>{thresholdDeg.toFixed(2)}°</strong> ({thresholdRad.toFixed(3)} rad)
      </span>
      <input
        type="range"
        min={0.5}
        max={20}
        step={0.1}
        value={thresholdDeg}
        aria-label="SAM threshold (degrees)"
        onChange={(e) => setThresholdRad(degToRad(Number(e.target.value)))}
      />
      <span style={{ fontSize: 11, color: 'var(--text-dim)' }}>
        A pixel is a candidate when its spectral angle to the reference is at or below this
        threshold. Lower = stricter. Default {radToDeg(DEFAULT_THRESHOLD_RAD).toFixed(2)}°.
      </span>
    </div>
  );
}
