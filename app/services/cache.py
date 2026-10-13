"""Persistent cache and conservative outbound-call budgets for a local deployment.

Reservations are atomic across SQLite connections, made before dispatch, and are
not refunded on failure. Single-flight locks deduplicate same-process requests.
Never store API keys, request URLs containing credentials, or account identities.
"""
from app.settings import setting
import asyncio
import hashlib
import json
import os
import sqlite3
import time
import weakref
from contextlib import contextmanager
from pathlib import Path

class QuotaError(RuntimeError): pass

_locks = weakref.WeakKeyDictionary()

def lock_for(name):
    loop = asyncio.get_running_loop()
    return _locks.setdefault(loop, {}).setdefault(name, asyncio.Lock())

def bounded_setting(name, default, maximum):
    try: return max(0, min(int(setting(name, default)), maximum))
    except ValueError: return default

class Store:
    def __init__(self, path=None):
        self.path = Path(path or setting("ROAM_DB_PATH") or Path(__file__).resolve().parents[2] / ".local/state.sqlite3")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connection() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS cache(key TEXT PRIMARY KEY, value TEXT NOT NULL, created REAL NOT NULL, expires REAL NOT NULL);
                CREATE TABLE IF NOT EXISTS usage(provider TEXT NOT NULL, at REAL NOT NULL, units INTEGER NOT NULL);
                CREATE INDEX IF NOT EXISTS usage_lookup ON usage(provider, at);
            """)

    @contextmanager
    def connection(self):
        db = sqlite3.connect(self.path, timeout=1)
        self.path.chmod(0o600)
        try:
            with db: yield db
        finally: db.close()

    def cache_key(self, provider, params, credential=""):
        from app.security import principal
        # Shared provider-account counters stay global; private AI decisions do not.
        identity = principal.get() if provider == 'groq' else 'public-quotes'
        scope = hashlib.sha256((identity + ':' + credential).encode()).hexdigest()[:16]
        digest = hashlib.sha256(json.dumps(params, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        return f"v2:{provider}:{scope}:{digest}"

    def get(self, key):
        with self.connection() as db:
            row = db.execute("SELECT value,created FROM cache WHERE key=? AND expires>?", (key, time.time())).fetchone()
        return (json.loads(row[0]), row[1]) if row else None

    def put(self, key, value, ttl):
        now = time.time()
        with self.connection() as db:
            db.execute("INSERT OR REPLACE INTO cache VALUES(?,?,?,?)", (key, json.dumps(value), now, now + ttl))
            db.execute("DELETE FROM cache WHERE expires<?", (now - 86400,))
            db.execute("DELETE FROM usage WHERE at<?", (now - 32 * 86400,))
            # Bound cached payloads even when provider data is unexpectedly large.
            size=db.execute('SELECT COALESCE(SUM(LENGTH(value)),0) FROM cache').fetchone()[0]
            while size>64*1024*1024:
                oldest=db.execute('SELECT key,LENGTH(value) FROM cache ORDER BY created LIMIT 1').fetchone()
                db.execute('DELETE FROM cache WHERE key=?',(oldest[0],));size-=oldest[1]

    def consume_balance(self, key, reserve=20):
        """Deduct locally from a cached provider balance without extending its TTL."""
        with self.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            row=db.execute("SELECT value FROM cache WHERE key=? AND expires>?",(key,time.time())).fetchone()
            if not row: raise QuotaError("SerpApi balance check expired; please retry.")
            data=json.loads(row[0]);left=data.get("plan_searches_left")
            if not isinstance(left,(int,float)) or left<=reserve:
                raise QuotaError("SerpApi free-plan reserve reached. Cached searches still work; the last 20 searches are protected.")
            data["plan_searches_left"]=left-1
            db.execute("UPDATE cache SET value=? WHERE key=?",(json.dumps(data),key))

    def policies(self, provider):
        if provider == "serpapi":
            return [(31*86400, bounded_setting("SERPAPI_31_DAY_LIMIT", 200, 230)),
                    (86400, bounded_setting("SERPAPI_DAILY_LIMIT", 10, 40)), (3600, 40)], .2
        if provider == "geoapify":
            return [(86400, bounded_setting("GEOAPIFY_DAILY_LIMIT", 500, 2500))], .3
        if provider == "groq":
            return [(86400, bounded_setting("GROQ_DAILY_CALL_LIMIT", 100, 500)), (60, 20)], 3.1
        return [(86400, 1000)], .3

    def reserve(self, provider, units=1):
        now = time.time()
        policies, interval = self.policies(provider)
        with self.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            for window, limit in policies:
                used = db.execute("SELECT COALESCE(SUM(units),0) FROM usage WHERE provider=? AND at>?", (provider, now-window)).fetchone()[0]
                if used + units > limit:
                    raise QuotaError(f"{provider.title()} local usage limit reached. Cached searches still work; try again after the rolling usage window clears.")
            latest = db.execute("SELECT MAX(at) FROM usage WHERE provider=?", (provider,)).fetchone()[0] or 0
            scheduled = max(now, latest + interval)
            db.execute("INSERT INTO usage VALUES(?,?,?)", (provider, scheduled, units))
        return max(0, scheduled-now)

    def stats(self):
        now = time.time()
        result = {}
        with self.connection() as db:
            for provider in ("serpapi", "geoapify", "groq"):
                policies, _ = self.policies(provider)
                window, limit = policies[0]
                used = db.execute("SELECT COALESCE(SUM(units),0) FROM usage WHERE provider=? AND at>?", (provider, now-window)).fetchone()[0]
                daily = db.execute("SELECT COALESCE(SUM(units),0) FROM usage WHERE provider=? AND at>?", (provider, now-86400)).fetchone()[0]
                result[provider] = {"used": used, "limit": limit, "remaining": max(0,limit-used), "daily_used": daily,
                    "window": "rolling 31 days" if provider == "serpapi" else "rolling 24 hours"}
        return result

    async def cached(self, provider, params, credential, ttl, loader, units=1):
        key = self.cache_key(provider, params, credential)
        async with lock_for(str(self.path.resolve()) + key):
            found = self.get(key)
            if found: return found[0], True, found[1]
            delay = self.reserve(provider, units)
            if delay: await asyncio.sleep(delay)
            value = await loader()
            self.put(key, value, ttl)
            return value, False, time.time()
