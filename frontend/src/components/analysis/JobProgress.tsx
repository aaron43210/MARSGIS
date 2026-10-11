import { useStore } from '@/store';
import { Button, ErrorBanner } from '@/components/common';

const STATUS_LABEL: Record<string, string> = {
  queued: 'Queued',
  running: 'Running',
  succeeded: 'Succeeded',
  failed: 'Failed',
};

export function JobProgress(): React.ReactElement | null {
  const activeJobId = useStore((s) => s.activeJobId);
  const job = useStore((s) => (activeJobId ? s.jobs[activeJobId] : undefined));
  const setMode = useStore((s) => s.setMode);

  if (!job) return null;

  const pct = Math.round((job.progress || 0) * 100);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12 }}>
        <span>
          Job <span className="mono">{job.id}</span>
        </span>
        <span>{STATUS_LABEL[job.status] ?? job.status}</span>
      </div>
      <div className="bar">
        <span style={{ width: `${pct}%` }} />
      </div>
      {job.message ? (
        <div style={{ fontSize: 11, color: 'var(--text-dim)' }}>{job.message}</div>
      ) : null}

      {job.status === 'failed' && job.error ? (
        <ErrorBanner message={`${job.error.code}: ${job.error.message}`} />
      ) : null}

      {job.status === 'succeeded' ? (
        <Button variant="primary" block onClick={() => setMode('results')}>
          View results →
        </Button>
      ) : null}
    </div>
  );
}
