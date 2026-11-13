import { useStore } from '@/store';
import { radToDeg, degToRad } from '@/utils/format';

// Band-depth matching (the server default) separates minerals at ~0.30 rad.
const DEFAULT_THRESHOLD_RAD = 0.3;

/** SAM spectral-angle threshold. Shown in degrees; stored in radians (contract unit). */
export function SamParams(): React.ReactElement {
  const thresholdRad = useStore((s) => s.config.params.threshold_rad ?? DEFAULT_THRESHOLD_RAD);
  const setThresholdRad = useStore((s) => s.setThresholdRad);
  const thresholdDeg = radToDeg(thresholdRad);

  return (
    <div className="field">
      <span>
        Detection threshold: <strong>{thresholdDeg.toFixed(2)}°</strong> ({thresholdRad.toFixed(3)}{' '}
        rad)
      </span>
      <input
        type="range"
        min={0.5}
        max={40}
        step={0.1}
        value={thresholdDeg}
        aria-label="SAM threshold (degrees)"
        onChange={(e) => setThresholdRad(degToRad(Number(e.target.value)))}
      />
      <span style={{ fontSize: 11, color: 'var(--text-dim)' }}>
        Each pixel's absorption bands (in the mineral's own wavelength window) are compared with the
        reference. A pixel is a candidate when the angle is at or below this threshold. Lower =
        stricter. Default {radToDeg(DEFAULT_THRESHOLD_RAD).toFixed(2)}°.
      </span>
    </div>
  );
}
