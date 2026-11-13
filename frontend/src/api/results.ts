// Result endpoints (frozen contract).
//   GET /api/results/{id}                      -> AnalysisResult
//   GET /api/results/{id}/download?asset=...    -> COG GeoTIFF (media URL)
//   GET /api/results/{id}/tiles/{z}/{x}/{y}.png -> rendered tile (media URL template)
//   GET /api/results/{id}/pixel?lon=&lat=        -> ResultPixel (real spectrum + angle)
//   GET /api/provenance/{id}                    -> Provenance
import { apiFetch, mediaUrl } from './client';
import { zAnalysisResult, zResultPixel } from './validators';
import { API_ROUTES } from '@/types';
import type { AnalysisResult, AssetRole, ResultPixel } from '@/types';

export async function getResult(id: string, signal?: AbortSignal): Promise<AnalysisResult> {
  return apiFetch<AnalysisResult>(API_ROUTES.result(id), { signal, schema: zAnalysisResult });
}

/** The real spectrum and SAM angle of the result pixel under lon/lat. */
export async function getResultPixel(
  id: string,
  lon: number,
  lat: number,
  signal?: AbortSignal,
): Promise<ResultPixel> {
  return apiFetch<ResultPixel>(API_ROUTES.resultPixel(id), {
    signal,
    query: { lon, lat },
    schema: zResultPixel,
  });
}

/** Absolute URL for a downloadable raster asset (opened in a new tab / anchor href). */
export function downloadUrl(id: string, asset: AssetRole = 'primary_metric'): string {
  return mediaUrl(`${API_ROUTES.resultDownload(id)}?asset=${encodeURIComponent(asset)}`);
}
