import { it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { UnitsSelect } from "../components/UnitsSelect";

it("shows current units and reports a change", async () => {
  const onChange = vi.fn();
  render(
    <UnitsSelect value="ft" options={["mm", "cm", "m", "ft"]} onChange={onChange} />,
  );
  const select = screen.getByLabelText(/drawing units/i) as HTMLSelectElement;
  expect(select.value).toBe("ft");
  await userEvent.selectOptions(select, "mm");
  expect(onChange).toHaveBeenCalledWith("mm");
});
