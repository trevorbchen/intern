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
        self.c.execute("""CREATE TABLE IF NOT EXISTS programs(
            name TEXT PRIMARY KEY, url TEXT, status TEXT, deadline TEXT, text_hash TEXT,
            changed INTEGER DEFAULT 0, last_checked TEXT)""")
        self.c.execute("""CREATE TABLE IF NOT EXISTS researchers(
            author_id TEXT PRIMARY KEY, name TEXT, company TEXT, score REAL, papers TEXT, url TEXT,
            draft TEXT DEFAULT '', contacted INTEGER DEFAULT 0, found_at TEXT DEFAULT CURRENT_TIMESTAMP)""")
        self.c.execute("CREATE TABLE IF NOT EXISTS kv(k TEXT PRIMARY KEY, v TEXT)")
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

    def set_status(self, company_substr: str, status: str, note: str = "") -> int:
        cur = self.c.execute("UPDATE applications SET status=?, note=?, applied_at=applied_at WHERE lower(company) LIKE ?",
                             (status, note, f"%{company_substr.lower()}%"))
        self.c.commit()
        return cur.rowcount

    def all_postings(self):
        return self.c.execute("SELECT first_seen,source,company,title,location,url FROM postings "
                              "ORDER BY first_seen DESC").fetchall()

    def program_rows(self):
        return self.c.execute("SELECT name,url,status,deadline,changed,last_checked FROM programs").fetchall()

    def upsert_program(self, name, url, status, deadline, text_hash):
        old = self.c.execute("SELECT text_hash FROM programs WHERE name=?", (name,)).fetchone()
        changed = 1 if (old and old[0] and text_hash and old[0] != text_hash) else 0
        self.c.execute("""INSERT INTO programs(name,url,status,deadline,text_hash,changed,last_checked)
            VALUES(?,?,?,?,?,?,CURRENT_TIMESTAMP) ON CONFLICT(name) DO UPDATE SET url=excluded.url,
            status=excluded.status, deadline=COALESCE(excluded.deadline, deadline),
            text_hash=excluded.text_hash, changed=excluded.changed, last_checked=CURRENT_TIMESTAMP""",
            (name, url, status, deadline, text_hash, changed))
        self.c.commit()
        return bool(changed)

    def upsert_researcher(self, r):
        import json
        self.c.execute("""INSERT INTO researchers(author_id,name,company,score,papers,url) VALUES(?,?,?,?,?,?)
            ON CONFLICT(author_id) DO UPDATE SET score=excluded.score, papers=excluded.papers""",
            (r["author_id"], r["name"], r["company"], r["score"], json.dumps(r["papers"]), r["url"]))
        self.c.commit()

    def researchers(self):
        return self.c.execute("SELECT author_id,name,company,score,papers,url,draft,contacted FROM researchers "
                              "ORDER BY score DESC").fetchall()

    def set_draft(self, author_id, draft):
        self.c.execute("UPDATE researchers SET draft=? WHERE author_id=?", (draft, author_id))
        self.c.commit()

    def get(self, k, default=None):
        r = self.c.execute("SELECT v FROM kv WHERE k=?", (k,)).fetchone()
        return r[0] if r else default

    def put(self, k, v):
        self.c.execute("INSERT INTO kv(k,v) VALUES(?,?) ON CONFLICT(k) DO UPDATE SET v=excluded.v", (k, str(v)))
        self.c.commit()
