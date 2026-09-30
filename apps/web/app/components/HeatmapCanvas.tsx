"use client";

import { useEffect, useRef } from "react";

export type HeatCell = { x: number; y: number; value: number };
export type HeatmapCanvasProps = { cells: readonly HeatCell[]; label: string; className?: string };

function colorFor(value: number): string {
  const stops = [[33, 92, 145], [57, 199, 160], [215, 255, 84]] as const;
  const t = Math.max(0, Math.min(1, value)) * 2;
  const start = stops[Math.floor(t)] ?? stops[1];
  const end = stops[Math.min(2, Math.floor(t) + 1)];
  const local = t - Math.floor(t);
  return `rgba(${start.map((channel, index) => Math.round(channel + (end[index] - channel) * local)).join(",")},${0.18 + value * 0.72})`;
}

export function HeatmapCanvas({ cells, label, className }: HeatmapCanvasProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  useEffect(() => {
    const canvas = canvasRef.current;
    const parent = canvas?.parentElement;
    const context = canvas?.getContext("2d", { alpha: true });
    if (!canvas || !parent || !context) return;
    const paint = () => {
      const { width, height } = parent.getBoundingClientRect();
      const dpr = Math.min(window.devicePixelRatio || 1, 2);
      canvas.width = Math.round(width * dpr);
      canvas.height = Math.round(height * dpr);
      context.setTransform(dpr, 0, 0, dpr, 0, 0);
      context.clearRect(0, 0, width, height);
      const cw = width / 12, ch = height / 8;
      for (const cell of cells) {
        if (cell.x < 0 || cell.x >= 12 || cell.y < 0 || cell.y >= 8) continue;
        context.fillStyle = colorFor(cell.value);
        context.fillRect(cell.x * cw, height - (cell.y + 1) * ch, cw, ch);
      }
    };
    paint();
    const observer = new ResizeObserver(paint);
    observer.observe(parent);
    return () => observer.disconnect();
  }, [cells]);
  const summary = cells.slice().sort((a, b) => b.value - a.value).slice(0, 3).map((cell) => `zone ${cell.x + 1}, ${cell.y + 1}: ${Math.round(cell.value * 100)} percent`).join("; ");
  return <div className={className}>
    <div className="heatmap-wrap" role="img" aria-label={`${label}. Most active zones: ${summary || "no activity"}`}><canvas ref={canvasRef} className="heatmap-canvas" aria-hidden="true" /></div>
    <div className="heatmap-caption"><span>{label}</span><span className="heat-scale" aria-hidden="true" /><span>low&nbsp; / &nbsp;high</span></div>
    <p className="sr-only">Highest activity: {summary || "No activity recorded."}</p>
  </div>;
}
