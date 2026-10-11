import { describe, it, expect } from 'vitest';
import {
  normalizeLon180,
  normalizeLon360,
  bboxOfFeature,
  centroidOfFeature,
  centerOfBbox,
  clampLat,
} from '@/cesium/geo';
import type { Footprint } from '@/types';

describe('normalizeLon', () => {
  it('wraps into [-180,180]', () => {
    expect(normalizeLon180(0)).toBe(0);
    expect(normalizeLon180(190)).toBeCloseTo(-170);
    expect(normalizeLon180(-190)).toBeCloseTo(170);
    expect(normalizeLon180(360)).toBe(0);
    expect(normalizeLon180(540)).toBe(180);
  });
  it('wraps into [0,360)', () => {
    expect(normalizeLon360(-10)).toBeCloseTo(350);
    expect(normalizeLon360(370)).toBeCloseTo(10);
    expect(normalizeLon360(0)).toBe(0);
  });
});

describe('clampLat', () => {
  it('clamps to [-90,90]', () => {
    expect(clampLat(95)).toBe(90);
    expect(clampLat(-95)).toBe(-90);
    expect(clampLat(12)).toBe(12);
  });
});

const square: Footprint = {
  type: 'Polygon',
  coordinates: [
    [
      [10, 20],
      [14, 20],
      [14, 24],
      [10, 24],
      [10, 20],
    ],
  ],
};

describe('bboxOfFeature', () => {
  it('computes [w,s,e,n]', () => {
    expect(bboxOfFeature(square)).toEqual([10, 20, 14, 24]);
  });
  it('handles MultiPolygon', () => {
    const mp: Footprint = { type: 'MultiPolygon', coordinates: [square.coordinates] };
    expect(bboxOfFeature(mp)).toEqual([10, 20, 14, 24]);
  });
});

describe('centroidOfFeature', () => {
  it('averages ring vertices', () => {
    const [lon, lat] = centroidOfFeature(square);
    expect(lon).toBeCloseTo(11.6, 1); // mean of 10,14,14,10,10
    expect(lat).toBeCloseTo(21.6, 1);
  });
});

describe('centerOfBbox', () => {
  it('returns the midpoint', () => {
    expect(centerOfBbox([10, 20, 14, 24])).toEqual([12, 22]);
  });
});
