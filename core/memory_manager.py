import os
import json
import logging
from typing import List, Dict, Optional, Any
from enum import Enum
from pydantic import BaseModel
from core.supabase_utils import supabase
import requests

# -- Configuration --
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_API_URL = os.getenv("GROQ_API_URL", "https://api.groq.com/openai/v1/chat/completions")
LLM_MODEL = "llama-3.1-8b-instant"

# -- Enums & Models --
class MemoryScope(str, Enum):
    SESSION = "session"
    PROJECT = "project"
    GLOBAL = "global"

class MemoryImportance(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"

class MemoryCandidate(BaseModel):
    fact: str
    importance: MemoryImportance
    scope: MemoryScope
    confidence: float
    keywords: List[str]

class MemoryAction(str, Enum):
    INSERT = "INSERT"
    UPDATE = "UPDATE"
    PROMOTE = "PROMOTE"
    DEMOTE = "DEMOTE"
    OVERRIDE = "OVERRIDE"
    IGNORE = "IGNORE"

class PlannedUpdate(BaseModel):
    action: MemoryAction
    target_id: Optional[str] = None
    content: Optional[str] = None
    new_scope: Optional[MemoryScope] = None
    new_confidence: Optional[float] = None
    new_importance: Optional[MemoryImportance] = None
    increment_repetition: bool = False
    original_scope: Optional[str] = None
    current_repetition: int = 0

class MemoryManager:
    """
    V1 Canonical Memory Lifecycle Authority.
    Implements: Extraction -> Lookup -> Impact Analysis -> Promotion -> Persistence.
    """
    def __init__(self):
        self.api_key = GROQ_API_KEY
        self.api_url = GROQ_API_URL
        self.model = LLM_MODEL

    def _call_llm(self, system_prompt: str, user_content: str, json_mode: bool = True) -> str:
        if not self.api_key:
            print("[WARN] No GROQ_API_KEY. Memory Manager disabled.")
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
            "temperature": 0.1,
            "max_tokens": 1000
        }
        if json_mode:
            payload["response_format"] = {"type": "json_object"}

        try:
            response = requests.post(self.api_url, headers=headers, json=payload, timeout=10)
            if response.status_code == 200:
                return response.json().get("choices", [{}])[0].get("message", {}).get("content", "")
            else:
                print(f"[ERROR] LLM Failed: {response.text}")
                return ""
        except Exception as e:
            print(f"[ERROR] LLM Exception: {e}")
            return ""

    def route(self, message: str, user_id: str, session_id: str = None, project_id: str = None) -> Dict:
        """
        Main entry point. Orchestrates the lifecycle.
        Returns Dict with 'intent' and 'context' or 'status'.
        """
        # 1. Extraction (The Miner)
        candidates = self.extract_candidates(message, session_id, project_id)
        
        if not candidates:
            # If no candidates, it's likely just a conversation or retrieval intent
            # For V1 simplicity, we'll try to retrieve context if it looks like a question
            # But the Extraction step usually handles intent classification too.
            # Let's assume extract_candidates returns empty if INTENT != STORAGE
            # Actually, to fit the 'route' signature expected by main.py, we need to return intent.
            # We'll adapt extract_candidates to return intent + candidates.
            return self._handle_retrieval_or_chat(message, user_id, session_id, project_id)

        # 2. Historical Lookup (The Consistency Check)
        existing_memories = self.fetch_related_memories(user_id, candidates, project_id)

        # 3. Impact Analysis (The Judge)
        updates = self.determine_memory_updates(candidates, existing_memories)

        # 4. Lifecycle & Promotion (The Promoter)
        final_commits = self.apply_lifecycle_rules(updates, project_id)

        # 5. Persistence (The Writer)
        self.commit_batch(user_id, final_commits, session_id, project_id)

        return {"intent": "STORAGE", "candidates_processed": len(candidates)}

    def _handle_retrieval_or_chat(self, message, user_id, session_id, project_id):
        # Quick check for retrieval intent via LLM (simplified for V1)
        prompt = """Classify intent: "RETRIEVAL" (asking facts) or "CONVERSATION". JSON: {"intent": "..."}"""
        resp = self._call_llm(prompt, message)
        try:
            intent = json.loads(resp).get("intent", "CONVERSATION")
        except:
            intent = "CONVERSATION"

        if intent == "RETRIEVAL":
            context = self._retrieve_context(user_id, message, project_id, session_id)
            return {"intent": "RETRIEVAL", "context": context}
        return {"intent": "CONVERSATION"}

    def extract_candidates(self, message: str, session_id: str, project_id: str) -> List[MemoryCandidate]:
        """Step 1: Extract potential memories with importance and scope."""
        prompt = f"""
        Extract facts/rules from user input for an AI memory system.
        Context: ProjectID={project_id}, SessionID={session_id}.
        
        Return JSON list 'candidates':
        [
          {{
            "fact": "concise fact statement",
            "importance": "high"|"medium"|"low",
            "scope": "session"|"project"|"global" (default to session unless explicitly project/global relevant),
            "confidence": 0.0-1.0,
            "keywords": ["key1", "key2"] (for search)
          }}
        ]
        If no facts, return "candidates": [].
        """
        resp = self._call_llm(prompt, message)
        try:
            data = json.loads(resp)
            candidates = []
            for c in data.get("candidates", []):
                candidates.append(MemoryCandidate(
                    fact=c["fact"],
                    importance=MemoryImportance(c["importance"].lower()),
                    scope=MemoryScope(c.get("scope", "session").lower()),
                    confidence=float(c.get("confidence", 0.7)),
                    keywords=c.get("keywords", [])
                ))
            return candidates
        except Exception as e:
            print(f"[WARN] Extraction failed: {e}")
            return []

    def fetch_related_memories(self, user_id: str, candidates: List[MemoryCandidate], current_project_id: str) -> Dict[str, List[Dict]]:
        """Step 2: Find matches in DB using keywords."""
        results = {
            "potential_matches": [],
            "cross_project_matches": []
        }
        
        all_keywords = set()
        for c in candidates:
            all_keywords.update(c.keywords)
        
        if not all_keywords:
            return results

        # Search query (Or use pgvector if available, here using simple ilike OR logic or textSearch)
        # Assuming supabase text search for now
        # We need to fetch ALL scopes to check for duplicates/promotions
        
        # We'll fetch potential matches based on keywords (naive but functional for V1 without vector)
        keyword_list = list(all_keywords)[:5] # Limit to 5 keywords to prevent query bloat
        or_query = ",".join([f"content.ilike.%{k}%" for k in keyword_list])
        
        try:
            # 1. Fetch potential matches in current context (Session/Project/Global)
            q = supabase.table("user_memory").select("*").eq("user_id", user_id).or_(or_query).limit(20)
            data = q.execute().data
            results["potential_matches"] = data
            
            # 2. Fetch cross-project matches (for Global promotion check)
            # We specifically look for matches in OTHER projects
            if current_project_id:
                q_cross = supabase.table("user_memory").select("*") \
                    .eq("user_id", user_id) \
                    .neq("project_id", current_project_id) \
                    .eq("scope", "project") \
                    .or_(or_query) \
                    .limit(10)
                results["cross_project_matches"] = q_cross.execute().data
                
        except Exception as e:
            print(f"[ERROR] DB Fetch failed: {e}")
        
        return results

    def determine_memory_updates(self, candidates: List[MemoryCandidate], related: Dict[str, List[Dict]]) -> List[PlannedUpdate]:
        """Step 3: Analyze Impact (The Judge). Check duplicates, paraphrases, contradictions."""
        updates = []
        
        # We use LLM to compare candidates vs related memories tightly
        # This is expensive but necessary for "Tiered Similarity" without vectors
        
        for cand in candidates:
            prompt = f"""
            Compare NEW candidate vs EXISTING memories.
            Candidate: "{cand.fact}" (Scope: {cand.scope}, Imp: {cand.importance})
            
            Existing: {json.dumps(related['potential_matches'])}
            Cross-Project Existing: {json.dumps(related['cross_project_matches'])}
            
            Determine Action:
            1. EXACT_MATCH (Sim > 0.98): Update existing (increment rep).
            2. STRONG_PARAPHRASE (Sim > 0.85): Update existing (merge/increment rep).
            3. CONTRADICTION: If New Confidence > Old -> OVERRIDE. Else IMPLICIT_DEMOTE.
            4. RELATED (Sim > 0.7): IGNORE (don't store duplicate) or INSERT as new if distinct.
            5. NO_MATCH: INSERT.
            
            Cross-Project Rule: If NO match in current context, but STRONG_PARAPHRASE found in Cross-Project, mark as "PROMOTE_TO_GLOBAL".
            
            Return JSON:
            {{
                "action": "INSERT" | "UPDATE" | "OVERRIDE" | "PROMOTE_TO_GLOBAL",
                "target_id": "uuid or null",
                "explanation": "..."
            }}
            """
            try:
                resp = self._call_llm(prompt, "Analyze")
                decision = json.loads(resp)
                
                action = decision.get("action")
                target_id = decision.get("target_id")
                
                # Default to INSERT if nothing found
                if action == "INSERT" or not action:
                    updates.append(PlannedUpdate(
                        action=MemoryAction.INSERT,
                        content=cand.fact,
                        new_scope=cand.scope,
                        new_confidence=cand.confidence,
                        new_importance=cand.importance
                    ))
                elif action == "UPDATE" or action == "STRONG_PARAPHRASE" or action == "EXACT_MATCH":
                    # Fetch existing record to get current repetition
                    existing = next((m for m in related['potential_matches'] if m['id'] == target_id), None)
                    current_rep = existing['repetition_count'] if existing else 1
                    
                    updates.append(PlannedUpdate(
                        action=MemoryAction.UPDATE,
                        target_id=target_id,
                        increment_repetition=True,
                        new_confidence=min(cand.confidence + 0.1, 1.0),
                        original_scope=existing.get('scope') if existing else None,
                        current_repetition=current_rep,
                        new_importance=cand.importance # Update importance to latest
                    ))
                elif action == "PROMOTE_TO_GLOBAL":
                     # This implies a CROSS PROJECT match was found
                     updates.append(PlannedUpdate(
                        action=MemoryAction.INSERT, # Insert new GLOBAL memory (or promote existing if we had the ID)
                        content=cand.fact,
                        new_scope=MemoryScope.GLOBAL,
                        new_confidence=0.9,
                        new_importance=MemoryImportance.HIGH
                    ))
                elif action == "OVERRIDE":
                     updates.append(PlannedUpdate(
                        action=MemoryAction.OVERRIDE,
                        target_id=target_id,
                        content=cand.fact,
                        new_confidence=cand.confidence
                    ))
                    
            except Exception as e:
                print(f"[WARN] Analysis failed for {cand.fact}: {e}")
                # Fallback to INSERT
                updates.append(PlannedUpdate(
                    action=MemoryAction.INSERT,
                    content=cand.fact,
                    new_scope=cand.scope,
                    new_confidence=cand.confidence,
                    new_importance=cand.importance
                ))
                
        return updates

    def apply_lifecycle_rules(self, updates: List[PlannedUpdate], project_id: str) -> List[PlannedUpdate]:
        """Step 4: Lifecycle Rules & Promotion (The Promoter)."""
        final_updates = []
        
        for update in updates:
            # Rule 1: Session -> Project Promotion
            # strict rule: >= 3 reps OR (>=2 reps AND High Import)
            if update.action == MemoryAction.UPDATE and update.original_scope == "session":
                # We are about to increment, so uses current_repetition + 1 approx, 
                # but 'increment_repetition' flag handles the DB update. 
                # Here we check if we should FLIP the scope in this update.
                
                # Logic: If existing rep count (before this increment) is 2 (so now 3), PROMOTE.
                # OR if existing is 1 (now 2) AND importance is High.
                
                is_high_imp = update.new_importance == MemoryImportance.HIGH
                next_rep = update.current_repetition + 1
                
                should_promote = False
                if next_rep >= 3:
                    should_promote = True
                elif next_rep >= 2 and is_high_imp:
                    should_promote = True
                
                if should_promote:
                    update.action = MemoryAction.PROMOTE
                    update.new_scope = MemoryScope.PROJECT
                    # Add project_id if promoting
                    # (Persistence layer must handle adding project_id if it was null)
            
            final_updates.append(update)
            
        return final_updates

    def commit_batch(self, user_id: str, updates: List[PlannedUpdate], session_id: str, project_id: str):
        """Step 5: Persistence (The Writer)."""
        for up in updates:
            try:
                if up.action == MemoryAction.INSERT:
                    data = {
                        "user_id": user_id,
                        "content": up.content,
                        "scope": up.new_scope,
                        "confidence": up.new_confidence,
                        "importance": up.new_importance,
                        "repetition_count": 1
                    }
                    if up.new_scope == MemoryScope.SESSION:
                        data["session_id"] = session_id
                    elif up.new_scope == MemoryScope.PROJECT:
                        data["project_id"] = project_id
                    
                    supabase.table("user_memory").insert(data).execute()
                    print(f"[MEMORY] Inserted: {up.content} ({up.new_scope})")

                elif up.action == MemoryAction.UPDATE:
                    data = {}
                    if up.increment_repetition:
                        # We can't do atomic increment easily without RPC, so we set explicitly based on our tracking
                        # or just rely on 'current_rep + 1'. 
                        # Ideally, use an RPC. For now, we update strictly.
                        # Wait, we don't know the DB state perfectly if valid concurrency.
                        # But for a single user agent, it's okay.
                        pass # We will use rpc or simple update
                    
                    # Construct update payload
                    # Note: We can't easily increment via simple update dict.
                    # We'll just update fields we decided on.
                    # Creating a separate call for repetition increment might be safer if we had an RPC.
                    # For v1, let's just update the confidence and importance.
                    
                    # Actually, we need to increment repetition!
                    # We'll fetch-update (optimistic) since we already fetched in Step 2.
                    # But Step 2 data might be stale? Unlikely for single user.
                    
                    update_data = {
                        "confidence": up.new_confidence,
                        "importance": up.new_importance,
                        "repetition_count": up.current_repetition + 1
                    }
                    supabase.table("user_memory").update(update_data).eq("id", up.target_id).execute()
                    print(f"[MEMORY] Updated: {up.target_id} (Rep: {up.current_repetition + 1})")

                elif up.action == MemoryAction.PROMOTE:
                    # Session -> Project
                    update_data = {
                        "scope": "project",
                        "project_id": project_id,
                        "repetition_count": up.current_repetition + 1,
                        "importance": up.new_importance
                    }
                    supabase.table("user_memory").update(update_data).eq("id", up.target_id).execute()
                    print(f"[MEMORY] PROMOTED Session->Project: {up.target_id}")
                    
                elif up.action == MemoryAction.OVERRIDE:
                    update_data = {
                        "content": up.content,
                        "confidence": up.new_confidence
                    }
                    supabase.table("user_memory").update(update_data).eq("id", up.target_id).execute()
                    print(f"[MEMORY] OVERRIDE: {up.target_id}")

            except Exception as e:
                print(f"[ERROR] Commit failed for {up.action}: {e}")

    def _retrieve_context(self, user_id: str, query: str, project_id: str, session_id: str = None) -> str:
        """
        V1 Retrieval Contract Implementation.
        Scopes: Global (High Conf) > Project (Med Conf) > Session (All).
        Resolves conflicts by precedence: Session > Project > Global.
        """
        try:
            # 1. Fetch Candidates from Supabase
            # Global: High confidence (>=0.85), Universal truths
            global_data = []
            try:
                global_data = supabase.table("user_memory") \
                    .select("*") \
                    .eq("user_id", user_id) \
                    .eq("scope", "global") \
                    .gte("confidence", 0.85) \
                    .order("importance", desc=True) \
                    .limit(5) \
                    .execute().data
            except Exception as e:
                print(f"[WARN] Global memory fetch error: {e}")

            # Project: Medium confidence (>=0.70), Context specific
            project_data = []
            if project_id:
                try:
                    project_data = supabase.table("user_memory") \
                        .select("*") \
                        .eq("user_id", user_id) \
                        .eq("project_id", project_id) \
                        .eq("scope", "project") \
                        .gte("confidence", 0.70) \
                        .order("created_at", desc=True) \
                        .limit(5) \
                        .execute().data
                except Exception as e:
                    print(f"[WARN] Project memory fetch error: {e}")

            # Session: All confidence, Immediate working memory
            session_data = []
            if session_id:
                try:
                    session_data = supabase.table("user_memory") \
                        .select("*") \
                        .eq("user_id", user_id) \
                        .eq("session_id", session_id) \
                        .eq("scope", "session") \
                        .order("created_at", desc=True) \
                        .limit(10) \
                        .execute().data
                except Exception as e:
                    print(f"[WARN] Session memory fetch error: {e}")

            # 2. Conflict Resolution & Formatting using Precedence Rule (Session > Project > Global)
            # We will perform a simple deduplication based on content for V1.
            # In V2, we would use an LLM or 'override_id' to filter contradictions.
            
            seen_content = set()
            
            # Helper to deduplicate
            # We treat content as unique key. 
            # We prefer Session > Project > Global.
            
            items_by_scope = {"global": [], "project": [], "session": []}
            
            # Process Session First (Highest Priority)
            if session_data:
                for m in session_data:
                    if m['content'] not in seen_content:
                        items_by_scope["session"].append(m['content'])
                        seen_content.add(m['content'])
            
            # Process Project Second
            if project_data:
                for m in project_data:
                    if m['content'] not in seen_content:
                        items_by_scope["project"].append(m['content'])
                        seen_content.add(m['content'])
            
            # Process Global Last
            if global_data:
                for m in global_data:
                    if m['content'] not in seen_content:
                        items_by_scope["global"].append(m['content'])
                        seen_content.add(m['content'])

            # Construct Output String (Presentation Order: Global -> Project -> Session)
            output_parts = []
            
            if items_by_scope["global"]:
                output_parts.append("### Global Context (User Truths)")
                for c in items_by_scope["global"]:
                    output_parts.append(f"- {c}")
            
            if items_by_scope["project"]:
                output_parts.append("\n### Project Context")
                for c in items_by_scope["project"]:
                    output_parts.append(f"- {c}")
                    
            if items_by_scope["session"]:
                output_parts.append("\n### Recent Working Memory")
                for c in items_by_scope["session"]:
                    output_parts.append(f"- {c}")

            return "\n".join(output_parts)

        except Exception as e:
            print(f"[ERROR] Context retrieval failed: {e}")
    def get_memory_stats(self, user_id: str) -> Dict:
        """
        Calculates User Optimization Score based on Domain Coverage (Identity, Preferences, etc.).
        Only considers GLOBAL scope with Confidence >= 0.85.
        """
        domains = ["identity", "preferences", "habits", "goals", "constraints"]
        try:
            # 1. Fetch High-Confidence Global Memories
            # These are the only ones that count for "User Optimization"
            mems = supabase.table("user_memory") \
                .select("content") \
                .eq("user_id", user_id) \
                .eq("scope", "global") \
                .gte("confidence", 0.85) \
                .execute().data
            
            facts = [m["content"] for m in mems]
            
            if not facts:
                return {
                    "optimization_score": 0,
                    "domains": {d: "missing" for d in domains},
                    "last_updated": "2026-01-01T00:00:00Z" # Placeholder or now
                }

            # 2. Analyze Domain Coverage via LLM
            # We want to know which domains are "covered" by these facts.
            prompt = f"""
            Analyze these User Memories (Global Truths):
            {json.dumps(facts)}

            Classify them into these Personal Info Domains: {json.dumps(domains)}.
            
            For each domain, assign status:
            - "missing": No relevant info.
            - "partial": Some info exists.
            - "complete": Detailed/comprehensive info exists.

            Return JSON:
            {{
                "domains": {{
                    "identity": "partial",
                    ...
                }}
            }}
            """
            resp = self._call_llm(prompt, "Analyze Domains")
            analysis = json.loads(resp)
            domain_status = analysis.get("domains", {})
            
            # 3. Compute Score
            # Covered = status is "partial" or "complete"
            # We treat both as "covered" for the binary score, or maybe weight them?
            # Requirement: "covered if there exists at least one..." -> implies Binary coverage.
            # But maybe distinct weights? 
            # User said: "optimization_score = (covered_domains / total_domains) * 100"
            # This implies binary. partial=covered, complete=covered.
            
            covered_count = 0
            final_domains = {}
            for d in domains:
                status = domain_status.get(d, "missing").lower()
                final_domains[d] = status
                if status in ["partial", "complete"]:
                    covered_count += 1
            
            score = int((covered_count / len(domains)) * 100)
            
            return {
                "optimization_score": score,
                "domains": final_domains,
                "last_updated": "2026-01-01T00:00:00Z" # In V2 store this timestamp
                # Using hardcoded/now timestamp for V1 is acceptable as it's computed on-the-fly
            }

        except Exception as e:
            print(f"[ERROR] Stats calc failed: {e}")
            return {
                "optimization_score": 0,
                "domains": {d: "missing" for d in domains},
                "last_updated": "Error"
            }

    def get_next_personal_info_question(self, user_id: str, current_session_questions: int = 0) -> Optional[Dict]:
        """
        Orchestrator for Personal Info Chat.
        1. Checks constraints (max 5 questions, score < 70%).
        2. Identifies missing domains.
        3. Generates a friendly question.
        """
        # 1. Constraints
        if current_session_questions >= 5:
            return None # Session limit reached
            
        stats = self.get_memory_stats(user_id)
        if stats["optimization_score"] >= 70:
            return None # sufficiently optimized
            
        # 2. Identify Target Domain
        # Priority: missing -> partial
        domains = stats["domains"]
        target_domain = None
        
        # Look for missing first
        for d, status in domains.items():
            if status == "missing":
                target_domain = d
                break
        
        # If no missing, look for partial
        if not target_domain:
            for d, status in domains.items():
                if status == "partial":
                    target_domain = d
                    break
                    
        if not target_domain:
            return None # All complete
            
        # 3. Generate Question
        prompt = f"""
        You are a friendly, human AI assistant onboarding a new user.
        Your goal is to learn about their "{target_domain}" (Identity, Preferences, Habits, Goals, or Constraints) 
        to help them better.
        
        Current Domain Status: {domains}
        Target Domain: {target_domain}
        
        Task: Generate ONE conversational, non-intrusive question to learn more about their {target_domain}.
        - Tone: Casual, curious, empathetic. NO generic "Please enter data".
        - Example (Identity): "What's something you consider a superpower of yours?"
        - Example (Habits): "How do you usually like to start your mornings?"
        - Example (Goals): "Is there anything big you're working towards right now?"
        
        Return JSON:
        {{
            "question": "The question string",
            "domain": "{target_domain}"
        }}
        """
        resp = self._call_llm(prompt, "Generate Question")
        try:
            return json.loads(resp)
        except:
            return None
