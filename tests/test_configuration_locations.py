from datetime import date, timedelta
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.models import CITIES, TripRequest
from app.agents.orchestrator import plan_trip
from app.settings import setting
from app.providers.live import LiveProvider
from app.providers.errors import ProviderError


def request(**changes):
    return TripRequest(start=date.today()+timedelta(days=30), end=date.today()+timedelta(days=34), budget=250000, **changes)


def test_saved_keys_override_stale_terminal_and_refresh(monkeypatch, tmp_path, signed_in_client):
    env = tmp_path / '.env'
    env.write_text('GROQ_API_KEY=saved-groq\nSERPAPI_API_KEY=saved-serp\nGEOAPIFY_API_KEY=saved-geo\n')
    from contextlib import nullcontext
    with nullcontext(signed_in_client) as client:
        response = client.get('/api/config')
        assert response.headers['cache-control'] == 'no-store'
        assert response.json()['live_available']
        assert 'saved-groq' not in response.text
        assert setting('GROQ_API_KEY') == 'saved-groq'
        assert setting('SERPAPI_API_KEY') == 'saved-serp'
        env.write_text('GROQ_API_KEY=saved-groq\nSERPAPI_API_KEY=  \nGEOAPIFY_API_KEY=saved-geo\n')
        data = client.get('/api/config').json()
        assert not data['live_available']
        assert data['missing_keys'] == ['SERPAPI_API_KEY']
        assert setting('SERPAPI_API_KEY') == ''


def test_global_catalog_and_same_airport_rejection():
    assert len(CITIES) > 3000
    assert sum(c['country_code']=='IN' for c in CITIES.values()) > 100
    for code in ('MAA','CCU','HYD','PNQ','COK','AMD','SIN','DXB','SYD','LAX'):
        assert request(origin=code, destination='GOI').origin == code
        assert request(destination=code).destination == code
    with pytest.raises(ValueError, match='different'):
        request(origin='maa',destination='MAA')
    with pytest.raises(ValueError, match='suggestions'):
        request(origin='UNKNOWN')


@pytest.mark.asyncio
@pytest.mark.parametrize('origin,destination', [('MAA','COK'),('SIN','SYD')])
async def test_new_locations_work_through_entire_team(origin,destination):
    plan=await plan_trip(request(origin=origin,destination=destination))
    assert plan['status']=='within_budget'
    assert plan['destination_name']==CITIES[destination]['name']
    assert plan['metrics']['model_calls']==0
    assert plan['total']==sum(plan['costs'].values())


@pytest.mark.asyncio
async def test_new_destination_uses_city_center_for_places():
    provider=LiveProvider()
    calls=[]
    async def geo(path,params,ttl=7*86400):
        calls.append((path,params,ttl))
        if path=='/v1/geocode/search':
            return {'results':[{'lat':13.08,'lon':80.27,'country_code':'in'}]},1
        return {'features':[]},1
    provider.geo=geo
    try:
        assert await provider.search_activities(request(destination='MAA'))==[]
        assert calls[0][1]['filter']=='countrycode:in'
        assert calls[0][2]==30*86400
        assert calls[1][1]['filter']=='circle:80.27,13.08,8000'
    finally: await provider.close()


@pytest.mark.asyncio
async def test_failed_geocoding_does_not_search_near_airport():
    provider=LiveProvider()
    calls=[]
    async def geo(path,params,ttl):
        calls.append(path)
        return {'results':[]},1
    provider.geo=geo
    try:
        with pytest.raises(ProviderError,match='locate'):
            await provider.search_activities(request(destination='MAA'))
        assert calls==['/v1/geocode/search']
    finally: await provider.close()
