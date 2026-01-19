import sys
import os
import time
from dotenv import load_dotenv

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.memory.memory_extractor import memory_extractor
from core.memory.memory_store import memory_store
from core.supabase_utils import supabase

load_dotenv()

def test_memory_flow():
    print("🚀 Starting Memory System Test...")
    
    # 1. Setup Test Data
    test_user_id = "test-user-001" # Mock ID
    test_project_id = "test-project-A"
    test_message = "Project Rule: Always return responses in valid JSON format."
    
    print(f"\n📝 Simulating User Input: '{test_message}'")
    print(f"   User ID: {test_user_id}")
    print(f"   Project ID: {test_project_id}")

    # 2. Run Extraction (Mimic main.py)
    print("\n⚙️  Running Extractor...")
    try:
        memory_extractor.extract_and_save(
            user_id=test_user_id,
            user_message=test_message,
            project_id=test_project_id
        )
        print("✅ Extraction Complete.")
    except Exception as e:
        print(f"❌ Extraction Failed: {e}")
        return

    # 3. Verify in Database
    print("\n🔍 Verifying in Supabase `user_memory` table...")
    time.sleep(2) # Give it a moment if there's any async lag (though code is sync)
    
    try:
        response = supabase.table("user_memory") \
            .select("*") \
            .eq("user_id", test_user_id) \
            .order("created_at", desc=True) \
            .limit(1) \
            .execute()
            
        data = response.data
        
        if data:
            entry = data[0]
            print("\n✅ MEMORY FOUND!")
            print(f"   ID: {entry['id']}")
            print(f"   Content: {entry['content']}")
            print(f"   Scope: {entry['scope']}")
            print(f"   Confidence: {entry['confidence']}")
            print(f"   Metadata: {entry['metadata']}")
            
            # 4. cleanup
            print("\n🧹 Cleaning up test row...")
            supabase.table("user_memory").delete().eq("id", entry["id"]).execute()
            print("✅ Cleanup complete.")
            
        else:
            print("\n❌ NO MEMORY FOUND. Extraction/Save may have failed silently.")
            
    except Exception as e:
        print(f"❌ Verification Logic Failed: {e}")

if __name__ == "__main__":
    # We need to make sure we have a valid User ID constraint if the DB enforces FK
    # If the schema has "REFERENCES auth.users(id)", we can't use a fake string.
    # We might need to fetch a real user or disable foreign key checks (not possible easily).
    # Strategy: Fetch the first real user from DB to use as test subject.
    
    try:
        print("🔍 Fetching a valid user ID for testing...")
        # Try to find a user from projects or something accessible
        # Since we can't query auth.users directly usually, let's try to query 'projects' to find a user_id
        res = supabase.table("projects").select("user_id").limit(1).execute()
        if res.data:
            real_user_id = res.data[0]['user_id']
            print(f"✅ Using Real User ID: {real_user_id}")
            
            # Monkey patch the test function args or just update logic
            # Let's just run the test logic inside here
            
            test_project_id = "00000000-0000-0000-0000-000000000000" # Dummy UUID for project if FK allows or use real one
            # If projects has FK, we need a real project too.
            res_proj = supabase.table("projects").select("id").eq("user_id", real_user_id).limit(1).execute()
            if res_proj.data:
                test_project_id = res_proj.data[0]['id']
                print(f"✅ Using Real Project ID: {test_project_id}")
                
                # Now run the test
                print("\n🚀 Starting Memory Flow...")
                
                # Input
                # Note: We are using "Always answer in JSON" which is a strong rule.
                test_msg = "Project Rule: Always return responses in valid JSON format."
                
                # Extract
                memory_extractor.extract_and_save(real_user_id, test_msg, test_project_id)
                print("✅ Extractor called.")
                
                # Access DB
                time.sleep(2)
                check = supabase.table("user_memory").select("*").eq("user_id", real_user_id).order("created_at", desc=True).limit(1).execute()
                
                if check.data:
                    m = check.data[0]
                    # Simple check to see if it matches our inserted topic
                    if "JSON" in m["content"]:
                        print(f"\n✅ SUCCESS! Memory Saved: '{m['content']}'")
                        print(f"   Scope: {m['scope']}")
                        
                        # Cleanup
                        supabase.table("user_memory").delete().eq("id", m["id"]).execute()
                        print("✅ Test memory deleted.")
                    else:
                        print(f"\n⚠️ Memory found but content differs: {m['content']}")
                else:
                    print("\n❌ Memory check returned empty.")
            else:
                print("❌ No projects found for user. Cannot verify Project Scope.")
        else:
            print("❌ No users found in public tables. Cannot run FK-constrained test.")
            
    except Exception as e:
        print(f"❌ Test Script Error: {e}")
