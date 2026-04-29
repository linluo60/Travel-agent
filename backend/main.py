import os

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field


app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:5500",
        "http://localhost:5500",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

OLLAMA_MODEL = "llama3.2:3b"
OLLAMA_TIMEOUT_SECONDS = 300
GEOCODING_TIMEOUT_SECONDS = 20
PLACES_TIMEOUT_SECONDS = 30
WEATHER_TIMEOUT_SECONDS = 20
ROUTING_TIMEOUT_SECONDS = 30
SEARCH_RADIUS_METERS = 5000

WEATHER_CODE_MAP = {
    0: "clear sky",
    1: "mainly clear",
    2: "partly cloudy",
    3: "overcast",
    45: "fog",
    48: "depositing rime fog",
    51: "light drizzle",
    53: "moderate drizzle",
    55: "dense drizzle",
    56: "light freezing drizzle",
    57: "dense freezing drizzle",
    61: "slight rain",
    63: "moderate rain",
    65: "heavy rain",
    66: "light freezing rain",
    67: "heavy freezing rain",
    71: "slight snow fall",
    73: "moderate snow fall",
    75: "heavy snow fall",
    77: "snow grains",
    80: "slight rain showers",
    81: "moderate rain showers",
    82: "violent rain showers",
    85: "slight snow showers",
    86: "heavy snow showers",
    95: "thunderstorm",
    96: "thunderstorm with slight hail",
    99: "thunderstorm with heavy hail",
}


class TripRequest(BaseModel):
    origin: str = Field(..., description="Where the user starts from")
    destination: str = Field(..., description="Where the user wants to go")
    days: int = Field(..., gt=0, le=14)
    budget: float = Field(..., gt=0)
    travelers: int = Field(1, gt=0, le=10)
    interests: list[str] = Field(default_factory=list)


@app.get("/")
def root():
    return {"message": "Free travel agent backend is running."}


async def get_coordinates(city_name: str):
    url = "https://geocoding-api.open-meteo.com/v1/search"
    params = {
        "name": city_name,
        "count": 1,
        "language": "en",
        "format": "json",
    }

    async with httpx.AsyncClient(timeout=GEOCODING_TIMEOUT_SECONDS) as client:
        response = await client.get(url, params=params)
        response.raise_for_status()
        data = response.json()

    results = data.get("results")
    if not results:
        raise HTTPException(status_code=404, detail=f"Could not find location: {city_name}")

    place = results[0]
    return {
        "name": place.get("name"),
        "country": place.get("country"),
        "latitude": place.get("latitude"),
        "longitude": place.get("longitude"),
    }


async def get_weather_forecast(latitude: float, longitude: float):
    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": latitude,
        "longitude": longitude,
        "current": "temperature_2m,weather_code,wind_speed_10m",
        "daily": "weather_code,temperature_2m_max,temperature_2m_min,precipitation_probability_max",
        "forecast_days": 7,
        "timezone": "auto",
    }

    async with httpx.AsyncClient(timeout=WEATHER_TIMEOUT_SECONDS) as client:
        response = await client.get(url, params=params)
        response.raise_for_status()
        return response.json()


async def search_geoapify_places(latitude: float, longitude: float, categories: str, limit: int = 5):
    api_key = os.getenv("GEOAPIFY_API_KEY")
    if not api_key:
        raise HTTPException(
            status_code=500,
            detail="GEOAPIFY_API_KEY is missing. Add your Geoapify API key before starting the server.",
        )

    url = "https://api.geoapify.com/v2/places"
    params = {
        "categories": categories,
        "filter": f"circle:{longitude},{latitude},{SEARCH_RADIUS_METERS}",
        "bias": f"proximity:{longitude},{latitude}",
        "limit": limit,
        "apiKey": api_key,
    }

    async with httpx.AsyncClient(timeout=PLACES_TIMEOUT_SECONDS) as client:
        response = await client.get(url, params=params)
        response.raise_for_status()
        data = response.json()

    return data.get("features", [])


async def get_geoapify_route(start_lat: float, start_lon: float, end_lat: float, end_lon: float, mode: str):
    api_key = os.getenv("GEOAPIFY_API_KEY")
    if not api_key:
        raise HTTPException(
            status_code=500,
            detail="GEOAPIFY_API_KEY is missing. Add your Geoapify API key before starting the server.",
        )

    url = "https://api.geoapify.com/v1/routing"
    params = {
        "waypoints": f"{start_lat},{start_lon}|{end_lat},{end_lon}",
        "mode": mode,
        "details": "instruction_details",
        "apiKey": api_key,
    }

    async with httpx.AsyncClient(timeout=ROUTING_TIMEOUT_SECONDS) as client:
        response = await client.get(url, params=params)
        response.raise_for_status()
        data = response.json()

    features = data.get("features", [])
    if not features:
        return None

    properties = features[0].get("properties", {})
    distance_meters = properties.get("distance")
    time_seconds = properties.get("time")

    return {
        "mode": mode,
        "distance_meters": distance_meters,
        "distance_km": round(distance_meters / 1000, 1) if distance_meters is not None else None,
        "time_seconds": time_seconds,
        "time_hours": round(time_seconds / 3600, 1) if time_seconds is not None else None,
        "time_minutes": round(time_seconds / 60) if time_seconds is not None else None,
    }


def format_place_results(features: list[dict], place_type: str) -> list[dict]:
    results = []
    seen_keys = set()

    for feature in features:
        properties = feature.get("properties", {})
        geometry = feature.get("geometry", {})
        coordinates = geometry.get("coordinates", [None, None])
        longitude = coordinates[0] if len(coordinates) > 0 else None
        latitude = coordinates[1] if len(coordinates) > 1 else None

        name = (
            properties.get("name")
            or properties.get("address_line1")
            or properties.get("formatted")
        )
        address = properties.get("formatted") or properties.get("address_line1") or "Address not available"
        website = properties.get("website")
        phone = properties.get("contact", {}).get("phone") if properties.get("contact") else None
        categories = properties.get("categories", [])

        if place_type == "attraction":
            if not name:
                continue
            if name == address and not website and not phone:
                continue
            if any(cat.startswith("accommodation") or cat.startswith("catering") for cat in categories):
                continue

        dedupe_key = (place_type, (name or "").strip().lower(), (address or "").strip().lower())
        if dedupe_key in seen_keys:
            continue
        seen_keys.add(dedupe_key)

        results.append(
            {
                "type": place_type,
                "name": name or "Unnamed place",
                "address": address,
                "categories": categories,
                "website": website,
                "phone": phone,
                "latitude": latitude,
                "longitude": longitude,
            }
        )
    return results


def build_weather_summary(weather_data: dict, requested_days: int) -> str:
    current = weather_data.get("current", {})
    daily = weather_data.get("daily", {})

    current_code = current.get("weather_code")
    current_description = WEATHER_CODE_MAP.get(current_code, f"weather code {current_code}")
    current_line = (
        f"Current conditions are {current_description} at {current.get('temperature_2m')}°C "
        f"with wind speed around {current.get('wind_speed_10m')} km/h."
    )

    dates = daily.get("time", [])
    max_temps = daily.get("temperature_2m_max", [])
    min_temps = daily.get("temperature_2m_min", [])
    rain_probs = daily.get("precipitation_probability_max", [])
    weather_codes = daily.get("weather_code", [])

    lines = [current_line]
    for i in range(min(requested_days, len(dates))):
        code = weather_codes[i] if i < len(weather_codes) else None
        description = WEATHER_CODE_MAP.get(code, f"weather code {code}")
        max_temp = max_temps[i] if i < len(max_temps) else "N/A"
        min_temp = min_temps[i] if i < len(min_temps) else "N/A"
        rain_prob = rain_probs[i] if i < len(rain_probs) else "N/A"
        lines.append(
            f"Day {i + 1} ({dates[i]}): {description}, high {max_temp}°C, low {min_temp}°C, "
            f"precipitation probability up to {rain_prob}%."
        )

    return "\n".join(lines)


# NEW FUNCTION: build_daily_activity_guidance
def build_daily_activity_guidance(weather_data: dict, requested_days: int) -> str:
    daily = weather_data.get("daily", {})
    dates = daily.get("time", [])
    rain_probs = daily.get("precipitation_probability_max", [])
    weather_codes = daily.get("weather_code", [])

    lines = []
    for i in range(min(requested_days, len(dates))):
        rain_prob = rain_probs[i] if i < len(rain_probs) else 0
        code = weather_codes[i] if i < len(weather_codes) else None
        description = WEATHER_CODE_MAP.get(code, f"weather code {code}")

        if rain_prob >= 60 or code in {51, 53, 55, 61, 63, 65, 80, 81, 82, 95, 96, 99}:
            recommendation = "Prefer indoor attractions such as museums, libraries, indoor markets, or shopping. Avoid parks, bridges, and long outdoor walks as the main activity."
        elif rain_prob >= 30 or code in {45, 48}:
            recommendation = "Use a mixed day plan. Short outdoor stops are okay, but keep at least one strong indoor backup."
        else:
            recommendation = "This is a good day for outdoor attractions, viewpoints, parks, and walking routes."

        lines.append(
            f"Day {i + 1} ({dates[i]}): {description}, precipitation probability {rain_prob}%. {recommendation}"
        )

    return "\n".join(lines)


def build_places_summary(title: str, places: list[dict]) -> str:
    if not places:
        return f"{title}: no results found."

    lines = [title + ":"]
    for idx, place in enumerate(places, start=1):
        parts = [f"{idx}. {place['name']}", f"Address: {place['address']}"]
        if place.get("website"):
            parts.append(f"Website: {place['website']}")
        if place.get("phone"):
            parts.append(f"Phone: {place['phone']}")
        lines.append(" | ".join(parts))
    return "\n".join(lines)


def build_map_markers(destination_info: dict, hotels: list[dict], restaurants: list[dict], attractions: list[dict]) -> list[dict]:
    markers = [
        {
            "type": "destination",
            "label": destination_info["name"],
            "name": destination_info["name"],
            "address": f"{destination_info['name']}, {destination_info['country']}",
            "latitude": destination_info["latitude"],
            "longitude": destination_info["longitude"],
        }
    ]

    for hotel in hotels:
        if hotel.get("latitude") is not None and hotel.get("longitude") is not None:
            markers.append(
                {
                    "type": "hotel",
                    "label": hotel["name"],
                    "name": hotel["name"],
                    "address": hotel["address"],
                    "website": hotel.get("website"),
                    "phone": hotel.get("phone"),
                    "latitude": hotel["latitude"],
                    "longitude": hotel["longitude"],
                }
            )

    for restaurant in restaurants:
        if restaurant.get("latitude") is not None and restaurant.get("longitude") is not None:
            markers.append(
                {
                    "type": "restaurant",
                    "label": restaurant["name"],
                    "name": restaurant["name"],
                    "address": restaurant["address"],
                    "website": restaurant.get("website"),
                    "phone": restaurant.get("phone"),
                    "latitude": restaurant["latitude"],
                    "longitude": restaurant["longitude"],
                }
            )

    for attraction in attractions:
        if attraction.get("latitude") is not None and attraction.get("longitude") is not None:
            markers.append(
                {
                    "type": "attraction",
                    "label": attraction["name"],
                    "name": attraction["name"],
                    "address": attraction["address"],
                    "website": attraction.get("website"),
                    "phone": attraction.get("phone"),
                    "latitude": attraction["latitude"],
                    "longitude": attraction["longitude"],
                }
            )

    return markers


def build_intercity_recommendation(drive_route: dict | None) -> dict:
    if not drive_route or drive_route.get("time_hours") is None:
        return {
            "recommended_mode": "flight_or_train",
            "reason": "Driving time could not be estimated. A flight or train is more practical for long-distance trips.",
        }

    drive_hours = drive_route["time_hours"]
    if drive_hours <= 4:
        mode = "drive"
        reason = "Driving is practical for this trip because the total driving time is relatively short."
    elif drive_hours <= 8:
        mode = "drive_or_flight"
        reason = "Driving is possible, but a flight may save time depending on price and schedule."
    else:
        mode = "flight_or_train"
        reason = "Driving would take too long, so a flight or train is likely the better choice."

    return {
        "recommended_mode": mode,
        "reason": reason,
    }


def build_budget_summary(total_budget: float, travelers: int) -> dict:
    return {
        "total_budget": total_budget,
        "travelers": travelers,
        "budget_per_person": round(total_budget / travelers, 2),
    }


def categories_from_interests(interests: list[str]) -> str:
    interest_map = {
        "museum": ["entertainment.museum"],
        "museums": ["entertainment.museum"],
        "walking": ["leisure.park", "tourism", "tourism.attraction.viewpoint"],
        "park": ["leisure.park"],
        "parks": ["leisure.park"],
        "nature": ["leisure.park", "natural"],
        "shopping": ["commercial"],
        "history": ["tourism", "entertainment.museum"],
        "art": ["entertainment.museum", "tourism"],
        "viewpoint": ["tourism.attraction.viewpoint"],
    }

    categories = set()
    for interest in interests:
        key = interest.strip().lower()
        for category in interest_map.get(key, []):
            categories.add(category)

    if not categories:
        categories.update([
            "entertainment.museum",
            "tourism.attraction.viewpoint",
            "leisure.park",
            "tourism.sights",
        ])

    return ",".join(sorted(categories))


async def ask_ollama(prompt: str):
    url = "http://127.0.0.1:11434/api/generate"
    payload = {
        "model": OLLAMA_MODEL,
        "prompt": prompt,
        "stream": False,
    }

    async with httpx.AsyncClient(timeout=OLLAMA_TIMEOUT_SECONDS) as client:
        try:
            response = await client.post(url, json=payload)
            response.raise_for_status()
        except httpx.ConnectError:
            raise HTTPException(
                status_code=500,
                detail="Could not connect to Ollama. Make sure Ollama is installed and running on your computer.",
            )
        except httpx.ReadTimeout:
            raise HTTPException(
                status_code=504,
                detail="Ollama took too long to respond. Try again or switch to an even smaller local model.",
            )

    data = response.json()
    return data.get("response", "No response returned from Ollama.")


@app.post("/plan-trip")
async def plan_trip(request: TripRequest):
    origin_info = await get_coordinates(request.origin)
    destination_info = await get_coordinates(request.destination)

    origin_lat = origin_info["latitude"]
    origin_lon = origin_info["longitude"]
    destination_lat = destination_info["latitude"]
    destination_lon = destination_info["longitude"]

    weather_data = await get_weather_forecast(destination_lat, destination_lon)
    weather_summary = build_weather_summary(weather_data, request.days)
    daily_activity_guidance = build_daily_activity_guidance(weather_data, request.days)

    restaurant_features = await search_geoapify_places(
        destination_lat,
        destination_lon,
        categories="catering.restaurant",
        limit=5,
    )
    hotel_features = await search_geoapify_places(
        destination_lat,
        destination_lon,
        categories="accommodation.hotel",
        limit=5,
    )
    attraction_features = await search_geoapify_places(
        destination_lat,
        destination_lon,
        categories=categories_from_interests(request.interests),
        limit=8,
    )

    restaurants = format_place_results(restaurant_features, "restaurant")
    hotels = format_place_results(hotel_features, "hotel")
    attractions = format_place_results(attraction_features, "attraction")

    map_markers = build_map_markers(destination_info, hotels, restaurants, attractions)

    drive_route = await get_geoapify_route(origin_lat, origin_lon, destination_lat, destination_lon, "drive")

    local_to_hotel = None
    if hotels and hotels[0].get("latitude") is not None and hotels[0].get("longitude") is not None:
        local_to_hotel = await get_geoapify_route(
            destination_lat,
            destination_lon,
            hotels[0]["latitude"],
            hotels[0]["longitude"],
            "drive",
        )

    local_to_restaurant = None
    if restaurants and restaurants[0].get("latitude") is not None and restaurants[0].get("longitude") is not None:
        local_to_restaurant = await get_geoapify_route(
            destination_lat,
            destination_lon,
            restaurants[0]["latitude"],
            restaurants[0]["longitude"],
            "drive",
        )

    intercity_transport = {
        "origin": origin_info,
        "destination": destination_info,
        "drive_route": drive_route,
        "recommendation": build_intercity_recommendation(drive_route),
        "note": "Flight and train ticket prices are not included yet. Add a flight or rail API for live ticket search.",
    }

    local_transport = {
        "destination_to_first_hotel": local_to_hotel,
        "destination_to_first_restaurant": local_to_restaurant,
        "note": "These local route estimates use driving mode from the destination center to the first hotel and restaurant options.",
    }

    budget_summary = build_budget_summary(request.budget, request.travelers)

    interests_text = ", ".join(request.interests) if request.interests else "general sightseeing"
    restaurants_summary = build_places_summary("Real restaurant options", restaurants)
    hotels_summary = build_places_summary("Real hotel options", hotels)
    attractions_summary = build_places_summary("Real attraction options", attractions)
    primary_hotel_name = hotels[0]["name"] if hotels else "the recommended hotel"

    prompt = f"""
You are a helpful travel planning assistant.

Create a practical and SPECIFIC trip recommendation based on the real weather, real restaurant results,
real hotel results, real attraction results, and transport summaries provided below.

User request:
- Origin: {request.origin}
- Destination: {request.destination}
- Days: {request.days}
- Budget: ${request.budget}
- Travelers: {request.travelers}
- Interests: {interests_text}

Budget summary:
- Total budget: ${budget_summary['total_budget']}
- Travelers: {budget_summary['travelers']}
- Budget per person: ${budget_summary['budget_per_person']}

Destination weather summary:
{weather_summary}

Daily activity guidance:
{daily_activity_guidance}

Intercity transport:
{intercity_transport}

Local transport:
{local_transport}

{hotels_summary}

{restaurants_summary}

{attractions_summary}

Instructions:
1. Describe the actual weather conditions from the provided weather summary. Do not tell the user to check the weather themselves.
2. Build a CONCRETE day-by-day itinerary using ONLY the provided real hotel, restaurant, and attraction names.
3. Hotels are for lodging only. Do NOT use hotels as sightseeing destinations or afternoon activities. Only mention the hotel for check-in, check-out, or staying overnight.
4. Restaurants are for meals only. Attractions are for sightseeing and activities.
5. Do NOT write vague phrases like "explore the city", "visit museums", or "do outdoor activities".
6. For each day, include:
   - morning attraction with a specific attraction name
   - lunch at a specific restaurant name when possible
   - afternoon attraction with a specific attraction name
   - dinner at a specific restaurant name when possible
7. Use the daily activity guidance strictly. On rainy days, choose indoor attractions only as the main activities.
8. Avoid repeating the same attraction or restaurant across multiple days unless there are no other suitable options.
9. Explain whether driving looks practical based on the provided drive summary.
10. Mention that flight or train tickets still need a live ticket API if no live prices are available.
11. Only use the provided restaurant, hotel, and attraction names as specific recommendations.
12. The recommended hotel for the trip is: {primary_hotel_name}. Use this as the lodging base unless there is a strong reason not to.
13. If exact prices are not available, explicitly say prices should be checked before booking.
14. Do not invent hotel names, restaurant names, attraction names, ratings, opening hours, ticket prices, or menu prices.
15. Return sections in this order:
   - Trip summary
   - Weather summary
   - Intercity transport recommendation
   - Local transport recommendation
   - Recommended hotel
   - Recommended restaurants
   - Recommended attractions
   - Day-by-day itinerary
   - Budget advice
   - Important notes
16. In the Day-by-day itinerary section, each day must contain at least 4 concrete named places: one hotel reference only if needed, two attractions, and two meal stops when available.
17. Keep the full answer under 650 words.
""".strip()

    travel_plan = await ask_ollama(prompt)

    return {
        "message": "Free travel plan created successfully.",
        "trip_request": request.model_dump(),
        "origin_info": origin_info,
        "destination_info": destination_info,
        "budget_summary": budget_summary,
        "weather_summary": weather_summary,
        "daily_activity_guidance": daily_activity_guidance,
        "intercity_transport": intercity_transport,
        "local_transport": local_transport,
        "recommended_hotels": hotels,
        "recommended_restaurants": restaurants,
        "recommended_attractions": attractions,
        "map_center": {
            "latitude": destination_lat,
            "longitude": destination_lon,
            "label": destination_info["name"],
        },
        "map_markers": map_markers,
        "trip_plan": travel_plan,
    }