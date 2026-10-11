import { useStore } from '@/store';
import type { WorkspaceMode } from '@/store/types';

const MODES: { id: WorkspaceMode; label: string }[] = [
  { id: 'explore', label: 'Explore' },
  { id: 'observations', label: 'Observations' },
  { id: 'analysis', label: 'Analysis' },
  { id: 'results', label: 'Results' },
];

export function ModeTabs(): React.ReactElement {
  const mode = useStore((s) => s.mode);
  const setMode = useStore((s) => s.setMode);
  return (
    <div className="mode-tabs" role="tablist" aria-label="Workspace mode">
      {MODES.map((m) => (
        <button
          key={m.id}
          role="tab"
          aria-pressed={mode === m.id}
          aria-selected={mode === m.id}
          onClick={() => setMode(m.id)}
        >
          {m.label}
        </button>
      ))}
    </div>
  );
}
