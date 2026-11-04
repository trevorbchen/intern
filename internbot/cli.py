import argparse, os, random, time, traceback, yaml
from .db import DB
from .filters import matches, target_names, canon, too_old, is_program
from . import llm
from .notify import export_csv, webhook, ntfy, alert
from .sources import web, linkedin, twitter, extra
from . import apply as applier


def load_env(path=".env"):
    """Load KEY=VALUE lines from a local, gitignored .env (never committed)."""
    if os.path.exists(path):
        for line in open(path):
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip("'\""))


def export_applications(db, path="out/applications.csv"):
    import csv
    os.makedirs("out", exist_ok=True)
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["applied_at", "status", "company", "title", "url", "note"])
        w.writerows(db.applications())
    with open("out/contacts.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["first_seen", "handle", "apply_url", "tweet_url", "messaged"])
        w.writerows(db.contacts())


def health(db, name, raw):
    """Alert if a source silently returns nothing several runs in a row (site changed / blocked)."""
    key = f"zero:{name}"
    n = int(db.get(key, 0)) + 1 if raw == 0 else 0
    db.put(key, n)
    if n == 3:
        alert(f"source '{name}' returned nothing 3 runs in a row - it may be broken or blocked")


def run(cfg_path="config.yaml", dry=False, apply=False, submit=False, outreach_flag=False, only=None):
    cfg = yaml.safe_load(open(cfg_path))
    db = DB(cfg.get("db_path", "internbot.db"))
    src = cfg.get("sources", {})
    targets = None
    extra_pages = []
    streams = []  # (name, generator)
    want = lambda n: only is None or n in only
    if want("web"):
        if cfg.get("target_only") and os.path.exists(cfg.get("targets_file", "targets.yaml")):
            td = yaml.safe_load(open(cfg.get("targets_file", "targets.yaml")))
            targets = target_names(td["companies"])
            streams.append(("web", web.fetch_targets(td["companies"])))
            if td.get("careers_pages"):
                streams.append(("pages", extra.careers_pages(td["careers_pages"])))
        else:
            streams.append(("web", web.fetch(src)))
        if cfg.get("hn_hiring", True):
            streams.append(("hn", extra.hn_hiring()))
    if cfg.get("target_only") and targets is None and os.path.exists(cfg.get("targets_file", "targets.yaml")):
        targets = target_names(yaml.safe_load(open(cfg.get("targets_file", "targets.yaml")))["companies"])
    if want("linkedin") and src.get("linkedin", {}).get("enabled"):
        streams.append(("linkedin", linkedin.fetch(src["linkedin"])))
    if want("twitter") and src.get("twitter", {}).get("enabled"):
        streams.append(("twitter", twitter.fetch(src["twitter"])))
    new, seen_keys = [], set()
    max_age = cfg.get("max_age_days", 120)
    for sname, stream in streams:
        raw = 0
        try:
            for p in stream:
                raw += 1
                if not matches(p, cfg["keywords"], cfg.get("exclude", []), cfg.get("locations", []),
                               cfg.get("topics", []), cfg.get("exclude_companies", []), targets):
                    continue
                if p.source in ("linkedin", "twitter") and too_old(p, max_age):  # company boards only list live jobs
                    continue
                key = (canon(p.company), p.title.lower().strip())
                if key in seen_keys and p.source in ("linkedin", "twitter"):
                    continue  # same role already found (e.g. LinkedIn lists one per location)
                seen_keys.add(key)
                if dry or db.add_if_new(p):
                    new.append(p)
        except Exception as e:  # one broken source must not kill the run
            print(f"[source error] {sname}: {type(e).__name__}: {e}")
        health(db, sname, raw)
    for p in new:
        tag = " ** PROGRAM - apply by hand **" if is_program(p) else ""
        print(f"[{p.source}] {p.title} | {p.company} | {p.location}{tag}\n    {p.url}")
    print(f"\n{len(new)} new matching postings")
    for p in new:
        if not dry:
            db.add_contact(p)
    if outreach_flag and new:
        from . import outreach
        outreach.draft_all(new, db if not dry else None)
    if apply and not dry and new:
        if not os.path.exists("profile.yaml"):
            print("[apply] profile.yaml missing (copy profile.example.yaml)")
        else:
            prof = yaml.safe_load(open("profile.yaml"))
            applier.run_applications([p for p in new if not is_program(p)], prof, db, submit, prof.get("apply", {}).get("max_per_run", 5))
    if not dry:
        export_applications(db)
        try:
            from . import programs, ui
            if only is None:
                programs.check_all(db)
            print(f"[ui] dashboard: {ui.build(db)}")
        except Exception as e:
            print(f"[ui] skipped: {type(e).__name__}: {e}")
    if not dry:
        export_csv(cfg.get("export_csv"), new)
        webhook(os.environ.get("INTERNBOT_WEBHOOK") or cfg.get("webhook_url"), new)
        ntfy(new)


def main():
    ap = argparse.ArgumentParser(description="Research internship scraper")
    ap.add_argument("-c", "--config", default="config.yaml")
    ap.add_argument("--dry-run", action="store_true", help="don't save/export/notify")
    ap.add_argument("--apply", action="store_true", help="auto-fill Greenhouse/Lever forms for new postings (no submit)")
    ap.add_argument("--submit", action="store_true", help="with --apply: actually submit applications")
    ap.add_argument("--outreach", action="store_true", help="draft personalised cold emails/DMs for new postings (never sends)")
    ap.add_argument("--status", nargs="+", metavar=("COMPANY", "STATUS"), help="update an application: --status Cohere interview [note...]  (replied|interview|rejected|offer)")
    ap.add_argument("--programs", action="store_true", help="check fellowship/residency pages (programs.yaml) and rebuild the dashboard")
    ap.add_argument("--researchers", action="store_true", help="find researchers at target companies similar to you (needs OPENALEX_API_KEY)")
    ap.add_argument("--draft", action="store_true", help="with --researchers: draft an email to each (needs ANTHROPIC_API_KEY)")
    ap.add_argument("--ui", action="store_true", help="rebuild out/dashboard.html + deadlines.ics and exit")
    ap.add_argument("--applied", action="store_true", help="print the running list of applications and exit")
    ap.add_argument("--contacts", action="store_true", help="print Twitter handles collected and exit")
    ap.add_argument("--harvest", action="store_true", help="read-only crawl of application forms to collect questions into answers.yaml")
    ap.add_argument("--per-board", type=int, default=4, help="forms to read per company when harvesting")
    ap.add_argument("--answer", action="store_true", help="interactively answer the collected questions (saved permanently)")
    ap.add_argument("--watch", action="store_true", help="the full continuous loop: scrape, programs, researchers, outreach, dashboard, alerts")
    ap.add_argument("--once", action="store_true", help="with --watch: run every due task once, then exit")
    ap.add_argument("--force", action="store_true", help="with --watch: run every task now regardless of schedule")
    a = ap.parse_args()
    load_env()
    if a.programs or a.ui or a.researchers:
        from . import programs, ui, researchers, llm
        cfg = yaml.safe_load(open(a.config))
        db = DB(cfg.get("db_path", "internbot.db"))
        if a.programs:
            programs.check_all(db)
        if a.researchers:
            prof = yaml.safe_load(open("profile.yaml")) if os.path.exists("profile.yaml") else {}
            res = llm.resume_text(prof.get("resume", ""))
            tl = yaml.safe_load(open(cfg.get("targets_file", "targets.yaml")))["companies"]
            try:
                found = researchers.find_researchers(tl, prof, res, db=db)
            except researchers.OpenAlexError as e:
                return print(f"[researchers] {e}")
            if a.draft:
                for r in found[:25]:
                    db.set_draft(r["author_id"], llm.draft_researcher_outreach(r["name"], r["company"], r["papers"], prof, res)
                                 if llm.enabled() else llm.template_researcher(r["name"], r["company"], r["papers"], prof))
            print(f"[researchers] {len(found)} researchers saved")
        print(f"[ui] {ui.build(db)}")
        return
    if a.status:
        db = DB(yaml.safe_load(open(a.config)).get("db_path", "internbot.db"))
        n = db.set_status(a.status[0], a.status[1] if len(a.status) > 1 else "replied", " ".join(a.status[2:]))
        export_applications(db)
        return print(f"updated {n} application(s)")
    if a.harvest:
        from . import harvest as H
        full = yaml.safe_load(open(a.config))
        H.harvest(full.get("harvest") or full["sources"], a.per_board)
        if os.path.exists("profile.yaml"):
            print(f"prefilled {H.prefill_from_profile(yaml.safe_load(open('profile.yaml')))} from profile answers")
        return
    if a.answer:
        from . import harvest as H
        return H.interactive()
    if a.applied or a.contacts:
        db = DB(yaml.safe_load(open(a.config)).get("db_path", "internbot.db"))
        if a.applied:
            for r in db.applications():
                print(" | ".join(str(x) for x in r))
            print(f"{len(db.applications())} applications")
        else:
            for r in db.contacts():
                print(" | ".join(str(x) for x in r))
        return
    if not a.watch:
        return run(a.config, a.dry_run, a.apply, a.submit, a.outreach)
    from . import loop
    loop.watch(a.config, once=a.once, force=a.force, dry=a.dry_run)


if __name__ == "__main__":
    main()
