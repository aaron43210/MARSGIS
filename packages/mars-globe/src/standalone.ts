// Standalone (IIFE/CDN) entry: exposes the full API as window.MarsGlobe AND
// auto-registers the <mars-globe> element, for plain <script> tag usage.
// Cesium must already be on the page as window.Cesium.
import { defineMarsGlobe } from './webcomponent';

export * from './index';

defineMarsGlobe();
