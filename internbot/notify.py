import csv, os
import requests


def export_csv(path, rows):
    if not path or not rows:
        return
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    new = not os.path.exists(path)
    with open(path, "a", newline="") as f:
        w = csv.writer(f)
        if new:
            w.writerow(["source", "title", "company", "location", "posted", "url"])
        for p in rows:
            w.writerow([p.source, p.title, p.company, p.location, p.posted, p.url])


def webhook(url, rows):
    if not url or not rows:
        return
    lines = [f"• [{p.source}] {p.title} — {p.company} {p.location}\n  {p.url}" for p in rows[:20]]
    text = f"{len(rows)} new research internships:\n" + "\n".join(lines)
    requests.post(url, json={"text": text, "content": text[:1900]}, timeout=15)


def ntfy(rows, topic=None, title="New research internships"):
    """Free push notifications to your phone via ntfy.sh (install the app, subscribe to your topic)."""
    topic = topic or os.environ.get("NTFY_TOPIC")
    if not topic or not rows:
        return
    from .filters import is_program
    body = "\n".join(f"{'* ' if is_program(p) else ''}{p.company}: {p.title}" for p in rows[:15])
    top = rows[0].url if rows else ""
    try:
        requests.post(f"https://ntfy.sh/{topic}", data=body.encode(), timeout=15,
                      headers={"Title": f"{len(rows)} {title}", "Click": top,
                               "Priority": "high" if any(is_program(p) for p in rows) else "default"})
    except Exception as e:
        print(f"[ntfy] failed: {type(e).__name__}")


def alert(message, topic=None):
    topic = topic or os.environ.get("NTFY_TOPIC")
    if topic:
        try:
            requests.post(f"https://ntfy.sh/{topic}", data=message.encode(), timeout=15, headers={"Title": "internbot"})
        except Exception:
            pass
    print(f"[alert] {message}")
