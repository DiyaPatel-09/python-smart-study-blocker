"""
migrate_apps.py - One-time script to replace firefox.exe with brave.exe in the database.
Run once: python migrate_apps.py
"""
from database import Database

db = Database()
apps = db.get_blocked_apps()

if "firefox.exe" in apps:
    db.remove_blocked_app("firefox.exe")
    db.add_blocked_app("brave.exe")
    print("Replaced firefox.exe with brave.exe")
elif "brave.exe" not in apps:
    db.add_blocked_app("brave.exe")
    print("Added brave.exe (firefox.exe was not present)")
else:
    print("brave.exe already in list, nothing to do")

db.close()
