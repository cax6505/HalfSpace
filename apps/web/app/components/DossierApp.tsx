"use client";

import Link from "next/link";
import { useCallback, useEffect, useState, type FormEvent } from "react";
import { DEMO_DOSSIER, DEMO_RESULTS, sequenceForId, type DossierClaimData, type DossierData } from "../lib/demo";
import { SequencePlayer } from "./SequencePlayer";

type TraceStep = { step: string; [key: string]: unknown };

async function consumeDossier(response: Response, onStep: (step: TraceStep) => void): Promise<Record<string, unknown>> {
  if (!response.ok || !response.body) throw new Error(`Dossier service returned ${response.status}`);
  const reader = response.body.getReader(); const decoder = new TextDecoder(); let buffer = ""; let final: Record<string, unknown> | null = null;
  while (true) {
    const { value, done } = await reader.read(); buffer += decoder.decode(value, { stream: !done });
    const blocks = buffer.split("\n\n"); buffer = blocks.pop() ?? "";
    for (const block of blocks) {
      const event = block.match(/^event:\s*(.+)$/m)?.[1]?.trim();
      const data = block.split("\n").filter((line) => line.startsWith("data:")).map((line) => line.slice(5).trim()).join("\n");
      if (!data) continue;
      const value = JSON.parse(data) as Record<string, unknown>;
      if (event === "step") onStep(value as TraceStep);
      else if (event === "final") final = value;
      else if (event === "error") throw new Error(String(value.error ?? "Dossier failed"));
    }
    if (done) break;
  }
  if (!final) throw new Error("Dossier stream ended before its report arrived");
  return final;
}

export function DossierApp() {
  const [team, setTeam] = useState("");
  const [question, setQuestion] = useState("Scout the transition attack, build-up, pressing triggers, and set pieces.");
  const [report, setReport] = useState<DossierData | null>(null);
  const [busy, setBusy] = useState(false);
  const [latencyMs, setLatencyMs] = useState<number | null>(null);
  const [notice, setNotice] = useState("Load a match or clip to build an evidence-led dossier.");
  const [trace, setTrace] = useState<TraceStep[]>([]);
  const [traceOpen, setTraceOpen] = useState(false);
  const [activeClaim, setActiveClaim] = useState<DossierClaimData | null>(null);
  const [copied, setCopied] = useState(false);

  const generate = useCallback(async (teamName: string, prompt: string) => {
    if (!teamName.trim()) {
      setNotice("Select a team from the loaded match or clip first.");
      return;
    }
    const startedAt = performance.now();
    setBusy(true); setLatencyMs(null); setNotice("Planner is breaking the brief into evidence questions…"); setTrace([]); setTraceOpen(true); setActiveClaim(null);
    const url = new URL(window.location.href); url.searchParams.set("team", teamName); url.searchParams.set("q", prompt); window.history.pushState({}, "", `${url.pathname}${url.search}`);
    try {
      const response = await fetch("/api/scout/dossier", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ team: teamName, query: prompt, stream: true }) });
      const final = await consumeDossier(response, (step) => { setTrace((current) => [...current, step]); setNotice(`${step.step.replaceAll("_", " ")} · evidence trace updated`); });
      const next = final.dossier as DossierData;
      if (!next?.overview || !Array.isArray(next.claims)) throw new Error("Dossier response did not contain claims");
      const duration = Number(final.latency_ms);
      setLatencyMs(Number.isFinite(duration) ? duration : null);
      setReport(next); setNotice(`Live dossier verified · ${Number(final.steps ?? 0)} streamed steps`);
    } catch {
      await new Promise((resolve) => window.setTimeout(resolve, 280));
      setReport(DEMO_DOSSIER); setLatencyMs(performance.now() - startedAt); setNotice("Sample dossier · API unavailable, evidence replay remains interactive.");
      setTrace([{ step: "planner", question_count: 4, tool: "sample planner" }, { step: "retriever", evidence_count: 6, tool: "sequence search + tactical tools" }, { step: "tactician", claims: 3, tool: "sample synthesizer" }, { step: "critic", concerns: ["Sample claims are illustrative"], tool: "sample critic" }, { step: "verifier", supported_claims: 4, tool: "sample verifier" }]);
    } finally { setBusy(false); }
  }, []);

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const initialTeam = params.get("team") || "";
    setTeam(initialTeam); setQuestion(params.get("q") || "Scout the transition attack, build-up, pressing triggers, and set pieces.");
    if (initialTeam) setReport(DEMO_DOSSIER);
    if (params.has("claim")) {
      const target = DEMO_DOSSIER.claims.find((claim) => claim.evidence_ids.includes(params.get("claim")!));
      if (target) setActiveClaim(target);
    } else if (params.has("sequence")) setActiveClaim({ statement: `Review sequence ${params.get("sequence")} in the team report.`, evidence_ids: [`sequence:${params.get("sequence")}`] });
  }, []);

  const share = async () => { await navigator.clipboard.writeText(window.location.href); setCopied(true); window.setTimeout(() => setCopied(false), 1500); };
  const openEvidence = (claim: DossierClaimData) => {
    setActiveClaim(claim);
    const url = new URL(window.location.href); url.searchParams.set("claim", claim.evidence_ids[0]);
    window.history.pushState({}, "", `${url.pathname}${url.search}`);
  };
  const closeEvidence = () => {
    setActiveClaim(null);
    const url = new URL(window.location.href); url.searchParams.delete("claim");
    window.history.replaceState({}, "", `${url.pathname}${url.search}`);
  };
  const claims = report ? [report.overview, ...report.claims] : [];
  const activeSequence = activeClaim?.evidence_ids[0] ? sequenceForId(activeClaim.evidence_ids[0]) : null;
  const submit = (event: FormEvent) => { event.preventDefault(); void generate(team, question); };

  return <main className={`product-shell dossier-shell ${activeClaim ? "drawer-open" : ""}`}>
    <header className="product-header"><Link className="brand" href="/"><span className="brand-mark" aria-hidden="true">H</span> HalfSpace</Link><nav aria-label="Main navigation"><Link href="/">Sequence search</Link><a href="/dossier" className="nav-current" aria-current="page">Scouting dossier</a><Link href="/design">Design lab</Link></nav><button className="control-button" type="button" onClick={share}>{copied ? "Link copied" : "Share report ↗"}</button></header>
    <section className="dossier-hero"><div><span className="eyebrow">Scouting desk / intelligence brief</span><h1>{team || "No team selected"}<br /><span>Matchup dossier</span></h1><p className="dossier-status" role="status" aria-live="polite"><span className={`status-dot ${busy ? "parsing" : "ready"}`} />{notice}</p></div><form className="dossier-request panel" onSubmit={submit}><label htmlFor="dossier-team">Team from loaded clip</label><select id="dossier-team" value={team} onChange={(event) => setTeam(event.target.value)}><option value="">Select a team</option>{Array.from(new Set(DEMO_RESULTS.map((result) => result.team))).map((teamName) => <option key={teamName} value={teamName}>{teamName}</option>)}</select><label htmlFor="dossier-question">Scout brief</label><textarea id="dossier-question" rows={3} value={question} onChange={(event) => setQuestion(event.target.value)} /><button className="control-button accent-button" disabled={busy || !team}>{busy ? "Building evidence…" : "Generate dossier"}</button></form></section>
    <div className="dossier-toolbar"><span className="eyebrow">Evidence-led report · every claim opens its source plays</span><button className="text-button" aria-expanded={traceOpen} onClick={() => setTraceOpen((value) => !value)}>{traceOpen ? "Hide agent trace" : "Show agent trace"} {trace.length ? `(${trace.length})` : ""}</button></div>
    {traceOpen && <section className="trace-panel panel" aria-label="Agent trace"><div className="trace-heading"><div><span className="eyebrow">Live process</span><h2>Agent trace</h2></div><span className="trace-latency">{busy ? "Running · streaming" : `${trace.length} steps · ${latencyMs === null ? "latency pending" : `${latencyMs.toFixed(0)} ms`} `}</span></div>{busy && trace.length === 0 && <div className="trace-skeleton"><span /><span /><span /></div>}<ol className="trace-steps">{trace.map((step, index) => <li className="trace-step" key={`${step.step}-${index}`}><span className="trace-index">0{index + 1}</span><span><strong>{step.step.replaceAll("_", " ")}</strong><small>{Array.isArray(step.tool_names) ? step.tool_names.join(", ") : String(step.tool ?? "LangGraph node")} · {Object.entries(step).filter(([key]) => key !== "step" && key !== "tool" && key !== "tool_names").map(([key, value]) => `${key.replaceAll("_", " ")}: ${Array.isArray(value) ? value.length : String(value)}`).join(" · ")}</small></span><span className="trace-check">{busy && index === trace.length - 1 ? "RUN" : "DONE"}</span></li>)}</ol></section>}

    <section className="dossier-content" aria-labelledby="report-title"><div className="dossier-report-head"><div><span className="eyebrow">Analyst readout / tactical intelligence</span><h2 id="report-title">The tactical picture</h2></div><span className="verified-stamp">◈ EVIDENCE LINKED</span></div>
      {busy && !report && <div className="dossier-skeleton"><div className="skeleton-block" /><div className="skeleton-block" /><div className="skeleton-block" /></div>}
      {!report && !busy && <div className="empty-state"><h3>No dossier yet.</h3><p>Choose a team and generate an evidence-led tactical brief.</p></div>}
      {report && <div className="claim-list">{claims.map((claim, index) => <article className={`claim-card ${index === 0 ? "claim-overview" : ""}`} key={`${index}-${claim.statement}`}><span className="claim-number">{index === 0 ? "READOUT" : `0${index}`}</span><div className="claim-content"><p>{claim.statement}</p><div className="claim-evidence">{claim.evidence_ids.map((id) => <span className="evidence-chip" key={id}>◉ {id}</span>)}</div></div><button className="claim-open" aria-label={`Replay claim. Evidence for: ${claim.statement}`} onClick={() => openEvidence(claim)}>Replay claim ↗</button></article>)}</div>}
    </section>
    <footer className="product-footer"><span>HALFSPACE · VERIFIED CLAIMS / SOURCE SEQUENCES</span><Link href="/">Back to search</Link><Link href="/design">Design system</Link></footer>

    {activeClaim && <><button className="drawer-scrim" aria-label="Close evidence drawer" onClick={closeEvidence} /><aside className="evidence-drawer" aria-labelledby="evidence-title"><div className="drawer-heading"><div><span className="eyebrow">Supporting evidence</span><h2 id="evidence-title">Replay the claim</h2></div><button className="icon-button" aria-label="Close evidence drawer" onClick={closeEvidence}>×</button></div><p className="drawer-claim">{activeClaim.statement}</p><div className="drawer-evidence-ids"><span className="eyebrow">Cited sequence / event IDs</span>{activeClaim.evidence_ids.map((id) => <code key={id}>{id}</code>)}</div>{activeSequence && <><div className="drawer-sequence-title"><span className="eyebrow">Sequence replay</span><strong>{activeSequence.title}</strong></div><SequencePlayer sequence={activeSequence} label="Evidence sequence replay" /></>}<div className="evidence-context"><span className="eyebrow">Verification</span><p>{report?.verification ? `${report.verification.supported_claims ?? 0} claims supported by tool evidence.` : "Each cited play links to the sequence tool result."} Sample mode uses illustrative local plays; live dossier evidence comes from the API trace.</p></div></aside></>}
  </main>;
}
