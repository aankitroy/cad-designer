import { it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { SvgViewer } from "../components/SvgViewer";
import type { View, Selectable } from "../lib/api";

const view: View = { world: [0, 0, 10, 8], viewBox: [0, 0, 1_000_000, 800_000], meters_per_unit: 1.0 };
const sel: Selectable = { handle: "H1", type: "INSERT", label: "chair", bbox: [4, 3, 6, 5] };

// jsdom has no getScreenCTM/createSVGPoint; identity CTM means screen coords == svg coords.
beforeEach(() => {
  // @ts-expect-error test shim
  SVGElement.prototype.getScreenCTM = function () {
    return { inverse: () => ({}) };
  };
  // @ts-expect-error test shim
  SVGSVGElement.prototype.createSVGPoint = function () {
    const p = { x: 0, y: 0, matrixTransform: () => ({ x: p.x, y: p.y }) };
    return p;
  };
  // @ts-expect-error test shim
  Element.prototype.setPointerCapture = function () {};
});

it("renders the provided svg markup", () => {
  const { container } = render(<SvgViewer svg='<svg data-testid="dwg"></svg>' />);
  expect(container.querySelector('[data-testid="dwg"]')).not.toBeNull();
});

it("shows a placeholder when svg is empty", () => {
  render(<SvgViewer svg="" />);
  expect(screen.getByText(/no drawing/i)).toBeTruthy();
});

it("selecting an item via the overlay calls onSelect", () => {
  const onSelect = vi.fn();
  render(
    <SvgViewer svg="<svg/>" view={view} selectables={[sel]} onSelect={onSelect} onEdit={vi.fn()} />,
  );
  fireEvent.pointerDown(screen.getByTestId("sel-H1"));
  expect(onSelect).toHaveBeenCalledWith("H1");
});

it("Delete key on a selected item calls onEdit delete_entity", () => {
  const onEdit = vi.fn().mockResolvedValue(undefined);
  render(
    <SvgViewer svg="<svg/>" view={view} selectables={[sel]} selected="H1" onEdit={onEdit} onSelect={vi.fn()} />,
  );
  fireEvent.keyDown(window, { key: "Delete" });
  expect(onEdit).toHaveBeenCalledWith("delete_entity", { handle: "H1" });
});

it("arrow key nudges by 0.1m via move_entity", () => {
  const onEdit = vi.fn().mockResolvedValue(undefined);
  render(
    <SvgViewer svg="<svg/>" view={view} selectables={[sel]} selected="H1" onEdit={onEdit} onSelect={vi.fn()} />,
  );
  fireEvent.keyDown(window, { key: "ArrowRight" });
  expect(onEdit).toHaveBeenCalledWith("move_entity", { handle: "H1", dx_m: 0.1, dy_m: 0 });
});

it("dragging the rotate handle calls onEdit rotate_entity", () => {
  const onEdit = vi.fn().mockResolvedValue(undefined);
  render(
    <SvgViewer svg="<svg/>" view={view} selectables={[sel]} selected="H1" onEdit={onEdit} onSelect={vi.fn()} />,
  );
  const handle = screen.getByTestId("rotate-H1");
  fireEvent.pointerDown(handle, { clientX: 0, clientY: 0 });
  fireEvent.pointerUp(handle, { clientX: 0, clientY: 0 });
  expect(onEdit).toHaveBeenCalledWith("rotate_entity", expect.objectContaining({ handle: "H1" }));
});
