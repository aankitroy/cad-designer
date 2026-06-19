"use client";

export function Uploader({
  onUpload,
  label = "Upload DXF",
}: {
  onUpload: (f: File) => void;
  label?: string;
}) {
  return (
    <label className="btn btn-primary" style={{ position: "relative" }}>
      <svg width="15" height="15" viewBox="0 0 24 24" fill="none" aria-hidden="true">
        <path
          d="M12 16V4m0 0L7 9m5-5 5 5M5 20h14"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      </svg>
      {label}
      <input
        type="file"
        accept=".dxf"
        className="vh"
        onChange={(e) => {
          const f = e.target.files?.[0];
          if (f) onUpload(f);
          e.target.value = ""; // allow re-uploading the same file
        }}
      />
    </label>
  );
}
