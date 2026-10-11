import { TopBar } from './TopBar';
import { StatusBar } from './StatusBar';
import { SidePanel } from './SidePanel';
import { useStore } from '@/store';

/**
 * Dock layout grid floating over the globe. The center column is pointer-events:none so the
 * globe stays interactive; panels re-enable pointer events.
 */
export function AppShell(): React.ReactElement {
  const leftOpen = useStore((s) => s.panels.left.open);
  const rightOpen = useStore((s) => s.panels.right.open);
  const togglePanel = useStore((s) => s.togglePanel);

  return (
    <div className="app-shell">
      <TopBar />

      {leftOpen ? (
        <SidePanel side="left" />
      ) : (
        <button
          className="panel-collapse-tab left"
          aria-label="Open left panel"
          title="Open left panel"
          onClick={() => togglePanel('left', true)}
        >
          ›
        </button>
      )}

      <div className="center-spacer" />

      {rightOpen ? (
        <SidePanel side="right" />
      ) : (
        <button
          className="panel-collapse-tab right"
          aria-label="Open right panel"
          title="Open right panel"
          onClick={() => togglePanel('right', true)}
        >
          ‹
        </button>
      )}

      <StatusBar />
    </div>
  );
}
