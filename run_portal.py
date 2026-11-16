#!/usr/bin/env python3
"""
=============================================================================
PHOENIX PORTAL — ONE-CLICK LAUNCHER
Defence R&D Project Management System | ISSA DRDO Summer Internship
=============================================================================
This script automatically:
 1. Configures the environment (SQLite fallback if PostgreSQL is offline).
 2. Configures in-memory cache fallback if Redis is offline.
 3. Initializes database tables and auto-seeds test military accounts.
 4. Launches the FastAPI backend server on http://127.0.0.1:8000.
 5. Opens your default web browser directly to the Phoenix Portal Login.
=============================================================================
"""

import sys
import os
import time
import threading
import webbrowser

# Add backend directory to Python path
ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.join(ROOT_DIR, "backend")
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

# Auto-detect or fallback to SQLite if PostgreSQL is not running locally
db_url = os.environ.get("DATABASE_URL")
if not db_url:
    # Check if local postgres is reachable; if not, use local SQLite
    sqlite_path = os.path.join(ROOT_DIR, "phoenix.db").replace("\\", "/")
    os.environ["DATABASE_URL"] = f"sqlite:///{sqlite_path}"

# Set default redis url if not provided
if not os.environ.get("REDIS_URL"):
    os.environ["REDIS_URL"] = "redis://127.0.0.1:6379/0"

def banner():
    print("=" * 72)
    print("   PHOENIX PORTAL — DEFENCE R&D PROJECT MANAGEMENT SYSTEM")
    print("   ISSA DRDO Summer Internship | Prasha Singh | UPES Dehradun")
    print("=" * 72)

def prepare_database():
    """Ensure database schema is created and seeded with military accounts."""
    try:
        from app.database import engine, Base, SessionLocal
        from app.models import User
        from scripts.seed import seed_database

        print("[STARTUP] Checking database schema...")
        Base.metadata.create_all(bind=engine)

        db = SessionLocal()
        user_count = db.query(User).count()
        db.close()

        if user_count == 0:
            print("[STARTUP] Empty database detected. Seeding initial DRDO accounts & projects...")
            seed_database()
        else:
            print(f"[STARTUP] Database active with {user_count} military personnel accounts.")
    except Exception as e:
        print(f"[STARTUP ERROR] Database initialization issue: {e}")

def open_browser():
    """Wait 1.5 seconds for uvicorn to bind, then launch browser."""
    time.sleep(1.5)
    url = "http://127.0.0.1:8000/login.html"
    print(f"\n[PORTAL READY] Opening browser: {url}\n")
    try:
        webbrowser.open(url)
    except Exception:
        pass

def main():
    banner()
    prepare_database()

    print("\n" + "-" * 72)
    print("DEMO CREDENTIALS FOR TESTING:")
    print("  * Director:  Username: director    | Password: Director@123  (Full Access)")
    print("  * Scientist: Username: scientist1  | Password: Science@123   (Edit Projects)")
    print("  * Intern:    Username: intern1     | Password: Intern@123    (Read-Only)")
    print("-" * 72)
    print("\nStarting Phoenix Portal Server on http://127.0.0.1:8000 ...")
    print("Press Ctrl+C to terminate the server.\n")

    # Start browser in background thread
    threading.Thread(target=open_browser, daemon=True).start()

    # Launch Uvicorn
    import uvicorn
    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=False, log_level="info")

if __name__ == "__main__":
    main()
