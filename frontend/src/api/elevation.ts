// Cursor elevation read-out — GET /api/elevation?lon=&lat= (not in the frozen v1
// contract). Returns metres, or null when unavailable (offline, nodata, error),
// so a failed lookup never breaks the UI.
import { apiFetch, isAbort } from './client';
import { env } from '@/env';

interface ElevationResponse {
  lon: number;
  lat: number;
  elevation_m: number | null;
  datum: string;
  source: string;
}

export async function getElevation(
  lon: number,
  lat: number,
  signal?: AbortSignal,
): Promise<number | null> {
  if (env.useMocks) return null; // no backend in offline mock mode
  try {
    const res = await apiFetch<ElevationResponse>('/api/elevation', {
      query: { lon, lat },
      signal,
    });
    return res.elevation_m;
  } catch (err) {
    if (isAbort(err)) throw err;
    return null;
  }
}
