from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID, uuid4

from .schemas import AssessmentRequest, BaselineFeatures, SafetyDecision, TrustedContactRequest


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Storage:
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
                """
            )

    def create_baseline(self, owner_id: str, request: BaselineFeatures) -> tuple[UUID, datetime]:
        baseline_id, created_at = uuid4(), utcnow()
        with self.connection() as con:
            con.execute(
                "INSERT INTO baselines VALUES (?, ?, ?, ?)",
                (str(baseline_id), owner_id, request.model_dump_json(), created_at.isoformat()),
            )
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
        return assessment_id, created_at

    def create_contact(self, owner_id: str, request: TrustedContactRequest) -> UUID:
        contact_id = uuid4()
        with self.connection() as con:
            con.execute(
                "INSERT INTO trusted_contacts VALUES (?, ?, ?, ?, ?)",
                (str(contact_id), owner_id, request.name, request.phone_e164, utcnow().isoformat()),
            )
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

    def save_alert(
        self, owner_id: str, assessment_id: UUID, contact_id: UUID, message: str
    ) -> UUID:
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
        return alert_id

    def delete_owner_data(self, owner_id: str) -> None:
        with self.connection() as con:
            for table in ("baselines", "assessments", "trusted_contacts", "alerts"):
                con.execute(f"DELETE FROM {table} WHERE owner_id = ?", (owner_id,))
