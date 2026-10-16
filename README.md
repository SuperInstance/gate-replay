# gate-replay — calibrate the idle gate from git history

The zero-poc agent's v0.4 idle gate skips an LLM cycle when a System-1
decision model confidently says "nothing actionable" (threshold 0.6, model
`laya`, both chosen from a two-example synthetic test). This PoC replaces
that guess with measurement: git history IS a labeled corpus — every
`think: autonomous cycle` commit is one cycle, and what the cycle changed
is the label.

## What it does

- `extract.py <zero-poc path> > corpus.jsonl` — reconstructs the digest
  each cycle WOULD have seen (from the previous cycle's tree, mirroring
  `agent.py build_gate_digest()` exactly) and labels it:
  **busy** = diff touched non-bookkeeping files OR unchecked open tasks
  existed at start; **idle** = otherwise. Composite label because
  consuming a Telegram task edits only TASKS.md.
- `replay.py` — posts every digest through the EXACT `gate_says_work()`
  question to Ollaya (`laya`, `winnow:e4b`), sweeps thresholds, prints
  idle-skip rate (savings) vs false-idle rate (missed work) → `results.json`.

## Measured (2026-10-16, 49 real cycles + 6 synthetic, RTX 4050)

| model | idle-skip @0.6 | false-idle | idle "no" conf |
|---|---|---|---|
| winnow:e4b | **98%** | **0%** (holds 0.50–0.95) | 0.96–0.99 (n=48) |
| laya | 6% | 0% | median 0.44 (only 19/51 chose "no") |

- The agent's actual recent life: 48 of 49 cycles idle. **winnow:e4b would
  have skipped ~98% of them at zero measured false-idle** — the empirical
  case for raising heartbeat cadence (gate first, LLM only when needed).
- **Actionable: v0.4's default `DECISION_MODEL=laya` is the wrong tool for
  the gate** (it barely fires on real digests). Use a winnow-class model.
- 3 rows hit server timeouts (excluded, not guessed) — they are the first
  three rows positionally (post-warmup instability), not ambiguous cases.
- Known blind spot: "open issues" is not reconstructable from git, so the
  one real busy cycle (issue-driven docs fix) is digest-invisible — every
  model and the minigate distillation read it idle. Production digests
  include live issue titles, so this is a corpus artifact, not a gate
  defect. Recorded, not hidden.

## Adversarial set (24 probes: 15 busy / 9 idle, signal combos the real
history never shows — stale+fresh mixes, error retries, fetch-failures,
human-facing issues, consumed-work outcomes)

| model | busy caught | false-idle | idle skipped | zero-false-idle point |
|---|---|---|---|---|
| winnow:e4b | 14/15 | 7% (thr 0.6–0.9) | 67% | threshold 0.95 |
| minigate v1 (corpus-only) | 11/15 | 27% | 78% | — |
| minigate v2 (+adversarial) | 13/15 | 13% | 78% | — |

Reading: the semantic model generalizes where distilled features don't
(minigate's misses trace to two learned-but-fragile weights). winnow's
zero-false-idle point is at **0.95, not 0.6** — a very different
recommendation than the production default. All numbers are
idle-detection/busy-detection rates on this corpus, NOT accuracy claims;
production drift will differ. Run the gate in **shadow mode** (log, don't
skip) before granting skip authority. Calibration of the 0.96–0.99
confidences is unverified — treat as ranking, not probability.

## Next

Feed corpus.jsonl to `../minigate` (distilled serverless gate). Grow the
busy class from real cycles once cadence increases. Track the false-idle
metric in production from `.agent-state.json` outcomes.
