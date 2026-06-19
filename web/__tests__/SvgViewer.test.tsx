import { it, expect } from "vitest";
import { render } from "@testing-library/react";
import { SvgViewer } from "../components/SvgViewer";

it("renders the provided svg markup", () => {
  const { container } = render(<SvgViewer svg='<svg data-testid="dwg"></svg>' />);
  expect(container.querySelector('[data-testid="dwg"]')).not.toBeNull();
});

it("shows a placeholder when svg is empty", () => {
  const { getByText } = render(<SvgViewer svg="" />);
  expect(getByText(/no drawing/i)).toBeTruthy();
});
