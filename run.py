#!/usr/bin/env python3
"""
ZATICS v3.0 — CYCLONE IMPACT FORECASTER
Single-Command Launcher (Windows & Cross-Platform Safe)

Usage:
  python run.py
"""

import sys
import os
import subprocess

# Ensure UTF-8 output encoding on Windows consoles
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

def check_and_install_dependencies():
    print("=" * 70)
    print("   ZATICS v3.0 // CYCLONE IMPACT FORECASTER")
    print("   Anticipatory Action & Infrastructure Preparedness Platform")
    print("=" * 70)
    print("\n[1/3] Verifying environment & initializing SQLite database...")

    try:
        from backend.db import init_db
        init_db()
        print("  [OK] Database verified & pre-seeded with 40+ AP coastal assets")
    except Exception as e:
        print(f"  [WARN] Notice during DB init: {e}")

def main():
    check_and_install_dependencies()

    print("\n[2/3] Checking FastAPI & Uvicorn runtime...")
    try:
        import uvicorn
        import fastapi
    except ImportError:
        print("  Installing missing dependencies from requirements.txt...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"])

    port = int(os.environ.get("PORT", 8000))
    host = os.environ.get("HOST", "0.0.0.0")
    display_host = "127.0.0.1" if host == "0.0.0.0" else host
    url = f"http://{display_host}:{port}"

    print(f"\n[3/3] Launching ZATICS v3.0 Command Center at {url}")
    print("=" * 70)
    print(f"  * Tactical Operations Center: {url}")
    print(f"  * Interactive API Docs (Swagger): {url}/docs")
    print(f"  * Citizen Safety Portal: {url} (Click 'Citizen Portal')")
    print("=" * 70)
    print("\nServer is running. Press Ctrl+C to stop.\n")

    import uvicorn
    uvicorn.run("backend.main:app", host=host, port=port, reload=False)

if __name__ == "__main__":
    main()
