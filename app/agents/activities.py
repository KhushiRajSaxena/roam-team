from .base import Specialist

class ActivityAgent(Specialist):
    role = "activities"
    instructions = "You are the activities specialist. Choose up to six different activities from your search tool results matching the user's interests and the total allowance. Fewer activities and free time are preferable to exceeding the allowance. Report your selection to the orchestrator. Do not claim verified opening hours or bookability."

    def choose(self, candidates, trip, cap, revision):
        ordered = sorted(candidates, key=lambda o: (not bool(set(o.tags) & set(trip.interests)), o.cost))
        selected, spent = [], 0
        for offer in ordered:
            if spent + offer.cost <= cap and len(selected) < min(6, trip.nights * 2):
                selected.append(offer)
                spent += offer.cost
        return selected
