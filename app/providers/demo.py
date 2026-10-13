"""Synthetic fixtures. None of these prices, operators or hours are live facts."""
import math
from app.models import CITIES, Offer, TripRequest

class DemoProvider:
    async def search_flights(self, trip: TripRequest):
        c = CITIES[trip.destination]
        multiplier = {"DEL": 1, "BOM": .94, "BLR": 1.06, "LHR": 1.8, "JFK": 2.7}.get(trip.origin, 1.0)
        base = round(c["flight"] * multiplier) * 100 * trip.travelers
        return [Offer(id=f"flight-{i}", category="flights", title=title, cost=round(base * factor),
            description=f"{trip.origin} → {trip.destination} → {trip.origin} · Round trip · {trip.travelers} adult(s). Fictional schedule and fare; baggage not priced.",
            arrival=f"{trip.start}T{arrival}:00:00", departure=f"{trip.end}T{departure}:00:00",
            outbound_departure=f"{trip.start}T06:00:00", return_arrival=f"{trip.end}T23:00:00",
            source="Synthetic flight catalog", tags=["economy"])
            for i, (title, factor, arrival, departure) in enumerate([
                ("Sample Saver · Economy", 1, "16", "13"),
                ("Sample Connect · Economy", 1.25, "12", "17"),
                ("Sample Direct · Economy", 1.55, "10", "19")])]

    async def search_stays(self, trip: TripRequest):
        c = CITIES[trip.destination]
        rooms = math.ceil(trip.travelers / 2)
        return [Offer(id=f"stay-{i}", category="stays", title=f"{c['name']} {name} (sample)",
            cost=round(c["stay"] * factor) * 100 * rooms * trip.nights,
            description=f"{rooms} private room(s) · {trip.nights} nights · {trip.travelers} adult(s). Check-in 15:00, checkout 11:00 are planning assumptions.",
            source="Synthetic accommodation catalog", location="Central area", tags=["private room"])
            for i, (name, factor) in enumerate([("Guesthouse", .65), ("Courtyard Hotel", 1), ("Garden Retreat", 1.65)])]

    async def search_activities(self, trip: TripRequest):
        c = CITIES[trip.destination]
        themes = {
            "GOI": ["Coastal nature walk", "Old quarter heritage walk", "Local flavors tour", "Kayaking session", "Sunset by the shore", "Art and craft visit"],
            "JAI": ["Garden walk", "Old city heritage walk", "Local flavors tour", "Hill trail", "Sunset viewpoint", "Craft workshop"],
            "DPS": ["Rice terrace walk", "Village culture walk", "Local flavors tour", "Beginner surf session", "Sunset beach walk", "Craft workshop"],
            "CDG": ["Riverside walk", "Architecture walk", "Neighborhood food tour", "City cycling session", "Garden afternoon", "Gallery visit"],
            "HND": ["Park walk", "Historic district walk", "Neighborhood food tour", "City cycling session", "Waterfront sunset", "Design gallery visit"],
        }
        prices = [0, 600, 1400, 2000, 0, 900]
        tags = ["nature", "culture", "food", "adventure", "nature", "culture"]
        return [Offer(id=f"activity-{i}", category="activities", title=name,
            cost=round(prices[i] * c["daily"] / 1200) * 100 * trip.travelers,
            description="Suggested two-hour block with a one-hour transfer buffer. Sample timing and fee; confirm location, opening hours and access before travel.",
            source="Synthetic activity catalog", tags=[tags[i]], location="Central area") for i, name in enumerate(themes.get(trip.destination, ["Park walk", "Historic district walk", "Neighborhood food tour", "City cycling session", "Garden afternoon", "Gallery visit"]))]
