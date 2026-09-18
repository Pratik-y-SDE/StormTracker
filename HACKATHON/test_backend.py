import sys
import os
import json
from fastapi.testclient import TestClient

from backend.main import app

client = TestClient(app)

def test_health():
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["version"].startswith("3.0.0")
    print("[PASS] Health check passed")

def test_events_and_updates():
    response = client.get("/api/events/latest")
    assert response.status_code == 200
    data = response.json()
    assert "event_id" in data
    assert len(data["updates"]) == 3
    print("[PASS] Events & Updates passed")

def test_districts():
    response = client.get("/api/districts")
    assert response.status_code == 200
    districts = response.json()
    assert len(districts) == 5
    district_ids = [d["id"] for d in districts]
    assert "kakinada" in district_ids
    assert "visakhapatnam" in district_ids
    print("[PASS] Districts list passed")

def test_impact_scoring():
    response = client.get("/api/impact?update_id=update-03")
    assert response.status_code == 200
    data = response.json()
    assert "summary" in data
    assert "assets" in data
    assert len(data["assets"]) >= 35

    # Check first asset has required factor breakdown and total score in 0-100
    top_asset = data["assets"][0]
    assert 0 <= top_asset["total_score"] <= 100
    factors = top_asset["factor_breakdown"]
    assert "hazard_exposure" in factors
    assert "vulnerability" in factors
    assert "consequence" in factors
    assert "access_criticality" in factors
    assert "data_confidence" in factors

    # Check top action is not empty
    assert len(top_asset["recommended_action"]) > 0
    print("[PASS] Impact scoring and factor breakdown passed")

def test_forecast_comparison():
    response = client.get("/api/compare?from_update=update-01&to_update=update-03")
    assert response.status_code == 200
    data = response.json()
    assert "new_high_risk_assets" in data
    assert "significant_score_changes" in data
    assert "narrative_summary" in data
    assert len(data["new_high_risk_assets"]) > 0
    print("[PASS] Forecast comparison diff engine passed")

def test_hazard_scenarios():
    # Surge
    res_surge = client.get("/api/hazards/surge?scenario=high")
    assert res_surge.status_code == 200
    surge_data = res_surge.json()
    assert surge_data["surge_height_m"] == 4.2

    # Rainfall
    res_rain = client.get("/api/hazards/rainfall?district=kakinada")
    assert res_rain.status_code == 200
    rain_data = res_rain.json()
    assert rain_data["accumulation_mm"] > 100
    assert len(rain_data["waterlogged_roads"]) > 0
    print("[PASS] Hazard scenarios (surge & rainfall) passed")

def test_satellite_layers():
    response = client.get("/api/satellite/layers")
    assert response.status_code == 200
    layers = response.json()
    assert len(layers) >= 2
    sensors = [l["sensor"] for l in layers]
    assert any("Sentinel-1" in s for s in sensors)
    print("[PASS] Satellite GEE layers passed")

def test_advisory_approval_workflow():
    # 1. Generate draft
    res_gen = client.post("/api/advisories/generate", json={"district_id": "kakinada", "target_audience": "Port Authorities"})
    assert res_gen.status_code == 200
    adv = res_gen.json()
    adv_id = adv["advisory_id"]

    # 2. Approve draft
    res_app = client.post("/api/advisories/approve", json={
        "advisory_id": adv_id,
        "approver_name": "Dr. S. K. Rao (District Collector)",
        "approved": True,
        "dispatch_channel": "AP State Rapid Disaster Network"
    })
    assert res_app.status_code == 200
    app_data = res_app.json()
    assert app_data["status"] == "Dispatched"
    print("[PASS] Human-in-the-loop advisory approval workflow passed")

def test_insurance_triggers():
    response = client.get("/api/insurance/triggers?update_id=update-03")
    assert response.status_code == 200
    triggers = response.json()
    assert len(triggers) >= 3
    # Update-03 should trigger Kakinada policy
    triggered_policies = [t for t in triggers if t["is_triggered"]]
    assert len(triggered_policies) > 0
    print("[PASS] Parametric insurance trigger panel passed")

def test_district_briefing():
    response = client.get("/api/briefing/kakinada?update_id=update-03")
    assert response.status_code == 200
    brief = response.json()
    assert "markdown_content" in brief
    assert "KAKINADA" in brief["markdown_content"].upper()
    print("[PASS] District briefing generator passed")

def test_citizen_shelter_and_copilot():
    # Nearest shelter
    res_shelter = client.get("/api/shelters/nearest?lat=16.98&lon=82.24")
    assert res_shelter.status_code == 200
    shelters = res_shelter.json()
    assert len(shelters) > 0
    assert "distance_km" in shelters[0]

    # Multilingual copilot
    res_copilot = client.post("/api/citizen/copilot", json={
        "query": "Where is the nearest safe shelter?",
        "district": "Kakinada",
        "language": "te",
        "lat": 16.98,
        "lon": 82.24
    })
    assert res_copilot.status_code == 200
    copilot_data = res_copilot.json()
    assert "response" in copilot_data
    print("[PASS] Citizen shelter locator & multilingual copilot passed")

if __name__ == "__main__":
    print("Running Cyclone Impact Forecaster Backend Test Suite...")
    test_health()
    test_events_and_updates()
    test_districts()
    test_impact_scoring()
    test_forecast_comparison()
    test_hazard_scenarios()
    test_satellite_layers()
    test_advisory_approval_workflow()
    test_insurance_triggers()
    test_district_briefing()
    test_citizen_shelter_and_copilot()
    print("\n[SUCCESS] ALL 10 TEST SUITES PASSED PERFECTLY!")
