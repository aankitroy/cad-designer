"use client";
import { useRef, useState } from "react";

export function SvgViewer({ svg }: { svg: string }) {
  const [scale, setScale] = useState(1);
  const [pos, setPos] = useState({ x: 0, y: 0 });
  const drag = useRef<{ x: number; y: number } | null>(null);
  const stageRef = useRef<HTMLDivElement>(null);

  function zoomAroundCenter(factor: number) {
    const el = stageRef.current;
    const cx = el ? el.clientWidth / 2 : 0;
    const cy = el ? el.clientHeight / 2 : 0;
    setScale((s) => {
      const next = Math.min(20, Math.max(0.05, s * factor));
      const applied = next / s;
      setPos((p) => ({ x: cx - (cx - p.x) * applied, y: cy - (cy - p.y) * applied }));
      return next;
    });
  }

  function resetView() {
    setScale(1);
    setPos({ x: 0, y: 0 });
  }

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
        ref={stageRef}
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

      <div className="canvas-controls">
        <button aria-label="Zoom in" onClick={() => zoomAroundCenter(1.25)}>
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" aria-hidden="true">
            <path d="M12 5v14M5 12h14" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
          </svg>
        </button>
        <button aria-label="Zoom out" onClick={() => zoomAroundCenter(0.8)}>
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" aria-hidden="true">
            <path d="M5 12h14" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
          </svg>
        </button>
        <button aria-label="Reset view" onClick={resetView}>
          <svg width="15" height="15" viewBox="0 0 24 24" fill="none" aria-hidden="true">
            <path
              d="M3 12a9 9 0 1 0 3-6.7L3 8m0-5v5h5"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </svg>
        </button>
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
