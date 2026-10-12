import { Component, type ErrorInfo, type ReactNode } from 'react';

interface Props {
  children: ReactNode;
  fallback?: (error: Error, reset: () => void) => ReactNode;
}

interface State {
  error: Error | null;
}

/**
 * Top-level error boundary. Without this, any uncaught throw in a React tree
 * (e.g. Cesium Viewer init crash) silently unmounts the whole app → white screen.
 * With this, the user sees a readable error message instead.
 */
export class ErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props);
    this.state = { error: null };
    this.reset = this.reset.bind(this);
  }

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  override componentDidCatch(error: Error, info: ErrorInfo): void {
    console.error('[MarsGIS] Uncaught render error:', error, info.componentStack);
  }

  reset(): void {
    this.setState({ error: null });
  }

  override render(): ReactNode {
    const { error } = this.state;
    const { children, fallback } = this.props;

    if (error) {
      if (fallback) return fallback(error, this.reset);
      return <DefaultFallback error={error} reset={this.reset} />;
    }
    return children;
  }
}

function DefaultFallback({ error, reset }: { error: Error; reset: () => void }) {
  return (
    <div style={{
      position: 'fixed', inset: 0,
      display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
      background: '#05070b', color: '#e2e8f0',
      fontFamily: 'system-ui, sans-serif', padding: '2rem', textAlign: 'center',
      gap: '1rem',
    }}>
      <div style={{ fontSize: '3rem' }}>🔴</div>
      <h1 style={{ color: '#f87171', margin: 0, fontSize: '1.4rem' }}>Mars Globe Failed to Load</h1>
      <p style={{ color: '#94a3b8', maxWidth: '520px', margin: 0, lineHeight: 1.6 }}>
        The Cesium 3D globe encountered an error during initialization.
        Check the browser console (F12) for details.
      </p>
      <pre style={{
        background: '#0f1117', color: '#fca5a5', padding: '1rem',
        borderRadius: '8px', fontSize: '0.75rem', maxWidth: '600px',
        overflowX: 'auto', textAlign: 'left', border: '1px solid #7f1d1d',
      }}>
        {error.message}
      </pre>
      <button onClick={reset} style={{
        background: '#7c3f25', color: '#fff', border: 'none',
        padding: '0.6rem 1.4rem', borderRadius: '8px', cursor: 'pointer',
        fontSize: '0.9rem', marginTop: '0.5rem',
      }}>
        Retry
      </button>
    </div>
  );
}
