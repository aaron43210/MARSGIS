// Legend/colormap helpers for rendering result & quality legends from contract metadata.
import type { Legend, LegendStop } from '@/types';

/** Build a CSS linear-gradient from ordered legend stops (continuous legends). */
export function stopsToCssGradient(stops: LegendStop[]): string {
  if (stops.length === 0) return 'linear-gradient(to right, #000, #fff)';
  const range = valueRange(stops);
  const parts = stops.map((s, i) => {
    const pct =
      s.value != null && range
        ? ((s.value - range[0]) / (range[1] - range[0] || 1)) * 100
        : (i / Math.max(1, stops.length - 1)) * 100;
    return `${s.color} ${clampPct(pct)}%`;
  });
  return `linear-gradient(to right, ${parts.join(', ')})`;
}

function valueRange(stops: LegendStop[]): [number, number] | null {
  const values = stops.map((s) => s.value).filter((v): v is number => v != null);
  if (values.length < 2) return null;
  return [Math.min(...values), Math.max(...values)];
}

function clampPct(p: number): number {
  return Math.max(0, Math.min(100, p));
}

interface Swatch {
  color: string;
  label: string;
}

/** Discrete/categorical swatch rows. */
export function discreteSwatches(legend: Legend): Swatch[] {
  return legend.stops.map((s) => ({ color: s.color, label: s.label }));
}
