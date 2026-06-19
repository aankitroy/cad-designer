import { describe, it, expect, vi, beforeEach } from "vitest";
import { uploadDxf, sendChat, setUnits } from "../lib/api";

beforeEach(() => {
  vi.restoreAllMocks();
});

it("uploadDxf posts multipart and returns parsed body", async () => {
  const body = { session_id: "s1", svg: "<svg/>", summary: { layers: [] } };
  global.fetch = vi.fn().mockResolvedValue({ ok: true, json: async () => body });
  const file = new File(["x"], "p.dxf");
  const res = await uploadDxf(file);
  expect(res.session_id).toBe("s1");
  expect((global.fetch as ReturnType<typeof vi.fn>).mock.calls[0][0]).toContain(
    "/sessions",
  );
});

it("sendChat posts json message", async () => {
  const body = { reply: "ok", changes: [], svg: "<svg/>" };
  global.fetch = vi.fn().mockResolvedValue({ ok: true, json: async () => body });
  const res = await sendChat("s1", "move it");
  expect(res.reply).toBe("ok");
});

it("setUnits posts the chosen units", async () => {
  global.fetch = vi.fn().mockResolvedValue({ ok: true, json: async () => ({ units: "mm" }) });
  const res = await setUnits("s1", "mm");
  expect(res.units).toBe("mm");
  const call = (global.fetch as ReturnType<typeof vi.fn>).mock.calls[0];
  expect(call[0]).toContain("/sessions/s1/units");
  expect(JSON.parse(call[1].body)).toEqual({ units: "mm" });
});

it("throws on non-ok", async () => {
  global.fetch = vi
    .fn()
    .mockResolvedValue({ ok: false, status: 422, json: async () => ({ detail: "bad" }) });
  await expect(uploadDxf(new File(["x"], "p.dxf"))).rejects.toThrow();
});
