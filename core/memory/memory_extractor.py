import os
import json
import logging
import requests
from typing import Dict, List, Optional, Any
from core.memory.memory_store import memory_store

# Use same env vars as router
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_API_URL = os.getenv("GROQ_API_URL", "https://api.groq.com/openai/v1/chat/completions")
LLM_MODEL = "llama-3.1-8b-instant"

class MemoryExtractor:
    """
    Extracts memory candidates from user messages and applies promotion rules.
    """
    def __init__(self):
        self.api_key = GROQ_API_KEY
        self.api_url = GROQ_API_URL
        self.model = LLM_MODEL

    def _call_llm(self, system_prompt: str, user_content: str) -> str:
        if not self.api_key: return "{}"
        
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
            "temperature": 0.1,
            "max_tokens": 500,
            "response_format": {"type": "json_object"}
        }
        try:
            response = requests.post(self.api_url, headers=headers, json=payload, timeout=5)
            if response.status_code == 200:
                return response.json().get("choices", [{}])[0].get("message", {}).get("content", "")
        except Exception as e:
            logging.error(f"Extractor LLM Error: {e}")
        return "{}"

    def extract_and_save(self, user_id: str, user_message: str, project_id: Optional[str] = None):
        """
        Main entry point: Extract -> Rule Check -> Save
        """
        candidates = self._extract_candidates(user_message)
        
        for candidate in candidates:
            decision = self._promotion_rules(candidate, project_id)
            
            if decision == "IGNORE":
                continue
                
            scope = "project" if decision == "PROJECT" else "global"
            
            # Additional safety: If PROJECT scope but no project_id, fallback to ignore (or global if explicitly global?)
            # Let's say if PROJECT but no ID, we ignore to be safe/strict.
            if scope == "project" and not project_id:
                continue

            memory_store.save_memory(
                user_id=user_id,
                content=candidate["content"],
                scope=scope,
                project_id=project_id if scope == "project" else None,
                metadata={"type": candidate.get("type", "fact")},
                confidence=candidate.get("confidence", 0.5)
            )

    def _extract_candidates(self, message: str) -> List[Dict[str, Any]]:
        system_prompt = """
        You are a Memory Extractor. Extract potential "facts", "preferences", or "rules" from the user text.
        
        Rules:
        - Extract ONLY explicit facts or strong preferences.
        - IGNORE emotions ("I'm angry"), complaints, or transient states ("I'm tired").
        - IGNORE conversational fillers.
        - Assign a CONFIDENCE score (0.0 to 1.0). 1.0 = Explicitly stated ("I am vegan"). 0.5 = Inferred.
        - Assign TYPE: "habit", "preference", "fact", "rule".
        
        Output JSON:
        {
          "candidates": [
             { "content": "User prefers bullet points", "type": "preference", "confidence": 0.9, "is_explicit": true },
             ...
          ]
        }
        """
        response = self._call_llm(system_prompt, message)
        try:
            data = json.loads(response)
            return data.get("candidates", [])
        except:
            return []

    def _promotion_rules(self, candidate: Dict[str, Any], project_id: Optional[str]) -> str:
        """
        Decides: IGNORE, PROJECT, GLOBAL
        """
        # Rule 1: High Confidence Check
        if candidate.get("confidence", 0) < 0.4:
            return "IGNORE"

        # Rule 2: Explicit commands promote easily
        is_explicit = candidate.get("is_explicit", False)
        
        # Rule 3: Content checks (Simplified for now)
        content = candidate.get("content", "").lower()
        
        # Heuristics
        # If it seems universal (name, job, broadly applicable), Global.
        # This is hard to do without LLM, but let's assume the extraction might hint? 
        # For now, default to PROJECT if project_id exists, else GLOBAL if explicit.
        
        # Let's trust the "type". 
        # "Rule" -> Project (usually)
        # "Fact" (My name is...) -> Global
        
        # Implementation of "Strict" Rules from request:
        # "If promotion_rules returns... ignore, project, global"
        
        # For this version, let's use a simple heuristic:
        # If Project ID is present:
        #    If it looks like a Project Rule -> PROJECT
        #    If it looks like a Personal Fact -> GLOBAL
        # If No Project ID:
        #    Only save if Explicit Global Fact -> GLOBAL
        
        if not project_id:
            return "GLOBAL" if is_explicit else "IGNORE"
            
        return "PROJECT" # Default to project scope for safety/containment

memory_extractor = MemoryExtractor()
