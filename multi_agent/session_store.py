"""
session_store.py — lightweight JSON-backed session persistence.
Stores task, agent context, chat history, and metadata for every run.
"""
import json
import os
import time
import uuid

SESSIONS_FILE = os.path.join(os.path.dirname(__file__), "sessions.json")


def _load_raw() -> dict:
    if os.path.exists(SESSIONS_FILE):
        try:
            with open(SESSIONS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def _save_raw(sessions: dict):
    with open(SESSIONS_FILE, "w", encoding="utf-8") as f:
        json.dump(sessions, f, indent=2, ensure_ascii=False)


def _safe_context(ctx: dict) -> dict:
    """Strip non-serialisable / oversized fields before saving."""
    safe = {}
    for k, v in ctx.items():
        if k == "file_analysis":
            # Drop the chart base64 (can be MBs) — keep summary + insights
            fa = dict(v) if isinstance(v, dict) else {}
            fa.pop("chart_b64", None)
            safe[k] = fa
        else:
            try:
                json.dumps(v)
                safe[k] = v
            except Exception:
                safe[k] = str(v)
    return safe


# ── Public API ─────────────────────────────────────────────────────────────────

def create_session(task: str, context_dict: dict, messages: list) -> str:
    """Persist a new session and return its ID."""
    sid = str(uuid.uuid4())[:8]
    sessions = _load_raw()
    sessions[sid] = {
        "id": sid,
        "title": task[:70].strip(),
        "created": time.time(),
        "updated": time.time(),
        "task": task,
        "context_dict": _safe_context(context_dict),
        "messages": messages,
    }
    _save_raw(sessions)
    return sid


def update_session(sid: str, context_dict: dict = None, messages: list = None):
    """Update an existing session's context and/or messages."""
    sessions = _load_raw()
    if sid not in sessions:
        return
    if context_dict is not None:
        sessions[sid]["context_dict"] = _safe_context(context_dict)
    if messages is not None:
        sessions[sid]["messages"] = messages
    sessions[sid]["updated"] = time.time()
    _save_raw(sessions)


def get_session(sid: str) -> dict | None:
    return _load_raw().get(sid)


def get_all_sessions() -> list:
    sessions = _load_raw()
    return sorted(sessions.values(), key=lambda s: s.get("updated", 0), reverse=True)


def delete_session(sid: str):
    sessions = _load_raw()
    sessions.pop(sid, None)
    _save_raw(sessions)


def append_message(sid: str, role: str, content: str):
    """Append a single chat message to a session."""
    sessions = _load_raw()
    if sid not in sessions:
        return
    sessions[sid].setdefault("messages", []).append({
        "role": role,
        "content": content,
        "ts": time.time(),
    })
    sessions[sid]["updated"] = time.time()
    _save_raw(sessions)
