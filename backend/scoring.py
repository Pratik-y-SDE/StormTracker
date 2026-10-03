from typing import Dict, Any, List, Tuple
from backend.scenarios import (
    calculate_distance_to_track,
    is_point_in_corridor,
    compute_shifted_track
)

def compute_asset_score(
    asset: Dict[str, Any],
    track_points: List[Dict[str, Any]],
    corridor_geojson: Dict[str, Any],
    active_surge_scenario: str = "central"
) -> Dict[str, Any]:
    """
    Computes explainable Impact Priority Score for an asset given a cyclone forecast track.
    Implements PRD v3.0 Section 9.2:
    ImpactPriority(a,t) = 0.35 * HazardExposure + 0.25 * Vulnerability + 0.20 * Consequence + 0.10 * AccessCriticality + 0.10 * DataConfidence
    """
    lat = asset["lat"]
    lon = asset["lon"]
    asset_type = asset["type"]
    criticality = asset["criticality"]
    pop = asset["population_served"]
    backup = asset.get("backup_power", "None")
    elevation = asset.get("elevation_m", 10.0)
    access_status = asset.get("access_route_status", "Normal")
    inspected = str(asset.get("last_inspected", ""))

    # 1. HazardExposure (0-100)
    dist_km, peak_wind = calculate_distance_to_track(lat, lon, track_points)
    in_corridor = is_point_in_corridor(lat, lon, corridor_geojson)

    # Base distance score
    if dist_km <= 20.0:
        dist_score = 95.0
    elif dist_km <= 45.0:
        dist_score = 80.0
    elif dist_km <= 80.0:
        dist_score = 60.0
    elif dist_km <= 130.0:
        dist_score = 35.0
    elif dist_km <= 180.0:
        dist_score = 18.0
    else:
        dist_score = 5.0

    hazard_score = dist_score
    if in_corridor:
        hazard_score += 10.0
    if peak_wind >= 150.0:
        hazard_score += 12.0
    elif peak_wind >= 130.0:
        hazard_score += 6.0

    # Low elevation coastal surge exposure add-on
    surge_risk_level = "Low"
    if elevation <= 2.5:
        surge_risk_level = "Extreme"
        hazard_score += 15.0
    elif elevation <= 4.0:
        surge_risk_level = "Moderate"
        hazard_score += 8.0

    hazard_exposure = min(100.0, max(0.0, hazard_score))

    # 2. Vulnerability (0-100)
    vuln_score = 0.0
    # Elevation component
    if elevation <= 2.0:
        vuln_score += 40.0
    elif elevation <= 3.5:
        vuln_score += 25.0
    elif elevation <= 6.0:
        vuln_score += 12.0

    # Backup power status
    if backup == "None":
        vuln_score += 45.0
    elif backup == "Unverified":
        vuln_score += 28.0
    else:  # Verified
        vuln_score += 5.0

    # Facility fragility
    if asset_type in ["Substation", "Bridge"]:
        vuln_score += 15.0
    elif asset_type == "Hospital" and backup != "Verified":
        vuln_score += 18.0

    vulnerability = min(100.0, max(0.0, vuln_score))

    # 3. Consequence (0-100)
    conseq_score = 0.0
    # Criticality tier
    conseq_score += criticality * 10.0  # 10 to 50 pts

    # Population served
    if pop >= 500000:
        conseq_score += 45.0
    elif pop >= 200000:
        conseq_score += 32.0
    elif pop >= 50000:
        conseq_score += 20.0
    elif pop >= 2000:
        conseq_score += 10.0
    else:
        conseq_score += 0.0

    consequence = min(100.0, max(0.0, conseq_score))

    # 4. AccessCriticality (0-100)
    access_score = 15.0
    if access_status == "Bridge Dependent":
        access_score = 80.0
    elif access_status == "Flood Prone":
        access_score = 60.0

    details = asset.get("details", {})
    if details.get("island_delta_access") or details.get("vital_evacuation_lifeline"):
        access_score += 20.0

    access_criticality = min(100.0, max(0.0, access_score))

    # 5. DataConfidence (0-100)
    # Reflects data quality: fresh verified data is rewarded, stale unverified records are penalized
    conf_score = 90.0
    if "Stale" in inspected:
        conf_score = 35.0
    elif "2025" in inspected:
        conf_score = 65.0
    elif backup == "Unverified":
        conf_score -= 15.0

    data_confidence = min(100.0, max(0.0, conf_score))

    # Total Impact Priority Formula
    total_score = (
        0.35 * hazard_exposure +
        0.25 * vulnerability +
        0.20 * consequence +
        0.10 * access_criticality +
        0.10 * data_confidence
    )
    total_score = round(min(100.0, max(0.0, total_score)), 1)

    # Risk Band
    if total_score >= 75.0:
        risk_band = "Immediate attention"
    elif total_score >= 50.0:
        risk_band = "Prioritize"
    elif total_score >= 25.0:
        risk_band = "Prepare"
    else:
        risk_band = "Monitor"

    # Top 3 Contributing Factors
    factors_list = []
    if hazard_exposure >= 70.0:
        factors_list.append(f"Located within high-hazard corridor ({dist_km:.1f} km from center track with {peak_wind:.0f} km/h wind gusts)")
    elif hazard_exposure >= 40.0:
        factors_list.append(f"Exposed to cyclone periphery ({dist_km:.1f} km distance)")

    if backup == "None":
        factors_list.append("Zero verified backup power capacity on record")
    elif backup == "Unverified":
        factors_list.append("Backup power and generator logs unverified since last season")

    if elevation <= 3.0:
        factors_list.append(f"Low coastal elevation ({elevation}m MSL) directly exposed to storm surge")

    if pop >= 200000:
        factors_list.append(f"Serves major regional population ({pop:,} citizens)")

    if access_status == "Bridge Dependent":
        factors_list.append("Single-point-of-failure bridge dependency for emergency access")
    elif access_status == "Flood Prone":
        factors_list.append("Approach corridor prone to monsoon and tidal flooding")

    if "Stale" in inspected:
        factors_list.append(f"Data audit warning: Inspection record stale ({inspected})")

    # Pick top 3
    top_factors = factors_list[:3]
    if len(top_factors) < 2:
        top_factors.append(f"Criticality level Tier-{criticality} essential infrastructure")

    # Recommended Action
    action = generate_recommended_action(asset_type, total_score, backup, access_status, elevation)

    # Scenario Sensitivity Calculation (Center vs Left-Shift -35km vs Right-Shift +35km)
    left_track = compute_shifted_track(track_points, -35.0)
    right_track = compute_shifted_track(track_points, 35.0)

    dist_left, _ = calculate_distance_to_track(lat, lon, left_track)
    dist_right, _ = calculate_distance_to_track(lat, lon, right_track)

    if dist_right < dist_km - 20.0:
        scenario_sensitivity = "High sensitivity to Eastward track shift (Priority escalates)"
    elif dist_left < dist_km - 20.0:
        scenario_sensitivity = "High sensitivity to Westward track shift (Priority escalates)"
    else:
        scenario_sensitivity = "Stable priority across ±35km track scenarios"

    rainfall_risk = "High" if dist_km < 70.0 else ("Moderate" if dist_km < 140.0 else "Low")

    return {
        "asset_id": asset["id"],
        "name": asset["name"],
        "type": asset["type"],
        "district": asset["district"],
        "lat": asset["lat"],
        "lon": asset["lon"],
        "criticality": criticality,
        "total_score": total_score,
        "risk_band": risk_band,
        "factor_breakdown": {
            "hazard_exposure": round(hazard_exposure, 1),
            "vulnerability": round(vulnerability, 1),
            "consequence": round(consequence, 1),
            "access_criticality": round(access_criticality, 1),
            "data_confidence": round(data_confidence, 1)
        },
        "top_factors": top_factors,
        "recommended_action": action,
        "scenario_sensitivity": scenario_sensitivity,
        "distance_to_track_km": round(dist_km, 1),
        "in_corridor": in_corridor,
        "surge_risk_level": surge_risk_level,
        "rainfall_risk_level": rainfall_risk,
        "population_served": pop,
        "backup_power": backup
    }

def generate_recommended_action(asset_type: str, score: float, backup: str, access: str, elevation: float) -> str:
    """Generates an operational next action based on asset profile and risk score."""
    if score >= 75.0:
        if asset_type == "Hospital":
            return "Pre-position auxiliary 500kVA fuel reserve, secure cryogenic oxygen supply, and activate trauma wing contingency."
        elif asset_type == "Substation":
            return "Deploy mobile emergency transformer unit, install flood perimeter sandbags, and initiate pre-emptive coastal feeder isolation."
        elif asset_type == "Bridge":
            return "Deploy structural watch team, establish radar clearance telemetry, and verify alternate inland detour signs."
        elif asset_type == "Shelter":
            return "Confirm shelter opening with Tahsildar, stock 72-hour drinking water, and test satellite VHF radio."
        elif asset_type == "Water Treatment":
            return "Engage auxiliary diesel pumps, protect chlorination chambers against seawater intrusion, and pre-charge municipal tanks."
        else:
            return "Immediate on-site inspection, secure loose infrastructure, and notify district emergency control room."
    elif score >= 50.0:
        if backup != "Verified":
            return "Dispatch field technician to test emergency generator and log fuel replenishment before impact window."
        if access == "Flood Prone":
            return "Verify high-clearance vehicle availability and inspect approach causeway drainage culverts."
        return "Pre-position operational team, verify communications, and review readiness checklist."
    elif score >= 25.0:
        return "Confirm designated facility owner, verify backup power telemetry, and maintain hourly watch."
    else:
        return "Continue routine monitoring and verify maintenance records."
