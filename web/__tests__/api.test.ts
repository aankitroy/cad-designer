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

it("sendChat sends multipart when a file is attached", async () => {
  const body = { reply: "ok", changes: [], svg: "<svg/>", layers: [] };
  global.fetch = vi.fn().mockResolvedValue({ ok: true, json: async () => body });
  const file = new File(["x"], "chair.dxf");
  await sendChat("s1", "place it", file);
  const call = (global.fetch as ReturnType<typeof vi.fn>).mock.calls[0];
  expect(call[1].body).toBeInstanceOf(FormData);
});

it("sendChat sends form fields without a file too", async () => {
  const body = { reply: "ok", changes: [], svg: "<svg/>", layers: [] };
  global.fetch = vi.fn().mockResolvedValue({ ok: true, json: async () => body });
  await sendChat("s1", "hello");
  const call = (global.fetch as ReturnType<typeof vi.fn>).mock.calls[0];
  expect(call[1].body).toBeInstanceOf(FormData);
});

it("throws on non-ok", async () => {
  global.fetch = vi
    .fn()
    .mockResolvedValue({ ok: false, status: 422, json: async () => ({ detail: "bad" }) });
  await expect(uploadDxf(new File(["x"], "p.dxf"))).rejects.toThrow();
});

it("getSelectables returns selectables and view", async () => {
  const body = { selectables: [{ handle: "A", type: "INSERT", label: "chair", bbox: [0, 0, 1, 1] }], view: null };
  global.fetch = vi.fn().mockResolvedValue({ ok: true, json: async () => body });
  const { getSelectables } = await import("../lib/api");
  const res = await getSelectables("s1");
  expect(res.selectables[0].handle).toBe("A");
  const call = (global.fetch as ReturnType<typeof vi.fn>).mock.calls[0];
  expect(call[0]).toContain("/sessions/s1/selectables");
});

it("manualEdit posts name+args as json", async () => {
  const body = { change: { op: "move_entity" }, svg: "<svg/>", view: null, layers: [], selectables: [] };
  global.fetch = vi.fn().mockResolvedValue({ ok: true, json: async () => body });
  const { manualEdit } = await import("../lib/api");
  const res = await manualEdit("s1", "move_entity", { handle: "A", dx_m: 1, dy_m: 0 });
  expect(res.change.op).toBe("move_entity");
  const call = (global.fetch as ReturnType<typeof vi.fn>).mock.calls[0];
  expect(call[0]).toContain("/sessions/s1/edit");
  expect(JSON.parse(call[1].body)).toEqual({ name: "move_entity", args: { handle: "A", dx_m: 1, dy_m: 0 } });
});

it("getLibrary returns the component list", async () => {
  const body = { components: [{ id: "chair", name: "CHAIR UNIT" }] };
  global.fetch = vi.fn().mockResolvedValue({ ok: true, json: async () => body });
  const { getLibrary } = await import("../lib/api");
  const res = await getLibrary();
  expect(res.components[0].id).toBe("chair");
});

it("thumbnailUrl builds the right path", async () => {
  const { thumbnailUrl } = await import("../lib/api");
  expect(thumbnailUrl("chair")).toContain("/library/chair/thumbnail.svg");
});

it("placeFromLibrary posts id + coords", async () => {
  const body = { change: { op: "place_component" }, svg: "<svg/>", view: null, layers: [], selectables: [] };
  global.fetch = vi.fn().mockResolvedValue({ ok: true, json: async () => body });
  const { placeFromLibrary } = await import("../lib/api");
  const res = await placeFromLibrary("s1", "chair", 5, 4);
  expect(res.change.op).toBe("place_component");
  const call = (global.fetch as ReturnType<typeof vi.fn>).mock.calls[0];
  expect(call[0]).toContain("/sessions/s1/library/place");
  expect(JSON.parse(call[1].body)).toMatchObject({ id: "chair", x_m: 5, y_m: 4 });
});
