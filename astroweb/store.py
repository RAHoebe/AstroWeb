"""Small durable JSON-record store; connections are never shared across threads."""
import json
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path


def now():
    return datetime.now(timezone.utc).isoformat()


class Store:
    def __init__(self, root):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.db = self.root / "astroweb.sqlite3"
        self.lock = threading.RLock()
        with self.connect() as db:
            db.execute("PRAGMA journal_mode=WAL")
            db.execute("CREATE TABLE IF NOT EXISTS objects (id TEXT PRIMARY KEY, record TEXT NOT NULL)")
            db.execute("CREATE TABLE IF NOT EXISTS jobs (id TEXT PRIMARY KEY, record TEXT NOT NULL)")
            db.execute("CREATE TABLE IF NOT EXISTS object_aliases (alias TEXT PRIMARY KEY, current_id TEXT NOT NULL)")
            db.execute("CREATE TABLE IF NOT EXISTS settings (id TEXT PRIMARY KEY, record TEXT NOT NULL)")

    def connect(self):
        db = sqlite3.connect(self.db, timeout=30)
        db.execute("PRAGMA busy_timeout=30000")
        return db

    def get(self, table, key, default=None):
        if table not in {"objects", "jobs", "settings"}:
            raise ValueError("table")
        with self.connect() as db:
            row = db.execute(f"SELECT record FROM {table} WHERE id=?", (key,)).fetchone()
        return json.loads(row[0]) if row else default

    def all(self, table):
        if table not in {"objects", "jobs"}:
            raise ValueError("table")
        with self.connect() as db:
            rows = db.execute(f"SELECT record FROM {table} ORDER BY rowid DESC").fetchall()
        return [json.loads(row[0]) for row in rows]

    def put(self, table, key, value):
        if table not in {"objects", "jobs", "settings"}:
            raise ValueError("table")
        with self.lock, self.connect() as db:
            db.execute(f"INSERT INTO {table}(id,record) VALUES (?,?) ON CONFLICT(id) DO UPDATE SET record=excluded.record", (key, json.dumps(value, ensure_ascii=False)))
        return value

    def update(self, table, key, **changes):
        with self.lock:
            record = self.get(table, key)
            if record is None:
                raise KeyError(key)
            record.update(changes)
            return self.put(table, key, record)

    def current_id(self, identifier):
        with self.connect() as db:
            row = db.execute("SELECT current_id FROM object_aliases WHERE alias=?", (identifier,)).fetchone()
        return row[0] if row else identifier

    def rename_object(self, old, new, metadata, catalog_id=None):
        with self.lock, self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT record FROM objects WHERE id=?", (old,)).fetchone()
            if not row:
                raise ValueError("object_not_found")
            record = json.loads(row[0])
            if old == new:
                return record
            occupied = db.execute("SELECT 1 FROM objects WHERE id=? UNION ALL SELECT 1 FROM object_aliases WHERE alias=? AND current_id!=?", (new,new,old)).fetchone()
            if occupied:
                raise ValueError("object_exists")
            jobs = [json.loads(r[0]) for r in db.execute("SELECT record FROM jobs WHERE json_extract(record,'$.object_id')=?", (old,))]
            if any(j["status"] in ("running","queued","cancelling") for j in jobs) or (record.get("gaia") or {}).get("status") in ("pending","running"):
                raise ValueError("rename_busy")
            record.setdefault("storage_id", old)
            record.update(id=new,metadata=metadata)
            if catalog_id:
                record["catalog_id"] = catalog_id
            db.execute("UPDATE objects SET id=?,record=? WHERE id=?", (new,json.dumps(record),old))
            for job in jobs:
                job["object_id"] = new
                db.execute("UPDATE jobs SET record=? WHERE id=?", (json.dumps(job),job["id"]))
            db.execute("DELETE FROM object_aliases WHERE alias=?", (new,))
            db.execute("UPDATE object_aliases SET current_id=? WHERE current_id=?", (new,old))
            db.execute("INSERT INTO object_aliases VALUES(?,?)", (old,new))
            return record

    def finish_render(self, record, job):
        with self.lock, self.connect() as db:
            db.execute("UPDATE objects SET record=? WHERE id=?", (json.dumps(record), record["id"]))
            db.execute("UPDATE jobs SET record=? WHERE id=?", (json.dumps(job), job["id"]))

    def path(self, relative):
        path = (self.root / relative).resolve()
        if not path.is_relative_to(self.root):
            raise ValueError("invalid_path")
        return path
