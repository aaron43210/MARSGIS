import { ModeTabs } from './ModeTabs';
import { GazetteerSearch } from '@/components/search/GazetteerSearch';
import { useStore } from '@/store';
import { allFeatures } from '@/api/gazetteer';
import { CrosshairIcon } from '@/components/common';

export function TopBar(): React.ReactElement {
  const baseLayers = useStore((s) => s.baseLayers);
  const basemapId = useStore((s) => s.basemapId);
  const setBasemap = useStore((s) => s.setBasemap);
  const selectFeature = useStore((s) => s.selectFeature);
  const requestFlyTo = useStore((s) => s.requestFlyTo);

  const flyNili = (): void => {
    const nili = allFeatures().find((f) => f.id === 'nili_fossae');
    if (nili) selectFeature(nili);
    else requestFlyTo(null);
  };

  return (
    <header className="topbar">
      <div className="brand">
        <img src="/favicon.svg" alt="" aria-hidden="true" />
        <span>MarsGIS</span>
      </div>

      <ModeTabs />

      <label className="field" style={{ flexDirection: 'row', alignItems: 'center', gap: 6 }}>
        <span>Basemap</span>
        <select
          value={basemapId ?? ''}
          onChange={(e) => setBasemap(e.target.value)}
          aria-label="Base layer"
        >
          {baseLayers.map((l) => (
            <option key={l.id} value={l.id}>
              {l.title}
            </option>
          ))}
        </select>
      </label>

      <button
        className="btn"
        onClick={() => requestFlyTo(null)}
        title="Auto-center and Zoom to Layer"
        style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}
      >
        <CrosshairIcon />
        <span>Auto-Center</span>
      </button>

      <button className="btn btn-ghost" onClick={flyNili} title="Fly to Nili Fossae regional view">
        Nili Fossae
      </button>

      <div className="spacer" />

      <GazetteerSearch />
    </header>
  );
}
