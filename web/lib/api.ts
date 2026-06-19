const BASE = process.env.NEXT_PUBLIC_ENGINE_URL ?? "http://localhost:8000";

export type Layer = { name: string; entity_count: number };
export type UploadResult = {
  session_id: string;
  svg: string;
  summary: { layers: Layer[] };
};
export type Change = { op: string; handle: string; summary: string };
export type ChatResult = { reply: string; changes: Change[]; svg: string };

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

export async function sendChat(sid: string, message: string): Promise<ChatResult> {
  return asJson<ChatResult>(
    await fetch(`${BASE}/sessions/${sid}/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message }),
    }),
  );
}

export async function undo(sid: string): Promise<{ svg: string }> {
  return asJson<{ svg: string }>(
    await fetch(`${BASE}/sessions/${sid}/undo`, { method: "POST" }),
  );
}

export function downloadUrl(sid: string): string {
  return `${BASE}/sessions/${sid}/dxf`;
}
