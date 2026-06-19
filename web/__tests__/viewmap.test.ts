import { describe, it, expect } from "vitest";
import { worldToSvg, svgRectFromBBox, svgDeltaToMeters, svgToWorldMeters, type View } from "../lib/viewmap";

// 10 x 8 world (meters), viewBox 1,000,000 x 800,000, scale s = 100000
const view: View = {
  world: [0, 0, 10, 8],
  viewBox: [0, 0, 1_000_000, 800_000],
  meters_per_unit: 1.0,
};

it("worldToSvg maps origin to top-left (Y flipped)", () => {
  expect(worldToSvg(view, 0, 0)).toEqual([0, 800_000]); // world y=0 is bottom -> svg bottom
  expect(worldToSvg(view, 0, 8)).toEqual([0, 0]); // world y=8 (top) -> svg y=0
  expect(worldToSvg(view, 10, 8)).toEqual([1_000_000, 0]);
});

it("svgRectFromBBox builds an svg-space rect", () => {
  const r = svgRectFromBBox(view, [2, 2, 4, 3]); // 2 wide, 1 tall in world
  expect(r.width).toBe(200_000);
  expect(r.height).toBe(100_000);
  expect(r.x).toBe(200_000);
  expect(r.y).toBe(500_000); // top edge y=3 -> (8-3)*1e5
});

it("svgDeltaToMeters inverts scale with Y flip", () => {
  expect(svgDeltaToMeters(view, 100_000, 100_000)).toEqual([1, -1]);
});

it("svgDeltaToMeters honors meters_per_unit (mm)", () => {
  const mm: View = {
    world: [0, 0, 10000, 8000],
    viewBox: [0, 0, 1_000_000, 800_000],
    meters_per_unit: 0.001,
  };
  expect(svgDeltaToMeters(mm, 100_000, 0)[0]).toBeCloseTo(1, 6);
});

it("svgToWorldMeters inverts worldToSvg", () => {
  // svg (0, 0) -> world top-left (0, 8) meters; svg (1e6, 8e5) -> (10, 0)
  expect(svgToWorldMeters(view, 0, 0)).toEqual([0, 8]);
  expect(svgToWorldMeters(view, 1_000_000, 800_000)).toEqual([10, 0]);
});

it("svgToWorldMeters honors meters_per_unit (mm)", () => {
  const mm: View = { world: [0, 0, 10000, 8000], viewBox: [0, 0, 1_000_000, 800_000], meters_per_unit: 0.001 };
  // s = 100 svg/unit; svg x=1e6 -> 10000 units -> 10 m
  const [x, y] = svgToWorldMeters(mm, 1_000_000, 0);
  expect(x).toBeCloseTo(10, 6);
  expect(y).toBeCloseTo(8, 6); // svg y=0 -> world top (8000 units -> 8 m)
});
