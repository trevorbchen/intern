import sqlite3
from .models import Posting


class DB:
    def __init__(self, path):
        self.c = sqlite3.connect(path)
        self.c.execute("""CREATE TABLE IF NOT EXISTS postings(
            uid TEXT PRIMARY KEY, source TEXT, title TEXT, company TEXT, url TEXT,
            location TEXT, posted TEXT, first_seen TEXT DEFAULT CURRENT_TIMESTAMP)""")

    def add_if_new(self, p: Posting) -> bool:
        cur = self.c.execute(
            "INSERT OR IGNORE INTO postings(uid,source,title,company,url,location,posted) VALUES(?,?,?,?,?,?,?)",
            (p.uid, p.source, p.title, p.company, p.url, p.location, p.posted))
        self.c.commit()
        return cur.rowcount == 1
