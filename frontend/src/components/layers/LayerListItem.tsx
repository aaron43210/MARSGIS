import { useStore } from '@/store';
import type { LayerEntry } from '@/store/types';
import { OpacitySlider } from './OpacitySlider';
import { IconButton, Badge } from '@/components/common';

export function LayerListItem({ entry }: { entry: LayerEntry }): React.ReactElement {
  const setVisible = useStore((s) => s.setLayerVisible);
  const setOpacity = useStore((s) => s.setLayerOpacity);
  const removeOverlay = useStore((s) => s.removeOverlay);

  return (
    <div className="layer-row">
      <input
        type="checkbox"
        checked={entry.visible}
        aria-label={`Toggle ${entry.layer.title}`}
        onChange={(e) => setVisible(entry.id, e.target.checked)}
      />
      <div className="grow">
        <div className="name" title={entry.layer.attribution}>
          {entry.layer.title}
        </div>
        <OpacitySlider value={entry.opacity} onChange={(v) => setOpacity(entry.id, v)} />
      </div>
      <Badge>{entry.layer.type}</Badge>
      {entry.removable ? (
        <IconButton label={`Remove ${entry.layer.title}`} onClick={() => removeOverlay(entry.id)}>
          ✕
        </IconButton>
      ) : null}
    </div>
  );
}
