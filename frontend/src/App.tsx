import { useEffect } from 'react';
import { GlobeView } from '@/components/GlobeView';
import { AppShell } from '@/components/layout/AppShell';
import { useUrlSync } from '@/hooks/useUrlSync';
import { useAnalysisJob } from '@/hooks/useAnalysisJob';
import { useStore } from '@/store';

/**
 * Top-level composition. GlobeView mounts ONCE as a persistent full-viewport background and is
 * never conditionally unmounted across workspace modes; AppShell (dock panels) floats above it.
 */
export default function App(): React.ReactElement {
  const loadLayers = useStore((s) => s.loadLayers);
  const loadMinerals = useStore((s) => s.loadMinerals);
  const loadObservations = useStore((s) => s.loadObservations);

  useUrlSync();
  useAnalysisJob();

  // Initial data load (layer catalogue, reference library, Nili Fossae observations).
  useEffect(() => {
    void loadLayers();
    void loadMinerals();
    void loadObservations();
  }, [loadLayers, loadMinerals, loadObservations]);

  return (
    <>
      <GlobeView />
      <AppShell />
    </>
  );
}
