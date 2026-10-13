# Three-minute project walkthrough

1. Open the planner. Explain the departure, destination, date, adult-count, budget and interest inputs. Point out the sample-data badge.
2. Choose New Delhi → Goa, four nights, one adult and ₹45,000. Click **Build my trip**. Expand the team conversation and show separate specialist events.
3. Inspect the flight, hotel, daily activity blocks and all six cost categories. Explain that calculations and schedule checks run in code rather than relying on a model's arithmetic.
4. Repeat at ₹25,000 to see a budget revision. At ₹1,000, the planner must report the trip as unaffordable rather than invent cheaper prices.
5. Show `app/agents/orchestrator.py`: parallel branches, shared-state join and targeted bounded revisions. Explain that demo uses deterministic selectors; AI mode makes independent structured calls.
6. Show `docs/evaluation.json` and describe its limits. A rule-based ablation is not proof that a multi-agent AI system outperforms one AI agent.
7. Select Live search to demonstrate Groq, SerpApi and Geoapify. Repeat identical inputs to show zero new API calls. Show docs/live-validation.json as the measured example.

## Engineering decisions to discuss

- Separate agent contracts and domain-specific retrieval tools make responsibilities inspectable.
- Validating selected IDs prevents fabricated offers from becoming authoritative results.
- The orchestrator owns allocation and revisions; deterministic validators own math and schedule feasibility checks.
- Bounded rounds and cached search results limit cost and latency.
- All paid items in the final activity cost appear in the actual schedule; unplaceable activities are removed before final totals.
- Missing data, estimated costs and fictional offers are visible to the user.

## Next milestones

Expand the geographic test set and evaluation repeats, add date-specific opening-hour validation, then introduce authenticated hosting and saved trips. Multi-city travel and booking are separate features.
