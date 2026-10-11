import { useStore } from '@/store';
import { Button } from '@/components/common';

const REGIONS = ['Nili Fossae', 'Jezero', 'Syrtis Major'];

export function CatalogFilters(): React.ReactElement {
  const filters = useStore((s) => s.filters);
  const setFilters = useStore((s) => s.setFilters);
  const loadObservations = useStore((s) => s.loadObservations);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
      <label className="field">
        <span>Region</span>
        <select
          value={filters.region ?? ''}
          onChange={(e) => setFilters({ region: e.target.value || undefined })}
        >
          <option value="">All regions</option>
          {REGIONS.map((r) => (
            <option key={r} value={r}>
              {r}
            </option>
          ))}
        </select>
      </label>

      <label className="field">
        <span>Instrument</span>
        <select
          value={filters.instrument ?? 'CRISM'}
          onChange={(e) =>
            setFilters({ instrument: (e.target.value || undefined) as typeof filters.instrument })
          }
        >
          <option value="CRISM">CRISM</option>
        </select>
      </label>

      <label className="field">
        <span>Search (id / title)</span>
        <input
          type="search"
          value={filters.q ?? ''}
          placeholder="e.g. carbonate, FRT…"
          onChange={(e) => setFilters({ q: e.target.value || undefined })}
        />
      </label>

      <label style={{ display: 'inline-flex', alignItems: 'center', gap: 6, fontSize: 12 }}>
        <input
          type="checkbox"
          checked={filters.suitable ?? false}
          onChange={(e) => setFilters({ suitable: e.target.checked || undefined })}
        />
        Analysis-suitable only
      </label>

      <Button onClick={() => void loadObservations()}>Apply filters</Button>
    </div>
  );
}
