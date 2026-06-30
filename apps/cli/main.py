"""Animus-Mind CLI entry point.

Commands: validate, migrate, evidence, health-check, policy-demo.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


def _run_pytest(test_path: str | None = None, verbose: bool = True) -> int:
    """Run pytest and return exit code."""
    cmd = ["python3", "-m", "pytest"]
    if verbose:
        cmd.append("-v")
    if test_path:
        cmd.append(test_path)
    result = subprocess.run(cmd, cwd=Path(__file__).resolve().parent.parent.parent)
    return result.returncode


def _cmd_validate() -> int:
    """Run schema compilation tests."""
    print("[validate] Running schema compilation tests...")
    return _run_pytest("tests/schema/")


def _cmd_health_check() -> int:
    """Run full test suite."""
    print("[health-check] Running full test suite...")
    return _run_pytest()


def _cmd_policy_demo() -> int:
    """Demonstrate the Policy Decision Point."""
    from datetime import datetime, timedelta, timezone

    from modules.identity_policy import (
        CapabilityGrant,
        CapabilityGrantStore,
        Decision,
        PolicyDecisionPoint,
    )

    print("[policy-demo] Animus-Mind Policy Decision Point demo")
    print("-" * 50)

    store = CapabilityGrantStore()
    store.create(
        CapabilityGrant(
            grant_id="grant-researcher",
            principal="agent-researcher",
            scope=["read", "write"],
            resource="ws-demo/*",
            action=["create", "read", "update"],
            granted_by="owner-arete",
            granted_at=datetime.now(timezone.utc),
            expires_at=datetime.now(timezone.utc) + timedelta(days=7),
            budget={"max_calls": 1000, "window_seconds": 3600},
            conditions={"allowed_workspaces": ["ws-demo"]},
        )
    )

    pdp = PolicyDecisionPoint(store)

    # Scenario 1: Allowed action
    print("\n1. Allowed action (read):")
    result = pdp.evaluate(
        principal="agent-researcher",
        action="read",
        resource="mem-001",
        workspace_id="ws-demo",
    )
    print(f"   Decision: {result.decision.value}")
    print(f"   Reason:   {result.reason}")

    # Scenario 2: Unknown principal
    print("\n2. Unknown principal (agent-hacker):")
    result = pdp.evaluate(
        principal="agent-hacker",
        action="read",
        resource="mem-001",
        workspace_id="ws-demo",
    )
    print(f"   Decision: {result.decision.value}")
    print(f"   Reason:   {result.reason}")
    print(f"   Denial:   {result.denial_reason_code.value if result.denial_reason_code else 'N/A'}")

    # Scenario 3: High-risk action escalates
    print("\n3. High-risk action (execute) — requires approval:")
    store.create(
        CapabilityGrant(
            grant_id="grant-execute",
            principal="agent-researcher",
            scope=["admin"],
            resource="*",
            action=["execute"],
            granted_by="owner-arete",
            granted_at=datetime.now(timezone.utc),
        )
    )
    result = pdp.evaluate(
        principal="agent-researcher",
        action="execute",
        resource="script-001",
        workspace_id="ws-demo",
    )
    print(f"   Decision: {result.decision.value}")
    print(f"   Reason:   {result.reason}")
    if result.obligations:
        print(f"   Obligations: {result.obligations}")

    print("\n" + "-" * 50)
    print("[policy-demo] Complete — deterministic core operational")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(prog="animus-mind", description="Animus-Mind CLI")
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("validate", help="Run schema and contract validation")
    sub.add_parser("migrate", help="Run database migrations")
    sub.add_parser("evidence", help="Assemble evidence bundle for current commit")
    sub.add_parser("health-check", help="Run truth baseline and smoke tests")
    sub.add_parser("policy-demo", help="Demonstrate the Policy Decision Point")

    args = parser.parse_args()

    if args.command == "validate":
        return _cmd_validate()
    elif args.command == "migrate":
        print("[migrate] Database migrations — placeholder")
        return 0
    elif args.command == "evidence":
        print("[evidence] Evidence bundle assembly — placeholder")
        return 0
    elif args.command == "health-check":
        return _cmd_health_check()
    elif args.command == "policy-demo":
        return _cmd_policy_demo()
    else:
        parser.print_help()
        return 1


if __name__ == "__main__":
    sys.exit(main())
