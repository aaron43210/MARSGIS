import { useStore } from '@/store';
import { Panel } from '@/components/common/Panel';
import { Button, ErrorBanner, Spinner } from '@/components/common';
import { MethodSelect } from '@/components/analysis/MethodSelect';
import { ReferenceSpectrumSelect } from '@/components/analysis/ReferenceSpectrumSelect';
import { SamParams } from '@/components/analysis/SamParams';
import { JobProgress } from '@/components/analysis/JobProgress';
import { CANDIDATE_MATCH_CAVEAT } from '@/types';

/** Screen 3: configure + run the SAM analysis for the selected observation. */
export function AnalysisPanel(): React.ReactElement {
  const observationId = useStore((s) => s.config.observation_id);
  const referenceId = useStore((s) => s.config.reference_id);
  const submitJob = useStore((s) => s.submitJob);
  const submitStatus = useStore((s) => s.submitStatus);
  const submitError = useStore((s) => s.submitError);
  const setMode = useStore((s) => s.setMode);

  const canRun = Boolean(observationId && referenceId) && submitStatus !== 'loading';

  return (
    <Panel title="Analysis — Spectral Angle Mapper">
      {observationId ? (
        <div style={{ fontSize: 12 }}>
          Observation: <span className="mono">{observationId}</span>
        </div>
      ) : (
        <div className="caveat" role="note">
          Select an observation first (
          <button
            className="btn"
            style={{ padding: '2px 6px' }}
            onClick={() => setMode('observations')}
          >
            open catalogue
          </button>
          ), then its footprint becomes the analysis input.
        </div>
      )}

      <MethodSelect />
      <ReferenceSpectrumSelect />
      <SamParams />

      {submitStatus === 'error' && submitError ? <ErrorBanner message={submitError} /> : null}

      <Button variant="primary" block disabled={!canRun} onClick={() => void submitJob()}>
        {submitStatus === 'loading' ? 'Submitting…' : 'Run analysis'}
      </Button>
      {submitStatus === 'loading' ? <Spinner label="Submitting job" /> : null}

      <JobProgress />

      <div className="caveat" role="note">
        <strong>Candidate match only. </strong>
        {CANDIDATE_MATCH_CAVEAT}
      </div>
    </Panel>
  );
}
