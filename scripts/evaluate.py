"""python -m scripts.evaluate [--mode ai --compare] [--output docs/evaluation.json]"""
import argparse
import asyncio
import json
from datetime import date, timedelta, datetime, timezone
from pathlib import Path
from dotenv import load_dotenv
from app.models import TripRequest
from app.agents.orchestrator import plan_trip
from app.baseline import baseline_trip

SCENARIOS=[("goa-comfort","GOI",45000,1,4),("goa-tight","GOI",25000,1,4),
    ("unaffordable","GOI",1000,1,4),("jaipur-pair","JAI",65000,2,3),
    ("bali-week","DPS",160000,2,6),("paris-short","CDG",180000,1,3),
    ("tokyo-group","HND",500000,4,5),("one-night","GOI",25000,1,1)]

def score(plan):
    conflicts=0
    for day in plan["itinerary"]:
        timed=[i for i in day["items"] if i["kind"]=="activity"]
        for previous,current in zip(timed,timed[1:]):
            if previous["end"]>current["time"]: conflicts+=1
    return {"status":plan["status"],"budget_compliant":plan["checks"]["budget_compliant"],
        "schedule_conflicts":conflicts,"total_paise":plan["total"],"revision_rounds":plan["revision_rounds"],**plan["metrics"]}

async def main(args):
    load_dotenv()
    rows=[]
    for name,destination,budget,travelers,nights in SCENARIOS:
        start=date.today()+timedelta(days=30)
        trip=TripRequest(destination=destination,budget=budget,travelers=travelers,start=start,end=start+timedelta(days=nights),mode=args.mode)
        row={"scenario":name,"expected_affordable":name!="unaffordable"}
        for label,runner in [("team",plan_trip)]+([("baseline",baseline_trip)] if args.compare else []):
            try: row[label]=score(await runner(trip))
            except Exception as exc: row[label]={"error":str(exc)}
        rows.append(row)
    result={"generated_at":datetime.now(timezone.utc).isoformat(),"mode":args.mode,
        "data":"Synthetic fixtures; not live travel prices.",
        "baseline_type":"Single model call on identical fixtures" if args.mode=="ai" else "Rule-based ablation with identical initial allocations, without revisions; not an AI baseline",
        "limitations":"Small illustrative scenario set, one run per case. No statistically significant quality claim. Schedule score checks block overlap only, not real opening hours or travel times.","scenarios":rows}
    path=Path(args.output);path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(result,indent=2)+"\n")
    print(f"Saved {len(rows)} scenarios to {path}")
    for row in rows: print(row["scenario"],row["team"].get("status", "error"),row["team"].get("revision_rounds",""))

if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--mode",choices=["demo","ai"],default="demo")
    parser.add_argument("--compare",action="store_true")
    parser.add_argument("--output",default="docs/evaluation.json")
    asyncio.run(main(parser.parse_args()))
