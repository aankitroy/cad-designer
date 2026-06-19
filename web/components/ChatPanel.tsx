"use client";
import { useEffect, useRef, useState } from "react";

export type Msg = { role: "user" | "assistant"; text: string };

export function ChatPanel({
  messages,
  onSend,
  busy,
}: {
  messages: Msg[];
  onSend: (m: string, file?: File) => void;
  busy: boolean;
}) {
  const [text, setText] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const el = scrollRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [messages, busy]);

  return (
    <div className="chat">
      <div className="panel-head">
        <span className="dot" />
        Assistant
      </div>

      <div className="chat-scroll" ref={scrollRef}>
        {messages.map((m, i) => (
          <div key={i} className={m.role === "user" ? "msg msg-user" : "msg msg-ai"}>
            {m.text}
          </div>
        ))}
        {busy && (
          <div className="typing" aria-label="Assistant is working">
            <span />
            <span />
            <span />
          </div>
        )}
      </div>

      {file && (
        <div className="attach-chip">
          <span>{file.name}</span>
          <button
            type="button"
            aria-label="Remove attachment"
            onClick={() => setFile(null)}
          >
            ×
          </button>
        </div>
      )}

      <form
        className="chat-form"
        onSubmit={(e) => {
          e.preventDefault();
          if ((text.trim() || file) && !busy) {
            onSend(text.trim(), file ?? undefined);
            setText("");
            setFile(null);
          }
        }}
      >
        <label className="attach-btn" aria-label="Attach DXF">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" aria-hidden="true">
            <path
              d="M21 11.5 12.5 20a5 5 0 0 1-7-7l8-8a3.5 3.5 0 0 1 5 5l-8 8a2 2 0 0 1-3-3l7.5-7.5"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </svg>
          <input
            type="file"
            accept=".dxf"
            className="vh"
            onChange={(e) => {
              const f = e.target.files?.[0];
              if (f) setFile(f);
              e.target.value = "";
            }}
          />
        </label>
        <input
          className="chat-input"
          placeholder="Describe a change…"
          value={text}
          onChange={(e) => setText(e.target.value)}
          disabled={busy}
        />
        <button type="submit" className="send-btn" aria-label="Send" disabled={busy}>
          <svg width="17" height="17" viewBox="0 0 24 24" fill="none" aria-hidden="true">
            <path
              d="M5 12h14M13 6l6 6-6 6"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </svg>
        </button>
      </form>
    </div>
  );
}
