import { useEffect, useRef } from 'react';
import { useStore } from '@/store';
import { getJob } from '@/api/analysis';
import { TERMINAL_JOB_STATUSES } from '@/types';

/**
 * Polls the active analysis job until it reaches a terminal state (succeeded/failed), writing
 * each update into the store. The store's updateJob handles loading the result and switching to
 * the Results workspace on success. Interval backs off slightly after the first few polls.
 */
export function useAnalysisJob(): void {
  const activeJobId = useStore((s) => s.activeJobId);
  const updateJob = useStore((s) => s.updateJob);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    if (!activeJobId) return;
    const current = useStore.getState().jobs[activeJobId];
    if (current && TERMINAL_JOB_STATUSES.includes(current.status)) return;

    let cancelled = false;
    let polls = 0;
    const controller = new AbortController();

    const tick = async (): Promise<void> => {
      if (cancelled) return;
      try {
        const job = await getJob(activeJobId, controller.signal);
        if (cancelled) return;
        updateJob(job);
        if (TERMINAL_JOB_STATUSES.includes(job.status)) return;
      } catch {
        if (cancelled) return;
        // transient error: keep polling a bounded number of times
      }
      polls += 1;
      const delay = polls < 5 ? 800 : polls < 15 ? 1500 : 3000;
      timer.current = setTimeout(() => void tick(), delay);
    };

    void tick();

    return () => {
      cancelled = true;
      controller.abort();
      if (timer.current) clearTimeout(timer.current);
    };
  }, [activeJobId, updateJob]);
}
