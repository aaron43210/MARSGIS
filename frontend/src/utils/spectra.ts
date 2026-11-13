/**
 * Divide a spectrum by its own mean so curves of very different brightness share one
 * scale. SAM compares shape only (brightness cancels), so this is the honest picture
 * of what it compared; nulls (no data) stay as gaps.
 */
export function toRelative(values: (number | null)[]): (number | null)[] {
  const finite = values.filter((v): v is number => v != null && Number.isFinite(v));
  const mean = finite.reduce((a, b) => a + b, 0) / (finite.length || 1);
  if (!mean) return values;
  return values.map((v) => (v == null || !Number.isFinite(v) ? null : v / mean));
}
