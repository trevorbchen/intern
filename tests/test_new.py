import json, types
from internbot.db import DB
from internbot import programs, researchers, ui
from internbot.models import Posting
from internbot.filters import is_program, matches


def test_program_detection():
    assert is_program(Posting("x", "Anthropic Fellows Program, AI Safety", "Anthropic", "u"))
    assert not is_program(Posting("x", "Research Intern", "Cohere", "u"))
    assert matches(Posting("x", "AI Safety Fellow", "Anthropic", "u", "", "AI research"), ["fellow"], [], [], ["AI"])


def test_researcher_ranking():
    inst = "I1"
    work = lambda title, topics, names: {"title": title, "publication_year": 2026, "doi": "d", "id": "w",
        "topics": [{"display_name": t} for t in topics], "keywords": [],
        "authorships": [{"author": {"id": f"https://openalex.org/A{n}", "display_name": n},
                         "institutions": [{"id": "https://openalex.org/I1"}]} for n in names]}
    works = [work("Reinforcement learning for agents", ["Reinforcement Learning"], ["Ada", "Bob"]),
             work("Protein folding", ["Biology"], ["Cy"]),
             work("Interpretability of RL policies", ["Interpretability"], ["Ada"])]
    r = researchers.rank_authors(works, inst, ["reinforcement learning", "interpretability"])
    assert r[0]["name"] == "Ada" and len(r[0]["papers"]) == 2 and all(x["name"] != "Cy" for x in r)


def test_dashboard(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    db = DB(":memory:")
    db.upsert_program("MATS", "https://m", "open", "2027-03-01", "h")
    db.add_if_new(Posting("ashby", "AI Fellow", "X", "https://x/1"))
    path = ui.build(db)
    html = open(path).read()
    assert "MATS" in html and "AI Fellow" in html and "2027-03-01" in html
    assert "DTSTART;VALUE=DATE:20270301" in open(tmp_path / "out/deadlines.ics").read()


def test_program_change_detect():
    db = DB(":memory:")
    assert not db.upsert_program("P", "u", "open", None, "a")
    assert db.upsert_program("P", "u", "open", None, "b")
