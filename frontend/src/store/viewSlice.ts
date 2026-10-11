import type { AppSlice } from './createSlice';
import type { CameraState, LeftPanelTab, Panels, RightPanelTab, ViewSlice, WorkspaceMode } from './types';
import { DEFAULT_CAMERA } from '@/config/constants';
import { env } from '@/env';
import { DEFAULT_BASEMAP_ID } from '@/config/basemaps';

const INITIAL_CAMERA: CameraState = { ...DEFAULT_CAMERA };

const INITIAL_PANELS: Panels = {
  left: { open: true, width: 320, active: 'layers' },
  right: { open: false, width: 360, active: 'analysis' },
};

function panelsForMode(mode: WorkspaceMode, panels: Panels): Panels {
  const next: Panels = {
    left: { ...panels.left },
    right: { ...panels.right },
  };
  switch (mode) {
    case 'explore':
      next.left.active = 'layers';
      next.left.open = true;
      break;
    case 'observations':
      next.left.active = 'catalog';
      next.left.open = true;
      break;
    case 'analysis':
      next.right.active = 'analysis';
      next.right.open = true;
      break;
    case 'results':
      next.right.active = 'results';
      next.right.open = true;
      break;
  }
  return next;
}

export const createViewSlice: AppSlice<ViewSlice> = (set) => ({
  mode: 'explore',
  panels: INITIAL_PANELS,
  camera: INITIAL_CAMERA,
  basemapId: env.defaultBasemap || DEFAULT_BASEMAP_ID,
  hover: null,

  setMode: (mode) =>
    set((state) => {
      state.mode = mode;
      state.panels = panelsForMode(mode, state.panels);
    }),

  togglePanel: (side, open) =>
    set((state) => {
      state.panels[side].open = open ?? !state.panels[side].open;
    }),

  setPanelActive: (_side: 'left', tab: LeftPanelTab) =>
    set((state) => {
      state.panels.left.active = tab;
      state.panels.left.open = true;
    }),

  setRightPanelActive: (tab: RightPanelTab) =>
    set((state) => {
      state.panels.right.active = tab;
      state.panels.right.open = true;
    }),

  setPanelWidth: (side, width) =>
    set((state) => {
      state.panels[side].width = Math.max(240, Math.min(560, width));
    }),

  setCamera: (camera) =>
    set((state) => {
      state.camera = camera;
    }),

  setBasemap: (id) =>
    set((state) => {
      state.basemapId = id;
    }),

  setHover: (hover) =>
    set((state) => {
      state.hover = hover;
    }),
});
