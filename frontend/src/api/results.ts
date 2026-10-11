// Result endpoints (frozen contract).
//   GET /api/results/{id}                      -> AnalysisResult
//   GET /api/results/{id}/download?asset=...    -> COG GeoTIFF (media URL)
//   GET /api/results/{id}/tiles/{z}/{x}/{y}.png -> rendered tile (media URL template)
//   GET /api/provenance/{id}                    -> Provenance
import { apiFetch, mediaUrl } from './client';
import { zAnalysisResult } from './validators';
import { API_ROUTES } from '@/types';
import type { AnalysisResult, AssetRole, Provenance } from '@/types';

export async function getResult(id: string, signal?: AbortSignal): Promise<AnalysisResult> {
  return apiFetch<AnalysisResult>(API_ROUTES.result(id), { signal, schema: zAnalysisResult });
}

/** Absolute URL for a downloadable raster asset (opened in a new tab / anchor href). */
export function downloadUrl(id: string, asset: AssetRole = 'primary_metric'): string {
  return mediaUrl(`${API_ROUTES.resultDownload(id)}?asset=${encodeURIComponent(asset)}`);
}

/** Tile URL template for Cesium (zxy, geographic). {z}/{x}/{y} are left for Cesium to fill. */
export function tileTemplate(id: string): string {
  return mediaUrl(API_ROUTES.resultTiles(id));
}

export async function getProvenance(id: string, signal?: AbortSignal): Promise<Provenance> {
  return apiFetch<Provenance>(API_ROUTES.provenance(id), { signal });
}
