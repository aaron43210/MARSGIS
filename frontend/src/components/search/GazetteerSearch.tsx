import { useState } from 'react';
import { useStore } from '@/store';
import { useGazetteer } from '@/hooks/useGazetteer';
import { formatLonLat } from '@/utils/format';

/** Debounced planetary-feature search (bundled IAU nomenclature). Seeded so "nili" finds Nili Fossae. */
export function GazetteerSearch(): React.ReactElement {
  const { results, onQueryChange } = useGazetteer();
  const selectFeature = useStore((s) => s.selectFeature);
  const [text, setText] = useState('');
  const [open, setOpen] = useState(false);
  const [activeIdx, setActiveIdx] = useState(-1);

  const choose = (index: number): void => {
    const feature = results[index];
    if (!feature) return;
    selectFeature(feature);
    setText(feature.name);
    setOpen(false);
    setActiveIdx(-1);
  };

  return (
    <div className="combo" style={{ width: 240 }}>
      <input
        type="search"
        role="combobox"
        aria-expanded={open}
        aria-controls="gazetteer-results"
        aria-autocomplete="list"
        placeholder="Search features (e.g. Nili Fossae)"
        value={text}
        style={{
          width: '100%',
          background: 'var(--bg-elev)',
          border: '1px solid var(--border)',
          color: 'var(--text)',
          padding: '7px 9px',
          borderRadius: 6,
        }}
        onChange={(e) => {
          setText(e.target.value);
          onQueryChange(e.target.value);
          setOpen(true);
          setActiveIdx(-1);
        }}
        onFocus={() => results.length > 0 && setOpen(true)}
        onBlur={() => setTimeout(() => setOpen(false), 150)}
        onKeyDown={(e) => {
          if (e.key === 'ArrowDown') {
            e.preventDefault();
            setActiveIdx((i) => Math.min(results.length - 1, i + 1));
            setOpen(true);
          } else if (e.key === 'ArrowUp') {
            e.preventDefault();
            setActiveIdx((i) => Math.max(0, i - 1));
          } else if (e.key === 'Enter') {
            choose(activeIdx >= 0 ? activeIdx : 0);
          } else if (e.key === 'Escape') {
            setOpen(false);
          }
        }}
      />
      {open && results.length > 0 ? (
        <ul className="results" id="gazetteer-results" role="listbox">
          {results.map((f, i) => (
            <li
              key={f.id}
              role="option"
              aria-selected={i === activeIdx}
              onMouseDown={(e) => {
                e.preventDefault();
                choose(i);
              }}
            >
              <div style={{ fontSize: 13 }}>{f.name}</div>
              <div style={{ fontSize: 11, color: 'var(--text-dim)' }}>
                {f.featureType} · {formatLonLat(f.lon, f.lat)}
              </div>
            </li>
          ))}
        </ul>
      ) : null}
    </div>
  );
}
