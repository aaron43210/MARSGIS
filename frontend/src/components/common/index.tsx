// Minimal accessible UI primitives (no UI framework dependency). Light/dark via CSS tokens.
import type { ButtonHTMLAttributes, ReactNode } from 'react';

export function Button({
  variant = 'default',
  block,
  className,
  children,
  ...rest
}: ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: 'default' | 'primary';
  block?: boolean;
}): React.ReactElement {
  const cls = ['btn', variant === 'primary' ? 'primary' : '', block ? 'block' : '', className ?? '']
    .filter(Boolean)
    .join(' ');
  return (
    <button className={cls} {...rest}>
      {children}
    </button>
  );
}

export function IconButton({
  label,
  children,
  ...rest
}: ButtonHTMLAttributes<HTMLButtonElement> & { label: string }): React.ReactElement {
  return (
    <button className="icon-btn" aria-label={label} title={label} {...rest}>
      {children}
    </button>
  );
}

export function CrosshairIcon({ size = 14 }: { size?: number }): React.ReactElement {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 16 16"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.5"
      aria-hidden="true"
    >
      <circle cx="8" cy="8" r="5" />
      <path d="M8 1v3M8 12v3M1 8h3M12 8h3" strokeLinecap="round" />
    </svg>
  );
}

export function Spinner({ label = 'Loading' }: { label?: string }): React.ReactElement {
  return (
    <span style={{ display: 'inline-flex', alignItems: 'center', gap: 8 }}>
      <span className="spinner" role="status" aria-label={label} />
      <span style={{ color: 'var(--text-dim)', fontSize: 12 }}>{label}…</span>
    </span>
  );
}

export function ErrorBanner({ message }: { message: string }): React.ReactElement {
  return (
    <div className="error-banner" role="alert">
      {message}
    </div>
  );
}

export function Badge({
  children,
  synthetic,
}: {
  children: ReactNode;
  synthetic?: boolean;
}): React.ReactElement {
  return <span className={`badge${synthetic ? ' syn' : ''}`}>{children}</span>;
}

export function Toggle({
  checked,
  onChange,
  label,
}: {
  checked: boolean;
  onChange: (v: boolean) => void;
  label: string;
}): React.ReactElement {
  return (
    <label style={{ display: 'inline-flex', alignItems: 'center', gap: 6, cursor: 'pointer' }}>
      <input type="checkbox" checked={checked} onChange={(e) => onChange(e.target.checked)} />
      <span style={{ fontSize: 12 }}>{label}</span>
    </label>
  );
}

/** The required scientific-honesty caveat block (candidate match, not a confirmed deposit). */
export function CaveatBlock({ text }: { text: string }): React.ReactElement {
  return (
    <div className="caveat" role="note">
      <strong>Candidate match only. </strong>
      {text}
    </div>
  );
}
