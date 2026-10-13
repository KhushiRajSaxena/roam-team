"""Validated contracts; monetary values are integer INR minor units (paise)."""
from datetime import date, datetime, timezone
from typing import Literal
from pydantic import BaseModel, Field, ConfigDict, model_validator

CITIES = {
    "GOI": {"name": "Goa", "country": "India", "city": "GOI", "lat": 15.49, "lon": 73.83, "flight": 8500, "stay": 2800, "daily": 1200},
    "JAI": {"name": "Jaipur", "country": "India", "city": "JAI", "lat": 26.91, "lon": 75.79, "flight": 6500, "stay": 2300, "daily": 1100},
    "DPS": {"name": "Bali", "country": "Indonesia", "city": "DPS", "lat": -8.65, "lon": 115.22, "flight": 30000, "stay": 3800, "daily": 2000},
    "CDG": {"name": "Paris", "country": "France", "city": "PAR", "lat": 48.86, "lon": 2.35, "flight": 56000, "stay": 10500, "daily": 5000},
    "HND": {"name": "Tokyo", "country": "Japan", "city": "TYO", "lat": 35.68, "lon": 139.76, "flight": 49000, "stay": 8000, "daily": 4000},
}
# Bundled public-domain OurAirports catalog; no lookup API is called while typing.
import json
from pathlib import Path
AIRPORTS = json.loads((Path(__file__).parent / 'data' / 'airports.json').read_text())
for code, airport in AIRPORTS.items():
    if code not in CITIES:
        domestic = airport['country_code'] == 'IN'
        CITIES[code] = {**airport, 'city': code, 'geocode': True,
                       'flight': 8500 if domestic else 45000,
                       'stay': 2800 if domestic else 7000,
                       'daily': 1200 if domestic else 3500}
    else:
        CITIES[code].update({key: airport[key] for key in ('airport', 'country_code')})
ORIGINS = {code: city['name'] for code, city in CITIES.items()}

class TripRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    origin: str = "DEL"
    destination: str = "GOI"
    start: date
    end: date
    budget: int = Field(ge=1000, le=10_000_000)
    travelers: int = Field(default=1, ge=1, le=4)
    interests: list[Literal["nature", "culture", "food", "adventure"]] = Field(default_factory=lambda: ["nature", "culture"], max_length=4)
    mode: Literal["demo", "ai", "live"] = "demo"

    @model_validator(mode="after")
    def dates_valid(self):
        self.origin = self.origin.strip().upper()
        self.destination = self.destination.strip().upper()
        if self.origin not in ORIGINS or self.destination not in CITIES:
            raise ValueError("Choose an airport from the location suggestions.")
        if self.origin == self.destination:
            raise ValueError("Departure and destination airports must be different.")
        if self.start <= date.today():
            raise ValueError("Departure must be after today.")
        if not 1 <= (self.end - self.start).days <= 14:
            raise ValueError("Choose a trip of 1 to 14 nights, with return after departure.")
        if (self.start - date.today()).days > 330:
            raise ValueError("Choose departure within the next 330 days.")
        return self

    @property
    def nights(self): return (self.end - self.start).days

    @property
    def money(self): return self.budget * 100

class Offer(BaseModel):
    id: str
    category: Literal["flights", "stays", "activities"]
    title: str
    cost: int = Field(ge=0)
    description: str
    source: str
    retrieved_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    sample: bool = True
    url: str | None = None
    # Airport-local timestamps; only same-day arrival is supported in this release.
    arrival: str | None = None
    departure: str | None = None
    outbound_departure: str | None = None
    return_arrival: str | None = None
    tags: list[str] = Field(default_factory=list)
    duration_minutes: int = Field(default=120, ge=15, le=720)
    location: str = "Central area"
    availability_verified: bool = False
    price_kind: Literal["sample", "search_price", "estimate", "listed_free"] = "sample"
    latitude: float | None = None
    longitude: float | None = None
    opening_hours: str | None = None
    rating: float | None = None

class Selection(BaseModel):
    selected_ids: list[str]
    message: str

class Allocation(BaseModel):
    flight_percent: int = Field(ge=20, le=65)
    stay_percent: int = Field(ge=15, le=60)
    message: str

class Event(BaseModel):
    agent: str
    to: str = "orchestrator"
    kind: str
    message: str
    round: int = 0
    at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
