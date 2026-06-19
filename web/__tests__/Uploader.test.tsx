import { it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Uploader } from "../components/Uploader";

it("calls onUpload with the chosen file", async () => {
  const onUpload = vi.fn();
  render(<Uploader onUpload={onUpload} />);
  const file = new File(["x"], "plan.dxf", { type: "application/dxf" });
  const input = screen.getByLabelText(/upload dxf/i) as HTMLInputElement;
  await userEvent.upload(input, file);
  expect(onUpload).toHaveBeenCalledWith(file);
});
