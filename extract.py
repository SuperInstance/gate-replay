#!/usr/bin/env python3
"""Extract a labeled corpus from zero-poc's git history.

Each `think: autonomous cycle` commit ends one heartbeat cycle. For every
cycle we reconstruct the digest the v0.4 gate WOULD have seen at cycle
start (from the previous cycle's tree) and label it:

  busy   = the cycle touched files beyond bookkeeping (MEMORY.md/TASKS.md)
           OR the board held unchecked open tasks at cycle start
  idle   = otherwise

The composite label matters: a cycle whose only real work was consuming a
Telegram task edits just TASKS.md, so diff-alone would mislabel it idle —
exactly the false-idle the gate must never cause. Caveats (also in README):
"open issues" cannot be reconstructed from git, so digests carry a constant
"unknown" for it; issue-driven cycles are therefore labeled only via the
board/diff signals.

Usage: python3 extract.py /path/to/zero-poc > corpus.jsonl
"""
import json
import subprocess
import sys

BOOKKEEPING = {"MEMORY.md", "TASKS.md"}


def git(repo, *args):
    out = subprocess.run(
        ["git", "-C", repo, *args], capture_output=True, text=True, check=True
    )
    return out.stdout


def show(repo, rev, path):
    try:
        return git(repo, "show", f"{rev}:{path}")
    except subprocess.CalledProcessError:
        return ""


def open_items(tasks_text):
    """Unchecked items in the ## Open section — mirrors agent.py's parse."""
    section = tasks_text.split("## Open", 1)[-1].split("\n## ", 1)[0]
    return [l.strip()[len("- [ ]"):].strip()
            for l in section.splitlines()
            if l.strip().startswith("- [ ]")]


def build_digest(tasks_text, memory_text):
    items = open_items(tasks_text)
    lines = [f"open tasks: {len(items)}"]
    for item in items[:5]:
        lines.append("  task: " + item[:120])
    tg = sum(1 for i in items if "(telegram" in i.lower())
    if tg:
        lines.append(f"unread user messages via telegram: {tg}")
    lines.append("open issues: unknown (not reconstructable from history)")
    outcomes = [l for l in memory_text.splitlines() if "Completed" in l]
    if outcomes:
        lines.append(f"last cycle outcome: {outcomes[-1][:120]}")
    return "Agent digest: " + " ".join(lines)


def main():
    repo = sys.argv[1]
    log = git(repo, "log", "--reverse", "--format=%H%x1f%an%x1f%s")
    commits = []
    for line in log.strip().splitlines():
        sha, author, subject = line.split("\x1f", 2)
        commits.append((sha, author, subject))
    cycles = [c for c in commits if c[2].startswith("think: autonomous cycle")]

    rows, skipped = [], 0
    for prev, cur in zip(cycles, cycles[1:]):
        window = git(repo, "log", "--format=%an", f"{prev[0]}..{cur[0]}")
        if any(a != "zero" for a in window.split()):
            skipped += 1  # maintenance commits inside the window: noisy cycle
            continue
        tasks_prev = show(repo, prev[0], "TASKS.md")
        memory_prev = show(repo, prev[0], "MEMORY.md")
        changed = git(repo, "diff", "--name-only", prev[0], cur[0]).split()
        substance = [f for f in changed if f not in BOOKKEEPING]
        items = open_items(tasks_prev)
        if substance:
            label, reason = "busy", f"changed non-bookkeeping files: {substance[:3]}"
        elif items:
            label, reason = "busy", f"{len(items)} open task(s) on board at start"
        else:
            label, reason = "idle", "no substance changes, empty board"
        rows.append({
            "cycle": cur[0][:10],
            "ts": cur[2].split()[-1],
            "digest": build_digest(tasks_prev, memory_prev),
            "label": label,
            "label_reason": reason,
            "synthetic": False,
        })

    for row in SYNTHETIC:
        rows.append(row)

    for row in rows:
        print(json.dumps(row))
    print(f"cycles: {len(cycles) - 1 - skipped} real (skipped {skipped} noisy), "
          f"{len(SYNTHETIC)} synthetic", file=sys.stderr)


# Hand-built edge cases the history doesn't cover (marked synthetic).
SYNTHETIC = [
    {"cycle": "syn-idle-1", "ts": "synthetic",
     "digest": "Agent digest: open tasks: 0 open issues: 0 last cycle outcome: "
               "Completed: awaiting further instructions",
     "label": "idle", "label_reason": "bench idle scenario (validated 2026-10-16)",
     "synthetic": True},
    {"cycle": "syn-idle-2", "ts": "synthetic",
     "digest": "Agent digest: open tasks: 0 open issues: 0 last cycle outcome: "
               "gated_idle",
     "label": "idle", "label_reason": "bench idle scenario post-gate",
     "synthetic": True},
    {"cycle": "syn-idle-stale", "ts": "synthetic",
     "digest": "Agent digest: open tasks: 1   task: check the old registration "
               "thread from three weeks ago (telegram 2026-09-20) open issues: 0",
     "label": "idle",
     "label_reason": "zombie task: stale telegram entry already handled long ago",
     "synthetic": True},
    {"cycle": "syn-busy-1", "ts": "synthetic",
     "digest": "Agent digest: open tasks: 1   task: Add a Usage section to "
               "README.md documenting the hermit-crab env vars open issues: 0",
     "label": "busy", "label_reason": "bench busy scenario (validated 2026-10-16)",
     "synthetic": True},
    {"cycle": "syn-busy-2", "ts": "synthetic",
     "digest": "Agent digest: open tasks: 2   task: reply to Casey on telegram "
               "(telegram 10 min ago)   task: fix the broken link in "
               "docs/architecture.md open issues: 1   issue #3: CI failing on "
               "main",
     "label": "busy", "label_reason": "fresh user message + real defect",
     "synthetic": True},
    {"cycle": "syn-busy-3", "ts": "synthetic",
     "digest": "Agent digest: open tasks: 0 open issues: 1   issue #5: Fleet "
               "bottle from zero-alpha requesting status report",
     "label": "busy", "label_reason": "unaddressed issue requiring action",
     "synthetic": True},
]

if __name__ == "__main__":
    main()
