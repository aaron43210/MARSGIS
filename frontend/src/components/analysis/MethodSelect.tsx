/** Choose analysis method. v1 implements SAM only (SID/BAND_RATIO reserved -> backend 422). */
export function MethodSelect(): React.ReactElement {
  return (
    <label className="field">
      <span>Method</span>
      <select value="SAM" disabled aria-label="Analysis method">
        <option value="SAM">SAM — Spectral Angle Mapper</option>
        <option value="SID" disabled>
          SID (not implemented in v1)
        </option>
        <option value="BAND_RATIO" disabled>
          Band ratio (not implemented in v1)
        </option>
      </select>
    </label>
  );
}
