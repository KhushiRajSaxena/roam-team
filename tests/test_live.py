import asyncio
import json
import time
from datetime import date,timedelta
import httpx
import pytest
from app.services.cache import Store, QuotaError
from app.providers.live import LiveProvider, scrub
from app.providers.errors import ProviderError
from app.llm import ModelClient, ModelError
from app.models import Allocation, TripRequest
from app.planning import validate_plan


def trip(**kw):
    start=date.today()+timedelta(days=30)
    return TripRequest(**{'start':start,'end':start+timedelta(days=4),'budget':45000,'mode':'live',**kw})

@pytest.mark.asyncio
async def test_persistent_cache_deduplicates_concurrent_requests(tmp_path):
    a=Store(tmp_path/'db');b=Store(tmp_path/'db');calls=[]
    async def loader(): calls.append(1);await asyncio.sleep(.01);return {'ok':True}
    results=await asyncio.gather(a.cached('serpapi',{'route':'DEL-GOI'},'key',3600,loader),b.cached('serpapi',{'route':'DEL-GOI'},'key',3600,loader))
    assert len(calls)==1
    assert sorted(x[1] for x in results)==[False,True]
    assert b.stats()['serpapi']['used']==1
    assert (await b.cached('serpapi',{'route':'DEL-GOI'},'key',3600,loader))[1]

@pytest.mark.asyncio
async def test_cache_hits_work_after_quota_exhaustion(monkeypatch):
    monkeypatch.setenv('SERPAPI_DAILY_LIMIT','1');s=Store()
    async def loader(): return {'ok':True}
    await s.cached('serpapi',{},'key',3600,loader)
    assert (await s.cached('serpapi',{},'key',3600,loader))[1]
    with pytest.raises(QuotaError): await s.cached('serpapi',{'new':True},'key',3600,loader)

@pytest.mark.asyncio
async def test_expired_cache_does_not_silently_serve_old_quotes():
    s=Store();key=s.cache_key('serpapi',{},'key');s.put(key,{'old':True},-1)
    assert s.get(key) is None

@pytest.mark.asyncio
async def test_failed_request_is_counted_and_not_retried():
    s=Store();calls=[]
    async def fail(): calls.append(1);raise ProviderError('unavailable')
    with pytest.raises(ProviderError): await s.cached('serpapi',{},'key',60,fail)
    assert calls==[1] and s.stats()['serpapi']['used']==1


def test_geo_rate_reservations_are_spaced():
    s=Store();a=s.reserve('geoapify');b=s.reserve('geoapify')
    assert b-a>.25


def test_credential_values_never_survive_sanitization():
    result=scrub({'api_key':'secret','url':'https://example.test?apiKey=secret','nested':['secret'],'account_email':'private'},['secret'])
    assert 'secret' not in json.dumps(result)
    assert 'account_email' not in result


def flight_data(t, returning=False):
    origin,dest=(t.destination,t.origin) if returning else (t.origin,t.destination)
    day=t.end if returning else t.start
    return {'search_parameters':{'currency':'INR'},'search_metadata':{'google_flights_url':'https://www.google.com/travel/flights'},'best_flights':[{
        'price':12000,'departure_token':'outbound-token','booking_token':'return-token',
        'flights':[{'airline':'Test Air','departure_airport':{'id':origin,'time':f'{day} 09:00'},'arrival_airport':{'id':dest,'time':f'{day} 11:00'}}]}]}

@pytest.mark.asyncio
async def test_flights_expand_only_one_outbound_and_use_return_total():
    t=trip();p=LiveProvider();seen=[]
    async def serp(params):
        seen.append(params)
        return flight_data(t,'departure_token' in params),time.time()
    p.serp=serp
    try:
        offers=await p.search_flights(t)
        assert len(seen)==2 and len(offers)==1
        assert offers[0].cost==1200000 # not outbound + round-trip total
        assert offers[0].departure.startswith(str(t.end))
    finally: await p.close()

@pytest.mark.asyncio
async def test_hotel_stay_total_is_not_multiplied_again():
    p=LiveProvider()
    async def serp(params):
        return {'search_parameters':{'currency':'INR'},'properties':[{'name':'Test Hotel','total_rate':{'extracted_lowest':12000},'rate_per_night':{'extracted_lowest':3000}}]},time.time()
    p.serp=serp
    try:
        offers=await p.search_stays(trip(travelers=2))
        assert offers[0].cost==1200000 and offers[0].price_kind=='search_price'
    finally: await p.close()

@pytest.mark.asyncio
async def test_unknown_activity_fee_is_an_allowance_not_free():
    p=LiveProvider()
    async def geo(path,params):
        assert params['limit']==20
        return {'features':[{'geometry':{'coordinates':[73.8,15.5]},'properties':{'name':'Museum','place_id':'a','categories':['entertainment.museum']}}]},time.time()
    p.geo=geo
    try:
        o=(await p.search_activities(trip()))[0]
        assert o.cost>0 and o.price_kind=='estimate' and not o.sample
    finally: await p.close()

@pytest.mark.asyncio
async def test_serp_provider_balance_protects_last_twenty_searches():
    calls=[]
    def handler(request):
        calls.append(request.url.path)
        return httpx.Response(200,json={'plan_searches_left':20})
    p=LiveProvider(client=httpx.AsyncClient(transport=httpx.MockTransport(handler)))
    try:
        with pytest.raises(ProviderError,match='reserve'): await p.serp({'engine':'google_hotels'})
        assert calls==['/account.json']
    finally: await p.close()

@pytest.mark.asyncio
async def test_groq_structured_output_is_cached_and_tracks_tokens():
    requests=[]
    def handler(request):
        requests.append(request)
        body=json.loads(request.content)
        assert body['response_format']['json_schema']['strict'] is True
        assert request.url.host=='api.groq.com'
        return httpx.Response(200,json={'choices':[{'finish_reason':'stop','message':{'content':json.dumps({'flight_percent':45,'stay_percent':40,'message':'Delegate'})}}],
                'usage':{'prompt_tokens':100,'completion_tokens':20}})
    m=ModelClient(client=httpx.AsyncClient(transport=httpx.MockTransport(handler)))
    try:
        await m.ask('Coordinate','{}',Allocation)
        await m.ask('Coordinate','{}',Allocation)
        assert len(requests)==1
        assert m.metrics()['model_cache_hits']==1 and m.metrics()['input_tokens']==100
    finally: await m.close()

@pytest.mark.asyncio
async def test_groq_rate_limit_has_no_retry_or_paid_fallback():
    calls=[]
    def handler(request):calls.append(1);return httpx.Response(429,json={})
    m=ModelClient(client=httpx.AsyncClient(transport=httpx.MockTransport(handler)))
    try:
        with pytest.raises(ModelError,match='rate limit'): await m.ask('Coordinate','{}',Allocation)
        assert len(calls)==1
    finally: await m.close()

@pytest.mark.asyncio
async def test_independent_validator_detects_mutated_overlaps():
    from app.agents.orchestrator import plan_trip
    p=await plan_trip(trip(mode='demo'))
    day=next(d for d in p['itinerary'] if sum(i['kind']=='activity' for i in d['items'])>=2)
    activities=[i for i in day['items'] if i['kind']=='activity']
    activities[1]['time']=activities[0]['time']
    with pytest.raises(ValueError,match='conflict'):validate_plan(p)


def test_cached_account_balance_is_reserved_atomically():
    from concurrent.futures import ThreadPoolExecutor
    store=Store();key=store.cache_key('serpapi_account',{},'key')
    store.put(key,{'plan_searches_left':21},60)
    def consume():
        try: store.consume_balance(key);return True
        except QuotaError:return False
    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes=list(pool.map(lambda _:consume(),range(2)))
    assert sorted(outcomes)==[False,True]
    assert store.get(key)[0]['plan_searches_left']==20


def test_rolling_limit_survives_day_boundary_and_store_restart(monkeypatch,tmp_path):
    monkeypatch.setenv('SERPAPI_31_DAY_LIMIT','1')
    path=tmp_path/'persistent.db'
    initial=time.time()
    monkeypatch.setattr('app.services.cache.time.time',lambda:initial)
    Store(path).reserve('serpapi')
    monkeypatch.setattr('app.services.cache.time.time',lambda:initial+86401)
    with pytest.raises(QuotaError):Store(path).reserve('serpapi')


@pytest.mark.asyncio
async def test_route_reflow_drops_unfit_activity_and_recalculates_budget():
    from app.agents.orchestrator import plan_trip
    from app.planning import enrich_routes
    t=trip(mode='demo');p=await plan_trip(t)
    stay=p['selected']['stays'][0];stay['latitude']=15.5;stay['longitude']=73.8
    for o in p['selected']['activities']:o['latitude']=15.5;o['longitude']=73.8
    class LongRoutes:
        async def route(self,points):
            return {'legs':[{'minutes':600,'distance_m':100000} for _ in points[1:]],'source':'Test estimate'}
    await enrich_routes(p,t,LongRoutes())
    assert p['selected']['activities']==[]
    assert p['costs']['activities']==0
    assert p['total']==sum(p['costs'].values())
    validate_plan(p)
