# ...existing code from test.py...
from dotenv import load_dotenv
import os, chromadb

load_dotenv()

print("Loaded values:")
print("CHROMA_API_KEY:", os.getenv("CHROMA_API_KEY")[:6] + "..." if os.getenv("CHROMA_API_KEY") else None)
print("CHROMA_TENANT_ID:", os.getenv("CHROMA_TENANT_ID"))
print("CHROMA_DATABASE:", os.getenv("CHROMA_DATABASE"))

client = chromadb.CloudClient(
    api_key=os.getenv("CHROMA_API_KEY"),
    tenant=os.getenv("CHROMA_TENANT_ID"),
    database=os.getenv("CHROMA_DATABASE")
)

print(client.list_collections())
from dotenv import load_dotenv
import os, chromadb

load_dotenv()

print("Loaded values:")
print("CHROMA_API_KEY:", os.getenv("CHROMA_API_KEY")[:6] + "..." if os.getenv("CHROMA_API_KEY") else None)
print("CHROMA_TENANT_ID:", os.getenv("CHROMA_TENANT_ID"))
print("CHROMA_DATABASE:", os.getenv("CHROMA_DATABASE"))

client = chromadb.CloudClient(
    api_key=os.getenv("CHROMA_API_KEY"),
    tenant=os.getenv("CHROMA_TENANT_ID"),
    database=os.getenv("CHROMA_DATABASE")
)

print(client.list_collections())
