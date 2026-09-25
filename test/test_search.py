from rosgraph_tui.search import fuzzy_filter

NAMES = sorted(["/chatter", "/camera/image_raw", "/camera/image_rect", "/rosout", "/planning/trajectory"])


def test_empty_query_returns_everything_in_order():
    assert fuzzy_filter(NAMES, "") == NAMES


def test_exact_substring_scores_first():
    result = fuzzy_filter(NAMES, "chat")
    assert result[0] == "/chatter"


def test_cutoff_excludes_bad_matches():
    assert "/rosout" not in fuzzy_filter(NAMES, "image")
    assert set(fuzzy_filter(NAMES, "image")) >= {"/camera/image_raw", "/camera/image_rect"}


def test_ties_are_broken_by_name():
    result = fuzzy_filter(NAMES, "camera/image")
    assert result[:2] == ["/camera/image_raw", "/camera/image_rect"]


def test_case_insensitive():
    assert fuzzy_filter(NAMES, "CHATTER")[0] == "/chatter"


def test_cutoff_is_exclusive():
    from rosgraph_tui.search import fuzzy_rank

    # partial_ratio("chat", "/parameter_events") is exactly 50 -> excluded
    assert fuzzy_rank(["/parameter_events"], "chat") == []
    assert fuzzy_rank(["/chatter"], "chat") == [("/chatter", 100.0)]
