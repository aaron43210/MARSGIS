import { Panel } from '@/components/common/Panel';
import { CatalogFilters } from '@/components/catalog/CatalogFilters';
import { ObservationList } from '@/components/catalog/ObservationList';
import { ErrorBanner, Spinner } from '@/components/common';
import { useCatalog } from '@/hooks/useCatalog';

/** Screen 2: browse/filter CRISM observations whose footprints draw on the globe. */
export function DataCataloguePanel(): React.ReactElement {
  const { status, error } = useCatalog();

  return (
    <Panel title="Data catalogue">
      <CatalogFilters />
      {status === 'loading' ? <Spinner label="Loading observations" /> : null}
      {status === 'error' && error ? <ErrorBanner message={error} /> : null}
      <div style={{ fontSize: 11, color: 'var(--text-dim)' }}>
        Click a card (or its footprint on the globe) to select and fly to it.
      </div>
      <ObservationList />
    </Panel>
  );
}
