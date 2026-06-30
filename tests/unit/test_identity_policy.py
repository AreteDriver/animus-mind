"""Unit tests for the identity policy module.

Covers PolicyDecisionPoint and CapabilityGrantStore.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from modules.identity_policy import CapabilityGrant, CapabilityGrantStore, Decision, PolicyDecisionPoint


@pytest.fixture
def pdp():
    """Create a PDP with a seeded capability store."""
    store = CapabilityGrantStore()
    store.create(
        CapabilityGrant(
            grant_id="grant-test-001",
            principal="agent-researcher",
            scope=["read", "write"],
            resource="ws-test/*",
            action=["create", "read", "update"],
            granted_by="owner-arete",
            granted_at=datetime.now(timezone.utc),
            expires_at=datetime.now(timezone.utc) + timedelta(days=7),
            budget={"max_calls": 1000, "window_seconds": 3600},
            conditions={"allowed_workspaces": ["ws-test"]},
        )
    )
    return PolicyDecisionPoint(store)


class TestPolicyDecisionPoint:
    """PolicyDecisionPoint evaluation rules."""

    def test_allow_permitted_action(self, pdp):
        """A permitted action on a valid grant should ALLOW."""
        result = pdp.evaluate(
            principal="agent-researcher",
            action="read",
            resource="mem-001",
            workspace_id="ws-test",
        )
        assert result.decision == Decision.ALLOW
        assert result.confidence == 1.0

    def test_deny_unknown_principal(self, pdp):
        """A principal with no grants should be denied."""
        result = pdp.evaluate(
            principal="agent-stranger",
            action="read",
            resource="mem-001",
            workspace_id="ws-test",
        )
        assert result.decision == Decision.DENY
        assert result.denial_reason_code.value == "missing_scope"

    def test_deny_unpermitted_action(self, pdp):
        """An action not in any grant should be denied."""
        result = pdp.evaluate(
            principal="agent-researcher",
            action="import",
            resource="mem-001",
            workspace_id="ws-test",
        )
        assert result.decision == Decision.DENY
        assert result.denial_reason_code.value == "missing_scope"

    def test_deny_expired_grant(self):
        """An expired grant should not permit actions."""
        store = CapabilityGrantStore()
        store.create(
            CapabilityGrant(
                grant_id="grant-expired",
                principal="agent-old",
                scope=["read"],
                resource="*",
                action=["read"],
                granted_by="owner",
                granted_at=datetime.now(timezone.utc) - timedelta(days=14),
                expires_at=datetime.now(timezone.utc) - timedelta(days=7),
            )
        )
        pdp = PolicyDecisionPoint(store)
        result = pdp.evaluate(
            principal="agent-old",
            action="read",
            resource="mem-001",
            workspace_id="ws-default",
        )
        assert result.decision == Decision.DENY
        assert result.denial_reason_code.value == "capability_revoked"

    def test_escalate_high_risk_actions(self, pdp):
        """High-risk actions like execute should escalate."""
        # Add execute permission to test escalation logic
        store = pdp._store
        store.create(
            CapabilityGrant(
                grant_id="grant-execute",
                principal="agent-researcher",
                scope=["admin"],
                resource="*",
                action=["execute"],
                granted_by="owner",
                granted_at=datetime.now(timezone.utc),
            )
        )
        result = pdp.evaluate(
            principal="agent-researcher",
            action="execute",
            resource="script-001",
            workspace_id="ws-test",
        )
        assert result.decision == Decision.ESCALATE
        assert result.obligations is not None


class TestCapabilityGrantStore:
    """CapabilityGrantStore validation and lookup."""

    def test_create_valid_grant(self):
        """A valid grant should be stored without error."""
        store = CapabilityGrantStore()
        grant = CapabilityGrant(
            grant_id="grant-001",
            principal="agent-x",
            scope=["read"],
            resource="*",
            action=["read"],
            granted_by="owner",
            granted_at=datetime.now(timezone.utc),
        )
        store.create(grant)
        assert store._grants["grant-001"] is grant

    def test_create_invalid_grant_raises(self):
        """A grant with an invalid action enum should raise ValueError."""
        store = CapabilityGrantStore()
        grant = CapabilityGrant(
            grant_id="grant-002",
            principal="agent-x",
            scope=["read"],
            resource="*",
            action=["hack"],  # Invalid enum
            granted_by="owner",
            granted_at=datetime.now(timezone.utc),
        )
        with pytest.raises(ValueError) as exc_info:
            store.create(grant)
        assert "is not one of" in str(exc_info.value)

    def test_revoke_marks_grant(self):
        """Revoking a grant should set revoked_at."""
        store = CapabilityGrantStore()
        grant = CapabilityGrant(
            grant_id="grant-003",
            principal="agent-x",
            scope=["read"],
            resource="*",
            action=["read"],
            granted_by="owner",
            granted_at=datetime.now(timezone.utc),
        )
        store.create(grant)
        assert store.revoke("grant-003", "owner", "compromised") is True
        assert grant.revoked_at is not None
        assert grant.revocation_reason == "compromised"

    def test_revoke_missing_grant_returns_false(self):
        """Revoking a non-existent grant should return False."""
        store = CapabilityGrantStore()
        assert store.revoke("grant-missing", "owner", "test") is False
