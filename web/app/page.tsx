"use client";
import { useState } from "react";
import { Uploader } from "../components/Uploader";
import { SvgViewer } from "../components/SvgViewer";
import { ChatPanel, type Msg } from "../components/ChatPanel";
import { ChangeLog } from "../components/ChangeLog";
import { UnitsSelect } from "../components/UnitsSelect";
import {
  uploadDxf,
  sendChat,
  undo,
  setUnits,
  downloadUrl,
  type Change,
  type Layer,
} from "../lib/api";

export default function Home() {
  const [sid, setSid] = useState<string | null>(null);
  const [svg, setSvg] = useState("");
  const [fileName, setFileName] = useState<string | null>(null);
  const [layers, setLayers] = useState<Layer[]>([]);
  const [units, setUnitsState] = useState<string>("m");
  const [unitOptions, setUnitOptions] = useState<string[]>([]);
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
      setFileName(file.name);
      setLayers(res.summary.layers);
      setUnitsState(res.summary.units);
      setUnitOptions(res.summary.unit_options);
      setMessages([
        { role: "assistant", text: "Floor plan loaded. What would you like to change?" },
      ]);
      setChanges([]);
    } catch (e) {
      setError(String(e instanceof Error ? e.message : e));
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
      setLayers(res.layers);
      setMessages((m) => [...m, { role: "assistant", text: res.reply }]);
      setChanges((c) => [...c, ...res.changes]);
    } catch (e) {
      setError(String(e instanceof Error ? e.message : e));
    } finally {
      setBusy(false);
    }
  }

  async function handleUnitsChange(next: string) {
    setUnitsState(next); // optimistic
    if (!sid) return;
    try {
      const res = await setUnits(sid, next);
      setUnitsState(res.units);
    } catch (e) {
      setError(String(e instanceof Error ? e.message : e));
    }
  }

  async function handleUndo() {
    if (!sid) return;
    try {
      const res = await undo(sid);
      setSvg(res.svg);
      setLayers(res.layers);
      setChanges((c) => c.slice(0, -1));
    } catch (e) {
      setError(String(e instanceof Error ? e.message : e));
    }
  }

  const visibleLayers = layers.filter((l) => l.entity_count > 0);

  return (
    <div className="app">
      <header className="topbar">
        <div className="brand">
          <span className="brand-mark">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" aria-hidden="true">
              <path
                d="M4 20V6l8-3 8 3v14M4 20h16M9 20v-6h6v6"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
              />
            </svg>
          </span>
          CAD Designer
        </div>

        {fileName && (
          <div className="file-meta">
            <strong>{fileName}</strong>
            <span>
              {visibleLayers.length} layers · {changes.length} edits
            </span>
          </div>
        )}

        <div className="topbar-actions">
          <Uploader onUpload={handleUpload} label={sid ? "Replace" : "Upload DXF"} />
          {sid ? (
            <a className="btn btn-ghost" href={downloadUrl(sid)}>
              <svg width="15" height="15" viewBox="0 0 24 24" fill="none" aria-hidden="true">
                <path
                  d="M12 4v12m0 0 5-5m-5 5-5-5M5 20h14"
                  stroke="currentColor"
                  strokeWidth="2"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                />
              </svg>
              Download
            </a>
          ) : (
            <span className="btn btn-ghost disabled" aria-disabled="true">
              Download
            </span>
          )}
        </div>
      </header>

      <div className="workspace">
        <div className="canvas-wrap">
          <SvgViewer svg={svg} />
        </div>

        <aside className="sidebar">
          {sid && unitOptions.length > 0 && (
            <UnitsSelect
              value={units}
              options={unitOptions}
              onChange={handleUnitsChange}
            />
          )}
          {visibleLayers.length > 0 && (
            <div className="layers">
              {visibleLayers.map((l) => (
                <span className="chip" key={l.name}>
                  {l.name} <b>{l.entity_count}</b>
                </span>
              ))}
            </div>
          )}
          {error && (
            <div className="error-banner">
              <svg width="15" height="15" viewBox="0 0 24 24" fill="none" aria-hidden="true">
                <path
                  d="M12 8v5m0 3h.01M10.3 3.9 2 18a2 2 0 0 0 1.7 3h16.6a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0Z"
                  stroke="currentColor"
                  strokeWidth="2"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                />
              </svg>
              {error}
            </div>
          )}
          <ChatPanel messages={messages} onSend={handleSend} busy={busy} />
          <ChangeLog changes={changes} onUndo={handleUndo} />
        </aside>
      </div>
    </div>
  );
}
