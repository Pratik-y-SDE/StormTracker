import os
import json
import sqlite3
import hashlib
import re
from typing import List, Dict, Any, Optional
from fastapi import FastAPI, HTTPException, Query, Body
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from backend.db import get_connection, init_db
from backend.models import (
    Asset, ImpactScore, CycloneForecast, ActionRecord, ActionUpdate,
    AdvisoryDraft, AdvisoryApproval, ComparisonResult, DistrictBrief
)
from backend.scenarios import (
    compute_uncertainty_corridor,
    compute_shifted_track,
    generate_surge_scenarios,
    compute_rainfall_pathway,
    latlon_distance_km
)
from backend.scoring import compute_asset_score
from backend.gemini_service import (
    generate_district_executive_briefing,
    generate_ai_advisory_draft,
    citizen_safety_ai_copilot
)

# Initialize Database on startup
init_db()

app = FastAPI(
    title="Cyclone Impact Forecaster API",
    description="Operational Decision-Support System converting cyclone forecast tracks into ranked infrastructure preparedness actions.",
    version="3.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include Custom API Router from /api folder
try:
    from api.custom_routes import router as custom_router
    app.include_router(custom_router)
except Exception as e:
    pass


# Helper function to get update data
def get_update_by_id(update_id: str, conn: sqlite3.Connection) -> Dict[str, Any]:
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM forecast_updates WHERE id = ?;", (update_id,))
    row = cursor.fetchone()
    if not row:
        # Fallback to latest
        cursor.execute("SELECT * FROM forecast_updates ORDER BY update_number DESC LIMIT 1;")
        row = cursor.fetchone()
    return {
        "id": row["id"],
        "event_id": row["event_id"],
        "update_number": row["update_number"],
        "timestamp": row["timestamp"],
        "source": row["source"],
        "confidence": row["confidence"],
        "horizon_hours": row["horizon_hours"],
        "track": json.loads(row["track_json"])
    }

# 1. Health Endpoint
@app.get("/api/health")
def health_check():
    return {
        "status": "healthy",
        "version": "3.0.0 (Challenge Aligned)",
        "region": "Coastal Andhra Pradesh & Bay of Bengal APAC",
        "districts_count": 5,
        "assets_seeded": 42,
        "ai_engine": "Gemini 3.7 Flash + Deterministic Scoring Engine"
    }

# 2. Latest Event & All Updates
@app.get("/api/events/latest")
def get_latest_event():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM events LIMIT 1;")
    event = cursor.fetchone()
    if not event:
        conn.close()
        raise HTTPException(status_code=404, detail="No active event found.")

    cursor.execute("SELECT id, update_number, timestamp, source, confidence, horizon_hours FROM forecast_updates WHERE event_id = ? ORDER BY update_number ASC;", (event["id"],))
    updates = [dict(r) for r in cursor.fetchall()]
    conn.close()

    return {
        "event_id": event["id"],
        "name": event["name"],
        "basin": event["basin"],
        "season": event["season"],
        "category": event["current_category"],
        "updates": updates,
        "active_update_id": updates[-1]["id"] if updates else None
    }

@app.get("/api/events/{event_id}/updates")
def get_event_updates(event_id: str):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM forecast_updates WHERE event_id = ? ORDER BY update_number ASC;", (event_id,))
    rows = cursor.fetchall()
    conn.close()
    
    result = []
    for r in rows:
        result.append({
            "id": r["id"],
            "event_id": r["event_id"],
            "update_number": r["update_number"],
            "timestamp": r["timestamp"],
            "source": r["source"],
            "confidence": r["confidence"],
            "horizon_hours": r["horizon_hours"],
            "track": json.loads(r["track_json"])
        })
    return result

# 3. Districts List
@app.get("/api/districts")
def get_districts():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, name, state, headquarters, total_population, coastal_length_km, center_lat, center_lon, boundary_geojson FROM districts;")
    districts = []
    for r in cursor.fetchall():
        districts.append({
            "id": r["id"],
            "name": r["name"],
            "state": r["state"],
            "headquarters": r["headquarters"],
            "total_population": r["total_population"],
            "coastal_length_km": r["coastal_length_km"],
            "center": [r["center_lat"], r["center_lon"]],
            "boundary": json.loads(r["boundary_geojson"])
        })
    conn.close()
    return districts

# 4. Impact Scoring Engine (Core Decision View)
@app.get("/api/impact")
def get_impact_scores(
    event_id: str = "cyclone-jawhar-2026",
    update_id: str = "update-03",
    district: Optional[str] = None,
    risk_band: Optional[str] = None,
    asset_type: Optional[str] = None,
    surge_scenario: str = "central"
):
    conn = get_connection()
    update_data = get_update_by_id(update_id, conn)
    track_points = update_data["track"]
    corridor_geojson = compute_uncertainty_corridor(track_points)

    # Fetch assets
    cursor = conn.cursor()
    query = "SELECT * FROM assets WHERE 1=1"
    params = []
    if district and district.lower() != "all":
        query += " AND district = ?"
        params.append(district.lower())
    if asset_type and asset_type.lower() != "all":
        query += " AND type = ?"
        params.append(asset_type)

    cursor.execute(query, params)
    raw_assets = cursor.fetchall()

    scored_assets = []
    for r in raw_assets:
        asset_dict = {
            "id": r["id"],
            "name": r["name"],
            "type": r["type"],
            "district": r["district"],
            "lat": r["lat"],
            "lon": r["lon"],
            "criticality": r["criticality"],
            "population_served": r["population_served"],
            "backup_power": r["backup_power"],
            "elevation_m": r["elevation_m"],
            "access_route_status": r["access_route_status"],
            "last_inspected": r["last_inspected"],
            "details": json.loads(r["details_json"])
        }
        score_res = compute_asset_score(asset_dict, track_points, corridor_geojson, surge_scenario)
        if not risk_band or risk_band.lower() == "all" or score_res["risk_band"].lower() == risk_band.lower():
            scored_assets.append(score_res)

    # Sort descending by total score
    scored_assets.sort(key=lambda x: x["total_score"], reverse=True)

    # Calculate summary metrics
    immediate_count = sum(1 for a in scored_assets if a["risk_band"] == "Immediate attention")
    prioritize_count = sum(1 for a in scored_assets if a["risk_band"] == "Prioritize")
    prepare_count = sum(1 for a in scored_assets if a["risk_band"] == "Prepare")
    monitor_count = sum(1 for a in scored_assets if a["risk_band"] == "Monitor")

    total_exposed_pop = sum(a["population_served"] for a in scored_assets if a["total_score"] >= 50.0)

    top_action = scored_assets[0]["recommended_action"] if scored_assets else "Maintain routine weather monitoring."

    # Generate scenario tracks
    left_track = compute_shifted_track(track_points, -35.0)
    right_track = compute_shifted_track(track_points, 35.0)

    conn.close()

    return {
        "event_id": event_id,
        "update_id": update_id,
        "update_info": {
            "update_number": update_data["update_number"],
            "timestamp": update_data["timestamp"],
            "source": update_data["source"],
            "confidence": update_data["confidence"],
            "horizon_hours": update_data["horizon_hours"]
        },
        "summary": {
            "total_assets_evaluated": len(scored_assets),
            "immediate_attention_count": immediate_count,
            "prioritize_count": prioritize_count,
            "prepare_count": prepare_count,
            "monitor_count": monitor_count,
            "exposed_population_estimate": total_exposed_pop,
            "top_priority_action": top_action
        },
        "track": track_points,
        "corridor": corridor_geojson,
        "scenario_tracks": {
            "center": track_points,
            "left_shift_35km": left_track,
            "right_shift_35km": right_track
        },
        "assets": scored_assets
    }

# 5. Asset Detail
@app.get("/api/assets/{asset_id}")
def get_asset_detail(asset_id: str, update_id: str = "update-03"):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM assets WHERE id = ?;", (asset_id,))
    r = cursor.fetchone()
    if not r:
        conn.close()
        raise HTTPException(status_code=404, detail="Asset not found")

    update_data = get_update_by_id(update_id, conn)
    track_points = update_data["track"]
    corridor_geojson = compute_uncertainty_corridor(track_points)

    asset_dict = {
        "id": r["id"],
        "name": r["name"],
        "type": r["type"],
        "district": r["district"],
        "lat": r["lat"],
        "lon": r["lon"],
        "criticality": r["criticality"],
        "population_served": r["population_served"],
        "backup_power": r["backup_power"],
        "elevation_m": r["elevation_m"],
        "access_route_status": r["access_route_status"],
        "last_inspected": r["last_inspected"],
        "details": json.loads(r["details_json"])
    }
    score_res = compute_asset_score(asset_dict, track_points, corridor_geojson)

    # Find nearest shelter
    cursor.execute("SELECT * FROM assets WHERE type = 'Shelter';")
    shelters = cursor.fetchall()
    nearest_shelter = None
    min_dist = float("inf")
    for s in shelters:
        d = latlon_distance_km(r["lat"], r["lon"], s["lat"], s["lon"])
        if d < min_dist:
            min_dist = d
            nearest_shelter = {
                "id": s["id"],
                "name": s["name"],
                "district": s["district"],
                "distance_km": round(d, 1),
                "details": json.loads(s["details_json"])
            }

    # Fetch assigned actions for this asset
    cursor.execute("SELECT * FROM actions WHERE asset_id = ? ORDER BY updated_at DESC;", (asset_id,))
    actions = [dict(row) for row in cursor.fetchall()]

    conn.close()

    return {
        "asset": asset_dict,
        "impact_score": score_res,
        "nearest_shelter": nearest_shelter,
        "actions": actions
    }

# 6. "What Changed?" Forecast Update Comparison Diff Engine
@app.get("/api/compare")
def compare_forecast_updates(
    event_id: str = "cyclone-jawhar-2026",
    from_update: str = "update-01",
    to_update: str = "update-03"
):
    conn = get_connection()
    u1 = get_update_by_id(from_update, conn)
    u2 = get_update_by_id(to_update, conn)

    corridor_1 = compute_uncertainty_corridor(u1["track"])
    corridor_2 = compute_uncertainty_corridor(u2["track"])

    cursor = conn.cursor()
    cursor.execute("SELECT * FROM assets;")
    raw_assets = cursor.fetchall()

    scores_u1 = {}
    scores_u2 = {}

    for r in raw_assets:
        asset_dict = {
            "id": r["id"],
            "name": r["name"],
            "type": r["type"],
            "district": r["district"],
            "lat": r["lat"],
            "lon": r["lon"],
            "criticality": r["criticality"],
            "population_served": r["population_served"],
            "backup_power": r["backup_power"],
            "elevation_m": r["elevation_m"],
            "access_route_status": r["access_route_status"],
            "last_inspected": r["last_inspected"],
            "details": json.loads(r["details_json"])
        }
        s1 = compute_asset_score(asset_dict, u1["track"], corridor_1)
        s2 = compute_asset_score(asset_dict, u2["track"], corridor_2)
        scores_u1[r["id"]] = s1
        scores_u2[r["id"]] = s2

    conn.close()

    new_high_risk = []
    dropped_high_risk = []
    score_changes = []

    for aid, s2 in scores_u2.items():
        s1 = scores_u1[aid]
        delta = round(s2["total_score"] - s1["total_score"], 1)

        # Check threshold crossings
        if s1["total_score"] < 75.0 and s2["total_score"] >= 75.0:
            new_high_risk.append({
                "asset_id": aid,
                "name": s2["name"],
                "type": s2["type"],
                "district": s2["district"],
                "old_score": s1["total_score"],
                "new_score": s2["total_score"],
                "delta": delta,
                "cause": f"Track recurvature moved center corridor {abs(s2['distance_to_track_km'] - s1['distance_to_track_km']):.1f}km closer; high vulnerability triggered priority escalation."
            })
        elif s1["total_score"] >= 75.0 and s2["total_score"] < 75.0:
            dropped_high_risk.append({
                "asset_id": aid,
                "name": s2["name"],
                "type": s2["type"],
                "district": s2["district"],
                "old_score": s1["total_score"],
                "new_score": s2["total_score"],
                "delta": delta,
                "cause": f"Track moved away by {abs(s2['distance_to_track_km'] - s1['distance_to_track_km']):.1f}km; direct hazard corridor shifted away."
            })

        if abs(delta) >= 5.0:
            score_changes.append({
                "asset_id": aid,
                "name": s2["name"],
                "type": s2["type"],
                "district": s2["district"],
                "from_score": s1["total_score"],
                "to_score": s2["total_score"],
                "delta": delta,
                "from_band": s1["risk_band"],
                "to_band": s2["risk_band"],
                "top_factors": s2["top_factors"]
            })

    score_changes.sort(key=lambda x: abs(x["delta"]), reverse=True)

    # District Deltas
    district_deltas = [
        {"district": "Kakinada", "avg_delta": "+24.5 pts", "status": "ESCALATED TO HIGH CONCERN", "cause": "Direct landfall trajectory shift"},
        {"district": "Visakhapatnam", "avg_delta": "+16.2 pts", "status": "ESCALATED", "cause": "Core wind field proximity"},
        {"district": "Krishna / Machilipatnam", "avg_delta": "-11.8 pts", "status": "MODERATED", "cause": "Eye passed to the East"},
        {"district": "Bapatla", "avg_delta": "-28.4 pts", "status": "DROPPED TO MONITORING", "cause": "Exited primary uncertainty corridor"},
        {"district": "Srikakulam", "avg_delta": "+8.5 pts", "status": "PREPARING", "cause": "Post-landfall track heading Northeast"}
    ]

    narrative = (
        f"Comparing {u1['source']} ({u1['timestamp']}) to {u2['source']} ({u2['timestamp']}): "
        f"The cyclone underwent a major 45 km North-East recurvature. "
        f"{len(new_high_risk)} critical facilities in Kakinada and Visakhapatnam entered 'Immediate Attention' status, "
        f"while Bapatla district dropped out of the direct high-wind hazard corridor."
    )

    return {
        "from_update": {
            "id": u1["id"],
            "update_number": u1["update_number"],
            "timestamp": u1["timestamp"],
            "source": u1["source"]
        },
        "to_update": {
            "id": u2["id"],
            "update_number": u2["update_number"],
            "timestamp": u2["timestamp"],
            "source": u2["source"]
        },
        "new_high_risk_assets": new_high_risk,
        "dropped_high_risk_assets": dropped_high_risk,
        "significant_score_changes": score_changes[:10],
        "district_exposure_deltas": district_deltas,
        "narrative_summary": narrative
    }

# 7. Hazard Scenarios: Surge & Rainfall
@app.get("/api/hazards/surge")
def get_surge_hazard(scenario: str = "central", update_id: str = "update-03"):
    conn = get_connection()
    update_data = get_update_by_id(update_id, conn)
    conn.close()
    
    scenarios = generate_surge_scenarios(update_data["track"])
    chosen = scenarios.get(scenario.lower(), scenarios["central"])
    return chosen

@app.get("/api/hazards/rainfall")
def get_rainfall_hazard(district: str = "kakinada", update_id: str = "update-03"):
    conn = get_connection()
    update_data = get_update_by_id(update_id, conn)
    conn.close()

    dist_km = 30.0 if district.lower() == "kakinada" else 65.0
    pathway = compute_rainfall_pathway(district.lower(), dist_km, 150.0)
    return pathway

@app.get("/api/hazards/corridor")
def get_corridor_hazard(update_id: str = "update-03"):
    conn = get_connection()
    update_data = get_update_by_id(update_id, conn)
    conn.close()
    return compute_uncertainty_corridor(update_data["track"])

# 8. GEE Satellite Layers
@app.get("/api/satellite/layers")
def get_satellite_layers():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM satellite_layers;")
    rows = cursor.fetchall()
    conn.close()

    layers = []
    for r in rows:
        layers.append({
            "id": r["id"],
            "sensor": r["sensor"],
            "acquisition_time": r["acquisition_time"],
            "indicator": r["indicator"],
            "confidence": r["confidence"],
            "description": r["description"],
            "geojson": json.loads(r["geojson_data"])
        })
    return layers

# 9. Automated Advisory & Dispatch Workflow (Human-in-the-Loop)
@app.get("/api/advisories")
def list_advisories():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM advisories ORDER BY timestamp DESC;")
    advisories = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return advisories

@app.post("/api/advisories/generate")
def generate_advisory(payload: Dict[str, Any] = Body(...)):
    district_id = payload.get("district_id", "kakinada")
    target_audience = payload.get("target_audience", "District Disaster Operations Team & Utilities")
    evidence = payload.get("evidence", {
        "event": "Severe Cyclonic Storm JAWHAR",
        "update": "Special Bulletin 06",
        "surge_level": "Central (2.8m - 3.5m)",
        "critical_assets_summary": "Kakinada Deepwater Port 132kV Substation, Uppada Coastal MPCS"
    })

    draft_text = generate_ai_advisory_draft(district_id, target_audience, evidence)

    conn = get_connection()
    cursor = conn.cursor()
    adv_id = f"adv-{district_id[:3]}-{os.urandom(2).hex()}"
    timestamp = "2026-05-18T19:00:00Z"

    cursor.execute("""
    INSERT INTO advisories (id, district_id, target_audience, evidence_summary, draft_text, approval_status, approver, timestamp, dispatch_channel)
    VALUES (?, ?, ?, ?, ?, 'Draft', NULL, ?, 'State Disaster Management Rapid Network');
    """, (adv_id, district_id, target_audience, json.dumps(evidence), draft_text, timestamp))
    conn.commit()
    conn.close()

    return {
        "advisory_id": adv_id,
        "district_id": district_id,
        "target_audience": target_audience,
        "draft_text": draft_text,
        "approval_status": "Draft",
        "message": "AI Advisory generated. Requires human review and authorization before dispatch."
    }

@app.post("/api/advisories/approve")
def approve_advisory(approval: AdvisoryApproval):
    conn = get_connection()
    cursor = conn.cursor()
    status = "Dispatched" if approval.approved else "Rejected"
    cursor.execute("""
    UPDATE advisories 
    SET approval_status = ?, approver = ?, dispatch_channel = ?
    WHERE id = ?;
    """, (status, approval.approver_name, approval.dispatch_channel, approval.advisory_id))
    conn.commit()
    conn.close()

    return {
        "advisory_id": approval.advisory_id,
        "status": status,
        "approver": approval.approver_name,
        "channel": approval.dispatch_channel,
        "audit_log": f"Advisory {approval.advisory_id} approved by {approval.approver_name} and dispatched via {approval.dispatch_channel}."
    }

# 10. Parametric Insurance Readiness Triggers
# 10. Parametric Insurance Readiness Triggers & Event Monitoring
@app.get("/api/insurance/triggers")
def get_insurance_triggers(update_id: str = "update-03"):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM insurance_policies;")
    policies = cursor.fetchall()
    
    timestamp = "2026-05-18T18:30:00Z"
    if update_id == "update-01":
        timestamp = "2026-05-17T06:00:00Z"
    elif update_id == "update-02":
        timestamp = "2026-05-17T18:00:00Z"

    results = []
    for p in policies:
        pid = p["id"]
        is_triggered = False
        current_val = "115 km/h wind / 1.4m surge"
        exposed_assets = 3
        exposed_pop = 180000
        verification_status = "VERIFIED"
        verification_source = "IMD Coastal AWS Network + INCOIS Wave Buoy Telemetry"
        verification_hash = None
        payout_readiness = None  # None/null to test fallback when not ready

        if update_id in ["update-03", "latest"]:
            if "kak" in pid or "01" in pid:
                # Kakinada: TRIGGERED, VERIFIED, PAYOUT READY
                is_triggered = True
                current_val = "158 km/h wind / 3.4m surge"
                exposed_assets = 8
                exposed_pop = 780000
                verification_status = "VERIFIED"
                verification_source = "IMD Machilipatnam Doppler DWR-02 + INCOIS Tide Gauge TG-04"
                verification_hash = f"SHA256-{hashlib.sha256(f'{pid}-update-03-verified'.encode()).hexdigest()[:16].upper()}"
                payout_readiness = "PAYOUT READY"
            elif "vis" in pid or "03" in pid:
                # Visakhapatnam: TRIGGERED, PENDING VERIFICATION, PENDING VERIFICATION (to test distinct states!)
                is_triggered = True
                current_val = "142 km/h wind / 2.2m surge"
                exposed_assets = 6
                exposed_pop = 950000
                verification_status = "PENDING VERIFICATION"
                verification_source = "Awaiting Sentinel-1 SAR Overpass (Orbit 142 at 21:15 UTC)"
                verification_hash = None
                payout_readiness = "PENDING VERIFICATION"
            elif "kri" in pid or "02" in pid:
                # Krishna: MONITORING, VERIFIED, NOT AVAILABLE
                is_triggered = False
                current_val = "95 km/h wind / 1.1m surge"
                exposed_assets = 2
                exposed_pop = 120000
                verification_status = "VERIFIED"
                verification_source = "Machilipatnam AWS-01 (Normal Range)"
                payout_readiness = "NOT AVAILABLE"
            else:
                # Other/Bapatla: MONITORING, PENDING VERIFICATION, None (to test undefined/null fallback!)
                is_triggered = False
                current_val = "85 km/h wind / 0.8m surge"
                exposed_assets = 1
                exposed_pop = 80000
                verification_status = "PENDING VERIFICATION"
                verification_source = "Regional Buoy Array B-12"
                payout_readiness = None  # Explicitly null/None to test fallback in UI
        elif update_id == "update-01":
            if "kri" in pid or "02" in pid:
                is_triggered = True
                current_val = "140 km/h wind / 2.9m surge"
                exposed_assets = 5
                exposed_pop = 450000
                verification_status = "VERIFIED"
                verification_source = "IMD Radar Krishna Estuary"
                verification_hash = f"SHA256-{hashlib.sha256(f'{pid}-update-01-verified'.encode()).hexdigest()[:16].upper()}"
                payout_readiness = "PAYOUT READY"
            else:
                is_triggered = False
                current_val = "80 km/h wind / 1.0m surge"
                verification_status = "VERIFIED"
                verification_source = "IMD AWS Network"
                payout_readiness = "NOT AVAILABLE"

        payout_signal = {
            "policy_id": pid,
            "policy_zone": p["zone_name"],
            "insured_entity": p["insured_entity"],
            "trigger_condition": p["trigger_type"],
            "threshold_value": p["threshold_value"],
            "actual_sensor_reading": current_val,
            "threshold_met": is_triggered,
            "trigger_status": "TRIGGERED" if is_triggered else "MONITORING",
            "verification_status": verification_status,
            "verification_source": verification_source,
            "verification_hash": verification_hash,
            "payout_readiness_status": payout_readiness,
            "payout_amount_inr": p["payout_amount_inr"],
            "timestamp": timestamp
        }

        results.append({
            "policy_id": pid,
            "policy_name": p["zone_name"],
            "zone_name": p["zone_name"],
            "district_id": p["district_id"],
            "insured_entity": p["insured_entity"],
            "trigger_conditions": p["trigger_type"],
            "trigger_type": p["trigger_type"],
            "threshold_values": p["threshold_value"],
            "threshold_value": p["threshold_value"],
            "current_values": current_val,
            "current_value": current_val,
            "is_triggered": is_triggered,
            "trigger_status": "TRIGGERED" if is_triggered else "MONITORING",
            "timestamp": timestamp,
            "verification_status": verification_status,
            "verification_source": verification_source,
            "verification_hash": verification_hash,
            "payout_readiness_status": payout_readiness,
            "payout_amount_inr": p["payout_amount_inr"],
            "exposed_assets_count": exposed_assets,
            "exposed_population": exposed_pop,
            "payout_readiness_signal": payout_signal,
            "details": {
                "sensor_telemetry": {
                    "primary_wind_speed_kmh": float(re.search(r'(\d+(?:\.\d+)?)\s*km/h', current_val).group(1)) if re.search(r'(\d+(?:\.\d+)?)\s*km/h', current_val) else 0.0,
                    "peak_surge_height_m": float(re.search(r'(\d+(?:\.\d+)?)\s*m', current_val).group(1)) if re.search(r'(\d+(?:\.\d+)?)\s*m', current_val) else 0.0,
                    "reporting_station_count": 4 if is_triggered else 2,
                    "signal_latency_sec": 4.2
                },
                "contract_terms": {
                    "insured_sum_inr": p["payout_amount_inr"],
                    "escrow_smart_contract": f"0x71C...{pid.replace('-', '')}9A",
                    "multi_sig_threshold": "3-of-4 Oracle Signers Required",
                    "oracle_signatures": ["IMD_ORACLE_01_OK", "INCOIS_ORACLE_03_OK", "SENTINEL_SAR_GEE_OK"] if (payout_readiness == "PAYOUT READY") else []
                },
                "settlement_channel": "AP State Disaster Management Relief Escrow -> DBT Direct Transfer"
            }
        })

    conn.close()
    return results

@app.get("/api/insurance/policies/{policy_id}")
def get_insurance_policy_detail(policy_id: str, update_id: str = "update-03"):
    triggers = get_insurance_triggers(update_id=update_id)
    for t in triggers:
        if t["policy_id"] == policy_id:
            return t
    raise HTTPException(status_code=404, detail="Policy not found")


# 11. Action Queue Logging & Management
@app.get("/api/actions")
def get_actions(district: Optional[str] = None):
    conn = get_connection()
    cursor = conn.cursor()
    if district and district.lower() != "all":
        cursor.execute("SELECT * FROM actions WHERE district = ? ORDER BY updated_at DESC;", (district.lower(),))
    else:
        cursor.execute("SELECT * FROM actions ORDER BY updated_at DESC;")
    actions = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return actions

@app.post("/api/actions")
def create_action(payload: Dict[str, Any] = Body(...)):
    conn = get_connection()
    cursor = conn.cursor()
    aid = f"act-{os.urandom(3).hex()}"
    cursor.execute("""
    INSERT INTO actions (id, asset_id, asset_name, district, action_description, priority, owner, status, updated_at, notes)
    VALUES (?, ?, ?, ?, ?, ?, ?, 'Not Started', datetime('now'), ?);
    """, (
        aid,
        payload["asset_id"],
        payload.get("asset_name", "Asset"),
        payload.get("district", "kakinada"),
        payload["action_description"],
        payload.get("priority", "Immediate attention"),
        payload.get("owner", "District Control Room"),
        payload.get("notes", "")
    ))
    conn.commit()
    conn.close()
    return {"status": "created", "action_id": aid}

@app.patch("/api/actions/{action_id}")
def update_action_status(action_id: str, payload: ActionUpdate):
    conn = get_connection()
    cursor = conn.cursor()
    updates = []
    params = []
    if payload.status:
        updates.append("status = ?")
        params.append(payload.status)
    if payload.owner:
        updates.append("owner = ?")
        params.append(payload.owner)
    if payload.notes:
        updates.append("notes = ?")
        params.append(payload.notes)
    
    updates.append("updated_at = datetime('now')")
    params.append(action_id)

    query = f"UPDATE actions SET {', '.join(updates)} WHERE id = ?;"
    cursor.execute(query, params)
    conn.commit()
    conn.close()
    return {"status": "updated", "action_id": action_id}

# 12. District Preparedness Executive Briefing Generator
@app.get("/api/briefing/{district_id}")
def get_district_briefing(district_id: str, update_id: str = "update-03"):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM districts WHERE id = ?;", (district_id.lower(),))
    district_row = cursor.fetchone()
    if not district_row:
        conn.close()
        raise HTTPException(status_code=404, detail="District not found")

    dname = district_row["name"]
    update_data = get_update_by_id(update_id, conn)
    track_points = update_data["track"]
    corridor_geojson = compute_uncertainty_corridor(track_points)

    cursor.execute("SELECT * FROM assets WHERE district = ?;", (district_id.lower(),))
    assets = cursor.fetchall()
    scored = []
    for r in assets:
        adict = {
            "id": r["id"],
            "name": r["name"],
            "type": r["type"],
            "district": r["district"],
            "lat": r["lat"],
            "lon": r["lon"],
            "criticality": r["criticality"],
            "population_served": r["population_served"],
            "backup_power": r["backup_power"],
            "elevation_m": r["elevation_m"],
            "access_route_status": r["access_route_status"],
            "last_inspected": r["last_inspected"],
            "details": json.loads(r["details_json"])
        }
        scored.append(compute_asset_score(adict, track_points, corridor_geojson))

    scored.sort(key=lambda x: x["total_score"], reverse=True)
    conn.close()

    context = {
        "event_name": "Severe Cyclonic Storm JAWHAR",
        "update_time": f"{update_data['source']} ({update_data['timestamp']})",
        "top_assets": scored[:5],
        "exposed_population": sum(a["population_served"] for a in scored if a["total_score"] >= 50.0),
        "surge_scenario": "Central (2.8m - 3.5m)",
        "rainfall_accumulation": "280mm - 340mm in 24 hrs"
    }

    markdown_brief = generate_district_executive_briefing(dname, context)

    return {
        "district_id": district_id,
        "district_name": dname,
        "generated_at": "2026-05-18T19:15:00Z",
        "model_version": "ZATICS v3.0 Grounded Synthesis Engine",
        "markdown_content": markdown_brief,
        "top_assets": scored[:5]
    }

# 13. Citizen Safety Nearest Shelter & Multilingual Copilot
@app.get("/api/shelters/nearest")
def get_nearest_shelter(lat: float, lon: float, district: Optional[str] = None):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM assets WHERE type = 'Shelter';")
    shelters = cursor.fetchall()
    conn.close()

    nearest_list = []
    for s in shelters:
        d = latlon_distance_km(lat, lon, s["lat"], s["lon"])
        nearest_list.append({
            "id": s["id"],
            "name": s["name"],
            "district": s["district"],
            "lat": s["lat"],
            "lon": s["lon"],
            "distance_km": round(d, 1),
            "elevation_m": s["elevation_m"],
            "backup_power": s["backup_power"],
            "details": json.loads(s["details_json"])
        })

    nearest_list.sort(key=lambda x: x["distance_km"])
    return nearest_list[:3]

@app.post("/api/citizen/copilot")
def citizen_copilot_endpoint(payload: Dict[str, Any] = Body(...)):
    query = payload.get("query", "Is it safe to stay at home or should I evacuate?")
    district = payload.get("district", "Kakinada")
    language = payload.get("language", "en")
    user_lat = payload.get("lat", 16.98)
    user_lon = payload.get("lon", 82.24)

    # Find nearest shelter
    shelters = get_nearest_shelter(user_lat, user_lon, district)
    top_shelter = shelters[0] if shelters else {"name": "Local High School MPCS", "distance_km": 1.5}

    response_text = citizen_safety_ai_copilot(query, district, top_shelter, language)

    return {
        "district": district,
        "language": language,
        "nearest_shelter": top_shelter,
        "response": response_text,
        "official_warning_url": "https://mausam.imd.gov.in",
        "sachet_alerts_url": "https://sachet.ndma.gov.in"
    }

# Serve Frontend Static Directory
frontend_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend")
if os.path.exists(frontend_dir):
    app.mount("/static", StaticFiles(directory=frontend_dir), name="static")

    @app.get("/")
    def serve_index():
        return FileResponse(os.path.join(frontend_dir, "index.html"))
