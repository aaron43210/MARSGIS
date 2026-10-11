// Framework-agnostic <mars-globe> custom element.
// Requires Cesium present (bundled, or window.Cesium via the standalone build)
// and, for assets, window.CESIUM_BASE_URL + Cesium's widgets.css on the page.
import { type BasemapId } from './basemaps';
import { MarsGlobe, createMarsGlobe } from './globe';

const VALID = new Set<string>(['viking', 'mola', 'mola-dem', 'themis']);

export class MarsGlobeElement extends HTMLElement {
  private globe: MarsGlobe | undefined;
  private container: HTMLDivElement | undefined;

  static get observedAttributes(): string[] {
    return ['basemap'];
  }

  connectedCallback(): void {
    if (this.globe) return;
    if (!this.style.display) this.style.display = 'block';
    const container = document.createElement('div');
    container.style.width = '100%';
    container.style.height = '100%';
    this.appendChild(container);
    this.container = container;
    const basemap = this.getAttribute('basemap');
    this.globe = createMarsGlobe(container, {
      defaultBasemap: (basemap && VALID.has(basemap) ? basemap : 'viking') as BasemapId,
    });
  }

  attributeChangedCallback(name: string, _old: string | null, value: string | null): void {
    if (name === 'basemap' && this.globe && value && VALID.has(value)) {
      this.globe.setBasemap(value as BasemapId);
    }
  }

  disconnectedCallback(): void {
    this.globe?.destroy();
    this.globe = undefined;
    this.container?.remove();
    this.container = undefined;
  }

  /** The underlying MarsGlobe instance (available once connected). */
  get marsGlobe(): MarsGlobe | undefined {
    return this.globe;
  }
}

/** Register the custom element (default tag `<mars-globe>`). Safe to call twice. */
export function defineMarsGlobe(tagName = 'mars-globe'): void {
  if (typeof customElements !== 'undefined' && !customElements.get(tagName)) {
    customElements.define(tagName, MarsGlobeElement);
  }
}
