import { useStore } from '@/store';
import type { AreaSize } from '@/types';

/** Rough download sizes for a typical CRISM image (843 px wide, 489 bands). */
const OPTIONS: { value: AreaSize; label: string; hint: string }[] = [
  { value: 'small', label: 'Small strip — 48 rows', hint: '~80 MB · about 1–3 min' },
  { value: 'medium', label: 'Medium strip — 128 rows', hint: '~210 MB · about 4–8 min' },
  { value: 'large', label: 'Large strip — 256 rows', hint: '~420 MB · about 8–15 min' },
  { value: 'full', label: 'Whole image', hint: '~1.4 GB · about 25–45 min' },
];

/**
 * How much of the observation to analyse. Every option spans the image's full width;
 * bigger areas stream more rows from NASA. Times are for a slow (~0.5 MB/s) connection;
 * an area already downloaded once runs again instantly.
 */
export function AreaSizeSelect(): React.ReactElement {
  const area = useStore((s) => s.config.area);
  const setArea = useStore((s) => s.setArea);
  const current = OPTIONS.find((o) => o.value === area) ?? OPTIONS[0]!;
  return (
    <label className="field">
      <span>Area to analyse</span>
      <select
        value={area}
        onChange={(e) => setArea(e.target.value as AreaSize)}
        aria-label="Area to analyse"
      >
        {OPTIONS.map((o) => (
          <option key={o.value} value={o.value}>
            {o.label}
          </option>
        ))}
      </select>
      <small style={{ color: 'var(--text-dim)' }}>
        Full image width. {current.hint}; re-running the same area is instant.
      </small>
    </label>
  );
}
