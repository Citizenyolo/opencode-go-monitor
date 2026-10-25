#!/usr/bin/env python3
"""
OpenCode GO & OpenAI v6 Fleet Monitor
Lightweight, real-time HTTP Dashboard for tracking 5-hour rolling quotas and monthly dollar allowances.
Zero external dependencies (pure standard library).
Includes OpenCode Console API (Option 3) Real-Time Synchronization.
"""

import http.server
import socketserver
import json
import time
import os
import urllib.parse
import urllib.request
import urllib.error
import threading
import copy
import re
import bisect
from datetime import datetime

PORT = 7890
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_FILE = os.path.join(BASE_DIR, "monitor_state.json")
ENV_FILE = os.path.join(BASE_DIR, ".env")

# Model Configurations for both OpenCode Go ($10) and OpenCode Go Plus ($40)
TIER_MODELS_CONFIG = {
    "go": {
        "kimi-k3-1-pro": {"limit_5h": 147, "limit_usd": 15.0, "is_unlimited_5h": False, "is_unlimited_usd": False, "is_ltd": False, "bonus": 1, "prov": "Moonshot (OpenCode Go)"},
        "gemini-4-argon": {"limit_5h": 440, "limit_usd": 30.0, "is_unlimited_5h": False, "is_unlimited_usd": False, "is_ltd": False, "bonus": 1, "prov": "Google (OpenCode Go)"},
        "glm-5-3": {"limit_5h": 220, "limit_usd": 15.0, "is_unlimited_5h": False, "is_unlimited_usd": False, "is_ltd": False, "bonus": 1, "prov": "Z.AI (OpenCode Go)"},
        "mimo-v2-6-pro": {"limit_5h": 3250, "limit_usd": 15.0, "is_unlimited_5h": False, "is_unlimited_usd": False, "is_ltd": False, "bonus": 1, "prov": "Xiaomi (OpenCode Go)"},
        "deepseek-v4-pro": {"limit_5h": 1050, "limit_usd": 15.0, "is_unlimited_5h": False, "is_unlimited_usd": False, "is_ltd": False, "bonus": 1, "prov": "DeepSeek (OpenCode Go)"},
        "deepseek-v4-1-flash": {"limit_5h": 34670, "limit_usd": 80.0, "is_unlimited_5h": False, "is_unlimited_usd": False, "is_ltd": False, "bonus": 1, "prov": "DeepSeek (OpenCode Go)"},
        "claude-haiku-5-5": {"limit_5h": 3850, "limit_usd": 15.0, "is_unlimited_5h": False, "is_unlimited_usd": False, "is_ltd": False, "bonus": 1, "prov": "Anthropic (OpenCode Go)"},
        "mimo-v2-6-flash": {"limit_5h": 30100, "limit_usd": 60.0, "is_unlimited_5h": False, "is_unlimited_usd": False, "is_ltd": False, "bonus": 1, "prov": "Xiaomi (OpenCode Go)"},
        "beam-free": {"limit_5h": 0, "limit_usd": 0.0, "is_unlimited_5h": True, "is_unlimited_usd": True, "is_ltd": True, "bonus": 1, "prov": "Reflection AI (OpenCode Go)"}
    },
    "go-plus": {
        "kimi-k3-1-pro": {"limit_5h": 588, "limit_usd": 60.0, "is_unlimited_5h": False, "is_unlimited_usd": False, "is_ltd": False, "bonus": 1, "prov": "Moonshot (OpenCode Go Plus)"},
        "gemini-4-argon": {"limit_5h": 1760, "limit_usd": 120.0, "is_unlimited_5h": False, "is_unlimited_usd": False, "is_ltd": False, "bonus": 1, "prov": "Google (OpenCode Go Plus)"},
        "glm-5-3": {"limit_5h": 1760, "limit_usd": 120.0, "is_unlimited_5h": False, "is_unlimited_usd": False, "is_ltd": False, "bonus": 1, "prov": "Z.AI (OpenCode Go Plus)"},
        "mimo-v2-6-pro": {"limit_5h": 13000, "limit_usd": 60.0, "is_unlimited_5h": False, "is_unlimited_usd": False, "is_ltd": False, "bonus": 1, "prov": "Xiaomi (OpenCode Go Plus)"},
        "deepseek-v4-pro": {"limit_5h": 4200, "limit_usd": 60.0, "is_unlimited_5h": False, "is_unlimited_usd": False, "is_ltd": False, "bonus": 1, "prov": "DeepSeek (OpenCode Go Plus)"},
        "deepseek-v4-1-flash": {"limit_5h": 69330, "limit_usd": 160.0, "is_unlimited_5h": False, "is_unlimited_usd": False, "is_ltd": False, "bonus": 1, "prov": "DeepSeek (OpenCode Go Plus)"},
        "claude-haiku-5-5": {"limit_5h": 15380, "limit_usd": 60.0, "is_unlimited_5h": False, "is_unlimited_usd": False, "is_ltd": False, "bonus": 1, "prov": "Anthropic (OpenCode Go Plus)"},
        "mimo-v2-6-flash": {"limit_5h": 60200, "limit_usd": 120.0, "is_unlimited_5h": False, "is_unlimited_usd": False, "is_ltd": False, "bonus": 1, "prov": "Xiaomi (OpenCode Go Plus)"},
        "beam-free": {"limit_5h": 0, "limit_usd": 0.0, "is_unlimited_5h": True, "is_unlimited_usd": True, "is_ltd": True, "bonus": 1, "prov": "Reflection AI (OpenCode Go Plus)"}
    }
}

# Clean, accurate v6 Model Specifications in requested 3x3 layout
DEFAULT_MODELS = {
    "kimi-k3-1-pro": {
        "id": "kimi-k3-1-pro",
        "name": "Kimi K3.1 Pro",
        "role": "🧠 SOTA Reasoning & Kódarchitektúra",
        "category": "Reasoning Fallback",
        "categories": ["Reasoning Fallback", "Deep Debugging"],
        "provider": "Moonshot (OpenCode Go Plus)",
        "limit_5h_req": 588,
        "is_unlimited_5h": False,
        "limit_monthly_usd": 60.0,
        "is_unlimited_usd": False,
        "is_limited_time": False,
        "promo_bonus": 1,
        "current_req_5h": 0,
        "current_spent_usd": 0.0,
        "escalation_target": "Gemini 4 Argon",
        "unit_desc": "requests",
        "timestamps": []
    },
    "gemini-4-argon": {
        "id": "gemini-4-argon",
        "name": "Gemini 4 Argon",
        "role": "🐛 Nehéz Debugging & Root Cause",
        "category": "Deep Debugging",
        "categories": ["Deep Debugging"],
        "provider": "Google (OpenCode Go Plus)",
        "limit_5h_req": 1760,
        "is_unlimited_5h": False,
        "limit_monthly_usd": 120.0,
        "is_unlimited_usd": False,
        "is_limited_time": False,
        "promo_bonus": 1,
        "current_req_5h": 0,
        "current_spent_usd": 0.0,
        "escalation_target": "GLM-5.3",
        "unit_desc": "requests",
        "timestamps": []
    },
    "glm-5-3": {
        "id": "glm-5-3",
        "name": "GLM-5.3",
        "role": "🧠 / 🛠️ Deep Reasoning Fallback",
        "category": "Reasoning Fallback",
        "categories": ["Reasoning Fallback"],
        "provider": "Z.AI (OpenCode Go Plus)",
        "limit_5h_req": 1760,
        "is_unlimited_5h": False,
        "limit_monthly_usd": 120.0,
        "is_unlimited_usd": False,
        "is_limited_time": False,
        "promo_bonus": 1,
        "current_req_5h": 0,
        "current_spent_usd": 0.0,
        "escalation_target": "MiMo-V2.6-Pro",
        "unit_desc": "requests",
        "timestamps": []
    },
    "mimo-v2-6-pro": {
        "id": "mimo-v2-6-pro",
        "name": "MiMo-V2.6-Pro",
        "role": "⚙️ Napi Coding Munkaerő (OpenCode)",
        "category": "Agentic Coding",
        "provider": "Xiaomi (OpenCode Go Plus)",
        "limit_5h_req": 13000,
        "is_unlimited_5h": False,
        "limit_monthly_usd": 60.0,
        "is_unlimited_usd": False,
        "is_limited_time": False,
        "promo_bonus": 1,
        "current_req_5h": 0,
        "current_spent_usd": 0.0,
        "escalation_target": "DeepSeek V4 Pro",
        "unit_desc": "requests",
        "timestamps": []
    },
    "deepseek-v4-pro": {
        "id": "deepseek-v4-pro",
        "name": "DeepSeek V4 Pro",
        "role": "🛠️ Komplex Funkciófejlesztés",
        "category": "Implementation",
        "provider": "DeepSeek (OpenCode Go Plus)",
        "limit_5h_req": 4200,
        "is_unlimited_5h": False,
        "limit_monthly_usd": 60.0,
        "is_unlimited_usd": False,
        "is_limited_time": False,
        "promo_bonus": 1,
        "current_req_5h": 0,
        "current_spent_usd": 0.0,
        "escalation_target": "DeepSeek V4.1 Flash",
        "unit_desc": "requests",
        "timestamps": []
    },
    "deepseek-v4-1-flash": {
        "id": "deepseek-v4-1-flash",
        "name": "DeepSeek V4.1 Flash",
        "role": "⚙️ / ⚡ Gyors Kódolási & Workflow Tartalék",
        "category": "High-Throughput",
        "provider": "DeepSeek (OpenCode Go Plus)",
        "limit_5h_req": 69330,
        "is_unlimited_5h": False,
        "limit_monthly_usd": 160.0,
        "is_unlimited_usd": False,
        "is_limited_time": False,
        "promo_bonus": 1,
        "current_req_5h": 0,
        "current_spent_usd": 0.0,
        "escalation_target": "Claude Haiku 5.5",
        "unit_desc": "requests",
        "timestamps": []
    },
    "claude-haiku-5-5": {
        "id": "claude-haiku-5-5",
        "name": "Claude Haiku 5.5",
        "role": "⚡ Gyors Subagent & Részfeladatok",
        "category": "Fast Subagent",
        "provider": "Anthropic (OpenCode Go Plus)",
        "limit_5h_req": 15380,
        "is_unlimited_5h": False,
        "limit_monthly_usd": 60.0,
        "is_unlimited_usd": False,
        "is_limited_time": False,
        "promo_bonus": 1,
        "current_req_5h": 0,
        "current_spent_usd": 0.0,
        "escalation_target": "MiMo-V2.6-Flash",
        "unit_desc": "requests",
        "timestamps": []
    },
    "mimo-v2-6-flash": {
        "id": "mimo-v2-6-flash",
        "name": "MiMo-V2.6-Flash",
        "role": "♾️ Nagy Volumenű Automatizálás",
        "category": "High-Throughput",
        "provider": "Xiaomi (OpenCode Go Plus)",
        "limit_5h_req": 60200,
        "is_unlimited_5h": False,
        "limit_monthly_usd": 120.0,
        "is_unlimited_usd": False,
        "is_limited_time": False,
        "promo_bonus": 1,
        "current_req_5h": 0,
        "current_spent_usd": 0.0,
        "escalation_target": "BEAM Free",
        "unit_desc": "requests",
        "timestamps": []
    },
    "beam-free": {
        "id": "beam-free",
        "name": "BEAM Free",
        "role": "🔎 Web Research & Extraction Subagent",
        "category": "Research & Extraction",
        "provider": "Reflection AI (OpenCode Go Plus)",
        "limit_5h_req": 0,
        "is_unlimited_5h": True,
        "limit_monthly_usd": 0.0,
        "is_unlimited_usd": True,
        "is_limited_time": True,
        "promo_bonus": 1,
        "current_req_5h": 0,
        "current_spent_usd": 0.0,
        "escalation_target": "Last Man Standing (∞)",
        "unit_desc": "requests",
        "timestamps": []
    }
}

# --- Secure Local Key Management ---

def load_env_key():
    """Loads OpenCode API key securely from process env or local .env file."""
    if "OPENCODE_API_KEY" in os.environ and os.environ["OPENCODE_API_KEY"]:
        return os.environ["OPENCODE_API_KEY"].strip()
    if os.path.exists(ENV_FILE):
        try:
            with open(ENV_FILE, "r") as f:
                for line in f:
                    line = line.strip()
                    if line.startswith("OPENCODE_API_KEY="):
                        return line.split("=", 1)[1].strip().strip('"').strip("'")
                    elif line.startswith("oc_sk_"):
                        return line
        except Exception as e:
            print(f"[Env] Error reading .env: {e}")
    return ""

def load_env_org_id():
    """Loads OpenCode organization ID from env or local .env file."""
    if "OPENCODE_ORG_ID" in os.environ and os.environ["OPENCODE_ORG_ID"]:
        return os.environ["OPENCODE_ORG_ID"].strip()
    if os.path.exists(ENV_FILE):
        try:
            with open(ENV_FILE, "r") as f:
                for line in f:
                    line = line.strip()
                    if line.startswith("OPENCODE_ORG_ID="):
                        return line.split("=", 1)[1].strip().strip('"').strip("'")
        except Exception:
            pass
    return ""

def load_opencode_oauth_token():
    """Extracts active OpenCode session token from local opencode.db SQLite database."""
    db_path = os.path.expanduser("~/.local/share/opencode/opencode.db")
    if os.path.exists(db_path):
        try:
            import sqlite3
            conn = sqlite3.connect(db_path)
            c = conn.cursor()
            c.execute("SELECT value FROM credential WHERE integration_id = 'opencode' ORDER BY id DESC")
            rows = c.fetchall()
            for r in rows:
                try:
                    data = json.loads(r[0])
                    if "access" in data and data["access"]:
                        return data["access"].strip()
                except Exception:
                    pass
        except Exception as e:
            print(f"[OAuth] Error reading opencode.db: {e}")
    return ""

def save_env_key(key):
    """Saves OpenCode API key to local .env file atomically, preserving all other variables."""
    key = key.strip()
    os.environ["OPENCODE_API_KEY"] = key
    lines = []
    found = False

    if os.path.exists(ENV_FILE):
        try:
            with open(ENV_FILE, "r") as f:
                for line in f:
                    stripped = line.strip()
                    if stripped.startswith("OPENCODE_API_KEY=") or stripped.startswith("oc_sk_"):
                        lines.append(f"OPENCODE_API_KEY={key}\n")
                        found = True
                    else:
                        lines.append(line)
        except Exception as e:
            print(f"[Env] Error reading existing .env: {e}")

    if not found:
        lines.append(f"OPENCODE_API_KEY={key}\n")

    tmp_path = f"{ENV_FILE}.{os.getpid()}.{time.time_ns()}.tmp"
    try:
        with open(tmp_path, "w") as f:
            f.writelines(lines)
            f.flush()
            os.fsync(f.fileno())
        try:
            os.chmod(tmp_path, 0o600)
        except Exception:
            pass
        os.replace(tmp_path, ENV_FILE)
        return True
    except Exception as e:
        print(f"[Env] Error saving .env: {e}")
        if os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except Exception:
                pass
        return False

def delete_env_key():
    """Deletes API key from memory and local .env, preserving all other configuration."""
    if "OPENCODE_API_KEY" in os.environ:
        del os.environ["OPENCODE_API_KEY"]
    if not os.path.exists(ENV_FILE):
        return True

    lines = []
    has_other_content = False
    try:
        with open(ENV_FILE, "r") as f:
            for line in f:
                stripped = line.strip()
                if stripped.startswith("OPENCODE_API_KEY=") or stripped.startswith("oc_sk_"):
                    continue
                lines.append(line)
                if stripped and not stripped.startswith("#"):
                    has_other_content = True
    except Exception as e:
        print(f"[Env] Error reading .env for deletion: {e}")
        return False

    tmp_path = f"{ENV_FILE}.{os.getpid()}.{time.time_ns()}.tmp"
    try:
        with open(tmp_path, "w") as f:
            f.writelines(lines)
            f.flush()
            os.fsync(f.fileno())
        try:
            os.chmod(tmp_path, 0o600)
        except Exception:
            pass
        os.replace(tmp_path, ENV_FILE)
        return True
    except Exception as e:
        print(f"[Env] Error updating .env on delete: {e}")
        if os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except Exception:
                pass
        return False

def mask_key(key):
    if not key:
        return ""
    if len(key) <= 8:
        return "..."
    return key[:6] + "..." + key[-4:]

# --- Canonical Model Resolution (Strict matching, no loose substring false positives) ---
CANONICAL_MODEL_ALIASES = {
    # Kimi
    "kimi-k3-1-pro": "kimi-k3-1-pro",
    "kimi-k3-1": "kimi-k3-1-pro",
    "kimi-k3": "kimi-k3-1-pro",
    "kimi-k3-pro": "kimi-k3-1-pro",
    
    # Gemini 4 Argon
    "gemini-4-argon": "gemini-4-argon",
    "gemini-4-argon-contributor": "gemini-4-argon",
    
    # GLM 5.3
    "glm-5-3": "glm-5-3",
    "glm-5-3-flash": "glm-5-3",
    
    # MiMo V2.6 Pro
    "mimo-v2-6-pro": "mimo-v2-6-pro",
    "mimo-v2-6": "mimo-v2-6-pro",
    
    # DeepSeek V4 Pro
    "deepseek-v4-pro": "deepseek-v4-pro",
    
    # DeepSeek V4.1 Flash
    "deepseek-v4-1-flash": "deepseek-v4-1-flash",
    "deepseek-v4-flash": "deepseek-v4-1-flash",
    "deepseek-flash": "deepseek-v4-1-flash",
    
    # Claude Haiku 5.5
    "claude-haiku-5-5": "claude-haiku-5-5",
    
    # MiMo V2.6 Flash
    "mimo-v2-6-flash": "mimo-v2-6-flash",
    
    # BEAM Free
    "beam-free": "beam-free",
    "beam": "beam-free",
}

def resolve_model_id(raw_name):
    """Resolves arbitrary API model strings to canonical fleet model IDs strictly."""
    if not raw_name or not isinstance(raw_name, str):
        return None
    slug = raw_name.lower().strip()
    # Strip provider path e.g. "moonshotai/kimi-k3.1" -> "kimi-k3.1"
    if "/" in slug:
        slug = slug.split("/")[-1]
    # Normalize separators
    slug = slug.replace(".", "-").replace("_", "-")
    return CANONICAL_MODEL_ALIASES.get(slug)

MODEL_MAPPINGS = [
    ("gemini-4-argon-contributor", "gemini-4-argon"),
    ("gemini-4-argon", "gemini-4-argon"),
    ("kimi-k3.1-pro", "kimi-k3-1-pro"),
    ("kimi-k3.1", "kimi-k3-1-pro"),
    ("kimi-k3", "kimi-k3-1-pro"),
    ("glm-5.3-flash", "glm-5-3"),
    ("glm-5.3", "glm-5-3"),
    ("mimo-v2.6-flash", "mimo-v2-6-flash"),
    ("mimo-v2.6-pro", "mimo-v2-6-pro"),
    ("deepseek-v4.1-flash", "deepseek-v4-1-flash"),
    ("deepseek-flash", "deepseek-v4-1-flash"),
    ("deepseek-v4-pro", "deepseek-v4-pro"),
    ("claude-haiku-5.5", "claude-haiku-5-5"),
    ("claude-haiku-5-5", "claude-haiku-5-5"),
    ("beam-free", "beam-free"),
    ("beam", "beam-free"),
]

# --- State Manager ---

class StateManager:
    def __init__(self):
        self.lock = threading.RLock()
        self.models = copy.deepcopy(DEFAULT_MODELS)
        self.active_tier = "go-plus"  # "go" or "go-plus"
        self.tier_mode = "auto"       # "auto", "go", "go-plus"
        self.catalog_cache = {}
        self.go_status = {
            "rolling": {"pct": 0, "resets_at": "", "used_usd": 0.0, "limit_usd": 48.0},
            "weekly": {"pct": 0, "resets_at": "", "used_usd": 0.0, "limit_usd": 120.0},
            "monthly": {"pct": 0, "resets_at": "", "used_usd": 0.0, "limit_usd": 240.0},
            "renews_at": "",
            "renews_label": "Renews Nov 24"
        }
        self.cost_summary = {
            "today_usd": 0.0,
            "today_requests": 0,
            "mtd_usd": 0.0,
            "mtd_requests": 0
        }
        self.load()

    def set_tier_mode(self, mode):
        with self.lock:
            self.tier_mode = mode
            if mode in ("go", "go-plus"):
                self.apply_tier(mode)
            elif mode == "auto":
                limit_usd = self.go_status.get("rolling", {}).get("limit_usd", 12.0)
                detected = "go-plus" if limit_usd >= 40.0 else "go"
                self.apply_tier(detected)

    def apply_tier(self, tier):
        with self.lock:
            if tier not in ("go", "go-plus"):
                tier = "go-plus"
            self.active_tier = tier
            updated = 0
            tier_label = "Go Plus" if tier == "go-plus" else "Go"

            for m_id, m in self.models.items():
                base_prov = m.get("raw_provider") or m["provider"].split("(")[0].strip()
                m["raw_provider"] = base_prov
                m["provider"] = f"{base_prov} (OpenCode {tier_label})"

                cat_info = None
                if self.catalog_cache and m_id in self.catalog_cache:
                    cat_info = self.catalog_cache[m_id].get(tier)

                if cat_info:
                    new_req = cat_info.get("requests_5h")
                    new_usd = cat_info.get("limit_monthly_usd")
                    is_ltd = cat_info.get("is_limited_time", False)
                    bonus = cat_info.get("bonus", 1)
                elif tier in TIER_MODELS_CONFIG and m_id in TIER_MODELS_CONFIG[tier]:
                    cfg = TIER_MODELS_CONFIG[tier][m_id]
                    new_req = cfg["limit_5h"]
                    new_usd = cfg["limit_usd"]
                    is_ltd = cfg["is_ltd"]
                    bonus = cfg["bonus"]
                else:
                    continue

                if new_req == '∞' or new_req == 0:
                    m["is_unlimited_5h"] = True
                else:
                    m["is_unlimited_5h"] = False
                    m["limit_5h_req"] = int(new_req)

                if new_usd == '∞' or new_usd == 0.0:
                    m["is_unlimited_usd"] = True
                else:
                    m["is_unlimited_usd"] = False
                    m["limit_monthly_usd"] = float(new_usd)

                m["is_limited_time"] = is_ltd
                m["promo_bonus"] = bonus
                updated += 1

            self.save()
            return updated

    def update_go_status(self, go_data):
        if not go_data:
            return
        with self.lock:
            access = go_data.get("access", {})
            meters = access.get("meters", {})
            
            product = (go_data.get("product") or "").lower()
            five_meter = meters.get("fiveHour") or {}
            limit_micro_5h = int(five_meter.get("limitMicroCents") or 0)
            
            detected_tier = "go-plus" if (product == "go-plus" or limit_micro_5h >= 4000000000) else "go"
            if self.tier_mode == "auto":
                self.apply_tier(detected_tier)

            def_rolling = 48.0 if self.active_tier == "go-plus" else 12.0
            def_weekly = 120.0 if self.active_tier == "go-plus" else 30.0
            def_monthly = 240.0 if self.active_tier == "go-plus" else 60.0

            def parse_meter(m, def_limit=0.0):
                if not m:
                    return {"pct": 0.0, "resets_at": "", "used_usd": 0.0, "limit_usd": round(def_limit, 1)}
                used_micro = int(m.get("usedMicroCents") or 0)
                limit_micro = int(m.get("limitMicroCents") or 1)
                pct = round((used_micro / limit_micro) * 100, 1) if limit_micro > 0 else 0.0
                return {
                    "pct": pct,
                    "used_usd": round(used_micro / 100_000_000.0, 1),
                    "limit_usd": int(limit_micro / 100_000_000.0) if (limit_micro / 100_000_000.0).is_integer() else round(limit_micro / 100_000_000.0, 1),
                    "resets_at": m.get("resetsAt") or ""
                }

            ends_at = access.get("endsAt") or ""
            renews_label = "Renews Nov 24"
            if ends_at:
                try:
                    dt = datetime.fromisoformat(ends_at.replace("Z", "+00:00"))
                    renews_label = f"Renews {dt.strftime('%b %d')}"
                except Exception:
                    pass

            self.go_status = {
                "rolling": parse_meter(meters.get("fiveHour"), def_rolling),
                "weekly": parse_meter(meters.get("week"), def_weekly),
                "monthly": parse_meter(meters.get("month"), def_monthly),
                "renews_at": ends_at,
                "renews_label": renews_label
            }

    def update_cost_summary(self, today_data, mtd_data):
        with self.lock:
            if today_data:
                today_micro = int(today_data.get("totalCostMicroCents") or 0)
                self.cost_summary["today_usd"] = round(today_micro / 100_000_000.0, 1)
                self.cost_summary["today_requests"] = int(today_data.get("totalRequests") or 0)
            if mtd_data:
                mtd_micro = int(mtd_data.get("totalCostMicroCents") or 0)
                self.cost_summary["mtd_usd"] = round(mtd_micro / 100_000_000.0, 1)
                self.cost_summary["mtd_requests"] = int(mtd_data.get("totalRequests") or 0)

    def load(self):
        with self.lock:
            if os.path.exists(DATA_FILE):
                try:
                    with open(DATA_FILE, "r") as f:
                        saved = json.load(f)
                        for k, v in saved.items():
                            if k in self.models:
                                for attr in [
                                    "timestamps", "current_req_5h", "current_spent_usd", "manual_override",
                                    "limit_5h_req", "limit_monthly_usd", "is_unlimited_5h", "is_unlimited_usd",
                                    "is_limited_time", "promo_bonus", "provider"
                                ]:
                                    if attr in v:
                                        self.models[k][attr] = v[attr]
                                if isinstance(self.models[k].get("timestamps"), list):
                                    self.models[k]["timestamps"].sort()
                except Exception as e:
                    print(f"[State] Load error: {e}")

    def update_catalog_limits(self, catalog_data):
        if not catalog_data:
            return 0
        with self.lock:
            self.catalog_cache = catalog_data
            updated = self.apply_tier(self.active_tier)
            if updated > 0:
                print(f"[Catalog] Updated live limits for {updated} models (tier: {self.active_tier}).")
            return updated

    def save(self):
        with self.lock:
            tmp_path = f"{DATA_FILE}.{os.getpid()}.{time.time_ns()}.tmp"
            try:
                with open(tmp_path, "w") as f:
                    json.dump(self.models, f, indent=2)
                    f.flush()
                    os.fsync(f.fileno())
                os.replace(tmp_path, DATA_FILE)
            except Exception as e:
                print(f"[State] Save error: {e}")
                if os.path.exists(tmp_path):
                    try:
                        os.remove(tmp_path)
                    except Exception:
                        pass

    def clean_sliding_windows(self):
        with self.lock:
            now = time.time()
            five_hours_ago = now - 5 * 3600
            for m in self.models.values():
                if "timestamps" in m and m["timestamps"]:
                    idx = bisect.bisect_right(m["timestamps"], five_hours_ago)
                    if idx > 0:
                        m["timestamps"] = m["timestamps"][idx:]
                    if not m.get("manual_override", False):
                        m["current_req_5h"] = len(m["timestamps"])

    def record_request(self, model_id, count=1, est_dollars=0.0):
        with self.lock:
            if model_id in self.models:
                m = self.models[model_id]
                now = time.time()
                if "timestamps" not in m:
                    m["timestamps"] = []
                for _ in range(count):
                    m["timestamps"].append(now)
                m["current_req_5h"] = len(m["timestamps"])
                m["current_spent_usd"] = round(m.get("current_spent_usd", 0.0) + est_dollars, 4)
                self.save()
                return True
            return False

    def update_model(self, model_id, req_5h, spent_usd):
        with self.lock:
            if model_id in self.models:
                m = self.models[model_id]
                m["manual_override"] = True
                m["current_req_5h"] = int(req_5h)
                m["current_spent_usd"] = float(spent_usd)
                self.save()
                return True
            return False

    def clear_override(self, model_id=None, clear_all=False):
        """Clears manual override and resumes automatic sliding window updates."""
        with self.lock:
            cleared = 0
            for k, m in self.models.items():
                if clear_all or (model_id and k == model_id):
                    m["manual_override"] = False
                    m["current_req_5h"] = len(m.get("timestamps", []))
                    cleared += 1
            if cleared:
                self.save()
            return cleared

    def import_cloud_models(self, models_data):
        with self.lock:
            items = models_data.get("items", []) if isinstance(models_data, dict) else models_data
            if not items:
                return 0
            
            # Reset spent for opencode models before importing fresh cloud totals
            for k, m in self.models.items():
                if "OpenCode" in m.get("provider", ""):
                    m["current_spent_usd"] = 0.0

            matched = 0
            for it in items:
                m_raw = (it.get("model") or "").strip()
                target_id = resolve_model_id(m_raw) or (m_raw if m_raw in self.models else None)
                
                if target_id and target_id in self.models:
                    cost_micro = int(it.get("totalCostMicroCents") or 0)
                    cost_usd = round(cost_micro / 100_000_000.0, 4)
                    self.models[target_id]["current_spent_usd"] = round(self.models[target_id]["current_spent_usd"] + cost_usd, 4)
                    matched += 1

            self.save()
            return matched

    def import_cloud_request_logs(self, logs_data):
        with self.lock:
            items = logs_data.get("items", []) if isinstance(logs_data, dict) else (logs_data if isinstance(logs_data, list) else [])
            now = time.time()
            five_hours_ago = now - 5 * 3600

            # Group incoming timestamps by target model
            model_timestamps = {k: [] for k in self.models}
            matched = 0

            for it in items:
                m_raw = (it.get("model") or it.get("requestedModel") or "").strip()
                target_id = resolve_model_id(m_raw) or (m_raw if m_raw in self.models else None)
                
                if target_id and target_id in self.models:
                    started_at = (it.get("startedAt") or 0) / 1000.0
                    if started_at > five_hours_ago:
                        model_timestamps[target_id].append(started_at)
                    matched += 1

            for k in self.models:
                model_timestamps[k].sort()
                self.models[k]["timestamps"] = model_timestamps[k]
                if not self.models[k].get("manual_override", False):
                    self.models[k]["current_req_5h"] = len(model_timestamps[k])

            self.save()
            return matched

    def import_logs_data(self, log_dict):
        with self.lock:
            items = log_dict.get("items", [])
            if not items and isinstance(log_dict, list):
                items = log_dict
            if not items:
                return 0
            now = time.time()
            five_hours_ago = now - 5 * 3600
            
            # Reset current counters before import
            for k in self.models:
                self.models[k]["timestamps"] = []
                self.models[k]["current_req_5h"] = 0
                self.models[k]["current_spent_usd"] = 0.0
                self.models[k]["manual_override"] = False

            imported_count = 0
            for it in items:
                m_raw = (it.get("model") or it.get("requestedModel") or "").strip()
                target_id = resolve_model_id(m_raw) or (m_raw if m_raw in self.models else None)
                
                if target_id and target_id in self.models:
                    m = self.models[target_id]
                    started_at = (it.get("startedAt") or 0) / 1000.0
                    cost = float(it.get("cost") or 0.0)
                    m["current_spent_usd"] = round(m["current_spent_usd"] + cost, 4)
                    
                    if started_at > five_hours_ago:
                        m["timestamps"].append(started_at)
                    imported_count += 1

            for k in self.models:
                m = self.models[k]
                if m["timestamps"]:
                    m["timestamps"].sort()
                    if not m.get("manual_override", False):
                        m["current_req_5h"] = len(m["timestamps"])

            self.save()
            return imported_count

    def reset_all(self):
        with self.lock:
            for k in self.models:
                self.models[k]["timestamps"] = []
                self.models[k]["current_req_5h"] = 0
                self.models[k]["current_spent_usd"] = 0.0
                self.models[k]["manual_override"] = False
            self.save()

    def get_status_snapshot(self):
        """Returns a thread-safe, consistent snapshot of monitor state for UI and API consumers."""
        with self.lock:
            self.clean_sliding_windows()
            now = time.time()
            models_data = []
            alerts = []
            
            for m in self.models.values():
                if m["is_unlimited_5h"]:
                    pct_5h = 0.0
                    status_5h = "UNLIMITED"
                    reset_mins = 0
                else:
                    pct_5h = round((m["current_req_5h"] / m["limit_5h_req"]) * 100, 1)
                    if m.get("timestamps"):
                        earliest = m["timestamps"][0]
                        reset_secs = max(0, (earliest + 5 * 3600) - now)
                        reset_mins = int(reset_secs // 60)
                    else:
                        reset_mins = 0
                
                if m["is_unlimited_usd"]:
                    pct_usd = 0.0
                else:
                    pct_usd = round((m["current_spent_usd"] / m["limit_monthly_usd"]) * 100, 1)

                max_pct = max(pct_5h, pct_usd)
                if max_pct >= 85:
                    risk = "CRITICAL"
                    if not m["is_unlimited_5h"] and pct_5h >= 85:
                        alerts.append({
                            "model": m["name"],
                            "type": "5H_CAP",
                            "msg": f"5H keret elérve ({pct_5h}%). Átirányítás: {m['escalation_target']}"
                        })
                    if not m["is_unlimited_usd"] and pct_usd >= 85:
                        alerts.append({
                            "model": m["name"],
                            "type": "USD_CAP",
                            "msg": f"Havi költési keret elérve ({pct_usd}%). Átirányítás: {m['escalation_target']}"
                        })
                elif max_pct >= 60:
                    risk = "WARNING"
                else:
                    risk = "OK"

                models_data.append({
                    "id": m["id"],
                    "name": m["name"],
                    "role": m["role"],
                    "category": m["category"],
                    "categories": m.get("categories", [m["category"]]),
                    "provider": m["provider"],
                    "limit_5h_req": m["limit_5h_req"],
                    "is_unlimited_5h": m["is_unlimited_5h"],
                    "limit_monthly_usd": int(m["limit_monthly_usd"]) if float(m["limit_monthly_usd"]).is_integer() else round(m["limit_monthly_usd"], 1),
                    "is_unlimited_usd": m["is_unlimited_usd"],
                    "current_req_5h": m["current_req_5h"],
                    "current_spent_usd": round(m["current_spent_usd"], 1),
                    "pct_5h": round(pct_5h, 1),
                    "pct_usd": round(pct_usd, 1),
                    "reset_mins": reset_mins,
                    "risk": risk,
                    "manual_override": m.get("manual_override", False),
                    "escalation_target": m["escalation_target"],
                    "unit_desc": m["unit_desc"],
                    "is_limited_time": m.get("is_limited_time", False),
                    "promo_bonus": m.get("promo_bonus", 1)
                })

            return {
                "server_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "total_models": len(models_data),
                "active_tier": self.active_tier,
                "tier_mode": self.tier_mode,
                "alerts": alerts,
                "models": models_data,
                "go_status": copy.deepcopy(self.go_status),
                "cost_summary": copy.deepcopy(self.cost_summary)
            }

state = StateManager()

# --- OpenCode Live Sync Engine ---

class OpenCodeSyncEngine:
    def __init__(self, state_mgr):
        self.state_mgr = state_mgr
        self.sync_state = {
            "status": "idle",
            "last_sync": "No sync has run yet",
            "last_sync_timestamp": 0,
            "message": "Waiting for sync",
            "items_imported": 0,
            "error_code": None,
            "subsystems": {
                "models": {"status": "idle", "message": "", "last_sync": None},
                "logs": {"status": "idle", "message": "", "last_sync": None},
                "go_status": {"status": "idle", "message": "", "last_sync": None},
                "summary": {"status": "idle", "message": "", "last_sync": None},
            }
        }
        self.lock = threading.Lock()
        self.last_catalog_check = 0

    def get_sync_state_snapshot(self):
        with self.lock:
            return copy.deepcopy(self.sync_state)

    def fetch_opencode_go_catalog(self):
        """
        Fetches live Go quotas & promotions directly from https://opencode.ai/go.
        Extracts both OpenCode Go ($10) and OpenCode Go Plus ($40) tables via SSR HTML.
        """
        browser_ua = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"
        url = "https://opencode.ai/go"
        catalog_raw = {}

        try:
            req = urllib.request.Request(url, headers={"User-Agent": browser_ua, "Accept": "text/html"})
            with urllib.request.urlopen(req, timeout=10) as resp:
                html = resp.read().decode("utf-8")
        except Exception as e:
            print(f"[Catalog Sync] Failed to load {url}: {e}")
            return {}

        try:
            rows = re.findall(r'<tr[^>]*><th scope=\"row\"><bdi>([^<]+)</bdi>(.*?)</tr>', html, re.DOTALL)
            for name, rest in rows:
                name_clean = name.strip()
                labels = re.findall(r'<small[^>]*>([^<]+)</small>', rest)
                is_ltd = any('limited' in l.lower() for l in labels)
                bonus_val = 1
                for l in labels:
                    bm = re.search(r'([0-9]+)x\s*promo', l, re.IGNORECASE)
                    if bm:
                        bonus_val = int(bm.group(1))

                nums = re.findall(r'(?:\$|\b)(\d[\d,]*|∞)', re.sub(r'<[^>]+>', ' ', rest))
                if len(nums) >= 4:
                    def parse_n(s):
                        s = s.replace(',', '')
                        return '∞' if s == '∞' else int(s)
                    def parse_u(s):
                        s = s.replace(',', '')
                        return '∞' if s == '∞' else float(s)

                    req_go = parse_n(nums[0])
                    req_plus = parse_n(nums[1])
                    usd_go = parse_u(nums[2])
                    usd_plus = parse_u(nums[3])

                    key = name_clean.lower()
                    catalog_raw[key] = {
                        "id": key,
                        "name": name_clean,
                        "go": {
                            "requests_5h": req_go,
                            "limit_monthly_usd": usd_go,
                            "is_limited_time": is_ltd,
                            "bonus": bonus_val
                        },
                        "plus": {
                            "requests_5h": req_plus,
                            "limit_monthly_usd": usd_plus,
                            "is_limited_time": is_ltd,
                            "bonus": bonus_val
                        }
                    }
        except Exception as e:
            print(f"[Catalog Sync] Scraper warning: {e}")

        # Map to our 9 fleet models
        model_aliases = {
            'gemini-4-argon': ['gemini 4 argon', 'gemini-4-argon', 'gemini 4 argon contributor', 'gemini-4-argon-contributor'],
            'kimi-k3-1-pro': ['kimi k3.1 pro', 'kimi-k3.1-pro', 'kimi-k3.1', 'kimi-k3'],
            'glm-5-3': ['glm-5.3', 'glm 5.3', 'glm-5-3'],
            'mimo-v2-6-pro': ['mimo-v2.6-pro', 'mimo v2.6 pro', 'mimo-v2-6-pro'],
            'deepseek-v4-pro': ['deepseek-v4-pro', 'deepseek v4 pro'],
            'deepseek-v4-1-flash': ['deepseek v4.1 flash', 'deepseek-v4.1-flash', 'deepseek-flash'],
            'claude-haiku-5-5': ['claude haiku 5.5', 'claude-haiku-5-5', 'claude-haiku-5.5'],
            'mimo-v2-6-flash': ['mimo-v2.6-flash', 'mimo-v2-6-flash'],
            'beam-free': ['beam free', 'beam-free', 'beam']
        }

        result = {}
        for m_id, candidates in model_aliases.items():
            for cand in candidates:
                if cand in catalog_raw:
                    result[m_id] = {
                        "go": catalog_raw[cand]["go"],
                        "go-plus": catalog_raw[cand]["plus"]
                    }
                    break
        return result

    def _api_get(self, endpoint, preferred_tokens, base_headers=None):
        if base_headers is None:
            base_headers = {}
        for tok in preferred_tokens:
            if not tok:
                continue
            try:
                headers = {**base_headers, "Authorization": f"Bearer {tok}"}
                req = urllib.request.Request(endpoint, headers=headers)
                with urllib.request.urlopen(req, timeout=10) as resp:
                    if resp.status == 200:
                        return json.loads(resp.read().decode("utf-8")), None
            except urllib.error.HTTPError as e:
                if e.code in (401, 403):
                    continue
                return None, f"HTTP {e.code}"
            except Exception as e:
                return None, str(e)
        return None, "Authorization required"

    def sync_now(self, force_catalog=False):
        now_ts = time.time()
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # 0. Check live Go catalog limits & promotions from https://opencode.ai/go
        if (now_ts - self.last_catalog_check > 300) or force_catalog or self.last_catalog_check == 0:
            try:
                cat_limits = self.fetch_opencode_go_catalog()
                if cat_limits:
                    self.state_mgr.update_catalog_limits(cat_limits)
                    self.last_catalog_check = now_ts
            except Exception as e:
                print(f"[Catalog Sync] Error: {e}")

        key = load_env_key()
        oauth_token = load_opencode_oauth_token()

        if not key and not oauth_token:
            with self.lock:
                self.sync_state["status"] = "no_key"
                self.sync_state["message"] = "No API key or local OpenCode credentials configured."
            return False, "No credentials provided."

        with self.lock:
            self.sync_state["status"] = "syncing"
            self.sync_state["message"] = "Cloud sync in progress..."

        browser_ua = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"
        org_id = load_env_org_id()
        base_headers = {
            "User-Agent": browser_ua,
            "Accept": "application/json"
        }
        if org_id:
            base_headers["x-org-id"] = org_id

        def api_get(endpoint, preferred_tokens):
            return self._api_get(endpoint, preferred_tokens, base_headers)

        subsystems = {
            "models": {"status": "pending", "message": "", "last_sync": None},
            "logs": {"status": "pending", "message": "", "last_sync": None},
            "go_status": {"status": "pending", "message": "", "last_sync": None},
            "summary": {"status": "pending", "message": "", "last_sync": None},
        }
        errors = []
        imported_models = 0
        imported_requests = 0

        # 1. Fetch cloud aggregated model usage (MTD spent)
        data_models, err = api_get("https://opencode.ai/console/api/usage/models?range=all", [key, oauth_token])
        if data_models:
            imported_models = self.state_mgr.import_cloud_models(data_models)
            subsystems["models"]["status"] = "ok"
            subsystems["models"]["message"] = f"{imported_models} models mapped"
            subsystems["models"]["last_sync"] = now_str
        else:
            subsystems["models"]["status"] = "error"
            subsystems["models"]["message"] = err or "No model data"
            if err:
                errors.append(f"Model aggregation: {err}")

        # 2. Fetch cloud live request logs with verified cursor pagination (P0.1)
        logs_items = []
        logs_err = None
        cursor = None
        max_pages = 25
        page_count = 0
        five_hours_ago = now_ts - 5 * 3600
        reached_window_end = False

        while page_count < max_pages:
            page_count += 1
            url = "https://opencode.ai/console/api/request-logs?category=inference&limit=100"
            if cursor:
                url += f"&cursor={urllib.parse.quote(cursor)}"

            data_logs, err = api_get(url, [oauth_token, key])
            if err:
                logs_err = err
                break
            if not data_logs:
                logs_err = "Empty response from request-logs API"
                break

            items = data_logs.get("items", []) if isinstance(data_logs, dict) else (data_logs if isinstance(data_logs, list) else [])
            if not items:
                reached_window_end = True
                break

            logs_items.extend(items)

            # Check oldest item timestamp on page
            oldest_on_page = min((it.get("startedAt") or 0) / 1000.0 for it in items)
            if oldest_on_page < five_hours_ago:
                reached_window_end = True
                break

            next_cursor = data_logs.get("nextCursor") if isinstance(data_logs, dict) else None
            if not next_cursor:
                reached_window_end = True
                break
            cursor = next_cursor

        # Guard against incomplete pagination: do not overwrite authoritative counters with partial results
        pagination_incomplete = False
        if logs_err:
            pagination_incomplete = True
            err_reason = f"Request logs: {logs_err}"
        elif not reached_window_end and page_count >= max_pages:
            pagination_incomplete = True
            err_reason = f"Request logs: Max pagination limit ({max_pages} pages) reached before 5h window boundary"
            logs_err = f"Max pagination limit ({max_pages} pages) reached before 5h boundary"

        if pagination_incomplete:
            subsystems["logs"]["status"] = "error"
            subsystems["logs"]["message"] = f"Incomplete logs ({logs_err}); retained previous data"
            errors.append(err_reason)
        else:
            imported_requests = self.state_mgr.import_cloud_request_logs(logs_items)
            subsystems["logs"]["status"] = "ok"
            subsystems["logs"]["message"] = f"{imported_requests} reqs in 5h ({page_count} pages traversed)"
            subsystems["logs"]["last_sync"] = now_str

        # 3. Fetch official Go subscription status
        data_go, err = api_get("https://opencode.ai/console/api/go/status", [oauth_token, key])
        if data_go:
            self.state_mgr.update_go_status(data_go)
            subsystems["go_status"]["status"] = "ok"
            subsystems["go_status"]["message"] = "Subscription active"
            subsystems["go_status"]["last_sync"] = now_str
        else:
            subsystems["go_status"]["status"] = "error"
            subsystems["go_status"]["message"] = err or "Failed to fetch Go status"
            if err:
                errors.append(f"Go status: {err}")

        # 4. Fetch 24h & 30d usage summaries
        today_data, err_today = api_get("https://opencode.ai/console/api/usage/summary?range=24h", [key, oauth_token])
        mtd_data, err_mtd = api_get("https://opencode.ai/console/api/usage/summary?range=30d", [key, oauth_token])
        if today_data or mtd_data:
            self.state_mgr.update_cost_summary(today_data, mtd_data)
            subsystems["summary"]["status"] = "ok"
            subsystems["summary"]["message"] = "Spend summary loaded"
            subsystems["summary"]["last_sync"] = now_str
        else:
            subsystems["summary"]["status"] = "error"
            subsystems["summary"]["message"] = err_mtd or err_today or "Failed to fetch summary"
            if err_mtd:
                errors.append(f"Cost summary: {err_mtd}")

        # Determine overall sync state (P0.3)
        sub_statuses = [v["status"] for v in subsystems.values()]
        tier_display = "Go Plus" if self.state_mgr.active_tier == "go-plus" else "Go"

        with self.lock:
            self.sync_state["subsystems"] = subsystems
            self.sync_state["last_sync"] = now_str
            self.sync_state["last_sync_timestamp"] = time.time()
            self.sync_state["items_imported"] = imported_requests

            if all(s == "ok" for s in sub_statuses):
                msg = f"Live connection active [{tier_display}] ({imported_models} models, {imported_requests} reqs in 5h)"
                self.sync_state["status"] = "ok"
                self.sync_state["message"] = msg
                self.sync_state["error_code"] = None
                return True, msg
            elif any(s == "ok" for s in sub_statuses):
                failed = [k for k, v in subsystems.items() if v["status"] == "error"]
                err_msg = "; ".join(errors) if errors else "Some endpoints failed."
                msg = f"Partial sync (Degraded: {', '.join(failed)}): {err_msg}"
                self.sync_state["status"] = "degraded"
                self.sync_state["message"] = msg
                self.sync_state["error_code"] = "DEGRADED"
                return True, msg
            else:
                err_msg = "; ".join(errors) if errors else "No data received from cloud."
                self.sync_state["status"] = "error"
                self.sync_state["message"] = f"Sync error: {err_msg}"
                self.sync_state["error_code"] = err_msg
                return False, self.sync_state["message"]

    def background_worker(self):
        while True:
            try:
                self.sync_now()
            except Exception as e:
                print(f"[Sync Worker] Error: {e}")
            time.sleep(30)

sync_engine = OpenCodeSyncEngine(state)

# --- HTTP Request Handler ---

class MonitorHandler(http.server.SimpleHTTPRequestHandler):
    ALLOWED_ORIGINS = {
        f"http://localhost:{PORT}",
        f"http://127.0.0.1:{PORT}",
    }

    def _get_cors_origin(self):
        origin = self.headers.get("Origin")
        if origin and origin in self.ALLOWED_ORIGINS:
            return origin
        return None

    def _is_request_authorized(self):
        origin = self.headers.get("Origin")
        if origin and origin not in self.ALLOWED_ORIGINS:
            return False, f"Untrusted Origin '{origin}'"

        referer = self.headers.get("Referer")
        if referer:
            ref_parsed = urllib.parse.urlparse(referer)
            ref_origin = f"{ref_parsed.scheme}://{ref_parsed.netloc}"
            if ref_origin not in self.ALLOWED_ORIGINS:
                return False, f"Untrusted Referer '{ref_origin}'"

        sec_fetch = self.headers.get("Sec-Fetch-Site")
        if sec_fetch and sec_fetch not in ("same-origin", "same-site", "none"):
            return False, f"Cross-site fetch '{sec_fetch}' rejected"

        return True, ""

    def do_OPTIONS(self):
        cors_origin = self._get_cors_origin()
        if not cors_origin:
            self.send_error(403, "CORS Forbidden")
            return
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", cors_origin)
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization, x-opencode-session")
        self.send_header("Vary", "Origin")
        self.end_headers()

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == "/api/status":
            resp = state.get_status_snapshot()
            resp["sync_state"] = sync_engine.get_sync_state_snapshot()
            self.send_json_response(resp)
            return

        elif parsed.path in ("/api/key_status", "/api/key/status"):
            key = load_env_key()
            resp = {
                "configured": bool(key),
                "masked_key": mask_key(key),
                "active_tier": state.active_tier,
                "tier_mode": state.tier_mode,
                "sync_state": sync_engine.get_sync_state_snapshot()
            }
            self.send_json_response(resp)
            return

        elif parsed.path in ("/", "/index.html"):
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            html_content = generate_html()
            self.wfile.write(html_content.encode("utf-8"))
            return

        elif parsed.path in ["/opencode-wordmark-light.svg", "/opencode-wordmark-dark.svg"]:
            svg_filename = parsed.path.lstrip("/")
            svg_path = os.path.join(BASE_DIR, svg_filename)
            if os.path.exists(svg_path):
                self.send_response(200)
                self.send_header("Content-Type", "image/svg+xml")
                self.end_headers()
                with open(svg_path, "rb") as f:
                    self.wfile.write(f.read())
                return
            else:
                self.send_error(404, "Logo Not Found")
                return

        else:
            self.send_error(404, "Not Found")

    def do_POST(self):
        authorized, reason = self._is_request_authorized()
        if not authorized:
            self.send_json_response({"success": False, "error": f"Forbidden: {reason}"}, status_code=403)
            return

        parsed = urllib.parse.urlparse(self.path)
        content_length = int(self.headers.get("Content-Length", 0))
        post_data = self.rfile.read(content_length).decode("utf-8")
        try:
            payload = json.loads(post_data) if post_data else {}
        except Exception:
            payload = {}

        if parsed.path in ("/api/save_key", "/api/key"):
            action = payload.get("action")
            if action == "delete":
                delete_env_key()
                with sync_engine.lock:
                    sync_engine.sync_state["status"] = "no_key"
                    sync_engine.sync_state["message"] = "API key removed."
                self.send_json_response({"success": True})
                return
            key = payload.get("api_key", "").strip()
            if not key:
                self.send_json_response({"success": False, "error": "Az API kulcs mező nem lehet üres!"})
                return
            save_env_key(key)
            success, msg = sync_engine.sync_now()
            self.send_json_response({
                "success": True,
                "sync_success": success,
                "message": msg,
                "masked_key": mask_key(key),
                "sync_state": sync_engine.get_sync_state_snapshot()
            })

        elif parsed.path == "/api/delete_key":
            delete_env_key()
            with sync_engine.lock:
                sync_engine.sync_state["status"] = "no_key"
                sync_engine.sync_state["message"] = "API key removed."
            self.send_json_response({"success": True})

        elif parsed.path in ("/api/sync_now", "/api/sync"):
            success, msg = sync_engine.sync_now(force_catalog=True)
            self.send_json_response({
                "success": success,
                "message": msg,
                "sync_state": sync_engine.get_sync_state_snapshot()
            })

        elif parsed.path in ("/api/set_tier", "/api/tier"):
            tier_mode = payload.get("tier_mode", "auto")
            state.set_tier_mode(tier_mode)
            sync_engine.sync_now(force_catalog=True)
            self.send_json_response({
                "success": True,
                "tier_mode": state.tier_mode,
                "active_tier": state.active_tier
            })

        elif parsed.path == "/api/record":
            model_id = payload.get("model")
            count = int(payload.get("count", 1))
            dollars = float(payload.get("dollars", 0.0))
            success = state.record_request(model_id, count, dollars)
            self.send_json_response({"success": success})

        elif parsed.path == "/api/update":
            model_id = payload.get("model")
            req_5h = payload.get("req_5h", 0)
            spent_usd = payload.get("spent_usd", 0.0)
            success = state.update_model(model_id, req_5h, spent_usd)
            self.send_json_response({"success": success})

        elif parsed.path == "/api/clear_override":
            model_id = payload.get("model")
            clear_all = payload.get("all", False)
            cleared = state.clear_override(model_id, clear_all)
            self.send_json_response({"success": True, "cleared": cleared})

        elif parsed.path == "/api/import_logs":
            count = state.import_logs_data(payload)
            self.send_json_response({"success": True, "imported_count": count})

        elif parsed.path == "/api/reset_all":
            state.reset_all()
            self.send_json_response({"success": True, "message": "All statistics reset to 0"})

        else:
            self.send_error(404, "Not Found")

    def send_json_response(self, data, status_code=200):
        body = json.dumps(data).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        cors_origin = self._get_cors_origin()
        if cors_origin:
            self.send_header("Access-Control-Allow-Origin", cors_origin)
            self.send_header("Vary", "Origin")
        self.send_header("Cache-Control", "no-store, no-cache, must-revalidate")
        self.end_headers()
        self.wfile.write(body)

def generate_html():
    return """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>OpenCode Go Fleet Monitor</title>
  <script src="https://cdn.tailwindcss.com"></script>
  <script>
    tailwind.config = {
      darkMode: 'class'
    }
  </script>
  <script>
    (function() {
      const pref = localStorage.getItem('theme_preference') || 'dark';
      const isDark = pref === 'dark' || (pref === 'system' && window.matchMedia('(prefers-color-scheme: dark)').matches);
      if (isDark) {
        document.documentElement.classList.add('dark');
      } else {
        document.documentElement.classList.remove('dark');
      }
    })();
  </script>
  <style>
    @import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;600;700&family=Inter:wght@400;500;600;700;800&display=swap');
    body { font-family: 'Inter', sans-serif; }
    .mono { font-family: 'JetBrains Mono', monospace; }
    
    /* Codex Warm Daylight Palette (Day Mode) */
    html:not(.dark), html:not(.dark) body {
      background-color: #f2f8f5 !important;
      color: #1c221e !important;
    }
    
    /* PyCharm Dark Theme (Night Mode) - Untouched */
    html.dark, html.dark body {
      background-color: #191a1c !important;
    }
  </style>
</head>
<body class="bg-[#f2f8f5] text-[#1c221e] dark:bg-[#191a1c] dark:text-slate-100 min-h-screen transition-colors duration-150">

  <!-- Top Navigation & Status -->
  <header class="border-b border-[#d8e0db] bg-[#edf3f0]/95 dark:border-[#32363a] dark:bg-[#25292c] backdrop-blur sticky top-0 z-40 transition-colors">
    <div class="w-full px-4 sm:px-6 py-2 flex items-center justify-between gap-3">
      
      <!-- Left Controls & Metrics Group (+2 text sizes) -->
      <div class="flex items-center gap-2 sm:gap-2.5 text-sm sm:text-base flex-nowrap shrink-0">
        <!-- Dual Spend Pill: Today (24h) vs Month-to-Date (30d) -->
        <div class="bg-[#e1e9e4] border border-[#d0dad3] dark:bg-[#191a1c] dark:border-[#32363a] px-3 py-1.5 rounded-xl flex items-center gap-2 shadow-sm">
          <span class="text-[#556358] dark:text-slate-400 font-semibold text-sm sm:text-[15px]">Today:</span>
          <span id="header-today-usd" class="mono text-[#0f765e] dark:text-emerald-400 font-black text-[16px] sm:text-[17px]">$0.0</span>
          <span class="text-[#b4c0b8] dark:text-slate-600 font-light">|</span>
          <span class="text-[#556358] dark:text-slate-400 font-semibold text-sm sm:text-[15px]">MTD:</span>
          <span id="header-total-usd" class="mono text-[#0f765e] dark:text-emerald-400 font-black text-[16px] sm:text-[17px]">$0.0</span>
        </div>

        <!-- Plan Badge & Renews Pill -->
        <div class="bg-[#e1e9e4] border border-[#d0dad3] dark:bg-[#191a1c] dark:border-[#32363a] px-3 py-1.5 rounded-xl flex items-center gap-2 shadow-sm">
          <span id="plan-badge" class="px-2 py-0.5 rounded-md text-[11px] font-black uppercase tracking-wider bg-indigo-500/20 text-indigo-400 border border-indigo-500/40">GO PLUS</span>
          <span id="go-renews-label" class="font-bold text-[#1c221e] dark:text-slate-200 text-sm sm:text-[15px]">Renews Nov 24</span>
        </div>

        <!-- Live API Status Pill (Relocated green pulsating dot) -->
        <div id="api-status-pill" class="bg-[#e1e9e4] border border-[#d0dad3] dark:bg-[#191a1c] dark:border-[#32363a] px-3 py-1.5 rounded-xl flex items-center gap-2 shadow-sm">
          <span id="api-dot" class="w-2.5 h-2.5 rounded-full bg-emerald-500 animate-pulse shrink-0"></span>
          <span id="api-status-text" class="text-[#252f27] dark:text-slate-200 font-bold text-sm sm:text-[15px] truncate max-w-[210px]">Checking...</span>
          <button onclick="openApiKeyModal()" class="text-[#0f765e] hover:text-[#0b5443] dark:text-indigo-400 dark:hover:text-indigo-300 underline font-bold text-sm sm:text-[15px] ml-0.5">Manage</button>
        </div>

        <!-- Sync button -->
        <button onclick="triggerSyncNow()" id="sync-btn" class="bg-[#0f765e] hover:bg-[#0c624e] dark:bg-emerald-700 dark:hover:bg-emerald-600 text-white px-3.5 py-1.5 rounded-xl font-bold transition flex items-center gap-1.5 shadow-sm text-sm sm:text-[15px]">
          <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"/></svg>
          <span id="sync-btn-label">Sync</span>
        </button>

        <!-- Theme Toggle (System, Day, Night) -->
        <div class="flex items-center bg-[#dbe4de] dark:bg-[#191a1c] p-0.5 rounded-xl border border-[#cbd5ce] dark:border-[#32363a] shadow-sm">
          <button onclick="setTheme('system')" id="theme-btn-system" title="System" class="p-1.5 rounded-lg transition text-[#556358] hover:text-[#1c221e] dark:text-slate-400 dark:hover:text-slate-200">
            <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><rect x="2" y="3" width="20" height="14" rx="2" stroke-width="2"/><path stroke-width="2" stroke-linecap="round" d="M8 21h8m-4-4v4"/></svg>
          </button>
          <button onclick="setTheme('light')" id="theme-btn-light" title="Day (Light)" class="p-1.5 rounded-lg transition text-[#556358] hover:text-[#1c221e] dark:text-slate-400 dark:hover:text-slate-200">
            <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><circle cx="12" cy="12" r="4" stroke-width="2"/><path stroke-width="2" stroke-linecap="round" d="M12 2v2m0 16v2M4.93 4.93l1.41 1.41m11.32 11.32l1.41 1.41M2 12h2m16 0h2M6.34 17.66l-1.41 1.41M19.07 4.93l-1.41 1.41"/></svg>
          </button>
          <button onclick="setTheme('dark')" id="theme-btn-dark" title="Night (Dark)" class="p-1.5 rounded-lg transition text-[#556358] hover:text-[#1c221e] dark:text-slate-400 dark:hover:text-slate-200">
            <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-width="2" stroke-linecap="round" stroke-linejoin="round" d="M20.354 15.354A9 9 0 018.646 3.646 9.003 9.003 0 0012 21a9.003 9.003 0 008.354-5.646z"/></svg>
          </button>
        </div>

      </div>

      <!-- Right Area: OpenCode Wordmark Logo Centered in the free space between Night icon and screen right edge -->
      <div class="flex-1 flex justify-center items-center min-w-[130px] pl-3">
        <a href="https://opencode.ai" target="_blank" rel="noopener noreferrer" class="opacity-90 hover:opacity-100 transition inline-flex items-center" title="OpenCode">
          <!-- Light Mode Logo (Visible in DAY mode) -->
          <svg class="h-[25px] sm:h-[27px] w-auto block dark:hidden" style="height: 26px;" viewBox="0 0 640 115" fill="none" xmlns="http://www.w3.org/2000/svg">
            <g clip-path="url(#clip0_opencode_light)"><mask id="mask0_opencode_light" style="mask-type:luminance" maskUnits="userSpaceOnUse" x="0" y="0" width="640" height="115"><path d="M640 0H0V115H640V0Z" fill="white"/></mask><g mask="url(#mask0_opencode_light)"><path d="M49.2346 82.1433H16.4141V49.2861H49.2346V82.1433Z" fill="#CFCECD"/><path d="M49.2308 32.8573H16.4103V82.143H49.2308V32.8573ZM65.641 98.5716H0V16.4287H65.641V98.5716Z" fill="#656363"/><path d="M131.281 82.1433H98.4609V49.2861H131.281V82.1433Z" fill="#CFCECD"/><path d="M98.4649 82.143H131.285V32.8573H98.4649V82.143ZM147.696 98.5716H98.4649V115H82.0547V16.4287H147.696V98.5716Z" fill="#656363"/><path d="M229.746 65.7139V82.1424H180.516V65.7139H229.746Z" fill="#CFCECD"/><path d="M229.743 65.7144H180.512V82.143H229.743V98.5716H164.102V16.4287H229.743V65.7144ZM180.512 49.2859H213.332V32.8573H180.512V49.2859Z" fill="#656363"/><path d="M295.383 98.5718H262.562V49.2861H295.383V98.5718Z" fill="#CFCECD"/><path d="M295.387 32.8573H262.567V98.5716H246.156V16.4287H295.387V32.8573ZM311.797 98.5716H295.387V32.8573H311.797V98.5716Z" fill="#656363"/><path d="M393.848 82.1433H344.617V49.2861H393.848V82.1433Z" fill="#CFCECD"/><path d="M393.844 32.8573H344.613V82.143H393.844V98.5716H328.203V16.4287H393.844V32.8573Z" fill="#211E1E"/><path d="M459.485 82.1433H426.664V49.2861H459.485V82.1433Z" fill="#CFCECD"/><path d="M459.489 32.8573H426.668V82.143H459.489V32.8573ZM475.899 98.5716H410.258V16.4287H475.899V98.5716Z" fill="#211E1E"/><path d="M541.539 82.1433H508.719V49.2861H541.539V82.1433Z" fill="#CFCECD"/><path d="M541.535 32.8571H508.715V82.1428H541.535V32.8571ZM557.946 98.5714H492.305V16.4286H541.535V0H557.946V98.5714Z" fill="#211E1E"/><path d="M639.996 65.7139V82.1424H590.766V65.7139H639.996Z" fill="#CFCECD"/><path d="M590.77 32.8573V49.2859H623.59V32.8573H590.77ZM640 65.7144H590.77V82.143H640V98.5716H574.359V16.4287H640V65.7144Z" fill="#211E1E"/></g></g><defs><clipPath id="clip0_opencode_light"><rect width="640" height="115" fill="white"/></clipPath></defs>
          </svg>
          <!-- Dark Mode Logo (Visible in NIGHT mode) -->
          <svg class="h-[25px] sm:h-[27px] w-auto hidden dark:block" style="height: 26px;" viewBox="0 0 641 115" fill="none" xmlns="http://www.w3.org/2000/svg">
            <g clip-path="url(#clip0_opencode_dark)"><mask id="mask0_opencode_dark" style="mask-type:luminance" maskUnits="userSpaceOnUse" x="0" y="0" width="641" height="115"><path d="M640.714 0H0V115H640.714V0Z" fill="white"/></mask><g mask="url(#mask0_opencode_dark)"><path d="M49.2868 82.1433H16.4297V49.2861H49.2868V82.1433Z" fill="#4B4646"/><path d="M49.2857 32.8573H16.4286V82.143H49.2857V32.8573ZM65.7143 98.5716H0V16.4287H65.7143V98.5716Z" fill="#B7B1B1"/><path d="M131.427 82.1433H98.5703V49.2861H131.427V82.1433Z" fill="#4B4646"/><path d="M98.5692 82.143H131.426V32.8573H98.5692V82.143ZM147.855 98.5716H98.5692V115H82.1406V16.4287H147.855V98.5716Z" fill="#B7B1B1"/><path d="M229.997 65.7139V82.1424H180.711V65.7139H229.997Z" fill="#4B4646"/><path d="M230.003 65.7144H180.718V82.143H230.003V98.5716H164.289V16.4287H230.003V65.7144ZM180.718 49.2859H213.575V32.8573H180.718V49.2859Z" fill="#B7B1B1"/><path d="M295.717 98.5718H262.859V49.2861H295.717V98.5718Z" fill="#4B4646"/><path d="M295.715 32.8573H262.858V98.5716H246.43V16.4287H295.715V32.8573ZM312.144 98.5716H295.715V32.8573H312.144V98.5716Z" fill="#B7B1B1"/><path d="M394.286 82.1433H345V49.2861H394.286V82.1433Z" fill="#4B4646"/><path d="M394.285 32.8573H344.999V82.143H394.285V98.5716H328.57V16.4287H394.285V32.8573Z" fill="#F1ECEC"/><path d="M459.998 82.1433H427.141V49.2861H459.998V82.1433Z" fill="#4B4646"/><path d="M459.997 32.8573H427.14V82.143H459.997V32.8573ZM476.425 98.5716H410.711V16.4287H476.425V98.5716Z" fill="#F1ECEC"/><path d="M542.146 82.1433H509.289V49.2861H542.146V82.1433Z" fill="#4B4646"/><path d="M542.145 32.8571H509.288V82.1429H542.145V32.8571ZM558.574 98.5714H492.859V16.4286H542.145V0H558.574V98.5714Z" fill="#F1ECEC"/><path d="M640.715 65.7139V82.1424H591.43V65.7139H640.715Z" fill="#4B4646"/><path d="M591.429 32.8573V49.2859H624.286V32.8573H591.429ZM640.714 65.7144H591.429V82.143H640.714V98.5716H575V16.4287H640.714V65.7144Z" fill="#F1ECEC"/></g></g><defs><clipPath id="clip0_opencode_dark"><rect width="640.714" height="115" fill="white"/></clipPath></defs>
          </svg>
        </a>
      </div>

    </div>

    <!-- Official OpenCode Go Subscription Meters Bar (3-column grid aligned with card columns) -->
    <div class="border-t border-[#d8e0db] bg-[#f0f6f3]/95 dark:border-[#32363a] dark:bg-[#25292c]/95 px-4 sm:px-6 py-3 sm:py-3.5">
      <div class="w-full grid grid-cols-1 md:grid-cols-3 lg:grid-cols-3 gap-3">
        
        <!-- Rolling (5h) - Column 1 -->
        <div class="relative flex items-center justify-start gap-3 sm:gap-4 lg:gap-5">
          <div class="relative w-12 h-12 sm:w-[52px] sm:h-[52px] shrink-0 flex items-center justify-center" title="5h Rolling Usage">
            <svg class="w-full h-full -rotate-90" viewBox="0 0 36 36">
              <circle cx="18" cy="18" r="15.9155" class="stroke-[#dbe3de] dark:stroke-[#191a1c]" stroke-width="4.5" fill="none" />
              <circle id="meter-rolling-pie" cx="18" cy="18" r="15.9155" class="stroke-emerald-600 transition-all duration-500" stroke-width="4.5" stroke-dasharray="0, 100" stroke-linecap="round" fill="none" />
            </svg>
          </div>
          <div class="flex items-center gap-3 sm:gap-4 lg:gap-5 whitespace-nowrap min-w-0">
            <span class="font-black text-[#151c17] dark:text-white text-[19px] sm:text-[21px] tracking-tight shrink-0">Rolling</span>
            <div class="flex flex-col justify-center leading-none shrink-0">
              <span class="text-[13px] sm:text-[14px] font-bold text-[#556358] dark:text-slate-400 tracking-tight leading-none mb-1">Resets in</span>
              <span id="meter-rolling-reset" class="text-base sm:text-[18px] text-[#1c221e] dark:text-slate-200 font-black mono leading-none">--</span>
            </div>
            <span id="meter-rolling-pct" class="mono font-black text-[19px] sm:text-[21px] text-[#0f765e] dark:text-emerald-400 shrink-0">0.0% used</span>
          </div>
          <!-- Vertical separator positioned in the gap between Col 1 and Col 2 -->
          <div class="hidden md:block absolute -right-[6px] top-1/2 -translate-y-1/2 h-9 w-px bg-[#ccd5cf] dark:bg-[#3d4248] pointer-events-none"></div>
        </div>

        <!-- Weekly - Column 2 -->
        <div class="relative flex items-center justify-start gap-3 sm:gap-4 lg:gap-5">
          <div class="relative w-12 h-12 sm:w-[52px] sm:h-[52px] shrink-0 flex items-center justify-center" title="Weekly Spend">
            <svg class="w-full h-full -rotate-90" viewBox="0 0 36 36">
              <circle cx="18" cy="18" r="15.9155" class="stroke-[#dbe3de] dark:stroke-[#191a1c]" stroke-width="4.5" fill="none" />
              <circle id="meter-weekly-pie" cx="18" cy="18" r="15.9155" class="stroke-emerald-600 transition-all duration-500" stroke-width="4.5" stroke-dasharray="0, 100" stroke-linecap="round" fill="none" />
            </svg>
          </div>
          <div class="flex items-center gap-3 sm:gap-4 lg:gap-5 whitespace-nowrap min-w-0">
            <span class="font-black text-[#151c17] dark:text-white text-[19px] sm:text-[21px] tracking-tight shrink-0">Weekly</span>
            <div class="flex flex-col justify-center leading-none shrink-0">
              <span class="text-[13px] sm:text-[14px] font-bold text-[#556358] dark:text-slate-400 tracking-tight leading-none mb-1">Resets in</span>
              <span id="meter-weekly-reset" class="text-base sm:text-[18px] text-[#1c221e] dark:text-slate-200 font-black mono leading-none">--</span>
            </div>
            <span id="meter-weekly-pct" class="mono font-black text-[19px] sm:text-[21px] text-[#0f765e] dark:text-emerald-400 shrink-0">0.0% used</span>
          </div>
          <!-- Vertical separator positioned in the gap between Col 2 and Col 3 -->
          <div class="hidden md:block absolute -right-[6px] top-1/2 -translate-y-1/2 h-9 w-px bg-[#ccd5cf] dark:bg-[#3d4248] pointer-events-none"></div>
        </div>

        <!-- Monthly - Column 3 -->
        <div class="relative flex items-center justify-start gap-3 sm:gap-4 lg:gap-5">
          <div class="relative w-12 h-12 sm:w-[52px] sm:h-[52px] shrink-0 flex items-center justify-center" title="Monthly Spend">
            <svg class="w-full h-full -rotate-90" viewBox="0 0 36 36">
              <circle cx="18" cy="18" r="15.9155" class="stroke-[#dbe3de] dark:stroke-[#191a1c]" stroke-width="4.5" fill="none" />
              <circle id="meter-monthly-pie" cx="18" cy="18" r="15.9155" class="stroke-emerald-600 transition-all duration-500" stroke-width="4.5" stroke-dasharray="0, 100" stroke-linecap="round" fill="none" />
            </svg>
          </div>
          <div class="flex items-center gap-3 sm:gap-4 lg:gap-5 whitespace-nowrap min-w-0">
            <span class="font-black text-[#151c17] dark:text-white text-[19px] sm:text-[21px] tracking-tight shrink-0">Monthly</span>
            <div class="flex flex-col justify-center leading-none shrink-0">
              <span class="text-[13px] sm:text-[14px] font-bold text-[#556358] dark:text-slate-400 tracking-tight leading-none mb-1">Resets in</span>
              <span id="meter-monthly-reset" class="text-base sm:text-[18px] text-[#1c221e] dark:text-slate-200 font-black mono leading-none">--</span>
            </div>
            <span id="meter-monthly-pct" class="mono font-black text-[19px] sm:text-[21px] text-[#0f765e] dark:text-emerald-400 shrink-0">0.0% used</span>
          </div>
        </div>

      </div>
    </div>
  </header>

  <!-- Main Container (100% Full Fill Rate for 1280x854 Display) -->
  <main class="w-full px-4 sm:px-6 py-2.5 space-y-2.5">
    
    <!-- Active Alert Banner (Hidden when 0 alerts) -->
    <div id="alert-banner" class="hidden p-2.5 rounded-xl bg-red-50 dark:bg-red-950/80 border border-red-200 dark:border-red-800/80 space-y-1">
      <div class="flex items-center gap-2 text-red-600 dark:text-red-400 font-bold text-xs">
        <svg class="w-4 h-4 animate-bounce" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"/></svg>
        QUOTA ALERT — ESCALATION NEEDED!
      </div>
      <div id="alert-list" class="space-y-1 text-xs text-red-700 dark:text-red-200"></div>
    </div>

    <!-- Category Filters (Clickable - Larger font and touch targets) -->
    <div class="flex items-center justify-between gap-2 overflow-x-auto py-1">
      <div class="flex items-center gap-2 text-sm sm:text-[14px] flex-wrap">
        <button onclick="filterCards('all', this)" class="filter-btn active bg-[#1c221e] dark:bg-[#32363a] text-white px-3 py-1.5 rounded-xl font-bold border border-[#1c221e] dark:border-[#42474c] transition shadow-sm">All (9)</button>
        <button onclick="filterCards('Deep Debugging', this)" class="filter-btn bg-[#f8fbf9] dark:bg-[#25292c] text-[#4d5950] dark:text-slate-300 px-3 py-1.5 rounded-xl font-bold border border-[#d5ded7] dark:border-[#32363a] hover:bg-[#e7eee9] hover:text-[#1c221e] dark:hover:text-white transition shadow-sm">🐛 Debugging</button>
        <button onclick="filterCards('Implementation', this)" class="filter-btn bg-[#f8fbf9] dark:bg-[#25292c] text-[#4d5950] dark:text-slate-300 px-3 py-1.5 rounded-xl font-bold border border-[#d5ded7] dark:border-[#32363a] hover:bg-[#e7eee9] hover:text-[#1c221e] dark:hover:text-white transition shadow-sm">🛠️ Implementation</button>
        <button onclick="filterCards('Reasoning Fallback', this)" class="filter-btn bg-[#f8fbf9] dark:bg-[#25292c] text-[#4d5950] dark:text-slate-300 px-3 py-1.5 rounded-xl font-bold border border-[#d5ded7] dark:border-[#32363a] hover:bg-[#e7eee9] hover:text-[#1c221e] dark:hover:text-white transition shadow-sm">🧠 Reasoning</button>
        <button onclick="filterCards('Agentic Coding', this)" class="filter-btn bg-[#f8fbf9] dark:bg-[#25292c] text-[#4d5950] dark:text-slate-300 px-3 py-1.5 rounded-xl font-bold border border-[#d5ded7] dark:border-[#32363a] hover:bg-[#e7eee9] hover:text-[#1c221e] dark:hover:text-white transition shadow-sm">⚙️ Coding Workhorse</button>
        <button onclick="filterCards('Fast Subagent', this)" class="filter-btn bg-[#f8fbf9] dark:bg-[#25292c] text-[#4d5950] dark:text-slate-300 px-3 py-1.5 rounded-xl font-bold border border-[#d5ded7] dark:border-[#32363a] hover:bg-[#e7eee9] hover:text-[#1c221e] dark:hover:text-white transition shadow-sm">⚡ Subagent</button>
        <button onclick="filterCards('High-Throughput', this)" class="filter-btn bg-[#f8fbf9] dark:bg-[#25292c] text-[#4d5950] dark:text-slate-300 px-3 py-1.5 rounded-xl font-bold border border-[#d5ded7] dark:border-[#32363a] hover:bg-[#e7eee9] hover:text-[#1c221e] dark:hover:text-white transition shadow-sm">♾️ High-Volume</button>
        <button onclick="filterCards('Research & Extraction', this)" class="filter-btn bg-[#f8fbf9] dark:bg-[#25292c] text-[#4d5950] dark:text-slate-300 px-3 py-1.5 rounded-xl font-bold border border-[#d5ded7] dark:border-[#32363a] hover:bg-[#e7eee9] hover:text-[#1c221e] dark:hover:text-white transition shadow-sm">🔎 Web Research</button>
      </div>

      <div class="text-xs sm:text-[13px] text-[#556358] dark:text-slate-400 font-semibold flex items-center gap-1.5 shrink-0 hidden sm:flex">
        <span class="w-2 h-2 rounded-full bg-emerald-500 dark:bg-emerald-400"></span>
        <span>Auto-sync: 30s</span>
      </div>
    </div>

    <!-- Models Grid (3x3 Layout for 9 models) -->
    <div id="models-grid" class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
      <!-- Populated via JS -->
    </div>

  </main>

  <!-- ================= API KEY PROMPT MODAL ================= -->
  <div id="api-key-modal" class="fixed inset-0 bg-black/60 backdrop-blur-sm hidden flex items-center justify-center z-50 p-4">
    <div class="bg-[#f8fbf9] dark:bg-[#25292c] border border-[#d8e0db] dark:border-[#32363a] rounded-2xl max-w-lg w-full p-6 space-y-5 shadow-2xl">
      <div class="flex items-start justify-between">
        <div class="flex items-center gap-2.5">
          <div class="p-2 bg-[#e4ece6] dark:bg-indigo-950/80 border border-[#d2dbd4] dark:border-indigo-700/50 rounded-lg text-[#0f765e] dark:text-indigo-400">
            <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 7a2 2 0 012 2m4 0a6 6 0 01-7.743 5.743L11 17H9v2H7v2H4a1 1 0 01-1-1v-2.586a1 1 0 01.293-.707l5.964-5.964A6 6 0 1121 9z"/></svg>
          </div>
          <div>
            <h3 class="text-lg font-bold text-[#151c17] dark:text-white">OpenCode API Key Configuration</h3>
            <p class="text-xs text-[#556358] dark:text-slate-400">Official Console API real-time sync</p>
          </div>
        </div>
        <button onclick="closeApiKeyModal()" class="text-[#556358] hover:text-[#1c221e] dark:hover:text-white p-1 rounded-lg">✕</button>
      </div>

      <div class="p-3 bg-[#e8f1eb] dark:bg-emerald-950/40 border border-[#d2ded6] dark:border-emerald-800/40 rounded-xl text-xs text-[#135f47] dark:text-emerald-300 leading-relaxed">
        🔒 <strong>Data security guarantee:</strong> The provided key is never sent to external servers. It is strictly stored locally on your Mac in a secured environment file (<code>.env</code>, <code>chmod 600</code>) for direct OpenCode Console communication.
      </div>

      <div class="space-y-2">
        <label class="block text-xs font-semibold text-[#252f27] dark:text-slate-300">
          Enter your API key:
        </label>
        <div class="relative">
          <input type="password" id="api-key-input" placeholder="oc_sk_..." class="w-full bg-[#ffffff] dark:bg-[#191a1c] border border-[#cbd5ce] dark:border-[#32363a] rounded-xl px-4 py-2.5 text-sm text-[#1c221e] dark:text-white mono focus:outline-none focus:border-[#0f765e] pr-10">
          <button type="button" onclick="toggleKeyVisibility()" class="absolute right-3 top-2.5 text-[#556358] hover:text-[#1c221e] dark:hover:text-slate-200 text-sm">
            <span id="eye-icon">👁️</span>
          </button>
        </div>
        <p id="api-key-error" class="hidden text-xs text-red-500 font-medium"></p>
      </div>

      <!-- Subscription Plan Tier Override -->
      <div class="space-y-1.5 pt-1">
        <label class="block text-xs font-semibold text-[#252f27] dark:text-slate-300">
          OpenCode Subscription Plan:
        </label>
        <div class="grid grid-cols-3 gap-2">
          <button type="button" onclick="setTierMode('auto')" id="tier-btn-auto" class="px-2.5 py-1.5 rounded-xl text-xs font-bold border transition text-center">
            Auto-Detect
          </button>
          <button type="button" onclick="setTierMode('go')" id="tier-btn-go" class="px-2.5 py-1.5 rounded-xl text-xs font-bold border transition text-center">
            Go ($10)
          </button>
          <button type="button" onclick="setTierMode('go-plus')" id="tier-btn-plus" class="px-2.5 py-1.5 rounded-xl text-xs font-bold border transition text-center">
            Go Plus ($40)
          </button>
        </div>
        <p id="tier-status-desc" class="text-[11px] text-[#556358] dark:text-slate-400">Auto-detect syncs automatically with your active OpenCode subscription.</p>
      </div>

      <!-- Step by step guidance -->
      <div class="border border-[#d5ded7] dark:border-[#32363a] rounded-xl p-3 bg-[#edf3ef] dark:bg-[#191a1c]/80 text-xs space-y-2">
        <div class="font-semibold text-[#252f27] dark:text-slate-300 flex items-center gap-1.5">
          <span>📌</span> Where to find your key in OpenCode Console:
        </div>
        <ol class="list-decimal list-inside text-[#556358] dark:text-slate-400 space-y-1 pl-1">
          <li>Open console: <a href="https://opencode.ai/console" target="_blank" class="text-[#0f765e] dark:text-indigo-400 underline hover:underline">opencode.ai/console</a></li>
          <li>Click on <strong>Add Service Account</strong>.</li>
          <li>Select permissions: <strong>All</strong> (or Console/Logs).</li>
          <li>Click <strong>Add API Key</strong>, and copy the generated <code>oc_sk_...</code> token.</li>
        </ol>
      </div>

      <div class="flex items-center justify-between pt-2">
        <button id="delete-key-btn" onclick="deleteApiKey()" class="hidden text-xs text-red-500 hover:text-red-700 dark:text-red-400 dark:hover:text-red-300 underline">
          Delete Key
        </button>
        <div class="flex gap-2 ml-auto">
          <button onclick="closeApiKeyModal()" class="px-4 py-2 text-xs text-[#556358] hover:text-[#1c221e] dark:text-slate-400 dark:hover:text-white rounded-lg">Close</button>
          <button onclick="saveApiKey()" id="save-key-btn" class="bg-[#0f765e] hover:bg-[#0c624e] text-white px-5 py-2 rounded-xl text-xs font-semibold shadow-md flex items-center gap-1.5 transition">
            <span>💾 Save & Connect</span>
          </button>
        </div>
      </div>
    </div>
  </div>

  <!-- Manual Edit Modal -->
  <div id="edit-modal" class="fixed inset-0 bg-black/60 backdrop-blur-sm hidden flex items-center justify-center z-50 p-4">
    <div class="bg-[#f8fbf9] dark:bg-[#25292c] border border-[#d8e0db] dark:border-[#32363a] rounded-2xl max-w-md w-full p-6 space-y-4 shadow-xl">
      <h3 class="text-lg font-bold text-[#151c17] dark:text-white flex items-center gap-2">
        <span id="modal-model-name">Model Settings</span>
      </h3>
      <p class="text-xs text-[#556358] dark:text-slate-400">Manual override for testing or offline mode:</p>
      
      <div class="space-y-3">
        <div>
          <label class="block text-xs text-[#252f27] dark:text-slate-400 mb-1">5-Hour Usage (Prompts / Requests):</label>
          <input type="number" id="modal-req" class="w-full bg-[#ffffff] dark:bg-[#191a1c] border border-[#cbd5ce] dark:border-[#32363a] rounded-lg px-3 py-2 text-sm text-[#1c221e] dark:text-white mono">
        </div>
        <div>
          <label class="block text-xs text-[#252f27] dark:text-slate-400 mb-1">Monthly Spend ($ USD):</label>
          <input type="number" step="0.1" id="modal-usd" class="w-full bg-[#ffffff] dark:bg-[#191a1c] border border-[#cbd5ce] dark:border-[#32363a] rounded-lg px-3 py-2 text-sm text-[#1c221e] dark:text-white mono">
        </div>
      </div>

      <div class="flex justify-end gap-2 pt-2">
        <button onclick="closeModal()" class="px-4 py-2 text-xs text-[#556358] hover:text-[#1c221e] dark:text-slate-400 dark:hover:text-white">Cancel</button>
        <button onclick="saveModal()" class="bg-[#0f765e] hover:bg-[#0c624e] text-white px-4 py-2 rounded-lg text-xs font-semibold">Save</button>
      </div>
    </div>
  </div>

  <script>
    let currentData = null;
    let activeFilter = 'all';
    let currentEditModelId = null;
    let keyConfigured = false;

    // Check API Key & Tier status on startup
    async function checkKeyStatus() {
      try {
        const res = await fetch('/api/key_status');
        const data = await res.json();
        keyConfigured = data.configured;
        
        const pillText = document.getElementById('api-status-text');
        const pillDot = document.getElementById('api-dot');
        const deleteBtn = document.getElementById('delete-key-btn');

        updateTierButtons(data.tier_mode || 'auto', data.active_tier || 'go-plus');

        if (data.configured) {
          deleteBtn.classList.remove('hidden');
          if (data.sync_state.status === 'ok') {
            pillDot.className = 'w-2 h-2 rounded-full bg-emerald-400 animate-pulse';
            pillText.innerText = 'Live: ' + data.masked_key;
            pillText.parentElement.title = data.sync_state.message || 'Connected';
          } else if (data.sync_state.status === 'degraded') {
            pillDot.className = 'w-2 h-2 rounded-full bg-amber-400 animate-pulse';
            pillText.innerText = 'Partial: ' + data.masked_key;
            pillText.parentElement.title = data.sync_state.message || 'Partial sync';
          } else if (data.sync_state.status === 'error') {
            pillDot.className = 'w-2 h-2 rounded-full bg-red-500';
            pillText.innerText = 'API Error: ' + (data.sync_state.error_code || '403');
            pillText.parentElement.title = data.sync_state.message || 'Sync error';
          } else {
            pillDot.className = 'w-2 h-2 rounded-full bg-indigo-400';
            pillText.innerText = 'Connected: ' + data.masked_key;
            pillText.parentElement.title = data.sync_state.message || 'Connected';
          }
        } else {
          deleteBtn.classList.add('hidden');
          pillDot.className = 'w-2 h-2 rounded-full bg-amber-400 animate-ping';
          pillText.innerText = 'No API key configured';
          
          // Auto prompt modal if no key configured
          if (!sessionStorage.getItem('modal_dismissed')) {
            openApiKeyModal();
          }
        }
      } catch (err) {
        console.error('Key status check error:', err);
      }
    }

    function updateTierButtons(tierMode, activeTier) {
      const btnAuto = document.getElementById('tier-btn-auto');
      const btnGo = document.getElementById('tier-btn-go');
      const btnPlus = document.getElementById('tier-btn-plus');
      const desc = document.getElementById('tier-status-desc');
      if (!btnAuto || !btnGo || !btnPlus) return;

      const activeClass = 'bg-[#1c221e] text-white border-[#1c221e] dark:bg-[#32363a] dark:border-[#42474c]';
      const inactiveClass = 'bg-[#f8fbf9] dark:bg-[#25292c] text-[#4d5950] dark:text-slate-300 border-[#d5ded7] dark:border-[#32363a]';

      btnAuto.className = `px-2.5 py-1.5 rounded-xl text-xs font-bold border transition text-center ${tierMode === 'auto' ? activeClass : inactiveClass}`;
      btnGo.className = `px-2.5 py-1.5 rounded-xl text-xs font-bold border transition text-center ${tierMode === 'go' ? activeClass : inactiveClass}`;
      btnPlus.className = `px-2.5 py-1.5 rounded-xl text-xs font-bold border transition text-center ${tierMode === 'go-plus' ? activeClass : inactiveClass}`;

      if (desc) {
        const currentTierLabel = activeTier === 'go-plus' ? 'Go Plus ($40)' : 'Go ($10)';
        if (tierMode === 'auto') {
          desc.innerText = `Auto-detect active: using ${currentTierLabel} limits based on OpenCode Cloud.`;
        } else {
          desc.innerText = `Manual override active: locked to ${currentTierLabel}.`;
        }
      }
    }

    async function setTierMode(mode) {
      try {
        const res = await fetch('/api/set_tier', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ tier_mode: mode })
        });
        const d = await res.json();
        updateTierButtons(d.tier_mode, d.active_tier);
        await fetchStatus();
      } catch (err) {
        console.error('Error setting tier:', err);
      }
    }

    function openApiKeyModal() {
      document.getElementById('api-key-modal').classList.remove('hidden');
      document.getElementById('api-key-input').focus();
    }

    function closeApiKeyModal() {
      document.getElementById('api-key-modal').classList.add('hidden');
      sessionStorage.setItem('modal_dismissed', 'true');
    }

    function toggleKeyVisibility() {
      const input = document.getElementById('api-key-input');
      const icon = document.getElementById('eye-icon');
      if (input.type === 'password') {
        input.type = 'text';
        icon.innerText = '🙈';
      } else {
        input.type = 'password';
        icon.innerText = '👁️';
      }
    }

    async function saveApiKey() {
      const input = document.getElementById('api-key-input');
      const errBox = document.getElementById('api-key-error');
      const saveBtn = document.getElementById('save-key-btn');
      const key = input.value.trim();

      if (!key) {
        errBox.innerText = 'Please enter your key (e.g. oc_sk_...)!';
        errBox.classList.remove('hidden');
        return;
      }

      errBox.classList.add('hidden');
      saveBtn.disabled = true;
      saveBtn.innerHTML = `<span>⏳ Connecting...</span>`;

      try {
        const res = await fetch('/api/save_key', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ api_key: key })
        });
        const resData = await res.json();
        
        saveBtn.disabled = false;
        saveBtn.innerHTML = `<span>💾 Save & Connect</span>`;

        if (resData.success) {
          input.value = '';
          closeApiKeyModal();
          checkKeyStatus();
          fetchStatus();
        } else {
          errBox.innerText = resData.error || 'Failed to save key.';
          errBox.classList.remove('hidden');
        }
      } catch (err) {
        saveBtn.disabled = false;
        saveBtn.innerHTML = `<span>💾 Save & Connect</span>`;
        errBox.innerText = 'Connection error: ' + err.message;
        errBox.classList.remove('hidden');
      }
    }

    async function deleteApiKey() {
      if (!confirm('Are you sure you want to delete the saved OpenCode API key?')) return;
      try {
        await fetch('/api/delete_key', { method: 'POST' });
        checkKeyStatus();
        closeApiKeyModal();
      } catch (err) {
        alert('Error deleting key: ' + err.message);
      }
    }

    async function triggerSyncNow() {
      const btn = document.getElementById('sync-btn');
      const label = document.getElementById('sync-btn-label');
      label.innerText = 'Syncing...';
      btn.disabled = true;

      try {
        await fetch('/api/sync_now', { method: 'POST' });
        await checkKeyStatus();
        await fetchStatus();
      } catch (err) {
        console.error('Sync error:', err);
      } finally {
        label.innerText = 'Sync';
        btn.disabled = false;
      }
    }

    function formatResetCountdown(isoDateStr) {
      if (!isoDateStr) return '--';
      const target = new Date(isoDateStr).getTime();
      const now = Date.now();
      const diffMs = target - now;
      if (diffMs <= 0) return 'Resetting...';

      const totalSecs = Math.floor(diffMs / 1000);
      const days = Math.floor(totalSecs / 86400);
      const hours = Math.floor((totalSecs % 86400) / 3600);
      const mins = Math.floor((totalSecs % 3600) / 60);

      if (days > 0) {
        return `${days}d ${hours}h`;
      } else if (hours > 0) {
        return `${hours}h ${mins}m`;
      } else {
        return `${mins}m`;
      }
    }

    function updateLiveMeters() {
      if (!currentData) return;

      // Update plan badge
      const planBadge = document.getElementById('plan-badge');
      if (planBadge && currentData.active_tier) {
        if (currentData.active_tier === 'go-plus') {
          planBadge.innerText = 'GO PLUS';
          planBadge.className = 'px-2 py-0.5 rounded-md text-[11px] font-black uppercase tracking-wider bg-indigo-500/20 text-indigo-400 border border-indigo-500/40';
        } else {
          planBadge.innerText = 'GO';
          planBadge.className = 'px-2 py-0.5 rounded-md text-[11px] font-black uppercase tracking-wider bg-emerald-500/20 text-emerald-400 border border-emerald-500/40';
        }
      }

      // Update costs
      if (currentData.cost_summary) {
        const todayEl = document.getElementById('header-today-usd');
        if (todayEl) todayEl.innerText = `$${Number(currentData.cost_summary.today_usd || 0).toFixed(1)}`;
        const mtdEl = document.getElementById('header-total-usd');
        if (mtdEl) mtdEl.innerText = `$${Number(currentData.cost_summary.mtd_usd || 0).toFixed(1)}`;
      }

      // Update official Go meters
      const gs = currentData.go_status;
      if (!gs) return;

      const renewsEl = document.getElementById('go-renews-label');
      if (renewsEl && gs.renews_label) renewsEl.innerText = gs.renews_label;

      function updateMeterPie(pieId, pct) {
        const pieEl = document.getElementById(pieId);
        if (!pieEl) return;
        const clamped = Math.max(0, Math.min(100, pct || 0));
        pieEl.setAttribute('stroke-dasharray', `${clamped}, 100`);
        let color = 'stroke-emerald-500';
        if (clamped >= 85) color = 'stroke-red-500';
        else if (clamped >= 70) color = 'stroke-amber-400';
        pieEl.setAttribute('class', `${color} transition-all duration-500`);
      }

      function getMeterTextColor(pct) {
        if (pct >= 85) return 'text-red-600 dark:text-red-400';
        if (pct >= 70) return 'text-amber-600 dark:text-amber-400';
        return 'text-[#0f765e] dark:text-emerald-400';
      }

      if (gs.rolling) {
        const resetEl = document.getElementById('meter-rolling-reset');
        const pctEl = document.getElementById('meter-rolling-pct');
        if (resetEl) resetEl.innerText = formatResetCountdown(gs.rolling.resets_at);
        if (pctEl) {
          pctEl.innerText = `${Number(gs.rolling.pct || 0).toFixed(1)}% used`;
          pctEl.className = `mono font-black text-[19px] sm:text-[21px] shrink-0 ${getMeterTextColor(gs.rolling.pct)}`;
        }
        updateMeterPie('meter-rolling-pie', gs.rolling.pct);
      }

      if (gs.weekly) {
        const resetEl = document.getElementById('meter-weekly-reset');
        const pctEl = document.getElementById('meter-weekly-pct');
        if (resetEl) resetEl.innerText = formatResetCountdown(gs.weekly.resets_at);
        if (pctEl) {
          pctEl.innerText = `${Number(gs.weekly.pct || 0).toFixed(1)}% used`;
          pctEl.className = `mono font-black text-[19px] sm:text-[21px] shrink-0 ${getMeterTextColor(gs.weekly.pct)}`;
        }
        updateMeterPie('meter-weekly-pie', gs.weekly.pct);
      }

      if (gs.monthly) {
        const resetEl = document.getElementById('meter-monthly-reset');
        const pctEl = document.getElementById('meter-monthly-pct');
        if (resetEl) resetEl.innerText = formatResetCountdown(gs.monthly.resets_at);
        if (pctEl) {
          pctEl.innerText = `${Number(gs.monthly.pct || 0).toFixed(1)}% used`;
          pctEl.className = `mono font-black text-[19px] sm:text-[21px] shrink-0 ${getMeterTextColor(gs.monthly.pct)}`;
        }
        updateMeterPie('meter-monthly-pie', gs.monthly.pct);
      }
    }

    async function fetchStatus() {
      try {
        const res = await fetch('/api/status');
        const data = await res.json();
        currentData = data;
        renderDashboard(data);
      } catch (err) {
        console.error('Fetch error:', err);
      }
    }

    function renderDashboard(data) {
      const serverTimeEl = document.getElementById('server-time');
      if (serverTimeEl) {
        serverTimeEl.innerText = data.server_time.split(' ')[1];
      }
      
      const totalSpent = data.models.reduce((sum, m) => sum + (m.current_spent_usd || 0), 0);
      const headerTotal = document.getElementById('header-total-usd');
      if (headerTotal) {
        headerTotal.innerText = '$' + totalSpent.toFixed(1);
      }

      updateLiveMeters();

      const alertBanner = document.getElementById('alert-banner');
      const alertList = document.getElementById('alert-list');

      if (data.alerts && data.alerts.length > 0) {
        alertBanner.classList.remove('hidden');
        alertList.innerHTML = data.alerts.map(a => `
          <div class="flex items-center justify-between p-1.5 rounded bg-red-900/40 border border-red-700/60 text-xs">
            <span><strong>${a.model}:</strong> ${a.msg}</span>
            <span class="mono font-bold text-red-300">${Number(a.pct || 0).toFixed(1)}%</span>
          </div>
        `).join('');
      } else {
        alertBanner.classList.add('hidden');
      }

      const grid = document.getElementById('models-grid');
      grid.innerHTML = data.models
        .filter(m => activeFilter === 'all' || (m.categories ? m.categories.includes(activeFilter) : m.category === activeFilter))
        .map(m => createCardHtml(m))
        .join('');
    }

    function getModelLogoHtml(id) {
      const cleanId = (id || '').toLowerCase();

      // 1. Kimi K3.1 Pro (Moonshot AI / Kimi)
      if (cleanId.includes('kimi')) {
        return `
          <span class="inline-flex items-center justify-center w-5 h-5 shrink-0" title="Moonshot Kimi" aria-hidden="true">
            <svg class="w-full h-full drop-shadow-[0_1px_2px_rgba(0,0,0,0.08)] dark:drop-shadow-[0_0_6px_rgba(56,189,248,0.3)] transition-all" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
              <path d="M21.846 0a1.923 1.923 0 110 3.846H20.15a.226.226 0 01-.227-.226V1.923C19.923.861 20.784 0 21.846 0z" class="fill-[#1783FF] dark:fill-[#38BDF8]"/>
              <path d="M11.065 11.199l7.257-7.2c.137-.136.06-.41-.116-.41H14.3a.164.164 0 00-.117.051l-7.82 7.756c-.122.12-.302.013-.302-.179V3.82c0-.127-.083-.23-.185-.23H3.186c-.103 0-.186.103-.186.23V19.77c0 .128.083.23.186.23h2.69c.103 0 .186-.102.186-.23v-3.25c0-.069.025-.135.069-.178l2.424-2.406a.158.158 0 01.205-.023l6.484 4.772a7.677 7.677 0 003.453 1.283c.108.012.2-.095.2-.23v-3.06c0-.117-.07-.212-.164-.227a5.028 5.028 0 01-2.027-.807l-5.613-4.064c-.117-.078-.132-.279-.028-.381z" class="fill-[#0F172A] dark:fill-slate-100"/>
            </svg>
          </span>
        `;
      }

      // 2. Gemini 4 Argon (Google Gemini)
      if (cleanId.includes('gemini')) {
        return `
          <span class="inline-flex items-center justify-center w-5 h-5 shrink-0" title="Google Gemini" aria-hidden="true">
            <svg class="w-full h-full drop-shadow-[0_1px_2px_rgba(0,0,0,0.08)] dark:drop-shadow-[0_0_8px_rgba(56,189,248,0.3)] transition-all" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
              <defs>
                <linearGradient id="gem-g" x1="7" y1="15.5" x2="11" y2="12" gradientUnits="userSpaceOnUse"><stop stop-color="#08B962"/><stop offset="1" stop-color="#08B962" stop-opacity="0"/></linearGradient>
                <linearGradient id="gem-r" x1="8" y1="5.5" x2="11.5" y2="11" gradientUnits="userSpaceOnUse"><stop stop-color="#F94543"/><stop offset="1" stop-color="#F94543" stop-opacity="0"/></linearGradient>
                <linearGradient id="gem-y" x1="3.5" y1="13.5" x2="17.5" y2="12" gradientUnits="userSpaceOnUse"><stop stop-color="#FABC12"/><stop offset="0.46" stop-color="#FABC12" stop-opacity="0"/></linearGradient>
              </defs>
              <path d="M20.616 10.835a14.147 14.147 0 01-4.45-3.001 14.111 14.111 0 01-3.678-6.452.503.503 0 00-.975 0 14.134 14.134 0 01-3.679 6.452 14.155 14.155 0 01-4.45 3.001c-.65.28-1.318.505-2.002.678a.502.502 0 000 .975c.684.172 1.35.397 2.002.677a14.147 14.147 0 014.45 3.001 14.112 14.112 0 013.679 6.453.502.502 0 00.975 0c.172-.685.397-1.351.677-2.003a14.145 14.145 0 013.001-4.45 14.113 14.113 0 016.453-3.678.503.503 0 000-.975 13.245 13.245 0 01-2.003-.678z" fill="#3186FF"/>
              <path d="M20.616 10.835a14.147 14.147 0 01-4.45-3.001 14.111 14.111 0 01-3.678-6.452.503.503 0 00-.975 0 14.134 14.134 0 01-3.679 6.452 14.155 14.155 0 01-4.45 3.001c-.65.28-1.318.505-2.002.678a.502.502 0 000 .975c.684.172 1.35.397 2.002.677a14.147 14.147 0 014.45 3.001 14.112 14.112 0 013.679 6.453.502.502 0 00.975 0c.172-.685.397-1.351.677-2.003a14.145 14.145 0 013.001-4.45 14.113 14.113 0 016.453-3.678.503.503 0 000-.975 13.245 13.245 0 01-2.003-.678z" fill="url(#gem-g)"/>
              <path d="M20.616 10.835a14.147 14.147 0 01-4.45-3.001 14.111 14.111 0 01-3.678-6.452.503.503 0 00-.975 0 14.134 14.134 0 01-3.679 6.452 14.155 14.155 0 01-4.45 3.001c-.65.28-1.318.505-2.002.678a.502.502 0 000 .975c.684.172 1.35.397 2.002.677a14.147 14.147 0 014.45 3.001 14.112 14.112 0 013.679 6.453.502.502 0 00.975 0c.172-.685.397-1.351.677-2.003a14.145 14.145 0 013.001-4.45 14.113 14.113 0 016.453-3.678.503.503 0 000-.975 13.245 13.245 0 01-2.003-.678z" fill="url(#gem-r)"/>
              <path d="M20.616 10.835a14.147 14.147 0 01-4.45-3.001 14.111 14.111 0 01-3.678-6.452.503.503 0 00-.975 0 14.134 14.134 0 01-3.679 6.452 14.155 14.155 0 01-4.45 3.001c-.65.28-1.318.505-2.002.678a.502.502 0 000 .975c.684.172 1.35.397 2.002.677a14.147 14.147 0 014.45 3.001 14.112 14.112 0 013.679 6.453.502.502 0 00.975 0c.172-.685.397-1.351.677-2.003a14.145 14.145 0 013.001-4.45 14.113 14.113 0 016.453-3.678.503.503 0 000-.975 13.245 13.245 0 01-2.003-.678z" fill="url(#gem-y)"/>
            </svg>
          </span>
        `;
      }

      // 3. GLM-5.3 (Zhipu AI / ChatGLM)
      if (cleanId.includes('glm')) {
        return `
          <span class="inline-flex items-center justify-center w-5 h-5 shrink-0" title="Zhipu GLM" aria-hidden="true">
            <svg class="w-full h-full drop-shadow-[0_1px_2px_rgba(0,0,0,0.08)] dark:drop-shadow-[0_0_6px_rgba(99,102,241,0.35)] transition-all" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
              <defs>
                <linearGradient id="glm-g" x1="0%" y1="0%" x2="100%" y2="100%"><stop offset="0%" stop-color="#6366F1"/><stop offset="100%" stop-color="#38BDF8"/></linearGradient>
              </defs>
              <path d="M9.917 2c4.906 0 10.178 3.947 8.93 10.58-.014.07-.037.14-.057.21l-.003-.277c-.083-3-1.534-8.934-8.87-8.934-3.393 0-8.137 3.054-7.93 8.158-.04 4.778 3.555 8.4 7.95 8.332l.073-.001c1.2-.033 2.763-.429 3.1-1.657.063-.031.26.534.268.598.048.256.112.369.192.34.981-.348 2.286-1.222 1.952-2.38-.176-.61-1.775-.147-1.921-.347.418-.979 2.234-.926 3.153-.716.443.102.657.38 1.012.442.29.052.981-.2.96.242-1.5 3.042-4.893 5.41-8.808 5.41C3.654 22 0 16.574 0 11.737 0 5.947 4.959 2 9.917 2z" fill="url(#glm-g)"/>
            </svg>
          </span>
        `;
      }

      // 4 & 8. MiMo-V2.6-Pro & MiMo-V2.6-Flash (Xiaomi)
      if (cleanId.includes('mimo') || cleanId.includes('xiaomi')) {
        return `
          <span class="inline-flex items-center justify-center w-5 h-5 shrink-0 rounded-[5px] overflow-hidden shadow-sm border border-black/5 dark:border-white/15 dark:shadow-[0_0_8px_rgba(255,105,0,0.25)] transition-all" title="Xiaomi MiMo" aria-hidden="true">
            <svg class="w-full h-full" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
              <rect width="24" height="24" rx="5" fill="#FF6900"/>
              <path d="M4.906 7.405h5.624c1.47 0 3.007.068 3.764.827.746.746.827 2.233.83 3.676v4.54a.15.15 0 0 1-.152.147h-1.947a.15.15 0 0 1-.152-.148V11.83c-.002-.806-.048-1.634-.464-2.051-.358-.36-1.026-.441-1.72-.458H7.158a.15.15 0 0 0-.151.147v6.98a.15.15 0 0 1-.152.148H4.906a.15.15 0 0 1-.15-.148V7.554a.15.15 0 0 1 .15-.149zm12.131 0h1.949a.15.15 0 0 1 .15.15v8.892a.15.15 0 0 1-.15.148h-1.949a.15.15 0 0 1-.151-.148V7.554a.15.15 0 0 1 .151-.149zM8.92 10.948h2.046c.083 0 .15.066.15.147v5.352a.15.15 0 0 1-.15.148H8.92a.15.15 0 0 1-.152-.148v-5.352a.15.15 0 0 1 .152-.147Z" fill="#FFFFFF"/>
            </svg>
          </span>
        `;
      }

      // 6. DeepSeek V4.1 Flash (DeepSeek Flash)
      if (cleanId === 'deepseek-v4-1-flash' || (cleanId.includes('deepseek') && cleanId.includes('flash'))) {
        return `
          <span class="inline-flex items-center justify-center w-5 h-5 shrink-0" title="DeepSeek V4.1 Flash" aria-hidden="true">
            <svg class="w-full h-full drop-shadow-[0_1px_2px_rgba(0,0,0,0.08)] dark:drop-shadow-[0_0_6px_rgba(56,189,248,0.4)] transition-all" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
              <path d="M23.748 4.482c-.254-.124-.364.113-.512.234-.051.039-.094.09-.137.136-.372.397-.806.657-1.373.626-.829-.046-1.537.214-2.163.848-.133-.782-.575-1.248-1.247-1.548-.352-.156-.708-.311-.955-.65-.172-.241-.219-.51-.305-.774-.055-.16-.11-.323-.293-.35-.2-.031-.278.136-.356.276-.313.572-.434 1.202-.422 1.84.027 1.436.633 2.58 1.838 3.393.137.093.172.187.129.323-.082.28-.18.552-.266.833-.055.179-.137.217-.329.14a5.526 5.526 0 01-1.736-1.18c-.857-.828-1.631-1.742-2.597-2.458a11.365 11.365 0 00-.689-.471c-.985-.957.13-1.743.388-1.836.27-.098.093-.432-.779-.428-.872.004-1.67.295-2.687.684a3.055 3.055 0 01-.465.137 9.597 9.597 0 00-2.883-.102c-1.885.21-3.39 1.102-4.497 2.623C.082 8.606-.231 10.684.152 12.85c.403 2.284 1.569 4.175 3.36 5.653 1.858 1.533 3.997 2.284 6.438 2.14 1.482-.085 3.133-.284 4.994-1.86.47.234.962.327 1.78.397.63.059 1.236-.03 1.705-.128.735-.156.684-.837.419-.961-2.155-1.004-1.682-.595-2.113-.926 1.096-1.296 2.746-2.642 3.392-7.003.05-.347.007-.565 0-.845-.004-.17.035-.237.23-.256a4.173 4.173 0 001.545-.475c1.396-.763 1.96-2.015 2.093-3.517.02-.23-.004-.467-.247-.588zM11.581 18c-2.089-1.642-3.102-2.183-3.52-2.16-.392.024-.321.471-.235.763.09.288.207.486.371.739.114.167.192.416-.113.603-.673.416-1.842-.14-1.897-.167-1.361-.802-2.5-1.86-3.301-3.307-.774-1.393-1.224-2.887-1.298-4.482-.02-.386.093-.522.477-.592a4.696 4.696 0 011.529-.039c2.132.312 3.946 1.265 5.468 2.774.868.86 1.525 1.887 2.202 2.891.72 1.066 1.494 2.082 2.48 2.914.348.292.625.514.891.677-.802.09-2.14.11-3.054-.614zm1-6.44a.306.306 0 01.415-.287.302.302 0 01.2.288.306.306 0 01-.31.307.303.303 0 01-.304-.308zm3.11 1.596c-.2.081-.399.151-.59.16a1.245 1.245 0 01-.798-.254c-.274-.23-.47-.358-.552-.758a1.73 1.73 0 01.016-.588c.07-.327-.008-.537-.239-.727-.187-.156-.426-.199-.688-.199a.559.559 0 01-.254-.078c-.11-.054-.2-.19-.114-.358.028-.054.16-.186.192-.21.356-.202.767-.136 1.146.016.352.144.618.408 1.001.782.391.451.462.576.685.914.176.265.336.537.445.848.067.195-.019.354-.25.452z" class="fill-[#0284C7] dark:fill-[#38BDF8]"/>
            </svg>
          </span>
        `;
      }

      // 5. DeepSeek V4 Pro (DeepSeek)
      if (cleanId.includes('deepseek')) {
        return `
          <span class="inline-flex items-center justify-center w-5 h-5 shrink-0" title="DeepSeek V4 Pro" aria-hidden="true">
            <svg class="w-full h-full drop-shadow-[0_1px_2px_rgba(0,0,0,0.08)] dark:drop-shadow-[0_0_6px_rgba(77,107,254,0.35)] transition-all" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
              <path d="M23.748 4.482c-.254-.124-.364.113-.512.234-.051.039-.094.09-.137.136-.372.397-.806.657-1.373.626-.829-.046-1.537.214-2.163.848-.133-.782-.575-1.248-1.247-1.548-.352-.156-.708-.311-.955-.65-.172-.241-.219-.51-.305-.774-.055-.16-.11-.323-.293-.35-.2-.031-.278.136-.356.276-.313.572-.434 1.202-.422 1.84.027 1.436.633 2.58 1.838 3.393.137.093.172.187.129.323-.082.28-.18.552-.266.833-.055.179-.137.217-.329.14a5.526 5.526 0 01-1.736-1.18c-.857-.828-1.631-1.742-2.597-2.458a11.365 11.365 0 00-.689-.471c-.985-.957.13-1.743.388-1.836.27-.098.093-.432-.779-.428-.872.004-1.67.295-2.687.684a3.055 3.055 0 01-.465.137 9.597 9.597 0 00-2.883-.102c-1.885.21-3.39 1.102-4.497 2.623C.082 8.606-.231 10.684.152 12.85c.403 2.284 1.569 4.175 3.36 5.653 1.858 1.533 3.997 2.284 6.438 2.14 1.482-.085 3.133-.284 4.994-1.86.47.234.962.327 1.78.397.63.059 1.236-.03 1.705-.128.735-.156.684-.837.419-.961-2.155-1.004-1.682-.595-2.113-.926 1.096-1.296 2.746-2.642 3.392-7.003.05-.347.007-.565 0-.845-.004-.17.035-.237.23-.256a4.173 4.173 0 001.545-.475c1.396-.763 1.96-2.015 2.093-3.517.02-.23-.004-.467-.247-.588zM11.581 18c-2.089-1.642-3.102-2.183-3.52-2.16-.392.024-.321.471-.235.763.09.288.207.486.371.739.114.167.192.416-.113.603-.673.416-1.842-.14-1.897-.167-1.361-.802-2.5-1.86-3.301-3.307-.774-1.393-1.224-2.887-1.298-4.482-.02-.386.093-.522.477-.592a4.696 4.696 0 011.529-.039c2.132.312 3.946 1.265 5.468 2.774.868.86 1.525 1.887 2.202 2.891.72 1.066 1.494 2.082 2.48 2.914.348.292.625.514.891.677-.802.09-2.14.11-3.054-.614zm1-6.44a.306.306 0 01.415-.287.302.302 0 01.2.288.306.306 0 01-.31.307.303.303 0 01-.304-.308zm3.11 1.596c-.2.081-.399.151-.59.16a1.245 1.245 0 01-.798-.254c-.274-.23-.47-.358-.552-.758a1.73 1.73 0 01.016-.588c.07-.327-.008-.537-.239-.727-.187-.156-.426-.199-.688-.199a.559.559 0 01-.254-.078c-.11-.054-.2-.19-.114-.358.028-.054.16-.186.192-.21.356-.202.767-.136 1.146.016.352.144.618.408 1.001.782.391.451.462.576.685.914.176.265.336.537.445.848.067.195-.019.354-.25.452z" class="fill-[#2B66FF] dark:fill-[#587BFE]"/>
            </svg>
          </span>
        `;
      }

      // 7. Claude Haiku 5.5 (Anthropic Claude)
      if (cleanId.includes('claude') || cleanId.includes('haiku') || cleanId.includes('anthropic')) {
        return `
          <span class="inline-flex items-center justify-center w-5 h-5 shrink-0" title="Anthropic Claude" aria-hidden="true">
            <svg class="w-full h-full drop-shadow-[0_1px_2px_rgba(0,0,0,0.08)] dark:drop-shadow-[0_0_6px_rgba(232,146,116,0.35)] transition-all" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
              <path d="M4.709 15.955l4.72-2.647.08-.23-.08-.128H9.2l-.79-.048-2.698-.073-2.339-.097-2.266-.122-.571-.121L0 11.784l.055-.352.48-.321.686.06 1.52.103 2.278.158 1.652.097 2.449.255h.389l.055-.157-.134-.098-.103-.097-2.358-1.596-2.552-1.688-1.336-.972-.724-.491-.364-.462-.158-1.008.656-.722.881.06.225.061.893.686 1.908 1.476 2.491 1.833.365.304.145-.103.019-.073-.164-.274-1.355-2.446-1.446-2.49-.644-1.032-.17-.619a2.97 2.97 0 01-.104-.729L6.283.134 6.696 0l.996.134.42.364.62 1.414 1.002 2.229 1.555 3.03.456.898.243.832.091.255h.158V9.01l.128-1.706.237-2.095.23-2.695.08-.76.376-.91.747-.492.584.28.48.685-.067.444-.286 1.851-.559 2.903-.364 1.942h.212l.243-.242.985-1.306 1.652-2.064.73-.82.85-.904.547-.431h1.033l.76 1.129-.34 1.166-1.064 1.347-.881 1.142-1.264 1.7-.79 1.36.073.11.188-.02 2.856-.606 1.543-.28 1.841-.315.833.388.091.395-.328.807-1.969.486-2.309.462-3.439.813-.042.03.049.061 1.549.146.662.036h1.622l3.02.225.79.522.474.638-.079.485-1.215.62-1.64-.389-3.829-.91-1.312-.329h-.182v.11l1.093 1.068 2.006 1.81 2.509 2.33.127.578-.322.455-.34-.049-2.205-1.657-.851-.747-1.926-1.62h-.128v.17l.444.649 2.345 3.521.122 1.08-.17.353-.608.213-.668-.122-1.374-1.925-1.415-2.167-1.143-1.943-.14.08-.674 7.254-.316.37-.729.28-.607-.461-.322-.747.322-1.476.389-1.924.315-1.53.286-1.9.17-.632-.012-.042-.14.018-1.434 1.967-2.18 2.945-1.726 1.845-.414.164-.717-.37.067-.662.401-.589 2.388-3.036 1.44-1.882.93-1.086-.006-.158h-.055L4.132 18.56l-1.13.146-.487-.456.061-.746.231-.243 1.908-1.312-.006.006z" class="fill-[#CC785C] dark:fill-[#E89274]"/>
            </svg>
          </span>
        `;
      }

      // 9. BEAM Free (Reflection AI / Beam)
      if (cleanId.includes('beam') || cleanId.includes('reflection')) {
        return `
          <span class="inline-flex items-center justify-center w-5 h-5 shrink-0" title="Reflection Beam" aria-hidden="true">
            <svg class="w-full h-full drop-shadow-[0_1px_2px_rgba(0,0,0,0.08)] dark:drop-shadow-[0_0_6px_rgba(6,182,212,0.35)] transition-all" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
              <defs>
                <linearGradient id="beam-grad" x1="0%" y1="0%" x2="100%" y2="100%"><stop offset="0%" stop-color="#A78BFA"/><stop offset="100%" stop-color="#22D3EE"/></linearGradient>
              </defs>
              <circle cx="7.5" cy="12" r="5" stroke="url(#beam-grad)" stroke-width="2.2" class="fill-none dark:fill-violet-500/10"/>
              <circle cx="16.5" cy="12" r="5" fill="url(#beam-grad)"/>
            </svg>
          </span>
        `;
      }

      // Fallback
      return `
        <span class="inline-flex items-center justify-center w-5 h-5 shrink-0 text-slate-500" aria-hidden="true">
          <svg class="w-full h-full" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 10V3L4 14h7v7l9-11h-7z"/>
          </svg>
        </span>
      `;
    }

    function createCardHtml(m) {
      let riskGlow = 'border-[#d6dfd8] dark:border-[#32363a] shadow-[0_2px_6px_rgba(25,35,28,0.05)] hover:shadow-[0_4px_14px_rgba(25,35,28,0.08)] dark:shadow-none';
      let badgeColor = 'bg-[#e4ece6] text-[#0f765e] border-[#c8d4cb] dark:bg-emerald-950 dark:text-emerald-400 dark:border-emerald-800';
      if (m.risk === 'CRITICAL') {
        riskGlow = 'border-red-400 dark:border-red-600 shadow-[0_0_15px_rgba(239,68,68,0.2)] dark:shadow-[0_0_20px_rgba(239,68,68,0.35)]';
        badgeColor = 'bg-red-100 text-red-800 border-red-300 dark:bg-red-950 dark:text-red-300 dark:border-red-700';
      } else if (m.risk === 'WARNING') {
        riskGlow = 'border-amber-400 dark:border-amber-600 shadow-[0_0_12px_rgba(234,179,8,0.2)] dark:shadow-[0_0_15px_rgba(234,179,8,0.25)]';
        badgeColor = 'bg-amber-100 text-amber-800 border-amber-300 dark:bg-amber-950 dark:text-amber-300 dark:border-amber-700';
      }

      const isUnlimited5h = m.is_unlimited_5h;
      const isUnlimitedUsd = m.is_unlimited_usd;

      let resetStr = 'Clean window';
      if (isUnlimited5h) {
        resetStr = 'N/A';
      } else if (m.reset_mins > 0) {
        if (m.reset_mins >= 60) {
          const h = Math.floor(m.reset_mins / 60);
          const rem = m.reset_mins % 60;
          resetStr = rem > 0 ? `in ~${h}h ${rem}m` : `in ~${h}h`;
        } else {
          resetStr = `in ~${m.reset_mins} mins`;
        }
      }

      return `
        <div class="bg-[#faf9f6] dark:bg-[#25292c] rounded-2xl border p-4 sm:p-4.5 transition-all duration-200 ${riskGlow}">
          <!-- Title row with brand logo, model name, and dynamic badges -->
          <div class="flex items-center justify-between gap-2 mb-2">
            <div class="flex items-center gap-2 min-w-0">
              ${getModelLogoHtml(m.id)}
              <h3 class="font-bold text-[18px] sm:text-[19px] text-[#151c17] dark:text-white tracking-tight truncate" title="${m.name}">${m.name}</h3>
            </div>
            <div class="flex items-center gap-1.5 shrink-0">
              ${m.is_limited_time && m.promo_bonus > 1 ? `<span class="text-xs font-bold px-2 py-0.5 rounded-md bg-amber-100 text-amber-800 border border-amber-300 dark:bg-amber-950/80 dark:text-amber-300 dark:border-amber-700/60 mono shrink-0" title="Limited Time Promotion Active">⚡ ${m.promo_bonus}× Promo</span>` : (m.is_limited_time && !m.is_unlimited_5h ? `<span class="text-xs font-bold px-2 py-0.5 rounded-md bg-amber-100 text-amber-800 border border-amber-300 dark:bg-amber-950/80 dark:text-amber-300 dark:border-amber-700/60 mono shrink-0" title="Limited Time Promotion Active">⚡ Promo</span>` : '')}
              ${m.risk !== 'OK' ? `<span class="text-xs font-bold px-2 py-0.5 rounded border mono shrink-0 ${badgeColor}">${m.risk}</span>` : ''}
            </div>
          </div>

          <!-- Progress 1: 5-Hour Sliding Window -->
          <div class="space-y-1.5">
            <div class="flex items-center justify-between text-xs sm:text-[13px] font-semibold gap-1.5">
              <span class="text-xs sm:text-[13px] font-bold uppercase tracking-wider text-[#556358] dark:text-slate-400 flex items-center gap-1.5 shrink-0">
                ⏱️ 5h Rolling Usage
              </span>
              <span class="mono text-[15px] sm:text-[16px] font-black tracking-tight whitespace-nowrap text-right ${m.pct_5h >= 85 ? 'text-red-600 dark:text-red-400' : (m.pct_5h >= 70 ? 'text-amber-600 dark:text-amber-400' : 'text-[#1c221e] dark:text-slate-100')}">
                ${isUnlimited5h ? '∞ Unlimited' : `${m.current_req_5h} / ${m.limit_5h_req} (${Number(m.pct_5h || 0).toFixed(1)}%)`}
              </span>
            </div>
            <div class="w-full bg-[#e5ece7] dark:bg-[#191a1c] border border-[#d7dfd9] dark:border-[#32363a]/50 rounded-full h-3.5 sm:h-4 overflow-hidden shadow-inner">
              <div class="h-full rounded-full transition-all duration-300 ${getBarColor(m.pct_5h)}" style="width: ${Math.min(100, m.pct_5h)}%"></div>
            </div>
            <div class="text-[14px] sm:text-[15px] text-[#556358] dark:text-slate-400 pt-0.5">
              Reset: <strong class="mono text-[#1c221e] dark:text-slate-200 font-bold text-[15.5px] sm:text-[16px]">${resetStr}</strong>
            </div>
          </div>

          <!-- Progress 2: Monthly Spend Allowance -->
          <div class="space-y-1.5 mt-2.5 pt-2.5 border-t border-[#e5eae4] dark:border-[#32363a]/70">
            <div class="flex items-center justify-between text-xs sm:text-[13px] font-semibold gap-1.5">
              <span class="text-xs sm:text-[13px] font-bold uppercase tracking-wider text-[#556358] dark:text-slate-400 flex items-center gap-1.5 shrink-0">
                💰 Month to Date
              </span>
              <span class="mono text-[14.5px] sm:text-[15.5px] font-black tracking-tight whitespace-nowrap text-right ${m.pct_usd >= 85 ? 'text-red-600 dark:text-red-400' : (m.pct_usd >= 70 ? 'text-amber-600 dark:text-amber-400' : 'text-[#1c221e] dark:text-slate-100')}">
                ${isUnlimitedUsd ? '$0 (Free)' : `$${Number(m.current_spent_usd || 0).toFixed(1)} / $${m.limit_monthly_usd % 1 === 0 ? Math.round(m.limit_monthly_usd) : Number(m.limit_monthly_usd).toFixed(1)} (${Number(m.pct_usd || 0).toFixed(1)}%)`}
              </span>
            </div>
            <div class="w-full bg-[#e5ece7] dark:bg-[#191a1c] border border-[#d7dfd9] dark:border-[#32363a]/50 rounded-full h-3.5 sm:h-4 overflow-hidden shadow-inner">
              <div class="h-full rounded-full transition-all duration-300 ${getBarColor(m.pct_usd)}" style="width: ${Math.min(100, m.pct_usd)}%"></div>
            </div>
          </div>
        </div>
      `;
    }

    function getBarColor(pct) {
      if (pct >= 85) return 'bg-red-500';
      if (pct >= 70) return 'bg-amber-400';
      return 'bg-emerald-500';
    }

    function filterCards(category, btn) {
      activeFilter = category;
      document.querySelectorAll('.filter-btn').forEach(b => {
        b.classList.remove('active', 'bg-[#1c221e]', 'dark:bg-[#32363a]', 'text-white', 'border-[#1c221e]');
        b.classList.add('bg-[#f8fbf9]', 'dark:bg-[#25292c]', 'text-[#4d5950]', 'dark:text-slate-300', 'border-[#d5ded7]');
      });
      const targetBtn = btn || (typeof event !== 'undefined' && event ? event.target : null);
      if (targetBtn) {
        targetBtn.classList.remove('bg-[#f8fbf9]', 'dark:bg-[#25292c]', 'text-[#4d5950]', 'dark:text-slate-300', 'border-[#d5ded7]');
        targetBtn.classList.add('active', 'bg-[#1c221e]', 'dark:bg-[#32363a]', 'text-white', 'border-[#1c221e]');
      }
      if (currentData) renderDashboard(currentData);
    }

    async function recordHit(modelId, count) {
      await fetch('/api/record', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ model: modelId, count: count, dollars: count * 0.02 })
      });
      fetchStatus();
    }

    function openModal(modelId) {
      currentEditModelId = modelId;
      const model = currentData.models.find(m => m.id === modelId);
      if (!model) return;
      document.getElementById('modal-model-name').innerText = model.name + ' Settings';
      document.getElementById('modal-req').value = model.current_req_5h;
      document.getElementById('modal-usd').value = Number(model.current_spent_usd || 0).toFixed(1);
      document.getElementById('edit-modal').classList.remove('hidden');
    }

    function closeModal() {
      document.getElementById('edit-modal').classList.add('hidden');
      currentEditModelId = null;
    }

    async function saveModal() {
      if (!currentEditModelId) return;
      const req = document.getElementById('modal-req').value;
      const usd = document.getElementById('modal-usd').value;
      await fetch('/api/update', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          model: currentEditModelId,
          req_5h: req,
          spent_usd: usd
        })
      });
      closeModal();
      fetchStatus();
    }

    function applyTheme(theme) {
      const root = document.documentElement;
      const isDark = theme === 'dark' || (theme === 'system' && window.matchMedia('(prefers-color-scheme: dark)').matches);
      if (isDark) {
        root.classList.add('dark');
      } else {
        root.classList.remove('dark');
      }

      ['system', 'light', 'dark'].forEach(t => {
        const btn = document.getElementById('theme-btn-' + t);
        if (!btn) return;
        if (t === theme) {
          btn.className = 'p-1.5 rounded-lg transition shadow-sm bg-[#ffffff] dark:bg-[#32363a] text-[#0f765e] dark:text-indigo-300 font-semibold';
        } else {
          btn.className = 'p-1.5 rounded-lg transition text-[#556358] hover:text-[#1c221e] dark:text-slate-400 dark:hover:text-slate-200';
        }
      });
    }

    function setTheme(theme) {
      localStorage.setItem('theme_preference', theme);
      applyTheme(theme);
    }

    window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', () => {
      const pref = localStorage.getItem('theme_preference') || 'dark';
      if (pref === 'system') applyTheme('system');
    });

    // Initialize
    const savedTheme = localStorage.getItem('theme_preference') || 'dark';
    applyTheme(savedTheme);
    checkKeyStatus();
    fetchStatus();
    setInterval(fetchStatus, 4000);
    setInterval(checkKeyStatus, 15000);
    setInterval(updateLiveMeters, 1000);
  </script>
</body>
</html>
"""

def run():
    socketserver.TCPServer.allow_reuse_address = True
    handler = MonitorHandler

    # Start background synchronization worker thread
    sync_thread = threading.Thread(target=sync_engine.background_worker, daemon=True)
    sync_thread.start()

    with socketserver.TCPServer(("127.0.0.1", PORT), handler) as httpd:
        print(f"==================================================")
        print(f"🚀 OpenCode GO & OpenAI v6 Monitor Live!")
        print(f"🌐 Dashboard URL: http://localhost:{PORT}")
        print(f"🔑 Live API Sync Engine (Option 3): READY")
        print(f"==================================================")
        httpd.serve_forever()

if __name__ == "__main__":
    run()
