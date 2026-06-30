"""Animus-Mind CLI entry point.

Commands: validate, migrate, evidence, health-check.
"""
import argparse
import sys


def main() -> int:
    parser = argparse.ArgumentParser(prog="animus-mind", description="Animus-Mind CLI")
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("validate", help="Run schema and contract validation")
    sub.add_parser("migrate", help="Run database migrations")
    sub.add_parser("evidence", help="Assemble evidence bundle for current commit")
    sub.add_parser("health-check", help="Run truth baseline and smoke tests")

    args = parser.parse_args()

    if args.command == "validate":
        print("[validate] Schema compilation — placeholder")
        return 0
    elif args.command == "migrate":
        print("[migrate] Database migrations — placeholder")
        return 0
    elif args.command == "evidence":
        print("[evidence] Evidence bundle assembly — placeholder")
        return 0
    elif args.command == "health-check":
        print("[health-check] Truth baseline — placeholder")
        return 0
    else:
        parser.print_help()
        return 1


if __name__ == "__main__":
    sys.exit(main())
