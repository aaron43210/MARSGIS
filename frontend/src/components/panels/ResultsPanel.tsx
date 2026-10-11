import { useStore } from '@/store';
import { selectActiveResult } from '@/store/selectors';
import { Panel } from '@/components/common/Panel';
import { Toggle, CaveatBlock, ErrorBanner, Spinner } from '@/components/common';
import { OpacitySlider } from '@/components/layers/OpacitySlider';
import { Legend } from '@/components/layers/Legend';
import { ResultList } from '@/components/results/ResultList';
import { ClassStats } from '@/components/results/ClassStats';
import { ExportButtons } from '@/components/results/ExportButtons';

/** Screen 4: result overlay control, legend, stats, exports. */
export function ResultsPanel(): React.ReactElement {
  const result = useStore(selectActiveResult);
  const overlayVisible = useStore((s) => s.overlayVisible);
  const overlayOpacity = useStore((s) => s.overlayOpacity);
  const setOverlayVisible = useStore((s) => s.setOverlayVisible);
  const setOverlayOpacity = useStore((s) => s.setOverlayOpacity);
  const loadStatus = useStore((s) => s.loadStatus);
  const loadError = useStore((s) => s.loadError);

  return (
    <Panel title="Results & exports">
      {loadStatus === 'loading' ? <Spinner label="Loading result" /> : null}
      {loadStatus === 'error' && loadError ? <ErrorBanner message={loadError} /> : null}

      <ResultList />

      {result ? (
        <>
          <CaveatBlock text={result.caveat} />

          <div className="layer-row">
            <Toggle checked={overlayVisible} onChange={setOverlayVisible} label="Overlay" />
            <OpacitySlider value={overlayOpacity} onChange={setOverlayOpacity} label="Overlay opacity" />
          </div>

          <Legend legend={result.legend} />
          <ClassStats stats={result.summary_stats} />
          <ExportButtons result={result} />

          <div style={{ fontSize: 11, color: 'var(--text-dim)' }}>
            Tip: in Results mode, click a pixel on the overlay to inspect its spectrum.
          </div>
        </>
      ) : (
        <div style={{ color: 'var(--text-dim)', fontSize: 12 }}>
          Select a result above, or run an analysis to produce one.
        </div>
      )}
    </Panel>
  );
}
