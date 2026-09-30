import type { Sequence, SequenceFrame } from "../components/SequencePlayer";

export type SearchFilters = { phase: string; zone: string; trigger: string; team: string; competition: string; outcome: string };
export type SequenceResult = { sequence_id: number; match_id: number; possession_id: number; phase_index: number; tag: string; score: number; team: string; competition: string; summary: string; sequence: Sequence };
export type DossierClaimData = { statement: string; evidence_ids: string[]; checks?: { metric: string; value: number }[] };
export type DossierData = { overview: DossierClaimData; claims: DossierClaimData[]; verification?: Record<string, number> };

export const EMPTY_FILTERS: SearchFilters = { phase: "", zone: "", trigger: "", team: "", competition: "", outcome: "" };
const tags = ["counter-attack", "build-up", "press-win-trigger", "zone-entry", "set-piece", "counter-attack", "build-up", "zone-entry"];
const teams = ["Arsenal", "Manchester City", "Barcelona", "Liverpool", "Arsenal", "Bayern Munich", "Chelsea", "Real Madrid"];
const competitions = ["Premier League", "Premier League", "La Liga", "Premier League", "Premier League", "Bundesliga", "Premier League", "La Liga"];
const summaries = [
  "Quick regain, vertical carry, and a runner breaking beyond the back line.",
  "Patient first phase draws pressure before a clean switch into the right half-space.",
  "A counterpress recovery immediately turns into a forward pass behind midfield.",
  "Third-player combination enters the box channel with support arriving centrally.",
  "Corner delivery targets the near-post run; second ball remains live.",
  "Three-pass transition attacks the space before the opponent can reset.",
  "Short build-up uses the goalkeeper to create a free player on the left.",
  "Wide overload opens the inside lane for a progressive carry.",
];

function frameAt(index: number, tick: number, setPiece = false): SequenceFrame {
  const progress = tick / 7;
  const startX = index % 2 ? 27 : 22;
  const startY = index % 3 ? 54 : 27;
  const ball = setPiece ? { x: 118 - progress * 15, y: 5 + progress * 31 } : { x: startX + progress * 55, y: startY + progress * (index % 2 ? -27 : 25) };
  const from = setPiece ? { x: 118 - Math.max(0, tick - 1) / 7 * 15, y: 5 + Math.max(0, tick - 1) / 7 * 31 } : { x: startX + Math.max(0, tick - 1) / 7 * 55, y: startY + Math.max(0, tick - 1) / 7 * (index % 2 ? -27 : 25) };
  const openPlayHome = [[5,40,1],[18,12,2],[22,30,4],[22,50,5],[18,68,3],[37,20,6],[41,40,8],[37,60,10],[57,16,7],[61,40,9],[57,64,11]];
  const openPlayAway = [[115,40,1],[101,13,2],[96,30,4],[96,50,5],[101,67,3],[83,18,7],[79,35,6],[79,54,8],[69,23,11],[67,47,9],[72,63,10]];
  const cornerHome = [[5,40,1],[88,17,2],[98,30,4],[99,49,5],[90,64,3],[101,25,6],[104,36,8],[100,55,10],[112,28,7],[110,43,9],[116,7,11]];
  const cornerAway = [[115,40,1],[107,25,2],[104,32,4],[104,47,5],[107,56,3],[97,23,6],[96,34,8],[96,48,10],[87,28,7],[89,44,9],[91,59,11]];
  const homeLineup = setPiece ? cornerHome : openPlayHome;
  const awayLineup = setPiece ? cornerAway : openPlayAway;
  return {
    timeMs: tick * 420,
    ball,
    players: [
      ...homeLineup.map(([x,y,number], playerIndex) => ({ id: `h-${index}-${playerIndex}`, team: "home" as const, number, x: x + (setPiece ? -progress * (playerIndex === 10 ? 8 : playerIndex > 5 ? 2 : 0) : progress * (playerIndex > 7 ? 9 : 5)), y: y + (setPiece ? progress * (playerIndex % 2 ? 1 : -1) : Math.sin(progress * Math.PI + playerIndex) * 2) })),
      ...awayLineup.map(([x,y,number], playerIndex) => ({ id: `a-${index}-${playerIndex}`, team: "away" as const, number, x: x + (setPiece ? -progress * (playerIndex > 5 ? 2 : 0) : -progress * 5), y: y + Math.sin(progress * Math.PI + playerIndex) * 1.5 })),
    ],
    pass: tick ? { from, to: ball } : undefined,
  };
}

export const DEMO_RESULTS: SequenceResult[] = tags.map((tag, index) => {
  const frames = Array.from({ length: 8 }, (_, tick) => frameAt(index, tick, tag === "set-piece"));
  return {
    sequence_id: 4102 + index * 5,
    match_id: 3869685 + index,
    possession_id: 14 + index,
    phase_index: index % 2,
    tag,
    score: Number((0.96 - index * 0.035).toFixed(3)),
    team: teams[index],
    competition: competitions[index],
    summary: summaries[index],
    sequence: { id: `demo-${4102 + index * 5}`, title: `${teams[index]} · ${tag.replaceAll("-", " ")}`, durationMs: 2940, frames, dataSource: "sample" },
  };
});

export function sequenceForId(id: string | number): Sequence {
  const normalized = String(id).replace(/^sequence:/, "").replace(/^event:/, "");
  const exact = DEMO_RESULTS.find((result) => String(result.sequence_id) === normalized);
  if (exact) return exact.sequence;
  const index = Math.abs(Number.parseInt(normalized, 10) || 0) % DEMO_RESULTS.length;
  return DEMO_RESULTS[index].sequence;
}

export function demoSearch(query: string, filters: SearchFilters, exemplarId?: number): SequenceResult[] {
  let rows = [...DEMO_RESULTS];
  if (exemplarId) {
    const source = rows.find((row) => row.sequence_id === exemplarId) ?? rows[0];
    rows = rows.filter((row) => row.sequence_id !== source.sequence_id).sort((a, b) => Math.abs(a.sequence_id - source.sequence_id) - Math.abs(b.sequence_id - source.sequence_id));
  }
  const phase = filters.phase || (/counter|transition/i.test(query) ? "counter-attack" : /set.?piece|corner/i.test(query) ? "set-piece" : /build.?up/i.test(query) ? "build-up" : "");
  if (phase) rows = rows.filter((row) => row.tag === phase);
  if (filters.zone) {
    const match = filters.zone.match(/x(\d+)-(\d+)\s*\/\s*y(\d+)-(\d+)/i);
    if (match) {
      const [xMin, xMax, yMin, yMax] = match.slice(1).map((value) => Number(value) - 1);
      rows = rows.filter((row) => row.sequence.frames.some((frame) => frame.ball.x / 10 >= xMin && frame.ball.x / 10 <= xMax + 1 && frame.ball.y / 10 >= yMin && frame.ball.y / 10 <= yMax + 1));
    }
  }
  if (filters.team) rows = rows.filter((row) => row.team.toLowerCase().includes(filters.team.toLowerCase()));
  if (filters.competition) rows = rows.filter((row) => row.competition.toLowerCase().includes(filters.competition.toLowerCase()));
  if (filters.outcome && filters.outcome !== "Any") rows = rows.filter((row) => /progress|chance|success/i.test(row.summary));
  if (filters.trigger) rows = rows.filter((row) => row.summary.toLowerCase().includes(filters.trigger.toLowerCase()) || row.tag.includes(filters.trigger.toLowerCase()));
  return rows.slice(0, 6);
}

export const DEMO_DOSSIER: DossierData = {
  overview: { statement: "Arsenal's sample profile is strongest when it regains the ball and attacks forward space quickly.", evidence_ids: ["sequence:4102"] },
  claims: [
    { statement: "The counter-attack sample reaches the attacking third in three progressive actions.", evidence_ids: ["sequence:4102", "event:41021"], checks: [{ metric: "progressive actions", value: 3 }] },
    { statement: "Build-up sequences use a wider route before entering the final third.", evidence_ids: ["sequence:4107", "event:41071"] },
    { statement: "The press-win sample begins with a recovery and creates an immediate forward option.", evidence_ids: ["sequence:4112", "event:41121"] },
  ],
};

export function parseDemoQuery(query: string): { semantic_query: string; filters: Partial<SearchFilters>; exemplar_sequence_id: number | null } {
  const lower = query.toLowerCase();
  const phase = lower.includes("counter") || lower.includes("transition") ? "counter-attack" : lower.includes("set piece") || lower.includes("corner") ? "set-piece" : lower.includes("build") ? "build-up" : lower.includes("press") ? "press-win-trigger" : "";
  const team = teams.find((name) => lower.includes(name.toLowerCase())) ?? "";
  const id = query.match(/sequence\s*(?:#|id\s*)?(\d+)/i);
  return { semantic_query: query.trim(), filters: { phase, team }, exemplar_sequence_id: id ? Number(id[1]) : null };
}
