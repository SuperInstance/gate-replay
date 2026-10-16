#!/usr/bin/env python3
"""Adversarial busy corpus — the combinations 48 real idles don't cover.

Built in response to external review: "you validated does-it-skip-idle,
not does-it-catch-work." Each row is a digest-shaped probe with a stated
ground-truth reason. Borderline rows say so in the reason; where ground
truth is genuinely debatable the label reflects the SAFE answer for a
gate (busy — the LLM decides, not the gate).

Usage: python3 adversarial.py > adversarial.jsonl
"""
import json

ROWS = [
    # --- fresh work, various carriers ---
    ("busy", "fresh single task, no issues",
     "open tasks: 1   task: update the dependency list in README"),
    ("busy", "fresh task + prior idle outcome",
     "open tasks: 1   task: triage the new CI failure   open issues: 0   "
     "last cycle outcome: Completed: awaiting further instructions"),
    ("busy", "two fresh tasks",
     "open tasks: 2   task: reply to Casey on telegram (telegram 5 min ago)"
     "   task: investigate failing test in tests/test_agent.py"),
    ("busy", "hot issue, empty board",
     "open tasks: 0   open issues: 1   issue #7: Actions workflow failing "
     "on main since last push"),
    ("busy", "hot issue + telegram",
     "open tasks: 1   task: respond to owner message (telegram 2 min ago)"
     "   open issues: 1   issue #8: security advisory for a pinned dep"),
    ("busy", "many fresh issues",
     "open tasks: 0   open issues: 4   issue #9: broken link   "
     "issue #10: typo in onboarding   issue #11: feature request: digest "
     "email   issue #12: stale badge"),
    ("busy", "fleet bottle awaiting reply",
     "open tasks: 0   open issues: 1   issue #5: Fleet bottle from "
     "zero-alpha requesting status report"),
    ("busy", "mixed: stale task + fresh issue",
     "open tasks: 1   task: check old registration thread (telegram "
     "2026-09-20)   open issues: 1   issue #13: user reports vault 404 on "
     "list_issues"),
    ("busy", "task phrased as a question to the agent",
     "open tasks: 1   task: can you summarize what changed in v0.4?"),
    ("busy", "bug report on board",
     "open tasks: 1   task: agent posted duplicate comment on issue #1 — "
     "investigate echo"),

    # --- should stay idle: decayed/stale/bookkeeping only ---
    ("idle", "all tasks stale (weeks old), no issues",
     "open tasks: 2   task: follow up registration (telegram 2026-09-18)"
     "   task: check thread from three weeks ago (telegram 2026-09-20)"),
    ("idle", "board empty, prior gated_idle",
     "open tasks: 0   open issues: 0   last cycle outcome: gated_idle"),
    ("idle", "board empty, awaiting outcome",
     "open tasks: 0   open issues: 0   last cycle outcome: Completed: "
     "awaiting further instructions"),
    ("idle", "one stale task, nothing else",
     "open tasks: 1   task: revisit the 2026-09-12 telegram thread"),

    # --- borderline: label busy (LLM should decide, not the gate) ---
    ("busy", "borderline: fresh task phrased vaguely",
     "open tasks: 1   task: look into the thing Casey mentioned"),
    ("busy", "borderline: issue that may be human-facing",
     "open tasks: 0   open issues: 1   issue #4: question for the "
     "maintainer about roadmap"),
    ("busy", "borderline: stale task but recent outcome says unhandled",
     "open tasks: 1   task: old registration follow-up (telegram "
     "2026-09-20)   open issues: 0   last cycle outcome: Completed: "
     "attempted registration, blocked on vault 404"),

    # --- tricky negatives that LOOK busy ---
    ("idle", "mentions of tasks in past outcome only",
     "open tasks: 0   open issues: 0   last cycle outcome: Completed: "
     "the 'Write your first journal entry' task fully"),
    ("idle", "issue count zero but historical issue lines in outcome",
     "open tasks: 0   open issues: 0   last cycle outcome: commented on "
     "issue #1 and updated board, nothing further needed"),
    ("idle", "telegram messages already consumed (marked done)",
     "open tasks: 0   open issues: 0   last cycle outcome: Completed: "
     "replied to all telegram messages"),

    # --- unknowns / failures must not look like work ---
    ("idle", "issue fetch failed, board empty, prior idle",
     "open tasks: 0   open issues: fetch failed, count unknown   "
     "last cycle outcome: gated_idle"),
    ("idle", "unknown issues but empty board and idle prior",
     "open tasks: 0   open issues: unknown (not reconstructable from "
     "history)   last cycle outcome: Completed: awaiting further "
     "instructions"),
    ("busy", "unknown issues BUT board has fresh work",
     "open tasks: 1   task: draft the fleet coordination doc   "
     "open issues: unknown (fetch failed)"),
    ("busy", "issues unknown and prior outcome was an ERROR (retry worth)",
     "open tasks: 0   open issues: unknown (fetch failed)   last cycle "
     "outcome: llm_error after 3 attempts"),
]

PREFIX = "Agent digest: "

for label, reason, body in ROWS:
    print(json.dumps({
        "cycle": "adv-" + reason.split()[0] + "-" + str(ROWS.index((label, reason, body))),
        "ts": "adversarial",
        "digest": PREFIX + body,
        "label": label,
        "label_reason": reason,
        "synthetic": True,
    }))
