import os
import json
import logging
import requests
from typing import Dict, List, Optional
from dotenv import load_dotenv

load_dotenv()

class MemoryRouter:
    """
    Pure logic router to decide WHAT memory is needed based on user intent.
    Does NOT fetch from DB.
    """
    def __init__(self, model: str = "llama-3.1-8b-instant"):
        self.api_key = os.getenv("GROQ_API_KEY")
        self.api_url = os.getenv("GROQ_API_URL", "https://api.groq.com/openai/v1/chat/completions")
        self.model = model

    def _call_llm(self, system_prompt: str, user_content: str) -> str:
        """Helper to call Groq/LLM"""
        if not self.api_key:
            logging.warning("No GROQ_API_KEY found. Memory Router disabled.")
            return "{}"

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
            "temperature": 0.1, # Deterministic
            "max_tokens": 500,
            "response_format": {"type": "json_object"} 
        }

        try:
            response = requests.post(self.api_url, headers=headers, json=payload, timeout=5)
            if response.status_code == 200:
                return response.json().get("choices", [{}])[0].get("message", {}).get("content", "")
            else:
                logging.error(f"LLM Router Failed: {response.text}")
                return "{}"
        except Exception as e:
            logging.error(f"LLM Router Exception: {e}")
            return "{}"

    def route(self, user_id: str, session_id: str, project_id: str, user_message: str) -> Dict:
        """
        Classifies intent and decides memory scopes.
        """
        system_prompt = """
        You are a Memory Router. Analyze the user message and classify the INTENT.
        
        Intent Categories:
        - "generic": General questions, greetings, small talk. No deep memory needed.
        - "project_specific": Questions regarding the current project context, code, or rules.
        - "historical_pattern": Questions about past chats, summaries, or "what did I say about X?".
        - "preference_based": Statements or questions about user preferences, habits, or global constraints.

        Rules for Scope Selection:
        - generic -> No memory (or just session).
        - project_specific -> Needs PROJECT and GLOBAL memory.
        - historical_pattern -> Needs GLOBAL memory (and maybe Project).
        - preference_based -> Needs GLOBAL memory.
        
        Output JSON:
        {
          "intent": "category_name",
          "use_session": boolean,
          "use_project": boolean,
          "use_global": boolean,
          "memory_types": ["list", "of", "relevant", "types"]
        }
        """

        context_info = f"Project ID: {project_id}" if project_id else "No Project Context"
        user_input = f"[{context_info}] User Message: {user_message}"

        response = self._call_llm(system_prompt, user_input)
        
        try:
            result = json.loads(response)
        except json.JSONDecodeError:
            # Safe Default
            return {
                "intent": "generic",
                "use_session": true,
                "use_project": False,
                "use_global": False,
                "memory_types": []
            }

        # Enforce hard logic rules (sanitization)
        intent = result.get("intent", "generic")
        
        # Default Logic Mapping
        logic_map = {
            "generic": {"use_session": True, "use_project": False, "use_global": False},
            "project_specific": {"use_session": True, "use_project": True, "use_global": True},
            "historical_pattern": {"use_session": True, "use_project": True, "use_global": True},
            "preference_based": {"use_session": True, "use_project": False, "use_global": True}
        }

        # Apply defaults if LLM missed them, but respect LLM's explicit choice if valid?
        # User asked for deterministic "Rules". Let's enforce the rules from the prompt *strictly* overriding LLM noise.
        # However, the LLM is supposed to return the decision.
        # Let's trust the LLM's classification, but strictly apply the *scope rules* based on classification
        # to ensure the "Rules" requirement is met programmatically.
        
        defaults = logic_map.get(intent, logic_map["generic"])
        
        # Override decisions to ensure strict adherence to safety rules
        result["use_session"] = True # Always safe to have session context? User said "generic questions do not use memory" (maybe implies no *long term* memory).
        # Let's align with user prompt: "generic questions do not use memory" -> implies no PROJ/GLOBAL. Session is usually implicit in chat history, but maybe "use_session" means "search session memory"?
        # Actually session memory IS chat history usually. 
        # But let's stick to the mapped defaults for project/global.
        
        result["use_project"] = defaults["use_project"]
        result["use_global"] = defaults["use_global"]
        
        # Project logic constraint: If no project_id, can't use project memory
        if not project_id:
            result["use_project"] = False

        return result

# Simple test block
if __name__ == "__main__":
    router = MemoryRouter()
    # Test
    print(router.route("user1", "sess1", "proj1", "How do I center a div?")) # Likely generic or project_specific
