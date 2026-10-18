# gate-replay — measure an idle gate against real agent history

A heartbeat-driven autonomous agent wakes on a timer, and most of the time
there is nothing to do — so an *idle gate* (a cheap one-shot "System-1"
classifier) is asked "any actionable work?" before the expensive LLM cycle
runs. gate-replay replaces the guesswork behind that gate with measurement:
it turns the agent's own git history into a labeled corpus, then replays
every digest through the exact production gate question and sweeps
thresholds. On the history measured here, the model the agent actually
shipped as its gate default would have skipped 6% of idle cycles; the right
model would have skipped 98% at zero measured false-idles.

## How it works

```
git history ──extract.py──> corpus.jsonl ──replay.py──> threshold sweep, results.json
                                │
hand-built probes ──adversarial.py──> adversarial.jsonl ┘
corpus + adversarial ──────────────> combined.jsonl ──jev_bench.py──> hosted-API results
```

- `extract.py <repo> > corpus.jsonl` — every `think: autonomous cycle`
  commit ends one heartbeat cycle. For each cycle, reconstruct the digest
  the gate WOULD have seen at cycle start (from the previous cycle's tree,
  mirroring the production digest builder) and label it: **busy** = the
  cycle touched non-bookkeeping files OR unchecked open tasks existed at
  start; **idle** = otherwise. The composite label matters because
  consuming a user task can edit only the task board — diff-alone would
  mislabel exactly the cycles a gate must never skip.
- `replay.py` — posts every digest through the exact gate question
  (`choice` + `confidence`) to a local decision server, sweeps thresholds,
  and prints idle-skip rate (savings) vs false-idle rate (missed work) →
  `<corpus>-results.json` (the measured run's snapshot is checked in as
  `results.json`).
- `adversarial.py` — 24 hand-built probes (15 busy / 9 idle) covering
  signal combinations the real history never shows: stale+fresh mixes,
  error retries, fetch-failures, consumed-work outcomes. Regenerating the
  file reproduces the checked-in `adversarial.jsonl` byte-for-byte.
- `jev_bench.py` — the same corpora against a hosted decision API
  (TypeSafe Jev), plus judge/injection/fan-out experiments; needs
  `TYPESAFE_API_KEY`.

The decision server used for the local numbers is Ollaya, which serves
small classification models behind a `/v1/decisions` endpoint (`winnow:e4b`
is the ~8 GB discriminative model, `laya` a much smaller classifier).

## Quickstart

Python 3, standard library only. All commands below run offline except the
two marked as needing a server or API key.

```bash
git clone https://github.com/SuperInstance/gate-replay && cd gate-replay

python3 adversarial.py | head -3            # first adversarial probes
python3 adversarial.py > adversarial.jsonl  # regenerates the checked-in file exactly

# Rebuild a corpus from any repo that follows the heartbeat convention:
# one author, commits titled "think: autonomous cycle ...", TASKS.md and
# MEMORY.md at the root (see extract.py docstring). The shipped corpus.jsonl
# (55 rows: 49 real cycles + 6 synthetic edge cases) came from the private
# parent agent repo, which is not published — the corpus itself ships here.
python3 extract.py /path/to/heartbeat-repo > my-corpus.jsonl

python3 replay.py --help                    # options for the live replay
python3 replay.py --url http://localhost:11435 --models winnow:e4b,laya \
                  --corpus my-corpus.jsonl  # NEEDS the decision server up

TYPESAFE_API_KEY=... python3 jev_bench.py   # optional, ~$0.02 per full run
```

## Measured (2026-10-16, 49 real cycles + 6 synthetic, RTX 4050)

| model | idle-skip @0.6 | false-idle | idle "no" conf |
|---|---|---|---|
| winnow:e4b | **98%** | **0%** (holds 0.50–0.95) | 0.96–0.99 (n=48) |
| laya | 6% | 0% | median 0.44 (only 19/51 chose "no") |

- The agent's actual recent life: 48 of 49 cycles idle. **winnow:e4b would
  have skipped ~98% of them at zero measured false-idle** — the empirical
  case for raising heartbeat cadence (gate first, LLM only when needed).
- **Actionable: the shipped default decision model (`laya`) is the wrong
  tool for the gate** (it barely fires on real digests). Use a
  winnow-class model.
- 3 rows hit server timeouts (excluded, not guessed) — they are the first
  three rows positionally (post-warmup instability), not ambiguous cases.
- Known blind spot: "open issues" is not reconstructable from git, so the
  one real busy cycle (issue-driven docs fix) is digest-invisible — every
  model and the minigate distillation read it idle. Production digests
  include live issue titles, so this is a corpus artifact, not a gate
  defect. Recorded, not hidden.

### Adversarial set (24 probes: 15 busy / 9 idle)

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

### Hosted decision API (2026-10-17, live run — details in JEV-RESULTS.md)

79 gate rows (corpus + adversarial: 60 idle / 19 busy); total spend ~$0.02.

| model:framing | idle-skip | false-idle | med latency | cost/1k calls |
|---|---|---|---|---|
| jev-1.14.0:choice | 57/60 (95%) | 2/19 (10.5%) | 0.26s | $0.017 |
| jev-1.14.0:noul | 56/60 (93%) | 2/19 | 0.24s | $0.015 |
| jev-1.13.0:choice | 57/60 | 2/19 | 0.28s | $0.017 |
| jev-1.13.0:noul | 56/60 | 2/19 | 0.24s | $0.015 |

No infra, 0.25s flat, ~$0.05/month at production cadence — but 10.5%
false-idle on the combined (harder) set, and the one false-idle class
(`llm_error after 3 attempts` + issues fetch-failed) says the
deterministic blind-veto stays in front of ANY model gate. The judge
experiments in the same run: weasel claim caught at p=1.00, injection
7/8 attacks caught.

## Ecosystem

Built and measured around a private heartbeat-driven maintainer agent; the
public siblings are:

- https://github.com/SuperInstance/gate-replay — this repo: calibrate the
  idle gate from real history.
- https://github.com/SuperInstance/minigate — the gate distilled to
  `gate.py` + a 9-weight `gate.json`; zero-dependency deployment, trained
  on this repo's corpora.
- https://github.com/SuperInstance/cycle-judge — one-shot trust judges
  (completion, flail, injection) using the same decision-server protocol.

## Status and limitations

- PoC, measured once (2026-10-16/17) on one agent's history: 49 real
  cycles, exactly one real busy cycle. Small n; treat every number as a
  case study, not a benchmark.
- Corpus artifacts: open issues not reconstructable from git (see above);
  3 timeout rows excluded.
- `replay.py` requires a running decision server; without one it will
  retry, and the sweep divides by zero once every row has failed — it is
  not meant to run offline.
- Not deployed in production yet; shadow-mode deployment is the
  recommended next step, then track the false-idle metric from live
  outcomes.

## License

MIT — see [LICENSE](LICENSE).
