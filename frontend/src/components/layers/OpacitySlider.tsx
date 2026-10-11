import { useRef, useState } from 'react';

/** Reusable 0–100% opacity control mapping to a 0..1 value, with light debounce. */
export function OpacitySlider({
  value,
  onChange,
  label = 'Opacity',
}: {
  value: number;
  onChange: (v: number) => void;
  label?: string;
}): React.ReactElement {
  const [local, setLocal] = useState(value);
  const raf = useRef<number | null>(null);

  // Resync the local (debounced) value when the controlled prop changes, without an effect:
  // adjusting state during render is React's recommended alternative to a setState-in-effect.
  const [prevValue, setPrevValue] = useState(value);
  if (value !== prevValue) {
    setPrevValue(value);
    setLocal(value);
  }

  const handle = (next: number): void => {
    setLocal(next);
    if (raf.current) cancelAnimationFrame(raf.current);
    raf.current = requestAnimationFrame(() => onChange(next));
  };

  return (
    <label style={{ display: 'flex', alignItems: 'center', gap: 8, flex: 1 }}>
      <span className="visually-hidden">{label}</span>
      <input
        type="range"
        min={0}
        max={1}
        step={0.01}
        value={local}
        aria-label={label}
        onChange={(e) => handle(Number(e.target.value))}
      />
      <span className="mono" style={{ width: 36, fontSize: 11, color: 'var(--text-dim)' }}>
        {Math.round(local * 100)}%
      </span>
    </label>
  );
}
