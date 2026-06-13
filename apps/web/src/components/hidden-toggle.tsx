export function HiddenToggle({ checked, onChange, label = "暗投" }: {
  checked: boolean;
  onChange: (checked: boolean) => void;
  label?: string;
}) {
  return (
    <label style={{ fontSize: "12px", display: "flex", alignItems: "center", gap: "6px" }}>
      <input type="checkbox" checked={checked} onChange={(e) => onChange(e.target.checked)} />
      {label}
    </label>
  );
}
