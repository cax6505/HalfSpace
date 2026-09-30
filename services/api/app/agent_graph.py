"""Planner → Retriever → Tactician → Critic → Evidence Verifier LangGraph."""
from __future__ import annotations

import asyncio
import json
import math
import re
import time
from collections import defaultdict
from functools import lru_cache
from typing import Any, TypedDict

from openai import OpenAI
from langgraph.graph import END, START, StateGraph

from app.dossier_models import Critique, ScoutPlan, ScoutQuestion, TacticalDossier
from app.scout_tools import calculate_xt, guarded_text_to_sql, passing_network, pitch_control_360, search_sequences, set_piece_summary
from app.settings import settings
from app.tracing import traced


class AgentState(TypedDict, total=False):
    query: str
    team: str
    questions: list[ScoutQuestion]
    followups: list[ScoutQuestion]
    evidence: list[dict[str, Any]]
    tool_results: list[dict[str, Any]]
    dossier: dict[str, Any]
    critique: dict[str, Any]
    rounds: int
    continue_review: bool
    dropped_claims: list[dict[str, Any]]
    verification: dict[str, Any]
    trace_event: dict[str, Any]
    token_usage: dict[str, int]
    start_time: float


def _client() -> OpenAI:
    if not settings.openai_api_key:
        raise RuntimeError("OPENAI_API_KEY is required for the scout dossier graph")
    args = {"api_key": settings.openai_api_key}
    if settings.openai_base_url: args["base_url"] = settings.openai_base_url
    return OpenAI(**args)


def _structured(schema, system: str, user: str) -> tuple[Any, dict[str, int]]:
    completion = _client().chat.completions.parse(
        model=settings.search_llm_model, temperature=0, response_format=schema,
        messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
    )
    parsed = completion.choices[0].message.parsed
    if parsed is None:
        raise ValueError(f"Model returned no valid {schema.__name__} object")
    usage = {"input_tokens": completion.usage.prompt_tokens if completion.usage else 0, "output_tokens": completion.usage.completion_tokens if completion.usage else 0}
    return parsed, usage


def _add_usage(left: dict[str, int], right: dict[str, int]) -> dict[str, int]:
    keys = set(left) | set(right) | {"input_tokens", "output_tokens"}
    return {key: int(left.get(key, 0)) + int(right.get(key, 0)) for key in keys}


@traced("scout.planner")
def planner_node(state: AgentState) -> dict[str, Any]:
    plan, usage = _structured(
        ScoutPlan,
        "You are the Planner for a football scouting dossier. Decompose the request into 4-6 independent, answerable questions using different available tools where useful. Prioritize evidence that directly compares team strengths, weaknesses, transition behavior, chance creation, and set pieces. Include the team in tool arguments when relevant. Never invent match or sequence IDs.",
        f"Team: {state['team']}\nScout request: {state['query']}",
    )
    return {"questions": [question.model_dump() for question in plan.questions], "token_usage": _add_usage(state.get("token_usage", {}), usage), "trace_event": {"step": "planner", "questions": [question.model_dump() for question in plan.questions]}}


def _call_tool(question: dict[str, Any], team: str) -> dict[str, Any]:
    kind, text_question = question["tool"], question["question"]
    query_team = question.get("team") or team
    limit = question.get("limit", 10)
    if kind == "sql":
        return guarded_text_to_sql(text_question, query_team)
    if kind == "search_sequences":
        return search_sequences(f"{query_team}: {text_question}", limit)
    if kind == "xt": return calculate_xt(query_team, question.get("match_id"))
    if kind == "passing_network": return passing_network(query_team, question.get("match_id"))
    if kind == "pitch_control": return pitch_control_360(question.get("match_id"), query_team)
    if kind == "set_piece_summary": return set_piece_summary(query_team, question.get("match_id"))
    return {"error": "Unknown tool"}


@traced("scout.retriever")
async def retriever_node(state: AgentState) -> dict[str, Any]:
    questions = state.get("questions", [])
    outputs = await asyncio.gather(*(asyncio.to_thread(_call_tool, question, state["team"]) for question in questions), return_exceptions=True)
    new_evidence = []; results = []; errors = []; usage = state.get("token_usage", {})
    for question, output in zip(questions, outputs):
        if isinstance(output, BaseException):
            errors.append({"tool": question["tool"], "error": str(output)[:400]})
            results.append({"question": question["question"], "tool": question["tool"], "error": str(output)[:400]})
            continue
        evidence = output.get("evidence", [])
        usage = _add_usage(usage, output.get("usage", {}))
        # Bound graph state and LLM context while retaining many independent source IDs.
        new_evidence.extend(evidence if len(evidence) <= 100 else evidence[:99] + evidence[-1:])
        results.append({key: value for key, value in output.items() if key != "evidence"})
    old = state.get("evidence", [])
    combined = [{**item, "facts": dict(item.get("facts", {}))} for item in old]
    positions = {item["evidence_id"]: index for index, item in enumerate(combined)}
    for item in new_evidence:
        evidence_id = item.get("evidence_id")
        if evidence_id in positions:
            previous = combined[positions[evidence_id]]
            previous["facts"].update(item.get("facts", {}))
            if previous.get("tool") != item.get("tool"):
                previous["tools"] = list(dict.fromkeys(previous.get("tools", [previous.get("tool")]) + [item.get("tool")]))
        elif evidence_id:
            positions[evidence_id] = len(combined)
            combined.append(item)
    return {"evidence": combined, "tool_results": results, "token_usage": usage, "trace_event": {"step": "retriever", "question_count": len(questions), "new_evidence_count": len(combined)-len(old), "errors": errors}}


@traced("scout.tactician")
def tactician_node(state: AgentState) -> dict[str, Any]:
    evidence = state.get("evidence", [])
    dossier, usage = _structured(
        TacticalDossier,
        "You are the Tactician. Write a concise evidence-led scouting dossier. The overview and every claim must include one or more exact evidence_ids from the supplied evidence. Do not invent IDs. Every factual or numeric statement belongs in a claim. Include numeric checks for numbers in a claim using metric/value pairs that can be verified against cited tool facts. Separate observations from conclusions and avoid overstating heuristic xT or snapshot pitch-control estimates.",
        f"Team: {state['team']}\nRequest: {state['query']}\nTool results:\n{json.dumps(state.get('tool_results', []), default=str)[:15000]}\nEvidence:\n{json.dumps(evidence, default=str)[:25000]}",
    )
    return {"dossier": dossier.model_dump(), "token_usage": _add_usage(state.get("token_usage", {}), usage), "trace_event": {"step": "tactician", "claim_count": len(dossier.claims)+1}}


@traced("scout.critic")
def critic_node(state: AgentState) -> dict[str, Any]:
    critique, usage = _structured(
        Critique,
        "You are a skeptical scouting critic. Challenge unsupported causal language, missing comparison context, and conclusions based on thin evidence. Request more evidence only when a specific missing fact would materially improve the dossier. Follow-up questions must use an available tool and must not assume data exists. Do not restate unsupported claims as facts.",
        f"Team: {state['team']}\nDossier: {json.dumps(state.get('dossier', {}), default=str)}\nEvidence count: {len(state.get('evidence', []))}\nEvidence sample: {json.dumps(state.get('evidence', [])[:40], default=str)[:16000]}\nPrior tool failures: {json.dumps([r for r in state.get('tool_results',[]) if r.get('error')])}",
    )
    rounds = state.get("rounds", 0)
    should_continue = critique.request_more_evidence and bool(critique.followup_questions) and rounds < settings.scout_max_rounds
    result: dict[str, Any] = {"critique": critique.model_dump(), "rounds": rounds + int(should_continue), "continue_review": should_continue, "token_usage": _add_usage(state.get("token_usage", {}), usage), "trace_event": {"step": "critic", "request_more_evidence": should_continue, "concerns": critique.concerns}}
    if should_continue:
        result["questions"] = [q.model_dump() for q in critique.followup_questions]
    return result


def _numbers(value: Any):
    if isinstance(value, bool) or value is None: return
    if isinstance(value, (int, float)): yield float(value)
    elif isinstance(value, dict):
        for child in value.values(): yield from _numbers(child)
    elif isinstance(value, (list, tuple)):
        for child in value: yield from _numbers(child)


def _statement_numbers(statement: str) -> list[float]:
    values = []
    for match in re.finditer(r"(?<![A-Za-z])\d+(?:,\d{3})*(?:\.\d+)?%?", statement):
        raw = match.group(0); value = float(raw.rstrip("%").replace(",", ""))
        values.append(value / 100.0 if raw.endswith("%") else value)
    return values


@traced("scout.evidence_verifier")
def verifier_node(state: AgentState) -> dict[str, Any]:
    evidence = state.get("evidence", [])
    known = {item.get("evidence_id") for item in evidence}
    facts_by_id: dict[str, list[float]] = defaultdict(list)
    for item in evidence:
        facts_by_id[item["evidence_id"]].extend(_numbers(item.get("facts", {})))
    dossier = state.get("dossier", {})
    claims = [("overview", dossier.get("overview", {}))] + [("claim", claim) for claim in dossier.get("claims", [])]
    supported_overview = None; supported_claims = []; dropped = []
    for claim_kind, claim in claims:
        ids = claim.get("evidence_ids") or []
        reasons = []
        if not ids: reasons.append("claim has no evidence IDs")
        unknown = [evidence_id for evidence_id in ids if evidence_id not in known]
        if unknown: reasons.append("unknown evidence IDs: " + ", ".join(unknown))
        numeric_values = _statement_numbers(claim.get("statement", ""))
        for check in claim.get("checks", []):
            value = float(check["value"])
            cited_numbers = [number for evidence_id in ids if evidence_id in facts_by_id for number in facts_by_id[evidence_id]]
            if not any(math.isclose(value, candidate, rel_tol=1e-4, abs_tol=1e-4) for candidate in cited_numbers):
                reasons.append(f"numeric check {check['metric']}={value:g} is absent from cited tool facts")
        cited_numbers = [number for evidence_id in ids if evidence_id in facts_by_id for number in facts_by_id[evidence_id]]
        for number in numeric_values:
            if not any(math.isclose(number, candidate, rel_tol=1e-4, abs_tol=1e-4) for candidate in cited_numbers):
                reasons.append(f"number {number:g} is not present in cited tool facts")
                break
        if reasons:
            dropped.append({"statement": claim.get("statement", ""), "evidence_ids": ids, "reasons": reasons})
        else:
            if claim_kind == "overview": supported_overview = claim
            else: supported_claims.append(claim)
    supported_count = len(supported_claims) + int(supported_overview is not None)
    report = {"team": state["team"], "request": state["query"], "overview": supported_overview, "claims": supported_claims, "dropped_claims": dropped, "evidence": evidence, "verification": {"submitted_claims": len(claims), "supported_claims": supported_count, "dropped_claims": len(dropped)}}
    return {"verification": report["verification"], "dropped_claims": dropped, "dossier": report, "trace_event": {"step": "verifier", **report["verification"]}}


def _route_after_critic(state: AgentState) -> str:
    return "retriever" if state.get("continue_review") else "verifier"


@lru_cache(maxsize=1)
def build_scout_graph():
    graph = StateGraph(AgentState)
    graph.add_node("planner", planner_node)
    graph.add_node("retriever", retriever_node)
    graph.add_node("tactician", tactician_node)
    graph.add_node("critic", critic_node)
    graph.add_node("verifier", verifier_node)
    graph.add_edge(START, "planner")
    graph.add_edge("planner", "retriever")
    graph.add_edge("retriever", "tactician")
    graph.add_edge("tactician", "critic")
    graph.add_conditional_edges("critic", _route_after_critic, {"retriever": "retriever", "verifier": "verifier"})
    graph.add_edge("verifier", END)
    return graph.compile()


def initial_state(team: str, query: str) -> AgentState:
    return {"team": team, "query": query, "evidence": [], "tool_results": [], "rounds": 0, "token_usage": {"input_tokens": 0, "output_tokens": 0}, "start_time": time.perf_counter()}


def report_cost(state: AgentState) -> float:
    usage = state.get("token_usage", {})
    return (usage.get("input_tokens", 0) * settings.search_cost_input_per_million + usage.get("output_tokens", 0) * settings.search_cost_output_per_million + usage.get("embedding_tokens", 0) * settings.search_embedding_cost_per_million) / 1_000_000


async def run_single_agent_baseline(team: str, query: str) -> AgentState:
    """One-shot synthesizer over a fixed tool bundle; no planner or critic."""
    state = initial_state(team, query)
    questions = [
        {"tool": "sql", "question": query, "team": team, "limit": 50},
        {"tool": "search_sequences", "question": query, "team": team, "limit": 20},
        {"tool": "xt", "question": query, "team": team},
        {"tool": "passing_network", "question": query, "team": team},
        {"tool": "pitch_control", "question": query, "team": team},
        {"tool": "set_piece_summary", "question": query, "team": team},
    ]
    outputs = await asyncio.gather(*(asyncio.to_thread(_call_tool, question, team) for question in questions), return_exceptions=True)
    evidence = []; results = []; usage = state["token_usage"]
    for question, output in zip(questions, outputs):
        if isinstance(output, BaseException):
            results.append({"tool": question["tool"], "error": str(output)[:400]}); continue
        evidence.extend(output.get("evidence", [])[:100])
        usage = _add_usage(usage, output.get("usage", {}))
        results.append({key: value for key, value in output.items() if key != "evidence"})
    deduped = {}
    for item in evidence:
        if item["evidence_id"] not in deduped:
            deduped[item["evidence_id"]] = {**item, "facts": dict(item.get("facts", {}))}
        else:
            deduped[item["evidence_id"]]["facts"].update(item.get("facts", {}))
    state.update({"evidence": list(deduped.values()), "tool_results": results, "token_usage": usage, "trace_event": {"step": "single_agent_tools", "tool_count": len(questions)}})
    state.update(tactician_node(state))
    verified = verifier_node(state)
    state.update(verified)
    return state
