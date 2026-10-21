import { useEffect, useRef, useState } from 'react';
import { useStore } from '@/store';
import { selectActiveResult } from '@/store/selectors';
import { formatLonLat, formatKm } from '@/utils/format';
import { getElevation } from '@/api/elevation';

export function StatusBar(): React.ReactElement {
  const hover = useStore((s) => s.hover);
  const height = useStore((s) => s.camera.height);
  const basemapId = useStore((s) => s.basemapId);
  const baseLayers = useStore((s) => s.baseLayers);
  const hasResult = useStore((s) => selectActiveResult(s) != null && s.overlayVisible);

  const basemap = baseLayers.find((l) => l.id === basemapId)?.title ?? '—';

  // Live MOLA elevation at the cursor. undefined = fetching/unknown, null = unavailable.
  const [elev, setElev] = useState<number | null | undefined>(undefined);
  const abortRef = useRef<AbortController | null>(null);
  const lon = hover?.lon ?? null;
  const lat = hover?.lat ?? null;

  useEffect(() => {
    if (lon === null || lat === null) return; // footer shows '—' via the !hover guard
    const timer = setTimeout(() => {
      setElev(undefined); // reset inside the timer callback, not synchronously in the effect body
      abortRef.current?.abort();
      const ac = new AbortController();
      abortRef.current = ac;
      void getElevation(lon, lat, ac.signal)
        .then((m) => setElev(m))
        .catch(() => {
          /* aborted or failed — leave as unknown */
        });
    }, 220);
    return () => clearTimeout(timer);
  }, [lon, lat]);

  const elevText = !hover
    ? '—'
    : elev === undefined
      ? '…'
      : elev === null
        ? '—'
        : `${Math.round(elev).toLocaleString()} m`;

  return (
    <footer className="status-bar">
      <span>
        Cursor: <span className="mono">{hover ? formatLonLat(hover.lon, hover.lat) : '—'}</span>
      </span>
      <span>
        Elev:{' '}
        <span className="mono" title="MOLA 463 m global DEM">
          {elevText}
        </span>
      </span>
      <span>
        Camera: <span className="mono">{formatKm(height)}</span>
      </span>
      <span>
        Basemap: <span className="mono">{basemap}</span>
      </span>
      <span>
        CRS: <span className="mono">Mars IAU 2000 (east-positive)</span>
      </span>
      {hasResult ? (
        <span className="caveat-chip">
          ⚠ Candidate spectral matches only — not confirmed deposits
        </span>
      ) : null}
    </footer>
  );
}
