# StormTracker — Disaster Resilience Solution

## 1. Problem and proposed solution

### Problem
Severe storms and other disasters create a fast-moving information problem. Forecasts, hazard maps, infrastructure status, shelter information and preparedness instructions can be difficult for residents and response teams to interpret together. The result can be delayed preparation, avoidable exposure, and information overload at the moment when people need clarity.

### Proposed solution
**StormTracker** is a web-based disaster-resilience decision-support platform. It converts complex disaster information into a calm, structured experience built around four actions:

1. **Understand** — view the current forecast scenario and hazard layers.
2. **Prepare** — identify vulnerable infrastructure and preparedness priorities.
3. **Act** — access shelter information and plain-language safety guidance.
4. **Verify** — keep official warnings and human authority as the final source of truth.

The platform combines a geospatial situation map, forecast-change comparison, explainable infrastructure impact scoring, preparedness queues, shelter lookup, multilingual citizen guidance, operational briefing tools and a static-demo fallback for reliable public demonstration.

## 2. Intended audience

### Primary users
- **Residents and families:** need short, reassuring, actionable safety guidance.
- **Community volunteers:** need a shared view of hazards, vulnerable facilities and preparedness priorities.
- **District/emergency teams:** need structured situational awareness and operational prioritization.
- **Essential-service operators:** hospitals, power, water and transport teams can use the infrastructure queue to focus preparation.

### Why multiple audiences?
Disaster resilience depends on coordination. The citizen experience answers “What should I do?”, while the operational views answer “What needs preparation and attention?”. Both are connected to the same scenario model.

## 3. Social issue and intended positive impact

The social issue is **unequal access to timely, understandable disaster information**. Technical warnings can be difficult to translate into immediate household or community action, especially when conditions change.

StormTracker aims to create positive impact by:
- reducing information overload with a clear visual hierarchy;
- presenting safety guidance in English, Hindi, Telugu and Odia;
- helping users identify nearby verified shelter information;
- making infrastructure priorities explainable rather than opaque;
- supporting earlier preparation of essential services;
- clearly separating demonstration/simulated data from live official warnings;
- keeping human review in operational advisory workflows.

The intended outcome is not to replace emergency authorities, but to help people and response teams reach the right information faster and prepare more deliberately.

## 4. Core solution features

### Calm citizen experience
A new “Start here” area puts **My Safety**, **Understand the Situation**, and **Help Your Community** before the technical dashboard. The visual language uses soft teal, mint, sky and neutral tones, restrained animation, clear spacing and short instructions.

### Situation map
Leaflet-based map views provide:
- cyclone track and uncertainty corridor;
- storm-surge scenario layers;
- satellite/flood context;
- infrastructure markers;
- scenario controls.

### Impact intelligence
The backend calculates an explainable priority score using:
- hazard exposure;
- vulnerability;
- consequence;
- access criticality;
- data confidence.

### Forecast change view
The “What Changed?” workflow compares forecast updates so users can understand why priorities moved rather than only seeing a new score.

### Shelter and multilingual safety guidance
The Citizen Safety Portal provides:
- nearest shelter information;
- district selection;
- language selection;
- plain-language guidance;
- browser voice playback.

### Operational support
Authorized users can generate draft advisories, district briefings and readiness information. Protected endpoints require an administrator key.

## Deployment and reliability

The repository contains:
- `frontend/` — source web interface;
- `backend/` — FastAPI decision-support API;
- `docs/` — production static build for GitHub Pages;
- `dist/` — generated production distribution;
- `frontend/js/demo-data.js` — bundled demonstration responses.

On static hosting, the application detects unavailable API calls and switches to a visible **Demo mode** rather than showing a broken dashboard. The demo data is labelled so users are not misled into treating it as a live emergency feed.

## Validation

The repaired repository was validated with:
- `python verify_frontend.py` → **ALL FRONTEND VERIFICATIONS PASSED**
- `python -m pytest -q` → **11 passed**
- `python build.py` → **production build generated successfully**

## Safety and limitations

StormTracker should not be treated as an emergency authority or as a substitute for official warnings. The system is a decision-support and preparedness prototype. Forecasts, shelter availability, evacuation orders and emergency instructions can change; users should follow current instructions from the responsible authorities.

The GitHub Pages version uses bundled demonstration data when the backend is unavailable. A production deployment should connect the frontend to authenticated, monitored live services and validate data freshness before exposing it as live public information.
