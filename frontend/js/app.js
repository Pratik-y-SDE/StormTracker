/**
 * ZATICS v3.0 — CYCLONE IMPACT FORECASTER
 * Frontend Controller & Geospatial Intelligence Dashboard (Light Command-Centre Theme)
 */

// The browser only talks to the same origin. Do not accept a URL from a query
// parameter or local storage: that lets phishing links redirect the dashboard
// to an attacker-controlled API.
function getApiBase() {
  return '';
}

const API_BASE = getApiBase();

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

// --- Map Setup (Clean Voyager / Light Theme) ---
function initMap() {
  state.map = L.map('map', {
    center: [16.8, 82.8],
    zoom: 7,
    zoomControl: false
  });

  L.control.zoom({ position: 'bottomright' }).addTo(state.map);

  // CartoDB Voyager Light Basemap
  L.tileLayer('https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png', {
    attribution: '&copy; <a href="https://carto.com/">CARTO</a> &copy; OpenStreetMap',
    subdomains: 'abcd',
    maxZoom: 19
  }).addTo(state.map);
}

// --- Navigation Helpers ---
function switchNavTab(targetId, btnEl) {
  document.querySelectorAll('.nav-pill').forEach(pill => pill.classList.remove('active'));
  if (btnEl) btnEl.classList.add('active');

  const el = document.getElementById(targetId);
  if (el) {
    el.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }
}

function scrollToSection(secId) {
  const el = document.getElementById(secId);
  if (el) {
    el.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }
}

// --- API Data Fetchers ---
async function loadInitialData() {
  try {
    // 1. Fetch Latest Event & Updates
    const eventRes = await fetch(`${API_BASE}/api/events/latest`);
    const eventData = await eventRes.json();
    state.currentEvent = eventData;
    state.updatesList = eventData.updates || [];

    // 2. Fetch Districts
    const distRes = await fetch(`${API_BASE}/api/districts`);
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
  select.innerHTML = '<option value="all">All Districts (5)</option>';
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
  document.querySelectorAll('.forecast-pill').forEach(btn => {
    btn.classList.toggle('active', btn.dataset.update === updateId);
  });

  try {
    // Fetch Scored Assets for this update
    const res = await fetch(`${API_BASE}/api/impact?update_id=${updateId}`);
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
  const countEl = document.getElementById('kpi-critical-count');
  if (countEl) countEl.textContent = summary.critical_assets_count || 12;

  const popServed = (summary.exposed_population || 1420000).toLocaleString();
  const popEl = document.getElementById('kpi-exposed-pop');
  if (popEl) popEl.textContent = popServed;

  const surgeEl = document.getElementById('kpi-surge-info');
  if (surgeEl) {
    surgeEl.textContent = `${summary.surge_height_m || 2.8}m (${state.activeSurgeScenario.toUpperCase()})`;
  }

  const actionEl = document.getElementById('kpi-top-action');
  if (actionEl && state.assetsData.length > 0) {
    actionEl.textContent = state.assetsData[0].recommended_action;
  }
}

// --- Event Listeners Setup ---
function setupEventListeners() {
  // Forecast Update selector
  document.querySelectorAll('.forecast-pill').forEach(btn => {
    btn.addEventListener('click', () => switchUpdate(btn.dataset.update));
  });

  // Layer Toggles
  document.getElementById('layer-gee-sar')?.addEventListener('change', e => {
    state.layers.geeSar = e.target.checked;
    toggleLayerVisibility('geeLayer', e.target.checked);
  });

  document.getElementById('layer-surge')?.addEventListener('change', e => {
    state.layers.surge = e.target.checked;
    toggleLayerVisibility('surgeLayer', e.target.checked);
  });

  document.getElementById('layer-corridor')?.addEventListener('change', e => {
    state.layers.uncertaintyCone = e.target.checked;
    toggleLayerVisibility('cone', e.target.checked);
  });

  document.getElementById('layer-rainfall')?.addEventListener('change', e => {
    state.layers.rainfall = e.target.checked;
    toggleLayerVisibility('rainfallLayer', e.target.checked);
  });

  // Surge Scenario selector pills
  document.querySelectorAll('.scenario-pill').forEach(btn => {
    btn.addEventListener('click', async () => {
      document.querySelectorAll('.scenario-pill').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      state.activeSurgeScenario = btn.dataset.scenario;
      await updateSurgeLayer();
      updateMetricStrip();
    });
  });

  // Filters
  document.getElementById('district-filter')?.addEventListener('change', e => {
    state.filters.district = e.target.value;
    renderAssetQueue();
  });

  document.getElementById('type-filter')?.addEventListener('change', e => {
    state.filters.type = e.target.value;
    renderAssetQueue();
  });

  document.getElementById('risk-filter')?.addEventListener('change', e => {
    state.filters.riskBand = e.target.value;
    renderAssetQueue();
  });

  document.getElementById('search-input')?.addEventListener('input', e => {
    state.filters.search = e.target.value.toLowerCase();
    renderAssetQueue();
  });
}

// --- Map Layer Renderers ---
async function updateMapLayers() {
  clearMapLayers();

  const currentUpdateObj = state.updatesList.find(u => u.id === state.currentUpdate);
  if (!currentUpdateObj) return;

  const trackPoints = currentUpdateObj.track_points || [];

  // 1. Draw Cyclone Track Polyline & Forecast Points
  if (trackPoints.length > 0) {
    const latlngs = trackPoints.map(p => [p.lat, p.lon]);

    state.mapLayers.track = L.polyline(latlngs, {
      color: '#dc2626',
      weight: 3.5,
      opacity: 0.9,
      dashArray: '6, 6'
    }).addTo(state.map);

    // Add Cyclone Markers
    trackPoints.forEach((p, idx) => {
      const isLandfall = p.forecast_time.toLowerCase().includes('landfall');
      const isCurrent = idx === 0;

      const marker = L.circleMarker([p.lat, p.lon], {
        radius: isCurrent ? 9 : (isLandfall ? 8 : 5),
        fillColor: isCurrent ? '#ef4444' : '#f97316',
        color: '#ffffff',
        weight: 2,
        opacity: 1,
        fillOpacity: 0.9
      }).addTo(state.map);

      marker.bindPopup(`
        <div style="font-family:var(--font-sans); font-size:12px; line-height:1.4;">
          <b style="color:#ef4444;">${p.forecast_time}</b><br>
          <b>Wind Speed:</b> ${p.wind_kmh} km/h (${p.category})<br>
          <b>Pressure:</b> ${p.pressure_hpa} hPa<br>
          <b>Uncertainty Radius:</b> ±${p.uncertainty_radius_km} km
        </div>
      `);
    });

    // 2. Fetch and Render Uncertainty Corridor
    try {
      const coneRes = await fetch(`${API_BASE}/api/hazards/corridor?update_id=${state.currentUpdate}`);
      const coneData = await coneRes.json();
      state.mapLayers.cone = L.geoJSON(coneData, {
        style: {
          color: '#f59e0b',
          weight: 1.5,
          fillColor: '#f59e0b',
          fillOpacity: 0.12,
          dashArray: '4, 4'
        }
      }).addTo(state.map);
    } catch (e) {
      console.error('Error loading corridor cone:', e);
    }
  }

  // 3. Render Satellite GEE Layers
  await updateGeeLayers();

  // 4. Render Storm Surge Layer
  await updateSurgeLayer();

  // 5. Render Asset Markers
  renderAssetMarkers();
}

async function updateGeeLayers() {
  try {
    const res = await fetch(`${API_BASE}/api/satellite/layers`);
    const layers = await res.json();
    const sarLayer = layers.find(l => l.layer_id === 'gee-sentinel1-sar');

    if (sarLayer && sarLayer.tile_url) {
      if (state.mapLayers.geeLayer) state.map.removeLayer(state.mapLayers.geeLayer);
      state.mapLayers.geeLayer = L.tileLayer(sarLayer.tile_url, {
        opacity: 0.45,
        maxZoom: 19
      });
      if (state.layers.geeSar) state.mapLayers.geeLayer.addTo(state.map);
    }
  } catch (e) {
    console.error('Error loading GEE layer:', e);
  }
}

async function updateSurgeLayer() {
  if (state.mapLayers.surgeLayer) {
    state.map.removeLayer(state.mapLayers.surgeLayer);
  }

  try {
    const res = await fetch(`${API_BASE}/api/hazards/surge?scenario=${state.activeSurgeScenario}`);
    const surgeGeoJson = await res.json();

    state.mapLayers.surgeLayer = L.geoJSON(surgeGeoJson, {
      style: feature => {
        const depth = feature.properties.surge_depth_m || 2.5;
        const color = depth > 3.0 ? '#0284c7' : (depth > 2.0 ? '#38bdf8' : '#7dd3fc');
        return {
          color: color,
          weight: 1,
          fillColor: color,
          fillOpacity: 0.35
        };
      }
    });

    if (state.layers.surge) {
      state.mapLayers.surgeLayer.addTo(state.map);
    }
  } catch (e) {
    console.error('Error loading surge layer:', e);
  }
}

function renderAssetMarkers() {
  state.mapLayers.assetMarkers.forEach(m => state.map.removeLayer(m));
  state.mapLayers.assetMarkers = [];

  state.assetsData.forEach(asset => {
    const color = getRiskColor(asset.risk_band);
    const iconChar = getAssetTypeIcon(asset.type);

    const customIcon = L.divIcon({
      className: 'custom-asset-marker',
      html: `
        <div style="
          background: #ffffff;
          border: 2px solid ${color};
          color: ${color};
          width: 28px;
          height: 28px;
          border-radius: 50%;
          display: flex;
          align-items: center;
          justify-content: center;
          font-size: 13px;
          box-shadow: 0 2px 8px rgba(15,23,42,0.15);
          cursor: pointer;
        ">${iconChar}</div>
      `,
      iconSize: [28, 28],
      iconAnchor: [14, 14]
    });

    const marker = L.marker([asset.lat, asset.lon], { icon: customIcon }).addTo(state.map);

    marker.bindPopup(`
      <div style="font-family:var(--font-sans); font-size:12px; width:220px;">
        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:4px;">
          <b style="color:#0f172a; font-size:13px;">${asset.name}</b>
          <span style="background:${color}15; color:${color}; font-weight:800; padding:2px 6px; border-radius:12px; font-size:10px;">${asset.total_score}</span>
        </div>
        <div style="color:#64748b; font-size:11px; margin-bottom:6px;">${asset.type} · ${asset.district.toUpperCase()}</div>
        <div style="background:#f8fafc; border:1px solid #e2e8f0; border-radius:4px; padding:6px; font-size:11px; margin-bottom:6px;">
          <div><b>Exposure:</b> ${asset.hazard_exposure.toFixed(1)}/35</div>
          <div><b>Vulnerability:</b> ${asset.vulnerability.toFixed(1)}/25</div>
          <div><b>Backup Power:</b> ${asset.backup_power}</div>
        </div>
        <div style="color:#1e40af; font-weight:600; font-size:11px;">🎯 ${asset.recommended_action}</div>
      </div>
    `);

    marker.on('click', () => {
      focusAssetInQueue(asset.id);
    });

    state.mapLayers.assetMarkers.push(marker);
  });
}

function clearMapLayers() {
  if (state.mapLayers.track) state.map.removeLayer(state.mapLayers.track);
  if (state.mapLayers.cone) state.map.removeLayer(state.mapLayers.cone);
  if (state.mapLayers.surgeLayer) state.map.removeLayer(state.mapLayers.surgeLayer);
  if (state.mapLayers.geeLayer) state.map.removeLayer(state.mapLayers.geeLayer);
  state.mapLayers.assetMarkers.forEach(m => state.map.removeLayer(m));
  state.mapLayers.assetMarkers = [];
}

function toggleLayerVisibility(layerKey, visible) {
  const layer = state.mapLayers[layerKey];
  if (!layer) return;
  if (visible) {
    layer.addTo(state.map);
  } else {
    state.map.removeLayer(layer);
  }
}

// --- Ranked Infrastructure Queue Renderer ---
function renderAssetQueue() {
  const container = document.getElementById('asset-queue-list');
  if (!container) return;

  // Filter Assets
  let filtered = state.assetsData.filter(asset => {
    if (state.filters.district !== 'all' && asset.district.toLowerCase() !== state.filters.district.toLowerCase()) return false;
    if (state.filters.type !== 'all' && asset.type !== state.filters.type) return false;
    if (state.filters.riskBand !== 'all' && asset.risk_band !== state.filters.riskBand) return false;
    if (state.filters.search && !asset.name.toLowerCase().includes(state.filters.search) && !asset.district.toLowerCase().includes(state.filters.search)) return false;
    return true;
  });

  if (filtered.length === 0) {
    container.innerHTML = `
      <div style="text-align:center; padding:3rem; color:var(--text-muted); font-size:0.9rem;">
        🔍 No infrastructure assets match the active filter criteria.
      </div>
    `;
    return;
  }

  container.innerHTML = filtered.map(asset => {
    const riskClass = asset.risk_band === 'Immediate Attention' ? 'risk-crit' : (asset.risk_band === 'Prioritize' ? 'risk-prio' : 'risk-prep');
    const scoreClass = asset.risk_band === 'Immediate Attention' ? 'crit' : (asset.risk_band === 'Prioritize' ? 'prio' : 'prep');

    // 5 factor percentages for progress bars
    const hPct = (asset.hazard_exposure / 35.0) * 100;
    const vPct = (asset.vulnerability / 25.0) * 100;
    const cPct = (asset.consequence / 20.0) * 100;
    const aPct = (asset.access_criticality / 10.0) * 100;
    const dPct = (asset.data_confidence / 10.0) * 100;

    return `
      <div class="asset-item-card ${riskClass}" id="queue-item-${asset.id}">
        <div class="asset-main-info">
          <div class="asset-title-row">
            <span class="asset-name">${asset.name}</span>
            <span class="asset-type-badge">${getAssetTypeIcon(asset.type)} ${asset.type}</span>
            <span class="status-pill ${asset.backup_power === 'Verified' ? 'status-pill-ready' : 'status-pill-triggered'}">
              ⚡ Power: ${asset.backup_power}
            </span>
          </div>
          <div class="asset-district">
            📍 District: <b>${asset.district.toUpperCase()}</b> · Elevation: <b>${asset.elevation_m}m</b> · Population Served: <b>${asset.population_served.toLocaleString()}</b>
          </div>

          <!-- 5-Factor Score Decomposition -->
          <div class="factor-bars-container">
            <div class="factor-col">
              <div class="factor-label-row"><span>Hazard (35%)</span><b>${asset.hazard_exposure.toFixed(1)}</b></div>
              <div class="factor-bar-bg"><div class="factor-bar-fill" style="width:${hPct}%; background:#ef4444;"></div></div>
            </div>
            <div class="factor-col">
              <div class="factor-label-row"><span>Vuln (25%)</span><b>${asset.vulnerability.toFixed(1)}</b></div>
              <div class="factor-bar-bg"><div class="factor-bar-fill" style="width:${vPct}%; background:#f59e0b;"></div></div>
            </div>
            <div class="factor-col">
              <div class="factor-label-row"><span>Conseq (20%)</span><b>${asset.consequence.toFixed(1)}</b></div>
              <div class="factor-bar-bg"><div class="factor-bar-fill" style="width:${cPct}%; background:#3b82f6;"></div></div>
            </div>
            <div class="factor-col">
              <div class="factor-label-row"><span>Access (10%)</span><b>${asset.access_criticality.toFixed(1)}</b></div>
              <div class="factor-bar-bg"><div class="factor-bar-fill" style="width:${aPct}%; background:#8b5cf6;"></div></div>
            </div>
            <div class="factor-col">
              <div class="factor-label-row"><span>Conf (10%)</span><b>${asset.data_confidence.toFixed(1)}</b></div>
              <div class="factor-bar-bg"><div class="factor-bar-fill" style="width:${dPct}%; background:#10b981;"></div></div>
            </div>
          </div>

          <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:0.5rem;">
            <div class="action-recommendation">🎯 Action: ${asset.recommended_action}</div>
            <button class="btn-pill btn-pill-outline" style="font-size:0.7rem; padding:0.25rem 0.65rem;" onclick="focusAssetOnMap(${asset.lat}, ${asset.lon})">
              🗺️ Locate on Map
            </button>
          </div>
        </div>

        <div class="asset-score-block">
          <div class="score-pill-large ${scoreClass}">
            <span>${asset.total_score.toFixed(0)}</span>
          </div>
          <span class="score-band-tag ${scoreClass}">${asset.risk_band}</span>
        </div>
      </div>
    `;
  }).join('');
}

function focusAssetOnMap(lat, lon) {
  state.map.setView([lat, lon], 12, { animate: true });
  scrollToSection('sec-map');
}

function focusAssetInQueue(assetId) {
  const el = document.getElementById(`queue-item-${assetId}`);
  if (el) {
    el.scrollIntoView({ behavior: 'smooth', block: 'center' });
    el.style.transform = 'scale(1.02)';
    setTimeout(() => { el.style.transform = ''; }, 1200);
  }
}

// --- "What Changed?" Diff Modal ---
async function openDiffModal() {
  const modal = document.getElementById('diff-modal');
  modal.classList.add('active');

  const content = document.getElementById('diff-content');
  content.innerHTML = '<div style="text-align:center; padding:2rem; color:var(--text-muted);">Calculating vector diff from Update 01 to Update 03...</div>';

  try {
    const res = await fetch(`${API_BASE}/api/compare?from_update=update-01&to_update=update-03`);
    const data = await res.json();

    content.innerHTML = `
      <div style="background:var(--bg-card-subtle); border:1px solid var(--border-card); border-radius:12px; padding:1.2rem; margin-bottom:1rem;">
        <h4 style="color:var(--text-primary); font-size:1.05rem; font-weight:800; margin-bottom:0.4rem;">
          Track Shift Analysis: ${data.from_update_id.toUpperCase()} ➔ ${data.to_update_id.toUpperCase()}
        </h4>
        <p style="color:var(--text-secondary); font-size:0.85rem; line-height:1.6;">
          ${data.narrative_summary || 'Track recurved 38km NE towards Kakinada/Visakhapatnam coast, escalating northern assets while lowering threat to southern delta.'}
        </p>
      </div>

      <div style="display:grid; grid-template-columns:repeat(3, 1fr); gap:0.75rem; margin-bottom:1rem;">
        <div style="background:#fef2f2; border:1px solid #fecaca; border-radius:8px; padding:0.85rem; text-align:center;">
          <div style="font-size:1.5rem; font-weight:900; color:#ef4444;">+${data.newly_critical_count || 7}</div>
          <div style="font-size:0.75rem; font-weight:700; color:#b91c1c;">Newly Escalated Assets</div>
        </div>
        <div style="background:#ecfdf5; border:1px solid #a7f3d0; border-radius:8px; padding:0.85rem; text-align:center;">
          <div style="font-size:1.5rem; font-weight:900; color:#059669;">${data.downgraded_count || 4}</div>
          <div style="font-size:0.75rem; font-weight:700; color:#047857;">Downgraded Assets</div>
        </div>
        <div style="background:#eff6ff; border:1px solid #bfdbfe; border-radius:8px; padding:0.85rem; text-align:center;">
          <div style="font-size:1.5rem; font-weight:900; color:#2563eb;">+${((data.net_exposed_population_delta || 480000) / 1000).toFixed(0)}k</div>
          <div style="font-size:0.75rem; font-weight:700; color:#1d4ed8;">Net Population Delta</div>
        </div>
      </div>

      <div style="font-size:0.85rem; font-weight:800; color:var(--text-primary); margin-bottom:0.65rem;">Top Escalated Infrastructure Assets:</div>
      <div style="display:flex; flex-direction:column; gap:0.5rem;">
        ${(data.top_escalations || []).slice(0, 4).map(e => `
          <div style="background:#ffffff; border:1px solid var(--border-card); border-left:4px solid #ef4444; border-radius:6px; padding:0.75rem 1rem; display:flex; justify-content:space-between; align-items:center;">
            <div>
              <div style="font-weight:800; color:var(--text-primary); font-size:0.88rem;">${e.name}</div>
              <div style="font-size:0.72rem; color:var(--text-muted);">${e.district.toUpperCase()} · ${e.type}</div>
            </div>
            <div style="text-align:right;">
              <span style="background:#fef2f2; color:#ef4444; font-weight:800; padding:0.2rem 0.6rem; border-radius:12px; font-size:0.75rem;">+${e.delta_score.toFixed(0)} pts</span>
              <div style="font-size:0.7rem; color:var(--text-muted); margin-top:2px;">Score: ${e.from_score} ➔ ${e.to_score}</div>
            </div>
          </div>
        `).join('')}
      </div>
    `;
  } catch (e) {
    console.error('Error fetching compare diff:', e);
    content.innerHTML = '<div style="color:var(--risk-crit); padding:2rem;">Failed to fetch forecast comparison diff.</div>';
  }
}

// --- AI Advisory Workflow (Human-in-the-Loop) ---
function openAdvisoryModal() {
  document.getElementById('advisory-modal').classList.add('active');
}

async function generateAdvisory() {
  const district = document.getElementById('adv-district-select').value;
  const audience = document.getElementById('adv-audience-select').value;
  const btn = document.getElementById('btn-generate-advisory');
  btn.disabled = true;
  btn.innerHTML = '<span>⏳ Synthesizing Grounded Draft...</span>';

  try {
    const res = await fetch(`${API_BASE}/api/advisories/generate`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ district_id: district, target_audience: audience, update_id: state.currentUpdate })
    });
    const data = await res.json();

    document.getElementById('adv-draft-text').value = data.draft_text;
    document.getElementById('adv-evidence-preview').textContent = data.evidence_summary;
    document.getElementById('adv-status-badge').textContent = '📝 DRAFT READY FOR SIGN-OFF';
    document.getElementById('adv-status-badge').className = 'status-pill status-pill-pending';

    showToast('✨ AI Advisory Draft generated with Gemini AI');
  } catch (e) {
    console.error('Failed to generate advisory:', e);
    showToast('⚠️ Error generating advisory draft', 'error');
  } finally {
    btn.disabled = false;
    btn.innerHTML = '<span>✨ Generate Grounded Draft</span>';
  }
}

async function approveAndDispatchAdvisory() {
  const text = document.getElementById('adv-draft-text').value;
  const approver = document.getElementById('adv-approver-name').value;
  const channel = document.getElementById('adv-channel-select').value;

  if (!text.trim()) {
    showToast('⚠️ Please generate a draft before approving', 'error');
    return;
  }

  try {
    const res = await fetch(`${API_BASE}/api/advisories/approve`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        advisory_id: `adv-${Date.now()}`,
        approver_name: approver,
        dispatch_channel: channel,
        approved_text: text
      })
    });
    const result = await res.json();

    document.getElementById('adv-status-badge').textContent = '✅ DISPATCHED & AUDITED';
    document.getElementById('adv-status-badge').className = 'status-pill status-pill-ready';
    showToast(`✅ Advisory approved by ${approver} & dispatched via ${channel}!`);
    setTimeout(() => closeModal('advisory-modal'), 1800);
  } catch (e) {
    console.error('Failed to dispatch advisory:', e);
    showToast('⚠️ Failed to dispatch advisory', 'error');
  }
}

// ==============================================================================
// PARAMETRIC EVENT / POLICY MONITORING & REUSABLE POLICY ALERT CARD
// ==============================================================================
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
    verBadge = `<span class="status-pill status-pill-verified">✓ DATA VERIFIED</span>`;
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
    payoutBadge = `<span class="status-pill status-pill-na">⏸️ Payout readiness unavailable</span>`;
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
    <div class="policy-card ${isTriggered ? 'card-triggered' : ''}" data-policy-id="${pid}">
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
          <span style="margin-left:0.5rem; color:var(--text-secondary); font-weight:700;">💰 ${policy.payout_amount_inr || ''}</span>
        </div>
        <button class="policy-btn-details" onclick="openPolicyDetailsModal('${pid}')">
          🔍 View Details
        </button>
      </div>
    </div>
  `;
}

async function refreshPolicyMonitoring() {
  try {
    const res = await fetch(`${API_BASE}/api/insurance/triggers?update_id=${state.currentUpdate}`);
    if (!res.ok) return;
    const triggers = await res.json();
    state.insuranceTriggers = triggers;

    const triggeredList = triggers.filter(t => t.is_triggered || t.trigger_status === 'TRIGGERED');
    const readyList = triggers.filter(t => t.payout_readiness_status === 'PAYOUT READY' || t.payout_readiness_status === 'READY FOR SETTLEMENT');

    const countAllEl = document.getElementById('count-all-policies');
    const countTrigEl = document.getElementById('count-triggered-policies');
    const countReadyEl = document.getElementById('count-ready-policies');
    if (countAllEl) countAllEl.textContent = triggers.length;
    if (countTrigEl) countTrigEl.textContent = triggeredList.length;
    if (countReadyEl) countReadyEl.textContent = readyList.length;

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

async function openInsuranceModal() {
  const modal = document.getElementById('insurance-modal');
  modal.classList.add('active');

  try {
    const res = await fetch(`${API_BASE}/api/insurance/triggers?update_id=${state.currentUpdate}`);
    const triggers = await res.json();
    state.insuranceTriggers = triggers;

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

function filterPolicyCards(filterType, btnEl) {
  state.policyFilter = filterType;
  document.querySelectorAll('.policy-filter-tab').forEach(btn => btn.classList.remove('active'));
  if (btnEl) btnEl.classList.add('active');
  renderInsuranceGrid(filterType);
}

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
      <div style="grid-column: 1 / -1; text-align: center; padding: 2rem; color: var(--text-muted); background: var(--bg-card-subtle); border-radius: 8px; border: 1px dashed var(--border-card);">
        🛡️ No policies match the selected filter "${filterType.toUpperCase()}".
      </div>
    `;
    return;
  }

  grid.innerHTML = list.map(policy => renderPolicyAlertCard(policy)).join('');
}

async function openPolicyDetailsModal(policyId) {
  let policy = (state.insuranceTriggers || []).find(p => (p.policy_id === policyId || p.id === policyId));

  if (!policy) {
    try {
      const res = await fetch(`${API_BASE}/api/insurance/policies/${policyId}?update_id=${state.currentUpdate}`);
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
    <div style="background:${isTriggered ? '#fef2f2' : '#f8fafc'}; border:1px solid ${isTriggered ? '#fecaca' : '#e2e8f0'}; border-radius:8px; padding:0.85rem; margin-bottom:1rem;">
      <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:0.5rem;">
        <div>
          <span style="font-weight:800; color:var(--text-primary); font-size:0.95rem;">${policy.policy_name || policy.zone_name}</span>
          <div style="font-size:0.75rem; color:var(--text-muted); margin-top:0.2rem;">
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
    <div style="font-size:0.8rem; font-weight:800; color:var(--text-primary); margin-bottom:0.5rem; text-transform:uppercase;">Decoupled State Machine Progression</div>
    <div style="display:grid; grid-template-columns:repeat(3, 1fr); gap:0.65rem; margin-bottom:1rem;">
      <div style="background:var(--bg-card-subtle); border:1px solid var(--border-card); border-radius:8px; padding:0.75rem;">
        <div style="font-size:0.7rem; color:var(--text-muted); font-weight:700;">1. PHYSICAL TRIGGER</div>
        <div style="margin-top:0.35rem;">
          ${isTriggered ? '<span class="status-pill status-pill-triggered">⚡ TRIGGERED</span>' : '<span class="status-pill status-pill-monitoring">🛡️ MONITORING</span>'}
        </div>
        <div style="font-size:0.72rem; color:var(--text-secondary); margin-top:0.4rem; line-height:1.4;">
          Live reading (${policy.current_values || policy.current_value}) vs threshold (${policy.threshold_values || policy.threshold_value})
        </div>
      </div>
      <div style="background:var(--bg-card-subtle); border:1px solid var(--border-card); border-radius:8px; padding:0.75rem;">
        <div style="font-size:0.7rem; color:var(--text-muted); font-weight:700;">2. SENSOR VERIFICATION</div>
        <div style="margin-top:0.35rem;">
          ${policy.verification_status === 'VERIFIED' ? '<span class="status-pill status-pill-verified">✓ DATA VERIFIED</span>' : '<span class="status-pill status-pill-pending">⏳ PENDING PASS</span>'}
        </div>
        <div style="font-size:0.72rem; color:var(--text-secondary); margin-top:0.4rem; line-height:1.4;">
          ${policy.verification_source || 'IMD Machilipatnam Doppler DWR-02 & INCOIS Tide Gauge'}
        </div>
      </div>
      <div style="background:var(--bg-card-subtle); border:1px solid var(--border-card); border-radius:8px; padding:0.75rem;">
        <div style="font-size:0.7rem; color:var(--text-muted); font-weight:700;">3. PAYOUT READINESS</div>
        <div style="margin-top:0.35rem;">
          ${isPayoutReady ? '<span class="status-pill status-pill-ready">💰 PAYOUT READY</span>' : '<span class="status-pill status-pill-na">⏸️ Payout readiness unavailable</span>'}
        </div>
        <div style="font-size:0.72rem; color:var(--text-secondary); margin-top:0.4rem; line-height:1.4;">
          ${isPayoutReady ? 'Liquidity unlocked for instant DBT dispatch' : 'Awaiting multi-sig oracle verification signatures'}
        </div>
      </div>
    </div>

    <!-- Live Telemetry Forensic Feeds -->
    <div style="font-size:0.8rem; font-weight:800; color:var(--text-primary); margin-bottom:0.5rem; text-transform:uppercase;">Physical Sensor Forensics & Telemetry Metrics</div>
    <div style="display:grid; grid-template-columns:repeat(2, 1fr); gap:0.65rem; margin-bottom:1rem;">
      <div style="background:#ffffff; border:1px solid var(--border-card); border-radius:8px; padding:0.75rem;">
        <div style="font-size:0.72rem; color:var(--text-muted);">Primary Sustained Wind</div>
        <div style="font-size:1.3rem; font-weight:900; color:${(telemetry.primary_wind_speed_kmh || 0) > 135 ? '#ef4444' : '#2563eb'}; margin:0.2rem 0;">
          ${telemetry.primary_wind_speed_kmh || 0} km/h
        </div>
        <div style="font-size:0.7rem; color:var(--text-muted);">Contract Trigger: &gt; 135 km/h Wind</div>
      </div>
      <div style="background:#ffffff; border:1px solid var(--border-card); border-radius:8px; padding:0.75rem;">
        <div style="font-size:0.72rem; color:var(--text-muted);">Peak Storm Surge Gauge</div>
        <div style="font-size:1.3rem; font-weight:900; color:${(telemetry.peak_surge_height_m || 0) > 2.5 ? '#ef4444' : '#2563eb'}; margin:0.2rem 0;">
          ${telemetry.peak_surge_height_m || 0} m
        </div>
        <div style="font-size:0.7rem; color:var(--text-muted);">Contract Trigger: &gt; 2.5m Surge</div>
      </div>
      <div style="background:#ffffff; border:1px solid var(--border-card); border-radius:8px; padding:0.75rem;">
        <div style="font-size:0.72rem; color:var(--text-muted);">Active Oracle Stations</div>
        <div style="font-size:1.05rem; font-weight:800; color:var(--text-primary); margin:0.2rem 0;">
          ${telemetry.reporting_station_count || 2} Automated Weather Stations
        </div>
        <div style="font-size:0.7rem; color:var(--text-muted);">Signal Latency: ${telemetry.signal_latency_sec || 4.2}s</div>
      </div>
      <div style="background:#ffffff; border:1px solid var(--border-card); border-radius:8px; padding:0.75rem;">
        <div style="font-size:0.72rem; color:var(--text-muted);">Emergency Liquidity Allocation</div>
        <div style="font-size:1.15rem; font-weight:900; color:#059669; margin:0.2rem 0;">
          ${policy.payout_amount_inr}
        </div>
        <div style="font-size:0.7rem; color:var(--text-muted);">Beneficiary: ${policy.insured_entity}</div>
      </div>
    </div>

    <!-- Cryptographic Hash & Multi-Sig Audit -->
    <div style="font-size:0.8rem; font-weight:800; color:var(--text-primary); margin-bottom:0.5rem; text-transform:uppercase;">Cryptographic Oracle Verification & Smart Contract Escrow</div>
    <div style="background:var(--bg-card-subtle); border:1px solid var(--border-card); border-radius:8px; padding:0.85rem; font-family:var(--font-mono); font-size:0.75rem; color:#0f172a; word-break:break-all;">
      <div><b>ORACLE VERIFICATION HASH:</b> <span style="color:#059669;">${policy.verification_hash || 'SHA256-PENDING-SATELLITE-CROSS-VALIDATION'}</span></div>
      <div style="margin-top:0.35rem; color:var(--text-muted);"><b>ESCROW SMART CONTRACT:</b> ${terms.escrow_smart_contract || '0x71C8390A7...4A'} (AP Disaster Emergency Liquidity Pool)</div>
      <div style="margin-top:0.35rem; color:var(--primary);"><b>SETTLEMENT CHANNEL:</b> ${details.settlement_channel || 'Direct Benefit Transfer Escrow'}</div>
      <div style="margin-top:0.35rem; color:var(--text-secondary);"><b>ORACLE SIGNATURES:</b> ${terms.oracle_signatures && terms.oracle_signatures.length > 0 ? terms.oracle_signatures.map(s => `<code>${s}</code>`).join(' · ') : 'Awaiting 3rd consensus signature'}</div>
    </div>
  `;

  modal.classList.add('active');
}

// --- District Executive Briefing ---
async function openBriefingModal() {
  document.getElementById('briefing-modal').classList.add('active');
  const district = state.filters.district === 'all' ? 'kakinada' : state.filters.district;

  try {
    const res = await fetch(`${API_BASE}/api/briefing/${district}?update_id=${state.currentUpdate}`);
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
    const shelterRes = await fetch(`${API_BASE}/api/shelters/nearest?lat=16.98&lon=82.24&district=${district}`);
    const shelters = await shelterRes.json();
    const topShelter = shelters[0] || { name: 'Lawson\'s Bay Multi-Purpose Cyclone Shelter', distance_km: 1.2, elevation_m: 8.5 };

    document.getElementById('shelter-name').textContent = topShelter.name;
    document.getElementById('shelter-distance').textContent = `📍 ${topShelter.distance_km} km away`;
    document.getElementById('shelter-elevation').textContent = `⛰️ Elevation: ${topShelter.elevation_m}m (Safe above 4.2m Surge)`;

    // 2. Multilingual Copilot Guidance
    const copilotRes = await fetch(`${API_BASE}/api/citizen/copilot`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        query: 'What should our family do right now to prepare before cyclone landfall?',
        district: district,
        language: lang,
        lat: 16.98,
        lon: 82.24
      })
    });
    const copilotData = await copilotRes.json();
    document.getElementById('citizen-guidance-text').innerHTML = renderMarkdown(copilotData.response);

  } catch (e) {
    console.error('Error loading citizen data:', e);
  }
}

function speakCitizenGuidance() {
  const text = document.getElementById('citizen-guidance-text').innerText;
  const lang = document.getElementById('citizen-lang-select').value;

  if (!('speechSynthesis' in window)) {
    showToast('⚠️ Web Speech API not supported in this browser', 'error');
    return;
  }

  window.speechSynthesis.cancel();
  const utterance = new SpeechSynthesisUtterance(text);

  // Set language
  if (lang === 'te') utterance.lang = 'te-IN';
  else if (lang === 'hi') utterance.lang = 'hi-IN';
  else if (lang === 'or') utterance.lang = 'or-IN';
  else utterance.lang = 'en-IN';

  utterance.rate = 0.95;
  window.speechSynthesis.speak(utterance);
  showToast(`🔊 Playing voice audio (${utterance.lang})`);
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
  if (band === 'Prepare') return '#0ea5e9';
  return '#10b981';
}

function showToast(msg, type = 'info') {
  const container = document.getElementById('toast-container');
  if (!container) return;

  const toast = document.createElement('div');
  toast.className = 'toast';
  const label = document.createElement('span');
  label.textContent = msg;
  toast.appendChild(label);
  container.appendChild(toast);

  setTimeout(() => {
    toast.style.opacity = '0';
    setTimeout(() => toast.remove(), 300);
  }, 3500);
}

// Simple Markdown parser
function renderMarkdown(md) {
  if (!md) return '';
  // Escape untrusted model/API text before applying this deliberately small
  // Markdown subset. This prevents generated text from becoming executable HTML.
  const escaped = String(md)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
  return escaped
    .replace(/^### (.*$)/gim, '<h4 style="color:#2563eb; margin:0.8rem 0 0.3rem 0; font-weight:800;">$1</h4>')
    .replace(/^## (.*$)/gim, '<h3 style="color:#0f172a; margin:1rem 0 0.4rem 0; font-weight:800; border-bottom:1px solid #e2e8f0; padding-bottom:4px;">$1</h3>')
    .replace(/^# (.*$)/gim, '<h2 style="color:#0f172a; margin:1.2rem 0 0.5rem 0; font-weight:800;">$1</h2>')
    .replace(/\*\*(.*)\*\*/gim, '<b>$1</b>')
    .replace(/\*(.*)\*/gim, '<i>$1</i>')
    .replace(/^- (.*$)/gim, '<li style="margin-left:1.2rem; color:#334155; margin-bottom:3px;">$1</li>')
    .replace(/\n\n/gim, '<br><br>');
}
