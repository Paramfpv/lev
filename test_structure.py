import requests
import uuid
import json

BASE_URL = "http://localhost:8000"

def run_test():
    print("🧪 STARTING VERIFICATION TEST...")

    # 1. Register a new unique user
    email = f"test_user_{uuid.uuid4().hex[:8]}@example.com"
    password = "testpassword123"
    print(f"\n1️⃣ Registering User: {email}")
    
    try:
        res = requests.post(f"{BASE_URL}/register", json={"email": email, "password": password})
        if res.status_code != 200:
            print(f"❌ Registration Failed: {res.text}")
            return
        user_data = res.json()
        user_id = user_data["user_id"]
        print(f"✅ User Registered! ID: {user_id}")
    except Exception as e:
        print(f"❌ Connection Error: {e}")
        return

    # 2. Check Default Projects (Mind, Body, Soul)
    print("\n2️⃣ Checking Default Projects (Mind, Body, Soul)...")
    res = requests.get(f"{BASE_URL}/projects/{user_id}")
    if res.status_code == 200:
        projects = res.json().get("projects", [])
        names = [p["name"] for p in projects]
        print(f"   Found Projects: {names}")
        
        if "Mind" in names and "Body" in names and "Soul" in names:
            print("✅ Default Projects Created Successfully!")
        else:
            print("❌ MISSING Default Projects! Did you run the Trigger SQL?")
            return
            
        # Get Mind ID
        mind_project = next(p for p in projects if p["name"] == "Mind")
        mind_id = mind_project["id"]
    else:
        print(f"❌ Failed to get projects: {res.text}")
        return

    # 3. Create Sub-Project "Meditation" under "Mind"
    print(f"\n3️⃣ Creating Sub-Project 'Meditation' under 'Mind' ({mind_id})...")
    sub_res = requests.post(f"{BASE_URL}/projects", json={
        "user_id": user_id,
        "name": "Meditation",
        "parent_id": mind_id,
        "description": "Focusing on breath."
    })
    
    if sub_res.status_code == 200:
        meditation = sub_res.json()
        meditation_id = meditation["id"]
        print(f"✅ Sub-Project Created! ID: {meditation_id}")
    else:
        print(f"❌ Failed to create sub-project: {sub_res.text}")
        return

    # 4. Create Chat Session in "Meditation"
    print(f"\n4️⃣ Creating Chat Session in 'Meditation'...")
    sess_res = requests.post(f"{BASE_URL}/sessions", json={
        "user_id": user_id,
        "title": "Morning Om",
        "project_id": meditation_id
    })
    
    if sess_res.status_code == 200:
        session = sess_res.json()
        print(f"✅ Chat Session Created! ID: {session['id']}")
        print(f"   Linked to Project ID: {session.get('project_id')}")
        
        if session.get("project_id") == meditation_id:
             print("✅ Session correctly linked to project!")
        else:
             print("❌ Session NOT linked correctly.")
    else:
        print(f"❌ Failed to create session: {sess_res.text}")

    print("\n🎉 VERIFICATION COMPLETE!")

if __name__ == "__main__":
    run_test()
