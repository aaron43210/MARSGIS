import '@testing-library/jest-dom';
import { vi } from 'vitest';

// Cesium base url stub (no asset fetches happen in unit tests).
window.CESIUM_BASE_URL = '/cesium';

// jsdom lacks ResizeObserver (uPlot and panels use it).
if (!('ResizeObserver' in window)) {
  class ResizeObserverStub {
    observe(): void {}
    unobserve(): void {}
    disconnect(): void {}
  }
  (window as unknown as { ResizeObserver: unknown }).ResizeObserver = ResizeObserverStub;
}

// jsdom lacks matchMedia (prefers-color-scheme reads).
if (!window.matchMedia) {
  window.matchMedia = vi.fn().mockImplementation((query: string) => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: vi.fn(),
    removeListener: vi.fn(),
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    dispatchEvent: vi.fn(),
  }));
}
