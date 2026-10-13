import asyncio
from datetime import date, timedelta, datetime
import pytest
from pydantic import ValidationError
from fastapi.testclient import TestClient
from app.models import TripRequest, Selection, Allocation
from app.agents.orchestrator import plan_trip
from app.providers.demo import DemoProvider
from app.providers.errors import ProviderError
from app.providers.live import paise as money
from app.main import app

def trip(**kwargs):
    return TripRequest(**{"start": date.today()+timedelta(days=30), "end": date.today()+timedelta(days=34), "budget": 45000, **kwargs})

@pytest.mark.asyncio
async def test_full_trip_accounts_for_every_scheduled_item():
    p = await plan_trip(trip(travelers=2, budget=85000))
    assert p["status"] == "within_budget"
    assert p["total"] == sum(p["costs"].values())
    assert p["remaining"] == 8500000-p["total"]
    assert len(p["itinerary"]) == 5
    assert p["costs"]["activities"] == sum(i["cost"] for d in p["itinerary"] for i in d["items"] if i["kind"] == "activity")
    assert p["metrics"]["model_calls"] == 0
    assert {e["agent"] for e in p["events"]} == {"orchestrator", "flights", "stays", "activities"}

@pytest.mark.asyncio
async def test_unaffordable_budget_is_not_a_success():
    p = await plan_trip(trip(budget=1000))
    assert p["status"] == "over_budget"
    assert p["remaining"] < 0
    assert not p["checks"]["budget_compliant"]

@pytest.mark.parametrize("changes", [
    {"end": date.today()+timedelta(days=29)}, {"budget": -1}, {"travelers": 0},
    {"start": date.today()}, {"end": date.today()+timedelta(days=50)}, {"destination": "UNKNOWN"},
])
def test_invalid_requests(changes):
    with pytest.raises(ValidationError): trip(**changes)

@pytest.mark.asyncio
async def test_actual_parallel_retrieval():
    class ParallelProvider(DemoProvider):
        def __init__(self): self.started=set(); self.ready=asyncio.Event()
        async def gate(self, role):
            self.started.add(role)
            if len(self.started)==3: self.ready.set()
            await asyncio.wait_for(self.ready.wait(), timeout=2)
        async def search_flights(self,t): await self.gate("flights"); return await super().search_flights(t)
        async def search_stays(self,t): await self.gate("stays"); return await super().search_stays(t)
        async def search_activities(self,t): await self.gate("activities"); return await super().search_activities(t)
    provider=ParallelProvider()
    await plan_trip(trip(),provider=provider)
    assert len(provider.started)==3

@pytest.mark.asyncio
async def test_missing_flight_marks_partial_total():
    class NoFlights(DemoProvider):
        async def search_flights(self,t): return []
    p=await plan_trip(trip(),provider=NoFlights())
    assert p["status"]=="incomplete"
    assert not p["checks"]["budget_compliant"]

@pytest.mark.asyncio
async def test_schedule_respects_flight_and_transfer_windows():
    p=await plan_trip(trip())
    arrival=datetime.fromisoformat(p["selected"]["flights"][0]["arrival"])
    for day in p["itinerary"]:
        last_end=None
        for item in day["items"]:
            if item["kind"]!="activity": continue
            start=datetime.fromisoformat(day["date"]+"T"+item["time"])
            end=datetime.fromisoformat(day["date"]+"T"+item["end"])
            assert start>=arrival+timedelta(hours=3)
            assert end>start
            if last_end: assert start>=last_end+timedelta(hours=1)
            last_end=end
    assert not any(i["kind"]=="activity" for i in p["itinerary"][-1]["items"])

class FakeModel:
    def __init__(self, invalid=False): self.calls=[]; self.invalid=invalid
    async def ask(self,instructions,payload,schema):
        import json
        data=json.loads(payload);self.calls.append(instructions)
        if schema is Allocation: return Allocation(flight_percent=45,stay_percent=40,message="Delegate by remaining budget.")
        offers=data["tool_results"]
        if self.invalid: return Selection(selected_ids=["invented-offer"],message="Invalid selection")
        # Initial model prioritizes comfort even over allowance; revision must repair.
        if offers[0]["category"]=="activities": return Selection(selected_ids=[],message="Leave activity budget free.")
        selected=min(offers,key=lambda o:o["cost"]) if data["revision"] else max(offers,key=lambda o:o["cost"])
        return Selection(selected_ids=[selected["id"]],message="Selected a supplied offer.")
    def metrics(self): return {"model_calls":len(self.calls),"input_tokens":0,"output_tokens":0,"model":"test-double","estimated_model_cost_usd":None}
    async def close(self): pass

@pytest.mark.asyncio
async def test_separate_model_calls_and_targeted_budget_revision():
    model=FakeModel()
    p=await plan_trip(trip(budget=32000),model=model)
    assert p["status"]=="within_budget"
    assert p["revision_rounds"]==1
    assert p["metrics"]["model_calls"]==6
    revised={e["to"] for e in p["events"] if e["kind"]=="revision"}
    assert revised=={"flights","stays"}
    assert any("flight specialist" in c for c in model.calls)
    assert any("accommodation specialist" in c for c in model.calls)
    assert any("activities specialist" in c for c in model.calls)

@pytest.mark.asyncio
async def test_invented_model_ids_are_rejected():
    with pytest.raises(ValueError,match="invalid offer ID"):
        await plan_trip(trip(),model=FakeModel(invalid=True))

@pytest.mark.asyncio
async def test_provider_failure_is_not_silently_replaced():
    class Broken(DemoProvider):
        async def search_flights(self,t): raise ProviderError("Search unavailable")
    with pytest.raises(ProviderError): await plan_trip(trip(),provider=Broken())



def test_money_uses_decimal_and_rejects_nonfinite():
    assert money("123.45")==12345
    with pytest.raises(ValueError): money("NaN")

def test_api_validation_streaming_and_cross_origin(monkeypatch, signed_in_client):
    monkeypatch.delenv("GROQ_API_KEY",raising=False)
    from contextlib import nullcontext
    with nullcontext(signed_in_client) as client:
        assert client.get("/").status_code==200
        assert client.get("/api/health").json()=={"status":"ok"}
        data=trip().model_dump(mode="json")
        assert client.post("/api/plan",json={**data,"budget":-1}).status_code==422
        assert client.post("/api/plan",json={**data,"mode":"ai"}).status_code==400
        assert client.post("/api/plan",json=data,headers={"Origin":"https://untrusted.example"}).status_code==403
        import json
        response=client.post("/api/plan/stream",json=data)
        messages=[json.loads(line) for line in response.text.splitlines()]
        assert messages[0]["type"]=="event"
        assert messages[-1]["type"]=="result"
        assert messages[-1]["data"]["status"]=="within_budget"

@pytest.mark.asyncio
async def test_revision_rounds_remain_bounded_when_model_wont_reduce_cost():
    class Stubborn(FakeModel):
        async def ask(self,instructions,payload,schema):
            import json
            data=json.loads(payload)
            if schema is not Allocation: data["revision"]=0
            return await super().ask(instructions,json.dumps(data),schema)
    p=await plan_trip(trip(budget=25000),model=Stubborn())
    assert p["revision_rounds"]==2
    assert p["status"]=="over_budget"

@pytest.mark.asyncio
async def test_single_call_baseline_and_team_share_accounting():
    from app.baseline import baseline_trip
    t=trip(budget=25000)
    team=await plan_trip(t)
    baseline=await baseline_trip(t)
    assert team["status"]=="within_budget"
    assert baseline["status"]=="over_budget"
    for key in ("meals","local_transport","contingency"):
        assert team["costs"][key]==baseline["costs"][key]
