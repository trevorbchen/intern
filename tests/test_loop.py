"""Scheduler, health alerts, notifications, programs and researcher batching."""
import json, yaml
import pytest
from internbot import loop, cli, notify, programs, researchers
from internbot.db import DB
from internbot.models import Posting


def cfg_file(tmp_path, **extra):
    cfg = {"keywords": ["research intern", "ml intern"], "topics": ["LLM"], "db_path": str(tmp_path / "t.db"),
           "export_csv": str(tmp_path / "out/n.csv"), "sources": {"linkedin": {"enabled": False}}, "target_only": False,
           "hn_hiring": False, "targets_file": "none.yaml", **extra}
    p = tmp_path / "c.yaml"
    p.write_text(yaml.safe_dump(cfg))
    return str(p)


def test_loop_runs_due_tasks_once_and_respects_schedule(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    calls = []
    monkeypatch.setattr(cli, "run", lambda *a, **k: calls.append(("run", k.get("only"))))
    monkeypatch.setattr(loop.programs, "check_all", lambda db: calls.append("programs") or [])
    monkeypatch.setattr(loop.researchers, "find_researchers", lambda *a, **k: calls.append("researchers") or [])
    (tmp_path / "targets.yaml").write_text(yaml.safe_dump({"companies": []}))
    path = cfg_file(tmp_path, targets_file=str(tmp_path / "targets.yaml"))
    loop.watch(path, once=True)
    assert ("run", {"web", "linkedin"}) in calls and "programs" in calls and "researchers" in calls
    assert not any(c == ("run", {"twitter"}) for c in calls)  # twitter not enabled/ready -> skipped
    calls.clear()
    loop.watch(path, once=True)  # nothing is due a second later
    assert calls == []
    loop.watch(path, once=True, force=True)  # --force runs everything
    assert "programs" in calls


def test_loop_survives_task_crash(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(cli, "run", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom")))
    monkeypatch.setattr(loop.programs, "check_all", lambda db: [])
    monkeypatch.setattr(loop.researchers, "find_researchers", lambda *a, **k: [])
    (tmp_path / "targets.yaml").write_text(yaml.safe_dump({"companies": []}))
    loop.watch(cfg_file(tmp_path, targets_file=str(tmp_path / "targets.yaml")), once=True)  # must not raise
    assert (tmp_path / "out/dashboard.html").exists()


def test_health_alert_after_three_empty_runs(monkeypatch):
    db = DB(":memory:")
    msgs = []
    monkeypatch.setattr(cli, "alert", lambda m: msgs.append(m))
    for _ in range(2):
        cli.health(db, "linkedin", 0)
    assert msgs == []
    cli.health(db, "linkedin", 0)
    assert len(msgs) == 1 and "linkedin" in msgs[0]
    cli.health(db, "linkedin", 5)  # recovers
    cli.health(db, "linkedin", 0)
    assert len(msgs) == 1


def test_ntfy_and_webhook_payloads(monkeypatch):
    sent = []
    monkeypatch.setattr(notify.requests, "post", lambda url, **kw: sent.append((url, kw)))
    rows = [Posting("ashby", "AI Fellowship", "Co", "https://x/1"), Posting("ashby", "ML Intern", "Co2", "https://x/2")]
    notify.ntfy(rows, topic="mytopic")
    url, kw = sent[0]
    assert url == "https://ntfy.sh/mytopic" and kw["headers"]["Priority"] == "high" and b"Co: AI Fellowship" in kw["data"]
    notify.ntfy([], topic="mytopic")
    assert len(sent) == 1  # nothing to send
    notify.webhook("http://hook", rows)
    assert "2 new research internships" in sent[1][1]["json"]["text"]


def test_csv_export_appends(tmp_path):
    path = str(tmp_path / "o/x.csv")
    notify.export_csv(path, [Posting("a", "T1", "C", "u1")])
    notify.export_csv(path, [Posting("a", "T2", "C", "u2")])
    lines = open(path).read().strip().splitlines()
    assert len(lines) == 3 and lines[0].startswith("source,title")


def test_program_check_detects_status_deadline_and_change(tmp_path, monkeypatch):
    prog = tmp_path / "p.yaml"
    prog.write_text(yaml.safe_dump([{"name": "Prog", "url": "https://p/1"}, {"name": "Manual", "url": "https://m", "auto_check": False,
                                      "deadline": "2027-01-05"}]))
    page = {"html": "<p>Applications are now open. Deadline: January 15, 2027</p>"}
    monkeypatch.setattr(programs, "get", lambda u, **k: type("R", (), {"text": page["html"]})())
    db = DB(":memory:")
    assert programs.check_all(db, str(prog)) == []  # first sight: no "change"
    rows = {r[0]: r for r in db.program_rows()}
    assert rows["Prog"][2] == "open" and rows["Prog"][3] == "2027-01-15" and rows["Manual"][3] == "2027-01-05"
    page["html"] = "<p>Applications have closed.</p>"
    assert programs.check_all(db, str(prog)) == ["Prog"]
    assert {r[0]: r for r in db.program_rows()}["Prog"][2] == "closed"


def test_program_fetch_error_is_recorded_not_raised(tmp_path, monkeypatch):
    prog = tmp_path / "p.yaml"
    prog.write_text(yaml.safe_dump([{"name": "P", "url": "https://p"}]))
    monkeypatch.setattr(programs, "get", lambda u, **k: (_ for _ in ()).throw(ConnectionError("x")))
    db = DB(":memory:")
    programs.check_all(db, str(prog))
    assert db.program_rows()[0][2].startswith("error")


def test_researcher_batches_rotate_without_key(monkeypatch):
    monkeypatch.delenv("OPENALEX_API_KEY", raising=False)
    scanned = []
    monkeypatch.setattr(researchers, "find_institution", lambda n: scanned.append(n) or None)
    db = DB(":memory:")
    targets = [{"name": f"C{i}"} for i in range(14)]
    prof = {"interests": ["rl"]}
    researchers.find_researchers(targets, prof, db=db)
    first = list(scanned)
    scanned.clear()
    researchers.find_researchers(targets, prof, db=db)
    assert len(first) == 6 and len(scanned) == 6 and not set(first) & set(scanned)  # next batch is different companies


def test_researchers_without_interests_skips(monkeypatch):
    monkeypatch.setattr(researchers, "find_institution", lambda n: pytest.fail("should not query"))
    assert researchers.find_researchers([{"name": "X"}], {}) == []


def test_openalex_rate_limit_message(monkeypatch):
    monkeypatch.setattr(researchers.requests, "get", lambda *a, **k: type("R", (), {"status_code": 429})())
    monkeypatch.setattr(researchers.time, "sleep", lambda s: None)
    with pytest.raises(researchers.OpenAlexError):
        researchers._get("institutions", search="x")


def test_template_drafts_work_without_llm():
    from internbot import llm
    d = llm.template_researcher("Ada Lovelace", "Co", [{"title": "Cool RL paper"}], {"first_name": "Sam", "background": "I'm a CS student. More."})
    assert d.startswith("SUBJECT:") and "Hi Ada" in d and "Cool RL paper" in d and "Sam" in d
    p = Posting("x", "Research Intern", "Co", "u")
    out = llm.template_posting(p, {"first_name": "Sam", "last_name": "Lee", "background": "i study CS. More text"})
    assert "Research Intern" in out and "I study CS." in out and "Sam Lee" in out and ". a " not in out
