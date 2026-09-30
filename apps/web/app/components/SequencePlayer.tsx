"use client";

import { useCallback, useEffect, useRef, useState, type KeyboardEvent } from "react";
import { BallMarker, PassArrow, PlayerMarker, PressZone, type Point } from "./Markers";
import { Pitch } from "./Pitch";

export type SequenceFrame = { timeMs: number; ball: Point; players: readonly (Point & { id: string; team: "home" | "away"; number?: number; active?: boolean })[]; pass?: { from: Point; to: Point; label?: string }; pressZone?: { x: number; y: number; width: number; height: number }; visibleArea?: readonly number[] };
export type Sequence = { id: string; title: string; durationMs: number; frames: readonly SequenceFrame[]; dataSource?: "statsbomb-360" | "event-locations" | "zone-grid" | "sample" };
export type SequencePlayerProps = { sequence: Sequence; label?: string; autoPlay?: boolean; compact?: boolean };

const SPEEDS = [0.5, 1, 1.5, 2] as const;
const useReducedMotion = () => {
  const [reduced, setReduced] = useState(false);
  useEffect(() => {
    const query = window.matchMedia("(prefers-reduced-motion: reduce)");
    const update = () => setReduced(query.matches);
    update(); query.addEventListener("change", update);
    return () => query.removeEventListener("change", update);
  }, []);
  return reduced;
};

export function SequencePlayer({ sequence, label = "Sequence playback", autoPlay = false, compact = false }: SequencePlayerProps) {
  const reducedMotion = useReducedMotion();
  const [frameIndex, setFrameIndex] = useState(0);
  const [playing, setPlaying] = useState(autoPlay);
  const [speed, setSpeed] = useState<(typeof SPEEDS)[number]>(1);
  const [visible, setVisible] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);
  const frame = sequence.frames[Math.min(frameIndex, sequence.frames.length - 1)];
  const last = Math.max(0, sequence.frames.length - 1);
  const safeDuration = Math.max(1, sequence.durationMs);

  useEffect(() => { setFrameIndex(0); setPlaying(autoPlay && !reducedMotion); }, [sequence.id, autoPlay, reducedMotion]);
  useEffect(() => {
    const node = containerRef.current;
    if (!node) return;
    const observer = new IntersectionObserver(([entry]) => setVisible(entry.isIntersecting), { rootMargin: "120px" });
    observer.observe(node);
    return () => observer.disconnect();
  }, []);

  useEffect(() => {
    if (!playing || reducedMotion || !visible || last === 0) return;
    let raf = 0;
    let previous = 0;
    let elapsed = sequence.frames[frameIndex]?.timeMs ?? 0;
    const tick = (now: number) => {
      if (!previous) previous = now;
      elapsed += (now - previous) * speed;
      previous = now;
      if (elapsed >= safeDuration) {
        elapsed = 0;
        setFrameIndex(0);
      } else {
        let next = frameIndex;
        while (next < last && sequence.frames[next + 1].timeMs <= elapsed) next++;
        if (next !== frameIndex) setFrameIndex(next);
      }
      raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [playing, reducedMotion, visible, frameIndex, last, safeDuration, sequence.frames, speed]);

  const step = useCallback((amount: number) => {
    setPlaying(false);
    setFrameIndex((current) => Math.max(0, Math.min(last, current + amount)));
  }, [last]);
  const togglePlay = () => { if (!reducedMotion) setPlaying((current) => !current); };
  const onKeyDown = (event: KeyboardEvent<HTMLDivElement>) => {
    const target = event.target as HTMLElement;
    if (["INPUT", "BUTTON", "SELECT", "TEXTAREA"].includes(target.tagName)) return;
    if (event.code === "Space") { event.preventDefault(); togglePlay(); }
    else if (event.key === "ArrowLeft") { event.preventDefault(); step(-1); }
    else if (event.key === "ArrowRight") { event.preventDefault(); step(1); }
  };
  if (!frame) return <p className="error-note">This sequence has no frames to play.</p>;

  return <div className="sequence-player" ref={containerRef} onKeyDown={onKeyDown} tabIndex={0} role="group" aria-label={`${label}: ${sequence.title}`}>
    {!compact && <div className="pitch-stage"><Pitch label={`${sequence.title}, frame ${frameIndex + 1} of ${sequence.frames.length}`} showZones>
      {frame.visibleArea && <polygon className="visible-area" points={Array.from({ length: Math.floor(frame.visibleArea.length / 2) }, (_, i) => `${frame.visibleArea![i * 2]},${frame.visibleArea![i * 2 + 1]}`).join(" ")} aria-label="Observed StatsBomb 360 coverage area" />}
      {frame.pressZone && <PressZone {...frame.pressZone} />}
      {frame.pass && <PassArrow from={frame.pass.from} to={frame.pass.to} progress={1} label={frame.pass.label ?? "Pass"} />}
      {frame.players.map((player) => <PlayerMarker key={player.id} {...player} label={`Player ${player.number ?? player.id}`} active={player.active} />)}
      <BallMarker {...frame.ball} />
    </Pitch></div>}
    <div className="panel-body">
      {!compact && <p className="tracking-note">{sequence.dataSource === "statsbomb-360" ? `StatsBomb 360 snapshot · ${frame.players.length} observed players` : sequence.dataSource === "sample" ? "Illustrative 11v11 sample animation · not match tracking" : sequence.dataSource === "zone-grid" ? "Approximate zone-grid playback · rerun make ingest for event coordinates" : "Event locations only · complete player tracking unavailable for this match"}</p>}
      <div className="player-controls">
        <button className="control-button accent-button" type="button" onClick={togglePlay} disabled={reducedMotion} aria-label={playing ? "Pause sequence" : "Play sequence"} aria-pressed={playing}>{reducedMotion ? "Reduced motion" : playing ? "Pause" : "Play"}</button>
        <label className="sr-only" htmlFor={`scrubber-${sequence.id}`}>Playback position</label>
        <input className="scrubber" id={`scrubber-${sequence.id}`} type="range" min={0} max={last} value={frameIndex} onChange={(event) => { setPlaying(false); setFrameIndex(Number(event.target.value)); }} aria-valuetext={`Frame ${frameIndex + 1} of ${sequence.frames.length}`} />
        <span className="time-readout" aria-live="off">{(frame.timeMs / 1000).toFixed(1)}s</span>
        <button className="control-button step-button" type="button" onClick={() => step(-1)} aria-label="Previous frame" disabled={frameIndex === 0}>−1</button>
        <button className="control-button step-button" type="button" onClick={() => step(1)} aria-label="Next frame" disabled={frameIndex === last}>+1</button>
        <label className="sr-only" htmlFor={`speed-${sequence.id}`}>Playback speed</label>
        <select className="select-control" id={`speed-${sequence.id}`} value={speed} onChange={(event) => setSpeed(Number(event.target.value) as (typeof SPEEDS)[number])}>
          {SPEEDS.map((value) => <option key={value} value={value}>{value}×</option>)}
        </select>
      </div>
      {!compact && <ul className="shortcut-list" aria-label="Keyboard shortcuts"><li><kbd>Space</kbd> play / pause</li><li><kbd>←</kbd> previous frame</li><li><kbd>→</kbd> next frame</li><li>{reducedMotion ? "Playback paused by reduced motion preference" : "Playback updates at frame boundaries"}</li></ul>}
    </div>
  </div>;
}
