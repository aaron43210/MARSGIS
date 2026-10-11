import { useEffect } from 'react';
import { useStore } from '@/store';
import type { AsyncStatus } from '@/store/types';

/**
 * Loads observations when entering a mode that needs footprints, and whenever filters change.
 * Returns the current catalogue async status for the panel to render.
 */
export function useCatalog(): { status: AsyncStatus; error: string | null } {
  const mode = useStore((s) => s.mode);
  const filters = useStore((s) => s.filters);
  const loadObservations = useStore((s) => s.loadObservations);
  const status = useStore((s) => s.observationsStatus);
  const error = useStore((s) => s.observationsError);

  useEffect(() => {
    if (mode === 'observations' || mode === 'analysis' || mode === 'results') {
      void loadObservations();
    }
  }, [mode, filters, loadObservations]);

  return { status, error };
}
