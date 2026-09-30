# Architecture

## Components

- `apps/web` is the Next.js App Router and TypeScript user interface. It will call the API for match and sequence views.
- `services/api` is a Python 3.12 FastAPI service. SQLAlchemy owns Postgres connections; Pydantic settings provide typed configuration. `app.ingest` is the repeatable StatsBomb open-data loader.
- `ml` holds PyTorch training and inference code. Sequence tokens are stored separately from optional 384-dimensional embeddings.
- `docs` records architecture and design constraints.
- Postgres is the source of truth. Local Compose uses pgvector's Postgres 16 image; Neon can be used by setting `DATABASE_URL`. Redis is available for future job queues and cache use.

## Data flow

1. The loader reads the public StatsBomb competitions index, then downloads every season/match for two competitions by default. `COMPETITION_IDS` can select competition IDs explicitly.
2. Match metadata, teams, players, events, shot freeze frames, and derived possessions are upserted. Source records retain their original JSON in `raw` columns where applicable.
3. Events are ordered and grouped by possession. A phase starts at possession changes, restart events, or gaps longer than ten seconds. Rule tags are assigned in priority order: set-piece, press-win trigger, counter-attack, zone-entry, then build-up. Each sequence is tokenized into event type, 12×8 pitch zone, outcome, and elapsed seconds from the preceding event.
4. The web app and model code consume persisted sequences. The model may write vector embeddings back to the sequence row; it is not required for ingestion.

## Decisions and tradeoffs

- **Postgres plus JSONB:** relational columns support joins and filters, while `raw`, `location`, and `tokens` retain source structure without prematurely flattening every StatsBomb field. Neon works as standard Postgres.
- **pgvector:** enabled at schema initialization to support future similarity search. The embedding column is nullable, so ingestion does not require a model. Add a vector index only after selecting a distance metric and measuring corpus/query scale.
- **Rule-based phase boundaries:** possession ID changes are the hard boundary; restarts and pauses over ten seconds split tactical phases within a possession. Rules are deterministic and unit-tested, and can later be versioned when labels evolve.
- **Idempotency:** stable StatsBomb match/event identifiers use primary keys, and upserts refresh changed source rows. A possession's derived sequence rows are replaced transactionally when recomputed.
- **Indexes:** primary keys serve direct entity lookups; `events_match_order_idx` supports ordered match timelines, `events_possession_idx` supports possession extraction, and `possessions_match_idx` and `sequences_match_possession_idx` support match-to-possession/phase traversal. `sequences_tag_idx` serves tag counts and tag filtering. These indexes avoid indexing every JSONB field, which would add ingest cost without an established query need.
- **Redis:** included in local infrastructure for future asynchronous ingest/model jobs; the initial loader runs synchronously to keep setup and failures observable.

## Schema

`matches`, `teams`, `players`, `events`, `possessions`, `sequences`, and `freeze_frames` are created idempotently by `app.db.initialize`. Event records reference matches, freeze frames reference events, and all match-derived data can be removed with a match cascade. Sequence uniqueness is `(match_id, possession_id, phase_index)`.

## Operational commands

`docker compose up -d postgres redis` starts local dependencies. `make ingest` downloads and loads data, then prints the count of generated sequences per tag. `make test` runs the segmentation rule tests. Configure a Neon URL through `DATABASE_URL` for hosted storage.
