import type { StateCreator } from 'zustand';
import type { AppState } from './types';

/** Shared slice-creator type: store composed as persist(immer(...)). */
export type AppSlice<T> = StateCreator<
  AppState,
  [['zustand/persist', unknown], ['zustand/immer', never]],
  [],
  T
>;
