import type { ReactNode } from 'react';

/** Shared panel chrome: header with title + optional actions, scrollable body. */
export function Panel({
  title,
  actions,
  children,
}: {
  title: string;
  actions?: ReactNode;
  children: ReactNode;
}): React.ReactElement {
  return (
    <div className="panel">
      <div className="panel-header">
        <span>{title}</span>
        {actions ? <span className="actions">{actions}</span> : null}
      </div>
      <div className="panel-body">{children}</div>
    </div>
  );
}
