import math
from typing import List, Dict, Any, Tuple
from shapely.geometry import LineString, Point, Polygon, mapping
from shapely.ops import transform

# Approximate conversion for coastal AP (latitude ~16-18 N)
KM_PER_DEG_LAT = 111.0
KM_PER_DEG_LON = 106.0  # at ~17° N, cos(17°) * 111 ≈ 106.1

def latlon_distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Haversine distance in kilometers between two lat/lon points."""
    R = 6371.0  # Earth's radius in km
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat / 2) ** 2 +
         math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2)
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c

def compute_track_linestring(track_points: List[Dict[str, Any]]) -> LineString:
    """Create a Shapely LineString from track points in (lon, lat) order."""
    coords = [(p["lon"], p["lat"]) for p in track_points]
    return LineString(coords)

def compute_uncertainty_corridor(track_points: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Construct an expanding uncertainty corridor polygon around the cyclone track.
    Returns a GeoJSON Polygon geometry.
    """
    if not track_points:
        return {"type": "Polygon", "coordinates": []}

    left_points = []
    right_points = []

    for i, pt in enumerate(track_points):
        lat = pt["lat"]
        lon = pt["lon"]
        radius_km = pt.get("uncertainty_radius_km", 40.0)

        # Calculate track direction vector
        if i < len(track_points) - 1:
            next_pt = track_points[i + 1]
            dlat = next_pt["lat"] - lat
            dlon = next_pt["lon"] - lon
        elif i > 0:
            prev_pt = track_points[i - 1]
            dlat = lat - prev_pt["lat"]
            dlon = lon - prev_pt["lon"]
        else:
            dlat, dlon = 1.0, 0.0

        length = math.hypot(dlat, dlon)
        if length == 0:
            length = 1.0

        # Normal vector perpendicular to track
        norm_lat = -dlon / length
        norm_lon = dlat / length

        deg_lat_offset = (radius_km / KM_PER_DEG_LAT) * norm_lat
        deg_lon_offset = (radius_km / KM_PER_DEG_LON) * norm_lon

        left_points.append([lon + deg_lon_offset, lat + deg_lat_offset])
        right_points.append([lon - deg_lon_offset, lat - deg_lat_offset])

    # Combine left and reversed right to form closed polygon
    polygon_coords = left_points + list(reversed(right_points))
    polygon_coords.append(polygon_coords[0])  # close ring

    return {
        "type": "Polygon",
        "coordinates": [polygon_coords]
    }

def compute_shifted_track(track_points: List[Dict[str, Any]], offset_km: float) -> List[Dict[str, Any]]:
    """
    Generates a parallel shifted scenario track (e.g. +35 km East / -35 km West).
    """
    shifted = []
    for i, pt in enumerate(track_points):
        lat = pt["lat"]
        lon = pt["lon"]

        if i < len(track_points) - 1:
            next_pt = track_points[i + 1]
            dlat = next_pt["lat"] - lat
            dlon = next_pt["lon"] - lon
        elif i > 0:
            prev_pt = track_points[i - 1]
            dlat = lat - prev_pt["lat"]
            dlon = lon - prev_pt["lon"]
        else:
            dlat, dlon = 1.0, 0.0

        length = math.hypot(dlat, dlon)
        if length == 0:
            length = 1.0

        norm_lat = -dlon / length
        norm_lon = dlat / length

        offset_lat = (offset_km / KM_PER_DEG_LAT) * norm_lat
        offset_lon = (offset_km / KM_PER_DEG_LON) * norm_lon

        shifted_pt = dict(pt)
        shifted_pt["lat"] = round(lat + offset_lat, 4)
        shifted_pt["lon"] = round(lon + offset_lon, 4)
        shifted.append(shifted_pt)

    return shifted

def calculate_distance_to_track(asset_lat: float, asset_lon: float, track_points: List[Dict[str, Any]]) -> Tuple[float, float]:
    """
    Calculates:
    1. Minimum distance in km from asset to track centerline.
    2. Estimated peak wind at closest track point.
    """
    min_dist = float("inf")
    peak_wind = 60.0

    for pt in track_points:
        dist = latlon_distance_km(asset_lat, asset_lon, pt["lat"], pt["lon"])
        if dist < min_dist:
            min_dist = dist
            peak_wind = pt.get("wind_kmh", 120.0)

    return min_dist, peak_wind

def is_point_in_corridor(lat: float, lon: float, corridor_geojson: Dict[str, Any]) -> bool:
    """Checks if a point is within the corridor polygon."""
    try:
        coords = corridor_geojson["coordinates"][0]
        poly = Polygon(coords)
        return poly.contains(Point(lon, lat))
    except Exception:
        return False

def generate_surge_scenarios(track_points: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    """
    Generates Low (1.5m), Central (2.8m), and High (4.2m) storm surge inundation zones.
    Returns GeoJSON feature collections and affected characteristics.
    """
    # Find coastal landfall coordinates from track
    landfall_pt = track_points[min(2, len(track_points)-1)]
    clat = landfall_pt["lat"]
    clon = landfall_pt["lon"]

    # Low surge: narrow buffer along coastline
    low_polygon = [
        [clon - 0.4, clat - 0.5], [clon + 0.15, clat - 0.4],
        [clon + 0.25, clat + 0.3], [clon - 0.25, clat + 0.35],
        [clon - 0.4, clat - 0.5]
    ]

    # Central surge: moderate inundation penetrations (estuaries & deltas)
    central_polygon = [
        [clon - 0.65, clat - 0.75], [clon + 0.3, clat - 0.6],
        [clon + 0.45, clat + 0.55], [clon - 0.45, clat + 0.6],
        [clon - 0.65, clat - 0.75]
    ]

    # High surge: deep seawater intrusion up to 8-12 km inland
    high_polygon = [
        [clon - 0.9, clat - 1.0], [clon + 0.45, clat - 0.8],
        [clon + 0.6, clat + 0.8], [clon - 0.7, clat + 0.85],
        [clon - 0.9, clat - 1.0]
    ]

    return {
        "low": {
            "scenario_type": "Low Surge",
            "surge_height_m": 1.5,
            "description": "Minor tidal surge (1.0m - 1.5m) restricted to open beaches and intertidal mudflats.",
            "inundation_boundary": {"type": "Polygon", "coordinates": [low_polygon]},
            "surge_risk_threshold_elev_m": 2.0
        },
        "central": {
            "scenario_type": "Central Surge",
            "surge_height_m": 2.8,
            "description": "Moderate to severe storm surge (2.5m - 2.8m). Inundates low-lying coastal roads, delta bypasses, and port installations.",
            "inundation_boundary": {"type": "Polygon", "coordinates": [central_polygon]},
            "surge_risk_threshold_elev_m": 3.5
        },
        "high": {
            "scenario_type": "High Surge (Plausible Upper Bound)",
            "surge_height_m": 4.2,
            "description": "Catastrophic cyclonic surge (3.8m - 4.2m) coinciding with astronomical high tide. Heavy seawater intrusion up to 10km inland.",
            "inundation_boundary": {"type": "Polygon", "coordinates": [high_polygon]},
            "surge_risk_threshold_elev_m": 5.0
        }
    }

def compute_rainfall_pathway(district_id: str, distance_to_track_km: float, max_wind: float) -> Dict[str, Any]:
    """
    Models rainfall accumulation and road/bridge access cutoff pathways per district.
    """
    # Closer to track centerline = heavier precipitation bands
    base_rainfall = max(50.0, 320.0 - (distance_to_track_km * 1.8))
    if max_wind > 140:
        base_rainfall += 60.0

    accumulation_mm = round(min(450.0, max(60.0, base_rainfall)), 1)

    pathways_by_district = {
        "kakinada": {
            "waterlogged_roads": ["Uppada Beach Bypass Road (NH-216)", "Kakinada-Yanam Coastal Corridor", "Coringa Estuary Approach Road"],
            "cut_off_facilities": ["Uppada MPCS Coastal Approach", "Port Area 33kV Line Road"],
            "advisory": "Extreme waterlogging (>300mm) expected in low-lying delta canals. Pre-position high-clearance rescue vehicles at GGH Kakinada."
        },
        "visakhapatnam": {
            "waterlogged_roads": ["Bheemili Beach Road (Gosthani section)", "Gajuwaka Industrial Lowline Canal", "Lawson's Bay Ingress Route"],
            "cut_off_facilities": ["Bheemili Relief Camp Bridge Detour", "Pedagantyada Substation Feeder Lane"],
            "advisory": "Flash runoff from Eastern Ghats foothills into Gosthani basin may submerge estuary bypass by T-06h."
        },
        "krishna": {
            "waterlogged_roads": ["Bandar Canal Bank Road", "Manginapudi Beach Access Way", "Nagayalanka Delta Island Ferry Cutoff"],
            "cut_off_facilities": ["Manginapudi Shelter East Gate", "Gilakaladindi Harbor Link"],
            "advisory": "Saturated soil backpressure preventing drainage from Bandar Canal into Bay of Bengal. Road breach probable."
        },
        "bapatla": {
            "waterlogged_roads": ["Suryalanka Beach Road", "Romperu Drain Causeway", "Karlapalem Rural Artery"],
            "cut_off_facilities": ["Karlapalem Substation Access", "Suryalanka West Relief Outpost"],
            "advisory": "Romperu drain discharge choke point will cause shallow flooding (0.5m-0.8m) over 12km of connecting roads."
        },
        "srikakulam": {
            "waterlogged_roads": ["Kalingapatnam Coastal Highway", "Nagavali River Delta Margins", "Bhavanapadu Port Access"],
            "cut_off_facilities": ["Kalingapatnam Substation Approach Road"],
            "advisory": "Heavy localized spells (180mm-240mm) expected. River bridges remain passable but coastal access ramps vulnerable."
        }
    }

    info = pathways_by_district.get(district_id, {
        "waterlogged_roads": ["District Coastal Feeder Road"],
        "cut_off_facilities": ["Low-lying Substation Approach"],
        "advisory": "Continuous rainfall and gusty winds will reduce vehicular visibility and slow emergency transit."
    })

    return {
        "district_id": district_id,
        "accumulation_mm": accumulation_mm,
        "waterlogged_roads": info["waterlogged_roads"],
        "cut_off_facilities": info["cut_off_facilities"],
        "advisory": info["advisory"]
    }
