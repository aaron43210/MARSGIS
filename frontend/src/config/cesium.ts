// Cesium setup for MarsGIS; the Mars ellipsoid itself comes from mars-globe.
import { Ion } from 'cesium';

// We don't use Cesium Ion — clear the default token so Cesium never attempts
// to reach api.cesium.com (which would fail in isolated/docker environments).
Ion.defaultAccessToken = '';

export { installMarsEllipsoid } from 'mars-globe';
