from app.segmentation import segment_possessions


def event(index, kind, minute=0, second=0, possession=1, **extra):
    return {"id": str(index), "index": index, "type": {"name": kind}, "minute": minute, "second": second, "possession": possession, **extra}


def test_counter_attack_advances_quickly():
    events = [event(1, "Ball Recovery", location=[30, 20]), event(2, "Pass", second=5, location=[70, 30])]
    result = segment_possessions(events)
    assert len(result) == 1
    assert result[0].tag == "counter-attack"


def test_restart_is_a_set_piece_phase():
    result = segment_possessions([event(1, "Pass"), event(2, "Corner", second=1), event(3, "Pass", second=2)])
    assert len(result) == 2
    assert result[1].tag == "set-piece"


def test_counterpress_recovery_has_press_win_tag():
    result = segment_possessions([event(1, "Ball Recovery", counterpress=True)])
    assert result[0].tag == "press-win-trigger"


def test_long_gap_starts_new_phase():
    result = segment_possessions([event(1, "Pass"), event(2, "Pass", second=11)])
    assert len(result) == 2


def test_progression_into_final_third_is_zone_entry():
    result = segment_possessions([
        event(1, "Pass", location=[70, 20]),
        event(2, "Carry", second=1, location=[90, 20]),
    ])
    assert result[0].tag == "zone-entry"
