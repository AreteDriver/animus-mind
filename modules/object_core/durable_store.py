"""PostgreSQL-backed durable object store with bitemporal event ledger.

Implements the Mind-class deterministic core:
- Object registry with versioned records and bitemporal state
- Immutable append-only event ledger (aligned with ledger_event.schema.json)
- Transactional outbox for async consumers
- Optimistic concurrency control on updates
- Rebuildable projection support

Requires ``sqlalchemy`` and a running PostgreSQL instance.
Connection string is read from ``ANIMUS_DATABASE_URL``.
"""

from __future__ import annotations

import hashlib
import json
import os
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

try:
    from contracts.validator import ValidationError as _SchemaValidationError
    from contracts.validator import validate as _validate_schema

    _HAS_CONTRACTS = True
except ImportError:  # pragma: no cover
    _HAS_CONTRACTS = False

try:
    from sqlalchemy import (
        Column,
        DateTime,
        Integer,
        JSON,
        String,
        create_engine,
        func,
        select,
    )
    from sqlalchemy.engine import Engine
    from sqlalchemy.orm import Session, declarative_base, sessionmaker

    _HAS_SQLALCHEMY = True
except ImportError:  # pragma: no cover
    _HAS_SQLALCHEMY = False

Base = declarative_base() if _HAS_SQLALCHEMY else object  # type: ignore[misc,assignment]


# ------------------------------------------------------------------
# Domain enums (Mind-class, not kernel memory types)
# ------------------------------------------------------------------

class ObjectType(str, Enum):
    MEMORY = "memory"
    SOURCE = "source"
    CLAIM = "claim"
    FORECAST = "forecast"
    DECISION = "decision"
    ACTION = "action"
    AGENT_CONTRACT = "agent_contract"


class StorageTier(str, Enum):
    HOT = "hot"
    WARM = "warm"
    COLD = "cold"


class SecurityClass(str, Enum):
    PUBLIC = "public"
    INTERNAL = "internal"
    CONFIDENTIAL = "confidential"
    RESTRICTED = "restricted"


class EpistemicStatus(str, Enum):
    UNVERIFIED = "unverified"
    SUPPORTED = "supported"
    DISPUTED = "disputed"
    REFUTED = "refuted"


class LifecycleStatus(str, Enum):
    ACTIVE = "active"
    SUPERSEDED = "superseded"
    DEPRECATED = "deprecated"
    ARCHIVED = "archived"
    DELETED = "deleted"


class EventType(str, Enum):
    CREATED = "created"
    UPDATED = "updated"
    SUPERSEDED = "superseded"
    APPROVED = "approved"
    REJECTED = "rejected"
    DELETED = "deleted"
    RESTORED = "restored"
    EXPORTED = "exported"
    IMPORTED = "imported"


class LedgerValidationError(Exception):
    """Raised when a ledger event fails schema validation.

    This is a **fail-closed** error: the event is NOT written to the
    ledger, and the calling transaction should be rolled back.
    """


# ------------------------------------------------------------------
# Domain dataclass
# ------------------------------------------------------------------

@dataclass
class ObjectRecord:
    """A canonical object record in the Mind-class registry."""

    object_id: str
    schema_id: str
    schema_version: str = "1.0.0"
    owner_id: str = "owner-default"
    workspace_id: str = "ws-default"
    subject_domain: str = "self"
    artifact_type: str = ObjectType.MEMORY.value
    cognitive_role: str = "memory"
    workflow_status: str = "active"
    epistemic_status: str = EpistemicStatus.SUPPORTED.value
    lifecycle_status: str = LifecycleStatus.ACTIVE.value
    storage_tier: str = StorageTier.WARM.value
    presentation: str = "canonical"
    security_class: str = SecurityClass.INTERNAL.value
    payload: dict[str, Any] = field(default_factory=dict)
    tags: list[str] = field(default_factory=list)
    created_by: str = "animus-mind"
    trace_id: str | None = None
    version: int = 1


# ------------------------------------------------------------------
# SQLAlchemy models
# ------------------------------------------------------------------

class _ObjectRegistryRow(Base):  # type: ignore[valid-type,misc]
    """Canonical object registry with bitemporal state.

    *valid_time* — when the object was true in the real world.
    *transaction_time* — when the system recorded the fact.
    """

    __tablename__ = "object_registry"

    id = Column(Integer, primary_key=True, autoincrement=True)
    object_id = Column(String(128), nullable=False, index=True)
    object_version = Column(Integer, nullable=False, default=1)
    schema_id = Column(String(256), nullable=False)
    schema_version = Column(String(32), nullable=False)
    owner_id = Column(String(128), nullable=False)
    workspace_id = Column(String(128), nullable=False, index=True)
    subject_domain = Column(String(32), nullable=False)
    artifact_type = Column(String(64), nullable=False)
    cognitive_role = Column(String(32), nullable=False)
    workflow_status = Column(String(32), nullable=False)
    epistemic_status = Column(String(32), nullable=False)
    lifecycle_status = Column(String(32), nullable=False)
    storage_tier = Column(String(16), nullable=False)
    presentation = Column(String(32), nullable=False)
    security_class = Column(String(32), nullable=False)

    # Bitemporal — valid time (real-world truth interval)
    valid_from = Column(DateTime(timezone=True), nullable=True)
    valid_to = Column(DateTime(timezone=True), nullable=True)

    # Bitemporal — transaction time (system record interval)
    recorded_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    superseded_at = Column(DateTime(timezone=True), nullable=True)

    created_by = Column(String(256), nullable=False)
    trace_id = Column(String(256), nullable=True)
    content_sha256 = Column(String(64), nullable=False)
    payload = Column(JSON, nullable=False)
    tags = Column(JSON, nullable=False, server_default="[]")


class _LedgerEventRow(Base):  # type: ignore[valid-type,misc]
    """Immutable append-only event ledger.

    Aligned with ``ledger_event.schema.json``.
    """

    __tablename__ = "event_ledger"

    id = Column(Integer, primary_key=True, autoincrement=True)
    event_id = Column(String(128), nullable=False, unique=True)
    event_type = Column(String(64), nullable=False)
    object_id = Column(String(128), nullable=False, index=True)
    object_version = Column(Integer, nullable=False)
    principal = Column(String(256), nullable=False)
    workspace_id = Column(String(128), nullable=False)
    payload = Column(JSON, nullable=False, server_default="{}")
    integrity_hash = Column(String(64), nullable=False)
    tx_time = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    parent_event_id = Column(String(128), nullable=True)


class _OutboxEntryRow(Base):  # type: ignore[valid-type,misc]
    """Transactional outbox entry for async consumers.

    Workers claim, process, and acknowledge entries.
    Duplicate delivery is safe because every consumer must be idempotent.
    """

    __tablename__ = "outbox_entries"

    id = Column(Integer, primary_key=True, autoincrement=True)
    entry_id = Column(String(128), nullable=False, unique=True)
    topic = Column(String(128), nullable=False)
    payload = Column(JSON, nullable=False)
    headers = Column(JSON, nullable=False, server_default="{}")
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    claimed_at = Column(DateTime(timezone=True), nullable=True)
    claimed_by = Column(String(128), nullable=True)
    retry_count = Column(Integer, nullable=False, default=0)
    processed_at = Column(DateTime(timezone=True), nullable=True)
    error_message = Column(String(512), nullable=True)


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _sha256(payload: dict[str, Any]) -> str:
    canonical = json.dumps(payload, sort_keys=True, ensure_ascii=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _generate_id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:16]}"


# ------------------------------------------------------------------
# Store
# ------------------------------------------------------------------

class DurableObjectStore:
    """PostgreSQL-backed durable object store.

    This is the **canonical authority** in the Mind-class architecture.
    All consequential state transitions flow through here.
    """

    def __init__(
        self,
        database_url: str | None = None,
        owner_id: str = "owner-default",
        workspace_id: str = "ws-default",
    ):
        if not _HAS_SQLALCHEMY:
            raise RuntimeError(
                "sqlalchemy is required. Install: pip install sqlalchemy psycopg[binary]"
            )

        self.database_url = database_url or os.getenv("ANIMUS_DATABASE_URL")
        if not self.database_url:
            raise RuntimeError(
                "DurableObjectStore requires database_url or ANIMUS_DATABASE_URL."
            )

        self.owner_id = owner_id
        self.workspace_id = workspace_id
        self._engine: Engine = create_engine(self.database_url, echo=False)
        self._session_factory = sessionmaker(bind=self._engine)

    def create_tables(self) -> None:
        """Create all tables. Call once during setup."""
        Base.metadata.create_all(self._engine)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _compute_integrity_hash(self, record: ObjectRecord) -> str:
        payload = {
            "object_id": record.object_id,
            "version": record.version,
            "schema_id": record.schema_id,
            "schema_version": record.schema_version,
            "owner_id": record.owner_id,
            "workspace_id": record.workspace_id,
            "artifact_type": record.artifact_type,
            "payload": record.payload,
            "tags": record.tags,
        }
        return _sha256(payload)

    def _validate_object_version(
        self,
        record: ObjectRecord,
        integrity_hash: str,
        valid_from: datetime | None = None,
        recorded_at: datetime | None = None,
    ) -> None:
        """Validate an object record against ``object_version.schema.json``.

        Raises ``LedgerValidationError`` on mismatch (fail-closed).
        """
        if not _HAS_CONTRACTS:
            return

        now_iso = (recorded_at or _now_utc()).isoformat()
        valid_from_iso = valid_from.isoformat() if valid_from else None

        version_dict = {
            "object_id": record.object_id,
            "object_version": record.version,
            "schema_id": record.schema_id,
            "schema_version": record.schema_version,
            "owner_id": record.owner_id,
            "workspace_id": record.workspace_id,
            "subject_domain": record.subject_domain,
            "artifact_type": record.artifact_type,
            "cognitive_role": record.cognitive_role,
            "workflow_status": record.workflow_status,
            "epistemic_status": record.epistemic_status,
            "lifecycle_status": record.lifecycle_status,
            "storage_tier": record.storage_tier,
            "presentation": record.presentation,
            "security_class": record.security_class,
            "valid_from": valid_from_iso,
            "recorded_at": now_iso,
            "created_by": record.created_by,
            "content_sha256": integrity_hash,
            "payload": record.payload,
            "tags": record.tags or [],
        }

        try:
            _validate_schema(version_dict, "object_version")
        except _SchemaValidationError as exc:
            raise LedgerValidationError(
                f"Object version failed schema validation: {exc.errors}"
            ) from exc

    def _write_ledger_event(
        self,
        session: Session,
        event_type: str,
        record: ObjectRecord,
        parent_event_id: str | None = None,
    ) -> str:
        """Append an immutable event to the ledger. Returns event_id.

        The event is validated against ``ledger_event.schema.json`` before
        persistence. If validation fails, ``LedgerValidationError`` is raised
        and the event is **not** written.
        """
        event_id = _generate_id("evt")
        payload = {
            "artifact_type": record.artifact_type,
            "schema_id": record.schema_id,
            "tags": record.tags,
        }
        now = _now_utc()
        integrity = _sha256({
            "event_id": event_id,
            "event_type": event_type,
            "object_id": record.object_id,
            "version": record.version,
            "payload": payload,
        })

        # Build canonical event dict for schema validation
        event_dict = {
            "event_id": event_id,
            "event_type": event_type,
            "object_id": record.object_id,
            "object_version": record.version,
            "principal": record.created_by,
            "workspace_id": record.workspace_id,
            "payload": payload,
            "integrity_hash": integrity,
            "tx_time": now.isoformat(),
            "parent_event_id": parent_event_id,
        }

        if _HAS_CONTRACTS:
            try:
                _validate_schema(event_dict, "ledger_event")
            except _SchemaValidationError as exc:
                raise LedgerValidationError(
                    f"Ledger event failed schema validation: {exc.errors}"
                ) from exc

        row = _LedgerEventRow(
            event_id=event_id,
            event_type=event_type,
            object_id=record.object_id,
            object_version=record.version,
            principal=record.created_by,
            workspace_id=record.workspace_id,
            payload=payload,
            integrity_hash=integrity,
            tx_time=now,
            parent_event_id=parent_event_id,
        )
        session.add(row)
        session.flush()
        return event_id

    def _enqueue_outbox(
        self,
        session: Session,
        topic: str,
        payload: dict[str, Any],
        headers: dict[str, str] | None = None,
    ) -> str:
        """Enqueue an outbox entry for async processing. Returns entry_id."""
        entry_id = _generate_id("obx")
        row = _OutboxEntryRow(
            entry_id=entry_id,
            topic=topic,
            payload=payload,
            headers=headers or {},
        )
        session.add(row)
        session.flush()
        return entry_id

    # ------------------------------------------------------------------
    # CRUD + ledger
    # ------------------------------------------------------------------

    def store(self, record: ObjectRecord) -> tuple[str, str]:
        """Store a new object. Returns (object_id, event_id).

        Writes:
        1. Object registry row (current projection)
        2. Ledger event (immutable)
        3. Outbox entry (async projection update)
        """
        record.version = 1
        integrity = self._compute_integrity_hash(record)
        now = _now_utc()

        self._validate_object_version(record, integrity, valid_from=now, recorded_at=now)

        with self._session_factory() as session:
            row = _ObjectRegistryRow(
                object_id=record.object_id,
                object_version=record.version,
                schema_id=record.schema_id,
                schema_version=record.schema_version,
                owner_id=record.owner_id,
                workspace_id=record.workspace_id,
                subject_domain=record.subject_domain,
                artifact_type=record.artifact_type,
                cognitive_role=record.cognitive_role,
                workflow_status=record.workflow_status,
                epistemic_status=record.epistemic_status,
                lifecycle_status=record.lifecycle_status,
                storage_tier=record.storage_tier,
                presentation=record.presentation,
                security_class=record.security_class,
                valid_from=now,
                created_by=record.created_by,
                trace_id=record.trace_id,
                content_sha256=integrity,
                payload=record.payload,
                tags=record.tags,
            )
            session.add(row)
            event_id = self._write_ledger_event(session, EventType.CREATED.value, record)
            self._enqueue_outbox(
                session,
                topic="object.created",
                payload={"object_id": record.object_id, "version": record.version, "event_id": event_id},
            )
            session.commit()
            return record.object_id, event_id

    def update(self, record: ObjectRecord, expected_version: int | None = None) -> tuple[bool, str]:
        """Update an object with optimistic concurrency control.

        If *expected_version* is provided and does not match the current
        version, raises ``ConcurrencyError``.

        Writes:
        1. Supersede old registry row
        2. Insert new registry row with version + 1
        3. Ledger event
        4. Outbox entry
        """
        with self._session_factory() as session:
            current = session.execute(
                select(_ObjectRegistryRow).where(
                    _ObjectRegistryRow.object_id == record.object_id,
                    _ObjectRegistryRow.superseded_at.is_(None),
                )
            ).scalar_one_or_none()

            if not current:
                return False, ""

            if expected_version is not None and current.object_version != expected_version:
                raise ConcurrencyError(
                    f"Expected version {expected_version}, found {current.object_version}"
                )

            # Supersede old version
            now = _now_utc()
            current.superseded_at = now
            current.valid_to = now
            current.lifecycle_status = LifecycleStatus.SUPERSEDED.value

            # Increment version
            record.version = current.object_version + 1
            integrity = self._compute_integrity_hash(record)

            self._validate_object_version(record, integrity, valid_from=now, recorded_at=now)

            new_row = _ObjectRegistryRow(
                object_id=record.object_id,
                object_version=record.version,
                schema_id=record.schema_id,
                schema_version=record.schema_version,
                owner_id=record.owner_id,
                workspace_id=record.workspace_id,
                subject_domain=record.subject_domain,
                artifact_type=record.artifact_type,
                cognitive_role=record.cognitive_role,
                workflow_status=record.workflow_status,
                epistemic_status=record.epistemic_status,
                lifecycle_status=record.lifecycle_status,
                storage_tier=record.storage_tier,
                presentation=record.presentation,
                security_class=record.security_class,
                valid_from=now,
                created_by=record.created_by,
                trace_id=record.trace_id,
                content_sha256=integrity,
                payload=record.payload,
                tags=record.tags,
            )
            session.add(new_row)
            event_id = self._write_ledger_event(
                session, EventType.UPDATED.value, record, parent_event_id=None
            )
            self._enqueue_outbox(
                session,
                topic="object.updated",
                payload={"object_id": record.object_id, "version": record.version, "event_id": event_id},
            )
            session.commit()
            return True, event_id

    def retrieve(self, object_id: str) -> ObjectRecord | None:
        """Retrieve the current (non-superseded) version of an object."""
        with self._session_factory() as session:
            row = session.execute(
                select(_ObjectRegistryRow).where(
                    _ObjectRegistryRow.object_id == object_id,
                    _ObjectRegistryRow.superseded_at.is_(None),
                )
            ).scalar_one_or_none()

            if not row:
                return None

            return ObjectRecord(
                object_id=row.object_id,
                schema_id=row.schema_id,
                schema_version=row.schema_version,
                owner_id=row.owner_id,
                workspace_id=row.workspace_id,
                subject_domain=row.subject_domain,
                artifact_type=row.artifact_type,
                cognitive_role=row.cognitive_role,
                workflow_status=row.workflow_status,
                epistemic_status=row.epistemic_status,
                lifecycle_status=row.lifecycle_status,
                storage_tier=row.storage_tier,
                presentation=row.presentation,
                security_class=row.security_class,
                payload=row.payload,
                tags=row.tags or [],
                created_by=row.created_by,
                trace_id=row.trace_id,
                version=row.object_version,
            )

    def retrieve_version(self, object_id: str, version: int) -> ObjectRecord | None:
        """Retrieve a specific historical version of an object."""
        with self._session_factory() as session:
            row = session.execute(
                select(_ObjectRegistryRow).where(
                    _ObjectRegistryRow.object_id == object_id,
                    _ObjectRegistryRow.object_version == version,
                )
            ).scalar_one_or_none()

            if not row:
                return None

            return ObjectRecord(
                object_id=row.object_id,
                schema_id=row.schema_id,
                schema_version=row.schema_version,
                owner_id=row.owner_id,
                workspace_id=row.workspace_id,
                subject_domain=row.subject_domain,
                artifact_type=row.artifact_type,
                cognitive_role=row.cognitive_role,
                workflow_status=row.workflow_status,
                epistemic_status=row.epistemic_status,
                lifecycle_status=row.lifecycle_status,
                storage_tier=row.storage_tier,
                presentation=row.presentation,
                security_class=row.security_class,
                payload=row.payload,
                tags=row.tags or [],
                created_by=row.created_by,
                trace_id=row.trace_id,
                version=row.object_version,
            )

    def delete(self, object_id: str, principal: str = "animus-mind") -> tuple[bool, str]:
        """Soft-delete an object (mark superseded + ledger event)."""
        with self._session_factory() as session:
            row = session.execute(
                select(_ObjectRegistryRow).where(
                    _ObjectRegistryRow.object_id == object_id,
                    _ObjectRegistryRow.superseded_at.is_(None),
                )
            ).scalar_one_or_none()

            if not row:
                return False, ""

            now = _now_utc()
            row.superseded_at = now
            row.valid_to = now
            row.lifecycle_status = LifecycleStatus.DELETED.value

            record = self.retrieve(object_id)
            if record:
                record.created_by = principal
                event_id = self._write_ledger_event(session, EventType.DELETED.value, record)
                self._enqueue_outbox(
                    session,
                    topic="object.deleted",
                    payload={"object_id": object_id, "event_id": event_id},
                )
                session.commit()
                return True, event_id
            return False, ""

    def list_current(self, artifact_type: str | None = None) -> list[ObjectRecord]:
        """List all current (non-superseded) objects."""
        with self._session_factory() as session:
            stmt = select(_ObjectRegistryRow).where(
                _ObjectRegistryRow.superseded_at.is_(None)
            )
            if artifact_type:
                stmt = stmt.where(_ObjectRegistryRow.artifact_type == artifact_type)

            rows = session.execute(stmt).scalars().all()
            return [
                ObjectRecord(
                    object_id=r.object_id,
                    schema_id=r.schema_id,
                    schema_version=r.schema_version,
                    owner_id=r.owner_id,
                    workspace_id=r.workspace_id,
                    subject_domain=r.subject_domain,
                    artifact_type=r.artifact_type,
                    cognitive_role=r.cognitive_role,
                    workflow_status=r.workflow_status,
                    epistemic_status=r.epistemic_status,
                    lifecycle_status=r.lifecycle_status,
                    storage_tier=r.storage_tier,
                    presentation=r.presentation,
                    security_class=r.security_class,
                    payload=r.payload,
                    tags=r.tags or [],
                    created_by=r.created_by,
                    trace_id=r.trace_id,
                    version=r.object_version,
                )
                for r in rows
            ]

    # ------------------------------------------------------------------
    # Bitemporal queries
    # ------------------------------------------------------------------

    def as_of_valid_time(self, object_id: str, vt: datetime) -> ObjectRecord | None:
        """Retrieve the version of an object that was valid at *vt* (valid time)."""
        with self._session_factory() as session:
            row = session.execute(
                select(_ObjectRegistryRow).where(
                    _ObjectRegistryRow.object_id == object_id,
                    _ObjectRegistryRow.valid_from <= vt,
                    _ObjectRegistryRow.valid_to.is_(None) | (_ObjectRegistryRow.valid_to > vt),
                )
            ).scalar_one_or_none()

            if not row:
                return None

            return ObjectRecord(
                object_id=row.object_id,
                schema_id=row.schema_id,
                schema_version=row.schema_version,
                owner_id=row.owner_id,
                workspace_id=row.workspace_id,
                subject_domain=row.subject_domain,
                artifact_type=row.artifact_type,
                cognitive_role=row.cognitive_role,
                workflow_status=row.workflow_status,
                epistemic_status=row.epistemic_status,
                lifecycle_status=row.lifecycle_status,
                storage_tier=row.storage_tier,
                presentation=row.presentation,
                security_class=row.security_class,
                payload=row.payload,
                tags=row.tags or [],
                created_by=row.created_by,
                trace_id=row.trace_id,
                version=row.object_version,
            )

    def as_of_transaction_time(self, object_id: str, tt: datetime) -> ObjectRecord | None:
        """Retrieve the version of an object as known at *tt* (transaction time)."""
        with self._session_factory() as session:
            row = session.execute(
                select(_ObjectRegistryRow).where(
                    _ObjectRegistryRow.object_id == object_id,
                    _ObjectRegistryRow.recorded_at <= tt,
                    _ObjectRegistryRow.superseded_at.is_(None) | (_ObjectRegistryRow.superseded_at > tt),
                )
            ).scalar_one_or_none()

            if not row:
                return None

            return ObjectRecord(
                object_id=row.object_id,
                schema_id=row.schema_id,
                schema_version=row.schema_version,
                owner_id=row.owner_id,
                workspace_id=row.workspace_id,
                subject_domain=row.subject_domain,
                artifact_type=row.artifact_type,
                cognitive_role=row.cognitive_role,
                workflow_status=row.workflow_status,
                epistemic_status=row.epistemic_status,
                lifecycle_status=row.lifecycle_status,
                storage_tier=row.storage_tier,
                presentation=row.presentation,
                security_class=row.security_class,
                payload=row.payload,
                tags=row.tags or [],
                created_by=row.created_by,
                trace_id=row.trace_id,
                version=row.object_version,
            )

    # ------------------------------------------------------------------
    # Ledger access
    # ------------------------------------------------------------------

    def get_ledger_events(self, object_id: str) -> list[dict[str, Any]]:
        """Retrieve all ledger events for an object, ordered by tx_time."""
        with self._session_factory() as session:
            rows = session.execute(
                select(_LedgerEventRow)
                .where(_LedgerEventRow.object_id == object_id)
                .order_by(_LedgerEventRow.tx_time)
            ).scalars().all()

            return [
                {
                    "event_id": r.event_id,
                    "event_type": r.event_type,
                    "object_id": r.object_id,
                    "object_version": r.object_version,
                    "principal": r.principal,
                    "workspace_id": r.workspace_id,
                    "payload": r.payload,
                    "integrity_hash": r.integrity_hash,
                    "tx_time": r.tx_time.isoformat() if r.tx_time else None,
                    "parent_event_id": r.parent_event_id,
                }
                for r in rows
            ]

    def verify_integrity(self, event_id: str) -> bool:
        """Verify the integrity hash of a ledger event."""
        with self._session_factory() as session:
            row = session.execute(
                select(_LedgerEventRow).where(_LedgerEventRow.event_id == event_id)
            ).scalar_one_or_none()

            if not row:
                return False

            expected = _sha256({
                "event_id": row.event_id,
                "event_type": row.event_type,
                "object_id": row.object_id,
                "version": row.object_version,
                "payload": row.payload,
            })
            return row.integrity_hash == expected

    # ------------------------------------------------------------------
    # Outbox processing
    # ------------------------------------------------------------------

    def claim_outbox_entries(self, worker_id: str, limit: int = 10) -> list[dict[str, Any]]:
        """Claim unprocessed outbox entries for a worker."""
        with self._session_factory() as session:
            rows = session.execute(
                select(_OutboxEntryRow)
                .where(_OutboxEntryRow.processed_at.is_(None))
                .where(_OutboxEntryRow.claimed_at.is_(None))
                .limit(limit)
            ).scalars().all()

            now = _now_utc()
            entries = []
            for row in rows:
                row.claimed_at = now
                row.claimed_by = worker_id
                entries.append({
                    "entry_id": row.entry_id,
                    "topic": row.topic,
                    "payload": row.payload,
                    "headers": row.headers,
                    "created_at": row.created_at.isoformat() if row.created_at else None,
                })
            session.commit()
            return entries

    def acknowledge_outbox_entry(self, entry_id: str, error: str | None = None) -> bool:
        """Mark an outbox entry as processed (or failed)."""
        with self._session_factory() as session:
            row = session.execute(
                select(_OutboxEntryRow).where(_OutboxEntryRow.entry_id == entry_id)
            ).scalar_one_or_none()

            if not row:
                return False

            if error:
                row.retry_count += 1
                row.error_message = error
                row.claimed_at = None
                row.claimed_by = None
            else:
                row.processed_at = _now_utc()
                row.error_message = None

            session.commit()
            return True


class ConcurrencyError(RuntimeError):
    """Raised when optimistic concurrency check fails."""
    pass
