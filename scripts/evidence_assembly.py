#!/usr/bin/env python3
"""Assemble an evidence bundle for the current release.

Per v2.2 operational evidence standard, every release must create an
immutable evidence directory with machine-readable proof of what ran,
against which code and contracts, under which configuration, with what result.

Usage:
    python scripts/evidence_assembly.py [--release-id <id>]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _git_sha() -> str:
    try:
        return (
            subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
        )
    except subprocess.CalledProcessError:
        return "unknown"


def _git_dirty() -> bool:
    try:
        out = subprocess.check_output(["git", "status", "--porcelain"], text=True).strip()
        return len(out) > 0
    except subprocess.CalledProcessError:
        return True


def _file_digest(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def _schema_digests(schema_dir: Path) -> dict[str, str]:
    result: dict[str, str] = {}
    for path in sorted(schema_dir.glob("*.schema.json")):
        result[path.name] = _file_digest(path)
    return result


def assemble(release_id: str | None = None) -> Path:
    repo_root = Path(__file__).parent.parent.resolve()
    release_id = release_id or f"release-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}"
    evidence_dir = repo_root / "evidence" / "releases" / release_id
    evidence_dir.mkdir(parents=True, exist_ok=True)

    manifest: dict[str, Any] = {
        "release_id": release_id,
        "source_control_commit": _git_sha(),
        "dirty_tree": _git_dirty(),
        "execution_start": datetime.now(timezone.utc).isoformat(),
        "environment_identity": os.getenv("HOSTNAME", "unknown"),
        "schema_digests": _schema_digests(repo_root / "contracts" / "schemas"),
    }

    # Write manifest
    manifest_path = evidence_dir / "manifest.json"
    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=2, sort_keys=True)

    # Placeholder reports (populated by CI/test runs)
    for report_name in [
        "schema_report.json",
        "unit_test_report.xml",
        "integration_test_report.xml",
        "adversarial_report.json",
        "fault_injection_report.json",
        "gate_results.json",
    ]:
        placeholder = {"status": "not_run", "release_id": release_id}
        with open(evidence_dir / report_name, "w") as f:
            json.dump(placeholder, f, indent=2)

    # Manifest integrity
    manifest["manifest_digest"] = _file_digest(manifest_path)
    manifest["execution_complete"] = datetime.now(timezone.utc).isoformat()
    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=2, sort_keys=True)

    print(f"Evidence bundle assembled: {evidence_dir}")
    print(f"Manifest: {manifest_path}")
    return evidence_dir


def main() -> int:
    parser = argparse.ArgumentParser(description="Assemble evidence bundle")
    parser.add_argument("--release-id", help="Explicit release identifier")
    args = parser.parse_args()
    assemble(args.release_id)
    return 0


if __name__ == "__main__":
    sys.exit(main())
