import asyncio
import hashlib
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import date,timedelta
import httpx
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.security import SecurityStore, Denied, COOKIE, principal, guarded
from app.services.cache import Store
from app.http_limits import bounded_request

PASSWORD='a-very-long-test-password'
def trip():return {'start':str(date.today()+timedelta(days=30)),'end':str(date.today()+timedelta(days=34)),'budget':45000}
def login(client,name='alice'):
    r=client.post('/api/auth/login',json={'username':name,'password':PASSWORD},headers={'Origin':'http://testserver'})
    assert r.status_code==200
    client.headers.update({'Origin':'http://testserver','Content-Type':'application/json','X-CSRF-Token':r.json()['csrf']})
    return r

@pytest.mark.parametrize('path',['/api/config','/api/usage','/api/auth/session','/api/plan','/api/plan/stream'])
def test_api_requires_account(path):
    with TestClient(app) as c:
        r=c.post(path,json=trip(),headers={'Origin':'http://testserver'}) if '/plan' in path else c.get(path)
        assert r.status_code==401

@pytest.mark.parametrize('path',['/.env','/.local/state.sqlite3','/.local/owner-login.txt','/app/settings.py','/openapi.json','/docs','/api/plans/another-user'])
def test_private_resources_not_exposed(path):
    with TestClient(app) as c:assert c.get(path).status_code in (401,404)

def test_cookie_hashes_and_cross_account_revoke():
    s=SecurityStore();s.create_user('alice',PASSWORD);s.create_user('bob',PASSWORD)
    with TestClient(app) as a,TestClient(app) as b:
        response=login(a);login(b,'bob');old=a.cookies.get(COOKIE)
        assert 'HttpOnly' in response.headers['set-cookie'] and 'SameSite=strict' in response.headers['set-cookie']
        with s.connection() as db:
            hashes=[r[0] for r in db.execute('SELECT digest FROM sessions')]
            assert old not in hashes and hashlib.sha256(old.encode()).hexdigest() in hashes
            assert db.execute('SELECT password FROM users WHERE username="alice"').fetchone()[0]!=PASSWORD
        assert a.post('/api/auth/logout-all',json={'user_id':'bob'}).status_code==200
        assert b.get('/api/auth/session').json()['username']=='bob'
        with pytest.raises(Denied):s.session(old)

def test_csrf_and_origin_cannot_be_bypassed(signed_in_client):
    c=signed_in_client
    assert c.post('/api/plan',json=trip(),headers={'Origin':'https://evil.example'}).status_code==403
    assert c.post('/api/plan',json=trip(),headers={'X-CSRF-Token':'wrong'}).status_code==403
    assert c.get('/api/config',headers={'Sec-Fetch-Site':'cross-site'}).status_code==403
    c.headers.pop('Origin')
    assert c.post('/api/plan',json=trip()).status_code==403

def test_input_limits_and_validation_do_not_echo_secrets(signed_in_client):
    c=signed_in_client
    assert c.post('/api/plan',content=b'x'*16385).status_code==413
    assert c.post('/api/plan',content='{}',headers={'Content-Type':'text/plain'}).status_code==415
    assert c.post('/api/plan',content='{}',headers={'Content-Encoding':'gzip'}).status_code==415
    r=c.post('/api/plan',json={**trip(),'role':'admin','secret':'never-echo-this'})
    assert r.status_code==422 and 'never-echo-this' not in r.text
    assert c.get('/api/config?'+('x'*1025)).status_code==414

def test_login_limit_persists_ignores_forwarded_ip():
    with TestClient(app) as c:
        for i in range(5):
            r=c.post('/api/auth/login',json={'username':'nobody','password':PASSWORD},headers={'Origin':'http://testserver','X-Forwarded-For':f'1.2.3.{i}'})
            assert r.status_code==401
    with TestClient(app) as c:
        r=c.post('/api/auth/login',json={'username':'other','password':PASSWORD},headers={'Origin':'http://testserver','X-Forwarded-For':'8.8.8.8'})
        assert r.status_code==429 and r.headers['Retry-After']=='60'

def test_expired_disabled_and_revoked_sessions():
    s=SecurityStore();s.create_user('alice',PASSWORD)
    token,_=s.login('alice',PASSWORD)
    with s.connection() as db:db.execute('UPDATE sessions SET touched=?',(time.time()-1801,))
    with pytest.raises(Denied):s.session(token)
    token,_=s.login('alice',PASSWORD)
    with s.connection() as db:db.execute('UPDATE sessions SET expires=?',(time.time()-1,))
    with pytest.raises(Denied):s.session(token)
    token,_=s.login('alice',PASSWORD)
    with s.connection() as db:db.execute('UPDATE users SET disabled=1')
    with pytest.raises(Denied):s.session(token)

def test_per_user_atomic_admission_and_release(signed_in_client):
    c=signed_in_client;s=SecurityStore();user=s.session(c.cookies.get(COOKIE));lease=s.acquire(user)
    try:
        for path in ('/api/plan','/api/plan/stream'):
            assert c.post(path,json=trip()).status_code==429
    finally:s.release(lease)
    assert c.post('/api/plan',json=trip()).status_code==200
    with s.connection() as db:assert db.execute('SELECT COUNT(*) FROM leases').fetchone()[0]==0

def test_limit_atomic_across_instances():
    SecurityStore()
    def attempt(_):
        try:SecurityStore().limit([('race',60,3)]);return True
        except Denied:return False
    with ThreadPoolExecutor(max_workers=8) as pool:assert sum(pool.map(attempt,range(12)))==3

def test_private_model_cache_is_partitioned():
    s=Store();token=principal.set('alice')
    try:
        first=s.cache_key('groq',{'budget':123},'key');quote=s.cache_key('serpapi',{'route':'DEL-GOI'},'key')
        principal.set('bob')
        assert s.cache_key('groq',{'budget':123},'key')!=first
        assert s.cache_key('serpapi',{'route':'DEL-GOI'},'key')==quote
    finally:principal.reset(token)

@pytest.mark.asyncio
async def test_revocation_cancels_inflight_work():
    s=SecurityStore();s.create_user('alice',PASSWORD);token,_=s.login('alice',PASSWORD);user=s.session(token);cancelled=asyncio.Event()
    async def expensive():
        try:await asyncio.sleep(30)
        finally:cancelled.set()
    task=asyncio.create_task(guarded(expensive(),user['digest']))
    await asyncio.sleep(.02);s.revoke(user)
    with pytest.raises(Denied):await asyncio.wait_for(task,2)
    assert cancelled.is_set()

@pytest.mark.asyncio
async def test_remote_peers_denied_despite_forged_headers():
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app,client=('10.0.0.2',123)),base_url='http://localhost') as c:
        assert (await c.get('/api/config',headers={'X-Forwarded-For':'127.0.0.1'})).status_code==403

@pytest.mark.asyncio
async def test_provider_response_memory_cap():
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda r:httpx.Response(200,content=b'x'*(2*1024*1024+1)))) as c:
        with pytest.raises(httpx.HTTPError):await bounded_request(c,'GET','https://example.com')

def test_security_headers(signed_in_client):
    r=signed_in_client.get('/')
    assert r.headers['x-frame-options']=='DENY'
    assert "script-src 'self'" in r.headers['content-security-policy']
    assert r.headers['cache-control']=='no-store'

@pytest.mark.asyncio
async def test_compressed_provider_response_decoded_once():
    import gzip
    data=gzip.compress(b'{"ok":true}')
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda r:httpx.Response(200,headers={'Content-Encoding':'gzip'},content=data))) as c:
        assert (await bounded_request(c,'GET','https://example.com')).json()=={'ok':True}

def test_global_admission_survives_new_store_instances():
    s=SecurityStore();leases=[]
    try:
        for i in range(3):leases.append(SecurityStore().acquire({'id':str(i),'digest':'test'}))
        with pytest.raises(Denied):SecurityStore().acquire({'id':'fourth','digest':'test'})
    finally:
        for lease in leases:s.release(lease)

def test_planning_rate_shared_between_endpoints(signed_in_client):
    c=signed_in_client
    # Invalid attempts still consume admission/rate budget and cannot rotate paths.
    for i in range(5):assert c.post('/api/plan' if i%2 else '/api/plan/stream',json={}).status_code==422
    assert c.post('/api/plan/stream',json=trip()).status_code==429

@pytest.mark.asyncio
async def test_chunked_body_cannot_bypass_limit(signed_in_client):
    cookie=signed_in_client.cookies.get(COOKIE);csrf=signed_in_client.headers['X-CSRF-Token']
    async def chunks():
        for i in range(4):yield b'x'*5000
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://testserver') as c:
        r=await c.post('/api/plan',content=chunks(),headers={'Origin':'http://testserver','Content-Type':'application/json','Cookie':f'{COOKIE}={cookie}','X-CSRF-Token':csrf})
        assert r.status_code==413

def test_api_error_scrubs_configured_secret(signed_in_client,monkeypatch):
    import app.main as main
    from app.providers import ProviderError
    async def failing(*args,**kwargs):raise ProviderError('bad test-not-a-real-key')
    monkeypatch.setattr(main,'plan_trip',failing)
    r=signed_in_client.post('/api/plan',json=trip())
    assert r.status_code==502 and 'test-not-a-real-key' not in r.text
