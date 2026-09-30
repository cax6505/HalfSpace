import pytest

from app.sql_guard import SQLGuardError, validate_readonly_sql


def test_safe_select_requires_evidence_id_and_is_capped():
    query = validate_readonly_sql("SELECT e.id AS event_id, e.event_type FROM events e LIMIT 900", max_rows=50)
    assert "LIMIT 50" in query
    assert "event_id" in query


@pytest.mark.parametrize("sql", [
    "SELECT e.id AS event_id FROM events e; DROP TABLE sequences",
    "DELETE FROM events RETURNING id AS event_id",
    "UPDATE events SET event_type='x' RETURNING id AS event_id",
    "SELECT * INTO copied_events FROM events",
    "SELECT e.id AS event_id FROM events e OFFSET 500000",
    "SELECT e.id AS event_id FROM events e FOR UPDATE",
    "SELECT e.id AS event_id FROM events e JOIN secret_users u ON true",
    "SELECT pg_sleep(20), e.id AS event_id FROM events e",
    "SELECT pg_read_file('/etc/passwd') AS event_id FROM events",
    "SELECT set_config('search_path','public',false), e.id AS event_id FROM events e",
    "SELECT count(*) AS n FROM events",
    "SELECT 1 AS event_id",
])
def test_injection_and_unsafe_or_ungrounded_queries_are_rejected(sql):
    with pytest.raises(SQLGuardError):
        validate_readonly_sql(sql)


@pytest.mark.parametrize("sql", [
    "SELECT e.id AS event_id FROM events e LIMIT -1",
    "SELECT e.id AS event_id FROM events e LIMIT 1.5",
    "SELECT e.id AS event_id FROM events e LIMIT ALL",
])
def test_limit_must_be_a_positive_integer_literal(sql):
    with pytest.raises(SQLGuardError):
        validate_readonly_sql(sql)
