"""Test D&D multi-player flow end-to-end."""
import json
import os
import subprocess
import sys

os.environ["PYTHONIOENCODING"] = "utf-8"

BASE = "https://bank-bot-ruby.vercel.app"

def api(method, path, body=None):
    args = ["curl.exe", "-s", "--max-time", "120", "-X", method]
    if body:
        args += ["-H", "Content-Type: application/json", "-d", json.dumps(body)]
    args.append(BASE + path)
    r = subprocess.run(args, capture_output=True, text=True)
    try:
        return json.loads(r.stdout)
    except:
        return {"error": r.stdout[:500], "raw": r.stdout[:500]}

def api_get(path, params=None):
    if params:
        qs = "&".join(f"{k}={v}" for k,v in params.items())
        path = BASE + path + "?" + qs
    else:
        path = BASE + path
    args = ["curl.exe", "-s", "--max-time", "120", path]
    r = subprocess.run(args, capture_output=True, text=True)
    try:
        return json.loads(r.stdout)
    except:
        return {"error": r.stdout[:500], "raw": r.stdout[:500]}

# 1. Create session as P1
print("=== 1. Create session ===")
r = api("POST", "/api/dnd/start", {"name": "MultiTest", "user_id": "p1"})
print(f"   active={r.get('active')} session={r.get('session')}")
if r.get("session"):
    SESSION_ID = r["session"]["id"]
else:
    # Find current session for P1
    r2 = api_get("/api/dnd/status", {"user_id": "p1"})
    print(f"   status={r2}")
    if r2.get("session"):
        SESSION_ID = r2["session"]["id"]
    else:
        print("   ERROR: no session found")
        exit(1)

# 2. P1 acts
print(f"\n=== 2. P1 acts (session {SESSION_ID}) ===")
r = api("POST", "/api/dnd/act", {"action": "I enter the ancient temple and light a torch", "user_id": "p1"})
print(f"   reply={r.get('reply','')[:100]}")

# 3. Check log for P1
print("\n=== 3. Log after P1 ===")
r = api_get("/api/dnd/log", {"session_id": SESSION_ID, "user_id": "p1"})
print(f"   entries={len(r.get('log',[]))}")

# 4. P2 joins
print(f"\n=== 4. P2 joins {SESSION_ID} ===")
r = api("POST", "/api/dnd/join", {"session_id": SESSION_ID, "user_id": "p2"})
print(f"   reply={r.get('reply','')[:100]}")

# 5. P2 acts
print("\n=== 5. P2 acts ===")
r = api("POST", "/api/dnd/act", {"action": "I follow P1 and look for traps", "user_id": "p2"})
print(f"   reply={r.get('reply','')[:100]}")

# 6. Final log
print("\n=== 6. Final log ===")
r = api_get("/api/dnd/log", {"session_id": SESSION_ID, "user_id": "p1"})
print(f"   entries={len(r.get('log',[]))}")
for i, e in enumerate(r.get("log", [])):
    print(f"   [{i}] role={e.get('role')} content={e.get('content','')[:80]}")
