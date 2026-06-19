import type { Change } from "../lib/api";

export function ChangeLog({
  changes,
  onUndo,
}: {
  changes: Change[];
  onUndo: () => void;
}) {
  return (
    <div style={{ padding: 12, borderTop: "1px solid #eee" }}>
      <div style={{ display: "flex", justifyContent: "space-between" }}>
        <b>Changes</b>
        <button onClick={onUndo} disabled={changes.length === 0}>
          Undo last
        </button>
      </div>
      <ul>
        {changes.map((c, i) => (
          <li key={i}>{c.summary}</li>
        ))}
      </ul>
    </div>
  );
}
