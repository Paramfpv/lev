import logging
from typing import List, Dict, Any, Optional
from core.supabase_utils import supabase

class MemoryStore:
    """
    Handles direct DB interactions for User Memory.
    Maps high-level requests to Supabase Query Builder calls.
    
    Schema Mapping:
    - user_id -> user_id
    - scope -> scope
    - project_id -> project_id
    - memory_type -> metadata->>'type' (Assumed stored in JSONB metadata)
    - content -> content
    - confidence -> confidence
    - last_updated -> created_at (Using created_at as proxy for versioning)
    """

    def __init__(self, client=None):
        self.client = client or supabase

    def _clean_response(self, data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Removes Supabase specific metadata if any, returns clean list"""
        return data

    def get_project_memory(
        self, 
        user_id: str, 
        project_id: str, 
        memory_types: Optional[List[str]] = None, 
        limit: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Fetches memories scoped to a specific project.
        """
        try:
            query = self.client.table("user_memory") \
                .select("content, confidence, metadata, created_at, scope, project_id") \
                .eq("user_id", user_id) \
                .eq("scope", "project") \
                .eq("project_id", project_id)

            # Filter by memory_types if provided (using metadata->>type)
            if memory_types:
                # PostgREST syntax for OR filter on a specific column
                # Syntax: metadata->>type.eq.value1,metadata->>type.eq.value2
                or_condition = ",".join([f"metadata->>type.eq.{t}" for t in memory_types])
                query = query.or_(or_condition)

            # Order by Confidence DESC, then Recency
            query = query.order("confidence", desc=True).order("created_at", desc=True).limit(limit)
            
            response = query.execute()
            return self._clean_response(response.data)

        except Exception as e:
            logging.error(f"[MemoryStore] Failed to get project memory: {e}")
            return []

    def get_global_memory(
        self, 
        user_id: str, 
        memory_types: Optional[List[str]] = None, 
        limit: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Fetches global memories.
        """
        try:
            query = self.client.table("user_memory") \
                .select("content, confidence, metadata, created_at, scope") \
                .eq("user_id", user_id) \
                .eq("scope", "global")

            # Filter by memory_types
            if memory_types:
                or_condition = ",".join([f"metadata->>type.eq.{t}" for t in memory_types])
                query = query.or_(or_condition)

            # Order by Confidence DESC, then Recency
            query = query.order("confidence", desc=True).order("created_at", desc=True).limit(limit)

            response = query.execute()
            return self._clean_response(response.data)

        except Exception as e:
            logging.error(f"[MemoryStore] Failed to get global memory: {e}")
            return []

    def save_memory(self, user_id: str, content: str, scope: str, project_id: Optional[str] = None, metadata: Dict = None, confidence: float = 1.0):
        """
        Inserts a new memory into the user_memory table.
        """
        try:
            data = {
                "user_id": user_id,
                "content": content,
                "scope": scope,
                "confidence": confidence,
                "created_at": "now()" # Let DB handle or explicit
            }
            if project_id:
                data["project_id"] = project_id
            
            if metadata:
                data["metadata"] = metadata
                
            self.client.table("user_memory").insert(data).execute()
        except Exception as e:
            logging.error(f"[MemoryStore] Failed to save memory: {e}")

# Singleton (if needed, though class usage is also fine)
memory_store = MemoryStore()
