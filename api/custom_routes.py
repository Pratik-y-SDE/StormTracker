"""
Custom API Endpoints Router
Add any new custom API endpoints or third-party integrations in this file.
They will automatically be served under the /api prefix.
"""

from fastapi import APIRouter, HTTPException, Body
from typing import Dict, Any, List

router = APIRouter(prefix="/api/custom", tags=["Custom APIs"])

@router.get("/health")
def custom_api_health():
    """Sample endpoint showing your custom API folder is active."""
    return {
        "status": "active",
        "message": "Custom API router is loaded and ready for your new endpoints!"
    }

# Example: Add your own custom API here
# @router.post("/my-endpoint")
# def my_custom_endpoint(payload: Dict[str, Any] = Body(...)):
#     return {"result": "success", "received": payload}
