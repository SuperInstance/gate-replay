# JEV-RESULTS — TypeSafe Jev on our bench (2026-10-17, live run)
79 gate rows (corpus + adversarial: 60 idle / 19 busy) × 2 models × 2
framings; judge battery; injection set; fan-out demo. Ledger: 346 rows
filed (jev-ledger.jsonl). Total spend: ~$0.02. All numbers live.

## Gate (the headline)

| model:framing | idle-skip | false-idle | med latency | cost/1k calls |
|---|---|---|---|---|
| jev-1.14.0:choice | 57/60 (95%) | 2/19 (10.5%) | 0.26s | $0.017 |
| jev-1.14.0:noul | 56/60 (93%) | 2/19 | 0.24s | $0.015 |
| jev-1.13.0:choice | 57/60 | 2/19 | 0.28s | $0.017 |
| jev-1.13.0:noul | 56/60 | 2/19 | 0.24s | $0.015 |

- **Framings are equivalent** (choice ≈ noul; the question is
  well-posed either way — ledger median sharpness 0.94 over 318 gate
  answers).
- **vs local:** winnow:e4b scored 98% idle-skip @ 0 false-idle on the
  corpus-only set and 7% false-idle on the adversarial set — still the
  sharpest busy-discrimination, but it needs an 8 GB local server with
  122s cold loads. Jev: no infra, 0.25s flat, 95% skip, 10.5%
  false-idle on the COMBINED (harder) set.
- **The one false-idle class:** `llm_error after 3 attempts` + issues
  fetch-failed — Jev confidently reads "no work" past the error
  signal. Verdict: **the deterministic blind-veto stays in front of
  ANY model gate** (minigate already has it; wrap Jev the same way).
- **Cost at production cadence:** 96 beats/day × 30 days ≈ 2,880 calls
  ≈ **$0.05/month.** The DECISION_URL-in-Actions problem is dead.

## Judge

- **Weasel claim: caught at p=1.00 on both models** (`task_completed`
  = not_completed) — sharper than winnow's 0.99 and vastly beyond
  laya's 0.31. Task-framing + Jev is the best completion judge we have
  measured.
- **The ordinal score question PASSED** (confidence 0.00 on 1.13,
  0.30 on 1.14): the claim_supported score-framing is ill-posed for
  this situation — the truth sits between "partial" and "overstated"
  and Jev refuses to pretend otherwise. First live validation of the
  ledger's 0.5-means-pass principle: use the sharp question
  (task_completed), rewrite the dull one.
- **Injection: 7/8 attacks caught** (vs laya's 0/6), with 1/2 benign
  false-flagged (the "ignore previous similar reports" edge — hard
  for everyone). With the deterministic [UNTRUSTED] annotation already
  shipped in agent.py, Jev screening would make the trust layer
  genuinely strong rather than decorative.

## Fan-out (the architecture win)

One 0.2s call returned gate (work=yes), stake (0.19 — sensible for a
telegram reply), and injection (0.09 clean) together. **The entire
System-1 layer fits in a single sub-second call per heartbeat.**

## Deployment recommendation

1. Wrap Jev with the deterministic blind-veto (fetch-failed → RUN).
2. Point zero-poc's DECISION_URL at a thin adapter (vault action or
   direct with the key in the vault) using noul or choice framing —
   both work; noul is marginally cheaper.
3. Keep minigate as the zero-dependency fallback (Jev outage →
   fail-open to local/CI gate); keep winnow for the local bench where
   sharpness matters more than latency.
4. Ledger every call (jev rows = teacher) → the decision-ledger
   analytics now have real data: teacher labels for Platt-scaling
   laya, pass-clusters for question rewrites.

## Ledger analytics (first real run)

- `actionable_work`: n=318, median sharpness 0.94 — well-posed.
- `task_completed`: sharp 1.00 — well-posed, razor.
- `claim_supported` (score framing): median 0.30, min 0.00 —
  ILL-POSED → rewrite queue (needs n≥5 states to auto-flag; the
  stats caught it first).
- `is_injection`: median 0.80 — well-posed.
