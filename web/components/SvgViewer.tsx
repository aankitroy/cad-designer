"use client";
import { useRef, useState } from "react";

export function SvgViewer({ svg }: { svg: string }) {
  const [scale, setScale] = useState(1);
  const [pos, setPos] = useState({ x: 0, y: 0 });
  const drag = useRef<{ x: number; y: number } | null>(null);

  if (!svg) {
    return (
      <div className="empty">
        <div className="empty-icon">
          <svg width="30" height="30" viewBox="0 0 24 24" fill="none" aria-hidden="true">
            <path
              d="M3 9h18M9 21V9M5 3h14a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2Z"
              stroke="currentColor"
              strokeWidth="1.8"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </svg>
        </div>
        <h2>No drawing loaded</h2>
        <p>
          Upload a <code>.dxf</code> floor plan to view it here, then describe
          changes in plain language on the right.
        </p>
      </div>
    );
  }

  return (
    <>
      <div
        className="canvas-stage"
        onWheel={(e) =>
          setScale((s) => Math.min(20, Math.max(0.05, s - e.deltaY * 0.0015)))
        }
        onMouseDown={(e) =>
          (drag.current = { x: e.clientX - pos.x, y: e.clientY - pos.y })
        }
        onMouseUp={() => (drag.current = null)}
        onMouseLeave={() => (drag.current = null)}
        onMouseMove={(e) => {
          if (drag.current)
            setPos({ x: e.clientX - drag.current.x, y: e.clientY - drag.current.y });
        }}
      >
        <div
          style={{
            transform: `translate(${pos.x}px, ${pos.y}px) scale(${scale})`,
            transformOrigin: "0 0",
            width: "100%",
            height: "100%",
          }}
          dangerouslySetInnerHTML={{ __html: svg }}
        />
      </div>
      <div className="zoom-hint">
        <svg width="13" height="13" viewBox="0 0 24 24" fill="none" aria-hidden="true">
          <circle cx="11" cy="11" r="7" stroke="currentColor" strokeWidth="2" />
          <path d="m20 20-3-3" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
        </svg>
        Scroll to zoom · drag to pan · {Math.round(scale * 100)}%
      </div>
    </>
  );
}
