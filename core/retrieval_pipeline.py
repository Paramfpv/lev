"""
Retrieval Pipeline for LEV Longevity RAG System
- Connects to Chroma Cloud
- Performs vector-based context retrieval
- Uses Groq API for answer generation
"""

import os
import logging
import requests
import threading
import queue
from typing import List, Dict, Optional
from dotenv import load_dotenv
import chromadb

load_dotenv()

MAX_MEMORY_TURNS = 10
MAX_CONTEXT_CHARS = 3000
BACKGROUND_TIMEOUT = int(os.getenv("BACKGROUND_TIMEOUT", "40"))

# ============================================================
# 1️⃣ RAG CHATBOT CLASS
# ============================================================

class LongevityRAGChatbot:
    def __init__(
        self,
        collection_name: str = "lev_protocols",
        llm_model: str = "llama-3.1-8b-instant",
        groq_api_key: Optional[str] = None,
    ):
        self.model = llm_model
        self.groq_api_key = groq_api_key or os.getenv("GROQ_API_KEY")
        self.api_url = os.getenv("GROQ_API_URL", "https://api.groq.com/openai/v1/chat/completions")
        self.memory: List[Dict] = []

        print("[INFO] Connecting to Chroma Cloud...")
        self.client = chromadb.CloudClient(
            api_key=os.getenv("CHROMA_API_KEY"),
            tenant=os.getenv("CHROMA_TENANT_ID"),
            database=os.getenv("CHROMA_DATABASE")
        )
        self.collection = self.client.get_or_create_collection(collection_name)
        print(f"[INFO] Connected to Chroma Cloud collection: {collection_name}")

    # ============================================================
    # MEMORY
    # ============================================================

    def reset_memory(self):
        self.memory = []

    def add_to_memory(self, role: str, content: str):
        self.memory.append({"role": role, "content": content})
        if len(self.memory) > MAX_MEMORY_TURNS * 2:
            self.memory = self.memory[-(MAX_MEMORY_TURNS * 2):]

    # ============================================================
    # RETRIEVAL
    # ============================================================

    def _search_relevant_chunks(self, query: str, top_k: int = 3) -> List[str]:
        """Query Chroma Cloud for relevant chunks"""
        results = self.collection.query(query_texts=[query], n_results=top_k)
        return results.get("documents", [[]])[0]

    # ============================================================
    # MESSAGE BUILDING
    # ============================================================

    def _build_conversational_messages(self, query: str, contexts: List[str]) -> List[Dict]:
        persona = (
            "You are a friendly, science-based longevity expert. "
            "Give short, evidence-based, and practical answers. "
            "If needed, suggest the user consult a doctor."
        )
        system = {"role": "system", "content": persona}

        memory_snippet = "\n".join(
            [f"{m['role']}: {m['content']}" for m in self.memory[-MAX_MEMORY_TURNS * 2:]]
        )
        context_text = "\n\n".join(contexts)[:MAX_CONTEXT_CHARS]

        user = {
            "role": "user",
            "content": f"Context:\n{context_text}\n\nHistory:\n{memory_snippet}\n\nQuestion: {query}",
        }
        return [system, user]

    # ============================================================
    # GROQ API CALL
    # ============================================================

    def _call_groq(self, messages: List[Dict]) -> str:
        """Send the messages to the Groq API and get a reply"""
        if not self.groq_api_key:
            return "Error: missing GROQ_API_KEY."

        headers = {"Authorization": f"Bearer {self.groq_api_key}", "Content-Type": "application/json"}
        payload = {"model": self.model, "messages": messages, "temperature": 0.3, "max_tokens": 800}

        try:
            response = requests.post(self.api_url, headers=headers, json=payload, timeout=BACKGROUND_TIMEOUT)
            if response.status_code != 200:
                return f"API error: {response.status_code} - {response.text}"
            data = response.json()
            return data.get("choices", [{}])[0].get("message", {}).get("content", "")
        except Exception as e:
            return f"Request failed: {e}"

    # ============================================================
    # MAIN CHAT FUNCTION
    # ============================================================

    def chat(self, query: str) -> str:
        """Main method for chat interaction"""
        if not query.strip():
            return "Please enter a valid question."

        contexts = self._search_relevant_chunks(query)
        messages = self._build_conversational_messages(query, contexts)
        reply = self._call_groq(messages)

        self.add_to_memory("user", query)
        self.add_to_memory("assistant", reply)
        return reply
