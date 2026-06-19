"use client";
import { useState } from "react";

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
  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100%" }}>
      <div style={{ flex: 1, overflowY: "auto", padding: 12 }}>
        {messages.map((m, i) => (
          <p key={i} style={{ color: m.role === "user" ? "#222" : "#0b6" }}>
            <b>{m.role === "user" ? "You" : "AI"}:</b> {m.text}
          </p>
        ))}
      </div>
      <form
        onSubmit={(e) => {
          e.preventDefault();
          if (text.trim()) {
            onSend(text.trim());
            setText("");
          }
        }}
        style={{ display: "flex", gap: 8, padding: 12 }}
      >
        <input
          placeholder="Describe a change…"
          value={text}
          onChange={(e) => setText(e.target.value)}
          disabled={busy}
          style={{ flex: 1 }}
        />
        <button type="submit" disabled={busy}>
          Send
        </button>
      </form>
    </div>
  );
}
