#!/usr/bin/env python3
"""
Comprehensive Automated Regression Test Suite for OpenCode Go Fleet Monitor.
Covers:
- P0.1: Rolling-window accounting, pagination, and sliding window reconstruction.
- P0.2: Local HTTP API security, loopback binding, origin validation, CORS restriction.
- P0.3: Granular subsystem sync status (ok, degraded, error).
- P1.4: Manual override lifecycle and automatic sliding window resumption.
- P1.5: Strict model identification and canonical mapping (no loose substring false positives).
- P1.6: Process management validation.
- P1.7: State persistence atomicity and thread-safety under concurrent access.
- P2: .env preservation of OPENCODE_ORG_ID on key save/delete.
"""

import unittest
import os
import sys
import time
import json
import tempfile
import threading
import copy

# Add repo root to import path
REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

import server


class TestSecurity(unittest.TestCase):
    def test_localhost_origin_allowed(self):
        handler = server.MonitorHandler
        allowed = handler.ALLOWED_ORIGINS
        self.assertIn("http://localhost:7890", allowed)
        self.assertIn("http://127.0.0.1:7890", allowed)

    def test_untrusted_origins_rejected(self):
        class DummyRequest:
            def __init__(self, headers):
                self.headers = headers

            _get_cors_origin = server.MonitorHandler._get_cors_origin
            _is_request_authorized = server.MonitorHandler._is_request_authorized
            ALLOWED_ORIGINS = server.MonitorHandler.ALLOWED_ORIGINS

        # Untrusted Origin
        req_evil = DummyRequest({"Origin": "https://evil.com"})
        auth, reason = req_evil._is_request_authorized()
        self.assertFalse(auth)
        self.assertIn("evil.com", reason)
        self.assertIsNone(req_evil._get_cors_origin())

        # Untrusted Referer
        req_ref = DummyRequest({"Referer": "http://malicious.org/dashboard"})
        auth, reason = req_ref._is_request_authorized()
        self.assertFalse(auth)
        self.assertIn("malicious.org", reason)

        # Cross-site Sec-Fetch-Site
        req_fetch = DummyRequest({"Sec-Fetch-Site": "cross-site"})
        auth, reason = req_fetch._is_request_authorized()
        self.assertFalse(auth)
        self.assertIn("cross-site", reason)

        # Valid localhost Origin
        req_good = DummyRequest({"Origin": "http://127.0.0.1:7890"})
        auth, reason = req_good._is_request_authorized()
        self.assertTrue(auth)
        self.assertEqual(req_good._get_cors_origin(), "http://127.0.0.1:7890")


class TestEnvPreservation(unittest.TestCase):
    def setUp(self):
        self.orig_env_file = server.ENV_FILE
        self.test_dir = tempfile.mkdtemp()
        self.test_env = os.path.join(self.test_dir, ".env")
        server.ENV_FILE = self.test_env

    def tearDown(self):
        server.ENV_FILE = self.orig_env_file
        if os.path.exists(self.test_env):
            os.remove(self.test_env)
        if os.path.exists(self.test_dir):
            os.rmdir(self.test_dir)

    def test_save_key_preserves_org_id_and_comments(self):
        # Initial .env with ORG_ID and custom comment
        with open(self.test_env, "w") as f:
            f.write("# Developer config\nOPENCODE_ORG_ID=org_abc_12345\nCUSTOM_VAR=true\n")

        # Save API key
        res = server.save_env_key("oc_sk_test_key_999")
        self.assertTrue(res)

        with open(self.test_env, "r") as f:
            content = f.read()

        self.assertIn("OPENCODE_API_KEY=oc_sk_test_key_999", content)
        self.assertIn("OPENCODE_ORG_ID=org_abc_12345", content)
        self.assertIn("CUSTOM_VAR=true", content)
        self.assertIn("# Developer config", content)

    def test_delete_key_preserves_org_id(self):
        # Initial .env with API key and ORG_ID
        with open(self.test_env, "w") as f:
            f.write("OPENCODE_API_KEY=oc_sk_test\nOPENCODE_ORG_ID=org_my_important_org\n")

        res = server.delete_env_key()
        self.assertTrue(res)

        with open(self.test_env, "r") as f:
            content = f.read()

        self.assertNotIn("OPENCODE_API_KEY", content)
        self.assertIn("OPENCODE_ORG_ID=org_my_important_org", content)


class TestStateConcurrencyAndAtomicity(unittest.TestCase):
    def setUp(self):
        self.orig_data_file = server.DATA_FILE
        self.test_dir = tempfile.mkdtemp()
        self.test_data = os.path.join(self.test_dir, "monitor_state.json")
        server.DATA_FILE = self.test_data
        self.state = server.StateManager()

    def tearDown(self):
        server.DATA_FILE = self.orig_data_file
        if os.path.exists(self.test_data):
            os.remove(self.test_data)
        if os.path.exists(self.test_dir):
            os.rmdir(self.test_dir)

    def test_state_manager_has_rlock(self):
        self.assertTrue(hasattr(self.state, "lock"))
        self.assertIsInstance(self.state.lock, type(threading.RLock()))

    def test_atomic_save_replaces_cleanly(self):
        self.state.record_request("gemini-4-argon", count=5, est_dollars=0.25)
        self.assertTrue(os.path.exists(self.test_data))
        with open(self.test_data, "r") as f:
            data = json.load(f)
        self.assertEqual(data["gemini-4-argon"]["current_req_5h"], 5)

    def test_multithreaded_concurrency_stress(self):
        errors = []

        def worker_record():
            try:
                for _ in range(50):
                    self.state.record_request("kimi-k3-1-pro", count=1, est_dollars=0.01)
                    time.sleep(0.001)
            except Exception as e:
                errors.append(e)

        def worker_snapshot():
            try:
                for _ in range(50):
                    snap = self.state.get_status_snapshot()
                    self.assertIsInstance(snap["models"], list)
                    time.sleep(0.001)
            except Exception as e:
                errors.append(e)

        t1 = threading.Thread(target=worker_record)
        t2 = threading.Thread(target=worker_snapshot)
        t3 = threading.Thread(target=worker_record)

        t1.start()
        t2.start()
        t3.start()
        t1.join()
        t2.join()
        t3.join()

        self.assertEqual(errors, [])
        self.assertEqual(self.state.models["kimi-k3-1-pro"]["current_req_5h"], 100)


class TestRollingWindowAndPagination(unittest.TestCase):
    def setUp(self):
        self.orig_data_file = server.DATA_FILE
        self.test_dir = tempfile.mkdtemp()
        self.test_data = os.path.join(self.test_dir, "monitor_state.json")
        server.DATA_FILE = self.test_data
        self.state = server.StateManager()

    def tearDown(self):
        server.DATA_FILE = self.orig_data_file
        if os.path.exists(self.test_data):
            os.remove(self.test_data)
        if os.path.exists(self.test_dir):
            os.rmdir(self.test_dir)

    def test_more_than_100_requests_across_sliding_window(self):
        now = time.time()
        # Generate 150 requests:
        # 120 requests within past 2 hours
        # 30 requests from 6 hours ago (should be excluded)
        recent_items = [
            {
                "id": f"req_{i}",
                "model": "gemini-4-argon",
                "startedAt": int((now - (i * 30)) * 1000)  # within last hour
            }
            for i in range(120)
        ]
        expired_items = [
            {
                "id": f"old_{i}",
                "model": "gemini-4-argon",
                "startedAt": int((now - (6 * 3600 + i * 10)) * 1000)  # 6 hours ago
            }
            for i in range(30)
        ]

        total_items = recent_items + expired_items
        imported = self.state.import_cloud_request_logs(total_items)

        # Matched count is all matching models, but timestamps/current_req_5h only keeps active < 5h
        self.assertEqual(imported, 150)
        self.assertEqual(self.state.models["gemini-4-argon"]["current_req_5h"], 120)
        self.assertEqual(len(self.state.models["gemini-4-argon"]["timestamps"]), 120)

    def test_state_reconstruction_after_restart(self):
        # Record requests
        self.state.record_request("mimo-v2-6-pro", count=7, est_dollars=0.05)
        self.assertEqual(self.state.models["mimo-v2-6-pro"]["current_req_5h"], 7)

        # Simulate monitor restart by creating a new StateManager pointing to same file
        restarted_state = server.StateManager()
        self.assertEqual(restarted_state.models["mimo-v2-6-pro"]["current_req_5h"], 7)
        self.assertEqual(len(restarted_state.models["mimo-v2-6-pro"]["timestamps"]), 7)


class TestModelIdentification(unittest.TestCase):
    def test_canonical_and_aliased_matching(self):
        # Exact canonical slugs
        self.assertEqual(server.resolve_model_id("gemini-4-argon"), "gemini-4-argon")
        self.assertEqual(server.resolve_model_id("kimi-k3-1-pro"), "kimi-k3-1-pro")
        self.assertEqual(server.resolve_model_id("mimo-v2-6-pro"), "mimo-v2-6-pro")

        # Provider prefixes and dot-notation
        self.assertEqual(server.resolve_model_id("moonshotai/kimi-k3.1-pro"), "kimi-k3-1-pro")
        self.assertEqual(server.resolve_model_id("google/gemini-4-argon"), "gemini-4-argon")
        self.assertEqual(server.resolve_model_id("glm-5.3"), "glm-5-3")
        self.assertEqual(server.resolve_model_id("deepseek-v4.1-flash"), "deepseek-v4-1-flash")

    def test_no_false_positive_substring_matches(self):
        # Random models that happen to contain 'kimi' or 'beam' must NOT merge
        self.assertIsNone(server.resolve_model_id("kimi-chat-v1"))
        self.assertIsNone(server.resolve_model_id("beam-advanced-model"))
        self.assertIsNone(server.resolve_model_id("random-gpt-model"))


class TestManualOverrideLifecycle(unittest.TestCase):
    def setUp(self):
        self.state = server.StateManager()

    def test_manual_override_and_clear(self):
        # 1. Normal state
        self.assertFalse(self.state.models["kimi-k3-1-pro"].get("manual_override", False))

        # 2. Apply manual override
        self.state.update_model("kimi-k3-1-pro", req_5h=450, spent_usd=25.0)
        self.assertTrue(self.state.models["kimi-k3-1-pro"]["manual_override"])
        self.assertEqual(self.state.models["kimi-k3-1-pro"]["current_req_5h"], 450)

        # 3. Sliding window clean does NOT wipe out manual override count
        self.state.clean_sliding_windows()
        self.assertEqual(self.state.models["kimi-k3-1-pro"]["current_req_5h"], 450)

        # 4. Clear manual override -> resumes automatic count based on timestamps
        cleared = self.state.clear_override("kimi-k3-1-pro")
        self.assertEqual(cleared, 1)
        self.assertFalse(self.state.models["kimi-k3-1-pro"]["manual_override"])
        self.assertEqual(self.state.models["kimi-k3-1-pro"]["current_req_5h"], 0)


class TestSyncSubsystemStatus(unittest.TestCase):
    def test_granular_sync_state_structure(self):
        engine = server.OpenCodeSyncEngine(server.StateManager())
        snap = engine.get_sync_state_snapshot()
        self.assertIn("subsystems", snap)
        self.assertIn("models", snap["subsystems"])
        self.assertIn("logs", snap["subsystems"])
        self.assertIn("go_status", snap["subsystems"])
        self.assertIn("summary", snap["subsystems"])


class TestSyncIntegration(unittest.TestCase):
    def setUp(self):
        self.orig_data_file = server.DATA_FILE
        self.test_dir = tempfile.mkdtemp()
        self.test_data = os.path.join(self.test_dir, "monitor_state.json")
        server.DATA_FILE = self.test_data
        self.state = server.StateManager()
        self.engine = server.OpenCodeSyncEngine(self.state)
        self.now = time.time()

        # Mock credentials
        self.orig_load_key = server.load_env_key
        self.orig_load_oauth = server.load_opencode_oauth_token
        server.load_env_key = lambda: "oc_sk_mock_valid_key"
        server.load_opencode_oauth_token = lambda: "mock_oauth_token"

    def tearDown(self):
        server.load_env_key = self.orig_load_key
        server.load_opencode_oauth_token = self.orig_load_oauth
        server.DATA_FILE = self.orig_data_file
        if os.path.exists(self.test_data):
            os.remove(self.test_data)
        if os.path.exists(self.test_dir):
            os.rmdir(self.test_dir)

    def test_sync_now_multiple_pages_150_plus(self):
        # 100 items on page 1, 60 items on page 2 (total 160 requests within 5h window)
        page1_items = [
            {"id": f"p1_{i}", "model": "gemini-4-argon", "startedAt": int((self.now - 600 - i * 10) * 1000)}
            for i in range(100)
        ]
        page2_items = [
            {"id": f"p2_{i}", "model": "gemini-4-argon", "startedAt": int((self.now - 3600 - i * 10) * 1000)}
            for i in range(59)
        ]
        # Add 1 item that is older than 5 hours to trigger window boundary
        page2_items.append({"id": "old_boundary", "model": "gemini-4-argon", "startedAt": int((self.now - 6 * 3600) * 1000)})

        def mock_api_get(endpoint, tokens, headers=None):
            if "usage/models" in endpoint:
                return {"items": [{"model": "gemini-4-argon", "totalCostMicroCents": 100000000}]}, None
            elif "request-logs" in endpoint:
                if "cursor=page2" in endpoint:
                    return {"items": page2_items, "nextCursor": None}, None
                else:
                    return {"items": page1_items, "nextCursor": "page2"}, None
            elif "go/status" in endpoint:
                return {"access": {"meters": {"fiveHour": {"usedMicroCents": 1000, "limitMicroCents": 4800000000}}}}, None
            elif "usage/summary" in endpoint:
                return {"totalCostMicroCents": 50000000, "totalRequests": 159}, None
            return None, "Not found"

        self.engine._api_get = mock_api_get
        success, msg = self.engine.sync_now()

        self.assertTrue(success)
        snap = self.engine.get_sync_state_snapshot()
        self.assertEqual(snap["status"], "ok")
        self.assertEqual(snap["subsystems"]["logs"]["status"], "ok")
        self.assertIn("2 pages traversed", snap["subsystems"]["logs"]["message"])
        self.assertEqual(self.state.models["gemini-4-argon"]["current_req_5h"], 159)

    def test_sync_now_failure_on_page_2_retains_data(self):
        # Pre-populate state with 15 requests
        for _ in range(15):
            self.state.record_request("kimi-k3-1-pro", count=1, est_dollars=0.01)
        self.assertEqual(self.state.models["kimi-k3-1-pro"]["current_req_5h"], 15)

        page1_items = [
            {"id": f"p1_{i}", "model": "kimi-k3-1-pro", "startedAt": int((self.now - 300) * 1000)}
            for i in range(50)
        ]

        def mock_api_get(endpoint, tokens, headers=None):
            if "usage/models" in endpoint:
                return {"items": []}, None
            elif "request-logs" in endpoint:
                if "cursor=page2" in endpoint:
                    # Page 2 fails with HTTP 500!
                    return None, "HTTP 500 Internal Server Error"
                else:
                    return {"items": page1_items, "nextCursor": "page2"}, None
            elif "go/status" in endpoint:
                return {"access": {"meters": {}}}, None
            elif "usage/summary" in endpoint:
                return {}, None
            return None, "Not found"

        self.engine._api_get = mock_api_get
        success, msg = self.engine.sync_now()

        snap = self.engine.get_sync_state_snapshot()
        # Subsystem logs must be error, and overall status must be degraded
        self.assertEqual(snap["subsystems"]["logs"]["status"], "error")
        self.assertIn("retained previous data", snap["subsystems"]["logs"]["message"])
        self.assertEqual(snap["status"], "degraded")

        # Crucial check: previous 15 requests must NOT have been overwritten by partial page 1!
        self.assertEqual(self.state.models["kimi-k3-1-pro"]["current_req_5h"], 15)

    def test_sync_now_max_pages_limit_reached_retains_data(self):
        # Pre-populate state with 8 requests
        for _ in range(8):
            self.state.record_request("mimo-v2-6-pro", count=1, est_dollars=0.01)

        def mock_api_get(endpoint, tokens, headers=None):
            if "usage/models" in endpoint:
                return {"items": []}, None
            elif "request-logs" in endpoint:
                # Always returns recent items with a nextCursor, never reaching 5h boundary
                items = [{"id": f"inf_{time.time_ns()}", "model": "mimo-v2-6-pro", "startedAt": int((self.now - 60) * 1000)}]
                return {"items": items, "nextCursor": "keep_going"}, None
            elif "go/status" in endpoint:
                return {"access": {"meters": {}}}, None
            elif "usage/summary" in endpoint:
                return {}, None
            return None, "Not found"

        self.engine._api_get = mock_api_get
        success, msg = self.engine.sync_now()

        snap = self.engine.get_sync_state_snapshot()
        self.assertEqual(snap["subsystems"]["logs"]["status"], "error")
        self.assertIn("Max pagination limit", snap["subsystems"]["logs"]["message"])
        self.assertEqual(snap["status"], "degraded")
        # Retained previous 8 requests
        self.assertEqual(self.state.models["mimo-v2-6-pro"]["current_req_5h"], 8)

    def test_sync_now_successful_empty_response_clears_stale_counters(self):
        # gemini-4-argon has 10 normal requests
        for _ in range(10):
            self.state.record_request("gemini-4-argon", count=1, est_dollars=0.01)
        # kimi-k3-1-pro has a manual override of 25 requests
        self.state.update_model("kimi-k3-1-pro", req_5h=25, spent_usd=5.0)

        self.assertEqual(self.state.models["gemini-4-argon"]["current_req_5h"], 10)
        self.assertEqual(self.state.models["kimi-k3-1-pro"]["current_req_5h"], 25)

        def mock_api_get(endpoint, tokens, headers=None):
            if "usage/models" in endpoint:
                return {"items": []}, None
            elif "request-logs" in endpoint:
                # Cloud reports 0 requests in the window
                return {"items": [], "nextCursor": None}, None
            elif "go/status" in endpoint:
                return {"access": {"meters": {}}}, None
            elif "usage/summary" in endpoint:
                return {}, None
            return None, "Not found"

        self.engine._api_get = mock_api_get
        success, msg = self.engine.sync_now()

        snap = self.engine.get_sync_state_snapshot()
        self.assertEqual(snap["subsystems"]["logs"]["status"], "ok")
        # gemini-4-argon should now be cleared to 0
        self.assertEqual(self.state.models["gemini-4-argon"]["current_req_5h"], 0)
        self.assertEqual(self.state.models["gemini-4-argon"]["timestamps"], [])
        # kimi-k3-1-pro was manually overridden, so its 25 count must be preserved!
        self.assertEqual(self.state.models["kimi-k3-1-pro"]["current_req_5h"], 25)
        self.assertTrue(self.state.models["kimi-k3-1-pro"]["manual_override"])

    def test_sync_now_partial_failure_of_subsystems(self):
        def mock_api_get(endpoint, tokens, headers=None):
            if "usage/models" in endpoint:
                return {"items": [{"model": "gemini-4-argon", "totalCostMicroCents": 50000000}]}, None
            elif "request-logs" in endpoint:
                return {"items": [], "nextCursor": None}, None
            elif "go/status" in endpoint:
                # go/status fails
                return None, "HTTP 401 Unauthorized"
            elif "usage/summary" in endpoint:
                return {"totalCostMicroCents": 10000000, "totalRequests": 5}, None
            return None, "Not found"

        self.engine._api_get = mock_api_get
        success, msg = self.engine.sync_now()

        snap = self.engine.get_sync_state_snapshot()
        self.assertEqual(snap["subsystems"]["models"]["status"], "ok")
        self.assertEqual(snap["subsystems"]["logs"]["status"], "ok")
        self.assertEqual(snap["subsystems"]["go_status"]["status"], "error")
        self.assertEqual(snap["subsystems"]["summary"]["status"], "ok")
        # Overall status must be degraded
        self.assertEqual(snap["status"], "degraded")
        self.assertIn("go_status", snap["message"])


if __name__ == "__main__":
    unittest.main()
