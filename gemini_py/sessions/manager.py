"""
JSON-backed session store.

Mirrors `packages/core/src/utils/sessions.ts` in the original TS gemini-cli.
Each session is a single JSON file in `~/.gemini-py/sessions/`.
"""

from __future__ import annotations

import json
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Optional

from ..config import sessions_dir


# --------------------------------------------------------------------------- #
# Data model
# --------------------------------------------------------------------------- #


@dataclass
class MessageRecord:
    """One message in a session — either user, model, or tool output."""

    role: str  # "user" | "model" | "tool" | "system"
    content: str = ""
    # For model messages that contain tool calls:
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    # For tool messages: which tool call this is the result of
    tool_call_id: Optional[str] = None
    # Display metadata
    name: Optional[str] = None
    timestamp: float = field(default_factory=time.time)


@dataclass
class Session:
    id: str
    title: str = "New conversation"
    messages: list[MessageRecord] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    model: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "messages": [asdict(m) for m in self.messages],
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "model": self.model,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Session":
        msgs = [MessageRecord(**m) for m in d.get("messages", [])]
        return cls(
            id=d["id"],
            title=d.get("title", "New conversation"),
            messages=msgs,
            created_at=d.get("created_at", time.time()),
            updated_at=d.get("updated_at", time.time()),
            model=d.get("model"),
        )


# --------------------------------------------------------------------------- #
# Store
# --------------------------------------------------------------------------- #


class SessionStore:
    """CRUD for sessions, persisted as JSON files."""

    def __init__(self, root: Optional[Path] = None):
        self.root = root or sessions_dir()
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, sid: str) -> Path:
        # Sanitize the session id so we don't escape the sessions dir
        safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in sid)
        return self.root / f"{safe}.json"

    def create(self, title: str = "New conversation") -> Session:
        sid = uuid.uuid4().hex[:12]
        s = Session(id=sid, title=title)
        self.save(s)
        return s

    def save(self, session: Session) -> None:
        session.updated_at = time.time()
        path = self._path(session.id)
        path.write_text(
            json.dumps(session.to_dict(), indent=2, default=str),
            encoding="utf-8",
        )

    def load(self, sid: str) -> Optional[Session]:
        path = self._path(sid)
        if not path.exists():
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return Session.from_dict(data)
        except Exception:
            return None

    def delete(self, sid: str) -> bool:
        path = self._path(sid)
        if path.exists():
            path.unlink()
            return True
        return False

    def list_sessions(self) -> list[Session]:
        out: list[Session] = []
        for p in sorted(self.root.glob("*.json"), key=lambda x: x.stat().st_mtime, reverse=True):
            try:
                data = json.loads(p.read_text(encoding="utf-8"))
                out.append(Session.from_dict(data))
            except Exception:
                continue
        return out

    def rename(self, sid: str, new_title: str) -> Optional[Session]:
        s = self.load(sid)
        if s is None:
            return None
        s.title = new_title
        self.save(s)
        return s
