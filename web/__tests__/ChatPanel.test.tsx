import { it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ChatPanel } from "../components/ChatPanel";

it("submits a message and clears the input", async () => {
  const onSend = vi.fn();
  render(<ChatPanel messages={[]} onSend={onSend} busy={false} />);
  const input = screen.getByPlaceholderText(/describe a change/i);
  await userEvent.type(input, "move counter 2m left");
  await userEvent.click(screen.getByRole("button", { name: /send/i }));
  expect(onSend).toHaveBeenCalledWith("move counter 2m left", undefined);
});

it("shows the attached filename and submits message + file", async () => {
  const onSend = vi.fn();
  render(<ChatPanel messages={[]} onSend={onSend} busy={false} />);
  const file = new File(["x"], "chair.dxf", { type: "application/dxf" });
  const input = screen.getByLabelText(/attach dxf/i) as HTMLInputElement;
  await userEvent.upload(input, file);
  expect(screen.getByText("chair.dxf")).toBeTruthy();
  await userEvent.type(screen.getByPlaceholderText(/describe a change/i), "place it");
  await userEvent.click(screen.getByRole("button", { name: /send/i }));
  expect(onSend).toHaveBeenCalledWith("place it", file);
});

it("renders existing messages", () => {
  render(
    <ChatPanel
      messages={[{ role: "assistant", text: "Done." }]}
      onSend={vi.fn()}
      busy={false}
    />,
  );
  expect(screen.getByText("Done.")).toBeTruthy();
});
