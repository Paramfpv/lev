import os
import json
import logging
from typing import List, Dict, Optional, Tuple
from core.supabase_utils import supabase
import requests

# You might want to move these to a config/env file later
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_API_URL = os.getenv("GROQ_API_URL", "https://api.groq.com/openai/v1/chat/completions")
LLM_MODEL = "llama-3.1-8b-instant" # Fast model for routing

class MemoryManager:
    """
    Manages user memory: Intent Classification -> Storage/Retrieval
    """
    def __init__(self):
        self.api_key = GROQ_API_KEY
        self.api_url = GROQ_API_URL
        self.model = LLM_MODEL

    def _call_llm(self, system_prompt: str, user_content: str) -> str:
        """Helper to call Groq/LLM"""
        if not self.api_key:
            print("[WARN] No GROQ_API_KEY found. Memory Router disabled.")
            return ""

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content}
        ]
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": 0.1, # Low temp for deterministic routing
            "max_tokens": 500,
            "response_format": {"type": "json_object"} 
        }

        try:
            response = requests.post(self.api_url, headers=headers, json=payload, timeout=5)
            if response.status_code == 200:
                return response.json().get("choices", [{}])[0].get("message", {}).get("content", "")
            else:
                print(f"[ERROR] LLM Router Failed: {response.text}")
                return ""
        except Exception as e:
            print(f"[ERROR] LLM Router Exception: {e}")
            return ""

    def route(self, message: str, user_id: str, session_id: str = None, project_id: str = None) -> Dict:
        """
        Decides if message is STORAGE, RETRIEVAL, or CONVERSATION.
        Returns a dict with action details.
        """
        system_prompt = """
        You are the 'Memory Router' for an AI assistant. Analyze the user's message.
        CLASSIFY into one of these intents:
        1. 'STORAGE': User is stating a fact, preference, or rule to remember (e.g. "My name is X", "Use Python").
        2. 'RETRIEVAL': User is asking a question that requires knowing past facts (e.g. "What is my name?", "Recap the project").
        3. 'CONVERSATION': Standard chat, greeting, or simple follow-up.
        
        Output JSON only:
        {
            "intent": "STORAGE" | "RETRIEVAL" | "CONVERSATION",
            "fact": "extracted fact if STORAGE, else null",
            "scope": "global" | "project" | "session" (if STORAGE, guess best fit),
            "search_query": "search term if RETRIEVAL, else null"
        }
        """
        
        response = self._call_llm(system_prompt, message)
        
        try:
            result = json.loads(response)
        except:
            # Fallback if JSON parsing fails
            return {"intent": "CONVERSATION"}

        # EXECUTE INTENT
        if result.get("intent") == "STORAGE":
            self._save_memory(
                user_id, 
                result.get("fact"), 
                result.get("scope", "session"), 
                session_id, 
                project_id
            )
            return {"intent": "STORAGE"}

        elif result.get("intent") == "RETRIEVAL":
            context = self._retrieve_context(
                user_id, 
                result.get("search_query", message), 
                project_id
            )
            return {"intent": "RETRIEVAL", "context": context}

        return {"intent": "CONVERSATION"}

    def _save_memory(self, user_id, content, scope, session_id, project_id):
        """Inserts into user_memory table"""
        if not content: return

        data = {
            "user_id": user_id,
            "content": content,
            "scope": scope,
            "confidence": 1.0
        }
        
        # Validate Scope Logic
        if scope == "project" and project_id:
            data["project_id"] = project_id
        elif scope == "session" and session_id:
            data["session_id"] = session_id
        elif scope == "global":
            pass # No extra ID needed
        else:
            # Fallback if scope mismatch (e.g. project scope but no project_id)
            data["scope"] = "session"
            if session_id: data["session_id"] = session_id

        try:
            supabase.table("user_memory").insert(data).execute()
            print(f"[MEMORY] Saved: {content} ({scope})")
        except Exception as e:
            print(f"[ERROR] Failed to save memory: {e}")

    def _retrieve_context(self, user_id, query, project_id) -> str:
        """
        Retrieves relevant memories. 
        TODO: Use pgvector embedding search. For now, using simple text match or getting recent.
        Since we haven't set up embedding generation yet, we will just fetch recent Global/Project memories.
        """
        try:
            # 1. Get Global Memories
            global_mems = supabase.table("user_memory") \
                .select("content") \
                .eq("user_id", user_id) \
                .eq("scope", "global") \
                .order("created_at", desc=True) \
                .limit(5) \
                .execute()

            # 2. Get Project Memories
            project_mems = {"data": []}
            if project_id:
                project_mems = supabase.table("user_memory") \
                    .select("content") \
                    .eq("project_id", project_id) \
                    .eq("scope", "project") \
                    .order("created_at", desc=True) \
                    .limit(5) \
                    .execute()

            # Compile Context
            context_lines = []
            if global_mems.data:
                context_lines.append("Global Context:")
                for m in global_mems.data:
                    context_lines.append(f"- {m['content']}")
            
            if project_mems.data:
                context_lines.append("Project Context:")
                for m in project_mems.data:
                    context_lines.append(f"- {m['content']}")

            return "\n".join(context_lines)

        except Exception as e:
            print(f"[ERROR] Context retrieval failed: {e}")
            return ""

# Singleton instance
memory_manager = MemoryManager()
