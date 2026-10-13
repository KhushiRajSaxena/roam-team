"""Deterministic accounting and scheduling. Models cannot override these checks."""
from datetime import datetime, timedelta
from app.models import CITIES

def allowances(trip):
    daily = CITIES[trip.destination]["daily"] * 100 * trip.travelers
    return {"meals": daily * (trip.nights + 1) * 2 // 3,
            "local_transport": daily * (trip.nights + 1) // 3,
            "contingency": trip.money // 10}

def selected_cost(result): return sum(o.cost for o in result.get("selected", []))

def schedule(trip, flight, activities):
    """Airport-local schedule with 3h arrival/departure buffers and 1h between outings.

    No route-time or hours verification is implied. Unplaceable paid activities are
    dropped before accounting, so the user is never charged for an unscheduled item.
    """
    pending = list(activities)
    included = []
    days = []
    arrival = datetime.fromisoformat(flight.arrival) if flight else None
    departure = datetime.fromisoformat(flight.departure) if flight else None
    for index in range(trip.nights + 1):
        day = trip.start + timedelta(days=index)
        start = datetime.combine(day, datetime.min.time()).replace(hour=9)
        end = start.replace(hour=19)
        items = []
        if index == 0:
            if arrival:
                start = max(start.replace(hour=15), arrival.replace(tzinfo=None) + timedelta(hours=3))
                items.append({"time": arrival.strftime("%H:%M"), "end": start.strftime("%H:%M"), "title": "Arrival, transfer & check-in", "description": "Three hours reserved after landing; hotel check-in assumed from 15:00. Confirm transfer and check-in details.", "cost": 0, "kind": "travel"})
            else:
                start = start.replace(hour=17)
                items.append({"time": "TBC", "end": "TBC", "title": "Arrival & check-in to confirm", "description": "No flight selected. All itinerary times are provisional.", "cost": 0, "kind": "travel"})
        if index == trip.nights:
            # Keep departure day flexible; don't assume luggage storage or late checkout.
            items.append({"time": min(11, max(0, departure.hour - 3)).__format__("02d") + ":00" if departure else "11:00", "end": "", "title": "Check out & leave for the airport", "description": f"Return flight departs {departure.strftime('%H:%M')}; allow at least three hours for transfer and airport formalities." if departure else "Return flight missing. Confirm checkout and airport transfer time.", "cost": 0, "kind": "travel"})
            end = start
        cursor = start
        count = 0
        while pending and count < 2:
            offer = pending[0]
            finish = cursor + timedelta(minutes=offer.duration_minutes)
            if finish > end: break
            pending.pop(0)
            included.append(offer)
            items.append({"time": cursor.strftime("%H:%M"), "end": finish.strftime("%H:%M"), "title": offer.title,
                "description": offer.description, "cost": offer.cost, "kind": "activity", "offer_id": offer.id,
                "source": offer.source, "url": offer.url, "price_kind": offer.price_kind,
                "opening_hours": offer.opening_hours, "location": offer.location})
            cursor = finish + timedelta(hours=1)
            count += 1
        if index < trip.nights:
            items.append({"time": "Flexible", "end": "", "title": "Meals & time to explore", "description": "Keep unscheduled time for meals, rest and local discoveries. Meals and local transport are included as daily allowances.", "cost": 0, "kind": "free_time"})
        days.append({"date": str(day), "day": index + 1, "title": "Arrive & settle in" if index == 0 else "Heading home" if index == trip.nights else "Explore at your pace", "items": items})
    return days, included, pending

def assemble(trip, results, rounds):
    flights = results["flights"]["selected"]
    stays = results["stays"]["selected"]
    days, activities, dropped = schedule(trip, flights[0] if flights else None, results["activities"]["selected"])
    costs = {"flights": sum(o.cost for o in flights), "stays": sum(o.cost for o in stays), "activities": sum(o.cost for o in activities), **allowances(trip)}
    total = sum(costs.values())
    missing = [role for role in ("flights", "stays") if not results[role]["selected"]]
    status = "incomplete" if missing else "over_budget" if total > trip.money else "within_budget"
    notes = ["Sample offers are fictional and cannot be booked." if trip.mode != "live" else "Search prices are not bookings. Reconfirm fares, room totals and availability with each operator.",
        "Meals and local transport are destination-based planning allowances, not quotes. A 10% contingency is included.",
        "Activity admission and opening hours need confirmation. Two-hour visits are suggested; unknown entry fees have explicit allowances, not zero prices.",
        "Only outbound flights arriving on the departure date are supported. Departure day is reserved for checkout and return travel.",
        "Baggage, visas, insurance and origin-airport transport are not priced; add them before treating this as a complete travel budget."]
    if trip.mode == "demo": notes.append("Demo specialists use deterministic selection rules. Enable AI mode for separate model calls by the orchestrator and specialists.")
    if trip.mode == "live":
        notes.append("Searches cover one selected outbound flight and the first hotel results page to conserve your quota; this is not an exhaustive cheapest-fare search.")
        notes.append("Cached flight/hotel results may be up to six hours old. Geoapify places are cached for seven days. Always recheck prices on the provider page.")
    for role, result in results.items():
        if result.get("error"): notes.append(f"{role.title()} search unavailable: {result['error']}")
    if missing: notes.append("Missing " + ", ".join(missing) + ": the displayed total is a partial estimate, not a feasible complete trip.")
    if not activities: notes.append("No priced activities fit the available time or allowance. Free-time suggestions remain unpriced and unverified.")
    if dropped: notes.append(f"Removed {len(dropped)} activities that could not fit around flight times; their costs are excluded.")
    if total > trip.money: notes.append(f"This selection exceeds the budget by ₹{(total-trip.money)/100:,.0f}. Increase the budget, reduce nights or try another destination; affordability is not guaranteed.")
    plan = {"request": trip.model_dump(mode="json"), "destination_name": CITIES[trip.destination]["name"], "status": status,
        "currency": "INR", "money_unit": "paise", "costs": costs, "total": total, "remaining": trip.money - total,
        "selected": {"flights": [o.model_dump() for o in flights], "stays": [o.model_dump() for o in stays], "activities": [o.model_dump() for o in activities]},
        "alternatives": {role: [o.model_dump() for o in result["candidates"] if o.id not in {s.id for s in result["selected"]}][:3] for role, result in results.items()},
        "itinerary": days, "notes": notes, "revision_rounds": rounds,
        "checks": {"budget_compliant": total <= trip.money and not missing, "required_options_present": not missing, "activity_schedule_nonoverlapping": False, "live_availability_verified": False}}
    validate_plan(plan)
    return plan

def validate_plan(plan):
    """Check actual output, independent of the scheduler implementation."""
    ids=[]
    amount=0
    for day in plan["itinerary"]:
        previous=None
        for item in sorted((i for i in day["items"] if i["kind"]=="activity"), key=lambda i:i["time"]):
            start=datetime.fromisoformat(day["date"]+"T"+item["time"])
            end=datetime.fromisoformat(day["date"]+"T"+item["end"])
            if end<=start or (previous and start<previous+timedelta(hours=1)):
                raise ValueError("Activity schedule contains a conflict or insufficient transfer time.")
            if day["date"]==plan["request"]["end"]:
                raise ValueError("Activities cannot overlap departure-day travel.")
            flights=plan["selected"]["flights"]
            if flights and start<datetime.fromisoformat(flights[0]["arrival"]).replace(tzinfo=None)+timedelta(hours=3):
                raise ValueError("Activity starts before the arrival buffer ends.")
            previous=end
            ids.append(item["offer_id"])
            amount+=item["cost"]
    if len(ids)!=len(set(ids)): raise ValueError("An activity was scheduled more than once.")
    if set(ids)!={o["id"] for o in plan["selected"]["activities"]}: raise ValueError("Activity selection and itinerary disagree.")
    if amount!=plan["costs"]["activities"] or sum(plan["costs"].values())!=plan["total"]:
        raise ValueError("Itinerary accounting does not match selected activities.")
    plan["checks"]["activity_schedule_nonoverlapping"]=True

async def enrich_routes(plan, trip, provider):
    """At most one basic routing call per activity day; no isochrones or matrices."""
    import math
    from app.providers.errors import ProviderError
    stay=(plan["selected"]["stays"] or [None])[0]
    by_id={o["id"]:o for o in plan["selected"]["activities"]}
    if not stay or stay.get("latitude") is None or stay.get("longitude") is None:
        plan["notes"].append("Hotel coordinates unavailable; transfers use provisional one-hour buffers.")
        return
    dropped=[]
    for day in plan["itinerary"]:
        items=[i for i in day["items"] if i["kind"]=="activity"]
        if not items: continue
        places=[by_id[i["offer_id"]] for i in items]
        if any(o.get("latitude") is None or o.get("longitude") is None for o in places): continue
        home=(stay["latitude"],stay["longitude"])
        points=[home]+[(o["latitude"],o["longitude"]) for o in places]+[home]
        try: route=await provider.route(points)
        except ProviderError as exc:
            plan["notes"].append(f"Route estimate unavailable: {exc} One-hour buffers remain provisional.")
            continue
        if not route: continue
        day["route"]=route
        cursor=datetime.fromisoformat(day["date"]+"T09:00")
        if day["day"]==1:
            flights=plan["selected"]["flights"]
            cursor=cursor.replace(hour=15)
            if flights: cursor=max(cursor,datetime.fromisoformat(flights[0]["arrival"]).replace(tzinfo=None)+timedelta(hours=3))
        closing=cursor.replace(hour=19,minute=0)
        for index,item in enumerate(items):
            transfer=max(60,math.ceil(route["legs"][index]["minutes"]*1.3)+15)
            start=cursor+timedelta(minutes=transfer)
            finish=start+timedelta(minutes=by_id[item["offer_id"]]["duration_minutes"])
            return_buffer=sum(math.ceil(l["minutes"]*1.3)+15 for l in route["legs"][index+1:])
            if finish+timedelta(minutes=return_buffer)>closing:
                dropped.extend(i["offer_id"] for i in items[index:])
                route["includes_unscheduled_stops"]=True
                break
            item["time"],item["end"]=start.strftime("%H:%M"),finish.strftime("%H:%M")
            item["transfer_minutes"]=transfer
            cursor=finish
    if dropped:
        for day in plan["itinerary"]: day["items"]=[i for i in day["items"] if i.get("offer_id") not in dropped]
        plan["selected"]["activities"]=[o for o in plan["selected"]["activities"] if o["id"] not in dropped]
        plan["costs"]["activities"]=sum(o["cost"] for o in plan["selected"]["activities"])
        plan["total"]=sum(plan["costs"].values())
        plan["remaining"]=trip.money-plan["total"]
        if plan["checks"]["required_options_present"]:
            plan["status"]="within_budget" if plan["remaining"]>=0 else "over_budget"
            plan["checks"]["budget_compliant"]=plan["remaining"]>=0
        plan["notes"]=[n for n in plan["notes"] if not n.startswith("This selection exceeds")]
        if plan["remaining"]<0: plan["notes"].append(f"This selection exceeds the budget by ₹{-plan['remaining']/100:,.0f}.")
        plan["notes"].append(f"Removed {len(dropped)} activities after route estimates showed insufficient time. Their allowances are excluded.")
    plan["notes"].append("Driving routes are estimates, not live traffic. Transfer blocks include a safety buffer. Listed opening hours are not date-specific confirmations.")
    validate_plan(plan)
