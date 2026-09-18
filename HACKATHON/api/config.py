"""
API Configuration & Key Manager
Central credentials and configuration for Google Gemini AI and Google Earth Engine (GEE).
"""

import os

# Helper to load key from environment or root .env
def _load_env_val(var_name: str, default: str = "") -> str:
    val = os.environ.get(var_name, "")
    if not val:
        env_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env")
        if os.path.exists(env_path):
            try:
                with open(env_path, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if line.startswith(f"{var_name}="):
                            val = line.split("=", 1)[1].strip().strip('"').strip("'")
                            break
            except Exception:
                pass
    return val or default

# ==============================================================================
# 1. Google Gemini AI API Configuration
# ==============================================================================
GEMINI_API_KEY = _load_env_val("GEMINI_API_KEY", "")

# ==============================================================================
# 2. Google Earth Engine (GEE) Service Account Credentials
# ==============================================================================
GEE_SERVICE_ACCOUNT = _load_env_val("GEE_SERVICE_ACCOUNT", "")
GEE_PROJECT_ID = _load_env_val("GEE_PROJECT_ID", "")
GEE_PRIVATE_KEY_PATH = _load_env_val(
    "GEE_PRIVATE_KEY_PATH",
    os.path.join(os.path.dirname(__file__), "gee-credentials.json")
)

# ==============================================================================
# 3. Geospatial, Weather & Alert Gateways (Optional)
# ==============================================================================
GOOGLE_MAPS_API_KEY = os.environ.get("GOOGLE_MAPS_API_KEY", "")
WEATHER_API_KEY = os.environ.get("WEATHER_API_KEY", "")
SMS_GATEWAY_API_KEY = os.environ.get("SMS_GATEWAY_API_KEY", "")

# Helper function to get all active keys
def get_api_status():
    return {
        "gemini_api_configured": bool(GEMINI_API_KEY),
        "gee_configured": bool(GEE_SERVICE_ACCOUNT and os.path.exists(GEE_PRIVATE_KEY_PATH)),
        "gee_project_id": GEE_PROJECT_ID,
        "gee_service_account": GEE_SERVICE_ACCOUNT,
        "google_maps_configured": bool(GOOGLE_MAPS_API_KEY),
        "weather_api_configured": bool(WEATHER_API_KEY),
        "sms_gateway_configured": bool(SMS_GATEWAY_API_KEY)
    }
