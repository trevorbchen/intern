import argparse, os, random, time, traceback, yaml
from .db import DB
from .filters import matches, target_names, canon, too_old
from . import llm
from .notify import export_csv, webhook
from .sources import web, linkedin, twitter
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


def run(cfg_path="config.yaml", dry=False, apply=False, submit=False, outreach_flag=False):
    cfg = yaml.safe_load(open(cfg_path))
    db = DB(cfg.get("db_path", "internbot.db"))
    src = cfg.get("sources", {})
    targets = None
    if cfg.get("target_only") and os.path.exists(cfg.get("targets_file", "targets.yaml")):
        tl = yaml.safe_load(open(cfg.get("targets_file", "targets.yaml")))["companies"]
        targets = target_names(tl)
        streams = [web.fetch_targets(tl)]
    else:
        streams = [web.fetch(src)]
    if src.get("linkedin", {}).get("enabled"):
        streams.append(linkedin.fetch(src["linkedin"]))
    if src.get("twitter", {}).get("enabled"):
        streams.append(twitter.fetch(src["twitter"]))
    new, seen_keys = [], set()
    for stream in streams:
        try:
            for p in stream:
                if matches(p, cfg["keywords"], cfg.get("exclude", []), cfg.get("locations", []),
                           cfg.get("topics", []), cfg.get("exclude_companies", []), targets):
                    key = (canon(p.company), p.title.lower().strip())
                if key in seen_keys and p.source in ("linkedin", "twitter"):
                    continue  # same role already found (e.g. LinkedIn lists one per location)
                seen_keys.add(key)
                if dry or db.add_if_new(p):
                        new.append(p)
        except Exception as e:  # one broken source must not kill the run
            print(f"[source error] {type(e).__name__}: {e}")
    for p in new:
        tag = f" ({p.score}: {p.reason})" if p.score >= 0 else ""
        print(f"[{p.source}] {p.title} | {p.company} | {p.location}{tag}\n    {p.url}")
    print(f"\n{len(new)} new matching postings")
    new = [p for p in new if not too_old(p, cfg.get("max_age_days", 120))]
    if new and llm.enabled() and cfg.get("score_with_llm", True) and os.path.exists("profile.yaml"):
        prof = yaml.safe_load(open("profile.yaml"))
        res = llm.resume_text(prof.get("resume", ""))
        for p in new:
            p.score, p.reason = llm.score_posting(p, prof, res)
        floor = cfg.get("min_score", 60)
        skipped = [p for p in new if 0 <= p.score < floor]
        new = sorted([p for p in new if p.score < 0 or p.score >= floor], key=lambda p: -p.score)
        if skipped:
            print(f"[score] {len(skipped)} postings below {floor} skipped")
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
            applier.run_applications(new, prof, db, submit, prof.get("apply", {}).get("max_per_run", 5))
    if not dry:
        export_applications(db)
    if not dry:
        export_csv(cfg.get("export_csv"), new)
        webhook(os.environ.get("INTERNBOT_WEBHOOK") or cfg.get("webhook_url"), new)


def main():
    ap = argparse.ArgumentParser(description="Research internship scraper")
    ap.add_argument("-c", "--config", default="config.yaml")
    ap.add_argument("--dry-run", action="store_true", help="don't save/export/notify")
    ap.add_argument("--apply", action="store_true", help="auto-fill Greenhouse/Lever forms for new postings (no submit)")
    ap.add_argument("--submit", action="store_true", help="with --apply: actually submit applications")
    ap.add_argument("--outreach", action="store_true", help="draft personalised cold emails/DMs for new postings (never sends)")
    ap.add_argument("--status", nargs="+", metavar=("COMPANY", "STATUS"), help="update an application: --status Cohere interview [note...]  (replied|interview|rejected|offer)")
    ap.add_argument("--applied", action="store_true", help="print the running list of applications and exit")
    ap.add_argument("--contacts", action="store_true", help="print Twitter handles collected and exit")
    ap.add_argument("--harvest", action="store_true", help="read-only crawl of application forms to collect questions into answers.yaml")
    ap.add_argument("--per-board", type=int, default=4, help="forms to read per company when harvesting")
    ap.add_argument("--answer", action="store_true", help="interactively answer the collected questions (saved permanently)")
    ap.add_argument("--watch", action="store_true", help="run forever, re-scraping on an interval")
    ap.add_argument("--interval", type=int, help="minutes between runs (default: config interval_minutes or 30)")
    a = ap.parse_args()
    load_env()
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
    mins = a.interval or yaml.safe_load(open(a.config)).get("interval_minutes", 30)
    while True:
        try:
            run(a.config, a.dry_run, a.apply, a.submit, a.outreach)
        except Exception:
            traceback.print_exc()  # never die; try again next cycle
        wait = mins * 60 * random.uniform(0.85, 1.15)  # jitter
        print(f"-- sleeping {wait/60:.1f} min --", flush=True)
        time.sleep(wait)


if __name__ == "__main__":
    main()
