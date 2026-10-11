import { describe, it, expect } from 'vitest';
import {
  formatLon,
  formatLat,
  formatLonLat,
  radToDeg,
  degToRad,
  formatAngle,
  formatPercent,
  normalizeLon180,
  normalizeLon360,
} from '@/utils/format';

describe('formatLon/formatLat', () => {
  it('uses E/W and N/S hemispheres (east-positive)', () => {
    expect(formatLon(77)).toBe('77.00°E');
    expect(formatLon(-45.5)).toBe('45.50°W');
    expect(formatLat(21)).toBe('21.00°N');
    expect(formatLat(-14.6)).toBe('14.60°S');
  });
  it('combines lat, lon', () => {
    expect(formatLonLat(77, 21)).toBe('21.00°N, 77.00°E');
  });
});

describe('angle conversions', () => {
  it('rad<->deg round-trips', () => {
    expect(radToDeg(Math.PI)).toBeCloseTo(180);
    expect(degToRad(180)).toBeCloseTo(Math.PI);
    expect(radToDeg(degToRad(42))).toBeCloseTo(42);
  });
  it('formats a spectral angle', () => {
    expect(formatAngle(0.1)).toBe('0.100 rad (5.73°)');
  });
});

describe('formatPercent', () => {
  it('scales a fraction', () => {
    expect(formatPercent(0.1347)).toBe('13.5%');
  });
});

describe('re-exported normalizeLon', () => {
  it('matches geo helpers', () => {
    expect(normalizeLon180(200)).toBeCloseTo(-160);
    expect(normalizeLon360(-20)).toBeCloseTo(340);
  });
});
