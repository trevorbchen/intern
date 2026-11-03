import argparse, os, yaml
from .db import DB
from .filters import matches
from .notify import export_csv, webhook
from .sources import web, linkedin, twitter


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
        for p in stream:
            if matches(p, cfg["keywords"], cfg.get("exclude", []), cfg.get("locations", [])):
                if dry or db.add_if_new(p):
                    new.append(p)
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
    a = ap.parse_args()
    run(a.config, a.dry_run)


if __name__ == "__main__":
    main()
