import { useId } from "react";

export type Point = { x: number; y: number };
export type PlayerMarkerProps = Point & { label: string; team: "home" | "away"; active?: boolean; number?: string | number };
export function PlayerMarker({ x, y, label, team, active = false, number }: PlayerMarkerProps) {
  const fill = team === "home" ? "#d7ff54" : "#84d7ff";
  return <g transform={`translate(${x} ${y})`} role="img" aria-label={`${label}${number ? `, number ${number}` : ""}${active ? ", active player" : ""}`}>
    {active && <circle r="3.5" fill="none" stroke={fill} strokeWidth=".35" opacity=".8" />}
    <circle r="2.1" fill={fill} stroke="#111713" strokeWidth=".55" />
    {number != null && <text y=".7" textAnchor="middle" fontSize="1.8" fontWeight="800" fill="#182016">{number}</text>}
  </g>;
}

export type BallMarkerProps = Point & { label?: string; state?: "tracked" | "interpolated"; confidence?: number };
export function BallMarker({ x, y, label = "Ball", state = "tracked", confidence }: BallMarkerProps) {
  const status = state === "interpolated" ? "interpolated" : "tracked";
  return <g transform={`translate(${x} ${y})`} role="img" aria-label={`${label}, ${status}${confidence == null ? "" : `, ${Math.round(confidence * 100)} percent confidence`}`}>
    <circle r="2.4" fill="#fffdf5" stroke="#111713" strokeWidth=".45" />
    <path d="M-.8-.8 0-1.15 .8-.8 .55.15 0 .7 -.55.15Z" fill="#202720" />
  </g>;
}

export type PassArrowProps = { from: Point; to: Point; progress?: number; color?: string; label?: string };
export function PassArrow({ from, to, progress = 1, color = "#f4f2e9", label = "Pass" }: PassArrowProps) {
  const id = `arrow-${useId().replaceAll(":", "")}`;
  const safeProgress = Math.max(0, Math.min(1, progress));
  return <g role="img" aria-label={`${label}, ${Math.round(safeProgress * 100)} percent complete`}>
    <defs><marker id={id} markerWidth="4" markerHeight="4" refX="3.3" refY="2" orient="auto" markerUnits="userSpaceOnUse"><path d="M0 0 4 2 0 4Z" fill={color} /></marker></defs>
    <path d={`M${from.x} ${from.y} L${to.x} ${to.y}`} fill="none" stroke={color} strokeWidth=".45" strokeDasharray="1.6 1" opacity=".45" />
    <path d={`M${from.x} ${from.y} L${from.x + (to.x-from.x)*safeProgress} ${from.y + (to.y-from.y)*safeProgress}`} fill="none" stroke={color} strokeWidth=".65" markerEnd={safeProgress > 0 ? `url(#${id})` : undefined} />
  </g>;
}

export type PressZoneProps = { x: number; y: number; width: number; height: number; label?: string };
export function PressZone({ x, y, width, height, label = "Pressing zone" }: PressZoneProps) {
  return <g role="img" aria-label={label}><rect x={x} y={y} width={width} height={height} rx="1" fill="#ff987e" fillOpacity=".2" stroke="#ff987e" strokeWidth=".5" strokeDasharray="1.4 .8" />
    <path d={`M${x+width/2-2} ${y+height/2}h4m-1.5-1.5L${x+width/2+2} ${y+height/2}l-1.5 1.5 M${x+width/2} ${y+height/2-2}v4m-1.5-1.5L${x+width/2} ${y+height/2+2}l1.5-1.5`} fill="none" stroke="#ff987e" strokeWidth=".5" /></g>;
}
