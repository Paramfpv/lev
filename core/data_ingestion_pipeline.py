import os
import json
import logging
from typing import List, Dict, Set
from dotenv import load_dotenv
import chromadb
from langchain_text_splitters import RecursiveCharacterTextSplitter

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

load_dotenv()

# Configuration
PROTOCOLS_DIR = os.path.join(os.getcwd(), "protocols_data")
PROCESSED_DATA_DIR = os.path.join(os.getcwd(), "processed_data")
OUTPUT_FILE = os.path.join(PROCESSED_DATA_DIR, "all_chunks.json")
COLLECTION_NAME = "lev_protocols"

# Chroma Config
CHROMA_API_KEY = os.getenv("CHROMA_API_KEY")
CHROMA_TENANT_ID = os.getenv("CHROMA_TENANT_ID")
CHROMA_DATABASE = os.getenv("CHROMA_DATABASE")

def load_protocols(data_dir: str, exclude_files: Set[str] = None) -> List[Dict[str, str]]:
    """Loads .txt files from the protocols directory, skipping excluded ones."""
    documents = []
    if not os.path.exists(data_dir):
        logging.error(f"Directory not found: {data_dir}")
        return []

    exclude_files = exclude_files or set()
    files_loaded = 0

    for filename in os.listdir(data_dir):
        if filename.endswith(".txt"):
            if filename in exclude_files:
                continue
            
            filepath = os.path.join(data_dir, filename)
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    content = f.read()
                    documents.append({"source": filename, "content": content})
                    files_loaded += 1
            except Exception as e:
                logging.warning(f"Failed to read {filename}: {e}")
    
    if files_loaded > 0:
        logging.info(f"Loaded {files_loaded} new documents from {data_dir}")
    else:
        logging.info("No new documents to load.")
        
    return documents

def chunk_data(documents: List[Dict[str, str]]) -> List[Dict]:
    """Chunks documents into smaller pieces for retrieval."""
    if not documents:
        return []

    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,
        chunk_overlap=200,
        length_function=len
    )

    all_chunks = []
    for doc in documents:
        chunks = text_splitter.split_text(doc["content"])
        protocol_name = doc["source"].replace(".txt", "")
        
        for i, chunk in enumerate(chunks):
            chunk_data = {
                "chunk_id": f"{protocol_name}_{i}",
                "protocol_name": protocol_name,
                "source": doc["source"],
                "content": chunk
            }
            all_chunks.append(chunk_data)
            
    logging.info(f"Created {len(all_chunks)} chunks from {len(documents)} documents")
    return all_chunks

def load_existing_chunks(output_path: str) -> List[Dict]:
    """Loads existing chunks from JSON file."""
    if not os.path.exists(output_path):
        return []
    try:
        with open(output_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logging.error(f"Failed to load existing JSON: {e}")
        return []

def save_to_json(chunks: List[Dict], output_path: str):
    """Saves processed chunks to a JSON file."""
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    try:
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(chunks, f, indent=2)
        logging.info(f"Saved total {len(chunks)} chunks to {output_path}")
    except Exception as e:
        logging.error(f"Failed to save JSON: {e}")

def ingest_to_chroma(chunks: List[Dict]):
    """Ingests processed chunks into Chroma Cloud."""
    if not chunks:
        return

    if not CHROMA_API_KEY:
        logging.error("Missing CHROMA_API_KEY. Skipping vector ingestion.")
        return

    try:
        logging.info("Connecting to Chroma Cloud...")
        client = chromadb.CloudClient(
            api_key=CHROMA_API_KEY,
            tenant=CHROMA_TENANT_ID,
            database=CHROMA_DATABASE
        )
        
        collection = client.get_or_create_collection(name=COLLECTION_NAME)
        
        # Prepare data for insertion
        ids = [c["chunk_id"] for c in chunks]
        documents = [c["content"] for c in chunks]
        metadatas = [{"source": c["source"], "protocol_name": c["protocol_name"]} for c in chunks]
        
        # Insert in batches
        batch_size = 100
        total_chunks = len(chunks)
        logging.info(f"Ingesting {total_chunks} new chunks into collection '{COLLECTION_NAME}'...")
        
        for i in range(0, total_chunks, batch_size):
            batch_ids = ids[i:i+batch_size]
            batch_docs = documents[i:i+batch_size]
            batch_metas = metadatas[i:i+batch_size]
            
            collection.upsert(
                ids=batch_ids,
                documents=batch_docs,
                metadatas=batch_metas
            )
            if (i + batch_size) % 500 == 0:
                 logging.info(f"Processed {i + batch_size}/{total_chunks} chunks...")

        logging.info("Successfully ingested new chunks into ChromaDB.")

    except Exception as e:
        logging.error(f"ChromaDB ingestion failed: {e}")

def run_simple_pipeline():
    """Main function to run the data ingestion pipeline."""
    print("🚀 Starting Data Ingestion Pipeline...")
    
    # 1. Identify Existing Data
    existing_chunks = load_existing_chunks(OUTPUT_FILE)
    processed_files = set(c["source"] for c in existing_chunks)
    logging.info(f"Found {len(processed_files)} already processed files.")

    # 2. Load Only NEW Data
    new_docs = load_protocols(PROTOCOLS_DIR, exclude_files=processed_files)
    
    if not new_docs:
        print("✅ No new documents found. Everything is up to date!")
        return

    # 3. Chunk New Data
    new_chunks = chunk_data(new_docs)

    # 4. Save (Append) to JSON
    all_chunks = existing_chunks + new_chunks
    save_to_json(all_chunks, OUTPUT_FILE)

    # 5. Ingest ONLY New chunks to Vector DB
    ingest_to_chroma(new_chunks)

    print(f"✅ Data Ingestion Complete! Added {len(new_chunks)} new chunks.")

if __name__ == "__main__":
    run_simple_pipeline()
