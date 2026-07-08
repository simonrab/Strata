// Material Symbols Outlined wrapper. The font is loaded in index.css; the icon
// name is rendered as a ligature (its text content becomes the glyph).
//
// Decorative icons default to aria-hidden so the ligature name never leaks to
// assistive tech (or to test queries like getByText). Pass `label` for a
// meaningful icon to give it an accessible name instead.
export function Icon({
  name,
  size = 20,
  fill = false,
  weight = 300,
  className = "",
  label,
}: {
  name: string;
  size?: number;
  fill?: boolean;
  weight?: number;
  className?: string;
  label?: string;
}) {
  return (
    <span
      className={`material-symbols-outlined select-none ${className}`}
      style={{
        fontSize: size,
        fontVariationSettings: `'FILL' ${fill ? 1 : 0}, 'wght' ${weight}, 'GRAD' 0, 'opsz' ${size}`,
      }}
      aria-hidden={label ? undefined : true}
      role={label ? "img" : undefined}
      aria-label={label}
    >
      {name}
    </span>
  );
}
