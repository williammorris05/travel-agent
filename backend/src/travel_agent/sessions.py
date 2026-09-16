"""Single-process, ephemeral session storage with atomic revision checks."""

from threading import RLock
from uuid import uuid4
from contextlib import contextmanager

from travel_agent.contracts import Contract, PreferenceUpdate, Preferences, ResultSnapshot
from pydantic import Field
from typing import Literal


class RevisionConflict(Exception):
    pass


class ConversationMessage(Contract):
    role: Literal["user", "assistant"]
    text: str


class Session(Contract):
    id: str
    revision: int = 0
    preferences: Preferences
    last_update_source: str | None = None
    result: ResultSnapshot | None = None
    activity_result: ResultSnapshot | None = None
    conversation_revision: int = 0
    messages: list[ConversationMessage] = Field(default_factory=list)


def merge(current: dict, changes: dict) -> dict:
    merged = dict(current)
    for key, value in changes.items():
        merged[key] = merge(current[key], value) if isinstance(value, dict) and isinstance(current.get(key), dict) else value
    return merged


class SessionStore:
    def __init__(self):
        self._sessions: dict[str, Session] = {}
        self._lock = RLock()
        self._chat_inflight: set[str] = set()

    @contextmanager
    def chat_turn(self, session_id: str):
        with self._lock:
            if session_id in self._chat_inflight:
                raise RevisionConflict()
            self._chat_inflight.add(session_id)
        try:
            yield
        finally:
            with self._lock:
                self._chat_inflight.discard(session_id)

    def create(self, preferences: Preferences) -> Session:
        with self._lock:
            session = Session(id=str(uuid4()), preferences=preferences.model_copy(deep=True))
            self._sessions[session.id] = session
            return session.model_copy(deep=True)

    def get(self, session_id: str) -> Session:
        with self._lock:
            return self._sessions[session_id].model_copy(deep=True)

    def update(self, session_id: str, update: PreferenceUpdate) -> Session:
        with self._lock:
            current = self._sessions[session_id]
            if current.revision != update.expected_revision:
                raise RevisionConflict()
            preferences = Preferences.model_validate(merge(current.preferences.model_dump(), update.changes.model_dump(exclude_unset=True)))
            if preferences != current.preferences:
                current.preferences = preferences
                current.revision += 1
                current.last_update_source = update.source
            return current.model_copy(deep=True)

    def publish(self, session_id: str, result: ResultSnapshot, *, activities: bool = False) -> Session:
        with self._lock:
            current = self._sessions[session_id]
            if current.revision != result.preference_revision:
                raise RevisionConflict()
            if activities:
                current.activity_result = result.model_copy(deep=True)
            else:
                current.result = result.model_copy(deep=True)
            return current.model_copy(deep=True)

    def commit_chat(self, previous: Session, preferences: Preferences, result: ResultSnapshot | None,
                    user_text: str, reply: str, activity_result: ResultSnapshot | None = None) -> Session:
        with self._lock:
            current = self._sessions[previous.id]
            if current.revision != previous.revision or current.conversation_revision != previous.conversation_revision:
                raise RevisionConflict()
            revision = current.revision + (preferences != current.preferences)
            if result is not None and result.preference_revision != revision:
                raise RevisionConflict()
            if activity_result is not None and activity_result.preference_revision != revision:
                raise RevisionConflict()
            next_state = current.model_copy(deep=True)
            next_state.preferences = preferences.model_copy(deep=True)
            next_state.revision = revision
            next_state.conversation_revision += 1
            next_state.last_update_source = "chat"
            next_state.messages = (current.messages + [ConversationMessage(role="user", text=user_text),
                                                       ConversationMessage(role="assistant", text=reply)])[-20:]
            if result is not None:
                next_state.result = result.model_copy(deep=True)
            if activity_result is not None:
                next_state.activity_result = activity_result.model_copy(deep=True)
            self._sessions[previous.id] = next_state
            return next_state.model_copy(deep=True)
