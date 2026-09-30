from app.agent_graph import verifier_node


def test_verifier_keeps_cited_numbers_and_drops_unsupported_claims():
    state = {
        "team": "Arsenal",
        "query": "scout Arsenal",
        "evidence": [{"evidence_id": "event:evt-1", "kind": "event", "tool": "guarded_text_to_sql", "facts": {"count": 3}}],
        "dossier": {
            "overview": {"statement": "Three completed sequences were found.", "evidence_ids": ["event:evt-1"], "checks": [{"metric": "count", "value": 3}]},
            "claims": [
                {"statement": "The total was 3 sequences.", "evidence_ids": ["event:evt-1"], "checks": []},
                {"statement": "The total was 4 sequences.", "evidence_ids": ["event:evt-1"], "checks": []},
                {"statement": "The team scored 2 goals.", "evidence_ids": ["event:missing"], "checks": []},
            ],
        },
    }
    result = verifier_node(state)["dossier"]
    assert result["overview"] is not None
    assert len(result["claims"]) == 1
    assert len(result["dropped_claims"]) == 2
    assert result["verification"] == {"submitted_claims": 4, "supported_claims": 2, "dropped_claims": 2}
