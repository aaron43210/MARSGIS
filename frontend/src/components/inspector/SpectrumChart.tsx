import { useEffect, useRef } from 'react';
import uPlot from 'uplot';
import 'uplot/dist/uPlot.min.css';

export interface SpectrumSeries {
  label: string;
  color: string;
  /** y values aligned to the shared `x` wavelength grid. */
  y: number[];
}

export interface SpectrumChartProps {
  /** Shared x axis (wavelength, nm). */
  x: number[];
  series: SpectrumSeries[];
  height?: number;
}

function cssVar(name: string, fallback: string): string {
  if (typeof window === 'undefined') return fallback;
  const v = getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  return v || fallback;
}

/** Thin imperative uPlot wrapper for reflectance-vs-wavelength plots. */
export function SpectrumChart({ x, series, height = 240 }: SpectrumChartProps): React.ReactElement {
  const hostRef = useRef<HTMLDivElement | null>(null);
  const plotRef = useRef<uPlot | null>(null);

  useEffect(() => {
    const host = hostRef.current;
    if (!host) return;

    const grid = cssVar('--border', '#2a3140');
    const text = cssVar('--text-dim', '#8b93a7');

    const opts: uPlot.Options = {
      width: host.clientWidth || 320,
      height,
      scales: { x: { time: false } },
      legend: { show: true },
      axes: [
        {
          label: 'Wavelength (nm)',
          stroke: text,
          grid: { stroke: grid, width: 1 },
          ticks: { stroke: grid },
        },
        {
          label: 'Reflectance (I/F, continuum-removed)',
          stroke: text,
          grid: { stroke: grid, width: 1 },
          ticks: { stroke: grid },
        },
      ],
      series: [
        {},
        ...series.map((s) => ({
          label: s.label,
          stroke: s.color,
          width: 2,
          points: { show: false },
        })),
      ],
    };

    const data: uPlot.AlignedData = [x, ...series.map((s) => s.y)];
    const plot = new uPlot(opts, data, host);
    plotRef.current = plot;

    const ro = new ResizeObserver(() => {
      plot.setSize({ width: host.clientWidth || 320, height });
    });
    ro.observe(host);

    return () => {
      ro.disconnect();
      plot.destroy();
      plotRef.current = null;
    };
    // Rebuild when the series shape changes (labels/colors/count) or x identity changes.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [x, series.map((s) => `${s.label}:${s.color}:${s.y.length}`).join('|'), height]);

  return <div className="chart-host" ref={hostRef} />;
}
