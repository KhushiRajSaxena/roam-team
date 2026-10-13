from .base import Specialist

class StayAgent(Specialist):
    role = "stays"
    instructions = "You are the accommodation specialist. Choose a stay covering every night and all adults. Compare total trip prices, location and room details. Report your selection to the orchestrator. Your scope is accommodation only."
