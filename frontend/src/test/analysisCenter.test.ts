import { describe, it, expect, beforeEach, vi } from 'vitest';

const createJob = vi.fn();
vi.mock('@/api/analysis', async (orig) => ({
  ...(await orig<typeof import('@/api/analysis')>()),
  createJob: (...args: unknown[]) => createJob(...args),
}));

const { useStore } = await import('@/store');

const job = { id: 'j1', status: 'queued' };

describe('analysis centre option', () => {
  beforeEach(() => {
    createJob.mockReset().mockResolvedValue(job);
    useStore.getState().selectObservation('frt00003e12');
    useStore.getState().setReference('mica_carbonate_mg');
    useStore.getState().setUseCenter(false);
    useStore.getState().setAnalysisCenter(null);
  });

  it('sends the clicked spot only when the option is on', async () => {
    useStore.getState().setAnalysisCenter({ lon: 77.05, lat: 22.3 });
    await useStore.getState().submitJob();
    expect(createJob.mock.calls[0]![0].center).toBeUndefined();

    useStore.getState().setUseCenter(true);
    await useStore.getState().submitJob();
    expect(createJob.mock.calls[1]![0].center).toEqual({ lon: 77.05, lat: 22.3 });
  });

  it('sends the chosen area size (small by default)', async () => {
    await useStore.getState().submitJob();
    expect(createJob.mock.calls[0]![0].area).toBe('small');
    useStore.getState().setArea('full');
    await useStore.getState().submitJob();
    expect(createJob.mock.calls[1]![0].area).toBe('full');
    useStore.getState().setArea('small');
  });

  it('forgets the spot when another observation is selected', () => {
    useStore.getState().setAnalysisCenter({ lon: 77.05, lat: 22.3 });
    useStore.getState().selectObservation('frt0000634b');
    expect(useStore.getState().config.center).toBeNull();
  });
});
