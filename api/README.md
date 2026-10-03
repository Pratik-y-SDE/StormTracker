# 🔌 API & Integration Hub

This folder is your dedicated space to manage all **API Keys**, **Third-Party Integrations**, and **Custom API Endpoints**.

---

## 📁 Folder Contents

- **`config.py`**: Central place to configure API keys (Gemini, Google Maps, Earth Engine, Weather APIs, SMS gateways).
- **`custom_routes.py`**: Add your own custom FastAPI routes (`@router.get(...)`, `@router.post(...)`).
- **`__init__.py`**: Exports config and routers to the main server.

---

## 🔑 How to Add Your API Keys

Open [config.py](file:///c:/HACKATHON/api/config.py) and paste your keys directly, or set them in the `.env` file:

```python
# In api/config.py:
GEMINI_API_KEY = "your-actual-gemini-key-here"
GOOGLE_MAPS_API_KEY = "your-google-maps-key-here"
WEATHER_API_KEY = "your-weather-key-here"
```

---

## 🚀 How to Add New Custom API Endpoints

Open [custom_routes.py](file:///c:/HACKATHON/api/custom_routes.py) and write your FastAPI functions:

```python
@router.get("/my-new-api")
def my_new_api():
    return {"message": "Hello from custom API!"}
```

This will automatically be accessible at **`http://127.0.0.1:8000/api/custom/my-new-api`** and appear in Swagger docs at **`http://127.0.0.1:8000/docs`**.
