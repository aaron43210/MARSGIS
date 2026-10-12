// Render CRISM footprints as clickable, state-styled polygon entities in a CustomDataSource.
// Entity id === observation id, so picking maps straight back to the store.
import {
  Cartesian3,
  Color,
  ColorMaterialProperty,
  ConstantProperty,
  CustomDataSource,
  Entity,
  PolygonHierarchy,
  Rectangle,
  type Viewer,
} from 'cesium';
import type { Footprint, ObservationSummary } from '@/types';

interface FootprintStyle {
  fill: Color;
  outline: Color;
  outlineWidth: number;
}

const STYLE_DEFAULT: FootprintStyle = {
  fill: Color.fromCssColorString('#4fc3f7').withAlpha(0.18),
  outline: Color.fromCssColorString('#4fc3f7').withAlpha(0.85),
  outlineWidth: 1.5,
};
const STYLE_HOVER: FootprintStyle = {
  fill: Color.fromCssColorString('#8ad6ff').withAlpha(0.3),
  outline: Color.fromCssColorString('#bfe9ff').withAlpha(0.95),
  outlineWidth: 2,
};
const STYLE_SELECTED: FootprintStyle = {
  fill: Color.fromCssColorString('#ffb74d').withAlpha(0.35),
  outline: Color.fromCssColorString('#ffd38a').withAlpha(1),
  outlineWidth: 2.5,
};
const STYLE_UNSUITABLE: FootprintStyle = {
  fill: Color.fromCssColorString('#9aa3b5').withAlpha(0.12),
  outline: Color.fromCssColorString('#9aa3b5').withAlpha(0.6),
  outlineWidth: 1,
};

function outerRing(f: Footprint): number[][] {
  if (f.type === 'Polygon') return f.coordinates[0] ?? [];
  return f.coordinates[0]?.[0] ?? [];
}

function hierarchyFromFootprint(f: Footprint): PolygonHierarchy {
  const ring = outerRing(f);
  const flat: number[] = [];
  for (const pt of ring) {
    if (pt.length >= 2) flat.push(pt[0]!, pt[1]!);
  }
  return new PolygonHierarchy(Cartesian3.fromDegreesArray(flat));
}

export class FootprintLayer {
  private readonly viewer: Viewer;
  private readonly dataSource = new CustomDataSource('footprints');
  private selectedId: string | null = null;
  private hoveredId: string | null = null;
  private suitable = new Map<string, boolean>();
  private bboxes = new Map<string, [number, number, number, number]>();

  constructor(viewer: Viewer) {
    this.viewer = viewer;
    void viewer.dataSources.add(this.dataSource);
  }

  /** Replace all footprint entities from observation summaries. */
  load(observations: ObservationSummary[]): void {
    this.dataSource.entities.removeAll();
    this.suitable.clear();
    this.bboxes.clear();
    for (const obs of observations) {
      this.suitable.set(obs.id, obs.analysis_suitable);
      this.bboxes.set(obs.id, obs.bbox);
      this.dataSource.entities.add(
        new Entity({
          id: obs.id,
          name: obs.title,
          polygon: {
            hierarchy: new ConstantProperty(hierarchyFromFootprint(obs.footprint)),
            material: new ColorMaterialProperty(this.baseStyle(obs.id).fill),
            outline: new ConstantProperty(true),
            outlineColor: new ConstantProperty(this.baseStyle(obs.id).outline),
            outlineWidth: new ConstantProperty(this.baseStyle(obs.id).outlineWidth),
            height: new ConstantProperty(0),
          },
        }),
      );
    }
    this.restyleAll();
    this.viewer.scene.requestRender();
  }

  private baseStyle(id: string): FootprintStyle {
    return this.suitable.get(id) === false ? STYLE_UNSUITABLE : STYLE_DEFAULT;
  }

  setSelected(id: string | null): void {
    if (this.selectedId === id) return;
    this.selectedId = id;
    this.restyleAll();
    this.viewer.scene.requestRender();
  }

  setHovered(id: string | null): void {
    if (this.hoveredId === id) return;
    this.hoveredId = id;
    this.restyleAll();
    this.viewer.scene.requestRender();
  }

  private restyleAll(): void {
    for (const entity of this.dataSource.entities.values) {
      if (!entity.polygon) continue;
      const id = entity.id;
      let style = this.baseStyle(id);
      if (id === this.hoveredId) style = STYLE_HOVER;
      if (id === this.selectedId) style = STYLE_SELECTED;
      entity.polygon.material = new ColorMaterialProperty(style.fill);
      entity.polygon.outlineColor = new ConstantProperty(style.outline);
      entity.polygon.outlineWidth = new ConstantProperty(style.outlineWidth);
    }
  }

  /** Fly the camera to frame one observation's footprint WITH context.
   *
   * A raw ``viewer.flyTo(entity)`` fits the tiny CRISM footprint edge-to-edge,
   * zooming far past the global basemap's resolution (a blurry close-up). We
   * instead frame a padded rectangle around the footprint with a minimum extent,
   * so the scene stays legible and the footprint reads as a shape in context.
   */
  flyToObservation(id: string): void {
    const bbox = this.bboxes.get(id);
    if (!bbox) {
      const entity = this.dataSource.entities.getById(id);
      if (entity) {
        void this.viewer.flyTo(entity, { duration: 1.2 }).then(() => this.viewer.scene.requestRender());
      }
      return;
    }
    const [w, s, e, n] = bbox;
    const cx = (w + e) / 2;
    const cy = (s + n) / 2;
    // View ~4-5x the footprint span, with a floor so pinpoint scenes don't over-zoom.
    const half = Math.max(e - w, n - s, 0.4) * 2.2;
    const west = Math.max(-180, cx - half);
    const east = Math.min(180, cx + half);
    const south = Math.max(-90, cy - half);
    const north = Math.min(90, cy + half);
    this.flyToRectangle(west, south, east, north);
  }

  /** Fly to frame all loaded observation footprints combined (auto-centre layer view). */
  flyToAllObservations(duration = 2.0): void {
    if (this.bboxes.size === 0) return;
    let minW = 180;
    let minS = 90;
    let maxE = -180;
    let maxN = -90;
    for (const [w, s, e, n] of this.bboxes.values()) {
      if (w < minW) minW = w;
      if (s < minS) minS = s;
      if (e > maxE) maxE = e;
      if (n > maxN) maxN = n;
    }
    const cx = (minW + maxE) / 2;
    const cy = (minS + maxN) / 2;
    const span = Math.max(maxE - minW, maxN - minS, 1.5) * 1.6;
    const west = Math.max(-180, cx - span);
    const east = Math.min(180, cx + span);
    const south = Math.max(-90, cy - span);
    const north = Math.min(90, cy + span);
    this.flyToRectangle(west, south, east, north, duration);
  }

  /** Fly to a bbox rectangle. */
  flyToRectangle(west: number, south: number, east: number, north: number, duration = 1.8): void {
    this.viewer.camera.flyTo({
      destination: Rectangle.fromDegrees(west, south, east, north),
      duration,
      complete: () => this.viewer.scene.requestRender(),
    });
  }

  destroy(): void {
    this.dataSource.entities.removeAll();
    void this.viewer.dataSources.remove(this.dataSource, true);
  }
}
