// App bootstrap. ORDER MATTERS:
//   1. Set window.CESIUM_BASE_URL so Cesium can find its copied Workers/Assets/Widgets.
//   2. Install the Mars ellipsoid (Ellipsoid.default) BEFORE any Viewer/Camera is created.
//   3. Mount React.
import 'cesium/Build/Cesium/Widgets/widgets.css';
import './styles/index.css';
import './styles/panels.css';

import { createRoot } from 'react-dom/client';
import { env } from './env';
import { installMarsEllipsoid } from './config/cesium';
import { ErrorBoundary } from './components/ErrorBoundary';
import App from './App';

window.CESIUM_BASE_URL = env.cesiumBaseUrl;
installMarsEllipsoid();

const rootEl = document.getElementById('root');
if (!rootEl) throw new Error('#root element not found');

// NOTE: StrictMode is intentionally NOT used here. React StrictMode double-invokes
// useEffect (mount → unmount → remount) in development to detect side-effects.
// Cesium creates a WebGL rendering context on mount and destroys it on unmount.
// The second mount after the StrictMode teardown fails because the canvas has already
// had its context destroyed — resulting in a blank white screen with no error.
createRoot(rootEl).render(
  <ErrorBoundary>
    <App />
  </ErrorBoundary>,
);
