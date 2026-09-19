"""Single-process, ephemeral session storage with atomic revision checks."""

from threading import RLock
from uuid import uuid4
from contextlib import contextmanager

from travel_agent.contracts import Contract, PreferenceUpdate, Preferences, ResultSnapshot
from pydantic import Field
from typing import Literal


class RevisionConflict(Exception):
    pass


class RefreshLimit(Exception):
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
    source_issues: dict[str, str] = Field(default_factory=dict)
    refresh_request_id: str | None = None
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
        self._refresh_requests: dict[str, set[str]] = {}

    def refresh_seen(self, session_id: str, request_id: str) -> bool:
        with self._lock:
            seen = self._refresh_requests.get(session_id, set())
            if request_id in seen:
                return True
            if len(seen) >= 100:
                raise RefreshLimit()  # Bound memory without forgetting spent requests.
            return False

    def record_issue(self, previous: Session, source: str, message: str):
        with self._lock:
            current = self._sessions[previous.id]
            if current.revision == previous.revision and current.conversation_revision == previous.conversation_revision:
                current.source_issues[source] = message

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
                current.source_issues.pop('activities', None)
            else:
                current.result = result.model_copy(deep=True)
                current.source_issues.pop('hotels', None)
            return current.model_copy(deep=True)

    def publish_bundle(self, previous: Session, result: ResultSnapshot | None, activity: ResultSnapshot,
                       issues: dict[str, str], request_id: str) -> Session:
        with self._lock:
            current = self._sessions[previous.id]
            if current.revision != previous.revision or current.conversation_revision != previous.conversation_revision:
                raise RevisionConflict()
            if activity.preference_revision != current.revision or result is not None and result.preference_revision != current.revision:
                raise RevisionConflict()
            next_state = current.model_copy(deep=True)
            if result is not None:
                next_state.result = result.model_copy(deep=True)
            next_state.activity_result = activity.model_copy(deep=True)
            next_state.source_issues = dict(issues)
            next_state.refresh_request_id = request_id
            self._refresh_requests.setdefault(previous.id, set()).add(request_id)
            self._sessions[previous.id] = next_state
            return next_state.model_copy(deep=True)

    def commit_chat(self, previous: Session, preferences: Preferences, result: ResultSnapshot | None,
                    user_text: str, reply: str, activity_result: ResultSnapshot | None = None,
                    source_issues: dict[str, str] | None = None) -> Session:
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
                next_state.source_issues.pop('hotels', None)
            if activity_result is not None:
                next_state.activity_result = activity_result.model_copy(deep=True)
                next_state.source_issues.pop('activities', None)
            if source_issues is not None:
                next_state.source_issues.update(source_issues)
            self._sessions[previous.id] = next_state
            return next_state.model_copy(deep=True)
