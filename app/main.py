"""Local API and same-origin web interface."""
import asyncio
import json
import os
from pathlib import Path
from contextlib import suppress
from app.settings import key_status, setting
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import StreamingResponse, JSONResponse
from fastapi.exceptions import RequestValidationError
from pydantic import BaseModel, Field, ConfigDict
from app.security import SecurityMiddleware, SecurityStore, Denied, COOKIE, guarded
from fastapi.staticfiles import StaticFiles
from starlette.middleware.trustedhost import TrustedHostMiddleware
from app.models import TripRequest, CITIES, ORIGINS
from app.agents.orchestrator import plan_trip
from app.providers import ProviderError
from app.llm import ModelError
from app.services.cache import Store


app = FastAPI(title="Roam Team", version="0.2.0", docs_url=None, redoc_url=None, openapi_url=None)
app.add_middleware(TrustedHostMiddleware, allowed_hosts=["127.0.0.1", "localhost", "testserver"])
app.add_middleware(SecurityMiddleware)

@app.exception_handler(RequestValidationError)
async def invalid_request(request, exc):
    return JSONResponse({"detail": "Invalid request. Check dates, airports, budget and required fields."}, status_code=422)

class Login(BaseModel):
    model_config = ConfigDict(extra='forbid')
    username: str = Field(min_length=3, max_length=64)
    password: str = Field(min_length=1, max_length=128)

@app.post('/api/auth/login')
def login(data: Login, request: Request):
    store=SecurityStore()
    try: token,csrf=store.login(data.username,data.password)
    except Denied as exc: raise HTTPException(exc.status,exc.message) from None
    old=request.cookies.get(COOKIE)
    if old:
        try:store.revoke(store.session(old))
        except Denied:pass
    response=JSONResponse({'username':data.username,'csrf':csrf})
    response.set_cookie(COOKIE,token,httponly=True,secure=request.url.scheme=='https',samesite='strict',max_age=8*3600,path='/')
    return response

@app.get('/api/auth/session')
def session(request: Request):
    return {'username':request.state.user['username'],'csrf':request.state.user['csrf']}

@app.post('/api/auth/logout')
def logout(request: Request):
    SecurityStore().revoke(request.state.user)
    response=JSONResponse({'ok':True});response.delete_cookie(COOKIE,path='/');return response

@app.post('/api/auth/logout-all')
def logout_all(request: Request):
    SecurityStore().revoke(request.state.user,all_sessions=True)
    response=JSONResponse({'ok':True});response.delete_cookie(COOKIE,path='/');return response

def safe_error(exc):
    message=str(exc)
    for key in ('GROQ_API_KEY','SERPAPI_API_KEY','GEOAPIFY_API_KEY'):
        value=setting(key)
        if value:message=message.replace(value,'[redacted]')
    return message[:500]

@app.get("/api/health")
def health():
    return {"status": "ok"}

@app.get("/api/config")
def config():
    keys = key_status()
    return {"ai_available": keys["GROQ_API_KEY"], "live_available": all(keys.values()),
        "keys_configured": keys, "missing_keys": [key for key, present in keys.items() if not present],
        "config_version": 3, "ai_provider": "Groq", "destinations": CITIES, "origins": ORIGINS}

@app.get("/api/usage")
def usage():
    return {"providers": Store().stats(), "note": "Local conservative reservations, including failed attempts. Usage in other apps is not included; SerpApi's account balance is also checked before uncached searches.",
        "cache_hours": {"flight_and_hotel": 6, "places": 168, "routes": 24, "ai_decisions": 24}, "max_serpapi_searches_per_trip": 3}

def check_mode(trip):
    options = config()
    if trip.mode == "ai" and not options["ai_available"]:
        raise HTTPException(400, "Add GROQ_API_KEY to the local .env file to enable AI mode.")
    if trip.mode == "live" and not options["live_available"]:
        raise HTTPException(400, "Live mode requires GROQ_API_KEY, SERPAPI_API_KEY and GEOAPIFY_API_KEY in the local .env file.")

@app.post("/api/plan")
async def plan(trip: TripRequest, request: Request):
    check_mode(trip)
    try:
        return await guarded(plan_trip(trip),request.state.user['digest'])
    except Denied as exc:
        raise HTTPException(exc.status,exc.message) from None
    except (ProviderError, ModelError, ValueError) as exc:
        raise HTTPException(502, safe_error(exc)) from None
    except TimeoutError as exc:
        raise HTTPException(504, "Planning timed out. Please try again.") from exc

@app.post("/api/plan/stream")
async def stream(trip: TripRequest, request: Request):
    check_mode(trip)
    async def generate():
        queue = asyncio.Queue(maxsize=64)
        async def callback(event): await queue.put({"type": "event", "data": event})
        async def run():
            try:
                result = await guarded(plan_trip(trip, callback),request.state.user['digest'])
                await queue.put({"type": "result", "data": result})
            except (ProviderError, ModelError, ValueError, Denied) as exc:
                await queue.put({"type": "error", "data": exc.message if isinstance(exc,Denied) else safe_error(exc)})
            except TimeoutError:
                await queue.put({"type": "error", "data": "Planning timed out. Please try again."})
            except Exception:
                await queue.put({"type": "error", "data": "Planning failed unexpectedly. Check the local server logs."})

            finally: await queue.put(None)
        task = asyncio.create_task(run())
        try:
            while True:
                item = await queue.get()
                if item is None: break
                yield json.dumps(item) + "\n"
        finally:
            task.cancel()
            with suppress(asyncio.CancelledError): await task
    return StreamingResponse(generate(), media_type="application/x-ndjson", headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"})

app.mount("/", StaticFiles(directory=Path(__file__).resolve().parents[1] / "dist", html=True), name="web")
