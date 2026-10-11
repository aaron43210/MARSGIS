import { useState } from 'react';
import { useStore } from '@/store';
import { Button, ErrorBanner, Spinner } from '@/components/common';
import type { BBox } from '@/types';

// CRISM-rich regions spanning the planet — picking any one proves whole-Mars
// discovery, not just the seeded Nili Fossae scenes.
const REGIONS: { label: string; bbox: BBox }[] = [
  { label: 'Nili Fossae', bbox: [74, 20, 78, 24] },
  { label: 'Jezero Crater', bbox: [76.5, 17.5, 78.6, 19.2] },
  { label: 'Mawrth Vallis', bbox: [-20, 22, -16, 26] },
  { label: 'Gale Crater', bbox: [136.5, -6, 138.6, -4] },
  { label: 'Meridiani Planum', bbox: [-5, -4, 1, 2] },
  { label: 'Valles Marineris (W)', bbox: [-80, -14, -60, -2] },
  { label: 'Hellas rim', bbox: [60, -45, 75, -33] },
];

/** Live catalogue discovery: query the NASA PDS archive (ODE) for real CRISM
 * products anywhere on Mars and merge them onto the map. */
export function DiscoverRegions(): React.ReactElement {
  const [idx, setIdx] = useState(0);
  const discover = useStore((s) => s.discover);
  const status = useStore((s) => s.discoverStatus);
  const error = useStore((s) => s.discoverError);
  const last = useStore((s) => s.lastDiscovery);
  const region = REGIONS[idx]!;

  return (
    <div
      className="field"
      style={{ borderTop: '1px solid var(--border)', paddingTop: 10, marginTop: 6 }}
    >
      <span style={{ fontWeight: 600 }}>Discover across Mars</span>
      <span style={{ fontSize: 11, color: 'var(--text-dim)' }}>
        Query the live NASA PDS archive (ODE) for real CRISM scenes in a region and add them to the
        catalogue. Metadata + footprints only — cubes download on demand.
      </span>
      <select
        aria-label="Discovery region"
        value={idx}
        onChange={(e) => setIdx(Number(e.target.value))}
      >
        {REGIONS.map((r, i) => (
          <option key={r.label} value={i}>
            {r.label}
          </option>
        ))}
      </select>
      <Button block disabled={status === 'loading'} onClick={() => void discover(region.bbox, region.label)}>
        {status === 'loading' ? 'Discovering…' : `Discover CRISM in ${region.label}`}
      </Button>
      {status === 'loading' ? <Spinner label="Querying PDS ODE" /> : null}
      {status === 'error' && error ? <ErrorBanner message={error} /> : null}
      {status === 'ready' && last ? (
        <span style={{ fontSize: 11, color: 'var(--text-dim)' }}>
          Found {last.found} scene{last.found === 1 ? '' : 's'} in {last.label}.{' '}
          {last.found > 0 ? 'Flew to the first — click any card or footprint.' : 'Try another region.'}
        </span>
      ) : null}
    </div>
  );
}
