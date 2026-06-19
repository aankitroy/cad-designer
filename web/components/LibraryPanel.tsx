"use client";
import { useState } from "react";
import { thumbnailUrl, type LibraryItem } from "../lib/api";

export function LibraryPanel({ items }: { items: LibraryItem[] }) {
  const [q, setQ] = useState("");
  const filtered = items.filter((it) =>
    it.name.toLowerCase().includes(q.trim().toLowerCase()),
  );
  return (
    <div className="library">
      <div className="panel-head">Components</div>
      <input
        className="library-search"
        placeholder="Search components…"
        value={q}
        onChange={(e) => setQ(e.target.value)}
      />
      <div className="library-list">
        {filtered.map((it) => (
          <div
            key={it.id}
            data-testid={`lib-${it.id}`}
            className="library-item"
            draggable
            onDragStart={(e) =>
              e.dataTransfer.setData("application/x-cad-component", it.id)
            }
            title={it.name}
          >
            <img
              className="library-thumb"
              src={thumbnailUrl(it.id)}
              alt=""
              loading="lazy"
              draggable={false}
            />
            <span className="library-name">{it.name}</span>
          </div>
        ))}
        {filtered.length === 0 && <div className="library-empty">No matches</div>}
      </div>
    </div>
  );
}
