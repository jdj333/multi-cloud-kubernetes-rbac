#!/usr/bin/env python3
"""Render the shared policy for one group without string-interpolating YAML."""
import argparse
import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]


def render(group, namespace="team-a"):
    if not re.fullmatch(r"[a-z0-9](?:[-a-z0-9]{0,61}[a-z0-9])?", namespace):
        raise ValueError("namespace must be a DNS label of 1 to 63 characters")
    if not group or group != group.strip() or any(ord(c) < 32 for c in group):
        raise ValueError("group must be nonempty with no control or surrounding whitespace")
    if group.startswith("system:"):
        raise ValueError("system: groups are reserved; use a dedicated team group")
    docs = []
    for name in ("namespace", "role", "rolebinding"):
        doc = yaml.safe_load((ROOT / "kubernetes" / f"{name}.yaml").read_text())
        if doc["kind"] == "Namespace":
            doc["metadata"]["name"] = namespace
        else:
            doc["metadata"]["namespace"] = namespace
        if doc["kind"] == "RoleBinding":
            doc["subjects"][0]["name"] = group
        docs.append(doc)
    return docs


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--group", required=True)
    parser.add_argument("--namespace", default="team-a")
    args = parser.parse_args()
    try:
        print(yaml.safe_dump_all(render(args.group, args.namespace), sort_keys=False), end="")
    except ValueError as exc:
        parser.error(str(exc))
