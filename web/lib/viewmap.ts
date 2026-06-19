export type View = {
  world: [number, number, number, number]; // xmin,ymin,xmax,ymax (drawing units)
  viewBox: [number, number, number, number]; // 0,0,VW,VH
  meters_per_unit: number;
};

function scale(view: View): number {
  const [xmin, , xmax] = view.world;
  return view.viewBox[2] / (xmax - xmin);
}

export function worldToSvg(view: View, wx: number, wy: number): [number, number] {
  const [xmin, , , ymax] = view.world;
  const s = scale(view);
  return [(wx - xmin) * s, (ymax - wy) * s];
}

export function svgRectFromBBox(
  view: View,
  bbox: [number, number, number, number],
): { x: number; y: number; width: number; height: number } {
  const [x0, y0, x1, y1] = bbox;
  const [sx0, sy1] = worldToSvg(view, x0, y1); // world top (y1) -> svg top
  const [sx1, sy0] = worldToSvg(view, x1, y0);
  return {
    x: Math.min(sx0, sx1),
    y: Math.min(sy0, sy1),
    width: Math.abs(sx1 - sx0),
    height: Math.abs(sy0 - sy1),
  };
}

export function svgToWorldMeters(view: View, sx: number, sy: number): [number, number] {
  const [xmin, , , ymax] = view.world;
  const s = scale(view);
  const xUnits = xmin + sx / s;
  const yUnits = ymax - sy / s; // Y flip
  return [xUnits * view.meters_per_unit, yUnits * view.meters_per_unit];
}

export function svgDeltaToMeters(
  view: View,
  dxSvg: number,
  dySvg: number,
): [number, number] {
  const s = scale(view);
  const dxUnits = dxSvg / s;
  const dyUnits = -dySvg / s; // Y flip
  return [dxUnits * view.meters_per_unit, dyUnits * view.meters_per_unit];
}
