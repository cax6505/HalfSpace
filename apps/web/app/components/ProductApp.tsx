"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useRef, useState, type FormEvent } from "react";
import { DEMO_RESULTS, EMPTY_FILTERS, demoSearch, parseDemoQuery, type SearchFilters, type SequenceResult } from "../lib/demo";
import { SequencePlayer, type SequenceFrame } from "./SequencePlayer";

type SearchIntent = { semantic_query?: string; filters?: Record<string, unknown>; exemplar_sequence_id?: number | null };
type AppState = "idle" | "parsing" | "retrieving" | "ready" | "empty" | "error";

function mergeParsedFilters(base: SearchFilters, parsed?: Record<string, unknown>): SearchFilters {
  if (!parsed) return base;
  const zone = parsed.zone && typeof parsed.zone === "object" ? parsed.zone as Record<string, number> : null;
  return {
    phase: parsed.phase == null ? base.phase : String(parsed.phase),
    team: parsed.team == null ? base.team : String(parsed.team),
    trigger: parsed.trigger == null ? base.trigger : String(parsed.trigger),
    competition: parsed.competition == null ? base.competition : String(parsed.competition),
    outcome: parsed.outcome == null ? base.outcome : String(parsed.outcome),
    zone: zone ? `x${zone.x_min + 1}-${zone.x_max + 1} / y${zone.y_min + 1}-${zone.y_max + 1}` : base.zone,
  };
}

function apiFilterPayload(filters: SearchFilters) {
  const zone = filters.zone.match(/x(\d+)-(\d+)\s*\/\s*y(\d+)-(\d+)/i);
  return { phase: filters.phase || null, zone: zone ? { x_min: Number(zone[1])-1, x_max: Number(zone[2])-1, y_min: Number(zone[3])-1, y_max: Number(zone[4])-1 } : null, trigger: filters.trigger || null, team: filters.team || null, competition: filters.competition || null, outcome: filters.outcome || null };
}

function fromApiHit(hit: Record<string, unknown>, fallbackTeam: string): SequenceResult {
  const tokens = Array.isArray(hit.tokens) ? hit.tokens as Record<string, unknown>[] : [];
  const playbackTokens = Array.isArray(hit.playback_tokens) ? hit.playback_tokens as Record<string, unknown>[] : tokens;
  const targetTeamId = Number(hit.team_id);
  const targetDirection = playbackTokens.find((token) => token.is_target_possession)?.attacking_right ?? tokens.find((token) => token.attacking_right != null)?.attacking_right;
  const targetStartIndex = Math.max(0, playbackTokens.findIndex((token) => token.is_target_possession));
  let timelineMs = 0;
  const frames: SequenceFrame[] = playbackTokens.map((token, index) => {
    const zone = Array.isArray(token.zone) ? token.zone as number[] : [Math.min(11, index + 1), 4];
    const location = Array.isArray(token.location) ? token.location as number[] : null;
    const rawX = location ? Number(location[0]) : ((zone[0] ?? 4) + 0.5) * 10;
    const y = location ? Number(location[1]) : ((zone[1] ?? 4) + 0.5) * 10;
    const flipX = targetDirection === false;
    const x = flipX ? 120 - rawX : rawX;
    const rawEnd = Array.isArray(token.end_location) ? token.end_location as number[] : null;
    const endX = rawEnd ? (flipX ? 120 - Number(rawEnd[0]) : Number(rawEnd[0])) : x;
    const endY = rawEnd ? Number(rawEnd[1]) : y;
    const teamId = Number(token.team_id);
    const tracking = Array.isArray(token.tracking_frame) ? token.tracking_frame as Record<string, unknown>[] : [];
    const players = tracking.length ? tracking.map((player, playerIndex) => {
      const coords = Array.isArray(player.location) ? player.location as number[] : [x, y];
      const teammate = player.teammate !== false;
      const homeSide = !teamId || !targetTeamId || teamId === targetTeamId ? teammate : !teammate;
      return { id: `tracking-${homeSide ? "home" : "away"}-${playerIndex}`, team: homeSide ? "home" as const : "away" as const, x: flipX ? 120 - Number(coords[0]) : Number(coords[0]), y: Number(coords[1]), active: player.actor === true };
    }) : location && token.player_id != null ? [{ id: `event-player-${String(token.player_id)}`, team: teamId && targetTeamId && teamId !== targetTeamId ? "away" as const : "home" as const, x, y, active: true }] : [];
    const rawArea = Array.isArray(token.visible_area) ? token.visible_area as number[] : undefined;
    const visibleArea = rawArea && flipX ? rawArea.map((value, i) => i % 2 === 0 ? 120 - value : value) : rawArea;
    const eventType = String(token.event_type ?? "");
    const hasBallPath = rawEnd && ["Pass", "Carry", "Shot"].includes(eventType);
    const actualDeltaMs = Math.max(0, Number(token.time_delta ?? 0) * 1000);
    timelineMs += index ? Math.max(100, actualDeltaMs) : 0;
    const owner = Number(token.possession_team_id);
    const previousOwner = index ? Number(playbackTokens[index - 1].possession_team_id) : 0;
    const changed = Boolean(owner && previousOwner && owner !== previousOwner);
    const targetPossession = token.is_target_possession !== false;
    const turnover = changed ? targetPossession ? `${String(hit.team_name ?? "Selected team")} regain` : `${String(hit.team_name ?? "Selected team")} lose possession · defend transition` : undefined;
    const phase = targetPossession ? `${String(hit.team_name ?? "Selected team")} possession · ${String(hit.tag ?? "sequence").replaceAll("-", " ")}` : index < targetStartIndex ? "Opponent possession · lead-up" : "Opponent response · defensive transition";
    return { timeMs: timelineMs, ball: { x: hasBallPath ? endX : x, y: hasBallPath ? endY : y }, players, visibleArea, pass: hasBallPath ? { from: { x, y }, to: { x: endX, y: endY }, label: eventType } : undefined, eventLabel: eventType, phaseLabel: phase, turnoverLabel: turnover };
  });
  if (!frames.length) frames.push({ timeMs: 0, ball: { x: 60, y: 40 }, players: [] });
  return {
    sequence_id: Number(hit.sequence_id), match_id: Number(hit.match_id), possession_id: Number(hit.possession_id), phase_index: Number(hit.phase_index ?? 0),
    tag: String(hit.tag ?? "sequence"), score: Number(hit.rerank_score ?? hit.score ?? 0), team: String(hit.team_name ?? (fallbackTeam || "Indexed team")), competition: String(hit.competition_name ?? "Indexed competition"),
    summary: tokens.slice(0, 5).map((token) => String(token.event_type ?? "event")).join(" · ") || "Sequence retrieved from the indexed corpus.",
    sequence: { id: `sequence-${String(hit.sequence_id)}`, title: `Sequence ${String(hit.sequence_id)} · ${String(hit.tag ?? "phase")}`, durationMs: Math.max(800, (frames[frames.length - 1]?.timeMs ?? 0) + 600), frames, dataSource: frames.some((item) => item.visibleArea) ? "statsbomb-360" : playbackTokens.some((token) => Array.isArray(token.location)) ? "event-locations" : "zone-grid" },
  };
}

function writeUrl(query: string, filters: SearchFilters, selected: number | null, compare: number[], replace = false) {
  const url = new URL(window.location.href);
  url.pathname = "/";
  const values: Record<string, string> = { q: query, phase: filters.phase, zone: filters.zone, trigger: filters.trigger, team: filters.team, competition: filters.competition, outcome: filters.outcome };
  for (const [key, value] of Object.entries(values)) value ? url.searchParams.set(key, value) : url.searchParams.delete(key);
  selected === null ? url.searchParams.delete("selected") : url.searchParams.set("selected", String(selected));
  compare.length ? url.searchParams.set("compare", compare.join(",")) : url.searchParams.delete("compare");
  window.history[replace ? "replaceState" : "pushState"]({}, "", `${url.pathname}${url.search}`);
}

async function streamSearch(response: Response, onStage: (stage: string, value: Record<string, unknown>) => void) {
  if (!response.ok || !response.body) throw new Error(`Search service returned ${response.status}`);
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = ""; let complete: Record<string, unknown> | null = null;
  while (true) {
    const { value, done } = await reader.read();
    buffer += decoder.decode(value, { stream: !done });
    const blocks = buffer.split("\n\n"); buffer = blocks.pop() ?? "";
    for (const block of blocks) {
      const event = block.match(/^event:\s*(.+)$/m)?.[1]?.trim() ?? "message";
      const data = block.split("\n").filter((line) => line.startsWith("data:")).map((line) => line.slice(5).trim()).join("\n");
      if (!data) continue;
      const parsed = JSON.parse(data) as Record<string, unknown>;
      onStage(event, parsed);
      if (event === "complete") complete = parsed;
      if (event === "error") throw new Error(String(parsed.error ?? "Search failed"));
    }
    if (done) break;
  }
  if (!complete) throw new Error("Search stream ended before results arrived");
  return complete;
}

export function ProductApp() {
  const [query, setQuery] = useState("");
  const [filters, setFilters] = useState<SearchFilters>(EMPTY_FILTERS);
  const [results, setResults] = useState<SequenceResult[]>([]);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [compareIds, setCompareIds] = useState<number[]>([]);
  const [state, setState] = useState<AppState>("idle");
  const [stage, setStage] = useState("Ready to search");
  const [source, setSource] = useState<"api" | "demo">("demo");
  const [commandOpen, setCommandOpen] = useState(false);
  const [commandQuery, setCommandQuery] = useState("");
  const [copied, setCopied] = useState(false);
  const commandRef = useRef<HTMLInputElement>(null);
  const resultLookup = useMemo(() => new Map(results.map((result) => [result.sequence_id, result])), [results]);
  const selected = selectedId === null ? null : resultLookup.get(selectedId) ?? null;
  const compare = compareIds.map((id) => resultLookup.get(id)).filter((item): item is SequenceResult => Boolean(item));

  const updateSelection = useCallback((id: number, fromHover = false) => {
    const run = () => { setSelectedId(id); writeUrl(query, filters, id, compareIds, fromHover || selectedId === id); };
    if (!fromHover && selectedId !== id && document.startViewTransition) document.startViewTransition(run); else run();
  }, [compareIds, filters, query, selectedId]);

  const executeSearch = useCallback(async (searchQuery: string, exemplarId?: number, startingFilters: SearchFilters = EMPTY_FILTERS, filtersAreExplicit = false, restore?: { selected: number | null; compare: number[] }) => {
    const clean = searchQuery.trim() || "counter-attacks that reach the box";
    setQuery(clean); setState("parsing"); setStage("Parsing the tactical question"); setCommandOpen(false); setSelectedId(restore?.selected ?? null); setCompareIds(restore?.compare ?? []);
    writeUrl(clean, startingFilters, restore?.selected ?? null, restore?.compare ?? []);
    const demoIntent = parseDemoQuery(clean);
    if (!filtersAreExplicit) setFilters((current) => ({ ...current, ...demoIntent.filters }));
    try {
      const response = await fetch("/api/search", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ query: exemplarId ? `Find sequences similar to sequence ${exemplarId}` : clean, limit: 8, stream: true, ...(filtersAreExplicit ? { filters: apiFilterPayload(startingFilters) } : {}) }) });
      const final = await streamSearch(response, (event, payload) => {
        if (event === "parsed") {
          const intent = payload.intent as SearchIntent | undefined;
          if (!filtersAreExplicit) setFilters((current) => mergeParsedFilters(current, intent?.filters));
          setState("retrieving"); setStage("Filters parsed · searching vector and event indexes");
        } else setStage(({ parsing: "Parsing query", embedding: "Embedding the tactical description", retrieving: "Searching sequence indexes", retrieved: "Merging vector and event matches", fused: "Ranking combined results", reranking: "Reranking the best sequences", reranked: "Preparing result cards", complete: "Search complete", cache_hit: "Serving a cached match", semantic_cache_hit: "Serving a semantically cached match" } as Record<string, string>)[event] ?? event);
      });
      const intent = final.intent as SearchIntent | undefined;
      const resolvedFilters = filtersAreExplicit ? startingFilters : mergeParsedFilters(startingFilters, intent?.filters);
      setFilters(resolvedFilters);
      const hits = Array.isArray(final.results) ? final.results as Record<string, unknown>[] : [];
      const mapped = hits.map((hit) => fromApiHit(hit, startingFilters.team));
      const nextId = restore?.selected && mapped.some((result) => result.sequence_id === restore.selected) ? restore.selected : mapped[0]?.sequence_id ?? null;
      const nextCompare = (restore?.compare ?? []).filter((id) => mapped.some((result) => result.sequence_id === id)).slice(0, 2);
      setResults(mapped); setSource("api"); setState(mapped.length ? "ready" : "empty"); setStage(mapped.length ? `${mapped.length} sequences found` : "No matching sequences");
      setSelectedId(nextId); setCompareIds(nextCompare);
      writeUrl(clean, resolvedFilters, nextId, nextCompare);
    } catch {
      await new Promise((resolve) => window.setTimeout(resolve, 260));
      const resolvedFilters = filtersAreExplicit ? startingFilters : { ...startingFilters, ...demoIntent.filters };
      const rows = demoSearch(clean, resolvedFilters, exemplarId);
      setResults(rows); setSource("demo"); setState(rows.length ? "ready" : "empty"); setStage(rows.length ? "Sample sequences · connect the API for live corpus results" : "No sample sequences match those filters");
      const nextId = restore?.selected && rows.some((result) => result.sequence_id === restore.selected) ? restore.selected : rows[0]?.sequence_id ?? null;
      const nextCompare = (restore?.compare ?? []).filter((id) => rows.some((result) => result.sequence_id === id)).slice(0, 2);
      setSelectedId(nextId); setCompareIds(nextCompare);
      writeUrl(clean, resolvedFilters, nextId, nextCompare);
    }
  }, []);

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const q = params.get("q") ?? "";
    const restored: SearchFilters = { phase: params.get("phase") ?? "", zone: params.get("zone") ?? "", trigger: params.get("trigger") ?? "", team: params.get("team") ?? "", competition: params.get("competition") ?? "", outcome: params.get("outcome") ?? "" };
    if (!q) return;
    setQuery(q); setFilters(restored);
    const initial = demoSearch(q, restored);
    setResults(initial); setSource("demo"); setState(initial.length ? "ready" : "empty");
    setSelectedId(Number(params.get("selected")) || initial[0]?.sequence_id || null);
    const restoredCompare = (params.get("compare") ?? "").split(",").map(Number).filter(Boolean).slice(0, 2);
    setCompareIds(restoredCompare);
    void executeSearch(q, undefined, restored, true, { selected: Number(params.get("selected")) || null, compare: restoredCompare });
    // Initial deep-link state is parsed once after hydration.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") { event.preventDefault(); setCommandOpen(true); }
      if (event.key === "Escape") setCommandOpen(false);
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, []);
  useEffect(() => { if (commandOpen) commandRef.current?.focus(); }, [commandOpen]);

  const submit = (event: FormEvent) => { event.preventDefault(); void executeSearch(query); };
  const submitCommand = (event: FormEvent) => { event.preventDefault(); void executeSearch(commandQuery); setCommandQuery(""); };
  const setFilter = (key: keyof SearchFilters, value: string) => {
    const next = { ...filters, [key]: value };
    setFilters(next); writeUrl(query, next, selectedId, compareIds, true);
  };
  const setCompare = (id: number) => {
    const next = compareIds.includes(id) ? compareIds.filter((value) => value !== id) : compareIds.length >= 2 ? [compareIds[1], id] : [...compareIds, id];
    setCompareIds(next); writeUrl(query, filters, selectedId, next);
  };
  const share = async () => { await navigator.clipboard.writeText(window.location.href); setCopied(true); window.setTimeout(() => setCopied(false), 1500); };
  const sampleTeam = DEMO_RESULTS[0]?.team;
  const selectSuggestions = [
    sampleTeam ? `Show ${sampleTeam} counter-attacks into the box` : "Show counter-attacks into the box",
    "Find build-up sequences under pressure",
    "Compare set-piece routines",
  ];
  const updateField = (key: keyof SearchFilters, value: string) => setFilter(key, value);

  return <main className="product-shell">
    <header className="product-header"><Link className="brand" href="/"><span className="brand-mark" aria-hidden="true">H</span> HalfSpace</Link><nav aria-label="Main navigation"><a className="nav-current" href="/">Sequence search</a><Link href="/dossier">Scouting dossier</Link><Link href="/design">Design lab</Link></nav><button className="control-button command-trigger" type="button" onClick={() => setCommandOpen(true)}><span>Search the match library</span><kbd>⌘ K</kbd></button></header>
    <section className="product-hero"><div><span className="eyebrow">Tactical sequence explorer / 01</span><h1>Find the moment<br />that changes shape.</h1></div><p>Search match sequences by the tactical detail that matters. Follow the action on the pitch, compare patterns, then build a report.</p></section>
    <form className="search-form" onSubmit={submit}><label className="sr-only" htmlFor="main-search">Describe the sequence you want to find</label><span className="search-glyph" aria-hidden="true">⌕</span><input id="main-search" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Try “counter-attacks after a press win”" /><button className="control-button accent-button" type="submit" disabled={state === "parsing" || state === "retrieving"}>{state === "parsing" || state === "retrieving" ? "Searching…" : "Search sequences"}</button></form>
    <div className="query-suggestions" aria-label="Suggested searches">{selectSuggestions.map((suggestion) => <button key={suggestion} type="button" className="suggestion" onClick={() => void executeSearch(suggestion)}>{suggestion}<span aria-hidden="true"> ↗</span></button>)}</div>
    <section className="filter-panel" aria-label="Editable search filters"><div className="filter-heading"><span className="eyebrow">Parsed filters</span><span className={`status-dot ${state}`} aria-hidden="true" /><span className="stage-message" role="status" aria-live="polite">{stage}</span><button className="text-button" type="button" onClick={() => void executeSearch(query, undefined, filters, true)}>Apply filters</button></div><div className="filter-chips">
      <label className="filter-chip"><span>Phase</span><select aria-label="Phase" value={filters.phase} onChange={(event) => updateField("phase", event.target.value)}><option value="">Any phase</option><option value="counter-attack">Counter-attack</option><option value="build-up">Build-up</option><option value="press-win-trigger">Press win</option><option value="zone-entry">Zone entry</option><option value="set-piece">Set piece</option></select></label>
      {(["team", "zone", "trigger", "competition", "outcome"] as const).map((key) => <label key={key} className="filter-chip"><span>{key}</span><input aria-label={`${key} filter`} value={filters[key]} onChange={(event) => updateField(key, event.target.value)} placeholder={key === "zone" ? "Any zone" : `Any ${key}`} /></label>)}
      <button className="text-button clear-filters" type="button" onClick={() => { setFilters(EMPTY_FILTERS); writeUrl(query, EMPTY_FILTERS, selectedId, compareIds, true); }}>Clear</button>
    </div></section>

    <div className="workspace-grid">
      <section className="results-column" aria-labelledby="results-title"><div className="section-heading"><div><span className="eyebrow">Match library / {source === "demo" ? "sample mode" : "live index"}</span><h2 id="results-title">Sequence results <span className="count-badge">{state === "parsing" || state === "retrieving" ? "···" : results.length}</span></h2></div><button className="text-button" type="button" onClick={share}>{copied ? "Link copied" : "Share search ↗"}</button></div>
        {(state === "parsing" || state === "retrieving") && <div className="results-list" aria-label="Loading sequence results">{[0, 1, 2].map((item) => <article className="result-card skeleton-card" key={item}><div className="skeleton-mark" /><div className="skeleton-copy"><span /><span /><span /></div></article>)}</div>}
        {state === "ready" && <div className="results-list">{results.map((result) => <article key={result.sequence_id} className={`result-card ${selectedId === result.sequence_id ? "result-selected" : ""}`} onMouseEnter={() => updateSelection(result.sequence_id, true)}>
            <button className="result-main" type="button" onClick={() => updateSelection(result.sequence_id)} aria-current={selectedId === result.sequence_id ? "true" : undefined}><span className="result-rank">{String(result.sequence_id).slice(-2)}</span><span className="result-copy"><span className="result-kicker">{result.team} <i>·</i> {result.competition}</span><strong>{result.tag.replaceAll("-", " ")}</strong><span>{result.summary}</span><span className="result-meta">Match {result.match_id} <i>·</i> Possession {result.possession_id} <i>·</i> score {result.score.toFixed(2)}</span></span></button>
            <div className="result-actions"><button className="icon-button" type="button" aria-label={`Find sequences similar to ${result.sequence_id}`} title="Find similar" onClick={() => void executeSearch(`Find sequences similar to sequence ${result.sequence_id}`, result.sequence_id, filters, true)}>↗</button><button className={`compare-toggle ${compareIds.includes(result.sequence_id) ? "is-on" : ""}`} type="button" aria-pressed={compareIds.includes(result.sequence_id)} onClick={() => setCompare(result.sequence_id)}>{compareIds.includes(result.sequence_id) ? "Comparing" : "Compare"}</button></div>
          </article>)}</div>}
        {state === "empty" && <div className="empty-state"><span className="empty-icon" aria-hidden="true">⌕</span><h3>No sequences match those filters.</h3><p>Try a wider phase, remove a team filter, or start with one of these searches.</p><div className="suggestion-stack">{selectSuggestions.map((item) => <button className="suggestion" key={item} onClick={() => void executeSearch(item)}>{item} →</button>)}</div></div>}
        {state === "error" && <div className="empty-state error-state"><h3>Search paused.</h3><p>The live index could not respond. Your query and filters are still here.</p><button className="control-button" onClick={() => void executeSearch(query)}>Retry search</button></div>}
        {state === "idle" && <div className="empty-state"><span className="empty-icon">↗</span><h3>Start with a tactical question.</h3><p>Describe the phase, pressure, team, or outcome you want to inspect.</p></div>}
      </section>

      <section className="pitch-column" aria-label="Selected sequence on pitch"><div className="pitch-panel-heading"><div><span className="eyebrow">Linked pitch / selection</span><h2>{selected?.sequence.title ?? "Waiting for a selection"}</h2></div><span className="live-indicator">{selected ? "● SELECTED" : "● READY"}</span></div>
        {selected ? <SequencePlayer key={selected.sequence.id} sequence={selected.sequence} label="Selected result" /> : <div className="pitch-placeholder"><div className="pitch-placeholder-inner"><span className="pitch-placeholder-ball">●</span><span>Select a sequence to follow its shape</span></div></div>}
        {selected && <div className="pitch-footer"><span>{selected.team} <i>·</i> {selected.tag.replaceAll("-", " ")}</span><Link href={`/dossier?team=${encodeURIComponent(selected.team)}&sequence=${selected.sequence_id}`}>Use in dossier →</Link></div>}
      </section>
    </div>

    {compare.length > 0 && <section className="compare-panel" aria-labelledby="compare-title"><div className="section-heading"><div><span className="eyebrow">Side by side / max two</span><h2 id="compare-title">Sequence comparison</h2></div><button className="text-button" onClick={() => { setCompareIds([]); writeUrl(query, filters, selectedId, []); }}>Clear comparison</button></div><div className="compare-grid">{compare.map((result, index) => <article className="compare-sequence" key={result.sequence_id}><div className="compare-head"><h3>{index === 0 ? "A" : "B"} / {result.sequence.title}</h3><span>{result.tag.replaceAll("-", " ")} · {result.score.toFixed(2)}</span></div><SequencePlayer sequence={result.sequence} label={`Compared sequence ${index === 0 ? "A" : "B"}`} /></article>)}{compare.length === 1 && <div className="compare-empty"><span>Choose one more sequence</span><p>Use Compare on another result to line up the patterns.</p></div>}</div></section>}
    <footer className="product-footer"><span>HALFSPACE · TACTICAL SEQUENCE INTELLIGENCE</span><Link href="/design">Design system</Link><Link href="/dossier">Dossier workspace</Link></footer>

    {commandOpen && <div className="command-backdrop" role="presentation" onMouseDown={(event) => { if (event.target === event.currentTarget) setCommandOpen(false); }}><section className="command-dialog" role="dialog" aria-modal="true" aria-labelledby="command-title"><div className="command-topline"><span id="command-title" className="eyebrow">Command search</span><kbd>ESC</kbd></div><form className="command-form" onSubmit={submitCommand}><label className="sr-only" htmlFor="command-search">Search sequences in natural language</label><span aria-hidden="true">⌕</span><input id="command-search" ref={commandRef} value={commandQuery} onChange={(event) => setCommandQuery(event.target.value)} placeholder="Ask about a tactical pattern…" /><button className="control-button accent-button" type="submit">Search</button></form><div className="command-hints"><span>Suggested</span>{selectSuggestions.map((item) => <button key={item} onClick={() => { setCommandQuery(item); void executeSearch(item); }}>{item}<kbd>↵</kbd></button>)}</div><p className="command-footnote"><kbd>↵</kbd> run search <kbd>⌘ K</kbd> open command bar</p></section></div>}
  </main>;
}

export { DEMO_RESULTS };
