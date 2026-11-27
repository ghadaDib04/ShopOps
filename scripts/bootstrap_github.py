#!/usr/bin/env python3

"""
Resume-safe ShopOps GitHub issue bootstrap.

Creates:
- 35 mission issues
- 8 sprint tracking issues

Existing issues are detected by title and skipped.
All issues remain unassigned unless --assign is explicitly used.
"""

import argparse
import csv
import json
import re
import subprocess
import sys

ap = argparse.ArgumentParser()
ap.add_argument("--repo", default="ghadaDib04/ShopOps")
ap.add_argument("--assign", nargs="*", default=[])
a = ap.parse_args()

who = dict(x.split("=", 1) for x in a.assign)
repo = ["--repo", a.repo]


def gh(*args):
    cmd = ["gh", *args, *repo]

    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True
    )

    if result.returncode != 0:
        print(f"\nGitHub CLI error: {' '.join(cmd)}")
        print(result.stderr)
        raise SystemExit(result.returncode)

    return result.stdout.strip()


def get_existing_issues():
    print("Checking existing GitHub issues...")

    output = gh(
        "issue", "list",
        "--state", "all",
        "--limit", "1000",
        "--json", "number,title"
    )

    return {
        item["title"]: int(item["number"])
        for item in json.loads(output)
    }


# Load missions
with open("docs/missions.tsv", newline="", encoding="utf-8") as f:
    rows = list(csv.DictReader(f, delimiter="\t"))

sprints = sorted({r["sprint"] for r in rows})

# Check GitHub before creating anything
existing = get_existing_issues()
print(f"Found {len(existing)} existing issues.")

num = {}


def body(r, blocks=()):
    deps = [d for d in r["depends"].split(",") if d]

    with open(r["doc"], encoding="utf-8") as f:
        doc = f.read().split("\n", 1)[1].lstrip()

    head = f"> Source document (canonical): `{r['doc']}`\n\n"

    head += "**Depends on:** " + (
        ", ".join(
            f"{d} (#{num.get(d, '?')})" for d in deps
        ) or "nothing"
    ) + "  \n"

    head += "**Blocks:** " + (
        ", ".join(
            f"{b} (#{num.get(b, '?')})" for b in blocks
        ) or "-"
    ) + "\n\n"

    return head + doc


# Create missing mission issues
print("\nProcessing mission issues...")

for r in rows:
    title = f"{r['id']} - {r['title']}"

    if title in existing:
        num[r["id"]] = existing[title]
        print(f"SKIP {r['id']}: already exists as #{num[r['id']]}")
        continue

    deps = [d for d in r["depends"].split(",") if d]

    labels = ["type:task", f"sprint:{r['sprint']}"]

    if deps:
        labels.append("blocked")

    if r["flags"] == "risk":
        labels.append("risk")

    args = [
        "issue", "create",
        "--title", title,
        "--body", body(r),
        "--label", ",".join(labels)
    ]

    if r["owner"] in who:
        args += ["--assignee", who[r["owner"]]]

    url = gh(*args)
    match = re.search(r"/issues/(\d+)", url)

    if not match:
        print(f"Could not extract issue number from: {url}")
        sys.exit(1)

    num[r["id"]] = int(match.group(1))
    existing[title] = num[r["id"]]

    print(f"CREATED {r['id']}: #{num[r['id']]}")


# Calculate blocking relationships
blocks = {
    r["id"]: [
        x["id"] for x in rows
        if r["id"] in x["depends"].split(",")
    ]
    for r in rows
}


# Update all mission issues with complete dependency references
print("\nUpdating mission dependencies...")

for r in rows:
    gh(
        "issue", "edit",
        str(num[r["id"]]),
        "--body", body(r, blocks[r["id"]])
    )

    print(f"UPDATED {r['id']}: #{num[r['id']]}")


# Create missing sprint tracking issues
print("\nProcessing sprint tracking issues...")

for s in sprints:
    title = f"{s} - Sprint tracking"

    items = "".join(
        f"- [ ] #{num[r['id']]} {r['id']} {r['title']}\n"
        for r in rows if r["sprint"] == s
    )

    if title in existing:
        print(f"SKIP {title}: already exists as #{existing[title]}")
        continue

    url = gh(
        "issue", "create",
        "--title", title,
        "--label", f"type:sprint,sprint:{s}",
        "--body", f"Parent issue for sprint {s}.\n\n{items}"
    )

    match = re.search(r"/issues/(\d+)", url)

    if not match:
        print(f"Could not extract issue number from: {url}")
        sys.exit(1)

    existing[title] = int(match.group(1))
    print(f"CREATED {title}: #{match.group(1)}")


# Update docs/status.md
print("\nUpdating docs/status.md...")

with open("docs/status.md", encoding="utf-8") as f:
    status = f.read()

for r in rows:
    issue_id = r["id"]
    pattern = rf"(\|\s*{re.escape(issue_id)}\s*\|)\s*(?:#\d+\s*)?\|"

    status = re.sub(
        pattern,
        lambda m: f"{m.group(1)} #{num[issue_id]} |",
        status
    )

with open("docs/status.md", "w", encoding="utf-8") as f:
    f.write(status)

print("\n====================================")
print("ShopOps issue bootstrap completed.")
print(f"Mission issues: {len(rows)}")
print(f"Sprint issues: {len(sprints)}")
print(f"Total expected: {len(rows) + len(sprints)}")
print("All mission issues remain unassigned unless explicitly assigned.")
print("Review and commit docs/status.md.")
print("====================================")
