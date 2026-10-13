"""Tests cannot use real credentials or share the application's quota database."""
import pytest

@pytest.fixture(autouse=True)
def isolated_configuration(monkeypatch, tmp_path):
    monkeypatch.setenv('ROAM_ENV_FILE', str(tmp_path / '.env'))
    monkeypatch.setenv('ROAM_DB_PATH', str(tmp_path / 'state.sqlite3'))
    for key in ('GROQ_API_KEY','SERPAPI_API_KEY','GEOAPIFY_API_KEY'):
        monkeypatch.setenv(key,'test-not-a-real-key')

@pytest.fixture
def signed_in_client():
    from fastapi.testclient import TestClient
    from app.main import app
    from app.security import SecurityStore
    store=SecurityStore();store.create_user('tester','test-password-at-least-14')
    with TestClient(app) as client:
        client.headers.update({'Origin':'http://testserver','Content-Type':'application/json'})
        response=client.post('/api/auth/login',json={'username':'tester','password':'test-password-at-least-14'})
        assert response.status_code==200
        client.headers['X-CSRF-Token']=response.json()['csrf']
        yield client
