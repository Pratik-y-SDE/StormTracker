"""StormTracker global third-party API integrations.

Live providers:
- Open-Meteo: global weather/current forecast
- GDACS: global disaster events

IMD is intentionally not included until authorized API access is available.
All provider data is normalized behind /api/custom.
"""

import time
import os
import json
from datetime import datetime, timezone
import math
from typing import Any, Dict, List, Optional, Set

import requests
from fastapi import APIRouter, HTTPException, Query


router = APIRouter(
    prefix="/api/custom",
    tags=["StormTracker Data Integrations"],
)

OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"
GDACS_EVENTS_URL = (
    "https://www.gdacs.org/gdacsapi/api/Events/geteventlist/EVENTS4APP"
)
GDACS_SEARCH_URL = (
    "https://www.gdacs.org/gdacsapi/api/Events/geteventlist/SEARCH"
)

DEFAULT_TIMEOUT = 15
WEATHER_TIMEOUT = 10
MAX_GDACS_PAGE_SIZE = 100

GDACS_EVENT_TYPES = {
    "EQ": "Earthquake",
    "TC": "Tropical Cyclone",
    "FL": "Flood",
    "WF": "Wildfire",
    "DR": "Drought",
    "VO": "Volcano",
}


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def parse_list(value: Optional[str], *, upper: bool = False, lower: bool = False) -> Set[str]:
    if not value:
        return set()
    values = {item.strip() for item in value.split(";") if item.strip()}
    if upper:
        return {item.upper() for item in values}
    if lower:
        return {item.lower() for item in values}
    return values


def validate_iso3(country: Optional[str]) -> Optional[str]:
    if country is None:
        return None
    value = country.strip().upper()
    if len(value) != 3 or not value.isalpha():
        raise HTTPException(
            status_code=400,
            detail="country must be a 3-letter ISO country code.",
        )
    return value


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    radius = 6371.0088
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(math.radians(lat1))
        * math.cos(math.radians(lat2))
        * math.sin(dlon / 2) ** 2
    )
    return radius * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def upstream_error(provider: str, exc: requests.RequestException) -> HTTPException:
    return HTTPException(
        status_code=502,
        detail=f"{provider} service unavailable: {exc}",
    )


def normalize_gdacs_feature(feature: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    props = feature.get("properties") or {}
    geometry = feature.get("geometry") or {}
    event_type = str(props.get("eventtype") or "").upper()

    if not event_type:
        return None

    coordinates = geometry.get("coordinates")
    latitude = None
    longitude = None

    if (
        geometry.get("type") == "Point"
        and isinstance(coordinates, list)
        and len(coordinates) >= 2
    ):
        longitude = coordinates[0]
        latitude = coordinates[1]

    severity = props.get("severitydata") or {}
    event_id = props.get("eventid")
    episode_id = props.get("episodeid")
    iso3 = str(props.get("iso3") or "").upper() or None

    return {
        "id": f"gdacs:{event_type}:{event_id}:{episode_id}",
        "provider_event_id": event_id,
        "episode_id": episode_id,
        "hazard": {
            "type": event_type,
            "name": GDACS_EVENT_TYPES.get(event_type, event_type),
        },
        "event": {
            "name": props.get("name"),
            "event_name": props.get("eventname"),
            "description": props.get("description"),
        },
        "location": {
            "latitude": latitude,
            "longitude": longitude,
            "country": props.get("country"),
            "country_iso3": iso3,
        },
        "alert": {
            "level": props.get("alertlevel"),
            "score": props.get("alertscore"),
            "episode_level": props.get("episodealertlevel"),
            "episode_score": props.get("episodealertscore"),
        },
        "time": {
            "started_at": props.get("fromdate"),
            "ended_at": props.get("todate"),
            "updated_at": props.get("datemodified"),
        },
        "severity": {
            "value": severity.get("severity"),
            "text": severity.get("severitytext"),
            "unit": severity.get("severityunit"),
        },
        "source": {
            "provider": "GDACS",
            "underlying_source": props.get("source"),
        },
        "affected_countries": props.get("affectedcountries", []),
        "geometry": {
            "type": geometry.get("type"),
            "coordinates": coordinates,
        },
        "links": props.get("url") or {},
    }


def fetch_gdacs(
    *,
    event_types: Set[str],
    alert_levels: Optional[Set[str]] = None,
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    page_size: int = 100,
    page_number: int = 1,
) -> Dict[str, Any]:
    params: Dict[str, Any] = {
        "eventlist": ";".join(sorted(event_types)),
        "pagesize": min(page_size, MAX_GDACS_PAGE_SIZE),
        "pagenumber": page_number,
    }

    if alert_levels:
        params["alertlevel"] = ";".join(sorted(alert_levels))
    if from_date:
        params["fromdate"] = from_date
    if to_date:
        params["todate"] = to_date

    try:
        response = requests.get(
            GDACS_SEARCH_URL,
            params=params,
            timeout=DEFAULT_TIMEOUT,
        )
        response.raise_for_status()
        return response.json()
    except requests.RequestException as exc:
        raise upstream_error("GDACS", exc) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=502,
            detail="GDACS returned invalid JSON.",
        ) from exc



# ---------------------------------------------------------------------------
# OpenStreetMap / Overpass infrastructure integration
# ---------------------------------------------------------------------------

OVERPASS_URL = os.getenv(
    "OVERPASS_URL",
    "https://overpass-api.de/api/interpreter",
)

OVERPASS_TIMEOUT = int(os.getenv("OVERPASS_TIMEOUT", "20"))
OVERPASS_CACHE_TTL_SECONDS = int(os.getenv("OVERPASS_CACHE_TTL_SECONDS", "300"))

# Public Overpass instances are shared infrastructure. Keep requests small,
# cache repeated queries, and never issue parallel/bulk queries.
OVERPASS_USER_AGENT = os.getenv(
    "OVERPASS_USER_AGENT",
    "StormTracker/1.0 (disaster-resilience-hackathon)",
)

INFRASTRUCTURE_TAGS = {
    "hospital": [
        'nwr["amenity"="hospital"]',
    ],
    "clinic": [
        'nwr["amenity"="clinic"]',
    ],
    "shelter": [
        'nwr["amenity"="shelter"]',
        'nwr["emergency"="shelter"]',
    ],
    "fire_station": [
        'nwr["amenity"="fire_station"]',
    ],
    "police": [
        'nwr["amenity"="police"]',
    ],
    "school": [
        'nwr["amenity"="school"]',
    ],
    "road": [
        'way["highway"]',
    ],
}

_osm_cache: dict[str, tuple[float, dict]] = {}


def _cache_get(key: str) -> Optional[dict]:
    item = _osm_cache.get(key)
    if not item:
        return None

    cached_at, value = item
    if time.time() - cached_at > OVERPASS_CACHE_TTL_SECONDS:
        _osm_cache.pop(key, None)
        return None

    return value


def _cache_set(key: str, value: dict) -> None:
    # Keep the in-memory cache deliberately small.
    if len(_osm_cache) >= 100:
        oldest_key = min(_osm_cache, key=lambda k: _osm_cache[k][0])
        _osm_cache.pop(oldest_key, None)

    _osm_cache[key] = (time.time(), value)


def _element_coordinates(element: dict) -> tuple[Optional[float], Optional[float]]:
    lat = element.get("lat")
    lon = element.get("lon")

    center = element.get("center") or {}
    if lat is None:
        lat = center.get("lat")
    if lon is None:
        lon = center.get("lon")

    try:
        return (
            float(lat) if lat is not None else None,
            float(lon) if lon is not None else None,
        )
    except (TypeError, ValueError):
        return None, None


def _osm_name(tags: dict) -> str:
    return (
        tags.get("name")
        or tags.get("official_name")
        or tags.get("short_name")
        or "Unnamed facility"
    )


def _normalize_osm_element(
    element: dict,
    category: str,
    query_lat: float,
    query_lon: float,
) -> Optional[dict]:
    lat, lon = _element_coordinates(element)
    if lat is None or lon is None:
        return None

    tags = element.get("tags") or {}

    return {
        "id": f"osm:{element.get('type', 'unknown')}:{element.get('id', '')}",
        "osm_type": element.get("type"),
        "osm_id": element.get("id"),
        "category": category,
        "name": _osm_name(tags),
        "latitude": lat,
        "longitude": lon,
        "distance_km": round(haversine_km(query_lat, query_lon, lat, lon), 2),
        "tags": {
            key: value
            for key, value in tags.items()
            if key in {
                "amenity",
                "emergency",
                "highway",
                "name",
                "official_name",
                "short_name",
                "operator",
                "phone",
                "website",
            }
        },
    }


def _build_overpass_query(
    latitude: float,
    longitude: float,
    radius_m: int,
    categories: list[str],
) -> str:
    statements: list[str] = []

    for category in categories:
        statements.extend(
            f"{selector}(around:{radius_m},{latitude},{longitude});"
            for selector in INFRASTRUCTURE_TAGS[category]
        )

    return (
        "[out:json][timeout:"
        + str(OVERPASS_TIMEOUT)
        + "];\n(\n"
        + "\n".join(statements)
        + "\n);\nout center tags;"
    )


def fetch_osm_infrastructure(
    latitude: float,
    longitude: float,
    radius_km: float,
    categories: list[str],
) -> dict:
    radius_m = max(100, min(int(radius_km * 1000), 25000))

    cache_key = json.dumps(
        {
            "lat": round(latitude, 4),
            "lon": round(longitude, 4),
            "radius_m": radius_m,
            "categories": categories,
        },
        sort_keys=True,
    )

    cached = _cache_get(cache_key)
    if cached:
        cached = dict(cached)
        cached["source"] = dict(cached["source"])
        cached["source"]["status"] = "cache"
        cached["source"]["cached"] = True
        return cached

    query = _build_overpass_query(
        latitude,
        longitude,
        radius_m,
        categories,
    )

    headers = {
        "User-Agent": OVERPASS_USER_AGENT,
        "Accept": "application/json",
    }

    fetched_at = utc_now_iso()

    try:
        response = requests.post(
            OVERPASS_URL,
            data={"data": query},
            headers=headers,
            timeout=OVERPASS_TIMEOUT + 5,
        )
        response.raise_for_status()
        payload = response.json()
    except requests.RequestException as exc:
        raise HTTPException(
            status_code=502,
            detail={
                "provider": "OpenStreetMap Overpass",
                "status": "unavailable",
                "message": str(exc),
                "hint": "Public Overpass instances can be busy or rate-limited. Retry later or configure OVERPASS_URL.",
            },
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=502,
            detail={
                "provider": "OpenStreetMap Overpass",
                "status": "invalid_response",
                "message": "Overpass returned a response that was not valid JSON.",
            },
        ) from exc

    elements = payload.get("elements", [])
    infrastructure: list[dict] = []

    # A single element can match multiple categories. De-duplicate by OSM id.
    seen: set[tuple[str, int, str]] = set()

    for element in elements:
        tags = element.get("tags") or {}

        matched_categories = []
        for category in categories:
            selectors = INFRASTRUCTURE_TAGS[category]

            # Determine category from the same tags used in the Overpass query.
            if category == "hospital" and tags.get("amenity") == "hospital":
                matched_categories.append(category)
            elif category == "clinic" and tags.get("amenity") == "clinic":
                matched_categories.append(category)
            elif category == "shelter" and (
                tags.get("amenity") == "shelter"
                or tags.get("emergency") == "shelter"
            ):
                matched_categories.append(category)
            elif category == "fire_station" and tags.get("amenity") == "fire_station":
                matched_categories.append(category)
            elif category == "police" and tags.get("amenity") == "police":
                matched_categories.append(category)
            elif category == "school" and tags.get("amenity") == "school":
                matched_categories.append(category)
            elif category == "road" and "highway" in tags:
                matched_categories.append(category)

        for category in matched_categories:
            element_key = (
                str(element.get("type")),
                int(element.get("id", 0)),
                category,
            )
            if element_key in seen:
                continue

            seen.add(element_key)

            normalized = _normalize_osm_element(
                element,
                category,
                latitude,
                longitude,
            )
            if normalized:
                infrastructure.append(normalized)

    infrastructure.sort(key=lambda item: item["distance_km"])

    result = {
        "source": {
            "provider": "OpenStreetMap Overpass",
            "status": "live",
            "url": OVERPASS_URL,
            "fetched_at": fetched_at,
            "attribution": "© OpenStreetMap contributors",
            "cached": False,
        },
        "query": {
            "latitude": latitude,
            "longitude": longitude,
            "radius_km": round(radius_m / 1000, 2),
            "categories": categories,
        },
        "count": len(infrastructure),
        "infrastructure": infrastructure,
        "limitations": {
            "potentially_nearby": True,
            "damage_confirmed": False,
            "completeness": "OpenStreetMap coverage varies by location.",
            "public_overpass": True,
        },
    }

    _cache_set(cache_key, result)
    return result




@router.get("/infrastructure/nearby")
def infrastructure_nearby(
    lat: float = Query(..., ge=-90, le=90),
    lon: float = Query(..., ge=-180, le=180),
    radius_km: float = Query(5.0, gt=0, le=25),
    categories: Optional[str] = Query(
        None,
        description="Comma-separated categories: hospital,clinic,shelter,fire_station,police,school,road",
    ),
):
    """Return nearby OpenStreetMap infrastructure around a location."""
    requested = parse_list(categories)

    if not requested:
        requested = [
            "hospital",
            "clinic",
            "shelter",
            "fire_station",
            "police",
            "school",
        ]

    invalid = [item for item in requested if item not in INFRASTRUCTURE_TAGS]
    if invalid:
        raise HTTPException(
            status_code=400,
            detail={
                "message": "Unsupported infrastructure category.",
                "invalid_categories": invalid,
                "supported_categories": sorted(INFRASTRUCTURE_TAGS),
            },
        )

    return fetch_osm_infrastructure(
        latitude=lat,
        longitude=lon,
        radius_km=radius_km,
        categories=requested,
    )


@router.get("/health")
def custom_api_health() -> Dict[str, Any]:
    return {
        "status": "active",
        "service": "StormTracker Global Data Integrations",
        "architecture": {
            "scope": "global",
            "country_specific_core": False,
            "provider_normalization": True,
        },
        "integrations": {
            "open_meteo": {
                "status": "live",
                "capabilities": ["current_weather", "hourly_forecast"],
            },
            "gdacs": {
                "status": "live",
                "capabilities": [
                    "global_disaster_events",
                    "search",
                    "alert_filtering",
                    "pagination",
                    "nearby_analysis",
                ],
            },
            "imd": {
                "status": "not_configured",
                "reason": "Official API access requires authorization/whitelisting.",
            },
        },
    }


@router.get("/weather")
def get_weather(
    lat: float = Query(..., ge=-90, le=90),
    lon: float = Query(..., ge=-180, le=180),
) -> Dict[str, Any]:
    params = {
        "latitude": lat,
        "longitude": lon,
        "current": (
            "temperature_2m,relative_humidity_2m,apparent_temperature,"
            "precipitation,rain,weather_code,cloud_cover,pressure_msl,"
            "wind_speed_10m,wind_direction_10m,wind_gusts_10m"
        ),
        "hourly": (
            "temperature_2m,precipitation_probability,precipitation,"
            "weather_code,wind_speed_10m,wind_direction_10m,"
            "wind_gusts_10m,visibility"
        ),
        "forecast_hours": 24,
        "timezone": "auto",
    }

    try:
        response = requests.get(
            OPEN_METEO_URL,
            params=params,
            timeout=WEATHER_TIMEOUT,
        )
        response.raise_for_status()
        data = response.json()
    except requests.RequestException as exc:
        raise upstream_error("Open-Meteo", exc) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=502,
            detail="Open-Meteo returned invalid JSON.",
        ) from exc

    current = data.get("current") or {}
    hourly = data.get("hourly") or {}
    fetched_at = utc_now_iso()

    return {
        "source": {
            "provider": "Open-Meteo",
            "status": "live",
            "url": OPEN_METEO_URL,
            "fetched_at": fetched_at,
            "attribution": "Open-Meteo",
        },
        "location": {
            "requested_latitude": lat,
            "requested_longitude": lon,
            "latitude": data.get("latitude"),
            "longitude": data.get("longitude"),
            "timezone": data.get("timezone"),
            "elevation_m": data.get("elevation"),
        },
        "current": {
            "time": current.get("time"),
            "temperature_c": current.get("temperature_2m"),
            "relative_humidity_percent": current.get("relative_humidity_2m"),
            "apparent_temperature_c": current.get("apparent_temperature"),
            "precipitation_mm": current.get("precipitation"),
            "rain_mm": current.get("rain"),
            "weather_code": current.get("weather_code"),
            "cloud_cover_percent": current.get("cloud_cover"),
            "pressure_msl_hpa": current.get("pressure_msl"),
            "wind_speed_kmh": current.get("wind_speed_10m"),
            "wind_direction_deg": current.get("wind_direction_10m"),
            "wind_gust_kmh": current.get("wind_gusts_10m"),
        },
        "forecast": {
            "time": hourly.get("time", []),
            "temperature_c": hourly.get("temperature_2m", []),
            "precipitation_probability_percent": hourly.get(
                "precipitation_probability", []
            ),
            "precipitation_mm": hourly.get("precipitation", []),
            "weather_code": hourly.get("weather_code", []),
            "wind_speed_kmh": hourly.get("wind_speed_10m", []),
            "wind_direction_deg": hourly.get("wind_direction_10m", []),
            "wind_gust_kmh": hourly.get("wind_gusts_10m", []),
            "visibility_m": hourly.get("visibility", []),
        },
        "metadata": {
            "timezone": data.get("timezone"),
            "timezone_abbreviation": data.get("timezone_abbreviation"),
            "utc_offset_seconds": data.get("utc_offset_seconds"),
            "provider_fetched_time": current.get("time"),
            "backend_fetched_at": fetched_at,
        },
    }


@router.get("/disasters")
def get_disasters(
    event_types: str = Query("EQ;TC;FL;WF;DR;VO"),
    alert_levels: Optional[str] = Query(None),
    country: Optional[str] = Query(None, min_length=3, max_length=3),
    from_date: Optional[str] = Query(None),
    to_date: Optional[str] = Query(None),
    page_size: int = Query(100, ge=1, le=100),
    page_number: int = Query(1, ge=1),
) -> Dict[str, Any]:
    requested_types = parse_list(event_types, upper=True)
    if not requested_types:
        raise HTTPException(400, "At least one event type is required.")

    unknown_types = requested_types.difference(GDACS_EVENT_TYPES)
    if unknown_types:
        raise HTTPException(
            400,
            "Unsupported GDACS event type(s): " + ", ".join(sorted(unknown_types)),
        )

    requested_alerts = parse_list(alert_levels, lower=True)
    unknown_alerts = requested_alerts.difference({"green", "orange", "red"})
    if unknown_alerts:
        raise HTTPException(
            400,
            "Unsupported alert level(s): " + ", ".join(sorted(unknown_alerts)),
        )

    normalized_country = validate_iso3(country)

    data = fetch_gdacs(
        event_types=requested_types,
        alert_levels=requested_alerts or None,
        from_date=from_date,
        to_date=to_date,
        page_size=page_size,
        page_number=page_number,
    )

    events: List[Dict[str, Any]] = []
    for feature in data.get("features", []):
        event = normalize_gdacs_feature(feature)
        if not event:
            continue
        if (
            normalized_country
            and event["location"]["country_iso3"] != normalized_country
        ):
            continue
        events.append(event)

    fetched_at = utc_now_iso()

    return {
        "source": {
            "provider": "GDACS",
            "status": "live",
            "service": "Global Disaster Alert and Coordination System",
            "url": GDACS_SEARCH_URL,
            "fetched_at": fetched_at,
            "attribution": "Global Disaster Awareness and Coordination System, GDACS",
        },
        "scope": {
            "global": True,
            "country_filter": normalized_country,
        },
        "filters": {
            "event_types": sorted(requested_types),
            "alert_levels": sorted(requested_alerts) if requested_alerts else None,
            "from_date": from_date,
            "to_date": to_date,
        },
        "pagination": {
            "page_size": page_size,
            "page_number": page_number,
            "returned": len(events),
            "provider_limit": MAX_GDACS_PAGE_SIZE,
        },
        "count": len(events),
        "events": events,
    }


@router.get("/disasters/nearby")
def get_nearby_disasters(
    lat: float = Query(..., ge=-90, le=90),
    lon: float = Query(..., ge=-180, le=180),
    radius_km: float = Query(500, gt=0, le=20000),
    event_types: str = Query("EQ;TC;FL;WF;DR;VO"),
    page_size: int = Query(100, ge=1, le=100),
) -> Dict[str, Any]:
    requested_types = parse_list(event_types, upper=True)
    if not requested_types:
        raise HTTPException(400, "At least one event type is required.")

    unknown_types = requested_types.difference(GDACS_EVENT_TYPES)
    if unknown_types:
        raise HTTPException(
            400,
            "Unsupported GDACS event type(s): " + ", ".join(sorted(unknown_types)),
        )

    data = fetch_gdacs(
        event_types=requested_types,
        page_size=page_size,
        page_number=1,
    )

    nearby: List[Dict[str, Any]] = []

    for feature in data.get("features", []):
        event = normalize_gdacs_feature(feature)
        if not event:
            continue

        event_lat = event["location"]["latitude"]
        event_lon = event["location"]["longitude"]

        if event_lat is None or event_lon is None:
            continue

        distance_km = haversine_km(lat, lon, event_lat, event_lon)

        if distance_km <= radius_km:
            nearby.append(
                {
                    "id": event["id"],
                    "provider_event_id": event["provider_event_id"],
                    "episode_id": event["episode_id"],
                    "hazard": event["hazard"],
                    "name": event["event"]["name"],
                    "country": event["location"]["country"],
                    "country_iso3": event["location"]["country_iso3"],
                    "latitude": event_lat,
                    "longitude": event_lon,
                    "alert": event["alert"],
                    "distance_km": round(distance_km, 2),
                    "updated_at": event["time"]["updated_at"],
                    "source": event["source"],
                }
            )

    nearby.sort(key=lambda item: item["distance_km"])

    return {
        "source": {
            "provider": "GDACS",
            "status": "live",
            "fetched_at": utc_now_iso(),
        },
        "query": {
            "latitude": lat,
            "longitude": lon,
            "radius_km": radius_km,
            "event_types": sorted(requested_types),
        },
        "limitations": {
            "point_events_only": True,
            "inspected_page_size": page_size,
            "complete_global_spatial_index": False,
        },
        "count": len(nearby),
        "events": nearby,
    }
