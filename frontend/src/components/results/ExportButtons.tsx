import type { AnalysisResult, AssetRole } from '@/types';
import { downloadUrl } from '@/api/results';
import { env } from '@/env';

const ASSET_LABELS: Record<AssetRole, string> = {
  primary_metric: 'Primary metric (COG)',
  sam_angle: 'SAM angle (COG)',
  detection_mask: 'Detection mask (COG)',
  match_score: 'Match score (COG)',
};

/** Download links for each raster asset the result exposes (Cloud-Optimized GeoTIFF). */
export function ExportButtons({ result }: { result: AnalysisResult }): React.ReactElement {
  const roles: AssetRole[] = [];
  const { cog, angle, mask, score } = result.rasters;
  if (cog) roles.push('primary_metric');
  if (angle) roles.push('sam_angle');
  if (mask) roles.push('detection_mask');
  if (score) roles.push('match_score');

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
      <div style={{ fontSize: 12, fontWeight: 600 }}>Exports</div>
      {env.useMocks ? (
        <div style={{ fontSize: 11, color: 'var(--text-dim)' }}>
          Offline mock mode: GeoTIFF export requires the backend tiler and is disabled.
        </div>
      ) : (
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
          {roles.map((role) => (
            <a
              key={role}
              className="btn"
              href={downloadUrl(result.id, role)}
              target="_blank"
              rel="noreferrer"
              download
            >
              ⬇ {ASSET_LABELS[role]}
            </a>
          ))}
        </div>
      )}
    </div>
  );
}
