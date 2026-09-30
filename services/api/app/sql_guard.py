"""Conservative SQLGlot validation for read-only, evidence-bearing SQL."""
from __future__ import annotations

from sqlglot import exp, parse
from sqlglot.errors import ParseError

from app.settings import settings

ALLOWED_TABLES = {"events", "possessions", "sequences", "matches", "teams", "players", "competitions", "freeze_frames"}
FORBIDDEN_FUNCTIONS = {
    "PG_SLEEP", "PG_READ_FILE", "PG_READ_BINARY_FILE", "PG_LS_DIR", "PG_STAT_FILE",
    "NEXTVAL", "SETVAL", "SET_CONFIG", "DBLINK", "LO_IMPORT", "LO_EXPORT",
    "PG_ADVISORY_LOCK", "PG_ADVISORY_XACT_LOCK", "PG_TERMINATE_BACKEND", "PG_CANCEL_BACKEND",
}
SAFE_FUNCTIONS = {"COUNT", "SUM", "AVG", "MIN", "MAX", "COALESCE", "NULLIF", "LOWER", "UPPER", "DATE_TRUNC", "DATE_PART", "ROUND", "ABS", "PERCENTILE_CONT", "FLOOR", "CEIL", "GREATEST", "LEAST", "EXTRACT"}


class SQLGuardError(ValueError):
    pass


def validate_readonly_sql(sql: str, max_rows: int | None = None) -> str:
    """Return one capped PostgreSQL SELECT or reject it before database access."""
    cap = max_rows or settings.scout_max_rows
    if not sql or len(sql) > 20_000:
        raise SQLGuardError("SQL is empty or exceeds 20,000 characters")
    try:
        statements = [statement for statement in parse(sql, read="postgres") if statement is not None]
    except ParseError as exc:
        raise SQLGuardError("SQL could not be parsed") from exc
    if len(statements) != 1:
        raise SQLGuardError("Exactly one SQL statement is allowed")
    query = statements[0]
    if not isinstance(query, (exp.Select, exp.Subquery)) or (isinstance(query, exp.Subquery) and not isinstance(query.this, exp.Select)):
        raise SQLGuardError("Only SELECT queries are allowed")
    nodes = list(query.walk())
    if len(nodes) > 1500 or sum(isinstance(node, exp.Select) for node in nodes) > 8 or sum(isinstance(node, exp.Join) for node in nodes) > 20:
        raise SQLGuardError("Query is too complex")
    if any(isinstance(node, (exp.Insert, exp.Update, exp.Delete, exp.Create, exp.Drop, exp.Alter, exp.Command, exp.Transaction, exp.Into)) for node in nodes):
        raise SQLGuardError("Mutating and transaction statements are forbidden")
    selects = [node for node in nodes if isinstance(node, exp.Select)]
    if any(node.args.get("locks") or node.args.get("into") or node.args.get("offset") for node in selects):
        raise SQLGuardError("SELECT locking, SELECT INTO, and OFFSET are forbidden")

    tables = list(query.find_all(exp.Table))
    if not tables:
        raise SQLGuardError("Queries must read an allowlisted football data table")
    for table in tables:
        if table.name.lower() not in ALLOWED_TABLES:
            raise SQLGuardError(f"Table is not allowlisted: {table.name}")
        if table.db and table.db.lower() != "public":
            raise SQLGuardError("Only public schema tables are allowed")

    for function in query.find_all(exp.Func):
        name = (function.name or function.sql_name()).upper()
        if name in FORBIDDEN_FUNCTIONS:
            raise SQLGuardError(f"Function is forbidden: {name}")
        if name not in SAFE_FUNCTIONS:
            raise SQLGuardError(f"Function is not allowlisted: {name}")

    # Require a projected source identifier so the answer can cite persisted evidence.
    event_aliases = {table.alias_or_name.lower() for table in tables if table.name.lower() == "events"}
    sequence_aliases = {table.alias_or_name.lower() for table in tables if table.name.lower() == "sequences"}
    aliases: set[str] = set()
    for projection in query.expressions:
        if isinstance(projection, exp.Star):
            continue
        alias = projection.alias_or_name.lower()
        if alias not in {"event_id", "event_ids", "sequence_id", "sequence_ids"}:
            continue
        value = projection.this if isinstance(projection, exp.Alias) else projection
        columns = [column for column in value.find_all(exp.Column) if column.name.lower() == "id"]
        sources = event_aliases if alias.startswith("event") else sequence_aliases
        if any((column.table.lower() in sources) or (not column.table and len(sources) == 1 and len(tables) == 1) for column in columns):
            aliases.add(alias)
    if not aliases:
        raise SQLGuardError("Project e.id AS event_id or s.id AS sequence_id (or an array of those IDs)")

    existing = query.args.get("limit")
    if existing is None:
        query = query.limit(cap)
    else:
        try:
            requested = int(existing.expression.this)
        except (AttributeError, TypeError, ValueError):
            raise SQLGuardError("LIMIT must be an integer literal")
        if requested < 1:
            raise SQLGuardError("LIMIT must be positive")
        if requested > cap:
            query = query.limit(cap)
    return query.sql(dialect="postgres", pretty=False)
