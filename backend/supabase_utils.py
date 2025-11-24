from supabase import create_client, Client
import os
from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

def test_supabase_connection():
    try:
        # Try to list tables (should succeed if credentials are correct)
        response = supabase.table("chat_history").select("*").limit(1).execute()
        print("Supabase connection successful! Table 'chat_history' accessible.")
        print("Sample row:", response.data)
    except Exception as e:
        print("Supabase connection failed:", e)

if __name__ == "__main__":
    test_supabase_connection()
