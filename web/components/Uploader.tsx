"use client";

export function Uploader({ onUpload }: { onUpload: (f: File) => void }) {
  return (
    <label>
      Upload DXF
      <input
        type="file"
        accept=".dxf"
        onChange={(e) => {
          const f = e.target.files?.[0];
          if (f) onUpload(f);
        }}
      />
    </label>
  );
}
