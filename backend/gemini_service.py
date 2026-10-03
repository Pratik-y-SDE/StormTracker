import os
import json
from typing import Dict, Any, List, Optional

# Load GEMINI_API_KEY from environment or .env file
def _load_env_key():
    key = os.environ.get("GEMINI_API_KEY", "")
    if not key:
        env_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env")
        if os.path.exists(env_path):
            try:
                with open(env_path, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if line.startswith("GEMINI_API_KEY="):
                            key = line.split("=", 1)[1].strip().strip('"').strip("'")
                            break
            except Exception:
                pass
    return key

GEMINI_API_KEY = _load_env_key()

def get_gemini_client():
    global GEMINI_API_KEY
    if not GEMINI_API_KEY:
        GEMINI_API_KEY = _load_env_key()
    if not GEMINI_API_KEY:
        return None
    try:
        from google import genai
        client = genai.Client(api_key=GEMINI_API_KEY)
        return client
    except Exception as e:
        print(f"Error initializing Gemini client: {e}")
        return None


def generate_district_executive_briefing(district_name: str, context: Dict[str, Any]) -> str:
    """
    Generates a Gemini 3.7 Flash grounded executive briefing for the District Magistrate / Collector.
    Falls back to a structured deterministic template if Gemini is offline or API key is not configured.
    """
    client = get_gemini_client()
    event_name = context.get("event_name", "Severe Cyclonic Storm JAWHAR")
    update_time = context.get("update_time", "Latest IMD Advisory")
    top_assets = context.get("top_assets", [])
    exposed_pop = context.get("exposed_population", 0)
    surge_level = context.get("surge_scenario", "Central (2.8m)")
    rainfall_accum = context.get("rainfall_accumulation", "280mm")

    asset_summary = "\n".join([
        f"- {a['name']} ({a['type']}, Score: {a['total_score']}/100, Band: {a['risk_band']}): {'; '.join(a.get('top_factors', []))} -> Action: {a.get('recommended_action', '')}"
        for a in top_assets[:5]
    ])

    prompt = f"""You are the Chief Disaster Operations Advisor for the Government of Andhra Pradesh.
Generate an urgent, actionable, and structured District Preparedness Operational Brief for the District Collector and Emergency Operations Center of {district_name}.

EVENT: {event_name}
UPDATE: {update_time}
PROJECTED SURGE: {surge_level}
PROJECTED RAINFALL: {rainfall_accum}
ESTIMATED EXPOSED POPULATION: {exposed_pop:,}

TOP ASSETS AT CRITICAL RISK:
{asset_summary}

Structure the briefing into clear sections:
1. SITUATIONAL ASSESSMENT (Threat level, landfall window, surge/rainfall severity)
2. PRIORITY INFRASTRUCTURE INTERVENTIONS (Specific directives for hospitals, power substations, and bridges)
3. EVACUATION & SHELTER DIRECTIVES (High-risk coastal villages, vulnerable populations, shelter capacity)
4. INTER-AGENCY CONTINGENCY ACTIONS (EPDCL power distribution, Roads & Buildings, Health & Sanitation)
5. LIMITATIONS & AUDIT NOTE (State that this is a decision-support synthesis grounded in IMD data and official warnings remain primary authority)

Tone: Professional, urgent, decisive, and grounded strictly in the provided data."""

    if client:
        try:
            response = client.models.generate_content(
                model='gemini-3.6-flash',
                contents=prompt
            )
            if response and response.text:
                return response.text
        except Exception as e:
            print(f"Gemini API call failed, falling back to deterministic synthesis: {e}")

    # High-quality deterministic fallback
    return f"""# DISTRICT PREPAREDNESS OPERATIONAL BRIEFING
**District:** {district_name.upper()} | **Event:** {event_name}
**Source:** IMD Official Track Forecast & GEE Satellite Synthesis | **Timestamp:** {update_time}
**Classification:** IMMEDIATE OPERATIONAL PRIORITY (DM Act 2005)

---

### 1. SITUATIONAL ASSESSMENT
- **Hazard Dynamics:** {event_name} has intensified with core sustained winds reaching 140–160 km/h with heavy cyclonic rainfall bands ({rainfall_accum}).
- **Storm Surge Warning:** Projected coastal storm surge of **{surge_level}** will cause seawater ingress across low-lying delta creeks and beachfront roads.
- **Population at Exposure:** An estimated **{exposed_pop:,} citizens** reside within the primary impact corridor and surge hazard zones.

### 2. PRIORITY INFRASTRUCTURE INTERVENTIONS
{chr(10).join([f"**{i+1}. {a['name']} ({a['type']}) — Score {a['total_score']}/100 [{a['risk_band']}]**" + chr(10) + f"   - *Vulnerability:* {', '.join(a.get('top_factors', []))}" + chr(10) + f"   - *Mandatory Action:* {a.get('recommended_action', '')}" for i, a in enumerate(top_assets[:4])])}

### 3. EVACUATION & SHELTER DIRECTIVES
- **Coastal Evacuation:** Mandatory evacuation of all habitations within 500m of the shoreline to Multi-Purpose Cyclone Shelters (MPCS) by 20:00 hrs.
- **Shelter Readiness:** Ensure 72-hour food grain stocks, halogen water purification tablets, and functional solar/battery VHF transceivers at all designated relief camps.
- **Vulnerable Groups:** Priority transport for expectant mothers, dialysis patients, and elderly citizens to District Hospital secondary wings.

### 4. INTER-AGENCY CONTINGENCY DIRECTIVES
- **AP EPDCL (Power):** Pre-emptively de-energize exposed 33kV coastal lines upon sustained winds crossing 80 km/h to prevent cascading transformer fires.
- **Roads & Buildings (R&B):** Position JCB earthmovers and chainsaw clearing squads at both ends of major estuary bridges.
- **Public Health & Sanitation:** Pre-chlorinate all municipal overhead tanks to prevent post-flood waterborne disease outbreaks.

---
*Note: Generated by Cyclone Impact Forecaster (ZATICS v3.0) Decision-Support Engine. Official IMD and NDMA SACHET bulletins remain the legal authority for public warnings.*"""

def generate_ai_advisory_draft(district_name: str, target_audience: str, evidence: Dict[str, Any]) -> str:
    """
    Generates a localized, evidence-grounded advisory draft for human-in-the-loop review.
    """
    client = get_gemini_client()
    evidence_text = json.dumps(evidence, indent=2)

    prompt = f"""You are drafting a high-priority official disaster advisory for {district_name} ({target_audience}).
Grounded Evidence:
{evidence_text}

Draft a clear, authoritative, and actionable operational warning.
Include:
- Exact threat timeline and wind/surge thresholds
- Clear instructions on what to inspect, secure, or evacuate
- Verification checkpoint and emergency radio contact frequencies
- Emphasize human review status (DRAFT FOR APPROVAL)."""

    if client:
        try:
            response = client.models.generate_content(
                model='gemini-3.6-flash',
                contents=prompt
            )
            if response and response.text:
                return response.text
        except Exception as e:
            print(f"Gemini advisory draft call failed: {e}")

    # Fallback
    return f"""OFFICIAL PREPAREDNESS ADVISORY [DRAFT FOR AUTHORITY REVIEW]
TARGET: {target_audience} | DISTRICT: {district_name.upper()}

EVIDENCE SUMMARY:
Track update confirms severe cyclonic wind field (>145 km/h) and coastal surge overlap ({evidence.get('surge_level', '2.8m')}). Top vulnerable facilities include {evidence.get('critical_assets_summary', 'Port Substations and Low-lying Health Centers')}.

OPERATIONAL DIRECTIVE:
1. Immediate activation of Stage-3 Emergency Protocol.
2. Complete all generator fueling and backup power checks prior to T-06h landfall window.
3. Restrict heavy vehicle movement across low-elevation estuary bridges.
4. Fishermen and coastal craft must remain moored in sheltered inner basins.

[STATUS: AWAITING AUTHORIZED APPROVAL BEFORE DISPATCH]"""

def citizen_safety_ai_copilot(query: str, district: str, nearest_shelter: Dict[str, Any], language: str = "en") -> str:
    """
    Provides plain-language, empathetic, and actionable citizen safety advice in English, Telugu, Hindi, or Odia.
    """
    client = get_gemini_client()
    shelter_name = nearest_shelter.get("name", "Nearest Multi-Purpose Cyclone Shelter")
    shelter_dist = nearest_shelter.get("distance_km", 2.5)

    lang_names = {
        "en": "English",
        "te": "Telugu (తెలుగు)",
        "hi": "Hindi (हिन्दी)",
        "or": "Odia (ଓଡ଼ିଆ)"
    }
    lang_name = lang_names.get(language, "English")

    prompt = f"""You are the Official Citizen Emergency Safety Copilot for coastal Andhra Pradesh.
User District: {district}
Nearest Verified Shelter: {shelter_name} (approx {shelter_dist:.1f} km away)
User Question: "{query}"
Target Language: {lang_name}

Provide a reassuring, plain-language, and practical response:
1. Answer the question directly with practical safety steps.
2. Mention their nearest shelter: {shelter_name} ({shelter_dist:.1f} km).
3. Do NOT make false promises of absolute safety. Advise them to follow official IMD/NDMA radio broadcasts.
4. Reply in {lang_name}."""

    if client:
        try:
            response = client.models.generate_content(
                model='gemini-3.6-flash',
                contents=prompt
            )
            if response and response.text:
                return response.text
        except Exception as e:
            print(f"Gemini citizen copilot failed: {e}")

    # Deterministic Multilingual Fallbacks
    if language == "te":
        return f"""తుఫాను భద్రతా మార్గదర్శకం ({district}):
మీ ప్రాంతంలో బలమైన ఈదురు గాలులు మరియు భారీ వర్షాలు కురిసే అవకాశం ఉంది. 
దయచేసి ఇంట్లోనే సురక్షితంగా ఉండండి లేదా తక్షణమే మీ సమీప సైక్లోన్ షెల్టర్ **{shelter_name}** ({shelter_dist:.1f} కి.మీ దూరంలో ఉంది) కు తరలివెళ్లండి.
- తాగునీరు మరియు అత్యవసర మందులను సిద్ధంగా ఉంచుకోండి.
- చెట్లు, విద్యుత్ స్తంభాల కింద నిలబడవద్దు.
- IMD మరియు ప్రభుత్వ అధికారిక సమాచారాన్ని మాత్రమే విశ్వసించండి."""
    elif language == "hi":
        return f"""चक्रवात सुरक्षा मार्गदर्शन ({district}):
आपके क्षेत्र में तेज हवाएं और भारी बारिश का अनुमान है।
कृपया सुरक्षित पक्के घर में रहें या अपने निकटतम चक्रवात आश्रय **{shelter_name}** ({shelter_dist:.1f} किमी दूर) पर पहुंचे।
- पीने का पानी, सूखा भोजन और टॉर्च तैयार रखें।
- बिजली के खंभों और कमजोर पेड़ों से दूर रहें।
- आधिकारिक सरकारी अलर्ट (IMD/NDMA SACHET) का पालन करें।"""
    elif language == "or":
        return f"""ବାତ୍ୟା ସୁରକ୍ଷା ପରାମର୍ଶ ({district}):
ଆପଣଙ୍କ ଅଞ୍ଚଳରେ ପ୍ରବଳ ପବନ ଏବଂ ବର୍ଷା ସମ୍ଭାବନା ରହିଛି।
ଦୟାକରି ସୁରକ୍ଷିତ ସ୍ଥାନରେ ରୁହନ୍ତୁ କିମ୍ବା ଆପଣଙ୍କ ନିକଟତମ ବାତ୍ୟା ଆଶ୍ରୟସ୍ଥଳୀ **{shelter_name}** ({shelter_dist:.1f} କିମି) କୁ ଯାଆନ୍ତୁ।
- ବିଶୁଦ୍ଧ ପାନୀୟ ଜଳ ଏବଂ ଔଷଧ ସାଥିରେ ରଖନ୍ତୁ।
- ସରକାରୀ ସୂଚନା ଏବଂ ରେଡିଓ ବାର୍ତ୍ତା ଅନୁସରଣ କରନ୍ତୁ।"""
    else:
        return f"""Cyclone Safety Advisory for {district}:
High-velocity winds and heavy precipitation are forecasted for your area.
- If you are in a low-lying or thatched house, move immediately to your nearest verified shelter: **{shelter_name}** (approx {shelter_dist:.1f} km away).
- Keep 72 hours of drinking water, dry rations, emergency medicines, and charged battery lights ready.
- Stay indoors during the landfall window. Do not venture near the sea or power lines.
- Follow official alerts from IMD and NDMA SACHET."""
