import { useStore } from '@/store';
import type { SpectralReferenceSummary } from '@/types';
import type { MineralClass } from '@/types';
import { Spinner, ErrorBanner } from '@/components/common';

function groupByClass(
  minerals: SpectralReferenceSummary[],
): Array<[MineralClass, SpectralReferenceSummary[]]> {
  const groups = new Map<MineralClass, SpectralReferenceSummary[]>();
  for (const m of minerals) {
    const arr = groups.get(m.mineral_class) ?? [];
    arr.push(m);
    groups.set(m.mineral_class, arr);
  }
  return [...groups.entries()];
}

export function ReferenceSpectrumSelect(): React.ReactElement {
  const minerals = useStore((s) => s.minerals);
  const status = useStore((s) => s.mineralsStatus);
  const error = useStore((s) => s.mineralsError);
  const referenceId = useStore((s) => s.config.reference_id);
  const setReference = useStore((s) => s.setReference);

  if (status === 'loading') return <Spinner label="Loading reference library" />;
  if (status === 'error' && error) return <ErrorBanner message={error} />;

  return (
    <label className="field">
      <span>Reference spectrum (MICA)</span>
      <select
        value={referenceId ?? ''}
        onChange={(e) => setReference(e.target.value || null)}
        aria-label="Reference spectrum"
      >
        <option value="" disabled>
          Choose a mineral reference…
        </option>
        {groupByClass(minerals).map(([cls, items]) => (
          <optgroup key={cls} label={cls}>
            {items.map((m) => (
              <option key={m.id} value={m.id}>
                {m.mineral} ({m.source})
              </option>
            ))}
          </optgroup>
        ))}
      </select>
    </label>
  );
}
