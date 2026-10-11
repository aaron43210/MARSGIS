// Gazetteer search.
//
// NOTE: the frozen API contract (contracts/openapi.yaml) exposes NO gazetteer endpoint, so
// this is a bundled static list of real IAU planetary nomenclature (src/data/*.json), filtered
// client-side. These are published feature names/locations, not analysis data — no caveat needed.
// Seeded so that typing "nili" surfaces Nili Fossae.
import type { GazetteerFeature } from '@/store/types';
import features from '@/data/nili-fossae-features.json';

const ALL: GazetteerFeature[] = features;

export function searchGazetteer(query: string, limit = 10): GazetteerFeature[] {
  const q = query.trim().toLowerCase();
  if (!q) return [];
  const scored = ALL.map((f) => {
    const name = f.name.toLowerCase();
    const clean = f.cleanName.toLowerCase();
    let score = -1;
    if (name === q || clean === q) score = 0;
    else if (name.startsWith(q) || clean.startsWith(q)) score = 1;
    else if (name.includes(q) || clean.includes(q)) score = 2;
    return { f, score };
  }).filter((s) => s.score >= 0);
  scored.sort((a, b) => a.score - b.score || a.f.name.localeCompare(b.f.name));
  return scored.slice(0, limit).map((s) => s.f);
}

export function allFeatures(): GazetteerFeature[] {
  return ALL;
}
