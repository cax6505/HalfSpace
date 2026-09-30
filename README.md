# halfspace

Football sequence analysis monorepo: Next.js web app, FastAPI service, StatsBomb open-data pipeline, and PyTorch modeling workspace.

## Quick start

```sh
cp .env.example .env
docker compose up -d postgres redis
make install
make test
make ingest
```

`make ingest` downloads StatsBomb open data and loads the first two available competitions. Set `COMPETITION_IDS="2 11"` (space-separated) to choose competitions. Point `DATABASE_URL` at Neon to use hosted Postgres; local development uses the Compose database. See [architecture](docs/ARCHITECTURE.md) and [design](docs/DESIGN.md).

Search API setup requires `OPENAI_API_KEY`, Postgres sequence embeddings, and the cross-encoder weights (downloaded on first rerank). `POST /search` streams SSE stage events by default; send `{"query":"...", "stream":false}` for a JSON response. Redis and Langfuse are optional. Search evaluation fixtures, promptfoo regression, and the ablation command are documented in [docs/EVALS.md](docs/EVALS.md).

`POST /scout/dossier` streams LangGraph planner, retrieval, synthesis, critique, and verification steps. Start the MCP stdio server with `make mcp`; evaluate with `make scout-benchmark`. SQL ground truth is populated from the live database by the benchmark runner.

Python 3.12 and Node.js 20+ are expected.
