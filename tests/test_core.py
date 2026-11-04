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
