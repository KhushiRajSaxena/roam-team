"""Local accounts, revocable opaque sessions, atomic limits and admission control."""
import asyncio
import hashlib
import hmac
import ipaddress
import json
import secrets
import sqlite3
import time
from contextvars import ContextVar
from http.cookies import SimpleCookie
from starlette.responses import JSONResponse
from app.services.cache import Store

principal = ContextVar('principal', default='offline')
COOKIE = 'roam_session'
MAX_BODY = 16384

class Denied(Exception):
    def __init__(self, status, message): self.status, self.message = status, message

class SecurityStore(Store):
    def __init__(self):
        super().__init__()
        self.path.chmod(0o600)
        with self.connection() as db:
            db.executescript('''
              CREATE TABLE IF NOT EXISTS users(id TEXT PRIMARY KEY, username TEXT UNIQUE, salt TEXT, password TEXT, disabled INTEGER DEFAULT 0);
              CREATE TABLE IF NOT EXISTS sessions(digest TEXT PRIMARY KEY, user_id TEXT, csrf TEXT, created REAL, touched REAL, expires REAL);
              CREATE INDEX IF NOT EXISTS sessions_user ON sessions(user_id);
              CREATE TABLE IF NOT EXISTS request_limits(bucket TEXT, at REAL);
              CREATE INDEX IF NOT EXISTS limits_bucket ON request_limits(bucket,at);
              CREATE TABLE IF NOT EXISTS leases(id TEXT PRIMARY KEY, user_id TEXT, session TEXT, expires REAL);
            ''')

    @staticmethod
    def password_hash(password, salt):
        return hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt), n=16384, r=8, p=1).hex()

    def create_user(self, username, password):
        if not 3 <= len(username) <= 64 or not username.isascii() or not all(c.isalnum() or c in '_-' for c in username):
            raise ValueError('Username must be 3-64 ASCII letters, digits, underscores or hyphens.')
        if not 14 <= len(password) <= 128: raise ValueError('Use a password of 14 to 128 characters.')
        salt=secrets.token_hex(16)
        with self.connection() as db:
            db.execute('INSERT INTO users VALUES(?,?,?,?,0)',(secrets.token_hex(16),username,salt,self.password_hash(password,salt)))

    def limit(self, rules):
        now=time.time()
        with self.connection() as db:
            db.execute('BEGIN IMMEDIATE')
            db.execute('DELETE FROM request_limits WHERE at<?',(now-3600,))
            for bucket,window,maximum in rules:
                used=db.execute('SELECT COUNT(*) FROM request_limits WHERE bucket=? AND at>?',(bucket,now-window)).fetchone()[0]
                if used>=maximum: raise Denied(429,'Too many requests. Please wait before trying again.')
            db.executemany('INSERT INTO request_limits VALUES(?,?)',[(b,now) for b,_,_ in rules])

    def login(self, username, password):
        with self.connection() as db:
            row=db.execute('SELECT id,salt,password,disabled FROM users WHERE username=?',(username,)).fetchone()
        # Run scrypt even for unknown usernames to avoid a cheap account oracle.
        actual=self.password_hash(password,row[1] if row else '00'*16)
        if not row or not hmac.compare_digest(actual,row[2]) or row[3]:
            raise Denied(401,'Incorrect username or password.')
        token=secrets.token_urlsafe(32);csrf=secrets.token_urlsafe(32);now=time.time()
        with self.connection() as db:
            db.execute('DELETE FROM sessions WHERE expires<? OR touched<?',(now,now-1800))
            db.execute('INSERT INTO sessions VALUES(?,?,?,?,?,?)',(hashlib.sha256(token.encode()).hexdigest(),row[0],csrf,now,now,now+8*3600))
        return token,csrf

    def session(self, token):
        if not token or len(token)>128: raise Denied(401,'Please sign in to continue.')
        digest=hashlib.sha256(token.encode()).hexdigest();now=time.time()
        with self.connection() as db:
            row=db.execute('SELECT s.user_id,s.csrf,u.username FROM sessions s JOIN users u ON u.id=s.user_id WHERE s.digest=? AND s.expires>? AND s.touched>? AND u.disabled=0',(digest,now,now-1800)).fetchone()
            if not row: raise Denied(401,'Your session has expired or been revoked. Please sign in again.')
            db.execute('UPDATE sessions SET touched=? WHERE digest=?',(now,digest))
        return {'id':row[0],'csrf':row[1],'username':row[2],'digest':digest}

    def revoke(self, user, all_sessions=False):
        with self.connection() as db:
            db.execute('DELETE FROM sessions WHERE '+('user_id' if all_sessions else 'digest')+'=?',(user['id'] if all_sessions else user['digest'],))

    def acquire(self, user):
        now=time.time();lease=secrets.token_hex(16)
        with self.connection() as db:
            db.execute('BEGIN IMMEDIATE');db.execute('DELETE FROM leases WHERE expires<?',(now,))
            if db.execute('SELECT COUNT(*) FROM leases').fetchone()[0]>=3 or db.execute('SELECT COUNT(*) FROM leases WHERE user_id=?',(user['id'],)).fetchone()[0]>=1:
                raise Denied(429,'The planner is busy. Wait for the current trip to finish.')
            db.execute('INSERT INTO leases VALUES(?,?,?,?)',(lease,user['id'],user['digest'],now+190))
        return lease

    def release(self, lease):
        with self.connection() as db: db.execute('DELETE FROM leases WHERE id=?',(lease,))

    def active(self, digest):
        with self.connection() as db:
            return bool(db.execute('SELECT 1 FROM sessions s JOIN users u ON u.id=s.user_id WHERE digest=? AND expires>? AND touched>? AND disabled=0',(digest,time.time(),time.time()-1800)).fetchone())

async def guarded(awaitable, digest):
    """Stop active model/provider work shortly after revocation or expiry."""
    task=asyncio.ensure_future(awaitable)
    try:
        async with asyncio.timeout(180):
            while True:
                done,_=await asyncio.wait([task],timeout=1)
                if not await asyncio.to_thread(SecurityStore().active,digest):
                    raise Denied(401,'Session revoked. Please sign in again.')
                if done:return task.result()
    finally:
        task.cancel()
        from contextlib import suppress
        with suppress(asyncio.CancelledError): await task

class SecurityMiddleware:
    def __init__(self, app): self.app=app

    async def __call__(self, scope, receive, send):
        if scope['type']!='http':return await self.app(scope,receive,send)
        headers={k.decode().lower():v.decode() for k,v in scope['headers']}
        path=scope['path'];method=scope['method'];started=False;lease=None;store=None;context=None
        async def secured_send(message):
            nonlocal started
            if message['type']=='http.response.start':
                started=True
                message['headers']+= [(b'cache-control',b'no-store'),(b'x-content-type-options',b'nosniff'),(b'referrer-policy',b'no-referrer'),(b'x-frame-options',b'DENY'),(b'permissions-policy',b'camera=(), microphone=(), geolocation=()'),
                    (b'content-security-policy',b"default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; font-src 'self' https://fonts.gstatic.com; img-src 'self' data:; connect-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'; form-action 'self'")]
            await send(message)
        try:
            peer=(scope.get('client') or ('',))[0]
            # This release is intentionally local-only. Never trust forwarded IPs.
            try: local=ipaddress.ip_address(peer).is_loopback
            except ValueError: local=peer=='testclient'
            if not local: raise Denied(403,'This application is restricted to the local machine.')
            if len(path)>256 or len(scope.get('query_string',b''))>1024:raise Denied(414,'Request URL is too long.')
            if path.startswith('/api/'):
                store=await asyncio.to_thread(SecurityStore)
                await asyncio.to_thread(store.limit,[('global-api',60,180),('peer:'+peer,60,120)])
                if headers.get('sec-fetch-site') not in (None,'same-origin','none'):
                    raise Denied(403,'Cross-site API requests are not allowed.')
                if method not in ('GET','HEAD'):
                    origin=scope['scheme']+'://'+headers.get('host','')
                    if headers.get('origin')!=origin:raise Denied(403,'A same-origin request is required.')
                    if headers.get('content-type','').split(';')[0].strip()!='application/json':raise Denied(415,'Use application/json.')
                    if headers.get('content-encoding','identity')!='identity':raise Denied(415,'Compressed request bodies are not supported.')
                if path not in ('/api/health','/api/auth/login'):
                    cookie=SimpleCookie()
                    try:cookie.load(headers.get('cookie',''))
                    except Exception:raise Denied(401,'Please sign in to continue.')
                    token=cookie.get(COOKIE)
                    user=await asyncio.to_thread(store.session,token.value if token else '')
                    scope.setdefault('state',{})['user']=user
                    if method not in ('GET','HEAD') and not hmac.compare_digest(headers.get('x-csrf-token',''),user['csrf']):
                        raise Denied(403,'Invalid request token. Refresh and try again.')
                    await asyncio.to_thread(store.limit,[('user:'+user['id'],60,60)])
                    context=principal.set(user['id'])
                    if path in ('/api/plan','/api/plan/stream'):
                        await asyncio.to_thread(store.limit,[('plans:'+user['id'],3600,20),('burst:'+user['id'],60,5),('global-plans',3600,30)])
                        lease=await asyncio.to_thread(store.acquire,user)
                elif path=='/api/auth/login':
                    await asyncio.to_thread(store.limit,[('login:'+peer,60,5),('global-login',60,10)])
                body=bytearray()
                try:
                    async with asyncio.timeout(10):
                        while True:
                            message=await receive()
                            if message['type']=='http.disconnect':return
                            body.extend(message.get('body',b''))
                            if len(body)>MAX_BODY:raise Denied(413,'Request body exceeds 16 KB.')
                            if not message.get('more_body'):break
                except TimeoutError:raise Denied(408,'Request body timed out.')
                consumed=False
                async def replay():
                    nonlocal consumed
                    if not consumed:consumed=True;return {'type':'http.request','body':bytes(body),'more_body':False}
                    return await receive()
                await self.app(scope,replay,secured_send)
            else:
                await self.app(scope,receive,secured_send)
        except Denied as exc:
            if not started:await JSONResponse({'detail':exc.message},status_code=exc.status,headers={'Retry-After':'60'} if exc.status==429 else {})(scope,receive,secured_send)
        except Exception:
            # Do not expose exception text, provider URLs, credentials or tracebacks.
            if not started:await JSONResponse({'detail':'Request could not be completed. Please try again.'},status_code=503)(scope,receive,secured_send)
        finally:
            if lease and store:await asyncio.to_thread(store.release,lease)
            if context is not None:principal.reset(context)
