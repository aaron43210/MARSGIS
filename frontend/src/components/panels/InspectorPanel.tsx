import { useStore } from '@/store';
import { Panel } from '@/components/common/Panel';
import { Button, ErrorBanner, Spinner } from '@/components/common';
import { SpectrumChart, type SpectrumSeries } from '@/components/inspector/SpectrumChart';
import { SpectralAngleBadge } from '@/components/inspector/SpectralAngleBadge';
import { formatLonLat } from '@/utils/format';
import { SERIES_COLORS } from '@/config/constants';

/** Pixel/Spectrum inspector. Opens when a result pixel is clicked (Results mode). */
export function InspectorPanel(): React.ReactElement {
  const open = useStore((s) => s.open);
  const status = useStore((s) => s.inspectorStatus);
  const error = useStore((s) => s.inspectorError);
  const point = useStore((s) => s.point);
  const reference = useStore((s) => s.reference);
  const observed = useStore((s) => s.observed);
  const clearInspector = useStore((s) => s.clearInspector);

  if (!open) {
    return (
      <Panel title="Pixel inspector">
        <div style={{ color: 'var(--text-dim)', fontSize: 12 }}>
          In Results mode, click a pixel on the result overlay to inspect its spectral angle and
          compare it against the reference spectrum.
        </div>
      </Panel>
    );
  }

  const series: SpectrumSeries[] = [];
  let xGrid: number[] = [];
  if (reference) {
    xGrid = reference.wavelength;
    series.push({
      label: `Reference: ${reference.mineral}`,
      color: reference.color || SERIES_COLORS.reference,
      y: reference.reflectance,
    });
  }
  if (observed && reference && observed.wavelength_nm.length === reference.wavelength.length) {
    series.push({
      label: 'Observed pixel (synthetic)',
      color: SERIES_COLORS.observed,
      y: observed.reflectance,
    });
  }

  return (
    <Panel
      title="Pixel inspector"
      actions={
        <Button onClick={clearInspector} style={{ padding: '2px 8px' }}>
          Close
        </Button>
      }
    >
      {point ? (
        <div style={{ fontSize: 12 }}>
          Location: <span className="mono">{formatLonLat(point.lon, point.lat, 3)}</span>
        </div>
      ) : null}

      {status === 'loading' ? <Spinner label="Loading spectrum" /> : null}
      {status === 'error' && error ? <ErrorBanner message={error} /> : null}

      {status === 'ready' && reference ? (
        <>
          <SpectralAngleBadge
            angleDeg={observed?.angle_deg ?? null}
            classLabel={reference.mineral}
            synthetic={observed?.synthetic ?? false}
          />

          {xGrid.length > 0 ? <SpectrumChart x={xGrid} series={series} /> : null}

          {!observed ? (
            <div style={{ fontSize: 11, color: 'var(--text-dim)' }}>
              The v1 API does not expose per-pixel observed spectra, so the plot shows the reference
              target spectrum only. The result overlay encodes the per-pixel SAM angle; use the
              legend and statistics to interpret this location.
            </div>
          ) : null}
        </>
      ) : null}
    </Panel>
  );
}
