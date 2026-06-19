import type { Change } from "../lib/api";

export function ChangeLog({
  changes,
  onUndo,
}: {
  changes: Change[];
  onUndo: () => void;
}) {
  return (
    <div className="changelog">
      <div className="changelog-head">
        <b>Changes{changes.length > 0 ? ` · ${changes.length}` : ""}</b>
        <button className="undo-btn" onClick={onUndo} disabled={changes.length === 0}>
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" aria-hidden="true">
            <path
              d="M9 14 4 9l5-5M4 9h11a5 5 0 0 1 0 10h-3"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </svg>
          Undo last
        </button>
      </div>
      {changes.length === 0 ? (
        <p className="changelog-empty">Edits you make will be listed here.</p>
      ) : (
        <ul className="changelog-list">
          {changes.map((c, i) => (
            <li key={i} className="change-item">
              <span className="marker" />
              {c.summary}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
