import { useStore } from '@/store';
import { selectActiveResult } from '@/store/selectors';
import { formatLonLat, formatKm } from '@/utils/format';

export function StatusBar(): React.ReactElement {
  const hover = useStore((s) => s.hover);
  const height = useStore((s) => s.camera.height);
  const basemapId = useStore((s) => s.basemapId);
  const baseLayers = useStore((s) => s.baseLayers);
  const hasResult = useStore((s) => selectActiveResult(s) != null && s.overlayVisible);

  const basemap = baseLayers.find((l) => l.id === basemapId)?.title ?? '—';

  return (
    <footer className="status-bar">
      <span>
        Cursor:{' '}
        <span className="mono">{hover ? formatLonLat(hover.lon, hover.lat) : '—'}</span>
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
        <span className="caveat-chip">⚠ Candidate spectral matches only — not confirmed deposits</span>
      ) : null}
    </footer>
  );
}
