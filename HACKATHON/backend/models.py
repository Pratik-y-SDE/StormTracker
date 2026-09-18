from pydantic import BaseModel, Field
from typing import List, Dict, Optional, Any

class CycloneTrackPoint(BaseModel):
    step: int
    lat: float
    lon: float
    wind_kmh: float
    pressure_hpa: float
    forecast_time: str
    category: str
    uncertainty_radius_km: float

class CycloneForecast(BaseModel):
    event_id: str
    name: str
    update_id: str
    timestamp: str
    source: str
    confidence: str
    horizon_hours: int
    track: List[CycloneTrackPoint]

class Asset(BaseModel):
    id: str
    name: str
    type: str  # Hospital, Substation, Bridge, Shelter, School, Water Treatment
    district: str
    lat: float
    lon: float
    criticality: int  # 1 to 5
    population_served: int
    backup_power: str  # Verified, Unverified, None
    elevation_m: float
    access_route_status: str  # Normal, Flood Prone, Bridge Dependent
    last_inspected: str  # Date string or 'Stale'
    details: Dict[str, Any] = Field(default_factory=dict)

class FactorBreakdown(BaseModel):
    hazard_exposure: float
    vulnerability: float
    consequence: float
    access_criticality: float
    data_confidence: float

class ImpactScore(BaseModel):
    asset_id: str
    name: str
    type: str
    district: str
    lat: float
    lon: float
    criticality: int
    total_score: float
    risk_band: str  # Immediate attention, Prioritize, Prepare, Monitor
    factor_breakdown: FactorBreakdown
    top_factors: List[str]
    recommended_action: str
    scenario_sensitivity: str  # Stable across scenarios, Sensitive to East Shift, Sensitive to West Shift
    distance_to_track_km: float
    in_corridor: bool
    surge_risk_level: str
    rainfall_risk_level: str
    population_served: int
    backup_power: str

class SatelliteLayer(BaseModel):
    id: str
    sensor: str  # Sentinel-1 SAR, Sentinel-2 Optical, SRTM DEM
    acquisition_time: str
    indicator: str
    confidence: str
    description: str
    geojson_data: Dict[str, Any]

class SurgeScenario(BaseModel):
    scenario_type: str  # Low, Central, High
    surge_height_m: float
    inundation_boundary: Dict[str, Any]
    affected_assets_count: int

class RainfallPathway(BaseModel):
    district_id: str
    accumulation_mm: float
    waterlogged_roads: List[str]
    cut_off_facilities: List[str]
    advisory: str

class ActionRecord(BaseModel):
    id: str
    asset_id: str
    asset_name: str
    district: str
    action_description: str
    priority: str
    owner: str
    status: str  # Not Started, In Progress, Verified, Closed
    updated_at: str
    notes: Optional[str] = ""

class ActionUpdate(BaseModel):
    status: Optional[str] = None
    owner: Optional[str] = None
    notes: Optional[str] = None

class AdvisoryDraft(BaseModel):
    id: str
    district_id: str
    target_audience: str
    evidence_summary: str
    draft_text: str
    approval_status: str  # Draft, Approved, Dispatched
    approver: Optional[str] = None
    timestamp: str

class AdvisoryApproval(BaseModel):
    advisory_id: str
    approver_name: str
    approved: bool
    dispatch_channel: Optional[str] = "Disaster Management Ops Network"
    custom_notes: Optional[str] = ""

class InsuranceTrigger(BaseModel):
    policy_id: str
    zone_name: str
    trigger_type: str
    threshold_value: str
    current_value: str
    is_triggered: bool
    exposed_assets_count: int
    exposed_population: int
    payout_readiness_signal: Dict[str, Any]

class ComparisonResult(BaseModel):
    from_update: str
    to_update: str
    new_high_risk: List[Dict[str, Any]]
    dropped_high_risk: List[Dict[str, Any]]
    score_changes: List[Dict[str, Any]]
    district_deltas: List[Dict[str, Any]]
    reprioritized_actions: List[Dict[str, Any]]
    narrative_cause: str

class DistrictBrief(BaseModel):
    district_id: str
    district_name: str
    summary: str
    top_assets: List[Dict[str, Any]]
    critical_actions: List[Dict[str, Any]]
    shelter_status: List[Dict[str, Any]]
    caveats: List[str]
    generated_at: str
    model_version: str
