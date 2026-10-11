import { useCallback, useMemo } from 'react';
import { useStore } from '@/store';
import { debounce } from '@/utils/debounce';
import type { GazetteerFeature } from '@/store/types';

/** Debounced gazetteer query (250ms). Search itself is synchronous over the bundled feature list. */
export function useGazetteer(): {
  query: string;
  results: GazetteerFeature[];
  onQueryChange: (q: string) => void;
} {
  const query = useStore((s) => s.query);
  const results = useStore((s) => s.gazetteerResults);
  const search = useStore((s) => s.search);

  const debounced = useMemo(() => debounce((q: string) => search(q), 250), [search]);

  const onQueryChange = useCallback(
    (q: string) => {
      // Update the controlled input immediately via the store, debounce the result compute.
      debounced(q);
    },
    [debounced],
  );

  return { query, results, onQueryChange };
}
