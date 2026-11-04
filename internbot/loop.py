"""The continuous loop: runs each task on its own schedule, forever (or once with once=True)."""
import os, time, traceback, yaml
from datetime import datetime
from .db import DB
from . import cli, programs, researchers, llm, ui
from .notify import alert, ntfy


def _due(db, name, minutes, force):
    last = db.get(f"last:{name}")
    if force or not last:
        return True
    return (datetime.now() - datetime.fromisoformat(last)).total_seconds() >= minutes * 60


def _twitter_ready(cfg):
    return cfg["sources"].get("twitter", {}).get("enabled") and (
        os.environ.get("X_AUTH_TOKEN") or os.environ.get("X_USERNAME") or os.path.exists(".x_session.json"))


def watch(cfg_path="config.yaml", once=False, force=False, dry=False):
    while True:
        cfg = yaml.safe_load(open(cfg_path))
        db = DB(cfg.get("db_path", "internbot.db"))
        lp = cfg.get("loop", {})
        outreach = lp.get("outreach", True)

        def scrape():
            cli.run(cfg_path, dry, apply=lp.get("apply", False), outreach_flag=outreach, only={"web", "linkedin"})

        def twitter():
            if _twitter_ready(cfg):
                cli.run(cfg_path, dry, outreach_flag=outreach, only={"twitter"})

        def progs():
            for name in programs.check_all(db):
                alert(f"fellowship page changed: {name}")

        def researchers_task():
            prof = yaml.safe_load(open("profile.yaml")) if os.path.exists("profile.yaml") else {}
            tl = yaml.safe_load(open(cfg.get("targets_file", "targets.yaml")))["companies"]
            res = llm.resume_text(prof.get("resume", ""))
            try:
                found = researchers.find_researchers(tl, prof, res, db=db)
            except researchers.OpenAlexError as e:
                return print(f"[researchers] {e}")
            for r in db.researchers():
                if not r[6]:  # no draft yet
                    papers = __import__("json").loads(r[4])
                    d = (llm.draft_researcher_outreach(r[1], r[2], papers, prof, res) if llm.enabled()
                         else llm.template_researcher(r[1], r[2], papers, prof))
                    db.set_draft(r[0], d)
            if found:
                alert(f"{len(found)} new similar researchers found - see dashboard")

        tasks = [("scrape", lp.get("scrape_minutes", 30), scrape), ("twitter", lp.get("twitter_minutes", 120), twitter),
                 ("programs", lp.get("programs_minutes", 360), progs),
                 ("researchers", lp.get("researchers_minutes", 1440), researchers_task)]
        for name, mins, fn in tasks:
            if _due(db, name, mins, force):
                print(f"\n=== {datetime.now():%Y-%m-%d %H:%M} task: {name} ===", flush=True)
                try:
                    fn()
                except Exception:
                    traceback.print_exc()  # never die; retry next cycle
                db.put(f"last:{name}", datetime.now().isoformat())
        try:
            ui.build(db)
        except Exception:
            traceback.print_exc()
        if once:
            return
        time.sleep(60)
