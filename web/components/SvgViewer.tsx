"use client";
import { useRef, useState } from "react";

export function SvgViewer({ svg }: { svg: string }) {
  const [scale, setScale] = useState(1);
  const [pos, setPos] = useState({ x: 0, y: 0 });
  const drag = useRef<{ x: number; y: number } | null>(null);

  if (!svg) return <div style={{ padding: 24 }}>No drawing loaded</div>;

  return (
    <div
      style={{
        overflow: "hidden",
        width: "100%",
        height: "100%",
        cursor: "grab",
        background: "#fafafa",
      }}
      onWheel={(e) =>
        setScale((s) => Math.min(20, Math.max(0.1, s - e.deltaY * 0.001)))
      }
      onMouseDown={(e) => (drag.current = { x: e.clientX - pos.x, y: e.clientY - pos.y })}
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
        }}
        dangerouslySetInnerHTML={{ __html: svg }}
      />
    </div>
  );
}
