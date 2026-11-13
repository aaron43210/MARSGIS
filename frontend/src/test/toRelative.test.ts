import { describe, it, expect } from 'vitest';
import { toRelative } from '@/utils/spectra';

describe('toRelative', () => {
  it('puts a dim pixel and a bright reference of the same shape on one curve', () => {
    const shape = [1, 2, 3, 2];
    const dim = shape.map((v) => v * 0.1);
    const bright = shape.map((v) => v * 1.3);
    const a = toRelative(dim) as number[];
    const b = toRelative(bright) as number[];
    a.forEach((v, i) => expect(v).toBeCloseTo(b[i]!));
  });

  it('keeps gaps and survives an all-zero input', () => {
    expect(toRelative([2, null, 4])).toEqual([2 / 3, null, 4 / 3]);
    expect(toRelative([0, 0])).toEqual([0, 0]);
  });
});
