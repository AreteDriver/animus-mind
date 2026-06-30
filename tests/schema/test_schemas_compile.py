"""Schema compilation and validation tests.

Ensures every canonical schema loads into a Draft202012Validator and
that the 4 Mind-class schemas (object_version, outbox_entry,
capability_grant, policy_decision) accept valid payloads and reject
invalid ones.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from contracts.validator import ValidationError, validate, validate_with_schema

SCHEMAS_DIR = Path(__file__).resolve().parent.parent.parent / "contracts" / "schemas"


def _load_schema(name: str) -> dict:
    path = SCHEMAS_DIR / f"{name}.schema.json"
    return json.loads(path.read_text(encoding="utf-8"))


# ------------------------------------------------------------------
# 1. Every schema compiles
# ------------------------------------------------------------------

ALL_SCHEMAS = [p.stem.replace(".schema", "") for p in SCHEMAS_DIR.glob("*.schema.json")]


@pytest.mark.parametrize("schema_name", ALL_SCHEMAS)
def test_schema_compiles(schema_name: str) -> None:
    """A Draft202012Validator can be built from the schema without error."""
    schema = _load_schema(schema_name)
    validator = Draft202012Validator(schema)
    assert validator.schema.get("$id") is not None


# ------------------------------------------------------------------
# 2. object_version — positive and negative
# ------------------------------------------------------------------

VALID_OBJECT_VERSION = {
    "object_id": "mem-test-001",
    "object_version": 1,
    "schema_id": "https://animus.local/schemas/memory_candidate.schema.json",
    "schema_version": "1.0.0",
    "owner_id": "owner-test",
    "workspace_id": "ws-test",
    "subject_domain": "self",
    "artifact_type": "memory_candidate",
    "cognitive_role": "memory",
    "workflow_status": "approved",
    "epistemic_status": "supported",
    "lifecycle_status": "active",
    "storage_tier": "warm",
    "presentation": "canonical",
    "security_class": "internal",
    "valid_from": "2026-06-30T12:00:00+00:00",
    "recorded_at": "2026-06-30T12:00:00+00:00",
    "created_by": "animus-mind",
    "content_sha256": "a" * 64,
    "payload": {"content": "Remember this."},
}


def test_object_version_valid() -> None:
    validate(VALID_OBJECT_VERSION, "object_version")


@pytest.mark.parametrize(
    "mutation,expected_substring",
    [
        ({"object_id": "123-invalid"}, "does not match"),
        ({"object_version": 0}, "minimum"),
        ({"schema_version": "1.0"}, "does not match"),
        ({"owner_id": "bad"}, "does not match"),
        ({"workspace_id": "bad"}, "does not match"),
        ({"subject_domain": "unknown"}, "is not one of"),
        ({"artifact_type": "ghost"}, "is not one of"),
        ({"storage_tier": "frozen"}, "is not one of"),
        ({"security_class": "top-secret"}, "is not one of"),
        ({"content_sha256": "short"}, "does not match"),
        ({"valid_from": 123}, "is not of type"),
        ({"recorded_at": 123}, "is not of type"),
    ],
)
def test_object_version_invalid(mutation: dict, expected_substring: str) -> None:
    payload = {**VALID_OBJECT_VERSION, **mutation}
    with pytest.raises(ValidationError) as exc_info:
        validate(payload, "object_version")
    assert expected_substring in str(exc_info.value)


# ------------------------------------------------------------------
# 3. outbox_entry — positive and negative
# ------------------------------------------------------------------

VALID_OUTBOX_ENTRY = {
    "entry_id": "ent-test-001",
    "topic": "object.created",
    "payload": {"object_id": "mem-001"},
    "headers": {"trace_id": "trace-001"},
    "created_at": "2026-06-30T12:00:00+00:00",
    "claimed_at": None,
    "claimed_by": None,
    "retry_count": 0,
    "processed_at": None,
    "error_message": None,
}


def test_outbox_entry_valid() -> None:
    validate(VALID_OUTBOX_ENTRY, "outbox_entry")


@pytest.mark.parametrize(
    "mutation,expected_substring",
    [
        ({"entry_id": "bad"}, "does not match"),
        ({"topic": ""}, "should be non-empty"),
        ({"payload": "not-an-object"}, "is not of type"),
        ({"headers": "not-an-object"}, "is not of type"),
        ({"created_at": 123}, "is not of type"),
        ({"retry_count": -1}, "minimum"),
    ],
)
def test_outbox_entry_invalid(mutation: dict, expected_substring: str) -> None:
    payload = {**VALID_OUTBOX_ENTRY, **mutation}
    with pytest.raises(ValidationError) as exc_info:
        validate(payload, "outbox_entry")
    assert expected_substring in str(exc_info.value)


# ------------------------------------------------------------------
# 4. capability_grant — positive and negative
# ------------------------------------------------------------------

VALID_CAPABILITY_GRANT = {
    "grant_id": "grant-test-001",
    "principal": "agent-researcher",
    "scope": ["read", "write"],
    "resource": "ws-test/*",
    "action": ["create", "read", "update"],
    "granted_by": "owner-arete",
    "granted_at": "2026-06-30T12:00:00+00:00",
    "expires_at": "2026-12-31T23:59:59+00:00",
    "budget": {
        "max_calls": 1000,
        "max_tokens": 1_000_000,
        "max_cost": 50.0,
        "window_seconds": 3600,
    },
    "conditions": {
        "require_approval_above_risk": "high",
        "allowed_workspaces": ["ws-test"],
        "allowed_schemas": ["memory_candidate.schema.json"],
    },
    "revoked_at": None,
    "revoked_by": None,
    "revocation_reason": None,
}


def test_capability_grant_valid() -> None:
    validate(VALID_CAPABILITY_GRANT, "capability_grant")


@pytest.mark.parametrize(
    "mutation,expected_substring",
    [
        ({"grant_id": "bad"}, "does not match"),
        ({"scope": []}, "should be non-empty"),
        ({"action": ["hack"]}, "is not one of"),
        ({"granted_at": 123}, "is not of type"),
        ({"budget": {"max_calls": 0}}, "minimum"),
        ({"conditions": {"require_approval_above_risk": "extreme"}}, "is not one of"),
    ],
)
def test_capability_grant_invalid(mutation: dict, expected_substring: str) -> None:
    payload = {**VALID_CAPABILITY_GRANT, **mutation}
    with pytest.raises(ValidationError) as exc_info:
        validate(payload, "capability_grant")
    assert expected_substring in str(exc_info.value)


# ------------------------------------------------------------------
# 5. policy_decision — positive and negative
# ------------------------------------------------------------------

VALID_POLICY_DECISION = {
    "decision_id": "dec-test-001",
    "rule_id": "rule-no-delete-without-approval",
    "input_context": {
        "action": "delete",
        "resource": "mem-001",
        "principal": "agent-researcher",
        "workspace_id": "ws-test",
        "schema_id": "memory_candidate.schema.json",
        "payload_summary": "Delete memory candidate",
    },
    "decision": "deny",
    "confidence": 0.97,
    "reason": "Delete action requires explicit owner approval",
    "denial_reason_code": "escalation_required",
    "obligations": [
        {
            "obligation_type": "approve",
            "description": "Owner must approve deletion",
            "target": "owner-arete",
            "deadline": "2026-06-30T13:00:00+00:00",
        }
    ],
    "principal": "agent-researcher",
    "workspace_id": "ws-test",
    "tx_time": "2026-06-30T12:00:00+00:00",
    "parent_decision_id": None,
}


def test_policy_decision_valid() -> None:
    validate(VALID_POLICY_DECISION, "policy_decision")


@pytest.mark.parametrize(
    "mutation,expected_substring",
    [
        ({"decision_id": "bad"}, "does not match"),
        ({"decision": "maybe"}, "is not one of"),
        ({"confidence": 1.5}, "maximum"),
        ({"denial_reason_code": "bad_code"}, "is not one of"),
        ({"obligations": [{"obligation_type": "unknown"}]}, "is a required property"),
        ({"tx_time": 123}, "is not of type"),
        ({"parent_decision_id": "bad"}, "does not match"),
    ],
)
def test_policy_decision_invalid(mutation: dict, expected_substring: str) -> None:
    payload = {**VALID_POLICY_DECISION, **mutation}
    with pytest.raises(ValidationError) as exc_info:
        validate(payload, "policy_decision")
    assert expected_substring in str(exc_info.value)


# ------------------------------------------------------------------
# 6. Cross-schema $ref resolution (sanity)
# ------------------------------------------------------------------

def test_common_schema_ref_resolves_in_decision() -> None:
    """A schema that $refs common.schema.json validates without raising
    'Schema not found'."""
    payload = {
        "object_id": "dec-001",
        "object_version": 1,
        "schema_id": "https://animus.local/schemas/decision.schema.json",
        "schema_version": "1.0.0",
        "owner_id": "owner-test",
        "workspace_id": "ws-test",
        "subject_domain": "self",
        "artifact_type": "decision",
        "cognitive_role": "intelligence",
        "workflow_status": "approved",
        "epistemic_status": "supported",
        "lifecycle_status": "active",
        "storage_tier": "warm",
        "presentation": "canonical",
        "security_class": "internal",
        "valid_time": {
            "valid_from": "2026-06-30T12:00:00+00:00",
            "valid_to": None,
        },
        "transaction_time": {
            "recorded_at": "2026-06-30T12:00:00+00:00",
            "superseded_at": None,
        },
        "provenance": {
            "created_by": "animus-mind",
            "source_refs": [],
            "derived_from": [],
            "trace_id": None,
        },
        "integrity": {"content_sha256": "a" * 64},
        "payload": {
            "question": "Should we proceed?",
            "chosen_option": "yes",
            "alternatives": ["no"],
            "rationale": "Evidence supports it.",
            "authority": "owner",
            "decision_at": "2026-06-30T12:00:00+00:00",
        },
    }
    validate(payload, "decision")
