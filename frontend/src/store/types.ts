// MarsGIS Zustand store — exact shape. Domain data uses the FROZEN shared contract types
// from "@/types" directly (no parallel re-definition); only UI-local state is defined here.
import type {
  AnalysisJob,
  AnalysisResult,
  BBox,
  LonLat,
  MapLayer,
  ObservationQuery,
  ObservationSummary,
  SamParams,
  SpectralReference,
  SpectralReferenceSummary,
} from '@/types';

export type AsyncStatus = 'idle' | 'loading' | 'ready' | 'error';
export type WorkspaceMode = 'explore' | 'observations' | 'analysis' | 'results';

export type LeftPanelTab = 'layers' | 'catalog';
export type RightPanelTab = 'analysis' | 'results' | 'inspector';

export interface CameraState {
  lon: number;
  lat: number;
  height: number;
  heading: number;
  pitch: number;
  roll: number;
}

export interface PanelState<Tab extends string> {
  open: boolean;
  width: number;
  active: Tab;
}
export interface Panels {
  left: PanelState<LeftPanelTab>;
  right: PanelState<RightPanelTab>;
}

/** One entry in the overlay layer stack (context/geology/quality overlays, not the basemap). */
export interface LayerEntry {
  id: string;
  layer: MapLayer;
  visible: boolean;
  opacity: number;
  /** 0 = bottom of the overlay block (just above the basemap). */
  order: number;
  removable: boolean;
}

/** Minimal descriptor the LayerManager consumes to build/reconcile Cesium imagery. */
export interface ImageryStackItem {
  id: string;
  layer: MapLayer;
  show: boolean;
  alpha: number;
}

export interface ViewSlice {
  mode: WorkspaceMode;
  panels: Panels;
  camera: CameraState;
  basemapId: string | null;
  hover: LonLat | null;
  setMode: (mode: WorkspaceMode) => void;
  togglePanel: (side: 'left' | 'right', open?: boolean) => void;
  setPanelActive: (side: 'left', tab: LeftPanelTab) => void;
  setRightPanelActive: (tab: RightPanelTab) => void;
  setPanelWidth: (side: 'left' | 'right', width: number) => void;
  setCamera: (camera: CameraState) => void;
  setBasemap: (id: string) => void;
  setHover: (hover: LonLat | null) => void;
}

export interface LayerSlice {
  baseLayers: MapLayer[];
  overlays: LayerEntry[];
  overlayCatalog: MapLayer[];
  catalogStatus: AsyncStatus;
  catalogError: string | null;
  loadLayers: () => Promise<void>;
  addOverlay: (layer: MapLayer) => void;
  removeOverlay: (id: string) => void;
  setLayerVisible: (id: string, visible: boolean) => void;
  setLayerOpacity: (id: string, opacity: number) => void;
  reorderOverlay: (id: string, toIndex: number) => void;
}

export interface CatalogSlice {
  observations: ObservationSummary[];
  total: number;
  filters: ObservationQuery;
  observationsStatus: AsyncStatus;
  observationsError: string | null;
  selectedObservationId: string | null;
  hoveredObservationId: string | null;
  loadObservations: () => Promise<void>;
  setFilters: (patch: Partial<ObservationQuery>) => void;
  selectObservation: (id: string | null) => void;
  hoverObservation: (id: string | null) => void;
  discoverStatus: AsyncStatus;
  discoverError: string | null;
  lastDiscovery: { label: string; found: number } | null;
  discover: (bbox: BBox, label: string) => Promise<void>;
}

export interface AnalysisConfig {
  observation_id: string | null;
  algorithm: 'SAM';
  reference_id: string | null;
  params: Partial<SamParams>;
}

export interface AnalysisSlice {
  minerals: SpectralReferenceSummary[];
  mineralsStatus: AsyncStatus;
  mineralsError: string | null;
  config: AnalysisConfig;
  jobs: Record<string, AnalysisJob>;
  activeJobId: string | null;
  submitStatus: AsyncStatus;
  submitError: string | null;
  loadMinerals: () => Promise<void>;
  setReference: (referenceId: string | null) => void;
  setThresholdRad: (thresholdRad: number) => void;
  submitJob: () => Promise<void>;
  updateJob: (job: AnalysisJob) => void;
  setActiveJob: (id: string | null) => void;
}

export interface ResultSlice {
  results: Record<string, AnalysisResult>;
  activeResultId: string | null;
  overlayVisible: boolean;
  overlayOpacity: number;
  loadStatus: AsyncStatus;
  loadError: string | null;
  loadResult: (id: string) => Promise<void>;
  setActiveResult: (id: string | null) => void;
  setOverlayVisible: (visible: boolean) => void;
  setOverlayOpacity: (opacity: number) => void;
}

/** An observed spectrum trace for the inspector. `synthetic` MUST be surfaced in the UI. */
export interface ObservedSpectrum {
  wavelength_nm: number[];
  reflectance: number[];
  synthetic: boolean;
  angle_deg: number | null;
}

export interface InspectorSlice {
  open: boolean;
  inspectorStatus: AsyncStatus;
  inspectorError: string | null;
  point: LonLat | null;
  referenceId: string | null;
  reference: SpectralReference | null;
  observed: ObservedSpectrum | null;
  inspectPixel: (resultId: string, lon: number, lat: number) => Promise<void>;
  clearInspector: () => void;
}

/** A planetary nomenclature feature (bundled static IAU gazetteer; real nomenclature). */
export interface GazetteerFeature {
  id: string;
  name: string;
  cleanName: string;
  featureType: string;
  lon: number;
  lat: number;
  diameterKm: number;
}

export interface GazetteerSlice {
  query: string;
  gazetteerResults: GazetteerFeature[];
  gazetteerStatus: AsyncStatus;
  selectedFeature: GazetteerFeature | null;
  search: (q: string) => void;
  selectFeature: (feature: GazetteerFeature | null) => void;
}

export type AppState = ViewSlice &
  LayerSlice &
  CatalogSlice &
  AnalysisSlice &
  ResultSlice &
  InspectorSlice &
  GazetteerSlice;

/** Camera flyTo target published by the store; GlobeView effect consumes & clears it. */
export interface FlyTarget {
  lon: number;
  lat: number;
  height: number;
}

export type { BBox };
