import { useStore } from '@/store';
import { Panel } from '@/components/common/Panel';
import { Button, ErrorBanner, Spinner } from '@/components/common';
import { SpectrumChart, type SpectrumSeries } from '@/components/inspector/SpectrumChart';
import { SpectralAngleBadge } from '@/components/inspector/SpectralAngleBadge';
import { formatLonLat } from '@/utils/format';
import { toRelative } from '@/utils/spectra';
import { SERIES_COLORS } from '@/config/constants';

const RAD_TO_DEG = 180 / Math.PI;

/** Pixel/Spectrum inspector. Opens when a result pixel is clicked (Results mode). */
export function InspectorPanel(): React.ReactElement {
  const open = useStore((s) => s.open);
  const status = useStore((s) => s.inspectorStatus);
  const error = useStore((s) => s.inspectorError);
  const point = useStore((s) => s.point);
  const reference = useStore((s) => s.reference);
  const pixel = useStore((s) => s.pixel);
  const clearInspector = useStore((s) => s.clearInspector);

  if (!open) {
    return (
      <Panel title="Pixel inspector">
        <div style={{ color: 'var(--text-dim)', fontSize: 12 }}>
          In Results mode, click a pixel on the result overlay to see its real spectrum and its
          spectral angle against the reference.
        </div>
      </Panel>
    );
  }

  // Both curves come from the backend on the exact bands SAM used (continuum-removed when
  // the analysis used continuum removal), so the plot shows what SAM actually compared.
  const series: SpectrumSeries[] = [];
  if (pixel?.inside) {
    series.push({
      label: `Reference: ${reference?.mineral ?? pixel.mineral}`,
      color: reference?.color || SERIES_COLORS.reference,
      y: toRelative(pixel.reference),
    });
    series.push({
      label: `This pixel (row ${pixel.row}, col ${pixel.col})`,
      color: SERIES_COLORS.observed,
      y: toRelative(pixel.pixel),
    });
  }
  const angleDeg = pixel?.angle_rad != null ? pixel.angle_rad * RAD_TO_DEG : null;

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

      {status === 'loading' ? <Spinner label="Reading the pixel spectrum" /> : null}
      {status === 'error' && error ? <ErrorBanner message={error} /> : null}

      {status === 'ready' && pixel && !pixel.inside ? (
        <div style={{ fontSize: 12, color: 'var(--text-dim)' }}>
          This point is outside the analysed area. Click inside the result overlay.
        </div>
      ) : null}

      {status === 'ready' && pixel?.inside ? (
        <>
          <SpectralAngleBadge
            angleDeg={angleDeg}
            classLabel={reference?.mineral ?? pixel.mineral}
            synthetic={pixel.synthetic_input}
          />
          <div style={{ fontSize: 12 }}>
            {pixel.is_candidate ? (
              <strong style={{ color: 'var(--warn)' }}>Below the threshold: candidate.</strong>
            ) : (
              <span>Above the threshold: not a match.</span>
            )}{' '}
            {pixel.threshold_rad != null ? (
              <span className="mono">
                (threshold {(pixel.threshold_rad * RAD_TO_DEG).toFixed(2)}°)
              </span>
            ) : null}
          </div>
          {pixel.wavelength_nm.length > 0 ? (
            <SpectrumChart
              x={pixel.wavelength_nm}
              series={series}
              yLabel="Relative value (÷ own mean)"
            />
          ) : null}
          <div style={{ fontSize: 11, color: 'var(--text-dim)' }}>
            Shapes compared on {pixel.wavelength_nm.length} bands SAM used
            {pixel.window_nm ? ` (${pixel.window_nm[0]}–${pixel.window_nm[1]} nm)` : ''}
            {pixel.band_depth
              ? ': absorption depth, so dips in the spectrum show as peaks.'
              : pixel.continuum_removed
                ? ' (continuum-removed).'
                : '.'}{' '}
            Each curve is divided by its own average so their shapes can be compared; brightness
            does not affect the SAM angle.
          </div>
        </>
      ) : null}
    </Panel>
  );
}
