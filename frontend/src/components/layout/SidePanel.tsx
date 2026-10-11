import { useCallback, useRef } from 'react';
import { useStore } from '@/store';
import type { LeftPanelTab, RightPanelTab } from '@/store/types';
import { LayerExplorerPanel } from '@/components/panels/LayerExplorerPanel';
import { DataCataloguePanel } from '@/components/panels/DataCataloguePanel';
import { AnalysisPanel } from '@/components/panels/AnalysisPanel';
import { ResultsPanel } from '@/components/panels/ResultsPanel';
import { InspectorPanel } from '@/components/panels/InspectorPanel';

const LEFT_TABS: { id: LeftPanelTab; label: string }[] = [
  { id: 'layers', label: 'Layers' },
  { id: 'catalog', label: 'Catalogue' },
];
const RIGHT_TABS: { id: RightPanelTab; label: string }[] = [
  { id: 'analysis', label: 'Analysis' },
  { id: 'results', label: 'Results' },
  { id: 'inspector', label: 'Inspector' },
];

export function SidePanel({ side }: { side: 'left' | 'right' }): React.ReactElement {
  const panel = useStore((s) => s.panels[side]);
  const togglePanel = useStore((s) => s.togglePanel);
  const setLeftActive = useStore((s) => s.setPanelActive);
  const setRightActive = useStore((s) => s.setRightPanelActive);
  const setPanelWidth = useStore((s) => s.setPanelWidth);
  const dragging = useRef(false);

  const onDrag = useCallback(
    (startX: number, startWidth: number) => {
      dragging.current = true;
      const move = (e: MouseEvent): void => {
        if (!dragging.current) return;
        const delta = side === 'left' ? e.clientX - startX : startX - e.clientX;
        setPanelWidth(side, startWidth + delta);
      };
      const up = (): void => {
        dragging.current = false;
        window.removeEventListener('mousemove', move);
        window.removeEventListener('mouseup', up);
      };
      window.addEventListener('mousemove', move);
      window.addEventListener('mouseup', up);
    },
    [side, setPanelWidth],
  );

  const tabs = side === 'left' ? LEFT_TABS : RIGHT_TABS;

  return (
    <aside className={`side-panel ${side}`} style={{ width: panel.width }}>
      <div className="panel-tabs">
        {tabs.map((t) => (
          <button
            key={t.id}
            aria-pressed={panel.active === t.id}
            onClick={() =>
              side === 'left'
                ? setLeftActive('left', t.id as LeftPanelTab)
                : setRightActive(t.id as RightPanelTab)
            }
          >
            {t.label}
          </button>
        ))}
        <button
          className="icon-btn"
          style={{ marginLeft: 'auto' }}
          aria-label="Collapse panel"
          title="Collapse panel"
          onClick={() => togglePanel(side, false)}
        >
          {side === 'left' ? '‹' : '›'}
        </button>
      </div>

      <div style={{ flex: 1, minHeight: 0 }}>
        {side === 'left' && panel.active === 'layers' && <LayerExplorerPanel />}
        {side === 'left' && panel.active === 'catalog' && <DataCataloguePanel />}
        {side === 'right' && panel.active === 'analysis' && <AnalysisPanel />}
        {side === 'right' && panel.active === 'results' && <ResultsPanel />}
        {side === 'right' && panel.active === 'inspector' && <InspectorPanel />}
      </div>

      <div
        role="separator"
        aria-orientation="vertical"
        onMouseDown={(e) => onDrag(e.clientX, panel.width)}
        style={{
          position: 'absolute',
          top: 0,
          bottom: 0,
          right: side === 'left' ? 0 : undefined,
          left: side === 'right' ? 0 : undefined,
          width: 5,
          cursor: 'col-resize',
        }}
      />
    </aside>
  );
}
