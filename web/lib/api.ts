const BASE = process.env.NEXT_PUBLIC_ENGINE_URL ?? "http://localhost:8000";

export type Layer = { name: string; entity_count: number };
export type Summary = { layers: Layer[]; units: string; unit_options: string[] };
export type View = {
  world: [number, number, number, number];
  viewBox: [number, number, number, number];
  meters_per_unit: number;
};
export type Selectable = {
  handle: string;
  type: string;
  label: string;
  bbox: [number, number, number, number];
};
export type UploadResult = {
  session_id: string;
  svg: string;
  summary: Summary;
  view?: View | null;
};
export type Change = { op: string; handle: string; summary: string };
export type ChatResult = {
  reply: string;
  changes: Change[];
  svg: string;
  layers: Layer[];
  view?: View | null;
};
export type EditResult = {
  change: Change;
  svg: string;
  view: View | null;
  layers: Layer[];
  selectables: Selectable[];
};

async function asJson<T>(res: Response): Promise<T> {
  if (!res.ok) {
    const detail = await res.json().catch(() => ({}));
    throw new Error(
      (detail as { detail?: string }).detail ?? `Request failed (${res.status})`,
    );
  }
  return res.json() as Promise<T>;
}

export async function uploadDxf(file: File): Promise<UploadResult> {
  const fd = new FormData();
  fd.append("file", file);
  return asJson<UploadResult>(
    await fetch(`${BASE}/sessions`, { method: "POST", body: fd }),
  );
}

export async function sendChat(
  sid: string,
  message: string,
  file?: File,
): Promise<ChatResult> {
  const fd = new FormData();
  fd.append("message", message);
  if (file) fd.append("file", file);
  return asJson<ChatResult>(
    await fetch(`${BASE}/sessions/${sid}/chat`, { method: "POST", body: fd }),
  );
}

export async function undo(
  sid: string,
): Promise<{ svg: string; layers: Layer[]; view: View | null }> {
  return asJson(await fetch(`${BASE}/sessions/${sid}/undo`, { method: "POST" }));
}

export async function getSelectables(
  sid: string,
): Promise<{ selectables: Selectable[]; view: View | null }> {
  return asJson(await fetch(`${BASE}/sessions/${sid}/selectables`));
}

export async function manualEdit(
  sid: string,
  name: string,
  args: Record<string, unknown>,
): Promise<EditResult> {
  return asJson<EditResult>(
    await fetch(`${BASE}/sessions/${sid}/edit`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name, args }),
    }),
  );
}

export async function setUnits(sid: string, unitsName: string): Promise<{ units: string }> {
  return asJson<{ units: string }>(
    await fetch(`${BASE}/sessions/${sid}/units`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ units: unitsName }),
    }),
  );
}

export function downloadUrl(sid: string): string {
  return `${BASE}/sessions/${sid}/dxf`;
}

export type LibraryItem = { id: string; name: string };

export async function getLibrary(): Promise<{ components: LibraryItem[] }> {
  return asJson(await fetch(`${BASE}/library`));
}

export function thumbnailUrl(id: string): string {
  return `${BASE}/library/${id}/thumbnail.svg`;
}

export async function placeFromLibrary(
  sid: string,
  id: string,
  x_m: number,
  y_m: number,
  rotation_deg?: number,
  layer?: string,
): Promise<EditResult> {
  return asJson<EditResult>(
    await fetch(`${BASE}/sessions/${sid}/library/place`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ id, x_m, y_m, rotation_deg, layer }),
    }),
  );
}
