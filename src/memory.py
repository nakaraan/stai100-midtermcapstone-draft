"""Short-term session memory for AGENT P.

Unlike the persistent, per-user vector store in notebook4.py's PatientMemory
(facts embedded and written to disk, recalled by semantic similarity across
sessions), this is in-process, per-session state: it exists only for the
lifetime of one conversation so the agent can resolve follow-up queries like
"what about March instead?" without the user repeating their location.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

DEFAULT_HISTORY_WINDOW = 10


@dataclass
class Location:
    latitude: float
    longitude: float
    name: Optional[str] = None


class SessionMemory:
    """Tracks the last resolved location, query params, and recent turns for one session."""

    def __init__(self, session_id: str, history_window: int = DEFAULT_HISTORY_WINDOW):
        self.session_id = session_id
        self.history_window = history_window
        self._location: Optional[Location] = None
        self._last_year: Optional[int] = None
        self._last_attributes: Optional[list[str]] = None
        self._turns: list[dict] = []
        self._awaiting_clarification = False
        self._pending_slots: dict = {}

    # ── Location ─────────────────────────────────────────────────────────────
    def remember_location(self, latitude: float, longitude: float, name: Optional[str] = None) -> None:
        self._location = Location(latitude=latitude, longitude=longitude, name=name)

    def get_location(self) -> Optional[Location]:
        return self._location

    # ── Last query parameters, reused when a follow-up omits them ──────────────
    def remember_query(self, year: Optional[int] = None, attributes: Optional[list[str]] = None) -> None:
        if year is not None:
            self._last_year = year
        if attributes is not None:
            self._last_attributes = attributes

    def get_last_year(self) -> Optional[int]:
        return self._last_year

    def get_last_attributes(self) -> Optional[list[str]]:
        return self._last_attributes

    # ── Clarification state — a reply to our own follow-up question is, by
    # definition, on-topic, even if it's just "June" or "2019" on its own ────
    def set_awaiting_clarification(self, waiting: bool) -> None:
        self._awaiting_clarification = waiting

    def is_awaiting_clarification(self) -> bool:
        return self._awaiting_clarification

    # ── Slots already resolved before a clarification question was asked —
    # e.g. start_month=2 from the original message — so a short follow-up
    # reply like "June" doesn't lose that context on the next turn ──────────
    def remember_pending_slots(self, slots: dict) -> None:
        self._pending_slots = dict(slots)

    def get_pending_slots(self) -> dict:
        return dict(self._pending_slots)

    def clear_pending_slots(self) -> None:
        self._pending_slots = {}

    # ── Conversation buffer — rolling window, same pattern as buffer_chat() ────
    def remember_turn(self, role: str, content: str) -> None:
        self._turns.append({"role": role, "content": content})
        self._turns = self._turns[-self.history_window:]

    def get_history(self) -> list[dict]:
        return list(self._turns)

    def clear(self) -> None:
        self._location = None
        self._last_year = None
        self._last_attributes = None
        self._turns = []
        self._awaiting_clarification = False
        self._pending_slots = {}


_sessions: dict[str, SessionMemory] = {}


def get_session_memory(session_id: str) -> SessionMemory:
    """Get or create the in-memory session store for `session_id`."""
    if session_id not in _sessions:
        _sessions[session_id] = SessionMemory(session_id)
    return _sessions[session_id]
