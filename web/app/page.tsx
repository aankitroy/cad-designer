"use client";
import { useState } from "react";
import { Uploader } from "../components/Uploader";
import { SvgViewer } from "../components/SvgViewer";
import { ChatPanel, type Msg } from "../components/ChatPanel";
import { ChangeLog } from "../components/ChangeLog";
import { uploadDxf, sendChat, undo, downloadUrl, type Change } from "../lib/api";

export default function Home() {
  const [sid, setSid] = useState<string | null>(null);
  const [svg, setSvg] = useState("");
  const [messages, setMessages] = useState<Msg[]>([]);
  const [changes, setChanges] = useState<Change[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleUpload(file: File) {
    setError(null);
    try {
      const res = await uploadDxf(file);
      setSid(res.session_id);
      setSvg(res.svg);
      setMessages([
        { role: "assistant", text: "Floor plan loaded. What should I change?" },
      ]);
      setChanges([]);
    } catch (e) {
      setError(String(e));
    }
  }

  async function handleSend(msg: string) {
    if (!sid) return;
    setMessages((m) => [...m, { role: "user", text: msg }]);
    setBusy(true);
    setError(null);
    try {
      const res = await sendChat(sid, msg);
      setSvg(res.svg);
      setMessages((m) => [...m, { role: "assistant", text: res.reply }]);
      setChanges((c) => [...c, ...res.changes]);
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  }

  async function handleUndo() {
    if (!sid) return;
    const res = await undo(sid);
    setSvg(res.svg);
    setChanges((c) => c.slice(0, -1));
  }

  return (
    <main
      style={{ display: "grid", gridTemplateColumns: "1fr 380px", height: "100vh" }}
    >
      <section style={{ borderRight: "1px solid #eee", overflow: "hidden" }}>
        <div style={{ padding: 12, display: "flex", gap: 16, alignItems: "center" }}>
          <Uploader onUpload={handleUpload} />
          {sid && <a href={downloadUrl(sid)}>Download DXF</a>}
          {error && <span style={{ color: "crimson" }}>{error}</span>}
        </div>
        <div style={{ height: "calc(100vh - 56px)" }}>
          <SvgViewer svg={svg} />
        </div>
      </section>
      <aside style={{ display: "flex", flexDirection: "column", minHeight: 0 }}>
        <ChatPanel messages={messages} onSend={handleSend} busy={busy} />
        <ChangeLog changes={changes} onUndo={handleUndo} />
      </aside>
    </main>
  );
}
