import argparse, os, random, time, traceback, yaml
from .db import DB
from .filters import matches
from .notify import export_csv, webhook
from .sources import web, linkedin, twitter


def load_env(path=".env"):
    """Load KEY=VALUE lines from a local, gitignored .env (never committed)."""
    if os.path.exists(path):
        for line in open(path):
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip("'\""))


def run(cfg_path="config.yaml", dry=False):
    cfg = yaml.safe_load(open(cfg_path))
    db = DB(cfg.get("db_path", "internbot.db"))
    src = cfg.get("sources", {})
    streams = [web.fetch(src)]
    if src.get("linkedin", {}).get("enabled"):
        streams.append(linkedin.fetch(src["linkedin"]))
    if src.get("twitter", {}).get("enabled"):
        streams.append(twitter.fetch(src["twitter"]))
    new = []
    for stream in streams:
        try:
            for p in stream:
                if matches(p, cfg["keywords"], cfg.get("exclude", []), cfg.get("locations", [])):
                    if dry or db.add_if_new(p):
                        new.append(p)
        except Exception as e:  # one broken source must not kill the run
            print(f"[source error] {type(e).__name__}: {e}")
    for p in new:
        print(f"[{p.source}] {p.title} | {p.company} | {p.location}\n    {p.url}")
    print(f"\n{len(new)} new matching postings")
    if not dry:
        export_csv(cfg.get("export_csv"), new)
        webhook(os.environ.get("INTERNBOT_WEBHOOK") or cfg.get("webhook_url"), new)


def main():
    ap = argparse.ArgumentParser(description="Research internship scraper")
    ap.add_argument("-c", "--config", default="config.yaml")
    ap.add_argument("--dry-run", action="store_true", help="don't save/export/notify")
    ap.add_argument("--watch", action="store_true", help="run forever, re-scraping on an interval")
    ap.add_argument("--interval", type=int, help="minutes between runs (default: config interval_minutes or 30)")
    a = ap.parse_args()
    load_env()
    if not a.watch:
        return run(a.config, a.dry_run)
    mins = a.interval or yaml.safe_load(open(a.config)).get("interval_minutes", 30)
    while True:
        try:
            run(a.config, a.dry_run)
        except Exception:
            traceback.print_exc()  # never die; try again next cycle
        wait = mins * 60 * random.uniform(0.85, 1.15)  # jitter
        print(f"-- sleeping {wait/60:.1f} min --", flush=True)
        time.sleep(wait)


if __name__ == "__main__":
    main()
