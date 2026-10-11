import { useCallback } from 'react';
import { useStore } from '@/store';

/** Bridge result-pixel clicks to the inspector; guards when no active result exists. */
export function usePixelInspector(): {
  inspect: (lon: number, lat: number) => void;
  enabled: boolean;
} {
  const activeResultId = useStore((s) => s.activeResultId);
  const inspectPixel = useStore((s) => s.inspectPixel);

  const inspect = useCallback(
    (lon: number, lat: number) => {
      if (!activeResultId) return;
      void inspectPixel(activeResultId, lon, lat);
    },
    [activeResultId, inspectPixel],
  );

  return { inspect, enabled: activeResultId != null };
}
