from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import math
import random
import time
from functools import lru_cache
from typing import Any, AsyncIterator

from openai import OpenAI
from pydantic import ValidationError
from sqlalchemy import text

from app.db import get_engine
from app.search_models import SearchFilters, SearchHit, SearchIntent, SearchRequest
from app.settings import settings
from app.tracing import traced

log = logging.getLogger(__name__)


def _client() -> OpenAI:
    if not settings.openai_api_key:
        raise RuntimeError("OPENAI_API_KEY is required for sequence search")
    kwargs = {"api_key": settings.openai_api_key}
    if settings.openai_base_url:
        kwargs["base_url"] = settings.openai_base_url
    return OpenAI(**kwargs)


@traced("search.parse_intent")
def parse_intent(query: str) -> tuple[SearchIntent, dict[str, int]]:
    client = _client()
    messages: list[dict[str, str]] = [
        {"role": "system", "content": "Parse football sequence search requests. Return only the schema. Use phase for a primary tactical tag (counter-attack, build-up, set-piece, press-win-trigger, zone-entry). Zone coordinates use x cells 0-11 from own goal to attacking goal and y cells 0-7 across the pitch. Only set a filter when the user specifies it. Keep the meaning of the request as semantic_query. exemplar_sequence_id is for an explicit sequence ID."},
        {"role": "user", "content": query},
    ]
    usage = {"input_tokens": 0, "output_tokens": 0}
    for attempt in range(2):
        try:
            completion = client.chat.completions.parse(model=settings.search_llm_model, messages=messages, response_format=SearchIntent, temperature=0)
            choice = completion.choices[0]
            parsed = choice.message.parsed
            if parsed is None:
                if choice.message.refusal:
                    raise ValueError(f"Search query refused: {choice.message.refusal}")
                raise ValidationError.from_exception_data("SearchIntent", [{"type": "missing", "loc": ("response",), "input": None}])
            if completion.usage:
                usage = {"input_tokens": completion.usage.prompt_tokens, "output_tokens": completion.usage.completion_tokens}
            return parsed, usage
        except ValidationError as exc:
            if attempt:
                raise ValueError(f"Could not parse a valid search intent after one correction: {exc}") from exc
            messages.append({"role": "assistant", "content": "The previous response failed schema validation."})
            messages.append({"role": "user", "content": f"Return a corrected response that satisfies the schema. Validation error: {str(exc)[:1200]}"})
    raise RuntimeError("unreachable intent parse state")


@traced("search.embed_query")
def embed_query(query: str) -> tuple[list[float], int]:
    response = _client().embeddings.create(model=settings.search_embedding_model, input=query, dimensions=settings.search_embedding_dimensions)
    return response.data[0].embedding, response.usage.total_tokens


def _filter_sql(filters: SearchFilters) -> tuple[str, dict[str, Any]]:
    clauses: list[str] = []
    params: dict[str, Any] = {}
    if filters.phase:
        clauses.append("lower(s.tag) = lower(:phase)"); params["phase"] = filters.phase
    if filters.trigger:
        clauses.append("(s.tag ILIKE :trigger OR EXISTS (SELECT 1 FROM jsonb_array_elements(s.tokens) tok WHERE tok->>'event_type' ILIKE :trigger))")
        params["trigger"] = f"%{filters.trigger}%"
    if filters.team:
        clauses.append("EXISTS (SELECT 1 FROM possessions p JOIN teams t ON t.id=p.team_id WHERE p.match_id=s.match_id AND p.possession_id=s.possession_id AND t.name ILIKE :team)")
        params["team"] = f"%{filters.team}%"
    if filters.competition:
        try:
            params["competition_id"] = int(filters.competition)
            clauses.append("m.competition_id=:competition_id")
        except ValueError:
            clauses.append("c.name ILIKE :competition_name"); params["competition_name"] = f"%{filters.competition}%"
    if filters.outcome:
        clauses.append("EXISTS (SELECT 1 FROM jsonb_array_elements(s.tokens) tok WHERE tok->>'outcome' ILIKE :outcome)")
        params["outcome"] = f"%{filters.outcome}%"
    if filters.zone:
        zone = filters.zone
        clauses.append("EXISTS (SELECT 1 FROM jsonb_array_elements(s.tokens) tok WHERE (tok->'zone'->>0)::int BETWEEN :x_min AND :x_max AND (tok->'zone'->>1)::int BETWEEN :y_min AND :y_max)")
        params.update(x_min=zone.x_min, x_max=zone.x_max, y_min=zone.y_min, y_max=zone.y_max)
    return (" AND " + " AND ".join(clauses) if clauses else ""), params


@traced("search.pgvector_ann")
def _vector_candidates(vector: list[float], filters: SearchFilters, exclude_id: int | None = None) -> list[dict[str, Any]]:
    where, params = _filter_sql(filters)
    params.update(vector="[" + ",".join(str(v) for v in vector) + "]", limit=settings.search_candidate_limit, exclude_id=exclude_id)
    sql = text(f"""SELECT s.id,s.match_id,s.possession_id,s.phase_index,s.tag,s.tokens,
        1-(s.embedding <=> CAST(:vector AS vector)) AS score
        FROM sequences s JOIN matches m ON m.id=s.match_id LEFT JOIN competitions c ON c.id=m.competition_id
        WHERE s.embedding IS NOT NULL AND (CAST(:exclude_id AS bigint) IS NULL OR s.id != :exclude_id){where}
        ORDER BY s.embedding <=> CAST(:vector AS vector) LIMIT :limit""")
    with get_engine().connect() as conn:
        return [dict(row) for row in conn.execute(sql, params).mappings().all()]


@traced("search.postgres_fts")
def _fts_candidates(query: str, filters: SearchFilters) -> list[dict[str, Any]]:
    where, params = _filter_sql(filters)
    params.update(query=query, limit=settings.search_candidate_limit)
    sql = text(f"""SELECT s.id,s.match_id,s.possession_id,s.phase_index,s.tag,s.tokens,
        ts_rank(to_tsvector('english',s.tag || ' ' || s.tokens::text),websearch_to_tsquery('english',:query)) AS score
        FROM sequences s JOIN matches m ON m.id=s.match_id LEFT JOIN competitions c ON c.id=m.competition_id
        WHERE to_tsvector('english',s.tag || ' ' || s.tokens::text) @@ websearch_to_tsquery('english',:query){where}
        ORDER BY score DESC LIMIT :limit""")
    with get_engine().connect() as conn:
        return [dict(row) for row in conn.execute(sql, params).mappings().all()]


@traced("search.cross_encoder_rerank")
def _rerank(query: str, candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not candidates:
        return candidates
    pairs = [(query, _sequence_text(row)) for row in candidates]
    scores = _cross_encoder().predict(pairs, show_progress_bar=False)
    for row, score in zip(candidates, scores):
        row["rerank_score"] = float(score)
    return sorted(candidates, key=lambda item: item["rerank_score"], reverse=True)


@lru_cache(maxsize=1)
def _cross_encoder():
    from sentence_transformers import CrossEncoder
    return CrossEncoder(settings.search_cross_encoder)


def _sequence_text(row: dict[str, Any]) -> str:
    tokens = row["tokens"]
    if isinstance(tokens, str):
        tokens = json.loads(tokens)
    pieces = [row.get("tag", "")]
    pieces.extend(f"{token.get('event_type', '')} zone={token.get('zone', [])} outcome={token.get('outcome', '')}" for token in tokens)
    return " ; ".join(pieces)


def _rrf(vector_rows: list[dict[str, Any]], fts_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    merged: dict[int, dict[str, Any]] = {}
    for rows, source in ((vector_rows, "vector"), (fts_rows, "fts")):
        for rank, row in enumerate(rows, start=1):
            key = int(row["id"])
            item = merged.setdefault(key, {**row, "score": 0.0, "sources": []})
            item["score"] += 1.0 / (settings.search_rrf_k + rank)
            item["sources"].append(source)
    return sorted(merged.values(), key=lambda row: row["score"], reverse=True)


def _exemplar_query(sequence_id: int) -> tuple[list[float], str]:
    with get_engine().connect() as conn:
        row = conn.execute(text("SELECT embedding,tokens,tag FROM sequences WHERE id=:id"), {"id": sequence_id}).mappings().first()
    if not row or row["embedding"] is None:
        raise ValueError(f"Exemplar sequence {sequence_id} has no embedding")
    vector = row["embedding"]
    if isinstance(vector, str):
        vector = json.loads(vector.strip("[]"))
    return list(vector), _sequence_text(dict(row))


def _result_rows(rows: list[dict[str, Any]], limit: int) -> list[dict[str, Any]]:
    hits = []
    for row in rows[:limit]:
        hits.append(SearchHit(sequence_id=int(row["id"]), match_id=int(row["match_id"]), possession_id=int(row["possession_id"]), phase_index=int(row["phase_index"]), tag=row["tag"], score=float(row["score"]), tokens=row["tokens"] if isinstance(row["tokens"], list) else json.loads(row["tokens"]), rerank_score=row.get("rerank_score")).model_dump())
    return hits


def _lsh_bucket(vector: list[float]) -> str:
    rng = random.Random(9041)
    bits = []
    for _ in range(16):
        projection = sum(value * rng.gauss(0, 1) for value in vector)
        bits.append("1" if projection >= 0 else "0")
    return "".join(bits)


def _cosine(left: list[float], right: list[float]) -> float:
    numerator = sum(a * b for a, b in zip(left, right))
    denominator = math.sqrt(sum(a * a for a in left) * sum(b * b for b in right))
    return numerator / denominator if denominator else 0.0


async def _semantic_cache_get(cache: Any, vector: list[float], intent: SearchIntent, limit: int) -> tuple[dict[str, Any], float] | None:
    scope = hashlib.sha256(json.dumps([intent.filters.model_dump(), limit, settings.search_embedding_model, settings.search_cross_encoder, settings.search_rrf_k, settings.search_candidate_limit], sort_keys=True).encode()).hexdigest()[:20]
    index_key = f"halfspace:search:lsh:{scope}:{_lsh_bucket(vector)}"
    try:
        best = None; best_score = -1.0
        members = await cache.smembers(index_key)
        for entry_key in list(members)[:200]:
            entry_raw = await cache.get(entry_key)
            if not entry_raw:
                continue
            entry = json.loads(entry_raw)
            similarity = _cosine(vector, entry["vector"])
            if similarity >= settings.search_cache_similarity and similarity > best_score:
                best, best_score = entry.get("result"), similarity
        return (best, best_score) if best else None
    except Exception as exc:
        log.debug("Redis semantic-cache lookup failed: %s", exc)
        return None


async def _semantic_cache_put(cache: Any, vector: list[float], result: dict[str, Any], intent: SearchIntent, limit: int) -> None:
    scope = hashlib.sha256(json.dumps([intent.filters.model_dump(), limit, settings.search_embedding_model, settings.search_cross_encoder, settings.search_rrf_k, settings.search_candidate_limit], sort_keys=True).encode()).hexdigest()[:20]
    index_key = f"halfspace:search:lsh:{scope}:{_lsh_bucket(vector)}"
    entry_key = f"halfspace:search:entry:{hashlib.sha256((scope + json.dumps(vector)).encode()).hexdigest()}"
    try:
        await cache.set(entry_key, json.dumps({"vector": vector, "result": result}, default=str), ex=settings.search_cache_ttl_seconds)
        await cache.sadd(index_key, entry_key)
        await cache.expire(index_key, settings.search_cache_ttl_seconds)
    except Exception as exc:
        log.debug("Redis semantic-cache write failed: %s", exc)


async def _cache():
    try:
        from redis.asyncio import Redis
        client = Redis.from_url(settings.redis_url, decode_responses=True, socket_connect_timeout=0.25, socket_timeout=0.25)
        await client.ping()
        return client
    except Exception as exc:
        log.debug("Redis cache unavailable: %s", exc)
        return None


async def run_search(request: SearchRequest) -> AsyncIterator[dict[str, Any]]:
    start = time.perf_counter()
    cache = await _cache()
    key = "halfspace:search:" + hashlib.sha256(json.dumps([request.query.casefold().strip(), request.limit, settings.search_llm_model, settings.search_embedding_model, settings.search_cross_encoder, settings.search_rrf_k, settings.search_candidate_limit]).encode()).hexdigest()
    if cache:
        try:
            cached = await cache.get(key)
            if cached:
                result = json.loads(cached); result["cached"] = True
                result["latency_ms"] = round((time.perf_counter() - start) * 1000, 3)
                result["cost_usd"] = 0.0
                yield {"stage": "cache_hit"}; yield {"stage": "complete", **result}
                await cache.aclose()
                return
        except Exception as exc:
            log.debug("Redis read failed: %s", exc)
    yield {"stage": "parsing"}
    intent, llm_usage = await asyncio.to_thread(parse_intent, request.query)
    embed_tokens = 0
    yield {"stage": "parsed", "intent": intent.model_dump()}
    if intent.exemplar_sequence_id is not None:
        vector, semantic_query = await asyncio.to_thread(_exemplar_query, intent.exemplar_sequence_id)
        exclude_id = intent.exemplar_sequence_id
        embed_tokens = 0
    else:
        semantic_query = intent.semantic_query
        yield {"stage": "embedding"}
        vector, embed_tokens = await asyncio.to_thread(embed_query, semantic_query)
        exclude_id = None
    if cache and intent.exemplar_sequence_id is None:
        cache_hit = await _semantic_cache_get(cache, vector, intent, request.limit)
        if cache_hit:
            similar_result, similarity = cache_hit
            similar_result["query"] = request.query
            similar_result["intent"] = intent.model_dump()
            similar_result["cached"] = True
            similar_result["latency_ms"] = round((time.perf_counter() - start) * 1000, 3)
            similar_result["cache_similarity"] = round(similarity, 4)
            similar_result["cost_usd"] = (llm_usage["input_tokens"] * settings.search_cost_input_per_million + llm_usage["output_tokens"] * settings.search_cost_output_per_million + embed_tokens * settings.search_embedding_cost_per_million) / 1_000_000
            yield {"stage": "semantic_cache_hit"}; yield {"stage": "complete", **similar_result}
            await cache.aclose()
            return
    branches = ["pgvector"] if exclude_id is not None else ["pgvector", "postgres_fts"]
    yield {"stage": "retrieving", "branches": branches}
    if exclude_id is not None:
        vector_rows = await asyncio.to_thread(_vector_candidates, vector, intent.filters, exclude_id)
        fts_rows = []
    else:
        vector_rows, fts_rows = await asyncio.gather(
            asyncio.to_thread(_vector_candidates, vector, intent.filters, exclude_id),
            asyncio.to_thread(_fts_candidates, semantic_query, intent.filters),
        )
    yield {"stage": "retrieved", "vector_count": len(vector_rows), "fts_count": len(fts_rows)}
    fused = _rrf(vector_rows, fts_rows)
    yield {"stage": "fused", "candidate_count": len(fused)}
    yield {"stage": "reranking"}
    reranked = await asyncio.to_thread(_rerank, semantic_query, fused[:settings.search_candidate_limit])
    hits = _result_rows(reranked, request.limit)
    latency_ms = (time.perf_counter() - start) * 1000
    cost = (llm_usage["input_tokens"] * settings.search_cost_input_per_million + llm_usage["output_tokens"] * settings.search_cost_output_per_million + embed_tokens * settings.search_embedding_cost_per_million) / 1_000_000
    result = {"query": request.query, "intent": intent.model_dump(), "results": hits, "latency_ms": round(latency_ms, 3), "cost_usd": cost, "cached": False}
    if cache:
        try:
            await cache.set(key, json.dumps(result, default=str), ex=settings.search_cache_ttl_seconds)
            if intent.exemplar_sequence_id is None:
                await _semantic_cache_put(cache, vector, result, intent, request.limit)
        except Exception as exc:
            log.debug("Redis write failed: %s", exc)
        finally:
            await cache.aclose()
    yield {"stage": "reranked", "count": len(hits)}
    yield {"stage": "complete", **result}
