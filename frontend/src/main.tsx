// App bootstrap. ORDER MATTERS:
//   1. Set window.CESIUM_BASE_URL so Cesium can find its copied Workers/Assets/Widgets.
//   2. Install the Mars ellipsoid (Ellipsoid.default) BEFORE any Viewer/Camera is created.
//   3. Mount React.
import 'cesium/Build/Cesium/Widgets/widgets.css';
import './styles/index.css';
import './styles/panels.css';

import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { env } from './env';
import { installMarsEllipsoid } from './config/cesium';
import App from './App';

window.CESIUM_BASE_URL = env.cesiumBaseUrl;
installMarsEllipsoid();

const rootEl = document.getElementById('root');
if (!rootEl) throw new Error('#root element not found');

createRoot(rootEl).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
