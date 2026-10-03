"use client";

import { useMemo, useState } from "react";
import { BallMarker, PassArrow, PlayerMarker, PressZone } from "./Markers";
import { Pitch } from "./Pitch";
import { HeatmapCanvas, type HeatCell } from "./HeatmapCanvas";
import { SequencePlayer, type Sequence, type SequenceFrame } from "./SequencePlayer";

function makeSequence(index: number): Sequence {
  const frames: SequenceFrame[] = Array.from({ length: 8 }, (_, frame) => {
    const t = frame / 7;
    return {
      timeMs: frame * 400,
      ball: { x: 25 + t * 48 + (index % 4), y: 54 - t * 32 },
      players: [
        { id: `h${index}-1`, team: "home", number: 8, x: 19 + t * 25, y: 52 - t * 13 },
        { id: `h${index}-2`, team: "home", number: 10, x: 36 + t * 22, y: 30 + t * 4 },
        { id: `a${index}-1`, team: "away", number: 4, x: 61 - t * 12, y: 48 - t * 7 },
        { id: `a${index}-2`, team: "away", number: 5, x: 76 - t * 10, y: 27 + t * 8 },
      ],
      pass: { from: { x: 25 + t * 42, y: 54 - t * 29 }, to: { x: 41 + t * 42, y: 44 - t * 29 } },
      pressZone: { x: 66 - t * 12, y: 34, width: 18, height: 20 },
    };
  });
  return { id: `sequence-${index}`, title: `Sequence ${String(index + 1).padStart(3, "0")}`, durationMs: 2800, frames };
}

const primarySequence = makeSequence(0);
const heatCells: HeatCell[] = Array.from({ length: 36 }, (_, index) => ({ x: index % 12, y: Math.floor(index / 12) + 2, value: Math.max(0, 1 - Math.hypot(index % 12 - 8, Math.floor(index / 12) - 1) / 9) }));

export function DesignShowcase() {
  const [showZones, setShowZones] = useState(true);
  const [showHeatmap, setShowHeatmap] = useState(true);
  const showcaseSequences = useMemo(() => Array.from({ length: 200 }, (_, index) => makeSequence(index + 1)), []);
  return <main className="page-shell">
    <header className="site-header"><a className="brand" href="/"><span className="brand-mark" aria-hidden="true">H</span> HalfSpace</a><nav className="showcase-nav"><a href="/">Sequence search</a><a href="/dossier">Dossier</a><a href="/design" aria-current="page">Design system</a></nav></header>
    <section className="hero" aria-labelledby="page-title"><div><span className="eyebrow">Tactical sequence lab / 01</span><h1 id="page-title">Read the game<br />in its own shape.</h1></div><p>A broadcast analyst’s view of space, pressure, and progression. The pitch stays in focus; every mark carries meaning.</p></section>

    <section className="panel" aria-labelledby="player-title">
      <div className="panel-heading"><h2 id="player-title">Sequence player / live state</h2><span className="eyebrow">Build-up · 00:08</span></div>
      <SequencePlayer sequence={primarySequence} label="Build-up sequence" />
    </section>

    <section className="section" aria-labelledby="pitch-title">
      <div className="section-title"><h2 id="pitch-title">Pitch and overlay states</h2><p>StatsBomb 120 × 80 coordinate space · proportional markings</p></div>
      <div className="specimen-grid">
        <article className="panel"><div className="panel-heading"><h3>Zone grid toggle</h3><button type="button" className="control-button" aria-pressed={showZones} onClick={() => setShowZones((value) => !value)}>{showZones ? "Hide grid" : "Show grid"}</button></div><div className="pitch-stage"><Pitch showZones={showZones} label={`Pitch with ${showZones ? "" : "no "}12 by 8 zone grid`}><PassArrow from={{ x: 31, y: 51 }} to={{ x: 54, y: 32 }} progress={0.72} /><PlayerMarker x={31} y={51} label="Home midfielder" team="home" number={8} active /><PlayerMarker x={54} y={32} label="Home forward" team="home" number={10} /><PlayerMarker x={72} y={37} label="Away defender" team="away" number={4} /><BallMarker x={48} y={37} /><PressZone x={66} y={28} width={22} height={20} label="High press zone" /></Pitch></div></article>
        <article className="panel"><div className="panel-heading"><h3>Canvas heatmap / 12 × 8</h3><button type="button" className="control-button" aria-pressed={showHeatmap} onClick={() => setShowHeatmap((value) => !value)}>{showHeatmap ? "Hide layer" : "Show layer"}</button></div><div className="panel-body">{showHeatmap ? <HeatmapCanvas cells={heatCells} label="Attacking actions by zone" /> : <p className="muted">Heat layer hidden. The canvas redraws at device pixel ratio when shown.</p>}</div></article>
      </div>
    </section>

    <section className="section" aria-labelledby="markers-title"><div className="section-title"><h2 id="markers-title">Marker language</h2><p>Color pairs carry contrast; shape and labels carry meaning.</p></div>
      <div className="specimen-grid">
        <article className="panel"><div className="panel-heading"><h3>Player, ball, pass, press</h3><span className="muted">Focus and active states</span></div><div className="marker-demo"><svg viewBox="0 0 120 30" width="100%" role="img" aria-label="Examples of home and away players, ball, pass arrow and pressing zone"><PressZone x={70} y={5} width={30} height={20} /><PassArrow from={{ x: 15, y: 17 }} to={{ x: 55, y: 12 }} progress={0.65} /><PlayerMarker x={15} y={17} label="Home player" team="home" number={8} active /><PlayerMarker x={55} y={12} label="Away player" team="away" number={4} /><BallMarker x={42} y={21} /></svg></div><div className="panel-body"><div className="marker-legend"><span className="legend-item">● Home player</span><span className="legend-item">● Away player</span><span className="legend-item">◉ Ball</span><span className="legend-item">→ Pass progress</span><span className="legend-item">▧ Press zone</span></div></div></article>
        <article className="panel"><div className="panel-heading"><h3>Controls / focus states</h3><span className="muted">Keyboard and screen reader ready</span></div><div className="panel-body"><div className="toolbar"><button className="control-button accent-button" type="button">Primary action</button><button className="control-button" type="button" aria-pressed="false">Inactive toggle</button><label className="muted" htmlFor="showcase-speed">Speed</label><select id="showcase-speed" className="select-control" defaultValue="1"><option value="0.5">0.5×</option><option value="1">1×</option><option value="2">2×</option></select></div><p className="muted">Tab through controls to inspect the high contrast focus ring. Text, labels, and pitch markings maintain contrast on the dark broadcast palette.</p></div></article>
      </div>
    </section>

    <section className="section" aria-labelledby="stress-title"><div className="section-title"><h2 id="stress-title">Mounted sequence sample</h2><p>200 compact typed players · offscreen playback pauses automatically</p></div><details className="panel"><summary className="panel-heading">Expand 200-player stress sample</summary><div className="panel-body sequence-grid">{showcaseSequences.map((sequence) => <article key={sequence.id} className="mini-sequence"><h3>{sequence.title}</h3><SequencePlayer sequence={sequence} label={sequence.title} autoPlay compact /></article>)}</div></details></section>
  </main>;
}
