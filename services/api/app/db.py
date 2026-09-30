from functools import lru_cache

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from app.settings import settings


@lru_cache(maxsize=1)
def get_engine() -> Engine:
    return create_engine(settings.database_url, pool_pre_ping=True)


SCHEMA = """
CREATE EXTENSION IF NOT EXISTS vector;
CREATE TABLE IF NOT EXISTS teams (id integer PRIMARY KEY, name text NOT NULL);
CREATE TABLE IF NOT EXISTS players (id integer PRIMARY KEY, name text NOT NULL, team_id integer REFERENCES teams(id));
CREATE TABLE IF NOT EXISTS competitions (id integer PRIMARY KEY, name text NOT NULL);
CREATE TABLE IF NOT EXISTS matches (id bigint PRIMARY KEY, competition_id integer NOT NULL, season_id integer NOT NULL, match_date date, home_team_id integer, away_team_id integer, raw jsonb NOT NULL);
CREATE TABLE IF NOT EXISTS events (id text PRIMARY KEY, match_id bigint NOT NULL REFERENCES matches(id) ON DELETE CASCADE, possession_id integer, event_index integer NOT NULL, period integer, minute integer, second integer, team_id integer, player_id integer, event_type text NOT NULL, location jsonb, outcome text, time_seconds double precision, raw jsonb NOT NULL);
CREATE TABLE IF NOT EXISTS possessions (id bigserial PRIMARY KEY, match_id bigint NOT NULL REFERENCES matches(id) ON DELETE CASCADE, possession_id integer NOT NULL, team_id integer, start_seconds double precision, end_seconds double precision, UNIQUE(match_id, possession_id));
CREATE TABLE IF NOT EXISTS sequences (id bigserial PRIMARY KEY, match_id bigint NOT NULL REFERENCES matches(id) ON DELETE CASCADE, possession_id integer NOT NULL, phase_index integer NOT NULL, tag text NOT NULL, tokens jsonb NOT NULL, embedding vector(256), UNIQUE(match_id, possession_id, phase_index));
CREATE TABLE IF NOT EXISTS freeze_frames (id bigserial PRIMARY KEY, event_id text NOT NULL REFERENCES events(id) ON DELETE CASCADE, frame jsonb NOT NULL);
CREATE INDEX IF NOT EXISTS events_match_order_idx ON events(match_id, period, event_index);
CREATE INDEX IF NOT EXISTS events_possession_idx ON events(match_id, possession_id);
CREATE INDEX IF NOT EXISTS possessions_match_idx ON possessions(match_id, possession_id);
CREATE INDEX IF NOT EXISTS sequences_tag_idx ON sequences(tag);
CREATE INDEX IF NOT EXISTS sequences_match_possession_idx ON sequences(match_id, possession_id, phase_index);
CREATE INDEX IF NOT EXISTS sequences_tokens_fts_idx ON sequences USING gin (to_tsvector('english', tag || ' ' || tokens::text));
CREATE INDEX IF NOT EXISTS sequences_embedding_hnsw ON sequences USING hnsw (embedding vector_cosine_ops) WITH (m=16, ef_construction=128) WHERE embedding IS NOT NULL;
CREATE INDEX IF NOT EXISTS matches_competition_idx ON matches(competition_id);
"""


def initialize(engine: Engine) -> None:
    with engine.begin() as conn:
        for statement in SCHEMA.split(";"):
            if statement.strip():
                conn.execute(text(statement))
