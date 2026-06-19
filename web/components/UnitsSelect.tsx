"use client";

const LABELS: Record<string, string> = {
  mm: "Millimeters",
  cm: "Centimeters",
  m: "Meters",
  in: "Inches",
  ft: "Feet",
  unitless: "Unitless",
};

export function UnitsSelect({
  value,
  options,
  onChange,
}: {
  value: string;
  options: string[];
  onChange: (units: string) => void;
}) {
  return (
    <label className="units-select">
      <span>Drawing units</span>
      <select
        aria-label="Drawing units"
        value={value}
        onChange={(e) => onChange(e.target.value)}
      >
        {options.map((u) => (
          <option key={u} value={u}>
            {LABELS[u] ?? u}
          </option>
        ))}
      </select>
    </label>
  );
}
