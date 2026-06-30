"""Identity, policy, and authorization for the Mind-class architecture.

Provides:
- PolicyDecisionPoint: deterministic evaluation of action requests
- CapabilityGrantStore: scoped authorization grants with budget/expiry

Design principle: default deny, fail closed. Every consequential action
must pass through the PDP. No model-generated code bypasses this layer.
"""

from .policy_decision_point import PolicyDecisionPoint, Decision
from .capability_store import CapabilityGrantStore, CapabilityGrant

__all__ = [
    "PolicyDecisionPoint",
    "Decision",
    "CapabilityGrantStore",
    "CapabilityGrant",
]
