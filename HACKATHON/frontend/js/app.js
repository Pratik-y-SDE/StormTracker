/**
 * ZATICS v3.0 — CYCLONE IMPACT FORECASTER
 * Frontend Controller & Geospatial Intelligence Dashboard
 */

// Global State
const state = {
  currentUpdate: 'update-03',
  currentEvent: null,
  updatesList: [],
  districtsList: [],
  assetsData: [],
  summaryData: {},
  selectedAsset: null,
  insuranceTriggers: [],
  policyFilter: 'all',
  activeSurgeScenario: 'central',
  layers: {
    radar: true,
    surge: true,
    rainfall: false,
    geeSar: true,
    uncertaintyCone: true,
    shiftTracks: false
  },
  filters: {
    district: 'all',
    type: 'all',
    riskBand: 'all',
    search: ''
  },
  map: null,
  mapLayers: {
    track: null,
    cone: null,
    leftTrack: null,
    rightTrack: null,
    surgeLayer: null,
    rainfallLayer: null,
    geeLayer: null,
    assetMarkers: []
  }
};

// --- Initialization ---
document.addEventListener('DOMContentLoaded', async () => {
  initMap();
  setupEventListeners();
  await loadInitialData();
});

// --- Map Setup ---
function initMap() {
  // Center on Coastal Andhra Pradesh / Bay of Bengal
  state.map = L.map('map', {
    center: [16.5, 83.0],
    zoom: 7,
    zoomControl: false
  });

  L.control.zoom({ position: 'bottomright' }).addTo(state.map);

  // High-contrast Dark Matter CartoDB Basemap
  L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', {
    attribution: '&copy; <a href="https://carto.com/">CARTO</a> &copy; OpenStreetMap',
    subdomains: 'abcd',
    maxZoom: 19
  }).addTo(state.map);
}

// --- API Data Fetchers ---
async function loadInitialData() {
  try {
    // 1. Fetch Latest Event & Updates
    const eventRes = await fetch('/api/events/latest');
    const eventData = await eventRes.json();
    state.currentEvent = eventData;
    state.updatesList = eventData.updates || [];

    // 2. Fetch Districts
    const distRes = await fetch('/api/districts');
    state.districtsList = await distRes.json();
    populateDistrictFilter();

    // 3. Load Main Impact Data for Active Update
    await switchUpdate(state.currentUpdate);

  } catch (err) {
    console.error('Error initializing data:', err);
    showToast('⚠️ Error loading initial geospatial data', 'error');
  }
}

function populateDistrictFilter() {
  const select = document.getElementById('district-filter');
  if (!select) return;
  select.innerHTML = '<option value="all">All Districts</option>';
  state.districtsList.forEach(d => {
    const opt = document.createElement('option');
    opt.value = d.id;
    opt.textContent = d.name;
    select.appendChild(opt);
  });
}

// --- Switch Update (Update 1, 2, 3) ---
async function switchUpdate(updateId) {
  state.currentUpdate = updateId;
  
  // Update buttons state
  document.querySelectorAll('.update-btn').forEach(btn => {
    btn.classList.toggle('active', btn.dataset.update === updateId);
  });

  try {
    // Fetch Scored Assets for this update
    const res = await fetch(`/api/impact?update_id=${updateId}`);
    const data = await res.json();
    state.assetsData = data.assets || [];
    state.summaryData = data.summary || {};

    updateMetricStrip();
    renderAssetQueue();
    await updateMapLayers();
    await refreshPolicyMonitoring();

    showToast(`Loaded ${updateId.toUpperCase()} Track & Scored Assets`);
  } catch (err) {
    console.error('Failed to switch update:', err);
  }
}

// --- KPI Metric Strip Update ---
function updateMetricStrip() {
  const summary = state.summaryData;
  document.getElementById('kpi-critical-count').textContent = summary.critical_assets_count || 0;
  
  const popServed = (summary.exposed_population || 0).toLocaleString();
  document.getElementById('kpi-exposed-pop').textContent = popServed;

  const surgeEl = document.getElementById('kpi-surge-info');
  if (surgeEl) {
    surgeEl.textContent = `${summary.surge_height_m || 2.8}m (${state.activeSurgeScenario.toUpperCase()})`;
  }

  const actionEl = document.getElementById('kpi-top-action');
  if (actionEl && state.assetsData.length > 0) {
    actionEl.textContent = state.assetsData[0].recommended_action.slice(0, 45) + '...';
  }
}

// --- Map Layers & Overlays ---
async function updateMapLayers() {
  if (!state.map) return;

  // Clear previous layers
  clearMapLayers();

  const currentUpdateObj = state.updatesList.find(u => u.id === state.currentUpdate);
  if (!currentUpdateObj) return;

  const trackPoints = currentUpdateObj.track_points || [];

  // 1. Plot Cyclone Track Polyline
  if (trackPoints.length > 0) {
    const latlngs = trackPoints.map(p => [p.lat, p.lon]);
    state.mapLayers.track = L.polyline(latlngs, {
      color: '#ef4444',
      weight: 3.5,
      opacity: 0.95,
      dashArray: '4, 6'
    }).addTo(state.map);

    // Plot Cyclone Eye (Latest Forecast Point)
    const eyePoint = trackPoints[trackPoints.length - 1];
    const eyeIcon = L.divIcon({
      className: 'cyclone-eye-icon',
      html: `<div style="width:20px;height:20px;background:rgba(239,68,68,0.3);border:2px solid #ef4444;border-radius:50%;display:flex;align-items:center;justify-content:center;box-shadow:0 0 16px rgba(239,68,68,0.8);"><div style="width:6px;height:6px;background:#fff;border-radius:50%;"></div></div>`,
      iconSize: [20, 20],
      iconAnchor: [10, 10]
    });
    L.marker([eyePoint.lat, eyePoint.lon], { icon: eyeIcon })
      .bindPopup(`<b>${state.currentEvent.name} Eye</b><br>Wind: ${eyePoint.wind_kmh} km/h<br>Pressure: ${eyePoint.pressure_hpa} hPa`)
      .addTo(state.map);
  }

  // 2. Plot Uncertainty Corridor
  if (state.layers.uncertaintyCone) {
    try {
      const coneRes = await fetch(`/api/hazards/corridor?update_id=${state.currentUpdate}`);
      if (coneRes.ok) {
        const coneGeoJSON = await coneRes.json();
        state.mapLayers.cone = L.geoJSON(coneGeoJSON, {
          style: {
            color: '#38bdf8',
            weight: 1.5,
            fillColor: '#0284c7',
            fillOpacity: 0.12,
            dashArray: '3, 4'
          }
        }).addTo(state.map);
      }
    } catch (e) {
      console.warn('Could not load corridor geojson', e);
    }
  }

  // 3. Plot GEE Sentinel-1 SAR / Land Cover Layer
  if (state.layers.geeSar) {
    try {
      const geeRes = await fetch('/api/satellite/layers');
      const layers = await geeRes.json();
      const s1 = layers.find(l => l.sensor.includes('Sentinel-1'));
      if (s1 && s1.geojson) {
        state.mapLayers.geeLayer = L.geoJSON(s1.geojson, {
          style: {
            color: '#06b6d4',
            weight: 1,
            fillColor: '#0891b2',
            fillOpacity: 0.25
          }
        }).bindPopup(`<b>GEE Sentinel-1 SAR Water Inundation</b><br>Acquired: ${s1.acquisition_time}`).addTo(state.map);
      }
    } catch (e) {
      console.warn('Error rendering GEE layer', e);
    }
  }

  // 4. Plot Storm Surge Inundation Scenario
  if (state.layers.surge) {
    try {
      const surgeRes = await fetch(`/api/hazards/surge?scenario=${state.activeSurgeScenario}`);
      const surgeData = await surgeRes.json();
      if (surgeData.inundation_boundary_geojson) {
        state.mapLayers.surgeLayer = L.geoJSON(surgeData.inundation_boundary_geojson, {
          style: {
            color: '#f43f5e',
            weight: 1.5,
            fillColor: '#e11d48',
            fillOpacity: 0.3
          }
        }).bindPopup(`<b>Storm Surge Zone (${surgeData.surge_height_m}m)</b><br>Scenario: ${surgeData.scenario}`).addTo(state.map);
      }
    } catch (e) {
      console.warn('Error loading surge layer', e);
    }
  }

  // 5. Plot Scored Asset Pins
  plotAssetPins();
}

function clearMapLayers() {
  if (state.mapLayers.track) state.map.removeLayer(state.mapLayers.track);
  if (state.mapLayers.cone) state.map.removeLayer(state.mapLayers.cone);
  if (state.mapLayers.surgeLayer) state.map.removeLayer(state.mapLayers.surgeLayer);
  if (state.mapLayers.rainfallLayer) state.map.removeLayer(state.mapLayers.rainfallLayer);
  if (state.mapLayers.geeLayer) state.map.removeLayer(state.mapLayers.geeLayer);
  state.mapLayers.assetMarkers.forEach(m => state.map.removeLayer(m));
  state.mapLayers.assetMarkers = [];
}

function plotAssetPins() {
  const filtered = getFilteredAssets();

  filtered.forEach(asset => {
    const isCritical = asset.total_score >= 75;
    const color = getRiskColor(asset.risk_band);

    const iconHtml = `
      <div class="custom-pin ${isCritical ? 'pulse-immediate' : ''}" style="
        background: ${color};
        width: 24px;
        height: 24px;
        border-radius: 50%;
        display: flex;
        align-items: center;
        justify-content: center;
        border: 2px solid #fff;
        box-shadow: 0 0 10px ${color};
        font-size: 11px;
        color: #fff;
      ">
        ${getAssetTypeIcon(asset.type)}
      </div>
    `;

    const pinIcon = L.divIcon({
      html: iconHtml,
      className: '',
      iconSize: [24, 24],
      iconAnchor: [12, 12]
    });

    const marker = L.marker([asset.lat, asset.lon], { icon: pinIcon })
      .bindPopup(`
        <div style="min-width:180px;">
          <h4 style="margin:0 0 4px 0; color:#f8fafc;">${asset.name}</h4>
          <span class="score-badge ${asset.risk_band.toLowerCase().replace(' ', '-')}" style="display:inline-block;margin-bottom:6px;">
            Score: ${Math.round(asset.total_score)}/100 (${asset.risk_band})
          </span>
          <p style="font-size:0.75rem; color:#94a3b8; margin:0 0 6px 0;">District: ${asset.district.toUpperCase()}</p>
          <div style="font-size:0.75rem; color:#cbd5e1; background:#1e293b; padding:4px 6px; border-radius:4px; margin-bottom:6px;">
            <b>Action:</b> ${asset.recommended_action}
          </div>
          <button onclick="inspectAsset('${asset.id}')" style="
            background:#0284c7; color:#fff; border:none; padding:4px 8px; border-radius:4px; font-size:0.75rem; cursor:pointer; width:100%;
          ">Inspect Factor Breakdown</button>
        </div>
      `);

    marker.on('click', () => {
      highlightQueueItem(asset.id);
    });

    marker.addTo(state.map);
    state.mapLayers.assetMarkers.push(marker);
  });
}

// --- Asset Queue Rendering & Filtering ---
function getFilteredAssets() {
  return state.assetsData.filter(asset => {
    if (state.filters.district !== 'all' && asset.district.toLowerCase() !== state.filters.district.toLowerCase()) {
      return false;
    }
    if (state.filters.type !== 'all' && asset.type.toLowerCase() !== state.filters.type.toLowerCase()) {
      return false;
    }
    if (state.filters.riskBand !== 'all' && asset.risk_band.toLowerCase() !== state.filters.riskBand.toLowerCase()) {
      return false;
    }
    if (state.filters.search) {
      const q = state.filters.search.toLowerCase();
      return asset.name.toLowerCase().includes(q) || asset.district.toLowerCase().includes(q);
    }
    return true;
  });
}

function renderAssetQueue() {
  const container = document.getElementById('asset-cards-container');
  if (!container) return;

  const filtered = getFilteredAssets();
  document.getElementById('queue-count-badge').textContent = `${filtered.length} Assets`;

  if (filtered.length === 0) {
    container.innerHTML = '<div style="text-align:center; padding:2rem; color:#64748b;">No assets matching current filter criteria.</div>';
    return;
  }

  container.innerHTML = filtered.map((asset, index) => {
    const riskClass = asset.risk_band.toLowerCase().replace(' ', '-');
    const factors = asset.factor_breakdown || {};

    return `
      <div class="asset-card ${state.selectedAsset?.id === asset.id ? 'selected' : ''}" id="card-${asset.id}" onclick="inspectAsset('${asset.id}')">
        <div class="asset-card-top">
          <div class="asset-identity">
            <div class="asset-icon">${getAssetTypeIcon(asset.type)}</div>
            <div class="asset-name-block">
              <h4>${index + 1}. ${asset.name}</h4>
              <div class="asset-meta">
                <span>📍 ${asset.district.toUpperCase()}</span>
                <span>⚡ Power: ${asset.backup_power || 'None'}</span>
                <span>🏔️ ${asset.elevation_m}m DEM</span>
              </div>
            </div>
          </div>
          <div class="score-badge risk-${riskClass}">
            ${Math.round(asset.total_score)}
          </div>
        </div>

        <!-- Factor Contribution Breakdown Strip -->
        <div class="factor-bar-wrapper" title="Factor Breakdown: Hazard (${Math.round(factors.hazard_exposure || 0)}), Vuln (${Math.round(factors.vulnerability || 0)}), Conseq (${Math.round(factors.consequence || 0)}), Access (${Math.round(factors.access_criticality || 0)}), Conf (${Math.round(factors.data_confidence || 0)})">
          <div class="factor-segment seg-hazard" style="width: ${factors.hazard_exposure || 30}%;"></div>
          <div class="factor-segment seg-vuln" style="width: ${factors.vulnerability || 25}%;"></div>
          <div class="factor-segment seg-conseq" style="width: ${factors.consequence || 20}%;"></div>
          <div class="factor-segment seg-access" style="width: ${factors.access_criticality || 15}%;"></div>
          <div class="factor-segment seg-conf" style="width: ${factors.data_confidence || 10}%;"></div>
        </div>

        <!-- Action Box -->
        <div class="recommended-action-box">
          <span>🎯 ${asset.recommended_action}</span>
          <select class="status-select" onclick="event.stopPropagation()" onchange="updateActionStatus('${asset.id}', this.value)">
            <option value="Not Started" ${asset.action_status === 'Not Started' ? 'selected' : ''}>Not Started</option>
            <option value="In Progress" ${asset.action_status === 'In Progress' ? 'selected' : ''}>In Progress</option>
            <option value="Verified" ${asset.action_status === 'Verified' ? 'selected' : ''}>Verified</option>
            <option value="Closed" ${asset.action_status === 'Closed' ? 'selected' : ''}>Closed</option>
          </select>
        </div>
      </div>
    `;
  }).join('');
}

function highlightQueueItem(assetId) {
  document.querySelectorAll('.asset-card').forEach(c => c.classList.remove('selected'));
  const card = document.getElementById(`card-${assetId}`);
  if (card) {
    card.classList.add('selected');
    card.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
  }
}

// --- Asset Inspection Drawer ---
async function inspectAsset(assetId) {
  const asset = state.assetsData.find(a => a.id === assetId);
  if (!asset) return;

  state.selectedAsset = asset;
  highlightQueueItem(assetId);

  // Focus map on asset
  if (state.map) {
    state.map.flyTo([asset.lat, asset.lon], 11, { duration: 0.8 });
  }

  // Populate Drawer Fields
  document.getElementById('drawer-asset-name').textContent = asset.name;
  document.getElementById('drawer-asset-type').textContent = `${asset.type.toUpperCase()} • ${asset.district.toUpperCase()}`;
  document.getElementById('drawer-total-score').textContent = `${Math.round(asset.total_score)}/100`;
  
  const riskBadge = document.getElementById('drawer-risk-badge');
  riskBadge.textContent = asset.risk_band;
  riskBadge.className = `score-badge risk-${asset.risk_band.toLowerCase().replace(' ', '-')}`;

  document.getElementById('drawer-elevation').textContent = `${asset.elevation_m} m`;
  document.getElementById('drawer-pop-served').textContent = (asset.population_served || 0).toLocaleString();
  document.getElementById('drawer-power-status').textContent = asset.backup_power || 'None';
  document.getElementById('drawer-recommended-action').textContent = asset.recommended_action;

  // Factor Decompositions
  const factors = asset.factor_breakdown || {};
  renderFactorRow('hazard', 'Hazard Exposure (Distance, Wind, Surge)', factors.hazard_exposure || 0, 35);
  renderFactorRow('vuln', 'Vulnerability (DEM Elevation, Fragility)', factors.vulnerability || 0, 25);
  renderFactorRow('conseq', 'Consequence (Criticality & Population)', factors.consequence || 0, 20);
  renderFactorRow('access', 'Access Criticality (Road/Bridge Status)', factors.access_criticality || 0, 10);
  renderFactorRow('conf', 'Data Confidence & Verification', factors.data_confidence || 0, 10);

  // Scenario Sensitivity
  const sens = asset.scenario_sensitivity || { center: asset.total_score, left_shift: asset.total_score - 8, right_shift: asset.total_score + 12 };
  document.getElementById('sens-center').textContent = Math.round(sens.center || asset.total_score);
  document.getElementById('sens-left').textContent = Math.round(sens.left_shift || asset.total_score - 8);
  document.getElementById('sens-right').textContent = Math.round(sens.right_shift || asset.total_score + 12);

  // Open Drawer
  document.getElementById('inspection-drawer').classList.add('open');
}

function renderFactorRow(key, title, score, maxWeight) {
  const rowTitle = document.getElementById(`factor-title-${key}`);
  const rowScore = document.getElementById(`factor-score-${key}`);
  const rowFill = document.getElementById(`factor-fill-${key}`);

  if (rowTitle) rowTitle.textContent = title;
  if (rowScore) rowScore.textContent = `${Math.round(score)} / ${maxWeight} pts`;
  if (rowFill) {
    const pct = Math.min(100, Math.max(0, (score / maxWeight) * 100));
    rowFill.style.width = `${pct}%`;
  }
}

function closeDrawer() {
  document.getElementById('inspection-drawer').classList.remove('open');
}

// --- Action Status Updater ---
async function updateActionStatus(assetId, newStatus) {
  try {
    const res = await fetch(`/api/actions/${assetId}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ status: newStatus, notes: `Updated from operations dashboard` })
    });
    if (res.ok) {
      showToast(`Asset status updated to "${newStatus}"`);
    }
  } catch (e) {
    console.error('Failed to update action status', e);
  }
}

// --- "What Changed?" Diff Engine Modal ---
async function openDiffModal() {
  const modal = document.getElementById('diff-modal');
  modal.classList.add('active');

  try {
    const fromUpdate = 'update-01';
    const toUpdate = state.currentUpdate;

    const res = await fetch(`/api/compare?from_update=${fromUpdate}&to_update=${toUpdate}`);
    const data = await res.json();

    document.getElementById('diff-from-label').textContent = fromUpdate.toUpperCase();
    document.getElementById('diff-to-label').textContent = toUpdate.toUpperCase();
    document.getElementById('diff-narrative').textContent = data.narrative_summary || 'Track recurvature analysis complete.';

    const newHighRiskList = document.getElementById('diff-new-high-risk');
    newHighRiskList.innerHTML = (data.new_high_risk_assets || []).map(item => `
      <div class="diff-item">
        <div>
          <b>${item.name}</b> <span style="font-size:0.75rem; color:#94a3b8;">(${item.district.toUpperCase()})</span>
          <div style="font-size:0.75rem; color:#cbd5e1; margin-top:2px;">Reason: ${item.cause || 'Increased storm surge exposure'}</div>
        </div>
        <div style="color:#ef4444; font-weight:800; font-family:var(--font-mono); font-size:0.9rem;">
          +${Math.round(item.score_delta || 22)} pts
        </div>
      </div>
    `).join('') || '<div style="color:#94a3b8;">No new high-risk assets detected.</div>';

  } catch (err) {
    console.error('Failed to calculate forecast diff:', err);
  }
}

// --- Automated Advisory & Human-in-the-Loop Dispatch ---
let activeDraftId = null;

async function openAdvisoryModal() {
  document.getElementById('advisory-modal').classList.add('active');
  await draftAdvisory();
}

async function draftAdvisory() {
  const district = document.getElementById('advisory-district-select').value;
  const audience = document.getElementById('advisory-audience-select').value;
  const btn = document.getElementById('btn-draft-advisory');
  btn.textContent = '⏳ Generating with Gemini 3.7 Flash...';
  btn.disabled = true;

  try {
    const res = await fetch('/api/advisories/generate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ district_id: district, target_audience: audience, update_id: state.currentUpdate })
    });
    const data = await res.json();
    activeDraftId = data.advisory_id;

    document.getElementById('advisory-textarea').value = data.draft_text;
    document.getElementById('advisory-status-badge').textContent = data.status || 'Draft Ready';
    document.getElementById('advisory-grounding-summary').textContent = `Grounding: ${data.evidence_grounding ? data.evidence_grounding.join(' • ') : 'Official IMD track + GEE SAR flood inundation vectors'}`;

  } catch (e) {
    console.error('Failed to draft advisory:', e);
    showToast('⚠️ Error drafting advisory', 'error');
  } finally {
    btn.textContent = '🤖 Re-draft with Gemini';
    btn.disabled = false;
  }
}

async function approveAndDispatchAdvisory() {
  if (!activeDraftId) return;

  const approver = document.getElementById('advisory-approver-name').value || 'Authorized Incident Commander';
  const channel = document.getElementById('advisory-dispatch-channel').value;
  const editedText = document.getElementById('advisory-textarea').value;

  try {
    const res = await fetch('/api/advisories/approve', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        advisory_id: activeDraftId,
        approver_name: approver,
        approved: true,
        notes: editedText,
        dispatch_channel: channel
      })
    });
    const result = await res.json();

    showToast(`✅ Advisory DISPATCHED via ${channel}! Audit ID: ${result.dispatch_id || 'AP-DISP-9842'}`);
    closeModal('advisory-modal');
  } catch (e) {
    console.error('Failed to dispatch advisory:', e);
    showToast('⚠️ Failed to dispatch advisory', 'error');
  }
}

// ==========================================================================
// PARAMETRIC EVENT / POLICY MONITORING & REUSABLE POLICY ALERT CARD
// ==========================================================================

/**
 * Reusable Policy Alert Card Component
 * Strictly decouples and distinguishes:
 * 1. TRIGGERED (Breached threshold)
 * 2. VERIFIED (Telemetry confirmed by Doppler / SAR)
 * 3. PAYOUT READY (Multi-sig consensus reached)
 * 
 * Accurately falls back to "Pending verification" / "Not available" if backend
 * returns undefined, null, or empty for payout readiness - NEVER falsely showing READY.
 */
function renderPolicyAlertCard(policy) {
  if (!policy) return '';

  const pid = policy.policy_id || policy.id || 'pol-unknown';
  const name = policy.policy_name || policy.zone_name || policy.name || 'Parametric Policy Zone';
  const insured = policy.insured_entity || 'AP State Disaster Management Entity';
  const triggerCond = policy.trigger_conditions || policy.trigger_type || policy.trigger || 'Sustained metric breach';
  const thresholdVal = policy.threshold_values || policy.threshold_value || policy.threshold || 'N/A';
  const currentVal = policy.current_values || policy.current_value || policy.actual_sensor_reading || 'Awaiting live feed';

  // 1. Trigger Status: TRIGGERED vs MONITORING
  const isTriggered = Boolean(policy.is_triggered || policy.trigger_status === 'TRIGGERED');
  const triggerStatusBadge = isTriggered
    ? `<span class="status-pill status-pill-triggered">⚡ TRIGGERED</span>`
    : `<span class="status-pill status-pill-monitoring">🛡️ MONITORING</span>`;

  // 2. Verification / Data Status: VERIFIED vs PENDING VERIFICATION vs NOT AVAILABLE
  const verStatus = (policy.verification_status || 'PENDING VERIFICATION').toUpperCase();
  let verBadge = '';
  if (verStatus === 'VERIFIED') {
    verBadge = `<span class="status-pill status-pill-verified">✓ VERIFIED</span>`;
  } else if (verStatus.includes('PENDING')) {
    verBadge = `<span class="status-pill status-pill-pending">⏳ PENDING PASS</span>`;
  } else {
    verBadge = `<span class="status-pill status-pill-offline">⚠️ NOT AVAILABLE</span>`;
  }

  // 3. Payout Readiness Status: PAYOUT READY vs PENDING VERIFICATION vs NOT AVAILABLE (or null/undefined fallback)
  const rawPayout = policy.payout_readiness_status;
  let payoutBadge = '';
  const isPayoutReady = Boolean(rawPayout && typeof rawPayout === 'string' && (rawPayout.toUpperCase() === 'PAYOUT READY' || rawPayout.toUpperCase() === 'READY FOR SETTLEMENT'));

  if (rawPayout && typeof rawPayout === 'string') {
    const norm = rawPayout.trim().toUpperCase();
    if (isPayoutReady) {
      payoutBadge = `<span class="status-pill status-pill-ready">💰 PAYOUT READY</span>`;
    } else if (norm.includes('PENDING')) {
      payoutBadge = `<span class="status-pill status-pill-pending">⏳ PENDING VERIFICATION</span>`;
    } else if (norm.includes('NOT AVAILABLE') || norm.includes('BELOW TRIGGER')) {
      payoutBadge = `<span class="status-pill status-pill-na">⏸️ NOT AVAILABLE</span>`;
    } else {
      payoutBadge = `<span class="status-pill status-pill-na">⏸️ ${rawPayout}</span>`;
    }
  } else {
    // If undefined, null, or no value, display appropriate "Pending verification" state
    payoutBadge = `<span class="status-pill status-pill-na">⏸️ Pending verification</span>`;
  }

  // 4. Timestamp formatting
  let formattedTime = '2026-05-18 18:30:00 UTC';
  if (policy.timestamp) {
    try {
      const d = new Date(policy.timestamp);
      formattedTime = d.toISOString().replace('T', ' ').replace('.000Z', ' UTC').replace('Z', ' UTC');
    } catch(e) {
      formattedTime = String(policy.timestamp);
    }
  }

  return `
    <div class="policy-card ${isTriggered ? 'card-triggered' : ''}" data-policy-id="${pid}" data-triggered="${isTriggered}" data-ready="${isPayoutReady}">
      <div class="policy-card-header">
        <div>
          <span class="policy-id-tag">${pid}</span>
          <h4 class="policy-name-title">${name}</h4>
          <div class="policy-insured-entity">🏢 ${insured}</div>
        </div>
        <div>
          ${triggerStatusBadge}
        </div>
      </div>

      <!-- Trigger conditions & Threshold vs Current Values -->
      <div class="policy-metrics-box">
        <div class="metric-row">
          <span class="metric-label">Trigger Condition:</span>
          <span class="metric-val-contract">${triggerCond}</span>
        </div>
        <div class="metric-row">
          <span class="metric-label">Contract Threshold:</span>
          <span class="metric-val-contract">${thresholdVal}</span>
        </div>
        <div class="metric-row">
          <span class="metric-label">Current Live Reading:</span>
          <span class="metric-val-current ${isTriggered ? 'breached' : 'nominal'}">${currentVal}</span>
        </div>
      </div>

      <!-- 3 Distinct States: Triggered vs Verified vs Payout Ready -->
      <div class="policy-states-row">
        <div class="state-item">
          <span class="state-item-label">1. Trigger Status:</span>
          <div>${triggerStatusBadge}</div>
        </div>
        <div class="state-item">
          <span class="state-item-label">2. Verification / Data:</span>
          <div>${verBadge}</div>
        </div>
        <div class="state-item">
          <span class="state-item-label">3. Payout Readiness:</span>
          <div>${payoutBadge}</div>
        </div>
      </div>

      <!-- Card Footer with Timestamp, Sum Insured & View Details Action -->
      <div class="policy-card-footer">
        <div>
          <span>🕒 ${formattedTime}</span>
          <span style="margin-left:0.5rem; color:#cbd5e1; font-weight:600;">💰 ${policy.payout_amount_inr || ''}</span>
        </div>
        <button class="policy-btn-details" onclick="openPolicyDetailsModal('${pid}')">
          🔍 View Details
        </button>
      </div>
    </div>
  `;
}

/**
 * Background / Live Check for Active Triggers
 * Updates the Top Dashboard Alert Banner whenever an event trigger breaches threshold
 */
async function refreshPolicyMonitoring() {
  try {
    const res = await fetch(`/api/insurance/triggers?update_id=${state.currentUpdate}`);
    if (!res.ok) return;
    const triggers = await res.json();
    state.insuranceTriggers = triggers;

    // Check for active triggers
    const triggeredList = triggers.filter(t => t.is_triggered || t.trigger_status === 'TRIGGERED');
    const readyList = triggers.filter(t => t.payout_readiness_status === 'PAYOUT READY' || t.payout_readiness_status === 'READY FOR SETTLEMENT');
    
    // Update live counts in modal header if present
    const countAllEl = document.getElementById('count-all-policies');
    const countTrigEl = document.getElementById('count-triggered-policies');
    const countReadyEl = document.getElementById('count-ready-policies');
    if (countAllEl) countAllEl.textContent = triggers.length;
    if (countTrigEl) countTrigEl.textContent = triggeredList.length;
    if (countReadyEl) countReadyEl.textContent = readyList.length;

    // Prominent Alert Banner on Main UI
    const bannerEl = document.getElementById('policy-alert-banner');
    if (bannerEl) {
      if (triggeredList.length > 0) {
        bannerEl.style.display = 'block';
        const topTrig = triggeredList[0];
        const summaryText = `Policy ${topTrig.policy_id} (${topTrig.zone_name || topTrig.policy_name}) Breached Trigger — Reading: ${topTrig.current_values || topTrig.current_value} vs Threshold ${topTrig.threshold_values || topTrig.threshold_value} (${triggeredList.length} Active Breach${triggeredList.length > 1 ? 'es' : ''}, ${readyList.length} Payout Ready)`;
        const summaryEl = document.getElementById('banner-policy-summary');
        if (summaryEl) summaryEl.textContent = summaryText;
      } else {
        bannerEl.style.display = 'none';
      }
    }
  } catch (e) {
    console.error('Error refreshing policy monitoring', e);
  }
}

/**
 * Opens the Parametric Insurance & Policy Monitoring Modal
 */
async function openInsuranceModal() {
  const modal = document.getElementById('insurance-modal');
  modal.classList.add('active');

  try {
    const res = await fetch(`/api/insurance/triggers?update_id=${state.currentUpdate}`);
    const triggers = await res.json();
    state.insuranceTriggers = triggers;

    // Update Counts
    const triggeredList = triggers.filter(t => t.is_triggered || t.trigger_status === 'TRIGGERED');
    const readyList = triggers.filter(t => t.payout_readiness_status === 'PAYOUT READY' || t.payout_readiness_status === 'READY FOR SETTLEMENT');
    
    const countAllEl = document.getElementById('count-all-policies');
    const countTrigEl = document.getElementById('count-triggered-policies');
    const countReadyEl = document.getElementById('count-ready-policies');
    if (countAllEl) countAllEl.textContent = triggers.length;
    if (countTrigEl) countTrigEl.textContent = triggeredList.length;
    if (countReadyEl) countReadyEl.textContent = readyList.length;

    renderInsuranceGrid(state.policyFilter || 'all');
  } catch (e) {
    console.error('Failed to fetch insurance triggers', e);
  }
}

/**
 * Filter Policy Alert Cards in the Grid
 */
function filterPolicyCards(filterType, btnEl) {
  state.policyFilter = filterType;
  
  document.querySelectorAll('.policy-filter-tab').forEach(btn => {
    btn.classList.toggle('active', btn === btnEl);
  });

  renderInsuranceGrid(filterType);
}

/**
 * Renders the Grid of Reusable Policy Alert Cards
 */
function renderInsuranceGrid(filterType = 'all') {
  const grid = document.getElementById('insurance-grid');
  if (!grid) return;

  let list = state.insuranceTriggers || [];
  if (filterType === 'triggered') {
    list = list.filter(t => t.is_triggered || t.trigger_status === 'TRIGGERED');
  } else if (filterType === 'ready') {
    list = list.filter(t => t.payout_readiness_status === 'PAYOUT READY' || t.payout_readiness_status === 'READY FOR SETTLEMENT');
  }

  if (list.length === 0) {
    grid.innerHTML = `
      <div style="grid-column: 1 / -1; text-align: center; padding: 2rem; color: #94a3b8; background: #0f172a; border-radius: 6px; border: 1px dashed #334155;">
        🛡️ No policies match the selected filter "${filterType.toUpperCase()}".
      </div>
    `;
    return;
  }

  grid.innerHTML = list.map(policy => renderPolicyAlertCard(policy)).join('');
}

/**
 * "View Details" Modal Action
 * Displays full sensor forensics, comparison gauges, oracle signatures, and verification hash
 */
async function openPolicyDetailsModal(policyId) {
  let policy = (state.insuranceTriggers || []).find(p => (p.policy_id === policyId || p.id === policyId));
  
  if (!policy) {
    try {
      const res = await fetch(`/api/insurance/policies/${policyId}?update_id=${state.currentUpdate}`);
      policy = await res.json();
    } catch (e) {
      console.error('Failed to fetch policy details', e);
    }
  }

  if (!policy) {
    showToast('⚠️ Policy details unavailable', 'error');
    return;
  }

  const modal = document.getElementById('policy-details-modal');
  const isTriggered = Boolean(policy.is_triggered || policy.trigger_status === 'TRIGGERED');
  const isPayoutReady = Boolean(policy.payout_readiness_status === 'PAYOUT READY' || policy.payout_readiness_status === 'READY FOR SETTLEMENT');
  const details = policy.details || {};
  const telemetry = details.sensor_telemetry || {};
  const terms = details.contract_terms || {};

  document.getElementById('det-policy-title').textContent = `📋 Policy Telemetry & Forensics: ${policy.policy_id || policyId}`;
  document.getElementById('det-policy-subtitle').textContent = `${policy.policy_name || policy.zone_name} · ${policy.insured_entity}`;

  const bodyEl = document.getElementById('policy-details-body');
  bodyEl.innerHTML = `
    <!-- Top Summary Banner -->
    <div style="background:${isTriggered ? 'rgba(239,68,68,0.12)' : 'rgba(51,65,85,0.3)'}; border:1px solid ${isTriggered ? '#ef4444' : '#475569'}; border-radius:6px; padding:0.75rem; margin-bottom:1rem;">
      <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:0.5rem;">
        <div>
          <span style="font-weight:700; color:#f8fafc; font-size:0.92rem;">${policy.policy_name || policy.zone_name}</span>
          <div style="font-size:0.75rem; color:#94a3b8; margin-top:0.2rem;">
            District: <b>${(policy.district_id || 'AP-COAST').toUpperCase()}</b> · Insured Entity: <b>${policy.insured_entity}</b> · Sum: <b>${policy.payout_amount_inr}</b>
          </div>
        </div>
        <div>
          <span class="status-pill ${isTriggered ? 'status-pill-triggered' : 'status-pill-monitoring'}">
            ${isTriggered ? '⚡ TRIGGER BREACHED' : '🛡️ WITHIN LIMITS'}
          </span>
        </div>
      </div>
    </div>

    <!-- 3-Phase Decoupled State Machine Status -->
    <div class="detail-section-title">Decoupled State Machine Progression</div>
    <div style="display:grid; grid-template-columns:repeat(3, 1fr); gap:0.55rem; margin-bottom:1rem;">
      <div style="background:#0f172a; border:1px solid #334155; border-radius:6px; padding:0.65rem;">
        <div style="font-size:0.7rem; color:#94a3b8; font-weight:600;">1. PHYSICAL TRIGGER</div>
        <div style="margin-top:0.3rem;">
          ${isTriggered ? '<span class="status-pill status-pill-triggered">⚡ TRIGGERED</span>' : '<span class="status-pill status-pill-monitoring">🛡️ MONITORING</span>'}
        </div>
        <div style="font-size:0.7rem; color:#cbd5e1; margin-top:0.35rem; line-height:1.3;">
          Live reading (${policy.current_values || policy.current_value}) vs trigger condition (${policy.threshold_values || policy.threshold_value})
        </div>
      </div>
      <div style="background:#0f172a; border:1px solid #334155; border-radius:6px; padding:0.65rem;">
        <div style="font-size:0.7rem; color:#94a3b8; font-weight:600;">2. SENSOR VERIFICATION</div>
        <div style="margin-top:0.3rem;">
          ${policy.verification_status === 'VERIFIED' ? '<span class="status-pill status-pill-verified">✓ DATA VERIFIED</span>' : '<span class="status-pill status-pill-pending">⏳ PENDING PASS</span>'}
        </div>
        <div style="font-size:0.7rem; color:#cbd5e1; margin-top:0.35rem; line-height:1.3;">
          ${policy.verification_source || 'IMD Machilipatnam Doppler DWR-02 & INCOIS Tide Gauge'}
        </div>
      </div>
      <div style="background:#0f172a; border:1px solid #334155; border-radius:6px; padding:0.65rem;">
        <div style="font-size:0.7rem; color:#94a3b8; font-weight:600;">3. PAYOUT READINESS</div>
        <div style="margin-top:0.3rem;">
          ${isPayoutReady ? '<span class="status-pill status-pill-ready">💰 PAYOUT READY</span>' : '<span class="status-pill status-pill-na">⏸️ Pending verification</span>'}
        </div>
        <div style="font-size:0.7rem; color:#cbd5e1; margin-top:0.35rem; line-height:1.3;">
          ${isPayoutReady ? 'Liquidity unlocked for instant DBT dispatch' : 'Awaiting complete multi-sig oracle signatures'}
        </div>
      </div>
    </div>

    <!-- Live Telemetry Forensic Feeds -->
    <div class="detail-section-title">Physical Sensor Forensics & Telemetry Metrics</div>
    <div class="detail-telemetry-grid">
      <div class="detail-metric-card">
        <div style="font-size:0.72rem; color:#94a3b8;">Primary Sustained Wind</div>
        <div style="font-size:1.2rem; font-weight:700; color:${(telemetry.primary_wind_speed_kmh || 0) > 135 ? '#ef4444' : '#38bdf8'}; margin:0.2rem 0;">
          ${telemetry.primary_wind_speed_kmh || 0} km/h
        </div>
        <div style="font-size:0.7rem; color:#64748b;">Contract Trigger: &gt; 135 km/h Wind</div>
      </div>
      <div class="detail-metric-card">
        <div style="font-size:0.72rem; color:#94a3b8;">Peak Storm Surge Gauge</div>
        <div style="font-size:1.2rem; font-weight:700; color:${(telemetry.peak_surge_height_m || 0) > 2.5 ? '#ef4444' : '#38bdf8'}; margin:0.2rem 0;">
          ${telemetry.peak_surge_height_m || 0} m
        </div>
        <div style="font-size:0.7rem; color:#64748b;">Contract Trigger: &gt; 2.5m Surge</div>
      </div>
      <div class="detail-metric-card">
        <div style="font-size:0.72rem; color:#94a3b8;">Active Oracle Stations</div>
        <div style="font-size:1rem; font-weight:600; color:#f8fafc; margin:0.2rem 0;">
          ${telemetry.reporting_station_count || 2} Automated Weather Stations
        </div>
        <div style="font-size:0.7rem; color:#64748b;">Signal Latency: ${telemetry.signal_latency_sec || 4.2}s</div>
      </div>
      <div class="detail-metric-card">
        <div style="font-size:0.72rem; color:#94a3b8;">Emergency Liquidity Allocation</div>
        <div style="font-size:1.1rem; font-weight:700; color:#34d399; margin:0.2rem 0;">
          ${policy.payout_amount_inr}
        </div>
        <div style="font-size:0.7rem; color:#64748b;">Beneficiary: ${policy.insured_entity}</div>
      </div>
    </div>

    <!-- Cryptographic Hash & Multi-Sig Audit -->
    <div class="detail-section-title">Cryptographic Oracle Verification & Smart Contract Escrow</div>
    <div class="detail-crypto-box">
      <div><b>ORACLE VERIFICATION HASH:</b> ${policy.verification_hash || 'SHA256-PENDING-SATELLITE-CROSS-VALIDATION'}</div>
      <div style="margin-top:0.35rem; color:#94a3b8;"><b>ESCROW SMART CONTRACT:</b> ${terms.escrow_smart_contract || '0x71C8390A7...4A'} (AP Disaster Emergency Liquidity Pool)</div>
      <div style="margin-top:0.35rem; color:#38bdf8;"><b>SETTLEMENT CHANNEL:</b> ${details.settlement_channel || 'Direct Benefit Transfer Escrow'}</div>
      <div style="margin-top:0.35rem; color:#cbd5e1;"><b>ORACLE SIGNATURES:</b> ${terms.oracle_signatures && terms.oracle_signatures.length > 0 ? terms.oracle_signatures.map(s => `<code>${s}</code>`).join(' · ') : 'Awaiting 3rd consensus signature'}</div>
    </div>
  `;

  modal.classList.add('active');
}

// --- District Preparedness Executive Briefing ---
async function openBriefingModal() {
  document.getElementById('briefing-modal').classList.add('active');
  const district = state.filters.district === 'all' ? 'kakinada' : state.filters.district;
  
  try {
    const res = await fetch(`/api/briefing/${district}?update_id=${state.currentUpdate}`);
    const data = await res.json();
    document.getElementById('briefing-content').innerHTML = renderMarkdown(data.markdown_content || 'Briefing generated.');
  } catch (e) {
    console.error('Failed to load briefing', e);
  }
}

function copyBriefing() {
  const content = document.getElementById('briefing-content').innerText;
  navigator.clipboard.writeText(content);
  showToast('📋 Executive Briefing copied to clipboard!');
}

function printBriefing() {
  window.print();
}

// --- Citizen Safety Portal & Multilingual Voice Copilot ---
async function openCitizenModal() {
  document.getElementById('citizen-modal').classList.add('active');
  await loadCitizenData();
}

async function loadCitizenData() {
  const district = document.getElementById('citizen-district-select').value;
  const lang = document.getElementById('citizen-lang-select').value;

  try {
    // 1. Get Nearest Shelter
    const shelterRes = await fetch(`/api/shelters/nearest?lat=16.98&lon=82.24&district=${district}`);
    const shelters = await shelterRes.json();
    const topShelter = shelters[0] || { name: 'District MPCS Centre', distance_km: 1.2, elevation_m: 8.5 };

    document.getElementById('shelter-name').textContent = topShelter.name;
    document.getElementById('shelter-distance').textContent = `${topShelter.distance_km} km away`;
    document.getElementById('shelter-elevation').textContent = `Elevation: ${topShelter.elevation_m}m (Safe above 4.2m surge)`;

    // 2. Multilingual Copilot Guidance
    const copilotRes = await fetch('/api/citizen/copilot', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        query: 'What should our family do right now to prepare?',
        district: district,
        language: lang
      })
    });
    const copilotData = await copilotRes.json();
    document.getElementById('citizen-guidance-text').textContent = copilotData.response;

  } catch (e) {
    console.error('Failed to load citizen portal', e);
  }
}

// Web Speech API Text-to-Speech
function playVoiceWarning() {
  const text = document.getElementById('citizen-guidance-text').textContent;
  const lang = document.getElementById('citizen-lang-select').value;

  if (!('speechSynthesis' in window)) {
    showToast('⚠️ Speech synthesis not supported in this browser', 'error');
    return;
  }

  window.speechSynthesis.cancel();
  const utterance = new SpeechSynthesisUtterance(text);
  
  // Set language voice code
  if (lang === 'te') utterance.lang = 'te-IN';
  else if (lang === 'hi') utterance.lang = 'hi-IN';
  else if (lang === 'or') utterance.lang = 'or-IN';
  else utterance.lang = 'en-IN';

  utterance.rate = 0.95;
  utterance.pitch = 1.0;

  utterance.onstart = () => showToast('🔊 Playing spoken safety guidance...');
  window.speechSynthesis.speak(utterance);
}

// --- Event Listeners Setup ---
function setupEventListeners() {
  // Update Buttons
  document.querySelectorAll('.update-btn').forEach(btn => {
    btn.addEventListener('click', () => switchUpdate(btn.dataset.update));
  });

  // Filters
  document.getElementById('district-filter')?.addEventListener('change', e => {
    state.filters.district = e.target.value;
    renderAssetQueue();
    plotAssetPins();
  });

  document.getElementById('type-filter')?.addEventListener('change', e => {
    state.filters.type = e.target.value;
    renderAssetQueue();
    plotAssetPins();
  });

  document.getElementById('risk-filter')?.addEventListener('change', e => {
    state.filters.riskBand = e.target.value;
    renderAssetQueue();
    plotAssetPins();
  });

  document.getElementById('search-input')?.addEventListener('input', e => {
    state.filters.search = e.target.value;
    renderAssetQueue();
  });

  // Layer Toggles
  document.getElementById('layer-gee-sar')?.addEventListener('change', e => {
    state.layers.geeSar = e.target.checked;
    updateMapLayers();
  });

  document.getElementById('layer-surge')?.addEventListener('change', e => {
    state.layers.surge = e.target.checked;
    updateMapLayers();
  });

  // Scenario Pills (Surge)
  document.querySelectorAll('.scenario-pill').forEach(pill => {
    pill.addEventListener('click', () => {
      document.querySelectorAll('.scenario-pill').forEach(p => p.classList.remove('active'));
      pill.classList.add('active');
      state.activeSurgeScenario = pill.dataset.scenario;
      updateMapLayers();
      updateMetricStrip();
    });
  });

  // Citizen selectors
  document.getElementById('citizen-district-select')?.addEventListener('change', loadCitizenData);
  document.getElementById('citizen-lang-select')?.addEventListener('change', loadCitizenData);
}

// --- Utilities ---
function closeModal(id) {
  document.getElementById(id)?.classList.remove('active');
}

function getAssetTypeIcon(type) {
  const map = {
    'Hospital': '🏥',
    'Substation': '⚡',
    'Bridge': '🌉',
    'Cyclone Shelter': '🛡️',
    'Water Treatment': '💧',
    'School': '🏫'
  };
  return map[type] || '📍';
}

function getRiskColor(band) {
  if (band === 'Immediate Attention') return '#ef4444';
  if (band === 'Prioritize') return '#f59e0b';
  if (band === 'Prepare') return '#06b6d4';
  return '#10b981';
}

function showToast(msg, type = 'info') {
  const container = document.getElementById('toast-container');
  if (!container) return;

  const toast = document.createElement('div');
  toast.className = 'toast';
  toast.innerHTML = `<span>${msg}</span>`;
  container.appendChild(toast);

  setTimeout(() => {
    toast.style.opacity = '0';
    setTimeout(() => toast.remove(), 300);
  }, 3500);
}

// Simple Markdown parser for briefing modal
function renderMarkdown(md) {
  if (!md) return '';
  return md
    .replace(/^### (.*$)/gim, '<h4 style="color:#38bdf8; margin:1rem 0 0.4rem 0;">$1</h4>')
    .replace(/^## (.*$)/gim, '<h3 style="color:#f8fafc; margin:1.2rem 0 0.5rem 0; border-bottom:1px solid #334155; padding-bottom:4px;">$1</h3>')
    .replace(/^# (.*$)/gim, '<h2 style="color:#fff; margin:1.4rem 0 0.6rem 0;">$1</h2>')
    .replace(/\*\*(.*)\*\*/gim, '<b>$1</b>')
    .replace(/\*(.*)\*/gim, '<i>$1</i>')
    .replace(/^- (.*$)/gim, '<li style="margin-left:1.2rem; color:#cbd5e1;">$1</li>')
    .replace(/\n\n/gim, '<br><br>');
}
