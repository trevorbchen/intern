import sqlite3
from .models import Posting


class DB:
    def __init__(self, path):
        self.c = sqlite3.connect(path)
        self.c.execute("""CREATE TABLE IF NOT EXISTS postings(
            uid TEXT PRIMARY KEY, source TEXT, title TEXT, company TEXT, url TEXT,
            location TEXT, posted TEXT, first_seen TEXT DEFAULT CURRENT_TIMESTAMP)""")
        self.c.execute("""CREATE TABLE IF NOT EXISTS applications(
            uid TEXT PRIMARY KEY, title TEXT, company TEXT, url TEXT, source TEXT,
            status TEXT, note TEXT, applied_at TEXT DEFAULT CURRENT_TIMESTAMP)""")
        self.c.execute("""CREATE TABLE IF NOT EXISTS contacts(
            handle TEXT, tweet_url TEXT PRIMARY KEY, apply_url TEXT, text TEXT,
            messaged INTEGER DEFAULT 0, first_seen TEXT DEFAULT CURRENT_TIMESTAMP)""")

    def add_if_new(self, p: Posting) -> bool:
        cur = self.c.execute(
            "INSERT OR IGNORE INTO postings(uid,source,title,company,url,location,posted) VALUES(?,?,?,?,?,?,?)",
            (p.uid, p.source, p.title, p.company, p.url, p.location, p.posted))
        self.c.commit()
        return cur.rowcount == 1

    # ---- application log ----
    def already_applied(self, uid) -> bool:
        r = self.c.execute("SELECT status FROM applications WHERE uid=?", (uid,)).fetchone()
        return bool(r and r[0] == "submitted")

    def record_application(self, p: Posting, status: str, note: str = ""):
        """status: submitted | filled (dry run) | needs_manual | failed"""
        self.c.execute("""INSERT INTO applications(uid,title,company,url,source,status,note)
            VALUES(?,?,?,?,?,?,?) ON CONFLICT(uid) DO UPDATE SET status=excluded.status,
            note=excluded.note, applied_at=CURRENT_TIMESTAMP""",
            (p.uid, p.title, p.company, p.url, p.source, status, note))
        self.c.commit()

    def applications(self):
        return self.c.execute("SELECT applied_at,status,company,title,url,note FROM applications "
                              "ORDER BY applied_at DESC").fetchall()

    def add_contact(self, p: Posting):
        if p.handle:
            self.c.execute("INSERT OR IGNORE INTO contacts(handle,tweet_url,apply_url,text) VALUES(?,?,?,?)",
                           (p.handle, p.url, p.apply_url, p.description[:500]))
            self.c.commit()

    def contacts(self):
        return self.c.execute("SELECT first_seen,handle,apply_url,tweet_url,messaged FROM contacts "
                              "ORDER BY first_seen DESC").fetchall()
