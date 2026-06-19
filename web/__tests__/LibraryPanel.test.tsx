import { it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { LibraryPanel } from "../components/LibraryPanel";

const items = [
  { id: "euro", name: "EURO 1040 x 1175" },
  { id: "chair", name: "CHAIR UNIT" },
];

it("renders rows for each component", () => {
  render(<LibraryPanel items={items} />);
  expect(screen.getByText("EURO 1040 x 1175")).toBeTruthy();
  expect(screen.getByText("CHAIR UNIT")).toBeTruthy();
});

it("filters by search text", async () => {
  render(<LibraryPanel items={items} />);
  await userEvent.type(screen.getByPlaceholderText(/search/i), "chair");
  expect(screen.queryByText("EURO 1040 x 1175")).toBeNull();
  expect(screen.getByText("CHAIR UNIT")).toBeTruthy();
});

it("sets the component id on drag start", () => {
  render(<LibraryPanel items={items} />);
  const row = screen.getByTestId("lib-euro");
  const setData = vi.fn();
  fireEvent.dragStart(row, { dataTransfer: { setData } });
  expect(setData).toHaveBeenCalledWith("application/x-cad-component", "euro");
});
