from .base import Specialist

class FlightAgent(Specialist):
    role = "flights"
    instructions = "You are the flight specialist. Use your flight search results to choose a round-trip fare for all travelers. Balance price, stops and usable arrival/departure time. Report your selection to the orchestrator. Your scope is flights only."
