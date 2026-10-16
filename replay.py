#!/usr/bin/env python3
"""Replay corpus.jsonl digests through the v0.4 idle-gate question.

Uses the EXACT question from zero-poc agent.py gate_says_work() so the
numbers measure production behavior, not an approximation. Warms each
model first (cold load: winnow ~11s, tev1 ~46s — see the decide()
timeout bug in the brainstorm) and uses a 60s timeout.

Output: per-model confidence separation, threshold sweep (idle-skip rate
= savings vs false-idle rate = missed work), and results.json.

Usage: python3 replay.py [--url http://localhost:11435] [--models laya,winnow:e4b]
"""
import argparse
import json
import time
import urllib.request

GATE_QUESTION = {
    "actionable_work": {
        "type": "choice",
        "instructions": (
            "An AI agent checks this digest before invoking its expensive "
            "reasoning model. Are there specific open items to act on?"
        ),
        "criteria": {
            "yes": "Specific open tasks, user requests, or unresolved "
                   "problems are listed",
            "no": "No specific open items; only idle, awaiting, or status "
                  "entries",
        },
    },
}


def decide(url, model, digest, timeout=60, retries=2):
    body = json.dumps({"model": model, "state": digest,
                       "questions": GATE_QUESTION}).encode()
    req = urllib.request.Request(
        f"{url.rstrip('/')}/v1/decisions", data=body,
        headers={"Content-Type": "application/json"})
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                answers = json.load(r).get("answers", {})
            a = answers.get("actionable_work", {})
            return a.get("choice"), a.get("confidence", 0.0)
        except Exception:
            if attempt == retries - 1:
                return None, None
            time.sleep(2)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="http://localhost:11435")
    ap.add_argument("--models", default="laya,winnow:e4b")
    args = ap.parse_args()
    models = args.models.split(",")
    rows = [json.loads(l) for l in open("corpus.jsonl")]

    for m in models:
        t0 = time.time()
        decide(args.url, m, "Agent digest: warmup")
        print(f"warmed {m} in {time.time()-t0:.1f}s", flush=True)

    results = []
    for i, row in enumerate(rows):
        results.append(dict(row))
        for m in models:
            choice, conf = decide(args.url, m, row["digest"])
            results[-1][f"choice_{m}"] = choice
            results[-1][f"conf_{m}"] = round(conf, 4) if conf is not None else None
        if (i + 1) % 10 == 0:
            print(f"  {i+1}/{len(rows)} replayed", flush=True)

    thresholds = [round(0.5 + 0.05 * k, 2) for k in range(10)]
    print(f"\n{'model':<12} {'thr':>5} {'idle-skip':>9} {'false-idle':>10}")
    summary = {}
    for m in models:
        idles = [r for r in results if r["label"] == "idle"
                 and r.get(f"choice_{m}") is not None]
        busies = [r for r in results if r["label"] == "busy"
                  and r.get(f"choice_{m}") is not None]
        failed = sum(1 for r in results if r.get(f"choice_{m}") is None)
        if failed:
            print(f"  {m}: {failed} rows failed all retries (excluded)")
        best = None
        for t in thresholds:
            skip_i = sum(1 for r in idles
                         if r[f"choice_{m}"] == "no" and r[f"conf_{m}"] >= t)
            false_b = sum(1 for r in busies
                          if r[f"choice_{m}"] == "no" and r[f"conf_{m}"] >= t)
            fr_i, fr_b = skip_i / len(idles), false_b / len(busies)
            print(f"{m:<12} {t:>5.2f} {fr_i:>8.0%} {fr_b:>10.0%}")
            if fr_b == 0 and best is None:
                best = t
        summary[m] = {"zero_false_idle_threshold": best}
        confs_no = [r[f"conf_{m}"] for r in idles if r[f"choice_{m}"] == "no"]
        confs_busy = [r[f"conf_{m}"] for r in busies]
        if confs_no:
            print(f"  {m} idle 'no' conf: min {min(confs_no):.2f} "
                  f"median {sorted(confs_no)[len(confs_no)//2]:.2f} "
                  f"max {max(confs_no):.2f} (n={len(confs_no)})")
        if confs_busy:
            print(f"  {m} busy conf: {['%.2f' % c for c in confs_busy]}")

    json.dump({"rows": results, "summary": summary},
              open("results.json", "w"), indent=1)
    print("\nlowest zero-false-idle threshold per model:", summary)


if __name__ == "__main__":
    main()
