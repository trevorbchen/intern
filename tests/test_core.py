from internbot.models import Posting
from internbot.filters import matches
from internbot.db import DB

KW = ["research intern", "REU"]
EX = ["senior"]


def P(title, desc="", loc=""):
    return Posting("x", title, "co", "https://a.com/j/1?utm=1", loc, desc)


def test_match():
    assert matches(P("ML Research Intern"), KW, EX, [])
    assert not matches(P("Senior Research Intern"), KW, EX, [])
    assert not matches(P("Software Engineer"), KW, EX, [])
    assert not matches(P("Research Intern", loc="Paris"), KW, EX, ["Remote"])


def test_dedupe():
    db = DB(":memory:")
    assert db.add_if_new(P("a"))
    assert not db.add_if_new(P("a"))


def test_ai_startup_focus():
    tp, ex_c = ["machine learning", "LLM"], ["google"]
    ai = Posting("x", "Research Intern", "TinyAI", "https://a.com/2", "", "Work on LLM training")
    assert matches(ai, KW, EX, [], tp, ex_c)
    assert not matches(Posting("x", "Research Intern", "TinyAI", "https://a.com/3", "", "Equity research"), KW, EX, [], tp, ex_c)
    assert not matches(Posting("x", "Research Intern", "Google", "https://a.com/4", "", "LLM"), KW, EX, [], tp, ex_c)


def test_target_filter():
    from internbot.filters import target_names, is_target
    names = target_names([{"name": "Scale AI"}, {"name": "Cursor (Anysphere)"}, {"name": "Thinking Machines Lab"}])
    assert is_target("Scale", names) and is_target("Anysphere", names) and is_target("Thinking Machines", names)
    assert not is_target("Random Startup Inc", names)


def test_too_old():
    from internbot.filters import too_old
    assert too_old(P("a") if False else Posting("x", "a", "c", "u", posted="2020-01-01"), 120)
    assert not too_old(Posting("x", "a", "c", "u", posted=""), 120)
    assert not too_old(Posting("x", "a", "c", "u", posted="2999-01-01T00:00:00Z"), 120)


def test_status():
    db = DB(":memory:")
    p = P("a")
    db.record_application(p, "submitted")
    assert db.set_status("co", "interview") == 1
    assert db.applications()[0][1] == "interview"
