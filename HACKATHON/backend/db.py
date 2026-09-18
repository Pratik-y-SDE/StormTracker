import sqlite3
import json
import os
from typing import List, Dict, Any, Optional

DB_PATH = os.path.join(os.path.dirname(__file__), "cyclone_forecaster.db")

def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_connection()
    cursor = conn.cursor()

    # Table for Cyclone Events
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS events (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        basin TEXT NOT NULL,
        season TEXT NOT NULL,
        current_category TEXT NOT NULL
    );
    """)

    # Table for Forecast Updates
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS forecast_updates (
        id TEXT PRIMARY KEY,
        event_id TEXT NOT NULL,
        update_number INTEGER NOT NULL,
        timestamp TEXT NOT NULL,
        source TEXT NOT NULL,
        confidence TEXT NOT NULL,
        horizon_hours INTEGER NOT NULL,
        track_json TEXT NOT NULL,
        FOREIGN KEY (event_id) REFERENCES events (id)
    );
    """)

    # Table for Districts
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS districts (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        state TEXT NOT NULL,
        headquarters TEXT NOT NULL,
        total_population INTEGER NOT NULL,
        coastal_length_km REAL NOT NULL,
        center_lat REAL NOT NULL,
        center_lon REAL NOT NULL,
        boundary_geojson TEXT NOT NULL
    );
    """)

    # Table for Infrastructure Assets
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS assets (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        type TEXT NOT NULL,
        district TEXT NOT NULL,
        lat REAL NOT NULL,
        lon REAL NOT NULL,
        criticality INTEGER NOT NULL,
        population_served INTEGER NOT NULL,
        backup_power TEXT NOT NULL,
        elevation_m REAL NOT NULL,
        access_route_status TEXT NOT NULL,
        last_inspected TEXT NOT NULL,
        details_json TEXT NOT NULL,
        FOREIGN KEY (district) REFERENCES districts (id)
    );
    """)

    # Table for GEE Satellite Layers
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS satellite_layers (
        id TEXT PRIMARY KEY,
        sensor TEXT NOT NULL,
        acquisition_time TEXT NOT NULL,
        indicator TEXT NOT NULL,
        confidence TEXT NOT NULL,
        description TEXT NOT NULL,
        geojson_data TEXT NOT NULL
    );
    """)

    # Table for Actions
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS actions (
        id TEXT PRIMARY KEY,
        asset_id TEXT NOT NULL,
        asset_name TEXT NOT NULL,
        district TEXT NOT NULL,
        action_description TEXT NOT NULL,
        priority TEXT NOT NULL,
        owner TEXT NOT NULL,
        status TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        notes TEXT,
        FOREIGN KEY (asset_id) REFERENCES assets (id)
    );
    """)

    # Table for Advisories (Human-in-the-Loop)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS advisories (
        id TEXT PRIMARY KEY,
        district_id TEXT NOT NULL,
        target_audience TEXT NOT NULL,
        evidence_summary TEXT NOT NULL,
        draft_text TEXT NOT NULL,
        approval_status TEXT NOT NULL,
        approver TEXT,
        timestamp TEXT NOT NULL,
        dispatch_channel TEXT
    );
    """)

    # Table for Parametric Insurance Policies
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS insurance_policies (
        id TEXT PRIMARY KEY,
        zone_name TEXT NOT NULL,
        district_id TEXT NOT NULL,
        trigger_type TEXT NOT NULL,
        threshold_value TEXT NOT NULL,
        insured_entity TEXT NOT NULL,
        payout_amount_inr TEXT NOT NULL
    );
    """)

    conn.commit()
    conn.close()

    # Seed data if empty
    seed_data_if_needed()

def seed_data_if_needed():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) as count FROM events;")
    row = cursor.fetchone()
    if row["count"] > 0:
        conn.close()
        return

    print("Seeding Cyclone Impact Forecaster database with Coastal Andhra Pradesh pilot data...")

    # 1. Event: Severe Cyclonic Storm JAWHAR
    cursor.execute("""
    INSERT INTO events (id, name, basin, season, current_category)
    VALUES ('cyclone-jawhar-2026', 'Severe Cyclonic Storm JAWHAR', 'Bay of Bengal', 'Pre-Monsoon 2026', 'VSCS');
    """)

    # 2. Districts (5 Coastal AP Districts with simplified realistic polygon boundaries)
    districts_data = [
        {
            "id": "visakhapatnam",
            "name": "Visakhapatnam",
            "state": "Andhra Pradesh",
            "headquarters": "Visakhapatnam",
            "total_population": 2185000,
            "coastal_length_km": 132.0,
            "center_lat": 17.6868,
            "center_lon": 83.2185,
            "boundary": {
                "type": "Polygon",
                "coordinates": [[[83.05, 17.55], [83.40, 17.70], [83.45, 17.90], [83.20, 17.95], [82.95, 17.75], [83.05, 17.55]]]
            }
        },
        {
            "id": "kakinada",
            "name": "Kakinada",
            "state": "Andhra Pradesh",
            "headquarters": "Kakinada",
            "total_population": 1950000,
            "coastal_length_km": 115.0,
            "center_lat": 16.9891,
            "center_lon": 82.2475,
            "boundary": {
                "type": "Polygon",
                "coordinates": [[[82.10, 16.75], [82.40, 16.90], [82.42, 17.20], [82.15, 17.25], [81.95, 16.95], [82.10, 16.75]]]
            }
        },
        {
            "id": "krishna",
            "name": "Krishna / Machilipatnam",
            "state": "Andhra Pradesh",
            "headquarters": "Machilipatnam",
            "total_population": 1780000,
            "coastal_length_km": 88.0,
            "center_lat": 16.1876,
            "center_lon": 81.1389,
            "boundary": {
                "type": "Polygon",
                "coordinates": [[[80.95, 15.95], [81.30, 16.10], [81.35, 16.35], [81.05, 16.40], [80.85, 16.15], [80.95, 15.95]]]
            }
        },
        {
            "id": "bapatla",
            "name": "Bapatla",
            "state": "Andhra Pradesh",
            "headquarters": "Bapatla",
            "total_population": 1580000,
            "coastal_length_km": 72.0,
            "center_lat": 15.9042,
            "center_lon": 80.4674,
            "boundary": {
                "type": "Polygon",
                "coordinates": [[[80.20, 15.70], [80.55, 15.80], [80.60, 16.05], [80.35, 16.10], [80.15, 15.85], [80.20, 15.70]]]
            }
        },
        {
            "id": "srikakulam",
            "name": "Srikakulam",
            "state": "Andhra Pradesh",
            "headquarters": "Srikakulam",
            "total_population": 2700000,
            "coastal_length_km": 193.0,
            "center_lat": 18.2969,
            "center_lon": 83.8968,
            "boundary": {
                "type": "Polygon",
                "coordinates": [[[83.70, 18.15], [84.15, 18.35], [84.20, 18.65], [83.85, 18.60], [83.60, 18.30], [83.70, 18.15]]]
            }
        }
    ]

    for d in districts_data:
        cursor.execute("""
        INSERT INTO districts (id, name, state, headquarters, total_population, coastal_length_km, center_lat, center_lon, boundary_geojson)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
        """, (d["id"], d["name"], d["state"], d["headquarters"], d["total_population"], d["coastal_length_km"], d["center_lat"], d["center_lon"], json.dumps(d["boundary"])))

    # 3. Forecast Updates (3 Sequential Updates demonstrating clear Track Recurvature)
    # Update 1: South-West track aiming at Bapatla / Krishna (T-36h)
    track_update_1 = [
        {"step": 0, "lat": 13.8, "lon": 84.5, "wind_kmh": 90, "pressure_hpa": 992, "forecast_time": "T-36h (Actual)", "category": "CS", "uncertainty_radius_km": 30.0},
        {"step": 1, "lat": 14.6, "lon": 83.2, "wind_kmh": 115, "pressure_hpa": 982, "forecast_time": "T-24h", "category": "SCS", "uncertainty_radius_km": 50.0},
        {"step": 2, "lat": 15.4, "lon": 81.8, "wind_kmh": 130, "pressure_hpa": 974, "forecast_time": "T-12h", "category": "VSCS", "uncertainty_radius_km": 75.0},
        {"step": 3, "lat": 15.9, "lon": 80.6, "wind_kmh": 145, "pressure_hpa": 965, "forecast_time": "Landfall (Bapatla Coast)", "category": "VSCS", "uncertainty_radius_km": 100.0},
        {"step": 4, "lat": 16.4, "lon": 79.8, "wind_kmh": 85, "pressure_hpa": 990, "forecast_time": "+12h (Inland)", "category": "CS", "uncertainty_radius_km": 140.0}
    ]

    # Update 2: Central track shifting slightly north towards Machilipatnam (T-24h)
    track_update_2 = [
        {"step": 0, "lat": 14.7, "lon": 83.4, "wind_kmh": 120, "pressure_hpa": 980, "forecast_time": "T-24h (Actual)", "category": "SCS", "uncertainty_radius_km": 25.0},
        {"step": 1, "lat": 15.4, "lon": 82.5, "wind_kmh": 135, "pressure_hpa": 972, "forecast_time": "T-12h", "category": "VSCS", "uncertainty_radius_km": 45.0},
        {"step": 2, "lat": 16.2, "lon": 81.4, "wind_kmh": 150, "pressure_hpa": 962, "forecast_time": "Landfall (Krishna / Machilipatnam)", "category": "VSCS", "uncertainty_radius_km": 65.0},
        {"step": 3, "lat": 16.8, "lon": 80.8, "wind_kmh": 95, "pressure_hpa": 985, "forecast_time": "+12h (Inland)", "category": "SCS", "uncertainty_radius_km": 90.0}
    ]

    # Update 3: Sharp North-East recurvature tracking along Kakinada & Visakhapatnam (T-12h)
    track_update_3 = [
        {"step": 0, "lat": 15.6, "lon": 82.9, "wind_kmh": 135, "pressure_hpa": 970, "forecast_time": "T-12h (Actual)", "category": "VSCS", "uncertainty_radius_km": 20.0},
        {"step": 1, "lat": 16.4, "lon": 82.7, "wind_kmh": 150, "pressure_hpa": 960, "forecast_time": "T-06h (Approaching Kakinada)", "category": "VSCS", "uncertainty_radius_km": 35.0},
        {"step": 2, "lat": 17.0, "lon": 82.8, "wind_kmh": 160, "pressure_hpa": 952, "forecast_time": "Landfall Window (Near Kakinada-Yanam)", "category": "VSCS", "uncertainty_radius_km": 50.0},
        {"step": 3, "lat": 17.7, "lon": 83.3, "wind_kmh": 140, "pressure_hpa": 966, "forecast_time": "+06h (Skirting Visakhapatnam Coast)", "category": "VSCS", "uncertainty_radius_km": 65.0},
        {"step": 4, "lat": 18.4, "lon": 84.1, "wind_kmh": 105, "pressure_hpa": 982, "forecast_time": "+18h (Toward Srikakulam)", "category": "SCS", "uncertainty_radius_km": 90.0}
    ]

    cursor.execute("""
    INSERT INTO forecast_updates (id, event_id, update_number, timestamp, source, confidence, horizon_hours, track_json)
    VALUES 
    ('update-01', 'cyclone-jawhar-2026', 1, '2026-05-18T06:00:00Z', 'IMD Official Bulletin 04', 'Moderate (65%)', 36, ?),
    ('update-02', 'cyclone-jawhar-2026', 2, '2026-05-18T12:00:00Z', 'IMD Official Bulletin 05', 'High (80%)', 24, ?),
    ('update-03', 'cyclone-jawhar-2026', 3, '2026-05-18T18:00:00Z', 'IMD Special Tropical Advisory 06', 'Very High (92%)', 18, ?);
    """, (json.dumps(track_update_1), json.dumps(track_update_2), json.dumps(track_update_3)))

    # 4. Infrastructure Assets (42 Assets covering all 6 categories, including edge cases)
    assets_data = [
        # Visakhapatnam
        {
            "id": "vizag-hosp-01",
            "name": "King George Hospital (KGH)",
            "type": "Hospital",
            "district": "visakhapatnam",
            "lat": 17.7078,
            "lon": 83.3055,
            "criticality": 5,
            "population_served": 850000,
            "backup_power": "Verified",
            "elevation_m": 12.0,
            "access_route_status": "Normal",
            "last_inspected": "2026-05-10",
            "details": {"beds": 1200, "icu_capacity": 95, "oxygen_plant": "On-site PSA Plant"}
        },
        {
            "id": "vizag-hosp-02",
            "name": "Visakha Institute of Medical Sciences (VIMS)",
            "type": "Hospital",
            "district": "visakhapatnam",
            "lat": 17.7554,
            "lon": 83.3242,
            "criticality": 5,
            "population_served": 600000,
            "backup_power": "Unverified",  # Vulnerability factor
            "elevation_m": 8.5,
            "access_route_status": "Bridge Dependent",
            "last_inspected": "2025-11-20",
            "details": {"beds": 650, "icu_capacity": 60, "oxygen_plant": "Liquid O2 Cylinder Dependent"}
        },
        {
            "id": "vizag-sub-01",
            "name": "Gajuwaka 220kV Grid Substation",
            "type": "Substation",
            "district": "visakhapatnam",
            "lat": 17.6890,
            "lon": 83.1980,
            "criticality": 5,
            "population_served": 720000,
            "backup_power": "Verified",
            "elevation_m": 14.0,
            "access_route_status": "Normal",
            "last_inspected": "2026-04-15",
            "details": {"capacity_mva": 320, "feeders": 8, "industrial_supply": True}
        },
        {
            "id": "vizag-sub-02",
            "name": "Pedagantyada 33/11kV Coastal Substation",
            "type": "Substation",
            "district": "visakhapatnam",
            "lat": 17.6520,
            "lon": 83.2350,
            "criticality": 4,
            "population_served": 180000,
            "backup_power": "None",  # Vulnerability factor
            "elevation_m": 3.2,      # High surge vulnerability
            "access_route_status": "Flood Prone",
            "last_inspected": "2026-03-01",
            "details": {"capacity_mva": 25, "feeders": 4, "coastal_buffer_m": 450}
        },
        {
            "id": "vizag-brg-01",
            "name": "Gosthani River Estuary Bridge",
            "type": "Bridge",
            "district": "visakhapatnam",
            "lat": 17.8920,
            "lon": 83.4560,
            "criticality": 4,
            "population_served": 140000,
            "backup_power": "None",
            "elevation_m": 4.5,
            "access_route_status": "Bridge Dependent",
            "last_inspected": "2026-01-18",
            "details": {"span_m": 380, "clearance_m": 3.2, "alternate_detour_km": 28.5}
        },
        {
            "id": "vizag-shl-01",
            "name": "Lawson's Bay Multi-Purpose Cyclone Shelter",
            "type": "Shelter",
            "district": "visakhapatnam",
            "lat": 17.7340,
            "lon": 83.3380,
            "criticality": 4,
            "population_served": 2500,
            "backup_power": "Verified",
            "elevation_m": 9.0,
            "access_route_status": "Normal",
            "last_inspected": "2026-05-12",
            "details": {"capacity": 2200, "potable_water": True, "solar_battery": True}
        },
        {
            "id": "vizag-wtr-01",
            "name": "Kanithi Balancing Reservoir & Pump Station",
            "type": "Water Treatment",
            "district": "visakhapatnam",
            "lat": 17.6350,
            "lon": 83.1850,
            "criticality": 5,
            "population_served": 950000,
            "backup_power": "Verified",
            "elevation_m": 16.0,
            "access_route_status": "Normal",
            "last_inspected": "2026-04-28",
            "details": {"capacity_mld": 150, "pumping_stages": 3}
        },
        {
            "id": "vizag-sch-01",
            "name": "Bheemili Coastal High School Relief Camp",
            "type": "School",
            "district": "visakhapatnam",
            "lat": 17.8890,
            "lon": 83.4480,
            "criticality": 3,
            "population_served": 1200,
            "backup_power": "Unverified",
            "elevation_m": 7.0,
            "access_route_status": "Normal",
            "last_inspected": "2026-02-14",
            "details": {"capacity": 1500, "kitchen_facilities": True}
        },

        # Kakinada
        {
            "id": "kak-hosp-01",
            "name": "Government General Hospital Kakinada (GGH)",
            "type": "Hospital",
            "district": "kakinada",
            "lat": 16.9640,
            "lon": 82.2380,
            "criticality": 5,
            "population_served": 750000,
            "backup_power": "Verified",
            "elevation_m": 3.8,  # Coastal delta low elevation
            "access_route_status": "Normal",
            "last_inspected": "2026-05-08",
            "details": {"beds": 950, "icu_capacity": 75, "oxygen_plant": "PSA Plant + Cryogenic Tank"}
        },
        {
            "id": "kak-hosp-02",
            "name": "Community Health Center Yanam Border",
            "type": "Hospital",
            "district": "kakinada",
            "lat": 16.7320,
            "lon": 82.2150,
            "criticality": 4,
            "population_served": 120000,
            "backup_power": "None",
            "elevation_m": 2.2,  # Surge hazard zone
            "access_route_status": "Flood Prone",
            "last_inspected": "2026-03-15",
            "details": {"beds": 100, "emergency_maternity": True}
        },
        {
            "id": "kak-sub-01",
            "name": "Kakinada Deepwater Port 132kV Substation",
            "type": "Substation",
            "district": "kakinada",
            "lat": 16.9850,
            "lon": 82.2680,
            "criticality": 5,
            "population_served": 480000,
            "backup_power": "None",  # High consequence, no backup
            "elevation_m": 2.1,      # High surge risk
            "access_route_status": "Flood Prone",
            "last_inspected": "2026-04-02",
            "details": {"capacity_mva": 160, "port_cranes": True, "feeders": 6}
        },
        {
            "id": "kak-sub-02",
            "name": "Jagannaickpur 33/11kV Substation",
            "type": "Substation",
            "district": "kakinada",
            "lat": 16.9420,
            "lon": 82.2410,
            "criticality": 3,
            "population_served": 95000,
            "backup_power": "Unverified",
            "elevation_m": 2.8,
            "access_route_status": "Bridge Dependent",
            "last_inspected": "Stale 2023",  # Stale data confidence penalty
            "details": {"capacity_mva": 15, "missing_maintenance_log": True}
        },
        {
            "id": "kak-brg-01",
            "name": "Coringa Mangrove Estuary Bridge",
            "type": "Bridge",
            "district": "kakinada",
            "lat": 16.8450,
            "lon": 82.2850,
            "criticality": 5,
            "population_served": 210000,
            "backup_power": "None",
            "elevation_m": 2.6,
            "access_route_status": "Bridge Dependent",
            "last_inspected": "2026-02-28",
            "details": {"vital_evacuation_lifeline": True, "clearance_m": 2.1}
        },
        {
            "id": "kak-shl-01",
            "name": "Uppada Coastal Multi-Purpose Shelter",
            "type": "Shelter",
            "district": "kakinada",
            "lat": 17.0850,
            "lon": 82.3250,
            "criticality": 5,
            "population_served": 3500,
            "backup_power": "Verified",
            "elevation_m": 5.2,
            "access_route_status": "Flood Prone",
            "last_inspected": "2026-05-14",
            "details": {"capacity": 3000, "sea_wall_proximity_m": 80, "geotube_protected": True}
        },
        {
            "id": "kak-wtr-01",
            "name": "Kakinada Municipal Water Treatment Plant",
            "type": "Water Treatment",
            "district": "kakinada",
            "lat": 17.0120,
            "lon": 82.2210,
            "criticality": 4,
            "population_served": 420000,
            "backup_power": "Verified",
            "elevation_m": 4.1,
            "access_route_status": "Normal",
            "last_inspected": "2026-04-10",
            "details": {"capacity_mld": 65, "chlorination_reserve_days": 14}
        },
        {
            "id": "kak-sch-01",
            "name": "Uppada Zilla Parishad High School Relief Center",
            "type": "School",
            "district": "kakinada",
            "lat": 17.0780,
            "lon": 82.3120,
            "criticality": 3,
            "population_served": 1800,
            "backup_power": "None",
            "elevation_m": 4.8,
            "access_route_status": "Normal",
            "last_inspected": "2026-01-10",
            "details": {"capacity": 1200}
        },
        # Edge case: High hazard but low consequence
        {
            "id": "kak-edge-01",
            "name": "Kakinada Spit Unmanned Meteorological Tower Shed",
            "type": "Water Treatment",
            "district": "kakinada",
            "lat": 16.9920,
            "lon": 82.3020,
            "criticality": 1,  # Low consequence
            "population_served": 0,
            "backup_power": "None",
            "elevation_m": 1.2,  # Extreme surge hazard
            "access_route_status": "Bridge Dependent",
            "last_inspected": "2026-05-01",
            "details": {"unmanned": True, "instrument_only": True}
        },

        # Krishna / Machilipatnam
        {
            "id": "kri-hosp-01",
            "name": "District Headquarters Hospital Machilipatnam",
            "type": "Hospital",
            "district": "krishna",
            "lat": 16.1820,
            "lon": 81.1350,
            "criticality": 5,
            "population_served": 550000,
            "backup_power": "Verified",
            "elevation_m": 3.1,
            "access_route_status": "Normal",
            "last_inspected": "2026-05-02",
            "details": {"beds": 500, "icu_capacity": 45}
        },
        {
            "id": "kri-hosp-02",
            "name": "Avanigadda Area Hospital",
            "type": "Hospital",
            "district": "krishna",
            "lat": 16.0250,
            "lon": 80.9150,
            "criticality": 4,
            "population_served": 180000,
            "backup_power": "None",
            "elevation_m": 2.4,
            "access_route_status": "Flood Prone",
            "last_inspected": "2026-03-20",
            "details": {"beds": 120, "island_delta_access": True}
        },
        {
            "id": "kri-sub-01",
            "name": "Chilakalapudi 132/33kV Substation",
            "type": "Substation",
            "district": "krishna",
            "lat": 16.1950,
            "lon": 81.1620,
            "criticality": 4,
            "population_served": 340000,
            "backup_power": "Unverified",
            "elevation_m": 2.5,
            "access_route_status": "Normal",
            "last_inspected": "Stale 2022",  # Stale data record
            "details": {"capacity_mva": 100, "records_incomplete": True}
        },
        {
            "id": "kri-sub-02",
            "name": "Nagayalanka 33/11kV Delta Substation",
            "type": "Substation",
            "district": "krishna",
            "lat": 15.9450,
            "lon": 80.9150,
            "criticality": 4,
            "population_served": 85000,
            "backup_power": "None",
            "elevation_m": 1.6,  # Severe surge vulnerability
            "access_route_status": "Flood Prone",
            "last_inspected": "2026-04-12",
            "details": {"capacity_mva": 12, "mangrove_fringe": True}
        },
        {
            "id": "kri-brg-01",
            "name": "Bandar Canal Major Causeway Bridge",
            "type": "Bridge",
            "district": "krishna",
            "lat": 16.1680,
            "lon": 81.1210,
            "criticality": 5,
            "population_served": 290000,
            "backup_power": "None",
            "elevation_m": 2.8,
            "access_route_status": "Bridge Dependent",
            "last_inspected": "2026-01-25",
            "details": {"sole_artery_to_beach_belt": True}
        },
        {
            "id": "kri-shl-01",
            "name": "Manginapudi Beach Cyclone Shelter Hub",
            "type": "Shelter",
            "district": "krishna",
            "lat": 16.2250,
            "lon": 81.1980,
            "criticality": 5,
            "population_served": 4000,
            "backup_power": "Verified",
            "elevation_m": 6.5,
            "access_route_status": "Flood Prone",
            "last_inspected": "2026-05-11",
            "details": {"capacity": 3500, "stilted_design": True, "high_capacity": True}
        },
        {
            "id": "kri-shl-02",
            "name": "Gilakaladindi Fishermen Cyclone Shelter",
            "type": "Shelter",
            "district": "krishna",
            "lat": 16.1480,
            "lon": 81.1650,
            "criticality": 4,
            "population_served": 1800,
            "backup_power": "Verified",
            "elevation_m": 4.2,
            "access_route_status": "Flood Prone",
            "last_inspected": "2026-04-19",
            "details": {"capacity": 1600, "boat_anchorage_adjacent": True}
        },
        {
            "id": "kri-wtr-01",
            "name": "Machilipatnam Coastal Pumping Station",
            "type": "Water Treatment",
            "district": "krishna",
            "lat": 16.1750,
            "lon": 81.1420,
            "criticality": 4,
            "population_served": 310000,
            "backup_power": "Verified",
            "elevation_m": 3.0,
            "access_route_status": "Normal",
            "last_inspected": "2026-03-30",
            "details": {"capacity_mld": 45}
        },

        # Bapatla
        {
            "id": "bap-hosp-01",
            "name": "Bapatla Area Hospital",
            "type": "Hospital",
            "district": "bapatla",
            "lat": 15.9080,
            "lon": 80.4710,
            "criticality": 5,
            "population_served": 320000,
            "backup_power": "Verified",
            "elevation_m": 5.5,
            "access_route_status": "Normal",
            "last_inspected": "2026-05-05",
            "details": {"beds": 250, "icu_capacity": 25}
        },
        {
            "id": "bap-sub-01",
            "name": "Karlapalem 33/11kV Substation",
            "type": "Substation",
            "district": "bapatla",
            "lat": 15.9420,
            "lon": 80.5250,
            "criticality": 4,
            "population_served": 75000,
            "backup_power": "None",
            "elevation_m": 3.4,
            "access_route_status": "Flood Prone",
            "last_inspected": "2026-02-18",
            "details": {"capacity_mva": 15}
        },
        {
            "id": "bap-brg-01",
            "name": "Romperu Drain Coastal Bridge",
            "type": "Bridge",
            "district": "bapatla",
            "lat": 15.8650,
            "lon": 80.4210,
            "criticality": 4,
            "population_served": 110000,
            "backup_power": "None",
            "elevation_m": 3.8,
            "access_route_status": "Bridge Dependent",
            "last_inspected": "2026-01-30",
            "details": {"drainage_choke_risk": True}
        },
        {
            "id": "bap-shl-01",
            "name": "Suryalanka Beach Cyclone Shelter",
            "type": "Shelter",
            "district": "bapatla",
            "lat": 15.8520,
            "lon": 80.5180,
            "criticality": 5,
            "population_served": 2500,
            "backup_power": "Verified",
            "elevation_m": 7.2,
            "access_route_status": "Flood Prone",
            "last_inspected": "2026-05-09",
            "details": {"capacity": 2200, "coastal_sand_dune_shield": True}
        },
        {
            "id": "bap-sch-01",
            "name": "Bapatla Agricultural College Relief Camp",
            "type": "School",
            "district": "bapatla",
            "lat": 15.9150,
            "lon": 80.4550,
            "criticality": 3,
            "population_served": 1500,
            "backup_power": "Verified",
            "elevation_m": 6.8,
            "access_route_status": "Normal",
            "last_inspected": "2026-04-14",
            "details": {"capacity": 1800, "large_hall": True}
        },
        {
            "id": "bap-wtr-01",
            "name": "Nizampatnam Harbor Water Supply Tank",
            "type": "Water Treatment",
            "district": "bapatla",
            "lat": 15.9020,
            "lon": 80.6550,
            "criticality": 3,
            "population_served": 65000,
            "backup_power": "None",
            "elevation_m": 2.2,
            "access_route_status": "Flood Prone",
            "last_inspected": "2026-03-12",
            "details": {"capacity_mld": 12}
        },
        # Edge case: Low consequence, high surge risk
        {
            "id": "bap-edge-01",
            "name": "Suryalanka Unmanned Salt Pan Storage Shed",
            "type": "Water Treatment",
            "district": "bapatla",
            "lat": 15.8450,
            "lon": 80.4950,
            "criticality": 1,
            "population_served": 0,
            "backup_power": "None",
            "elevation_m": 1.1,
            "access_route_status": "Flood Prone",
            "last_inspected": "2026-04-01",
            "details": {"unmanned": True, "raw_salt_storage": True}
        },

        # Srikakulam
        {
            "id": "sri-hosp-01",
            "name": "Rajiv Gandhi Institute of Medical Sciences (RIMS)",
            "type": "Hospital",
            "district": "srikakulam",
            "lat": 18.3050,
            "lon": 83.9020,
            "criticality": 5,
            "population_served": 920000,
            "backup_power": "Verified",
            "elevation_m": 15.5,
            "access_route_status": "Normal",
            "last_inspected": "2026-05-06",
            "details": {"beds": 800, "icu_capacity": 70, "tertiary_care": True}
        },
        {
            "id": "sri-sub-01",
            "name": "Kalingapatnam 33/11kV Coastal Substation",
            "type": "Substation",
            "district": "srikakulam",
            "lat": 18.3380,
            "lon": 84.1250,
            "criticality": 4,
            "population_served": 110000,
            "backup_power": "None",
            "elevation_m": 4.2,
            "access_route_status": "Bridge Dependent",
            "last_inspected": "2026-03-25",
            "details": {"capacity_mva": 20, "lighthouse_feeder": True}
        },
        {
            "id": "sri-brg-01",
            "name": "Nagavali River Major Estuary Bridge",
            "type": "Bridge",
            "district": "srikakulam",
            "lat": 18.2850,
            "lon": 83.8950,
            "criticality": 5,
            "population_served": 450000,
            "backup_power": "None",
            "elevation_m": 8.0,
            "access_route_status": "Normal",
            "last_inspected": "2026-02-10",
            "details": {"span_m": 620, "nh16_connector": True}
        },
        {
            "id": "sri-shl-01",
            "name": "Bhavanapadu Port Cyclone Shelter",
            "type": "Shelter",
            "district": "srikakulam",
            "lat": 18.5720,
            "lon": 84.3480,
            "criticality": 4,
            "population_served": 2800,
            "backup_power": "Verified",
            "elevation_m": 6.0,
            "access_route_status": "Normal",
            "last_inspected": "2026-05-01",
            "details": {"capacity": 2500, "fisherman_hub": True}
        },
        {
            "id": "sri-sch-01",
            "name": "Kalingapatnam Government High School Relief Camp",
            "type": "School",
            "district": "srikakulam",
            "lat": 18.3410,
            "lon": 84.1180,
            "criticality": 3,
            "population_served": 1200,
            "backup_power": "None",
            "elevation_m": 5.0,
            "access_route_status": "Normal",
            "last_inspected": "2026-01-20",
            "details": {"capacity": 1000}
        },
        {
            "id": "sri-wtr-01",
            "name": "Srikakulam Headworks Water Supply",
            "type": "Water Treatment",
            "district": "srikakulam",
            "lat": 18.3120,
            "lon": 83.8820,
            "criticality": 4,
            "population_served": 280000,
            "backup_power": "Verified",
            "elevation_m": 12.0,
            "access_route_status": "Normal",
            "last_inspected": "2026-04-18",
            "details": {"capacity_mld": 40}
        }
    ]

    for a in assets_data:
        cursor.execute("""
        INSERT INTO assets (id, name, type, district, lat, lon, criticality, population_served, backup_power, elevation_m, access_route_status, last_inspected, details_json)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
        """, (a["id"], a["name"], a["type"], a["district"], a["lat"], a["lon"], a["criticality"], a["population_served"], a["backup_power"], a["elevation_m"], a["access_route_status"], a["last_inspected"], json.dumps(a["details"])))

    # 5. GEE Satellite Layers (Sentinel-1 SAR inundation, Sentinel-2 land cover, DEM elevation)
    sar_inundation_geojson = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {"sensor": "Sentinel-1 SAR C-Band", "flood_depth_est": "0.4m - 1.2m", "confidence": "High (94%)", "zone": "Kakinada Coringa Estuary"},
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [[[82.20, 16.80], [82.35, 16.82], [82.38, 17.02], [82.22, 17.00], [82.20, 16.80]]]
                }
            },
            {
                "type": "Feature",
                "properties": {"sensor": "Sentinel-1 SAR C-Band", "flood_depth_est": "0.6m - 1.5m", "confidence": "High (91%)", "zone": "Krishna Delta Manginapudi Belt"},
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [[[81.10, 16.12], [81.25, 16.15], [81.28, 16.28], [81.12, 16.25], [81.10, 16.12]]]
                }
            }
        ]
    }

    dem_contours_geojson = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {"sensor": "SRTM 30m DEM", "contour_level": "< 3m Extreme Surge Hazard Zone", "elevation_band": "0m - 3m"},
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [[[82.15, 16.70], [82.45, 16.85], [82.48, 17.15], [82.25, 17.20], [82.15, 16.70]]]
                }
            }
        ]
    }

    cursor.execute("""
    INSERT INTO satellite_layers (id, sensor, acquisition_time, indicator, confidence, description, geojson_data)
    VALUES 
    ('layer-s1-sar', 'Sentinel-1 SAR', '2026-05-18T04:20:00Z', 'Radar Surface Water Inundation', '94% (Cloud-independent)', 'Pre-landfall tidal surge and saturated soil backscatter anomalies detected across Godavari/Krishna estuaries.', ?),
    ('layer-dem-srtm', 'SRTM 30m DEM', '2026-05-01T00:00:00Z', 'Coastal Topographic Elevation', '99% (Calibrated)', 'Low-elevation coastal vulnerability contours identifying infrastructure below 3m Mean Sea Level.', ?);
    """, (json.dumps(sar_inundation_geojson), json.dumps(dem_contours_geojson)))

    # 6. Seed Initial Actions
    initial_actions = [
        ("act-01", "kak-sub-01", "Kakinada Deepwater Port 132kV Substation", "kakinada", "Deploy mobile 1000kVA emergency generator and verify perimeter sandbagging", "Immediate attention", "State Power Distribution Corp", "In Progress", "2026-05-18T18:30:00Z", "Corridor shift put substation in direct 150km/h wind field."),
        ("act-02", "vizag-hosp-02", "Visakha Institute of Medical Sciences (VIMS)", "visakhapatnam", "Inspect oxygen plant backup power and inspect Gosthani access route", "Immediate attention", "District Medical Health Officer", "Not Started", "2026-05-18T18:35:00Z", "Facility serves 600k population with unverified generator record."),
        ("act-03", "kri-shl-01", "Manginapudi Beach Cyclone Shelter Hub", "krishna", "Verify drinking water reserves and test VHF emergency radio transceiver", "Prioritize", "Tahsildar Machilipatnam", "Verified", "2026-05-18T17:15:00Z", "Confirmed ready with 4000 ration packets.")
    ]

    for a in initial_actions:
        cursor.execute("""
        INSERT INTO actions (id, asset_id, asset_name, district, action_description, priority, owner, status, updated_at, notes)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
        """, a)

    # 7. Seed Parametric Insurance Policies
    policies_data = [
        ("pol-01", "Kakinada Deepwater Port & Petrochemical Zone", "kakinada", "Wind Speed > 135 km/h OR Surge > 2.5m", "135 km/h Wind / 2.5m Surge", "Kakinada Seaports Authority & Marine Logistics", "INR 45,00,00,000"),
        ("pol-02", "Machilipatnam Aquaculture & Fisherman Infrastructure", "krishna", "Surge Scenario High (>3.0m) OR Inundation > 20%", "3.0m Storm Surge", "AP State Fishermen Cooperative Federation", "INR 28,00,00,000"),
        ("pol-03", "Visakhapatnam Coastal Utilities & Substation Grid", "visakhapatnam", "Wind Speed > 150 km/h", "150 km/h Wind", "Eastern Power Distribution Company of AP (EPDCL)", "INR 60,00,00,000"),
        ("pol-04", "Bapatla Agritech & Coastal Salinity Zone", "bapatla", "Inundation Area > 15 sq km OR Surge > 2.0m", "15 sq km Inundation / 2.0m Surge", "Bapatla Agricultural & Drainage Board", "INR 18,00,00,000")
    ]

    for p in policies_data:
        cursor.execute("""
        INSERT INTO insurance_policies (id, zone_name, district_id, trigger_type, threshold_value, insured_entity, payout_amount_inr)
        VALUES (?, ?, ?, ?, ?, ?, ?);
        """, p)

    # 8. Seed Initial Draft Advisory
    cursor.execute("""
    INSERT INTO advisories (id, district_id, target_audience, evidence_summary, draft_text, approval_status, approver, timestamp, dispatch_channel)
    VALUES (
        'adv-init-01',
        'kakinada',
        'District Administration & Essential Utility Operators',
        'Forecast Update 03 shows sharp 38km NE recurvature towards Kakinada coast with sustained winds of 150-160 km/h and high surge scenario (2.8m - 4.2m). Port Substation and Uppada coastal belt at extreme risk.',
        'URGENT PREPAREDNESS ADVISORY: Severe Cyclonic Storm JAWHAR has recurved towards Kakinada coast. Immediate mandatory shutdown of overhead 33kV feeders in coastal strip recommended by 22:00 hrs. Evacuation of all settlements within 500m of Uppada shoreline to verified cyclone shelters must be completed immediately. Pre-position emergency medical supplies at GGH Kakinada.',
        'Draft',
        NULL,
        '2026-05-18T18:45:00Z',
        'State Disaster Management Rapid Network'
    );
    """)

    conn.commit()
    conn.close()
    print("Database seeding completed successfully.")

if __name__ == "__main__":
    init_db()
