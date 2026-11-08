from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID, uuid4

from .schemas import (
    AssessmentRequest,
    BaselineFeatures,
    CreateSessionRequest,
    SafetyDecision,
    TaskEventRequest,
    TrustedContactRequest,
)


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Storage:
    """SQLite persistence for consented, derived metadata only."""

    def __init__(self, database_path: str):
        Path(database_path).parent.mkdir(parents=True, exist_ok=True)
        self.database_path = database_path

    @contextmanager
    def connection(self):
        con = sqlite3.connect(self.database_path)
        con.row_factory = sqlite3.Row
        try:
            yield con
            con.commit()
        finally:
            con.close()

    def initialize(self) -> None:
        with self.connection() as con:
            con.executescript(
                """
                CREATE TABLE IF NOT EXISTS baselines (
                    id TEXT PRIMARY KEY,
                    owner_id TEXT NOT NULL,
                    features_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS assessments (
                    id TEXT PRIMARY KEY,
                    owner_id TEXT NOT NULL,
                    request_json TEXT NOT NULL,
                    decision_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS trusted_contacts (
                    id TEXT PRIMARY KEY,
                    owner_id TEXT NOT NULL,
                    name TEXT NOT NULL,
                    phone_e164 TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS alerts (
                    id TEXT PRIMARY KEY,
                    owner_id TEXT NOT NULL,
                    assessment_id TEXT NOT NULL,
                    trusted_contact_id TEXT NOT NULL,
                    message TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS assessment_sessions (
                    id TEXT PRIMARY KEY,
                    owner_id TEXT NOT NULL,
                    label TEXT,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS task_events (
                    id TEXT PRIMARY KEY,
                    owner_id TEXT NOT NULL,
                    session_id TEXT NOT NULL,
                    client_event_id TEXT NOT NULL,
                    event_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    UNIQUE(owner_id, client_event_id)
                );
                CREATE TABLE IF NOT EXISTS audit_events (
                    id TEXT PRIMARY KEY,
                    owner_id TEXT NOT NULL,
                    action TEXT NOT NULL,
                    entity_type TEXT NOT NULL,
                    entity_id TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_assessments_owner ON assessments(owner_id);
                CREATE INDEX IF NOT EXISTS idx_sessions_owner ON assessment_sessions(owner_id);
                CREATE INDEX IF NOT EXISTS idx_events_session ON task_events(owner_id, session_id, created_at);
                """
            )

    def _audit(self, con: sqlite3.Connection, owner_id: str, action: str, entity_type: str, entity_id: UUID) -> None:
        con.execute(
            "INSERT INTO audit_events VALUES (?, ?, ?, ?, ?, ?)",
            (str(uuid4()), owner_id, action, entity_type, str(entity_id), utcnow().isoformat()),
        )

    def create_baseline(self, owner_id: str, request: BaselineFeatures) -> tuple[UUID, datetime]:
        baseline_id, created_at = uuid4(), utcnow()
        with self.connection() as con:
            con.execute(
                "INSERT INTO baselines VALUES (?, ?, ?, ?)",
                (str(baseline_id), owner_id, request.model_dump_json(), created_at.isoformat()),
            )
            self._audit(con, owner_id, "created", "baseline", baseline_id)
        return baseline_id, created_at

    def create_assessment(
        self, owner_id: str, request: AssessmentRequest, decision: SafetyDecision
    ) -> tuple[UUID, datetime]:
        assessment_id, created_at = uuid4(), utcnow()
        if request.consent_to_store_assessment:
            with self.connection() as con:
                con.execute(
                    "INSERT INTO assessments VALUES (?, ?, ?, ?, ?)",
                    (
                        str(assessment_id),
                        owner_id,
                        request.model_dump_json(),
                        decision.model_dump_json(),
                        created_at.isoformat(),
                    ),
                )
                self._audit(con, owner_id, "created", "assessment", assessment_id)
        return assessment_id, created_at

    def create_contact(self, owner_id: str, request: TrustedContactRequest) -> UUID:
        contact_id = uuid4()
        with self.connection() as con:
            con.execute(
                "INSERT INTO trusted_contacts VALUES (?, ?, ?, ?, ?)",
                (str(contact_id), owner_id, request.name, request.phone_e164, utcnow().isoformat()),
            )
            self._audit(con, owner_id, "created", "trusted_contact", contact_id)
        return contact_id

    def get_contact(self, owner_id: str, contact_id: UUID) -> sqlite3.Row | None:
        with self.connection() as con:
            return con.execute(
                "SELECT * FROM trusted_contacts WHERE id = ? AND owner_id = ?",
                (str(contact_id), owner_id),
            ).fetchone()

    def list_contacts(self, owner_id: str) -> list[sqlite3.Row]:
        with self.connection() as con:
            return con.execute(
                "SELECT * FROM trusted_contacts WHERE owner_id = ? ORDER BY created_at DESC",
                (owner_id,),
            ).fetchall()

    def get_assessment(self, owner_id: str, assessment_id: UUID) -> sqlite3.Row | None:
        with self.connection() as con:
            return con.execute(
                "SELECT * FROM assessments WHERE id = ? AND owner_id = ?",
                (str(assessment_id), owner_id),
            ).fetchone()

    def save_alert(self, owner_id: str, assessment_id: UUID, contact_id: UUID, message: str) -> UUID:
        alert_id = uuid4()
        with self.connection() as con:
            con.execute(
                "INSERT INTO alerts VALUES (?, ?, ?, ?, ?, ?)",
                (
                    str(alert_id),
                    owner_id,
                    str(assessment_id),
                    str(contact_id),
                    message,
                    utcnow().isoformat(),
                ),
            )
            self._audit(con, owner_id, "previewed", "trusted_contact_alert", alert_id)
        return alert_id

    def create_session(self, owner_id: str, request: CreateSessionRequest) -> tuple[UUID, datetime]:
        session_id, created_at = uuid4(), utcnow()
        with self.connection() as con:
            con.execute(
                "INSERT INTO assessment_sessions VALUES (?, ?, ?, ?)",
                (str(session_id), owner_id, request.label, created_at.isoformat()),
            )
            self._audit(con, owner_id, "created", "assessment_session", session_id)
        return session_id, created_at

    def get_session(self, owner_id: str, session_id: UUID) -> sqlite3.Row | None:
        with self.connection() as con:
            return con.execute(
                "SELECT * FROM assessment_sessions WHERE id = ? AND owner_id = ?",
                (str(session_id), owner_id),
            ).fetchone()

    def create_task_event(
        self, owner_id: str, session_id: UUID, request: TaskEventRequest
    ) -> tuple[UUID, datetime, bool]:
        """Returns id, timestamp, and whether this was a new idempotent write."""
        with self.connection() as con:
            existing = con.execute(
                "SELECT id, created_at FROM task_events WHERE owner_id = ? AND client_event_id = ?",
                (owner_id, str(request.client_event_id)),
            ).fetchone()
            if existing:
                return UUID(existing["id"]), datetime.fromisoformat(existing["created_at"]), False

            event_id, created_at = uuid4(), utcnow()
            con.execute(
                "INSERT INTO task_events VALUES (?, ?, ?, ?, ?, ?)",
                (
                    str(event_id),
                    owner_id,
                    str(session_id),
                    str(request.client_event_id),
                    request.model_dump_json(),
                    created_at.isoformat(),
                ),
            )
            self._audit(con, owner_id, "recorded", "task_event", event_id)
            return event_id, created_at, True

    def list_task_events(self, owner_id: str, session_id: UUID) -> list[sqlite3.Row]:
        with self.connection() as con:
            return con.execute(
                "SELECT * FROM task_events WHERE owner_id = ? AND session_id = ? ORDER BY created_at ASC",
                (owner_id, str(session_id)),
            ).fetchall()

    @staticmethod
    def _rows(con: sqlite3.Connection, table: str, owner_id: str) -> list[dict]:
        return [dict(row) for row in con.execute(f"SELECT * FROM {table} WHERE owner_id = ?", (owner_id,)).fetchall()]

    def export_owner_data(self, owner_id: str) -> dict[str, list[dict]]:
        with self.connection() as con:
            result = {
                "baselines": self._rows(con, "baselines", owner_id),
                "assessments": self._rows(con, "assessments", owner_id),
                "trusted_contacts": self._rows(con, "trusted_contacts", owner_id),
                "alerts": self._rows(con, "alerts", owner_id),
                "sessions": self._rows(con, "assessment_sessions", owner_id),
                "task_events": self._rows(con, "task_events", owner_id),
            }
        for item in result["baselines"]:
            item["features"] = json.loads(item.pop("features_json"))
        for item in result["assessments"]:
            item["request"] = json.loads(item.pop("request_json"))
            item["decision"] = json.loads(item.pop("decision_json"))
        for item in result["task_events"]:
            item["event"] = json.loads(item.pop("event_json"))
        return result

    def delete_owner_data(self, owner_id: str) -> None:
        with self.connection() as con:
            for table in (
                "baselines",
                "assessments",
                "trusted_contacts",
                "alerts",
                "task_events",
                "assessment_sessions",
                "audit_events",
            ):
                con.execute(f"DELETE FROM {table} WHERE owner_id = ?", (owner_id,))
