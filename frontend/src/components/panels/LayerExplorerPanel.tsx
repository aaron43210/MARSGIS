import { useStore } from '@/store';
import { Panel } from '@/components/common/Panel';
import { LayerListItem } from '@/components/layers/LayerListItem';
import { ErrorBanner, Spinner } from '@/components/common';

export function LayerExplorerPanel(): React.ReactElement {
  const baseLayers = useStore((s) => s.baseLayers);
  const basemapId = useStore((s) => s.basemapId);
  const setBasemap = useStore((s) => s.setBasemap);
  const overlays = useStore((s) => s.overlays);
  const overlayCatalog = useStore((s) => s.overlayCatalog);
  const addOverlay = useStore((s) => s.addOverlay);
  const status = useStore((s) => s.catalogStatus);
  const error = useStore((s) => s.catalogError);

  const availableToAdd = overlayCatalog.filter((l) => !overlays.some((o) => o.id === l.id));
  // Overlays are shown top-first (reverse of bottom->top stacking order).
  const ordered = [...overlays].sort((a, b) => b.order - a.order);

  return (
    <Panel title="Layers">
      {status === 'loading' ? <Spinner label="Loading layer catalogue" /> : null}
      {status === 'error' && error ? (
        <ErrorBanner message={`${error} Showing verified Trek basemaps only.`} />
      ) : null}

      <div>
        <div style={{ fontSize: 12, fontWeight: 600, marginBottom: 6 }}>Base map</div>
        <div className="list">
          {baseLayers.map((l) => (
            <label key={l.id} className="layer-row" style={{ cursor: 'pointer' }}>
              <input
                type="radio"
                name="basemap"
                checked={basemapId === l.id}
                onChange={() => setBasemap(l.id)}
              />
              <div className="grow">
                <div className="name">{l.title}</div>
                <div className="meta" style={{ fontSize: 11, color: 'var(--text-dim)' }}>
                  {l.subtitle ?? l.source.provider} · {l.availability.status}
                </div>
              </div>
            </label>
          ))}
        </div>
      </div>

      <div>
        <div style={{ fontSize: 12, fontWeight: 600, marginBottom: 6 }}>Overlays</div>
        {ordered.length === 0 ? (
          <div style={{ color: 'var(--text-dim)', fontSize: 12 }}>No overlays added.</div>
        ) : (
          <div className="list">
            {ordered.map((entry) => (
              <LayerListItem key={entry.id} entry={entry} />
            ))}
          </div>
        )}
      </div>

      {availableToAdd.length > 0 ? (
        <label className="field">
          <span>Add overlay</span>
          <select
            value=""
            onChange={(e) => {
              const layer = overlayCatalog.find((l) => l.id === e.target.value);
              if (layer) addOverlay(layer);
            }}
          >
            <option value="" disabled>
              Choose a context/geology layer…
            </option>
            {availableToAdd.map((l) => (
              <option key={l.id} value={l.id}>
                {l.title}
              </option>
            ))}
          </select>
        </label>
      ) : null}
    </Panel>
  );
}
