"use client";
import { useEffect, useRef, useState } from "react";

export type Msg = { role: "user" | "assistant"; text: string };

export function ChatPanel({
  messages,
  onSend,
  busy,
}: {
  messages: Msg[];
  onSend: (m: string) => void;
  busy: boolean;
}) {
  const [text, setText] = useState("");
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

      <form
        className="chat-form"
        onSubmit={(e) => {
          e.preventDefault();
          if (text.trim() && !busy) {
            onSend(text.trim());
            setText("");
          }
        }}
      >
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
