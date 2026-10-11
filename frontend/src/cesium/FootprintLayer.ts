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

  constructor(viewer: Viewer) {
    this.viewer = viewer;
    void viewer.dataSources.add(this.dataSource);
  }

  /** Replace all footprint entities from observation summaries. */
  load(observations: ObservationSummary[]): void {
    this.dataSource.entities.removeAll();
    this.suitable.clear();
    for (const obs of observations) {
      this.suitable.set(obs.id, obs.analysis_suitable);
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

  /** Fly the camera to frame one observation's footprint. */
  flyToObservation(id: string): void {
    const entity = this.dataSource.entities.getById(id);
    if (!entity) return;
    void this.viewer.flyTo(entity, { duration: 1.2 }).then(() => this.viewer.scene.requestRender());
  }

  /** Fly to a bbox rectangle (used when no entity exists yet). */
  flyToRectangle(west: number, south: number, east: number, north: number): void {
    this.viewer.camera.flyTo({
      destination: Rectangle.fromDegrees(west, south, east, north),
      duration: 1.2,
      complete: () => this.viewer.scene.requestRender(),
    });
  }

  destroy(): void {
    this.dataSource.entities.removeAll();
    void this.viewer.dataSources.remove(this.dataSource, true);
  }
}
