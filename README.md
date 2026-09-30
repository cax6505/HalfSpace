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

Python 3.12 and Node.js 20+ are expected.
