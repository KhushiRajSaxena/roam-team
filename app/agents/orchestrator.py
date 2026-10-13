"""LangGraph fan-out/fan-in with bounded, targeted specialist revisions."""
import json
import time
from typing import TypedDict
from langgraph.graph import StateGraph, START, END
from app.models import Event, Allocation
from app.providers import provider_for
from app.llm import ModelClient
from app.planning import allowances, selected_cost, assemble, enrich_routes
from .flights import FlightAgent
from .stays import StayAgent
from .activities import ActivityAgent

class State(TypedDict, total=False):
    caps: dict
    round: int
    targets: list[str]
    flights: dict
    stays: dict
    activities: dict
    retry: bool
    plan: dict

async def plan_trip(trip, callback=None, provider=None, model=None):
    start = time.perf_counter()
    events = []
    current_round = 0
    model = model or (ModelClient() if trip.mode != "demo" else None)
    provider = provider or provider_for(trip.mode)

    async def emit(agent, kind, message, to="orchestrator"):
        event = Event(agent=agent, kind=kind, message=message, round=current_round, to=to).model_dump()
        events.append(event)
        if callback: await callback(event)

    async def allocate(state):
        await emit("orchestrator", "started", "Reserving meals, local transport and a 10% contingency, then assigning the specialists.", "team")
        available = max(0, trip.money - sum(allowances(trip).values()))
        flight_share, stay_share = 45, 40
        if model:
            decision = await model.ask("You coordinate a travel-planning team. Allocate the remaining budget between flights and accommodation, leaving at least 5% for activities. flight_percent + stay_percent must be <=95. Consider the destination, dates and number of adults. Return a brief delegation summary, not private reasoning.",
                json.dumps({"trip": trip.model_dump(mode="json"), "available_paise": available}), Allocation)
            if decision.flight_percent + decision.stay_percent > 95:
                raise ValueError("Orchestrator returned an invalid allocation.")
            flight_share, stay_share = decision.flight_percent, decision.stay_percent
            await emit("orchestrator", "delegation", decision.message, "team")
        caps = {"flights": available * flight_share // 100, "stays": available * stay_share // 100}
        caps["activities"] = available - sum(caps.values())
        for role, cap in caps.items(): await emit("orchestrator", "delegation", f"Find {role} options within ₹{cap / 100:,.0f}; report total costs and constraints.", role)
        return {"caps": caps, "round": 0, "targets": ["flights", "stays", "activities"]}

    def specialist_node(agent):
        async def run(state):
            if agent.role not in state["targets"]: return {}
            cached = state.get(agent.role, {}).get("candidates")
            return {agent.role: await agent.run(trip, state["caps"][agent.role], state["round"], provider, model, emit, cached)}
        return run

    async def review(state):
        nonlocal current_round
        fixed = sum(allowances(trip).values())
        costs = {r: selected_cost(state[r]) for r in ("flights", "stays", "activities")}
        total = fixed + sum(costs.values())
        missing = [r for r in ("flights", "stays") if not state[r]["selected"]]
        await emit("orchestrator", "review", f"Combined estimate: ₹{total / 100:,.0f} against ₹{trip.budget:,.0f}. Checking required options and budget.", "team")
        if total <= trip.money or state["round"] >= 2 or missing:
            return {"retry": False}
        # Only revisits categories where the search actually found a cheaper choice.
        targets = [r for r in ("flights", "stays") if state[r]["candidates"] and min(o.cost for o in state[r]["candidates"]) < costs[r]]
        if costs["activities"] > 0: targets.append("activities")
        if not targets: return {"retry": False}
        current_round = state["round"] + 1
        caps = dict(state["caps"])
        for role in targets:
            caps[role] = min(o.cost for o in state[role]["candidates"]) if role != "activities" else 0
            await emit("orchestrator", "revision", f"Trip is ₹{(total-trip.money)/100:,.0f} over budget. Revise {role} toward ₹{caps[role]/100:,.0f}; preserve dates and traveler count.", role)
        return {"caps": caps, "round": current_round, "targets": targets, "retry": True}

    async def finalize(state):
        plan = assemble(trip, {r: state[r] for r in ("flights", "stays", "activities")}, state["round"])
        if hasattr(provider, "route"):
            await emit("orchestrator", "review", "Checking driving routes for the selected activity days using Geoapify.", "team")
            await enrich_routes(plan, trip, provider)
        await emit("orchestrator", "completed", f"Itinerary assembled: {plan['status'].replace('_',' ')}. Scheduled activities around flights and checked the cost totals.", "user")
        return {"plan": plan}

    graph = StateGraph(State)
    graph.add_node("allocate", allocate)
    graph.add_node("dispatch", lambda state: {})
    for agent in [FlightAgent(), StayAgent(), ActivityAgent()]:
        graph.add_node(agent.role, specialist_node(agent))
        graph.add_edge("dispatch", agent.role)
    graph.add_node("review", review)
    graph.add_node("finalize", finalize)
    graph.add_edge(START, "allocate")
    graph.add_edge("allocate", "dispatch")
    graph.add_edge(["flights", "stays", "activities"], "review")
    graph.add_conditional_edges("review", lambda s: "dispatch" if s["retry"] else "finalize")
    graph.add_edge("finalize", END)
    try:
        state = await graph.compile().ainvoke({}, {"recursion_limit": 20})
        plan = state["plan"]
        plan["events"] = events
        plan["metrics"] = {"latency_seconds": round(time.perf_counter()-start, 3), "event_count": len(events),
            **(model.metrics() if model else {"model_calls": 0, "input_tokens": 0, "output_tokens": 0, "model": None, "estimated_model_cost_usd": 0})}
        plan["metrics"].update(getattr(provider, "counts", {}))
        return plan
    finally:
        if hasattr(provider, "close"): await provider.close()
        if model: await model.close()
