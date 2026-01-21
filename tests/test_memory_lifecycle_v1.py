import sys
import os
import unittest
from unittest.mock import MagicMock, patch
import json

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# --- 1. Universal Mocking of Dependencies ---
# We must mock 'supabase' and 'core.supabase_utils' BEFORE importing memory_manager
mock_supabase_client = MagicMock()
mock_utils = MagicMock()
mock_utils.supabase = mock_supabase_client
sys.modules["supabase"] = MagicMock()
sys.modules["core.supabase_utils"] = mock_utils

from core.memory_manager import memory_manager, MemoryScope, MemoryImportance, MemoryCandidate, PlannedUpdate, MemoryAction

class TestMemoryLifecycleV1(unittest.TestCase):
    
    def setUp(self):
        # Reset mocks before each test
        mock_supabase_client.reset_mock()
        # Mock LLM to avoid real calls
        self.mock_llm_patcher = patch.object(memory_manager, '_call_llm')
        self.mock_llm = self.mock_llm_patcher.start()

    def tearDown(self):
        self.mock_llm_patcher.stop()

    # --- CP2: Extraction ---
    def test_extract_candidates(self):
        print("\nTesting CP2: Extraction...")
        # Setup Mock LLM response
        self.mock_llm.return_value = json.dumps({
            "candidates": [{
                "fact": "User likes Python",
                "importance": "high",
                "scope": "project",
                "confidence": 0.9,
                "keywords": ["python", "language"]
            }]
        })
        
        candidates = memory_manager.extract_candidates("I really like Python for this project", "sess_1", "proj_1")
        
        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0].fact, "User likes Python")
        self.assertEqual(candidates[0].scope, MemoryScope.PROJECT)
        self.assertEqual(candidates[0].importance, MemoryImportance.HIGH)

    # --- CP3: Analysis (Tiered Match) ---
    def test_determine_updates_exact_match(self):
        print("\nTesting CP3: Analysis (Exact Match)...")
        candidate = MemoryCandidate(fact="Sky is blue", importance=MemoryImportance.LOW, scope=MemoryScope.SESSION, confidence=0.8, keywords=[])
        
        # Mock LLM decision
        self.mock_llm.return_value = json.dumps({
            "action": "EXACT_MATCH",
            "target_id": "existing_123"
        })
        
        related = {"potential_matches": [{"id": "existing_123", "repetition_count": 5}], "cross_project_matches": []}
        updates = memory_manager.determine_memory_updates([candidate], related)
        
        self.assertEqual(len(updates), 1)
        up = updates[0]
        self.assertEqual(up.action, MemoryAction.UPDATE)
        self.assertEqual(up.target_id, "existing_123")
        self.assertTrue(up.increment_repetition)

    # --- CP3: Analysis (Cross-Project Promotion) ---
    def test_determine_updates_cross_project(self):
        print("\nTesting CP3: Analysis (Cross-Project Pormotion)...")
        candidate = MemoryCandidate(fact="Universal Truth", importance=MemoryImportance.HIGH, scope=MemoryScope.PROJECT, confidence=0.9, keywords=[])
        
        # Mock LLM decision
        self.mock_llm.return_value = json.dumps({
            "action": "PROMOTE_TO_GLOBAL"
        })
        
        # related has no potential matches, but has cross project matches (implied by LLM decision logic mocking)
        related = {"potential_matches": [], "cross_project_matches": [{"id": "other_proj_id"}]}
        updates = memory_manager.determine_memory_updates([candidate], related)
        
        self.assertEqual(len(updates), 1)
        self.assertEqual(updates[0].action, MemoryAction.INSERT)
        self.assertEqual(updates[0].new_scope, MemoryScope.GLOBAL) # Should insert as Global

    # --- CP3: Lifecycle Rules (Session -> Project Promotion) ---
    def test_apply_promotion_rules(self):
        print("\nTesting CP3: Promotion Rules...")
        # Case 1: Repetition 2 -> 3 (Standard Promotion)
        up1 = PlannedUpdate(
             action=MemoryAction.UPDATE,
             target_id="id_1",
             original_scope="session",
             current_repetition=2,
             new_importance=MemoryImportance.MEDIUM,
             increment_repetition=True
        )
        # Case 2: Repetition 1 -> 2 with High Importance (Fast-Track Promotion)
        up2 = PlannedUpdate(
             action=MemoryAction.UPDATE,
             target_id="id_2",
             original_scope="session",
             current_repetition=1,
             new_importance=MemoryImportance.HIGH,
             increment_repetition=True
        )
        
        processed = memory_manager.apply_lifecycle_rules([up1, up2], "proj_1")
        
        self.assertEqual(processed[0].action, MemoryAction.PROMOTE)
        self.assertEqual(processed[0].new_scope, MemoryScope.PROJECT)
        
        self.assertEqual(processed[1].action, MemoryAction.PROMOTE)
        self.assertEqual(processed[1].new_scope, MemoryScope.PROJECT)

    # --- CP5: Retrieval Contract ---
    def test_retrieval_precedence(self):
        print("\nTesting CP5: Retrieval Precedence...")
        # Mock DB responses chain
        mock_query = MagicMock()
        mock_supabase_client.table.return_value = mock_query
        mock_query.select.return_value = mock_query
        mock_query.eq.return_value = mock_query
        mock_query.gte.return_value = mock_query
        mock_query.order.return_value = mock_query
        mock_query.limit.return_value = mock_query
        
        # Mock Data
        global_mems = MagicMock()
        # Add a unique item "Earth is round" to ensure Global section renders
        global_mems.data = [{"content": "I like cats", "scope": "global"}, {"content": "Earth is round", "scope": "global"}]
        
        project_mems = MagicMock()
        project_mems.data = [{"content": "I like dogs", "scope": "project"}] 
        
        session_mems = MagicMock()
        session_mems.data = [{"content": "I like cats", "scope": "session"}] # Override of one global item
        
        # Order of execution in code: Global -> Project -> Session
        mock_query.execute.side_effect = [global_mems, project_mems, session_mems]
        
        ctx = memory_manager._retrieve_context("user", "query", "proj", "sess")
        
        # Verify Output
        # Should have "Global Context", "Project Context", "Recent Working Memory" headers
        self.assertIn("### Global Context", ctx)
        self.assertIn("### Project Context", ctx)
        self.assertIn("### Recent Working Memory", ctx)
        
        # Verify Deduplication favoring Session?
        # Our logic: Session adds "I like cats". 
        # Project adds "I like dogs".
        # Global tries to add "I like cats" -> seen already (in Session) -> Skipped?
        # Let's check implementation detail:
        # Session processed first. seen={"I like cats"}.
        # Global processed last. "I like cats" in seen? Yes. Skipped.
        # So "I like cats" appears in Session section, NOT Global section.
        
        # Let's verify "I like cats" allows valid_items['session'] list logic
        # It should appear under ### Recent Working Memory
        # And NOT under ### Global Context
        
        # We can simulate parsing the string or strict assertions
        # "I like cats" is in Session and Global. Session wins. Global is skipped (deduplicated).
        # So it should appear ONCE.
        self.assertEqual(ctx.count("I like cats"), 1, "Deduplication failed: 'I like cats' appeared multiple times")
        
        # Verify Global Context renders for the unique item
        self.assertIn("### Global Context", ctx)
        self.assertIn("Earth is round", ctx)
        
        # Verify Session Context contains the overridding item
        self.assertIn("### Recent Working Memory", ctx)

if __name__ == '__main__':
    unittest.main()
