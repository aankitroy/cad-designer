"use client";
import { useEffect, useRef, useState } from "react";
import { svgRectFromBBox, svgDeltaToMeters, type View } from "../lib/viewmap";
import type { Selectable } from "../lib/api";

type Props = {
  svg: string;
  view?: View | null;
  selectables?: Selectable[];
  selected?: string | null;
  onSelect?: (handle: string | null) => void;
  onEdit?: (name: string, args: Record<string, unknown>) => void;
};

export function SvgViewer({
  svg,
  view = null,
  selectables = [],
  selected = null,
  onSelect,
  onEdit,
}: Props) {
  const [scale, setScale] = useState(1);
  const [pos, setPos] = useState({ x: 0, y: 0 });
  const pan = useRef<{ x: number; y: number } | null>(null);
  const stageRef = useRef<HTMLDivElement>(null);
  const overlayRef = useRef<SVGSVGElement>(null);
  const dragRef = useRef<{ handle: string; startX: number; startY: number } | null>(null);
  const rotRef = useRef<{ handle: string; cx: number; cy: number; startX: number; startY: number } | null>(null);

  // keyboard: delete + arrow nudge on the selected entity
  useEffect(() => {
    if (!selected || !onEdit) return;
    function onKey(e: KeyboardEvent) {
      if (e.key === "Delete" || e.key === "Backspace") {
        e.preventDefault();
        onEdit!("delete_entity", { handle: selected });
      } else if (e.key.startsWith("Arrow")) {
        e.preventDefault();
        const step = 0.1;
        const d: Record<string, [number, number]> = {
          ArrowRight: [step, 0],
          ArrowLeft: [-step, 0],
          ArrowUp: [0, step],
          ArrowDown: [0, -step],
        };
        const [dx, dy] = d[e.key] ?? [0, 0];
        onEdit!("move_entity", { handle: selected, dx_m: dx, dy_m: dy });
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [selected, onEdit]);

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

  // map a pointer event to overlay-svg coordinates via the browser CTM
  function toSvg(e: React.PointerEvent): { x: number; y: number } {
    const svgEl = overlayRef.current!;
    const pt = svgEl.createSVGPoint();
    pt.x = e.clientX;
    pt.y = e.clientY;
    const ctm = svgEl.getScreenCTM();
    const local = ctm ? pt.matrixTransform(ctm.inverse()) : pt;
    return { x: local.x, y: local.y };
  }

  return (
    <>
      <div
        ref={stageRef}
        className="canvas-stage"
        onWheel={(e) =>
          setScale((s) => Math.min(20, Math.max(0.05, s - e.deltaY * 0.0015)))
        }
        onMouseDown={(e) => (pan.current = { x: e.clientX - pos.x, y: e.clientY - pos.y })}
        onMouseUp={() => (pan.current = null)}
        onMouseLeave={() => (pan.current = null)}
        onMouseMove={(e) => {
          if (pan.current)
            setPos({ x: e.clientX - pan.current.x, y: e.clientY - pan.current.y });
        }}
      >
        <div
          style={{
            transform: `translate(${pos.x}px, ${pos.y}px) scale(${scale})`,
            transformOrigin: "0 0",
            width: "100%",
            height: "100%",
            position: "relative",
          }}
        >
          <div style={{ width: "100%", height: "100%" }} dangerouslySetInnerHTML={{ __html: svg }} />
          {view && (
            <svg
              ref={overlayRef}
              className="edit-overlay"
              viewBox={view.viewBox.join(" ")}
              preserveAspectRatio="xMidYMid meet"
              style={{ position: "absolute", inset: 0, width: "100%", height: "100%" }}
            >
              {selectables.map((s) => {
                const r = svgRectFromBBox(view, s.bbox);
                const isSel = s.handle === selected;
                const cx = r.x + r.width / 2;
                const handleY = r.y - r.height * 0.25 - 1;
                return (
                  <g key={s.handle}>
                    <rect
                      data-testid={`sel-${s.handle}`}
                      x={r.x}
                      y={r.y}
                      width={r.width}
                      height={r.height}
                      className={isSel ? "sel-box sel-box-active" : "sel-box"}
                      onPointerDown={(e) => {
                        e.stopPropagation();
                        onSelect?.(s.handle);
                        const p = toSvg(e);
                        dragRef.current = { handle: s.handle, startX: p.x, startY: p.y };
                        (e.target as Element).setPointerCapture?.(e.pointerId);
                      }}
                      onPointerUp={(e) => {
                        const d = dragRef.current;
                        dragRef.current = null;
                        if (!d || !view || !onEdit) return;
                        const p = toSvg(e);
                        const [dx_m, dy_m] = svgDeltaToMeters(view, p.x - d.startX, p.y - d.startY);
                        if (dx_m !== 0 || dy_m !== 0)
                          onEdit("move_entity", { handle: d.handle, dx_m, dy_m });
                      }}
                    />
                    {isSel && (
                      <circle
                        data-testid={`rotate-${s.handle}`}
                        cx={cx}
                        cy={handleY}
                        r={Math.max(r.width, r.height) * 0.06 + 3000}
                        className="rotate-handle"
                        onPointerDown={(e) => {
                          e.stopPropagation();
                          const p = toSvg(e);
                          rotRef.current = {
                            handle: s.handle,
                            cx,
                            cy: r.y + r.height / 2,
                            startX: p.x,
                            startY: p.y,
                          };
                          (e.target as Element).setPointerCapture?.(e.pointerId);
                        }}
                        onPointerUp={(e) => {
                          const rt = rotRef.current;
                          rotRef.current = null;
                          if (!rt || !onEdit) return;
                          const p = toSvg(e);
                          const a0 = Math.atan2(rt.startY - rt.cy, rt.startX - rt.cx);
                          const a1 = Math.atan2(p.y - rt.cy, p.x - rt.cx);
                          let deg = ((a1 - a0) * 180) / Math.PI;
                          deg = Math.round(deg / 15) * 15; // snap 15°
                          onEdit("rotate_entity", { handle: rt.handle, angle_deg: deg });
                        }}
                      />
                    )}
                  </g>
                );
              })}
            </svg>
          )}
        </div>
      </div>

      <div className="canvas-controls">
        <button aria-label="Zoom in" onClick={() => setScale((s) => Math.min(20, s * 1.25))}>
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" aria-hidden="true">
            <path d="M12 5v14M5 12h14" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
          </svg>
        </button>
        <button aria-label="Zoom out" onClick={() => setScale((s) => Math.max(0.05, s * 0.8))}>
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" aria-hidden="true">
            <path d="M5 12h14" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
          </svg>
        </button>
        <button aria-label="Reset view" onClick={() => { setScale(1); setPos({ x: 0, y: 0 }); }}>
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
        Scroll to zoom · drag to pan · click an item to edit · {Math.round(scale * 100)}%
      </div>
    </>
  );
}
