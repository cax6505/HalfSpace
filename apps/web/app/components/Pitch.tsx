import { useId, type CSSProperties, type ReactNode } from "react";

export type PitchProps = {
  children?: ReactNode;
  showZones?: boolean;
  className?: string;
  label?: string;
  style?: CSSProperties;
};

/** StatsBomb coordinate space: 120 × 80, with a regulation pitch outline and markings. */
export function Pitch({ children, showZones = false, className, label = "Football pitch", style }: PitchProps) {
  const mowId = `pitch-mow-${useId().replaceAll(":", "")}`;
  return (
    <svg className={`pitch-svg ${className ?? ""}`} style={style} viewBox="0 0 120 80" role="img" aria-label={label}>
      <defs>
        <pattern id={mowId} width="20" height="80" patternUnits="userSpaceOnUse"><rect width="10" height="80" fill="#ffffff" opacity=".025" /></pattern>
      </defs>
      <rect x="0" y="0" width="120" height="80" rx="1.2" fill="var(--color-pitch)" />
      <rect x="0" y="0" width="120" height="80" rx="1.2" fill={`url(#${mowId})`} />
      <g fill="none" stroke="var(--color-pitch-line)" strokeWidth=".38" opacity=".9" vectorEffect="non-scaling-stroke">
        <rect x="1" y="1" width="118" height="78" rx=".7" />
        <line x1="60" y1="1" x2="60" y2="79" />
        <circle cx="60" cy="40" r="9.15" /><circle cx="60" cy="40" r=".45" fill="var(--color-pitch-line)" />
        <rect x="1" y="18" width="17" height="44" /><rect x="1" y="30" width="6" height="20" />
        <rect x="102" y="18" width="17" height="44" /><rect x="113" y="30" width="6" height="20" />
        <path d="M18 32.2 A9.15 9.15 0 0 1 18 47.8 M102 32.2 A9.15 9.15 0 0 0 102 47.8" />
        <circle cx="12" cy="40" r=".45" fill="var(--color-pitch-line)" /><circle cx="108" cy="40" r=".45" fill="var(--color-pitch-line)" />
        <path d="M1 36.8h-1v6.4h1 M119 36.8h1v6.4h-1" />
      </g>
      {showZones && <g className="zone-grid" aria-hidden="true">{Array.from({ length: 11 }, (_, i) => <line key={`v${i}`} x1={(i + 1) * 10} y1="1" x2={(i + 1) * 10} y2="79" />)}{Array.from({ length: 7 }, (_, i) => <line key={`h${i}`} x1="1" y1={(i + 1) * 10} x2="119" y2={(i + 1) * 10} />)}</g>}
      {children}
    </svg>
  );
}
