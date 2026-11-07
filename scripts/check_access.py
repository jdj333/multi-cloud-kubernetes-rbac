#!/usr/bin/env python3
"""Assert authorization decisions and real reads. Never treat API errors as denies."""
import argparse
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def run(command):
    return subprocess.run(command, text=True, capture_output=True, timeout=40, check=False)


def decision_matches(result, allowed):
    # kubectl can-i returns 1 for a genuine denial, but also for connection errors.
    return (result.stdout.strip(), result.returncode) == ("yes", 0) if allowed else (
        result.stdout.strip(), result.returncode
    ) == ("no", 1)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--context", required=True, help="explicit kubeconfig context")
    parser.add_argument("--namespace", default="team-a")
    parser.add_argument("--other-namespace", default="team-b")
    parser.add_argument("--as-user", help="admin-only RBAC test via impersonation")
    parser.add_argument("--group", help="group to impersonate; requires --as-user")
    args = parser.parse_args()
    if bool(args.as_user) != bool(args.group):
        parser.error("--as-user and --group must be supplied together")
    if args.namespace == args.other_namespace:
        parser.error("test namespaces must differ")
    base = ["kubectl", "--context", args.context, "--request-timeout=30s"]
    if args.as_user:
        base += [f"--as={args.as_user}", f"--as-group={args.group}", "--as-group=system:authenticated"]
    failures = 0
    for case in json.loads((ROOT / "tests/cases.json").read_text()):
        command = base + ["auth", "can-i", case["verb"], case["resource"]]
        if case.get("subresource"):
            command += [f"--subresource={case['subresource']}"]
        if case["scope"] in ("team", "other"):
            command += ["--namespace", args.namespace if case["scope"] == "team" else args.other_namespace]
        elif case["scope"] == "all":
            command.append("--all-namespaces")
        result = run(command)
        passed = decision_matches(result, case["allowed"])
        print(f"{'PASS' if passed else 'FAIL'} {case['verb']} {case['resource']}"
              f"{('/' + case['subresource']) if case.get('subresource') else ''}"
              f" ({case['scope']}): expected {'allow' if case['allowed'] else 'deny'}")
        if not passed:
            print(f"  exit={result.returncode}, stdout={result.stdout!r}, stderr={result.stderr!r}")
            failures += 1

    # These hit resource endpoints, not just SelfSubjectAccessReview.
    for resource, namespace, allowed in (
        ("pods", args.namespace, True),
        ("secrets", args.namespace, False),
        ("pods", args.other_namespace, False),
    ):
        result = run(base + ["get", resource, "--namespace", namespace, "-o", "json"])
        if allowed:
            try:
                passed = result.returncode == 0 and isinstance(json.loads(result.stdout)["items"], list)
            except (ValueError, KeyError, TypeError):
                passed = False
        else:
            passed = result.returncode != 0 and "(Forbidden)" in result.stderr
        print(f"{'PASS' if passed else 'FAIL'} actual GET {resource} in {namespace}")
        if not passed:
            # Do not print response bodies: an unexpected successful secrets read may contain secrets.
            print(f"  Unexpected response; exit={result.returncode}. Body omitted.")
            failures += 1

    if args.as_user:
        outsider = run(["kubectl", "--context", args.context, "--request-timeout=30s",
                        "--as=rbac-unbound-user", "--as-group=system:authenticated",
                        "auth", "can-i", "list", "pods", "--namespace", args.namespace])
        passed = decision_matches(outsider, False)
        print(f"{'PASS' if passed else 'FAIL'} unbound identity cannot list team pods")
        failures += int(not passed)

    print(f"Result: {failures} failure(s). Mode: {'impersonation' if args.as_user else 'real identity'}.")
    return int(failures > 0)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(2)
