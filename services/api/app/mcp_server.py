"""MCP server exposing the same guarded read-only scout tools as the API graph."""
from mcp.server.fastmcp import FastMCP

from app.scout_tools import calculate_xt as calculate_xt_impl
from app.scout_tools import guarded_text_to_sql as guarded_text_to_sql_impl
from app.scout_tools import passing_network as passing_network_impl
from app.scout_tools import pitch_control_360 as pitch_control_360_impl
from app.scout_tools import search_sequences as search_sequences_impl
from app.scout_tools import set_piece_summary as set_piece_summary_impl

mcp = FastMCP("halfspace-scout")


@mcp.tool()
def guarded_text_to_sql(question: str, team: str | None = None) -> dict:
    """Answer an analytical question with validated read-only SQL and event/sequence evidence IDs."""
    return guarded_text_to_sql_impl(question, team)


@mcp.tool()
def search_sequences(query: str, limit: int = 10) -> dict:
    """Find tactically similar sequence records and return sequence evidence IDs."""
    return search_sequences_impl(query, limit)


@mcp.tool()
def calculate_xt(team: str | None = None, match_id: int | None = None) -> dict:
    """Calculate a heuristic expected-threat delta from pass/carry locations; citations are event IDs."""
    return calculate_xt_impl(team, match_id)


@mcp.tool()
def passing_network(team: str | None = None, match_id: int | None = None) -> dict:
    """Summarize completed pass edges and cite their supporting event IDs."""
    return passing_network_impl(team, match_id)


@mcp.tool()
def pitch_control_360(team: str | None = None, match_id: int | None = None) -> dict:
    """Estimate nearest-player pitch control by grid cell from available StatsBomb 360 frames."""
    return pitch_control_360_impl(match_id, team)


@mcp.tool()
def set_piece_summary(team: str | None = None, match_id: int | None = None) -> dict:
    """Summarize corner, free-kick, throw-in, and penalty events with event evidence IDs."""
    return set_piece_summary_impl(team, match_id)


if __name__ == "__main__":
    mcp.run()
