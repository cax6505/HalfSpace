from __future__ import annotations

import json
import time
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse

from app.search import run_search
from app.search_models import SearchRequest
from app.agent_graph import build_scout_graph, initial_state, report_cost
from app.dossier_models import ScoutRequest

app = FastAPI(title="HalfSpace API", version="0.2.0")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/search")
async def search(request: SearchRequest):
    async def events():
        try:
            async for payload in run_search(request):
                yield f"event: {payload['stage']}\ndata: {json.dumps(payload, default=str)}\n\n"
        except ValueError as exc:
            yield f"event: error\ndata: {json.dumps({'error': str(exc)})}\n\n"
        except RuntimeError as exc:
            yield f"event: error\ndata: {json.dumps({'error': str(exc)})}\n\n"

    if request.stream:
        return StreamingResponse(events(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})
    final: dict[str, Any] | None = None
    try:
        async for payload in run_search(request):
            if payload.get("stage") == "complete": final = payload
        if final is None: raise RuntimeError("Search did not produce a result")
        return final
    except (ValueError, RuntimeError) as exc:
        raise HTTPException(status_code=422 if isinstance(exc, ValueError) else 503, detail=str(exc)) from exc


@app.post("/scout/dossier")
async def scout_dossier(request: ScoutRequest):
    async def events():
        graph = build_scout_graph()
        state = initial_state(request.team, request.query)
        current: dict[str, Any] = dict(state)
        steps = 0
        try:
            async for update in graph.astream(state, stream_mode="updates"):
                for name, delta in update.items():
                    current.update(delta)
                    steps += int("trace_event" in delta)
                    trace = delta.get("trace_event", {"step": name})
                    yield f"event: step\ndata: {json.dumps(trace, default=str)}\n\n"
            dossier = current.get("dossier")
            if dossier is None:
                raise RuntimeError("Scout graph did not produce a verified dossier")
            final = {"dossier": dossier, "steps": steps, "latency_ms": round((time.perf_counter()-state['start_time'])*1000, 2), "cost_usd": report_cost(current), "token_usage": current.get("token_usage", {})}
            yield f"event: final\ndata: {json.dumps(final, default=str)}\n\n"
        except Exception as exc:
            yield f"event: error\ndata: {json.dumps({'error': str(exc)[:800]})}\n\n"

    if request.stream:
        return StreamingResponse(events(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})
    final: dict[str, Any] | None = None
    async for chunk in events():
        if chunk.startswith("event: final\n"):
            final = json.loads(chunk.split("data: ", 1)[1])
        elif chunk.startswith("event: error\n"):
            detail = json.loads(chunk.split("data: ", 1)[1]).get("error", "Scout graph failed")
            raise HTTPException(status_code=503, detail=detail)
    if final is None: raise HTTPException(status_code=503, detail="Scout graph did not return a dossier")
    return final
